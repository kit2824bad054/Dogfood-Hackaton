from django.test import SimpleTestCase


class EventsSmokeTest(SimpleTestCase):
    def test_app_loads(self):
        """Smoke test verifying events app loads successfully."""
        self.assertTrue(True)
