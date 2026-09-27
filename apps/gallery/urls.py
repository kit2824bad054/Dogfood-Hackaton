"""
URL configuration for the public project gallery.

Phase 6: Public gallery views and individual submission showcases.
"""

from django.urls import path
from . import views

urlpatterns = [
    path('gallery/', views.gallery_list_view, name='gallery_list'),
    path('gallery/<int:submission_id>/', views.gallery_detail_view, name='gallery_detail'),
]
