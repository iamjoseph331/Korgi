"""Stub TTS adapter — template for adding a new provider (e.g. VoxCPM2).

To implement a new adapter:
1. Copy this file and rename it (e.g. voxcpm2.py).
2. Set `name` to the CLI --provider value (e.g. "voxcpm2").
3. Fill in `default_voices`, `supports_tags`, `supports_streaming`.
4. Implement `synth()` — write audio/full.wav and audio/timing.json.
5. Add a column to korgi/tts/tag_translate.py for your provider's tag syntax.
6. Import this module in registry._ensure_defaults_loaded().

VoxCPM2 reference:
    pip install voxcpm
    from voxcpm import VoxCPM
    model = VoxCPM()
    for chunk in model.generate_streaming(text, reference_wav_path=...):
        ...
    Style control: pass style as a parenthetical prefix, e.g. "(happy) text here".
    See: https://github.com/OpenBMB/VoxCPM
"""

from __future__ import annotations

import json
from pathlib import Path

from ..speech.schema import strip_slide_tags
from .base import Lang, SynthResult, TimingEntry
from .registry import register
from .tag_translate import to_stub


@register
class StubAdapter:
    name = "stub"
    supports_tags = True   # uses prose-style prefix via to_stub()
    supports_streaming = False
    default_voices: dict[str, str] = {
        "ja": "",
        "en": "",
    }

    def synth(self, text_with_tags: str, voice: str, lang: Lang, out_dir: Path) -> SynthResult:
        # Strip slide cues before synth; a real adapter should also call
        # estimate_cues() + write_slides_json() after it knows duration_ms.
        translated = strip_slide_tags(to_stub(text_with_tags))

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "full.wav"
        timing_path = out_dir / "timing.json"

        # TODO: replace with actual synthesis call, e.g.:
        #   from voxcpm import VoxCPM
        #   model = VoxCPM()
        #   chunks = list(model.generate_streaming(translated, reference_wav_path=voice or None))
        #   audio_bytes = b"".join(chunks)
        raise NotImplementedError(
            "Stub adapter: implement synth() for your target provider. "
            "See the module docstring for VoxCPM2 example."
        )

        entries = [TimingEntry(start_ms=0, end_ms=0, text=translated, tag="serious")]
        timing_path.write_text(
            json.dumps([vars(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return SynthResult(
            audio_path=audio_path,
            timing_path=timing_path,
            duration_ms=0,
            entries=entries,
        )
