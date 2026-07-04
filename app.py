import json
import os
import secrets
import traceback
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from desk import database
from desk.live_status import live_temporal_status
from desk.models import NewsItem
from desk.scoring import apply_temporal_guardrails, calculate_score, hours_until_deadline
from desk.update_runner import run_update


load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("PRISMA_DESK_SECRET_KEY") or os.getenv("PRISMA_DESK_PASSWORD") or "local-dev-only"


SECTIONS = OrderedDict(
    [
        (
            "akut",
            {
                "title": "🔴🔴🔴 AKUT NU",
                "filter": lambda item: item["priority"] == "RED" and is_fresh(item),
            },
        ),
        (
            "zuma",
            {
                "title": "🔴 ZUMA PRESS — bildmöjligheter",
                "filter": lambda item: (
                    item["desk"] in {"ZUMA", "BOTH"}
                    and item["priority"] != "RED"
                    and is_fresh(item)
                ),
            },
        ),
        (
            "prisma",
            {
                "title": "🟠 PRISMA SUECIA — publicerbara stories",
                "filter": lambda item: (
                    item["desk"] in {"PRISMA", "BOTH"}
                    and item["action_recommendation"] == "PUBLICERA_IDAG"
                    and is_fresh(item)
                ),
            },
        ),
        ("press", {"title": "🟡 PRESSINBJUDNINGAR / ACKREDITERING", "filter": lambda item: item["accreditation_needed"] or item["deadline_detected"]}),
        ("community", {"title": "🔵 STOCKHOLM / COMMUNITY / KULTUR", "filter": lambda item: item["priority"] == "BLUE"}),
        ("vardag", {"title": "🟢 SVERIGE FÖRKLARAT / VARDAG", "filter": lambda item: item["priority"] == "GREEN"}),
        ("published", {"title": "⚪ REDAN PUBLICERAT / UNDVIK DUBLETTER", "filter": lambda item: item["prisma_status"] in {"REDAN_PUBLICERAD", "DELVIS_TÄCKT", "ENDAST_UPPDATERING"}}),
    ]
)


def is_fresh(item):
    return from_json(item.get("raw_json")).get("temporal_status") not in {"OLD", "PAST_EVENT"}


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


def normalize_latest_run(row):
    if not row:
        return None
    data = dict(row)
    defaults = {
        "id": None,
        "started_at": None,
        "finished_at": None,
        "status": "Väntar",
        "items_found": 0,
        "red_alerts_found": 0,
        "sources_configured": 0,
        "sources_selected": 0,
        "sources_attempted": 0,
        "sources_failed": 0,
        "sources_skipped": 0,
        "sources_total": 0,
        "sources_fetched": 0,
        "sources_skipped_names": "[]",
        "errors": "",
    }
    return {**defaults, **data}


def item_from_dict(item):
    return NewsItem(
        source_name=item.get("source_name") or "",
        source_url=item.get("source_url") or "",
        title=item.get("title") or "",
        summary=item.get("summary") or "",
        content=item.get("content") or "",
        published_at=item.get("published_at"),
        fetched_at=item.get("fetched_at") or "",
        url=item.get("url") or "",
        hash=item.get("hash") or "",
        category=item.get("category") or "",
        priority=item.get("priority") or "GREY",
        desk=item.get("desk") or "IGNORE",
        physical_presence=bool(item.get("physical_presence")),
        accreditation_needed=None
        if item.get("accreditation_needed") is None
        else bool(item.get("accreditation_needed")),
        deadline_detected=bool(item.get("deadline_detected")),
        deadline_date=item.get("deadline_date"),
        already_on_prisma=bool(item.get("already_on_prisma")),
        prisma_status=item.get("prisma_status") or "EJ_PUBLICERAD",
        action_recommendation=item.get("action_recommendation") or "KAN_VÄNTA",
        score=int(item.get("score") or 0),
        raw_json=from_json(item.get("raw_json")),
    )


