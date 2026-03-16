# Benchmark Framework — Herbal Article Creator

Evaluation suite for comparing article generation approaches and measuring
component contributions in the Herbal Article Creator system.

---

## Architecture Overview

```
benchmark/
├── runner.py                   # Main orchestrator (BenchmarkRunner)
├── report.py                   # Console + Markdown report generator
├── llm_factory.py              # Shared LLM factory (judge LLMs)
│
├── models/                     # Article generators
│   ├── no_rag_llm.py           # Baseline: pure LLM, no tools
│   ├── single_agent_rag.py     # Single agent + PubMed + Pinecone
│   └── multi_agent.py          # Full CrewAI multi-agent crew
│
├── evaluators/                 # Evaluation metrics
│   ├── text_metrics.py         # BLEU / ROUGE-1/2/L
│   ├── llm_judge.py            # LLM-as-Judge (Safety, Validity, Hallucination)
│   ├── ner_kpi.py              # NER-KPI (Cultural / Scientific / Safety entities)
│   ├── go_no_go.py             # Go/No-Go threshold decisions
│   ├── mfs.py                  # Master Fact Sheet builder
│   ├── fact_alignment.py       # Fact-to-Article alignment (MFS grounding)
│   └── inter_rater.py          # Blind evaluation + Cohen's κ + Krippendorff's α
│
└── ablation/                   # Ablation study
    ├── configs.py              # 5 ablation configurations
    └── runner.py               # AblationRunner + delta analysis
```

---

## Full Benchmark Pipeline Flowchart

```
┌─────────────────────────────────────────────────────────────┐
│                    BENCHMARK PIPELINE                        │
│                  uv run benchmark                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │   STEP 1: GENERATE    │
          │  Article Generation   │
          └───────────┬───────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌────▼────────┐
  │ No-RAG  │   │  Single-  │  │   Multi-    │
  │   LLM   │   │ Agent RAG │  │   Agent     │
  │Baseline │   │PubMed+    │  │  (CrewAI)   │
  │         │   │Pinecone   │  │             │
  └────┬────┘   └─────┬─────┘  └────┬────────┘
       │              │              │
       └──────────────┼──────────────┘
                      │ Articles (text)
          ┌───────────▼───────────┐
          │  STEP 2: BUILD MFS    │
          │  Master Fact Sheet    │
          │  PubMed top-3 papers  │
          │  Pinecone top-5 docs  │
          │  → Verified claims    │
          └───────────┬───────────┘
                      │ MasterFactSheet
          ┌───────────▼───────────┐
          │  STEP 3: BLEU/ROUGE   │
          │  Text-overlap vs ref  │
          │  sacrebleu + rouge-   │
          │  score                │
          └───────────┬───────────┘
                      │ TextMetrics
          ┌───────────▼───────────┐
          │  STEP 4: LLM JUDGE    │
          │  Single-judge rubric  │
          │  • Safety (0-10)      │
          │  • Scientific Valid.  │
          │  • Hallucination rate │
          │  • Citations found    │
          └───────────┬───────────┘
                      │ JudgeResult
          ┌───────────▼───────────┐
          │   STEP 5: NER-KPI     │
          │  Entity extraction    │
          │  • Cultural entities  │
          │  • Scientific entities│
          │  • Safety entities    │
          │  Pass: ≥10 per cat.   │
          └───────────┬───────────┘
                      │ NERKPIResult
          ┌───────────▼───────────┐
          │  STEP 6: FACT ALIGN   │
          │  MFS Grounding check  │
          │  Per claim verdict:   │
          │  SUPPORTED /          │
          │  CONTRADICTED /       │
          │  MISSING              │
          └───────────┬───────────┘
                      │ AlignmentResult
          ┌───────────▼───────────┐
          │  STEP 7: INTER-RATER  │  ← Blind evaluation
          │  3 independent judges │    (Model A/B/C)
          │  Gemini 2.0 Flash     │
          │  GPT-4o-mini          │
          │  Claude Haiku 4.5     │
          │  → Cohen's κ (linear) │
          │  → Krippendorff's α   │
          └───────────┬───────────┘
                      │ IRAAgreement
          ┌───────────▼───────────┐
          │  STEP 8: GO / NO-GO   │
          │  Per-model decision   │
          │  ✅ GO                │
          │  ⚠️  CONDITIONAL GO   │
          │  ❌ NO-GO             │
          └───────────┬───────────┘
                      │ GoNoGoResult
          ┌───────────▼───────────┐
          │  STEP 9: RANKING      │
          │  Best model per metric│
          └───────────┬───────────┘
                      │
          ┌───────────▼───────────┐
          │  STEP 10: SAVE        │
          │  outputs/benchmark_   │
          │  comparison_*.json    │
          │  + Markdown report    │
          └───────────────────────┘
```

