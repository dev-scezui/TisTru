"""Firestore-backed daily usage quotas for fact-check submissions."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

from app.config import settings
from app.firebase_app import get_firestore_db

ANON_COLLECTION = "usage_anon"
USER_COLLECTION = "usage_users"


class UsageDenied(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UsageUnavailable(Exception):
    """Firestore is not configured or unreachable."""


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _anon_doc_id(ip: str) -> str:
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def _run_transaction(db: Any, callback: Callable[[Any], Any]) -> Any:
    """Run callback inside a Firestore transaction."""
    from google.cloud import firestore

    transaction = db.transaction()

    @firestore.transactional
    def _tx(transaction: Any) -> Any:
        return callback(transaction)

    return _tx(transaction)


def consume_anon_quota(ip: str) -> None:
    """Consume one anonymous slot for this IP today. Raises UsageDenied/UsageUnavailable."""
    db = get_firestore_db()
    if db is None:
        raise UsageUnavailable("Usage tracking unavailable")

    limit = settings.fact_check_anon_limit
    day = _utc_day()
    ref = db.collection(ANON_COLLECTION).document(_anon_doc_id(ip))

    def _body(transaction: Any) -> None:
        snap = ref.get(transaction=transaction) if transaction is not None else ref.get()
        data = snap.to_dict() if snap.exists else {}
        count = int(data.get("count") or 0)
        if data.get("day") != day:
            count = 0
        if count >= limit:
            raise UsageDenied("auth_required", "Sign in to continue investigating.")
        payload = {"count": count + 1, "day": day}
        if transaction is not None:
            transaction.set(ref, payload)
        else:
            ref.set(payload)

    _run_transaction(db, _body)


def consume_user_quota(uid: str) -> None:
    """Consume one authenticated slot for this user today."""
    db = get_firestore_db()
    if db is None:
        raise UsageUnavailable("Usage tracking unavailable")

    limit = settings.fact_check_user_daily_limit
    day = _utc_day()
    ref = (
        db.collection(USER_COLLECTION)
        .document(uid)
        .collection("days")
        .document(day)
    )

    def _body(transaction: Any) -> None:
        snap = ref.get(transaction=transaction) if transaction is not None else ref.get()
        data = snap.to_dict() if snap.exists else {}
        count = int(data.get("count") or 0)
        if count >= limit:
            raise UsageDenied("daily_limit", "Daily investigation limit reached. Try again tomorrow.")
        payload = {"count": count + 1}
        if transaction is not None:
            transaction.set(ref, payload)
        else:
            ref.set(payload)

    _run_transaction(db, _body)
