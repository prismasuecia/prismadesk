import unittest
from unittest.mock import Mock, patch

from feeds.web_reader import read_web_source


class WebReaderTest(unittest.TestCase):
    def test_regeringen_press_release_detail_is_merged_into_item(self):
        list_response = Mock()
        list_response.text = """
        <main>
          <ul>
            <li>
              <a href="/pressmeddelanden/2026/07/regeringen-och-sverigedemokraterna-bjuder-in-till-presstraff2/">
                Regeringen och Sverigedemokraterna bjuder in till pressträff
              </a>
              <span>Publicerad 13 juli 2026</span>
            </li>
          </ul>
        </main>
        """
        list_response.encoding = "utf-8"
        list_response.apparent_encoding = "utf-8"
        list_response.raise_for_status.return_value = None

        detail_response = Mock()
        detail_response.text = """
        <main>
          <h1>Regeringen och Sverigedemokraterna bjuder in till pressträff</h1>
          <p>Publicerad 13 juli 2026</p>
          <p>Tisdag den 14 juli klockan 10.00 bjuder regeringen och Sverigedemokraterna in till pressträff.</p>
          <p>Tid: 14 juli 2026 kl. 10.00. Plats: Rosenbad. Inpassering via Drottninggatan 1.</p>
          <p>Obligatorisk föranmälan senast 14 juli kl. 09.00. Giltig presslegitimation krävs.</p>
          <p>Dela Facebook - öppnas i ny flik</p>
          <section>Relaterat Remiss av rapporten Behandling av personuppgifter</section>
        </main>
        """
        detail_response.encoding = "utf-8"
        detail_response.apparent_encoding = "utf-8"
        detail_response.raise_for_status.return_value = None

        with patch("feeds.web_reader.requests.get", side_effect=[list_response, detail_response]):
            items = read_web_source(
                {
                    "name": "Regeringen pressmeddelanden web",
                    "url": "https://www.regeringen.se/pressmeddelanden/",
                    "category": "government",
                },
                timeout=4,
            )

        self.assertEqual(len(items), 1)
        self.assertIn("Rosenbad", items[0].content)
        self.assertIn("14 juli 2026 kl. 10.00", items[0].content)
        self.assertIn("Obligatorisk föranmälan", items[0].content)
        self.assertIn("presslegitimation", items[0].content)
        self.assertNotIn("Behandling av personuppgifter", items[0].content)
        self.assertTrue(items[0].raw_json.get("detail_fetched"))

    def test_regeringen_ud_advisory_detail_is_merged_into_item(self):
        list_response = Mock()
        list_response.text = """
        <main>
          <ul>
            <li>
              <a href="/ud-avrader/bolivia---avradan/">Bolivia - avrådan</a>
              <span>Publicerad 16 juli 2026</span>
            </li>
          </ul>
        </main>
        """
        list_response.encoding = "utf-8"
        list_response.apparent_encoding = "utf-8"
        list_response.raise_for_status.return_value = None

        detail_response = Mock()
        detail_response.text = """
        <main>
          <h1>Bolivia - avrådan</h1>
          <p>Publicerad 16 juli 2026</p>
          <p>Utrikesdepartementet avråder från alla resor till provinsen Chapare.</p>
          <p>Beslut om avrådan togs den 16 juli 2026 och gäller tills vidare.</p>
          <p>Dela Facebook - öppnas i ny flik</p>
        </main>
        """
        detail_response.encoding = "utf-8"
        detail_response.apparent_encoding = "utf-8"
        detail_response.raise_for_status.return_value = None

        with patch("feeds.web_reader.requests.get", side_effect=[list_response, detail_response]):
            items = read_web_source(
                {
                    "name": "UD avrådan",
                    "url": "https://www.regeringen.se/ud-avrader/",
                    "category": "ud_travel_advice",
                },
                timeout=4,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Bolivia - avrådan")
        self.assertIn("Chapare", items[0].content)
        self.assertEqual(items[0].published_at, "16 juli 2026")
        self.assertEqual(items[0].raw_json.get("source_type"), "web_regeringen_ud_advisory")
        self.assertTrue(items[0].raw_json.get("detail_fetched"))


if __name__ == "__main__":
    unittest.main()
