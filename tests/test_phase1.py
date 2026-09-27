from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class Phase1FoundationTests(SimpleTestCase):
    """Smoke tests validating the Phase 1 Django skeleton and app loading."""

    def test_installed_apps(self):
        """Ensure all required Phase 1 apps and DRF are in INSTALLED_APPS."""
        expected_apps = [
            'rest_framework',
            'apps.accounts',
            'apps.events',
            'apps.teams',
            'apps.submissions',
            'apps.gallery',
        ]
        for app_name in expected_apps:
            with self.subTest(app=app_name):
                self.assertIn(app_name, settings.INSTALLED_APPS)
                self.assertTrue(apps.is_installed(app_name))

    def test_app_configs_loaded(self):
        """Ensure AppConfig instances are properly loaded for each domain app."""
        domain_apps = ['accounts', 'events', 'teams', 'submissions', 'gallery']
        for app_label in domain_apps:
            with self.subTest(label=app_label):
                config = apps.get_app_config(app_label)
                self.assertIsNotNone(config)
                self.assertEqual(config.name, f'apps.{app_label}')

    def test_database_configuration(self):
        """Ensure database backend is configured."""
        db_config = settings.DATABASES.get('default')
        self.assertIsNotNone(db_config)
        self.assertTrue('ENGINE' in db_config)

    def test_rest_framework_installed(self):
        """Ensure Django REST Framework is loaded."""
        rf_config = apps.get_app_config('rest_framework')
        self.assertIsNotNone(rf_config)
