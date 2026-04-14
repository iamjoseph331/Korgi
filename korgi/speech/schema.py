from __future__ import annotations

import re

# Canonical emotion tag set.
TAG_SET = frozenset({"happy", "sad", "angry", "thinking", "hesitate", "serious"})

# Default implicit tag — not emitted in text; assumed when no tag is present.
DEFAULT_TAG = "serious"

# Matches any canonical tag in the speech text.
# Canonical format is ElevenLabs-native square brackets: [happy], [hesitate], etc.
TAG_RE = re.compile(r"\[(happy|sad|angry|thinking|hesitate|serious)\]")

# Speech length calibration.
# JA: measured in characters (kana/kanji mixed), ~180–200 chars/min for a
# measured academic lecture pace. EN: ~750 words/min is too fast; ~130-150 wpm.
JA_CHARS_PER_MIN: int = 190
EN_WORDS_PER_MIN: int = 140
