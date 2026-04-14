"""ElevenLabs v3 TTS adapter.

Requires: pip install 'korgi[elevenlabs]'
Requires: ELEVENLABS_API_KEY environment variable.
"""

from __future__ import annotations

import io
import json
import os
import wave
from pathlib import Path

from .base import Lang, SynthResult, TimingEntry
from .registry import register
from .tag_translate import to_elevenlabs


@register
class ElevenLabsV3Adapter:
    name = "elevenlabs"
    supports_tags = True
    supports_streaming = True
    default_voices: dict[str, str] = {
        "ja": "21m00Tcm4TlvDq8ikWAM",  # Rachel — placeholder; swap for a JA voice
        "en": "21m00Tcm4TlvDq8ikWAM",  # Rachel
    }

    def synth(self, text_with_tags: str, voice: str, lang: Lang, out_dir: Path) -> SynthResult:
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as e:
            raise RuntimeError(
                "elevenlabs SDK not installed. Run: pip install 'korgi[elevenlabs]'"
            ) from e

        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set.")

        translated = to_elevenlabs(text_with_tags)
        el = ElevenLabs(api_key=api_key)

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "full.wav"
        timing_path = out_dir / "timing.json"

        audio_bytes = b"".join(
            el.text_to_speech.convert(
                text=translated,
                voice_id=voice or self.default_voices.get(lang, self.default_voices["en"]),
                model_id="eleven_v3",
                output_format="pcm_24000",
            )
        )

        # Wrap raw PCM in a WAV container.
        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(24000)
            wf.writeframes(audio_bytes)

        duration_ms = int(len(audio_bytes) / 2 / 24000 * 1000)
        # ElevenLabs v3 doesn't expose per-word timing in the basic convert API;
        # write a single entry covering the full audio.
        entries = [TimingEntry(start_ms=0, end_ms=duration_ms, text=translated, tag="serious")]
        timing_path.write_text(
            json.dumps([vars(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return SynthResult(
            audio_path=audio_path,
            timing_path=timing_path,
            duration_ms=duration_ms,
            entries=entries,
        )