---

## Ablation Study Flowchart

```
┌─────────────────────────────────────────────────────────────┐
│                   ABLATION STUDY                            │
│                 uv run ablation                             │
└─────────────────────┬───────────────────────────────────────┘
                      │
     ┌────────────────┼──────────────────────────┐
     │         5 CONFIGURATIONS                  │
     │                                           │
  ┌──▼──────────┐  ┌───────────┐  ┌──────────┐  │
  │  baseline   │  │ +pubmed   │  │+pinecone │  │
  │  (No tools) │  │(PubMed   │  │(Pinecone │  │
  │             │  │ only)    │  │ only)    │  │
  └──┬──────────┘  └─────┬─────┘  └────┬─────┘  │
     │                   │             │         │
  ┌──▼──────────────────▼─────────────▼─────┐   │
  │        +pubmed+pinecone                 │   │
  │        (Both retrievers = Single RAG)   │   │
  └──────────────────┬──────────────────────┘   │
                     │                          │
  ┌──────────────────▼──────────────────────┐   │
  │             +multi_agent                │   │
  │         (Full CrewAI Pipeline)          │   │
  └──────────────────┬──────────────────────┘   │
                     │                          │
     └───────────────┴──────────────────────────┘
                      │ Generate articles (5 runs)
          ┌───────────▼───────────┐
          │     EVALUATE EACH     │
          │  BLEU/ROUGE + LLM     │
          │  Judge (Safety,       │
          │  Validity, Hallucin.) │
          └───────────┬───────────┘
                      │
          ┌───────────▼───────────┐
          │    DELTA ANALYSIS     │  7 comparison pairs:
          │                       │
          │  baseline → +pubmed   │  Value of PubMed
          │  baseline → +pinecone │  Value of Pinecone
          │  baseline → +pub+pin  │  Value of both
          │  +pubmed → +pub+pin   │  Marginal Pinecone
          │  +pinecone → +pub+pin │  Marginal PubMed
          │  +pub+pin → +multi    │  Value of multi-agent
          │  baseline → +multi    │  Total system gain
          └───────────┬───────────┘
                      │
          ┌───────────▼───────────┐
          │  SAVE + PRINT TABLE   │
          │  outputs/ablation_    │
          │  *.json               │
          └───────────────────────┘
```

---

## Quick Start

### 1. Run Full Benchmark

```bash
# Set required env vars
export HERBS_FOR_RESEARCH="Curcuma longa"
export HERBS_FOR_RESEARCH_ENG="Turmeric"
export HERBS_FOR_RESEARCH_THAI="ขมิ้นชัน"

uv run benchmark
```

### 2. Run Ablation Study

```bash
uv run ablation

# Run specific configs only
ABLATION_CONFIGS="baseline,+pubmed,+multi_agent" uv run ablation
```

### 3. Load precomputed Multi-Agent output (skip generation)

```bash
BENCHMARK_MULTI_PRECOMP="outputs/task_17_20260208.txt" uv run benchmark
```

