"""
Forms for project submissions.
"""

from django import forms
from apps.events.models import Track
from .models import Submission


class SubmissionForm(forms.ModelForm):
    """
    Form for creating and editing a team's project submission draft.
    """

    class Meta:
        model = Submission
        fields = ['title', 'description', 'repo_url', 'demo_url', 'track']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Autonomous Agent Platform',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Describe your project, architecture, core innovations, and technologies used...',
            }),
            'repo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://github.com/organization/project',
            }),
            'demo_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://demo.example.com (optional)',
            }),
            'track': forms.Select(attrs={
                'class': 'form-control',
            }),
        }
        labels = {
            'title': 'Project Title',
            'description': 'Project Overview & Details',
            'repo_url': 'Source Code Repository URL',
            'demo_url': 'Live Demo / Video URL (Optional)',
            'track': 'Hackathon Track / Category',
        }

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        if event:
            self.fields['track'].queryset = Track.objects.filter(event=event)
        elif self.instance and self.instance.pk and self.instance.event:
            self.fields['track'].queryset = Track.objects.filter(event=self.instance.event)
        self.fields['track'].empty_label = "-- Select a Track (Optional) --"
