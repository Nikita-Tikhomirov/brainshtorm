from __future__ import annotations

import re
from dataclasses import dataclass, replace

from brainshtorm.models import DirectionInput, EvidenceItem, MarketMetrics


AUTO_PROJECT_TYPE = "auto"

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


@dataclass(frozen=True)
class ProjectTypeDecision:
    direction: DirectionInput
    metrics: MarketMetrics
    evidence: EvidenceItem | None


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

    project_type, rule = infer_project_type(direction, metrics)
    resolved_direction = replace(direction, project_type=project_type)
    resolved_metrics = replace(
        metrics,
        estimated_launch_budget=estimate_launch_budget(
            project_type,
            metrics.estimated_difficulty,
        ),
    )

    evidence = EvidenceItem(
        source="Project type inference",
        claim="Рекомендованный тип проекта",
        value=f"{project_type_label(project_type)} ({project_type})",
        details=[
            f"direction={direction.direction}",
            f"rule={rule}",
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
    text = direction.direction.lower()

    telegram_terms = _has_any(text, ["телеграм", "telegram"]) or _has_word(
        text,
        ["бот", "бота", "боты", "канал", "каналы", "чат", "чаты"],
    )
    if telegram_terms and metrics.commercial_intent >= 0.45:
        return "telegram", "telegram_terms_with_commercial_intent"

    if (
        _has_any(text, ["курс", "обуч", "школ", "урок", "вебинар", "интенсив"])
        and metrics.commercial_intent >= 0.45
    ):
        return "infoproduct", "education_terms_with_commercial_intent"

    if _has_any(
        text,
        ["ремонт", "сервис", "мастер", "установка", "настройка", "диагностик", "услуг"],
    ):
        if metrics.commercial_intent >= 0.55:
            return "leadgen", "service_terms_with_high_commercial_intent"
        return "service", "service_terms_with_moderate_commercial_intent"

    if _has_any(
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
    ):
        return "marketplace", "commerce_catalog_terms"

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
    if guide_terms:
        return "seo_site", "guide_or_howto_terms"

    if metrics.commercial_intent < 0.4:
        return "seo_site", "low_commercial_intent_information_project"

    if (
        metrics.commercial_intent >= 0.65
        and metrics.competition <= 0.65
        and metrics.estimated_difficulty <= direction.max_difficulty
    ):
        return "leadgen", "high_intent_with_manageable_competition"

    if metrics.demand >= 3000 and metrics.trend >= 0.1:
        return "seo_site", "growing_demand_content_project"

    return "seo_site", "default_content_hypothesis"


def _has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _has_word(text: str, terms: list[str]) -> bool:
    return any(
        re.search(rf"(?<![0-9A-Za-zА-Яа-яЁё]){re.escape(term)}(?![0-9A-Za-zА-Яа-яЁё])", text)
        for term in terms
    )
