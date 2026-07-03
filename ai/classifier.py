from __future__ import annotations

import os
import re
from typing import Iterable

from desk.models import NewsItem
from desk.scoring import (
    apply_temporal_guardrails,
    calculate_score,
    detect_deadline,
    detect_swedish_event_datetime,
)

GENERIC_NON_STORY_TITLES = {
    "calendario cultural",
    "actividades culturales",
    "actividades anteriores",
    "próximas actividades",
    "proximas actividades",
    "programación del mes",
    "programacion del mes",
    "información general",
    "informacion general",
}

HIGH_IMPACT_PRISMA_TERMS = {
    "socialförsäkring",
    "socialförsäkringen",
    "socialförsäkringsförmåner",
    "barnbidrag",
    "bostadsbidrag",
    "föräldrapenning",
    "flerbarnstillägg",
    "äldreförsörjningsstöd",
    "bostadstillägg",
    "försörjningsstöd",
    "sjukersättning",
    "aktivitetsersättning",
    "medborgarskap",
    "migration",
    "Migrationsverket",
    "anhöriginvandring",
    "familjeåterförening",
    "uppehållstillstånd",
    "återvändande",
    "återvändandecenter",
    "mottagningscenter",
    "arbetskraftsinvandring",
    "arbetstillstånd",
    "lönegolv",
    "migrationsminister",
    "Johan Forssell",
    "Johan Britz",
    "laglig vistelse",
    "nyanlända",
    "invandrare",
    "barnfattigdom",
    "funktionsnedsättning",
    "barn",
    "barns hälsa",
    "barns trygghet",
    "psykisk hälsa",
    "psykisk ohälsa",
    "mental hälsa",
    "barn och unga",
    "ungdomars hälsa",
    "elevhälsa",
    "digitala miljöer",
    "åldersgräns",
    "sociala medier",
    "skärmtid",
    "unga",
    "ungdomar",
    "socialminister",
    "Jakob Forssmed",
    "äldreomsorg",
    "äldreboende",
    "övergrepp",
    "missförhållanden",
    "omsorg",
    "vårdskandal",
    "Linda Lindberg",
    "nationella säkerhetsrådgivaren",
    "säkerhetsrådgivaren",
    "säkerhetsråd",
    "nationell säkerhet",
    "civilbefolkningen",
    "civilt försvar",
    "civil beredskap",
    "krisberedskap",
    "beredskap",
    "varningssystem",
    "SE Alert",
    "VMA",
    "mobilvarning",
    "AI",
    "artificiell intelligens",
    "ansiktsigenkänning",
    "Polismyndigheten",
    "polisen",
    "integritet",
    "övervakning",
    "kameraövervakning",
    "biometrisk",
    "biometriska",
    "personuppgifter",
    "rättssäkerhet",
    "brottsbekämpning",
}

COMMON_SWEDISH_ARTIST_OR_NAME_WORDS = {
    "Benjamin",
    "Ingrosso",
    "Lars",
    "Winnerbäck",
    "Håkan",
    "Hellström",
    "Veronica",
    "Maggio",
    "Molly",
    "Sanden",
    "Carola",
}


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    matches: list[str] = []
    for term in terms:
        clean_term = str(term).strip()
        if not clean_term:
            continue
        pattern = r"(?<![0-9A-Za-zÅÄÖåäö])" + re.escape(clean_term.lower()) + r"(?![0-9A-Za-zÅÄÖåäö])"
        if re.search(pattern, text.lower()):
            matches.append(clean_term)
    return matches


def _latin_artist_name_patterns(text: str) -> list[str]:
    candidates = re.findall(r"\b([A-ZÅÄÖ][a-zåäö]+(?:\s+[A-ZÅÄÖ][a-zåäö]+){1,2})\b", text)
    ignored = {
        "Stockholm Sverige",
        "Strawberry Arena",
        "Avicii Arena",
        "Gröna Lund",
        "Debaser Stockholm",
        "Kollektivet Livet",
    }
    matches: list[str] = []
    for candidate in candidates:
        words = candidate.split()
        if candidate in ignored:
            continue
        if any(word in COMMON_SWEDISH_ARTIST_OR_NAME_WORDS for word in words):
            continue
        if candidate not in matches:
            matches.append(candidate)
    return matches[:5]


def score_latino_music_event(text: str, rules: dict) -> tuple[int, dict]:
    text_lower = text.lower()
    venue_hits = [v for v in rules.get("zuma_stockholm_music_venues", []) if v in text_lower]
    genre_hits = [g for g in rules.get("zuma_latino_music_genre_terms", []) if g in text_lower]
    significance_hits = [s for s in rules.get("zuma_international_significance_terms", []) if s in text_lower]
    artist_pattern_hits = _latin_artist_name_patterns(text)

    matched = {
        "venue": venue_hits,
        "genre": genre_hits,
        "significance": significance_hits,
        "artist_pattern": artist_pattern_hits,
    }

    if venue_hits and significance_hits and (genre_hits or artist_pattern_hits):
        return 8, matched
    if venue_hits and genre_hits:
        return 4, matched
    return 0, matched


