import logging
import secrets
from typing import Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from httpx import HTTPError
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile

from app.auth import optional_user
from app.config import settings
from app.firebase_app import get_firestore_db
from app.models import (
    ArtifactContext,
    FactCheckReport,
    FactCheckRequest,
    FactCheckResponse,
    ScoreCard,
    Verdict,
)
from app.rate_limit import SlidingWindowRateLimiter
from app.reports_store import load_report, save_report
from app.routers.admin import router as admin_router
from app.services.ai import _ai_available, extract_image_key_info, judge_report, summarize_context
from app.services.analytics import record_fact_check
from app.services.evidence import gather_evidence
from app.services.extractor import extract_artifact_context
from app.services.runtime_settings import get_runtime_settings, mask_secret
from app.services.scoring import score_report
from app.services.image_type import detect_image_mime
from app.services.url_safety import UnsafeUrlError, assert_safe_http_url
from app.services.usage import UsageDenied, UsageUnavailable, consume_anon_quota, consume_user_quota

_CANNOT_DETERMINE_REASON = (
    "This content does not contain a specific, verifiable factual claim that can be fact-checked."
)
_PIPELINE_FAILURE_DETAIL = "Unable to complete the investigation. Please try again later."
_fact_check_limiter = SlidingWindowRateLimiter(
    limit=settings.fact_check_rate_limit,
    window_seconds=settings.fact_check_rate_window_seconds,
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)

# Internal Next.js server address (standalone, started in start.sh)
NEXT_JS_URL = settings.frontend_origin


@app.on_event("startup")
async def startup() -> None:
    rt = get_runtime_settings(force=True)
    print("[startup] Tavily key:", mask_secret(rt.tavily_api_key))
    print("[startup] AI mode:", "local" if rt.use_local_llm else "api")
    if rt.use_local_llm:
        print("[startup] Ollama base URL:", rt.ollama_base_url)
        print("[startup] Ollama model:", rt.ollama_model)
    else:
        print("[startup] OpenAI key:", mask_secret(rt.openai_api_key))
        print("[startup] OpenAI base URL:", rt.openai_base_url or "not set")
        print("[startup] OpenAI model:", rt.openai_model)
    db = get_firestore_db()
    print("[startup] Firebase configured:", "yes" if db else "no")


@app.get("/health")
async def health() -> dict[str, str]:
    rt = get_runtime_settings()
    return {
        "status": "ok",
        "tavily_configured": "yes" if rt.tavily_api_key else "no",
        "ai_configured": "yes" if _ai_available() else "no",
        "ai_mode": "local" if rt.use_local_llm else "api",
        "firebase_configured": "yes" if get_firestore_db() else "no",
    }


class ClientLogBody(BaseModel):
    event: str = Field(max_length=64)
    code: str | None = Field(default=None, max_length=128)
    detail: str | None = Field(default=None, max_length=300)
    cancelled: bool = False


@app.post("/api/client-log")
async def client_log(body: ClientLogBody) -> dict[str, str]:
    """Accept sanitized client auth/events for server-side logging only."""
    level = logging.INFO if body.cancelled else logging.WARNING
    logger.log(
        level,
        "client_log event=%s code=%s cancelled=%s detail=%s",
        body.event,
        body.code or "-",
        body.cancelled,
        body.detail or "-",
    )
    return {"status": "ok"}


def _client_ip(request: Request) -> str:
    """Client IP for anon quotas. Ignore XFF unless TRUST_X_FORWARDED_FOR is set.

    When trust is enabled, use the rightmost XFF hop (typically appended by the
    reverse proxy). Never trust the leftmost hop — clients can spoof it.
    """
    if settings.trust_x_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [part.strip() for part in forwarded.split(",") if part.strip()]
            if hops:
                return hops[-1]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _honeypot_filled(value: Any) -> bool:
    if value is None:
        return False
    return bool(str(value).strip())


async def _parse_fact_check_submission(
    request: Request,
) -> tuple[str | None, str | None, bytes | None, str | None, str | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data") or content_type.startswith(
        "application/x-www-form-urlencoded"
    ):
        form = await request.form()
        if _honeypot_filled(form.get("website")) or _honeypot_filled(form.get("company")):
            raise HTTPException(status_code=422, detail="Invalid submission")
        url_value = form.get("url")
        text_value = form.get("text")
        image_file = form.get("image")
        image_bytes = None
        image_name = None
        image_content_type = None
        if isinstance(image_file, UploadFile) and image_file.filename:
            image_name = image_file.filename
            image_content_type = image_file.content_type
            image_bytes = await image_file.read()
        url = str(url_value).strip() if url_value else None
        text = str(text_value).strip() if text_value else None
        return (url or None, text or None, image_bytes, image_name, image_content_type)

    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid request payload") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid request payload")
    if _honeypot_filled(payload.get("website")) or _honeypot_filled(payload.get("company")):
        raise HTTPException(status_code=422, detail="Invalid submission")
    request_model = FactCheckRequest(**payload)
    url = str(request_model.url) if request_model.url else None
    text = request_model.text.strip() if request_model.text else None
    return (url, text or None, None, None, None)


