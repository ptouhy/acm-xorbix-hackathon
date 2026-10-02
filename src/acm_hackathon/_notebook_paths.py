"""Find project root and configure sys.path — use from Databricks notebooks."""

from __future__ import annotations

import sys
from pathlib import Path


def find_project_root() -> Path:
    """Walk up from cwd until we find src/acm_hackathon (Repos or bundle layout)."""
    for path in [Path.cwd(), *Path.cwd().parents]:
        if (path / "src" / "acm_hackathon").is_dir():
            return path
        # Notebook running from repo root with flat layout (unlikely)
        if (path / "acm_hackathon").is_dir() and path.name == "src":
            return path.parent
    raise RuntimeError(
        "Could not find project root (expected src/acm_hackathon).\n"
        "Clone the FULL repo via Databricks Repos — not just this notebook.\n"
        f"Current working directory: {Path.cwd()}"
    )


def ensure_importable() -> Path:
    """Add src/ to sys.path so `import acm_hackathon` works."""
    root = find_project_root()
    src = root / "src"
    src_str = str(src)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
    return root
