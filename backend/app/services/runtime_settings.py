from __future__ import annotations

import time
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.firebase_app import get_firestore_db

COLLECTION = "settings"
DOCUMENT = "runtime"
CACHE_TTL_SECONDS = 15
SECRET_FIELDS = frozenset({"openai_api_key", "tavily_api_key"})


@dataclass
class RuntimeSettings:
    use_local_llm: bool = False
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "llama3.1"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    tavily_api_key: str | None = None
    updated_at: str | None = None
    updated_by: str | None = None


_cache: RuntimeSettings | None = None
_cache_at: float = 0.0


def _env_defaults() -> RuntimeSettings:
    return RuntimeSettings(
        use_local_llm=settings.use_local_llm,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
        openai_model=settings.openai_model,
        tavily_api_key=settings.tavily_api_key,
    )


def _from_dict(data: dict[str, Any] | None) -> RuntimeSettings:
    base = _env_defaults()
    if not data:
        return base
    values = asdict(base)
    for f in fields(RuntimeSettings):
        if f.name in data and data[f.name] is not None:
            values[f.name] = data[f.name]
    return RuntimeSettings(**values)


def invalidate_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def get_runtime_settings(*, force: bool = False) -> RuntimeSettings:
    global _cache, _cache_at
    now = time.monotonic()
    if not force and _cache is not None and (now - _cache_at) < CACHE_TTL_SECONDS:
        return _cache

    db = get_firestore_db()
    if not db:
        _cache = _env_defaults()
        _cache_at = now
        return _cache

    try:
        doc = db.collection(COLLECTION).document(DOCUMENT).get()
        data = doc.to_dict() if doc.exists else None
        _cache = _from_dict(data)
    except Exception as exc:
        print("[runtime_settings] load failed:", exc)
        _cache = _env_defaults()

    _cache_at = now
    return _cache


def mask_secret(value: str | None, length: int = 6) -> str:
    if not value:
        return "not set"
    if len(value) <= length * 2:
        return "set"
    return f"{value[:length]}...{value[-length:]}"


def settings_public_view(runtime: RuntimeSettings | None = None) -> dict[str, Any]:
    rt = runtime or get_runtime_settings()
    return {
        "use_local_llm": rt.use_local_llm,
        "ollama_base_url": rt.ollama_base_url,
        "ollama_model": rt.ollama_model,
        "openai_api_key": mask_secret(rt.openai_api_key),
        "openai_base_url": rt.openai_base_url,
        "openai_model": rt.openai_model,
        "tavily_api_key": mask_secret(rt.tavily_api_key),
        "updated_at": rt.updated_at,
        "updated_by": rt.updated_by,
    }


def update_runtime_settings(patch: dict[str, Any], *, updated_by: str | None = None) -> RuntimeSettings:
    current = get_runtime_settings(force=True)
    merged = asdict(current)

    for key, value in patch.items():
        if key not in merged:
            continue
        if key in SECRET_FIELDS:
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            merged[key] = value
        else:
            merged[key] = value

    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    merged["updated_by"] = updated_by
    updated = RuntimeSettings(**merged)

    db = get_firestore_db()
    if db:
        payload = {k: v for k, v in asdict(updated).items()}
        db.collection(COLLECTION).document(DOCUMENT).set(payload, merge=True)

    global _cache, _cache_at
    _cache = updated
    _cache_at = time.monotonic()
    return updated
