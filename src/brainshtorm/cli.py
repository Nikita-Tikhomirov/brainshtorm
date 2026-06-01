import argparse
from pathlib import Path

from brainshtorm.io import read_directions_csv, write_analysis_csv
from brainshtorm.providers import get_provider
from brainshtorm.reporting import render_markdown_report
from brainshtorm.scoring import score_direction


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="brainshtorm",
        description="Analyze up to 100 Runet niche directions.",
    )
    parser.add_argument("input_csv", help="Path to directions CSV.")
    parser.add_argument(
        "--output-dir",
        default="out/niche-analysis",
        help="Directory for analysis.csv and report.md.",
    )
    parser.add_argument(
        "--provider",
        default="demo",
        choices=["demo"],
        help="Market data provider.",
    )
    args = parser.parse_args(argv)

    directions = read_directions_csv(args.input_csv)
    provider = get_provider(args.provider)
    assessments = [
        score_direction(direction, provider.metrics_for(direction))
        for direction in directions
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_analysis_csv(output_dir / "analysis.csv", assessments)
    (output_dir / "report.md").write_text(
        render_markdown_report(assessments),
        encoding="utf-8",
    )

    print(f"Wrote {output_dir / 'analysis.csv'}")
    print(f"Wrote {output_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
