from urllib.parse import urlparse

import httpx
import re

from app.config import settings
from app.models import EvidenceItem


_WORD_RE = re.compile(r"[a-zA-Z0-9\-]+")

_REFUTE_WORDS = frozenset(
    ["not", "no", "never", "none", "false", "fake", "hoax", "deny", "denies", "refute", "refutes", "debunk", "debunked", "disprove", "disproven", "untrue", "incorrect", "misleading", "rumor", "rumours", "scam", "fraud"]
)

TRUSTED_HINTS = (
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "who.int",
    "un.org",
    "gov",
    "edu",
    "nature.com",
    "science.org",
    "factcheck.org",
    "snopes.com",
    "politifact.com",
    "abs-cbn.com",
    "inquirer.net",
    "gmanetwork.com",
    "philstar.com",
    "rappler.com",
    "nytimes.com",
    "theguardian.com",
    "wsj.com",
    "aljazeera.com",
    "cnn.com",
    "nbcnews.com",
    "foxnews.com",
    "msnbc.com",
    "washingtonpost.com",
    "vox.com",
    "npr.org",
    "pbs.org",
    "cbsnews.com",
    "abcnews.go.com",
    "nypost.com",
    "thehill.com",
    "washingtontimes.com",
    "sciencedaily.com",
    "medicalxpress.com",
    "statnews.com",
    "fiercebiotech.com",
    "biomickr.com",
    "jamanetwork.com",
    "the-scientist.com",
)


async def gather_evidence(summary: str, claims: list[str]) -> list[EvidenceItem]:
    query = " ".join(claims[:2]) or summary
    if settings.tavily_api_key:
        return await _search_tavily(query, claims)
    return _demo_evidence(query)


async def _search_tavily(query: str, claims: list[str]) -> list[EvidenceItem]:
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": False,
                "max_results": 6,
            },
        )
        response.raise_for_status()

    results = response.json().get("results", [])
    items = [
        EvidenceItem(
            title=item.get("title") or "Untitled source",
            url=item.get("url") or "",
            snippet=item.get("content") or "",
            source=urlparse(item.get("url") or "").netloc,
            stance=_classify_stance(claims, item.get("content") or ""),
            credibility=_source_trust(
                item.get("url") or "",
                item.get("score"),
            ),
        )
        for item in results
        if item.get("url")
    ]
    return items


def _demo_evidence(query: str) -> list[EvidenceItem]:
    snippet = f"Add TAVILY_API_KEY to search the web for independent evidence about: {query[:180]}"
    return [
        EvidenceItem(
            title="Evidence search is in demo mode",
            url="https://tavily.com/",
            snippet=snippet,
            source="tavily.com",
            stance=_classify_stance([query], snippet),
            credibility=0.6,
        )
    ]


MEDIUM_TRUST_HINTS = (
    "stackoverflow.com",
    "stackexchange.com",
    "github.com",
    "developer.mozilla.org",
    "docs.",
    "microsoft.com",
    "wikipedia.org",
    "wikimedia.org",
    "arxiv.org",
    "nih.gov",
    "ncbi.nlm.nih.gov",
)

LOW_TRUST_HINTS = (
    "reddit.com",
    "quora.com",
    "medium.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "tiktok.com",
    "pinterest.com",
)


def _domain_trust(url: str) -> float:
    host = urlparse(url).netloc.lower()
    if any(hint in host for hint in TRUSTED_HINTS):
        return 0.92
    if host.endswith(".gov") or host.endswith(".edu"):
        return 0.9
    if any(hint in host for hint in MEDIUM_TRUST_HINTS):
        return 0.74
    if any(hint in host for hint in LOW_TRUST_HINTS):
        return 0.46
    return 0.52


def _source_trust(url: str, relevance_score: float | int | None) -> float:
    domain = _domain_trust(url)
    if relevance_score is None:
        return domain

    try:
        relevance = float(relevance_score)
    except (TypeError, ValueError):
        return domain

    if relevance > 1:
        relevance = relevance / 100

    relevance = max(0.0, min(1.0, relevance))
    blended = (domain * 0.45) + (relevance * 0.55)
    return round(max(0.35, min(0.95, blended)), 2)


def _classify_stance(claims: list[str], snippet: str) -> str:
    text = snippet.lower()
    claim_words: set[str] = set()
    for claim in claims:
        for raw in claim.lower().split():
            word = raw.strip(".,;:!?\"'()")
            if len(word) > 3 and word not in _REFUTE_WORDS:
                claim_words.add(word)

    if not claim_words:
        return "neutral"

    sentences = [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]
    supporting = 0
    refuting = 0

    for sentence in sentences:
        sent_words = set(_WORD_RE.findall(sentence))
        if not sent_words & claim_words:
            continue
        has_refute = bool(sent_words & _REFUTE_WORDS)
        if has_refute:
            refuting += 1
        else:
            supporting += 1

    if refuting > supporting:
        return "refutes"
    if supporting > 0:
        return "supports"
    return "neutral"
