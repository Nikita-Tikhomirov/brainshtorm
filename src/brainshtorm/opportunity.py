from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from brainshtorm.models import KeywordCluster, NicheAssessment, ProductRecommendation, SerpAnalysis


LAUNCH_TYPES = {
    "seo_site": "SEO-сайт",
    "leadgen": "Лидогенератор услуги",
    "service": "Витрина услуги",
    "telegram": "Telegram-продукт",
    "infoproduct": "Инфопродукт",
    "marketplace": "Нишевой каталог",
}


def build_product_recommendation(assessment: NicheAssessment) -> ProductRecommendation:
    direction = assessment.direction
    launch_type = LAUNCH_TYPES.get(direction.project_type, "Нишевой проект")
    weak_clusters = _weak_clusters(assessment)
    page_clusters = weak_clusters or _best_clusters(assessment)
    opportunity_score = _opportunity_score(assessment, weak_clusters)

    return ProductRecommendation(
        product_title=f"{launch_type}: {direction.direction}",
        launch_type=launch_type,
        target_audience=_target_audience(assessment),
        opportunity_score=opportunity_score,
        offer=_offer_for(assessment, page_clusters),
        why_this_can_rank=_ranking_reason(assessment, weak_clusters),
        landing_pages=_landing_pages(assessment, page_clusters),
        traffic_plan=_traffic_plan(assessment, page_clusters),
        first_test=_first_test(assessment, page_clusters),
        evidence=_evidence(assessment, weak_clusters),
        risks=_recommendation_risks(assessment),
    )


def apply_product_recommendation(assessment: NicheAssessment) -> NicheAssessment:
    return replace(
        assessment,
        product_recommendation=build_product_recommendation(assessment),
    )


def _weak_clusters(assessment: NicheAssessment) -> list[KeywordCluster]:
    clusters = [
        cluster
        for cluster in assessment.keyword_clusters
        if cluster.serp_analysis and cluster.serp_analysis.estimated_difficulty <= assessment.direction.max_difficulty
    ]
    return sorted(
        clusters,
        key=lambda item: (
            item.serp_analysis.estimated_difficulty if item.serp_analysis else 10,
            -item.total_demand,
        ),
    )


def _best_clusters(assessment: NicheAssessment) -> list[KeywordCluster]:
    return sorted(
        assessment.keyword_clusters,
        key=lambda item: (
            item.serp_analysis.estimated_difficulty if item.serp_analysis else 10,
            -item.total_demand,
        ),
    )[:3]


def _opportunity_score(assessment: NicheAssessment, weak_clusters: list[KeywordCluster]) -> float:
    metrics = assessment.metrics
    cluster_bonus = min(12.0, len(weak_clusters) * 4.0)
    offer_gap_bonus = min(8.0, _average_usable_offer_gap(assessment) * 8.0)
    budget_bonus = 6.0 if metrics.estimated_launch_budget <= assessment.direction.budget_rub else -8.0
    demand_bonus = min(8.0, metrics.demand / 2500)
    risk_penalty = metrics.risk_level * 15 + metrics.seasonality * 4
    return round(
        max(
            0.0,
            min(
                100.0,
                assessment.score + cluster_bonus + offer_gap_bonus + budget_bonus + demand_bonus - risk_penalty,
            ),
        ),
        1,
    )


def _target_audience(assessment: NicheAssessment) -> str:
    region = assessment.direction.region
    base = assessment.direction.direction
    if region and region != "Без региона":
        return f"Пользователи из региона {region}, которые уже ищут: {base}"
    return f"Пользователи Рунета, которые уже ищут: {base}"


def _offer_for(assessment: NicheAssessment, clusters: list[KeywordCluster]) -> str:
    base = assessment.direction.direction
    offer_edges = _offer_edges(assessment)
    edge_text = f" Акцент в оффере: {', '.join(offer_edges)}." if offer_edges else ""
    if assessment.direction.project_type == "leadgen":
        return f"Заявка на {base} с быстрым подбором исполнителя и понятной ценой.{edge_text}"
    if assessment.direction.project_type == "marketplace":
        return f"Каталог вариантов по теме '{base}' с фильтрами по цене, региону и условиям.{edge_text}"
    if assessment.direction.project_type == "infoproduct":
        return f"Короткий платный материал или мини-курс по теме '{base}' с бесплатным входным чеклистом.{edge_text}"
    if clusters:
        return f"Страница/витрина под запрос '{clusters[0].representative_query}' с понятным следующим действием.{edge_text}"
    return f"Нишевой продукт под спрос '{base}' с быстрым первым действием для пользователя.{edge_text}"


def _ranking_reason(assessment: NicheAssessment, weak_clusters: list[KeywordCluster]) -> str:
    offer_gap = _top_offer_gap(assessment)
    offer_gap_text = ""
    if offer_gap:
        offer_gap_text = f" Дополнительный зазор по офферам в SERP: {offer_gap[1]:.2f} по запросу '{offer_gap[0]}'."
    if weak_clusters:
        cluster_names = ", ".join(cluster.name for cluster in weak_clusters[:3])
        return (
            f"Есть коммерческие кластеры с допустимой сложностью SERP: {cluster_names}. "
            "Их можно закрывать отдельными посадочными страницами."
            f"{offer_gap_text}"
        )
    if assessment.serp_analysis and assessment.serp_analysis.estimated_difficulty <= assessment.direction.max_difficulty:
        return f"Seed-запрос проходит по сложности SERP, можно начинать с узкой посадочной страницы.{offer_gap_text}"
    return f"Продвижение возможно через более узкие низкочастотные страницы и тест платного трафика.{offer_gap_text}"


