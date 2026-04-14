from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from ..config import Config, load
from ..llm.client import client

_PROMPT = (Path(__file__).parent.parent / "llm" / "prompts" / "fact_check_speech.md").read_text(
    encoding="utf-8"
)

_SENT_RE = re.compile(r"(?<=[。．.!?！？])\s+|\n\n+")
_HEADING_RE = re.compile(r"^#{1,6}\s")


@dataclass
class SpeechFlag:
    sentence: str
    reason: str
    citation: str | None


def _split_sentences(md: str) -> list[str]:
    out: list[str] = []
    for line in md.splitlines():
        line = line.strip()
        if not line or _HEADING_RE.match(line):
            continue
        for piece in _SENT_RE.split(line):
            p = piece.strip()
            if len(p) >= 10:
                out.append(p)
    return out


def verify(
    speech_md: str,
    paper_md: str,
    cfg: Config | None = None,
    search_cap: int = 8,
) -> list[SpeechFlag]:
    """Stage 2b: classify speech sentences and web-search novel claims (capped)."""
    cfg = cfg or load()
    sentences = _split_sentences(speech_md)
    if not sentences:
        return []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    user_blocks = [
        {
            "type": "text",
            "text": f"<paper>\n{paper_md}\n</paper>",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"<sentences>\n{numbered}\n</sentences>\n\n"
                f"Web search budget: {search_cap} searches maximum. "
                "Return the JSON array."
            ),
        },
    ]

    resp = client(cfg).messages.create(
        model=cfg.factcheck_model,
        max_tokens=8192,
        system=_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": search_cap}],
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

    flags: list[SpeechFlag] = []
    for entry in entries:
        if not entry.get("verified", True):
            n = entry.get("n", 0)
            if 1 <= n <= len(sentences):
                flags.append(
                    SpeechFlag(
                        sentence=sentences[n - 1],
                        reason="unverified novel claim",
                        citation=entry.get("citation"),
                    )
                )
    return flags


def annotate_citations(speech_md: str, paper_md: str, cfg: Config | None = None, search_cap: int = 8) -> tuple[str, list[SpeechFlag]]:
    """Return speech with inline citations added for verified novel claims, plus flags list."""
    cfg = cfg or load()
    sentences = _split_sentences(speech_md)
    if not sentences:
        return speech_md, []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    user_blocks = [
        {
            "type": "text",
            "text": f"<paper>\n{paper_md}\n</paper>",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                f"<sentences>\n{numbered}\n</sentences>\n\n"
                f"Web search budget: {search_cap} searches maximum. "
                "Return the JSON array."
            ),
        },
    ]

    resp = client(cfg).messages.create(
        model=cfg.factcheck_model,
        max_tokens=8192,
        system=_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": search_cap}],
        messages=[{"role": "user", "content": user_blocks}],
    )

    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return speech_md, []
    try:
        entries = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return speech_md, []

    citation_map: dict[int, str] = {}
    flags: list[SpeechFlag] = []
    for entry in entries:
        n = entry.get("n", 0)
        if not (1 <= n <= len(sentences)):
            continue
        if entry.get("source") == "novel_claim":
            url = entry.get("citation")
            if url:
                citation_map[n - 1] = url
            if not entry.get("verified", True):
                flags.append(
                    SpeechFlag(
                        sentence=sentences[n - 1],
                        reason="unverified novel claim",
                        citation=url,
                    )
                )

    if not citation_map:
        return speech_md, flags

    # Splice citations back into speech text.
    annotated = speech_md
    for idx in sorted(citation_map.keys(), reverse=True):
        sent = re.escape(sentences[idx])
        url = citation_map[idx]
        annotated = re.sub(
            sent,
            lambda m, u=url: m.group(0) + f" [{u}]",
            annotated,
            count=1,
        )
    return annotated, flags


def dump_flags(flags: list[SpeechFlag]) -> str:
    return json.dumps([asdict(f) for f in flags], ensure_ascii=False, indent=2)
