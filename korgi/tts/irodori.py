"""Irodori-TTS adapter — Aratako/Irodori-TTS (https://github.com/Aratako/Irodori-TTS).

Install (from local clone at ../TTS/Irodori-TTS):
    uv sync --extra irodori

Irodori-TTS is a Japanese-first open-source flow-matching TTS. English support
is not a first-class target — if lang="en" is requested, the adapter falls back
to reading the text verbatim (pronunciation may be poor).

Emotion tags are stripped (the underlying model has no per-segment emotion
control). Voice cloning uses a reference .wav path passed through the `voice`
field. When `voice` is empty, the model synthesises with a random speaker
(no-ref mode).

This adapter uses the InferenceRuntime API:

    from irodori_tts.inference_runtime import (
        InferenceRuntime, RuntimeKey, SamplingRequest, default_runtime_device,
    )
    from huggingface_hub import hf_hub_download

    ckpt = hf_hub_download("Aratako/Irodori-TTS-500M-v2", "model.safetensors")
    runtime = InferenceRuntime.from_key(
        RuntimeKey(checkpoint=ckpt, model_device=default_runtime_device())
    )
    result = runtime.synthesize(SamplingRequest(
        text=text, ref_wav=voice or None, no_ref=not bool(voice),
        seconds=max(5.0, len(text) / 7.0 * 1.4),
    ))
    wav = result.audio.cpu().float().numpy()   # float32, 48 kHz mono
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
_DEFAULT_CKPT = "Aratako/Irodori-TTS-500M-v2"
_SAMPLE_RATE = 48000  # Irodori outputs 48 kHz via DACVAE codec


def _strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def _call_model(runtime, text: str, ref_wav: str | None) -> "np.ndarray":
    """Synthesize one sentence. Returns float32 numpy array at 48 kHz."""
    import numpy as np
    from irodori_tts.inference_runtime import SamplingRequest  # type: ignore

    # Estimate max output seconds: ~7 Japanese chars/sec with 40 % safety buffer
    seconds = max(5.0, len(text) / 7.0 * 1.4)

    result = runtime.synthesize(
        SamplingRequest(
            text=text,
            ref_wav=ref_wav or None,
            no_ref=not bool(ref_wav),
            seconds=seconds,
        )
    )
    return result.audio.cpu().float().numpy()


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
            from huggingface_hub import hf_hub_download  # type: ignore
            from irodori_tts.inference_runtime import (  # type: ignore
                InferenceRuntime,
                RuntimeKey,
                default_runtime_device,
            )
        except ImportError as e:
            raise RuntimeError(
                "irodori-tts not installed. Run: uv sync --extra irodori"
            ) from e

        if lang == "en":
            print(
                "[irodori] English is not a first-class target; "
                "pronunciation may degrade.",
                flush=True,
            )

        if voice_settings:
            if float(voice_settings.get("speed", 1.0)) != 1.0:
                print("[irodori] speed control not supported; ignored.", flush=True)
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

        # Download checkpoint on first run (cached by huggingface_hub afterwards)
        ckpt_path = hf_hub_download(repo_id=_DEFAULT_CKPT, filename="model.safetensors")
        key = RuntimeKey(checkpoint=ckpt_path, model_device=default_runtime_device())
        runtime = InferenceRuntime.from_key(key)

        import numpy as np
        segs: list[bytes] = []
        entries: list[TimingEntry] = []
        cursor_ms = 0

        for sent in sentences:
            wav = _call_model(runtime, sent, voice or None)
            if wav is None:
                continue
            arr = np.asarray(wav, dtype="float32")
            # Downmix stereo (2, T) → mono (T,) if needed
            if arr.ndim == 2:
                arr = arr.mean(axis=0)
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
