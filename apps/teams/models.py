"""Models and business logic constraints for team formation."""

import secrets
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.events.models import Event


def generate_invite_code():
    """Generate a cryptographically secure, url-safe short token."""
    return secrets.token_urlsafe(8)


class Team(models.Model):
    """
    Represents a team of participants formed for a specific hackathon event.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='teams',
        help_text="The hackathon event this team is participating in."
    )
    name = models.CharField(
        max_length=150,
        help_text="Unique team name within this hackathon event."
    )
    invite_code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        help_text="Unique shareable token used by teammates to join."
    )
    max_members = models.PositiveIntegerField(
        default=4,
        help_text="Maximum allowed team members."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_teams',
        help_text="The participant who founded the team."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'name'],
                name='unique_team_name_per_event'
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.event.name})"

    def save(self, *args, **kwargs):
        """Auto-generate non-guessable invite code upon team creation."""
        if not self.invite_code:
            code = generate_invite_code()
            while Team.objects.filter(invite_code=code).exists():
                code = generate_invite_code()
            self.invite_code = code
        super().save(*args, **kwargs)

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def is_full(self):
        return self.member_count >= self.max_members

    def has_member(self, user):
        if not (user and user.is_authenticated):
            return False
        return self.memberships.filter(user=user).exists()


class TeamMembership(models.Model):
    """
    Represents a participant's membership in a team.
    """
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'user'],
                name='unique_team_membership'
            )
        ]
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user.username} -> {self.team.name}"

    def clean(self):
        super().clean()
        if hasattr(self, 'team') and hasattr(self, 'user') and self.team_id and self.user_id:
            existing = TeamMembership.objects.filter(
                user=self.user,
                team__event=self.team.event
            )
            if self.pk:
                existing = existing.exclude(pk=self.pk)
            if existing.exists():
                existing_team = existing.first().team
                raise ValidationError(
                    f"User '{self.user.username}' is already a member of team '{existing_team.name}' "
                    f"in event '{self.team.event.name}'. Each participant can only join one team per event."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# Reusable Business Logic Services & Constraints

def user_has_team_in_event(user, event):
    """Return True if user is already a member of any team in the given event."""
    if not (user and user.is_authenticated and event):
        return False
    return TeamMembership.objects.filter(user=user, team__event=event).exists()


def get_user_team_for_event(user, event):
    """Return the Team instance the user belongs to for the given event, or None."""
    if not (user and user.is_authenticated and event):
        return None
    membership = TeamMembership.objects.filter(user=user, team__event=event).select_related('team').first()
    return membership.team if membership else None


def can_user_join_event_team(user, event, raise_exception=False):
    """
    Reusable validation utility checking whether a user is eligible to create or join a team.

    Checks:
    1. User role must be 'participant'.
    2. Event registration must be open (event.is_registration_open).
    3. User must not already belong to any team for this event (one-team-per-event constraint).

    Returns:
        (is_allowed: bool, error_message: str | None)
    Raises:
        ValidationError if raise_exception is True and check fails.
    """
    if getattr(user, 'role', None) != 'participant':
        msg = "Only participants can create or join hackathon teams."
        if raise_exception:
            raise ValidationError(msg)
        return False, msg

    if not event.is_registration_open:
        msg = "Registration for this hackathon has closed. Team creation and joins are no longer permitted."
        if raise_exception:
            raise ValidationError(msg)
        return False, msg

    if user_has_team_in_event(user, event):
        current_team = get_user_team_for_event(user, event)
        team_name = current_team.name if current_team else "another team"
        msg = f"You are already a member of team '{team_name}' in this event. Each participant can only join one team per event."
        if raise_exception:
            raise ValidationError(msg)
        return False, msg

    return True, None


def validate_user_can_join_event_team(user, event, raise_exception=False):
    """Alias for can_user_join_event_team."""
    return can_user_join_event_team(user, event, raise_exception=raise_exception)
