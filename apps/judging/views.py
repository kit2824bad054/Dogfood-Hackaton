"""
Views for judging, scoring, progress tracking, and CSV exports.

Phase 7:
- Judge dashboard listing only assigned submissions
- Isolated scoring interface (cannot access unassigned projects, cannot see other judges' scores)
- Organizer judge progress dashboard
- Organizer judge assignment trigger
- Organizer normalization calculation trigger
- CSV export for raw scores and final normalized rankings
"""

import csv
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.decorators import role_required
from apps.events.models import Event
from apps.submissions.models import Submission
from .models import JudgeAssignment, Rubric, Score
from .services import (
    assign_judges_to_event,
    get_event_judging_progress,
    get_event_rankings,
    normalize_event_scores,
)


# =============================================================================
# 1. JUDGE VIEWS (Strict Role Isolation)
# =============================================================================

@role_required('judge', 'admin')
def judge_dashboard_view(request):
    """
    Judge dashboard listing all submissions assigned to the logged-in judge.

    Strict Isolation:
    - Queries ONLY JudgeAssignment records where judge = request.user.
    - Cannot see unassigned projects or other judges' evaluations.
    """
    assignments = (
        JudgeAssignment.objects.filter(judge=request.user)
        .select_related('submission__event', 'submission__team', 'submission__track')
        .order_by('-assigned_at')
    )

    total_count = assignments.count()
    completed_count = assignments.filter(status=JudgeAssignment.Status.COMPLETED).count()
    in_progress_count = assignments.filter(status=JudgeAssignment.Status.IN_PROGRESS).count()
    not_started_count = assignments.filter(status=JudgeAssignment.Status.NOT_STARTED).count()

    context = {
        'assignments': assignments,
        'total_count': total_count,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'not_started_count': not_started_count,
    }
    return render(request, 'judging/judge_dashboard.html', context)


@login_required
def judge_score_submission_view(request, assignment_id):
    """
    Evaluation interface for a single assigned submission.

    Strict Isolation Enforcement:
    - A judge can ONLY view/score assignments where assignment.judge == request.user.
    - Attempting to access an unassigned project raises HTTP 403 Forbidden.
    - Query-level isolation: Only scores for THIS assignment are retrieved.
      A judge NEVER sees other judges' scores or comments for the same submission.

    Scoring Workflow:
    - Save Draft: Allows partial scores (saves status as 'in_progress').
    - Submit Complete: Strictly validates that EVERY rubric criterion has a valid score.
      Once complete, scores become read-only to prevent post-submission tampering.
    """
    assignment = get_object_or_404(
        JudgeAssignment.objects.select_related(
            'judge',
            'submission__event',
            'submission__team',
            'submission__track'
        ),
        id=assignment_id
    )

    # Security check: User must be the assigned judge (or platform admin)
    is_admin = getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser
    if not is_admin and assignment.judge != request.user:
        raise PermissionDenied("Access denied. You are not assigned to evaluate this submission.")

    submission = assignment.submission
    event = submission.event
    rubric_criteria = event.rubric_criteria.all()

    # Query only the logged-in judge's scores for this assignment
    existing_scores = {
        score.rubric_criterion_id: score
        for score in Score.objects.filter(assignment=assignment)
    }

    # If assignment is already completed, render read-only view
    if assignment.is_completed and not is_admin:
        return render(request, 'judging/score_readonly.html', {
            'assignment': assignment,
            'submission': submission,
            'event': event,
            'rubric_criteria': rubric_criteria,
            'existing_scores': existing_scores,
        })

    if request.method == 'POST':
        action = request.POST.get('action', 'save_draft')
        errors = {}
        scores_to_save = []

        for criterion in rubric_criteria:
            raw_val = request.POST.get(f'score_{criterion.id}', '').strip()
            comment_val = request.POST.get(f'comment_{criterion.id}', '').strip()

            if not raw_val:
                if action == 'submit_complete':
                    errors[criterion.id] = f"Score is required for '{criterion.name}' to complete evaluation."
                continue

            try:
                score_num = Decimal(raw_val)
            except Exception:
                errors[criterion.id] = "Invalid score format. Please enter a valid number."
                continue

            if score_num < Decimal('0'):
                errors[criterion.id] = "Score cannot be negative."
                continue

            if score_num > criterion.max_score:
                errors[criterion.id] = f"Score exceeds maximum allowable score of {criterion.max_score}."
                continue

            scores_to_save.append({
                'criterion': criterion,
                'raw_score': score_num,
                'comment': comment_val,
            })

        # If complete submission was requested, verify that ALL criteria are scored
        if action == 'submit_complete':
            scored_criterion_ids = {item['criterion'].id for item in scores_to_save}
            for criterion in rubric_criteria:
                if criterion.id not in scored_criterion_ids and criterion.id not in errors:
                    errors[criterion.id] = f"Missing score for '{criterion.name}'."

        if errors:
            return render(request, 'judging/score_form.html', {
                'assignment': assignment,
                'submission': submission,
                'event': event,
                'rubric_criteria': rubric_criteria,
                'existing_scores': existing_scores,
                'errors': errors,
                'form_error': "Please correct the highlighted errors before proceeding.",
            }, status=400)

        # Save valid scores
        for item in scores_to_save:
            criterion = item['criterion']
            Score.objects.update_or_create(
                assignment=assignment,
                rubric_criterion=criterion,
                defaults={
                    'raw_score': item['raw_score'],
                    'comment': item['comment'],
                }
            )

        if action == 'submit_complete':
            assignment.status = JudgeAssignment.Status.COMPLETED
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=['status', 'completed_at'])
            messages.success(request, f"Scoring for '{submission.title}' successfully submitted and locked!")
            return redirect('judge_dashboard')
        else:
            assignment.status = JudgeAssignment.Status.IN_PROGRESS
            assignment.save(update_fields=['status'])
            messages.info(request, f"Draft evaluation for '{submission.title}' saved successfully.")
            return redirect('judge_score_submission', assignment_id=assignment.id)

    return render(request, 'judging/score_form.html', {
        'assignment': assignment,
        'submission': submission,
        'event': event,
        'rubric_criteria': rubric_criteria,
        'existing_scores': existing_scores,
    })


