from __future__ import annotations

import re
from dataclasses import dataclass, replace

from brainshtorm.models import DirectionInput, EvidenceItem, MarketMetrics


AUTO_PROJECT_TYPE = "auto"
LOCAL_PROJECT_TYPE_SOURCE = "Project type inference"
AI_PROJECT_TYPE_SOURCE = "AI project type inference"

PROJECT_TYPE_OPTIONS = {
    "Авто (сам выберет)": AUTO_PROJECT_TYPE,
    "SEO-сайт": "seo_site",
    "Лидогенерация": "leadgen",
    "Сервис/услуга": "service",
    "Telegram-продукт": "telegram",
    "Инфопродукт": "infoproduct",
    "Маркетплейс/каталог": "marketplace",
}

PROJECT_TYPE_LABELS = {
    AUTO_PROJECT_TYPE: "Авто",
    "seo_site": "SEO-сайт",
    "leadgen": "Лидогенерация",
    "service": "Сервис/услуга",
    "telegram": "Telegram-продукт",
    "infoproduct": "Инфопродукт",
    "marketplace": "Маркетплейс/каталог",
}

VALID_PROJECT_TYPES = {
    project_type
    for project_type in PROJECT_TYPE_LABELS
    if project_type != AUTO_PROJECT_TYPE
}


@dataclass(frozen=True)
class ProjectTypeDecision:
    direction: DirectionInput
    metrics: MarketMetrics
    evidence: EvidenceItem | None


@dataclass(frozen=True)
class ProjectTypeCandidate:
    project_type: str
    score: float
    reasons: list[str]


def project_type_label(project_type: str) -> str:
    return PROJECT_TYPE_LABELS.get(project_type, project_type)


def estimate_launch_budget(project_type: str, difficulty: int) -> int:
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


def resolve_project_type(direction: DirectionInput, metrics: MarketMetrics) -> ProjectTypeDecision:
    if direction.project_type != AUTO_PROJECT_TYPE:
        return ProjectTypeDecision(direction=direction, metrics=metrics, evidence=None)

    candidates = rank_project_type_candidates(direction, metrics)
    return _decision_from_candidates(
        direction,
        metrics,
        candidates,
        source=LOCAL_PROJECT_TYPE_SOURCE,
        rule="local_candidate_scoring_v2",
    )


def resolve_project_type_choice(
    direction: DirectionInput,
    metrics: MarketMetrics,
    *,
    project_type: str,
    source: str,
    rationale: str,
    confidence: float,
) -> ProjectTypeDecision:
    if direction.project_type != AUTO_PROJECT_TYPE:
        return ProjectTypeDecision(direction=direction, metrics=metrics, evidence=None)
    if project_type not in VALID_PROJECT_TYPES:
        return resolve_project_type(direction, metrics)

    candidates = rank_project_type_candidates(direction, metrics)
    resolved_direction, resolved_metrics = _resolved_pair(direction, metrics, project_type)
    evidence = EvidenceItem(
        source=source,
        claim="Рекомендованный тип проекта",
        value=f"{project_type_label(project_type)} ({project_type})",
        details=[
            f"direction={direction.direction}",
            "rule=ai_project_type_override_v1",
            f"ai_confidence={_clamp(confidence, 0.0, 1.0):.2f}",
            f"ai_rationale={_short_detail(rationale)}",
            f"local_candidate_scores={_candidate_scores(candidates)}",
            f"estimated_launch_budget={resolved_metrics.estimated_launch_budget} ₽",
        ],
    )
    return ProjectTypeDecision(
        direction=resolved_direction,
        metrics=resolved_metrics,
        evidence=evidence,
    )


def rank_project_type_candidates(
    direction: DirectionInput,
    metrics: MarketMetrics,
) -> list[ProjectTypeCandidate]:
    text = direction.direction.lower()
    signals = _text_signals(text)

    candidates = [
        _seo_candidate(direction, metrics, signals),
        _leadgen_candidate(direction, metrics, signals),
        _service_candidate(direction, metrics, signals),
        _telegram_candidate(direction, metrics, signals),
        _infoproduct_candidate(direction, metrics, signals),
        _marketplace_candidate(direction, metrics, signals),
    ]
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def _decision_from_candidates(
    direction: DirectionInput,
    metrics: MarketMetrics,
    candidates: list[ProjectTypeCandidate],
    *,
    source: str,
    rule: str,
) -> ProjectTypeDecision:
    winner = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else winner
    margin = round(winner.score - runner_up.score, 1)
    confidence = _selection_confidence(margin)
    resolved_direction, resolved_metrics = _resolved_pair(direction, metrics, winner.project_type)
    evidence = EvidenceItem(
        source=source,
        claim="Рекомендованный тип проекта",
        value=f"{project_type_label(winner.project_type)} ({winner.project_type})",
        details=[
            f"direction={direction.direction}",
            f"rule={rule}",
            f"selected_score={winner.score:.1f}",
            f"winner_margin={margin:.1f}",
            f"selection_confidence={confidence:.2f}",
            f"candidate_scores={_candidate_scores(candidates)}",
            f"selected_reasons={', '.join(winner.reasons[:4])}",
            f"demand={metrics.demand}",
            f"commercial_intent={metrics.commercial_intent:.2f}",
            f"competition={metrics.competition:.2f}",
            f"estimated_difficulty={metrics.estimated_difficulty}/10",
            f"estimated_launch_budget={resolved_metrics.estimated_launch_budget} ₽",
        ],
    )
    return ProjectTypeDecision(
        direction=resolved_direction,
        metrics=resolved_metrics,
        evidence=evidence,
    )


