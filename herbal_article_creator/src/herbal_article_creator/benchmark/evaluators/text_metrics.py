"""
Text-overlap metrics: BLEU and ROUGE.

Both metrics compare a *hypothesis* (generated text) against a *reference*
(gold-standard text).  In this benchmark the Multi-Agent output is used as
the default reference; you can also supply an external reference file.

Dependencies (already in the project's uv environment):
  - sacrebleu  (corpus BLEU)
  - rouge-score (ROUGE-1, ROUGE-2, ROUGE-L)
"""
from __future__ import annotations

import re
from typing import NamedTuple

# sacrebleu ≥ 2.0 API
import sacrebleu
from rouge_score import rouge_scorer


class TextMetrics(NamedTuple):
    bleu: float           # 0-100 (sacrebleu corpus BLEU score)
    rouge1: float         # F1, 0-1
    rouge2: float         # F1, 0-1
    rougeL: float         # F1, 0-1


def _clean(text: str) -> str:
    """Minimal normalisation: collapse whitespace."""
    return re.sub(r"\s+", " ", text).strip()


def compute(hypothesis: str, reference: str) -> TextMetrics:
    """
    Compute BLEU and ROUGE scores.

    Parameters
    ----------
    hypothesis : generated text to evaluate
    reference  : gold-standard reference text

    Returns
    -------
    TextMetrics namedtuple
    """
    hyp = _clean(hypothesis)
    ref = _clean(reference)

    if not hyp or not ref:
        return TextMetrics(bleu=0.0, rouge1=0.0, rouge2=0.0, rougeL=0.0)

    # --- BLEU ---
    # sacrebleu corpus_bleu expects list[str] hypothesis and list[list[str]] references
    bleu_result = sacrebleu.corpus_bleu([hyp], [[ref]])
    bleu_score = round(bleu_result.score, 4)        # 0–100 scale

    # --- ROUGE ---
    scorer = rouge_scorer.RougeScorer(
        ["rouge1", "rouge2", "rougeL"], use_stemmer=True
    )
    scores = scorer.score(ref, hyp)

    return TextMetrics(
        bleu=bleu_score,
        rouge1=round(scores["rouge1"].fmeasure, 4),
        rouge2=round(scores["rouge2"].fmeasure, 4),
        rougeL=round(scores["rougeL"].fmeasure, 4),
    )


def compute_all(
    model_outputs: dict[str, str],
    reference: str,
) -> dict[str, TextMetrics]:
    """
    Compute text metrics for multiple model outputs against one reference.

    Parameters
    ----------
    model_outputs : {model_name: article_text}
    reference     : gold-standard reference text

    Returns
    -------
    {model_name: TextMetrics}
    """
    return {
        name: compute(text, reference)
        for name, text in model_outputs.items()
    }
