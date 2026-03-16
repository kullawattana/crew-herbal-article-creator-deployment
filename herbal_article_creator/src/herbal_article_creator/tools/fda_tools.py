"""
CrewAI Tool for searching FDA/ORYOR information with fda_search_service.py (universal input)
"""

from typing import Any
from crewai.tools import tool
from .services.fda_search_service import run_fda_search
import os, json, re, time, threading

MAX_FDA_CALLS = int(os.getenv("MAX_FDA_CALLS", "5"))

_STATE_LOCK = threading.Lock()
_STATE = {"count": 0, "seen": set(), "reset_at": time.time() + 3600}

def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _extract_query_and_payload(payload: Any):
    """คืน (query_str, normalized_payload_for_service)"""
    q = ""
    p = payload
    if isinstance(payload, str):
        # try to parse string to JSON before
        try:
            p = json.loads(payload)
        except json.JSONDecodeError:
            q = payload.strip()
    if isinstance(p, dict):
        q = p.get("payload", {}).get("query", "") or p.get("query", "") or q
    if not q and p and not isinstance(p, (str, dict)):
        q = str(p)
    return q, p

@tool("search_fda")
def search_fda_tool(payload: Any = None) -> Any: 
    """CrewAI Tool for searching information from FDA (FDA Thailand) and ORYOR"""
    q, p = _extract_query_and_payload(payload)
    qn = _norm(q)

    with _STATE_LOCK:
        if time.time() > _STATE["reset_at"]:
            _STATE.update({"count": 0, "seen": set(), "reset_at": time.time() + 3600})
        if qn and qn in _STATE["seen"]:
            return []                               # Repeat -> Empty (same type)
        if _STATE["count"] >= MAX_FDA_CALLS:
            return []                               # Over the limit -> Empty
        _STATE["count"] += 1
        if qn: _STATE["seen"].add(qn)
        call_no = _STATE["count"]

    print(f"FDA search call #{call_no}/{MAX_FDA_CALLS}: {q}")

    try:
        result = run_fda_search(p if p is not None else payload)
        return result if result is not None else [] # Return the original list/dict
    except Exception as e:
        return {"error": f"FDA search error: {e}"}  # Report error as dict