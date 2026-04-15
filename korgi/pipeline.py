"""End-to-end pipeline runner shared by the CLI and the web server.

Both `korgi pipeline` (CLI) and `POST /api/run` (web) drive this. The
`on_event` callback fires at every milestone so the web UI can stream
progress over SSE while the CLI just prints.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Literal, Optional

EventKind = Literal["stage", "log", "warn", "done", "error"]
EventCallback = Callable[[str, str, Optional[dict]], None]

# If the synthesized audio is shorter than this fraction of the requested
# duration, the pipeline re-prompts Stage 2 with an expanded length target
# and re-synthesizes. Disable with KORGI_LENGTH_RETRY=0.
LENGTH_RETRY_FLOOR: float = 0.80
MAX_EXPAND_RETRIES: int = 1


def _noop(_kind: str, _message: str, _payload: Optional[dict] = None) -> None:
    pass


def run_pipeline(
    paper: Path,
    lang: str = "ja",
    minutes: int = 45,
    character: str = "",
    provider: str = "elevenlabs",
    voice: str = "",
    out: Path = Path("out"),
    skip_factcheck: bool = False,
    slides: bool = True,
    voice_settings: Optional[dict] = None,
    on_event: EventCallback = _noop,
) -> Path:
    """Run Stage 1 → 2 (+ optional Stage 4 slides) → TTS. Returns the run dir."""
    if lang not in ("ja", "en"):
        raise ValueError(f"lang must be 'ja' or 'en', got {lang!r}")

    from .characters import loader as char_loader
    from .io.run_dir import prepare
    from .pdf import to_markdown
    from .resume import fact_check as resume_fact_check
    from .resume import generator as resume_generator
    from .slides import generator as slides_gen, render as slides_render
    from .speech import draft, fact_check as speech_fc, slide_cues, tags
    from .tts import registry

    char_name = character or f"default_{lang}"
    char = char_loader.load(char_name)
    run = prepare(out, paper)
    on_event("log", f"run dir: {run}", {"run_dir": str(run)})

    # ── Stage 1 ──────────────────────────────────────────
    on_event("stage", "Stage 1: レジュメ", {"stage": "resume"})
    paper_md_path = to_markdown.convert(paper, run)
    paper_md = paper_md_path.read_text(encoding="utf-8")
    on_event("log", f"paper.md  ({len(paper_md):,} chars)")

    resume_md = resume_generator.generate(paper_md, lang, minutes)  # type: ignore[arg-type]
    (run / "resume.md").write_text(resume_md, encoding="utf-8")
    flags = resume_fact_check.verify(resume_md, paper_md)
    (run / "resume.flags.json").write_text(
        resume_fact_check.dump_flags(flags), encoding="utf-8"
    )
    on_event(
        "log",
        f"resume.md  ({len(resume_md):,} chars) — flags={len(flags)}",
        {"resume_chars": len(resume_md), "flags": len(flags)},
    )

    # ── Stage 2 ──────────────────────────────────────────
    on_event("stage", "Stage 2: スピーチ", {"stage": "speech"})
    speech_plain = draft.generate(resume_md, paper_md, char, lang, minutes)  # type: ignore[arg-type]
    if not skip_factcheck:
        speech_plain, fc_flags = speech_fc.annotate_citations(speech_plain, paper_md)
        (run / "speech.flags.json").write_text(
            speech_fc.dump_flags(fc_flags), encoding="utf-8"
        )
        on_event("log", f"speech fact-check flags={len(fc_flags)}", {"flags": len(fc_flags)})
    tagged = tags.inject(speech_plain, char)

    # ── Stage 4 (optional) ───────────────────────────────
    final_speech = tagged
    if slides:
        on_event("stage", "Stage 4: slides", {"stage": "slides"})
        cued = slide_cues.inject(tagged, char)
        final_speech = cued
        slides_md = slides_gen.generate(cued, resume_md, lang)  # type: ignore[arg-type]
        slides_dir = run / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        slides_md_path = slides_dir / "slides.md"
        slides_md_path.write_text(slides_md, encoding="utf-8")
        rendered = slides_render.render(slides_md_path)
        on_event(
            "log",
            "slides.md written" + (" (+ slides.html)" if rendered else " (client render)"),
            {"html": bool(rendered)},
        )

    speech_path = run / "speech.md"
    speech_path.write_text(final_speech, encoding="utf-8")
    on_event("log", f"speech.md  ({len(final_speech):,} chars)")

    # ── TTS ──────────────────────────────────────────────
    on_event("stage", f"TTS: {provider}", {"stage": "tts", "provider": provider})
    adapter = registry.get(provider)
    audio_dir = run / "audio" / provider
    resolved_voice = voice or adapter.default_voices.get(lang, "")
    result = adapter.synth(
        final_speech, resolved_voice, lang, audio_dir,  # type: ignore[arg-type]
        voice_settings=voice_settings,
    )
    on_event(
        "log",
        f"audio: {result.audio_path}  ({result.duration_ms / 1000:.1f}s)",
        {"duration_ms": result.duration_ms},
    )

    # ── optional length-expand retry ─────────────────────
    expected_ms = minutes * 60_000
    retries_enabled = os.environ.get("KORGI_LENGTH_RETRY", "1") != "0"
    if (
        retries_enabled
        and expected_ms > 0
        and result.duration_ms < LENGTH_RETRY_FLOOR * expected_ms
    ):
        factor = expected_ms / max(result.duration_ms, 1)
        on_event(
            "warn",
            f"audio short ({result.duration_ms / 1000:.1f}s vs "
            f"{expected_ms / 1000:.0f}s target); expanding {factor:.2f}×",
            {"duration_ms": result.duration_ms, "expected_ms": expected_ms, "factor": factor},
        )
        speech_plain_v2 = draft.expand(
            speech_plain, resume_md, paper_md, char, lang, factor  # type: ignore[arg-type]
        )
        tagged_v2 = tags.inject(speech_plain_v2, char)
        final_speech_v2 = tagged_v2
        if slides:
            cued_v2 = slide_cues.inject(tagged_v2, char)
            final_speech_v2 = cued_v2
            slides_md_v2 = slides_gen.generate(cued_v2, resume_md, lang)  # type: ignore[arg-type]
            slides_md_path = (run / "slides" / "slides.md")
            slides_md_path.write_text(slides_md_v2, encoding="utf-8")
            slides_render.render(slides_md_path)
        speech_path.write_text(final_speech_v2, encoding="utf-8")
        on_event("log", f"speech.md expanded ({len(final_speech_v2):,} chars)")
        result = adapter.synth(final_speech_v2, resolved_voice, lang, audio_dir)  # type: ignore[arg-type]
        on_event(
            "log",
            f"audio (retry): {result.audio_path}  ({result.duration_ms / 1000:.1f}s)",
            {"duration_ms": result.duration_ms, "retry": True},
        )

    on_event(
        "done",
        "pipeline complete",
        {
            "run_dir": str(run),
            "run_slug": run.name,
            "audio_path": str(result.audio_path),
            "duration_ms": result.duration_ms,
        },
    )
    return run
