"""
tools/web_scraper.py
====================
Fetches and cleans the full text of a web page.

WHY this exists alongside web_search:
  - Serper returns snippets (150-200 chars) — often not enough
  - This tool lets Claude read the FULL article when needed
  - Pattern: search → find best URL → scrape → get full content

WHAT it does step by step:
  1. Makes an HTTP GET request to the URL
  2. Parses HTML with BeautifulSoup
  3. Strips noise (scripts, nav, ads, footer)
  4. Extracts clean readable text
  5. Truncates to 3000 chars so Claude's context isn't overwhelmed

Install: pip install requests beautifulsoup4
"""

import re
import requests
from bs4 import BeautifulSoup


# Tags that never contain useful article content
NOISE_TAGS = [
    "script",       # JavaScript
    "style",        # CSS
    "nav",          # Navigation menus
    "footer",       # Page footer
    "header",       # Page header
    "aside",        # Sidebars
    "form",         # Login/search forms
    "iframe",       # Embedded content
    "noscript",     # Fallback JS messages
    "advertisement",# Ads
]

# Realistic browser header so sites don't block us
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection":      "keep-alive",
}

MAX_CHARS    = 3000   # Max characters returned to Claude
TIMEOUT_SECS = 10     # How long to wait for a page to load


class WebScraper:
    """
    Fetches a URL and returns clean, readable plain text.

    The agent calls this when search snippets aren't detailed enough
    and it needs the full article content.

    Usage:
        scraper = WebScraper()
        text    = scraper.scrape("https://example.com/article")
    """

    def scrape(self, url: str) -> str:
        """
        Main method. Fetches and cleans a web page.

        Args:
            url: Full URL including https://

        Returns:
            Clean plain text (max 3000 chars), or an error message string.
            Always returns a string — errors are returned as readable messages
            so Claude can tell the user what went wrong.
        """
        print(f"  📄 Scraping: {url}")

        # ── Step 1: Validate URL ──────────────────────────────────────────────
        if not url.startswith(("http://", "https://")):
            return f"Error: Invalid URL '{url}'. Must start with http:// or https://"

        # ── Step 2: Fetch the page ────────────────────────────────────────────
        try:
            response = requests.get(
                url,
                headers = REQUEST_HEADERS,
                timeout = TIMEOUT_SECS,
            )
            response.raise_for_status()  # Raises exception for 4xx/5xx errors

        except requests.exceptions.Timeout:
            return f"Error: Page took too long to load (>{TIMEOUT_SECS}s). Try a different URL."

        except requests.exceptions.ConnectionError:
            return f"Error: Could not connect to '{url}'. Check the URL or your internet connection."

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status == 403:
                return f"Error: Access denied (403). '{url}' blocks automated requests."
            elif status == 404:
                return f"Error: Page not found (404). '{url}' does not exist."
            else:
                return f"Error: HTTP {status} from '{url}'."

        except requests.exceptions.RequestException as e:
            return f"Error fetching '{url}': {str(e)}"

        # ── Step 3: Check content type ────────────────────────────────────────
        # Only process HTML pages — skip PDFs, images, etc.
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return (
                f"Error: Cannot scrape this file type (Content-Type: {content_type}). "
                f"web_scraper only works on HTML pages."
            )

        # ── Step 4: Parse HTML ────────────────────────────────────────────────
        soup = BeautifulSoup(response.text, "html.parser")

        # ── Step 5: Remove noise ──────────────────────────────────────────────
        for tag in soup(NOISE_TAGS):
            tag.decompose()   # Remove tag + all its children from the tree

        # Also remove elements that are visually hidden (often nav/ad clutter)
        for tag in soup.find_all(style=re.compile(r"display:\s*none|visibility:\s*hidden")):
            tag.decompose()

        # ── Step 6: Try to find the main content block ────────────────────────
        # Many sites wrap article text in semantic tags — use them if available
        main_content = (
            soup.find("article")    or   # <article> tag (most news sites)
            soup.find("main")       or   # <main> tag
            soup.find(id="content") or   # Common id
            soup.find(class_=re.compile(r"article|content|post|story", re.I)) or
            soup.find("body")            # Fallback to full body
        )

        if not main_content:
            return "Error: Could not find readable content on this page."

        # ── Step 7: Extract text ──────────────────────────────────────────────
        text = main_content.get_text(separator="\n")

        # ── Step 8: Clean whitespace ──────────────────────────────────────────
        text = self._clean_text(text)

        if not text:
            return "Error: Page was found but contained no readable text."

        # ── Step 9: Add metadata header ───────────────────────────────────────
        # Give Claude context about where this text came from
        title = soup.find("title")
        title_text = title.get_text().strip() if title else "Unknown"

        header = (
            f"SOURCE: {url}\n"
            f"TITLE:  {title_text}\n"
            f"{'─' * 40}\n"
        )

        # ── Step 10: Truncate if too long ─────────────────────────────────────
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + f"\n\n[... truncated at {MAX_CHARS} chars ...]"

        return header + text

    # ── Private helpers ───────────────────────────────────────────────────────

    def _clean_text(self, text: str) -> str:
        """
        Removes excessive whitespace from extracted text.

        Raw get_text() output has tons of blank lines and spaces
        from HTML structure — this makes it readable.
        """
        # Remove lines that are just whitespace
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]

        # Collapse runs of 3+ blank lines into 2
        cleaned_lines = []
        blank_count   = 0

        for line in lines:
            if line == "":
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append(line)
            else:
                blank_count = 0
                cleaned_lines.append(line)

        text = "\n".join(cleaned_lines)

        # Collapse multiple spaces into one
        text = re.sub(r" {2,}", " ", text)

        return text.strip()
