# Korgi

Cute AI TAs giving you lectures — a pipeline that turns an academic PDF into a voiced lecture with a Live2D presenter.

```
PDF ──► resume.md ──► speech.md ──► audio + slides ──► Live2D web viewer
      Stage 1        Stage 2        Stage 2d / 4        Stage 3
```

---

## Demo

<!-- Populate this section with a video or screenshots. -->

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
        ├── full.wav
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

You can also edit the character directly in the web UI — open the **キャラクターを編集** panel on the setup page. Changes apply to that run only and do not overwrite the original file.

---

## Adding your own Live2D model

Korgi works with any Cubism 4 model (`.model3.json` + assets). The steps below assume the bundled web viewer.

### 1. Copy the model files

Place the model directory under `web/public/live2d/` so Vite serves it in development and includes it in the production build:

```
web/public/live2d/
└── my_model/
    └── runtime/
        ├── my_model.model3.json
        ├── my_model.moc3
        ├── textures/
        └── motions/
```

### 2. Create a character YAML

Copy an existing character as a template:

```bash
cp korgi/characters/default_ja.yaml korgi/characters/my_char.yaml
```

Then edit the `live2d` section to point to your model:

```yaml
live2d:
  model_path: /live2d/my_model/runtime/my_model.model3.json
  scale: 0.25          # start here; increase if the model appears too small
  x_offset: 0          # pixels right (negative = left)
  y_offset: 0          # pixels down  (negative = up)
  lip_sync:
    sensitivity: 2.0   # higher = more mouth movement for quiet audio
    smoothing: 0.15    # 0 = instant, 1 = very slow
    min_threshold: 0.01
    use_mouth_form: true
```

### 3. Map emotion tags to your model's motions / expressions

Korgi uses six canonical emotion tags: `happy`, `sad`, `angry`, `thinking`, `hesitate`, `serious`. These need to map to motion groups or expression names defined in your `.model3.json`.

Open the `.model3.json` and look for keys under `"Motions"` or `"Expressions"`. Then set `live2d_expression_map` in your character YAML:

```yaml
live2d_expression_map:
  happy:    Tap          # motion group name, or an expression name
  thinking: Idle
  hesitate: FlickDown
  sad:      FlickDown
  angry:    FlickUp
  serious:  Idle
```

If your model has named `.exp3.json` expressions, use those names instead of motion group names — the frontend driver tries expressions first, then falls back to motion groups.

### 4. Adjust the zoom origin (optional)

The zoom slider on the player page zooms in toward the upper body. If your model's face lands off-center at high zoom, tweak `y_offset` in the YAML or use the web UI's **キャラクターを編集** panel to try values live.

### 5. Use the character

```bash
korgi pipeline paper.pdf --character my_char
korgi serve out/<run>
```

Or select it from the **キャラクター** dropdown on the web setup page.

---

## TTS providers

| Provider       | Install                                                                | Notes                                                      |
| -------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------- |
| `elevenlabs` | `pip install 'korgi[elevenlabs]'`                                    | Cloud, emotion tags, streaming; supports `speed` setting |
| `moss`       | `pip install 'korgi[moss]'`                                          | Local CPU, voice cloning via ref wav, tags stripped        |
| `stub`       | built-in                                                               | Silent, writes placeholder files — useful for testing     |
| `voxcpm`     | `pip install "git+https://github.com/OpenBMB/VoxCPM.git" numpy`      | Local, experimental; tags stripped                         |
| `irodori`    | `pip install "git+https://github.com/Aratako/Irodori-TTS.git" numpy` | Local, Japanese-first, experimental; tags stripped         |

**Pitch and speaking speed** can be set on the web setup page. Only ElevenLabs currently maps these to its API; other providers accept the settings but ignore them (a notice is shown in the UI).

You can also switch providers in the **live player** without re-running the pipeline — the toolbar in the top-right corner of the stage re-synthesises on demand and caches the result for instant replay.

---

## Development

```bash
pip install -e '.[dev]'
pytest
```
