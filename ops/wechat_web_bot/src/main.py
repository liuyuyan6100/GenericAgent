#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "src"

from .browser import open_wechat, probe_page, qr_hint
from .config import BASE_DIR, LOG_DIR, PID_PATH, STATE_PATH, ensure_dirs, get_mode, load_config, set_mode
from .log_utils import directory_size_bytes, gc_logs, setup_logging


def write_state(**extra: object) -> None:
    ensure_dirs()
    state = {
        "pid": os.getpid(),
        "mode": get_mode(),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    state.update(extra)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_loop(args: argparse.Namespace) -> int:
    config = load_config()
    logger = setup_logging(str(config.get("logging", {}).get("level", "INFO")) if isinstance(config.get("logging"), dict) else "INFO")
    ensure_dirs()
    PID_PATH.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    stop = {"value": False}

    def _handle(signum: int, _frame: object) -> None:
        logger.info("received signal %s, stopping", signum)
        stop["value"] = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    logger.info("wxweb bot started base_dir=%s mode=%s", BASE_DIR, get_mode(config))
    write_state(status="running", last_event="started")
    try:
        if config.get("logging", {}).get("gc", {}).get("run_on_start", True) if isinstance(config.get("logging"), dict) else True:
            for action in gc_logs():
                logger.info("gc: %s", action)
        while not stop["value"]:
            mode = get_mode(config)
            write_state(status="running", mode=mode, last_event="heartbeat")
            logger.info("heartbeat mode=%s", mode)
            time.sleep(max(5, int(getattr(args, "interval", 30))))
    finally:
        write_state(status="stopped", last_event="stopped")
        try:
            PID_PATH.unlink()
        except FileNotFoundError:
            pass
        logger.info("wxweb bot stopped")
    return 0


def status(_args: argparse.Namespace) -> int:
    ensure_dirs()
    data = {"base_dir": str(BASE_DIR), "mode": get_mode(), "pid_file": str(PID_PATH), "state_file": str(STATE_PATH)}
    if PID_PATH.exists():
        pid_text = PID_PATH.read_text(encoding="utf-8").strip()
        data["pid"] = pid_text
        data["pid_running"] = Path(f"/proc/{pid_text}").exists() if pid_text.isdigit() else False
    if STATE_PATH.exists():
        try:
            data["state"] = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            data["state_error"] = repr(exc)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def cmd_probe(_args: argparse.Namespace) -> int:
    print(json.dumps(probe_page(), ensure_ascii=False, indent=2))
    return 0


def cmd_open(_args: argparse.Namespace) -> int:
    return open_wechat()


def cmd_qr(_args: argparse.Namespace) -> int:
    print(json.dumps(qr_hint(), ensure_ascii=False, indent=2))
    return 0


def cmd_gc(args: argparse.Namespace) -> int:
    for action in gc_logs(dry_run=args.dry_run):
        print(action)
    print(f"logs_total_mb={directory_size_bytes(LOG_DIR) / 1024 / 1024:.2f}")
    return 0


def cmd_logs_size(_args: argparse.Namespace) -> int:
    print(f"{directory_size_bytes(LOG_DIR) / 1024 / 1024:.2f} MB\t{LOG_DIR}")
    return 0


def cmd_mode(args: argparse.Namespace) -> int:
    if args.value:
        set_mode(args.value)
    print(get_mode())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="GA Web WeChat bot")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run heartbeat/automation loop")
    run.add_argument("--interval", type=int, default=30)
    run.set_defaults(func=run_loop)
    sub.add_parser("status").set_defaults(func=status)
    sub.add_parser("probe").set_defaults(func=cmd_probe)
    sub.add_parser("open").set_defaults(func=cmd_open)
    sub.add_parser("qr").set_defaults(func=cmd_qr)
    gc = sub.add_parser("gc")
    gc.add_argument("--dry-run", action="store_true")
    gc.set_defaults(func=cmd_gc)
    sub.add_parser("logs-size").set_defaults(func=cmd_logs_size)
    mode = sub.add_parser("mode")
    mode.add_argument("value", nargs="?", choices=["observe", "semi-auto", "auto"])
    mode.set_defaults(func=cmd_mode)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
