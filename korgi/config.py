import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    elevenlabs_api_key: str | None
    generation_model: str = "claude-opus-4-6"
    factcheck_model: str = "claude-haiku-4-5"
    web_search_cap: int = 8


def load() -> Config:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Export it in your shell or put it in a .env."
        )
    return Config(
        anthropic_api_key=key,
        elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY"),
        generation_model=os.environ.get("KORGI_GEN_MODEL", "claude-opus-4-6"),
        factcheck_model=os.environ.get("KORGI_FC_MODEL", "claude-haiku-4-5"),
    )
