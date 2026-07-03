import json
import unittest

from desk.live_status import live_temporal_status


class LiveStatusTest(unittest.TestCase):
    def test_live_status_ignores_stale_saved_raw_json(self):
        row = {
            "source_name": "Regeringen",
            "source_url": "https://example.com",
            "title": "Pressträff med statsministern",
            "summary": "Pressträff den 1 januari 2026 kl. 10.00 i Stockholm.",
            "content": "",
            "published_at": "2026-01-01T08:00:00+01:00",
            "fetched_at": "2026-01-01T08:00:00+01:00",
            "category": "government",
            "physical_presence": 1,
            "accreditation_needed": None,
            "deadline_detected": 0,
            "action_recommendation": "ÅK_DIT",
            "raw_json": json.dumps({"temporal_status": "CURRENT"}),
        }

        self.assertIn(live_temporal_status(row), {"PAST_EVENT", "OLD"})
