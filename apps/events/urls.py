"""URL routing for event management."""

from django.urls import path
from .views import (
    event_list_view,
    event_create_view,
    event_detail_view,
    event_edit_view,
)

urlpatterns = [
    path('events/', event_list_view, name='event_list'),
    path('events/create/', event_create_view, name='event_create'),
    path('events/<slug:slug>/', event_detail_view, name='event_detail'),
    path('events/<slug:slug>/edit/', event_edit_view, name='event_edit'),
]
