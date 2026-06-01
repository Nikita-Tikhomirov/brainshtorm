import hashlib
from typing import Protocol

from brainshtorm.models import DirectionInput, MarketMetrics


class MarketDataProvider(Protocol):
    def metrics_for(self, direction: DirectionInput) -> MarketMetrics:
        """Return market metrics for one seed direction."""


class DemoMarketDataProvider:
    """Deterministic provider for local development without paid APIs."""

    def metrics_for(self, direction: DirectionInput) -> MarketMetrics:
        value = _stable_int(direction.direction, direction.region, direction.project_type)
        demand = 800 + value % 14000
        trend = round(-0.15 + ((value >> 4) % 55) / 100, 2)
        regional_affinity = round(0.75 + ((value >> 9) % 70) / 100, 2)
        commercial_intent = round(0.35 + ((value >> 14) % 60) / 100, 2)
        competition = round(0.25 + ((value >> 20) % 70) / 100, 2)
        seasonality = round(((value >> 26) % 80) / 100, 2)
        risk_level = _estimate_risk(direction.direction)
        estimated_difficulty = max(1, min(10, round(competition * 10)))
        estimated_launch_budget = _estimate_launch_budget(direction.project_type, estimated_difficulty)

        return MarketMetrics(
            demand=demand,
            trend=trend,
            regional_affinity=regional_affinity,
            commercial_intent=commercial_intent,
            competition=competition,
            estimated_launch_budget=estimated_launch_budget,
            estimated_difficulty=estimated_difficulty,
            seasonality=seasonality,
            risk_level=risk_level,
        )


def get_provider(name: str) -> MarketDataProvider:
    if name == "demo":
        return DemoMarketDataProvider()
    raise ValueError(f"unsupported provider: {name}")


def _stable_int(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _estimate_launch_budget(project_type: str, difficulty: int) -> int:
    base_by_type = {
        "seo_site": 90000,
        "leadgen": 110000,
        "service": 130000,
        "telegram": 60000,
        "infoproduct": 80000,
        "marketplace": 250000,
    }
    base = base_by_type.get(project_type, 120000)
    return base + difficulty * 15000


def _estimate_risk(direction: str) -> float:
    text = direction.lower()
    risky_terms = [
        "банкрот",
        "кредит",
        "займ",
        "медицина",
        "лечение",
        "диагноз",
        "юрист",
        "юрид",
        "инвести",
    ]
    matches = sum(1 for term in risky_terms if term in text)
    return min(0.9, matches * 0.25)