---

## Environment Variables

### Core

| Variable | Description | Default |
|----------|-------------|---------|
| `HERBS_FOR_RESEARCH` | Scientific name (e.g. `Curcuma longa`) | **required** |
| `HERBS_FOR_RESEARCH_ENG` | English name (e.g. `Turmeric`) | **required** |
| `HERBS_FOR_RESEARCH_THAI` | Thai name (e.g. `ขมิ้นชัน`) | **required** |
| `OUTPUT_LANG` | `en` or `th` | `en` |

### Model Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `BENCHMARK_NO_RAG` | Run No-RAG LLM baseline | `true` |
| `BENCHMARK_SINGLE_RAG` | Run Single-Agent RAG | `true` |
| `BENCHMARK_MULTI_AGENT` | Run Multi-Agent crew | `true` |
| `BENCHMARK_MULTI_PRECOMP` | Path to pre-generated Multi-Agent `.txt` | — |
| `BENCHMARK_REFERENCE_FILE` | Path to gold-standard reference `.txt` | — |

### Evaluation Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `BENCHMARK_BUILD_MFS` | Build Master Fact Sheet | `true` |
| `BENCHMARK_MFS_FILE` | Path to pre-built MFS `.json` | — |
| `BENCHMARK_PUBMED_TOP_K` | PubMed papers for MFS | `3` |
| `BENCHMARK_PINECONE_TOP_K` | Pinecone snippets for MFS | `5` |
| `BENCHMARK_INTER_RATER` | Run multi-judge IRA | `true` |
| `BENCHMARK_BLIND` | Anonymize outputs before judging | `true` |

### Go/No-Go Thresholds (optional override)

| Variable | Default | Meaning |
|----------|---------|---------|
| `THRESH_SAFETY_GO` | `7.0` | Safety ≥ 7.0 → GO |
| `THRESH_SAFETY_NOGO` | `5.0` | Safety < 5.0 → NO-GO |
| `THRESH_VALIDITY_GO` | `7.0` | Validity ≥ 7.0 → GO |
| `THRESH_VALIDITY_NOGO` | `5.0` | Validity < 5.0 → NO-GO |
| `THRESH_HALLUC_GO` | `0.25` | Hallucination ≤ 0.25 → GO |
| `THRESH_HALLUC_NOGO` | `0.50` | Hallucination > 0.50 → NO-GO |
| `THRESH_NER_GO` | `80.0` | NER score ≥ 80% → GO |
| `THRESH_NER_NOGO` | `50.0` | NER score < 50% → NO-GO |
| `THRESH_BLEU_GO` | `20.0` | BLEU ≥ 20 → GO |
| `THRESH_BLEU_NOGO` | `5.0` | BLEU < 5 → NO-GO |

---

## Evaluation Metrics

### 1. Text Overlap

| Metric | Tool | Range | Higher = Better |
|--------|------|-------|----------------|
| BLEU | `sacrebleu` | 0–100 | Yes |
| ROUGE-1 F1 | `rouge-score` | 0–1 | Yes |
| ROUGE-2 F1 | `rouge-score` | 0–1 | Yes |
| ROUGE-L F1 | `rouge-score` | 0–1 | Yes |

### 2. LLM-as-Judge (Single Judge — Gemini 2.0 Flash)

| Metric | Range | GO threshold | NO-GO threshold |
|--------|-------|-------------|-----------------|
| Safety Score | 0–10 | ≥ 7.0 | < 5.0 |
| Scientific Validity | 0–10 | ≥ 7.0 | < 5.0 |
| Hallucination Rate | 0–1 | ≤ 0.25 | > 0.50 |
| Citations Found | count | — | — |

### 3. NER-KPI (Multi-LLM NER)

