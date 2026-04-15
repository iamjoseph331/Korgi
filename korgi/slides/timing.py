"""Slide timestamp estimation.

Two modes:
  * estimate_cues()              — character-ratio fallback (all providers)
  * cues_from_character_alignment() — exact timestamps from ElevenLabs
                                     character-level alignment data

Character-ratio estimation maps [slide:next] positions proportionally over
the total audio duration. It works reasonably well for prose but drifts on
emotionally-tagged or paused segments. Use alignment data when available.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..speech.schema import SLIDE_TAG, SUPPLEMENT_TAG_RE, TAG_RE


@dataclass
class SlideCue:
    idx: int
    start_ms: int


def _strip_all_tags(text: str) -> str:
    """Strip emotion tags and supplement wrapper tags; slide tags are handled
    by the caller (split point)."""
    text = TAG_RE.sub("", text)
    text = SUPPLEMENT_TAG_RE.sub("", text)
    return text


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


def cues_from_character_alignment(
    cued_speech: str,
    alignment_chars: list[str],
    alignment_start_times_seconds: list[float],
) -> list[SlideCue]:
    """Exact slide cue timestamps derived from ElevenLabs character-level alignment.

    Parameters
    ----------
    cued_speech:
        The speech text as it was originally tagged (with [slide:next] and
        <supplement> markers still present).
    alignment_chars:
        List of individual characters returned by ElevenLabs' alignment API.
        These correspond to the TTS input after slide + supplement tags were
        stripped (but emotion tags were kept for ElevenLabs).
    alignment_start_times_seconds:
        Start time in seconds for each character in `alignment_chars`.
    """
    n = len(alignment_start_times_seconds)
    if n == 0:
        # No alignment data — fall back to proportional estimate.
        total_ms = int(alignment_start_times_seconds[-1] * 1000) if n else 0
        return estimate_cues(cued_speech, total_ms)

    # Build a sorted list of cumulative char counts so we can binary-search
    # for the approximate time at any character offset in the TTS input.
    # alignment_start_times_seconds[i] is the time for the i-th char.

    def time_ms_at_offset(offset: int) -> int:
        """Return the timestamp (ms) for the character at `offset` in the TTS input."""
        # Clamp: if offset is past the last character, return end of audio.
        if offset >= n:
            return int(alignment_start_times_seconds[-1] * 1000)
        if offset <= 0:
            return 0
        return int(alignment_start_times_seconds[offset] * 1000)

    # Split on [slide:next]; each part's TTS-input length = chars after stripping
    # supplement tags (emotion tags stay since ElevenLabs reads them).
    segments = cued_speech.split(SLIDE_TAG)

    cues: list[SlideCue] = [SlideCue(idx=0, start_ms=0)]
    running_offset = 0
    for i, seg in enumerate(segments[:-1]):  # all but last — each marks a cue boundary
        tts_seg = SUPPLEMENT_TAG_RE.sub("", seg)  # strip supplement tags only
        running_offset += len(tts_seg)
        cues.append(SlideCue(idx=i + 1, start_ms=time_ms_at_offset(running_offset)))

    return cues


def write_slides_json(cues: list[SlideCue], path: Path) -> None:
    path.write_text(
        json.dumps([asdict(c) for c in cues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