def apply_live_temporal_guardrails(item):
    live_item = apply_temporal_guardrails(item_from_dict(item))
    live_item.raw_json["temporal_status"] = live_temporal_status(item)
    live_item.score = calculate_score(live_item)
    item.update(
        {
            "priority": live_item.priority,
            "desk": live_item.desk,
            "physical_presence": int(live_item.physical_presence),
            "accreditation_needed": None
            if live_item.accreditation_needed is None
            else int(live_item.accreditation_needed),
            "deadline_detected": int(live_item.deadline_detected),
            "action_recommendation": live_item.action_recommendation,
            "score": live_item.score,
            "raw_json": json.dumps(live_item.raw_json, ensure_ascii=False),
        }
    )
    return item


def prepare_items_for_dashboard(items):
    try:
        enriched_items = database.enrich_with_cluster_info(items)
    except Exception:
        traceback.print_exc()
        enriched_items = items
        for item in enriched_items:
            item["cluster_is_primary"] = True
            item["cluster_size"] = 1
            item["cluster_other_sources"] = []

    live_items = []
    for item in enriched_items:
        if not item.get("cluster_is_primary", True):
            continue
        try:
            live_items.append(apply_live_temporal_guardrails(item))
        except Exception:
            traceback.print_exc()
            item["raw_json"] = json.dumps(
                {
                    **from_json(item.get("raw_json")),
                    "temporal_status": "UNKNOWN",
                    "why_it_matters": "Fyndet kunde inte räknas om live, men visas ändå så det inte tappas bort.",
                },
                ensure_ascii=False,
            )
            live_items.append(item)
    live_items = apply_deadline_escalation(live_items)
    return sorted(live_items, key=lambda item: (item.get("score") or 0, item.get("last_seen_at") or item.get("fetched_at") or ""), reverse=True)


def apply_role_filter(items, view):
    if view == "zuma":
        return [item for item in items if item.get("desk") in {"ZUMA", "BOTH"}]
    if view == "prisma":
        return [item for item in items if item.get("desk") in {"PRISMA", "BOTH"}]
    return items


def apply_deadline_escalation(items):
    for item in items:
        hours_remaining = hours_until_deadline(item.get("deadline_date"))
        if hours_remaining is None:
            continue
        item["deadline_hours_remaining"] = round(hours_remaining, 1)
        if 0 <= hours_remaining <= 48:
            item["deadline_urgent"] = True
            item["score"] = max(int(item.get("score") or 0), 900)
    return items


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    parsers = (
        lambda candidate: datetime.fromisoformat(candidate.replace("Z", "+00:00")),
        parsedate_to_datetime,
    )
    for parser in parsers:
        try:
            timestamp = parser(text)
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
    return None


def timeline_datetime(item):
    raw = from_json(item.get("raw_json"))
    for value in (
        item.get("deadline_date"),
        raw.get("detected_event_datetime"),
        item.get("published_at"),
        item.get("fetched_at"),
    ):
        timestamp = parse_datetime(value)
        if timestamp:
            return timestamp
    return None


def group_timeline_items(items):
    grouped = OrderedDict()
    fallback = datetime.max.replace(tzinfo=timezone.utc)
    for item in sorted(items, key=lambda candidate: timeline_datetime(candidate) or fallback):
        timestamp = timeline_datetime(item)
        key = timestamp.date().isoformat() if timestamp else "Utan datum"
        grouped.setdefault(key, []).append(item)
    return grouped


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


