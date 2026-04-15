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
class LipSyncSettings:
    sensitivity: float = 2.0
    smoothing: float = 0.15
    min_threshold: float = 0.01
    use_mouth_form: bool = True


@dataclass(frozen=True)
class Live2DSettings:
    model_path: str = "/live2d/hiyori/Hiyori.model3.json"
    scale: float = 0.25
    x_offset: float = 0.0
    y_offset: float = 0.0
    lip_sync: LipSyncSettings = field(default_factory=LipSyncSettings)


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
    live2d: Live2DSettings = field(default_factory=Live2DSettings)
