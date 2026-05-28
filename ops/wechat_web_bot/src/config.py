from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = BASE_DIR / "config.yaml"
RUNTIME_DIR = BASE_DIR / "runtime"
LOG_DIR = BASE_DIR / "logs"
STATE_PATH = RUNTIME_DIR / "state.json"
MODE_PATH = RUNTIME_DIR / "mode.txt"
PID_PATH = RUNTIME_DIR / "wxweb.pid"


def ensure_dirs() -> None:
    for path in [
        RUNTIME_DIR,
        LOG_DIR,
        LOG_DIR / "messages",
        LOG_DIR / "screenshots",
        LOG_DIR / "dom_snapshots",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def _simple_yaml(text: str) -> Dict[str, Any]:
    """Very small YAML fallback for this config's simple top-level keys.

    PyYAML is preferred when available. The fallback intentionally returns an
    empty dict instead of guessing nested YAML semantics; defaults cover runtime.
    """
    return {}


def load_config() -> Dict[str, Any]:
    ensure_dirs()
    if not CONFIG_PATH.exists():
        return {}
    text = CONFIG_PATH.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return _simple_yaml(text)


def get_mode(config: Dict[str, Any] | None = None) -> str:
    if MODE_PATH.exists():
        mode = MODE_PATH.read_text(encoding="utf-8").strip()
        if mode:
            return mode
    config = config if config is not None else load_config()
    return str(config.get("mode") or "observe")


def set_mode(mode: str) -> None:
    if mode not in {"observe", "semi-auto", "auto"}:
        raise ValueError("mode must be one of: observe, semi-auto, auto")
    ensure_dirs()
    MODE_PATH.write_text(mode + "\n", encoding="utf-8")
