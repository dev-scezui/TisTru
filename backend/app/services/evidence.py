from urllib.parse import urlparse

import httpx
import re

from app.config import settings
from app.models import EvidenceItem
from app.services.runtime_settings import get_runtime_settings


_WORD_RE = re.compile(r"[a-zA-Z0-9\-]+")

_REFUTE_WORDS = frozenset(
    [
        "not",
        "no",
        "never",
        "none",
        "false",
        "fake",
        "hoax",
        "deny",
        "denies",
        "refute",
        "refutes",
        "debunk",
        "debunked",
        "disprove",
        "disproven",
        "untrue",
        "incorrect",
        "misleading",
        "rumor",
        "rumours",
        "scam",
        "fraud",
        "manipulated",
        "manipulation",
        "fabricated",
        "fabrication",
        "doctored",
        "photoshopped",
        "deepfake",
        "bogus",
        "falsehood",
    ]
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
    "verafiles.org"
)


async def gather_evidence(summary: str, claims: list[str]) -> list[EvidenceItem]:
    query = " ".join(claims[:2]) or summary
    tavily_key = get_runtime_settings().tavily_api_key
    if tavily_key:
        return await _search_tavily(query, claims, tavily_key)
    return _demo_evidence(query)


async def _search_tavily(query: str, claims: list[str], api_key: str) -> list[EvidenceItem]:
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
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
            stance=_classify_stance(
                claims,
                f"{item.get('title') or ''}. {item.get('content') or ''}",
            ),
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
    host = urlparse(url).netloc.lower()
    is_low_trust = any(hint in host for hint in LOW_TRUST_HINTS)

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
    # Relevance must not promote Facebook/X/TikTok/etc. into near-news credibility.
    ceiling = 0.55 if is_low_trust else 0.95
    return round(max(0.35, min(ceiling, blended)), 2)


_COMMON_WORDS = frozenset(
    [
        "that",
        "this",
        "with",
        "from",
        "have",
        "been",
        "were",
        "will",
        "their",
        "about",
        "after",
        "before",
        "under",
        "over",
        "into",
        "also",
        "than",
        "then",
        "when",
        "what",
        "which",
        "while",
        "where",
        "there",
        "these",
        "those",
        "being",
        "said",
        "says",
        "according",
        "claims",
        "claim",
        "president",
        "minister",
        "government",
        "official",
        "officials",
        "junior",
    ]
)

_WEAK_ANCHOR_PARTS = frozenset(
    ["style", "type", "kind", "like", "based", "old", "new", "two", "three", "four", "five"]
)

_SPECIFICITY_LEXICON = frozenset(
    [
        "tricycle",
        "tricycles",
        "sidecar",
        "pedicab",
        "deepfake",
        "photoshopped",
    ]
)

_HYPHEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+")
_PROPER_SEQ_RE = re.compile(r"\b(?:[A-Z][a-zA-Z]+\b[\s.,\"']*){2,}")


def _light_stems(word: str) -> set[str]:
    stems = {word}
    if len(word) > 5 and word.endswith("ation"):
        stems.add(word[:-5])
    if len(word) > 6 and word.endswith("ations"):
        stems.add(word[:-6])
    if len(word) > 5 and word.endswith("ing"):
        stems.add(word[:-3])
    if len(word) > 4 and word.endswith("ed"):
        stems.add(word[:-2])
        stems.add(word[:-1])
    if len(word) > 4 and word.endswith("es"):
        stems.add(word[:-2])
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        stems.add(word[:-1])
    return stems


def _expand_stems(words: set[str]) -> set[str]:
    expanded: set[str] = set()
    for word in words:
        expanded |= _light_stems(word)
    return expanded


def _normalize_tokens(text: str) -> set[str]:
    lower = text.lower()
    words = set(_WORD_RE.findall(lower))
    for compound in _HYPHEN_RE.findall(lower):
        words.add(compound)
        words.update(compound.split("-"))
    return words


def _person_name_tokens(claims: list[str]) -> set[str]:
    names: set[str] = set()
    for claim in claims:
        for quoted in re.findall(r'"([^"]+)"', claim):
            names.update(_WORD_RE.findall(quoted.lower()))
        for match in _PROPER_SEQ_RE.finditer(claim):
            names.update(word.lower() for word in _WORD_RE.findall(match.group(0)))
    return names


def _specificity_anchors(claims: list[str]) -> set[str]:
    """Distinctive claim modifiers that supporting evidence must also mention."""
    anchors: set[str] = set()
    for claim in claims:
        lower = claim.lower()
        for compound in _HYPHEN_RE.findall(lower):
            anchors.add(compound)
            for part in compound.split("-"):
                if part not in _WEAK_ANCHOR_PARTS and len(part) >= 4:
                    anchors.add(part)
        for word in _WORD_RE.findall(lower):
            if word in _SPECIFICITY_LEXICON:
                anchors.add(word)
    return anchors


def _claim_content_words(claims: list[str]) -> set[str]:
    words: set[str] = set()
    for claim in claims:
        words |= _normalize_tokens(claim)
    return {
        word
        for word in words
        if len(word) > 3 and word not in _REFUTE_WORDS and word not in _COMMON_WORDS
    }


def _classify_stance(claims: list[str], snippet: str) -> str:
    claim_words = _claim_content_words(claims)
    if not claim_words:
        return "neutral"

    anchors = _specificity_anchors(claims)
    name_tokens = _person_name_tokens(claims)
    detail_words = claim_words - anchors - name_tokens
    claim_stems = _expand_stems(claim_words)
    anchor_stems = _expand_stems(anchors)
    detail_stems = _expand_stems(detail_words)

    sentences = [s.strip() for s in re.split(r"[.!?\n]+", snippet.lower()) if s.strip()]
    supporting = 0
    refuting = 0

    for sentence in sentences:
        sent_words = _normalize_tokens(sentence)
        sent_stems = _expand_stems(sent_words)
        overlap = sent_stems & claim_stems
        if not overlap:
            continue

        has_refute = bool(sent_words & _REFUTE_WORDS)

        if has_refute:
            refuting += 1
            continue

        # Specific modifiers (e.g. tricycle-style) must be corroborated, not inferred
        # from a broader related event (generic ambulances / fire trucks).
        if anchors and not (sent_stems & anchor_stems):
            continue

        if anchors and detail_stems:
            detail_hits = sent_stems & detail_stems
            needed = 1 if len(detail_words) <= 3 else 2
            if len(detail_hits) < needed:
                continue
        elif not anchors:
            min_overlap = max(2, (len(claim_words) * 2 + 4) // 5)  # ~40%
            if len(overlap) < min_overlap:
                continue

        supporting += 1

    if refuting > supporting:
        return "refutes"
    if supporting > 0:
        return "supports"
    return "neutral"
