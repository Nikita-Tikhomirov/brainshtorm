from datetime import date

from brainshtorm.models import DirectionInput
from brainshtorm.yandex_wordstat import (
    YandexWordstatClient,
    YandexWordstatProvider,
    build_weekly_period,
)


def test_client_sends_top_requests_with_api_key_and_folder_id():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append((url, body, headers, timeout))
        return {"totalCount": "1200", "results": [], "associations": []}

    client = YandexWordstatClient(
        api_key="secret",
        folder_id="folder",
        transport=transport,
    )

    result = client.top_requests("ремонт техники", region_ids=["213"], num_phrases=25)

    assert result["totalCount"] == "1200"
    assert calls[0][0].endswith("/v2/wordstat/topRequests")
    assert calls[0][1] == {
        "phrase": "ремонт техники",
        "numPhrases": 25,
        "regions": ["213"],
        "devices": ["DEVICE_ALL"],
        "folderId": "folder",
    }
    assert calls[0][2]["Authorization"] == "Api-key secret"


def test_build_weekly_period_uses_full_previous_weeks():
    period = build_weekly_period(today=date(2026, 6, 1), weeks=8)

    assert period.from_date == "2026-04-06T00:00:00Z"
    assert period.to_date == "2026-05-31T00:00:00Z"


def test_provider_converts_wordstat_responses_to_market_metrics():
    class FakeClient:
        def top_requests(self, phrase, *, region_ids, num_phrases):
            return {
                "totalCount": "9000",
                "results": [{"phrase": phrase, "count": "9000"}],
                "associations": [{"phrase": "ремонт робота пылесоса xiaomi", "count": "1500"}],
            }

        def dynamics(self, phrase, *, region_ids, period):
            return {
                "results": [
                    {"date": "2026-04-06T00:00:00Z", "count": "1000"},
                    {"date": "2026-04-13T00:00:00Z", "count": "1200"},
                    {"date": "2026-04-20T00:00:00Z", "count": "1600"},
                ]
            }

        def regions(self, phrase, *, region_level):
            return {
                "results": [
                    {"region": "213", "count": "6000", "affinityIndex": "130"},
                    {"region": "2", "count": "1200", "affinityIndex": "95"},
                ]
            }

    provider = YandexWordstatProvider(client=FakeClient(), region_ids=["213"])
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )

    metrics = provider.metrics_for(direction)

    assert metrics.demand == 9000
    assert metrics.trend == 0.5
    assert metrics.regional_affinity == 1.3
    assert metrics.commercial_intent > 0.6
