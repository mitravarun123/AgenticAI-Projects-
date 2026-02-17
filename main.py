"""
main.py
=======
Entry point for the Research Assistant Agent.

Run with:
    python main.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

from agent import AgentLoop


# ── Pre-flight checks ─────────────────────────────────────────────────────────

def check_env():
    missing = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.getenv("SERPER_API_KEY"):
        missing.append("SERPER_API_KEY")

    if missing:
        print("❌  Missing keys in your .env file:")
        for key in missing:
            print(f"    {key}=your-key-here")
        print()
        print("  • Anthropic key → https://console.anthropic.com")
        print("  • Serper key    → https://serper.dev")
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

BANNER = """
╔═══════════════════════════════════════════════════╗
║        🔬  Research Assistant Agent               ║
║   Powered by Claude + Serper (Google Search)     ║
╠═══════════════════════════════════════════════════╣
║  Commands:                                        ║
║    'new'  — Start a fresh conversation            ║
║    'quit' — Exit                                  ║
╚═══════════════════════════════════════════════════╝
"""


def print_answer(answer: str):
    print()
    print("─" * 53)
    print("✅  Answer")
    print("─" * 53)
    print(answer)
    print("─" * 53)
    print()


def main():
    check_env()
    print(BANNER)

    agent = AgentLoop()

    while True:
        try:
            user_input = input("❓ Question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        if user_input.lower() in ("new", "reset", "clear"):
            agent.new_session()
            print("✅  New conversation started.\n")
            continue

        try:
            answer = agent.run(user_input)
            print_answer(answer)
        except Exception as e:
            print(f"\n❌  Error: {e}\n")
            # For debugging, uncomment:
            # import traceback; traceback.print_exc()


if __name__ == "__main__":
    main()
