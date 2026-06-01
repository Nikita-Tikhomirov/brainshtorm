from __future__ import annotations

import base64
import html
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import replace
import hashlib
from typing import Any, Callable

from brainshtorm.keywords import summarize_cluster_serp
from brainshtorm.models import DirectionInput, KeywordCluster, NicheAssessment, REVIEW, SerpAnalysis, SerpResult, SKIP, TAKE
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

    competitor_score = round(
        max(0.1, min(0.95, 0.25 + aggregator_share * 0.55 + marketplace_share * 0.2)),
        2,
    )
    estimated_difficulty = max(1, min(10, round(1 + competitor_score * 9)))
    score_delta = round((0.4 - competitor_score) * 30, 1)
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
        summary=_serp_summary(aggregator_count, marketplace_count, estimated_difficulty),
    )


def apply_serp_analysis(assessment: NicheAssessment, analysis: SerpAnalysis) -> NicheAssessment:
    score = round(_clamp_float(assessment.score + analysis.score_delta), 1)
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


def _serp_summary(aggregator_count: int, marketplace_count: int, difficulty: int) -> str:
    parts = [f"оценочная сложность выдачи {difficulty}/10"]
    if aggregator_count:
        parts.append(f"агрегаторов в топе: {aggregator_count}")
    if marketplace_count:
        parts.append(f"маркетплейсов в топе: {marketplace_count}")
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
