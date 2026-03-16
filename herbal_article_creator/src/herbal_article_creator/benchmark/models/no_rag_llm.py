"""
Baseline Model: No-RAG LLM
- Single agent, zero tools, pure LLM parametric knowledge
- Represents what the model knows without any retrieval augmentation
"""
import time
from crewai import Agent, Crew, Process, Task

from ..llm_factory import create_llm


def generate(herbs: str, herbs_eng: str, herbs_thai: str, lang: str = "en") -> dict:
    """
    Generate a herbal article using only the LLM (no tools, no RAG).

    Returns
    -------
    dict with keys:
        output       : article text (str)
        runtime_sec  : wall-clock seconds (float)
        model_name   : "no_rag_llm"
    """
    start = time.time()
    article_lang = "English" if lang == "en" else "Thai"

    llm = create_llm()

    agent = Agent(
        role="Herbal Medicine Expert Writer",
        goal=(
            "Write accurate, comprehensive herbal medicine articles "
            "based on your internal knowledge."
        ),
        backstory=(
            "You are a pharmacist and herbal medicine expert with deep knowledge "
            "of traditional herbalism and modern pharmacology. You write clear, "
            "well-structured scientific articles."
        ),
        llm=llm,
        tools=[],           # NO TOOLS — pure parametric knowledge
        verbose=False,
        max_iter=3,
    )

    task = Task(
        description=f"""Write a comprehensive scientific article about **{herbs_eng}**
(Thai name: {herbs_thai}, Scientific name: {herbs}).

The article MUST cover ALL of the following sections:
1. **Introduction** — traditional uses and cultural significance
2. **Phytochemistry** — active compounds and chemical constituents
3. **Pharmacological Activities** — mechanisms of action and biological effects
4. **Clinical Evidence** — summarise key human studies or clinical trials
5. **Safety Profile** — contraindications, drug interactions, adverse effects,
   and recommended precautions (advise consulting a healthcare provider)
6. **Modern Wellness Applications** — current uses in supplements/cosmetics/food
7. **Conclusion** — summary of evidence and future directions

Write in **{article_lang}**.
Use precise scientific terminology. Where you cite specific findings,
note them as general knowledge (e.g., "Studies have shown…").
Do NOT fabricate specific DOIs, PMIDs, or journal names.""",
        expected_output=(
            f"A comprehensive {article_lang} scientific article "
            f"about {herbs_eng} with all 7 sections clearly headed."
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
        "model_name": "no_rag_llm",
    }