def image_suggestions_for_item(
    item: NewsItem,
    text: str,
    prisma_terms: list[str],
    zuma_terms: list[str],
    stockholm_terms: list[str],
) -> list[str]:
    lowered = text.lower()
    suggestions: list[str] = []

    if _contains_any(text, ["ansiktsigenkänning", "ai-teknik", "artificiell intelligens", "övervakning", "biometrisk"]):
        suggestions.extend(
            [
                "Övervakningskameror i offentlig Stockholmsmiljö, till exempel tunnelbana, stationer eller citystråk.",
                "Poliser i yttre tjänst i Stockholm, fotograferade generellt och sakligt.",
                "Riksdagen eller Polismyndighetens exteriörer som tydlig svensk myndighetsbild.",
                "Människor i rörelse genom kamerabevakade offentliga miljöer, utan att peka ut enskilda personer.",
            ]
        )

    if _contains_any(text, ["varningssystem", "SE Alert", "mobilvarning", "civilbefolkningen", "civilt försvar", "civil beredskap", "krisberedskap"]):
        suggestions.extend(
            [
                "Närbild på mobiltelefon med varningssystem eller SE Alert-skärm, gärna i handen framför neutral stadsmiljö.",
                "Pressträffsmiljö med mobilgrafik, ansvariga politiker eller myndighetsföreträdare och TV-kameror.",
                "Generella beredskapsbilder: informationsskyltar, blåljus, sirener eller människor som tar emot mobilvarning.",
            ]
        )

    if _contains_any(text, ["polisen", "polismyndigheten", "brottsbekämpning"]):
        suggestions.extend(
            [
                "Polisfordon, polisstation eller uniformerade poliser i vardaglig stadsmiljö.",
                "Trygghets- eller säkerhetsmiljöer i Stockholm: entréer, spärrar, stationer, kameraskyltar.",
            ]
        )

    if _contains_any(
        text,
        [
            "Flygvapnet",
            "flygvapnet 100 år",
            "flygvapenjubileum",
            "överflygning",
            "flyguppvisning",
            "flygformation",
            "flygshow",
            "JAS Gripen",
            "Gripen",
            "luftfartyg",
        ],
    ):
        suggestions.extend(
            [
                "Flygformationer över Stockholms slott, centrala Stockholm eller vattenlinjen med tydlig platsmarkör.",
                "JAS Gripen, historiska flygplan, transportflyg och helikoptrar i formation mot igenkännbar Stockholmssiluett.",
                "Publik som tittar upp, fotograferar eller samlas vid Slottet, Karlaplan, Sergels torg eller kajerna.",
                "Flygarmonumentet, vaktparad, högvaktsavlösning eller militärmusik som markbild till jubileet.",
                "Detaljbilder på flaggor, uniformer, musikkårer, flygplansspår och människor i city under överflygningen.",
            ]
        )

    if _contains_any(text, ["SL", "kollektivtrafik", "tåg", "väg", "trafik", "Arlanda", "flyg"]):
        suggestions.extend(
            [
                "Resenärer, perronger, spärrlinjer eller trafikmiljöer i Stockholms län.",
                "Detaljbilder på skyltar, förseningstavlor, biljettsystem eller fordon kopplade till nyheten.",
            ]
        )

    if _contains_any(text, ["socialförsäkring", "barnbidrag", "bostadsbidrag", "Försäkringskassan", "Skatteverket", "Migrationsverket"]):
        suggestions.extend(
            [
                "Exteriörer vid berörd myndighet, till exempel Försäkringskassan, Skatteverket eller Migrationsverket.",
                "Neutrala vardagsbilder på barnfamiljer, bostadsområden eller myndighetskontakt utan att identifiera utsatta personer.",
            ]
        )

    if _contains_any(text, ["barns hälsa", "barns trygghet", "digitala miljöer", "åldersgräns", "sociala medier", "skärmtid"]):
        suggestions.extend(
            [
                "Barn och unga med mobiltelefoner i neutral offentlig miljö, fotograferat respektfullt utan identifierande närbilder.",
                "Mobilskärmar, sociala medier-symbolik eller händer med telefon som generell bild om digital vardag.",
                "Socialdepartementet, Regeringskansliet eller pressträffsmiljö med ansvarig minister som politisk bild.",
            ]
        )

    if _contains_any(text, ["psykisk hälsa", "psykisk ohälsa", "mental hälsa", "barn och unga", "ungdomars hälsa", "elevhälsa"]):
        suggestions.extend(
            [
                "Jakob Forssmed eller ansvarig politiker vid pressträff om barn och ungas psykiska hälsa.",
                "Neutrala bilder på unga i skol- eller stadsmiljö, fotograferat respektfullt utan att peka ut sårbara personer.",
                "Socialdepartementet, vårdmiljö eller skolmiljö som generell bild till psykisk hälsa-politiken.",
            ]
        )

    if _contains_any(text, ["äldreomsorg", "äldreboende", "övergrepp", "missförhållanden", "omsorg", "vårdskandal"]):
        suggestions.extend(
            [
                "Partiföreträdare eller ansvarig politiker under pressträff, med tydligt pressuppbåd och podie.",
                "Neutrala exteriörer vid äldreboende eller kommunal omsorgsmiljö, utan att identifiera boende eller anhöriga.",
                "Omsorgsmiljöer, rullatorer, entréer eller kommunskyltar som respektfull generell bild om äldreomsorg.",
            ]
        )

    if _contains_any(text, ["arbetskraftsinvandring", "arbetstillstånd", "lönegolv", "migrationsminister"]):
        suggestions.extend(
            [
                "Migrationsverket, arbetsplatser eller citymiljöer med människor på väg till arbete som generell bild om arbetskraftsinvandring.",
                "Regeringskansliet, Rosenbad eller riksdagsmiljö som politisk bild till pressbeskedet.",
                "Neutrala bilder på arbetsmiljöer inom bristyrken, utan att peka ut enskilda migranter.",
            ]
        )

    if _contains_any(text, ["valmanifest", "valkampanj", "valupptakt", "partiledare", "partiledartal", "möter journalister", "träffar journalister"]):
        suggestions.extend(
            [
                "Partiledaren vid pressträffen, gärna med valmanifest, partisymboler, podie eller pressuppbåd i bild.",
                "Bilder på kampanjmaterial, affischer, valsedlar eller partiets lokal/exteriör som visar valrörelsen konkret.",
                "Journalister, kameror och politiker i Stockholmsmiljö som tydlig nyhetsbild från valrörelsen.",
            ]
        )

    if _contains_any(text, ["Stockholm Marathon", "maraton", "marathon", "medaljutdelning", "målgång", "folkfest"]):
        suggestions.extend(
            [
                "Målgång, medaljutdelning och löpare vid Stockholm Stadion med tydlig Stockholm-känsla.",
                "Breda bilder på publik, löparmassor och stadsmiljöer längs banan som visar folkfesten.",
                "Detaljer: medaljer, nummerlappar, svettiga målgestalter och internationella deltagare.",
            ]
        )

    if _contains_any(text, ["fotbolls-VM", "fotbolls VM", "landslaget", "förbundskapten", "ledarstab", "spelarhotellet"]):
        suggestions.extend(
            [
                "Landslagets ledarstab eller spelare vid pressbord, sponsorvägg eller spelarhotell inför VM.",
                "Scandic Park, hotellentré, pressuppbåd och TV-kameror som visar landslagets VM-uppladdning i Stockholm.",
                "Detaljer med landslagssymboler, träningskläder, mikrofoner och VM-relaterad pressmiljö.",
            ]
        )

    if _contains_any(
        text,
        [
            "reggaeton",
            "latin trap",
            "salsa",
            "bachata",
            "cumbia",
            "merengue",
            "strawberry arena",
            "avicii arena",
            "debaser",
            "annexet",
            "fållan",
            "slaktkyrkan",
            "fasching",
        ],
    ):
        suggestions.extend(
            [
                "Publik och köer vid arenan eller konsertlokalen med tydlig Stockholm-platsmarkör.",
                "Exteriör på Strawberry Arena, Avicii Arena, Debaser eller aktuell konsertlokal med skyltning eller affischer.",
                "Fans med flaggor, artisttröjor eller latinamerikanska symboler, fotograferat respektfullt i offentlig miljö.",
                "Breda publikbilder, entréflöden och city/arena-miljö som visar latinamerikansk musik som Stockholmshändelse.",
            ]
        )

    if _contains_any(text, ["Veterandagen", "veterandag", "Sjöhistoriska", "kransnedläggning", "militär ceremoni"]):
        suggestions.extend(
            [
                "Statsminister, försvarsminister, talman och veteraner vid ceremonin, gärna med fanor eller honnör.",
                "Sjöhistoriska museet och ceremonimiljön som tydlig Stockholm- och försvarsbild.",
                "Detaljer på uniformer, medaljer, kransar, flaggor och publik under veterandagen.",
            ]
        )

    if _contains_any(
        text,
        [
            "guldbröllop",
            "bröllopsdag",
            "bröllopsjubileum",
            "kungligt jubileum",
            "Te Deum",
            "Vasaorden",
            "kungaslupen",
            "hästkortege",
            "kortege",
        ],
    ):
        suggestions.extend(
            [
                "Kungaparet under kortege, rodd eller ceremoni, med tydlig Stockholmsmiljö och pressuppbåd.",
                "Publik, flaggor, avspärrningar och kortege längs Skeppsbron, Strandvägen, Stureplan eller Kungsträdgården.",
                "Vasaorden, Stockholms ström eller kungaslupen som stark visuell huvudbild om firandet sker på vattnet.",
                "Slottskyrkan, Kungliga slottet eller Kungliga Operan exteriört med gäster, uniformer och galakläder.",
            ]
        )

    if item.category in {"parliament_reports", "parliament_decisions", "parliament_propositions"} and (
        prisma_terms or zuma_terms
    ):
        suggestions.append("Riksdagen exteriört eller ledamöter/media i riksdagsmiljö som generell bild till beslutsprocessen.")

    unique: list[str] = []
    for suggestion in suggestions:
        if suggestion not in unique:
            unique.append(suggestion)
    return unique[:5]


