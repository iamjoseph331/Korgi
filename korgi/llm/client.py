from __future__ import annotations

from functools import lru_cache

from anthropic import Anthropic

from ..config import Config, load


@lru_cache(maxsize=1)
def _client(api_key: str) -> Anthropic:
    return Anthropic(api_key=api_key)


def client(cfg: Config | None = None) -> Anthropic:
    cfg = cfg or load()
    return _client(cfg.anthropic_api_key)
