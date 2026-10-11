from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import require_admin
from app.reports_store import list_reports_since
from app.services.analytics import aggregate_analytics, record_pageview
from app.services.runtime_settings import get_runtime_settings, settings_public_view, update_runtime_settings

router = APIRouter()


class SettingsUpdate(BaseModel):
    use_local_llm: bool | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    tavily_api_key: str | None = None


class PageViewBody(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    session_id: str = Field(min_length=1, max_length=128)


@router.get("/api/admin/settings")
async def get_settings(_admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
    return settings_public_view(get_runtime_settings(force=True))


@router.put("/api/admin/settings")
async def put_settings(
    body: SettingsUpdate,
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=422, detail="No settings fields provided")
    updated_by = admin.get("email") or admin.get("uid")
    updated = update_runtime_settings(patch, updated_by=updated_by)
    return settings_public_view(updated)


@router.get("/api/admin/analytics")
async def get_analytics(
    range: str = Query(default="7d", pattern="^(7d|30d)$"),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    days = 30 if range == "30d" else 7
    since = datetime.now(timezone.utc) - timedelta(days=days)
    in_range = list_reports_since(since=since, limit=500)
    return aggregate_analytics(
        range_key=range,
        recent_reports=in_range[:10],
        reports_in_range=in_range,
    )


@router.post("/api/analytics/pageview")
async def post_pageview(body: PageViewBody) -> dict[str, str]:
    record_pageview(body.path, body.session_id)
    return {"status": "ok"}
