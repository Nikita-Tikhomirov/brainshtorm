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
        if assessment.score_breakdown or assessment.evidence_items:
            lines.extend(["", "Strict evidence:", ""])
            if assessment.score_breakdown:
                breakdown = assessment.score_breakdown
                lines.extend(
                    [
                        "Score formula:",
                        "",
                        f"- Formula: `{breakdown.formula_version}`",
                        f"- Final score: `{breakdown.final_score:.1f}`",
                        f"- Confidence: `{breakdown.confidence:.2f}`",
                    ]
                )
                lines.extend(f"- Confidence note: {note}" for note in breakdown.confidence_notes)
                lines.append("")
                lines.extend(
                    "- "
                    f"{factor.key}: raw `{factor.raw_value}`; "
                    f"normalized `{factor.normalized_score:.1f}`; "
                    f"weight `{factor.weight:.2f}`; "
                    f"contribution `{factor.contribution:+.1f}`; "
                    f"evidence: {factor.evidence}"
                    for factor in breakdown.factors
                )
            if assessment.evidence_items:
                lines.extend(["", "Evidence ledger:", ""])
                for item in assessment.evidence_items:
                    detail_text = "; ".join(item.details)
                    suffix = f" ({detail_text})" if detail_text else ""
                    lines.append(f"- {item.source}: {item.claim} = `{item.value}`{suffix}")
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
                    "Opportunity formula:",
                    "",
                ]
            )
            if recommendation.opportunity_factors:
                lines.extend(
                    "- "
                    f"{factor.key}: raw `{factor.raw_value}`; "
                    f"contribution `{factor.contribution:+.1f}`; "
                    f"evidence: {factor.evidence}"
                    for factor in recommendation.opportunity_factors
                )
            else:
                lines.append("- n/a")
            lines.extend(
                [
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
                    f"- Offer gap: `{serp.offer_gap_score:.2f}`",
                    f"- Offer signals: {', '.join(serp.offer_signals) or 'n/a'}",
                    f"- Missing offer signals: {', '.join(serp.missing_offer_signals) or 'n/a'}",
                    f"- Competitor types: {', '.join(serp.competitor_types) or 'n/a'}",
                    f"- SERP summary: {serp.summary}",
                    f"- Top domains: {', '.join(serp.top_domains) or 'n/a'}",
                ]
            )
            if serp.weak_spots:
                lines.extend(["", "SERP weak spots:", ""])
                lines.extend(f"- {spot}" for spot in serp.weak_spots)
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
                        f"offer gap `{serp.offer_gap_score:.2f}`; "
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
