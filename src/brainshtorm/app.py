from __future__ import annotations

import csv
import io
from dataclasses import dataclass, replace

import streamlit as st

from brainshtorm.ai import (
    AiError,
    DeepSeekClient,
    OpenAiClient,
    OpenRouterClient,
    apply_ai_insight,
    generate_ai_insight,
    generate_project_type_choices,
)
from brainshtorm.app_inputs import parse_pasted_directions
from brainshtorm.keywords import attach_cluster_serp
from brainshtorm.local_practice import (
    LocalPracticeProfile,
    build_local_practice_queries,
    calculate_practice_economics,
    generate_local_practice_ai_report,
    render_local_practice_report,
)
from brainshtorm.models import MarketMetrics, NicheAssessment
from brainshtorm.opportunity import apply_product_recommendation
from brainshtorm.project_types import (
    AI_PROJECT_TYPE_SOURCE,
    AUTO_PROJECT_TYPE,
    PROJECT_TYPE_OPTIONS,
    project_type_label,
    resolve_project_type_choice,
)
from brainshtorm.providers import DemoMarketDataProvider
from brainshtorm.reporting import render_markdown_report
from brainshtorm.scoring import score_direction, score_project_type_decision
from brainshtorm.serp import (
    DemoSerpProvider,
    YandexSerpClient,
    YandexSerpError,
    YandexSerpProvider,
    apply_keyword_cluster_serp_analysis,
    apply_serp_analysis,
)
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
    "Рыбинск": ["10839"],
    "Без региона": [],
}

DEFAULT_SERP_REGION_ID = "225"


PROJECT_TYPES = PROJECT_TYPE_OPTIONS

AI_PROVIDERS = ["OpenRouter", "GPT", "DeepSeek"]
ANALYSIS_MODES = ["Поиск ниш", "Локальная практика"]


