from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.firebase_app import get_firestore_db

COLLECTION = "analytics_events"

# In-memory fallback when Firestore is unavailable
_events_memory: list[dict[str, Any]] = []


def record_event(event: dict[str, Any]) -> None:
    payload = {
        **event,
        "ts": event.get("ts") or datetime.now(timezone.utc).isoformat(),
    }
    db = get_firestore_db()
    if db:
        try:
            db.collection(COLLECTION).document(str(uuid4())).set(payload)
            return
        except Exception as exc:
            print("[analytics] write failed:", exc)
    _events_memory.append(payload)
    if len(_events_memory) > 5000:
        del _events_memory[:1000]


def record_pageview(path: str, session_id: str) -> None:
    record_event(
        {
            "type": "page_view",
            "path": path[:500],
            "session_id": session_id[:128],
            "ok": True,
        }
    )


def record_fact_check(*, ok: bool, verdict: str | None = None) -> None:
    record_event(
        {
            "type": "fact_check",
            "ok": ok,
            "verdict": verdict,
        }
    )


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _range_start(range_key: str) -> datetime:
    days = 30 if range_key == "30d" else 7
    return datetime.now(timezone.utc) - timedelta(days=days)


def _load_events(since: datetime) -> list[dict[str, Any]]:
    db = get_firestore_db()
    events: list[dict[str, Any]] = []
    if db:
        try:
            docs = (
                db.collection(COLLECTION)
                .where("ts", ">=", since.isoformat())
                .stream()
            )
            for doc in docs:
                data = doc.to_dict() or {}
                events.append(data)
        except Exception as exc:
            print("[analytics] query failed:", exc)

    for item in _events_memory:
        ts = _parse_ts(item.get("ts"))
        if ts and ts >= since:
            events.append(item)
    return events


def aggregate_analytics(
    range_key: str = "7d",
    recent_reports: list[dict[str, Any]] | None = None,
    reports_in_range: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    since = _range_start(range_key)
    events = _load_events(since)

    # Successful fact-checks come from stored reports (durable source of truth).
    # Analytics events still track failures and page views.
    fact_checks_by_day: dict[str, int] = defaultdict(int)
    verdict_mix: dict[str, int] = defaultdict(int)
    fact_ok = 0
    fact_fail = 0
    page_views = 0
    sessions: set[str] = set()
    page_views_by_day: dict[str, int] = defaultdict(int)

    for report in reports_in_range or []:
        fact_ok += 1
        verdict = report.get("verdict") or "unknown"
        verdict_mix[str(verdict)] += 1
        ts = _parse_ts(report.get("created_at"))
        day = ts.date().isoformat() if ts else "unknown"
        fact_checks_by_day[day] += 1

    for event in events:
        ts = _parse_ts(event.get("ts"))
        day = ts.date().isoformat() if ts else "unknown"
        etype = event.get("type")

        if etype == "fact_check" and not event.get("ok"):
            fact_fail += 1
            fact_checks_by_day[day] += 1
        elif etype == "page_view":
            page_views += 1
            page_views_by_day[day] += 1
            sid = event.get("session_id")
            if sid:
                sessions.add(str(sid))

    total_fact = fact_ok + fact_fail
    return {
        "range": range_key,
        "fact_checks_by_day": dict(sorted(fact_checks_by_day.items())),
        "verdict_mix": dict(verdict_mix),
        "fact_check_ok": fact_ok,
        "fact_check_error": fact_fail,
        "fact_check_error_rate": (fact_fail / total_fact) if total_fact else 0.0,
        "page_views": page_views,
        "unique_sessions": len(sessions),
        "page_views_by_day": dict(sorted(page_views_by_day.items())),
        "recent_reports": recent_reports or [],
        "reports_in_range": reports_in_range or [],
    }
