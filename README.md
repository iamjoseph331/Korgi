# Korgi

Cute AI TAs giving you lectures — a pipeline that turns an academic PDF into a voiced lecture with a Live2D presenter.

```
PDF ──► resume.md ──► speech.md ──► audio + slides ──► Live2D web viewer
      Stage 1        Stage 2        Stage 2d / 4        Stage 3
```

---

## Install

```bash
pip install -e .                        # core (Claude only, stub TTS)
pip install -e '.[elevenlabs]'          # + ElevenLabs TTS
pip install -e '.[moss]'                # + MOSS-TTS-Nano (CPU, offline)
pip install -e '.[web]'                 # + web server (FastAPI)
pip install -e '.[elevenlabs,web,dev]'  # everything + tests
```

**Required env vars:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export ELEVENLABS_API_KEY=...          # only if using ElevenLabs
```

**Optional model overrides:**

```bash
export KORGI_GEN_MODEL=claude-opus-4-6    # default: claude-opus-4-6
export KORGI_FC_MODEL=claude-haiku-4-5   # default: claude-haiku-4-5
```

---

## Running the pipeline

### Full pipeline (recommended)

Runs Stage 1 → Stage 2 → Stage 4 (slides) → TTS in one command.

```bash
korgi pipeline paper.pdf
```

```bash
# Japanese lecture, 30 min, ElevenLabs TTS
korgi pipeline paper.pdf --lang ja --minutes 30 --provider elevenlabs

# English lecture, offline TTS, skip fact-check (faster)
korgi pipeline paper.pdf --lang en --provider moss --skip-factcheck

# No slides
korgi pipeline paper.pdf --no-slides

# Custom character
korgi pipeline paper.pdf --character ./my_char.yaml

# Custom output directory
korgi pipeline paper.pdf --out ./runs
```

Output lands in `out/<paper-slug>/`:

```
out/Mindware1/
├── paper.md            # PDF → Markdown
├── resume.md           # Stage 1: lecture handout
├── resume.flags.json   # fact-check flags
├── speech.md           # Stage 2: voiced script with emotion + slide tags
├── speech.flags.json   # speech fact-check flags
├── slides/
│   └── slides.md       # Marp slides
└── audio/
    └── elevenlabs/
        ├── speech.wav
        └── timing.json
```

---

### Step-by-step commands

Run stages individually if you want to inspect or edit intermediate files.

#### Stage 1 — PDF → resume

```bash
korgi resume paper.pdf
korgi resume paper.pdf --lang en --minutes 60 --out ./runs
```

Produces `resume.md` and `resume.flags.json` in the run dir.

#### Stage 2 — resume → speech

```bash
korgi speech out/Mindware1/resume.md --paper paper.pdf
korgi speech out/Mindware1/resume.md --paper paper.pdf --lang en --character default_en
korgi speech out/Mindware1/resume.md --paper paper.pdf --skip-factcheck
```

Produces `speech_draft.md`, `speech.md`, and `speech.flags.json`.

#### Stage 2d — speech → audio

```bash
# ElevenLabs (cloud)
korgi tts out/Mindware1/speech.md --provider elevenlabs

# MOSS-TTS-Nano (local, CPU)
korgi tts out/Mindware1/speech.md --provider moss

# Stub (silent, for testing)
korgi tts out/Mindware1/speech.md --provider stub

# Custom voice
korgi tts out/Mindware1/speech.md --provider elevenlabs --voice <voice-id>
korgi tts out/Mindware1/speech.md --provider moss --voice ./ref.wav
```

#### Stage 4 — slides

```bash
korgi slides out/Mindware1/speech.md --resume-md out/Mindware1/resume.md
korgi slides out/Mindware1/speech.md --resume-md out/Mindware1/resume.md --lang en
```

Produces `slides/slides.md` (and `slides.html` if `marp-cli` is installed).

#### Stage 3 — web viewer

```bash
# Empty viewer — upload a PDF from the browser
korgi serve

# Pre-load a finished run
korgi serve out/Mindware1

# Build the web bundle first (first run only)
korgi serve out/Mindware1 --build

# Custom port / host
korgi serve out/Mindware1 --port 9000 --host 0.0.0.0
```

Open `http://127.0.0.1:8000` in your browser.

---

## Characters

Built-in characters: `default_ja`, `default_en`.

```bash
# List available characters
ls korgi/characters/*.yaml

# Use a built-in
korgi pipeline paper.pdf --character default_en

# Use a custom YAML
korgi pipeline paper.pdf --character ./my_char.yaml
```

A character YAML controls persona, speech style, emotion tag biases, and the Live2D model path. Copy `korgi/characters/default_ja.yaml` as a starting point.

---

## TTS providers

| Provider | Flag | Notes |
|----------|------|-------|
| `elevenlabs` | `pip install 'korgi[elevenlabs]'` | Cloud, emotion tags, streaming |
| `moss` | `pip install 'korgi[moss]'` | Local CPU, voice cloning via ref wav, tags stripped |
| `stub` | built-in | Silent, writes placeholder files — useful for testing |

---

## Development

```bash
pip install -e '.[dev]'
pytest
```
