"""Size-based log rotation for the shop's JSON log, so the shared log cannot grow without limit.

When the file would pass `max_bytes`, it is renamed to shop.log.1 (and .1 to .2, and so on, up to `backups`),
and a fresh shop.log is started. Old backups beyond `backups` are deleted. Only the shop writes this file.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_MAX_BYTES = 256 * 1024
DEFAULT_BACKUPS = 3


def rotate(path: Path, backups: int) -> None:
    """Shift shop.log -> shop.log.1 -> ... and drop the oldest backup."""
    oldest = path.with_name(f"{path.name}.{backups}")
    if oldest.exists():
        oldest.unlink()
    for index in range(backups - 1, 0, -1):
        source = path.with_name(f"{path.name}.{index}")
        if source.exists():
            os.replace(source, path.with_name(f"{path.name}.{index + 1}"))
    if path.exists():
        os.replace(path, path.with_name(f"{path.name}.1"))


def append_line(path: Path, line: str, max_bytes: int = DEFAULT_MAX_BYTES, backups: int = DEFAULT_BACKUPS) -> None:
    """Append one line, rotating first when the file is already at or past the limit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if backups > 0 and path.exists() and path.stat().st_size + len(line) > max_bytes:
        rotate(path, backups)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