| Category | Pass threshold | Source |
|----------|---------------|--------|
| Cultural entities | ≥ 10 entities | Traditional use, cultural context |
| Scientific entities | ≥ 10 entities | Compounds, mechanisms, clinical terms |
| Safety entities | ≥ 10 entities | Contraindications, side effects, dosage |

> Auto-detects Flask server at `localhost:3000`; falls back to inline litellm if not running.

### 4. Master Fact Sheet (MFS) Grounding

| Metric | Description |
|--------|-------------|
| Grounding Score | `supported / total_claims` (0–1) |
| Contradiction Rate | `contradicted / total_claims` (0–1, lower = better) |
| Coverage Score | `supported / (supported + contradicted)` (0–1) |

Verdict per claim: **SUPPORTED** / **CONTRADICTED** / **MISSING**

### 5. Inter-Rater Agreement (Blind)

Three independent LLM judges score each article anonymously (Model A / B / C):

| Judge | Model |
|-------|-------|
| Judge 1 | Gemini 2.0 Flash |
| Judge 2 | GPT-4o-mini |
| Judge 3 | Claude Haiku 4.5 |

Agreement statistics:

| Statistic | Description |
|-----------|-------------|
| Cohen's κ (weighted, linear) | Pairwise agreement per judge-pair per metric |
| Krippendorff's α (ordinal) | Agreement across all judges |

Interpretation guide:

| κ / α | Interpretation |
|--------|---------------|
| < 0.20 | Slight (unreliable) |
| 0.20–0.40 | Fair |
| 0.40–0.60 | Moderate |
| 0.60–0.80 | **Substantial** ← publishable target |
| > 0.80 | Almost Perfect |

### 6. Go/No-Go Decision

```
ALL metrics ≥ GO threshold  →  ✅ GO
ANY metric  <  NO-GO zone   →  ❌ NO-GO
Otherwise                   →  ⚠️  CONDITIONAL GO
```

---

## Ablation Configurations

| Config | PubMed | Pinecone | Multi-Agent | Description |
|--------|--------|----------|-------------|-------------|
| `baseline` | ✗ | ✗ | ✗ | Pure LLM knowledge |
| `+pubmed` | ✓ | ✗ | ✗ | + Scientific literature retrieval |
| `+pinecone` | ✗ | ✓ | ✗ | + Internal herbal knowledge base |
| `+pubmed+pinecone` | ✓ | ✓ | ✗ | Both retrievers (= Single-Agent RAG) |
| `+multi_agent` | ✓ | ✓ | ✓ | Full CrewAI pipeline |

### Delta Pairs (Component Contribution)

| From | To | What it measures |
|------|----|-----------------|
| `baseline` | `+pubmed` | Value of PubMed retrieval |
| `baseline` | `+pinecone` | Value of Pinecone knowledge base |
| `baseline` | `+pubmed+pinecone` | Value of both retrievers combined |
| `+pubmed` | `+pubmed+pinecone` | Marginal value of adding Pinecone |
| `+pinecone` | `+pubmed+pinecone` | Marginal value of adding PubMed |
| `+pubmed+pinecone` | `+multi_agent` | Value of multi-agent orchestration |
| `baseline` | `+multi_agent` | **Total system gain** |

---

## Output Files

All outputs are saved to the `outputs/` directory:

```
outputs/
├── benchmark_comparison_YYYYMMDD_HHMMSS.json   # Full results (all metrics)
├── benchmark_report_YYYYMMDD_HHMMSS.md         # Markdown report
├── benchmark_no_rag_llm_YYYYMMDD_HHMMSS.txt    # Generated article (No-RAG)
├── benchmark_single_agent_rag_*.txt             # Generated article (Single RAG)
├── benchmark_multi_agent_*.txt                  # Generated article (Multi-Agent)
├── mfs_Curcuma_longa_*.json                     # Master Fact Sheet
└── ablation_YYYYMMDD_HHMMSS.json               # Ablation study results
```

---

## Programmatic Usage

### Full Benchmark