@app.errorhandler(Exception)
def handle_exception(error):
    if isinstance(error, HTTPException):
        return error
    traceback.print_exc()
    return (
        render_template(
            "error.html",
            message="Prisma Desk fick ett serverfel. Felet är loggat på servern.",
        ),
        500,
    )


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
    latest_run = normalize_latest_run(database.latest_run())
    view = request.args.get("view", "latest")
    source_view = "all" if view == "all" else "latest"
    if source_view == "all" or not latest_run:
        items = [row_to_dict(row) for row in database.latest_items()]
    else:
        items = [row_to_dict(row) for row in database.items_for_run(latest_run["id"])]
    items = prepare_items_for_dashboard(items)
    items = apply_role_filter(items, view)
    previous_visit = database.get_last_viewed_at()
    new_since_last_visit = 0
    if previous_visit:
        for item in items:
            is_new = bool(item.get("fetched_at") and item["fetched_at"] > previous_visit)
            item["is_new_since_last_visit"] = is_new
            if is_new:
                new_since_last_visit += 1
    database.mark_viewed_now()
    message = request.args.get("message", "")
    return render_template(
        "dashboard.html",
        sections=build_sections(items),
        latest_run=latest_run,
        view=view,
        source_view=source_view,
        total_items=len(items),
        red_alerts=sum(1 for item in items if item["priority"] == "RED"),
        previous_visit=previous_visit,
        new_since_last_visit=new_since_last_visit,
        message=message,
    )


@app.route("/healthz", methods=["GET"])
def healthz():
    try:
        database.init_db()
        latest_run = normalize_latest_run(database.latest_run())
        item_count = len(database.latest_items(limit=5, include_dismissed=True))
        status = latest_run["status"] if latest_run else "NO_RUNS"
        return f"ok latest_run={status} sample_items={item_count}\n", 200
    except Exception as exc:
        traceback.print_exc()
        return f"error {type(exc).__name__}: {exc}\n", 500


@app.route("/update", methods=["GET", "POST"])
def update():
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    if request.method == "GET":
        return redirect(url_for("dashboard"))
    try:
        result = run_update()
    except Exception as exc:
        traceback.print_exc()
        message = f"Uppdateringen kraschade: {type(exc).__name__}. Öppna Källhälsa eller Render-loggen för detaljer."
        return redirect(url_for("dashboard", message=message))
    message = f"Uppdatering klar: {result['saved']} nya sparade, {result['found']} fynd analyserade, {result['red_alerts']} rödalarm."
    source_stats = result.get("source_stats") or {}
    if source_stats:
        message += (
            " Källor: "
            f"{source_stats.get('attempted', 0)}/{source_stats.get('configured', 0)} körda"
        )
        if source_stats.get("failed", 0):
            message += f", {source_stats.get('failed')} fel"
        if source_stats.get("skipped", 0):
            message += f", {source_stats.get('skipped')} hoppade över"
        message += "."
    if result["errors"]:
        message += f" {len(result['errors'])} källa/källor gav fel."
    return redirect(url_for("dashboard", message=message))


@app.route("/item/<int:item_id>/dismiss", methods=["POST"])
def dismiss(item_id):
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    database.dismiss_item(item_id)
    database.record_feedback(item_id, "dismissed")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/item/<int:item_id>/feedback", methods=["POST"])
def feedback(item_id):
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    feedback_type = request.form.get("feedback_type", "")
    note = request.form.get("note", "")
    if feedback_type not in {"wrong_priority", "good_catch"}:
        return "Ogiltig feedback-typ", 400
    database.record_feedback(item_id, feedback_type, note)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/feedback-report", methods=["GET"])
def feedback_report():
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    database.init_db()
    return render_template("feedback_report.html", rows=database.feedback_summary())


@app.route("/source-health", methods=["GET"])
def source_health():
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    database.init_db()
    return render_template("source_health.html", rows=database.source_health_rows())


@app.route("/timeline", methods=["GET"])
def timeline():
    auth_redirect = require_auth()
    if auth_redirect:
        return auth_redirect
    database.init_db()
    items = [row_to_dict(row) for row in database.latest_items(limit=500)]
    items = prepare_items_for_dashboard(items)
    upcoming = [
        item
        for item in items
        if from_json(item.get("raw_json")).get("temporal_status") == "UPCOMING"
        or item.get("deadline_date")
    ]
    return render_template("timeline.html", grouped_by_date=group_timeline_items(upcoming))


if __name__ == "__main__":
    database.init_db()
    port = int(os.getenv("PORT", "5050"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
