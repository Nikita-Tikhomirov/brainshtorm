from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Protocol

from brainshtorm.models import NicheAssessment


@dataclass(frozen=True)
class LocalPracticeProfile:
    service: str
    audience: str
    city: str
    session_price_rub: int = 1500
    diagnostic_price_rub: int = 3000
    course_sessions: int = 8
    room_cost_per_visit_rub: int = 500
    ad_test_budget_rub: int = 15000
    tax_rate: float = 0.04


@dataclass(frozen=True)
class PracticeScenario:
    name: str
    new_clients: int
    monthly_visits: int
    monthly_revenue_rub: int
    room_cost_rub: int
    tax_rub: int
    ad_cost_rub: int
    operating_result_rub: int
    realized_cac_rub: int


@dataclass(frozen=True)
class PracticeEconomics:
    revenue_per_client_rub: int
    contribution_before_marketing_rub: int
    break_even_clients_for_ad_test: int | None
    recommended_cac_cap_rub: int
    minimum_test_reserve_rub: int
    scenarios: list[PracticeScenario]


class PracticeAiClient(Protocol):
    def generate(self, prompt: str, *, max_output_tokens: int = 900) -> str:
        """Generate one evidence-bound practice report."""


NEUROPSYCHOLOGY_PROBLEM_QUERIES = (
    "детский психолог",
    "нейропсихологическая диагностика",
    "нейропсихологическая коррекция",
    "занятия с нейропсихологом",
    "подготовка к школе",
    "готовность к школе",
    "коррекция дисграфии",
    "коррекция дислексии",
    "ребенок плохо читает",
    "ребенок плохо учится",
    "трудности в обучении ребенка",
    "развитие внимания у детей",
    "развитие памяти у детей",
    "дефицит внимания у ребенка",
    "гиперактивный ребенок",
    "СДВГ у ребенка",
    "школьная неуспеваемость",
    "ребенок неусидчивый",
    "ребенок не готов к школе",
)


GENERIC_LOCAL_SERVICE_QUERIES = (
    "{service} записаться {city}",
    "{service} консультация {city}",
    "{service} первичная консультация {city}",
    "{service} услуги {city}",
    "{service} специалист {city}",
    "частный {service} {city}",
    "хороший {service} {city}",
    "лучший {service} {city}",
    "{service} рядом",
    "{service} онлайн",
    "{service} на дому {city}",
    "как выбрать {service}",
    "когда нужен {service}",
    "что делает {service}",
    "{service} для {audience} {city}",
)


def build_local_practice_queries(
    profile: LocalPracticeProfile,
    *,
    extra_queries: Iterable[str] = (),
    limit: int = 50,
) -> list[str]:
    service = _required_text(profile.service, "Услуга")
    city = _required_text(profile.city, "Город")
    candidates = [
        f"{service} {city}",
        service,
        f"{service} цена {city}",
        f"{service} стоимость {city}",
        f"{service} отзывы {city}",
        f"{service} консультация {city}",
        f"{service} диагностика {city}",
        f"занятия с нейропсихологом {city}"
        if "нейропсихолог" in service.casefold()
        else f"занятия с {service} {city}",
    ]
    audience = _audience_query_fragment(profile.audience)
    candidates.extend(
        template.format(service=service, city=city, audience=audience)
        for template in GENERIC_LOCAL_SERVICE_QUERIES
    )
    if "нейропсихолог" in service.casefold():
        for query in NEUROPSYCHOLOGY_PROBLEM_QUERIES:
            candidates.append(f"{query} {city}" if query in {"детский психолог", "подготовка к школе"} else query)

    candidates.extend(extra_queries)
    return _unique_queries(candidates, limit=max(20, min(50, int(limit))))


