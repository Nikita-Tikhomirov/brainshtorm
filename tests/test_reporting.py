from brainshtorm.models import DirectionInput, MarketMetrics, NicheAssessment
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


def test_markdown_report_contains_ranked_verdicts():
    report = render_markdown_report([make_assessment()])

    assert "# Runet Niche Analyzer Report" in report
    assert "ремонт роботов пылесосов" in report
    assert "take" in report
    assert "SEO-страницы по моделям" in report