def _validate_submission(
    url: str | None,
    text: str | None,
    image_bytes: bytes | None,
    image_content_type: str | None,
) -> str | None:
    """Validate inputs. Returns detected image MIME when an image is provided."""
    provided = sum(bool(x) for x in (url, text, image_bytes))
    if provided == 0:
        raise HTTPException(status_code=422, detail="Provide a URL, text, or an image")
    if provided > 1:
        raise HTTPException(status_code=422, detail="Provide only one of URL, text, or image")

    if url is not None:
        if len(url) > settings.max_url_length:
            raise HTTPException(status_code=422, detail="URL is too long")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise HTTPException(status_code=422, detail="URL must start with http:// or https://")
        try:
            assert_safe_http_url(url)
        except UnsafeUrlError as exc:
            raise HTTPException(status_code=422, detail="URL is not allowed") from exc

    if text is not None:
        if len(text) < settings.min_text_chars:
            raise HTTPException(
                status_code=422,
                detail=f"Text must be at least {settings.min_text_chars} characters",
            )
        if len(text) > settings.max_text_chars:
            raise HTTPException(status_code=422, detail="Text is too long")

    if image_bytes is not None:
        if len(image_bytes) == 0:
            raise HTTPException(status_code=422, detail="Image file is empty")
        if len(image_bytes) > settings.max_image_bytes:
            raise HTTPException(status_code=422, detail="Image must be 5 MB or smaller")
        detected = detect_image_mime(image_bytes)
        if detected is None:
            raise HTTPException(
                status_code=422,
                detail="Image must be JPG, PNG, or WebP",
            )
        return detected
    return None


@app.post("/api/fact-check", response_model=FactCheckResponse)
async def fact_check(
    request: Request,
    user: dict[str, Any] | None = Depends(optional_user),
) -> FactCheckResponse | JSONResponse:
    burst_key = f"uid:{user['uid']}" if user else f"ip:{_client_ip(request)}"
    allowed, retry_after = _fact_check_limiter.check(burst_key)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many investigations. Try again shortly."},
            headers={"Retry-After": str(retry_after)},
        )

    try:
        if user:
            consume_user_quota(str(user["uid"]))
        else:
            consume_anon_quota(_client_ip(request))
    except UsageDenied as exc:
        if exc.code == "auth_required":
            return JSONResponse(status_code=401, content={"detail": "auth_required"})
        if exc.code == "daily_limit":
            return JSONResponse(status_code=429, content={"detail": "daily_limit"})
        raise HTTPException(status_code=429, detail=exc.message) from exc
    except UsageUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Usage tracking unavailable",
        ) from exc

    url, text, image_bytes, image_name, _declared_image_type = await _parse_fact_check_submission(
        request
    )
    image_content_type = _validate_submission(url, text, image_bytes, _declared_image_type)

    try:
        image_key_info = await extract_image_key_info(image_bytes, image_content_type, image_name)
        if url:
            context = await extract_artifact_context(url)
            context = context.model_copy(update={"image_key_info": image_key_info})
        elif text:
            context = ArtifactContext(
                source_url="Pasted text",
                title="User-submitted text",
                description="Text-only investigation",
                text=text,
                image_key_info=image_key_info,
            )
        else:
            context = ArtifactContext(
                source_url=image_name or "Uploaded image",
                title=image_name,
                description="Image-only investigation",
                image_key_info=image_key_info,
            )
        summary, claims, verifiable = await summarize_context(context)
        if not verifiable:
            evidence = []
            scores = ScoreCard(
                legitimacy=0,
                evidence_strength=0,
                source_credibility=0,
                contradiction_risk=0,
            )
            verdict = Verdict.cannot_be_determined
            reason = _CANNOT_DETERMINE_REASON
        else:
            evidence = await gather_evidence(summary, claims)
            scores, verdict = score_report(
                evidence,
                summary=summary,
                image_key_info=context.image_key_info,
            )
            reason = await judge_report(summary, claims, evidence, verdict)
    except UnsafeUrlError as exc:
        record_fact_check(ok=False)
        raise HTTPException(status_code=422, detail="URL is not allowed") from exc
    except HTTPError as exc:
        record_fact_check(ok=False)
        raise HTTPException(status_code=422, detail="Unable to fetch or inspect the URL") from exc
    except Exception as exc:
        record_fact_check(ok=False)
        logger.exception("Fact-check pipeline failed")
        raise HTTPException(status_code=500, detail=_PIPELINE_FAILURE_DETAIL) from exc

    report = FactCheckReport(
        url=url,
        context_summary=summary,
        image_key_info=context.image_key_info,
        key_claims=claims,
        evidence=evidence,
        scores=scores,
        verdict=verdict,
        verdict_reason=reason,
    )
    report_id = secrets.token_urlsafe(8)
    save_report(report_id, report)
    record_fact_check(ok=True, verdict=verdict.value)
    return FactCheckResponse(id=report_id, **report.model_dump())


@app.get("/api/reports/{report_id}", response_model=FactCheckReport)
async def get_report(report_id: str) -> FactCheckReport:
    report = load_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# ── Reverse proxy: forward all non-API requests to Next.js on port 3000 ──────
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_to_nextjs(request: Request, path: str) -> StreamingResponse:
    if path.startswith("api/") or path == "health":
        raise HTTPException(status_code=404)

    url = f"{NEXT_JS_URL}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                content=await request.body(),
                follow_redirects=True,
            )
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Frontend server unavailable")

    excluded_headers = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
    }
    headers = {
        k: v for k, v in response.headers.items()
        if k.lower() not in excluded_headers
    }

    return StreamingResponse(
        content=response.aiter_bytes(),
        status_code=response.status_code,
        headers=headers,
    )