def calculate_practice_economics(profile: LocalPracticeProfile) -> PracticeEconomics:
    _validate_profile(profile)
    visits_per_client = profile.course_sessions + 1
    revenue_per_client = (
        profile.diagnostic_price_rub
        + profile.course_sessions * profile.session_price_rub
    )
    room_cost_per_client = visits_per_client * profile.room_cost_per_visit_rub
    minimum_test_reserve = profile.ad_test_budget_rub + room_cost_per_client
    tax_per_client = round(revenue_per_client * profile.tax_rate)
    contribution = revenue_per_client - room_cost_per_client - tax_per_client
    break_even_clients = (
        math.ceil(profile.ad_test_budget_rub / contribution)
        if contribution > 0
        else None
    )
    recommended_cac_cap = round(max(0, contribution) * 0.35)

    scenarios = [
        _scenario(profile, "Осторожный тест", 3),
        _scenario(profile, "Рабочая база", 6),
        _scenario(profile, "Целевая загрузка", 10),
    ]
    return PracticeEconomics(
        revenue_per_client_rub=revenue_per_client,
        contribution_before_marketing_rub=contribution,
        break_even_clients_for_ad_test=break_even_clients,
        recommended_cac_cap_rub=recommended_cac_cap,
        minimum_test_reserve_rub=minimum_test_reserve,
        scenarios=scenarios,
    )


