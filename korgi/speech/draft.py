from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml

from ..characters.schema import CharacterProfile
from ..config import Config, load
from ..llm.client import client
from .schema import EN_WORDS_PER_MIN, JA_CHARS_PER_MIN

Lang = Literal["ja", "en"]

_PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"


def _system(lang: Lang) -> str:
    return (_PROMPT_DIR / f"speech_{lang}.md").read_text(encoding="utf-8")


def _char_block(char: CharacterProfile) -> str:
    return yaml.dump(
        {
            "name": char.name,
            "persona": char.persona,
            "speech_style": {
                "formality": char.speech_style.formality,
                "pace": char.speech_style.pace,
                "sentence_length": char.speech_style.sentence_length,
                "verbal_tics": list(char.speech_style.verbal_tics),
                "avoid": list(char.speech_style.avoid),
            },
            "energy": char.energy,
            "humor": char.humor,
            "catchphrases": list(char.catchphrases),
        },
        allow_unicode=True,
        default_flow_style=False,
    )


def generate(
    resume_md: str,
    paper_md: str,
    character: CharacterProfile,
    lang: Lang,
    minutes: int,
    cfg: Config | None = None,
) -> str:
    """Stage 2a: generate a plain speech draft (no emotion tags)."""
    cfg = cfg or load()

    if lang == "ja":
        target = minutes * JA_CHARS_PER_MIN
        length_tag = f"<length_target_chars>{target}</length_target_chars>"
    else:
        target = minutes * EN_WORDS_PER_MIN
        length_tag = f"<length_target_words>{target}</length_target_words>"

    user_blocks = [
        {
            "type": "text",
            "text": f"<paper>\n{paper_md}\n</paper>",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"<resume>\n{resume_md}\n</resume>",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"<character>\n{_char_block(character)}\n</character>\n"
                f"<minutes>{minutes}</minutes>\n"
                f"{length_tag}\n\n"
                "Write the lecture speech now."
            ),
        },
    ]

    resp = client(cfg).messages.create(
        model=cfg.generation_model,
        max_tokens=16000,
        system=_system(lang),
        messages=[{"role": "user", "content": user_blocks}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
