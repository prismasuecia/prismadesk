import unittest

from desk import database


class ViewStateTest(unittest.TestCase):
    def test_mark_viewed_now_updates_timestamp(self):
        database.init_db()
        before = database.get_last_viewed_at()

        database.mark_viewed_now()
        after = database.get_last_viewed_at()

        self.assertIsNotNone(after)
        if before:
            self.assertGreaterEqual(after, before)
