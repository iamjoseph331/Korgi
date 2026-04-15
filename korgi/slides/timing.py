"""Slide timestamp estimation via character-ratio against audio duration.

Given the cued speech and the total synthesized duration, compute the
`start_ms` for each `[slide:next]` cue (plus the implicit slide 0 at t=0).
Character count is measured on the post-emotion-tag-stripped, post-slide-
tag-stripped text so it tracks what the TTS engine actually voiced.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..speech.schema import SLIDE_TAG, TAG_RE


@dataclass
class SlideCue:
    idx: int
    start_ms: int


def _strip_all_tags(text: str) -> str:
    # Drop emotion tags; slide tags are handled by the caller (split point).
    return TAG_RE.sub("", text)


def estimate_cues(cued_speech: str, total_duration_ms: int) -> list[SlideCue]:
    """Split `cued_speech` on `[slide:next]` and scale chars → ms."""
    segments = cued_speech.split(SLIDE_TAG)
    cleaned = [_strip_all_tags(seg) for seg in segments]
    char_lens = [len(s) for s in cleaned]
    total_chars = sum(char_lens) or 1

    cues: list[SlideCue] = []
    running_chars = 0
    for i, seg_len in enumerate(char_lens):
        start_ms = int(running_chars / total_chars * total_duration_ms)
        cues.append(SlideCue(idx=i, start_ms=start_ms))
        running_chars += seg_len
    return cues


def write_slides_json(cues: list[SlideCue], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(c) for c in cues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
