from __future__ import annotations

import base64
import hashlib
import html
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from typing import Any, Callable

from brainshtorm.keywords import summarize_cluster_serp
from brainshtorm.models import (
    DirectionInput,
    EvidenceItem,
    KeywordCluster,
    NicheAssessment,
    REVIEW,
    SerpAnalysis,
    SerpResult,
    SKIP,
    TAKE,
)
from brainshtorm.scoring import add_score_adjustment, ensure_score_breakdown
from brainshtorm.yandex_wordstat import BASE_URL


SerpTransport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]


AGGREGATOR_DOMAINS = {
    "2gis.ru",
    "avito.ru",
    "flamp.ru",
    "orgpage.ru",
    "profi.ru",
    "spravker.ru",
    "yell.ru",
    "yandex.ru",
    "zoon.ru",
}


MARKETPLACE_DOMAINS = {
    "market.yandex.ru",
    "megamarket.ru",
    "ozon.ru",
    "wildberries.ru",
}


OFFER_SIGNAL_GROUPS = {
    "цена": ("цен", "стоимость", "прайс", "руб", "₽"),
    "гарантия": ("гарант", "официальн"),
    "скорость": ("срочно", "быстро", "сегодня", "за 1 день", "24 час"),
    "доставка": ("доставка", "самовывоз", "курьер"),
    "отзывы": ("отзыв", "рейтинг", "оценк"),
    "наличие": ("в наличии", "каталог", "выбор"),
    "сервис": ("выезд", "мастер", "диагностик", "ремонт", "сервис"),
    "действие": ("заказать", "купить", "заявк", "консультац", "расчет"),
}

INFO_INTENT_TERMS = (
    "как ",
    "что такое",
    "инструкция",
    "форум",
    "отзывы",
    "обзор",
    "блог",
    "статья",
)

LOCAL_SERVICE_TERMS = (
    "ремонт",
    "сервис",
    "мастер",
    "выезд",
    "диагностик",
    "студия",
    "центр",
)


@dataclass(frozen=True)
class _OfferAnalysis:
    offer_signal_score: float
    offer_gap_score: float
    competitor_types: list[str]
    offer_signals: list[str]
    missing_offer_signals: list[str]
    weak_spots: list[str]


class YandexSerpError(RuntimeError):
    pass


class YandexSerpClient:
    def __init__(
        self,
        *,
        api_key: str,
        folder_id: str,
        timeout: int = 60,
        transport: SerpTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Yandex API key is required")
        if not folder_id.strip():
            raise ValueError("Yandex folder ID is required")
        self.api_key = api_key.strip()
        self.folder_id = folder_id.strip()
        self.timeout = timeout
        self.transport = transport or _urllib_transport

    def search_xml(
        self,
        query: str,
        *,
        region_id: str,
        results_limit: int = 10,
    ) -> str:
        body: dict[str, Any] = {
            "query": {
                "searchType": "SEARCH_TYPE_RU",
                "queryText": query,
                "familyMode": "FAMILY_MODE_MODERATE",
                "page": "0",
                "fixTypoMode": "FIX_TYPO_MODE_ON",
            },
            "sortSpec": {
                "sortMode": "SORT_MODE_BY_RELEVANCE",
                "sortOrder": "SORT_ORDER_DESC",
            },
            "groupSpec": {
                "groupMode": "GROUP_MODE_FLAT",
                "groupsOnPage": str(_clamp_int(results_limit, 1, 100)),
                "docsInGroup": "1",
            },
            "maxPassages": "3",
            "region": region_id,
            "l10n": "LOCALIZATION_RU",
            "folderId": self.folder_id,
            "responseFormat": "FORMAT_XML",
        }
        response = self._post("/v2/web/search", body)
        return _decode_raw_data(response.get("rawData"))

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Api-key {self.api_key}",
            "Content-Type": "application/json",
        }
        return self.transport(f"{BASE_URL}{path}", body, headers, self.timeout)


