from __future__ import annotations

from typing import Iterable


def choose_reply(text: str, faq_items: Iterable[dict], default_reply: str) -> str | None:
    lowered = text.lower()
    for item in faq_items:
        keywords = item.get("keywords") or []
        if any(str(k).lower() in lowered for k in keywords):
            return str(item.get("reply") or default_reply)
    return default_reply
