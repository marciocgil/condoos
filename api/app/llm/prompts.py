"""Versioned prompts live in app/prompts/*.md; never inline prompt text in code."""

import hashlib
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def prompt_fingerprint(text: str) -> str:
    """SHA-256 of a system prompt as sent (D121): identifies the prompt version of a call."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
