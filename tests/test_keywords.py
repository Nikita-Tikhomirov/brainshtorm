from brainshtorm.keywords import build_keyword_clusters, extract_keyword_candidates


def test_extract_keyword_candidates_keeps_commercial_phrases_first():
    top_response = {
        "results": [
            {"phrase": "ремонт роботов пылесосов xiaomi", "count": "2600"},
            {"phrase": "робот пылесос инструкция", "count": "2100"},
            {"phrase": "ремонт робота пылесоса цена", "count": "1900"},
        ],
        "associations": [
            {"phrase": "купить аккумулятор робота пылесоса", "count": "1200"},
        ],
    }

    candidates = extract_keyword_candidates(top_response, limit=10)

    assert [candidate.phrase for candidate in candidates[:3]] == [
        "ремонт роботов пылесосов xiaomi",
        "ремонт робота пылесоса цена",
        "купить аккумулятор робота пылесоса",
    ]
    assert all(candidate.commercial_score >= 0.35 for candidate in candidates)


def test_build_keyword_clusters_groups_by_commercial_intent():
    top_response = {
        "results": [
            {"phrase": "ремонт роботов пылесосов xiaomi", "count": "2600"},
            {"phrase": "ремонт робота пылесоса цена", "count": "1900"},
            {"phrase": "купить аккумулятор робота пылесоса", "count": "1200"},
            {"phrase": "сервис роботов пылесосов москва", "count": "700"},
        ],
        "associations": [],
    }

    clusters = build_keyword_clusters(top_response, max_clusters=3)

    assert [cluster.name for cluster in clusters] == ["ремонт/сервис", "цены", "покупка"]
    assert clusters[0].representative_query == "ремонт роботов пылесосов xiaomi"
    assert clusters[0].total_demand == 3300
    assert clusters[1].representative_query == "ремонт робота пылесоса цена"
    assert clusters[2].representative_query == "купить аккумулятор робота пылесоса"


def test_local_child_service_phrases_are_kept_and_split_into_relevant_clusters():
    top_response = {
        "results": [
            {"phrase": "консультация детского нейропсихолога", "count": "80"},
            {"phrase": "нейропсихологическая диагностика ребенка", "count": "60"},
            {"phrase": "нейропсихологическая коррекция занятия", "count": "45"},
            {"phrase": "подготовка к школе занятия", "count": "120"},
        ],
        "associations": [],
    }

    clusters = build_keyword_clusters(top_response, max_clusters=6)

    assert {cluster.name for cluster in clusters} >= {
        "консультация/запись",
        "диагностика",
        "коррекция/занятия",
    }
    assert sum(len(cluster.phrases) for cluster in clusters) == 4