def access_guidance_for_item(item: NewsItem, text: str) -> list[str]:
    lowered = text.lower()
    guidance: list[str] = []

    if any(term in lowered for term in ["partiledardebatt", "kulturhuset stadsteatern", "kulturhuset", "stadsteatern"]):
        guidance.extend(
            [
                "Kontakta arrangörens presskontakt först: den som står bakom debatten styr oftast ackreditering och fotoposition.",
                "Kontakta även Kulturhuset Stadsteaterns press/kommunikation om platsen, insläpp, pressplats och eventuella fotoregler.",
                "Fråga uttryckligen om: pressackreditering, samlingstid, var fotografer får stå, om flash är tillåtet och om det finns möjlighet till bilder före/efter debatten.",
            ]
        )

    if "riksdagen" in lowered or "riksdagens presscenter" in lowered:
        guidance.append(
            "Vid Riksdagen: kontrollera pressackreditering/presskort och kontakta Riksdagens presscenter om tillträde, fotoregler och samlingsplats."
        )

    if any(
        term in lowered
        for term in [
            "flygvapnet",
            "överflygning",
            "flyguppvisning",
            "flygformation",
            "flygarmonumentet",
            "högvaktsavlösning",
            "vaktparad",
            "jas gripen",
        ]
    ):
        guidance.extend(
            [
                "Kontakta Försvarsmaktens pressjour om exakt tid, flygrutt, formationer, medverkan på marken och eventuella pressytor.",
                "För Stockholm: kontrollera bästa fotopositioner vid Slottet, Karlaplan, Skeppsholmen, Strömbron, Norrbro, kajerna och öppna cityytor.",
                "Fråga om väderreserv, ändrad flygrutt, säkerhetsavstånd, drönarförbud och om foto vid militär ceremoni kräver särskilda instruktioner.",
            ]
        )

    if any(
        term in lowered
        for term in [
            "kungaparet",
            "kung carl xvi gustaf",
            "drottning silvia",
            "guldbröllop",
            "bröllopsdag",
            "te deum",
            "vasaorden",
            "slottskyrkan",
            "kungliga operan",
        ]
    ):
        guidance.extend(
            [
                "Kontakta Kungahusets informationsavdelning/mediecenter om pressackreditering, fotopositioner, poolfoto, tider och säkerhetskontroll.",
                "Vid kortege eller offentligt firande: kontrollera även Stockholms stad, Polisen och aktuell platsarrangör för avspärrningar och tillåtna fotopositioner.",
                "Fråga uttryckligen om ackrediteringsdeadline, presslegitimation, samlingsplats, poolregler och om rörlig fotografering är tillåten.",
            ]
        )

    if item.category == "politics" or any(term in lowered for term in ["partiet", "partiledare", "valmanifest", "valkampanj"]):
        guidance.append(
            "Kontakta partiets pressjour och be om fototillstånd, exakt plats, tider och om partiledaren kan fotograferas separat."
        )

    if any(term in lowered for term in ["marathon", "maraton", "fotbolls-vm", "landslaget", "spelarhotellet"]):
        guidance.append(
            "Vid sportevent: leta efter arrangörens media/press office och fråga om mediaackreditering, bib/pressväst, fotopositioner och mixed zone."
        )

    unique: list[str] = []
    for item_text in guidance:
        if item_text not in unique:
            unique.append(item_text)
    return unique[:5]