def infer_project_type(direction: DirectionInput, metrics: MarketMetrics) -> tuple[str, str]:
    candidates = rank_project_type_candidates(direction, metrics)
    return candidates[0].project_type, "local_candidate_scoring_v2"


def _resolved_pair(
    direction: DirectionInput,
    metrics: MarketMetrics,
    project_type: str,
) -> tuple[DirectionInput, MarketMetrics]:
    resolved_direction = replace(direction, project_type=project_type)
    resolved_metrics = replace(
        metrics,
        estimated_launch_budget=estimate_launch_budget(
            project_type,
            metrics.estimated_difficulty,
        ),
    )
    return resolved_direction, resolved_metrics


def _seo_candidate(
    direction: DirectionInput,
    metrics: MarketMetrics,
    signals: dict[str, bool],
) -> ProjectTypeCandidate:
    reasons: list[str] = ["content_baseline"]
    score = 24.0 + _demand_bonus(metrics.demand) + _trend_bonus(metrics.trend)
    if signals["guide"]:
        score += 34.0
        reasons.append("guide_terms")
    if metrics.commercial_intent < 0.4:
        score += 16.0
        reasons.append("low_commercial_intent")
    if _budget_fits(direction, metrics, "seo_site"):
        score += 9.0
        reasons.append("budget_fit")
    if signals["service"] or signals["commerce"] or signals["education"]:
        score -= 18.0
        reasons.append("strong_non_content_terms")
    return _candidate("seo_site", score, reasons, metrics)


def _leadgen_candidate(
    direction: DirectionInput,
    metrics: MarketMetrics,
    signals: dict[str, bool],
) -> ProjectTypeCandidate:
    reasons: list[str] = []
    score = 18.0 + _demand_bonus(metrics.demand)
    if signals["service"]:
        score += 35.0
        reasons.append("service_terms")
    if metrics.commercial_intent >= 0.65:
        score += 20.0
        reasons.append("high_commercial_intent")
    if metrics.competition <= 0.65:
        score += 8.0
        reasons.append("manageable_competition")
    if metrics.estimated_difficulty <= direction.max_difficulty:
        score += 7.0
        reasons.append("difficulty_fit")
    if _budget_fits(direction, metrics, "leadgen"):
        score += 8.0
        reasons.append("budget_fit")
    if signals["guide"] and not signals["service"]:
        score -= 26.0
        reasons.append("guide_terms_penalty")
    if signals["education"] or signals["commerce"]:
        score -= 12.0
        reasons.append("strong_alternative_terms")
    return _candidate("leadgen", score, reasons, metrics)


def _service_candidate(
    direction: DirectionInput,
    metrics: MarketMetrics,
    signals: dict[str, bool],
) -> ProjectTypeCandidate:
    reasons: list[str] = []
    score = 16.0 + _demand_bonus(metrics.demand)
    if signals["service"]:
        score += 28.0
        reasons.append("service_terms")
    if 0.45 <= metrics.commercial_intent < 0.75:
        score += 12.0
        reasons.append("moderate_commercial_intent")
    if _budget_fits(direction, metrics, "service"):
        score += 8.0
        reasons.append("budget_fit")
    if signals["guide"] and not signals["service"]:
        score -= 20.0
        reasons.append("guide_terms_penalty")
    if signals["education"] or signals["commerce"]:
        score -= 10.0
        reasons.append("strong_alternative_terms")
    return _candidate("service", score, reasons, metrics)


