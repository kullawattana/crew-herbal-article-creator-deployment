"""
Ablation Configurations
========================
Each configuration enables/disables specific components to measure
the isolated contribution of each tool.

Naming convention:
  baseline          — No tools (pure LLM parametric knowledge)
  +pubmed           — Add PubMed search/fetch/parse
  +pinecone         — Add Pinecone knowledge base
  +pubmed+pinecone  — Both retrieval sources (= Single-Agent RAG)
  +multi_agent      — Full CrewAI multi-agent pipeline (all tools)

Delta analysis:
  Δ(+pubmed vs baseline)       = value of PubMed retrieval
  Δ(+pinecone vs baseline)     = value of Pinecone knowledge base
  Δ(+pubmed+pinecone vs +pubmed) = marginal value of adding Pinecone
  Δ(+multi_agent vs +pubmed+pinecone) = value of multi-agent orchestration
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AblationConfig:
    name: str               # short key
    label: str              # human-readable label
    description: str        # what this config tests
    use_pubmed: bool = False
    use_pinecone: bool = False
    use_multi_agent: bool = False   # triggers full HerbalArticleCreator crew
    max_iter: int = 10             # agent max iterations


# ── Configuration registry ────────────────────────────────────────────────────

CONFIGS: list[AblationConfig] = [
    AblationConfig(
        name="baseline",
        label="Baseline (No RAG)",
        description="Pure LLM knowledge — no retrieval tools",
        use_pubmed=False,
        use_pinecone=False,
        use_multi_agent=False,
    ),
    AblationConfig(
        name="+pubmed",
        label="+ PubMed",
        description="LLM + PubMed search/fetch — scientific literature only",
        use_pubmed=True,
        use_pinecone=False,
        use_multi_agent=False,
    ),
    AblationConfig(
        name="+pinecone",
        label="+ Pinecone",
        description="LLM + Pinecone KB — internal herbal documents only",
        use_pubmed=False,
        use_pinecone=True,
        use_multi_agent=False,
    ),
    AblationConfig(
        name="+pubmed+pinecone",
        label="+ PubMed + Pinecone",
        description="LLM + both retrievers (= Single-Agent RAG)",
        use_pubmed=True,
        use_pinecone=True,
        use_multi_agent=False,
    ),
    AblationConfig(
        name="+multi_agent",
        label="Full Multi-Agent",
        description="Full CrewAI pipeline — all agents and tools",
        use_pubmed=True,
        use_pinecone=True,
        use_multi_agent=True,
    ),
]

CONFIG_MAP: dict[str, AblationConfig] = {c.name: c for c in CONFIGS}
