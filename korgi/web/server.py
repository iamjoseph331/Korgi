"""FastAPI backend for the Stage 3 Live2D frontend.

Two modes, same app:
1. Classic: `korgi serve <run-dir>` pre-loads a completed run.
2. Empty-start: `korgi serve` (no arg) boots with no run active; the
   frontend's setup page uploads a PDF to `POST /api/run`, which drives
   the pipeline in a background thread and streams progress over
   `GET /api/runs/{id}/events` (SSE). On completion the server's active
   run dir is swapped to the new run, so the existing `/run/*` routes
   pick it up with no restart.
"""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..characters import loader as char_loader
from ..characters.schema import CharacterProfile
from ..pipeline import run_pipeline

WEB_ROOT = Path(__file__).parent.parent.parent / "web"
DIST_DIR = WEB_ROOT / "dist"
UPLOAD_DIR = Path("uploads")
PROVIDER_PRIORITY = ("elevenlabs", "moss", "stub")


# ──────────────────────────────────────────────────────────
# State
# ──────────────────────────────────────────────────────────

@dataclass
class RunState:
    """One pipeline invocation. Events accumulate; SSE replays them."""
    run_id: str
    events: list[dict] = field(default_factory=list)
    cond: threading.Condition = field(default_factory=threading.Condition)
    done: bool = False
    error: Optional[str] = None
    run_dir: Optional[Path] = None

    def emit(self, kind: str, message: str, payload: Optional[dict] = None) -> None:
        with self.cond:
            self.events.append(
                {"kind": kind, "message": message, "payload": payload or {}}
            )
            if kind in ("done", "error"):
                self.done = True
            self.cond.notify_all()

    def follow(self):
        """Sync generator: yields events as they arrive, stops when done."""
        idx = 0
        while True:
            with self.cond:
                while idx >= len(self.events) and not self.done:
                    self.cond.wait()
                new = self.events[idx:]
                idx = len(self.events)
                finished = self.done and idx >= len(self.events)
            for event in new:
                yield event
            if finished:
                return


@dataclass
class AppState:
    run_dir: Optional[Path] = None
    runs: dict[str, RunState] = field(default_factory=dict)


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _character_json(profile: CharacterProfile) -> dict:
    return {
        "name": profile.name,
        "lang": profile.lang,
        "live2d_expression_map": dict(profile.live2d_expression_map),
        "live2d": {
            "model_path": profile.live2d.model_path,
            "scale": profile.live2d.scale,
            "x_offset": profile.live2d.x_offset,
            "y_offset": profile.live2d.y_offset,
            "lip_sync": asdict(profile.live2d.lip_sync),
        },
    }


def _pick_audio_dir(run_dir: Path) -> Optional[Path]:
    audio_root = run_dir / "audio"
    if not audio_root.is_dir():
        return None
    for provider in PROVIDER_PRIORITY:
        candidate = audio_root / provider
        if (candidate / "full.wav").exists():
            return candidate
    for sub in audio_root.iterdir():
        if (sub / "full.wav").exists():
            return sub
    return None


def _guess_lang(run_dir: Path) -> str:
    speech_path = run_dir / "speech.md"
    if speech_path.exists():
        head = speech_path.read_text(encoding="utf-8")[:2000]
        if head.isascii():
            return "en"
    return "ja"


# ──────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────

