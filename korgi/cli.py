from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

from .io.run_dir import prepare
from .pdf import to_markdown
from .resume import fact_check as resume_fact_check
from .resume import generator as resume_generator
from .resume import skill_loader

app = typer.Typer(add_completion=False, help="Korgi — cute AI TAs giving you lectures")

VALID_LANGS = {"ja", "en"}


def _require_lang(lang: str) -> None:
    if lang not in VALID_LANGS:
        raise typer.BadParameter(f"--lang must be one of {sorted(VALID_LANGS)}")


# ──────────────────────────────────────────────
# Stage 1
# ──────────────────────────────────────────────

@app.command()
def resume(
    paper: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    lang: Annotated[str, typer.Option(help="ja or en")] = "ja",
    minutes: Annotated[int, typer.Option(help="Target lecture length in minutes")] = 45,
    out: Annotated[Path, typer.Option(help="Output root directory")] = Path("out"),
) -> None:
    """Stage 1: PDF → レジュメ (Markdown)."""
    _require_lang(lang)
    run = prepare(out, paper)
    typer.echo(f"[korgi] run dir: {run}")

    typer.echo("[korgi] converting PDF → markdown (markitdown)…")
    paper_md_path = to_markdown.convert(paper, run)
    paper_md = paper_md_path.read_text(encoding="utf-8")
    typer.echo(f"[korgi]   paper.md  ({len(paper_md):,} chars)")

    typer.echo(f"[korgi] generating レジュメ (lang={lang}, {minutes} min)…")
    resume_md = resume_generator.generate(paper_md, lang, minutes)  # type: ignore[arg-type]
    resume_path = run / "resume.md"
    resume_path.write_text(resume_md, encoding="utf-8")
    typer.echo(f"[korgi]   resume.md  ({len(resume_md):,} chars)")

    typer.echo("[korgi] fact-checking レジュメ (Haiku)…")
    flags = resume_fact_check.verify(resume_md, paper_md)
    flags_path = run / "resume.flags.json"
    flags_path.write_text(resume_fact_check.dump_flags(flags), encoding="utf-8")
    if flags:
        typer.echo(f"[korgi]   ⚠ {len(flags)} unsupported claim(s) — see resume.flags.json")
    else:
        typer.echo("[korgi]   ✓ no unsupported claims")


# ──────────────────────────────────────────────
# Stage 2
# ──────────────────────────────────────────────

@app.command()
def speech(
    resume_path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True,
                                                 metavar="RESUME_MD")],
    paper: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True,
                                        help="Original paper PDF (for fact-check context)")],
    lang: Annotated[str, typer.Option(help="ja or en")] = "ja",
    minutes: Annotated[int, typer.Option(help="Target lecture length in minutes")] = 45,
    character: Annotated[str, typer.Option(help="Character name (default_ja/default_en) or path to .yaml")] = "",
    out: Annotated[Path, typer.Option(help="Output root directory")] = Path("out"),
    skip_factcheck: Annotated[bool, typer.Option(help="Skip Stage 2b web-search fact-check")] = False,
) -> None:
    """Stage 2: レジュメ → speech draft → fact-check → emotion tags."""
    _require_lang(lang)

    from .characters import loader as char_loader
    from .speech import draft, fact_check as speech_fc, tags

    char_name = character or f"default_{lang}"
    char = char_loader.load(char_name)

    run = prepare(out, paper)
    typer.echo(f"[korgi] run dir: {run}")

    paper_md_path = to_markdown.convert(paper, run)
    paper_md = paper_md_path.read_text(encoding="utf-8")
    resume_md = resume_path.read_text(encoding="utf-8")

    typer.echo(f"[korgi] 2a: generating speech draft (char={char.name}, {minutes} min)…")
    speech_plain = draft.generate(resume_md, paper_md, char, lang, minutes)  # type: ignore[arg-type]
    (run / "speech_draft.md").write_text(speech_plain, encoding="utf-8")
    typer.echo(f"[korgi]   speech_draft.md  ({len(speech_plain):,} chars)")

    if not skip_factcheck:
        typer.echo("[korgi] 2b: fact-checking additions (Haiku + web_search)…")
        annotated, fc_flags = speech_fc.annotate_citations(speech_plain, paper_md)
        fc_path = run / "speech.flags.json"
        fc_path.write_text(speech_fc.dump_flags(fc_flags), encoding="utf-8")
        if fc_flags:
            typer.echo(f"[korgi]   ⚠ {len(fc_flags)} unverifiable claim(s) — see speech.flags.json")
        else:
            typer.echo("[korgi]   ✓ all novel claims verified")
        speech_plain = annotated

    typer.echo("[korgi] 2c: injecting emotion tags…")
    tagged = tags.inject(speech_plain, char)
    speech_out = run / "speech.md"
    speech_out.write_text(tagged, encoding="utf-8")
    typer.echo(f"[korgi]   speech.md  ({len(tagged):,} chars)")