```python
from herbal_article_creator.benchmark.runner import BenchmarkRunner
from herbal_article_creator.benchmark.report import print_report, save_markdown

runner = BenchmarkRunner(
    herbs="Curcuma longa",
    herbs_eng="Turmeric",
    herbs_thai="ขมิ้นชัน",
    lang="en",
    build_mfs=True,           # Build Master Fact Sheet
    run_inter_rater=True,     # Multi-judge blind evaluation
    blind_evaluation=True,    # Anonymize outputs (Model A/B/C)
    pubmed_top_k=3,
    pinecone_top_k=5,
    output_dir="outputs",
)

results = runner.run()
print_report(results)
save_markdown(results, output_dir="outputs")
```

### Ablation Study

```python
from herbal_article_creator.benchmark.ablation.runner import AblationRunner

runner = AblationRunner(
    herbs="Curcuma longa",
    herbs_eng="Turmeric",
    herbs_thai="ขมิ้นชัน",
    configs=["baseline", "+pubmed", "+multi_agent"],  # None = all
)
results = runner.run()
runner.print_table(results)
runner.print_deltas(results)
```

### Individual Evaluators

```python
from herbal_article_creator.benchmark.llm_factory import create_judge_llm
from herbal_article_creator.benchmark.evaluators import (
    text_metrics, llm_judge, ner_kpi, go_no_go,
    mfs as mfs_module, fact_alignment, inter_rater,
)

llm = create_judge_llm()

# BLEU / ROUGE
tm = text_metrics.compute(article_text, reference_text)

# LLM Judge
jr = llm_judge.judge_article(article_text, llm=llm)

# NER-KPI
nr = ner_kpi.evaluate(article_text, llm=llm)

# Master Fact Sheet + Fact Alignment
fact_sheet = mfs_module.build("Curcuma longa", "Turmeric", "ขมิ้นชัน", llm=llm)
ar = fact_alignment.evaluate(article_text, fact_sheet, llm=llm)

# Go/No-Go
gng = go_no_go.evaluate({
    "safety_score": jr.safety_score,
    "scientific_validity": jr.validity_score,
    "hallucination_rate": jr.hallucination_rate,
    "bleu": tm.bleu,
})
print(gng.decision)  # GO | CONDITIONAL GO | NO-GO

# Inter-Rater (blind, multi-judge)
ira_results = inter_rater.evaluate_all(
    {"model_a": article_a, "model_b": article_b},
    blind=True,
)
kappas = inter_rater.kappa_summary(ira_results)
```

---

## Academic Framing (LLM-as-Judge Paradigm)

This framework adopts the **LLM-as-Judge** evaluation paradigm
(Zheng et al., 2023; *Judging LLM-as-a-Judge with MT-Bench*),
which has demonstrated strong correlation with human judgment (r > 0.8)
in text quality assessment tasks.

### Why This Approach Is Academically Valid

| Concern | Mitigation in This System |
|---------|--------------------------|
| Single judge may be biased | **3 independent judges** from 3 different providers |
| Judge knows which model it is | **Blind evaluation** — outputs anonymized as Model A/B/C |
| LLM agreement may be spurious | **Cohen's κ ≥ 0.6** required (Substantial) for reportable results |
| Claims not grounded in evidence | **MFS Fact Alignment** checks against PubMed peer-reviewed sources |
| Hallucination hard to detect automatically | Dual check: LLM Judge hallucination_rate + MFS contradiction_rate |

### How to Report Results in a Paper

```
We evaluate article quality using an automated multi-judge framework
comprising three independent LLM evaluators: Gemini 2.0 Flash, GPT-4o-mini,
and Claude Haiku 4.5. To mitigate position and familiarity bias, all model
outputs were anonymized prior to evaluation (blind evaluation protocol).
Inter-rater agreement was measured using weighted Cohen's κ and
Krippendorff's α. Factual grounding was assessed against a Master Fact Sheet
(MFS) of verified claims extracted from PubMed abstracts.
```

