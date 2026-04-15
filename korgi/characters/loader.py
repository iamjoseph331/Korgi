from __future__ import annotations

from pathlib import Path

import yaml

from .schema import CharacterProfile, LipSyncSettings, Live2DSettings, SpeechStyle

CHAR_DIR = Path(__file__).parent


def load(name_or_path: str) -> CharacterProfile:
    """Load a character profile by short name (e.g. 'default_ja') or YAML path."""
    candidate = Path(name_or_path)
    if not candidate.exists():
        candidate = CHAR_DIR / f"{name_or_path}.yaml"
    if not candidate.exists():
        available = sorted(p.stem for p in CHAR_DIR.glob("*.yaml"))
        raise FileNotFoundError(
            f"Character '{name_or_path}' not found. "
            f"Built-ins: {available}. Or pass a full path to a .yaml file."
        )

    data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    ss = data.get("speech_style", {})

    l2d_raw = data.get("live2d", {}) or {}
    ls_raw = l2d_raw.get("lip_sync", {}) or {}
    defaults = Live2DSettings()
    default_ls = defaults.lip_sync
    live2d = Live2DSettings(
        model_path=l2d_raw.get("model_path", defaults.model_path),
        scale=float(l2d_raw.get("scale", defaults.scale)),
        x_offset=float(l2d_raw.get("x_offset", defaults.x_offset)),
        y_offset=float(l2d_raw.get("y_offset", defaults.y_offset)),
        lip_sync=LipSyncSettings(
            sensitivity=float(ls_raw.get("sensitivity", default_ls.sensitivity)),
            smoothing=float(ls_raw.get("smoothing", default_ls.smoothing)),
            min_threshold=float(ls_raw.get("min_threshold", default_ls.min_threshold)),
            use_mouth_form=bool(ls_raw.get("use_mouth_form", default_ls.use_mouth_form)),
        ),
    )

    return CharacterProfile(
        name=data["name"],
        lang=data["lang"],
        persona=data["persona"].strip(),
        speech_style=SpeechStyle(
            formality=ss.get("formality", ""),
            pace=ss.get("pace", ""),
            sentence_length=ss.get("sentence_length", ""),
            verbal_tics=tuple(ss.get("verbal_tics", []) or []),
            avoid=tuple(ss.get("avoid", []) or []),
        ),
        energy=float(data.get("energy", 0.5)),
        humor=data.get("humor", "low"),
        catchphrases=tuple(data.get("catchphrases", []) or []),
        tag_bias=dict(data.get("tag_bias", {}) or {}),
        live2d_expression_map=dict(data.get("live2d_expression_map", {}) or {}),
        live2d=live2d,
    )
