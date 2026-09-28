"""
Models for community voting, comments, anti-abuse controls, and audit trails.

Phase 8 / T3:
- Vote: 1-5 star community rating per participant per submission with update-on-revote
- Comment: Public feedback with duplicate detection flags and organizer soft-hiding
- EventRegistration: Explicit participant registration tracking for anti-Sybil protection
- AuditLog: Complete chronological record of votes, changes, comments, moderation, and rate-limits
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class EventRegistration(models.Model):
    """
    Explicit event participant registration record.
    Used for participant-only verification against Sybil abuse.
    """
    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='registrations',
        help_text="Event the user is registered for."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_registrations',
        help_text="Registered participant."
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'user'],
                name='unique_event_registration'
            )
        ]
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.user.username} registered for {self.event.name}"


class Vote(models.Model):
    """
    Community peer vote on a hackathon submission.
    Provides a 1-5 star rating value.
    Re-voting updates the existing row instead of creating duplicates.
    """
    submission = models.ForeignKey(
        'submissions.Submission',
        on_delete=models.CASCADE,
        related_name='votes',
        help_text="Submission being evaluated."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_votes',
        help_text="Participant who cast the vote."
    )
    value = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating score from 1 (lowest) to 5 (highest) stars."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['submission', 'user'],
                name='unique_vote_per_submission_user'
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} -> {self.submission.title}: {self.value}★"

    def clean(self):
        super().clean()
        if self.value < 1 or self.value > 5:
            raise ValidationError({'value': "Vote value must be between 1 and 5."})


class Comment(models.Model):
    """
    Community discussion comment on a hackathon submission.
    Supports organizer moderation (soft-hide) and duplicate detection flags.
    """
    submission = models.ForeignKey(
        'submissions.Submission',
        on_delete=models.CASCADE,
        related_name='comments',
        help_text="Submission being discussed."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='community_comments',
        help_text="Author of the comment."
    )
    body = models.TextField(help_text="Comment text content.")
    created_at = models.DateTimeField(auto_now_add=True)
    is_hidden = models.BooleanField(
        default=False,
        help_text="Soft-hidden by organizer for moderation. Remains in database for audit."
    )
    is_flagged_duplicate = models.BooleanField(
        default=False,
        help_text="Flagged as a repeated/near-identical comment for organizer review."
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='hidden_community_comments',
        help_text="Organizer/Admin who hid this comment."
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        status = " [HIDDEN]" if self.is_hidden else ""
        return f"Comment by {self.user.username} on {self.submission.title}{status}"


class AuditLog(models.Model):
    """
    Tamper-evident audit trail capturing all community interactions:
    vote casts, vote changes, comment postings, comment moderation, and rate limits.
    """
    class Action(models.TextChoices):
        VOTE_CAST = 'vote_cast', 'Vote Cast'
        VOTE_CHANGED = 'vote_changed', 'Vote Changed'
        COMMENT_POSTED = 'comment_posted', 'Comment Posted'
        COMMENT_HIDDEN = 'comment_hidden', 'Comment Hidden'
        COMMENT_UNHIDDEN = 'comment_unhidden', 'Comment Unhidden'
        RATE_LIMIT_TRIGGERED = 'rate_limit_triggered', 'Rate Limit Triggered'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='community_audit_logs',
        help_text="User who initiated the action (or null for unauthenticated/system)."
    )
    action = models.CharField(
        max_length=50,
        choices=Action.choices,
        help_text="Type of community action recorded."
    )
    target_submission = models.ForeignKey(
        'submissions.Submission',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='community_audit_logs',
        help_text="Target submission affected by this action."
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured context (old/new score, duplicate flag, client details)."
    )

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.get_action_display()} by {username}"
