from dataclasses import replace

from brainshtorm.models import (
    DirectionInput,
    EvidenceItem,
    MarketMetrics,
    NicheAssessment,
    REVIEW,
    SKIP,
    ScoreBreakdown,
    ScoreFactor,
    TAKE,
)


SCORE_FORMULA_VERSION = "score-v2-strict-evidence"


def score_direction(direction: DirectionInput, metrics: MarketMetrics) -> NicheAssessment:
    breakdown = build_score_breakdown(direction, metrics)
    score = breakdown.final_score
    verdict = _verdict_for(score)

    return NicheAssessment(
        direction=direction,
        metrics=metrics,
        score=score,
        verdict=verdict,
        explanation=_explain(verdict, direction, metrics),
        product_idea=_product_idea(direction),
        promotion_steps=_promotion_steps(direction),
        risks=_risks(direction, metrics),
        score_breakdown=breakdown,
        evidence_items=_metric_evidence(direction, metrics),
    )


def build_score_breakdown(direction: DirectionInput, metrics: MarketMetrics) -> ScoreBreakdown:
    demand_score = _clamp(metrics.demand / 10000 * 100)
    trend_score = _clamp((metrics.trend + 0.2) / 0.5 * 100)
    commercial_score = _clamp(metrics.commercial_intent * 100)
    competition_score = _clamp((1 - metrics.competition) * 100)
    budget_fit_score = _clamp(direction.budget_rub / max(1, metrics.estimated_launch_budget) * 100)
    difficulty_fit_score = (
        100.0
        if metrics.estimated_difficulty <= direction.max_difficulty
        else _clamp(direction.max_difficulty / max(1, metrics.estimated_difficulty) * 100)
    )
    regional_score = _clamp(metrics.regional_affinity / 1.25 * 100)
    factors = [
        _score_factor(
            key="demand",
            label="Спрос",
            raw_value=str(metrics.demand),
            normalized_score=demand_score,
            weight=0.25,
            evidence="Wordstat/GetTop demand, cap 10000.",
        ),
        _score_factor(
            key="trend",
            label="Динамика",
            raw_value=f"{metrics.trend:.2f}",
            normalized_score=trend_score,
            weight=0.15,
            evidence="Wordstat/GetDynamics trend normalized from -0.20 to +0.30.",
        ),
        _score_factor(
            key="commercial_intent",
            label="Коммерческий интент",
            raw_value=f"{metrics.commercial_intent:.2f}",
            normalized_score=commercial_score,
            weight=0.15,
            evidence="Доля коммерческих модификаторов в фразах.",
        ),
        _score_factor(
            key="competition_fit",
            label="Свободность конкуренции",
            raw_value=f"{metrics.competition:.2f}",
            normalized_score=competition_score,
            weight=0.15,
            evidence="1 - competition from provider metrics.",
        ),
        _score_factor(
            key="budget_fit",
            label="Вписывание в бюджет",
            raw_value=f"{direction.budget_rub}/{metrics.estimated_launch_budget}",
            normalized_score=budget_fit_score,
            weight=0.15,
            evidence="budget_rub / estimated_launch_budget, capped at 100.",
        ),
        _score_factor(
            key="difficulty_fit",
            label="Вписывание в сложность",
            raw_value=f"{direction.max_difficulty}/{metrics.estimated_difficulty}",
            normalized_score=difficulty_fit_score,
            weight=0.10,
            evidence="max_difficulty / estimated_difficulty, capped at 100.",
        ),
        _score_factor(
            key="regional_fit",
            label="Региональность",
            raw_value=f"{metrics.regional_affinity:.2f}",
            normalized_score=regional_score,
            weight=0.05,
            evidence="Regional affinity normalized by 1.25.",
        ),
        _penalty_factor(
            key="risk_penalty",
            label="Риск",
            raw_value=f"{metrics.risk_level:.2f}",
            penalty=metrics.risk_level * 20,
            evidence="risk_level * 20.",
        ),
        _penalty_factor(
            key="seasonality_penalty",
            label="Сезонность",
            raw_value=f"{metrics.seasonality:.2f}",
            penalty=metrics.seasonality * 5,
            evidence="seasonality * 5.",
        ),
    ]
    final_score = round(_clamp(sum(factor.contribution for factor in factors)), 1)
    return ScoreBreakdown(
        formula_version=SCORE_FORMULA_VERSION,
        factors=factors,
        final_score=final_score,
        confidence=0.55,
        confidence_notes=[
            "База рассчитана по Wordstat/метрикам без проверки SERP.",
            "SERP и коммерческие кластеры еще не подтверждены.",
        ],
    )


def ensure_score_breakdown(assessment: NicheAssessment) -> ScoreBreakdown:
    if assessment.score_breakdown:
        return assessment.score_breakdown
    breakdown = build_score_breakdown(assessment.direction, assessment.metrics)
    if breakdown.final_score == assessment.score:
        return breakdown
    return add_score_adjustment(
        breakdown,
        key="existing_score",
        label="Текущий score",
        raw_value=f"{assessment.score:.1f}",
        contribution=round(assessment.score - breakdown.final_score, 1),
        evidence="Existing assessment score before strict breakdown was attached.",
        final_score=assessment.score,
        confidence_delta=0.0,
        confidence_note="Score reconstructed from existing assessment.",
    )


