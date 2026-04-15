"""ElevenLabs v3 TTS adapter.

Requires: pip install 'korgi[elevenlabs]'
Requires: ELEVENLABS_API_KEY environment variable.

Slide timing strategy
---------------------
The adapter tries ElevenLabs' `convert_with_timestamps` endpoint first.
This returns character-level alignment data (start time per character) that
lets us place `[slide:next]` cues at their exact spoken position instead of
guessing by character ratio. If the endpoint is unavailable or returns
unexpected data, it falls back to `convert` + `estimate_cues`.
"""

from __future__ import annotations

import base64
import json
import os
import wave
from pathlib import Path

from ..slides.timing import cues_from_character_alignment, estimate_cues, write_slides_json
from ..speech.schema import SLIDE_TAG_RE, strip_slide_tags, strip_supplement_tags
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

    def synth(
        self,
        text_with_tags: str,
        voice: str,
        lang: Lang,
        out_dir: Path,
        voice_settings: dict | None = None,
    ) -> SynthResult:
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError as e:
            raise RuntimeError(
                "elevenlabs SDK not installed. Run: pip install 'korgi[elevenlabs]'"
            ) from e

        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set.")

        # Strip slide cues and supplement wrapper tags before sending to ElevenLabs.
        # <supplement> content (verbal preface) is intentionally kept — only the
        # wrapper tags are removed so the TTS reads the teacher's addition naturally.
        cued_speech = text_with_tags
        synth_input = strip_supplement_tags(strip_slide_tags(to_elevenlabs(text_with_tags)))
        el = ElevenLabs(api_key=api_key)

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "full.wav"
        timing_path = out_dir / "timing.json"
        slides_json_path = out_dir / "slides.json"

        voice_id = voice or self.default_voices.get(lang, self.default_voices["en"])

        base_kwargs: dict = {
            "voice_id": voice_id,
            "model_id": "eleven_v3",
            "output_format": "pcm_24000",
        }
        vs: dict = {}
        if voice_settings:
            speed = float(voice_settings.get("speed", 1.0))
            pitch = int(voice_settings.get("pitch", 0))
            if speed != 1.0:
                vs["speed"] = max(0.7, min(1.5, speed))
            if pitch != 0:
                print(
                    f"[elevenlabs] pitch={pitch} requested but not supported; ignored.",
                    flush=True,
                )
        if vs:
            base_kwargs["voice_settings"] = vs

        # ── Try convert_with_timestamps for exact slide cue positions ──────
        audio_bytes: bytes | None = None
        alignment_chars: list[str] | None = None
        alignment_times: list[float] | None = None

        if SLIDE_TAG_RE.search(cued_speech):
            try:
                ts_result = el.text_to_speech.convert_with_timestamps(
                    text=synth_input,
                    **base_kwargs,
                )
                if ts_result.audio_base64:
                    audio_bytes = base64.b64decode(ts_result.audio_base64)
                al = getattr(ts_result, "alignment", None)
                if al is not None:
                    alignment_chars = getattr(al, "characters", None)
                    alignment_times = getattr(al, "character_start_times_seconds", None)
            except Exception as exc:  # noqa: BLE001
                print(f"[elevenlabs] convert_with_timestamps failed ({exc}); falling back", flush=True)
                audio_bytes = None

        # ── Fall back to plain streaming convert ───────────────────────────
        if audio_bytes is None:
            audio_bytes = b"".join(
                el.text_to_speech.convert(text=synth_input, **base_kwargs)
            )

        # Wrap raw PCM in a WAV container.
        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(24000)
            wf.writeframes(audio_bytes)

        duration_ms = int(len(audio_bytes) / 2 / 24000 * 1000)
        entries = [TimingEntry(start_ms=0, end_ms=duration_ms, text=synth_input, tag="serious")]
        timing_path.write_text(
            json.dumps([vars(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if SLIDE_TAG_RE.search(cued_speech):
            if alignment_chars is not None and alignment_times is not None:
                cues = cues_from_character_alignment(cued_speech, alignment_chars, alignment_times)
            else:
                cues = estimate_cues(cued_speech, duration_ms)
            write_slides_json(cues, slides_json_path)

        return SynthResult(
            audio_path=audio_path,
            timing_path=timing_path,
            duration_ms=duration_ms,
            entries=entries,
        )
