import base64
import json
import re

from openai import AsyncOpenAI

from app.config import settings
from app.models import ArtifactContext, EvidenceItem, Verdict


def _ai_available() -> bool:
    return settings.use_local_llm or bool(settings.openai_api_key or settings.openai_base_url)


def _ai_model() -> str:
    if settings.use_local_llm:
        return settings.ollama_model
    return settings.openai_model


def _ai_client() -> AsyncOpenAI:
    if settings.use_local_llm:
        return AsyncOpenAI(
            api_key="ollama",
            base_url=settings.ollama_base_url,
        )
    return AsyncOpenAI(
        api_key=settings.openai_api_key or "local-model",
        base_url=settings.openai_base_url,
    )


async def extract_image_key_info(
    image_bytes: bytes | None,
    content_type: str | None = None,
    filename: str | None = None,
) -> str | None:
    if not image_bytes:
        return None

    fallback = _image_fallback(filename, content_type, len(image_bytes))
    if not _ai_available():
        return fallback

    try:
        data_url = _to_data_url(image_bytes, content_type)
        client = _ai_client()
        response = await client.chat.completions.create(
            model=_ai_model(),
            messages=[
                {
                    "role": "system",
                    "content": "You inspect a user-uploaded image for fact-checking. Return a concise plain-text note with the most useful visible details, such as text, named entities, dates, locations, logos, screenshots, charts, or claims. Do not use markdown bullets.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract the most important visible details from this image for a fact-check report.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                },
            ],
        )
        extracted = response.choices[0].message.content or ""
        cleaned = extracted.strip()
        return cleaned or fallback
    except Exception:
        return fallback


async def summarize_context(context: ArtifactContext) -> tuple[str, list[str]]:
    if not _ai_available():
        return _heuristic_summary(context)

    client = _ai_client()
    prompt = {
        "source_url": context.source_url,
        "title": context.title,
        "caption": context.caption,
        "description": context.description,
        "text": context.text,
        "image_key_info": context.image_key_info,
        "images": context.images,
        "videos": context.videos,
    }
    response = await client.chat.completions.create(
        model=_ai_model(),
        messages=[
            {"role": "system", "content": "You are a precise summarizer. Extract the post context and factual claims. Respond with ONLY a valid JSON object containing 'summary' (string) and 'key_claims' (array of strings). Do not include markdown fences or extra text."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    payload = _extract_json(raw)
    return payload.get("summary", "No summary generated."), payload.get("key_claims", [])


def _extract_json(text: str) -> dict:
    """Try to extract a JSON object from text that may contain markdown fences or extra prose."""
    stripped = text.strip()
    if stripped.startswith("```"):
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", stripped)
        if match:
            stripped = match.group(1)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"(\{[\s\S]*\})", stripped)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return {}


def _plain_text_reason(text: str) -> str:
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"_+", " ", cleaned)
    return cleaned.strip()


async def judge_report(summary: str, claims: list[str], evidence: list[EvidenceItem], verdict: Verdict) -> str:
    if not _ai_available():
        return "Verdict is based on available search evidence, source credibility, and whether evidence supports or contradicts the extracted claims."

    client = _ai_client()
    response = await client.chat.completions.create(
        model=_ai_model(),
        messages=[
            {
                "role": "system",
                "content": (
                    f"The computed fact-check verdict is '{verdict.value}'. "
                    "Write a concise plain-text rationale (no markdown, bullets, or bold). "
                    "Explain this verdict using only the supplied summary, claims, and evidence. "
                    "Do not contradict the given verdict or invent a different one."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "summary": summary,
                        "claims": claims,
                        "evidence": [item.model_dump() for item in evidence],
                    }
                ),
            },
        ],
    )
    raw = response.choices[0].message.content or "No rationale generated."
    return _plain_text_reason(raw)


def _heuristic_summary(context: ArtifactContext) -> tuple[str, list[str]]:
    parts = [context.title, context.caption, context.description]
    if context.image_key_info:
        parts.append(f"Image notes: {context.image_key_info}")
    summary = " ".join(part for part in parts if part).strip()
    if not summary and context.text:
        summary = context.text[:450]
    if not summary:
        summary = "The submitted URL did not expose enough readable text or metadata for a detailed summary."

    claims = []
    for sentence in summary.replace("?", ".").replace("!", ".").split("."):
        cleaned = sentence.strip()
        if len(cleaned.split()) >= 5:
            claims.append(cleaned)
    return summary, claims[:5]


def _to_data_url(image_bytes: bytes, content_type: str | None) -> str:
    mime_type = content_type or "image/jpeg"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _image_fallback(filename: str | None, content_type: str | None, byte_count: int) -> str:
    parts = ["Uploaded image received"]
    if filename:
        parts.append(f"filename: {filename}")
    if content_type:
        parts.append(f"type: {content_type}")
    parts.append(f"size: {byte_count} bytes")
    return ", ".join(parts)
