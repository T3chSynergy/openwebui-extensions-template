"""
title: Datum einfügen
author: T3chSynergy
version: 0.1.0
required_open_webui_version: 0.13.0
description: Ergänzt den System-Prompt um das aktuelle Datum, damit das Modell mit „heute“ und „morgen“ rechnen kann.
licence: MIT
"""

# Beispiel für einen Filter: inlet() verändert die Anfrage, bevor sie das
# Modell erreicht; outlet() könnte die fertige Antwort verändern.
# Einem Modell zuweisen unter Arbeitsbereich → Modelle → Filter
# oder in models/<id>/model.json unter meta.filterIds.

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MARKER = "Aktuelles Datum:"


def datumszeile(jetzt: datetime) -> str:
    return f"{MARKER} {WOCHENTAGE[jetzt.weekday()]}, {jetzt:%d.%m.%Y}, {jetzt:%H:%M} Uhr ({jetzt.tzname()})"


class Filter:
    class Valves(BaseModel):
        zeitzone: str = Field(default="Europe/Berlin", description="IANA-Zeitzone, z. B. Europe/Berlin.")
        priority: int = Field(default=0, description="Reihenfolge, wenn mehrere Filter aktiv sind.")

    def __init__(self):
        self.valves = self.Valves()

    def _jetzt(self) -> datetime:
        try:
            return datetime.now(ZoneInfo(self.valves.zeitzone))
        except ZoneInfoNotFoundError:
            return datetime.now(ZoneInfo("UTC"))

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        messages = body.get("messages")
        if not isinstance(messages, list):
            return body
        zeile = datumszeile(self._jetzt())
        system = next((m for m in messages if m.get("role") == "system"), None)
        if system is None:
            messages.insert(0, {"role": "system", "content": zeile})
        elif isinstance(system.get("content"), str) and MARKER not in system["content"]:
            system["content"] = f"{system['content'].rstrip()}\n\n{zeile}"
        return body
