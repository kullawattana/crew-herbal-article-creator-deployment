"""
NER-KPI Evaluator
=================
Mirrors the logic of crew-herbal-article-creator-evaluation/
Multi-LLM-NER-KPI-with-Backend/server.py

Extracts Named Entities in 3 categories per article, then scores:
  - Cultural  : Geographic, cultural refs, traditional medicine systems
  - Scientific: Compounds, lab methods, measurements, mechanisms
  - Safety    : Diseases, adverse effects, regulatory bodies, warnings

Threshold: ≥ 10 entities per category → PASS (score 100)
           < 10 entities              → score = (count / 10) × 100

Integration modes (tried in order):
  1. Flask server auto-detect at http://localhost:3000
     (crew-herbal-article-creator-evaluation/Multi-LLM-NER-KPI-with-Backend)
  2. Inline NER using litellm directly (no server needed)
"""
from __future__ import annotations

import json
import os
import re
from typing import NamedTuple

import requests

from ..llm_factory import create_judge_llm

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

FLASK_BASE_URL = os.getenv("NER_SERVER_URL", "http://localhost:3000")
PASS_THRESHOLD = int(os.getenv("NER_PASS_THRESHOLD", "10"))

# Category → display label mapping (matches server.py categories)
CATEGORIES = {
    "cultural": "Cultural Authenticity",
    "scientific": "Scientific Validity",
    "safety": "Safety & Compliance",
}

# ──────────────────────────────────────────────────────────────────────────────
# NER prompts (identical to server.py create_prompt() for reproducibility)
# ──────────────────────────────────────────────────────────────────────────────

_PROMPTS: dict[str, str] = {
    "cultural": """\
You are analyzing a herbal medicine article for CULTURAL AUTHENTICITY entities.

Extract ALL cultural entities including:
- Geographic/cultural references (Thai, Indian, Malaysian, Japanese, Korean, Western, Middle Eastern, etc.)
- Traditional medicine systems (Ayurveda, Traditional Chinese Medicine, etc.)
- Cultural institutions (museums, foundations, centers)
- Traditional practices, wisdom, and heritage
- Cultural locations and communities
- Wellness traditions and holistic practices

For each entity found, provide:
1. The entity name (exact text from article)
2. Number of occurrences in the text
3. Brief reasoning why it's a cultural entity

Article text (first 5000 characters):
{text}

Respond ONLY in valid JSON format with no markdown, no backticks, no preamble:
{{
  "entities": [
    {{
      "name": "Thai",
      "count": 3,
      "reasoning": "Geographic and cultural reference to Thailand's traditional medicine"
    }}
  ],
  "total_count": 12
}}""",

    "scientific": """\
You are analyzing a herbal medicine article for SCIENTIFIC VALIDITY entities.

Extract ALL scientific entities including:
- Chemical compounds and active ingredients (Curcumin, alkaloids, etc.)
- Scientific methods (LC-MS/MS, HPLC, clinical trials, etc.)
- Measurements and units (mg/kg, nmol, AUC, IC50, etc.)
- Biological processes and mechanisms (apoptosis, enzyme inhibition, etc.)
- Pharmacological terms (bioavailability, pharmacokinetics, etc.)
- Research methodologies and experimental approaches

For each entity found, provide:
1. The entity name (exact text from article)
2. Number of occurrences in the text
3. Brief reasoning why it's a scientific entity

Article text (first 5000 characters):
{text}

Respond ONLY in valid JSON format with no markdown, no backticks, no preamble:
{{
  "entities": [
    {{
      "name": "Curcumin",
      "count": 5,
      "reasoning": "Main bioactive compound - scientific chemical name"
    }}
  ],
  "total_count": 20
}}""",

    "safety": """\
You are analyzing a herbal medicine article for SAFETY & COMPLIANCE entities.

Extract ALL safety-related entities including:
- Diseases and medical conditions (Alzheimer's, Cancer, liver injury, etc.)
- Adverse effects and toxicity (hepatotoxicity, side effects, etc.)
- Regulatory bodies (FDA, Thai FDA, WHO, etc.)
- Safety warnings, contraindications, and precautions
- Clinical symptoms and biomarkers (HLA alleles, enzyme elevations, etc.)
- Drug interactions and dosage information

For each entity found, provide:
1. The entity name (exact text from article)
2. Number of occurrences in the text
3. Brief reasoning why it's a safety entity

Article text (first 5000 characters):
{text}

Respond ONLY in valid JSON format with no markdown, no backticks, no preamble:
{{
  "entities": [
    {{
      "name": "liver injury",
      "count": 4,
      "reasoning": "Adverse effect - important safety concern"
    }}
  ],
  "total_count": 11
}}""",
}

# ──────────────────────────────────────────────────────────────────────────────
# Result type
# ──────────────────────────────────────────────────────────────────────────────

class CategoryResult(NamedTuple):
    category: str          # "cultural" | "scientific" | "safety"
    entity_count: int
    score: float           # 0–100
    passed: bool           # entity_count >= PASS_THRESHOLD
    entities: list[dict]   # [{name, count, reasoning}, ...]


