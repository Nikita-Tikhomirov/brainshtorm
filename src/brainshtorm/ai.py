from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import replace
from typing import Any, Callable, Protocol

from brainshtorm.models import NicheAssessment


OllamaTransport = Callable[[str, dict[str, Any], int], dict[str, Any]]


class AiClient(Protocol):
    def generate(self, prompt: str) -> str:
        """Generate a text answer for one prompt."""


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:8b",
        timeout: int = 120,
        transport: OllamaTransport | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Ollama URL is required")
        if not model.strip():
            raise ValueError("Ollama model is required")
        self.base_url = base_url.strip().rstrip("/")
        self.model = model.strip()
        self.timeout = timeout
        self.transport = transport or _urllib_transport

    def generate(self, prompt: str) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_ctx": 4096,
            },
        }
        response = self.transport(f"{self.base_url}/api/generate", body, self.timeout)
        text = response.get("response")
        if not isinstance(text, str) or not text.strip():
            raise OllamaError("Ollama returned empty response")
        return _clean_ai_text(text)


def build_ai_prompt(assessment: NicheAssessment) -> str:
    direction = assessment.direction
    metrics = assessment.metrics
    serp = assessment.serp_analysis
    serp_lines = [
        "SERP: нет данных",
    ]
    if serp:
        serp_lines = [
            f"serp_difficulty: {serp.estimated_difficulty}/10",
            f"serp_delta: {serp.score_delta}",
            f"serp_summary: {serp.summary}",
            f"top_domains: {', '.join(serp.top_domains) or 'n/a'}",
        ]

    return "\n".join(
        [
            "Ты продуктовый SEO/leadgen-аналитик для Рунета.",
            "Нужно дать короткий практический вердикт по нише на основе метрик.",
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
            *serp_lines,
            f"existing_product_idea: {assessment.product_idea}",
            f"known_risks: {'; '.join(assessment.risks)}",
        ]
    )


def generate_ai_insight(assessment: NicheAssessment, client: AiClient) -> str:
    return _clean_ai_text(client.generate(build_ai_prompt(assessment)))


def apply_ai_insight(assessment: NicheAssessment, insight: str) -> NicheAssessment:
    return replace(assessment, ai_insight=_clean_ai_text(insight))


def _urllib_transport(url: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(f"Ollama HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"Ollama request failed: {exc.reason}") from exc


def _clean_ai_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()
