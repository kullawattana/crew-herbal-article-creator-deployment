"""
Report generator — pretty-prints benchmark results to the console
and writes a Markdown summary file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

_MODEL_LABELS = {
    "no_rag_llm": "No-RAG LLM (Baseline)",
    "single_agent_rag": "Single-Agent RAG",
    "multi_agent": "Multi-Agent (CrewAI)",
}


def _label(name: str) -> str:
    return _MODEL_LABELS.get(name, name)


def _bar(value: float | None, max_val: float = 10.0, width: int = 20) -> str:
    """ASCII progress bar."""
    if value is None:
        return "[" + "?" * width + "]"
    filled = int(round((value / max_val) * width))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _fmt(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def _decision_icon(decision: str) -> str:
    """Return a visual indicator for Go/No-Go decisions."""
    icons = {"GO": "✅ GO", "NO-GO": "❌ NO-GO", "CONDITIONAL GO": "⚠️  COND.GO"}
    return icons.get(decision, f"? {decision}")


def _kappa_label(k: float | None) -> str:
    """Interpret a Cohen's κ / Krippendorff α value."""
    if k is None or k != k:   # None or NaN
        return "N/A"
    if k < 0.2:
        return f"{k:.3f} (Slight)"
    if k < 0.4:
        return f"{k:.3f} (Fair)"
    if k < 0.6:
        return f"{k:.3f} (Moderate)"
    if k < 0.8:
        return f"{k:.3f} (Substantial)"
    return f"{k:.3f} (Almost Perfect)"


# ─────────────────────────────────────────────────────────────────────────────
# Console report
# ─────────────────────────────────────────────────────────────────────────────

