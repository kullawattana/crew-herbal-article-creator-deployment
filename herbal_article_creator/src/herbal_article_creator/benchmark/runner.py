"""
Benchmark Runner — orchestrates the three model runs and all evaluations.

Usage (programmatic):
    from herbal_article_creator.benchmark.runner import BenchmarkRunner

    runner = BenchmarkRunner(
        herbs="Curcuma longa",
        herbs_eng="Turmeric",
        herbs_thai="ขมิ้นชัน",
        lang="en",
        build_mfs=True,         # build Master Fact Sheet
        run_inter_rater=True,   # multi-judge agreement
    )
    results = runner.run()

Usage (CLI):
    uv run benchmark
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import no_rag_llm, single_agent_rag, multi_agent
from .evaluators import text_metrics, llm_judge, ner_kpi, go_no_go, mfs as mfs_module, fact_alignment, inter_rater
from .llm_factory import create_judge_llm


class BenchmarkRunner:
    """
    Full benchmark pipeline:
      1. Generate   : No-RAG LLM, Single-Agent RAG, Multi-Agent
      2. Evaluate   : BLEU/ROUGE, LLM-as-Judge, NER-KPI
      3. Ground     : Master Fact Sheet (MFS) + Fact-to-Article alignment
      4. Agree      : Inter-Rater Agreement (blind, multi-judge, Cohen's κ)
      5. Decide     : Go/No-Go per-model threshold verdict
    """

    def __init__(
        self,
        herbs: str,
        herbs_eng: str,
        herbs_thai: str,
        lang: str = "en",
        *,
        # Model flags
        run_no_rag: bool = True,
        run_single_rag: bool = True,
        run_multi_agent: bool = True,
        multi_agent_precomputed_file: str | None = None,
        # Reference for BLEU/ROUGE
        reference_text: str | None = None,
        reference_file: str | None = None,
        # MFS grounding
        build_mfs: bool = True,
        mfs_file: str | None = None,          # load pre-built MFS (skip build)
        pubmed_top_k: int = 3,
        pinecone_top_k: int = 5,
        # Inter-rater agreement (blind multi-judge)
        run_inter_rater: bool = True,
        blind_evaluation: bool = True,
        output_dir: str = "outputs",
    ):
        self.herbs = herbs
        self.herbs_eng = herbs_eng
        self.herbs_thai = herbs_thai
        self.lang = lang

        self.run_no_rag = run_no_rag
        self.run_single_rag = run_single_rag
        self.run_multi_agent = run_multi_agent
        self.multi_agent_precomputed_file = multi_agent_precomputed_file

        self._reference_text = reference_text
        self._reference_file = reference_file

        self.build_mfs = build_mfs
        self.mfs_file = mfs_file
        self.pubmed_top_k = pubmed_top_k
        self.pinecone_top_k = pinecone_top_k

        self.run_inter_rater = run_inter_rater
        self.blind_evaluation = blind_evaluation

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    def _load_reference(self, model_outputs: dict[str, dict]) -> str:
        if self._reference_text:
            return self._reference_text
        if self._reference_file:
            p = Path(self._reference_file)
            if p.exists():
                return p.read_text(encoding="utf-8")
            print(f"[Runner] Warning: reference_file not found: {p}")
        if "multi_agent" in model_outputs:
            return model_outputs["multi_agent"]["output"]
        return "\n\n".join(v["output"] for v in model_outputs.values())

    # ─────────────────────────────────────────────────────────────────────────
    def run(self) -> dict[str, Any]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print("\n" + "=" * 70)
        print(f"BENCHMARK START — {self.herbs_eng} ({self.herbs})")
        print("=" * 70)

        # ── Step 1: Generate articles ─────────────────────────────────────────
        model_outputs: dict[str, dict] = {}

        if self.run_no_rag:
            print("\n[1/3] Running No-RAG LLM baseline …")
            try:
                model_outputs["no_rag_llm"] = no_rag_llm.generate(
                    self.herbs, self.herbs_eng, self.herbs_thai, self.lang
                )
                print(f"      ✓ {model_outputs['no_rag_llm']['runtime_sec']}s")
            except Exception as e:
                print(f"      ✗ {e}")
                model_outputs["no_rag_llm"] = {"output": "", "runtime_sec": 0, "model_name": "no_rag_llm", "error": str(e)}

        if self.run_single_rag:
            print("\n[2/3] Running Single-Agent RAG …")
            try:
                model_outputs["single_agent_rag"] = single_agent_rag.generate(
                    self.herbs, self.herbs_eng, self.herbs_thai, self.lang
                )
                print(f"      ✓ {model_outputs['single_agent_rag']['runtime_sec']}s")
            except Exception as e:
                print(f"      ✗ {e}")
                model_outputs["single_agent_rag"] = {"output": "", "runtime_sec": 0, "model_name": "single_agent_rag", "error": str(e)}

        if self.run_multi_agent:
            print("\n[3/3] Running Multi-Agent crew …")
            try:
                model_outputs["multi_agent"] = multi_agent.generate(
                    self.herbs, self.herbs_eng, self.herbs_thai, self.lang,
                    precomputed_output_file=self.multi_agent_precomputed_file,
                )
                loaded = model_outputs["multi_agent"].get("loaded_from")
                print(f"      ✓ {'Loaded: ' + loaded if loaded else str(model_outputs['multi_agent']['runtime_sec']) + 's'}")
            except Exception as e:
                print(f"      ✗ {e}")
                model_outputs["multi_agent"] = {"output": "", "runtime_sec": 0, "model_name": "multi_agent", "error": str(e)}

        if not model_outputs:
            raise RuntimeError("No models were run.")

        text_only = {k: v["output"] for k, v in model_outputs.items() if v.get("output")}

        # ── Step 2: Master Fact Sheet ─────────────────────────────────────────
        fact_sheet = None
        if self.build_mfs:
            print("\n[MFS] Building Master Fact Sheet …")
            judge_llm = create_judge_llm()
            try:
                if self.mfs_file:
                    fact_sheet = mfs_module.load(self.mfs_file)
                    print(f"[MFS] Loaded {len(fact_sheet.claims)} claims from: {self.mfs_file}")
                else:
                    fact_sheet = mfs_module.build(
                        self.herbs, self.herbs_eng, self.herbs_thai,
                        llm=judge_llm,
                        pubmed_top_k=self.pubmed_top_k,
                        pinecone_top_k=self.pinecone_top_k,
                        output_dir=self.output_dir,
                    )
                print(f"[MFS] {len(fact_sheet.claims)} claims from {len(fact_sheet.sources)} sources")
            except Exception as e:
                print(f"[MFS] Failed: {e}")

        # ── Step 3: BLEU / ROUGE ─────────────────────────────────────────────
        print("\n[Eval] BLEU / ROUGE …")
        reference = self._load_reference(model_outputs)
        bleu_rouge = text_metrics.compute_all(text_only, reference)

        # ── Step 4: LLM-as-Judge (single judge) ─────────────────────────────
        print("[Eval] LLM-as-Judge …")
        judge_llm = create_judge_llm()
        judge_results = llm_judge.judge_all(text_only, llm=judge_llm)

        # ── Step 5: NER-KPI ──────────────────────────────────────────────────
        print("[Eval] NER-KPI …")
        ner_results = ner_kpi.evaluate_all(text_only, llm=judge_llm)

        # ── Step 6: Fact-to-Article alignment ────────────────────────────────
        alignment_results: dict = {}
        if fact_sheet and fact_sheet.claims:
            print("[Eval] Fact-to-Article alignment …")
            try:
                alignment_results = fact_alignment.evaluate_all(text_only, fact_sheet, llm=judge_llm)
            except Exception as e:
                print(f"[FactAlign] Failed: {e}")

        # ── Step 7: Inter-Rater Agreement (blind multi-judge) ────────────────
        ira_results: dict = {}
        ira_summary: dict = {}
        if self.run_inter_rater:
            print("[Eval] Inter-Rater Agreement (blind) …")
            try:
                ira_results = inter_rater.evaluate_all(text_only, blind=self.blind_evaluation)
                ira_summary = inter_rater.kappa_summary(ira_results)
            except Exception as e:
                print(f"[IRA] Failed: {e}")

        # ── Step 8: Assemble model results ───────────────────────────────────
        results: dict[str, Any] = {
            "herb": self.herbs,
            "herb_eng": self.herbs_eng,
            "herb_thai": self.herbs_thai,
            "lang": self.lang,
            "timestamp": timestamp,
            "reference_source": (
                self._reference_file
                or ("multi_agent_output" if "multi_agent" in model_outputs else "concatenated")
            ),
            "mfs_claims": len(fact_sheet.claims) if fact_sheet else 0,
            "inter_rater_summary": ira_summary,
            "models": {},
        }

        for name, gen in model_outputs.items():
            tm = bleu_rouge.get(name)
            jr = judge_results.get(name)
            nr = ner_results.get(name)
            ar = alignment_results.get(name)
            ir = ira_results.get(name)

            metrics = {
                # Text-overlap
                "bleu": tm.bleu if tm else None,
                "rouge1": tm.rouge1 if tm else None,
                "rouge2": tm.rouge2 if tm else None,
                "rougeL": tm.rougeL if tm else None,
                # LLM-as-Judge
                "safety_score": jr.safety_score if jr else None,
                "scientific_validity": jr.validity_score if jr else None,
                "hallucination_rate": jr.hallucination_rate if jr else None,
                "citations_found": jr.citations_found if jr else None,
                # NER-KPI
                "ner_cultural_score": nr.cultural.score if nr else None,
                "ner_cultural_count": nr.cultural.entity_count if nr else None,
                "ner_cultural_pass": nr.cultural.passed if nr else None,
                "ner_scientific_score": nr.scientific.score if nr else None,
                "ner_scientific_count": nr.scientific.entity_count if nr else None,
                "ner_scientific_pass": nr.scientific.passed if nr else None,
                "ner_safety_score": nr.safety.score if nr else None,
                "ner_safety_count": nr.safety.entity_count if nr else None,
                "ner_safety_pass": nr.safety.passed if nr else None,
                "ner_overall_score": nr.overall_score if nr else None,
                "ner_all_pass": nr.all_pass if nr else None,
                # Fact-to-Article Alignment (MFS grounding)
                "mfs_grounding_score": ar.grounding_score if ar else None,
                "mfs_contradiction_rate": ar.contradiction_rate if ar else None,
                "mfs_coverage_score": ar.coverage_score if ar else None,
                "mfs_claims_supported": ar.supported if ar else None,
                "mfs_claims_missing": ar.missing if ar else None,
                # Inter-Rater (multi-judge means)
                "ira_mean_safety": ir.mean_safety if ir else None,
                "ira_mean_validity": ir.mean_validity if ir else None,
                "ira_mean_hallucination": ir.mean_hallucination if ir else None,
                "ira_std_safety": ir.std_safety if ir else None,
                "ira_std_validity": ir.std_validity if ir else None,
            }

            # ── Go/No-Go decision ────────────────────────────────────────────
            gng = go_no_go.evaluate(metrics)

            results["models"][name] = {
                "runtime_sec": gen.get("runtime_sec", 0),
                "loaded_from": gen.get("loaded_from"),
                "error": gen.get("error"),
                "output_length_chars": len(gen.get("output", "")),
                "metrics": metrics,
                "go_no_go": {
                    "decision": gng.decision,
                    "nogo_reasons": gng.nogo_reasons,
                    "conditional_reasons": gng.conditional_reasons,
                    "verdicts": [
                        {"metric": v.metric, "value": v.value, "verdict": v.verdict}
                        for v in gng.verdicts
                    ],
                },
                "judge_details": {
                    "safety_reasoning": jr.safety_reasoning if jr else None,
                    "safety_issues": jr.safety_issues if jr else [],
                    "validity_reasoning": jr.validity_reasoning if jr else None,
                    "hallucination_reasoning": jr.hallucination_reasoning if jr else None,
                    "suspicious_claims": jr.suspicious_claims if jr else [],
                },
                "ner_details": {
                    "source": nr.source if nr else None,
                    "cultural_entities": nr.cultural.entities[:5] if nr else [],
                    "scientific_entities": nr.scientific.entities[:5] if nr else [],
                    "safety_entities": nr.safety.entities[:5] if nr else [],
                },
                "alignment_details": {
                    "total_claims": ar.total_claims if ar else 0,
                    "supported": ar.supported if ar else 0,
                    "contradicted": ar.contradicted if ar else 0,
                    "missing": ar.missing if ar else 0,
                    "traceability": [
                        {
                            "claim_id": a.claim_id,
                            "claim": a.claim[:100],
                            "verdict": a.verdict,
                            "source_id": a.source_id,
                            "confidence": a.confidence,
                            "snippet": a.article_snippet[:80],
                        }
                        for a in (ar.alignments if ar else [])
                    ],
                },
                "inter_rater_details": {
                    "judges": [
                        {"name": s.judge_name, "safety": s.safety_score,
                         "validity": s.scientific_validity, "hallucination": s.hallucination_rate,
                         "notes": s.notes}
                        for s in (ir.judge_scores if ir else [])
                    ],
                    "pair_kappas": [
                        {"pair": f"{p.judge_a} vs {p.judge_b}",
                         "kappa_safety": p.kappa_safety,
                         "kappa_validity": p.kappa_validity,
                         "kappa_hallucination": p.kappa_hallucination}
                        for p in (ir.pair_agreements if ir else [])
                    ],
                    "krippendorff_alpha": {
                        "safety": ir.krippendorff_alpha_safety if ir else None,
                        "validity": ir.krippendorff_alpha_validity if ir else None,
                        "hallucination": ir.krippendorff_alpha_hallucination if ir else None,
                    },
                },
                "output_preview": gen.get("output", "")[:500],
            }

        # ── Step 9: Ranking ───────────────────────────────────────────────────
        results["ranking"] = self._compute_ranking(results["models"])

        # ── Step 10: Save ─────────────────────────────────────────────────────
        out_path = self.output_dir / f"benchmark_comparison_{timestamp}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Results: {out_path}")

        for name, gen in model_outputs.items():
            if gen.get("output"):
                p = self.output_dir / f"benchmark_{name}_{timestamp}.txt"
                p.write_text(gen["output"], encoding="utf-8")

        return results

    @staticmethod
    def _compute_ranking(models: dict) -> dict:
        ranking: dict[str, Any] = {}

        def _best(metric: str, higher_is_better: bool = True):
            scores = {
                n: m["metrics"].get(metric)
                for n, m in models.items()
                if m["metrics"].get(metric) is not None
            }
            if not scores:
                return None
            return max(scores, key=scores.get) if higher_is_better else min(scores, key=scores.get)

        ranking["best_safety"] = _best("safety_score")
        ranking["best_scientific_validity"] = _best("scientific_validity")
        ranking["lowest_hallucination"] = _best("hallucination_rate", higher_is_better=False)
        ranking["best_bleu"] = _best("bleu")
        ranking["best_rouge1"] = _best("rouge1")
        ranking["best_rougeL"] = _best("rougeL")
        ranking["best_ner_cultural"] = _best("ner_cultural_score")
        ranking["best_ner_scientific"] = _best("ner_scientific_score")
        ranking["best_ner_safety"] = _best("ner_safety_score")
        ranking["best_ner_overall"] = _best("ner_overall_score")
        ranking["best_mfs_grounding"] = _best("mfs_grounding_score")
        ranking["lowest_contradiction"] = _best("mfs_contradiction_rate", higher_is_better=False)
        ranking["best_ira_safety"] = _best("ira_mean_safety")
        ranking["fastest"] = (
            min(models, key=lambda n: models[n]["runtime_sec"]) if models else None
        )
        return ranking
