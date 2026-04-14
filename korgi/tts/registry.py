from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import TTSAdapter

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Class decorator to register a TTSAdapter under its `name` attribute."""
    _REGISTRY[cls.name] = cls
    return cls


def get(name: str) -> "TTSAdapter":
    if name not in _REGISTRY:
        _ensure_defaults_loaded()
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown TTS provider '{name}'. Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]()


def available() -> list[str]:
    _ensure_defaults_loaded()
    return sorted(_REGISTRY)


def _ensure_defaults_loaded() -> None:
    # Import adapter modules so their @register decorators run.
    from . import elevenlabs_v3, moss_tts_nano, stub  # noqa: F401
