import csv
from pathlib import Path
from typing import Iterable

from brainshtorm.models import DirectionInput, NicheAssessment


REQUIRED_COLUMNS = {
    "direction",
    "region",
    "budget_rub",
    "max_difficulty",
    "project_type",
}

MAX_BATCH_SIZE = 100


def read_directions_csv(path: str | Path) -> list[DirectionInput]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fieldnames)
        if missing:
            raise ValueError(f"missing required columns: {', '.join(missing)}")

        directions = [_parse_row(row, index + 2) for index, row in enumerate(reader)]

    if len(directions) > MAX_BATCH_SIZE:
        raise ValueError(f"CSV batch must contain at most {MAX_BATCH_SIZE} directions")

    if not directions:
        raise ValueError("CSV batch must contain at least one direction")

    return directions


def write_analysis_csv(path: str | Path, assessments: Iterable[NicheAssessment]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "direction",
                "region",
                "budget_rub",
                "max_difficulty",
                "project_type",
                "score",
                "verdict",
                "demand",
                "trend",
                "competition",
                "estimated_launch_budget",
                "estimated_difficulty",
                "explanation",
                "product_idea",
            ],
        )
        writer.writeheader()
        for assessment in assessments:
            direction = assessment.direction
            metrics = assessment.metrics
            writer.writerow(
                {
                    "direction": direction.direction,
                    "region": direction.region,
                    "budget_rub": direction.budget_rub,
                    "max_difficulty": direction.max_difficulty,
                    "project_type": direction.project_type,
                    "score": f"{assessment.score:.1f}",
                    "verdict": assessment.verdict,
                    "demand": metrics.demand,
                    "trend": f"{metrics.trend:.2f}",
                    "competition": f"{metrics.competition:.2f}",
                    "estimated_launch_budget": metrics.estimated_launch_budget,
                    "estimated_difficulty": metrics.estimated_difficulty,
                    "explanation": assessment.explanation,
                    "product_idea": assessment.product_idea,
                }
            )


def _parse_row(row: dict[str, str], line_number: int) -> DirectionInput:
    direction = _required_text(row, "direction", line_number)
    region = _required_text(row, "region", line_number)
    project_type = _required_text(row, "project_type", line_number)
    budget_rub = _positive_int(row.get("budget_rub", ""), "budget_rub", line_number)
    max_difficulty = _bounded_int(
        row.get("max_difficulty", ""),
        "max_difficulty",
        line_number,
        minimum=1,
        maximum=10,
    )

    return DirectionInput(
        direction=direction,
        region=region,
        budget_rub=budget_rub,
        max_difficulty=max_difficulty,
        project_type=project_type,
    )


def _required_text(row: dict[str, str], column: str, line_number: int) -> str:
    value = (row.get(column) or "").strip()
    if not value:
        raise ValueError(f"{column} is required at line {line_number}")
    return value


def _positive_int(value: str, column: str, line_number: int) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{column} must be an integer at line {line_number}") from exc
    if parsed <= 0:
        raise ValueError(f"{column} must be positive at line {line_number}")
    return parsed


def _bounded_int(
    value: str,
    column: str,
    line_number: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    parsed = _positive_int(value, column, line_number)
    if parsed < minimum or parsed > maximum:
        raise ValueError(
            f"{column} must be between {minimum} and {maximum} at line {line_number}"
        )
    return parsed