class YandexSerpProvider:
    def __init__(
        self,
        *,
        client: YandexSerpClient,
        region_id: str,
        results_limit: int = 10,
    ) -> None:
        self.client = client
        self.region_id = region_id
        self.results_limit = results_limit

    def analysis_for(self, direction: DirectionInput) -> SerpAnalysis:
        xml_text = self.client.search_xml(
            direction.direction,
            region_id=self.region_id,
            results_limit=self.results_limit,
        )
        return analyze_serp_results(
            query=direction.direction,
            results=parse_yandex_xml_results(xml_text),
            max_difficulty=direction.max_difficulty,
        )


class DemoSerpProvider:
    """Deterministic SERP provider for checking the UI without paid API calls."""

    def __init__(self, *, results_limit: int = 10) -> None:
        self.results_limit = results_limit

    def analysis_for(self, direction: DirectionInput) -> SerpAnalysis:
        domains = _demo_domains(direction.direction)[: self.results_limit]
        results = [
            SerpResult(
                title=f"{direction.direction} - результат {index}",
                url=f"https://{domain}/demo/{index}",
                domain=domain,
                snippet="Демо-результат для оценки структуры выдачи.",
            )
            for index, domain in enumerate(domains, start=1)
        ]
        return analyze_serp_results(
            query=direction.direction,
            results=results,
            max_difficulty=direction.max_difficulty,
        )


def parse_yandex_xml_results(xml_text: str) -> list[SerpResult]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise YandexSerpError(f"Yandex SERP XML parse failed: {exc}") from exc

    results: list[SerpResult] = []
    for doc in _iter_by_local_name(root, "doc"):
        url = _first_text(doc, "url")
        if not url:
            continue
        title = _first_text(doc, "title") or url
        snippet = _first_text(doc, "passage") or _first_text(doc, "headline") or ""
        results.append(
            SerpResult(
                title=_clean_text(title),
                url=url,
                domain=_domain_from_url(url),
                snippet=_clean_text(snippet),
            )
        )
    return results


def analyze_serp_results(
    *,
    query: str,
    results: list[SerpResult],
    max_difficulty: int,
) -> SerpAnalysis:
    total = max(1, len(results))
    aggregator_count = sum(1 for result in results if _is_known_domain(result.domain, AGGREGATOR_DOMAINS))
    marketplace_count = sum(1 for result in results if _is_known_domain(result.domain, MARKETPLACE_DOMAINS))
    aggregator_share = aggregator_count / total
    marketplace_share = marketplace_count / total
    top_domains = _unique_domains(results, limit=5)
    offer_analysis = _analyze_offer_layer(
        query=query,
        results=results,
        aggregator_count=aggregator_count,
        marketplace_count=marketplace_count,
    )

    competitor_score = round(
        max(
            0.1,
            min(
                0.95,
                0.25
                + aggregator_share * 0.55
                + marketplace_share * 0.2
                + offer_analysis.offer_signal_score * 0.1
                - offer_analysis.offer_gap_score * 0.06,
            ),
        ),
        2,
    )
    estimated_difficulty = max(1, min(10, round(1 + competitor_score * 9)))
    score_delta = round((0.4 - competitor_score) * 30 + (offer_analysis.offer_gap_score - 0.45) * 6, 1)
    if estimated_difficulty > max_difficulty:
        score_delta -= min(8, (estimated_difficulty - max_difficulty) * 2)

    return SerpAnalysis(
        query=query,
        results=results,
        results_count=len(results),
        top_domains=top_domains,
        aggregator_count=aggregator_count,
        marketplace_count=marketplace_count,
        competitor_score=competitor_score,
        estimated_difficulty=estimated_difficulty,
        score_delta=round(score_delta, 1),
        summary=_serp_summary(aggregator_count, marketplace_count, estimated_difficulty, offer_analysis),
        offer_signal_score=offer_analysis.offer_signal_score,
        offer_gap_score=offer_analysis.offer_gap_score,
        competitor_types=offer_analysis.competitor_types,
        offer_signals=offer_analysis.offer_signals,
        missing_offer_signals=offer_analysis.missing_offer_signals,
        weak_spots=offer_analysis.weak_spots,
    )


