"""
CrewAI Tool for searching for knowledge/cultural information (e.g., SAC)
Provides the same behavior/input as fda_tools: receives a universal 'payload' and sends it to the service.
"""
from typing import Any
from crewai.tools import tool
from .services.sac_search_service import run_sac_search

@tool("search_SAC")
def search_sac_tool(payload: Any = None, **kwargs) -> str:
    """
    Supports all types of input via 'payload'.
    Backward compatible: If the caller directly sends {"query":...}, it will automatically be combined into a payload.
    """
    try:
        if payload is None and kwargs:
            payload = kwargs
        return run_sac_search(payload)
    except Exception as e:
        return f"An error occurred in search_SAC.: {e}"

search_SAC = search_sac_tool