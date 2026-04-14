"""Translate canonical Korgi emotion tags to each TTS provider's native syntax.

Canonical tags use ElevenLabs-native square-bracket format:
  [happy] [sad] [angry] [thinking] [hesitate] [serious]

ElevenLabs v3 is the "native" format — no translation needed, pass-through.
Other adapters convert away from square-bracket tags to their own syntax or strip them.
"""

from __future__ import annotations

import re

# ELEVENLABS: canonical IS the ElevenLabs format — identity mapping.
ELEVENLABS_MAP: dict[str, str] = {
    "happy": "[happy]",
    "sad": "[sad]",
    "angry": "[angry]",
    "thinking": "[thinking]",
    "hesitate": "[hesitate]",
    "serious": "[serious]",
}

# MOSS-TTS-Nano: no emotion control — strip all tags.
MOSS_MAP: dict[str, str] = {k: "" for k in ELEVENLABS_MAP}

# Stub / VoxCPM2-style: parenthetical prefix on each tagged segment.
STUB_MAP: dict[str, str] = {
    "happy": "(happy) ",
    "sad": "(sad) ",
    "angry": "(angry) ",
    "thinking": "(contemplative) ",
    "hesitate": "(hesitant) ",
    "serious": "(calm) ",
}

_TAG_RE = re.compile(r"\[(happy|sad|angry|thinking|hesitate|serious)\]")


def _translate(text: str, mapping: dict[str, str]) -> str:
    return _TAG_RE.sub(lambda m: mapping.get(m.group(1), ""), text)


def to_elevenlabs(text: str) -> str:
    """Pass-through — canonical format already matches ElevenLabs v3."""
    return text  # no translation needed; tags are already [bracket] style


def to_moss(text: str) -> str:
    return _translate(text, MOSS_MAP)


def to_stub(text: str) -> str:
    return _translate(text, STUB_MAP)
