"""VoxCPM adapter — OpenBMB/VoxCPM (https://github.com/OpenBMB/VoxCPM).

Install:
    pip install "git+https://github.com/OpenBMB/VoxCPM.git" numpy

VoxCPM is a local/open-source TTS from OpenBMB. It does not support emotion
tags — they are stripped before synthesis. Optional voice cloning via a
reference .wav path (same convention as moss-tts-nano's `voice` field).

This adapter targets the stable `VoxCPM` Python API:

    from voxcpm import VoxCPM
    model = VoxCPM.from_pretrained("openbmb/VoxCPM-0.5B")
    wav = model.generate(text=..., prompt_wav_path=... or None)
    #     wav: numpy.ndarray, float32, 24kHz mono (or 16kHz depending on ckpt)

If the upstream API diverges, adjust `_call_model` below — the rest of the
adapter (splitting, timing, cue estimation, WAV writing) is provider-agnostic.
"""

from __future__ import annotations

import json
import re
import wave
from pathlib import Path

from ..slides.timing import estimate_cues, write_slides_json
from ..speech.schema import SLIDE_TAG_RE, TAG_RE, strip_slide_tags, strip_supplement_tags
from .base import Lang, SynthResult, TimingEntry
from .registry import register

_SENT_SPLIT = re.compile(r"(?<=[。．.!?！？])\s*")
_DEFAULT_CKPT = "openbmb/VoxCPM-0.5B"
_SAMPLE_RATE = 16000  # VoxCPM default; override via env if your ckpt differs


def _strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def _call_model(model, text: str, prompt_wav: str | None):
    """One text → one waveform (numpy float32). Kept isolated so the rest of
    the adapter doesn't care about upstream API drift."""
    kwargs: dict = {"text": text}
    if prompt_wav:
        kwargs["prompt_wav_path"] = prompt_wav
    return model.generate(**kwargs)


@register
class VoxCPMAdapter:
    name = "voxcpm"
    supports_tags = False
    supports_streaming = False
    default_voices: dict[str, str] = {
        "ja": "",
        "en": "",
    }

    def synth(
        self,
        text_with_tags: str,
        voice: str,
        lang: Lang,
        out_dir: Path,
        voice_settings: dict | None = None,
    ) -> SynthResult:
        _ = voice_settings  # VoxCPM has no pitch/speed knobs in current API

        try:
            import numpy as np  # noqa: F401
            from voxcpm import VoxCPM  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "voxcpm not installed. Install from source: "
                "pip install 'git+https://github.com/OpenBMB/VoxCPM.git' numpy"
            ) from e

        cued_speech = text_with_tags
        plain = strip_supplement_tags(strip_slide_tags(_strip_tags(text_with_tags)))
        sentences = [s.strip() for s in _SENT_SPLIT.split(plain) if s.strip()]

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "full.wav"
        timing_path = out_dir / "timing.json"
        slides_json_path = out_dir / "slides.json"

        model = VoxCPM.from_pretrained(_DEFAULT_CKPT)

        import numpy as np
        segs: list[bytes] = []
        entries: list[TimingEntry] = []
        cursor_ms = 0

        for sent in sentences:
            wav = _call_model(model, sent, voice or None)
            if wav is None:
                continue
            # Normalise to int16 PCM little-endian.
            arr = np.asarray(wav, dtype="float32")
            arr = np.clip(arr, -1.0, 1.0)
            pcm = (arr * 32767.0).astype("<i2").tobytes()
            duration_ms = int(len(pcm) / 2 / _SAMPLE_RATE * 1000)
            entries.append(
                TimingEntry(start_ms=cursor_ms, end_ms=cursor_ms + duration_ms, text=sent, tag="serious")
            )
            cursor_ms += duration_ms
            segs.append(pcm)

        combined = b"".join(segs)
        with wave.open(str(audio_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_SAMPLE_RATE)
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
