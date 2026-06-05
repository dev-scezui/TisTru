from app.models import EvidenceItem, ScoreCard, Verdict


def score_report(evidence: list[EvidenceItem]) -> tuple[ScoreCard, Verdict]:
    if not evidence:
        scores = ScoreCard(legitimacy=35, evidence_strength=10, source_credibility=0, contradiction_risk=65)
        return scores, Verdict.uncertain

    credibility = round(sum(item.credibility for item in evidence) / len(evidence) * 100)
    evidence_strength = min(100, len(evidence) * 15 + credibility // 2)
    support = sum(1 for item in evidence if item.stance == "supports")
    refute = sum(1 for item in evidence if item.stance == "refutes")
    trusted_support = sum(1 for item in evidence if item.credibility >= 0.9 and item.stance == "supports")
    contradiction_risk = max(0, min(100, 10 + refute * 25 - support * 15))
    consensus_bonus = min(15, max(0, (trusted_support - 1) * 6))
    legitimacy = max(0, min(100, round((credibility * 0.50) + (evidence_strength * 0.40) - (contradiction_risk * 0.20) + consensus_bonus)))

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
