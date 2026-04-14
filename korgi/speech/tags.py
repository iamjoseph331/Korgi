from __future__ import annotations

import re
from pathlib import Path

from ..characters.schema import CharacterProfile
from ..config import Config, load
from ..llm.client import client
from .schema import TAG_RE, TAG_SET

_PROMPT = (Path(__file__).parent.parent / "llm" / "prompts" / "tag_inject.md").read_text(
    encoding="utf-8"
)
_MAX_RETRIES = 1


def _strip_unknown_tags(text: str) -> str:
    """Remove any [tag] that is not in TAG_SET."""
    return re.sub(r"\[([^\]]+)\]", lambda m: m.group(0) if m.group(1) in TAG_SET else "", text)


def _text_without_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def _non_tag_diff(original: str, tagged: str) -> bool:
    """Return True if non-tag content differs (signals invalid output)."""
    return _text_without_tags(original).strip() != _text_without_tags(tagged).strip()


def inject(
    speech_md: str,
    character: CharacterProfile,
    cfg: Config | None = None,
) -> str:
    """Stage 2c: insert canonical emotion tags into the speech draft.

    If the model modifies non-tag text, retries once. Returns best result.
    """
    cfg = cfg or load()
    bias_block = "\n".join(f"  {tag}: {level}" for tag, level in character.tag_bias.items())
    tag_bias_yaml = f"tag_bias:\n{bias_block}" if bias_block else "tag_bias: {}"

    def _call(speech: str) -> str:
        user_content = (
            f"<character_tag_bias>\n{tag_bias_yaml}\n</character_tag_bias>\n\n"
            f"<speech>\n{speech}\n</speech>\n\n"
            "Insert emotion tags now. Return the complete tagged speech."
        )
        resp = client(cfg).messages.create(
            model=cfg.generation_model,
            max_tokens=16000,
            system=_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text").strip()
        return _strip_unknown_tags(raw)

    result = _call(speech_md)

    if _non_tag_diff(speech_md, result):
        # One retry with an explicit reminder.
        retry_speech = (
            "IMPORTANT: Do not change any words. Only insert tags.\n\n"
            + speech_md
        )
        result = _call(retry_speech)
        if _non_tag_diff(speech_md, result):
            # Fall back to the original with no tags rather than corrupt text.
            return speech_md

    return result
