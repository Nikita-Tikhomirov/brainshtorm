from __future__ import annotations

import csv
import io

import streamlit as st

from brainshtorm.app_inputs import parse_pasted_directions
from brainshtorm.models import NicheAssessment
from brainshtorm.providers import DemoMarketDataProvider
from brainshtorm.reporting import render_markdown_report
from brainshtorm.scoring import score_direction
from brainshtorm.settings import AppSettings, load_settings, save_settings
from brainshtorm.yandex_wordstat import (
    YandexWordstatClient,
    YandexWordstatError,
    YandexWordstatProvider,
)


REGION_OPTIONS = {
    "Россия": [],
    "Москва": ["213"],
    "Санкт-Петербург": ["2"],
    "Без региона": [],
}


PROJECT_TYPES = {
    "SEO-сайт": "seo_site",
    "Лидогенерация": "leadgen",
    "Сервис/услуга": "service",
    "Telegram-продукт": "telegram",
    "Инфопродукт": "infoproduct",
    "Маркетплейс/каталог": "marketplace",
}


APP_STYLE = """
<style>
.stButton > button {
    border-radius: 6px;
    font-weight: 600;
}
textarea, input {
    border-radius: 6px !important;
}
</style>
"""


def run_app() -> None:
    st.set_page_config(page_title="Runet Niche Analyzer", layout="wide")
    _inject_styles()
    settings = load_settings()

    st.title("Runet Niche Analyzer")

    with st.sidebar:
        st.header("Источник данных")
        provider_options = ["Yandex Wordstat API", "Demo"]
        provider_name = st.radio(
            "Режим",
            provider_options,
            index=_option_index(provider_options, settings.provider_name),
            horizontal=False,
        )
        api_key = st.text_input("Yandex API key", value=settings.api_key, type="password")
        folder_id = st.text_input("Yandex folder ID", value=settings.folder_id, type="password")
        st.caption("Ключи и параметры сохраняются локально в профиле Windows и не попадают в git.")

        st.header("Параметры пачки")
        region_options = list(REGION_OPTIONS.keys())
        region_label = st.selectbox(
            "Регион",
            region_options,
            index=_option_index(region_options, settings.region_label),
        )
        custom_region_id = st.text_input(
            "ID региона Яндекса, если нужен другой",
            value=settings.custom_region_id,
        )
        budget_rub = st.number_input(
            "Бюджет запуска, ₽",
            min_value=1000,
            value=max(1000, int(settings.budget_rub)),
            step=10000,
        )
        max_difficulty = st.slider(
            "Максимальная сложность",
            min_value=1,
            max_value=10,
            value=_clamp(settings.max_difficulty, 1, 10),
        )
        project_options = list(PROJECT_TYPES.keys())
        project_label = st.selectbox(
            "Тип проекта",
            project_options,
            index=_option_index(project_options, settings.project_label, default=1),
        )
        num_phrases = st.slider(
            "Фраз Wordstat на направление",
            10,
            200,
            _snap_to_step(settings.num_phrases, minimum=10, maximum=200, step=10),
            10,
        )

    pasted = st.text_area(
        "Список направлений, по одному на строку",
        value=settings.pasted_directions,
        height=220,
        placeholder="ремонт роботов пылесосов\nкурсы нейросетей\nзапчасти для квадроциклов",
    )

    current_settings = AppSettings(
        provider_name=provider_name,
        api_key=api_key,
        folder_id=folder_id,
        region_label=region_label,
        custom_region_id=custom_region_id,
        budget_rub=int(budget_rub),
        max_difficulty=int(max_difficulty),
        project_label=project_label,
        num_phrases=int(num_phrases),
        pasted_directions=pasted,
    )

    col_run, col_save = st.columns(2)
    with col_run:
        run_clicked = st.button("Запустить анализ", type="primary", width="stretch")
    with col_save:
        save_clicked = st.button("Сохранить параметры", width="stretch")
    st.caption("Лимит первого рабочего режима: до 100 направлений за прогон.")

    if save_clicked:
        _save_user_settings(current_settings, show_success=True)

    if not run_clicked:
        return

    _save_user_settings(current_settings, show_success=False)

    try:
        directions = parse_pasted_directions(
            pasted,
            region=region_label,
            budget_rub=int(budget_rub),
            max_difficulty=int(max_difficulty),
            project_type=PROJECT_TYPES[project_label],
        )
        region_ids = _selected_region_ids(region_label, custom_region_id)
        assessments = _run_analysis(
            provider_name=provider_name,
            api_key=api_key,
            folder_id=folder_id,
            region_ids=region_ids,
            num_phrases=num_phrases,
            directions=directions,
        )
    except (ValueError, YandexWordstatError) as exc:
        st.error(str(exc))
        return

    _render_results(assessments)


