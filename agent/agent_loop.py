"""
agent/agent_loop.py
===================
The ReAct (Reason + Act) loop — the brain of the agent.

ReAct pattern, step by step:
  1. REASON  → Send question to Claude. It decides what to do.
  2. ACT     → Claude calls a tool (web_search or web_scraper).
  3. OBSERVE → WE run the tool, get the result, send it back to Claude.
  4. REPEAT  → Claude reasons again with new information.
  5. RESPOND → Claude says stop_reason="end_turn" → return the answer.

KEY DIFFERENCE vs Claude's built-in search:
  Built-in: Claude calls search → API runs it → result auto-injected.
  Serper:   Claude calls search → WE run it   → WE inject the result.

This means our tool_results must be carefully formatted and sent
back as a "user" message — that's the standard tool-use pattern.
"""

import anthropic
from agent.prompts      import RESEARCHER_PROMPT, FOLLOWUP_PROMPT, FALLBACK_MESSAGE
from agent.tool_registry import ToolRegistry
from memory.conversation import ConversationMemory

MODEL          = "claude-opus-4-5-20251101"
MAX_ITERATIONS = 10   # Safety cap — prevents runaway loops


class AgentLoop:
    """
    Orchestrates the full ReAct loop for one conversation session.

    Usage:
        agent  = AgentLoop()
        answer = agent.run("What is the latest news on fusion energy?")
    """

    def __init__(self):
        self.client   = anthropic.Anthropic()   # Reads ANTHROPIC_API_KEY from env
        self.registry = ToolRegistry()
        self.memory   = ConversationMemory()

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self, question: str) -> str:
        """
        Runs the ReAct loop for a single question.

        Args:
            question: The user's question (plain string).

        Returns:
            Claude's final answer as a plain string.
        """
        self.memory.add_user_message(question)

        system = FOLLOWUP_PROMPT if self.memory.is_followup() else RESEARCHER_PROMPT

        print(f"\n🤖 Agent thinking... (max {MAX_ITERATIONS} steps)")

        for step in range(1, MAX_ITERATIONS + 1):
            print(f"  ↻ Step {step}")

            # ── REASON: Ask Claude what to do next ───────────────────────────
            response = self.client.messages.create(
                model     = MODEL,
                max_tokens= 1024,
                system    = system,
                tools     = self.registry.get_schemas(),
                messages  = self.memory.get_messages(),
            )

            # ── Done? → Extract and return answer ────────────────────────────
            if response.stop_reason == "end_turn":
                answer = self._extract_text(response)
                self.memory.add_assistant_message(response.content)
                print(f"  ✓ Finished in {step} step(s) — {self.registry.summary()}")
                return answer or FALLBACK_MESSAGE

            # ── Tool call? → Execute it and loop ─────────────────────────────
            elif response.stop_reason == "tool_use":
                # Save Claude's response (contains the tool_use block)
                self.memory.add_assistant_message(response.content)

                # ACT + OBSERVE: run each tool, collect results
                tool_results = self._execute_tools(response)

                # Send results back to Claude as a user message
                self.memory.add_tool_results(tool_results)

            else:
                print(f"  ⚠ Unexpected stop_reason: {response.stop_reason}")
                break

        return FALLBACK_MESSAGE

    # ── Tool execution ────────────────────────────────────────────────────────

    def _execute_tools(self, response) -> list[dict]:
        """
        Finds all tool_use blocks in Claude's response,
        runs each tool, and packages the results.

        Returns:
            List of tool_result dicts ready to send back to Claude.

        INTERNAL: The tool_result format is required by the Anthropic API.
        Each result must reference the tool_use_id from Claude's request.
        """
        results = []

        for block in response.content:
            if block.type != "tool_use":
                continue

            # Run the tool via registry
            output = self.registry.execute(block.name, block.input)

            # Package result in the format the API expects
            results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,     # Must match Claude's tool_use id
                "content":     output,        # String result from our tool
            })

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_text(self, response) -> str:
        """Pull plain text from response content blocks."""
        return "\n".join(
            block.text
            for block in response.content
            if hasattr(block, "text") and block.text
        ).strip()

    def new_session(self):
        """Wipe memory and reset tool counters for a fresh conversation."""
        self.memory.clear()
        self.registry.reset()
        print("  🔄 New session started.")
