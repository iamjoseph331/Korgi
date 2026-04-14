from types import SimpleNamespace
from unittest.mock import MagicMock

from korgi.characters.loader import load as load_char
from korgi.config import Config
from korgi.speech import tags

_CFG = Config(anthropic_api_key="x", elevenlabs_api_key=None)


def _fake_response(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


def test_inject_adds_only_canonical_tags(monkeypatch):
    """Tags in the output must all be from TAG_SET; no non-tag text modified."""
    char = load_char("default_ja")
    speech = "これは真剣なセクションです。とても難しい問題ですね。"
    tagged_output = "[serious]これは真剣なセクションです。[thinking]とても難しい問題ですね。"

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _fake_response(tagged_output)
    monkeypatch.setattr(tags, "client", lambda cfg: mock_client)

    result = tags.inject(speech, char, cfg=_CFG)
    assert "[serious]" in result or "[thinking]" in result
    # No unknown tags
    import re
    all_tags = re.findall(r"\[([^\]]+)\]", result)
    from korgi.speech.schema import TAG_SET
    for t in all_tags:
        assert t in TAG_SET, f"unknown tag [{t}] in output"


def test_inject_falls_back_on_text_mutation(monkeypatch):
    """If model changes non-tag text on both attempts, return original speech."""
    char = load_char("default_ja")
    speech = "元のテキストです。"
    mutated = "[happy]書き換えられたテキストです。"

    call_count = {"n": 0}

    def fake_client(cfg):
        c = MagicMock()
        def create(**kw):
            call_count["n"] += 1
            return _fake_response(mutated)
        c.messages.create = create
        return c

    monkeypatch.setattr(tags, "client", fake_client)
    result = tags.inject(speech, char, cfg=_CFG)
    assert result == speech
    assert call_count["n"] == 2  # original attempt + one retry


def test_strip_unknown_tags():
    from korgi.speech.tags import _strip_unknown_tags
    text = "[happy]良い[unknown_tag]テキスト[thinking]考え中"
    out = _strip_unknown_tags(text)
    assert "[unknown_tag]" not in out
    assert "[happy]" in out
    assert "[thinking]" in out
