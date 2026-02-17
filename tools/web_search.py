"""
tools/web_search.py
===================
Web search using Serper.dev API (Google Search wrapper).

WHY Serper instead of Claude's built-in search?
  - You control the API → swap providers anytime
  - Returns structured JSON → you decide what the agent sees
  - Free tier: 2500 searches/month (enough to build & test)
  - Claude's built-in search is a black box; this is transparent

Get your free key at: https://serper.dev
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()


class WebSearch:

    def __init__(self):
        self.api_key     = os.getenv("SERPER_API_KEY")
        self.base_url    = "https://google.serper.dev/search"
        self.num_results = 5
        self.query       = ""

        if not self.api_key:
            print("⚠️  WARNING: SERPER_API_KEY not found in .env file!")

    # ── Raw API call ──────────────────────────────────────────────────────────

    def web_search(self, query: str, num_results: int = 5) -> dict:
        """
        Makes the raw API call to Serper.
        Returns raw JSON — no formatting yet.

        INTERNAL: Use search_and_format() instead unless you need raw data.
        """
        self.query       = query
        self.num_results = num_results

        response = requests.post(
            self.base_url,
            headers={
                "X-API-KEY":    self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "q":   query,
                "num": num_results,
            },
        )
        response.raise_for_status()
        return response.json()

    # ── Formatted output (what the agent reads) ───────────────────────────────

    def search_and_format(self, query: str, num_results: int = 5) -> str:
        """
        Searches the web and returns a clean, formatted string.

        INTERNAL: This is what Claude reads as the tool result.
        Format must be clear so Claude understands the structure.

        Returns:
            Formatted string with direct answer (if any) + top results.
        """
        data = self.web_search(query, num_results)
        formatted_results = []

        # ── Direct answer box (e.g. "Who is the CEO of Apple?") ──────────────
        if "answerBox" in data:
            answer = data["answerBox"].get("answer", "")
            if answer:
                formatted_results.append(f"DIRECT ANSWER: {answer}")

        # ── Organic search results ────────────────────────────────────────────
        if "organic" in data:
            for i, result in enumerate(data["organic"][:num_results]):
                title   = result.get("title",   "")
                link    = result.get("link",    "")
                snippet = result.get("snippet", "")

                if title and link:
                    formatted_results.append(
                        f"Result {i+1}:\n"
                        f"  Title:   {title}\n"
                        f"  Summary: {snippet}\n"
                        f"  URL:     {link}\n"
                    )

        final_output = "\n".join(formatted_results)
        return final_output if final_output else "No results found."
