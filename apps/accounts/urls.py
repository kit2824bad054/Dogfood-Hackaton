"""URL routing for accounts and dashboards."""

from django.urls import path
from .views import (
    SignUpView,
    CustomLoginView,
    CustomLogoutView,
    dashboard_redirect_view,
    participant_dashboard_view,
    judge_dashboard_view,
    organizer_dashboard_view,
    admin_dashboard_view,
)

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('dashboard/', dashboard_redirect_view, name='dashboard'),
    path('dashboard/participant/', participant_dashboard_view, name='dashboard_participant'),
    path('dashboard/judge/', judge_dashboard_view, name='dashboard_judge'),
    path('dashboard/organizer/', organizer_dashboard_view, name='dashboard_organizer'),
    path('dashboard/admin/', admin_dashboard_view, name='dashboard_admin'),
]
