"""
Master Fact Sheet (MFS) Builder
================================
Aggregates verified evidence from PubMed + Pinecone + RAG into a
structured, source-traceable fact sheet that serves as the ground-truth
reference for Fact-to-Article alignment.

MFS Schema (per claim):
  claim_id     : "C001", "C002", ...
  claim        : declarative sentence (e.g. "Curcumin inhibits NF-κB")
  category     : "pharmacological" | "phytochemical" | "clinical" |
                 "safety" | "cultural" | "wellness"
  source_type  : "pubmed" | "pinecone" | "rag"
  source_id    : PMID / Pinecone vector ID / RAG chunk ID
  source_title : paper title or document name
  evidence_text: exact extracted passage (≤ 300 chars)
  confidence   : "high" | "medium" | "low"

Workflow:
  1. Search PubMed (top-k papers) → extract claims
  2. Search Pinecone (top-k snippets) → extract claims
  3. De-duplicate overlapping claims
  4. Save MFS as JSON + return structured object
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import litellm

from ..llm_factory import create_judge_llm

# ──────────────────────────────────────────────────────────────────────────────
# Claim extraction prompt
# ──────────────────────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """\
You are a scientific fact extractor specialising in herbal medicine.

Given the SOURCE TEXT below (from {source_type}: {source_id}), extract
all VERIFIABLE FACTUAL CLAIMS about **{herb_eng}** ({herb}).

Rules:
- Each claim must be a single, self-contained declarative sentence.
- Include: compounds, mechanisms, clinical effects, dosages, safety data,
  cultural uses. Exclude vague marketing language.
- Assign category: pharmacological | phytochemical | clinical | safety |
  cultural | wellness
- Assign confidence: high (RCT/meta-analysis), medium (in-vivo study),
  low (in-vitro/anecdotal)
- Extract ONLY claims explicitly stated in the text (no inference).
- Maximum 8 claims per source.

SOURCE TEXT:
\"\"\"
{text}
\"\"\"

