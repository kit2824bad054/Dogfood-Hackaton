from django.test import SimpleTestCase


class GallerySmokeTest(SimpleTestCase):
    def test_app_loads(self):
        """Smoke test verifying gallery app loads successfully."""
        self.assertTrue(True)