# =============================================================================
# 2. ORGANIZER / ADMIN VIEWS (Oversight, Progress, Reopen, CSV)
# =============================================================================

def _check_organizer_permission(request, event):
    """Ensure user is platform admin or the organizer who created the event."""
    is_admin = getattr(request.user, 'role', None) == 'admin' or request.user.is_superuser
    if not is_admin and event.created_by != request.user:
        raise PermissionDenied("You do not have permission to manage judging for this event.")


@role_required('organizer', 'admin')
def event_judging_progress_view(request, event_slug):
    """
    Organizer overview dashboard displaying judging progress, per-judge completion rates,
    and access to judge assignment, normalization, and CSV exports.
    """
    event = get_object_or_404(Event, slug=event_slug)
    _check_organizer_permission(request, event)

    progress = get_event_judging_progress(event)
    rankings = get_event_rankings(event)
    rubric_criteria = event.rubric_criteria.all()

    context = {
        'event': event,
        'progress': progress,
        'rankings': rankings,
        'rubric_criteria': rubric_criteria,
    }
    return render(request, 'judging/organizer_progress.html', context)


@role_required('organizer', 'admin')
def event_assign_judges_view(request, event_slug):
    """Trigger the round-robin judge assignment algorithm for an event."""
    event = get_object_or_404(Event, slug=event_slug)
    _check_organizer_permission(request, event)

    if request.method == 'POST':
        judges_per_sub = int(request.POST.get('n', 3))
        clear_existing = bool(request.POST.get('clear', False))

        try:
            result = assign_judges_to_event(
                event=event,
                judges_per_submission=judges_per_sub,
                clear_existing=clear_existing
            )
            for warning in result.get('warnings', []):
                messages.warning(request, warning)

            messages.success(
                request,
                f"Judge assignment complete! {result['new_assigned_count']} new assignment(s) created "
                f"across {result['submissions_count']} project(s)."
            )
        except ValidationError as e:
            messages.error(request, str(e.message if hasattr(e, 'message') else e))

    return redirect('event_judging_progress', event_slug=event.slug)


@role_required('organizer', 'admin')
def event_normalize_scores_view(request, event_slug):
    """Trigger cross-judge z-score normalization for an event."""
    event = get_object_or_404(Event, slug=event_slug)
    _check_organizer_permission(request, event)

    if request.method == 'POST':
        result = normalize_event_scores(event)
        messages.success(
            request,
            f"Score normalization calculated! {result['updated_scores_count']} score(s) adjusted."
        )

    return redirect('event_judging_progress', event_slug=event.slug)


@role_required('organizer', 'admin')
def reopen_assignment_view(request, assignment_id):
    """
    Organizer action to reopen a completed evaluation back to 'in_progress',
    allowing the judge to revise their scores.
    """
    assignment = get_object_or_404(
        JudgeAssignment.objects.select_related('submission__event'),
        id=assignment_id
    )
    _check_organizer_permission(request, assignment.submission.event)

    if request.method == 'POST':
        assignment.status = JudgeAssignment.Status.IN_PROGRESS
        assignment.completed_at = None
        assignment.save(update_fields=['status', 'completed_at'])
        messages.success(
            request,
            f"Assignment for Judge '{assignment.judge.username}' on project '{assignment.submission.title}' has been reopened."
        )

    return redirect('event_judging_progress', event_slug=assignment.submission.event.slug)


