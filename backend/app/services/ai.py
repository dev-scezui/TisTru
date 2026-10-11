import base64
import json
import re

from openai import AsyncOpenAI

from app.models import ArtifactContext, EvidenceItem, Verdict
from app.services.runtime_settings import get_runtime_settings


def _ai_available() -> bool:
    rt = get_runtime_settings()
    return rt.use_local_llm or bool(rt.openai_api_key or rt.openai_base_url)


def _ai_model() -> str:
    rt = get_runtime_settings()
    if rt.use_local_llm:
        return rt.ollama_model
    return rt.openai_model


def _ai_client() -> AsyncOpenAI:
    rt = get_runtime_settings()
    if rt.use_local_llm:
        return AsyncOpenAI(
            api_key="ollama",
            base_url=rt.ollama_base_url,
        )
    return AsyncOpenAI(
        api_key=rt.openai_api_key or "local-model",
        base_url=rt.openai_base_url,
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
                    "content": (
                        "You inspect a user-uploaded image for fact-checking. "
                        "Return a concise plain-text note of ONLY what is literally visible: "
                        "on-image text, charts, logos, screenshots, dates, locations, or asserted claims shown in the image. "
                        "Preserve brand/logo spellings EXACTLY as written, including typos or misspellings "
                        "(e.g. write INQIURER if that is what appears, never autocorrect to Inquirer). "
                        "Always quote any satire/parody/joke labels if they are literally printed on the image. "
                        "Do not infer that a brand or outlet is satire/parody from the name alone. "
                        "Do not guess identities, names, meme origins, viral history, or off-image context. "
                        "If it is a reaction meme or joke caption with no factual assertion, say so briefly and quote the visible text. "
                        "Do not use markdown bullets."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe only the literally visible details useful for deciding whether this image has a fact-checkable claim.",
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


async def summarize_context(context: ArtifactContext) -> tuple[str, list[str], bool]:
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
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise extraction stage for a fact-checking system. "
                    "A downstream verifier will check your claims, so they must be faithful, specific, and standalone. "
                    "You extract; you never judge whether a claim is true. "
                    "Do not use judgment words such as 'falsely', 'misleading', or 'debunked'. "

                    # --- Input ---
                    "The user message is a JSON object describing one artifact (post text, image descriptions, image_key_info, etc.). "
                    "Use only what the artifact itself shows or says. "

                    # --- Writing claims ---
                    "CLAIMS: List each distinct real-world claim the artifact puts forward, most central first, "
                    "at most 8, merging duplicates. "
                    "Each claim must be one self-contained sentence that a stranger could check without seeing the post. "
                    "Keep every distinctive detail: vehicle/object type, location, quantity, dates, names, and modifiers "
                    "(e.g. 'tricycle-style' / three-wheeled, not just 'ambulances'). "
                    "Never broaden a specific claim into a generic one, and never add details that are not in the artifact. "
                    "Write claims in English, but keep names and quotes in their original language. "
                    "Resolve relative dates ('yesterday', 'this week') against the post date if given; "
                    "otherwise keep them relative and say so in the claim. "
                    "Ignore speculative identity guesses or viral-lore notes in image_key_info unless the artifact itself asserts them. "

                    # --- What counts as a checkable claim ---
                    "A claim is checkable if a fact-checker could, in principle, find a public record, news report, "
                    "or provenance trail that confirms or refutes it. Apply these rules: "
                    "(1) Personal anecdotes ('my neighbor's dog saved a kid'), predictions, hypotheticals, "
                    "and hyperbole ('everyone is leaving this city') are NOT checkable. "
                    "(2) Opinion with an embedded fact ('worst mayor ever, he cut the police budget by 40%'): "
                    "extract only the factual part. "
                    "(3) A rhetorical question that implies a claim ('why is the media hiding that X causes Y?'): "
                    "extract the implied claim. "
                    "(4) A captioned image or video ('footage from yesterday's protest in X'): "
                    "the claim is the image's provenance (what/where/when), even if no sentence looks like a claim. "
                    "(5) A screenshot of something a person said: the claim is that the person said it; "
                    "extract the content of what they said as its own claim only if the artifact endorses it as fact. "

                    # --- Satire / parody ---
                    "SATIRE: Only label the artifact itself as satire/parody when (a) it has an explicit satire/joke label, "
                    "or (b) it mimics a real news brand via misspelled branding. "
                    "When that applies, use an allowlisted phrase such as 'parody outlet' or 'satirical presentation' in the summary "
                    "and still extract the surface claims people might believe if they miss the label. "
                    "Do not invent 'parody outlet' or similar from an unfamiliar brand name alone, or from an absurd premise alone. "
                    "If the content merely discusses a film, show, or work that is a parody of something else, "
                    "describe that without labeling the artifact as satire. "

                    # --- verifiable ---
                    "VERIFIABLE: Decide in this order. "
                    "(1) If at least one checkable claim exists that the artifact presents as real "
                    "(including satire presented as a real event, and claims it reports others as saying), set verifiable to true. "
                    "(2) Otherwise, if the content is only vague/unfalsifiable, opinion, a reaction meme, joke, "
                    "caption template (e.g. 'When you accidentally flip the camera'), humor, or entertainment with no assertion of fact, "
                    "set verifiable to false. "
                    "(3) If you are genuinely torn between true and false, choose true and extract the best candidate claim; "
                    "a wasted check is cheaper than a missed one. "
                    "If verifiable is false, key_claims must be an empty array. "

                    # --- Summary ---
                    "SUMMARY: 1-2 neutral sentences covering who posted what, in what format, and the overall framing. "

                    # --- Examples ---
                    "EXAMPLES: "
                    "Post text 'BREAKING: 12 tricycle-style ambulances deployed in Cebu after quake' -> "
                    "verifiable true, key_claims ['Twelve tricycle-style (three-wheeled) ambulances were deployed in Cebu after an earthquake.']. "
                    "Image of a cat captioned 'me when the wifi drops' -> verifiable false, key_claims []. "
                    "Banner 'The Onion Bulletin' with a small 'satire' tag over the headline 'Mayor bans Mondays citywide' -> "
                    "summary mentions a satirical presentation, verifiable true, key_claims ['The mayor banned Mondays citywide.']. "
                    "A post praising the film 'Scary Movie' as a parody of horror films -> "
                    "summary describes a discussion of a parody film without calling the post satire; "
                    "verifiable false unless it asserts a specific checkable fact. "

                    # --- Output contract ---
                    "Respond with ONLY a valid JSON object containing "
                    "'summary' (string), 'key_claims' (array of strings), and 'verifiable' (boolean). "
                    "Do not include markdown fences or extra text."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    payload = _extract_json(raw)
    summary = payload.get("summary", "No summary generated.")
    claims = payload.get("key_claims", [])
    if not isinstance(claims, list):
        claims = []
    claims = [str(c).strip() for c in claims if str(c).strip()]
    if "verifiable" in payload:
        verifiable = bool(payload["verifiable"]) and bool(claims)
    else:
        verifiable = bool(claims)
    return summary, claims, verifiable


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


def _heuristic_summary(context: ArtifactContext) -> tuple[str, list[str], bool]:
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
    claims = claims[:5]
    return summary, claims, bool(claims)


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
