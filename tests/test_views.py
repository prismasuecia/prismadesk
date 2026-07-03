import json
import unittest

from app import apply_role_filter, group_timeline_items, parse_datetime


class ViewHelpersTest(unittest.TestCase):
    def test_apply_role_filter(self):
        items = [
            {"desk": "ZUMA", "title": "zuma"},
            {"desk": "PRISMA", "title": "prisma"},
            {"desk": "BOTH", "title": "both"},
            {"desk": "IGNORE", "title": "ignore"},
        ]

        self.assertEqual([item["title"] for item in apply_role_filter(items, "zuma")], ["zuma", "both"])
        self.assertEqual([item["title"] for item in apply_role_filter(items, "prisma")], ["prisma", "both"])

    def test_group_timeline_items_by_date(self):
        items = [
            {
                "title": "deadline",
                "deadline_date": "2026-07-04T12:00:00+02:00",
                "raw_json": json.dumps({}),
            },
            {
                "title": "event",
                "deadline_date": None,
                "published_at": "2026-07-05T12:00:00+02:00",
                "raw_json": json.dumps({"detected_event_datetime": "2026-07-05T10:00:00+02:00"}),
            },
        ]

        grouped = group_timeline_items(items)

        self.assertEqual(list(grouped.keys()), ["2026-07-04", "2026-07-05"])

    def test_timeline_accepts_mixed_datetime_formats(self):
        items = [
            {
                "title": "rss",
                "published_at": "Tue, 02 Jun 2026 14:21:15 GMT",
                "raw_json": json.dumps({}),
            },
            {
                "title": "iso-aware",
                "published_at": "2026-06-03T07:24:36+00:00",
                "raw_json": json.dumps({}),
            },
            {
                "title": "iso-naive",
                "published_at": "2026-06-04T08:00:00",
                "raw_json": json.dumps({}),
            },
        ]

        grouped = group_timeline_items(items)

        self.assertEqual(list(grouped.keys()), ["2026-06-02", "2026-06-03", "2026-06-04"])
        self.assertIsNotNone(parse_datetime("Tue, 02 Jun 2026 14:21:15 GMT"))
