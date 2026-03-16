# services/sac_search_service.py
"""
Thai wisdom/ritual information search service (such as SAC)
support input (str / dict / JSON-string / args)
"""
from typing import Any, List, Tuple, Iterable, Dict
import json, os
from ..tavily_tools import MyTavilySearchTool
from ..utils.link_sanitizer import sanitize_markdown_urls, strip_rag_file_links

def normalize_sac_input(raw_input: Any) -> Tuple[List[str], int]:
    limit = int(os.getenv("SAC_MAX_RESULTS", "6"))
    data = raw_input

    # JSON string → JSON object, or one word (string type)
    if isinstance(data, str):
        s = data.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try: data = json.loads(s)
            except Exception: return ([s], limit)
        else:
            return ([s], limit)

    # finding {"args": ...}
    if isinstance(data, dict) and "args" in data:
        args_val = data["args"]
        if isinstance(args_val, str):
            try: args_val = json.loads(args_val)
            except Exception: args_val = {"query": args_val}
        if isinstance(args_val, dict): data.update(args_val)

    terms: List[str] = []
    if isinstance(data, dict):
        if isinstance(data.get("limit"), int): limit = data["limit"]
        if isinstance(data.get("query"), str): terms.append(data["query"].strip())
        if "queries" in data:
            qv = data["queries"]
            if isinstance(qv, str):
                terms.extend([x.strip() for x in qv.split(",") if x.strip()])
            elif isinstance(qv, Iterable):
                terms.extend([str(x).strip() for x in qv if str(x).strip()])
    elif isinstance(data, (list, tuple)):
        terms.extend([str(x).strip() for x in data if str(x).strip()])

    return (terms, limit)

def search_sac_terms(terms: List[str], limit: int) -> Dict[str, str]:
    include_env = os.getenv("SAC_INCLUDE_DOMAINS", "")
    include_domains = [d.strip() for d in include_env.split(",") if d.strip()] or [
        "www.sac.or.th", "db.sac.or.th"
    ]
    tavily = MyTavilySearchTool(include_domains=include_domains, max_results=limit)
    out: Dict[str, str] = {}
    for t in terms:
        try:
            res = tavily._run(query=t)
            if not res or "error" in str(res).lower():
                out[t] = f"No data found from SAC for'{t}'"
            else:
                clean = strip_rag_file_links(sanitize_markdown_urls(str(res)))
                out[t] = clean
        except Exception as e:
            out[t] = f"An error occurred while searching SAC : {t}: {e}"
    return out

def run_sac_search(raw_input: Any) -> str:
    terms, limit = normalize_sac_input(raw_input)
    if not terms:
        return "Not found from SAC search (Prompt from LLM Must be 'query' or 'queries')"
    results = search_sac_terms(terms, limit)
    return "\n\n".join([f"### {t}\n{txt}" for t, txt in results.items()])