def render_practice_economics(
    profile: LocalPracticeProfile,
    economics: PracticeEconomics,
) -> str:
    lines = [
        "## Экономика локальной практики",
        "",
        "Это расчетные допущения, а не прогноз спроса. Сайт и работа разработчика в бюджет не включены.",
        "",
        f"- Услуга: {profile.service}, {profile.city}",
        f"- Диагностика: {_rub(profile.diagnostic_price_rub)} ₽",
        f"- Занятие: {_rub(profile.session_price_rub)} ₽",
        f"- Курс: {profile.course_sessions} занятий",
        f"- Почасовой кабинет на один визит: {_rub(profile.room_cost_per_visit_rub)} ₽",
        f"- Тест рекламы: {_rub(profile.ad_test_budget_rub)} ₽/мес.",
        "- Минимальный резерв теста: "
        f"{_rub(economics.minimum_test_reserve_rub)} ₽ "
        "(реклама и кабинет для одного полного клиента)",
        f"- Налог в модели: {profile.tax_rate:.0%}",
        f"- Выручка с клиента за диагностику и курс: {_rub(economics.revenue_per_client_rub)} ₽",
        f"- Вклад до маркетинга: {_rub(economics.contribution_before_marketing_rub)} ₽",
        f"- Рекомендуемый предел CAC для теста: {_rub(economics.recommended_cac_cap_rub)} ₽",
        "- Окупаемость рекламного теста: "
        + (
            f"минимум {economics.break_even_clients_for_ad_test} клиентов"
            if economics.break_even_clients_for_ad_test is not None
            else "невозможна при текущих вводных"
        ),
        "",
        "| Сценарий | Новых клиентов | Визитов | Выручка | Кабинет | Налог | Реклама | Результат до личной зарплаты | CAC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario in economics.scenarios:
        lines.append(
            f"| {scenario.name} | {scenario.new_clients} | {scenario.monthly_visits} | "
            f"{_rub(scenario.monthly_revenue_rub)} ₽ | {_rub(scenario.room_cost_rub)} ₽ | "
            f"{_rub(scenario.tax_rub)} ₽ | {_rub(scenario.ad_cost_rub)} ₽ | "
            f"{_rub(scenario.operating_result_rub)} ₽ | {_rub(scenario.realized_cac_rub)} ₽ |"
        )
    return "\n".join(lines) + "\n"


def build_local_practice_ai_prompt(
    profile: LocalPracticeProfile,
    economics: PracticeEconomics,
    assessments: list[NicheAssessment],
    *,
    data_source: str = "не указан",
    effective_region: str | None = None,
) -> str:
    query_lines: list[str] = []
    for assessment in _rank_assessments(assessments):
        metrics = assessment.metrics
        serp = assessment.serp_analysis
        query_line = (
            f"- {assessment.direction.direction} | demand={metrics.demand} | "
            f"trend={metrics.trend} | commercial_intent={metrics.commercial_intent} | "
            f"calculated_score={assessment.score}"
        )
        if serp:
            query_line += (
                f" | serp_difficulty={serp.estimated_difficulty}/10 | "
                f"offer_gap={serp.offer_gap_score} | "
                f"top_domains={','.join(serp.top_domains) or 'n/a'} | "
                f"weak_spots={'; '.join(serp.weak_spots) or 'n/a'}"
            )
        else:
            query_line += " | SERP=not_checked"
        query_lines.append(query_line)

    scenario_lines = [
        "- "
        f"{item.name}: clients={item.new_clients}; visits={item.monthly_visits}; "
        f"revenue={item.monthly_revenue_rub}; result_before_owner_salary={item.operating_result_rub}; "
        f"realized_CAC={item.realized_cac_rub}"
        for item in economics.scenarios
    ]
    return "\n".join(
        [
            "Подготовь итоговое бизнес-решение по запуску локальной частной практики.",
            "Используй только факты из блока evidence и явно помеченные расчетные допущения.",
            "Не придумывай спрос, конкурентов, квалификацию, юридические факты, конверсии или прибыль.",
            "Не суммируй частотности запросов: они пересекаются и не равны числу клиентов.",
            "Если данных недостаточно, напиши это и снизь уверенность.",
            "Отделяй наблюдаемые данные от расчетных формул и от гипотез для теста.",
            "Ответь по-русски в структуре:",
            "1. Вердикт: GO / CONDITIONAL GO / NO-GO, уверенность 0-100% и одна главная причина.",
            "2. Что подтверждено данными: спрос, SERP и конкуренция.",
            "3. Какой продукт запускать: аудитория, конкретная проблема, формат и оффер без медицинских обещаний.",
            "4. Каналы: партнерства, Карты/Услуги, Директ, SEO; расставь приоритеты.",
            "5. Экономика: CAC, точка окупаемости и ограничения расчетной модели.",
            "6. План теста на 30 дней с измеримыми KPI и stop-критериями.",
            "7. Риски и данные, которых пока нет.",
            "",
            "profile:",
            f"service={profile.service}",
            f"audience={profile.audience or 'не задана'}",
            f"city={profile.city}",
            f"data_source={data_source}",
            f"effective_region={effective_region or profile.city}",
            "",
            "calculation_assumptions:",
            f"session_price={profile.session_price_rub}",
            f"diagnostic_price={profile.diagnostic_price_rub}",
            f"course_sessions={profile.course_sessions}",
            f"room_cost_per_visit={profile.room_cost_per_visit_rub}",
            f"ad_test_budget={profile.ad_test_budget_rub}",
            f"tax_rate={profile.tax_rate}",
            f"revenue_per_client={economics.revenue_per_client_rub}",
            f"contribution_before_marketing={economics.contribution_before_marketing_rub}",
            f"recommended_CAC_cap={economics.recommended_cac_cap_rub}",
            f"minimum_test_reserve={economics.minimum_test_reserve_rub}",
            "break_even_clients_for_ad_test="
            + (
                str(economics.break_even_clients_for_ad_test)
                if economics.break_even_clients_for_ad_test is not None
                else "not_possible"
            ),
            *scenario_lines,
            "",
            "evidence:",
            *(query_lines or ["- нет данных Wordstat/SERP"]),
        ]
    )


def generate_local_practice_ai_report(
    profile: LocalPracticeProfile,
    economics: PracticeEconomics,
    assessments: list[NicheAssessment],
    client: PracticeAiClient,
    *,
    data_source: str = "не указан",
    effective_region: str | None = None,
) -> str:
    return client.generate(
        build_local_practice_ai_prompt(
            profile,
            economics,
            assessments,
            data_source=data_source,
            effective_region=effective_region,
        ),
        max_output_tokens=6000,
    ).strip()


def render_local_practice_report(
    profile: LocalPracticeProfile,
    economics: PracticeEconomics,
    assessments: list[NicheAssessment],
    *,
    ai_report: str | None = None,
    data_source: str = "не указан",
    effective_region: str | None = None,
) -> str:
    lines = [
        f"# {profile.service.capitalize()} — {profile.city}",
        "",
        f"- Источник данных: {data_source}",
        f"- Эффективный регион: {effective_region or profile.city}",
        "",
        "## Итоговый вердикт",
        "",
        ai_report.strip() if ai_report and ai_report.strip() else "AI-вердикт не запускался. Ниже приведены сырые данные и расчетная экономика.",
        "",
        "## Проверенные запросы",
        "",
        "Частотности запросов нельзя складывать: формулировки пересекаются и не равны числу потенциальных клиентов.",
        "",
        "| Запрос | Частотность | Тренд | Score | SERP | Offer gap | Домены |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for assessment in _rank_assessments(assessments):
        serp = assessment.serp_analysis
        lines.append(
            f"| {assessment.direction.direction} | {assessment.metrics.demand} | "
            f"{assessment.metrics.trend:.2f} | {assessment.score:.1f} | "
            f"{f'{serp.estimated_difficulty}/10' if serp else 'не проверен'} | "
            f"{f'{serp.offer_gap_score:.2f}' if serp else 'n/a'} | "
            f"{', '.join(serp.top_domains) if serp and serp.top_domains else 'n/a'} |"
        )
    if not assessments:
        lines.append("| нет данных | 0 | 0 | 0 | не проверен | n/a | n/a |")
    lines.extend(["", render_practice_economics(profile, economics).rstrip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _scenario(
    profile: LocalPracticeProfile,
    name: str,
    new_clients: int,
) -> PracticeScenario:
    visits = new_clients * (profile.course_sessions + 1)
    revenue = new_clients * (
        profile.diagnostic_price_rub
        + profile.course_sessions * profile.session_price_rub
    )
    room_cost = visits * profile.room_cost_per_visit_rub
    tax = round(revenue * profile.tax_rate)
    operating_result = revenue - room_cost - tax - profile.ad_test_budget_rub
    return PracticeScenario(
        name=name,
        new_clients=new_clients,
        monthly_visits=visits,
        monthly_revenue_rub=revenue,
        room_cost_rub=room_cost,
        tax_rub=tax,
        ad_cost_rub=profile.ad_test_budget_rub,
        operating_result_rub=operating_result,
        realized_cac_rub=round(profile.ad_test_budget_rub / new_clients),
    )


def _rank_assessments(assessments: list[NicheAssessment]) -> list[NicheAssessment]:
    return sorted(
        assessments,
        key=lambda item: (item.metrics.demand, item.score),
        reverse=True,
    )


def _validate_profile(profile: LocalPracticeProfile) -> None:
    _required_text(profile.service, "Услуга")
    _required_text(profile.city, "Город")
    integer_values = (
        profile.session_price_rub,
        profile.diagnostic_price_rub,
        profile.course_sessions,
        profile.room_cost_per_visit_rub,
        profile.ad_test_budget_rub,
    )
    if any(value < 0 for value in integer_values) or profile.course_sessions < 1:
        raise ValueError("Параметры экономики должны быть неотрицательными, а курс — не короче одного занятия")
    if not 0 <= profile.tax_rate < 1:
        raise ValueError("Ставка налога должна быть от 0 до 1")


def _required_text(value: str, label: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError(f"{label}: заполните поле")
    return cleaned


def _audience_query_fragment(value: str) -> str:
    audience = " ".join(value.split()) or "клиентов"
    lowered = audience.casefold()
    if lowered.startswith("родители "):
        return audience[len("родители ") :]
    return audience


def _unique_queries(candidates: Iterable[str], *, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        query = " ".join(str(candidate).split())
        key = query.casefold()
        if not query or key in seen:
            continue
        seen.add(key)
        result.append(query)
        if len(result) >= limit:
            break
    return result


def _rub(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")
