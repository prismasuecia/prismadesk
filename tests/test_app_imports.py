import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from desk import database


class AppImportTest(unittest.TestCase):
    def test_app_imports(self):
        from app import app

        self.assertIsNotNone(app)

    def test_update_runner_imports(self):
        from desk import update_runner

        self.assertTrue(hasattr(update_runner, "run_update"))

    def test_update_initializes_empty_database_before_stale_run_cleanup(self):
        original_db_path = database.DB_PATH
        try:
            database.DB_PATH = Path(tempfile.mkdtemp()) / "empty.sqlite3"
            import app as app_module

            app_module.database.DB_PATH = database.DB_PATH
            app_module.app.testing = True
            with patch(
                "app.run_update",
                return_value={"saved": 0, "found": 0, "red_alerts": 0, "errors": []},
            ):
                response = app_module.app.test_client().post("/update")

            self.assertEqual(response.status_code, 302)
        finally:
            database.DB_PATH = original_db_path
