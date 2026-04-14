from __future__ import annotations

from typing import Literal

from ..config import Config, load
from ..llm.client import client
from . import skill_loader

Lang = Literal["ja", "en"]


def generate(
    paper_md: str,
    lang: Lang,
    minutes: int,
    cfg: Config | None = None,
) -> str:
    """Run Stage 1: generate a レジュメ from the paper markdown.

    The paper block is marked with cache_control so the same paper can be
    reused across later Stage 2 calls without re-sending tokens.
    """
    cfg = cfg or load()
    skill_prompt = skill_loader.load()

    lang_name = {"ja": "Japanese (日本語)", "en": "English"}[lang]
    system = (
        skill_prompt
        + f"\n\n---\n\nWrite the entire レジュメ in {lang_name}. "
        f"Target lecture length: {minutes} minutes. Output raw Markdown only."
    )

    user_blocks = [
        {
            "type": "text",
            "text": f"<paper>\n{paper_md}\n</paper>",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"<lang>{lang}</lang>\n<minutes>{minutes}</minutes>\n\n"
                "Generate the レジュメ now."
            ),
        },
    ]

    resp = client(cfg).messages.create(
        model=cfg.generation_model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user_blocks}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
