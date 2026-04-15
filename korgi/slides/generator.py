"""Stage 2f — generate Marp-format slide markdown from cued speech.

Input: tagged speech containing `[slide:next]` markers + the resume for
reference. Output: `slides/slides.md` with one `---`-separated slide per
cue (plus one title slide).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..config import Config, load
from ..llm.client import client
from ..speech.schema import SLIDE_TAG_RE

Lang = Literal["ja", "en"]

_PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"


def _prompt(lang: Lang) -> str:
    return (_PROMPT_DIR / f"slides_{lang}.md").read_text(encoding="utf-8")


def generate(
    cued_speech: str,
    resume_md: str,
    lang: Lang,
    cfg: Config | None = None,
) -> str:
    """Return Marp markdown with `count([slide:next]) + 1` slides."""
    cfg = cfg or load()
    cue_count = len(SLIDE_TAG_RE.findall(cued_speech))
    expected_slides = cue_count + 1

    user_content = (
        f"<resume>\n{resume_md}\n</resume>\n\n"
        f"<speech_with_cues>\n{cued_speech}\n</speech_with_cues>\n\n"
        f"Produce exactly {expected_slides} slides "
        f"(1 title + {cue_count} content slides, one per [slide:next] cue)."
    )
    resp = client(cfg).messages.create(
        model=cfg.generation_model,
        max_tokens=16000,
        system=_prompt(lang),
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    # Defensive: strip any accidental surrounding code fence.
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```") and lines[-1].startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    return text
