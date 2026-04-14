from __future__ import annotations

from pathlib import Path

SKILL_PATH = Path.home() / ".claude" / "skills" / "resume-maker" / "SKILL.md"


def load() -> str:
    """Return the resume-maker SKILL.md body (frontmatter stripped)."""
    if not SKILL_PATH.exists():
        raise FileNotFoundError(
            f"resume-maker skill not found at {SKILL_PATH}. "
            f"Run `korgi init-skills` to install the default."
        )
    raw = SKILL_PATH.read_text(encoding="utf-8")
    return _strip_frontmatter(raw)


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")