def classify_item(item: NewsItem, rules: dict) -> NewsItem:
    text = item.text_for_analysis
    normalized_title = item.title.strip().lower()
    red_people = _contains_any(text, rules.get("red_alert_people", []))
    red_topics = _contains_any(text, rules.get("red_alert_topics", []))
    red_events = _contains_any(text, rules.get("red_alert_event_words", []))
    red_places = _contains_any(text, rules.get("red_alert_places", []))
    hard_terms = _contains_any(text, rules.get("hard_red_terms", []))
    zuma_terms = _contains_any(text, rules.get("zuma_terms", []))
    zuma_picture_event_terms = _contains_any(text, rules.get("zuma_picture_event_terms", []))
    zuma_picture_subject_terms = _contains_any(text, rules.get("zuma_picture_subject_terms", []))
    zuma_picture_place_terms = _contains_any(text, rules.get("zuma_picture_place_terms", []))
    prisma_terms = _contains_any(text, rules.get("prisma_terms", []))
    consequence_markers = rules.get("prisma_consequence_markers", [])
    matched_consequence_markers = _contains_any(text, consequence_markers)
    has_consequence_marker = bool(matched_consequence_markers)
    generic_prisma_terms = {
        "Riksdagen",
        "proposition",
        "betänkande",
        "interpellation",
        "skriftlig fråga",
        "KU-anmälan",
        "kammaren",
        "frågestund",
        "partiledardebatt",
        "interpellationsdebatt",
    }
    specific_prisma_terms = [term for term in prisma_terms if term not in generic_prisma_terms]
    high_impact_prisma_terms_lookup = {term.lower() for term in HIGH_IMPACT_PRISMA_TERMS}
    high_impact_prisma_terms = [
        term for term in specific_prisma_terms if term.lower() in high_impact_prisma_terms_lookup
    ]
    mail_terms = _contains_any(text, rules.get("mail_trigger_words", [])) if item.category == "mail" else []
    sweden_terms = _contains_any(text, rules.get("sweden_relevance_terms", []))
    foreign_terms = _contains_any(text, rules.get("foreign_low_relevance_terms", []))
    major_visual_accident_terms = _contains_any(text, rules.get("major_visual_accident_terms", []))
    stockholm_terms = _contains_any(text, rules.get("stockholm_priority_terms", []))
    outside_stockholm_terms = _contains_any(text, rules.get("outside_stockholm_terms", []))
    latino_music_score, latino_music_matches = score_latino_music_event(text, rules)
    is_media = item.category in {"media_breaking", "media_national", "media_stockholm", "media_economy"}
    is_prisma_topic = bool(specific_prisma_terms or item.category in {
        "stockholm_city",
        "stockholm_city_press",
        "transport",
        "rail",
        "aviation",
        "transport_infrastructure",
        "culture",
        "events",
        "latino_culture",
        "latino_community",
        "youth_family",
        "media_stockholm",
        "media_economy",
        "politics",
        "concerts_all_stockholm",
        "concert_venue",
        "arena_stockholm",
    })

    has_press_event = bool(
        _contains_any(
            text,
            [
                "pressträff",
                "pressinbjudan",
                "presskonferens",
                "pressbriefing",
                "gemensam pressbriefing",
                "media invitation",
            ],
        )
    )
    hard_red = has_press_event and bool(hard_terms)

    item.deadline_detected, item.deadline_date = detect_deadline(text)
    item.accreditation_needed = True if _contains_any(text, ["ackreditering", "föranmälan", "RSVP", "anmälan senast"]) else None
    item.physical_presence = bool(
        has_press_event
        or red_places
        or zuma_terms
        or (zuma_picture_event_terms and (stockholm_terms or outside_stockholm_terms or zuma_picture_place_terms))
    )
    if is_media:
        clear_media_event = bool(has_press_event)
        swedish_major_visual = bool(sweden_terms and major_visual_accident_terms)
        item.physical_presence = clear_media_event or swedish_major_visual

    zuma_picture_value = bool(
        item.physical_presence
        and (
            (zuma_picture_event_terms and (zuma_picture_subject_terms or zuma_picture_place_terms))
            or (major_visual_accident_terms and sweden_terms)
            or (item.category in {"royal", "defence"} and (zuma_picture_event_terms or zuma_picture_place_terms))
            or (item.category == "parliament_calendar" and zuma_picture_event_terms and zuma_picture_subject_terms)
        )
    )
    if is_media and not zuma_picture_value:
        item.physical_presence = False

    zuma_score = len(zuma_terms) * 2 + len(red_people) + len(red_topics) + len(red_places)
    zuma_score += latino_music_score
    prisma_score = len(specific_prisma_terms) * 2
    image_suggestions = image_suggestions_for_item(item, text, prisma_terms, zuma_terms, stockholm_terms)
    has_news_agency_visual_theme = bool(
        re.search(
            r"\b(ansiktsigenkänning|ai-teknik|artificiell intelligens|övervakning|kameraövervakning|"
            r"biometrisk|polisen|polismyndigheten|brottsbekämpning|säkerhet|sl|kollektivtrafik|"
            r"tåg|väg|trafik|arlanda|flyg)\b",
            text,
            flags=re.IGNORECASE,
        )
    )
    has_zuma_illustration_value = bool(
        image_suggestions
        and has_news_agency_visual_theme
        and (
            stockholm_terms
            or item.category in {"parliament_reports", "parliament_decisions", "parliament_propositions", "media_stockholm"}
        )
    )
    is_committee_proposal = bool(
        item.category == "parliament_reports"
        and high_impact_prisma_terms
        and re.search(
            r"\b(utskottet\s+föreslår|föreslår\s+att\s+riksdagen|ställer\s+sig\s+bakom|förslag\s+till\s+beslut)\b",
            text,
            flags=re.IGNORECASE,
        )
    )
    election_terms = _contains_any(
        text,
        [
            "valmanifest",
            "valkampanj",
            "valupptakt",
            "riksdagsval",
            "valet 2026",
            "partiledare",
            "partiledartal",
            "Simona Mohamsson",
            "Magdalena Andersson",
            "Jimmie Åkesson",
            "Nooshi Dadgostar",
            "Ebba Busch",
            "Muharrem Demirok",
            "Daniel Helldén",
            "Amanda Lind",
            "Johan Pehrson",
            "Linda Lindberg",
        ],
    )
    political_press_event = bool(
        has_press_event
        and (item.category == "politics" or election_terms)
        and (election_terms or zuma_picture_subject_terms)
    )
    political_media_availability = bool(
        (item.category == "politics" or election_terms)
        and election_terms
        and _contains_any(
            text,
            [
                "möter journalister",
                "träffar journalister",
                "kommenterar",
                "intervju",
                "medieträff",
                "riksdagen",
            ],
        )
    )
    party_leader_debate_picture_event = bool(
        (stockholm_terms or "stockholm" in text.lower())
        and _contains_any(text, ["partiledardebatt"])
        and (
            zuma_picture_subject_terms
            or _contains_any(
                text,
                [
                    "Simona Mohamsson",
                    "Magdalena Andersson",
                    "Jimmie Åkesson",
                    "Nooshi Dadgostar",
                    "Ebba Busch",
                    "Muharrem Demirok",
                    "Daniel Helldén",
                    "Amanda Lind",
                ],
            )
        )
    )
    stockholm_sports_picture_event = bool(
        (stockholm_terms or "stockholm" in text.lower())
        and _contains_any(
            text,
            [
                "Stockholm Marathon",
                "maraton",
                "marathon",
                "medaljutdelning",
                "målgång",
                "lopp",
                "folkfest",
                "fotbolls-VM",
                "fotbolls VM",
                "landslaget",
                "förbundskapten",
                "ledarstab",
                "spelarhotellet",
            ],
        )
    )
    stockholm_ceremony_picture_event = bool(
        (stockholm_terms or "stockholm" in text.lower())
        and _contains_any(text, ["Veterandagen", "veterandag", "Sjöhistoriska", "militär ceremoni", "kransnedläggning"])
        and (red_people or red_topics or zuma_picture_subject_terms)
    )
    stockholm_military_air_event = bool(
        (stockholm_terms or "stockholm" in text.lower())
        and _contains_any(
            text,
            [
                "Flygvapnet",
                "flygvapnet 100 år",
                "flygvapenjubileum",
                "överflygning",
                "flyguppvisning",
                "flygformation",
                "flygshow",
                "JAS Gripen",
                "Gripen",
                "luftfartyg",
            ],
        )
        and (
            item.category == "defence"
            or _contains_any(text, ["Försvarsmakten", "militär", "jubileum", "100 år", "vaktparad", "högvaktsavlösning"])
        )
    )
    royal_jubilee_picture_event = bool(
        (stockholm_terms or "stockholm" in text.lower())
        and (
            item.category == "royal"
            or red_people
            or zuma_picture_subject_terms
            or _contains_any(text, ["kungaparet", "Kung Carl XVI Gustaf", "Drottning Silvia", "kungafamiljen"])
        )
        and _contains_any(
            text,
            [
                "guldbröllop",
                "bröllopsdag",
                "bröllopsjubileum",
                "kungligt jubileum",
                "Te Deum",
                "Vasaorden",
                "kungaslupen",
                "hästkortege",
                "kortege",
                "Slottskyrkan",
                "Kungliga Operan",
            ],
        )
    )
    civil_alert_picture_event = bool(
        (stockholm_terms or "stockholm" in text.lower())
        and has_press_event
        and _contains_any(
            text,
            ["varningssystem", "SE Alert", "mobilvarning", "civilbefolkningen", "civilt försvar", "civil beredskap", "krisberedskap"],
        )
    )
    if item.category in {"stockholm_city", "stockholm_city_press", "transport", "rail", "aviation", "transport_infrastructure"}:
        prisma_score += 2
    if item.category in {"latino_culture", "latino_community", "culture", "youth_family"}:
        prisma_score += 3
    if item.category in {"government", "prime_minister", "nato", "royal", "defence"}:
        zuma_score += 3
    if mail_terms:
        zuma_score += 1
        prisma_score += 1

    urgent_prisma_press_event = bool(
        has_press_event
        and item.category in {"government", "prime_minister", "press_releases", "mail"}
        and high_impact_prisma_terms
    )

    if latino_music_score >= 8:
        item.priority = "ORANGE"
        item.desk = "BOTH"
        item.physical_presence = True
        item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Latino- eller spanskspråkig musik med Stockholm-arena och internationell betydelsesignal: starkt ZUMA-bildläge och tydlig Prisma-community-relevans."
        )
    elif latino_music_score >= 4:
        item.priority = "BLUE"
        item.desk = "BOTH"
        item.physical_presence = True
        item.action_recommendation = "FÖLJ_UPP"
        item.raw_json["why_it_matters"] = (
            "Latino- eller spanskspråkigt musikevent i Stockholm: relevant för Prisma-community och möjlig ZUMA-featurebild."
        )
    elif stockholm_military_air_event:
        item.priority = "RED"
        item.desk = "ZUMA" if not is_prisma_topic else "BOTH"
        item.physical_presence = True
        item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Militär flyguppvisning eller historisk överflygning över Stockholm: mycket starkt ZUMA-bildläge och tydlig Prisma-förklaring. "
            "Kontrollera tid, rutt och fotoposition direkt."
        )
    elif royal_jubilee_picture_event:
        item.priority = "RED"
        item.desk = "ZUMA" if not is_prisma_topic else "BOTH"
        item.physical_presence = True
        item.accreditation_needed = True if item.accreditation_needed is None else item.accreditation_needed
        item.action_recommendation = "SÖK_ACKREDITERING"
        item.raw_json["why_it_matters"] = (
            "Kungligt jubileum eller firande i Stockholm med kortege, ceremoni eller folkfest: mycket starkt ZUMA-bildläge. "
            "Kontrollera pressackreditering och fotoposition direkt."
        )
    elif party_leader_debate_picture_event:
        item.priority = "RED"
        item.desk = "ZUMA" if not specific_prisma_terms else "BOTH"
        item.physical_presence = True
        item.accreditation_needed = True if item.accreditation_needed is None else item.accreditation_needed
        item.action_recommendation = "SÖK_ACKREDITERING"
        item.raw_json["why_it_matters"] = (
            "Partiledardebatt i Stockholm: starkt valrörelse- och ZUMA-bildläge. Kontrollera ackreditering och fotoposition direkt."
        )
    elif civil_alert_picture_event:
        item.priority = "RED"
        item.desk = "BOTH"
        item.physical_presence = True
        item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Pressträff i Stockholm om civil varning eller beredskap: stark Prisma-story och konkret ZUMA-bildläge."
        )
    elif stockholm_ceremony_picture_event:
        item.priority = "RED"
        item.desk = "ZUMA" if not is_prisma_topic else "BOTH"
        item.physical_presence = True
        item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Veteran- eller försvarsceremoni i Stockholm med statsledning: starkt ZUMA-bildläge."
        )
    elif stockholm_sports_picture_event:
        item.priority = "ORANGE"
        item.desk = "ZUMA"
        item.physical_presence = True
        item.action_recommendation = "FÖLJ_UPP"
        item.raw_json["why_it_matters"] = (
            "Stort Stockholm-event med tydligt internationellt bildvärde: sport, folkfest och stadsmiljö."
        )
    elif (political_press_event or political_media_availability) and (
        stockholm_terms or "stockholm" in text.lower() or "stockholm" in item.source_name.lower()
    ):
        item.priority = "RED"
        item.desk = "ZUMA" if not specific_prisma_terms else "BOTH"
        item.physical_presence = True
        item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Partiledare, valrörelse eller politisk medieträff i Stockholm: tydligt ZUMA-bildläge."
        )
    elif political_press_event or political_media_availability:
        item.priority = "ORANGE"
        item.desk = "ZUMA" if not specific_prisma_terms else "BOTH"
        item.physical_presence = True
        item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Partipolitisk pressträff eller valhändelse med bildvärde. Kontrollera plats snabbt."
        )
    elif hard_red:
        item.priority = "RED"
        item.desk = "BOTH" if is_prisma_topic else "ZUMA"
        item.physical_presence = True
        item.action_recommendation = "SÖK_ACKREDITERING" if item.accreditation_needed else "ÅK_DIT"
    elif urgent_prisma_press_event:
        item.priority = "RED"
        item.desk = "BOTH"
        item.physical_presence = True
        item.action_recommendation = "SÖK_ACKREDITERING" if item.accreditation_needed else "RING_MAILA_NU"
        item.raw_json["why_it_matters"] = (
            "Akut Prisma-läge: pressträff om migration, arbetsmarknad eller myndighetsregler som kan påverka spansktalande i Sverige."
        )
    elif red_events and (red_people or red_topics or red_places):
        if zuma_picture_value:
            item.priority = "RED"
            item.desk = "BOTH" if is_prisma_topic else "ZUMA"
            item.action_recommendation = "RING_MAILA_NU" if item.accreditation_needed else "ÅK_DIT"
        else:
            item.priority = "YELLOW"
            item.desk = "PRISMA" if is_prisma_topic else "IGNORE"
            item.action_recommendation = "FÖLJ_UPP" if is_prisma_topic else "IGNORERA"
            item.raw_json["why_it_matters"] = "Viktig signal, men inget tydligt internationellt bildläge för ZUMA hittades."
    elif is_media:
        if item.category == "media_economy":
            item.priority = "GREEN"
            item.desk = "PRISMA"
            item.action_recommendation = "KAN_VÄNTA"
        elif foreign_terms and not sweden_terms:
            item.priority = "GREY"
            item.desk = "IGNORE"
            item.action_recommendation = "IGNORERA"
            item.raw_json["why_it_matters"] = "Utländsk mediesignal utan tydlig Sverige-, Prisma- eller lokal ZUMA-koppling."
        elif item.category == "media_stockholm":
            item.priority = "BLUE" if zuma_score < 3 else "YELLOW"
            item.desk = "BOTH" if zuma_picture_value else "PRISMA"
            item.action_recommendation = "FÖLJ_UPP"
        else:
            item.priority = "YELLOW" if zuma_score < 4 and prisma_score < 5 else "ORANGE"
            item.desk = "BOTH" if zuma_picture_value else "PRISMA"
            item.action_recommendation = "FÖLJ_UPP"
    elif item.category == "parliament_calendar":
        lowered = text.lower()
        is_visually_notable_chamber_event = any(term in lowered for term in ["partiledardebatt", "frågestund", "särskild debatt"])
        generic_calendar_terms = {"Riksdagen", "kammaren", "frågestund", "interpellationsdebatt", "partiledardebatt"}
        specific_prisma_calendar_terms = [term for term in prisma_terms if term not in generic_calendar_terms]
        has_prisma_calendar_topic = bool(specific_prisma_calendar_terms)
        has_zuma_calendar_picture_value = bool(
            is_visually_notable_chamber_event
            and zuma_picture_subject_terms
            and any(term in lowered for term in ["nato", "ukraina", "försvar", "statsminister", "utrikesminister", "försvarsminister"])
        )
        item.physical_presence = any(term in lowered for term in ["partiledardebatt", "frågestund", "debatt", "votering", "beslut"])
        if not has_prisma_calendar_topic:
            item.priority = "GREY"
            item.desk = "IGNORE"
            item.physical_presence = False
            item.action_recommendation = "IGNORERA"
            item.raw_json["why_it_matters"] = "Generisk riksdagskalenderhändelse utan tydligt Prisma-ämne."
        elif has_zuma_calendar_picture_value:
            item.priority = "ORANGE"
            item.desk = "BOTH"
            item.action_recommendation = "FÖLJ_UPP"
        elif has_prisma_calendar_topic:
            item.priority = "ORANGE"
            item.desk = "PRISMA"
            item.physical_presence = False
            item.action_recommendation = "FÖLJ_UPP"
    elif zuma_score >= 5 and zuma_picture_value:
        item.priority = "ORANGE"
        item.desk = "ZUMA" if prisma_score < 3 else "BOTH"
        item.action_recommendation = "FÖLJ_UPP" if not item.physical_presence else "RING_MAILA_NU"
    elif zuma_score >= 5 and is_prisma_topic:
        item.priority = "YELLOW"
        item.desk = "PRISMA"
        item.action_recommendation = "FÖLJ_UPP"
    elif prisma_score >= 5:
        item.priority = "ORANGE"
        item.desk = "PRISMA"
        item.action_recommendation = "PUBLICERA_IDAG" if has_consequence_marker else "FÖLJ_UPP"
        if not has_consequence_marker:
            item.raw_json["why_it_matters"] = (
                "Prisma-relevant ämne, men texten saknar tydlig konsekvensmarkör. Följ upp vinkel och praktisk påverkan innan publicering."
            )
        if item.category == "parliament_decisions" and high_impact_prisma_terms and "riksdagen sa ja" in text.lower():
            item.action_recommendation = "PUBLICERA_IDAG"
            item.raw_json["why_it_matters"] = (
                "Riksdagen har sagt ja till beslut som påverkar Prisma Suecias målgrupp. Kräver förklarande artikel."
            )
        elif is_committee_proposal:
            item.action_recommendation = "PUBLICERA_IDAG"
            item.raw_json["why_it_matters"] = (
                "Utskottets förslag påverkar rättigheter, vardag eller myndighetskontakt. Skriv tydligt att det är förslag till beslut, inte slutligt beslut."
            )
        elif item.category == "parliament_reports" and high_impact_prisma_terms:
            item.raw_json["why_it_matters"] = (
                "Riksdagsärende med hög Prisma-relevans: myndigheter, rättigheter, integritet eller vardagsregler kan påverkas."
            )
        if has_zuma_illustration_value:
            item.desk = "BOTH"
    elif item.category in {"parliament_decisions", "parliament_reports", "parliament_propositions"}:
        if item.category == "parliament_decisions" and high_impact_prisma_terms and "riksdagen sa ja" in text.lower():
            item.priority = "ORANGE"
            item.desk = "PRISMA"
            item.action_recommendation = "PUBLICERA_IDAG"
            item.raw_json["why_it_matters"] = (
                "Riksdagen har sagt ja till beslut som påverkar Prisma Suecias målgrupp. Kräver förklarande artikel."
            )
        elif is_committee_proposal:
            item.priority = "ORANGE"
            item.desk = "PRISMA"
            item.action_recommendation = "PUBLICERA_IDAG"
            item.raw_json["why_it_matters"] = (
                "Utskottets förslag påverkar rättigheter, vardag eller myndighetskontakt. Skriv tydligt att det är förslag till beslut, inte slutligt beslut."
            )
            if has_zuma_illustration_value:
                item.desk = "BOTH"
        elif specific_prisma_terms:
            item.priority = "ORANGE"
            item.desk = "PRISMA"
            item.action_recommendation = "FÖLJ_UPP"
        else:
            item.priority = "GREY"
            item.desk = "IGNORE"
            item.action_recommendation = "IGNORERA"
            item.raw_json["why_it_matters"] = "Riksdagsdokument utan tydligt Prisma-ämne."
    elif item.category == "parliament_scrutiny":
        if specific_prisma_terms:
            item.priority = "YELLOW"
            item.desk = "PRISMA"
            item.action_recommendation = "FÖLJ_UPP"
        else:
            item.priority = "GREY"
            item.desk = "IGNORE"
            item.action_recommendation = "IGNORERA"
            item.raw_json["why_it_matters"] = "Riksdagsfråga utan tydligt Prisma-ämne."
    elif item.category == "parliament_motions":
        item.priority = "GREEN"
        item.desk = "PRISMA"
        item.action_recommendation = "KAN_VÄNTA"
    elif mail_terms:
        item.priority = "YELLOW"
        item.desk = "BOTH"
        item.action_recommendation = "RING_MAILA_NU"
    elif item.category in {"culture", "events", "latino_culture", "latino_community", "youth_family"}:
        item.priority = "BLUE"
        item.desk = "PRISMA"
        item.action_recommendation = "FÖLJ_UPP"
    elif item.category in {"transport", "rail", "aviation", "transport_infrastructure", "stockholm_city"}:
        item.priority = "GREEN"
        item.desk = "PRISMA"
        item.action_recommendation = "KAN_VÄNTA"
    else:
        item.priority = "GREY"
        item.desk = "IGNORE"
        item.action_recommendation = "IGNORERA"

    if normalized_title in GENERIC_NON_STORY_TITLES:
        item.priority = "GREY"
        item.desk = "IGNORE"
        item.physical_presence = False
        item.action_recommendation = "IGNORERA"
        item.raw_json["why_it_matters"] = "Navigations- eller kategorisida, inte en konkret publicerbar story."

    is_stockholm_reachable = bool(stockholm_terms)
    is_outside_stockholm = bool(outside_stockholm_terms and not stockholm_terms)
    if is_stockholm_reachable and zuma_picture_value and item.physical_presence and item.desk in {"PRISMA", "IGNORE"}:
        item.desk = "BOTH"
    if is_stockholm_reachable and item.desk in {"ZUMA", "BOTH"} and item.physical_presence:
        item.raw_json["location_fit"] = "STOCKHOLM"
        if item.priority == "YELLOW":
            item.priority = "ORANGE"
        elif item.priority in {"BLUE", "GREEN", "GREY"}:
            item.priority = "ORANGE"
        if item.action_recommendation == "FÖLJ_UPP":
            item.action_recommendation = "RING_MAILA_NU"
        item.raw_json["location_note"] = "Stockholm eller nära Stockholm: praktiskt genomförbart och ska prioriteras högre."
    elif is_stockholm_reachable and item.desk == "PRISMA":
        item.raw_json["location_fit"] = "STOCKHOLM"
        item.raw_json["location_note"] = "Stockholmskoppling: högre lokal relevans för Prisma Desk."
    elif is_outside_stockholm:
        item.raw_json["location_fit"] = "UTANFÖR_STOCKHOLM"
        outside_was_physical = item.physical_presence
        outside_event_or_visit = bool(
            _contains_any(
                text,
                [
                    "besök",
                    "media bjuds in",
                    "pressträff",
                    "pressvisning",
                    "fototillfälle",
                    "öppet för media",
                ],
            )
        )
        if outside_was_physical and item.desk in {"ZUMA", "BOTH"}:
            if is_prisma_topic or red_people or red_topics or item.category in {"government", "prime_minister", "nato", "defence", "royal"}:
                item.desk = "PRISMA"
                if item.priority == "RED":
                    item.priority = "ORANGE"
                item.action_recommendation = "FÖLJ_UPP"
                item.raw_json["why_it_matters"] = (
                    "Viktigt för Prisma Suecia eller Sverige-förklarat, men utanför Stockholms län och därför inte ZUMA på plats."
                )
            else:
                item.desk = "IGNORE"
                item.physical_presence = False
                item.priority = "GREY"
                item.action_recommendation = "IGNORERA"
                item.raw_json["why_it_matters"] = "Utanför Stockholms län och saknar tydlig Prisma-relevans."
        if outside_was_physical:
            item.physical_presence = False
            if item.action_recommendation in {"ÅK_DIT", "SÖK_ACKREDITERING", "RING_MAILA_NU"}:
                item.action_recommendation = "FÖLJ_UPP"
        if outside_event_or_visit and item.action_recommendation == "PUBLICERA_IDAG":
            item.action_recommendation = "FÖLJ_UPP"
            if item.priority == "ORANGE":
                item.priority = "YELLOW"
            item.raw_json["why_it_matters"] = (
                "Prisma-relevant ämne, men detta är ett lokalt besök utanför Stockholms län. Följ upp sakfrågan innan publicering."
            )
        item.raw_json["location_note"] = "Utanför Stockholms län: bevaka för Prisma om målgruppen berörs, men ge inte ZUMA-uppdrag på plats."
    else:
        item.raw_json["location_fit"] = "OKÄNT"

    if (
        is_media
        and item.raw_json.get("location_fit") != "STOCKHOLM"
        and item.action_recommendation == "ÅK_DIT"
    ):
        item.action_recommendation = "RING_MAILA_NU" if item.priority == "RED" else "FÖLJ_UPP"
        item.physical_presence = False
        item.raw_json["why_it_matters"] = (
            "Aktuell stark signal, men mediekällan saknar tydlig plats i Stockholms län. Följ upp plats innan ZUMA på plats."
        )

    source_type = item.raw_json.get("source_type")
    is_scraped_political_web_item = bool(
        item.category == "politics"
        and source_type in {"web", "web_fallback"}
        and item.action_recommendation in {"RING_MAILA_NU", "ÅK_DIT", "SÖK_ACKREDITERING"}
        and not detect_swedish_event_datetime(text)
    )
    if is_scraped_political_web_item:
        item.physical_presence = False
        item.action_recommendation = "FÖLJ_UPP"
        if item.priority == "RED":
            item.priority = "ORANGE"
        item.raw_json["why_it_matters"] = (
            "Partipolitisk nyhet med bildvärde, men ingen tydlig kommande tid eller presstid hittades. Följ upp innan ZUMA på plats."
        )

    if image_suggestions:
        item.raw_json["image_suggestions"] = image_suggestions
        item.raw_json["zuma_image_angle"] = (
            "Illustrationsbild/featurebild för ZUMA, inte automatiskt ett på-plats-uppdrag."
        )
        if has_zuma_illustration_value and item.desk == "PRISMA":
            item.desk = "BOTH"

    access_guidance = access_guidance_for_item(item, text)
    if access_guidance:
        item.raw_json["access_guidance"] = access_guidance

    matched_terms = {
        "red_people": red_people,
        "red_topics": red_topics,
        "red_events": red_events,
        "red_places": red_places,
        "zuma": zuma_terms,
        "zuma_picture_event": zuma_picture_event_terms,
        "zuma_picture_subject": zuma_picture_subject_terms,
        "zuma_picture_place": zuma_picture_place_terms,
        "zuma_picture_value": ["true"] if zuma_picture_value else [],
        "prisma": prisma_terms,
        "prisma_consequence": matched_consequence_markers,
        "sweden": sweden_terms,
        "stockholm": stockholm_terms,
        "outside_stockholm": outside_stockholm_terms,
        "foreign_low_relevance": foreign_terms,
        "major_visual_accident": major_visual_accident_terms,
        "latino_music": (
            latino_music_matches.get("venue", [])
            + latino_music_matches.get("genre", [])
            + latino_music_matches.get("significance", [])
            + latino_music_matches.get("artist_pattern", [])
        ),
    }
    existing_why = item.raw_json.get("why_it_matters")
    item.raw_json.update(
        {
            "why_it_matters": existing_why
            or why_it_matters(item, red_people, red_topics, red_events, red_places, zuma_terms, prisma_terms),
            "matched_terms": matched_terms,
            "confidence": calculate_confidence(matched_terms),
        }
    )
    apply_temporal_guardrails(item)
    item.score = calculate_score(item)
    return item


def calculate_confidence(matched_terms: dict[str, list[str]]) -> str:
    distinct_categories_hit = sum(1 for terms in matched_terms.values() if terms)
    if distinct_categories_hit >= 3:
        return "HIGH"
    if distinct_categories_hit == 2:
        return "MEDIUM"
    return "LOW"


def why_it_matters(
    item: NewsItem,
    red_people: list[str],
    red_topics: list[str],
    red_events: list[str],
    red_places: list[str],
    zuma_terms: list[str],
    prisma_terms: list[str],
) -> str:
    signals = red_people + red_topics + red_events + red_places + zuma_terms + prisma_terms
    if item.priority == "RED":
        return "Rödalarm: " + ", ".join(dict.fromkeys(signals[:8]))
    if item.desk == "ZUMA":
        return "Bildläge med internationellt eller visuellt värde."
    if item.desk == "PRISMA":
        return "Relevant för Prisma Suecias publik och vardagsbevakning."
    if item.desk == "BOTH":
        return "Kan vara både bildläge och Prisma-story."
    return "Låg redaktionell träff i nuvarande regler."


def openai_enabled() -> bool:
    return os.getenv("ENABLE_OPENAI", "false").lower() == "true" and bool(os.getenv("OPENAI_API_KEY"))
