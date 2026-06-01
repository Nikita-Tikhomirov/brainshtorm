import re

from brainshtorm.io import MAX_BATCH_SIZE
from brainshtorm.models import DirectionInput


LIST_PREFIX_RE = re.compile(r"^\s*(?:[-*•]\s*|\d+[\).]\s*)")


def parse_pasted_directions(
    text: str,
    *,
    region: str,
    budget_rub: int,
    max_difficulty: int,
    project_type: str,
) -> list[DirectionInput]:
    directions = [
        DirectionInput(
            direction=_clean_direction(line),
            region=region.strip(),
            budget_rub=budget_rub,
            max_difficulty=max_difficulty,
            project_type=project_type,
        )
        for line in text.splitlines()
        if _clean_direction(line)
    ]

    if not directions:
        raise ValueError("Paste at least one direction")
    if len(directions) > MAX_BATCH_SIZE:
        raise ValueError(f"Paste at most {MAX_BATCH_SIZE} directions")
    if budget_rub <= 0:
        raise ValueError("budget_rub must be positive")
    if max_difficulty < 1 or max_difficulty > 10:
        raise ValueError("max_difficulty must be between 1 and 10")
    if not region.strip():
        raise ValueError("region is required")
    return directions


def _clean_direction(line: str) -> str:
    cleaned = LIST_PREFIX_RE.sub("", line.strip())
    return re.sub(r"\s+", " ", cleaned).strip()
