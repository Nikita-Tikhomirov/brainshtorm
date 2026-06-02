from brainshtorm.models import DirectionInput, MarketMetrics
from brainshtorm.project_types import (
    AUTO_PROJECT_TYPE,
    estimate_launch_budget,
    project_type_label,
    resolve_project_type,
)


def make_direction(text: str, project_type: str = AUTO_PROJECT_TYPE) -> DirectionInput:
    return DirectionInput(
        direction=text,
        region="Россия",
        budget_rub=150000,
        max_difficulty=6,
        project_type=project_type,
    )


def make_metrics(
    *,
    commercial_intent: float,
    demand: int = 4200,
    competition: float = 0.45,
    estimated_difficulty: int = 5,
) -> MarketMetrics:
    return MarketMetrics(
        demand=demand,
        trend=0.12,
        regional_affinity=1.0,
        commercial_intent=commercial_intent,
        competition=competition,
        estimated_launch_budget=999999,
        estimated_difficulty=estimated_difficulty,
        seasonality=0.2,
        risk_level=0.1,
    )


def test_auto_project_type_selects_seo_site_for_informational_theme():
    decision = resolve_project_type(
        make_direction("уход за кактусами"),
        make_metrics(commercial_intent=0.22, demand=3600, competition=0.35, estimated_difficulty=4),
    )

    assert decision.direction.project_type == "seo_site"
    assert decision.metrics.estimated_launch_budget == estimate_launch_budget("seo_site", 4)
    assert decision.evidence is not None
    assert decision.evidence.claim == "Рекомендованный тип проекта"
    assert "commercial_intent=0.22" in decision.evidence.details


def test_auto_project_type_keeps_guide_theme_as_seo_site_even_with_high_intent():
    decision = resolve_project_type(
        make_direction("уход за кактусами"),
        make_metrics(commercial_intent=0.82, demand=7200, competition=0.42, estimated_difficulty=5),
    )

    assert decision.direction.project_type == "seo_site"


def test_auto_project_type_selects_leadgen_for_repair_service_theme():
    decision = resolve_project_type(
        make_direction("ремонт роботов пылесосов"),
        make_metrics(commercial_intent=0.82, competition=0.42, estimated_difficulty=5),
    )

    assert decision.direction.project_type == "leadgen"
    assert "Лидогенерация" in project_type_label(decision.direction.project_type)


def test_auto_project_type_selects_infoproduct_for_learning_theme():
    decision = resolve_project_type(
        make_direction("курсы нейросетей"),
        make_metrics(commercial_intent=0.74, competition=0.5, estimated_difficulty=5),
    )

    assert decision.direction.project_type == "infoproduct"


def test_auto_project_type_selects_marketplace_for_parts_theme():
    decision = resolve_project_type(
        make_direction("запчасти для квадроциклов"),
        make_metrics(commercial_intent=0.78, competition=0.48, estimated_difficulty=5),
    )

    assert decision.direction.project_type == "marketplace"


def test_manual_project_type_is_not_overridden():
    metrics = make_metrics(commercial_intent=0.9, estimated_difficulty=6)
    decision = resolve_project_type(make_direction("ремонт техники", "seo_site"), metrics)

    assert decision.direction.project_type == "seo_site"
    assert decision.metrics is metrics
    assert decision.evidence is None
