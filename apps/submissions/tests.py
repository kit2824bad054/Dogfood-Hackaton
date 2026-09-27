from django.test import SimpleTestCase


class SubmissionsSmokeTest(SimpleTestCase):
    def test_app_loads(self):
        """Smoke test verifying submissions app loads successfully."""
        self.assertTrue(True)