def _landing_pages(assessment: NicheAssessment, clusters: list[KeywordCluster]) -> list[str]:
    if clusters:
        return [
            f"Страница под `{cluster.representative_query}` с оффером и формой заявки"
            for cluster in clusters[:5]
        ]
    return [
        f"Главная посадочная под `{assessment.direction.direction}`",
        f"Страница цен/условий под `{assessment.direction.direction} цена`",
    ]


def _traffic_plan(assessment: NicheAssessment, clusters: list[KeywordCluster]) -> list[str]:
    pages = clusters[:3]
    if pages:
        return [
            f"SEO: собрать страницу под кластер `{cluster.name}` и запрос `{cluster.representative_query}`"
            for cluster in pages
        ] + ["Контекст: запустить точные коммерческие запросы на 3-7 дней с лимитом бюджета."]
    return [
        "SEO: собрать 3 узкие страницы под низкочастотные коммерческие запросы.",
        "Контекст: запустить точные коммерческие запросы на 3-7 дней с лимитом бюджета.",
    ]


def _first_test(assessment: NicheAssessment, clusters: list[KeywordCluster]) -> str:
    pages = _landing_pages(assessment, clusters)[:3]
    return (
        "Запустить MVP из "
        f"{len(pages)} посадочных страниц, формы заявки и счетчика целей; "
        "оценить заявки, стоимость лида и конверсию за первую неделю."
    )


def _evidence(assessment: NicheAssessment, weak_clusters: list[KeywordCluster]) -> list[str]:
    evidence = [
        f"Спрос Wordstat: {assessment.metrics.demand}",
        f"Коммерческий интент: {assessment.metrics.commercial_intent:.2f}",
        f"Оценочный бюджет: {assessment.metrics.estimated_launch_budget} ₽ при лимите {assessment.direction.budget_rub} ₽",
    ]
    if weak_clusters:
        evidence.append(
            "Слабые SERP-кластеры: "
            + ", ".join(
                f"{cluster.name} {cluster.serp_analysis.estimated_difficulty}/10"
                for cluster in weak_clusters[:3]
                if cluster.serp_analysis
            )
        )
    offer_gap = _top_offer_gap(assessment)
    if offer_gap:
        evidence.append(f"Offer gap SERP: {offer_gap[1]:.2f} по запросу '{offer_gap[0]}'")
    weak_spots = _top_weak_spots(assessment)
    evidence.extend(weak_spots[:2])
    return evidence


def _recommendation_risks(assessment: NicheAssessment) -> list[str]:
    risks: list[str] = []
    if assessment.metrics.estimated_launch_budget > assessment.direction.budget_rub:
        risks.append("Бюджет запуска выше заданного лимита.")
    if assessment.metrics.competition >= 0.7:
        risks.append("Высокая общая конкуренция, стартовать лучше с узких кластеров.")
    if assessment.metrics.risk_level >= 0.5:
        risks.append("Есть повышенные юридические, финансовые или медицинские ограничения.")
    if _has_strong_competitor_offers(assessment):
        risks.append("Топ уже хорошо закрывает офферы, нужен более сильный УТП или узкая подниша.")
    if not risks:
        risks.append("Главный риск: фактическая стоимость заявки может оказаться выше маржи.")
    return risks


def _average_usable_offer_gap(assessment: NicheAssessment) -> float:
    analyses = [
        analysis
        for analysis in _serp_analyses(assessment)
        if analysis.estimated_difficulty <= assessment.direction.max_difficulty and analysis.offer_gap_score > 0
    ]
    if not analyses:
        return 0.0
    return sum(analysis.offer_gap_score for analysis in analyses) / len(analyses)


def _top_offer_gap(assessment: NicheAssessment) -> tuple[str, float] | None:
    analyses = sorted(
        [analysis for analysis in _serp_analyses(assessment) if analysis.offer_gap_score > 0],
        key=lambda item: item.offer_gap_score,
        reverse=True,
    )
    if not analyses:
        return None
    return analyses[0].query, analyses[0].offer_gap_score


def _top_weak_spots(assessment: NicheAssessment) -> list[str]:
    weak_spots: list[str] = []
    for analysis in sorted(_serp_analyses(assessment), key=lambda item: item.offer_gap_score, reverse=True):
        for spot in analysis.weak_spots:
            if spot not in weak_spots and "Явных слабых мест" not in spot:
                weak_spots.append(spot)
    return weak_spots


def _offer_edges(assessment: NicheAssessment) -> list[str]:
    labels = {
        "цена": "прозрачная цена",
        "гарантия": "гарантия",
        "скорость": "срок выполнения",
        "доставка": "доставка/выезд",
        "отзывы": "отзывы",
        "наличие": "наличие",
        "сервис": "диагностика/сервис",
        "действие": "заявка за 1 шаг",
    }
    missing: list[str] = []
    for analysis in sorted(_serp_analyses(assessment), key=lambda item: item.offer_gap_score, reverse=True):
        for signal in analysis.missing_offer_signals:
            label = labels.get(signal, signal)
            if label not in missing:
                missing.append(label)
    return missing[:3]


def _has_strong_competitor_offers(assessment: NicheAssessment) -> bool:
    analyses = [analysis for analysis in _serp_analyses(assessment) if analysis.offer_signal_score > 0]
    if not analyses:
        return False
    average_signal = sum(analysis.offer_signal_score for analysis in analyses) / len(analyses)
    average_gap = sum(analysis.offer_gap_score for analysis in analyses) / len(analyses)
    return average_signal >= 0.7 and average_gap <= 0.25


def _serp_analyses(assessment: NicheAssessment) -> Iterator[SerpAnalysis]:
    if assessment.serp_analysis:
        yield assessment.serp_analysis
    for cluster in assessment.keyword_clusters:
        if cluster.serp_analysis:
            yield cluster.serp_analysis
