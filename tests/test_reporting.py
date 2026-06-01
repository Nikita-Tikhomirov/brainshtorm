from brainshtorm.models import DirectionInput, MarketMetrics, NicheAssessment, SerpAnalysis, SerpResult
from brainshtorm.reporting import render_markdown_report


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
            demand=8500,
            trend=0.28,
            regional_affinity=1.25,
            commercial_intent=0.85,
            competition=0.35,
            estimated_launch_budget=110000,
            estimated_difficulty=5,
            seasonality=0.2,
            risk_level=0.1,
        ),
        score=82.4,
        verdict="take",
        explanation="Спрос растет, конкуренция умеренная.",
        product_idea="Лидогенератор заявок на ремонт.",
        promotion_steps=["SEO-страницы по моделям", "Яндекс Директ по горячим запросам"],
        risks=["Проверить качество подрядчиков"],
    )


def make_assessment_with_serp() -> NicheAssessment:
    assessment = make_assessment()
    return NicheAssessment(
        direction=assessment.direction,
        metrics=assessment.metrics,
        score=74.0,
        verdict="review",
        explanation=assessment.explanation,
        product_idea=assessment.product_idea,
        promotion_steps=assessment.promotion_steps,
        risks=assessment.risks,
        serp_analysis=SerpAnalysis(
            query="ремонт роботов пылесосов",
            results=[
                SerpResult(
                    title="Ремонт роботов пылесосов",
                    url="https://profi.ru/remont/robot-pylesos/",
                    domain="profi.ru",
                    snippet="Мастера и цены.",
                )
            ],
            results_count=1,
            top_domains=["profi.ru"],
            aggregator_count=1,
            marketplace_count=0,
            competitor_score=0.8,
            estimated_difficulty=8,
            score_delta=-8.4,
            summary="оценочная сложность выдачи 8/10; агрегаторов в топе: 1.",
        ),
    )


def test_markdown_report_contains_ranked_verdicts():
    report = render_markdown_report([make_assessment()])

    assert "# Runet Niche Analyzer Report" in report
    assert "ремонт роботов пылесосов" in report
    assert "take" in report
    assert "SEO-страницы по моделям" in report


def test_markdown_report_contains_serp_details_when_available():
    report = render_markdown_report([make_assessment_with_serp()])

    assert "SERP analysis" in report
    assert "profi.ru" in report
    assert "SERP score delta: `-8.4`" in report
