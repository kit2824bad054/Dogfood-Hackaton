"""URL routing for team formation, joins, and roster management."""

from django.urls import path
from .views import (
    team_create_view,
    team_join_view,
    team_detail_view,
    team_remove_member_view,
    my_team_view,
)

urlpatterns = [
    path('events/<slug:event_slug>/teams/create/', team_create_view, name='team_create'),
    path('events/<slug:event_slug>/my-team/', my_team_view, name='my_team'),
    path('teams/join/', team_join_view, name='team_join_input'),
    path('teams/join/<str:invite_code>/', team_join_view, name='team_join_code'),
    path('teams/<int:team_id>/', team_detail_view, name='team_detail'),
    path('teams/<int:team_id>/remove/<int:user_id>/', team_remove_member_view, name='team_remove_member'),
]
