import unittest


class AppImportTest(unittest.TestCase):
    def test_app_imports(self):
        from app import app

        self.assertIsNotNone(app)

    def test_update_runner_imports(self):
        from desk import update_runner

        self.assertTrue(hasattr(update_runner, "run_update"))