def add_score_adjustment(
    breakdown: ScoreBreakdown,
    *,
    key: str,
    label: str,
    raw_value: str,
    contribution: float,
    evidence: str,
    final_score: float,
    confidence_delta: float,
    confidence_note: str,
) -> ScoreBreakdown:
    factor = ScoreFactor(
        key=key,
        label=label,
        raw_value=raw_value,
        normalized_score=0.0,
        weight=1.0,
        contribution=round(contribution, 1),
        evidence=evidence,
    )
    notes = list(breakdown.confidence_notes)
    if confidence_note and confidence_note not in notes:
        notes.append(confidence_note)
    return replace(
        breakdown,
        factors=[*breakdown.factors, factor],
        final_score=round(_clamp(final_score), 1),
        confidence=round(_clamp(breakdown.confidence + confidence_delta, 0.0, 1.0), 2),
        confidence_notes=notes,
    )


def _verdict_for(score: float) -> str:
    if score >= 75:
        return TAKE
    if score >= 50:
        return REVIEW
    return SKIP


def _explain(verdict: str, direction: DirectionInput, metrics: MarketMetrics) -> str:
    if verdict == TAKE:
        return (
            "Спрос и коммерческий интент выглядят достаточными, "
            "а сложность укладывается в заданные ограничения."
        )
    if verdict == REVIEW:
        return (
            "Есть признаки спроса, но нужны SERP-разбор, "
            "оценка офферов конкурентов и тест экономики заявки."
        )
    return (
        "Направление сейчас не проходит фильтр по бюджету, сложности, риску "
        f"или конкуренции для проекта типа {direction.project_type}."
    )


def _product_idea(direction: DirectionInput) -> str:
    ideas = {
        "seo_site": "SEO-сайт с кластером посадочных страниц и монетизацией через заявки.",
        "leadgen": "лидогенератор заявок с передачей лидов проверенным исполнителям.",
        "service": "Небольшой сервис или витрина услуги с записью и заявками.",
        "telegram": "Telegram-продукт с контентной воронкой и лид-магнитом.",
        "infoproduct": "Инфопродукт с бесплатным входным материалом и платной программой.",
        "marketplace": "Нишевой каталог поставщиков или исполнителей с заявками.",
    }
    return ideas.get(
        direction.project_type,
        "Контентный проект с проверкой спроса через SEO и платный трафик.",
    )


def _promotion_steps(direction: DirectionInput) -> list[str]:
    common = [
        "Собрать расширенную семантику и разделить ее на кластеры.",
        "Проверить топ Яндекса по 10-20 горячим запросам.",
    ]
    by_type = {
        "seo_site": ["Сделать первые SEO-страницы под коммерческие кластеры."],
        "leadgen": ["Запустить тестовые страницы и Яндекс Директ по горячим запросам."],
        "service": ["Собрать лендинг с формой заявки и проверить стоимость лида."],
        "telegram": ["Подготовить лид-магнит и посевы в тематических каналах."],
        "infoproduct": ["Сделать бесплатный материал и проверить заявки на предзапись."],
        "marketplace": ["Собрать 20-30 поставщиков и проверить спрос на подбор."],
    }
    return common + by_type.get(direction.project_type, ["Запустить короткий тест спроса."])


def _risks(direction: DirectionInput, metrics: MarketMetrics) -> list[str]:
    risks: list[str] = []
    if metrics.competition >= 0.7:
        risks.append("Высокая конкуренция в выдаче.")
    if metrics.estimated_launch_budget > direction.budget_rub:
        risks.append("Оценочный бюджет запуска выше заданного.")
    if metrics.estimated_difficulty > direction.max_difficulty:
        risks.append("Оценочная сложность выше допустимой.")
    if metrics.risk_level >= 0.5:
        risks.append("Повышенный риск YMYL, юридических или финансовых ограничений.")
    if metrics.seasonality >= 0.6:
        risks.append("Выраженная сезонность спроса.")
    if not risks:
        risks.append("Нужно подтвердить экономику на тестовых заявках.")
    return risks


def _metric_evidence(direction: DirectionInput, metrics: MarketMetrics) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            source="Wordstat",
            claim="Спрос",
            value=str(metrics.demand),
            details=[f"direction={direction.direction}", f"region={direction.region}"],
        ),
        EvidenceItem(
            source="Wordstat",
            claim="Динамика",
            value=f"{metrics.trend:.2f}",
            details=["GetDynamics normalized trend."],
        ),
        EvidenceItem(
            source="Wordstat",
            claim="Коммерческий интент",
            value=f"{metrics.commercial_intent:.2f}",
            details=["Commercial modifiers in collected phrases."],
        ),
        EvidenceItem(
            source="Provider metrics",
            claim="Конкуренция",
            value=f"{metrics.competition:.2f}",
            details=["Used as inverse competition_fit in score formula."],
        ),
        EvidenceItem(
            source="Provider metrics",
            claim="Бюджет",
            value=f"{metrics.estimated_launch_budget} ₽",
            details=[f"user_limit={direction.budget_rub} ₽"],
        ),
        EvidenceItem(
            source="Provider metrics",
            claim="Сложность",
            value=f"{metrics.estimated_difficulty}/10",
            details=[f"user_limit={direction.max_difficulty}/10"],
        ),
    ]


def _score_factor(
    *,
    key: str,
    label: str,
    raw_value: str,
    normalized_score: float,
    weight: float,
    evidence: str,
) -> ScoreFactor:
    return ScoreFactor(
        key=key,
        label=label,
        raw_value=raw_value,
        normalized_score=round(normalized_score, 1),
        weight=weight,
        contribution=round(normalized_score * weight, 4),
        evidence=evidence,
    )


def _penalty_factor(
    *,
    key: str,
    label: str,
    raw_value: str,
    penalty: float,
    evidence: str,
) -> ScoreFactor:
    return ScoreFactor(
        key=key,
        label=label,
        raw_value=raw_value,
        normalized_score=round(penalty, 1),
        weight=1.0,
        contribution=round(-penalty, 4),
        evidence=evidence,
    )


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))