def create_app(run_dir: Optional[Path] = None, character: Optional[str] = None):
    state = AppState(run_dir=Path(run_dir).resolve() if run_dir else None)
    override_character = character

    app = FastAPI(title="korgi")

    # ── misc ─────────────────────────────────────────────
    @app.get("/favicon.ico", include_in_schema=False)
    def _favicon():
        return Response(status_code=204)

    @app.get("/.well-known/{rest:path}", include_in_schema=False)
    def _well_known():
        return Response(status_code=204)

    # ── read-side (/run/*) — re-derive paths from current state per call ─

    def _require_run() -> Path:
        if state.run_dir is None or not state.run_dir.is_dir():
            raise HTTPException(404, "no run active yet — upload a PDF first")
        return state.run_dir

    def _current_profile(run: Path) -> CharacterProfile:
        name = override_character or f"default_{_guess_lang(run)}"
        return char_loader.load(name)

    @app.get("/run/info.json")
    def info() -> JSONResponse:
        if state.run_dir is None or not state.run_dir.is_dir():
            return JSONResponse({"active": False})
        run = state.run_dir
        profile = _current_profile(run)
        audio_dir = _pick_audio_dir(run)
        slides_json = run / "slides.json"
        if audio_dir is not None:
            slides_json = audio_dir / "slides.json"
        return JSONResponse(
            {
                "active": True,
                "slug": run.name,
                "lang": profile.lang,
                "character": profile.name,
                "has_audio": audio_dir is not None,
                "has_slides": slides_json.exists(),
                "audio_url": "/run/audio/full.wav" if audio_dir else None,
            }
        )

    @app.get("/run/character.json")
    def character_json() -> JSONResponse:
        run = _require_run()
        return JSONResponse(_character_json(_current_profile(run)))

    @app.get("/run/speech.md")
    def speech() -> FileResponse:
        run = _require_run()
        p = run / "speech.md"
        if not p.exists():
            raise HTTPException(404, "speech.md not generated yet")
        return FileResponse(p, media_type="text/markdown; charset=utf-8")

    @app.get("/run/timing.json")
    def timing() -> FileResponse:
        run = _require_run()
        audio_dir = _pick_audio_dir(run)
        if audio_dir is None or not (audio_dir / "timing.json").exists():
            raise HTTPException(404, "timing.json not generated yet")
        return FileResponse(audio_dir / "timing.json", media_type="application/json")

    @app.get("/run/audio/full.wav")
    def audio() -> FileResponse:
        run = _require_run()
        audio_dir = _pick_audio_dir(run)
        if audio_dir is None:
            raise HTTPException(404, "audio not generated yet")
        return FileResponse(audio_dir / "full.wav", media_type="audio/wav")

    @app.get("/run/slides.json")
    def slides_json_route() -> FileResponse:
        run = _require_run()
        audio_dir = _pick_audio_dir(run)
        for candidate in (
            audio_dir / "slides.json" if audio_dir else None,
            run / "slides.json",
        ):
            if candidate is not None and candidate.exists():
                return FileResponse(candidate, media_type="application/json")
        raise HTTPException(404, "slides.json not generated yet")

    @app.get("/run/slides/slides.md")
    def slides_md() -> FileResponse:
        run = _require_run()
        p = run / "slides" / "slides.md"
        if not p.exists():
            raise HTTPException(404, "slides.md not generated yet")
        return FileResponse(p, media_type="text/markdown; charset=utf-8")

    @app.get("/run/slides/slides.html")
    def slides_html() -> FileResponse:
        run = _require_run()
        p = run / "slides" / "slides.html"
        if not p.exists():
            raise HTTPException(404, "slides.html not rendered (marp-cli missing?)")
        return FileResponse(p, media_type="text/html")

    # ── write-side (/api/*) ──────────────────────────────

    @app.get("/api/characters")
    def api_characters() -> JSONResponse:
        names = sorted(p.stem for p in char_loader.CHAR_DIR.glob("*.yaml"))
        return JSONResponse({"characters": names})

    @app.get("/api/characters/{name}")
    def api_character_yaml(name: str) -> Response:
        # Return the raw YAML text so the setup page can prefill the editor.
        # Reject path traversal: only accept built-in stems.
        if "/" in name or ".." in name:
            raise HTTPException(400, "invalid character name")
        p = char_loader.CHAR_DIR / f"{name}.yaml"
        if not p.exists():
            raise HTTPException(404, f"character '{name}' not found")
        return Response(p.read_text(encoding="utf-8"), media_type="text/yaml; charset=utf-8")

    @app.get("/api/providers")
    def api_providers() -> JSONResponse:
        from ..tts import registry
        return JSONResponse({"providers": registry.available()})

    @app.get("/api/runs")
    def api_runs() -> JSONResponse:
        return JSONResponse(
            {
                "active_run_dir": str(state.run_dir) if state.run_dir else None,
                "runs": {
                    rid: {
                        "done": rs.done,
                        "error": rs.error,
                        "run_dir": str(rs.run_dir) if rs.run_dir else None,
                        "events": len(rs.events),
                    }
                    for rid, rs in state.runs.items()
                },
            }
        )

    @app.post("/api/run")
    async def api_create_run(
        pdf: UploadFile = File(...),
        lang: str = Form("ja"),
        minutes: int = Form(45),
        character: str = Form(""),
        provider: str = Form("elevenlabs"),
        voice: str = Form(""),
        skip_factcheck: bool = Form(False),
        slides: bool = Form(True),
        pitch: int = Form(0),
        speed: float = Form(1.0),
        character_yaml: str = Form(""),
    ) -> JSONResponse:
        if lang not in ("ja", "en"):
            raise HTTPException(400, "lang must be 'ja' or 'en'")
        if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "expected a .pdf upload")

        run_id = uuid.uuid4().hex[:10]
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        pdf_path = UPLOAD_DIR / f"{run_id}_{Path(pdf.filename).name}"
        pdf_path.write_bytes(await pdf.read())

        # If the user edited the character YAML inline, validate it and
        # persist alongside the upload. We pass its path (not name) to the
        # pipeline — char_loader.load() accepts either.
        character_arg = character
        if character_yaml.strip():
            custom_path = UPLOAD_DIR / f"character_{run_id}.yaml"
            custom_path.write_text(character_yaml, encoding="utf-8")
            try:
                char_loader.load(str(custom_path))
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(400, f"invalid character YAML: {exc}") from exc
            character_arg = str(custom_path)

        voice_settings = {"pitch": int(pitch), "speed": float(speed)}

        rs = RunState(run_id=run_id)
        state.runs[run_id] = rs

        def worker() -> None:
            try:
                result_run = run_pipeline(
                    paper=pdf_path,
                    lang=lang,
                    minutes=minutes,
                    character=character_arg,
                    provider=provider,
                    voice=voice,
                    voice_settings=voice_settings,
                    out=Path("out"),
                    skip_factcheck=skip_factcheck,
                    slides=slides,
                    on_event=rs.emit,
                )
                rs.run_dir = result_run
                state.run_dir = result_run  # atomic swap for /run/* routes
            except Exception as exc:  # noqa: BLE001
                rs.error = f"{type(exc).__name__}: {exc}"
                rs.emit("error", rs.error, {"type": type(exc).__name__})

        threading.Thread(target=worker, daemon=True, name=f"korgi-run-{run_id}").start()
        return JSONResponse({"run_id": run_id})

    @app.get("/api/runs/{run_id}/events")
    async def api_run_events(run_id: str):
        rs = state.runs.get(run_id)
        if rs is None:
            raise HTTPException(404, f"unknown run_id {run_id}")

        async def gen():
            loop = asyncio.get_running_loop()
            it = iter(rs.follow())
            while True:
                event = await loop.run_in_executor(None, next, it, None)
                if event is None:
                    break
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── static bundle last (catches /) ───────────────────
    if DIST_DIR.exists():
        app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="dist")

    return app


def serve(
    run_dir: Optional[Path] = None,
    port: int = 8000,
    host: str = "127.0.0.1",
    character: Optional[str] = None,
) -> None:
    import uvicorn

    app = create_app(run_dir, character=character)
    uvicorn.run(app, host=host, port=port, log_level="info")
