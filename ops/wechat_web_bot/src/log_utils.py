from __future__ import annotations

import gzip
import logging
import logging.handlers
import os
import shutil
from pathlib import Path
from typing import Iterable

from .config import LOG_DIR, ensure_dirs


class GzipRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def doRollover(self) -> None:  # pragma: no cover - inherited mechanics
        super().doRollover()
        for candidate in self.baseFilename, f"{self.baseFilename}.1":
            path = Path(candidate)
            if path.exists() and path.suffix != ".gz" and path.name.endswith(".1"):
                gz = path.with_suffix(path.suffix + ".gz")
                with path.open("rb") as src, gzip.open(gz, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                path.unlink(missing_ok=True)


def setup_logging(level: str = "INFO") -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("wxweb")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = GzipRotatingFileHandler(LOG_DIR / "bot.log", maxBytes=20 * 1024 * 1024, backupCount=10, encoding="utf-8")
    app.setFormatter(fmt)
    app.setLevel(logger.level)
    err = GzipRotatingFileHandler(LOG_DIR / "errors.log", maxBytes=20 * 1024 * 1024, backupCount=10, encoding="utf-8")
    err.setFormatter(fmt)
    err.setLevel(logging.ERROR)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(logger.level)
    logger.addHandler(app)
    logger.addHandler(err)
    logger.addHandler(console)
    return logger


def directory_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for file in path.rglob("*"):
        if file.is_file():
            try:
                total += file.stat().st_size
            except OSError:
                pass
    return total


def _files_by_age(path: Path) -> Iterable[Path]:
    files = [p for p in path.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    return sorted(files, key=lambda p: p.stat().st_mtime if p.exists() else 0)


def gc_logs(max_total_mb: int = 1024, dry_run: bool = False) -> list[str]:
    ensure_dirs()
    actions: list[str] = []
    now = __import__("time").time()
    retention = {
        LOG_DIR / "messages": 30 * 86400,
        LOG_DIR / "screenshots": 7 * 86400,
        LOG_DIR / "dom_snapshots": 7 * 86400,
    }
    for folder, max_age in retention.items():
        for file in list(_files_by_age(folder)):
            try:
                age = now - file.stat().st_mtime
            except OSError:
                continue
            if age > max_age:
                actions.append(f"delete expired {file.relative_to(LOG_DIR)}")
                if not dry_run:
                    file.unlink(missing_ok=True)
    limit = max_total_mb * 1024 * 1024
    while directory_size_bytes(LOG_DIR) > limit:
        candidates = [p for p in _files_by_age(LOG_DIR) if p.name not in {"bot.log", "runner.log", "errors.log"}]
        if not candidates:
            break
        victim = candidates[0]
        actions.append(f"delete oldest {victim.relative_to(LOG_DIR)}")
        if dry_run:
            break
        victim.unlink(missing_ok=True)
    if not actions:
        actions.append("no cleanup needed")
    return actions
