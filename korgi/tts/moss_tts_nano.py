"""MOSS-TTS-Nano adapter.

Requires: pip install 'korgi[moss]'
CPU-capable; no GPU required.

MOSS-TTS-Nano does not support emotion tags — they are stripped before synthesis.
Voice cloning requires a reference audio file (.wav). If none is provided,
the adapter uses the model's built-in default voice.
"""

from __future__ import annotations

import json
import re
import wave
from pathlib import Path

from ..slides.timing import estimate_cues, write_slides_json
from ..speech.schema import SLIDE_TAG_RE, strip_slide_tags
from .base import Lang, SynthResult, TimingEntry
from .registry import register
from .tag_translate import to_moss

_SENT_SPLIT = re.compile(r"(?<=[。．.!?！？])\s*")


@register
class MOSSTTSNanoAdapter:
    name = "moss"
    supports_tags = False
    supports_streaming = True
    default_voices: dict[str, str] = {
        "ja": "",
        "en": "",
    }

    def synth(self, text_with_tags: str, voice: str, lang: Lang, out_dir: Path) -> SynthResult:
        try:
            from moss_tts_nano import MossTTSNano
        except ImportError as e:
            raise RuntimeError(
                "moss-tts-nano not installed. Run: pip install 'korgi[moss]'"
            ) from e

        cued_speech = text_with_tags
        plain = strip_slide_tags(to_moss(text_with_tags))
        sentences = [s.strip() for s in _SENT_SPLIT.split(plain) if s.strip()]

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "full.wav"
        timing_path = out_dir / "timing.json"
        slides_json_path = out_dir / "slides.json"

        model = MossTTSNano()
        all_pcm: list[bytes] = []
        entries: list[TimingEntry] = []
        cursor_ms = 0

        for sent in sentences:
            kwargs: dict = {"text": sent}
            if voice:
                kwargs["prompt_audio_path"] = voice
            pcm = model.generate(**kwargs)
            if pcm is None:
                continue
            duration_ms = int(len(pcm) / 2 / 24000 * 1000)
            entries.append(
                TimingEntry(start_ms=cursor_ms, end_ms=cursor_ms + duration_ms, text=sent, tag="serious")
            )
            cursor_ms += duration_ms
            all_pcm.append(pcm)

        combined = b"".join(all_pcm)
        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(combined)

        timing_path.write_text(
            json.dumps([vars(e) for e in entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if SLIDE_TAG_RE.search(cued_speech):
            write_slides_json(estimate_cues(cued_speech, cursor_ms), slides_json_path)
        return SynthResult(
            audio_path=audio_path,
            timing_path=timing_path,
            duration_ms=cursor_ms,
            entries=entries,
        )
