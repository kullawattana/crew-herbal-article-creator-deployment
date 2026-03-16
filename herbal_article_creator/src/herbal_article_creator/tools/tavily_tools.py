import os
from crewai.tools import BaseTool
from tavily import TavilyClient
from typing import Optional, List
from pydantic import Field
from .utils.link_sanitizer import canonicalize_url, sanitize_markdown_urls

class ToolBudget:
    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self.calls = 0

class MyTavilySearchTool(BaseTool):
    name: str = "tavily_search"
    description: str = (
        "Search the web using Tavily API and return concise results. "
        "Use this to find current information from the internet. "
        "Input should be a search query string."
    )

    max_results: int = Field(default=5, description="Maximum number of results")
    search_depth: str = Field(default="advanced", description="Search depth (basic or advanced)")
    include_domains: List[str] = Field(default_factory=list, description="Domains to include")
    exclude_domains: List[str] = Field(default_factory=list, description="Domains to exclude")

    _calls: int = 0
    _max_calls: int = 999_999
    _shared_budget: Optional[ToolBudget] = None

    def __init__(
        self,
        *,
        shared_budget: Optional[ToolBudget] = None,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)

        api_key = os.getenv("TAVILY_API_KEY")
        self._client = TavilyClient(api_key=api_key)

        self._shared_budget = shared_budget
        self.max_results = max_results
        self.search_depth = search_depth
        self.include_domains = include_domains or []
        self.exclude_domains = exclude_domains or []

        if self.search_depth not in ("basic", "advanced"):
            raise ValueError("search_depth must be 'basic' or 'advanced'")

    def _run(self, query: str = "", **kwargs) -> str:
        # 1) Get query from args/kwargs
        if not query:
            query = kwargs.get("input") or kwargs.get("query") or ""
        if not query:
            return "No query provided."

        # 2) budget guard
        if self._shared_budget:
            if self._shared_budget.calls >= self._shared_budget.max_calls:
                return "TOOL_LIMIT_REACHED: Please proceed to synthesize with current evidence."
            self._shared_budget.calls += 1
        else:
            if self._calls >= self._max_calls:
                return "TOOL_LIMIT_REACHED: Please proceed to synthesize with current evidence."
            self._calls += 1

        # 3) request Tavily
        try:
            resp = self._client.search(
                query=query,
                search_depth=self.search_depth,
                max_results=self.max_results,
                include_domains=self.include_domains or None,
                exclude_domains=self.exclude_domains or None,
            )
        except Exception as e:
            return f"[Tavily Error] {e}"

        results = (resp or {}).get("results") or []
        if not results:
            return "No results."

        # 4) create markdown block for easily to read + canonical URL
        bullets = []
        for item in results:
            title = (item.get("title") or "").strip() or "(no title)"
            url_raw = item.get("url") or ""
            url = canonicalize_url(url_raw) if isinstance(url_raw, str) else ""

            snippet = (
                item.get("content")
                or item.get("snippet")
                or ""
            )
            # Normalize newline and trim length
            snippet = (snippet or "").replace("\\n", " ").replace("\n", " ").strip()
            if len(snippet) > 300:
                snippet = snippet[:300].rstrip() + "..."

            bullets.append(f"- {title} :: {url}\n  {snippet}")

        text = "\n".join(bullets)

        # 5) Sanitize all blog links (prevent stray redirects/utm)
        text = sanitize_markdown_urls(text)

        return text


def create_tavily_tool(
    name: str = "tavily_search",
    description: str = None,
    max_results: int = 5,
    search_depth: str = "advanced",
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    shared_budget: Optional[ToolBudget] = None
) -> MyTavilySearchTool:
    """
    Factory function to create a configured Tavily search tool
    
    Args:
        name: Tool name
        description: Tool description
        max_results: Maximum number of search results
        search_depth: Search depth ('basic' or 'advanced')
        include_domains: List of domains to include in search
        exclude_domains: List of domains to exclude from search
        shared_budget: Shared budget tracker for limiting API calls
    
    Returns:
        Configured TavilySearchTool instance
    """
    tool = MyTavilySearchTool(
        max_results=max_results,
        search_depth=search_depth,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        shared_budget=shared_budget
    )
    
    if name:
        tool.name = name
    if description:
        tool.description = description
    
    return tool