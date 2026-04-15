# Korgi

Tired of reading papers all day? Let a cute AI TA teach them to you instead.

Korgi is a CLI and web app that converts academic papers into lecture-style outputs. It takes a PDF, turns it into Markdown, drafts a lecture handout, writes a spoken script with emotion tags, synthesizes audio, generates Marp slides, and presents the result in a browser-based Live2D viewer.

Korgi originally started as a platform for experimenting with different TTS providers during the recent surge of local text-to-speech tools. It now offers multiple interchangeable TTS backends — including ElevenLabs (API), irodori, VoxCPM, and MOSS-TTM-Nano — making it easy and intuitive to pick the one you like best.

Supports Japanese and English (I think)

Pipeline: 
```text
PDF -> paper.md -> resume.md -> speech.md -> audio + slides -> Live2D web viewer
```

<table>
  <tr>
    <td width="50%">
      <strong>Demo 1: Pipeline (web browser) + Elevenlabs API</strong><br />
      <video src="./Demo/Korgi-demo1.mp4" controls muted playsinline width="100%"></video><br />
      <a href="./Demo/Korgi-demo1.mp4">Open Demo 1</a>
    </td>
    <td width="50%">
      <strong>Demo 2: Irodori voice profiles</strong><br />
      <video src="./Demo/Korgi-demo2.mp4" controls muted playsinline width="100%"></video><br />
      <a href="./Demo/Korgi-demo2.mp4">Open Demo 2</a>
    </td>
  </tr>
</table>

## What Korgi does

- Converts academic PDFs to markdown with `markitdown`
- Generates a lecture handout (`resume.md`)
- Generates a spoken lecture script (`speech.md`)
- Adds emotion tags for delivery control
- Generates slide cues and Marp slide markdown
- Synthesizes audio with multiple TTS backends
- Serves the final result in a FastAPI-based web viewer with a Live2D character

## Demo

<table>
  <tr>
    <td width="50%">
      <strong>Demo 1</strong><br />
      <video src="./Demo/Korgi-demo1.mp4" controls muted playsinline width="100%"></video><br />
      <a href="./Demo/Korgi-demo1.mp4">Open Demo 1</a>
    </td>
    <td width="50%">
      <strong>Demo 2</strong><br />
      <video src="./Demo/Korgi-demo2.mp4" controls muted playsinline width="100%"></video><br />
      <a href="./Demo/Korgi-demo2.mp4">Open Demo 2</a>
    </td>
  </tr>
</table>

## Pipeline

Korgi is organized as stages:

- Stage 1: PDF -> `resume.md`
- Stage 2: `resume.md` -> `speech.md`
- Stage 2d: `speech.md` -> audio
- Stage 4: `speech.md` -> `slides/slides.md`
- Stage 3: web viewer for playback with Live2D

The `pipeline` command runs the main authoring flow end to end:

- Stage 1
- Stage 2
- optional Stage 4
- TTS synthesis

## Install

Core install:

```bash
uv sync
```

Optional extras:

```bash
uv sync --extra elevenlabs
uv sync --extra moss
uv sync --extra voxcpm
uv sync --extra irodori
uv sync --extra web
uv sync --extra elevenlabs --extra web --extra dev
```

Notes:

- `web` installs the FastAPI server dependencies
- `dev` installs test dependencies
- `moss`, `voxcpm`, and `irodori` are mutually conflicting in `uv`, so install one at a time

### Local clone requirements for some TTS backends

`voxcpm` and `irodori` are wired from local editable paths in `pyproject.toml`. Clone them first:

```bash
git clone https://github.com/OpenBMB/VoxCPM.git ../TTS/VoxCPM
git clone https://github.com/Aratako/Irodori-TTS.git ../TTS/Irodori-TTS
```

Then run:

```bash
uv sync --extra voxcpm
uv sync --extra irodori
```

The repo is also configured for a local editable `../TTS/MOSS-TTS-Nano` source when installing `--extra moss`.

## Environment variables

Required:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Optional:

```bash
export ELEVENLABS_API_KEY=...   # only if using ElevenLabs
```

Model overrides:

```bash
export KORGI_GEN_MODEL=claude-opus-4-6
export KORGI_FC_MODEL=claude-haiku-4-5
```

## Quick start

Run the full pipeline:

```bash
python korgi.cli pipeline paper.pdf
```

Examples:

```bash
# Japanese lecture with ElevenLabs
python korgi.cli pipeline paper.pdf --lang ja --minutes 30 --provider elevenlabs

# English lecture with offline TTS
python korgi.cli pipeline paper.pdf --lang en --provider moss --skip-factcheck

# Disable slide generation
python korgi.cli pipeline paper.pdf --no-slides

# Use a custom character YAML
python korgi.cli pipeline paper.pdf --character ./my_char.yaml

# Write outputs under a custom directory
python korgi.cli pipeline paper.pdf --out ./runs
```

