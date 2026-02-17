"""
agent/tool_registry.py
======================
Registers tools and routes Claude's tool_use calls to the right function.

KEY DIFFERENCE from built-in search approach:
  With Claude's built-in search → API runs the search automatically.
  With Serper (our approach)    → WE run the search and send results back.

So here the registry must:
  1. Tell Claude what tools exist (via schemas)
  2. Actually EXECUTE the search when Claude calls it
  3. Return the result so the agent_loop can send it back to Claude
"""

from tools.web_search  import WebSearch
from tools.web_scraper import WebScraper


class ToolRegistry:
    """
    Central hub for all tools.

    Usage:
        registry = ToolRegistry()
        schemas  = registry.get_schemas()       # → pass to API
        result   = registry.execute("web_search", {"query": "..."})
    """

    def __init__(self):
        self.searcher = WebSearch()
        self.scraper  = WebScraper()
        self._search_count = 0
        self._scrape_count = 0

    # ── Tool schemas (tell Claude what tools exist) ───────────────────────────

    def get_schemas(self) -> list[dict]:
        """
        Returns tool definitions for the Anthropic API.

        IMPORTANT: Because we use Serper (not Claude's built-in search),
        web_search is defined as a CUSTOM tool with a proper JSON schema.
        Claude will call it like a function, and WE run it.
        """
        return [
            {
                "name": "web_search",
                "description": (
                    "Search Google for current information. "
                    "Use this for any question that needs up-to-date facts. "
                    "Returns titles, summaries, and URLs of top results."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query. Be specific for better results.",
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default 5, max 10).",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "web_scraper",
                "description": (
                    "Fetch and read the full text of a specific URL. "
                    "Use this when search snippets aren't detailed enough "
                    "and you need the complete article content."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Full URL to fetch (must start with https://).",
                        }
                    },
                    "required": ["url"],
                },
            },
        ]

    # ── Execute a tool call ───────────────────────────────────────────────────

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """
        Runs the correct tool and returns the result as a string.

        Args:
            tool_name:  Name Claude used ("web_search" or "web_scraper").
            tool_input: Arguments Claude passed (matches the schema above).

        Returns:
            String result — this goes straight back to Claude as context.
        """
        if tool_name == "web_search":
            query       = tool_input.get("query", "")
            num_results = tool_input.get("num_results", 5)
            self._search_count += 1
            print(f"  🌐 Search #{self._search_count}: '{query}'")
            return self.searcher.search_and_format(query, num_results)

        elif tool_name == "web_scraper":
            url = tool_input.get("url", "")
            self._scrape_count += 1
            return self.scraper.scrape(url)

        else:
            return f"Error: Unknown tool '{tool_name}'"

    # ── Session helpers ───────────────────────────────────────────────────────

    def reset(self):
        """Reset counters for a new session."""
        self._search_count = 0
        self._scrape_count = 0

    def summary(self) -> str:
        parts = [f"{self._search_count} search(es)"]
        if self._scrape_count:
            parts.append(f"{self._scrape_count} scrape(s)")
        return ", ".join(parts)
