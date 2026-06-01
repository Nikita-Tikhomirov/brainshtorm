from pathlib import Path

import pytest

from brainshtorm.io import read_directions_csv


def write_csv(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_read_directions_accepts_valid_csv(tmp_path):
    path = tmp_path / "directions.csv"
    write_csv(
        path,
        "direction,region,budget_rub,max_difficulty,project_type\n"
        "ремонт роботов пылесосов,Москва,150000,6,leadgen\n",
    )

    directions = read_directions_csv(path)

    assert len(directions) == 1
    assert directions[0].direction == "ремонт роботов пылесосов"
    assert directions[0].region == "Москва"
    assert directions[0].budget_rub == 150000
    assert directions[0].max_difficulty == 6
    assert directions[0].project_type == "leadgen"


def test_read_directions_rejects_missing_columns(tmp_path):
    path = tmp_path / "directions.csv"
    write_csv(path, "direction,budget_rub\nремонт техники,100000\n")

    with pytest.raises(ValueError, match="missing required columns"):
        read_directions_csv(path)


def test_read_directions_rejects_more_than_100_rows(tmp_path):
    path = tmp_path / "directions.csv"
    rows = [
        f"направление {index},Россия,100000,6,seo_site"
        for index in range(101)
    ]
    write_csv(
        path,
        "direction,region,budget_rub,max_difficulty,project_type\n"
        + "\n".join(rows)
        + "\n",
    )

    with pytest.raises(ValueError, match="at most 100"):
        read_directions_csv(path)


def test_read_directions_rejects_invalid_budget(tmp_path):
    path = tmp_path / "directions.csv"
    write_csv(
        path,
        "direction,region,budget_rub,max_difficulty,project_type\n"
        "ремонт техники,Россия,0,6,seo_site\n",
    )

    with pytest.raises(ValueError, match="budget_rub"):
        read_directions_csv(path)


def test_read_directions_rejects_invalid_difficulty(tmp_path):
    path = tmp_path / "directions.csv"
    write_csv(
        path,
        "direction,region,budget_rub,max_difficulty,project_type\n"
        "ремонт техники,Россия,100000,11,seo_site\n",
    )

    with pytest.raises(ValueError, match="max_difficulty"):
        read_directions_csv(path)
