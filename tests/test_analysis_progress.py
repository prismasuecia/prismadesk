import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai.classifier import _contains_any, _term_pattern, classify_item
from desk import database
from desk.models import NewsItem
from desk.update_runner import run_update


class AnalysisProgressTest(unittest.TestCase):
    def test_rule_patterns_are_reused_beyond_standard_regex_cache_size(self):
        terms = [f"term{index}" for index in range(700)]
        text = " ".join(terms)
        _term_pattern.cache_clear()
        with patch("ai.classifier.re.compile", wraps=re.compile) as compile_pattern:
            self.assertEqual(_contains_any(text, terms), terms)
            self.assertEqual(_contains_any(text, terms), terms)
        self.assertEqual(compile_pattern.call_count, len(terms))
        self.assertEqual(_contains_any("asylsökande SL, slott", ["asyl", "SL", "slott"]), ["SL", "slott"])

    def test_results_are_saved_before_analysis_finishes(self):
        source = {"name": "Test", "url": "https://example.test", "type": "rss"}
        items = [NewsItem(source_name="Test", source_url=source['url'],
                          title=f"Nyheter om barnbidrag {index}",
                          url=f"https://example.test/{index}") for index in range(60)]
        processed = []

        def classify(item, rules):
            if len(processed) == 25:
                self.assertEqual(len(database.latest_items()), 25)
                self.assertEqual(database.latest_run()['status'], 'RUNNING')
            processed.append(item)
            return classify_item(item, rules)

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            'PRISMA_DB_PATH': str(Path(directory) / 'desk.sqlite3'), 'ENABLE_MAIL': 'false',
        }), patch('desk.update_runner.ordered_sources_for_update', return_value=[source]), patch(
            'desk.update_runner.fetch_source', return_value=items
        ), patch('desk.update_runner.fetch_prisma_articles', return_value=[]), patch(
            'desk.update_runner.classify_item', side_effect=classify
        ):
            result = run_update()
            self.assertEqual(result['saved'], 60)
            self.assertEqual(database.latest_run()['items_processed'], 60)
