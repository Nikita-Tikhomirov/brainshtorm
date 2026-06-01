from brainshtorm.cli import main


SAMPLE_CSV = (
    "direction,region,budget_rub,max_difficulty,project_type\n"
    "ремонт роботов пылесосов,Москва,150000,6,leadgen\n"
    "курсы нейросетей,Россия,100000,7,infoproduct\n"
)


def test_cli_writes_csv_and_markdown(tmp_path):
    input_path = tmp_path / "directions.csv"
    output_dir = tmp_path / "out"
    input_path.write_text(SAMPLE_CSV, encoding="utf-8")

    exit_code = main([str(input_path), "--output-dir", str(output_dir), "--provider", "demo"])

    assert exit_code == 0
    assert (output_dir / "analysis.csv").exists()
    assert (output_dir / "report.md").exists()
    assert "ремонт роботов пылесосов" in (output_dir / "report.md").read_text(encoding="utf-8")
