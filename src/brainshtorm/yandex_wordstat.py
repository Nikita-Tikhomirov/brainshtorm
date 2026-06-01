from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable

from brainshtorm.models import DirectionInput, MarketMetrics
from brainshtorm.providers import _estimate_launch_budget, _estimate_risk


BASE_URL = "https://searchapi.api.cloud.yandex.net"

Transport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]


@dataclass(frozen=True)
class WeeklyPeriod:
    from_date: str
    to_date: str


class YandexWordstatError(RuntimeError):
    pass


class YandexWordstatClient:
    def __init__(
        self,
        *,
        api_key: str,
        folder_id: str,
        timeout: int = 60,
        transport: Transport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Yandex API key is required")
        if not folder_id.strip():
            raise ValueError("Yandex folder ID is required")
        self.api_key = api_key.strip()
        self.folder_id = folder_id.strip()
        self.timeout = timeout
        self.transport = transport or _urllib_transport

    def top_requests(
        self,
        phrase: str,
        *,
        region_ids: list[str],
        num_phrases: int = 50,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "phrase": phrase,
            "numPhrases": num_phrases,
            "regions": region_ids,
            "devices": ["DEVICE_ALL"],
            "folderId": self.folder_id,
        }
        return self._post("/v2/wordstat/topRequests", body)

    def dynamics(
        self,
        phrase: str,
        *,
        region_ids: list[str],
        period: WeeklyPeriod,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "phrase": phrase,
            "period": "PERIOD_WEEKLY",
            "fromDate": period.from_date,
            "toDate": period.to_date,
            "regions": region_ids,
            "devices": ["DEVICE_ALL"],
            "folderId": self.folder_id,
        }
        return self._post("/v2/wordstat/dynamics", body)

    def regions(
        self,
        phrase: str,
        *,
        region_level: str = "REGION_CITIES",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "phrase": phrase,
            "region": region_level,
            "devices": ["DEVICE_ALL"],
            "folderId": self.folder_id,
        }
        return self._post("/v2/wordstat/regions", body)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Api-key {self.api_key}",
            "Content-Type": "application/json",
        }
        return self.transport(f"{BASE_URL}{path}", body, headers, self.timeout)


class YandexWordstatProvider:
    def __init__(
        self,
        *,
        client: Any,
        region_ids: list[str],
        num_phrases: int = 50,
        today: date | None = None,
    ) -> None:
        self.client = client
        self.region_ids = region_ids
        self.num_phrases = num_phrases
        self.period = build_weekly_period(today=today or date.today(), weeks=8)

    def metrics_for(self, direction: DirectionInput) -> MarketMetrics:
        top = self.client.top_requests(
            direction.direction,
            region_ids=self.region_ids,
            num_phrases=self.num_phrases,
        )
        dynamics = self.client.dynamics(
            direction.direction,
            region_ids=self.region_ids,
            period=self.period,
        )
        regions = self.client.regions(direction.direction, region_level="REGION_CITIES")

        demand = _int_value(top.get("totalCount")) or _sum_counts(top.get("results", []))
        trend = _trend_from_dynamics(dynamics.get("results", []))
        regional_affinity = _regional_affinity(regions.get("results", []), self.region_ids)
        commercial_intent = _commercial_intent(direction.direction, top)
        competition = _competition_estimate(demand, commercial_intent)
        estimated_difficulty = max(1, min(10, round(competition * 10)))
        risk_level = _estimate_risk(direction.direction)
        launch_budget = _estimate_launch_budget(direction.project_type, estimated_difficulty)

        return MarketMetrics(
            demand=demand,
            trend=trend,
            regional_affinity=regional_affinity,
            commercial_intent=commercial_intent,
            competition=competition,
            estimated_launch_budget=launch_budget,
            estimated_difficulty=estimated_difficulty,
            seasonality=0.25,
            risk_level=risk_level,
        )


def build_weekly_period(*, today: date, weeks: int) -> WeeklyPeriod:
    last_sunday = today - timedelta(days=today.weekday() + 1)
    start = last_sunday - timedelta(days=weeks * 7 - 1)
    return WeeklyPeriod(
        from_date=f"{start.isoformat()}T00:00:00Z",
        to_date=f"{last_sunday.isoformat()}T00:00:00Z",
    )


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
        raise YandexWordstatError(f"Yandex Wordstat HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise YandexWordstatError(f"Yandex Wordstat request failed: {exc.reason}") from exc


def _trend_from_dynamics(results: list[dict[str, Any]]) -> float:
    counts = [_int_value(item.get("count")) for item in results]
    counts = [count for count in counts if count is not None]
    if len(counts) < 2:
        return 0.0
    first = max(1, counts[0])
    return round(max(-0.5, min(0.5, (counts[-1] - first) / first)), 2)


def _regional_affinity(results: list[dict[str, Any]], region_ids: list[str]) -> float:
    if not results:
        return 1.0
    selected = [
        _float_value(item.get("affinityIndex"))
        for item in results
        if not region_ids or str(item.get("region")) in region_ids
    ]
    selected = [value for value in selected if value is not None]
    if not selected:
        return 1.0
    return round(max(0.5, min(2.0, max(selected) / 100)), 2)


def _commercial_intent(direction: str, top_response: dict[str, Any]) -> float:
    text = " ".join(
        [direction]
        + [str(item.get("phrase", "")) for item in top_response.get("results", [])]
        + [str(item.get("phrase", "")) for item in top_response.get("associations", [])]
    ).lower()
    hot_terms = [
        "купить",
        "цена",
        "стоимость",
        "заказать",
        "ремонт",
        "услуги",
        "доставка",
        "подбор",
        "курс",
        "обучение",
    ]
    matches = sum(1 for term in hot_terms if term in text)
    return round(max(0.35, min(0.95, 0.45 + matches * 0.18)), 2)


def _competition_estimate(demand: int, commercial_intent: float) -> float:
    demand_pressure = min(0.65, math.log10(max(demand, 10)) / 8)
    return round(max(0.2, min(0.95, demand_pressure + commercial_intent * 0.35)), 2)


def _sum_counts(results: list[dict[str, Any]]) -> int:
    return sum(_int_value(item.get("count")) or 0 for item in results)


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
