"""Stage 2e — insert [slide:next] cues into the tagged speech.

Opus 4.6 call with the same diff-guard pattern as tags.inject: the non-cue
text of the input must match the non-cue text of the output, else we retry
once, and on second failure fall back to a deterministic H2-boundary pass.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..characters.schema import CharacterProfile
from ..config import Config, load
from ..llm.client import client
from .schema import SLIDE_TAG, SLIDE_TAG_RE

_PROMPT = (Path(__file__).parent.parent / "llm" / "prompts" / "slide_cues.md").read_text(
    encoding="utf-8"
)

_H2_RE = re.compile(r"^##\s+", re.MULTILINE)


def _strip_cues(text: str) -> str:
    return SLIDE_TAG_RE.sub("", text)


def _non_cue_diff(original: str, cued: str) -> bool:
    """Return True if non-cue content differs (signals invalid output)."""
    return _strip_cues(original).strip() != _strip_cues(cued).strip()


def _deterministic_h2_fallback(tagged_speech: str) -> str:
    """Fallback: insert [slide:next] on its own line immediately before each H2.

    Preserves the original whitespace structure by replacing — not adding —
    the blank line that typically precedes an H2.
    """
    lines = tagged_speech.splitlines()
    out: list[str] = []
    for line in lines:
        if _H2_RE.match(line):
            prev_non_empty = next((ln for ln in reversed(out) if ln.strip()), "")
            if prev_non_empty.strip() != SLIDE_TAG:
                if out and out[-1].strip() == "":
                    out[-1] = SLIDE_TAG
                else:
                    out.append(SLIDE_TAG)
        out.append(line)
    return "\n".join(out)


def inject(
    tagged_speech: str,
    character: CharacterProfile,
    cfg: Config | None = None,
) -> str:
    """Insert [slide:next] cues into the tagged speech.

    If the model modifies any non-cue text, retries once with a stricter
    reminder. If that also fails, falls back to deterministic H2-boundary
    placement.
    """
    cfg = cfg or load()

    def _call(speech: str) -> str:
        user_content = (
            f"<speech>\n{speech}\n</speech>\n\n"
            "Insert [slide:next] cues per the rules. Return the complete speech."
        )
        resp = client(cfg).messages.create(
            model=cfg.generation_model,
            max_tokens=16000,
            system=_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()

    result = _call(tagged_speech)
    if _non_cue_diff(tagged_speech, result):
        retry = (
            "IMPORTANT: Do not change any word, tag, or punctuation. "
            "Only insert [slide:next] markers.\n\n" + tagged_speech
        )
        result = _call(retry)
        if _non_cue_diff(tagged_speech, result):
            return _deterministic_h2_fallback(tagged_speech)

    return result
