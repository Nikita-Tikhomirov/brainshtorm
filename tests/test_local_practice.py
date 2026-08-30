from brainshtorm.local_practice import (
    LocalPracticeProfile,
    build_local_practice_ai_prompt,
    build_local_practice_queries,
    calculate_practice_economics,
    generate_local_practice_ai_report,
    render_local_practice_report,
    render_practice_economics,
)
from brainshtorm.models import DirectionInput, MarketMetrics, SerpAnalysis, SerpResult
from brainshtorm.scoring import score_direction


def make_profile() -> LocalPracticeProfile:
    return LocalPracticeProfile(
        service="детский нейропсихолог",
        audience="родители детей 5-10 лет",
        city="Рыбинск",
        session_price_rub=1500,
        diagnostic_price_rub=3000,
        course_sessions=8,
        room_cost_per_visit_rub=500,
        ad_test_budget_rub=15000,
    )


def test_build_local_practice_queries_covers_service_local_and_problem_demand():
    queries = build_local_practice_queries(make_profile())

    assert queries[0] == "детский нейропсихолог Рыбинск"
    assert "детский психолог Рыбинск" in queries
    assert "подготовка к школе Рыбинск" in queries
    assert "СДВГ у ребенка" in queries
    assert "ребенок плохо учится" in queries
    assert all("родители детей" not in query for query in queries)
    assert len(queries) == len(set(query.casefold() for query in queries))
    assert 20 <= len(queries) <= 50


def test_build_local_practice_queries_accepts_extra_parent_problems_without_duplicates():
    queries = build_local_practice_queries(
        make_profile(),
        extra_queries=["страх школы у ребенка", "Детский психолог Рыбинск"],
    )

    assert "страх школы у ребенка" in queries
    assert sum(query.casefold() == "детский психолог рыбинск" for query in queries) == 1


def test_build_local_practice_queries_keeps_twenty_query_contract_for_generic_service():
    profile = LocalPracticeProfile(
        service="семейный психолог",
        audience="родителей с детьми",
        city="Рыбинск",
    )

    queries = build_local_practice_queries(profile)

    assert 20 <= len(queries) <= 50
    assert "семейный психолог записаться Рыбинск" in queries
    assert "семейный психолог для родителей с детьми Рыбинск" in queries


def test_calculate_practice_economics_exposes_assumptions_and_break_even():
    economics = calculate_practice_economics(make_profile())

    assert economics.revenue_per_client_rub == 15000
    assert economics.contribution_before_marketing_rub == 9900
    assert economics.break_even_clients_for_ad_test == 2
    assert economics.recommended_cac_cap_rub == 3465
    assert economics.minimum_test_reserve_rub == 19500
    assert [scenario.new_clients for scenario in economics.scenarios] == [3, 6, 10]
    assert economics.scenarios[1].monthly_revenue_rub == 90000
    assert economics.scenarios[1].operating_result_rub == 44400


def test_render_practice_economics_labels_calculations_as_assumptions():
    report = render_practice_economics(make_profile(), calculate_practice_economics(make_profile()))

    assert "расчетные допущения" in report.lower()
    assert "не прогноз спроса" in report.lower()
    assert "CAC" in report
    assert "44 400" in report


def test_negative_unit_contribution_is_reported_as_impossible_to_break_even():
    profile = LocalPracticeProfile(
        service="детский нейропсихолог",
        audience="родители",
        city="Рыбинск",
        session_price_rub=0,
        diagnostic_price_rub=0,
        course_sessions=8,
        room_cost_per_visit_rub=500,
        ad_test_budget_rub=15000,
    )

    economics = calculate_practice_economics(profile)
    report = render_practice_economics(profile, economics)

    assert economics.contribution_before_marketing_rub == -4500
    assert economics.break_even_clients_for_ad_test is None
    assert "невозможна при текущих вводных" in report


def make_assessment():
    assessment = score_direction(
        DirectionInput(
            "детский психолог Рыбинск",
            "Рыбинск",
            50000,
            7,
            "service",
        ),
        MarketMetrics(52, 0.1, 1.2, 0.8, 0.45, 75000, 5, 0.1, 0.1),
    )
    return assessment.__class__(
        **{
            **assessment.__dict__,
            "serp_analysis": SerpAnalysis(
                query="детский психолог Рыбинск",
                results=[
                    SerpResult(
                        title="Центр развития",
                        url="https://example.ru/psychologist",
                        domain="example.ru",
                        snippet="Диагностика и занятия",
                    )
                ],
                results_count=1,
                top_domains=["example.ru"],
                aggregator_count=0,
                marketplace_count=0,
                competitor_score=0.45,
                estimated_difficulty=5,
                score_delta=0.0,
                summary="средняя конкуренция",
                offer_gap_score=0.4,
                weak_spots=["У части результатов нет цены."],
            ),
        }
    )


def test_build_local_practice_ai_prompt_is_evidence_bound_and_aggregate_safe():
    profile = make_profile()
    prompt = build_local_practice_ai_prompt(
        profile,
        calculate_practice_economics(profile),
        [make_assessment()],
        data_source="Yandex Wordstat API + Yandex Web Search",
        effective_region="Рыбинск (Yandex ID 10839)",
    )

    assert "не суммируй частотности" in prompt.lower()
    assert "детский психолог Рыбинск | demand=52" in prompt
    assert "example.ru" in prompt
    assert "offer_gap=0.4" in prompt
    assert "CAC" in prompt
    assert "GO / CONDITIONAL GO / NO-GO" in prompt
    assert "minimum_test_reserve=19500" in prompt
    assert "data_source=Yandex Wordstat API + Yandex Web Search" in prompt
    assert "effective_region=Рыбинск (Yandex ID 10839)" in prompt


def test_generate_local_practice_ai_report_uses_large_single_synthesis_call():
    calls = []

    class Client:
        def generate(self, prompt, *, max_output_tokens=900):
            calls.append((prompt, max_output_tokens))
            return "  Вердикт: CONDITIONAL GO  "

    report = generate_local_practice_ai_report(
        make_profile(),
        calculate_practice_economics(make_profile()),
        [make_assessment()],
        Client(),
    )

    assert report == "Вердикт: CONDITIONAL GO"
    assert calls[0][1] == 6000


def test_render_local_practice_report_keeps_ai_and_raw_evidence_together():
    profile = make_profile()
    report = render_local_practice_report(
        profile,
        calculate_practice_economics(profile),
        [make_assessment()],
        ai_report="Вердикт: CONDITIONAL GO",
        data_source="Demo (синтетические данные)",
        effective_region="Рыбинск (Yandex ID 10839)",
    )

    assert "# Детский нейропсихолог — Рыбинск" in report
    assert "Вердикт: CONDITIONAL GO" in report
    assert "Частотности запросов нельзя складывать" in report
    assert "| детский психолог Рыбинск | 52 |" in report
    assert "## Экономика локальной практики" in report
    assert "Demo (синтетические данные)" in report
    assert "Рыбинск (Yandex ID 10839)" in report
