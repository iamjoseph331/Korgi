from korgi.characters import loader


def test_load_default_ja():
    p = loader.load("default_ja")
    assert p.lang == "ja"
    assert p.name
    assert p.persona
    assert "〜ですね" in p.speech_style.verbal_tics
    assert p.tag_bias.get("thinking") == "high"
    assert p.live2d_expression_map["serious"] == "Default"


def test_load_default_en():
    p = loader.load("default_en")
    assert p.lang == "en"
    assert p.speech_style.verbal_tics


def test_load_missing_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        loader.load("nope_does_not_exist")
