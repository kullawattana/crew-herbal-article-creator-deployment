import json
from typing import Any, Iterable, List, Dict
from ..tavily_tools import MyTavilySearchTool
from ..utils.link_sanitizer import sanitize_markdown_urls, strip_rag_file_links

def normalize_fda_input(raw_input: Any) -> List[str]:
    """
    input supported to list[str]:
      - {"query": "ฟ้าทะลายโจร"}
      - {"queries": ["ขมิ้นชัน","ฟ้าทะลายโจร"]}
      - "{\"queries\": [\"ขมิ้นชัน\"]}"
      - {"args": "{\"query\": \"ฟ้าทะลายโจร\"}"}
      - "ฟ้าทะลายโจร"
    """
    data = raw_input
    if data is None:
        return []

    # transfer string -> JSON
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return [data.strip()]

    # finding {"args": ...}
    if isinstance(data, dict) and "args" in data:
        args_val = data["args"]
        if isinstance(args_val, str):
            try:
                args_val = json.loads(args_val)
            except Exception:
                args_val = {"query": args_val}
        if isinstance(args_val, dict):
            data.update(args_val)

    terms = []
    if isinstance(data, dict):
        # single query -> [query] command call from LLM
        if "query" in data and isinstance(data["query"], str):
            terms.append(data["query"].strip())
        # multiple queries -> [queries] command call from LLM
        if "queries" in data:
            qv = data["queries"]
            if isinstance(qv, str):
                terms.extend([x.strip() for x in qv.split(",") if x.strip()])
            elif isinstance(qv, Iterable):
                terms.extend([str(x).strip() for x in qv if str(x).strip()])
    elif isinstance(data, str):
        terms.append(data.strip())

    # filtering
    seen, out = set(), []
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def search_fda_terms(terms: List[str], max_results: int = 5) -> Dict[str, str]:
    """
    Finding FDA
    response dict: {term: result_text}
    """
    include_domains = ["www.fda.moph.go.th", "www.oryor.com"]
    tavily = MyTavilySearchTool(include_domains=include_domains, max_results=max_results)

    results = {}
    for t in terms:
        try:
            res = tavily._run(query=t)
            if not res or "error" in str(res).lower():
                results[t] = f"Not found FDA/ORYOR for '{t}'"
            else:
                clean_text = strip_rag_file_links(sanitize_markdown_urls(str(res)))
                results[t] = clean_text
        except Exception as e:
            results[t] = f"An error occurred while searching FDA/ORYOR : {t}: {e}"

    return results


def run_fda_search(raw_input: Any) -> str:
    """
    normalize input + search + result
    response: Markdown for CrewAI
    """
    terms = normalize_fda_input(raw_input)
    if not terms:
        return "Not found from FDA/ORYOR search (Prompt from LLM Must be 'query' or 'queries')"

    results = search_fda_terms(terms)
    output_blocks = [f"### {t}\n{txt}" for t, txt in results.items()]
    return "\n\n".join(output_blocks)