from types import SimpleNamespace

from brainshtorm.ai import ProjectTypeChoice
import pytest

from brainshtorm.app import APP_STYLE
from brainshtorm.app import _build_ai_client
from brainshtorm.app import _compose_reports
from brainshtorm.app import _generate_practice_ai_report_safely
from brainshtorm.app import _override_estimated_launch_budget
from brainshtorm.app import _project_type_options
from brainshtorm.app import _resolve_region_context
from brainshtorm.app import _selected_region_ids
from brainshtorm.app import _assessment_row
from brainshtorm.app import _score_raw_items
from brainshtorm.local_practice import LocalPracticeProfile, calculate_practice_economics
from brainshtorm.models import DirectionInput, MarketMetrics


def test_app_style_uses_streamlit_theme_tokens():
    assert "background:" not in APP_STYLE
    assert "background-color:" not in APP_STYLE
    assert "background: #f7f8fb" not in APP_STYLE
    assert "background: #ffffff" not in APP_STYLE


def test_assessment_row_handles_legacy_assessment_without_strict_fields():
    assessment = SimpleNamespace(
        direction=DirectionInput("пупсы", "Россия", 150000, 6, "seo_site"),
        metrics=MarketMetrics(1000, 0.1, 1.0, 0.2, 0.4, 60000, 4, 0.1, 0.0),
        score=61.2,
        verdict="review",
        product_idea="Контентный сайт",
        serp_analysis=None,
        keyword_clusters=[],
        product_recommendation=None,
        ai_insight=None,
    )

    row = _assessment_row(assessment)

    assert row["direction"] == "пупсы"
    assert row["project_type"] == "SEO-сайт"
    assert row["score_confidence"] is None
    assert row["evidence_count"] == 0
    assert row["opportunity_score"] is None
    assert row["serp_difficulty"] is None
    assert row["serp_delta"] is None
    assert row["offer_gap"] is None


def test_score_raw_items_uses_ai_project_type_choice_for_auto_direction():
    direction = DirectionInput("ремонт роботов пылесосов", "Россия", 150000, 6, "auto")
    metrics = MarketMetrics(8500, 0.2, 1.0, 0.82, 0.42, 999999, 5, 0.2, 0.1)

    assessments = _score_raw_items(
        [(direction, metrics)],
        {
            0: ProjectTypeChoice(
                direction_id=0,
                project_type="service",
                confidence=0.64,
                rationale="лучше проверять как собственную услугу",
            )
        },
    )

    assert assessments[0].direction.project_type == "service"
    assert assessments[0].evidence_items[0].source == "AI project type inference"


def test_build_ai_client_supports_openrouter():
    client = _build_ai_client(
        provider="OpenRouter",
        openai_api_key="",
        deepseek_api_key="",
        openrouter_api_key="openrouter-secret",
        openai_model="gpt-5.5",
        deepseek_model="deepseek-v4-pro",
        openrouter_model="anthropic/claude-opus-5",
    )

    assert client.model == "anthropic/claude-opus-5"


def test_rybinsk_region_uses_yandex_region_id():
    assert _selected_region_ids("Рыбинск", "") == ["10839"]


def test_compose_reports_does_not_repeat_summary_in_visible_details():
    download_report, visible_details = _compose_reports(
        "# Raw details\n",
        "# Practice summary\n",
        summary_only=True,
    )

    assert download_report.count("# Practice summary") == 1
    assert "# Raw details" not in download_report
    assert visible_details == ""


def test_local_mode_forces_service_project_type_option():
    assert _project_type_options("Локальная практика") == ["Сервис/услуга"]
    assert "Авто (сам выберет)" in _project_type_options("Поиск ниш")


def test_local_rybinsk_region_overrides_mismatched_generic_selection():
    context = _resolve_region_context(
        analysis_mode="Локальная практика",
        local_city="Рыбинск",
        region_label="Россия",
        custom_region_id="",
    )

    assert context.region_ids == ("10839",)
    assert context.serp_region_id == "10839"
    assert context.label == "Рыбинск (Yandex ID 10839)"


def test_unknown_local_city_requires_explicit_yandex_region_id():
    with pytest.raises(ValueError, match="ID региона Яндекса"):
        _resolve_region_context(
            analysis_mode="Локальная практика",
            local_city="Неизвестный город",
            region_label="Россия",
            custom_region_id="",
        )


def test_local_test_budget_override_preserves_measured_metrics():
    metrics = MarketMetrics(52, 0.1, 1.2, 0.8, 0.45, 205000, 5, 0.1, 0.1)

    adjusted = _override_estimated_launch_budget(metrics, 19500)

    assert adjusted.estimated_launch_budget == 19500
    assert adjusted.demand == metrics.demand
    assert adjusted.competition == metrics.competition


def test_practice_ai_failure_returns_error_without_discarding_analysis(monkeypatch):
    class FailingClient:
        def generate(self, *_args, **_kwargs):
            raise TimeoutError("temporary failure")

    monkeypatch.setattr("brainshtorm.app._build_ai_client", lambda **_kwargs: FailingClient())
    profile = LocalPracticeProfile(
        service="детский нейропсихолог",
        audience="родители детей 5-10 лет",
        city="Рыбинск",
    )

    report, error = _generate_practice_ai_report_safely(
        profile,
        calculate_practice_economics(profile),
        [],
        provider="OpenRouter",
        openai_api_key="",
        deepseek_api_key="",
        openrouter_api_key="secret",
        openai_model="",
        deepseek_model="",
        openrouter_model="model",
        data_source="Demo",
        effective_region="Рыбинск",
    )

    assert report is None
    assert "temporary failure" in error
