"""
URL configuration for the judging and evaluation app.
Phase 7: Tier 2 (T2) Judging workflows, dashboards, scoring interfaces, and CSV exports.
"""

from django.urls import path
from . import views

urlpatterns = [
    # Judge workflow
    path('judging/', views.judge_dashboard_view, name='judge_dashboard'),
    path('judging/assignments/<int:assignment_id>/', views.judge_score_submission_view, name='judge_score_submission'),

    # Organizer & Admin progress & management
    path('judging/assignments/<int:assignment_id>/reopen/', views.reopen_assignment_view, name='reopen_assignment'),
    path('judging/events/<slug:event_slug>/progress/', views.event_judging_progress_view, name='event_judging_progress'),
    path('judging/events/<slug:event_slug>/assign/', views.event_assign_judges_view, name='event_assign_judges'),
    path('judging/events/<slug:event_slug>/normalize/', views.event_normalize_scores_view, name='event_normalize_scores'),
    path('judging/events/<slug:event_slug>/rubric/', views.event_rubric_manage_view, name='event_rubric_manage'),

    # CSV Exports
    path('judging/events/<slug:event_slug>/export/raw/', views.export_raw_scores_csv_view, name='export_raw_scores_csv'),
    path('judging/events/<slug:event_slug>/export/rankings/', views.export_rankings_csv_view, name='export_rankings_csv'),
]
