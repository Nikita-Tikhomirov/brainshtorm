import pytest

from brainshtorm.app_inputs import parse_pasted_directions


def test_parse_pasted_directions_builds_batch_from_plain_lines():
    directions = parse_pasted_directions(
        """
        ремонт роботов пылесосов
        - курсы нейросетей
        3. запчасти для квадроциклов
        """,
        region="Москва",
        budget_rub=150000,
        max_difficulty=6,
        project_type="leadgen",
    )

    assert [item.direction for item in directions] == [
        "ремонт роботов пылесосов",
        "курсы нейросетей",
        "запчасти для квадроциклов",
    ]
    assert all(item.region == "Москва" for item in directions)
    assert all(item.budget_rub == 150000 for item in directions)


def test_parse_pasted_directions_rejects_empty_input():
    with pytest.raises(ValueError, match="at least one"):
        parse_pasted_directions(
            " \n ",
            region="Россия",
            budget_rub=100000,
            max_difficulty=5,
            project_type="seo_site",
        )


def test_parse_pasted_directions_rejects_more_than_100_items():
    pasted = "\n".join(f"направление {index}" for index in range(101))

    with pytest.raises(ValueError, match="at most 100"):
        parse_pasted_directions(
            pasted,
            region="Россия",
            budget_rub=100000,
            max_difficulty=5,
            project_type="seo_site",
        )
