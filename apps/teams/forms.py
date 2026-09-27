"""Forms for team creation and joining via invite code."""

from django import forms
from .models import Team


class TeamCreateForm(forms.ModelForm):
    """Form used by a participant to create a new team for an event."""

    class Meta:
        model = Team
        fields = ('name', 'max_members')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Neural Pioneers'}),
            'max_members': forms.NumberInput(attrs={'min': 1, 'max': 10}),
        }

    def __init__(self, *args, event=None, **kwargs):
        self.event = event
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if self.event and Team.objects.filter(event=self.event, name__iexact=name).exists():
            raise forms.ValidationError(
                f"A team named '{name}' already exists in this hackathon. Please choose another name."
            )
        return name


class JoinInviteForm(forms.Form):
    """Form to enter an invite code manually."""
    invite_code = forms.CharField(
        max_length=32,
        required=True,
        label="Team Invite Code",
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 11-character code (e.g. Ab9z_kL1qP8)',
            'style': 'font-family: monospace; letter-spacing: 0.05em;'
        })
    )
