import json
import os
from collections import OrderedDict

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

from desk import database
from desk.update_runner import run_update


load_dotenv()
app = Flask(__name__)


SECTIONS = OrderedDict(
    [
        ("akut", {"title": "🔴🔴🔴 AKUT NU", "filter": lambda item: item["priority"] == "RED"}),
        ("zuma", {"title": "🔴 ZUMA PRESS — bildmöjligheter", "filter": lambda item: item["desk"] in {"ZUMA", "BOTH"} and item["priority"] != "RED"}),
        ("prisma", {"title": "🟠 PRISMA SUECIA — publicerbara stories", "filter": lambda item: item["desk"] in {"PRISMA", "BOTH"} and item["action_recommendation"] == "PUBLICERA_IDAG"}),
        ("press", {"title": "🟡 PRESSINBJUDNINGAR / ACKREDITERING", "filter": lambda item: item["accreditation_needed"] or item["deadline_detected"]}),
        ("community", {"title": "🔵 STOCKHOLM / COMMUNITY / KULTUR", "filter": lambda item: item["priority"] == "BLUE"}),
        ("vardag", {"title": "🟢 SVERIGE FÖRKLARAT / VARDAG", "filter": lambda item: item["priority"] == "GREEN"}),
        ("published", {"title": "⚪ REDAN PUBLICERAT / UNDVIK DUBLETTER", "filter": lambda item: item["prisma_status"] in {"REDAN_PUBLICERAD", "DELVIS_TÄCKT", "ENDAST_UPPDATERING"}}),
    ]
)


def is_press_or_accreditation(item):
    raw = from_json(item.get("raw_json"))
    if raw.get("temporal_status") in {"PAST_EVENT", "OLD"}:
        return False
    if item["accreditation_needed"] or item["deadline_detected"]:
        return True
    matched = raw.get("matched_terms", {})
    event_terms = set(matched.get("red_events", []) + matched.get("zuma_picture_event", []))
    press_terms = {
        "pressträff",
        "pressinbjudan",
        "presskonferens",
        "pressbriefing",
        "gemensam pressbriefing",
        "media invitation",
    }
    return bool(event_terms & press_terms)


SECTIONS["press"]["filter"] = is_press_or_accreditation


def row_to_dict(row):
    return dict(row)


@app.template_filter("from_json")
def from_json(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def build_sections(items):
    per_source_limits = {
        "community": 4,
        "vardag": 5,
        "press": 4,
    }
    grouped = OrderedDict()
    for key, section in SECTIONS.items():
        section_items = [item for item in items if section["filter"](item)]
        limit = per_source_limits.get(key)
        if limit:
            source_counts = {}
            balanced_items = []
            for item in section_items:
                source_name = item.get("source_name", "")
                if source_counts.get(source_name, 0) >= limit:
                    continue
                source_counts[source_name] = source_counts.get(source_name, 0) + 1
                balanced_items.append(item)
            section_items = balanced_items
        grouped[key] = {
            "title": section["title"],
            "items": section_items,
        }
    return grouped


@app.route("/", methods=["GET"])
def dashboard():
    database.init_db()
    latest_run = database.latest_run()
    view = request.args.get("view", "latest")
    if view == "all" or not latest_run:
        items = [row_to_dict(row) for row in database.latest_items()]
    else:
        items = [row_to_dict(row) for row in database.items_for_run(latest_run["id"])]
    message = request.args.get("message", "")
    return render_template(
        "dashboard.html",
        sections=build_sections(items),
        latest_run=latest_run,
        view=view,
        total_items=len(items),
        red_alerts=sum(1 for item in items if item["priority"] == "RED"),
        message=message,
    )


@app.route("/update", methods=["POST"])
def update():
    result = run_update()
    message = f"Uppdatering klar: {result['saved']} nya sparade, {result['found']} fynd analyserade, {result['red_alerts']} rödalarm."
    if result["errors"]:
        message += f" {len(result['errors'])} källa/källor gav fel."
    return redirect(url_for("dashboard", message=message))


if __name__ == "__main__":
    database.init_db()
    port = int(os.getenv("PORT", "5050"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