@role_required('organizer', 'admin')
def export_raw_scores_csv_view(request, event_slug):
    """
    Export all raw and normalized scores across all judges, submissions, and criteria as CSV.
    Restricted to organizer/admin role for this event only.
    """
    event = get_object_or_404(Event, slug=event_slug)
    _check_organizer_permission(request, event)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}_raw_scores.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Submission ID',
        'Project Title',
        'Team Name',
        'Judge Username',
        'Judge Email',
        'Rubric Criterion',
        'Max Score',
        'Criterion Weight (%)',
        'Raw Score',
        'Normalized Score',
        'Judge Comment',
        'Submitted At',
        'Assignment Status',
    ])

    scores = Score.objects.filter(
        assignment__submission__event=event
    ).select_related(
        'assignment__submission__team',
        'assignment__judge',
        'rubric_criterion'
    ).order_by('assignment__submission__id', 'rubric_criterion__id', 'assignment__judge__username')

    for s in scores:
        sub = s.assignment.submission
        writer.writerow([
            sub.id,
            sub.title,
            sub.team.name,
            s.assignment.judge.username,
            s.assignment.judge.email,
            s.rubric_criterion.name,
            s.rubric_criterion.max_score,
            s.rubric_criterion.weight,
            s.raw_score,
            s.normalized_score if s.normalized_score is not None else '',
            s.comment,
            s.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if s.submitted_at else '',
            s.assignment.get_status_display(),
        ])

    return response


@role_required('organizer', 'admin')
def export_rankings_csv_view(request, event_slug):
    """
    Export normalized final rankings as CSV.
    Columns: Rank, Submission ID, Project Title, Team Name, Track, Judge Count, Final Weighted Score, Fully Judged.
    Restricted to organizer/admin role for this event only.
    """
    event = get_object_or_404(Event, slug=event_slug)
    _check_organizer_permission(request, event)

    rankings = get_event_rankings(event)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{event.slug}_rankings.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Rank',
        'Submission ID',
        'Project Title',
        'Team Name',
        'Track',
        'Judges Assigned',
        'Judges Completed',
        'Final Weighted Score',
        'Fully Judged',
    ])

    for item in rankings:
        sub = item['submission']
        track_name = sub.track.name if sub.track else 'General'
        writer.writerow([
            item['rank'],
            sub.id,
            sub.title,
            sub.team.name,
            track_name,
            item['judge_count'],
            item['completed_judge_count'],
            item['final_weighted_score'],
            'Yes' if item['is_fully_judged'] else 'No',
        ])

    return response


# =============================================================================
# 3. RUBRIC MANAGEMENT VIEW (Organizer)
# =============================================================================

@role_required('organizer', 'admin')
def event_rubric_manage_view(request, event_slug):
    """
    View and edit rubric criteria for an event.
    Ensures that criteria weights sum to exactly 100%.
    """
    event = get_object_or_404(Event, slug=event_slug)
    _check_organizer_permission(request, event)

    criteria = event.rubric_criteria.all()
    total_weight = sum(c.weight for c in criteria) if criteria.exists() else Decimal('0.00')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'add_criterion':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            weight_val = request.POST.get('weight', '').strip()
            max_score_val = request.POST.get('max_score', '10').strip()

            if not name:
                messages.error(request, "Criterion name is required.")
                return redirect('event_rubric_manage', event_slug=event.slug)

            try:
                weight_dec = Decimal(weight_val)
                max_score_int = int(max_score_val)
            except Exception:
                messages.error(request, "Invalid weight or maximum score value.")
                return redirect('event_rubric_manage', event_slug=event.slug)

            try:
                Rubric.objects.create(
                    event=event,
                    name=name,
                    description=description,
                    weight=weight_dec,
                    max_score=max_score_int,
                )
                messages.success(request, f"Rubric criterion '{name}' added successfully.")
            except ValidationError as e:
                messages.error(request, str(e.message if hasattr(e, 'message') else e))

            return redirect('event_rubric_manage', event_slug=event.slug)

        elif action == 'delete_criterion':
            criterion_id = request.POST.get('criterion_id')
            Rubric.objects.filter(id=criterion_id, event=event).delete()
            messages.info(request, "Rubric criterion removed.")
            return redirect('event_rubric_manage', event_slug=event.slug)

    context = {
        'event': event,
        'criteria': criteria,
        'total_weight': total_weight,
        'is_valid_rubric': total_weight == Decimal('100.00'),
    }
    return render(request, 'judging/rubric_manage.html', context)
