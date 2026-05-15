#!/usr/bin/env python3
from src.main import main
for cmd in (["status"], ["logs-size"], ["mode"]):
    rc = main(list(cmd))
    if rc:
        raise SystemExit(rc)
print("smoke ok")
