from collections import Counter

from brainshtorm.models import NicheAssessment


def render_markdown_report(assessments: list[NicheAssessment]) -> str:
    ranked = sorted(assessments, key=lambda item: item.score, reverse=True)
    counts = Counter(item.verdict for item in ranked)
    lines = [
        "# Runet Niche Analyzer Report",
        "",
        "## Summary",
        "",
        f"- Total directions: {len(ranked)}",
        f"- take: {counts.get('take', 0)}",
        f"- review: {counts.get('review', 0)}",
        f"- skip: {counts.get('skip', 0)}",
        "",
        "## Ranked Niches",
        "",
    ]

    for index, assessment in enumerate(ranked, start=1):
        direction = assessment.direction
        metrics = assessment.metrics
        lines.extend(
            [
                f"### {index}. {direction.direction}",
                "",
                f"- Verdict: `{assessment.verdict}`",
                f"- Score: `{assessment.score:.1f}`",
                f"- Region: {direction.region}",
                f"- Demand: {metrics.demand}",
                f"- Trend: {metrics.trend:.2f}",
                f"- Competition: {metrics.competition:.2f}",
                f"- Estimated launch budget: {metrics.estimated_launch_budget} ₽",
                f"- Estimated difficulty: {metrics.estimated_difficulty}/10",
                f"- Product idea: {assessment.product_idea}",
                f"- Explanation: {assessment.explanation}",
                "",
                "Promotion steps:",
                "",
            ]
        )
        lines.extend(f"- {step}" for step in assessment.promotion_steps)
        lines.extend(["", "Risks:", ""])
        lines.extend(f"- {risk}" for risk in assessment.risks)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
