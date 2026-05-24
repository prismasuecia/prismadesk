import unittest

from feeds.calendar_reader import _agenda_items


class CalendarReaderTest(unittest.TestCase):
    def test_extracts_riksdagen_agenda_items_from_event_description(self):
        description = (
            "\n\n2025/26:JuU28 Polisens användning av AI för ansiktsigenkänning i realtid\n\n"
            "2025/26:SfU21 Kvalificering till socialförsäkringen\n\n"
        )

        items = _agenda_items(description)

        self.assertEqual(
            items,
            [
                ("2025/26:JuU28", "Polisens användning av AI för ansiktsigenkänning i realtid"),
                ("2025/26:SfU21", "Kvalificering till socialförsäkringen"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
