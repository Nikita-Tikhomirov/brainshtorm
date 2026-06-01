from __future__ import annotations

from dataclasses import replace
from typing import Any

from brainshtorm.models import KeywordCandidate, KeywordCluster, SerpAnalysis


COMMERCIAL_GROUPS = {
    "покупка": [
        "купить",
        "заказать",
        "доставка",
        "магазин",
        "запчаст",
        "аккумулятор",
    ],
    "цены": [
        "цена",
        "стоимость",
        "сколько стоит",
        "прайс",
        "тариф",
    ],
    "обучение": [
        "курс",
        "курсы",
        "обучение",
        "школа",
        "уроки",
    ],
    "подбор": [
        "подбор",
        "рейтинг",
        "лучший",
        "отзывы",
        "сравнение",
    ],
    "ремонт/сервис": [
        "ремонт",
        "починить",
        "сервис",
        "мастер",
        "мастерская",
        "диагностика",
    ],
}

LOW_INTENT_TERMS = [
    "инструкция",
    "своими руками",
    "что такое",
    "как сделать",
    "форум",
    "скачать",
]


def extract_keyword_candidates(
    top_response: dict[str, Any],
    *,
    limit: int,
    min_commercial_score: float = 0.35,
) -> list[KeywordCandidate]:
    candidates_by_phrase: dict[str, KeywordCandidate] = {}
    for item in _iter_phrase_items(top_response):
        phrase = _clean_phrase(item.get("phrase"))
        if not phrase:
            continue
        count = _int_value(item.get("count")) or 0
        score, modifiers = _commercial_score(phrase)
        if score < min_commercial_score:
            continue
        existing = candidates_by_phrase.get(phrase)
        if existing and existing.count >= count:
            continue
        candidates_by_phrase[phrase] = KeywordCandidate(
            phrase=phrase,
            count=count,
            commercial_score=score,
            modifiers=modifiers,
        )

    return sorted(
        candidates_by_phrase.values(),
        key=lambda item: (item.count, item.commercial_score),
        reverse=True,
    )[:limit]


def build_keyword_clusters(
    top_response: dict[str, Any],
    *,
    max_clusters: int,
    phrase_limit: int = 50,
) -> list[KeywordCluster]:
    candidates = extract_keyword_candidates(top_response, limit=phrase_limit)
    groups: dict[str, list[KeywordCandidate]] = {}
    for candidate in candidates:
        groups.setdefault(_cluster_name(candidate), []).append(candidate)

    clusters = [
        _build_cluster(name, phrases)
        for name, phrases in groups.items()
        if phrases
    ]
    return sorted(
        clusters,
        key=lambda item: (item.total_demand, item.commercial_score),
        reverse=True,
    )[:max_clusters]


def attach_cluster_serp(
    cluster: KeywordCluster,
    serp_analysis: SerpAnalysis,
) -> KeywordCluster:
    return replace(cluster, serp_analysis=serp_analysis)


def summarize_cluster_serp(clusters: list[KeywordCluster]) -> str:
    checked = [cluster for cluster in clusters if cluster.serp_analysis]
    if not checked:
        return "кластеры не проверялись"
    avg_difficulty = round(
        sum(cluster.serp_analysis.estimated_difficulty for cluster in checked if cluster.serp_analysis)
        / len(checked),
        1,
    )
    weak_clusters = [
        cluster.name
        for cluster in checked
        if cluster.serp_analysis and cluster.serp_analysis.estimated_difficulty <= 5
    ]
    if weak_clusters:
        return f"средняя сложность кластеров {avg_difficulty}/10; слабые кластеры: {', '.join(weak_clusters)}"
    return f"средняя сложность кластеров {avg_difficulty}/10; явных слабых кластеров не найдено"


def _iter_phrase_items(top_response: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key in ("results", "associations"):
        value = top_response.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    return items


def _build_cluster(name: str, phrases: list[KeywordCandidate]) -> KeywordCluster:
    sorted_phrases = sorted(
        phrases,
        key=lambda item: (item.count, item.commercial_score),
        reverse=True,
    )
    total_demand = sum(item.count for item in sorted_phrases)
    commercial_score = round(
        sum(item.commercial_score * max(1, item.count) for item in sorted_phrases)
        / max(1, sum(max(1, item.count) for item in sorted_phrases)),
        2,
    )
    return KeywordCluster(
        name=name,
        representative_query=sorted_phrases[0].phrase,
        phrases=sorted_phrases,
        total_demand=total_demand,
        commercial_score=commercial_score,
    )


def _cluster_name(candidate: KeywordCandidate) -> str:
    for group_name in COMMERCIAL_GROUPS:
        if group_name in candidate.modifiers:
            return group_name
    return "прочий коммерческий спрос"


def _commercial_score(phrase: str) -> tuple[float, list[str]]:
    text = phrase.lower()
    score = 0.1
    modifiers: list[str] = []
    for group_name, terms in COMMERCIAL_GROUPS.items():
        matches = sum(1 for term in terms if term in text)
        if matches:
            modifiers.append(group_name)
            score += min(0.55, matches * 0.25)
    if any(term in text for term in LOW_INTENT_TERMS):
        score -= 0.35
    return round(max(0.0, min(1.0, score)), 2), modifiers


def _clean_phrase(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
