from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class Verdict(str, Enum):
    legitimate = "legitimate"
    likely_legitimate = "likely_legitimate"
    uncertain = "uncertain"
    likely_fake = "likely_fake"
    fake = "fake"


class FactCheckRequest(BaseModel):
    url: HttpUrl


class ArtifactContext(BaseModel):
    source_url: str
    title: str | None = None
    caption: str | None = None
    description: str | None = None
    text: str | None = None
    images: list[str] = Field(default_factory=list)
    videos: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    title: str
    url: str
    snippet: str
    source: str | None = None
    stance: str = "neutral"
    credibility: float = 0.5


class ScoreCard(BaseModel):
    legitimacy: int
    evidence_strength: int
    source_credibility: int
    contradiction_risk: int


class FactCheckReport(BaseModel):
    url: str
    context_summary: str
    key_claims: list[str]
    evidence: list[EvidenceItem]
    scores: ScoreCard
    verdict: Verdict
    verdict_reason: str


class FactCheckResponse(FactCheckReport):
    id: str
