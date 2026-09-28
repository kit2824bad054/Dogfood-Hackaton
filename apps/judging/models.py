"""
Models for judging, rubrics, judge assignments, and scoring in the Dogfood Platform.

Phase 7: Tier 2 (T2) Rubrics with percentage weights, JudgeAssignment with conflict-of-interest
protection, and Score with raw & normalized score tracking.
"""

import secrets
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum

from apps.events.models import Event
from apps.submissions.models import Submission



class Rubric(models.Model):
    """
    Evaluation criterion for an event.
    The sum of weights across all criteria for an event must equal 100.00%.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='rubric_criteria',
        help_text="The event to which this evaluation rubric belongs."
    )
    name = models.CharField(
        max_length=200,
        help_text="Name of the rubric criterion (e.g. 'Tier Completion & Correctness')."
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed evaluation guidance and standards for judges."
    )
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage weight of this criterion (e.g. 40.00). Must sum to 100% per event."
    )
    max_score = models.PositiveIntegerField(
        default=10,
        help_text="Maximum raw rating score a judge can award (default: 10)."
    )

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'name'],
                name='unique_rubric_criterion_name_per_event'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.weight}%, max {self.max_score}) - {self.event.name}"

    def clean(self):
        super().clean()
        if self.weight is None or self.weight <= Decimal('0'):
            raise ValidationError({'weight': "Criterion weight must be strictly greater than 0."})
        if self.weight > Decimal('100.00'):
            raise ValidationError({'weight': "Criterion weight cannot exceed 100%."})

    def save(self, *args, validate_total=False, **kwargs):
        """
        Validate criterion and ensure event rubric weights do not exceed 100%.
        If validate_total=True, strictly enforces that the final sum equals 100%.
        """
        self.full_clean()

        # Calculate total weight for this event
        existing_weight = Rubric.objects.filter(event=self.event).exclude(pk=self.pk).aggregate(
            total=Sum('weight')
        )['total'] or Decimal('0')
        new_total = existing_weight + (self.weight or Decimal('0'))

        if new_total > Decimal('100.00'):
            raise ValidationError(
                f"Rubric criteria weights for event '{self.event.name}' cannot exceed 100.00%. "
                f"Attempted total would be {new_total}%."
            )

        if validate_total and new_total != Decimal('100.00'):
            raise ValidationError(
                f"Rubric criteria weights for event '{self.event.name}' must sum to exactly 100.00%. "
                f"Current total is {new_total}%."
            )

        super().save(*args, **kwargs)

    @classmethod
    def validate_event_rubric(cls, event):
        """
        Ensure the complete set of rubric criteria for an event sums to exactly 100%.
        Raises ValidationError if criteria are empty or sum != 100.
        """
        criteria = cls.objects.filter(event=event)
        if not criteria.exists():
            raise ValidationError(f"Event '{event.name}' has no rubric criteria defined.")

        total_weight = criteria.aggregate(total=Sum('weight'))['total'] or Decimal('0')
        if total_weight != Decimal('100.00'):
            raise ValidationError(
                f"Rubric criteria weights for event '{event.name}' must sum to exactly 100.00%. "
                f"Current sum: {total_weight}%."
            )
        return True


class JudgeAssignment(models.Model):
    """
    Assignment linking a Judge to a specific Submission for evaluation.
    Enforces that a judge is never assigned the same project twice.
    """

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Not Started'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'

    judge = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='judge_assignments',
        help_text="The judge assigned to evaluate this submission."
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name='judge_assignments',
        help_text="The submitted project to be judged."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
        help_text="Evaluation status: Not Started, In Progress, or Completed."
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_flagged_for_review = models.BooleanField(
        default=False,
        help_text="Flagged for organizer review (e.g. if judge was revoked after scoring)."
    )
    review_notes = models.TextField(
        blank=True,
        help_text="Organizer notes explaining flag reason."
    )


    class Meta:
        ordering = ['submission__event', 'submission', 'judge']
        constraints = [
            models.UniqueConstraint(
                fields=['judge', 'submission'],
                name='unique_judge_submission_assignment'
            )
        ]

    def __str__(self):
        return f"Judge {self.judge.username} -> {self.submission.title} [{self.get_status_display()}]"

    @property
    def is_completed(self):
        return self.status == self.Status.COMPLETED

    @property
    def is_in_progress(self):
        return self.status == self.Status.IN_PROGRESS

    @property
    def is_not_started(self):
        return self.status == self.Status.NOT_STARTED

    @property
    def scored_criteria_count(self):
        return self.scores.filter(raw_score__isnull=False).count()

    @property
    def total_criteria_count(self):
        return self.submission.event.rubric_criteria.count()

    def update_status_from_scores(self):
        """Update assignment status based on current scores."""
        total = self.total_criteria_count
        scored = self.scored_criteria_count

        if total > 0 and scored >= total:
            self.status = self.Status.COMPLETED
        elif scored > 0:
            self.status = self.Status.IN_PROGRESS
        else:
            self.status = self.Status.NOT_STARTED


class Score(models.Model):
    """
    A judge's score for a specific rubric criterion on an assigned submission.
    Stores both the judge's raw score and the normalized score (post cross-judge z-score adjustment).
    """
    assignment = models.ForeignKey(
        JudgeAssignment,
        on_delete=models.CASCADE,
        related_name='scores',
        help_text="The judge assignment this score belongs to."
    )
    rubric_criterion = models.ForeignKey(
        Rubric,
        on_delete=models.CASCADE,
        related_name='scores',
        help_text="The specific rubric criterion being rated."
    )
    raw_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Raw score awarded by the judge, bounded by rubric_criterion.max_score."
    )
    normalized_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Normalized score adjusted for judge harshness/leniency via z-score normalization."
    )
    comment = models.TextField(
        blank=True,
        help_text="Optional feedback or justification notes from the judge."
    )
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['assignment', 'rubric_criterion']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'rubric_criterion'],
                name='unique_score_per_assignment_criterion'
            )
        ]

    def __str__(self):
        norm = f" (norm: {self.normalized_score})" if self.normalized_score is not None else ""
        return f"{self.assignment.judge.username} on '{self.rubric_criterion.name}': {self.raw_score}/{self.rubric_criterion.max_score}{norm}"

    def clean(self):
        super().clean()
        if self.raw_score is not None:
            if self.raw_score < Decimal('0'):
                raise ValidationError({'raw_score': "Score cannot be negative."})
            if hasattr(self, 'rubric_criterion') and self.rubric_criterion_id:
                if self.raw_score > self.rubric_criterion.max_score:
                    raise ValidationError({
                        'raw_score': (
                            f"Score of {self.raw_score} exceeds maximum allowed score of "
                            f"{self.rubric_criterion.max_score} for '{self.rubric_criterion.name}'."
                        )
                    })
                # Check that criterion belongs to the same event as the assignment submission
                if self.assignment.submission.event_id != self.rubric_criterion.event_id:
                    raise ValidationError({
                        'rubric_criterion': "Rubric criterion does not belong to the submission's event."
                    })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


def generate_judge_invite_token():
    return secrets.token_urlsafe(24)


class EventJudge(models.Model):
    """
    Event-scoped judge invitation and acceptance record.
    Controls eligibility for being assigned submissions in an event.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        REVOKED = 'revoked', 'Revoked'

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='judge_invitations',
        help_text="The hackathon event this invitation is for."
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_judge_invitations',
        help_text="Organizer or admin who created the invitation."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='judge_invitations',
        help_text="The judge user invited or who accepted this invitation."
    )
    email = models.EmailField(
        blank=True,
        help_text="Optional target email address if the invitee does not have an account yet."
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_judge_invite_token,
        db_index=True,
        help_text="Cryptographically secure unique token for shareable invitation link."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Status of the invitation: pending, accepted, declined, revoked."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_event_judge_user'
            )
        ]

    def __str__(self):
        target = self.user.username if self.user else (self.email or f"Token:{self.token[:8]}")
        return f"Invite for {target} to {self.event.name} [{self.get_status_display()}]"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_accepted(self):
        return self.status == self.Status.ACCEPTED

    @property
    def is_declined(self):
        return self.status == self.Status.DECLINED

    @property
    def is_revoked(self):
        return self.status == self.Status.REVOKED

