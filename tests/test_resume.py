from types import SimpleNamespace
from unittest.mock import MagicMock

from korgi.config import Config
from korgi.resume import generator


def _fake_response(text: str) -> MagicMock:
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


def test_generator_sends_paper_with_cache_control(monkeypatch):
    captured = {}

    def fake_client(cfg):
        c = MagicMock()
        c.messages.create = lambda **kw: (captured.update(kw), _fake_response("# R\n\n本文"))[1]
        return c

    monkeypatch.setattr(generator, "client", fake_client)
    monkeypatch.setattr(generator.skill_loader, "load", lambda: "SKILL PROMPT")

    cfg = Config(anthropic_api_key="x", elevenlabs_api_key=None)
    out = generator.generate("PAPER BODY", "ja", 45, cfg=cfg)

    assert out.startswith("# R")
    assert captured["model"] == cfg.generation_model
    assert "SKILL PROMPT" in captured["system"]
    assert "Japanese" in captured["system"]
    assert "45 minutes" in captured["system"]
    user_blocks = captured["messages"][0]["content"]
    assert user_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "PAPER BODY" in user_blocks[0]["text"]
    assert "<lang>ja</lang>" in user_blocks[1]["text"]


def test_skill_loader_strips_frontmatter():
    from korgi.resume import skill_loader

    body = skill_loader._strip_frontmatter(
        "---\nname: x\ndescription: y\n---\n\n# Role\n\nBody here.\n"
    )
    assert body.startswith("# Role")
    assert "name: x" not in body