def apply_serp_analysis(assessment: NicheAssessment, analysis: SerpAnalysis) -> NicheAssessment:
    score = round(_clamp_float(assessment.score + analysis.score_delta), 1)
    base_breakdown = ensure_score_breakdown(assessment)
    evidence_items = getattr(assessment, "evidence_items", [])
    risks = list(assessment.risks)
    if analysis.estimated_difficulty > assessment.direction.max_difficulty:
        risks.append(
            "SERP: выдача сложнее заданного лимита, нужен автоматический разбор конкурентов и офферов."
        )
    elif analysis.aggregator_count or analysis.marketplace_count:
        risks.append("SERP: в топе есть агрегаторы или маркетплейсы, вход может быть дороже.")

    return replace(
        assessment,
        score=score,
        verdict=_verdict_for_score(score),
        explanation=f"{assessment.explanation} SERP: {analysis.summary}",
        risks=risks,
        serp_analysis=analysis,
        score_breakdown=add_score_adjustment(
            base_breakdown,
            key="seed_serp_delta",
            label="Seed SERP",
            raw_value=f"{analysis.query}; difficulty {analysis.estimated_difficulty}/10; offer_gap {analysis.offer_gap_score:.2f}",
            contribution=round(score - base_breakdown.final_score, 1),
            evidence=f"Yandex SERP top domains: {', '.join(analysis.top_domains) or 'n/a'}",
            final_score=score,
            confidence_delta=0.15,
            confidence_note="Seed SERP checked.",
        ),
        evidence_items=[*evidence_items, _serp_evidence(analysis, claim="Seed SERP")],
    )


def apply_keyword_cluster_serp_analysis(
    assessment: NicheAssessment,
    clusters: list[KeywordCluster],
) -> NicheAssessment:
    checked_clusters = [cluster for cluster in clusters if cluster.serp_analysis]
    if not checked_clusters:
        return replace(assessment, keyword_clusters=clusters)

    average_delta = sum(
        cluster.serp_analysis.score_delta
        for cluster in checked_clusters
        if cluster.serp_analysis
    ) / len(checked_clusters)
    cluster_delta = round(_clamp_float(average_delta * 0.6, -12.0, 8.0), 1)
    score = round(_clamp_float(assessment.score + cluster_delta), 1)
    base_breakdown = ensure_score_breakdown(assessment)
    evidence_items = getattr(assessment, "evidence_items", [])
    risks = list(assessment.risks)
    average_difficulty = sum(
        cluster.serp_analysis.estimated_difficulty
        for cluster in checked_clusters
        if cluster.serp_analysis
    ) / len(checked_clusters)

    if average_difficulty > assessment.direction.max_difficulty:
        risks.append(
            "Кластеры: коммерческие запросы сложнее заданного лимита, нужен автоматический разбор топа."
        )
    elif cluster_delta > 0:
        risks.append("Кластеры: есть признаки слабой коммерческой выдачи, следующий шаг — автоматический разбор офферов.")

    return replace(
        assessment,
        score=score,
        verdict=_verdict_for_score(score),
        explanation=f"{assessment.explanation} Кластеры: {summarize_cluster_serp(clusters)}.",
        risks=risks,
        keyword_clusters=clusters,
        score_breakdown=add_score_adjustment(
            base_breakdown,
            key="cluster_serp_delta",
            label="Кластерный SERP",
            raw_value=f"{len(checked_clusters)} clusters; average_delta {average_delta:.1f}",
            contribution=round(score - base_breakdown.final_score, 1),
            evidence="Yandex SERP by representative commercial cluster queries.",
            final_score=score,
            confidence_delta=0.15,
            confidence_note="Commercial keyword clusters checked in SERP.",
        ),
        evidence_items=[
            *evidence_items,
            *[_cluster_serp_evidence(cluster) for cluster in checked_clusters if cluster.serp_analysis],
        ],
    )


def _serp_evidence(analysis: SerpAnalysis, *, claim: str) -> EvidenceItem:
    return EvidenceItem(
        source="Yandex SERP",
        claim=claim,
        value=analysis.query,
        details=[
            f"difficulty={analysis.estimated_difficulty}/10",
            f"score_delta={analysis.score_delta:.1f}",
            f"offer_gap={analysis.offer_gap_score:.2f}",
            f"top_domains={', '.join(analysis.top_domains) or 'n/a'}",
            f"weak_spots={'; '.join(analysis.weak_spots) or 'n/a'}",
        ],
    )


