"""
Tests for Phase 2: Custom User model, authentication, signup, login/logout,
role-based dashboards, and access control decorators.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AccountsAuthTests(TestCase):
    """Test suite covering Phase 2 user registration, authentication, and RBAC."""

    def setUp(self):
        # Create test users for each platform role
        self.password = "DogfoodPlatform2026!"
        self.participant = User.objects.create_user(
            username="test_participant",
            email="participant@test.com",
            password=self.password,
            role=User.Role.PARTICIPANT
        )
        self.judge = User.objects.create_user(
            username="test_judge",
            email="judge@test.com",
            password=self.password,
            role=User.Role.JUDGE
        )
        self.organizer = User.objects.create_user(
            username="test_organizer",
            email="organizer@test.com",
            password=self.password,
            role=User.Role.ORGANIZER
        )
        self.admin_user = User.objects.create_superuser(
            username="test_admin",
            email="admin@test.com",
            password=self.password,
        )

    # 1. User Signup Tests
    def test_user_can_signup_and_login(self):
        """A new user can sign up, select a role, and automatically log in."""
        signup_data = {
            'username': 'new_candidate',
            'email': 'candidate@test.com',
            'role': User.Role.ORGANIZER,
            'password': self.password,
            'password_confirm': self.password,
        }
        response = self.client.post(reverse('signup'), signup_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Confirm user was created in the database with selected role
        new_user = User.objects.get(username='new_candidate')
        self.assertEqual(new_user.role, User.Role.ORGANIZER)
        self.assertEqual(new_user.email, 'candidate@test.com')

        # Confirm user is authenticated in the current session
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(response.context['user'].username, 'new_candidate')

        # Confirm redirected to organizer dashboard
        self.assertRedirects(response, reverse('dashboard_organizer'))

    def test_signup_role_defaults_to_participant_if_not_specified(self):
        """Role defaults to 'participant' if omitted or left blank in signup."""
        signup_data = {
            'username': 'default_role_user',
            'email': 'default@test.com',
            'role': '',  # Empty role
            'password': self.password,
            'password_confirm': self.password,
        }
        response = self.client.post(reverse('signup'), signup_data, follow=True)
        self.assertEqual(response.status_code, 200)

        user = User.objects.get(username='default_role_user')
        self.assertEqual(user.role, User.Role.PARTICIPANT)
        self.assertRedirects(response, reverse('dashboard_participant'))

    def test_signup_admin_role_cannot_be_selected(self):
        """Admin role cannot be self-selected at signup; validation error is raised."""
        signup_data = {
            'username': 'sneaky_admin',
            'email': 'sneaky@test.com',
            'role': 'admin',
            'password': self.password,
            'password_confirm': self.password,
        }
        response = self.client.post(reverse('signup'), signup_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='sneaky_admin').exists())
        form = response.context['form']
        self.assertIn('role', form.errors)
        self.assertIn("admin is not one of the available choices", str(form.errors['role']))

    # 2. Login & Redirection Tests
    def test_login_redirects_to_role_dashboard(self):
        """Logging in redirects to role-specific dashboard for each role."""
        role_expectations = [
            (self.participant, reverse('dashboard_participant')),
            (self.judge, reverse('dashboard_judge')),
            (self.organizer, reverse('dashboard_organizer')),
            (self.admin_user, reverse('dashboard_admin')),
        ]
        for user, expected_url in role_expectations:
            with self.subTest(user=user.username, role=user.role):
                self.client.logout()
                response = self.client.post(
                    reverse('login'),
                    {'username': user.username, 'password': self.password},
                    follow=True
                )
                self.assertEqual(response.status_code, 200)
                self.assertRedirects(response, expected_url)

    def test_logout(self):
        """User can log out and is redirected to login page."""
        self.client.login(username='test_participant', password=self.password)
        response = self.client.get(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('login'))

    # 3. Role-Based Access Control (RBAC) & 403 Tests
    def test_logged_out_user_redirected_to_login(self):
        """A logged-out user accessing a protected dashboard is redirected to login."""
        dashboards = [
            reverse('dashboard_participant'),
            reverse('dashboard_judge'),
            reverse('dashboard_organizer'),
            reverse('dashboard_admin'),
        ]
        for url in dashboards:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('login')))

    def test_participant_hitting_organizer_dashboard_gets_403(self):
        """A participant hitting /dashboard/organizer/ directly receives HTTP 403."""
        self.client.login(username='test_participant', password=self.password)
        response = self.client.get(reverse('dashboard_organizer'))
        self.assertEqual(response.status_code, 403)

    def test_participant_hitting_judge_dashboard_gets_403(self):
        """A participant hitting /dashboard/judge/ directly receives HTTP 403."""
        self.client.login(username='test_participant', password=self.password)
        response = self.client.get(reverse('dashboard_judge'))
        self.assertEqual(response.status_code, 403)

    def test_organizer_hitting_organizer_dashboard_gets_200(self):
        """An organizer hitting /dashboard/organizer/ receives HTTP 200."""
        self.client.login(username='test_organizer', password=self.password)
        response = self.client.get(reverse('dashboard_organizer'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, <strong>test_organizer</strong>, your role is <strong>organizer</strong>")

    def test_judge_hitting_judge_dashboard_gets_200(self):
        """A judge hitting /dashboard/judge/ receives HTTP 200."""
        self.client.login(username='test_judge', password=self.password)
        response = self.client.get(reverse('dashboard_judge'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, <strong>test_judge</strong>, your role is <strong>judge</strong>")

    def test_admin_can_access_admin_dashboard(self):
        """An admin user hitting /dashboard/admin/ receives HTTP 200."""
        self.client.login(username='test_admin', password=self.password)
        response = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, <strong>test_admin</strong>, your role is <strong>admin</strong>")
