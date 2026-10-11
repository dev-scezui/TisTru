from typing import Any

from app.config import settings

_firestore_db: Any | None = None
_firebase_ready: bool = False


def init_firebase() -> bool:
    """Initialize Firebase Admin once. Returns True if usable."""
    global _firestore_db, _firebase_ready
    if _firebase_ready and _firestore_db is not None:
        return True
    try:
        import json

        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred_json = settings.firebase_service_account_json
            cred_path = settings.firebase_credentials_path
            if cred_json:
                firebase_admin.initialize_app(credentials.Certificate(json.loads(cred_json)))
            elif cred_path:
                firebase_admin.initialize_app(credentials.Certificate(cred_path))
            else:
                firebase_admin.initialize_app()
        _firestore_db = firestore.client()
        _firebase_ready = True
        return True
    except Exception as exc:
        import traceback

        print("[firebase] initialization failed:", exc)
        traceback.print_exc()
        _firestore_db = None
        _firebase_ready = False
        return False


def get_firestore_db() -> Any | None:
    if _firestore_db is not None:
        return _firestore_db
    if init_firebase():
        return _firestore_db
    return None
