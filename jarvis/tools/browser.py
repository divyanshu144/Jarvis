"""
Browser / web fetch tool.
Primary:  Playwright (full JS-rendered browser — needs `playwright install chromium`)
Fallback: urllib (built-in, handles plain HTML, RSS, and most news sites)
"""

from __future__ import annotations

import asyncio
import html
import re
import urllib.request
from urllib.error import URLError

from jarvis.core.logger import get_logger

log = get_logger(__name__)

DEFINITION = {
    "name": "browser_control",
    "description": (
        "Fetch and read content from any URL, or control a browser. "
        "Use action='read' with a url to get the text content of a web page or RSS feed. "
        "Works without any extra setup — use it whenever you need to fetch web content, "
        "news, articles, or any live information from the internet."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "read", "click", "screenshot"],
                "description": (
                    "read=fetch and return page text (most common), "
                    "open=navigate browser to URL, "
                    "click=click element by selector, "
                    "screenshot=capture page screenshot"
                ),
            },
            "url": {"type": "string", "description": "URL to fetch or navigate to."},
            "selector": {"type": "string", "description": "CSS selector or text to click."},
        },
        "required": ["action"],
    },
}


# ── Simple urllib fetcher (no dependencies) ───────────────────────────────────

def _strip_html(raw: str) -> str:
    """Strip HTML tags and decode entities, return plain text."""
    # Remove script/style blocks entirely
    raw = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    raw = re.sub(r"<[^>]+>", " ", raw)
    # Decode HTML entities
    raw = html.unescape(raw)
    # Collapse whitespace
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def _parse_rss(raw: str) -> str:
    """Extract titles and descriptions from RSS/Atom XML."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []

        # RSS 2.0
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title", "").strip()
            desc = _strip_html(item.findtext("description", "").strip())[:200]
            if title:
                items.append(f"• {title}" + (f": {desc}" if desc else ""))

        # Atom
        if not items:
            for entry in root.findall(".//atom:entry", ns)[:10]:
                title = entry.findtext("atom:title", "", ns).strip()
                summary = _strip_html(entry.findtext("atom:summary", "", ns).strip())[:200]
                if title:
                    items.append(f"• {title}" + (f": {summary}" if summary else ""))

        return "\n".join(items) if items else _strip_html(raw)[:3000]
    except ET.ParseError:
        return _strip_html(raw)[:3000]


def _urllib_read(url: str, max_chars: int = 4000) -> str:
    """Fetch a URL and return clean text. Handles HTML and RSS/XML."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) JARVIS/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="replace")

        # RSS/Atom feed
        if "xml" in content_type or "rss" in content_type or raw.lstrip().startswith("<rss") or "<feed" in raw[:200]:
            return _parse_rss(raw)

        # HTML page
        text = _strip_html(raw)
        return text[:max_chars] + ("…" if len(text) > max_chars else "")

    except URLError as e:
        return f"Error fetching {url}: {e}"
    except Exception as e:
        log.warning(f"urllib fetch failed for {url}: {e}")
        return f"Error: {e}"


# ── Playwright path (optional, richer JS support) ────────────────────────────

_browser = None
_page = None


async def _get_page():
    global _browser, _page
    from playwright.async_api import async_playwright
    if _browser is None:
        pw = await async_playwright().start()
        _browser = await pw.chromium.launch(headless=True)
        _page = await _browser.new_page()
    return _page


async def _playwright_execute(action: str, url: str = "", selector: str = "") -> str:
    page = await _get_page()

    if action == "open":
        if not url:
            return "Error: url required."
        await page.goto(url, timeout=15000)
        return f"Navigated to {url} — title: {await page.title()}"

    if action == "read":
        if url:
            await page.goto(url, timeout=15000)
        text = await page.evaluate("() => document.body.innerText")
        return text[:4000] + ("…" if len(text) > 4000 else "")

    if action == "click":
        if not selector:
            return "Error: selector required."
        await page.click(selector, timeout=5000)
        return f"Clicked '{selector}'."

    if action == "screenshot":
        path = "/tmp/jarvis_browser_shot.png"
        await page.screenshot(path=path)
        return f"Screenshot saved to {path}"

    return f"Unknown action: {action}"


# ── Public execute ────────────────────────────────────────────────────────────

def execute(action: str, url: str = "", selector: str = "") -> str:
    # read action: try urllib first (fast, no deps); playwright only for JS-heavy sites
    if action == "read" and url:
        result = _urllib_read(url)
        if not result.startswith("Error"):
            log.info(f"browser_control: fetched {url} via urllib ({len(result)} chars)")
            return result
        log.warning(f"urllib failed, trying playwright: {result}")

    # For open/click/screenshot or urllib failure — try playwright
    try:
        return asyncio.run(_playwright_execute(action, url, selector))
    except ImportError:
        # Playwright not installed — fall back to urllib for read
        if action == "read" and url:
            return _urllib_read(url)
        return (
            "Browser automation unavailable (playwright not installed). "
            "For reading web pages, use action='read' with a URL — that works without playwright."
        )
    except Exception as e:
        log.error(f"browser_control failed: {e}")
        return f"Error: {e}"
