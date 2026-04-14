from types import SimpleNamespace
from unittest.mock import MagicMock

from korgi.characters.loader import load as load_char
from korgi.config import Config
from korgi.speech import draft
from korgi.speech.schema import JA_CHARS_PER_MIN, EN_WORDS_PER_MIN


def _fake_response(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


def _make_mock_client(captured: dict):
    mock = MagicMock()
    mock.messages.create = lambda **kw: (captured.update(kw), _fake_response("## 概要\n\n本文です。"))[1]
    return mock


def test_draft_prompt_contains_character_and_paper(monkeypatch):
    captured = {}
    monkeypatch.setattr(draft, "client", lambda cfg: _make_mock_client(captured))

    char = load_char("default_ja")
    cfg = Config(anthropic_api_key="x", elevenlabs_api_key=None)
    result = draft.generate("RESUME", "PAPER", char, "ja", 45, cfg=cfg)

    assert result.startswith("## 概要")
    user_blocks = captured["messages"][0]["content"]
    full_text = "".join(b.get("text", "") if isinstance(b, dict) else "" for b in user_blocks)
    assert "PAPER" in full_text
    assert "RESUME" in full_text
    assert char.name in full_text or "センセイ" in full_text
    assert "45" in full_text


def test_draft_length_target_ja(monkeypatch):
    captured = {}
    monkeypatch.setattr(draft, "client", lambda cfg: _make_mock_client(captured))

    char = load_char("default_ja")
    cfg = Config(anthropic_api_key="x", elevenlabs_api_key=None)
    draft.generate("R", "P", char, "ja", 30, cfg=cfg)

    user_blocks = captured["messages"][0]["content"]
    full_text = "".join(b.get("text", "") if isinstance(b, dict) else "" for b in user_blocks)
    assert str(30 * JA_CHARS_PER_MIN) in full_text


def test_draft_length_target_en(monkeypatch):
    captured = {}
    monkeypatch.setattr(draft, "client", lambda cfg: _make_mock_client(captured))

    char = load_char("default_en")
    cfg = Config(anthropic_api_key="x", elevenlabs_api_key=None)
    draft.generate("R", "P", char, "en", 60, cfg=cfg)

    user_blocks = captured["messages"][0]["content"]
    full_text = "".join(b.get("text", "") if isinstance(b, dict) else "" for b in user_blocks)
    assert str(60 * EN_WORDS_PER_MIN) in full_text


def test_paper_block_has_cache_control(monkeypatch):
    captured = {}
    monkeypatch.setattr(draft, "client", lambda cfg: _make_mock_client(captured))

    char = load_char("default_ja")
    cfg = Config(anthropic_api_key="x", elevenlabs_api_key=None)
    draft.generate("RESUME", "PAPER", char, "ja", 45, cfg=cfg)

    paper_block = captured["messages"][0]["content"][0]
    assert paper_block.get("cache_control") == {"type": "ephemeral"}
