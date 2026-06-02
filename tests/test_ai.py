from types import SimpleNamespace

from brainshtorm.ai import (
    AiError,
    DeepSeekClient,
    OpenAiClient,
    apply_ai_insight,
    build_ai_prompt,
    build_project_type_prompt,
    generate_ai_insight,
    parse_project_type_choices,
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
from brainshtorm.scoring import score_direction


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
            summary="оценочная сложность выдачи 8/10; агрегаторов в топе: 1; offer gap: 0.55.",
            offer_signal_score=0.3,
            offer_gap_score=0.55,
            competitor_types=["агрегаторы: 1"],
            offer_signals=["цена"],
            missing_offer_signals=["гарантия"],
            weak_spots=["В топе заметная доля агрегаторов."],
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
    assert "offer_gap: 0.55" in prompt
    assert "missing_offer_signals: гарантия" in prompt


def test_build_ai_prompt_handles_legacy_assessment_without_strict_fields():
    assessment = SimpleNamespace(
        direction=DirectionInput("кактусы", "Россия", 150000, 6, "seo_site"),
        metrics=MarketMetrics(1200, 0.1, 1.0, 0.2, 0.4, 60000, 4, 0.1, 0.0),
        score=62.5,
        verdict="review",
        product_idea="Контентный сайт",
        risks=["Проверить спрос"],
        serp_analysis=None,
        keyword_clusters=[],
        product_recommendation=None,
    )

    prompt = build_ai_prompt(assessment)

    assert "кактусы" in prompt
    assert "score_formula: нет данных" in prompt
    assert "strict_evidence: нет данных" in prompt


def test_build_ai_prompt_contains_strict_evidence_contract():
    direction = DirectionInput(
        direction="ремонт роботов пылесосов",
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )
    assessment = score_direction(
        direction,
        MarketMetrics(
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
    )

    prompt = build_ai_prompt(assessment)

    assert "Не придумывай факты" in prompt
    assert "strict_evidence:" in prompt
    assert "Wordstat | Спрос | 9000" in prompt
    assert "score_formula:" in prompt


def test_build_ai_prompt_includes_resolved_auto_project_type():
    direction = DirectionInput(
        direction="курсы нейросетей",
        region="Россия",
        budget_rub=150000,
        max_difficulty=6,
        project_type="auto",
    )
    assessment = score_direction(
        direction,
        MarketMetrics(
            demand=6400,
            trend=0.18,
            regional_affinity=1.1,
            commercial_intent=0.78,
            competition=0.45,
            estimated_launch_budget=999999,
            estimated_difficulty=5,
            seasonality=0.1,
            risk_level=0.1,
        ),
    )

    prompt = build_ai_prompt(assessment)

    assert "project_type: infoproduct" in prompt
    assert "project_type_label: Инфопродукт" in prompt


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
    assert calls[0][1]["max_output_tokens"] == 900
    assert calls[0][2]["Authorization"] == "Bearer openai-secret"


def test_openai_client_allows_custom_max_output_tokens():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append((url, body, headers, timeout))
        return {"output_text": "[]"}

    client = OpenAiClient(
        api_key="openai-secret",
        model="gpt-5.5",
        transport=transport,
    )

    client.generate("prompt", max_output_tokens=2400)

    assert calls[0][1]["max_output_tokens"] == 2400


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
    assert calls[0][1]["max_tokens"] == 900
    assert calls[0][1]["messages"][1]["content"] == "prompt"
    assert calls[0][1]["thinking"] == {"type": "enabled"}
    assert calls[0][2]["Authorization"] == "Bearer deepseek-secret"


def test_deepseek_client_retries_empty_thinking_message_without_thinking():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append(body)
        if len(calls) == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": "",
                            "reasoning_content": "thinking consumed the budget",
                        },
                    }
                ],
            }
        return {
            "choices": [
                {"finish_reason": "stop", "message": {"content": "Вердикт: брать в тест."}},
            ],
        }

    client = DeepSeekClient(
        api_key="deepseek-secret",
        model="deepseek-v4-pro",
        transport=transport,
    )

    result = client.generate("prompt", max_output_tokens=900)

    assert result == "Вердикт: брать в тест."
    assert calls[0]["thinking"] == {"type": "enabled"}
    assert calls[1]["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in calls[1]
    assert calls[1]["max_tokens"] >= 1600


def test_deepseek_client_empty_message_error_has_diagnostics_after_retry():
    calls = []

    def transport(url, body, headers, timeout):
        calls.append(body)
        return {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "",
                        "reasoning_content": "thinking only",
                    },
                }
            ],
        }

    client = DeepSeekClient(
        api_key="deepseek-secret",
        model="deepseek-v4-pro",
        transport=transport,
    )

    try:
        client.generate("prompt", max_output_tokens=900)
    except AiError as exc:
        message = str(exc)
    else:
        raise AssertionError("DeepSeekClient should raise AiError")

    assert len(calls) == 2
    assert "finish_reason=length" in message
    assert "reasoning_content_present=True" in message
    assert "non-thinking retry" in message


def test_build_project_type_prompt_contains_allowed_types_and_candidates():
    direction = DirectionInput("ремонт роботов пылесосов", "Россия", 150000, 6, "auto")
    metrics = MarketMetrics(8500, 0.2, 1.0, 0.82, 0.42, 999999, 5, 0.2, 0.1)

    prompt = build_project_type_prompt([(direction, metrics)])

    assert "allowed_project_types" in prompt
    assert "leadgen" in prompt
    assert "local_candidates" in prompt
    assert "ремонт роботов пылесосов" in prompt
    assert "JSON" in prompt


def test_parse_project_type_choices_accepts_plain_or_fenced_json():
    choices = parse_project_type_choices(
        """
        ```json
        [
          {"id": 0, "project_type": "leadgen", "confidence": 0.72, "rationale": "service demand"}
        ]
        ```
        """
    )

    assert choices[0].direction_id == 0
    assert choices[0].project_type == "leadgen"
    assert choices[0].confidence == 0.72
    assert choices[0].rationale == "service demand"


def test_parse_project_type_choices_ignores_invalid_types():
    choices = parse_project_type_choices(
        '[{"id": 0, "project_type": "blog", "confidence": 0.9, "rationale": "bad"}]'
    )

    assert choices == {}


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
