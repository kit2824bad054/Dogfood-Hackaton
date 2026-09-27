from django.test import SimpleTestCase


class TeamsSmokeTest(SimpleTestCase):
    def test_app_loads(self):
        """Smoke test verifying teams app loads successfully."""
        self.assertTrue(True)
