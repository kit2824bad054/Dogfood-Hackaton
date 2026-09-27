"""Forms and inline formsets for event creation and editing."""

from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import Event, Track, Prize


class EventForm(forms.ModelForm):
    """Form for creating and editing hackathon events."""

    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Start date and time."
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="End date and time."
    )
    registration_deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Registration cutoff date and time."
    )
    submission_deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text="Project submission deadline."
    )

    class Meta:
        model = Event
        fields = (
            'name',
            'description',
            'start_date',
            'end_date',
            'registration_deadline',
            'submission_deadline',
            'status',
            'gallery_enabled',
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date >= end_date:
            self.add_error('end_date', "End date must be strictly after start date.")

        # Enforcement: Core dates cannot be modified after event is open and started
        if self.instance and self.instance.pk:
            original = Event.objects.get(pk=self.instance.pk)
            # If the event was already open and its original start_date has passed
            if original.status == Event.Status.OPEN and original.start_date <= timezone.now():
                if start_date and start_date != original.start_date:
                    self.add_error(
                        'start_date',
                        "Cannot modify start date after the event has opened and started."
                    )
                submission_deadline = cleaned_data.get('submission_deadline')
                if submission_deadline and submission_deadline != original.submission_deadline:
                    self.add_error(
                        'submission_deadline',
                        "Cannot modify submission deadline after the event has opened and started."
                    )

        return cleaned_data


# Inline formsets for managing tracks and prizes alongside the event
TrackFormSet = inlineformset_factory(
    Event,
    Track,
    fields=('name', 'description'),
    extra=2,
    can_delete=True,
    widgets={
        'name': forms.TextInput(attrs={'placeholder': 'Track Title (e.g. AI / Open Innovation)'}),
        'description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Track description (optional)'}),
    }
)

PrizeFormSet = inlineformset_factory(
    Event,
    Prize,
    fields=('title', 'description', 'rank'),
    extra=2,
    can_delete=True,
    widgets={
        'title': forms.TextInput(attrs={'placeholder': 'Prize Name (e.g. 1st Place)'}),
        'description': forms.TextInput(attrs={'placeholder': 'Amount/Reward (e.g. ₹80,000)'}),
        'rank': forms.NumberInput(attrs={'min': 1, 'style': 'width: 80px;'}),
    }
)