class NERKPIResult(NamedTuple):
    cultural: CategoryResult
    scientific: CategoryResult
    safety: CategoryResult
    source: str            # "flask_server" | "inline"

    @property
    def overall_score(self) -> float:
        """Average of the three category scores."""
        return round((self.cultural.score + self.scientific.score + self.safety.score) / 3, 2)

    @property
    def all_pass(self) -> bool:
        return self.cultural.passed and self.scientific.passed and self.safety.passed


# ──────────────────────────────────────────────────────────────────────────────
# Flask server integration
# ──────────────────────────────────────────────────────────────────────────────

def _flask_available() -> bool:
    try:
        r = requests.get(f"{FLASK_BASE_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _call_flask(text: str, category: str, model: str = "gemini-2.0-flash") -> dict:
    """Call the running NER Flask server."""
    payload = {"text": text, "category": category, "model": model}
    r = requests.post(f"{FLASK_BASE_URL}/api/analyze", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _analyze_via_flask(text: str) -> tuple[dict, str]:
    """Run all 3 categories via the Flask server."""
    results = {}
    model = os.getenv("NER_FLASK_MODEL", "gemini-2.0-flash")
    for cat in CATEGORIES:
        data = _call_flask(text, cat, model=model)
        results[cat] = {
            "entities": data.get("entities", []),
            "total_count": data.get("count", 0),
        }
    return results, "flask_server"


# ──────────────────────────────────────────────────────────────────────────────
# Inline NER (no Flask required)
# ──────────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {"entities": [], "total_count": 0}


def _call_llm_inline(prompt: str, llm) -> str:
    """Call litellm via crewai LLM wrapper."""
    import litellm

    cfg = {
        "model": getattr(llm, "model", "gemini/gemini-2.0-flash"),
        "api_key": getattr(llm, "api_key", None),
        "base_url": getattr(llm, "base_url", None),
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    kwargs: dict = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    if cfg.get("api_key"):
        kwargs["api_key"] = cfg["api_key"]
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content


def _analyze_inline(text: str, llm) -> tuple[dict, str]:
    """Run all 3 categories inline using litellm."""
    truncated = text[:5000]
    results = {}
    for cat, prompt_tpl in _PROMPTS.items():
        prompt = prompt_tpl.format(text=truncated)
        try:
            raw = _call_llm_inline(prompt, llm)
            data = _extract_json(raw)
            results[cat] = {
                "entities": data.get("entities", []),
                "total_count": data.get("total_count", len(data.get("entities", []))),
            }
        except Exception as e:
            print(f"[NER-KPI] {cat} inline error: {e}")
            results[cat] = {"entities": [], "total_count": 0}
    return results, "inline"


# ──────────────────────────────────────────────────────────────────────────────
# Score calculation (mirrors server.py completeness/efficacy logic)
# ──────────────────────────────────────────────────────────────────────────────

def _to_category_result(cat: str, data: dict) -> CategoryResult:
    count = data.get("total_count", len(data.get("entities", [])))
    score = min(100.0, round((count / PASS_THRESHOLD) * 100, 2))
    return CategoryResult(
        category=cat,
        entity_count=count,
        score=score,
        passed=count >= PASS_THRESHOLD,
        entities=data.get("entities", []),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def evaluate(article_text: str, llm=None) -> NERKPIResult:
    """
    Evaluate a single article for Cultural / Scientific / Safety NER-KPI.

    Parameters
    ----------
    article_text : The generated article text.
    llm          : Optional crewai.LLM — used for inline mode.
                   Defaults to create_judge_llm().

    Returns
    -------
    NERKPIResult
    """
    if llm is None:
        llm = create_judge_llm()

    # Try Flask server first, then inline
    if _flask_available():
        print("[NER-KPI] Using Flask server at", FLASK_BASE_URL)
        try:
            raw_results, source = _analyze_via_flask(article_text)
        except Exception as e:
            print(f"[NER-KPI] Flask failed ({e}), falling back to inline.")
            raw_results, source = _analyze_inline(article_text, llm)
    else:
        print("[NER-KPI] Flask server not found — running inline NER.")
        raw_results, source = _analyze_inline(article_text, llm)

    return NERKPIResult(
        cultural=_to_category_result("cultural", raw_results.get("cultural", {})),
        scientific=_to_category_result("scientific", raw_results.get("scientific", {})),
        safety=_to_category_result("safety", raw_results.get("safety", {})),
        source=source,
    )


def evaluate_all(
    model_outputs: dict[str, str],
    llm=None,
) -> dict[str, NERKPIResult]:
    """
    Evaluate multiple model outputs.

    Parameters
    ----------
    model_outputs : {model_name: article_text}
    llm           : shared judge LLM

    Returns
    -------
    {model_name: NERKPIResult}
    """
    if llm is None:
        llm = create_judge_llm()

    # Check Flask once before loop
    use_flask = _flask_available()
    if use_flask:
        print(f"[NER-KPI] Flask server online at {FLASK_BASE_URL} — using server mode.")
    else:
        print("[NER-KPI] Running NER inline (Flask server not detected).")

    results = {}
    for name, text in model_outputs.items():
        print(f"[NER-KPI] Evaluating: {name} ...")
        results[name] = evaluate(text, llm=llm)
    return results
