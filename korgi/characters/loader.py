from __future__ import annotations

from pathlib import Path

import yaml

from .schema import CharacterProfile, SpeechStyle

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
    )
