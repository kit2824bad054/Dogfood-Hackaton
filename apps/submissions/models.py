"""
Models for project submissions in the Dogfood Platform.

Phase 5: Submissions model managing project metadata, repository/demo URLs,
tracks, submission status (draft vs submitted), and deadline enforcement.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.events.models import Event, Track
from apps.teams.models import Team


class Submission(models.Model):
    """
    Project submission for a hackathon team.
    
    Each team has exactly one submission (OneToOneField).
    The submission starts as a 'draft' and can be collaboratively edited
    by any team member before the submission deadline.
    Once submitted, further edits are blocked unless un-submitted prior to deadline.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'

    team = models.OneToOneField(
        Team,
        on_delete=models.CASCADE,
        related_name='submission',
        help_text="The team submitting this project (one submission per team)."
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='submissions',
        help_text="Denormalized from team.event for query convenience."
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submissions',
        help_text="Optional track category selected for this submission."
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        help_text="Project title."
    )
    description = models.TextField(
        blank=True,
        help_text="Comprehensive project description and technical overview."
    )
    repo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Public repository URL (GitHub, GitLab, etc.)."
    )
    demo_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Optional live demo URL, hosted app, or video walkthrough."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text="State of the submission: draft or submitted."
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when project was officially marked as submitted."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at', '-updated_at']

    def __str__(self):
        name = self.title or f"Draft ({self.team.name})"
        return f"{name} - {self.team.name} [{self.get_status_display()}]"

    def clean(self):
        super().clean()
        if hasattr(self, 'team') and self.team_id:
            self.event = self.team.event

        # Ensure selected track belongs to this event
        if self.track_id and self.event_id and self.track.event_id != self.event_id:
            raise ValidationError({'track': "The selected track does not belong to this event."})

        # Required fields check for final submission
        if self.status == self.Status.SUBMITTED:
            errors = {}
            if not (self.title and self.title.strip()):
                errors['title'] = "Project title is required for final submission."
            if not (self.description and self.description.strip()):
                errors['description'] = "Project description is required for final submission."
            if not (self.repo_url and self.repo_url.strip()):
                errors['repo_url'] = "Repository URL is required for final submission."
            if errors:
                raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Auto-denormalize event from team
        if hasattr(self, 'team') and self.team_id:
            self.event = self.team.event

        # Handle submitted_at timestamp
        if self.status == self.Status.SUBMITTED:
            if not self.submitted_at:
                self.submitted_at = timezone.now()
        elif self.status == self.Status.DRAFT:
            self.submitted_at = None

        super().save(*args, **kwargs)

    @property
    def is_submitted(self):
        return self.status == self.Status.SUBMITTED

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT
