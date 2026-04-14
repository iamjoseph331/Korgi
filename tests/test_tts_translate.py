from korgi.tts.tag_translate import to_elevenlabs, to_moss, to_stub
from korgi.speech.schema import TAG_SET


def _sample(tag: str) -> str:
    return f"[{tag}]これはテストです。"


def test_elevenlabs_passthrough_all_tags():
    """ElevenLabs is the native format — canonical tags pass through unchanged."""
    for tag in TAG_SET:
        out = to_elevenlabs(_sample(tag))
        assert out == _sample(tag), f"ElevenLabs should not modify [{tag}]"


def test_moss_strips_all_tags():
    for tag in TAG_SET:
        out = to_moss(_sample(tag))
        assert f"[{tag}]" not in out
        assert "(" not in out
        assert "これはテストです。" in out


def test_stub_all_tags():
    for tag in TAG_SET:
        out = to_stub(_sample(tag))
        assert f"[{tag}]" not in out
        assert "これはテストです。" in out


def test_elevenlabs_thinking_passthrough():
    assert to_elevenlabs("[thinking]hello") == "[thinking]hello"


def test_elevenlabs_hesitate_passthrough():
    assert to_elevenlabs("[hesitate]困った") == "[hesitate]困った"


def test_no_tag_passthrough():
    plain = "タグなしのテキストです。"
    assert to_elevenlabs(plain) == plain
    assert to_moss(plain) == plain
    assert to_stub(plain) == plain