def _cluster_serp_evidence(cluster: KeywordCluster) -> EvidenceItem:
    analysis = cluster.serp_analysis
    if analysis is None:
        return EvidenceItem(
            source="Yandex SERP",
            claim=f"Кластер {cluster.name}",
            value=cluster.representative_query,
            details=[f"demand={cluster.total_demand}", "SERP not checked"],
        )
    return EvidenceItem(
        source="Yandex SERP",
        claim=f"Кластер {cluster.name}",
        value=cluster.representative_query,
        details=[
            f"demand={cluster.total_demand}",
            f"difficulty={analysis.estimated_difficulty}/10",
            f"score_delta={analysis.score_delta:.1f}",
            f"offer_gap={analysis.offer_gap_score:.2f}",
            f"top_domains={', '.join(analysis.top_domains) or 'n/a'}",
        ],
    )


def _decode_raw_data(raw_data: Any) -> str:
    if not isinstance(raw_data, str) or not raw_data:
        raise YandexSerpError("Yandex SERP response has empty rawData")

    stripped = raw_data.strip()
    if stripped.startswith("<"):
        return stripped

    try:
        decoded = base64.b64decode(stripped.encode("ascii"), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise YandexSerpError("Yandex SERP rawData is not XML or base64 XML") from exc

    if not decoded.lstrip().startswith("<"):
        raise YandexSerpError("Yandex SERP rawData decoded payload is not XML")
    return decoded


def _urllib_transport(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise YandexSerpError(f"Yandex SERP HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise YandexSerpError(f"Yandex SERP request failed: {exc.reason}") from exc


def _iter_by_local_name(root: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == name]


def _first_text(root: ET.Element, name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text:
            return element.text
    return ""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_text(value: str) -> str:
    return " ".join(html.unescape(value).split())


def _domain_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")
    return domain.split(":", 1)[0]


def _is_known_domain(domain: str, known_domains: set[str]) -> bool:
    return any(domain == known or domain.endswith(f".{known}") for known in known_domains)


def _unique_domains(results: list[SerpResult], *, limit: int) -> list[str]:
    domains: list[str] = []
    for result in results:
        if result.domain and result.domain not in domains:
            domains.append(result.domain)
        if len(domains) >= limit:
            break
    return domains


def _analyze_offer_layer(
    *,
    query: str,
    results: list[SerpResult],
    aggregator_count: int,
    marketplace_count: int,
) -> _OfferAnalysis:
    if not results:
        return _OfferAnalysis(
            offer_signal_score=0.0,
            offer_gap_score=0.0,
            competitor_types=[],
            offer_signals=[],
            missing_offer_signals=list(OFFER_SIGNAL_GROUPS),
            weak_spots=["Нет результатов SERP для автоматического разбора офферов."],
        )

    total = len(results)
    query_tokens = _important_tokens(query)
    result_texts = [_result_text(result) for result in results]
    present_signals = [
        label
        for label, terms in OFFER_SIGNAL_GROUPS.items()
        if any(_has_any_term(text, terms) for text in result_texts)
    ]
    signal_result_share = sum(1 for text in result_texts if _has_any_offer_signal(text)) / total
    signal_coverage = len(present_signals) / max(1, len(OFFER_SIGNAL_GROUPS))
    offer_signal_score = round(min(1.0, signal_coverage * 0.65 + signal_result_share * 0.35), 2)

    exact_match_share = _exact_match_share(query, query_tokens, result_texts)
    info_count = sum(1 for text in result_texts if _has_any_term(text, INFO_INTENT_TERMS))
    competitor_types = _competitor_types(results, result_texts)
    missing_signals = [label for label in OFFER_SIGNAL_GROUPS if label not in present_signals]

    middleman_share = min(1.0, (aggregator_count + marketplace_count) / total)
    info_share = info_count / total
    offer_gap_score = round(
        _clamp_float(
            (1 - offer_signal_score) * 0.35
            + (1 - exact_match_share) * 0.25
            + middleman_share * 0.25
            + info_share * 0.15,
            0.0,
            1.0,
        ),
        2,
    )
    weak_spots = _offer_weak_spots(
        offer_signal_score=offer_signal_score,
        exact_match_share=exact_match_share,
        aggregator_count=aggregator_count,
        marketplace_count=marketplace_count,
        info_count=info_count,
        total=total,
        missing_signals=missing_signals,
    )
    return _OfferAnalysis(
        offer_signal_score=offer_signal_score,
        offer_gap_score=offer_gap_score,
        competitor_types=competitor_types,
        offer_signals=present_signals,
        missing_offer_signals=missing_signals[:4],
        weak_spots=weak_spots,
    )


def _result_text(result: SerpResult) -> str:
    return f"{result.title} {result.snippet} {result.url}".lower()


def _important_tokens(value: str) -> list[str]:
    normalized = "".join(char if char.isalnum() else " " for char in value.lower())
    return [token for token in normalized.split() if len(token) >= 4]


def _has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _has_any_offer_signal(text: str) -> bool:
    return any(_has_any_term(text, terms) for terms in OFFER_SIGNAL_GROUPS.values())


def _exact_match_share(query: str, query_tokens: list[str], result_texts: list[str]) -> float:
    normalized_query = " ".join(query.lower().split())
    if not query_tokens:
        return 0.0
    exact_matches = 0
    for text in result_texts:
        if normalized_query in text or all(token in text for token in query_tokens):
            exact_matches += 1
    return round(exact_matches / max(1, len(result_texts)), 2)


def _competitor_types(results: list[SerpResult], result_texts: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for result, text in zip(results, result_texts):
        if _is_known_domain(result.domain, AGGREGATOR_DOMAINS):
            label = "агрегаторы"
        elif _is_known_domain(result.domain, MARKETPLACE_DOMAINS):
            label = "маркетплейсы"
        elif _has_any_term(text, INFO_INTENT_TERMS):
            label = "информационные страницы"
        elif _has_any_term(text, LOCAL_SERVICE_TERMS):
            label = "сервисные сайты"
        else:
            label = "нишевые сайты"
        counts[label] = counts.get(label, 0) + 1

    return [
        f"{label}: {count}"
        for label, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _offer_weak_spots(
    *,
    offer_signal_score: float,
    exact_match_share: float,
    aggregator_count: int,
    marketplace_count: int,
    info_count: int,
    total: int,
    missing_signals: list[str],
) -> list[str]:
    weak_spots: list[str] = []
    if aggregator_count / total >= 0.3:
        weak_spots.append("В топе заметная доля агрегаторов, можно конкурировать более точной посадочной страницей.")
    if marketplace_count / total >= 0.3:
        weak_spots.append("В топе заметная доля маркетплейсов, нужен узкий ассортимент или экспертная витрина.")
    if offer_signal_score < 0.45 and missing_signals:
        weak_spots.append("В сниппетах мало явных офферов: " + ", ".join(missing_signals[:4]) + ".")
    if exact_match_share < 0.45:
        weak_spots.append("Мало страниц с точным совпадением запроса в title/snippet.")
    if info_count / total >= 0.25:
        weak_spots.append("В топе есть информационные страницы, коммерческая посадочная может закрыть интент точнее.")
    if not weak_spots:
        weak_spots.append("Явных слабых мест по офферу в сниппетах не найдено.")
    return weak_spots


def _serp_summary(
    aggregator_count: int,
    marketplace_count: int,
    difficulty: int,
    offer_analysis: _OfferAnalysis,
) -> str:
    parts = [f"оценочная сложность выдачи {difficulty}/10"]
    if aggregator_count:
        parts.append(f"агрегаторов в топе: {aggregator_count}")
    if marketplace_count:
        parts.append(f"маркетплейсов в топе: {marketplace_count}")
    parts.append(f"offer gap: {offer_analysis.offer_gap_score:.2f}")
    return "; ".join(parts) + "."


def _verdict_for_score(score: float) -> str:
    if score >= 75:
        return TAKE
    if score >= 50:
        return REVIEW
    return SKIP


def _clamp_float(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _demo_domains(direction: str) -> list[str]:
    pool = [
        "profi.ru",
        "small-service.ru",
        "remont-local.ru",
        "2gis.ru",
        "expert-blog.ru",
        "market.yandex.ru",
        "service-city.ru",
        "avito.ru",
        "niche-leads.ru",
        "ozon.ru",
    ]
    value = int(hashlib.sha256(direction.encode("utf-8")).hexdigest()[:8], 16)
    shift = value % len(pool)
    return pool[shift:] + pool[:shift]
