"""
title: Textstatistik anzeigen
author: T3chSynergy
version: 0.1.0
required_open_webui_version: 0.13.0
description: Zeigt unter einer Antwort eine Karte mit Wörtern, Zeichen und Lesezeit.
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMzc0MTUxIiBzdHJva2Utd2lkdGg9IjEuOCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIj48cGF0aCBkPSJNNCAyMFYxME0xMCAyMFY0TTE2IDIwdi03TTIyIDIwSDIiLz48L3N2Zz4=
licence: MIT
"""

# Beispiel für eine Aktion: ein Button unter jeder Antwort des Modells.
# Zeigt zwei Wege, dem Anwender etwas zurückzugeben:
#   - eine kurze Meldung (notification)
#   - eine eingebettete HTML-Karte (embeds), die mit der Nachricht gespeichert wird
#
# Open WebUI lädt jede Datei einzeln. Die Zählfunktion ist deshalb hier kopiert
# und nicht aus tools/text_statistik.py importiert.

import html
import math
import re
from typing import Any, Optional

from pydantic import BaseModel, Field


def statistik(text: str, woerter_pro_minute: int = 200) -> dict:
    woerter = re.findall(r"\w+(?:[-']\w+)*", text, flags=re.UNICODE)
    saetze = [s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()]
    return {
        "woerter": len(woerter),
        "zeichen": len(text),
        "saetze": len(saetze),
        "lesezeit_minuten": math.ceil(len(woerter) / max(woerter_pro_minute, 1)) if woerter else 0,
    }


def message_text(body: dict) -> str:
    """Text der Antwort, unter der der Button geklickt wurde."""
    messages = body.get("messages") or []
    if not messages:
        return ""
    clicked = next((m for m in messages if m.get("id") == body.get("id")), messages[-1])
    content = clicked.get("content", "")
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else ""


def build_card(werte: dict) -> str:
    zeilen = "".join(
        f"<div class='kachel'><span class='zahl'>{html.escape(str(wert))}</span>"
        f"<span class='label'>{html.escape(label)}</span></div>"
        for label, wert in (
            ("Wörter", werte["woerter"]),
            ("Zeichen", werte["zeichen"]),
            ("Sätze", werte["saetze"]),
            ("Min. Lesezeit", werte["lesezeit_minuten"]),
        )
    )
    return _TEMPLATE.replace("__KACHELN__", zeilen)


class Action:
    class Valves(BaseModel):
        woerter_pro_minute: int = Field(default=200, description="Lesegeschwindigkeit für die Lesezeit.")

    def __init__(self):
        self.valves = self.Valves()

    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__: Any = None,
    ) -> None:
        if not __event_emitter__:
            return None
        text = message_text(body)
        if not text.strip():
            await __event_emitter__(
                {"type": "notification", "data": {"type": "info", "content": "Diese Antwort enthält keinen Text."}}
            )
            return None
        werte = statistik(text, self.valves.woerter_pro_minute)
        # "replace": ein zweiter Klick ersetzt die Karte, statt eine weitere anzuhängen
        await __event_emitter__({"type": "embeds", "data": {"embeds": [build_card(werte)], "replace": True}})
        return None


# Eingebettete Seiten laufen in einem abgeschotteten iframe. Die Höhe meldet die
# Seite selbst per postMessage („iframe:height“), sonst wird sie abgeschnitten.
_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; font: 13px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; background: transparent; }
  .karte { display: flex; gap: 8px; flex-wrap: wrap; padding: 4px 0; }
  .kachel { flex: 1 1 110px; display: flex; flex-direction: column; padding: 10px 12px;
            border: 1px solid #d1d5db; border-radius: 10px; background: #fff; color: #1f2937; }
  .zahl { font-size: 20px; font-weight: 600; }
  .label { color: #6b7280; }
  @media (prefers-color-scheme: dark) {
    .kachel { background: #1f2937; color: #f3f4f6; border-color: #374151; }
    .label { color: #9ca3af; }
  }
</style>
</head>
<body>
<div class="karte" id="karte">__KACHELN__</div>
<script>
  function hoeheMelden() {
    parent.postMessage({ type: 'iframe:height', height: Math.ceil(document.getElementById('karte').getBoundingClientRect().height) + 8 }, '*');
  }
  window.addEventListener('load', hoeheMelden);
  if (window.ResizeObserver) { new ResizeObserver(hoeheMelden).observe(document.body); }
</script>
</body>
</html>
"""
