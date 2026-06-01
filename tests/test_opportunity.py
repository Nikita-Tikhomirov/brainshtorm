from brainshtorm.models import (
    DirectionInput,
    KeywordCandidate,
    KeywordCluster,
    MarketMetrics,
    NicheAssessment,
    SerpAnalysis,
    TAKE,
)
from brainshtorm.opportunity import apply_product_recommendation, build_product_recommendation


def make_assessment() -> NicheAssessment:
    return NicheAssessment(
        direction=DirectionInput(
            direction="ремонт роботов пылесосов",
            region="Москва",
            budget_rub=150000,
            max_difficulty=6,
            project_type="leadgen",
        ),
        metrics=MarketMetrics(
            demand=9000,
            trend=0.35,
            regional_affinity=1.2,
            commercial_intent=0.85,
            competition=0.35,
            estimated_launch_budget=125000,
            estimated_difficulty=4,
            seasonality=0.2,
            risk_level=0.0,
        ),
        score=78.0,
        verdict=TAKE,
        explanation="Спрос достаточный.",
        product_idea="Лидогенератор заявок.",
        promotion_steps=["Собрать семантику."],
        risks=["Нужно подтвердить экономику на тестовых заявках."],
        keyword_clusters=[
            KeywordCluster(
                name="цены",
                representative_query="ремонт робота пылесоса цена",
                phrases=[
                    KeywordCandidate(
                        phrase="ремонт робота пылесоса цена",
                        count=1900,
                        commercial_score=0.85,
                        modifiers=["цены"],
                    )
                ],
                total_demand=1900,
                commercial_score=0.85,
                serp_analysis=SerpAnalysis(
                    query="ремонт робота пылесоса цена",
                    results=[],
                    results_count=5,
                    top_domains=["small-service.ru", "profi.ru"],
                    aggregator_count=1,
                    marketplace_count=0,
                    competitor_score=0.35,
                    estimated_difficulty=4,
                    score_delta=3.0,
                    summary="оценочная сложность выдачи 4/10; offer gap: 0.62.",
                    offer_signal_score=0.25,
                    offer_gap_score=0.62,
                    competitor_types=["агрегаторы: 1", "сервисные сайты: 1"],
                    offer_signals=["цена"],
                    missing_offer_signals=["гарантия", "скорость"],
                    weak_spots=["В сниппетах мало явных офферов: гарантия, скорость."],
                ),
            ),
            KeywordCluster(
                name="покупка",
                representative_query="купить аккумулятор робота пылесоса",
                phrases=[],
                total_demand=1200,
                commercial_score=0.75,
                serp_analysis=SerpAnalysis(
                    query="купить аккумулятор робота пылесоса",
                    results=[],
                    results_count=5,
                    top_domains=["market.yandex.ru", "ozon.ru"],
                    aggregator_count=0,
                    marketplace_count=2,
                    competitor_score=0.75,
                    estimated_difficulty=8,
                    score_delta=-9.0,
                    summary="оценочная сложность выдачи 8/10.",
                ),
            ),
        ],
    )


def test_build_product_recommendation_returns_actionable_launch_card():
    recommendation = build_product_recommendation(make_assessment())

    assert recommendation.opportunity_score >= 70
    assert "ремонт роботов пылесосов" in recommendation.product_title
    assert recommendation.launch_type == "Лидогенератор услуги"
    assert "ремонт робота пылесоса цена" in recommendation.landing_pages[0]
    assert "гарантия" in recommendation.offer
    assert any("Offer gap SERP" in item for item in recommendation.evidence)
    assert "ручн" not in " ".join(recommendation.evidence + recommendation.risks).lower()
    assert recommendation.first_test


def test_apply_product_recommendation_attaches_card_without_changing_metrics():
    assessment = make_assessment()

    adjusted = apply_product_recommendation(assessment)

    assert adjusted.product_recommendation is not None
    assert adjusted.metrics == assessment.metrics
    assert adjusted.score == assessment.score


def test_recommendation_does_not_delegate_expertise_to_manual_review():
    recommendation = build_product_recommendation(make_assessment())
    text = " ".join(
        [
            recommendation.why_this_can_rank,
            recommendation.first_test,
            *recommendation.traffic_plan,
            *recommendation.evidence,
            *recommendation.risks,
        ]
    ).lower()

    assert "ручн" not in text
    assert "вруч" not in text