def _telegram_candidate(
    direction: DirectionInput,
    metrics: MarketMetrics,
    signals: dict[str, bool],
) -> ProjectTypeCandidate:
    reasons: list[str] = []
    score = 12.0 + _trend_bonus(metrics.trend)
    if signals["telegram"]:
        score += 42.0
        reasons.append("telegram_terms")
    if metrics.trend >= 0.15:
        score += 8.0
        reasons.append("strong_trend")
    if _budget_fits(direction, metrics, "telegram"):
        score += 12.0
        reasons.append("low_budget_fit")
    if signals["service"] or signals["commerce"]:
        score -= 14.0
        reasons.append("transactional_terms_penalty")
    return _candidate("telegram", score, reasons, metrics)


def _infoproduct_candidate(
    direction: DirectionInput,
    metrics: MarketMetrics,
    signals: dict[str, bool],
) -> ProjectTypeCandidate:
    reasons: list[str] = []
    score = 15.0 + _demand_bonus(metrics.demand) + _trend_bonus(metrics.trend)
    if signals["education"]:
        score += 38.0
        reasons.append("education_terms")
    if metrics.commercial_intent >= 0.45:
        score += 12.0
        reasons.append("paid_learning_intent")
    if _budget_fits(direction, metrics, "infoproduct"):
        score += 10.0
        reasons.append("budget_fit")
    if signals["service"] or signals["commerce"]:
        score -= 14.0
        reasons.append("strong_alternative_terms")
    return _candidate("infoproduct", score, reasons, metrics)


def _marketplace_candidate(
    direction: DirectionInput,
    metrics: MarketMetrics,
    signals: dict[str, bool],
) -> ProjectTypeCandidate:
    reasons: list[str] = []
    score = 14.0 + _demand_bonus(metrics.demand)
    if signals["commerce"]:
        score += 42.0
        reasons.append("commerce_catalog_terms")
    if metrics.commercial_intent >= 0.6:
        score += 12.0
        reasons.append("transactional_intent")
    if _budget_fits(direction, metrics, "marketplace"):
        score += 10.0
        reasons.append("budget_fit")
    else:
        score -= 8.0
        reasons.append("marketplace_budget_pressure")
    if signals["service"] or signals["education"]:
        score -= 16.0
        reasons.append("strong_alternative_terms")
    return _candidate("marketplace", score, reasons, metrics)


def _candidate(
    project_type: str,
    score: float,
    reasons: list[str],
    metrics: MarketMetrics,
) -> ProjectTypeCandidate:
    penalty = metrics.risk_level * 8 + metrics.seasonality * 3
    return ProjectTypeCandidate(
        project_type=project_type,
        score=round(_clamp(score - penalty), 1),
        reasons=reasons or ["weak_signal"],
    )


def _text_signals(text: str) -> dict[str, bool]:
    telegram_terms = _has_any(text, ["телеграм", "telegram"]) or _has_word(
        text,
        ["бот", "бота", "боты", "канал", "каналы", "чат", "чаты"],
    )
    education_terms = _has_any(text, ["курс", "обуч", "школ", "урок", "вебинар", "интенсив"])
    service_terms = _has_any(
        text,
        ["ремонт", "сервис", "мастер", "установка", "настройка", "диагностик", "услуг"],
    )
    commerce_terms = _has_any(
        text,
        [
            "запчаст",
            "купить",
            "магазин",
            "каталог",
            "товар",
            "аксессуар",
            "комплект",
            "поставщик",
        ],
    )
    guide_terms = _has_any(
        text,
        [
            "уход",
            "инструкц",
            "гайд",
            "совет",
            "обзор",
            "рейтинг",
            "сравнен",
            "идеи",
            "пошаг",
        ],
    ) or _has_word(text, ["как", "что", "где", "почему", "зачем"])
    return {
        "telegram": telegram_terms,
        "education": education_terms,
        "service": service_terms,
        "commerce": commerce_terms,
        "guide": guide_terms,
    }


def _candidate_scores(candidates: list[ProjectTypeCandidate]) -> str:
    return ", ".join(f"{item.project_type}:{item.score:.1f}" for item in candidates[:6])


def _selection_confidence(margin: float) -> float:
    return round(_clamp(0.45 + margin / 70, 0.45, 0.92), 2)


def _budget_fits(direction: DirectionInput, metrics: MarketMetrics, project_type: str) -> bool:
    budget = estimate_launch_budget(project_type, metrics.estimated_difficulty)
    return budget <= direction.budget_rub


def _demand_bonus(demand: int) -> float:
    return min(14.0, demand / 700)


def _trend_bonus(trend: float) -> float:
    return _clamp((trend + 0.05) * 20, 0.0, 9.0)


def _short_detail(value: str, *, limit: int = 160) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _has_word(text: str, terms: list[str]) -> bool:
    return any(
        re.search(rf"(?<![0-9A-Za-zА-Яа-яЁё]){re.escape(term)}(?![0-9A-Za-zА-Яа-яЁё])", text)
        for term in terms
    )


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))
