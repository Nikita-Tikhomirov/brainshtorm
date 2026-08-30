from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from typing import Any, Callable, Protocol

from brainshtorm.models import DirectionInput, MarketMetrics, NicheAssessment
from brainshtorm.project_types import (
    PROJECT_TYPE_LABELS,
    VALID_PROJECT_TYPES,
    project_type_label,
    rank_project_type_candidates,
)


AiTransport = Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]]

AI_SYSTEM_INSTRUCTIONS = (
    "Ты продуктовый SEO/leadgen-аналитик для Рунета. "
    "Давай короткие практические выводы по запуску продукта, SEO и рискам."
)


class AiClient(Protocol):
    def generate(self, prompt: str, *, max_output_tokens: int = 900) -> str:
        """Generate a text answer for one prompt."""


class AiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectTypeChoice:
    direction_id: int
    project_type: str
    confidence: float
    rationale: str


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

    def generate(self, prompt: str, *, max_output_tokens: int = 900) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": AI_SYSTEM_INSTRUCTIONS,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
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


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "anthropic/claude-opus-5",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 180,
        transport: AiTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        if not model.strip():
            raise ValueError("OpenRouter model is required")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = timeout
        self.transport = transport or _urllib_transport

    def generate(self, prompt: str, *, max_output_tokens: int = 900) -> str:
        response = self.transport(
            f"{self.base_url}/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": AI_SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "max_completion_tokens": max_output_tokens,
            },
            {
                "Authorization": f"Bearer {self.api_key}",
                "X-OpenRouter-Title": "Runet Niche Analyzer",
            },
            self.timeout,
        )
        return _extract_chat_completion_text(response, provider="OpenRouter")


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

    def generate(self, prompt: str, *, max_output_tokens: int = 900) -> str:
        body = _deepseek_body(
            model=self.model,
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            thinking_enabled=True,
        )
        response = self.transport(
            f"{self.base_url}/chat/completions",
            body,
            {"Authorization": f"Bearer {self.api_key}"},
            self.timeout,
        )
        try:
            return _extract_deepseek_text(response)
        except AiError as exc:
            if not _is_empty_deepseek_message(response):
                raise

            retry_body = _deepseek_body(
                model=self.model,
                prompt=prompt,
                max_output_tokens=max(max_output_tokens, 1600),
                thinking_enabled=False,
            )
            retry_response = self.transport(
                f"{self.base_url}/chat/completions",
                retry_body,
                {"Authorization": f"Bearer {self.api_key}"},
                self.timeout,
            )
            try:
                return _extract_deepseek_text(retry_response)
            except AiError as retry_exc:
                raise AiError(
                    f"{retry_exc}; non-thinking retry also failed; "
                    f"first_response=({_deepseek_diagnostics(response)}); "
                    f"retry_response=({_deepseek_diagnostics(retry_response)})"
                ) from retry_exc


def build_ai_prompt(assessment: NicheAssessment) -> str:
    direction = assessment.direction
    metrics = assessment.metrics
    serp = getattr(assessment, "serp_analysis", None)
    score_lines = ["score_formula: нет данных"]
    score_breakdown = getattr(assessment, "score_breakdown", None)
    if score_breakdown:
        breakdown = score_breakdown
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
    evidence_items = getattr(assessment, "evidence_items", [])
    if evidence_items:
        evidence_lines = ["strict_evidence:"]
        evidence_lines.extend(
            "- "
            f"{item.source} | {item.claim} | {item.value} | {'; '.join(item.details) or 'n/a'}"
            for item in evidence_items
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
            f"offer_gap: {getattr(serp, 'offer_gap_score', 0.0)}",
            f"offer_signals: {', '.join(getattr(serp, 'offer_signals', [])) or 'n/a'}",
            f"missing_offer_signals: {', '.join(getattr(serp, 'missing_offer_signals', [])) or 'n/a'}",
            f"competitor_types: {', '.join(getattr(serp, 'competitor_types', [])) or 'n/a'}",
            f"serp_weak_spots: {'; '.join(getattr(serp, 'weak_spots', [])) or 'n/a'}",
        ]
    cluster_lines = ["keyword_clusters: нет данных"]
    keyword_clusters = getattr(assessment, "keyword_clusters", [])
    if keyword_clusters:
        cluster_lines = ["keyword_clusters:"]
        for cluster in keyword_clusters:
            cluster_serp = getattr(cluster, "serp_analysis", None)
            if cluster_serp:
                cluster_lines.append(
                    "- "
                    f"{cluster.name}; query={cluster.representative_query}; "
                    f"demand={cluster.total_demand}; "
                    f"serp_difficulty={cluster_serp.estimated_difficulty}/10; "
                    f"serp_delta={cluster_serp.score_delta}; "
                    f"offer_gap={getattr(cluster_serp, 'offer_gap_score', 0.0)}; "
                    f"offer_signals={', '.join(getattr(cluster_serp, 'offer_signals', [])) or 'n/a'}; "
                    f"weak_spots={'; '.join(getattr(cluster_serp, 'weak_spots', [])) or 'n/a'}; "
                    f"top_domains={', '.join(cluster_serp.top_domains) or 'n/a'}"
                )
            else:
                cluster_lines.append(
                    "- "
                    f"{cluster.name}; query={cluster.representative_query}; "
                    f"demand={cluster.total_demand}; SERP=нет данных"
                )
    recommendation_lines = ["launch_recommendation: нет данных"]
    recommendation = getattr(assessment, "product_recommendation", None)
    if recommendation:
        opportunity_factors = getattr(recommendation, "opportunity_factors", [])
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
                for factor in opportunity_factors
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
            f"project_type_label: {project_type_label(direction.project_type)}",
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