## Output structure

Outputs are written to a run directory under `out/<paper-slug>/` by default.

Typical layout:

```text
out/<your_paper>/
├── paper.md
├── resume.md
├── resume.flags.json
├── speech.md
├── speech.flags.json
├── slides/
│   └── slides.md
└── audio/
    └── elevenlabs/
        ├── full.wav
        └── timing.json
```

Depending on the flow you run, you may also see files such as `speech_draft.md`, provider-specific audio outputs, `slides.json`, or `slides.html` when `marp-cli` is available.

## CLI usage

### Full pipeline

```bash
python korgi.cli pipeline paper.pdf
```

### Stage 1: PDF -> resume

```bash
python korgi.cli resume paper.pdf
python korgi.cli resume paper.pdf --lang en --minutes 60 --out ./runs
```

### Stage 2: resume -> speech

```bash
python korgi.cli speech out/<your_paper>/resume.md --paper paper.pdf
python korgi.cli speech out/<your_paper>/resume.md --paper paper.pdf --lang en --character default_en
python korgi.cli speech out/<your_paper>/resume.md --paper paper.pdf --skip-factcheck
```

### Stage 2d: speech -> audio

```bash
# ElevenLabs
python korgi.cli tts out/<your_paper>/speech.md --provider elevenlabs

# MOSS-TTS-Nano
python korgi.cli tts out/<your_paper>/speech.md --provider moss

# Custom voice / reference
python korgi.cli tts out/<your_paper>/speech.md --provider elevenlabs --voice <voice-id>
python korgi.cli tts out/<your_paper>/speech.md --provider moss --voice ./ref.wav
```

### Stage 4: slides

```bash
python korgi.cli slides out/<your_paper>/speech.md --resume-md out/<your_paper>/resume.md
python korgi.cli slides out/<your_paper>/speech.md --resume-md out/<your_paper>/resume.md --lang en
```

### Stage 3: web viewer

```bash
# Start empty and upload a PDF from the browser
python korgi.cli serve

# Pre-load an existing run
python korgi.cli serve out/<your_paper>

# Build the frontend before serving
python korgi.cli serve out/<your_paper> --build

# Custom host / port
python korgi.cli serve out/<your_paper> --port 9000 --host 0.0.0.0
```

Then open:

```text
http://127.0.0.1:8000
```

## Characters

Built-in character names include:

- `default_ja`
- `default_en`

Use one with:

```bash
python korgi.cli pipeline paper.pdf --character default_en
```

Or point to a custom YAML:

```bash
python korgi.cli pipeline paper.pdf --character ./my_char.yaml
```

Character YAML files define:

- persona
- speech style
- tag bias
- Live2D model path
- Live2D expression or motion mapping
- lip sync settings

The web setup screen also lets you edit character YAML for a single run without overwriting the source file.

## Adding your own Live2D model

Korgi works with Cubism 4 `.model3.json` models and their runtime assets.

### 1. Put the model under `web/public`

Use `web/public/live2d/...`, not `web/dist/...`.

Example:

```text
web/public/live2d/
└── my_model/
    └── runtime/
        ├── my_model.model3.json
        ├── my_model.moc3
        ├── textures/
        └── motions/
```

### 2. Create a character YAML

```bash
cp korgi/characters/default_ja.yaml korgi/characters/my_char.yaml
```

Point the character at your model:

```yaml
live2d:
  model_path: /live2d/my_model/runtime/my_model.model3.json
  scale: 0.25
  x_offset: 0
  y_offset: 0
  lip_sync:
    sensitivity: 2.0
    smoothing: 0.15
    min_threshold: 0.01
    use_mouth_form: true
```

### 3. Map canonical emotion tags

Korgi uses these canonical tags:

- `happy`
- `sad`
- `angry`
- `thinking`
- `hesitate`
- `serious`

Map them to expression names or motion groups present in your model:

```yaml
live2d_expression_map:
  happy: Smile
  thinking: Think
  hesitate: Troubled
  sad: Sad
  angry: Angry
  serious: Default
```

The frontend tries expressions first, then falls back to motion groups when possible.

### 4. Use the character

```bash
python korgi.cli pipeline paper.pdf --character my_char
python korgi.cli serve out/<run>
```

## Notes

- `marp-cli` is optional. If it is not installed, the frontend renders slide markdown client-side.
- The web viewer supports starting empty and creating a run from an uploaded PDF.
- The web UI includes character selection, one-run YAML editing, a progress screen, and a Live2D player view.

## License

Korgi is released under the MIT License.

See [LICENSE](./LICENSE) for the full text.
