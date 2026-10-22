import unittest
from unittest.mock import patch

from desk.clustering import cluster_new_items


class ClusteringTest(unittest.TestCase):
    def test_event_dates_are_parsed_once_per_item_in_large_batch(self):
        items = [{"id": index, "title": "Regeringen håller pressträff om migration",
                  "published_at": "2026-10-22T08:00:00+02:00"} for index in range(120)]
        with patch("desk.clustering._extract_event_date", return_value=None) as parse:
            clusters = cluster_new_items(items, items)
        self.assertLessEqual(parse.call_count, len(items))
        self.assertEqual(set().union(*(set(ids) for ids in clusters.values())), set(range(120)))

    def test_similar_titles_same_event_date_cluster(self):
        items = [
            {
                "id": 1,
                "title": "Pressträff om arbetskraftsinvandring",
                "summary": "Pressträff den 5 juli 2026 kl. 10.00 i Stockholm.",
                "published_at": "2026-07-04T08:00:00+02:00",
            },
            {
                "id": 2,
                "title": "Regeringen håller pressträff om arbetskraftsinvandring",
                "summary": "Pressträff den 5 juli 2026 kl. 10.00.",
                "published_at": "2026-07-04T08:10:00+02:00",
            },
            {
                "id": 3,
                "title": "Pressträff om arbetskraftsinvandring",
                "summary": "Pressträff den 12 juli 2026 kl. 10.00 i Stockholm.",
                "published_at": "2026-07-11T08:00:00+02:00",
            },
        ]

        clusters = cluster_new_items(items, [])

        clustered = [set(ids) for ids in clusters.values()]
        self.assertIn({1, 2}, clustered)
        self.assertIn({3}, clustered)
