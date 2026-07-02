import json
import unittest
from datetime import datetime

from app import build_sections, prepare_items_for_dashboard


class DashboardSectionsTest(unittest.TestCase):
    def test_old_red_press_event_is_not_in_akut(self):
        item = {
            "source_name": "Regeringen",
            "source_url": "https://example.com",
            "title": "Pressträff med statsministern",
            "summary": "Pressträff den 1 januari 2026 kl. 10.00 i Stockholm.",
            "content": "",
            "published_at": "2026-01-01T08:00:00+01:00",
            "fetched_at": datetime.now().astimezone().isoformat(),
            "url": "https://example.com/press",
            "hash": "abc",
            "category": "government",
            "priority": "RED",
            "desk": "ZUMA",
            "physical_presence": 1,
            "accreditation_needed": None,
            "deadline_detected": 0,
            "deadline_date": None,
            "already_on_prisma": 0,
            "prisma_status": "EJ_PUBLICERAD",
            "action_recommendation": "ÅK_DIT",
            "score": 150,
            "last_seen_at": datetime.now().astimezone().isoformat(),
            "raw_json": json.dumps({"temporal_status": "CURRENT"}),
        }

        sections = build_sections(prepare_items_for_dashboard([item]))

        self.assertEqual(sections["akut"]["items"], [])
        self.assertEqual(sections["zuma"]["items"], [])
