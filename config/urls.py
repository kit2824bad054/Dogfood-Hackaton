"""
URL configuration for Dogfood Platform config project.
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('', include('apps.events.urls')),
    path('', lambda request: redirect('event_list'), name='home'),
]