Respond with ONLY valid JSON (no markdown):
{{
  "claims": [
    {{
      "claim": "<declarative sentence>",
      "category": "<category>",
      "confidence": "<high|medium|low>",
      "evidence_text": "<exact quote ≤200 chars>"
    }}
  ]
}}"""


# ──────────────────────────────────────────────────────────────────────────────
# MFS data structure
# ──────────────────────────────────────────────────────────────────────────────

class MasterFactSheet:
    """
    In-memory Master Fact Sheet — a list of verified claims with provenance.
    """

    def __init__(self, herb: str, herb_eng: str, herb_thai: str):
        self.herb = herb
        self.herb_eng = herb_eng
        self.herb_thai = herb_thai
        self.timestamp = datetime.now().isoformat()
        self.claims: list[dict] = []
        self.sources: list[dict] = []
        self._claim_counter = 0

    def add_claims(
        self,
        raw_claims: list[dict],
        source_type: str,
        source_id: str,
        source_title: str = "",
    ) -> None:
        for c in raw_claims:
            self._claim_counter += 1
            self.claims.append({
                "claim_id": f"C{self._claim_counter:03d}",
                "claim": c.get("claim", ""),
                "category": c.get("category", "unknown"),
                "source_type": source_type,
                "source_id": source_id,
                "source_title": source_title,
                "evidence_text": c.get("evidence_text", "")[:300],
                "confidence": c.get("confidence", "low"),
            })

    def to_dict(self) -> dict:
        return {
            "herb": self.herb,
            "herb_eng": self.herb_eng,
            "herb_thai": self.herb_thai,
            "timestamp": self.timestamp,
            "total_claims": len(self.claims),
            "claims": self.claims,
            "sources": self.sources,
        }

    def save(self, output_dir: str | Path = "outputs") -> Path:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = p / f"mfs_{self.herb.replace(' ', '_')}_{ts}.json"
        out.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[MFS] Saved: {out}")
        return out


# ──────────────────────────────────────────────────────────────────────────────
# LLM claim extractor
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
    return {"claims": []}


def _llm_extract_claims(
    text: str,
    herb: str,
    herb_eng: str,
    source_type: str,
    source_id: str,
    llm,
) -> list[dict]:
    """Use LLM to extract structured claims from a text passage."""
    if not text or not text.strip():
        return []

    prompt = _EXTRACT_PROMPT.format(
        source_type=source_type,
        source_id=source_id,
        herb_eng=herb_eng,
        herb=herb,
        text=text[:3000],
    )

    cfg = {
        "model": getattr(llm, "model", "gemini/gemini-2.0-flash"),
        "api_key": getattr(llm, "api_key", None),
        "base_url": getattr(llm, "base_url", None),
        "temperature": 0.1,
        "max_tokens": 1500,
    }
    kwargs: dict[str, Any] = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
    }
    if cfg.get("api_key"):
        kwargs["api_key"] = cfg["api_key"]
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]

    try:
        resp = litellm.completion(**kwargs)
        raw = resp.choices[0].message.content
        data = _extract_json(raw)
        return data.get("claims", [])
    except Exception as e:
        print(f"[MFS] Claim extraction error ({source_id}): {e}")
        return []


# ──────────────────────────────────────────────────────────────────────────────
# PubMed source
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_pubmed_claims(
    herb: str,
    herb_eng: str,
    mfs: MasterFactSheet,
    llm,
    top_k: int = 3,
) -> None:
    """Query PubMed and extract claims from top-k abstracts."""
    try:
        from ...tools.pubmed_tools import PubMedSearchTool, PubMedFetchTool, PubMedParseTool

        searcher = PubMedSearchTool()
        fetcher = PubMedFetchTool()
        parser = PubMedParseTool()

        print(f"[MFS] Searching PubMed for '{herb_eng}' ...")
        search_result = searcher.run(herb_eng)

        # Extract PMIDs from search result text
        pmids = re.findall(r'\b\d{7,9}\b', str(search_result))[:top_k]
        if not pmids:
            print("[MFS] No PMIDs found in PubMed search.")
            return

        for pmid in pmids:
            try:
                raw_paper = fetcher.run(pmid)
                parsed = parser.run(raw_paper if isinstance(raw_paper, str) else str(raw_paper))
                text = str(parsed)
                # Extract title from parsed output
                title_m = re.search(r"title[:\s]+(.+?)(?:\n|$)", text, re.IGNORECASE)
                title = title_m.group(1).strip()[:100] if title_m else f"PMID:{pmid}"

                claims = _llm_extract_claims(text, herb, herb_eng, "pubmed", f"PMID:{pmid}", llm)
                mfs.add_claims(claims, "pubmed", f"PMID:{pmid}", title)
                mfs.sources.append({"type": "pubmed", "id": f"PMID:{pmid}", "title": title})
                print(f"[MFS]   PMID:{pmid} → {len(claims)} claims")
            except Exception as e:
                print(f"[MFS] PubMed fetch error PMID:{pmid}: {e}")

    except ImportError as e:
        print(f"[MFS] PubMed tools not available: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Pinecone source
# ──────────────────────────────────────────────────────────────────────────────

def _fetch_pinecone_claims(
    herb: str,
    herb_eng: str,
    herb_thai: str,
    mfs: MasterFactSheet,
    llm,
    top_k: int = 5,
) -> None:
    """Query Pinecone and extract claims from top-k snippets."""
    if not os.getenv("PINECONE_API_KEY"):
        print("[MFS] PINECONE_API_KEY not set — skipping Pinecone.")
        return

    try:
        from ...tools.pinecone_tools import search_pinecone

        for query in [herb_thai, herb_eng, herb]:
            try:
                result = search_pinecone.run(query)
                if not result or "not found" in str(result).lower():
                    continue
                text = str(result)[:4000]
                claims = _llm_extract_claims(text, herb, herb_eng, "pinecone", f"pinecone:{query}", llm)
                mfs.add_claims(claims, "pinecone", f"pinecone:{query}", f"Pinecone KB ({query})")
                mfs.sources.append({"type": "pinecone", "id": f"pinecone:{query}", "query": query})
                print(f"[MFS]   Pinecone '{query}' → {len(claims)} claims")
                if claims:
                    break  # Stop after first successful query
            except Exception as e:
                print(f"[MFS] Pinecone query error '{query}': {e}")

    except ImportError as e:
        print(f"[MFS] Pinecone tools not available: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def build(
    herbs: str,
    herbs_eng: str,
    herbs_thai: str,
    llm=None,
    pubmed_top_k: int = 3,
    pinecone_top_k: int = 5,
    output_dir: str | Path = "outputs",
    save: bool = True,
) -> MasterFactSheet:
    """
    Build the Master Fact Sheet for a given herb.

    Parameters
    ----------
    herbs          : Scientific name ("Curcuma longa")
    herbs_eng      : English name ("Turmeric")
    herbs_thai     : Thai name ("ขมิ้นชัน")
    llm            : LLM for claim extraction (defaults to judge LLM)
    pubmed_top_k   : Number of PubMed papers to process
    pinecone_top_k : Number of Pinecone snippets to process
    output_dir     : Where to save the MFS JSON
    save           : Save MFS to disk

    Returns
    -------
    MasterFactSheet
    """
    if llm is None:
        llm = create_judge_llm()

    mfs = MasterFactSheet(herbs, herbs_eng, herbs_thai)

    print(f"\n[MFS] Building Master Fact Sheet for {herbs_eng} ({herbs}) ...")

    _fetch_pubmed_claims(herbs, herbs_eng, mfs, llm, top_k=pubmed_top_k)
    _fetch_pinecone_claims(herbs, herbs_eng, herbs_thai, mfs, llm, top_k=pinecone_top_k)

    print(f"[MFS] Complete: {mfs.total_claims if hasattr(mfs, 'total_claims') else len(mfs.claims)} claims from {len(mfs.sources)} sources")

    if save:
        mfs.save(output_dir)

    return mfs


def load(json_path: str | Path) -> MasterFactSheet:
    """Load a previously saved MFS from JSON file."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    mfs = MasterFactSheet(
        data["herb"], data.get("herb_eng", ""), data.get("herb_thai", "")
    )
    mfs.claims = data.get("claims", [])
    mfs.sources = data.get("sources", [])
    mfs._claim_counter = len(mfs.claims)
    mfs.timestamp = data.get("timestamp", mfs.timestamp)
    return mfs
