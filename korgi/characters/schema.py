from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Lang = Literal["ja", "en"]
TagBiasLevel = Literal["none", "low", "medium", "high"]


@dataclass(frozen=True)
class SpeechStyle:
    formality: str
    pace: str
    sentence_length: str
    verbal_tics: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()


@dataclass(frozen=True)
class CharacterProfile:
    name: str
    lang: Lang
    persona: str
    speech_style: SpeechStyle
    energy: float = 0.5
    humor: str = "low"
    catchphrases: tuple[str, ...] = ()
    tag_bias: dict[str, TagBiasLevel] = field(default_factory=dict)
    live2d_expression_map: dict[str, str] = field(default_factory=dict)
