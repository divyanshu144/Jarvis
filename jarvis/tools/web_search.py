"""
Web search tool.
Primary:  Tavily API (if key configured)
Fallback: BBC News RSS for news queries, DuckDuckGo HTML for everything else.
         Falls through transparently — the model always gets real content.
"""

from __future__ import annotations

import urllib.parse

from jarvis.core.config import cfg
from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "web_search",
    "description": (
        "Search the web and return relevant results. "
        "Also use this to get live news, headlines, or current events. "
        "Works without any API key — always returns real content."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query or topic to look up."},
            "max_results": {"type": "integer", "description": "Number of results (default 5)."},
        },
        "required": ["query"],
    },
}

_NEWS_KEYWORDS = {
    "news", "headline", "headlines", "world", "today", "happening",
    "latest", "current", "events", "breaking", "report",
}


def _is_news_query(query: str) -> bool:
    words = set(query.lower().split())
    return bool(words & _NEWS_KEYWORDS)


def _browser_fallback(query: str) -> str:
    """Fetch real content using browser_control when Tavily is unavailable."""
    from jarvis.tools.browser import execute as browser_execute

    if _is_news_query(query):
        log.info("web_search: no Tavily key — fetching BBC News RSS")
        result = browser_execute("read", "https://feeds.bbci.co.uk/news/rss.xml")
        return f"[BBC News — live feed]\n{result}"

    # General query — DuckDuckGo HTML (no API key needed)
    url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote_plus(query)
    log.info(f"web_search: no Tavily key — fetching DuckDuckGo: {url}")
    return browser_execute("read", url)


def execute(query: str, max_results: int = 5) -> str:
    if not cfg.tavily_key:
        return _browser_fallback(query)
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=cfg.tavily_key)
        resp = client.search(query, max_results=max_results)
        results = resp.get("results", [])
        if not results:
            return _browser_fallback(query)
        lines = []
        for r in results:
            lines.append(f"**{r.get('title', 'No title')}**")
            lines.append(r.get("url", ""))
            lines.append(r.get("content", "")[:300])
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        log.error(f"web_search Tavily failed: {e} — falling back to browser")
        return _browser_fallback(query)
