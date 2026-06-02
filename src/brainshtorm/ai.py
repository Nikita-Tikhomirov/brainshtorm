from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any, Callable, Protocol

from brainshtorm.models import NicheAssessment


AiTransport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]

AI_SYSTEM_INSTRUCTIONS = (
    "Ты продуктовый SEO/leadgen-аналитик для Рунета. "
    "Давай короткие практические выводы по запуску продукта, SEO и рискам."
)


class AiClient(Protocol):
    def generate(self, prompt: str) -> str:
        """Generate a text answer for one prompt."""


class AiError(RuntimeError):
    pass


class OpenAiClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5.5",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 180,
        transport: AiTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is required")
        if not model.strip():
            raise ValueError("OpenAI model is required")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = timeout
        self.transport = transport or _urllib_transport

    def generate(self, prompt: str) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": AI_SYSTEM_INSTRUCTIONS,
            "input": prompt,
            "max_output_tokens": 900,
        }
        if _supports_openai_reasoning(self.model):
            body["reasoning"] = {"effort": "medium"}

        response = self.transport(
            f"{self.base_url}/responses",
            body,
            {"Authorization": f"Bearer {self.api_key}"},
            self.timeout,
        )
        return _extract_openai_text(response)


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-pro",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 180,
        transport: AiTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API key is required")
        if not model.strip():
            raise ValueError("DeepSeek model is required")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = timeout
        self.transport = transport or _urllib_transport

    def generate(self, prompt: str) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": AI_SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": prompt},
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "stream": False,
            "max_tokens": 900,
        }
        response = self.transport(
            f"{self.base_url}/chat/completions",
            body,
            {"Authorization": f"Bearer {self.api_key}"},
            self.timeout,
        )
        return _extract_deepseek_text(response)


