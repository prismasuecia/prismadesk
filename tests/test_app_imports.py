import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from desk import database


class AppImportTest(unittest.TestCase):
    def tearDown(self):
        import app as app_module

        if app_module.update_lock.locked():
            try:
                app_module.update_lock.release()
            except RuntimeError:
                pass

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

    def test_update_starts_background_job_without_running_update_inline(self):
        original_db_path = database.DB_PATH

        class FakeThread:
            started = False

            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                FakeThread.started = True

        try:
            database.DB_PATH = Path(tempfile.mkdtemp()) / "async.sqlite3"
            import app as app_module

            app_module.database.DB_PATH = database.DB_PATH
            app_module.app.testing = True
            with patch.dict("os.environ", {"PRISMA_DESK_PASSWORD": ""}, clear=False):
                with patch("app.Thread", FakeThread), patch("app.run_update", side_effect=AssertionError("run_update must not run inline")):
                    response = app_module.app.test_client().post("/update")

            self.assertEqual(response.status_code, 302)
            self.assertIn("Uppdatering+startad", response.headers["Location"])
            self.assertTrue(FakeThread.started)
        finally:
            database.DB_PATH = original_db_path

    def test_update_fetch_request_returns_json_started_response(self):
        original_db_path = database.DB_PATH

        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                pass

        try:
            database.DB_PATH = Path(tempfile.mkdtemp()) / "fetch.sqlite3"
            import app as app_module

            app_module.database.DB_PATH = database.DB_PATH
            app_module.app.testing = True
            with patch.dict("os.environ", {"PRISMA_DESK_PASSWORD": ""}, clear=False):
                with patch("app.Thread", FakeThread):
                    response = app_module.app.test_client().post(
                        "/update",
                        headers={
                            "Accept": "application/json",
                            "X-Requested-With": "fetch",
                        },
                    )

            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json["started"], True)
            self.assertEqual(response.json["active"], True)
        finally:
            database.DB_PATH = original_db_path

    def test_update_refuses_second_click_while_job_is_running(self):
        original_db_path = database.DB_PATH
        try:
            database.DB_PATH = Path(tempfile.mkdtemp()) / "busy.sqlite3"
            import app as app_module

            app_module.database.DB_PATH = database.DB_PATH
            app_module.app.testing = True
            app_module.update_lock.acquire()
            with patch.dict("os.environ", {"PRISMA_DESK_PASSWORD": ""}, clear=False):
                response = app_module.app.test_client().post("/update")

            self.assertEqual(response.status_code, 302)
            self.assertIn("k%C3%B6r+redan", response.headers["Location"])
        finally:
            database.DB_PATH = original_db_path
