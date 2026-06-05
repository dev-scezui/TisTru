import os
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError
from starlette.datastructures import UploadFile

from app.config import settings
from app.models import ArtifactContext, FactCheckReport, FactCheckRequest, FactCheckResponse
from app.services.ai import _ai_available, extract_image_key_info, judge_report, summarize_context
from app.services.evidence import gather_evidence
from app.services.extractor import extract_artifact_context
from app.services.scoring import score_report

# Optional Firebase Firestore
_firestore_db: Any | None = None

def _get_firestore_db() -> Any | None:
    global _firestore_db
    if _firestore_db is not None:
        return _firestore_db
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
        return _firestore_db
    except Exception as exc:
        import traceback
        print("[firebase] initialization failed:", exc)
        traceback.print_exc()
        return None

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory fallback store for shareable reports
reports_db: dict[str, FactCheckReport] = {}


def _save_report(report_id: str, report: FactCheckReport) -> None:
    db = _get_firestore_db()
    if db:
        db.collection("reports").document(report_id).set(report.model_dump())
    else:
        reports_db[report_id] = report


def _load_report(report_id: str) -> FactCheckReport | None:
    db = _get_firestore_db()
    if db:
        doc = db.collection("reports").document(report_id).get()
        if doc.exists:
            return FactCheckReport(**doc.to_dict())
        return None
    return reports_db.get(report_id)


def _mask(value: str | None, length: int = 6) -> str:
    if not value:
        return "not set"
    if len(value) <= length * 2:
        return "set"
    return f"{value[:length]}...{value[-length:]}"


@app.on_event("startup")
async def startup() -> None:
    print("[startup] Tavily key:", _mask(settings.tavily_api_key))
    print("[startup] AI mode:", "local" if settings.use_local_llm else "api")
    if settings.use_local_llm:
        print("[startup] Ollama base URL:", settings.ollama_base_url)
        print("[startup] Ollama model:", settings.ollama_model)
    else:
        print("[startup] OpenAI key:", _mask(settings.openai_api_key))
        print("[startup] OpenAI base URL:", settings.openai_base_url or "not set")
        print("[startup] OpenAI model:", settings.openai_model)
    db = _get_firestore_db()
    print("[startup] Firebase configured:", "yes" if db else "no")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "tavily_configured": "yes" if settings.tavily_api_key else "no",
        "ai_configured": "yes" if _ai_available() else "no",
        "ai_mode": "local" if settings.use_local_llm else "api",
        "firebase_configured": "yes" if _get_firestore_db() else "no",
    }


async def _parse_fact_check_submission(request: Request) -> tuple[str | None, bytes | None, str | None, str | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        url_value = form.get("url")
        image_file = form.get("image")
        image_bytes = None
        image_name = None
        image_content_type = None
        if isinstance(image_file, UploadFile):
            image_name = image_file.filename
            image_content_type = image_file.content_type
            image_bytes = await image_file.read()
        return (str(url_value) if url_value else None, image_bytes, image_name, image_content_type)

    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid request payload")
    request_model = FactCheckRequest(**payload)
    return (str(request_model.url) if request_model.url else None, None, None, None)


@app.post("/api/fact-check", response_model=FactCheckResponse)
async def fact_check(request: Request) -> FactCheckResponse:
    url, image_bytes, image_name, image_content_type = await _parse_fact_check_submission(request)
    if not url and not image_bytes:
        raise HTTPException(status_code=422, detail="Provide either a URL or an image")
    try:
        image_key_info = await extract_image_key_info(image_bytes, image_content_type, image_name)
        if url:
            context = await extract_artifact_context(url)
            context = context.model_copy(update={"image_key_info": image_key_info})
        else:
            context = ArtifactContext(
                source_url=image_name or "Uploaded image",
                title=image_name,
                description="Image-only investigation",
                image_key_info=image_key_info,
            )
        summary, claims = await summarize_context(context)
        evidence = await gather_evidence(summary, claims)
        scores, verdict = score_report(evidence)
        reason = await judge_report(summary, claims, evidence, verdict)
    except HTTPError as exc:
        raise HTTPException(status_code=422, detail=f"Unable to fetch or inspect the URL: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Fact-check pipeline failed: {exc}") from exc

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
    _save_report(report_id, report)
    return FactCheckResponse(id=report_id, **report.model_dump())


@app.get("/api/reports/{report_id}", response_model=FactCheckReport)
async def get_report(report_id: str) -> FactCheckReport:
    report = _load_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# Serve the bundled frontend (only when the built dist exists, e.g., in Docker)
_frontend_dist = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
_frontend_next = os.path.join(_frontend_dist, "_next")
if os.path.isdir(_frontend_dist) and os.path.isdir(_frontend_next):
    app.mount("/_next", StaticFiles(directory=_frontend_next), name="_next")

    @app.get("/{path:path}")
    async def serve_spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        file_path = os.path.join(_frontend_dist, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_frontend_dist, "index.html"))
