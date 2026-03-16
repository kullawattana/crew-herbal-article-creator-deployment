"""
Multi-Agent Model — wraps the existing HerbalArticleCreator crew.
Also supports loading a pre-existing output file to avoid re-running
the expensive full crew when results are already available.
"""
import time
from pathlib import Path

from ...crew import HerbalArticleCreator


def generate(
    herbs: str,
    herbs_eng: str,
    herbs_thai: str,
    lang: str = "en",
    precomputed_output_file: str | None = None,
) -> dict:
    """
    Run (or load) the full multi-agent HerbalArticleCreator pipeline.

    Parameters
    ----------
    herbs                  : Scientific name (e.g. "Curcuma longa")
    herbs_eng              : English common name (e.g. "Turmeric")
    herbs_thai             : Thai name (e.g. "ขมิ้นชัน")
    lang                   : Output language code ("en" | "th")
    precomputed_output_file: Path to a task_XX_*.txt file to load instead
                             of running the crew again.

    Returns
    -------
    dict with keys:
        output       : article text (str)
        runtime_sec  : wall-clock seconds (float)
        model_name   : "multi_agent"
        loaded_from  : file path if loaded from file, else None
    """
    # --- Load from existing output file ---
    if precomputed_output_file:
        p = Path(precomputed_output_file)
        if p.exists():
            text = p.read_text(encoding="utf-8")
            print(f"[MultiAgent] Loaded existing output from: {p}")
            return {
                "output": text,
                "runtime_sec": 0.0,
                "model_name": "multi_agent",
                "loaded_from": str(p),
            }
        else:
            print(f"[MultiAgent] Warning: file not found: {p}. Running crew instead.")

    # --- Run full crew ---
    start = time.time()
    crew_instance = HerbalArticleCreator(params={"herbs": herbs})
    inputs = {
        "herbs": herbs,
        "herbs_eng": herbs_eng,
        "herbs_thai": herbs_thai,
        "lang": lang,
    }
    result = crew_instance.crew().kickoff(inputs=inputs)

    return {
        "output": str(result),
        "runtime_sec": round(time.time() - start, 2),
        "model_name": "multi_agent",
        "loaded_from": None,
    }
