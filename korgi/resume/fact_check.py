from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from ..config import Config, load
from ..llm.client import client

_SENT_RE = re.compile(r"(?<=[。．.!?！？])\s+|\n\n+")
_HEADING_RE = re.compile(r"^#{1,6}\s")


@dataclass
class Flag:
    sentence: str
    reason: str


def _split_sentences(md: str) -> list[str]:
    out: list[str] = []
    for line in md.splitlines():
        if not line.strip() or _HEADING_RE.match(line) or line.lstrip().startswith(("- ", "* ", "> ")):
            continue
        for piece in _SENT_RE.split(line):
            p = piece.strip()
            if len(p) >= 8:
                out.append(p)
    return out


def verify(resume_md: str, paper_md: str, cfg: Config | None = None) -> list[Flag]:
    """Flag resume sentences not supported by the paper. Uses Haiku + paper prompt cache."""
    cfg = cfg or load()
    sentences = _split_sentences(resume_md)
    if not sentences:
        return []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    system = (
        "You are a strict fact-checker. For each numbered sentence from a lecture "
        "handout, decide whether its factual content is supported by the given "
        "paper. Respond ONLY with a JSON array of objects: "
        '[{"n": 1, "supported": true|false, "reason": "..."}] — one entry per sentence.'
    )
    user_blocks = [
        {
            "type": "text",
            "text": f"<paper>\n{paper_md}\n</paper>",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"<sentences>\n{numbered}\n</sentences>\n\nReturn the JSON array now.",
        },
    ]
    resp = client(cfg).messages.create(
        model=cfg.factcheck_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_blocks}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        entries = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []

    flags: list[Flag] = []
    for entry in entries:
        if entry.get("supported") is False:
            n = entry.get("n", 0)
            if 1 <= n <= len(sentences):
                flags.append(Flag(sentence=sentences[n - 1], reason=str(entry.get("reason", ""))))
    return flags


def dump_flags(flags: list[Flag]) -> str:
    return json.dumps([asdict(f) for f in flags], ensure_ascii=False, indent=2)
