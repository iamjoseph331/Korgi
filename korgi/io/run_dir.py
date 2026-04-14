from __future__ import annotations

import re
from pathlib import Path


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return s or "run"


def prepare(out_root: Path, paper_path: Path) -> Path:
    run = Path(out_root) / slugify(paper_path.stem)
    (run / "audio").mkdir(parents=True, exist_ok=True)
    return run
