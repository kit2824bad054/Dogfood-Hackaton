"""Forms for authentication and user registration."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

# Allowed roles selectable during public signup (Admin role is excluded)
SIGNUP_ROLE_CHOICES = [
    (User.Role.PARTICIPANT, 'Participant'),
    (User.Role.JUDGE, 'Judge'),
    (User.Role.ORGANIZER, 'Organizer'),
]


class SignUpForm(forms.ModelForm):
    """
    User registration form with email, username, password, password confirmation,
    and self-selectable role (Participant, Judge, Organizer).
    Admin role cannot be self-selected and must be assigned via Django admin.
    """

    email = forms.EmailField(
        required=True,
        help_text="Required. A valid email address."
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label="Password",
        help_text="Password must satisfy standard validation rules."
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        label="Confirm password",
        help_text="Enter the same password as above for verification."
    )
    role = forms.ChoiceField(
        choices=SIGNUP_ROLE_CHOICES,
        required=False,
        initial=User.Role.PARTICIPANT,
        help_text="Select your role: Participant, Judge, or Organizer."
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'role')

    def clean_role(self):
        """Ensure role is within allowed signup choices and default to participant if empty."""
        role = self.cleaned_data.get('role')
        if not role:
            return User.Role.PARTICIPANT

        allowed = [choice[0] for choice in SIGNUP_ROLE_CHOICES]
        if role not in allowed:
            raise forms.ValidationError(
                "Invalid role selected. 'Admin' cannot be selected during signup."
            )
        return role

    def clean(self):
        """Validate that passwords match and pass Django password validators."""
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm:
            if password != password_confirm:
                self.add_error("password_confirm", "Passwords do not match.")
            else:
                # Run Django built-in password validators
                validate_password(password)

        return cleaned_data

    def save(self, commit=True):
        """Hash the password and save the new user."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        # Ensure role defaults to participant if empty
        if not user.role:
            user.role = User.Role.PARTICIPANT
        if commit:
            user.save()
        return user
