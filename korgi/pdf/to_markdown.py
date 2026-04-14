from __future__ import annotations

import hashlib
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def convert(pdf_path: Path, cache_dir: Path) -> Path:
    """Convert a PDF to markdown via markitdown. Cached by file SHA256.

    Returns the path to the cached .md file under cache_dir.
    """
    pdf_path = Path(pdf_path)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    digest = _sha256(pdf_path)
    out = cache_dir / f"{pdf_path.stem}.{digest[:12]}.md"
    if out.exists():
        return out

    try:
        from markitdown import MarkItDown
    except ImportError as e:
        raise RuntimeError(
            "markitdown is not installed. Install with: pip install 'markitdown[all]'"
        ) from e

    md = MarkItDown()
    result = md.convert(str(pdf_path))
    out.write_text(result.text_content, encoding="utf-8")
    return out