@app.command()
def tts(
    speech_md: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True,
                                               metavar="SPEECH_MD")],
    provider: Annotated[str, typer.Option(help="TTS provider: elevenlabs | moss | stub")] = "elevenlabs",
    voice: Annotated[str, typer.Option(help="Voice ID (or path to reference .wav for MOSS)")] = "",
    lang: Annotated[str, typer.Option(help="ja or en")] = "ja",
    out: Annotated[Path, typer.Option(help="Output root directory (audio/ written here)")] = Path("out"),
) -> None:
    """Stage 2d: speech.md → audio via the chosen TTS provider."""
    _require_lang(lang)

    from .tts import registry

    adapter = registry.get(provider)
    text = speech_md.read_text(encoding="utf-8")
    audio_dir = Path(out) / "audio" / provider

    typer.echo(f"[korgi] synthesising via {provider} (voice={voice or 'default'})…")
    resolved_voice = voice or adapter.default_voices.get(lang, "")
    result = adapter.synth(text, resolved_voice, lang, audio_dir)  # type: ignore[arg-type]
    typer.echo(f"[korgi]   audio: {result.audio_path}  ({result.duration_ms / 1000:.1f}s)")
    typer.echo(f"[korgi]   timing: {result.timing_path}")


@app.command()
def pipeline(
    paper: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    lang: Annotated[str, typer.Option(help="ja or en")] = "ja",
    minutes: Annotated[int, typer.Option(help="Target lecture length in minutes")] = 45,
    character: Annotated[str, typer.Option(help="Character name or path to .yaml")] = "",
    provider: Annotated[str, typer.Option(help="TTS provider")] = "elevenlabs",
    voice: Annotated[str, typer.Option(help="Voice ID / reference wav")] = "",
    out: Annotated[Path, typer.Option(help="Output root directory")] = Path("out"),
    skip_factcheck: Annotated[bool, typer.Option(help="Skip Stage 2b fact-check (faster)")] = False,
) -> None:
    """Run the full Stage 1 + 2 pipeline end-to-end."""
    _require_lang(lang)
    typer.echo("[korgi] === Stage 1: レジュメ ===")
    ctx = typer.get_current_context()

    from .characters import loader as char_loader
    from .speech import draft, fact_check as speech_fc, tags
    from .tts import registry

    char_name = character or f"default_{lang}"
    char = char_loader.load(char_name)
    run = prepare(out, paper)
    typer.echo(f"[korgi] run dir: {run}")

    # Stage 1
    paper_md_path = to_markdown.convert(paper, run)
    paper_md = paper_md_path.read_text(encoding="utf-8")

    resume_md = resume_generator.generate(paper_md, lang, minutes)  # type: ignore[arg-type]
    (run / "resume.md").write_text(resume_md, encoding="utf-8")
    flags = resume_fact_check.verify(resume_md, paper_md)
    (run / "resume.flags.json").write_text(resume_fact_check.dump_flags(flags), encoding="utf-8")
    typer.echo(f"[korgi] resume.md  ({len(resume_md):,} chars)  flags={len(flags)}")

    # Stage 2
    typer.echo("[korgi] === Stage 2: スピーチ ===")
    speech_plain = draft.generate(resume_md, paper_md, char, lang, minutes)  # type: ignore[arg-type]
    if not skip_factcheck:
        speech_plain, fc_flags = speech_fc.annotate_citations(speech_plain, paper_md)
        (run / "speech.flags.json").write_text(speech_fc.dump_flags(fc_flags), encoding="utf-8")
        typer.echo(f"[korgi] fact-check flags={len(fc_flags)}")
    tagged = tags.inject(speech_plain, char)
    speech_path = run / "speech.md"
    speech_path.write_text(tagged, encoding="utf-8")
    typer.echo(f"[korgi] speech.md  ({len(tagged):,} chars)")

    # TTS
    typer.echo(f"[korgi] === Stage 2d: TTS ({provider}) ===")
    adapter = registry.get(provider)
    audio_dir = run / "audio" / provider
    resolved_voice = voice or adapter.default_voices.get(lang, "")
    result = adapter.synth(tagged, resolved_voice, lang, audio_dir)  # type: ignore[arg-type]
    typer.echo(f"[korgi] audio: {result.audio_path}  ({result.duration_ms / 1000:.1f}s)")


# ──────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────

@app.command("init-skills")
def init_skills(force: Annotated[bool, typer.Option(help="Overwrite if present")] = False) -> None:
    """Install the resume-maker skill into ~/.claude/skills/ if missing."""
    target = skill_loader.SKILL_PATH
    if target.exists() and not force:
        typer.echo(f"[korgi] skill already at {target}. Use --force to overwrite.")
        raise typer.Exit(0)

    source_repo = Path(__file__).parent.parent / "skills" / "resume-maker"
    if not source_repo.exists():
        typer.echo(
            "[korgi] No in-repo skills/ snapshot. "
            "The canonical skill lives at ~/.claude/skills/resume-maker/; "
            "create it by hand or restore from your skills backup."
        )
        raise typer.Exit(1)

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_repo, target.parent, dirs_exist_ok=True)
    typer.echo(f"[korgi] installed skill to {target.parent}")


if __name__ == "__main__":
    app()
