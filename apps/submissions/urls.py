"""
URL configuration for project submissions.
"""

from django.urls import path
from .views import (
    team_submission_status_view,
    submission_edit_view,
    submission_submit_view,
    submission_unsubmit_view,
    event_submissions_list_view,
    event_my_submission_redirect_view,
)

urlpatterns = [
    path('teams/<int:team_id>/submission/', team_submission_status_view, name='team_submission_status'),
    path('teams/<int:team_id>/submission/edit/', submission_edit_view, name='submission_edit'),
    path('teams/<int:team_id>/submission/submit/', submission_submit_view, name='submission_submit'),
    path('teams/<int:team_id>/submission/unsubmit/', submission_unsubmit_view, name='submission_unsubmit'),
    path('events/<slug:event_slug>/submissions/', event_submissions_list_view, name='event_submissions_list'),
    path('events/<slug:event_slug>/submission/', event_my_submission_redirect_view, name='event_my_submission'),
]
