from dataclasses import dataclass, field


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
class KeywordCandidate:
    phrase: str
    count: int
    commercial_score: float
    modifiers: list[str]


@dataclass(frozen=True)
class KeywordCluster:
    name: str
    representative_query: str
    phrases: list[KeywordCandidate]
    total_demand: int
    commercial_score: float
    serp_analysis: SerpAnalysis | None = None


@dataclass(frozen=True)
class ProductRecommendation:
    product_title: str
    launch_type: str
    target_audience: str
    opportunity_score: float
    offer: str
    why_this_can_rank: str
    landing_pages: list[str]
    traffic_plan: list[str]
    first_test: str
    evidence: list[str]
    risks: list[str]


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
    keyword_clusters: list[KeywordCluster] = field(default_factory=list)
    product_recommendation: ProductRecommendation | None = None
    ai_insight: str | None = None
