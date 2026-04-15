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


def expand(
    prev_speech: str,
    resume_md: str,
    paper_md: str,
    character: CharacterProfile,
    lang: Lang,
    factor: float,
    cfg: Config | None = None,
) -> str:
    """Re-prompt Stage 2 to produce a *longer* draft.

    Used by the pipeline when the synthesized audio falls short of the
    requested minutes. The previous draft is passed in as a reference so
    the expansion stays on-topic.
    """
    cfg = cfg or load()
    factor = max(1.1, float(factor))

    if lang == "ja":
        prev_units = len(prev_speech)
        target = int(prev_units * factor)
        length_tag = f"<expand_to_chars>{target}</expand_to_chars>"
    else:
        prev_units = len(prev_speech.split())
        target = int(prev_units * factor)
        length_tag = f"<expand_to_words>{target}</expand_to_words>"

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
                f"<previous_draft>\n{prev_speech}\n</previous_draft>\n"
                f"{length_tag}\n\n"
                "The previous draft is too short. Rewrite the lecture to reach "
                "the expanded length target. Preserve the overall structure, "
                "section order, and claims — add depth via worked examples, "
                "intuition, restatements, and smoother transitions. Do not add "
                "new citations or facts not present in the paper or resume. "
                "Return only the new speech body (no preamble)."
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
