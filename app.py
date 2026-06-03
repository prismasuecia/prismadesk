import json
import os
import secrets
from collections import OrderedDict

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

from desk import database
from desk.update_runner import run_update


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("PRISMA_DESK_SECRET_KEY") or os.getenv("PRISMA_DESK_PASSWORD") or "local-dev-only"


SECTIONS = OrderedDict(
    [
        ("akut", {"title": "🔴🔴🔴 AKUT NU", "filter": lambda item: item["priority"] == "RED"}),
        (
            "zuma",
            {
                "title": "🔴 ZUMA PRESS — bildmöjligheter",
                "filter": lambda item: (
                    item["desk"] in {"ZUMA", "BOTH"}
                    and item["priority"] != "RED"
                    and from_json(item.get("raw_json")).get("temporal_status") not in {"OLD", "PAST_EVENT"}
                ),
            },
        ),
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


def auth_required() -> bool:
    return bool(os.getenv("PRISMA_DESK_PASSWORD"))


def is_authenticated() -> bool:
    return not auth_required() or bool(session.get("authenticated"))


def require_auth():
    if not is_authenticated():
        return redirect(url_for("login", next=request.path))
    return None


@app.context_processor
def auth_context():
    return {
        "auth_required": auth_required(),
        "is_authenticated": is_authenticated(),
    }


@app.after_request
def add_private_headers(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Cache-Control"] = "no-store"
    return response


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


@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth_required():
        return redirect(url_for("dashboard"))
    error = ""
    if request.method == "POST":
        expected = os.getenv("PRISMA_DESK_PASSWORD", "")
        submitted = request.form.get("password", "")
        if secrets.compare_digest(submitted, expected):
            session["authenticated"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        error = "Fel lösenord."
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])
def dashboard():
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
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


@app.route("/update", methods=["GET", "POST"])
def update():
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    if request.method == "GET":
        return redirect(url_for("dashboard"))
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
