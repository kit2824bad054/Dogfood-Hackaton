"""
Domain services and algorithms for judging management.

Phase 7:
- Judge assignment algorithm with conflict-of-interest exclusion and workload balancing
- Cross-judge score normalization (z-score adjustment against harsh/lenient judge bias)
- Weighted final score computation and event rankings calculation
- Judging progress metrics for organizer oversight
"""

import math
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.events.models import Event
from apps.submissions.models import Submission
from apps.teams.models import TeamMembership
from .models import JudgeAssignment, Rubric, Score

User = get_user_model()


def assign_judges_to_event(event, judges_per_submission=3, clear_existing=False):
    """
    Round-robin judge assignment algorithm for an event.

    Rules:
    - Only submissions with status='submitted' are assigned.
    - Each submission is assigned up to `judges_per_submission` judges.
    - Judges receive a balanced workload across the event.
    - Conflict of Interest: A judge who is a member of a submission's team is EXCLUDED.
    - Gracefully handles fewer judges than requested without crashing.
    - Idempotent: Re-running does not duplicate existing assignments.
    - If clear_existing=True, clears current assignments and re-assigns cleanly.
    """
    # 1. Validate that the event has a valid rubric
    Rubric.validate_event_rubric(event)

    warnings = []

    # 2. Get submitted projects
    submissions = list(
        Submission.objects.filter(event=event, status=Submission.Status.SUBMITTED)
        .select_related('team')
        .order_by('id')
    )
    if not submissions:
        return {
            'success': True,
            'assigned_count': 0,
            'submissions_count': 0,
            'judges_count': 0,
            'warnings': ["No submitted projects found for this event."]
        }

    # 3. Handle clear_existing flag
    if clear_existing:
        JudgeAssignment.objects.filter(submission__event=event).delete()

    # 4. Get all eligible judges (users with role='judge')
    judges = list(User.objects.filter(role=User.Role.JUDGE).order_by('id'))
    if not judges:
        # Also fall back to admin if no judges exist
        judges = list(User.objects.filter(role=User.Role.ADMIN).order_by('id'))
        if not judges:
            raise ValidationError("No users with the 'judge' role found on the platform.")
        warnings.append("No users with 'judge' role found; platform administrators were used as fallback.")

    if len(judges) < judges_per_submission:
        warnings.append(
            f"Requested {judges_per_submission} judges per project, but only {len(judges)} "
            f"eligible judges are registered. Projects will receive at most {len(judges)} judges."
        )

    # 5. Track existing workloads per judge for this event
    judge_workload = {
        j.id: JudgeAssignment.objects.filter(judge=j, submission__event=event).count()
        for j in judges
    }

    new_assignments = []

    with transaction.atomic():
        for sub in submissions:
            # Query existing assignments for this submission
            current_judge_ids = set(
                JudgeAssignment.objects.filter(submission=sub).values_list('judge_id', flat=True)
            )

            # Determine conflict-of-interest user IDs (team members for this submission)
            team_member_ids = set(
                TeamMembership.objects.filter(team=sub.team).values_list('user_id', flat=True)
            )

            # Eligible judges for this project:
            # - Not already assigned to this project
            # - Not a member of this project's team
            eligible_judges = [
                j for j in judges
                if j.id not in current_judge_ids and j.id not in team_member_ids
            ]

            needed_slots = max(0, judges_per_submission - len(current_judge_ids))
            if needed_slots == 0:
                continue

            if len(eligible_judges) < needed_slots:
                warnings.append(
                    f"Submission '{sub.title}' (Team: {sub.team.name}) could only be assigned "
                    f"{len(current_judge_ids) + len(eligible_judges)} judges due to team conflicts or judge capacity."
                )

            # Sort eligible judges by workload (ascending) so least-loaded judges get picked first
            eligible_judges.sort(key=lambda j: (judge_workload[j.id], j.id))

            selected = eligible_judges[:needed_slots]
            for judge in selected:
                assignment = JudgeAssignment(
                    judge=judge,
                    submission=sub,
                    status=JudgeAssignment.Status.NOT_STARTED,
                )
                new_assignments.append(assignment)
                judge_workload[judge.id] += 1

        if new_assignments:
            JudgeAssignment.objects.bulk_create(new_assignments)

    total_assignments = JudgeAssignment.objects.filter(submission__event=event).count()

    return {
        'success': True,
        'new_assigned_count': len(new_assignments),
        'total_assigned_count': total_assignments,
        'submissions_count': len(submissions),
        'judges_count': len(judges),
        'warnings': warnings,
    }


