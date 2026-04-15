"""Irodori-TTS adapter — Aratako/Irodori-TTS (https://github.com/Aratako/Irodori-TTS).

Install:
    pip install "git+https://github.com/Aratako/Irodori-TTS.git" numpy

Irodori-TTS is a Japanese-first open-source TTS. English support is not a
first-class target — if lang="en" is requested, the adapter falls back to
reading the text verbatim (pronunciation may be poor).

Emotion tags are stripped (the underlying model does not expose per-segment
emotion control in its stable API). Voice cloning uses a reference .wav path
passed through the `voice` field.

This adapter targets a typical `IrodoriTTS` loader:

    from irodori_tts import IrodoriTTS
    model = IrodoriTTS.from_pretrained("Aratako/Irodori-TTS")
    wav = model.synthesize(text=..., reference_audio=... or None, sr=24000)
    #     wav: numpy.ndarray, float32, 24kHz mono

If the upstream API diverges, adjust `_call_model` below — the rest of this
adapter is provider-agnostic.
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
_DEFAULT_CKPT = "Aratako/Irodori-TTS"
_SAMPLE_RATE = 24000


def _strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def _call_model(model, text: str, reference_wav: str | None, speed: float):
    kwargs: dict = {"text": text, "sr": _SAMPLE_RATE}
    if reference_wav:
        kwargs["reference_audio"] = reference_wav
    if abs(speed - 1.0) > 1e-6:
        # If the upstream API doesn't accept `speed`, it will raise; fall back
        # to unscaled synthesis so generation still succeeds.
        try:
            return model.synthesize(**kwargs, speed=speed)
        except TypeError:
            pass
    return model.synthesize(**kwargs)


@register
class IrodoriTTSAdapter:
    name = "irodori"
    supports_tags = False
    supports_streaming = False
    default_voices: dict[str, str] = {
        "ja": "",
        "en": "",  # English not a first-class target; warn at call time
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
            import numpy as np  # noqa: F401
            from irodori_tts import IrodoriTTS  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "irodori-tts not installed. Install from source: "
                "pip install 'git+https://github.com/Aratako/Irodori-TTS.git' numpy"
            ) from e

        if lang == "en":
            print(
                "[irodori] English is not a first-class target; "
                "pronunciation may degrade.",
                flush=True,
            )

        speed = 1.0
        if voice_settings:
            speed = max(0.7, min(1.5, float(voice_settings.get("speed", 1.0))))
            if int(voice_settings.get("pitch", 0)) != 0:
                print("[irodori] pitch not supported; ignored.", flush=True)

        cued_speech = text_with_tags
        plain = strip_supplement_tags(strip_slide_tags(_strip_tags(text_with_tags)))
        sentences = [s.strip() for s in _SENT_SPLIT.split(plain) if s.strip()]

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "full.wav"
        timing_path = out_dir / "timing.json"
        slides_json_path = out_dir / "slides.json"

        model = IrodoriTTS.from_pretrained(_DEFAULT_CKPT)

        import numpy as np
        segs: list[bytes] = []
        entries: list[TimingEntry] = []
        cursor_ms = 0

        for sent in sentences:
            wav = _call_model(model, sent, voice or None, speed)
            if wav is None:
                continue
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
