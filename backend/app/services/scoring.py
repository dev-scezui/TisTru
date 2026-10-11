import re

from app.models import EvidenceItem, ScoreCard, Verdict

# Match only phrasing that means *this artifact/source* is satirical news,
# not incidental uses like "a parody of The Hunger Games".
_SATIRE_MARKERS = re.compile(
    r"\b("
    r"parody\s+outlet|satire\s+outlet|satirical\s+outlet|"
    r"parody\s+news|satirical\s+news|satire\s+site|"
    r"satire\s+post|satirical\s+post|"
    r"satirical\s+presentation|"
    r"labeled\s+as\s+(?:satire|parody)|"
    r"joke\s+post|humor\s+post|humour\s+post|"
    r"fake\s+news\s+satire|onion[\-\s]?style"
    r")\b",
    re.IGNORECASE,
)


def _artifact_is_satire(summary: str = "", image_key_info: str | None = None) -> bool:
    blob = f"{summary or ''}\n{image_key_info or ''}"
    return bool(_SATIRE_MARKERS.search(blob))


def score_report(
    evidence: list[EvidenceItem],
    *,
    summary: str = "",
    image_key_info: str | None = None,
) -> tuple[ScoreCard, Verdict]:
    if not evidence:
        scores = ScoreCard(legitimacy=35, evidence_strength=10, source_credibility=0, contradiction_risk=65)
        return scores, Verdict.uncertain

    credibility = round(sum(item.credibility for item in evidence) / len(evidence) * 100)
    support = sum(1 for item in evidence if item.stance == "supports")
    refute = sum(1 for item in evidence if item.stance == "refutes")
    trusted_support = sum(1 for item in evidence if item.credibility >= 0.9 and item.stance == "supports")
    contradiction_risk = max(0, min(100, 10 + refute * 25 - support * 15))

    # Strength tracks corroboration of the claim, not raw search-hit count.
    evidence_strength = min(
        100,
        support * 22 + trusted_support * 10 + (credibility // 4 if support else 8),
    )
    if support == 0:
        evidence_strength = min(evidence_strength, 22)
        contradiction_risk = max(contradiction_risk, 40)

    consensus_bonus = min(15, max(0, (trusted_support - 1) * 6))
    legitimacy = max(
        0,
        min(
            100,
            round(
                (credibility * 0.50)
                + (evidence_strength * 0.40)
                - (contradiction_risk * 0.20)
                + consensus_bonus
            ),
        ),
    )

    # Explicit satire / parody labels mean the artifact is not presenting real news.
    # Do not let loosely related real coverage (e.g. a Manila fan meeting) inflate legitimacy.
    if _artifact_is_satire(summary, image_key_info):
        contradiction_risk = max(contradiction_risk, 75)
        legitimacy = min(legitimacy, 28)

    # Related hits that never corroborate the *specific* claim are uncertain, not proof of fraud.
    if support == 0 and refute == 0 and not _artifact_is_satire(summary, image_key_info):
        legitimacy = max(36, min(legitimacy, 45))

    scores = ScoreCard(
        legitimacy=legitimacy,
        evidence_strength=evidence_strength,
        source_credibility=credibility,
        contradiction_risk=contradiction_risk,
    )

    if legitimacy >= 75:
        verdict = Verdict.legitimate
    elif legitimacy >= 50:
        verdict = Verdict.likely_legitimate
    elif legitimacy <= 20:
        verdict = Verdict.fake
    elif legitimacy <= 35:
        verdict = Verdict.likely_fake
    else:
        verdict = Verdict.uncertain

    return scores, verdict
