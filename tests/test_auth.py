import unittest
from unittest.mock import patch

from app import app


class AuthTest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True

    def test_dashboard_is_open_when_password_is_not_set(self):
        with patch.dict("os.environ", {"PRISMA_DESK_PASSWORD": ""}, clear=False):
            response = app.test_client().get("/")

        self.assertEqual(response.status_code, 200)

    def test_dashboard_redirects_to_login_when_password_is_set(self):
        with patch.dict("os.environ", {"PRISMA_DESK_PASSWORD": "secret"}, clear=False):
            response = app.test_client().get("/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_login_accepts_password(self):
        with patch.dict("os.environ", {"PRISMA_DESK_PASSWORD": "secret"}, clear=False):
            client = app.test_client()
            response = client.post("/login", data={"password": "secret"})
            dashboard = client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(dashboard.status_code, 200)


if __name__ == "__main__":
    unittest.main()
