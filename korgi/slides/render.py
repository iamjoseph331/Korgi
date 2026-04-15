"""Stage 2g — optional Marp CLI render (best-effort).

Shells out to `marp-cli` to produce `slides/slides.html`. If `marp-cli` is
not installed, returns None and the frontend renders Marp client-side via
@marp-team/marp-core.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def render(slides_md: Path) -> Path | None:
    """Render `slides.md` → `slides.html` via marp-cli if available.

    Returns the HTML path on success, None if marp-cli is absent or the
    render failed. Never raises.
    """
    marp = shutil.which("marp")
    if marp is None:
        return None
    html_path = slides_md.with_suffix(".html")
    try:
        subprocess.run(
            [marp, str(slides_md), "--html", "-o", str(html_path)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return html_path if html_path.exists() else None
