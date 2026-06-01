from dataclasses import dataclass


TAKE = "take"
REVIEW = "review"
SKIP = "skip"


@dataclass(frozen=True)
class DirectionInput:
    direction: str
    region: str
    budget_rub: int
    max_difficulty: int
    project_type: str


@dataclass(frozen=True)
class MarketMetrics:
    demand: int
    trend: float
    regional_affinity: float
    commercial_intent: float
    competition: float
    estimated_launch_budget: int
    estimated_difficulty: int
    seasonality: float
    risk_level: float


@dataclass(frozen=True)
class SerpResult:
    title: str
    url: str
    domain: str
    snippet: str


@dataclass(frozen=True)
class SerpAnalysis:
    query: str
    results: list[SerpResult]
    results_count: int
    top_domains: list[str]
    aggregator_count: int
    marketplace_count: int
    competitor_score: float
    estimated_difficulty: int
    score_delta: float
    summary: str


@dataclass(frozen=True)
class NicheAssessment:
    direction: DirectionInput
    metrics: MarketMetrics
    score: float
    verdict: str
    explanation: str
    product_idea: str
    promotion_steps: list[str]
    risks: list[str]
    serp_analysis: SerpAnalysis | None = None
    ai_insight: str | None = None
