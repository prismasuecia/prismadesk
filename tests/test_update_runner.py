import os
import unittest
from unittest.mock import patch

from desk.update_runner import _maybe_read_mail, load_sources


class UpdateRunnerTest(unittest.TestCase):
    def test_password_does_not_limit_sources(self):
        sources = [{"name": f"Källa {index}", "priority": "green"} for index in range(20)]
        with patch.dict(
            os.environ,
            {"PRISMA_DESK_PASSWORD": "secret", "PRISMA_SOURCE_LIMIT": ""},
            clear=False,
        ):
            with patch("desk.update_runner.load_yaml", return_value={"sources": sources}):
                self.assertEqual(len(load_sources()), 20)

    def test_explicit_source_limit_still_limits_sources(self):
        sources = [{"name": f"Källa {index}", "priority": "green"} for index in range(20)]
        with patch.dict(os.environ, {"PRISMA_SOURCE_LIMIT": "5"}, clear=False):
            with patch("desk.update_runner.load_yaml", return_value={"sources": sources}):
                self.assertEqual(len(load_sources()), 5)

    def test_mail_reader_is_disabled_by_default(self):
        with patch.dict(os.environ, {"ENABLE_MAIL": "false"}, clear=False):
            self.assertEqual(_maybe_read_mail(), [])
