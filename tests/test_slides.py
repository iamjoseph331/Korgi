from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from korgi.characters.loader import load as load_char
from korgi.config import Config
from korgi.slides.timing import estimate_cues, write_slides_json
from korgi.speech import slide_cues
from korgi.speech.schema import SLIDE_TAG, SLIDE_TAG_RE, strip_slide_tags

_CFG = Config(anthropic_api_key="x", elevenlabs_api_key=None)


def _fake_response(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block])


def test_strip_slide_tags_removes_all():
    text = f"foo {SLIDE_TAG} bar {SLIDE_TAG} baz"
    assert strip_slide_tags(text) == "foo  bar  baz"
    assert SLIDE_TAG_RE.search(strip_slide_tags(text)) is None


def test_estimate_cues_monotonic_and_within_duration():
    speech = (
        "# 講義\n\n## 概要\n" + "あ" * 100 + f"\n{SLIDE_TAG}\n"
        "## 手法\n" + "い" * 200 + f"\n{SLIDE_TAG}\n"
        "## 結果\n" + "う" * 300
    )
    total_ms = 60_000
    cues = estimate_cues(speech, total_ms)
    assert len(cues) == 3  # 2 [slide:next] + implicit slide 0
    assert cues[0].idx == 0 and cues[0].start_ms == 0
    assert cues[0].start_ms < cues[1].start_ms < cues[2].start_ms
    for c in cues:
        assert 0 <= c.start_ms <= total_ms


def test_estimate_cues_character_ratio():
    # Two equal-length segments → second cue at 50% duration.
    speech = f"{'a' * 50}{SLIDE_TAG}{'b' * 50}"
    cues = estimate_cues(speech, 10_000)
    assert cues[0].start_ms == 0
    assert abs(cues[1].start_ms - 5_000) <= 50  # within 0.5%


def test_write_slides_json_roundtrip(tmp_path: Path):
    speech = f"x{SLIDE_TAG}y{SLIDE_TAG}z"
    cues = estimate_cues(speech, 9_000)
    path = tmp_path / "slides.json"
    write_slides_json(cues, path)
    import json
    data = json.loads(path.read_text())
    assert [c["idx"] for c in data] == [0, 1, 2]


def test_slide_cues_fallback_on_mutation(monkeypatch):
    """If model mutates text both times, fall back to deterministic H2 placement."""
    char = load_char("default_ja")
    speech = "# 講義\n\n## 導入\n本文。\n\n## 方法\n手法の説明。\n"
    mutated = "# 変更\n\n## 導入\nbad.\n"

    def fake_client(cfg):
        c = MagicMock()
        c.messages.create = lambda **kw: _fake_response(mutated)
        return c

    monkeypatch.setattr(slide_cues, "client", fake_client)
    result = slide_cues.inject(speech, char, cfg=_CFG)
    # Fallback should insert cues before each H2 (2 H2s here).
    assert result.count(SLIDE_TAG) == 2
    assert strip_slide_tags(result).strip() == speech.strip()


def test_slide_cues_diff_guard_accepts_good_output(monkeypatch):
    char = load_char("default_ja")
    speech = "# 講義\n\n## 導入\n本文。\n"
    cued = f"# 講義\n\n{SLIDE_TAG}\n## 導入\n本文。\n"

    def fake_client(cfg):
        c = MagicMock()
        c.messages.create = lambda **kw: _fake_response(cued)
        return c

    monkeypatch.setattr(slide_cues, "client", fake_client)
    result = slide_cues.inject(speech, char, cfg=_CFG)
    assert SLIDE_TAG in result
    assert strip_slide_tags(result).strip() == speech.strip()