def print_report(results: dict[str, Any]) -> None:
    """Print a formatted comparison table to stdout."""
    herb = results.get("herb_eng", results.get("herb", "?"))
    ts = results.get("timestamp", "")
    models = results.get("models", {})
    ranking = results.get("ranking", {})

    print("\n" + "=" * 70)
    print(f"  BENCHMARK RESULTS — {herb}  [{ts}]")
    print("=" * 70)

    # ── Per-model metrics table ──────────────────────────────────────────────
    header = f"{'Metric':<28}" + "".join(f"{_label(n):>22}" for n in models)
    print(f"\n{header}")
    print("-" * (28 + 22 * len(models)))

    def _row(label, key, fmt_fn, bar_max=None):
        row = f"{label:<28}"
        for name, data in models.items():
            val = data["metrics"].get(key)
            cell = fmt_fn(val)
            if bar_max is not None:
                cell += " " + _bar(val, bar_max, 10)
            row += f"{cell:>22}"
        print(row)

    # LLM-as-Judge
    _row("Safety Score (0-10)",        "safety_score",        lambda v: _fmt(v), bar_max=10)
    _row("Scientific Validity (0-10)", "scientific_validity", lambda v: _fmt(v), bar_max=10)
    _row("Hallucination Rate (↓)",     "hallucination_rate",  lambda v: _fmt(v, 3))
    _row("Citations Found",            "citations_found",     lambda v: str(int(v)) if v is not None else "N/A")
    # Text-overlap
    _row("BLEU (0-100)",               "bleu",                lambda v: _fmt(v))
    _row("ROUGE-1 F1",                 "rouge1",              lambda v: _fmt(v, 3))
    _row("ROUGE-2 F1",                 "rouge2",              lambda v: _fmt(v, 3))
    _row("ROUGE-L F1",                 "rougeL",              lambda v: _fmt(v, 3))

    # NER-KPI (Multi-LLM-NER-KPI system)
    print()
    print(f"  {'── NER-KPI (≥10 entities = PASS)':<28}")
    def _ner_row(label, score_key, count_key, pass_key):
        row = f"  {label:<26}"
        for name, data in models.items():
            m = data["metrics"]
            score = m.get(score_key)
            count = m.get(count_key)
            passed = m.get(pass_key)
            flag = "✓" if passed else ("✗" if passed is not None else "?")
            cell = f"{flag} {_fmt(score)}% ({count if count is not None else '?'})"
            row += f"{cell:>22}"
        print(row)
    _ner_row("  Cultural",   "ner_cultural_score",   "ner_cultural_count",   "ner_cultural_pass")
    _ner_row("  Scientific", "ner_scientific_score",  "ner_scientific_count",  "ner_scientific_pass")
    _ner_row("  Safety",     "ner_safety_score",      "ner_safety_count",      "ner_safety_pass")
    _ner_row("  Overall",    "ner_overall_score",     None,                    "ner_all_pass")
    print()

    # MFS Grounding (Fact-to-Article alignment)
    mfs_total = results.get("mfs_claims", 0)
    if mfs_total:
        print(f"  ── MFS Grounding ({mfs_total} verified claims)")
        _row("  Grounding Score (↑)",      "mfs_grounding_score",    lambda v: _fmt(v, 3))
        _row("  Contradiction Rate (↓)",   "mfs_contradiction_rate", lambda v: _fmt(v, 3))
        _row("  Coverage Score",           "mfs_coverage_score",     lambda v: _fmt(v, 3))
        _row("  Claims Supported",         "mfs_claims_supported",   lambda v: str(int(v)) if v is not None else "N/A")
        _row("  Claims Missing",           "mfs_claims_missing",     lambda v: str(int(v)) if v is not None else "N/A")
        print()

    # Inter-Rater Agreement (multi-judge means)
    ira_summary = results.get("inter_rater_summary", {})
    if ira_summary:
        print("  ── Inter-Rater Agreement (Multi-Judge Means)")
        _row("  IRA Safety (mean)",         "ira_mean_safety",        lambda v: _fmt(v))
        _row("  IRA Validity (mean)",        "ira_mean_validity",      lambda v: _fmt(v))
        _row("  IRA Hallucination (mean)",   "ira_mean_hallucination", lambda v: _fmt(v, 3))
        _row("  IRA Safety Std",            "ira_std_safety",         lambda v: _fmt(v, 3))
        _row("  IRA Validity Std",          "ira_std_validity",       lambda v: _fmt(v, 3))
        # Print overall kappa summary
        for metric in ["safety", "validity", "hallucination"]:
            k = ira_summary.get(f"mean_kappa_{metric}")
            std = ira_summary.get(f"std_kappa_{metric}")
            if k is not None:
                std_str = f" ±{std:.3f}" if std is not None else ""
                print(f"    Kappa {metric:<15} {_kappa_label(k)}{std_str}")
        print()

    # Runtime separately
    row = f"{'Runtime (sec)':<28}"
    for name, data in models.items():
        rt = data.get("runtime_sec", 0)
        row += f"{rt:>22.1f}"
    print(row)

    # ── Go/No-Go decisions ────────────────────────────────────────────────────
    print("\n── Go/No-Go Decisions ────────────────────────────────────────────")
    for name, data in models.items():
        gng = data.get("go_no_go", {})
        decision = gng.get("decision", "N/A")
        print(f"\n  [{_label(name)}]  {_decision_icon(decision)}")
        for reason in gng.get("nogo_reasons", []):
            print(f"    ✗ {reason}")
        for reason in gng.get("conditional_reasons", []):
            print(f"    ⚠ {reason}")
        if not gng.get("nogo_reasons") and not gng.get("conditional_reasons"):
            print("    All thresholds met.")

    # ── Rankings ─────────────────────────────────────────────────────────────
    print("\n── Rankings ─────────────────────────────────────────────────────")
    for metric, winner in ranking.items():
        label = metric.replace("_", " ").title()
        winner_label = _label(winner) if winner else "N/A"
        print(f"  {label:<30} → {winner_label}")

    # ── Judge reasoning ──────────────────────────────────────────────────────
    print("\n── LLM Judge Reasoning ──────────────────────────────────────────")
    for name, data in models.items():
        jd = data.get("judge_details", {})
        nd = data.get("ner_details", {})
        m = data.get("metrics", {})
        print(f"\n  [{_label(name)}]")
        print(f"    Safety ({_fmt(m.get('safety_score'))}/10): {jd.get('safety_reasoning', 'N/A')}")
        for issue in jd.get("safety_issues", [])[:2]:
            print(f"      ⚠ {issue}")
        print(f"    Validity ({_fmt(m.get('scientific_validity'))}/10): {jd.get('validity_reasoning', 'N/A')}")
        print(f"    Hallucination ({_fmt(m.get('hallucination_rate'), 3)}): {jd.get('hallucination_reasoning', 'N/A')}")
        for claim in jd.get("suspicious_claims", [])[:2]:
            print(f"      ? {claim}")
        # NER top entities
        if nd.get("source"):
            print(f"    NER source: {nd['source']}")
        for cat, key in [("Cultural", "cultural_entities"), ("Scientific", "scientific_entities"), ("Safety", "safety_entities")]:
            ents = nd.get(key, [])[:3]
            if ents:
                names = ", ".join(e.get("name", "?") for e in ents)
                print(f"    NER {cat}: {names} …")

    # ── Inter-Rater detail per model ──────────────────────────────────────────
    has_ira = any(data.get("inter_rater_details", {}).get("judges") for data in models.values())
    if has_ira:
        print("\n── Inter-Rater Agreement Detail ─────────────────────────────────")
        for name, data in models.items():
            ird = data.get("inter_rater_details", {})
            if not ird.get("judges"):
                continue
            print(f"\n  [{_label(name)}]")
            # Per-judge scores
            for judge in ird["judges"]:
                print(f"    {judge['name']:<25} Safety={_fmt(judge.get('safety'))}  "
                      f"Validity={_fmt(judge.get('validity'))}  "
                      f"Halluc={_fmt(judge.get('hallucination'), 3)}")
                if judge.get("notes"):
                    print(f"      Note: {judge['notes']}")
            # Pairwise kappa
            for pair_k in ird.get("pair_kappas", []):
                print(f"    κ {pair_k['pair']}")
                print(f"      Safety={_kappa_label(pair_k.get('kappa_safety'))}  "
                      f"Validity={_kappa_label(pair_k.get('kappa_validity'))}  "
                      f"Halluc={_kappa_label(pair_k.get('kappa_hallucination'))}")
            # Krippendorff alpha
            ka = ird.get("krippendorff_alpha", {})
            if any(v is not None for v in ka.values()):
                print(f"    Krippendorff α: "
                      f"Safety={_kappa_label(ka.get('safety'))}  "
                      f"Validity={_kappa_label(ka.get('validity'))}  "
                      f"Halluc={_kappa_label(ka.get('hallucination'))}")

    # ── MFS claim traceability ────────────────────────────────────────────────
    has_align = any(data.get("alignment_details", {}).get("total_claims", 0) > 0 for data in models.values())
    if has_align:
        print("\n── MFS Claim Traceability (first 5 per model) ───────────────────")
        for name, data in models.items():
            ad = data.get("alignment_details", {})
            if not ad.get("total_claims"):
                continue
            print(f"\n  [{_label(name)}]  "
                  f"Supported={ad.get('supported', 0)}  "
                  f"Contradicted={ad.get('contradicted', 0)}  "
                  f"Missing={ad.get('missing', 0)}")
            for trace in ad.get("traceability", [])[:5]:
                verdict = trace.get("verdict", "?")
                icon = {"SUPPORTED": "✓", "CONTRADICTED": "✗", "MISSING": "—"}.get(verdict, "?")
                claim_text = trace.get("claim", "")[:80]
                print(f"    {icon} [{trace.get('claim_id')}] {claim_text}")
                snippet = trace.get("snippet", "")
                if snippet:
                    print(f"       ↳ \"{snippet}\"")

    print("\n" + "=" * 70 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Markdown report
# ─────────────────────────────────────────────────────────────────────────────

def save_markdown(results: dict[str, Any], output_dir: str | Path = "outputs") -> Path:
    """
    Generate a Markdown comparison report and save it.

    Returns the path to the saved file.
    """
    herb = results.get("herb_eng", results.get("herb", "Herb"))
    ts = results.get("timestamp", "")
    models = results.get("models", {})
    ranking = results.get("ranking", {})

    lines: list[str] = []

    lines.append(f"# Benchmark Report: {herb}")
    lines.append(f"\n**Timestamp:** {ts}")
    lines.append(f"**Scientific name:** {results.get('herb', '?')}")
    lines.append(f"**Language:** {results.get('lang', 'en')}")
    lines.append(f"**Reference:** {results.get('reference_source', 'N/A')}")
    mfs_total = results.get("mfs_claims", 0)
    if mfs_total:
        lines.append(f"**MFS Claims:** {mfs_total} verified claims")

    lines.append("\n---\n")

    # ── Metric table ─────────────────────────────────────────────────────────
    lines.append("## Evaluation Metrics\n")

    col_names = list(models.keys())
    header = "| Metric | " + " | ".join(_label(n) for n in col_names) + " |"
    separator = "|--------|" + "|".join(["-----:"] * len(col_names)) + "|"
    lines.append(header)
    lines.append(separator)

    def _md_row(label, key, fmt_fn=None):
        cells = []
        for name in col_names:
            val = models[name]["metrics"].get(key)
            cells.append((fmt_fn or _fmt)(val) if val is not None else "N/A")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    # LLM-as-Judge
    _md_row("Safety Score (0–10)", "safety_score")
    _md_row("Scientific Validity (0–10)", "scientific_validity")
    _md_row("Hallucination Rate (↓)", "hallucination_rate", lambda v: _fmt(v, 3))
    _md_row("Citations Found", "citations_found", lambda v: str(int(v)) if v is not None else "N/A")
    # Text-overlap
    _md_row("BLEU (0–100)", "bleu")
    _md_row("ROUGE-1 F1", "rouge1", lambda v: _fmt(v, 3))
    _md_row("ROUGE-2 F1", "rouge2", lambda v: _fmt(v, 3))
    _md_row("ROUGE-L F1", "rougeL", lambda v: _fmt(v, 3))
    # NER-KPI
    def _md_ner_row(label, score_key, count_key, pass_key):
        cells = []
        for name in col_names:
            m = models[name]["metrics"]
            score = m.get(score_key)
            count = m.get(count_key)
            passed = m.get(pass_key)
            flag = "✓" if passed else ("✗" if passed is not None else "?")
            cell = f"{flag} {_fmt(score)}%"
            if count is not None:
                cell += f" ({count})"
            cells.append(cell)
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    _md_ner_row("NER Cultural (≥10=PASS)", "ner_cultural_score", "ner_cultural_count", "ner_cultural_pass")
    _md_ner_row("NER Scientific (≥10=PASS)", "ner_scientific_score", "ner_scientific_count", "ner_scientific_pass")
    _md_ner_row("NER Safety (≥10=PASS)", "ner_safety_score", "ner_safety_count", "ner_safety_pass")
    _md_ner_row("NER Overall Score", "ner_overall_score", None, "ner_all_pass")

    # MFS Grounding
    if mfs_total:
        _md_row("MFS Grounding Score (↑)", "mfs_grounding_score", lambda v: _fmt(v, 3))
        _md_row("MFS Contradiction Rate (↓)", "mfs_contradiction_rate", lambda v: _fmt(v, 3))
        _md_row("MFS Coverage Score", "mfs_coverage_score", lambda v: _fmt(v, 3))
        _md_row("MFS Claims Supported", "mfs_claims_supported", lambda v: str(int(v)) if v is not None else "N/A")
        _md_row("MFS Claims Missing", "mfs_claims_missing", lambda v: str(int(v)) if v is not None else "N/A")

    # Inter-Rater (multi-judge means)
    ira_summary = results.get("inter_rater_summary", {})
    if ira_summary:
        _md_row("IRA Safety (mean)", "ira_mean_safety")
        _md_row("IRA Validity (mean)", "ira_mean_validity")
        _md_row("IRA Hallucination (mean)", "ira_mean_hallucination", lambda v: _fmt(v, 3))
        _md_row("IRA Safety Std", "ira_std_safety", lambda v: _fmt(v, 3))
        _md_row("IRA Validity Std", "ira_std_validity", lambda v: _fmt(v, 3))

    # Runtime row
    rt_cells = [str(models[n].get("runtime_sec", "N/A")) for n in col_names]
    lines.append(f"| Runtime (sec) | " + " | ".join(rt_cells) + " |")

    # ── Go/No-Go verdicts ─────────────────────────────────────────────────────
    lines.append("\n## Go/No-Go Decisions\n")
    lines.append("| Model | Decision | Reasons |")
    lines.append("|-------|----------|---------|")
    for name in col_names:
        gng = models[name].get("go_no_go", {})
        decision = gng.get("decision", "N/A")
        icon = {"GO": "✅", "NO-GO": "❌", "CONDITIONAL GO": "⚠️"}.get(decision, "?")
        reasons = "; ".join(
            gng.get("nogo_reasons", []) + gng.get("conditional_reasons", [])
        ) or "All thresholds met"
        lines.append(f"| {_label(name)} | {icon} **{decision}** | {reasons} |")

    # Per-model Go/No-Go metric verdicts
    lines.append("\n### Threshold Verdicts\n")
    for name in col_names:
        gng = models[name].get("go_no_go", {})
        verdicts = gng.get("verdicts", [])
        if not verdicts:
            continue
        lines.append(f"**{_label(name)}**\n")
        lines.append("| Metric | Value | Verdict |")
        lines.append("|--------|-------|---------|")
        for v in verdicts:
            verdict_icon = {"GO": "✅", "NO-GO": "❌", "CONDITIONAL GO": "⚠️", "N/A": "—"}.get(v.get("verdict", ""), "?")
            val_str = _fmt(v.get("value")) if v.get("value") is not None else "N/A"
            lines.append(f"| {v.get('metric', '?')} | {val_str} | {verdict_icon} {v.get('verdict', '?')} |")
        lines.append("")

    # ── Rankings ─────────────────────────────────────────────────────────────
    lines.append("\n## Rankings\n")
    lines.append("| Metric | Best Model |")
    lines.append("|--------|-----------|")
    for metric, winner in ranking.items():
        label = metric.replace("_", " ").title()
        lines.append(f"| {label} | {_label(winner) if winner else 'N/A'} |")

    # ── Inter-Rater Agreement ─────────────────────────────────────────────────
    has_ira = any(models[n].get("inter_rater_details", {}).get("judges") for n in col_names)
    if has_ira:
        lines.append("\n## Inter-Rater Agreement (Blind Evaluation)\n")

        # Overall kappa summary
        if ira_summary:
            lines.append("### Overall Kappa Summary\n")
            lines.append("| Metric | Mean κ | Std κ | Interpretation |")
            lines.append("|--------|--------|-------|----------------|")
            for metric in ["safety", "validity", "hallucination"]:
                k = ira_summary.get(f"mean_kappa_{metric}")
                std = ira_summary.get(f"std_kappa_{metric}")
                if k is not None:
                    interp = _kappa_label(k).split("(")[-1].rstrip(")")
                    lines.append(f"| {metric.title()} | {_fmt(k, 3)} | {_fmt(std, 3) if std else 'N/A'} | {interp} |")
            lines.append("")

        # Per-model IRA detail
        for name in col_names:
            ird = models[name].get("inter_rater_details", {})
            if not ird.get("judges"):
                continue
            lines.append(f"### {_label(name)}\n")

            # Judge scores table
            lines.append("**Judge Scores**\n")
            lines.append("| Judge | Safety | Validity | Hallucination | Notes |")
            lines.append("|-------|--------|----------|---------------|-------|")
            for judge in ird["judges"]:
                notes = str(judge.get("notes", "")).replace("|", "\\|")[:80]
                lines.append(
                    f"| {judge['name']} | {_fmt(judge.get('safety'))} | "
                    f"{_fmt(judge.get('validity'))} | {_fmt(judge.get('hallucination'), 3)} | {notes} |"
                )
            lines.append("")

            # Pairwise kappa
            if ird.get("pair_kappas"):
                lines.append("**Pairwise Cohen's κ (linear weighted)**\n")
                lines.append("| Judge Pair | κ Safety | κ Validity | κ Hallucination |")
                lines.append("|------------|----------|------------|-----------------|")
                for pk in ird["pair_kappas"]:
                    lines.append(
                        f"| {pk['pair']} | {_kappa_label(pk.get('kappa_safety'))} | "
                        f"{_kappa_label(pk.get('kappa_validity'))} | "
                        f"{_kappa_label(pk.get('kappa_hallucination'))} |"
                    )
                lines.append("")

            # Krippendorff alpha
            ka = ird.get("krippendorff_alpha", {})
            if any(v is not None for v in ka.values()):
                lines.append("**Krippendorff's α (ordinal)**\n")
                lines.append("| Metric | α | Interpretation |")
                lines.append("|--------|---|----------------|")
                for metric in ["safety", "validity", "hallucination"]:
                    v = ka.get(metric)
                    if v is not None:
                        interp = _kappa_label(v).split("(")[-1].rstrip(")")
                        lines.append(f"| {metric.title()} | {_fmt(v, 3)} | {interp} |")
                lines.append("")

    # ── MFS Claim Traceability ─────────────────────────────────────────────────
    has_align = any(models[n].get("alignment_details", {}).get("total_claims", 0) > 0 for n in col_names)
    if has_align:
        lines.append("\n## Master Fact Sheet Grounding\n")
        lines.append(
            f"Verified against **{mfs_total} claims** extracted from PubMed + Pinecone.\n"
        )

        for name in col_names:
            ad = models[name].get("alignment_details", {})
            if not ad.get("total_claims"):
                continue
            lines.append(f"### {_label(name)}\n")
            total = ad.get("total_claims", 0)
            sup = ad.get("supported", 0)
            con = ad.get("contradicted", 0)
            mis = ad.get("missing", 0)
            lines.append(
                f"- **Supported:** {sup}/{total} ({round(sup/total*100, 1) if total else 0}%)\n"
                f"- **Contradicted:** {con}/{total} ({round(con/total*100, 1) if total else 0}%)\n"
                f"- **Missing:** {mis}/{total} ({round(mis/total*100, 1) if total else 0}%)\n"
            )

            traceability = ad.get("traceability", [])
            if traceability:
                lines.append("\n**Claim Traceability (first 10)**\n")
                lines.append("| ID | Claim | Verdict | Source | Confidence | Article Snippet |")
                lines.append("|----|-------|---------|--------|------------|-----------------|")
                for trace in traceability[:10]:
                    verdict = trace.get("verdict", "?")
                    icon = {"SUPPORTED": "✅", "CONTRADICTED": "❌", "MISSING": "—"}.get(verdict, "?")
                    claim = str(trace.get("claim", "")).replace("|", "\\|")[:80]
                    snippet = str(trace.get("snippet", "")).replace("|", "\\|")[:60]
                    lines.append(
                        f"| {trace.get('claim_id')} | {claim} | {icon} {verdict} | "
                        f"{trace.get('source_id', '?')} | {trace.get('confidence', '?')} | {snippet} |"
                    )
                lines.append("")

    # ── Per-model details ─────────────────────────────────────────────────────
    lines.append("## Judge Reasoning\n")
    for name, data in models.items():
        jd = data.get("judge_details", {})
        nd = data.get("ner_details", {})
        m = data.get("metrics", {})
        lines.append(f"### {_label(name)}\n")
        lines.append(f"**Safety ({_fmt(m.get('safety_score'))}/10):** {jd.get('safety_reasoning', 'N/A')}")
        if jd.get("safety_issues"):
            lines.append("\nIssues found:")
            for issue in jd["safety_issues"]:
                lines.append(f"- {issue}")
        lines.append(f"\n**Scientific Validity ({_fmt(m.get('scientific_validity'))}/10):** "
                     f"{jd.get('validity_reasoning', 'N/A')}")
        lines.append(f"\n**Hallucination Rate ({_fmt(m.get('hallucination_rate'), 3)}):** "
                     f"{jd.get('hallucination_reasoning', 'N/A')}")
        if jd.get("suspicious_claims"):
            lines.append("\nSuspicious claims:")
            for claim in jd["suspicious_claims"]:
                lines.append(f"- {claim}")
        # NER entity samples
        lines.append(f"\n**NER-KPI** *(via {nd.get('source', 'N/A')})*")
        for cat_label, cat_key in [
            ("Cultural", "cultural_entities"),
            ("Scientific", "scientific_entities"),
            ("Safety", "safety_entities"),
        ]:
            ents = nd.get(cat_key, [])
            if ents:
                sample = ", ".join(e.get("name", "?") for e in ents[:5])
                lines.append(f"- {cat_label}: {sample}")
        lines.append("")

    # ── Output previews ───────────────────────────────────────────────────────
    lines.append("## Output Previews (first 300 chars)\n")
    for name, data in models.items():
        lines.append(f"### {_label(name)}\n")
        preview = data.get("output_preview", "")[:300]
        lines.append(f"```\n{preview}\n```\n")

    md = "\n".join(lines)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_report_{ts}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"📄 Markdown report saved: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# Load from JSON
# ─────────────────────────────────────────────────────────────────────────────

def load_and_print(json_path: str | Path) -> None:
    """Load a saved benchmark JSON and print the console report."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    print_report(data)
    save_markdown(data, output_dir=Path(json_path).parent)
