"""
Single-Agent RAG Model
- One agent equipped with PubMed + Pinecone tools
- Represents a simpler RAG pipeline vs the full multi-agent crew
"""
import os
import time
from crewai import Agent, Crew, Process, Task

from ..llm_factory import create_llm
from ...tools.pubmed_tools import PubMedSearchTool, PubMedFetchTool, PubMedParseTool
from ...tools.pinecone_tools import search_pinecone


def _build_tools() -> list:
    """Assemble RAG tools, skip Pinecone gracefully if key missing."""
    tools = [
        PubMedSearchTool(),
        PubMedFetchTool(),
        PubMedParseTool(),
    ]
    if os.getenv("PINECONE_API_KEY"):
        tools.append(search_pinecone)
    else:
        print("[SingleAgentRAG] PINECONE_API_KEY not set — Pinecone tool skipped.")
    return tools


def generate(herbs: str, herbs_eng: str, herbs_thai: str, lang: str = "en") -> dict:
    """
    Generate a herbal article using a single agent with RAG tools.

    Returns
    -------
    dict with keys:
        output       : article text (str)
        runtime_sec  : wall-clock seconds (float)
        model_name   : "single_agent_rag"
    """
    start = time.time()
    article_lang = "English" if lang == "en" else "Thai"

    llm = create_llm()
    tools = _build_tools()

    pinecone_hint = (
        f'Search the internal knowledge base for "{herbs_thai}" and "{herbs}" '
        "using search_pinecone.\n"
        if os.getenv("PINECONE_API_KEY")
        else ""
    )

    agent = Agent(
        role="Herbal Research Writer",
        goal=(
            "Write comprehensive, evidence-based herbal articles "
            "by retrieving information from scientific databases and internal knowledge."
        ),
        backstory=(
            "You are a pharmacist-researcher specialising in systematic reviews. "
            "You retrieve real scientific evidence before writing and cite your sources."
        ),
        llm=llm,
        tools=tools,
        verbose=False,
        max_iter=15,
    )

    task = Task(
        description=f"""Write a comprehensive scientific article about **{herbs_eng}**
(Thai name: {herbs_thai}, Scientific name: {herbs}).

## Retrieval Steps (complete BEFORE writing)
1. Search PubMed: use `search_pubmed` with query "{herbs}" to find recent studies.
2. Fetch top 2-3 papers: use `fetch_pubmed` then `parse_pubmed` to extract abstracts,
   key findings, and APA citations.
{pinecone_hint}
## Article Sections (write AFTER retrieval)
1. **Introduction** — traditional uses and cultural significance
2. **Phytochemistry** — active compounds (cite sources)
3. **Pharmacological Activities** — mechanisms of action (cite studies)
4. **Clinical Evidence** — human studies / clinical trials with APA citations
5. **Safety Profile** — contraindications, interactions, adverse effects,
   recommend consulting a healthcare professional
6. **Modern Wellness Applications** — supplement / cosmetic / food uses
7. **Conclusion** — summary and future directions

Write in **{article_lang}**.
Include in-text citations for all specific scientific claims.
Do NOT fabricate PMIDs, DOIs, or journal names — only use what you retrieved.""",
        expected_output=(
            f"A comprehensive {article_lang} evidence-based article about {herbs_eng} "
            "with 7 clearly headed sections and PubMed citations."
        ),
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff(inputs={
        "herbs": herbs,
        "herbs_eng": herbs_eng,
        "herbs_thai": herbs_thai,
    })

    return {
        "output": str(result),
        "runtime_sec": round(time.time() - start, 2),
        "model_name": "single_agent_rag",
    }
