from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager ensuring superusers are assigned the admin role by default."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model for the Dogfood Platform.

    Extends AbstractUser and introduces a platform role field:
    participant, judge, organizer, or admin.
    """

    class Role(models.TextChoices):
        PARTICIPANT = 'participant', 'Participant'
        JUDGE = 'judge', 'Judge'
        ORGANIZER = 'organizer', 'Organizer'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.PARTICIPANT,
        help_text="Role determining platform permissions."
    )

    objects = UserManager()

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def is_participant(self):
        return self.role == self.Role.PARTICIPANT

    @property
    def is_judge(self):
        return self.role == self.Role.JUDGE

    @property
    def is_organizer(self):
        return self.role == self.Role.ORGANIZER

    @property
    def is_role_admin(self):
        return self.role == self.Role.ADMIN
