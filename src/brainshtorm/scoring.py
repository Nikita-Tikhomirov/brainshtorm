from brainshtorm.models import DirectionInput, MarketMetrics, NicheAssessment, REVIEW, SKIP, TAKE


def score_direction(direction: DirectionInput, metrics: MarketMetrics) -> NicheAssessment:
    demand_score = _clamp(metrics.demand / 10000 * 100)
    trend_score = _clamp((metrics.trend + 0.2) / 0.5 * 100)
    commercial_score = _clamp(metrics.commercial_intent * 100)
    competition_score = _clamp((1 - metrics.competition) * 100)
    budget_fit_score = _clamp(direction.budget_rub / metrics.estimated_launch_budget * 100)
    difficulty_fit_score = (
        100.0
        if metrics.estimated_difficulty <= direction.max_difficulty
        else _clamp(direction.max_difficulty / metrics.estimated_difficulty * 100)
    )
    regional_score = _clamp(metrics.regional_affinity / 1.25 * 100)
    risk_penalty = metrics.risk_level * 20 + metrics.seasonality * 5

    score = (
        demand_score * 0.25
        + trend_score * 0.15
        + commercial_score * 0.15
        + competition_score * 0.15
        + budget_fit_score * 0.15
        + difficulty_fit_score * 0.10
        + regional_score * 0.05
        - risk_penalty
    )
    score = round(_clamp(score), 1)
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
            "Есть признаки спроса, но нужны ручная проверка выдачи, "
            "офферов конкурентов и тест экономики заявки."
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


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))
