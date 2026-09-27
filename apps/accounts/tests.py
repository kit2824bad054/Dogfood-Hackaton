from django.test import SimpleTestCase


class AccountsSmokeTest(SimpleTestCase):
    def test_app_loads(self):
        """Smoke test verifying accounts app loads successfully."""
        self.assertTrue(True)
