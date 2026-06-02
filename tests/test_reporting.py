from types import SimpleNamespace

from brainshtorm.models import (
    DirectionInput,
    KeywordCandidate,
    KeywordCluster,
    MarketMetrics,
    NicheAssessment,
    ProductRecommendation,
    SerpAnalysis,
    SerpResult,
)
from brainshtorm.reporting import render_markdown_report
from brainshtorm.scoring import score_direction


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
            summary="оценочная сложность выдачи 8/10; агрегаторов в топе: 1; offer gap: 0.55.",
            offer_signal_score=0.3,
            offer_gap_score=0.55,
            competitor_types=["агрегаторы: 1"],
            offer_signals=["цена"],
            missing_offer_signals=["гарантия", "скорость"],
            weak_spots=["В топе заметная доля агрегаторов, можно конкурировать более точной посадочной страницей."],
        ),
    )


def make_assessment_with_ai() -> NicheAssessment:
    assessment = make_assessment_with_serp()
    return NicheAssessment(
        direction=assessment.direction,
        metrics=assessment.metrics,
        score=assessment.score,
        verdict=assessment.verdict,
        explanation=assessment.explanation,
        product_idea=assessment.product_idea,
        promotion_steps=assessment.promotion_steps,
        risks=assessment.risks,
        serp_analysis=assessment.serp_analysis,
        ai_insight="Вердикт: брать в тест.\nПродукт: лидогенератор заявок.",
    )


def make_assessment_with_keyword_clusters() -> NicheAssessment:
    assessment = make_assessment()
    return NicheAssessment(
        direction=assessment.direction,
        metrics=assessment.metrics,
        score=assessment.score,
        verdict=assessment.verdict,
        explanation=assessment.explanation,
        product_idea=assessment.product_idea,
        promotion_steps=assessment.promotion_steps,
        risks=assessment.risks,
        keyword_clusters=[
            KeywordCluster(
                name="ремонт/сервис",
                representative_query="ремонт роботов пылесосов xiaomi",
                phrases=[
                    KeywordCandidate(
                        phrase="ремонт роботов пылесосов xiaomi",
                        count=2600,
                        commercial_score=0.6,
                        modifiers=["ремонт/сервис"],
                    )
                ],
                total_demand=2600,
                commercial_score=0.6,
                serp_analysis=SerpAnalysis(
                    query="ремонт роботов пылесосов xiaomi",
                    results=[],
                    results_count=0,
                    top_domains=["profi.ru"],
                    aggregator_count=1,
                    marketplace_count=0,
                    competitor_score=0.8,
                    estimated_difficulty=8,
                    score_delta=-7.0,
                    summary="оценочная сложность выдачи 8/10; offer gap: 0.50.",
                    offer_gap_score=0.5,
                ),
            )
        ],
    )


def make_assessment_with_product_recommendation() -> NicheAssessment:
    assessment = make_assessment()
    return NicheAssessment(
        direction=assessment.direction,
        metrics=assessment.metrics,
        score=assessment.score,
        verdict=assessment.verdict,
        explanation=assessment.explanation,
        product_idea=assessment.product_idea,
        promotion_steps=assessment.promotion_steps,
        risks=assessment.risks,
        product_recommendation=ProductRecommendation(
            product_title="Лидогенератор ремонта роботов пылесосов",
            launch_type="Лидогенератор услуги",
            target_audience="Владельцы роботов-пылесосов в Москве",
            opportunity_score=82.0,
            offer="Диагностика и ремонт с подбором мастера",
            why_this_can_rank="Есть слабый коммерческий кластер.",
            landing_pages=["Страница под `ремонт робота пылесоса цена`"],
            traffic_plan=["SEO по кластеру цен", "Директ по горячим запросам"],
            first_test="Запустить 3 посадочные страницы и форму заявки.",
            evidence=["Спрос 8500", "Кластер цен сложность 4/10"],
            risks=["Следить за стоимостью лида"],
        ),
    )


def test_markdown_report_contains_ranked_verdicts():
    report = render_markdown_report([make_assessment()])

    assert "# Runet Niche Analyzer Report" in report
    assert "ремонт роботов пылесосов" in report
    assert "take" in report
    assert "SEO-страницы по моделям" in report


def test_markdown_report_handles_legacy_assessment_without_strict_fields():
    assessment = SimpleNamespace(
        direction=DirectionInput("кактусы", "Россия", 150000, 6, "seo_site"),
        metrics=MarketMetrics(1200, 0.1, 1.0, 0.2, 0.4, 60000, 4, 0.1, 0.0),
        score=62.5,
        verdict="review",
        explanation="legacy",
        product_idea="Контентный сайт",
        promotion_steps=["Собрать статьи"],
        risks=["Проверить спрос"],
        serp_analysis=None,
        keyword_clusters=[],
        product_recommendation=None,
        ai_insight=None,
    )

    report = render_markdown_report([assessment])

    assert "кактусы" in report
    assert "Strict evidence" not in report


def test_markdown_report_contains_strict_evidence_and_score_formula():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )
    assessment = score_direction(
        direction,
        MarketMetrics(
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
    )

    report = render_markdown_report([assessment])

    assert "Strict evidence" in report
    assert "Score formula" in report
    assert "demand" in report
    assert "raw `8500`" in report
    assert "Wordstat: Спрос" in report


def test_markdown_report_contains_serp_details_when_available():
    report = render_markdown_report([make_assessment_with_serp()])

    assert "SERP analysis" in report
    assert "profi.ru" in report
    assert "SERP score delta: `-8.4`" in report
    assert "Offer gap: `0.55`" in report
    assert "SERP weak spots" in report


def test_markdown_report_contains_ai_insight_when_available():
    report = render_markdown_report([make_assessment_with_ai()])

    assert "AI verdict" in report
    assert "Вердикт: брать в тест." in report


def test_markdown_report_contains_keyword_clusters_when_available():
    report = render_markdown_report([make_assessment_with_keyword_clusters()])

    assert "Keyword clusters" in report
    assert "ремонт/сервис" in report
    assert "ремонт роботов пылесосов xiaomi" in report
    assert "difficulty 8/10" in report
    assert "offer gap `0.50`" in report


def test_markdown_report_contains_product_recommendation_when_available():
    report = render_markdown_report([make_assessment_with_product_recommendation()])

    assert "Launch recommendation" in report
    assert "Лидогенератор ремонта роботов пылесосов" in report
    assert "Opportunity score: `82.0`" in report
    assert "ремонт робота пылесоса цена" in report
