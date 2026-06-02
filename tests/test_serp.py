import base64

from brainshtorm.models import (
    DirectionInput,
    KeywordCandidate,
    KeywordCluster,
    MarketMetrics,
    NicheAssessment,
    REVIEW,
    SerpResult,
    TAKE,
)
from brainshtorm.serp import (
    YandexSerpClient,
    analyze_serp_results,
    apply_keyword_cluster_serp_analysis,
    apply_serp_analysis,
    parse_yandex_xml_results,
)


SERP_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch>
  <response>
    <results>
      <grouping>
        <group>
          <doc>
            <url>https://profi.ru/remont/robot-pylesos/</url>
            <title>Ремонт роботов пылесосов - Профи</title>
            <passages>
              <passage>Мастера и цены на ремонт.</passage>
            </passages>
          </doc>
        </group>
        <group>
          <doc>
            <url>https://small-service.ru/remont-robotov-pylesosov</url>
            <title>Ремонт роботов пылесосов в Москве</title>
            <headline>Частный сервис с гарантией.</headline>
          </doc>
        </group>
      </grouping>
    </results>
  </response>
</yandexsearch>
"""


def test_serp_client_sends_web_search_request_and_decodes_raw_data():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append((url, body, headers, timeout))
        return {"rawData": base64.b64encode(SERP_XML.encode("utf-8")).decode("ascii")}

    client = YandexSerpClient(api_key="secret", folder_id="folder", transport=transport)

    xml_text = client.search_xml("ремонт роботов пылесосов", region_id="213", results_limit=7)

    assert xml_text.startswith("<?xml")
    assert calls[0][0].endswith("/v2/web/search")
    assert calls[0][1]["folderId"] == "folder"
    assert calls[0][1]["query"]["queryText"] == "ремонт роботов пылесосов"
    assert calls[0][1]["region"] == "213"
    assert calls[0][1]["groupSpec"]["groupsOnPage"] == "7"
    assert calls[0][2]["Authorization"] == "Api-key secret"


def test_parse_yandex_xml_results_extracts_top_urls_domains_and_snippets():
    results = parse_yandex_xml_results(SERP_XML)

    assert [item.domain for item in results] == ["profi.ru", "small-service.ru"]
    assert results[0].title == "Ремонт роботов пылесосов - Профи"
    assert results[0].snippet == "Мастера и цены на ремонт."
    assert results[1].snippet == "Частный сервис с гарантией."


def test_analyze_serp_results_scores_aggregator_heavy_serp_as_harder():
    results = parse_yandex_xml_results(SERP_XML)

    analysis = analyze_serp_results(
        query="ремонт роботов пылесосов",
        results=results,
        max_difficulty=4,
    )

    assert analysis.results_count == 2
    assert analysis.aggregator_count == 1
    assert analysis.estimated_difficulty >= 5
    assert analysis.score_delta < 0
    assert "profi.ru" in analysis.top_domains


def test_analyze_serp_results_extracts_offer_gap_and_competitor_types():
    results = parse_yandex_xml_results(SERP_XML)

    analysis = analyze_serp_results(
        query="ремонт роботов пылесосов",
        results=results,
        max_difficulty=6,
    )

    assert analysis.offer_signal_score > 0
    assert analysis.offer_gap_score > 0
    assert "цена" in analysis.offer_signals
    assert "гарантия" in analysis.offer_signals
    assert any("агрегаторы" in item for item in analysis.competitor_types)
    assert analysis.weak_spots
    assert "offer gap" in analysis.summary


def test_analyze_serp_results_marks_weak_offer_serp_as_opportunity_gap():
    results = [
        SerpResult(
            title="Форум владельцев роботов-пылесосов",
            url="https://forum.example/topic",
            domain="forum.example",
            snippet="Как выбрать и обслуживать устройство дома.",
        ),
        SerpResult(
            title="Обзор моделей",
            url="https://blog.example/review",
            domain="blog.example",
            snippet="Статья без цен, гарантии и формы заказа.",
        ),
    ]

    analysis = analyze_serp_results(
        query="ремонт роботов пылесосов xiaomi цена",
        results=results,
        max_difficulty=6,
    )

    assert analysis.offer_gap_score >= 0.5
    assert any("Мало страниц" in spot for spot in analysis.weak_spots)
    assert any("информационные" in item for item in analysis.competitor_types)


def test_apply_serp_analysis_adjusts_assessment_verdict_and_risks():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=4,
        project_type="leadgen",
    )
    assessment = NicheAssessment(
        direction=direction,
        metrics=MarketMetrics(
            demand=9000,
            trend=0.4,
            regional_affinity=1.1,
            commercial_intent=0.8,
            competition=0.45,
            estimated_launch_budget=125000,
            estimated_difficulty=4,
            seasonality=0.2,
            risk_level=0.0,
        ),
        score=76.0,
        verdict=TAKE,
        explanation="ok",
        product_idea="leadgen",
        promotion_steps=["step"],
        risks=[],
    )
    analysis = analyze_serp_results(
        query=direction.direction,
        results=parse_yandex_xml_results(SERP_XML),
        max_difficulty=direction.max_difficulty,
    )

    adjusted = apply_serp_analysis(assessment, analysis)

    assert adjusted.serp_analysis == analysis
    assert adjusted.score < assessment.score
    assert adjusted.verdict == REVIEW
    assert any("SERP" in risk for risk in adjusted.risks)
    assert any(item.source == "Yandex SERP" and item.claim == "Seed SERP" for item in adjusted.evidence_items)


def test_apply_serp_analysis_adds_score_adjustment_to_breakdown():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )
    assessment = NicheAssessment(
        direction=direction,
        metrics=MarketMetrics(
            demand=9000,
            trend=0.4,
            regional_affinity=1.1,
            commercial_intent=0.8,
            competition=0.45,
            estimated_launch_budget=125000,
            estimated_difficulty=4,
            seasonality=0.2,
            risk_level=0.0,
        ),
        score=76.0,
        verdict=TAKE,
        explanation="ok",
        product_idea="leadgen",
        promotion_steps=["step"],
        risks=[],
    )
    analysis = analyze_serp_results(
        query=direction.direction,
        results=parse_yandex_xml_results(SERP_XML),
        max_difficulty=direction.max_difficulty,
    )

    adjusted = apply_serp_analysis(assessment, analysis)
    breakdown = adjusted.score_breakdown

    assert breakdown is not None
    assert breakdown.final_score == adjusted.score
    assert any(factor.key == "seed_serp_delta" for factor in breakdown.factors)
    assert breakdown.confidence >= 0.7


def test_apply_keyword_cluster_serp_analysis_attaches_clusters_and_adjusts_score():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=4,
        project_type="leadgen",
    )
    assessment = NicheAssessment(
        direction=direction,
        metrics=MarketMetrics(
            demand=9000,
            trend=0.4,
            regional_affinity=1.1,
            commercial_intent=0.8,
            competition=0.45,
            estimated_launch_budget=125000,
            estimated_difficulty=4,
            seasonality=0.2,
            risk_level=0.0,
        ),
        score=76.0,
        verdict=TAKE,
        explanation="ok",
        product_idea="leadgen",
        promotion_steps=["step"],
        risks=[],
    )
    cluster = KeywordCluster(
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
        serp_analysis=analyze_serp_results(
            query="ремонт роботов пылесосов xiaomi",
            results=parse_yandex_xml_results(SERP_XML),
            max_difficulty=direction.max_difficulty,
        ),
    )

    adjusted = apply_keyword_cluster_serp_analysis(assessment, [cluster])

    assert adjusted.keyword_clusters == [cluster]
    assert adjusted.score < assessment.score
    assert adjusted.verdict == REVIEW
    assert "Кластеры" in adjusted.explanation
    assert any("Кластеры" in risk for risk in adjusted.risks)
