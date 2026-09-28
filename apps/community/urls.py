from django.urls import path
from apps.community import views

urlpatterns = [
    # Voting & commenting write paths
    path('community/submissions/<int:submission_id>/vote/', views.cast_vote_view, name='community_vote'),
    path('community/submissions/<int:submission_id>/comment/', views.post_comment_view, name='community_comment'),

    # Comment moderation (organizers/admins)
    path('community/comments/<int:comment_id>/moderate/', views.moderate_comment_view, name='community_moderate_comment'),

    # Organizer audit log browser
    path('community/events/<slug:event_slug>/audit-logs/', views.audit_log_view, name='event_audit_logs'),
    path('community/audit-logs/', views.audit_log_view, name='all_audit_logs'),

    # Organizer event voting settings
    path('community/events/<slug:event_slug>/voting-settings/', views.manage_event_voting_view, name='event_voting_manage'),
]