def normalize_event_scores(event):
    """
    Cross-judge score normalization using z-scores.

    Algorithm:
    For each rubric criterion in the event:
    1. For each judge who scored that criterion, compute:
       - mean score (mu_j)
       - standard deviation (sigma_j)
    2. Edge Case: If a judge only evaluated one submission (n <= 1) or sigma_j == 0,
       there is no meaningful standard deviation -> fall back to their raw score.
    3. For judges with n > 1 and sigma_j > 0, convert raw score to z-score:
       z = (raw_score - mu_j) / sigma_j
    4. Rescale z-score back to the criterion's scale [0, max_score] using the
       event-wide population mean and standard deviation across all judges:
       rescaled = mu_all + (z * sigma_all)
       clamped to [0, max_score] and rounded to 2 decimal places.
    5. Save normalized_score on the Score model without overwriting raw_score.
    """
    criteria = event.rubric_criteria.all()
    updated_scores_count = 0

    with transaction.atomic():
        for criterion in criteria:
            # Fetch all scores for this criterion in this event
            scores_qs = Score.objects.filter(
                rubric_criterion=criterion,
                assignment__submission__event=event
            ).select_related('assignment__judge')

            scores_list = list(scores_qs)
            if not scores_list:
                continue

            # Compute overall population parameters across all judges for this criterion
            all_raw = [float(s.raw_score) for s in scores_list]
            n_all = len(all_raw)
            mu_all = sum(all_raw) / n_all
            if n_all > 1:
                var_all = sum((x - mu_all) ** 2 for x in all_raw) / (n_all - 1)
                sigma_all = math.sqrt(var_all)
            else:
                sigma_all = 0.0

            # Group scores by judge
            judge_scores = {}
            for s in scores_list:
                j_id = s.assignment.judge_id
                judge_scores.setdefault(j_id, []).append(s)

            # Compute per-judge normalization
            for j_id, j_scores in judge_scores.items():
                raw_values = [float(s.raw_score) for s in j_scores]
                n_j = len(raw_values)

                # Edge case: A judge with only 1 score (or zero variance) has no meaningful std dev
                if n_j <= 1:
                    for s in j_scores:
                        s.normalized_score = s.raw_score
                        s.save(update_fields=['normalized_score'])
                        updated_scores_count += 1
                    continue

                mu_j = sum(raw_values) / n_j
                var_j = sum((x - mu_j) ** 2 for x in raw_values) / (n_j - 1)
                sigma_j = math.sqrt(var_j)

                if sigma_j == 0.0:
                    # Judge gave the exact same score to all projects -> fall back to raw score
                    for s in j_scores:
                        s.normalized_score = s.raw_score
                        s.save(update_fields=['normalized_score'])
                        updated_scores_count += 1
                    continue

                # Standard case: Compute z-score and rescale back to [0, max_score]
                for s in j_scores:
                    raw_val = float(s.raw_score)
                    z = (raw_val - mu_j) / sigma_j

                    if sigma_all > 0:
                        rescaled = mu_all + (z * sigma_all)
                    else:
                        rescaled = mu_all

                    # Clamp to [0, max_score]
                    clamped = max(0.0, min(float(criterion.max_score), rescaled))
                    s.normalized_score = Decimal(str(round(clamped, 2)))
                    s.save(update_fields=['normalized_score'])
                    updated_scores_count += 1

    return {
        'success': True,
        'updated_scores_count': updated_scores_count,
    }


def compute_submission_weighted_score(submission):
    """
    Compute a single submission's final weighted score.

    Formula:
    For each rubric criterion:
      average_normalized_score = average of normalized_scores from all judges who scored this criterion
      criterion_contribution = average_normalized_score * (criterion.weight / 100)
    final_weighted_score = sum(criterion_contribution) across all criteria
    """
    event = submission.event
    criteria = event.rubric_criteria.all()
    if not criteria.exists():
        return Decimal('0.00')

    total_weighted_score = Decimal('0.00')

    for criterion in criteria:
        scores = Score.objects.filter(
            assignment__submission=submission,
            rubric_criterion=criterion,
            assignment__status=JudgeAssignment.Status.COMPLETED
        )

        if not scores.exists():
            # If not yet completed, check any recorded scores
            scores = Score.objects.filter(
                assignment__submission=submission,
                rubric_criterion=criterion
            )

        if scores.exists():
            # Use normalized_score if available, else raw_score
            norm_avg = scores.aggregate(
                avg=Avg('normalized_score')
            )['avg']
            if norm_avg is None:
                norm_avg = scores.aggregate(avg=Avg('raw_score'))['avg'] or Decimal('0.00')

            weight_factor = criterion.weight / Decimal('100.00')
            total_weighted_score += (norm_avg * weight_factor)

    return round(total_weighted_score, 2)


