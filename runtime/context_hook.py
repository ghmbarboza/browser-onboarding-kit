#!/usr/bin/env python3
"""Supply local instructions; never read page contents or approve tools."""
import json
import os
from pathlib import Path
import sys


def main():
    if os.environ.get("BROWSER_ONBOARDING_OFF") == "1":
        return
    try:
        payload = json.load(sys.stdin)
        event = payload.get("hook_event_name")
        if event not in {"SessionStart", "UserPromptSubmit"}:
            return
        context = Path(__file__).with_name("context.md").read_text(encoding="utf-8")
    except (OSError, ValueError, AttributeError):
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": event,
        "additionalContext": context,
    }}, ensure_ascii=False))


if __name__ == "__main__":
    main()
