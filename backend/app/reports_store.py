from datetime import datetime, timezone
from typing import Any

from app.firebase_app import get_firestore_db
from app.models import FactCheckReport

reports_db: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _report_payload(report: FactCheckReport, created_at: str | None = None) -> dict[str, Any]:
    payload = report.model_dump()
    payload["created_at"] = created_at or _now_iso()
    return payload


def _strip_meta(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(data)
    cleaned.pop("created_at", None)
    return cleaned


def save_report(report_id: str, report: FactCheckReport) -> None:
    payload = _report_payload(report)
    db = get_firestore_db()
    if db:
        db.collection("reports").document(report_id).set(payload)
    else:
        reports_db[report_id] = payload


def load_report(report_id: str) -> FactCheckReport | None:
    db = get_firestore_db()
    if db:
        doc = db.collection("reports").document(report_id).get()
        if doc.exists:
            return FactCheckReport(**_strip_meta(doc.to_dict() or {}))
        return None
    stored = reports_db.get(report_id)
    if stored is None:
        return None
    return FactCheckReport(**_strip_meta(stored))


def _item_from_stored(report_id: str, data: dict[str, Any], created_at: Any = None) -> dict[str, Any]:
    verdict = data.get("verdict")
    if hasattr(verdict, "value"):
        verdict = verdict.value
    return {
        "id": report_id,
        "verdict": verdict,
        "url": data.get("url"),
        "context_summary": (data.get("context_summary") or "")[:160],
        "created_at": created_at or data.get("created_at"),
    }


def list_recent_reports(limit: int = 10) -> list[dict[str, Any]]:
    items = list_reports_since(since=None, limit=max(limit * 3, limit))
    return items[:limit]


def list_reports_since(since: datetime | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Return reports newest-first. Optional since filters by created_at / Firestore create_time."""
    db = get_firestore_db()
    items: list[dict[str, Any]] = []
    if db:
        try:
            docs = db.collection("reports").limit(limit).stream()
            for doc in docs:
                data = doc.to_dict() or {}
                created = _parse_ts(data.get("created_at")) or getattr(doc, "create_time", None)
                created_dt = _parse_ts(created)
                # Skip only when we know the report is outside the range.
                if since and created_dt is not None and created_dt < since:
                    continue
                items.append(
                    _item_from_stored(
                        doc.id,
                        data,
                        created_at=created_dt.isoformat() if created_dt else data.get("created_at"),
                    )
                )
        except Exception as exc:
            print("[reports] list failed:", exc)
    else:
        for rid, data in reports_db.items():
            created_dt = _parse_ts(data.get("created_at"))
            if since and (created_dt is None or created_dt < since):
                continue
            items.append(_item_from_stored(rid, data))

    def sort_key(item: dict[str, Any]) -> str:
        return str(item.get("created_at") or "")

    items.sort(key=sort_key, reverse=True)
    return items[:limit]