@dataclass(frozen=True)
class RegionContext:
    region_ids: tuple[str, ...]
    serp_region_id: str
    label: str


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

        st.header("Сценарий")
        analysis_mode = st.selectbox(
            "Что анализируем",
            ANALYSIS_MODES,
            index=_option_index(ANALYSIS_MODES, settings.analysis_mode),
        )
        if analysis_mode == "Локальная практика":
            local_service = st.text_input(
                "Услуга или специалист",
                value=settings.local_service,
                placeholder="детский нейропсихолог",
            )
            local_audience = st.text_input(
                "Основная аудитория",
                value=settings.local_audience,
                placeholder="родители детей 5-10 лет",
            )
            local_city = st.text_input(
                "Город",
                value=settings.local_city,
                placeholder="Рыбинск",
            )
            with st.expander("Экономика практики"):
                local_session_price_rub = st.number_input(
                    "Цена занятия, ₽",
                    min_value=0,
                    value=max(0, settings.local_session_price_rub),
                    step=100,
                )
                local_diagnostic_price_rub = st.number_input(
                    "Цена диагностики, ₽",
                    min_value=0,
                    value=max(0, settings.local_diagnostic_price_rub),
                    step=100,
                )
                local_course_sessions = st.number_input(
                    "Занятий в курсе",
                    min_value=1,
                    value=max(1, settings.local_course_sessions),
                    step=1,
                )
                local_room_cost_per_visit_rub = st.number_input(
                    "Кабинет на визит, ₽",
                    min_value=0,
                    value=max(0, settings.local_room_cost_per_visit_rub),
                    step=100,
                )
                local_ad_test_budget_rub = st.number_input(
                    "Тест рекламы в месяц, ₽",
                    min_value=0,
                    value=max(0, settings.local_ad_test_budget_rub),
                    step=1000,
                )
        else:
            local_service = settings.local_service
            local_audience = settings.local_audience
            local_city = settings.local_city
            local_session_price_rub = settings.local_session_price_rub
            local_diagnostic_price_rub = settings.local_diagnostic_price_rub
            local_course_sessions = settings.local_course_sessions
            local_room_cost_per_visit_rub = settings.local_room_cost_per_visit_rub
            local_ad_test_budget_rub = settings.local_ad_test_budget_rub

        st.header("Параметры пачки")
        known_local_region = (
            _known_local_region_label(local_city)
            if analysis_mode == "Локальная практика"
            else None
        )
        region_options = [known_local_region] if known_local_region else list(REGION_OPTIONS.keys())
        region_label = st.selectbox(
            "Регион",
            region_options,
            index=_option_index(region_options, settings.region_label),
            disabled=bool(known_local_region),
        )
        custom_region_id = st.text_input(
            "ID региона Яндекса, если нужен другой",
            value="" if known_local_region else settings.custom_region_id,
            disabled=bool(known_local_region),
        )
        if known_local_region:
            st.caption(
                f"Регион определен по городу автоматически: {known_local_region}, "
                f"ID {REGION_OPTIONS[known_local_region][0]}."
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
        project_options = _project_type_options(analysis_mode)
        project_label = st.selectbox(
            "Тип проекта",
            project_options,
            index=_option_index(project_options, settings.project_label),
            disabled=analysis_mode == "Локальная практика",
        )
        if analysis_mode == "Локальная практика":
            st.caption("Для частной практики тип фиксирован: сервис/услуга.")
        num_phrases = st.slider(
            "Фраз Wordstat на направление",
            10,
            200,
            _snap_to_step(settings.num_phrases, minimum=10, maximum=200, step=10),
            10,
        )
        st.header("SERP-анализ")
        enable_serp = st.checkbox(
            "Проверять выдачу финалистов",
            value=settings.enable_serp,
        )
        serp_finalists = st.slider(
            "Финалистов для SERP",
            1,
            30,
            _clamp(settings.serp_finalists, 1, 30),
        )
        serp_results = st.slider(
            "Результатов выдачи на нишу",
            5,
            30,
            _snap_to_step(settings.serp_results, minimum=5, maximum=30, step=5),
            5,
        )
        enable_cluster_serp = st.checkbox(
            "Проверять коммерческие кластеры",
            value=settings.enable_cluster_serp,
        )
        keyword_clusters = st.slider(
            "Кластеров на нишу",
            1,
            8,
            _clamp(settings.keyword_clusters, 1, 8),
        )
        st.header("AI-вердикт")
        enable_ai_project_type = st.checkbox(
            "Уточнять авто-тип проекта через AI",
            value=False if analysis_mode == "Локальная практика" else settings.enable_ai_project_type,
            disabled=analysis_mode == "Локальная практика",
        )
        enable_ai = st.checkbox(
            "Генерировать AI-вердикт финалистов",
            value=settings.enable_ai,
        )
        ai_provider = st.selectbox(
            "AI-провайдер",
            AI_PROVIDERS,
            index=_option_index(AI_PROVIDERS, settings.ai_provider),
        )
        if ai_provider == "OpenRouter":
            openrouter_api_key = st.text_input(
                "OpenRouter API key",
                value=settings.openrouter_api_key,
                type="password",
            )
            openrouter_model = st.text_input(
                "OpenRouter модель",
                value=settings.openrouter_model,
            )
            openai_api_key = settings.openai_api_key
            deepseek_api_key = settings.deepseek_api_key
            openai_model = settings.openai_model
            deepseek_model = settings.deepseek_model
        elif ai_provider == "GPT":
            openai_api_key = st.text_input(
                "OpenAI API key",
                value=settings.openai_api_key,
                type="password",
            )
            deepseek_api_key = settings.deepseek_api_key
            openrouter_api_key = settings.openrouter_api_key
            openai_model = st.text_input("GPT модель", value=settings.openai_model)
            deepseek_model = settings.deepseek_model
            openrouter_model = settings.openrouter_model
        else:
            deepseek_api_key = st.text_input(
                "DeepSeek API key",
                value=settings.deepseek_api_key,
                type="password",
            )
            openai_api_key = settings.openai_api_key
            openrouter_api_key = settings.openrouter_api_key
            deepseek_model = st.text_input("DeepSeek модель", value=settings.deepseek_model)
            openai_model = settings.openai_model
            openrouter_model = settings.openrouter_model
        ai_finalists = st.slider(
            "Финалистов для AI",
            1,
            20,
            _clamp(settings.ai_finalists, 1, 20),
        )

    pasted_label = (
        "Дополнительные запросы родителей, по одному на строку"
        if analysis_mode == "Локальная практика"
        else "Список направлений, по одному на строку"
    )
    pasted_placeholder = (
        "страх школы у ребенка\nребенок быстро устает на уроках"
        if analysis_mode == "Локальная практика"
        else "ремонт роботов пылесосов\nкурсы нейросетей\nзапчасти для квадроциклов"
    )
    pasted = st.text_area(
        pasted_label,
        value=settings.pasted_directions,
        height=220,
        placeholder=pasted_placeholder,
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
        enable_serp=enable_serp,
        serp_finalists=int(serp_finalists),
        serp_results=int(serp_results),
        enable_cluster_serp=enable_cluster_serp,
        keyword_clusters=int(keyword_clusters),
        enable_ai_project_type=enable_ai_project_type,
        enable_ai=enable_ai,
        ai_provider=ai_provider,
        openai_api_key=openai_api_key,
        deepseek_api_key=deepseek_api_key,
        openrouter_api_key=openrouter_api_key,
        openai_model=openai_model,
        deepseek_model=deepseek_model,
        openrouter_model=openrouter_model,
        ai_finalists=int(ai_finalists),
        analysis_mode=analysis_mode,
        local_service=local_service,
        local_audience=local_audience,
        local_city=local_city,
        local_session_price_rub=int(local_session_price_rub),
        local_diagnostic_price_rub=int(local_diagnostic_price_rub),
        local_course_sessions=int(local_course_sessions),
        local_room_cost_per_visit_rub=int(local_room_cost_per_visit_rub),
        local_ad_test_budget_rub=int(local_ad_test_budget_rub),
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
        practice_profile = None
        practice_economics = None
        direction_text = pasted
        direction_region = region_label
        selected_project_type = PROJECT_TYPES[project_label]
        if analysis_mode == "Локальная практика":
            practice_profile = LocalPracticeProfile(
                service=local_service,
                audience=local_audience,
                city=local_city,
                session_price_rub=int(local_session_price_rub),
                diagnostic_price_rub=int(local_diagnostic_price_rub),
                course_sessions=int(local_course_sessions),
                room_cost_per_visit_rub=int(local_room_cost_per_visit_rub),
                ad_test_budget_rub=int(local_ad_test_budget_rub),
            )
            practice_economics = calculate_practice_economics(practice_profile)
            queries = build_local_practice_queries(
                practice_profile,
                extra_queries=pasted.splitlines(),
            )
            direction_text = "\n".join(queries)
            direction_region = local_city
            selected_project_type = "service"
            st.info(f"Автоматически сформировано запросов для проверки: {len(queries)}")

        directions = parse_pasted_directions(
            direction_text,
            region=direction_region,
            budget_rub=int(budget_rub),
            max_difficulty=int(max_difficulty),
            project_type=selected_project_type,
        )
        region_context = _resolve_region_context(
            analysis_mode=analysis_mode,
            local_city=local_city,
            region_label=region_label,
            custom_region_id=custom_region_id,
        )
        data_source = _practice_data_source_label(provider_name)
        if practice_profile:
            st.info(
                f"Источник: {data_source}. Эффективный регион: {region_context.label}."
            )
        assessments = _run_analysis(
            provider_name=provider_name,
            api_key=api_key,
            folder_id=folder_id,
            region_ids=list(region_context.region_ids),
            num_phrases=num_phrases,
            enable_serp=enable_serp,
            serp_region_id=region_context.serp_region_id,
            serp_finalists=int(serp_finalists),
            serp_results=int(serp_results),
            enable_cluster_serp=enable_cluster_serp,
            keyword_clusters=int(keyword_clusters),
            enable_ai_project_type=enable_ai_project_type and practice_profile is None,
            enable_ai=enable_ai and practice_profile is None,
            ai_provider=ai_provider,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key,
            openrouter_api_key=openrouter_api_key,
            openai_model=openai_model,
            deepseek_model=deepseek_model,
            openrouter_model=openrouter_model,
            ai_finalists=int(ai_finalists),
            directions=directions,
            estimated_launch_budget_override=(
                practice_economics.minimum_test_reserve_rub
                if practice_economics is not None
                else None
            ),
        )
        practice_report = None
        if practice_profile:
            economics = practice_economics
            assert economics is not None
            ai_report = None
            if enable_ai:
                ai_report, ai_error = _generate_practice_ai_report_safely(
                    practice_profile,
                    economics,
                    assessments,
                    provider=ai_provider,
                    openai_api_key=openai_api_key,
                    deepseek_api_key=deepseek_api_key,
                    openrouter_api_key=openrouter_api_key,
                    openai_model=openai_model,
                    deepseek_model=deepseek_model,
                    openrouter_model=openrouter_model,
                    data_source=data_source,
                    effective_region=region_context.label,
                )
                if ai_error:
                    st.warning(
                        "AI-синтез не сработал; Wordstat, SERP и экономика сохранены в отчете. "
                        f"Причина: {ai_error}"
                    )
            practice_report = render_local_practice_report(
                practice_profile,
                economics,
                assessments,
                ai_report=ai_report,
                data_source=data_source,
                effective_region=region_context.label,
            )
    except (ValueError, YandexWordstatError, YandexSerpError, AiError) as exc:
        st.error(str(exc))
        return

    _render_results(
        assessments,
        summary_report=practice_report,
        summary_only=practice_profile is not None,
    )


def _run_analysis(
    *,
    provider_name: str,
    api_key: str,
    folder_id: str,
    region_ids: list[str],
    num_phrases: int,
    enable_serp: bool,
    serp_region_id: str,
    serp_finalists: int,
    serp_results: int,
    enable_cluster_serp: bool,
    keyword_clusters: int,
    enable_ai_project_type: bool,
    enable_ai: bool,
    ai_provider: str,
    openai_api_key: str,
    deepseek_api_key: str,
    openrouter_api_key: str,
    openai_model: str,
    deepseek_model: str,
    openrouter_model: str,
    ai_finalists: int,
    directions,
    estimated_launch_budget_override: int | None = None,
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
    raw_items = []
    for index, direction in enumerate(directions, start=1):
        metrics = provider.metrics_for(direction)
        metrics = _override_estimated_launch_budget(
            metrics,
            estimated_launch_budget_override,
        )
        raw_items.append((direction, metrics))
        progress.progress(index / len(directions))
    ai_project_type_choices = {}
    if enable_ai_project_type and any(
        direction.project_type == AUTO_PROJECT_TYPE for direction, _metrics in raw_items
    ):
        try:
            ai_client = _build_ai_client(
                provider=ai_provider,
                openai_api_key=openai_api_key,
                deepseek_api_key=deepseek_api_key,
                openrouter_api_key=openrouter_api_key,
                openai_model=openai_model,
                deepseek_model=deepseek_model,
                openrouter_model=openrouter_model,
            )
            ai_project_type_choices = generate_project_type_choices(raw_items, ai_client)
        except (AiError, ValueError, TypeError) as exc:
            st.warning(f"AI-выбор типа проекта не сработал, использован локальный выбор: {exc}")

    assessments = _score_raw_items(raw_items, ai_project_type_choices)
    ranked = sorted(assessments, key=lambda item: item.score, reverse=True)

    if enable_serp:
        ranked = _apply_serp_to_finalists(
            ranked,
            provider_name=provider_name,
            api_key=api_key,
            folder_id=folder_id,
            region_id=serp_region_id,
            finalists=serp_finalists,
            results_limit=serp_results,
            market_provider=provider,
            enable_cluster_serp=enable_cluster_serp,
            keyword_clusters=keyword_clusters,
        )

    ranked = [apply_product_recommendation(assessment) for assessment in ranked]

    if enable_ai:
        ranked = _apply_ai_to_finalists(
            ranked,
            provider=ai_provider,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key,
            openrouter_api_key=openrouter_api_key,
            openai_model=openai_model,
            deepseek_model=deepseek_model,
            openrouter_model=openrouter_model,
            finalists=ai_finalists,
        )

    return ranked


def _score_raw_items(raw_items, ai_project_type_choices) -> list[NicheAssessment]:
    assessments: list[NicheAssessment] = []
    for index, (direction, metrics) in enumerate(raw_items):
        choice = ai_project_type_choices.get(index)
        if choice:
            decision = resolve_project_type_choice(
                direction,
                metrics,
                project_type=choice.project_type,
                source=AI_PROJECT_TYPE_SOURCE,
                rationale=choice.rationale,
                confidence=choice.confidence,
            )
            assessments.append(score_project_type_decision(decision))
            continue
        assessments.append(score_direction(direction, metrics))
    return assessments


def _apply_serp_to_finalists(
    assessments: list[NicheAssessment],
    *,
    provider_name: str,
    api_key: str,
    folder_id: str,
    region_id: str,
    finalists: int,
    results_limit: int,
    market_provider,
    enable_cluster_serp: bool,
    keyword_clusters: int,
) -> list[NicheAssessment]:
    serp_provider = _build_serp_provider(
        provider_name=provider_name,
        api_key=api_key,
        folder_id=folder_id,
        region_id=region_id,
        results_limit=results_limit,
    )
    finalist_count = min(max(1, finalists), len(assessments))
    serp_progress = st.progress(0)
    adjusted = list(assessments)
    for index, assessment in enumerate(assessments[:finalist_count], start=1):
        analysis = serp_provider.analysis_for(assessment.direction)
        adjusted_assessment = apply_serp_analysis(assessment, analysis)
        if enable_cluster_serp:
            clusters = market_provider.keyword_clusters_for(
                assessment.direction,
                max_clusters=keyword_clusters,
            )
            checked_clusters = [
                attach_cluster_serp(
                    cluster,
                    serp_provider.analysis_for(
                        _cluster_direction(assessment, cluster.representative_query)
                    ),
                )
                for cluster in clusters
            ]
            adjusted_assessment = apply_keyword_cluster_serp_analysis(
                adjusted_assessment,
                checked_clusters,
            )
        adjusted[index - 1] = adjusted_assessment
        serp_progress.progress(index / finalist_count)

    return sorted(adjusted, key=lambda item: item.score, reverse=True)


def _cluster_direction(assessment: NicheAssessment, query: str):
    direction = assessment.direction
    return type(direction)(
        direction=query,
        region=direction.region,
        budget_rub=direction.budget_rub,
        max_difficulty=direction.max_difficulty,
        project_type=direction.project_type,
    )


def _apply_ai_to_finalists(
    assessments: list[NicheAssessment],
    *,
    provider: str,
    openai_api_key: str,
    deepseek_api_key: str,
    openrouter_api_key: str,
    openai_model: str,
    deepseek_model: str,
    openrouter_model: str,
    finalists: int,
) -> list[NicheAssessment]:
    client = _build_ai_client(
        provider=provider,
        openai_api_key=openai_api_key,
        deepseek_api_key=deepseek_api_key,
        openrouter_api_key=openrouter_api_key,
        openai_model=openai_model,
        deepseek_model=deepseek_model,
        openrouter_model=openrouter_model,
    )
    finalist_count = min(max(1, finalists), len(assessments))
    ai_progress = st.progress(0)
    adjusted = list(assessments)
    for index, assessment in enumerate(assessments[:finalist_count], start=1):
        insight = generate_ai_insight(assessment, client)
        adjusted[index - 1] = apply_ai_insight(assessment, insight)
        ai_progress.progress(index / finalist_count)

    return adjusted


def _build_ai_client(
    *,
    provider: str,
    openai_api_key: str,
    deepseek_api_key: str,
    openrouter_api_key: str,
    openai_model: str,
    deepseek_model: str,
    openrouter_model: str,
):
    if provider == "GPT":
        return OpenAiClient(api_key=openai_api_key, model=openai_model)
    if provider == "DeepSeek":
        return DeepSeekClient(api_key=deepseek_api_key, model=deepseek_model)
    if provider == "OpenRouter":
        return OpenRouterClient(api_key=openrouter_api_key, model=openrouter_model)
    raise ValueError(f"Неподдерживаемый AI-провайдер: {provider}")


def _generate_practice_ai_report_safely(
    profile,
    economics,
    assessments,
    *,
    provider: str,
    openai_api_key: str,
    deepseek_api_key: str,
    openrouter_api_key: str,
    openai_model: str,
    deepseek_model: str,
    openrouter_model: str,
    data_source: str,
    effective_region: str,
) -> tuple[str | None, str | None]:
    try:
        client = _build_ai_client(
            provider=provider,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key,
            openrouter_api_key=openrouter_api_key,
            openai_model=openai_model,
            deepseek_model=deepseek_model,
            openrouter_model=openrouter_model,
        )
        report = generate_local_practice_ai_report(
            profile,
            economics,
            assessments,
            client,
            data_source=data_source,
            effective_region=effective_region,
        )
        return report, None
    except (AiError, OSError, ValueError, TypeError, RuntimeError) as exc:
        return None, str(exc)


def _build_serp_provider(
    *,
    provider_name: str,
    api_key: str,
    folder_id: str,
    region_id: str,
    results_limit: int,
):
    if provider_name == "Demo":
        return DemoSerpProvider(results_limit=results_limit)

    client = YandexSerpClient(api_key=api_key, folder_id=folder_id)
    return YandexSerpProvider(
        client=client,
        region_id=region_id,
        results_limit=results_limit,
    )


def _save_user_settings(settings: AppSettings, *, show_success: bool) -> None:
    try:
        settings_path = save_settings(settings)
    except OSError as exc:
        st.warning(f"Не удалось сохранить параметры: {exc}")
        return

    if show_success:
        st.success(f"Параметры сохранены: {settings_path}")


def _render_results(
    assessments: list[NicheAssessment],
    *,
    summary_report: str | None = None,
    summary_only: bool = False,
) -> None:
    st.subheader("Результат")
    if summary_report:
        st.markdown(summary_report)
    rows = [_assessment_row(item) for item in assessments]
    if not summary_only:
        st.dataframe(rows, width="stretch", hide_index=True)

    csv_text = _rows_to_csv(rows)
    details_report = "" if summary_only else render_markdown_report(assessments)
    report, visible_details = _compose_reports(
        details_report,
        summary_report,
        summary_only=summary_only,
    )

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

    if visible_details:
        st.markdown(visible_details)


def _compose_reports(
    details_report: str,
    summary_report: str | None,
    *,
    summary_only: bool = False,
) -> tuple[str, str]:
    if not summary_report:
        return details_report, details_report
    if summary_only:
        return summary_report, ""
    combined = f"{summary_report.rstrip()}\n\n---\n\n{details_report}"
    return combined, details_report


def _assessment_row(assessment: NicheAssessment) -> dict[str, object]:
    serp = getattr(assessment, "serp_analysis", None)
    recommendation = getattr(assessment, "product_recommendation", None)
    score_breakdown = getattr(assessment, "score_breakdown", None)
    evidence_items = getattr(assessment, "evidence_items", [])
    return {
        "direction": assessment.direction.direction,
        "project_type": project_type_label(assessment.direction.project_type),
        "score": assessment.score,
        "verdict": assessment.verdict,
        "score_confidence": score_breakdown.confidence if score_breakdown else None,
        "evidence_count": len(evidence_items),
        "opportunity_score": recommendation.opportunity_score if recommendation else None,
        "launch": recommendation.product_title if recommendation else "",
        "first_test": recommendation.first_test if recommendation else "",
        "demand": assessment.metrics.demand,
        "trend": assessment.metrics.trend,
        "competition": assessment.metrics.competition,
        "budget_fit": assessment.metrics.estimated_launch_budget,
        "difficulty": assessment.metrics.estimated_difficulty,
        "serp_difficulty": serp.estimated_difficulty if serp else None,
        "serp_delta": serp.score_delta if serp else None,
        "offer_gap": getattr(serp, "offer_gap_score", None) if serp else None,
        "serp_weak_spots": _short_text("; ".join(getattr(serp, "weak_spots", [])) if serp else ""),
        "top_domains": ", ".join(serp.top_domains) if serp else "",
        "keyword_clusters": _cluster_summary(assessment),
        "ai_insight": _short_text(getattr(assessment, "ai_insight", None)),
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


def _selected_serp_region_id(region_label: str, custom_region_id: str) -> str:
    custom = custom_region_id.strip()
    if custom:
        return custom
    region_ids = REGION_OPTIONS[region_label]
    if region_ids:
        return region_ids[0]
    return DEFAULT_SERP_REGION_ID


def _project_type_options(analysis_mode: str) -> list[str]:
    if analysis_mode == "Локальная практика":
        return ["Сервис/услуга"]
    return list(PROJECT_TYPES.keys())


def _known_local_region_label(city: str) -> str | None:
    normalized_city = city.strip().casefold()
    for label, region_ids in REGION_OPTIONS.items():
        if region_ids and label.casefold() == normalized_city:
            return label
    return None


def _resolve_region_context(
    *,
    analysis_mode: str,
    local_city: str,
    region_label: str,
    custom_region_id: str,
) -> RegionContext:
    custom = custom_region_id.strip()
    if custom and not custom.isdigit():
        raise ValueError("ID региона Яндекса должен состоять из цифр")

    if analysis_mode == "Локальная практика":
        known_label = _known_local_region_label(local_city)
        if known_label:
            region_id = REGION_OPTIONS[known_label][0]
            return RegionContext(
                region_ids=(region_id,),
                serp_region_id=region_id,
                label=f"{known_label} (Yandex ID {region_id})",
            )
        if not custom:
            raise ValueError(
                f"Для города «{local_city.strip()}» укажите ID региона Яндекса, "
                "чтобы Wordstat и SERP не анализировали другой регион"
            )
        return RegionContext(
            region_ids=(custom,),
            serp_region_id=custom,
            label=f"{local_city.strip()} (Yandex ID {custom})",
        )

    region_ids = tuple(_selected_region_ids(region_label, custom))
    serp_region_id = _selected_serp_region_id(region_label, custom)
    if custom:
        label = f"{region_label} (Yandex ID {custom})"
    elif region_ids:
        label = f"{region_label} (Yandex ID {region_ids[0]})"
    else:
        label = f"{region_label} (без фильтра Wordstat; SERP ID {serp_region_id})"
    return RegionContext(region_ids=region_ids, serp_region_id=serp_region_id, label=label)


def _practice_data_source_label(provider_name: str) -> str:
    if provider_name == "Demo":
        return "Demo (синтетические данные; не Wordstat и не реальная выдача)"
    return "Yandex Wordstat API + Yandex Web Search"


def _override_estimated_launch_budget(
    metrics: MarketMetrics,
    estimated_launch_budget: int | None,
) -> MarketMetrics:
    if estimated_launch_budget is None:
        return metrics
    return replace(
        metrics,
        estimated_launch_budget=max(0, int(estimated_launch_budget)),
    )


def _short_text(value: str | None, *, limit: int = 180) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _cluster_summary(assessment: NicheAssessment) -> str:
    parts: list[str] = []
    for cluster in getattr(assessment, "keyword_clusters", []):
        serp = getattr(cluster, "serp_analysis", None)
        if serp:
            parts.append(f"{cluster.name}: {serp.estimated_difficulty}/10, gap {getattr(serp, 'offer_gap_score', 0.0):.2f}")
        else:
            parts.append(cluster.name)
    return "; ".join(parts)


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
