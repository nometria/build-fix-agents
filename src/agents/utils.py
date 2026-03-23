"""Shared utilities for build-fix agents."""
from pathlib import Path
from typing import List

SOURCE_EXTS = {".js", ".jsx", ".ts", ".tsx"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "out"}


def source_files(project_root: Path) -> List[Path]:
    """Walk project_root and return all JS/TS source files (skips node_modules etc.)."""
    out: List[Path] = []
    for path in project_root.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_EXTS:
            continue
        try:
            rel = path.relative_to(project_root)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            out.append(path)
        except ValueError:
            continue
    return out
