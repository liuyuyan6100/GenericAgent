from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from .config import BASE_DIR, LOG_DIR, ensure_dirs

REPO_ROOT = BASE_DIR.parents[1]
WX_URL = "https://wx.qq.com/"


def open_wechat(url: str = WX_URL) -> int:
    helper = REPO_ROOT / "ops" / "vnc-browser"
    if helper.exists():
        return subprocess.call([str(helper), "open", url], cwd=str(REPO_ROOT))
    print(f"Browser helper not found: {helper}", file=sys.stderr)
    return 1


def probe_page() -> Dict[str, Any]:
    ensure_dirs()
    try:
        from TMWebDriver import TMWebDriver  # type: ignore
        d = TMWebDriver()
        try:
            d.set_session("wx.qq.com")
        except Exception:
            d.set_session("web.wechat.com")
        js = r"""
        return (() => {
          const text = document.body ? document.body.innerText.slice(0, 2000) : '';
          const title = document.title;
          const url = location.href;
          const hasQr = !!document.querySelector('img.qrcode,.qrcode img,canvas');
          const input = !!document.querySelector('#editArea,[contenteditable="true"],textarea');
          return {ok:true, title, url, hasQr, hasInput: input, textSample: text};
        })();
        """
        res = d.execute_js(js)
        data = res.get("data") if isinstance(res, dict) else res
        out = data if isinstance(data, dict) else {"ok": True, "raw": data}
    except Exception as exc:
        out = {"ok": False, "error": repr(exc), "hint": "Start tmwd/browser first, then open Web WeChat."}
    snap = LOG_DIR / "dom_snapshots" / "probe-latest.json"
    snap.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def qr_hint() -> Dict[str, Any]:
    rc = open_wechat(WX_URL)
    return {
        "opened": rc == 0,
        "url": WX_URL,
        "message": "Scan QR in the VNC Chromium window if Web WeChat shows a login QR.",
        "screenshot_hint": "Use ga-service browser screenshot ops/wechat_web_bot/logs/screenshots/qr-latest.png if evidence is needed.",
    }
