"""
Ablation Study Runner
======================
Systematically runs each AblationConfig and measures the contribution
of each component via delta metrics.

Usage:
    from herbal_article_creator.benchmark.ablation.runner import AblationRunner

    runner = AblationRunner(
        herbs="Curcuma longa",
        herbs_eng="Turmeric",
        herbs_thai="ขมิ้นชัน",
    )
    results = runner.run()
    runner.print_deltas(results)
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from crewai import Agent, Crew, Process, Task

from .configs import AblationConfig, CONFIGS, CONFIG_MAP
from ..evaluators import text_metrics, llm_judge
from ..llm_factory import create_llm, create_judge_llm

# ──────────────────────────────────────────────────────────────────────────────
# Article generator for each ablation config
# ──────────────────────────────────────────────────────────────────────────────

def _generate(
    cfg: AblationConfig,
    herbs: str,
    herbs_eng: str,
    herbs_thai: str,
    lang: str = "en",
) -> dict[str, Any]:
    """Generate an article under a specific ablation configuration."""
    start = time.time()
    article_lang = "English" if lang == "en" else "Thai"

    # ── Full multi-agent crew ────────────────────────────────────────────────
    if cfg.use_multi_agent:
        from ..models.multi_agent import generate
        result = generate(herbs, herbs_eng, herbs_thai, lang)
        result["config"] = cfg.name
        return result

    # ── Single agent with selectable tools ──────────────────────────────────
    tools = []

    if cfg.use_pubmed:
        try:
            from ...tools.pubmed_tools import (
                PubMedSearchTool, PubMedFetchTool, PubMedParseTool
            )
            tools += [PubMedSearchTool(), PubMedFetchTool(), PubMedParseTool()]
        except ImportError:
            print(f"[Ablation] PubMed tools not available for config: {cfg.name}")

    if cfg.use_pinecone and os.getenv("PINECONE_API_KEY"):
        try:
            from ...tools.pinecone_tools import search_pinecone
            tools.append(search_pinecone)
        except ImportError:
            print(f"[Ablation] Pinecone tool not available for config: {cfg.name}")

    llm = create_llm()

    pinecone_step = (
        f'3. Search Pinecone for "{herbs_thai}" using search_pinecone.\n'
        if cfg.use_pinecone and os.getenv("PINECONE_API_KEY") else ""
    )
    pubmed_step = (
        f'1. Search PubMed for "{herbs_eng}" using search_pubmed (top 2-3 papers).\n'
        '2. Fetch and parse key abstracts for evidence.\n'
        if cfg.use_pubmed else ""
    )
    no_tool_note = (
        "Write based purely on your parametric knowledge. "
        "Do not fabricate specific PMIDs or DOIs.\n"
        if not tools else ""
    )

    agent = Agent(
        role="Herbal Medicine Research Writer",
        goal="Write comprehensive, accurate herbal medicine articles",
        backstory=(
            "Expert pharmacist-researcher specialising in herbal medicine. "
            "Retrieves evidence before writing."
        ),
        llm=llm,
        tools=tools,
        verbose=False,
        max_iter=cfg.max_iter,
    )

    task = Task(
        description=f"""Write a comprehensive scientific article about **{herbs_eng}**
(Thai: {herbs_thai}, Scientific: {herbs}).