---

## Human Evaluation Guideline

If human expert evaluation is available, use the following protocol
to validate and complement the automated scores.

### Recommended Evaluators

| Role | Count | Evaluates |
|------|-------|-----------|
| Pharmacist / Thai traditional medicine practitioner | 2–3 | Safety + Clinical accuracy |
| NLP / AI researcher | 1–2 | Coherence + Factual quality |

> Minimum for publishable results: **2 raters**, κ ≥ 0.60

### Evaluation Criteria (Likert 1–5)

| Criteria | Scale | Description |
|----------|-------|-------------|
| Clinical Safety | 1–5 | Are dosage, contraindications, and warnings appropriate? |
| Thai Traditional Context | 1–5 | Is the cultural and traditional use accurately represented? |
| Scientific Accuracy | 1–5 | Are pharmacological claims consistent with current evidence? |
| Overall Usefulness | 1–5 | Would this article be useful in a real wellness application? |

### Correlating Human vs Automated Scores

```python
import numpy as np

human_scores   = [4.2, 3.8, 4.5]   # per model, from human raters
llm_scores     = [7.8, 6.5, 8.2]   # safety_score / 2 (normalize to 0-5)

r = np.corrcoef(human_scores, llm_scores)[0, 1]
print(f"Human-AI alignment: r = {r:.3f}")
# r ≥ 0.7 → LLM judge can substitute human evaluation
```

---

## Limitations

The following limitations should be disclosed in any publication:

1. **LLM-based evaluation** — Judges are language models, not domain experts.
   Clinical plausibility of dosage and drug interactions cannot be fully verified automatically.

2. **Single-herb evaluation** — Results were obtained on one herb (Turmeric / *Curcuma longa*).
   Generalizability to other herbs requires additional experiments.

3. **Reference text source** — BLEU/ROUGE scores use the Multi-Agent output as reference,
   which originates from the same system family being evaluated.

4. **PubMed coverage** — MFS uses top-3 PubMed abstracts. Rare herbs with limited
   literature may yield sparse fact sheets.

5. **No human expert validation** — Automated evaluation has not been calibrated against
   pharmacist or traditional medicine practitioner scores.

### Suggested Limitation Paragraph (for paper)

> *"This study relies on automated LLM-based evaluation due to resource constraints.
> While human expert validation was not conducted, the use of three independent judges
> with substantial inter-rater agreement (κ = X.XX) and fact-grounding against
> PubMed-derived claims provides a rigorous proxy for expert assessment.
> Results are demonstrated on a single herb species; future work should validate
> generalizability across a broader herbal dataset and include domain expert review."*

---

## Future Work

### 1. Expand Dataset
- Test on multiple herb species → generalizable conclusions
- Evaluate both `en` and `th` outputs → multilingual performance comparison
- Build a **gold standard herbal article dataset** from validated MFS outputs

### 2. Human-in-the-Loop Validation
- Add pharmacist annotation interface for MFS claim verification
- Measure **human-AI alignment** (Pearson r) between LLM judge and expert scores
- If r ≥ 0.7 → publish automated system as validated proxy for human review

### 3. Continuous Improvement Loop

```
Benchmark results
      ↓
Go/No-Go decision
      ↓ (NO-GO or CONDITIONAL GO)
Prompt optimization (DSPy) or RAG tuning
      ↓
Re-run benchmark → compare Δ metrics
      ↓
Validated MFS claims → Gold standard dataset
```

### 4. Chain-of-Thought Judge
Add reasoning trace before scoring to improve judge reliability:
```python
# In llm_judge.py — extend prompt to require step-by-step reasoning
# before producing the final JSON score
```

### 5. Deployment Integration
- Trigger benchmark automatically after each `uv run herbal_article_creator`
- Alert if Go/No-Go = NO-GO before article is published to end users
