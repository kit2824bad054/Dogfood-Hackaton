"""Models for event management in the Dogfood Platform."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Event(models.Model):
    """
    Hackathon event entity managing lifecycle, deadlines, tracks, and prizes.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    name = models.CharField(max_length=200, help_text="Name of the hackathon event.")
    slug = models.SlugField(max_length=250, unique=True, blank=True, help_text="Auto-generated URL identifier.")
    description = models.TextField(help_text="Detailed description and rules for the event.")
    start_date = models.DateTimeField(help_text="When the hackathon starts.")
    end_date = models.DateTimeField(help_text="When the hackathon officially concludes.")
    registration_deadline = models.DateTimeField(help_text="Last date and time for participants/teams to register.")
    submission_deadline = models.DateTimeField(help_text="Final deadline for submitting projects.")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text="Event state: Draft, Open, or Closed."
    )
    gallery_enabled = models.BooleanField(
        default=False,
        help_text="Controls whether submitted projects appear on the public gallery."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_events',
        help_text="Organizer or administrator who created the event."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Auto-generate unique slug from name if not provided."""
        if not self.slug:
            base_slug = slugify(self.name) or 'event'
            candidate = base_slug
            counter = 1
            while Event.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def is_registration_open(self):
        """
        Check if registration is currently open.

        Registration is open when:
        1. Event status is 'open'.
        2. Current server time is at or before registration_deadline.

        Phase 4 (teams & membership) will import and rely on this server-side
        to block team creation and registration actions after deadline.
        """
        if self.status != self.Status.OPEN:
            return False
        return timezone.now() <= self.registration_deadline

    @property
    def is_submission_open(self):
        """
        Check if project submissions are currently open.

        Submissions are open when:
        1. Event status is 'open'.
        2. Current server time is at or before submission_deadline.

        Phase 5 (submissions) will import and rely on this server-side
        to reject project submissions after the deadline.
        """
        if self.status != self.Status.OPEN:
            return False
        return timezone.now() <= self.submission_deadline


class Track(models.Model):
    """
    Sub-theme or category under an event (e.g. AI/ML, Web3, Social Impact).
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='tracks',
        help_text="Event to which this track belongs."
    )
    name = models.CharField(max_length=150, help_text="Track title.")
    description = models.TextField(blank=True, help_text="Specific requirements and guidelines for this track.")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.event.name}"


class Prize(models.Model):
    """
    Award or reward associated with an event.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='prizes',
        help_text="Event to which this prize belongs."
    )
    title = models.CharField(max_length=150, help_text="Prize title (e.g., '1st Place', 'Best UI').")
    description = models.CharField(max_length=255, help_text="Prize value or details (e.g., '₹80,000' or 'Cash + Swag').")
    rank = models.PositiveIntegerField(
        default=1,
        help_text="Ordering rank (1 for first place, 2 for second place, etc.)."
    )

    class Meta:
        ordering = ['rank', 'title']

    def __str__(self):
        return f"{self.title}: {self.description} ({self.event.name})"
