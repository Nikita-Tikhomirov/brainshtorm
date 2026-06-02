from brainshtorm.models import DirectionInput, MarketMetrics
from brainshtorm.scoring import score_direction


def test_high_quality_direction_gets_take_verdict():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )
    metrics = MarketMetrics(
        demand=8500,
        trend=0.28,
        regional_affinity=1.25,
        commercial_intent=0.85,
        competition=0.35,
        estimated_launch_budget=110000,
        estimated_difficulty=5,
        seasonality=0.2,
        risk_level=0.1,
    )

    result = score_direction(direction, metrics)

    assert result.verdict == "take"
    assert result.score >= 75
    assert "лидогенератор" in result.product_idea
    assert result.score_breakdown is not None
    assert result.score_breakdown.formula_version
    assert result.score_breakdown.final_score == result.score
    assert any(factor.key == "demand" and factor.raw_value == "8500" for factor in result.score_breakdown.factors)
    assert any(item.source == "Wordstat" and item.claim == "Спрос" for item in result.evidence_items)


def test_score_breakdown_contributions_match_final_score():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )
    metrics = MarketMetrics(
        demand=8500,
        trend=0.28,
        regional_affinity=1.25,
        commercial_intent=0.85,
        competition=0.35,
        estimated_launch_budget=110000,
        estimated_difficulty=5,
        seasonality=0.2,
        risk_level=0.1,
    )

    result = score_direction(direction, metrics)
    breakdown = result.score_breakdown

    assert breakdown is not None
    contribution_total = round(sum(factor.contribution for factor in breakdown.factors), 1)
    assert contribution_total == result.score
    assert breakdown.confidence < 0.7
    assert any("SERP" in note for note in breakdown.confidence_notes)


def test_expensive_and_competitive_direction_gets_skip_verdict():
    direction = DirectionInput(
        direction="юридическая помощь банкротство",
        region="Россия",
        budget_rub=50000,
        max_difficulty=4,
        project_type="seo_site",
    )
    metrics = MarketMetrics(
        demand=15000,
        trend=0.05,
        regional_affinity=0.9,
        commercial_intent=0.8,
        competition=0.95,
        estimated_launch_budget=350000,
        estimated_difficulty=9,
        seasonality=0.1,
        risk_level=0.8,
    )

    result = score_direction(direction, metrics)

    assert result.verdict == "skip"
    assert result.score < 50
    assert "риск" in " ".join(result.risks).lower()


def test_mid_quality_direction_gets_review_verdict():
    direction = DirectionInput(
        direction="ремонт электросамокатов",
        region="Санкт-Петербург",
        budget_rub=120000,
        max_difficulty=6,
        project_type="service",
    )
    metrics = MarketMetrics(
        demand=4200,
        trend=0.12,
        regional_affinity=1.05,
        commercial_intent=0.7,
        competition=0.55,
        estimated_launch_budget=130000,
        estimated_difficulty=6,
        seasonality=0.65,
        risk_level=0.2,
    )

    result = score_direction(direction, metrics)

    assert result.verdict == "review"
    assert 50 <= result.score < 75
