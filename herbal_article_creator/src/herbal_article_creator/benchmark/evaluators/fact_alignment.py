"""
Fact-to-Article Alignment Evaluator
=====================================
Checks how well a generated article is grounded in the Master Fact Sheet (MFS).

For each MFS claim, the LLM judge determines whether the article:
  SUPPORTED    — article contains equivalent or corroborating content
  CONTRADICTED — article states the opposite of the claim
  MISSING      — article does not mention the claim at all

Metrics reported:
  grounding_score  : supported / total_claims  (0–1, higher = more grounded)
  contradiction_rate: contradicted / total_claims (0–1, lower = safer)
  coverage_score   : (supported + partially) / total_claims (0–1)
  evidence_traceability: list of {claim_id, verdict, article_snippet}
"""
from __future__ import annotations

import json
import re
from typing import NamedTuple

import litellm

from .mfs import MasterFactSheet
from ..llm_factory import create_judge_llm

# ──────────────────────────────────────────────────────────────────────────────
# Alignment prompt (batch: check multiple claims at once for efficiency)
# ──────────────────────────────────────────────────────────────────────────────

_ALIGN_PROMPT = """\
You are a fact-alignment auditor for herbal medicine articles.

TASK: For each CLAIM below, determine whether the ARTICLE supports,
contradicts, or omits that claim.

Verdicts:
  SUPPORTED    — The article explicitly states this or an equivalent fact.
  CONTRADICTED — The article states the opposite of this claim.
  MISSING      — The article does not mention this claim at all.

CLAIMS (JSON list):
{claims_json}

ARTICLE:
\"\"\"
{article}
\"\"\"

Respond ONLY with valid JSON (no markdown):
{{
  "alignments": [
    {{
      "claim_id": "<e.g. C001>",
      "verdict": "<SUPPORTED|CONTRADICTED|MISSING>",
      "article_snippet": "<≤100 chars from the article that led to this verdict, or empty string if MISSING>"
    }}
  ]
}}"""


# ──────────────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────────────

class ClaimAlignment(NamedTuple):
    claim_id: str
    claim: str
    category: str
    source_id: str
    confidence: str
    verdict: str            # SUPPORTED | CONTRADICTED | MISSING
    article_snippet: str


class AlignmentResult(NamedTuple):
    grounding_score: float       # supported / total (0–1)
    contradiction_rate: float    # contradicted / total (0–1)
    coverage_score: float        # (supported) / non-missing * 100 (0–1)
    total_claims: int
    supported: int
    contradicted: int
    missing: int
    alignments: list[ClaimAlignment]


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {"alignments": []}


def _call_llm(prompt: str, llm) -> str:
    cfg = {
        "model": getattr(llm, "model", "gemini/gemini-2.0-flash"),
        "api_key": getattr(llm, "api_key", None),
        "base_url": getattr(llm, "base_url", None),
    }
    kwargs: dict = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    if cfg.get("api_key"):
        kwargs["api_key"] = cfg["api_key"]
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    resp = litellm.completion(**kwargs)
    return resp.choices[0].message.content


def _batch_align(
    claims_batch: list[dict],
    article: str,
    llm,
) -> list[dict]:
    """Align a batch of claims against the article text."""
    claims_json = json.dumps(
        [{"claim_id": c["claim_id"], "claim": c["claim"]} for c in claims_batch],
        ensure_ascii=False, indent=2
    )
    prompt = _ALIGN_PROMPT.format(
        claims_json=claims_json,
        article=article[:4000],
    )
    try:
        raw = _call_llm(prompt, llm)
        data = _extract_json(raw)
        return data.get("alignments", [])
    except Exception as e:
        print(f"[FactAlign] Batch alignment error: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def evaluate(
    article_text: str,
    mfs: MasterFactSheet,
    llm=None,
    batch_size: int = 8,
) -> AlignmentResult:
    """
    Evaluate how well the article is grounded in the MFS.

    Parameters
    ----------
    article_text : the generated article to audit
    mfs          : Master Fact Sheet built by mfs.build()
    llm          : judge LLM
    batch_size   : number of claims to check per LLM call

    Returns
    -------
    AlignmentResult
    """
    if llm is None:
        llm = create_judge_llm()

    claims = mfs.claims
    if not claims:
        return AlignmentResult(0, 0, 0, 0, 0, 0, 0, [])

    # Build a lookup for rapid access
    claim_map = {c["claim_id"]: c for c in claims}

    # Process in batches to stay within token limits
    all_align_raw: list[dict] = []
    for i in range(0, len(claims), batch_size):
        batch = claims[i : i + batch_size]
        results = _batch_align(batch, article_text, llm)
        all_align_raw.extend(results)

    # Merge LLM verdicts with claim metadata
    verdict_map: dict[str, dict] = {a["claim_id"]: a for a in all_align_raw}
    alignments: list[ClaimAlignment] = []

    for c in claims:
        cid = c["claim_id"]
        raw_align = verdict_map.get(cid, {})
        verdict = raw_align.get("verdict", "MISSING").upper()
        if verdict not in ("SUPPORTED", "CONTRADICTED", "MISSING"):
            verdict = "MISSING"
        alignments.append(ClaimAlignment(
            claim_id=cid,
            claim=c.get("claim", ""),
            category=c.get("category", "unknown"),
            source_id=c.get("source_id", ""),
            confidence=c.get("confidence", "low"),
            verdict=verdict,
            article_snippet=raw_align.get("article_snippet", ""),
        ))

    total = len(alignments)
    supported = sum(1 for a in alignments if a.verdict == "SUPPORTED")
    contradicted = sum(1 for a in alignments if a.verdict == "CONTRADICTED")
    missing = sum(1 for a in alignments if a.verdict == "MISSING")
    non_missing = supported + contradicted

    return AlignmentResult(
        grounding_score=round(supported / total, 3) if total else 0.0,
        contradiction_rate=round(contradicted / total, 3) if total else 0.0,
        coverage_score=round(supported / non_missing, 3) if non_missing else 0.0,
        total_claims=total,
        supported=supported,
        contradicted=contradicted,
        missing=missing,
        alignments=alignments,
    )


def evaluate_all(
    model_outputs: dict[str, str],
    mfs: MasterFactSheet,
    llm=None,
) -> dict[str, AlignmentResult]:
    """
    Evaluate fact alignment for multiple model outputs.

    Parameters
    ----------
    model_outputs : {model_name: article_text}
    mfs           : Master Fact Sheet
    """
    if llm is None:
        llm = create_judge_llm()

    results = {}
    for name, text in model_outputs.items():
        print(f"[FactAlign] Evaluating: {name} ...")
        results[name] = evaluate(text, mfs, llm=llm)
    return results
