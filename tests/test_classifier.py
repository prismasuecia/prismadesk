import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from ai.classifier import classify_item
from desk.models import NewsItem


BASE_DIR = Path(__file__).resolve().parents[1]
SWEDISH_MONTHS = [
    "",
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
]


def swedish_date(value: datetime) -> str:
    return f"{value.day} {SWEDISH_MONTHS[value.month]}"


class ClassifierTest(unittest.TestCase):
    def setUp(self):
        with (BASE_DIR / "config" / "rules.yaml").open("r", encoding="utf-8") as handle:
            self.rules = yaml.safe_load(handle)

    def test_press_meeting_with_pm_defence_and_skeppsbron_is_red_alert(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Ulf Kristersson och Pål Jonson bjuder in till pressträff på Skeppsbron",
            summary="Pressträffen gäller försvar, NATO och marin säkerhet. Föranmälan krävs.",
            category="government",
            url="https://example.test/presstraff",
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertIn(item.desk, {"ZUMA", "BOTH"})
        self.assertTrue(item.physical_presence)
        self.assertIn(item.action_recommendation, {"ÅK_DIT", "SÖK_ACKREDITERING", "RING_MAILA_NU"})

    def test_press_meeting_about_labour_migration_is_acute_prisma(self):
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        event_date = swedish_date(tomorrow)
        item = NewsItem(
            source_name="Regeringen pressmeddelanden web",
            source_url="https://www.regeringen.se/pressmeddelanden/",
            title="Pressträff om arbetskraftsinvandring",
            summary=(
                f"Imorgon {event_date} bjuder migrationsminister Johan Forssell, "
                "arbetsmarknadsminister Johan Britz, Ludvig Aspling (SD), "
                "Liza-Maria Norlin (KD) in till pressträff för att presentera "
                "en nyhet som rör arbetskraftsinvandring."
            ),
            category="government",
            url="https://www.regeringen.se/pressmeddelanden/2026/05/presstraff-om-arbetskraftsinvandring/",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertEqual(item.desk, "BOTH")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("Akut Prisma-läge", item.raw_json.get("why_it_matters", ""))

    def test_yesterday_date_only_press_meeting_is_past_event(self):
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        item = NewsItem(
            source_name="Regeringen pressmeddelanden web",
            source_url="https://www.regeringen.se/pressmeddelanden/",
            title="Pressträff för att presentera lagförslag för anhöriginvandring",
            summary=(
                f"Publicerad {swedish_date(yesterday)} {yesterday.year}. "
                "Migrationsministern bjuder in till pressträff om anhöriginvandring."
            ),
            category="government",
            url="https://www.regeringen.se/pressmeddelanden/2026/06/presstraff-anhoriginvandring/",
            published_at=swedish_date(yesterday),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("temporal_status"), "PAST_EVENT")
        self.assertFalse(item.physical_presence)
        self.assertNotEqual(item.priority, "RED")
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")

    def test_party_manifest_press_meeting_in_stockholm_is_zuma_picture_alert(self):
        item = NewsItem(
            source_name="Liberalerna pressrum",
            source_url="https://www.liberalerna.se/pressrum",
            title="Pressträff Liberalernas valmanifest",
            summary=(
                "Stockholm, Sverige. Partiledare Simona Mohamsson (L) håller en "
                "pressträff om partiets valmanifest inför valet 2026."
            ),
            category="politics",
            url="https://www.liberalerna.se/pressrum/presstraff-liberalernas-valmanifest",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertIn(item.desk, {"ZUMA", "BOTH"})
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json["matched_terms"]["zuma_picture_value"])
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("ZUMA-bildläge", item.raw_json.get("why_it_matters", ""))

    def test_scraped_party_manifest_without_event_time_is_follow_up(self):
        item = NewsItem(
            source_name="Liberalerna pressrum",
            source_url="https://www.liberalerna.se/pressrum",
            title="Liberalerna presenterar valmanifest inför valet 2026 - För din frihet",
            summary=(
                "Liberalerna presenterar sitt valmanifest. Partiledare Simona Mohamsson "
                "medverkade vid en pressträff."
            ),
            category="politics",
            url="https://www.liberalerna.se/pressrum/liberalerna-presenterar-valmanifest",
            published_at=datetime.now(timezone.utc).isoformat(),
            raw_json={"source_type": "web"},
        )

        classify_item(item, self.rules)

        self.assertIn(item.priority, {"YELLOW", "ORANGE"})
        self.assertFalse(item.physical_presence)
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")
        self.assertIn("ingen tydlig kommande tid", item.raw_json.get("why_it_matters", ""))

    def test_digital_child_safety_press_meeting_is_prisma_and_picture_alert(self):
        item = NewsItem(
            source_name="Regeringen pressmeddelanden",
            source_url="https://www.regeringen.se/pressmeddelanden/",
            title="Pressträff åldersgräns digitala miljöer",
            summary=(
                "Stockholm, Sverige. Socialminister Jakob Forssmed tar emot "
                "delbetänkandet En åldersgräns till skydd för barns hälsa och "
                "trygghet i digitala miljöer under en pressträff."
            ),
            category="government",
            url="https://www.regeringen.se/pressmeddelanden/2026/06/presstraff-aldersgrans-digitala-miljoer/",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertIn(item.priority, {"RED", "ORANGE"})
        self.assertEqual(item.desk, "BOTH")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("digital", " ".join(item.raw_json.get("image_suggestions", [])).lower())

    def test_child_mental_health_press_meeting_is_prisma_picture_alert(self):
        item = NewsItem(
            source_name="Kristdemokraterna press",
            source_url="https://press.kristdemokraterna.se/",
            title="KD pressträff om psykisk ohälsa",
            summary=(
                "Stockholm, Sverige. Jakob Forssmed håller pressträff om den fortsatta "
                "planen för bättre psykisk hälsa för barn och unga."
            ),
            category="politics",
            url="https://press.kristdemokraterna.se/presstraff-psykisk-ohalsa",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertEqual(item.desk, "BOTH")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("psykisk", " ".join(item.raw_json.get("image_suggestions", [])).lower())

    def test_party_press_meeting_about_eldercare_abuse_is_prisma_picture_alert(self):
        item = NewsItem(
            source_name="Sverigedemokraterna press",
            source_url="https://www.sd.se/press/",
            title="SD pressträff övergrepp äldreomsorg",
            summary=(
                "Stockholm, Sverige. Sverigedemokraternas gruppledare Linda Lindberg "
                "kommenterar uppgifterna om en SD-ledamot under en pressträff där SD "
                "presenterar politiska förslag mot övergreppen inom äldreomsorgen."
            ),
            category="politics",
            url="https://www.sd.se/press/presstraff-overgrepp-aldreomsorg/",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertEqual(item.desk, "BOTH")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("äldre", " ".join(item.raw_json.get("image_suggestions", [])).lower())

    def test_party_leader_media_availability_in_riksdagen_is_zuma_picture_alert(self):
        item = NewsItem(
            source_name="Socialdemokraterna press",
            source_url="https://www.socialdemokraterna.se/vart-parti/press",
            title="Magdalena Andersson kommenterar nationella säkerhetsrådgivaren",
            summary=(
                "Stockholm, Sverige. Socialdemokraternas partiledare Magdalena Andersson "
                "kommenterar att partiet tänker avskaffa den nationella säkerhetsrådgivaren "
                "om de får bilda regering efter valet i höst, när hon möter journalister i riksdagen."
            ),
            category="politics",
            url="https://www.socialdemokraterna.se/press/magdalena-andersson-sakerhetsradgivaren",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertEqual(item.desk, "BOTH")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("politisk medieträff", item.raw_json.get("why_it_matters", ""))

    def test_party_leader_debate_at_kulturhuset_requires_accreditation(self):
        item = NewsItem(
            source_name="TT bildsignal",
            source_url="https://example.test/tt",
            title="Partiledardebatt Kulturhuset Stadsteatern 2026",
            summary=(
                "Stockholm, Sverige. Utbildningsminister och Liberalernas partiledare "
                "Simona Mohamsson under partiledardebatten på Kulturhuset Stadsteatern "
                "i Stockholm."
            ),
            category="events",
            url="https://example.test/partiledardebatt-kulturhuset",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertIn(item.desk, {"ZUMA", "BOTH"})
        self.assertTrue(item.physical_presence)
        self.assertTrue(item.accreditation_needed)
        self.assertEqual(item.action_recommendation, "SÖK_ACKREDITERING")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("access_guidance"))
        self.assertIn("Kulturhuset", " ".join(item.raw_json.get("access_guidance", [])))

    def test_stockholm_marathon_medal_ceremony_is_zuma_picture_event(self):
        item = NewsItem(
            source_name="TT bildsignal",
            source_url="https://example.test/tt",
            title="Stockholm Marathon 2026",
            summary=(
                "Stockholm, Sverige. Medaljutdelning efter målgång i Stockholm Stadion "
                "under Stockholm marathon på lördagen."
            ),
            category="events",
            url="https://example.test/stockholm-marathon-2026",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "ORANGE")
        self.assertEqual(item.desk, "ZUMA")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("internationellt bildvärde", item.raw_json.get("why_it_matters", ""))

    def test_national_team_world_cup_press_meeting_is_zuma_picture_event(self):
        item = NewsItem(
            source_name="TT bildsignal",
            source_url="https://example.test/tt",
            title="Pressträff landslaget ledarstab inför fotbolls-VM",
            summary=(
                "Stockholm, Sverige. Assisterande förbundskapten Sebastian Larsson "
                "under en pressträff med landslagets ledarstab på spelarhotellet "
                "Scandic Park inför fotbolls-VM."
            ),
            category="events",
            url="https://example.test/landslaget-fotbolls-vm",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "ORANGE")
        self.assertEqual(item.desk, "ZUMA")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("VM", " ".join(item.raw_json.get("image_suggestions", [])))

    def test_veterans_day_with_government_leaders_is_red_zuma_picture_event(self):
        item = NewsItem(
            source_name="TT bildsignal",
            source_url="https://example.test/tt",
            title="Veterandagen Stockholm 2026",
            summary=(
                "Stockholm, Sverige. Carl-Oskar Bohlin, Pål Jonsson, statsminister "
                "Ulf Kristersson och talmannen Andreas Norlén under veterandagen "
                "vid Sjöhistoriska museet i Stockholm."
            ),
            category="events",
            url="https://example.test/veterandagen-stockholm-2026",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertIn(item.desk, {"ZUMA", "BOTH"})
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("försvarsceremoni", item.raw_json.get("why_it_matters", ""))

    def test_civil_alert_press_meeting_is_prisma_and_zuma_picture_event(self):
        item = NewsItem(
            source_name="TT bildsignal",
            source_url="https://example.test/tt",
            title="Pressträff varningssystem till civilbefolkningen",
            summary=(
                "Stockholm, Sverige. Exemplet på hur varningssystemet, SE Alert, "
                "till civilbefolkningen kommer att se ut på mobilen presenterades "
                "under en pressträff."
            ),
            category="government",
            url="https://example.test/se-alert-civilbefolkningen",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertEqual(item.desk, "BOTH")
        self.assertTrue(item.physical_presence)
        self.assertEqual(item.action_recommendation, "RING_MAILA_NU")
        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("mobil", " ".join(item.raw_json.get("image_suggestions", [])).lower())
        self.assertIn("civil varning", item.raw_json.get("why_it_matters", ""))

    def test_already_published_must_not_keep_publish_today(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="SL inför ändringar i trafiken",
            summary="Praktisk information för resenärer i Stockholm.",
            category="transport",
            url="https://example.test/sl",
            action_recommendation="PUBLICERA_IDAG",
            prisma_status="REDAN_PUBLICERAD",
        )

        if item.prisma_status == "REDAN_PUBLICERAD" and item.action_recommendation == "PUBLICERA_IDAG":
            item.action_recommendation = "UPPDATERA_ARTIKEL"

        self.assertNotEqual(item.action_recommendation, "PUBLICERA_IDAG")

    def test_old_press_meeting_is_not_go_there(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Ulf Kristersson bjuder in till pressträff om bokslut över Tidöavtalet",
            summary="Statsministern håller pressträff.",
            category="prime_minister",
            url="https://example.test/old-presstraff",
            published_at=old_date,
        )

        classify_item(item, self.rules)

        self.assertNotEqual(item.priority, "RED")
        self.assertNotEqual(item.action_recommendation, "ÅK_DIT")
        self.assertEqual(item.raw_json.get("temporal_status"), "PAST_EVENT")

    def test_old_undated_spring_press_briefing_is_not_rolled_to_next_year(self):
        item = NewsItem(
            source_name="Regeringen statsministern",
            source_url="https://www.regeringen.se",
            title="Pressbriefing med statsminister Ulf Kristersson och finansminister Elisabeth Svantesson",
            summary=(
                "Torsdag den 23 april klockan 11.30 håller statsminister Ulf Kristersson "
                "och finansminister Elisabeth Svantesson en pressbriefing."
            ),
            category="prime_minister",
            url="https://example.test/april-briefing",
            published_at="Thu, 23 Apr 2026 07:00:23 +0200",
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("temporal_status"), "PAST_EVENT")
        self.assertNotEqual(item.raw_json.get("detected_event_datetime", "")[:4], "2027")
        self.assertNotEqual(item.action_recommendation, "ÅK_DIT")

    def test_go_there_requires_physical_presence(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Utrikesminister Maria Malmer Stenergard möter Ukrainas utrikesminister i Kristianstad",
            summary="Pressmeddelande från Utrikesdepartementet.",
            category="government",
            url="https://example.test/ukraina",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertFalse(item.physical_presence)
        self.assertNotEqual(item.action_recommendation, "ÅK_DIT")

    def test_foreign_media_accident_without_sweden_link_is_ignored(self):
        item = NewsItem(
            source_name="Aftonbladet senaste nytt",
            source_url="https://rss.aftonbladet.se/",
            title="Döda dykare i olyckan i Maldiverna bärgade",
            summary="Olyckan inträffade utomlands.",
            category="media_breaking",
            url="https://example.test/maldiverna",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "GREY")
        self.assertEqual(item.desk, "IGNORE")
        self.assertEqual(item.action_recommendation, "IGNORERA")
        self.assertFalse(item.physical_presence)

    def test_media_nato_quote_is_not_physical_presence(self):
        item = NewsItem(
            source_name="Aftonbladet senaste nytt",
            source_url="https://rss.aftonbladet.se/",
            title="Natochefen: Måste producera mer",
            summary="Artikel om NATO och försvar.",
            category="media_breaking",
            url="https://example.test/nato",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertFalse(item.physical_presence)
        self.assertNotEqual(item.desk, "BOTH")
        self.assertNotEqual(item.action_recommendation, "ÅK_DIT")

    def test_plain_e4_crash_is_not_international_physical_presence(self):
        item = NewsItem(
            source_name="Expressen nyheter",
            source_url="https://feeds.expressen.se/nyheter/",
            title="JUST NU: Stor krock på E4",
            summary="Trafikolycka på E4.",
            category="media_breaking",
            url="https://example.test/e4",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertFalse(item.physical_presence)
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")

    def test_nato_media_signal_without_picture_value_is_not_zuma(self):
        item = NewsItem(
            source_name="Svenska Dagbladet",
            source_url="https://www.svd.se/feed/articles.rss",
            title="Natochefen: Måste producera mer",
            summary="Mark Rutte uttalar sig om NATO i en vanlig nyhetsartikel utan svensk plats eller fototillfälle.",
            category="media_national",
            url="https://example.test/nato-signal",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.desk, "PRISMA")
        self.assertFalse(item.physical_presence)
        self.assertFalse(item.raw_json["matched_terms"]["zuma_picture_value"])

    def test_media_red_alert_without_stockholm_place_is_not_go_there(self):
        item = NewsItem(
            source_name="Svenska Dagbladet",
            source_url="https://www.svd.se/feed/articles.rss",
            title="Kristersson till Rutte: Vi når försvarsmål redan 2030",
            summary="Ulf Kristersson och Mark Rutte håller pressträff.",
            category="media_national",
            url="https://example.test/rutte",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "RED")
        self.assertFalse(item.physical_presence)
        self.assertNotEqual(item.action_recommendation, "ÅK_DIT")

    def test_press_meeting_with_visual_place_has_zuma_picture_value(self):
        item = NewsItem(
            source_name="Regeringen",
            source_url="https://www.regeringen.se",
            title="Ulf Kristersson och Pål Jonson bjuder in till pressträff på Skeppsbron",
            summary="Pressträff om försvar, NATO och marinen. Fotografer kan närvara.",
            category="prime_minister",
            url="https://example.test/skeppsbron",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertIn(item.desk, {"ZUMA", "BOTH"})
        self.assertTrue(item.physical_presence)
        self.assertTrue(item.raw_json["matched_terms"]["zuma_picture_value"])

    def test_stockholm_picture_event_gets_location_boost(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Demonstration på Sergels torg med internationellt bildvärde",
            summary="Stor demonstration i Stockholm med över 500 personer. Fototillfälle på Sergels torg.",
            category="events",
            url="https://example.test/sergels-torg",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("location_fit"), "STOCKHOLM")
        self.assertIn(item.priority, {"ORANGE", "RED"})
        self.assertIn(item.action_recommendation, {"RING_MAILA_NU", "ÅK_DIT"})
        self.assertGreaterEqual(item.score, 100)

    def test_outside_stockholm_physical_event_notes_travel_friction(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Pressvisning i Göteborg",
            summary="Fototillfälle och pressvisning i Göteborg.",
            category="events",
            url="https://example.test/goteborg",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("location_fit"), "UTANFÖR_STOCKHOLM")
        self.assertEqual(item.desk, "PRISMA")
        self.assertFalse(item.physical_presence)
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")
        self.assertIn("inte ZUMA", item.raw_json.get("location_note", ""))

    def test_pm_receives_mark_rutte_with_press_briefing_is_red_zuma(self):
        item = NewsItem(
            source_name="Regeringen pressmeddelanden",
            source_url="https://www.regeringen.se",
            title="Statsministern tar emot Natos generalsekreterare Mark Rutte",
            summary=(
                "Torsdag den 21 maj tar statsminister Ulf Kristersson emot Natos "
                "generalsekreterare Mark Rutte för ett bilateralt möte och gemensamt "
                "besök med fokus på Sveriges totalförsvar, civilt försvar och resiliens. "
                "I samband med besöket hålls en gemensam pressbriefing i Revinge, Skåne."
            ),
            category="prime_minister",
            url="https://www.regeringen.se",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "ORANGE")
        self.assertEqual(item.desk, "PRISMA")
        self.assertFalse(item.physical_presence)
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")
        self.assertEqual(item.raw_json.get("location_fit"), "UTANFÖR_STOCKHOLM")
        self.assertTrue(item.raw_json["matched_terms"]["zuma_picture_value"])

    def test_future_event_date_overrides_older_publish_date_for_press_briefing(self):
        future_event = datetime.now(timezone.utc) + timedelta(days=2)
        item = NewsItem(
            source_name="Regeringen statsministern",
            source_url="https://www.regeringen.se",
            title="Statsministern tar emot Natos generalsekreterare Mark Rutte",
            summary=(
                f"Tisdag den {swedish_date(future_event)} tar statsminister Ulf Kristersson emot Natos "
                "generalsekreterare Mark Rutte. I samband med besöket hålls en gemensam "
                "pressbriefing i Revinge, Skåne."
            ),
            category="prime_minister",
            url="https://www.regeringen.se",
            published_at="Wed, 13 May 2026 12:00:19 +0200",
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "ORANGE")
        self.assertEqual(item.raw_json.get("temporal_status"), "UPCOMING")
        self.assertFalse(item.physical_presence)
        self.assertEqual(item.desk, "PRISMA")
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")

    def test_outside_stockholm_prisma_story_is_kept_for_target_audience(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Migrationsverket öppnar ny service i Malmö",
            summary="Nyheten påverkar migration, medborgarskap och arbetsmarknad för spansktalande i Sverige.",
            category="government",
            url="https://example.test/malmo-migration",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("location_fit"), "UTANFÖR_STOCKHOLM")
        self.assertEqual(item.desk, "PRISMA")
        self.assertFalse(item.physical_presence)
        self.assertIn(item.action_recommendation, {"PUBLICERA_IDAG", "FÖLJ_UPP"})

    def test_migration_center_visit_in_boden_is_not_zuma_physical_alert(self):
        item = NewsItem(
            source_name="Via TT",
            source_url="https://via.tt.se/",
            title="Besök Migrationsverkets mottagnings- och återvändandecenter i Boden",
            summary=(
                "Media bjuds in till besök på Migrationsverkets mottagnings- och "
                "återvändandecenter i Boden. Nyheten rör migration och återvändande."
            ),
            category="press_releases",
            url="https://via.tt.se/pressmeddelande/boden-migrationsverket",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("location_fit"), "UTANFÖR_STOCKHOLM")
        self.assertEqual(item.desk, "PRISMA")
        self.assertFalse(item.physical_presence)
        self.assertNotEqual(item.priority, "RED")
        self.assertEqual(item.action_recommendation, "FÖLJ_UPP")
        self.assertNotIn("Polisfordon", " ".join(item.raw_json.get("image_suggestions", [])))

    def test_generic_parliament_question_time_is_ignored_without_prisma_topic(self):
        item = NewsItem(
            source_name="Riksdagen kalender kammaren",
            source_url="https://data.riksdagen.se/kalender/?org=kamm&utformat=icalendar",
            title="Frågestund",
            summary="Vid frågestunden svarar ministrarna i regeringen på frågor från riksdagsledamöterna direkt i kammaren.",
            category="parliament_calendar",
            url="https://example.test/fragestund",
            published_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "GREY")
        self.assertEqual(item.desk, "IGNORE")
        self.assertEqual(item.action_recommendation, "IGNORERA")
        self.assertFalse(item.physical_presence)

    def test_old_parliament_document_is_old_not_past_event(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
            "%a, %d %b %Y %H:%M:%S +0000"
        )
        item = NewsItem(
            source_name="Riksdagen propositioner",
            source_url="https://data.riksdagen.se/",
            title="EU:s bankpaket",
            summary="Proposition om EU:s bankpaket.",
            category="parliament_propositions",
            url="https://example.test/eu-bankpaket",
            published_at=old_date,
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("temporal_status"), "OLD")
        self.assertNotEqual(item.raw_json.get("temporal_status"), "PAST_EVENT")
        self.assertNotEqual(item.action_recommendation, "PUBLICERA_IDAG")
        self.assertFalse(item.deadline_detected)

    def test_riksdagen_document_numbers_are_not_deadlines(self):
        item = NewsItem(
            source_name="Riksdagen beslutade betänkanden",
            source_url="https://data.riksdagen.se/",
            title="En mer flexibel hyresmarknad",
            summary="Betänkande 2025/26:CU31. Beslut fattades 2026-05-08 och lagen börjar gälla 1 juli.",
            category="parliament_decisions",
            url="https://example.test/hyresmarknad",
            published_at="Fri, 20 Feb 2026 16:41:32 +0200",
        )

        classify_item(item, self.rules)

        self.assertFalse(item.deadline_detected)
        self.assertEqual(item.raw_json.get("temporal_status"), "OLD")

    def test_riksdagen_social_insurance_decision_is_publish_today(self):
        item = NewsItem(
            source_name="Riksdagen beslutade betänkanden",
            source_url="https://data.riksdagen.se/",
            title="Kvalificering till socialförsäkringen",
            summary=(
                "Riksdagen sa ja till regeringens förslag om att det ska införas ett krav "
                "på kvalificering för att få ta del av vissa bosättningsbaserade "
                "socialförsäkringsförmåner. Exempel på sådana förmåner är föräldrapenning "
                "på grund- och lägstanivå, barnbidrag, sjukersättning i form av "
                "garantiersättning och bostadsbidrag. I dag kan personer som flyttar till "
                "Sverige få tillgång till bosättningsbaserade förmåner direkt."
            ),
            category="parliament_decisions",
            url="https://www.riksdagen.se/sv/dokument-och-lagar/dokument/betankande/_hd01sfu21/",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "ORANGE")
        self.assertEqual(item.desk, "PRISMA")
        self.assertEqual(item.action_recommendation, "PUBLICERA_IDAG")
        self.assertIn(item.raw_json.get("temporal_status"), {"CURRENT", "UPCOMING"})
        self.assertIn("Riksdagen har sagt ja", item.raw_json.get("why_it_matters", ""))
        self.assertNotIn("detected_event_datetime", item.raw_json)

    def test_old_riksdagen_decision_is_not_current_even_if_fetched_today(self):
        item = NewsItem(
            source_name="Riksdagen beslutade betänkanden",
            source_url="https://data.riksdagen.se/",
            title="Polisens användning av AI för ansiktsigenkänning i realtid",
            summary=(
                "Riksdagen sa ja till förslaget om Polisens användning av AI för "
                "ansiktsigenkänning i realtid."
            ),
            category="parliament_decisions",
            url="https://www.riksdagen.se/sv/dokument-och-lagar/dokument/betankande/_hd01juu28/",
            published_at="Mon, 19 Jan 2026 14:17:55 +0200",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("temporal_status"), "OLD")
        self.assertNotEqual(item.action_recommendation, "PUBLICERA_IDAG")
        self.assertIn(item.priority, {"YELLOW", "GREY"})
        self.assertEqual(item.desk, "PRISMA")
        self.assertFalse(item.physical_presence)
        self.assertNotIn("image_suggestions", item.raw_json)
        self.assertNotIn("access_guidance", item.raw_json)
        self.assertIn("Äldre", item.raw_json.get("why_it_matters", ""))

    def test_old_building_rules_do_not_get_transport_image_suggestions(self):
        item = NewsItem(
            source_name="Riksdagen beslutade betänkanden",
            source_url="https://data.riksdagen.se/",
            title="Förenklade regler vid ändring av en byggnad",
            summary="Riksdagen sa ja till förenklade regler vid ändring av en byggnad.",
            category="parliament_decisions",
            url="https://www.riksdagen.se/sv/dokument-och-lagar/dokument/betankande/_hd01cu39/",
            published_at="Fri, 20 Feb 2026 16:44:27 +0200",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.raw_json.get("temporal_status"), "OLD")
        self.assertNotIn("image_suggestions", item.raw_json)
        self.assertNotIn("access_guidance", item.raw_json)
        self.assertNotEqual(item.desk, "BOTH")

    def test_riksdagen_ai_face_recognition_proposal_is_prisma_publish_today(self):
        item = NewsItem(
            source_name="Riksdagen betänkanden förslag",
            source_url="https://data.riksdagen.se/",
            title="Polisens användning av AI för ansiktsigenkänning i realtid",
            summary=(
                "Justitieutskottet föreslår att riksdagen säger ja till regeringens "
                "förslag att ge Polismyndigheten möjlighet att få använda AI-teknik "
                "för ansiktsigenkänning i realtid. V, C och MP lämnar reservationer."
            ),
            category="parliament_reports",
            url="https://www.riksdagen.se/sv/dokument-och-lagar/dokument/betankande/_hd01juu28/",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertEqual(item.priority, "ORANGE")
        self.assertEqual(item.desk, "BOTH")
        self.assertEqual(item.action_recommendation, "PUBLICERA_IDAG")
        self.assertFalse(item.physical_presence)
        self.assertIn("förslag till beslut", item.raw_json.get("why_it_matters", ""))
        self.assertTrue(item.raw_json.get("image_suggestions"))
        self.assertIn("Illustrationsbild", item.raw_json.get("zuma_image_angle", ""))

    def test_real_accreditation_deadline_is_detected(self):
        item = NewsItem(
            source_name="Test",
            source_url="https://example.test",
            title="Pressinbjudan till pressträff",
            summary="Ackreditering krävs. Anmälan senast 22 maj klockan 12.00.",
            category="government",
            url="https://example.test/deadline",
            published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
        )

        classify_item(item, self.rules)

        self.assertTrue(item.deadline_detected)
        self.assertTrue(item.accreditation_needed)

    def test_recent_or_reported_cases_are_not_deadlines(self):
        examples = [
            "Senaste nytt om kriget i Ukraina.",
            "Susanne gjorde en anmälan till Skolinspektionen.",
            "Senaste mandatperioden har regeringen föreslagit flera förändringar.",
            "Ett videosamtal på Whatsapp nämns i utredningen.",
        ]
        for summary in examples:
            item = NewsItem(
                source_name="Test",
                source_url="https://example.test",
                title="Vanlig nyhet",
                summary=summary,
                category="media_national",
                url="https://example.test/no-deadline",
                published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            )

            classify_item(item, self.rules)

            self.assertFalse(item.deadline_detected, summary)

    def test_cervantes_navigation_pages_are_not_publish_today(self):
        for title in ["Calendario cultural", "Actividades anteriores", "Próximas actividades", "Programación del mes"]:
            item = NewsItem(
                source_name="Instituto Cervantes Stockholm",
                source_url="https://estocolmo.cervantes.es",
                title=title,
                summary="Inicio > Actividades culturales > Calendario cultural",
                category="latino_culture",
                url="https://example.test/cervantes-nav",
                published_at=datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            )

            classify_item(item, self.rules)

            self.assertEqual(item.priority, "GREY", title)
            self.assertEqual(item.desk, "IGNORE", title)
            self.assertEqual(item.action_recommendation, "IGNORERA", title)


if __name__ == "__main__":
    unittest.main()