{pubmed_step}{pinecone_step}{no_tool_note}
Cover: Introduction, Phytochemistry, Pharmacology, Clinical Evidence,
Safety Profile, Modern Applications, Conclusion.
Write in **{article_lang}**.""",
        expected_output=f"Comprehensive {article_lang} herbal article with 7 sections.",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff(inputs={"herbs": herbs, "herbs_eng": herbs_eng, "herbs_thai": herbs_thai})

    return {
        "output": str(result),
        "runtime_sec": round(time.time() - start, 2),
        "model_name": cfg.name,
        "config": cfg.name,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Delta computation
# ──────────────────────────────────────────────────────────────────────────────

def _delta(a: float | None, b: float | None, higher_is_better: bool = True) -> float | None:
    """b - a (positive = improvement). For hallucination: a - b (lower is better)."""
    if a is None or b is None:
        return None
    diff = b - a if higher_is_better else a - b
    return round(diff, 4)


DELTA_PAIRS = [
    # (from_config, to_config, description)
    ("baseline",          "+pubmed",           "Value of PubMed"),
    ("baseline",          "+pinecone",          "Value of Pinecone KB"),
    ("baseline",          "+pubmed+pinecone",   "Value of both retrievers"),
    ("+pubmed",           "+pubmed+pinecone",   "Marginal value of adding Pinecone"),
    ("+pinecone",         "+pubmed+pinecone",   "Marginal value of adding PubMed"),
    ("+pubmed+pinecone",  "+multi_agent",       "Value of multi-agent orchestration"),
    ("baseline",          "+multi_agent",       "Total system gain"),
]

METRICS_DIR = {
    "safety_score": True,
    "scientific_validity": True,
    "hallucination_rate": False,  # lower is better
    "bleu": True,
    "rouge1": True,
    "rougeL": True,
}


# ──────────────────────────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────────────────────────

class AblationRunner:
    """
    Runs all ablation configurations and computes delta metrics.
    """

    def __init__(
        self,
        herbs: str,
        herbs_eng: str,
        herbs_thai: str,
        lang: str = "en",
        configs: list[str] | None = None,
        reference_text: str | None = None,
        output_dir: str = "outputs",
    ):
        """
        Parameters
        ----------
        herbs        : Scientific name
        herbs_eng    : English name
        herbs_thai   : Thai name
        lang         : "en" | "th"
        configs      : List of config names to run (default: all)
        reference_text: Gold standard for BLEU/ROUGE (default: multi-agent output)
        output_dir   : Where to save results
        """
        self.herbs = herbs
        self.herbs_eng = herbs_eng
        self.herbs_thai = herbs_thai
        self.lang = lang
        self.configs = [CONFIG_MAP[n] for n in configs] if configs else CONFIGS
        self._reference_text = reference_text
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> dict[str, Any]:
        """
        Run all ablation configurations and return results dict.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print("\n" + "=" * 70)
        print(f"ABLATION STUDY — {self.herbs_eng} ({self.herbs})")
        print(f"Configurations: {[c.name for c in self.configs]}")
        print("=" * 70)

        # ── Step 1: Generate articles for each config ─────────────────────────
        generations: dict[str, dict] = {}
        for i, cfg in enumerate(self.configs):
            print(f"\n[{i+1}/{len(self.configs)}] Config: {cfg.label}")
            print(f"   {cfg.description}")
            try:
                gen = _generate(cfg, self.herbs, self.herbs_eng, self.herbs_thai, self.lang)
                generations[cfg.name] = gen
                print(f"   ✓ Done in {gen.get('runtime_sec', 0):.1f}s")
            except Exception as e:
                print(f"   ✗ Failed: {e}")
                generations[cfg.name] = {
                    "output": "", "runtime_sec": 0,
                    "config": cfg.name, "error": str(e),
                }

        # ── Step 2: Reference text ────────────────────────────────────────────
        reference = (
            self._reference_text
            or generations.get("+multi_agent", {}).get("output")
            or generations.get("+pubmed+pinecone", {}).get("output")
            or next(
                (g["output"] for g in generations.values() if g.get("output")), ""
            )
        )

        # ── Step 3: Evaluate each config ──────────────────────────────────────
        text_only = {k: v["output"] for k, v in generations.items() if v.get("output")}
        judge_llm = create_judge_llm()

        print("\n[Eval] BLEU/ROUGE …")
        bleu_rouge = text_metrics.compute_all(text_only, reference)

        print("[Eval] LLM-as-Judge …")
        judge_results = llm_judge.judge_all(text_only, llm=judge_llm)

        # ── Step 4: Assemble per-config results ───────────────────────────────
        config_results: dict[str, dict] = {}
        for cfg in self.configs:
            name = cfg.name
            gen = generations.get(name, {})
            tm = bleu_rouge.get(name)
            jr = judge_results.get(name)

            config_results[name] = {
                "label": cfg.label,
                "description": cfg.description,
                "runtime_sec": gen.get("runtime_sec", 0),
                "error": gen.get("error"),
                "output_length_chars": len(gen.get("output", "")),
                "metrics": {
                    "bleu": tm.bleu if tm else None,
                    "rouge1": tm.rouge1 if tm else None,
                    "rouge2": tm.rouge2 if tm else None,
                    "rougeL": tm.rougeL if tm else None,
                    "safety_score": jr.safety_score if jr else None,
                    "scientific_validity": jr.validity_score if jr else None,
                    "hallucination_rate": jr.hallucination_rate if jr else None,
                    "citations_found": jr.citations_found if jr else None,
                },
            }

        # ── Step 5: Delta analysis ────────────────────────────────────────────
        deltas = self._compute_deltas(config_results)

        results = {
            "herb": self.herbs,
            "herb_eng": self.herbs_eng,
            "herb_thai": self.herbs_thai,
            "timestamp": timestamp,
            "configs": config_results,
            "deltas": deltas,
        }

        # ── Step 6: Save ──────────────────────────────────────────────────────
        out_path = self.output_dir / f"ablation_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Ablation results saved: {out_path}")

        # Save article outputs
        for cfg_name, gen in generations.items():
            if gen.get("output"):
                txt = self.output_dir / f"ablation_{cfg_name.replace('+', 'plus_')}_{timestamp}.txt"
                txt.write_text(gen["output"], encoding="utf-8")

        return results

    @staticmethod
    def _compute_deltas(configs: dict[str, dict]) -> list[dict]:
        """Compute delta metrics for all defined comparison pairs."""
        deltas = []
        for from_cfg, to_cfg, desc in DELTA_PAIRS:
            if from_cfg not in configs or to_cfg not in configs:
                continue
            from_m = configs[from_cfg]["metrics"]
            to_m = configs[to_cfg]["metrics"]

            entry: dict[str, Any] = {
                "from": from_cfg,
                "to": to_cfg,
                "description": desc,
                "deltas": {},
            }
            for metric, higher_is_better in METRICS_DIR.items():
                d = _delta(from_m.get(metric), to_m.get(metric), higher_is_better)
                entry["deltas"][metric] = d

            deltas.append(entry)
        return deltas

    @staticmethod
    def print_deltas(results: dict) -> None:
        """Pretty-print delta analysis to stdout."""
        print("\n" + "=" * 70)
        print("  ABLATION DELTA ANALYSIS")
        print("=" * 70)

        for entry in results.get("deltas", []):
            print(f"\n  {entry['from']} → {entry['to']}  [{entry['description']}]")
            for metric, val in entry["deltas"].items():
                sign = "+" if (val is not None and val > 0) else ""
                val_str = f"{sign}{val:.4f}" if val is not None else "N/A"
                direction = "↑" if val is not None and val > 0 else ("↓" if val is not None and val < 0 else "=")
                print(f"    {metric:<25} {direction} {val_str}")

        print("\n" + "=" * 70)

    @staticmethod
    def print_table(results: dict) -> None:
        """Print a per-config metric table."""
        configs = results.get("configs", {})
        metrics = ["safety_score", "scientific_validity", "hallucination_rate", "bleu", "rouge1", "rougeL"]

        header = f"{'Config':<25}" + "".join(f"{m[:12]:>14}" for m in metrics)
        print("\n" + header)
        print("-" * (25 + 14 * len(metrics)))

        for name, data in configs.items():
            m = data.get("metrics", {})
            row = f"{name:<25}"
            for metric in metrics:
                val = m.get(metric)
                row += f"{f'{val:.3f}' if val is not None else 'N/A':>14}"
            print(row)