def get_event_rankings(event):
    """
    Generate the normalized final rankings for all submitted projects in an event.

    Returns a list of dicts ordered by final_weighted_score descending:
    [
      {
        'rank': 1,
        'submission': <Submission>,
        'final_weighted_score': Decimal('8.75'),
        'judge_count': 3,
        'completed_judge_count': 3,
        'is_fully_judged': True,
      },
      ...
    ]
    """
    # Ensure scores are normalized first
    normalize_event_scores(event)

    submissions = Submission.objects.filter(
        event=event,
        status=Submission.Status.SUBMITTED
    ).select_related('team', 'track')

    ranked_items = []
    for sub in submissions:
        assignments = sub.judge_assignments.all()
        judge_count = assignments.count()
        completed_judge_count = assignments.filter(status=JudgeAssignment.Status.COMPLETED).count()

        final_score = compute_submission_weighted_score(sub)

        ranked_items.append({
            'submission': sub,
            'final_weighted_score': final_score,
            'judge_count': judge_count,
            'completed_judge_count': completed_judge_count,
            'is_fully_judged': (judge_count > 0 and completed_judge_count >= judge_count),
        })

    # Sort descending by final weighted score, then by completed judge count
    ranked_items.sort(key=lambda x: (x['final_weighted_score'], x['completed_judge_count']), reverse=True)

    # Assign ranks (1-indexed)
    for idx, item in enumerate(ranked_items, start=1):
        item['rank'] = idx

    return ranked_items


def get_event_judging_progress(event):
    """
    Compute progress metrics for an event's judging phase.

    Returns:
    {
      'total_submissions': int,
      'fully_scored_submissions': int,
      'pending_submissions': int,
      'overall_completion_pct': float,
      'total_assignments': int,
      'completed_assignments': int,
      'judge_metrics': [
         {
           'judge': <User>,
           'total_assigned': int,
           'completed': int,
           'pending': int,
           'completion_pct': float,
         },
         ...
      ]
    }
    """
    submissions = Submission.objects.filter(event=event, status=Submission.Status.SUBMITTED)
    total_submissions = submissions.count()

    assignments = JudgeAssignment.objects.filter(submission__event=event).select_related('judge', 'submission')
    total_assignments = assignments.count()
    completed_assignments = assignments.filter(status=JudgeAssignment.Status.COMPLETED).count()

    # Per-submission completion
    fully_scored_count = 0
    for sub in submissions:
        sub_assignments = sub.judge_assignments.all()
        if sub_assignments.exists() and not sub_assignments.exclude(status=JudgeAssignment.Status.COMPLETED).exists():
            fully_scored_count += 1

    pending_submissions = total_submissions - fully_scored_count
    overall_pct = (completed_assignments / total_assignments * 100.0) if total_assignments > 0 else 0.0

    # Per-judge breakdown
    judges_map = {}
    for a in assignments:
        j = a.judge
        if j.id not in judges_map:
            judges_map[j.id] = {
                'judge': j,
                'total_assigned': 0,
                'completed': 0,
            }
        judges_map[j.id]['total_assigned'] += 1
        if a.status == JudgeAssignment.Status.COMPLETED:
            judges_map[j.id]['completed'] += 1

    judge_metrics = []
    for data in judges_map.values():
        total = data['total_assigned']
        comp = data['completed']
        pct = (comp / total * 100.0) if total > 0 else 0.0
        judge_metrics.append({
            'judge': data['judge'],
            'total_assigned': total,
            'completed': comp,
            'pending': total - comp,
            'completion_pct': round(pct, 1),
        })

    judge_metrics.sort(key=lambda x: x['completion_pct'], reverse=True)

    return {
        'total_submissions': total_submissions,
        'fully_scored_submissions': fully_scored_count,
        'pending_submissions': pending_submissions,
        'overall_completion_pct': round(overall_pct, 1),
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'judge_metrics': judge_metrics,
    }
