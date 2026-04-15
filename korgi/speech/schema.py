from __future__ import annotations

import re

# Canonical emotion tag set.
TAG_SET = frozenset({"happy", "sad", "angry", "thinking", "hesitate", "serious"})

# Default implicit tag — not emitted in text; assumed when no tag is present.
DEFAULT_TAG = "serious"

# Matches any canonical tag in the speech text.
# Canonical format is ElevenLabs-native square brackets: [happy], [hesitate], etc.
TAG_RE = re.compile(r"\[(happy|sad|angry|thinking|hesitate|serious)\]")

# Speech length calibration — the *LLM draft* target, not TTS wall-clock speed.
# Retuned on 2026-04-15 after a 30-min JA request produced only ~8:42 of audio
# with ElevenLabs v3 (≈3.4× undershoot vs. the old 190/140 targets). The new
# constants aim for wall-clock duration with the current default voices; if
# the observed duration is still <80% of the request, the pipeline issues a
# one-shot expand-retry (see pipeline.run_pipeline).
JA_CHARS_PER_MIN: int = 420
EN_WORDS_PER_MIN: int = 170

# Stage 4: slide cue pseudo-tag.
# Inserted into speech.md to mark where the slide should advance. TTS adapters
# MUST strip this before synthesis and record the cue position as a timestamp
# in slides.json (via character-ratio estimation against total audio duration).
SLIDE_TAG = "[slide:next]"
SLIDE_TAG_RE = re.compile(r"\[slide:next\]")


def strip_slide_tags(text: str) -> str:
    """Remove all [slide:next] cue markers from `text`."""
    return SLIDE_TAG_RE.sub("", text)
