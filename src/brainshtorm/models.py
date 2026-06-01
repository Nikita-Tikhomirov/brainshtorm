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
class NicheAssessment:
    direction: DirectionInput
    metrics: MarketMetrics
    score: float
    verdict: str
    explanation: str
    product_idea: str
    promotion_steps: list[str]
    risks: list[str]
