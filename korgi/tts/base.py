from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

Lang = Literal["ja", "en"]


@dataclass
class TimingEntry:
    start_ms: int
    end_ms: int
    text: str
    tag: str  # canonical tag in effect at this segment, or "serious" (default)


@dataclass
class SynthResult:
    audio_path: Path
    timing_path: Path
    duration_ms: int
    entries: list[TimingEntry] = field(default_factory=list)


@runtime_checkable
class TTSAdapter(Protocol):
    name: str
    supports_tags: bool
    supports_streaming: bool
    default_voices: dict[Lang, str]

    def synth(
        self,
        text_with_tags: str,
        voice: str,
        lang: Lang,
        out_dir: Path,
    ) -> SynthResult: ...