def build_ai_prompt(assessment: NicheAssessment) -> str:
    direction = assessment.direction
    metrics = assessment.metrics
    serp = assessment.serp_analysis
    score_lines = ["score_formula: нет данных"]
    if assessment.score_breakdown:
        breakdown = assessment.score_breakdown
        score_lines = [
            "score_formula:",
            f"formula_version: {breakdown.formula_version}",
            f"formula_final_score: {breakdown.final_score}",
            f"formula_confidence: {breakdown.confidence}",
            f"formula_confidence_notes: {'; '.join(breakdown.confidence_notes)}",
        ]
        score_lines.extend(
            "- "
            f"{factor.key}; raw={factor.raw_value}; normalized={factor.normalized_score}; "
            f"weight={factor.weight}; contribution={factor.contribution}; evidence={factor.evidence}"
            for factor in breakdown.factors
        )
    evidence_lines = ["strict_evidence: нет данных"]
    if assessment.evidence_items:
        evidence_lines = ["strict_evidence:"]
        evidence_lines.extend(
            "- "
            f"{item.source} | {item.claim} | {item.value} | {'; '.join(item.details) or 'n/a'}"
            for item in assessment.evidence_items
        )
    serp_lines = [
        "SERP: нет данных",
    ]
    if serp:
        serp_lines = [
            f"serp_difficulty: {serp.estimated_difficulty}/10",
            f"serp_delta: {serp.score_delta}",
            f"serp_summary: {serp.summary}",
            f"top_domains: {', '.join(serp.top_domains) or 'n/a'}",
            f"offer_gap: {serp.offer_gap_score}",
            f"offer_signals: {', '.join(serp.offer_signals) or 'n/a'}",
            f"missing_offer_signals: {', '.join(serp.missing_offer_signals) or 'n/a'}",
            f"competitor_types: {', '.join(serp.competitor_types) or 'n/a'}",
            f"serp_weak_spots: {'; '.join(serp.weak_spots) or 'n/a'}",
        ]
    cluster_lines = ["keyword_clusters: нет данных"]
    if assessment.keyword_clusters:
        cluster_lines = ["keyword_clusters:"]
        for cluster in assessment.keyword_clusters:
            cluster_serp = cluster.serp_analysis
            if cluster_serp:
                cluster_lines.append(
                    "- "
                    f"{cluster.name}; query={cluster.representative_query}; "
                    f"demand={cluster.total_demand}; "
                    f"serp_difficulty={cluster_serp.estimated_difficulty}/10; "
                    f"serp_delta={cluster_serp.score_delta}; "
                    f"offer_gap={cluster_serp.offer_gap_score}; "
                    f"offer_signals={', '.join(cluster_serp.offer_signals) or 'n/a'}; "
                    f"weak_spots={'; '.join(cluster_serp.weak_spots) or 'n/a'}; "
                    f"top_domains={', '.join(cluster_serp.top_domains) or 'n/a'}"
                )
            else:
                cluster_lines.append(
                    "- "
                    f"{cluster.name}; query={cluster.representative_query}; "
                    f"demand={cluster.total_demand}; SERP=нет данных"
                )
    recommendation_lines = ["launch_recommendation: нет данных"]
    if assessment.product_recommendation:
        recommendation = assessment.product_recommendation
        recommendation_lines = [
            "launch_recommendation:",
            f"product_title: {recommendation.product_title}",
            f"launch_type: {recommendation.launch_type}",
            f"target_audience: {recommendation.target_audience}",
            f"opportunity_score: {recommendation.opportunity_score}",
            f"offer: {recommendation.offer}",
            f"why_this_can_rank: {recommendation.why_this_can_rank}",
            f"landing_pages: {'; '.join(recommendation.landing_pages)}",
            f"traffic_plan: {'; '.join(recommendation.traffic_plan)}",
            f"first_test: {recommendation.first_test}",
            f"evidence: {'; '.join(recommendation.evidence)}",
            f"recommendation_risks: {'; '.join(recommendation.risks)}",
            "opportunity_formula: "
            + "; ".join(
                f"{factor.key} raw={factor.raw_value} contribution={factor.contribution} evidence={factor.evidence}"
                for factor in recommendation.opportunity_factors
            ),
        ]

    return "\n".join(
        [
            "Нужно дать короткий практический вердикт по нише на основе метрик.",
            "Не придумывай факты, запросы, частотность, домены, риски или выводы, которых нет в strict_evidence, SERP, keyword_clusters или score_formula.",
            "Если данных для вывода нет, прямо напиши: нет данных.",
            "Ответь на русском, без воды, в таком формате:",
            "Вердикт: ...",
            "Продукт: ...",
            "Продвижение: ...",
            "Риски: ...",
            "Первый тест: ...",
            "",
            "Данные ниши:",
            f"direction: {direction.direction}",
            f"region: {direction.region}",
            f"project_type: {direction.project_type}",
            f"budget_rub: {direction.budget_rub}",
            f"max_difficulty: {direction.max_difficulty}",
            f"score: {assessment.score}",
            f"verdict: {assessment.verdict}",
            f"demand: {metrics.demand}",
            f"trend: {metrics.trend}",
            f"competition: {metrics.competition}",
            f"commercial_intent: {metrics.commercial_intent}",
            f"estimated_budget: {metrics.estimated_launch_budget}",
            f"estimated_difficulty: {metrics.estimated_difficulty}/10",
            *score_lines,
            *evidence_lines,
            *serp_lines,
            *cluster_lines,
            *recommendation_lines,
            f"existing_product_idea: {assessment.product_idea}",
            f"known_risks: {'; '.join(assessment.risks)}",
        ]
    )


def generate_ai_insight(assessment: NicheAssessment, client: AiClient) -> str:
    return _clean_ai_text(client.generate(build_ai_prompt(assessment)))


def apply_ai_insight(assessment: NicheAssessment, insight: str) -> NicheAssessment:
    return replace(assessment, ai_insight=_clean_ai_text(insight))


def _urllib_transport(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json", **headers}
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AiError(f"AI provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AiError(f"AI provider request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise AiError("AI provider returned invalid JSON") from exc


def _extract_openai_text(response: dict[str, Any]) -> str:
    direct_text = response.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return _clean_ai_text(direct_text)

    chunks: list[str] = []
    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text)

    if chunks:
        return _clean_ai_text("\n".join(chunks))
    raise AiError("OpenAI returned empty response")


def _extract_deepseek_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiError("DeepSeek returned empty response")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AiError("DeepSeek returned invalid response")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AiError("DeepSeek returned invalid message")
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        raise AiError("DeepSeek returned empty message")
    return _clean_ai_text(text)


def _supports_openai_reasoning(model: str) -> bool:
    normalized = model.lower()
    return normalized.startswith("gpt-5") or normalized.startswith("o")


def _clean_ai_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()
