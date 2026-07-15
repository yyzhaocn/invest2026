"""Repository-root paths for invest2026 (independent of cwd / atime)."""
from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import List

# stock/ -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
STOCK_DIR = Path(__file__).resolve().parent
GENERATED_EM = str(REPO_ROOT / 'generated' / 'em')
GENERATED_CACHE = str(REPO_ROOT / 'generated' / 'cache')
SHARED_DIR = str(REPO_ROOT / 'shared')


def em_path(*parts: str) -> str:
    return os.path.join(GENERATED_EM, *parts)


def shared_path(*parts: str) -> str:
    return os.path.join(SHARED_DIR, *parts)


def em_glob(pattern: str) -> List[str]:
    """Glob under generated/em; pattern may start with */ e.g. '*/zjlx_zlb_*.csv'."""
    return glob.glob(em_path(pattern))
