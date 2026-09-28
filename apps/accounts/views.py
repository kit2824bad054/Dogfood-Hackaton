"""Views for authentication, registration, and role-based dashboards."""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as BaseLoginView, LogoutView as BaseLogoutView
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView

from .decorators import role_required
from .forms import SignUpForm


def get_dashboard_url_for_role(role):
    """Return the corresponding dashboard URL name for a given user role."""
    role_urls = {
        'participant': 'dashboard_participant',
        'judge': 'dashboard_judge',
        'organizer': 'dashboard_organizer',
        'admin': 'dashboard_admin',
    }
    target = role_urls.get(role, 'dashboard_participant')
    return reverse(target)


class SignUpView(FormView):
    """
    User registration view.

    Validates user credentials, saves new user, logs them in,
    and redirects directly to their role-specific dashboard.
    """
    template_name = 'accounts/signup.html'
    form_class = SignUpForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend='apps.accounts.backends.EmailOrUsernameBackend')
        return redirect(get_dashboard_url_for_role(user.role))



class CustomLoginView(BaseLoginView):
    """
    User login view extending Django's built-in LoginView.

    Redirects authenticated users to their corresponding role-specific dashboard.
    """
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return get_dashboard_url_for_role(self.request.user.role)


class CustomLogoutView(BaseLogoutView):
    """
    User logout view supporting both POST and GET for developer convenience.
    """
    http_method_names = ['get', 'post', 'options']

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


@login_required
def dashboard_redirect_view(request):
    """Redirect authenticated users to their role dashboard."""
    return redirect(get_dashboard_url_for_role(request.user.role))


# Role-protected dashboard views

@role_required('participant')
def participant_dashboard_view(request):
    return render(request, 'accounts/dashboard.html', {
        'role': 'participant',
        'title': 'Participant Dashboard',
    })


@role_required('judge')
def judge_dashboard_view(request):
    return render(request, 'accounts/dashboard.html', {
        'role': 'judge',
        'title': 'Judge Dashboard',
    })


@role_required('organizer')
def organizer_dashboard_view(request):
    return render(request, 'accounts/dashboard.html', {
        'role': 'organizer',
        'title': 'Organizer Dashboard',
    })


@role_required('admin')
def admin_dashboard_view(request):
    from apps.events.models import Event
    from apps.submissions.models import Submission
    from apps.accounts.models import User

    stats = {
        'total_users': User.objects.count(),
        'total_events': Event.objects.count(),
        'total_submissions': Submission.objects.count(),
        'total_judges': User.objects.filter(role=User.Role.JUDGE).count(),
    }
    return render(request, 'accounts/dashboard.html', {
        'role': 'admin',
        'title': 'Admin Dashboard',
        'stats': stats,
    })

