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
        if assessment.product_recommendation:
            recommendation = assessment.product_recommendation
            lines.extend(
                [
                    "",
                    "Launch recommendation:",
                    "",
                    f"- Product: {recommendation.product_title}",
                    f"- Launch type: {recommendation.launch_type}",
                    f"- Opportunity score: `{recommendation.opportunity_score:.1f}`",
                    f"- Audience: {recommendation.target_audience}",
                    f"- Offer: {recommendation.offer}",
                    f"- Why it can rank: {recommendation.why_this_can_rank}",
                    f"- First test: {recommendation.first_test}",
                    "",
                    "Landing pages:",
                    "",
                ]
            )
            lines.extend(f"- {page}" for page in recommendation.landing_pages)
            lines.extend(["", "Traffic plan:", ""])
            lines.extend(f"- {step}" for step in recommendation.traffic_plan)
            lines.extend(["", "Evidence:", ""])
            lines.extend(f"- {item}" for item in recommendation.evidence)
        if assessment.serp_analysis:
            serp = assessment.serp_analysis
            lines.extend(
                [
                    "",
                    "SERP analysis:",
                    "",
                    f"- SERP difficulty: {serp.estimated_difficulty}/10",
                    f"- SERP score delta: `{serp.score_delta:.1f}`",
                    f"- SERP summary: {serp.summary}",
                    f"- Top domains: {', '.join(serp.top_domains) or 'n/a'}",
                ]
            )
        if assessment.keyword_clusters:
            lines.extend(["", "Keyword clusters:", ""])
            for cluster in assessment.keyword_clusters:
                serp = cluster.serp_analysis
                if serp:
                    lines.append(
                        "- "
                        f"{cluster.name}: `{cluster.representative_query}`; "
                        f"demand {cluster.total_demand}; "
                        f"difficulty {serp.estimated_difficulty}/10; "
                        f"delta `{serp.score_delta}`; "
                        f"top {', '.join(serp.top_domains) or 'n/a'}"
                    )
                else:
                    lines.append(
                        "- "
                        f"{cluster.name}: `{cluster.representative_query}`; "
                        f"demand {cluster.total_demand}; SERP not checked"
                    )
        if assessment.ai_insight:
            lines.extend(
                [
                    "",
                    "AI verdict:",
                    "",
                    assessment.ai_insight,
                ]
            )
        lines.extend(["", "Risks:", ""])
        lines.extend(f"- {risk}" for risk in assessment.risks)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
