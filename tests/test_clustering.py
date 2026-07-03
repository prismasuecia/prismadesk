import unittest

from desk.clustering import cluster_new_items


class ClusteringTest(unittest.TestCase):
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
