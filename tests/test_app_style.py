from types import SimpleNamespace

from brainshtorm.app import APP_STYLE
from brainshtorm.app import _assessment_row
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
    assert row["score_confidence"] == ""
    assert row["evidence_count"] == 0