def _run_analysis(
    *,
    provider_name: str,
    api_key: str,
    folder_id: str,
    region_ids: list[str],
    num_phrases: int,
    directions,
) -> list[NicheAssessment]:
    if provider_name == "Demo":
        provider = DemoMarketDataProvider()
    else:
        client = YandexWordstatClient(api_key=api_key, folder_id=folder_id)
        provider = YandexWordstatProvider(
            client=client,
            region_ids=region_ids,
            num_phrases=num_phrases,
        )

    progress = st.progress(0)
    assessments: list[NicheAssessment] = []
    for index, direction in enumerate(directions, start=1):
        assessments.append(score_direction(direction, provider.metrics_for(direction)))
        progress.progress(index / len(directions))
    return sorted(assessments, key=lambda item: item.score, reverse=True)


def _save_user_settings(settings: AppSettings, *, show_success: bool) -> None:
    try:
        settings_path = save_settings(settings)
    except OSError as exc:
        st.warning(f"Не удалось сохранить параметры: {exc}")
        return

    if show_success:
        st.success(f"Параметры сохранены: {settings_path}")


def _render_results(assessments: list[NicheAssessment]) -> None:
    st.subheader("Результат")
    rows = [_assessment_row(item) for item in assessments]
    st.dataframe(rows, width="stretch", hide_index=True)

    csv_text = _rows_to_csv(rows)
    report = render_markdown_report(assessments)

    left, right = st.columns(2)
    with left:
        st.download_button(
            "Скачать CSV",
            data=csv_text.encode("utf-8-sig"),
            file_name="analysis.csv",
            mime="text/csv",
            width="stretch",
        )
    with right:
        st.download_button(
            "Скачать Markdown-отчет",
            data=report.encode("utf-8"),
            file_name="report.md",
            mime="text/markdown",
            width="stretch",
        )

    st.markdown(report)


def _assessment_row(assessment: NicheAssessment) -> dict[str, object]:
    return {
        "direction": assessment.direction.direction,
        "score": assessment.score,
        "verdict": assessment.verdict,
        "demand": assessment.metrics.demand,
        "trend": assessment.metrics.trend,
        "competition": assessment.metrics.competition,
        "budget_fit": assessment.metrics.estimated_launch_budget,
        "difficulty": assessment.metrics.estimated_difficulty,
        "product": assessment.product_idea,
    }


def _rows_to_csv(rows: list[dict[str, object]]) -> str:
    if not rows:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _selected_region_ids(region_label: str, custom_region_id: str) -> list[str]:
    custom = custom_region_id.strip()
    if custom:
        return [custom]
    return REGION_OPTIONS[region_label]


def _option_index(options: list[str], value: str, *, default: int = 0) -> int:
    try:
        return options.index(value)
    except ValueError:
        return default


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _snap_to_step(value: int, *, minimum: int, maximum: int, step: int) -> int:
    clamped = _clamp(value, minimum, maximum)
    return minimum + round((clamped - minimum) / step) * step


def _inject_styles() -> None:
    st.markdown(APP_STYLE, unsafe_allow_html=True)


if __name__ == "__main__":
    run_app()
