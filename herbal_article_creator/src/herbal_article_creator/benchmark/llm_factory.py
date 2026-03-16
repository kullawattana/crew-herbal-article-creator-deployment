"""
Shared LLM factory — mirrors the logic in crew.py _create_llm()
so benchmark models use the same model configured via .env.
"""
import os
from crewai import LLM


def create_llm(temperature: float | None = None) -> LLM:
    """Create LLM using the same env-based config as the main crew."""
    temp = temperature if temperature is not None else float(os.getenv("LLM_TEMPERATURE", "0.5"))
    model_name = os.getenv("LLM_MODEL_NAME", "gemini")

    if model_name == "gpt":
        return LLM(
            model=os.getenv("LLM_GPT_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=temp,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )
    elif model_name == "anthropic":
        return LLM(
            model=os.getenv("LLM_CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            temperature=temp,
            max_completion_tokens=int(os.getenv("LLM_MAX_COMPLETION_TOKENS", "8000")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )
    elif model_name == "gemini":
        return LLM(
            model=os.getenv("LLM_GEMINI_MODEL", "gemini/gemini-2.0-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=temp,
        )
    else:  # llama / nvidia
        return LLM(
            model=os.getenv("LLM_MODEL", "meta/llama-3.1-8b-instruct"),
            base_url=os.getenv("LLM_API_BASE", "https://integrate.api.nvidia.com/v1"),
            api_key=os.getenv("LLM_API_KEY"),
            custom_llm_provider=os.getenv("LLM_PROVIDER"),
            temperature=temp,
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
        )


def create_judge_llm() -> LLM:
    """
    LLM for evaluation/judging — always uses Gemini Flash for speed & cost,
    falls back to the configured LLM if GEMINI_API_KEY is absent.
    """
    if os.getenv("GEMINI_API_KEY"):
        return LLM(
            model=os.getenv("LLM_GEMINI_MODEL", "gemini/gemini-2.0-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.1,  # low temp for consistent judging
        )
    # fallback to main LLM at low temperature
    return create_llm(temperature=0.1)
