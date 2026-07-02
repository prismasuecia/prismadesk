import unittest


class AppImportTest(unittest.TestCase):
    def test_app_imports(self):
        from app import app

        self.assertIsNotNone(app)