def build_project_type_prompt(items: list[tuple[DirectionInput, MarketMetrics]]) -> str:
    directions: list[str] = []
    for index, (direction, metrics) in enumerate(items):
        candidates = rank_project_type_candidates(direction, metrics)
        candidate_text = "; ".join(
            f"{candidate.project_type}:{candidate.score:.1f}"
            f" ({', '.join(candidate.reasons[:3])})"
            for candidate in candidates[:4]
        )
        directions.extend(
            [
                f"- id: {index}",
                f"  direction: {direction.direction}",
                f"  region: {direction.region}",
                f"  budget_rub: {direction.budget_rub}",
                f"  max_difficulty: {direction.max_difficulty}",
                f"  demand: {metrics.demand}",
                f"  trend: {metrics.trend}",
                f"  commercial_intent: {metrics.commercial_intent}",
                f"  competition: {metrics.competition}",
                f"  estimated_difficulty: {metrics.estimated_difficulty}/10",
                f"  risk_level: {metrics.risk_level}",
                f"  local_candidates: {candidate_text}",
            ]
        )

    allowed = ", ".join(
        f"{project_type}={PROJECT_TYPE_LABELS[project_type]}"
        for project_type in sorted(VALID_PROJECT_TYPES)
    )
    return "\n".join(
        [
            "Выбери лучший тип проекта для каждой ниши Рунета.",
            "Не придумывай новые типы проекта и не добавляй факты вне входных метрик.",
            f"allowed_project_types: {allowed}",
            "Верни только JSON-массив без пояснений вне JSON.",
            "Формат каждого объекта:",
            '{"id": 0, "project_type": "seo_site", "confidence": 0.62, "rationale": "короткая причина"}',
            "",
            "directions:",
            *directions,
        ]
    )


def generate_project_type_choices(
    items: list[tuple[DirectionInput, MarketMetrics]],
    client: AiClient,
) -> dict[int, ProjectTypeChoice]:
    prompt = build_project_type_prompt(items)
    max_output_tokens = max(900, min(6000, 140 * max(1, len(items))))
    return parse_project_type_choices(
        client.generate(prompt, max_output_tokens=max_output_tokens)
    )


def parse_project_type_choices(text: str) -> dict[int, ProjectTypeChoice]:
    try:
        payload = json.loads(_json_payload(text))
    except json.JSONDecodeError as exc:
        raise AiError("AI project type response is not valid JSON") from exc

    if not isinstance(payload, list):
        raise AiError("AI project type response must be a JSON array")

    choices: dict[int, ProjectTypeChoice] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        direction_id = _int_value(item.get("id"))
        project_type = item.get("project_type")
        if direction_id is None or project_type not in VALID_PROJECT_TYPES:
            continue
        choices[direction_id] = ProjectTypeChoice(
            direction_id=direction_id,
            project_type=project_type,
            confidence=_clamp_float(_float_value(item.get("confidence")), 0.0, 1.0),
            rationale=_clean_ai_text(str(item.get("rationale") or "")),
        )
    return choices


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
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", str(exc))
        raise AiError(f"AI provider request failed: {reason}") from exc
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
    return _extract_chat_completion_text(response, provider="DeepSeek")


def _extract_chat_completion_text(
    response: dict[str, Any],
    *,
    provider: str,
) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise AiError(f"{provider} returned empty response")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise AiError(f"{provider} returned invalid response")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise AiError(f"{provider} returned invalid message")
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        if provider == "DeepSeek":
            raise AiError(f"DeepSeek returned empty message ({_deepseek_diagnostics(response)})")
        raise AiError(f"{provider} returned empty message")
    return _clean_ai_text(text)


def _deepseek_body(
    *,
    model: str,
    prompt: str,
    max_output_tokens: int,
    thinking_enabled: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": prompt},
        ],
        "thinking": {"type": "enabled" if thinking_enabled else "disabled"},
        "stream": False,
        "max_tokens": max_output_tokens,
    }
    if thinking_enabled:
        body["reasoning_effort"] = "high"
    return body


def _is_empty_deepseek_message(response: dict[str, Any]) -> bool:
    message = _first_deepseek_message(response)
    if not isinstance(message, dict):
        return False
    text = message.get("content")
    return not isinstance(text, str) or not text.strip()


def _deepseek_diagnostics(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else None
    message = first_choice.get("message") if isinstance(first_choice, dict) else None
    finish_reason = first_choice.get("finish_reason") if isinstance(first_choice, dict) else None
    reasoning_content = message.get("reasoning_content") if isinstance(message, dict) else None
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    content_length = len(content.strip()) if isinstance(content, str) else 0
    return (
        f"finish_reason={finish_reason}; "
        f"content_length={content_length}; "
        f"reasoning_content_present={bool(reasoning_content)}; "
        f"tool_calls_present={bool(tool_calls)}"
    )


def _first_deepseek_message(response: dict[str, Any]) -> Any:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    return first_choice.get("message")


def _supports_openai_reasoning(model: str) -> bool:
    normalized = model.lower()
    return normalized.startswith("gpt-5") or normalized.startswith("o")


def _clean_ai_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def _json_payload(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, value)), 2)
