import importlib

import pytest


def test_convert_raises_when_markitdown_missing(tmp_path, monkeypatch):
    from korgi.pdf import to_markdown

    pdf = tmp_path / "tiny.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def blocked_import(name, *args, **kwargs):
        if name == "markitdown":
            raise ImportError("forced")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked_import)
    with pytest.raises(RuntimeError, match="markitdown is not installed"):
        to_markdown.convert(pdf, tmp_path / "cache")


def test_convert_caches_by_hash(tmp_path, monkeypatch):
    """A second call with the same bytes reuses the cached .md without re-invoking markitdown."""
    if importlib.util.find_spec("markitdown") is None:
        pytest.skip("markitdown not installed")

    import markitdown as mk
    from korgi.pdf import to_markdown

    pdf = tmp_path / "same.pdf"
    pdf.write_bytes(b"stand-in bytes")

    calls = {"n": 0}

    class FakeMarkItDown:
        def convert(self, path):
            calls["n"] += 1
            from types import SimpleNamespace

            return SimpleNamespace(text_content=f"# fake\n\nmd for {path}")

    monkeypatch.setattr(mk, "MarkItDown", FakeMarkItDown)

    cache = tmp_path / "cache"
    first = to_markdown.convert(pdf, cache)
    mtime = first.stat().st_mtime_ns
    second = to_markdown.convert(pdf, cache)
    assert first == second
    assert second.stat().st_mtime_ns == mtime
    assert calls["n"] == 1  # second call hit the cache
