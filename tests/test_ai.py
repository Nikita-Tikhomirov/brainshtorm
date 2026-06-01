from brainshtorm.ai import (
    DeepSeekClient,
    OpenAiClient,
    apply_ai_insight,
    build_ai_prompt,
    generate_ai_insight,
)
from brainshtorm.models import (
    DirectionInput,
    MarketMetrics,
    NicheAssessment,
    ProductRecommendation,
    SerpAnalysis,
    SerpResult,
    TAKE,
)


def make_assessment() -> NicheAssessment:
    return NicheAssessment(
        direction=DirectionInput(
            direction="ремонт роботов пылесосов",
            region="Москва",
            budget_rub=150000,
            max_difficulty=6,
            project_type="leadgen",
        ),
        metrics=MarketMetrics(
            demand=9000,
            trend=0.4,
            regional_affinity=1.2,
            commercial_intent=0.85,
            competition=0.45,
            estimated_launch_budget=125000,
            estimated_difficulty=4,
            seasonality=0.2,
            risk_level=0.0,
        ),
        score=78.0,
        verdict=TAKE,
        explanation="Спрос достаточный.",
        product_idea="Лидогенератор заявок.",
        promotion_steps=["Собрать семантику."],
        risks=["Проверить экономику лида."],
        product_recommendation=ProductRecommendation(
            product_title="Лидогенератор ремонта роботов пылесосов",
            launch_type="Лидогенератор услуги",
            target_audience="Владельцы роботов-пылесосов",
            opportunity_score=82.0,
            offer="Диагностика и ремонт с подбором мастера",
            why_this_can_rank="Есть слабый коммерческий кластер.",
            landing_pages=["Страница под `ремонт робота пылесоса цена`"],
            traffic_plan=["SEO по кластеру цен"],
            first_test="Запустить 3 посадочные страницы.",
            evidence=["Спрос 9000"],
            risks=["Следить за стоимостью лида"],
        ),
        serp_analysis=SerpAnalysis(
            query="ремонт роботов пылесосов",
            results=[
                SerpResult(
                    title="Профи",
                    url="https://profi.ru/remont/robot-pylesos/",
                    domain="profi.ru",
                    snippet="Мастера и цены.",
                )
            ],
            results_count=1,
            top_domains=["profi.ru"],
            aggregator_count=1,
            marketplace_count=0,
            competitor_score=0.8,
            estimated_difficulty=8,
            score_delta=-7.0,
            summary="оценочная сложность выдачи 8/10; агрегаторов в топе: 1.",
        ),
    )


def test_build_ai_prompt_contains_metrics_serp_and_output_contract():
    prompt = build_ai_prompt(make_assessment())

    assert "ремонт роботов пылесосов" in prompt
    assert "score: 78.0" in prompt
    assert "top_domains: profi.ru" in prompt
    assert "Ответь на русском" in prompt
    assert "Вердикт" in prompt
    assert "launch_recommendation" in prompt
    assert "Лидогенератор ремонта роботов пылесосов" in prompt


def test_openai_client_posts_responses_request_and_returns_output_text():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append((url, body, headers, timeout))
        return {"output_text": "Вердикт: брать в тест."}

    client = OpenAiClient(
        api_key="openai-secret",
        model="gpt-5.5",
        transport=transport,
    )

    result = client.generate("prompt")

    assert result == "Вердикт: брать в тест."
    assert calls[0][0] == "https://api.openai.com/v1/responses"
    assert calls[0][1]["model"] == "gpt-5.5"
    assert calls[0][1]["input"] == "prompt"
    assert calls[0][2]["Authorization"] == "Bearer openai-secret"


def test_deepseek_client_posts_chat_completion_request_and_returns_message():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append((url, body, headers, timeout))
        return {
            "choices": [
                {"message": {"content": "Продукт: каталог подрядчиков."}},
            ],
        }

    client = DeepSeekClient(
        api_key="deepseek-secret",
        model="deepseek-v4-pro",
        transport=transport,
    )

    result = client.generate("prompt")

    assert result == "Продукт: каталог подрядчиков."
    assert calls[0][0] == "https://api.deepseek.com/chat/completions"
    assert calls[0][1]["model"] == "deepseek-v4-pro"
    assert calls[0][1]["messages"][1]["content"] == "prompt"
    assert calls[0][1]["thinking"] == {"type": "enabled"}
    assert calls[0][2]["Authorization"] == "Bearer deepseek-secret"


def test_generate_ai_insight_uses_assessment_prompt():
    prompts = []

    class FakeClient:
        def generate(self, prompt):
            prompts.append(prompt)
            return "Вердикт: брать в тест."

    insight = generate_ai_insight(make_assessment(), FakeClient())

    assert insight == "Вердикт: брать в тест."
    assert "ремонт роботов пылесосов" in prompts[0]


def test_apply_ai_insight_adds_clean_text_to_assessment():
    assessment = make_assessment()

    adjusted = apply_ai_insight(assessment, "\n\nВердикт: брать в тест.\n")

    assert adjusted.ai_insight == "Вердикт: брать в тест."
    assert adjusted.score == assessment.score
    assert adjusted.serp_analysis == assessment.serp_analysis
