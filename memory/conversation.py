"""
memory/conversation.py
======================
Manages the message history sent to the Anthropic API each turn.

WHY this is needed:
  The Anthropic API is completely stateless — every call is independent.
  To give Claude "memory", we must manually send the full conversation
  history in every API request.

Message format the API expects:
  [
    {"role": "user",      "content": "What is ...?"},
    {"role": "assistant", "content": [ToolUseBlock(...)]},
    {"role": "user",      "content": [{"type": "tool_result", ...}]},
    {"role": "assistant", "content": [TextBlock("The answer is...")]},
    {"role": "user",      "content": "Follow-up question?"},
  ]

RULES enforced here:
  - Roles must alternate: user → assistant → user → ...
  - Tool results are sent as a "user" message (API requirement)
  - Assistant messages store full content block list (not just text)
"""


class ConversationMemory:
    """
    Stores and exposes the message history for one session.
    """

    def __init__(self):
        self._messages:   list[dict] = []
        self._turn_count: int        = 0

    # ── Add messages ──────────────────────────────────────────────────────────

    def add_user_message(self, text: str):
        """Add a plain-text user message."""
        self._messages.append({"role": "user", "content": text})

    def add_assistant_message(self, content):
        """
        Save Claude's response (the full content block list).

        Args:
            content: response.content from the API (list of blocks).
                     Stored as-is because the API needs the full structure
                     when this appears as a previous "assistant" turn.
        """
        self._messages.append({"role": "assistant", "content": content})
        self._turn_count += 1

    def add_tool_results(self, tool_results: list[dict]):
        """
        Send tool execution results back to Claude as a "user" message.

        This is the OBSERVE step — Claude learns what the tool returned.

        Args:
            tool_results: List of tool_result dicts:
                [{"type": "tool_result", "tool_use_id": "...", "content": "..."}]
        """
        self._messages.append({"role": "user", "content": tool_results})

    # ── Read messages ─────────────────────────────────────────────────────────

    def get_messages(self) -> list[dict]:
        """Returns the full history to pass to the API."""
        return self._messages

    def is_followup(self) -> bool:
        """True if at least one full Q→A turn has completed."""
        return self._turn_count > 0

    # ── Session management ────────────────────────────────────────────────────

    def clear(self):
        """Wipe all history — start fresh."""
        self._messages   = []
        self._turn_count = 0

    def __repr__(self) -> str:
        return f"ConversationMemory(messages={len(self._messages)}, turns={self._turn_count})"
