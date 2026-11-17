"""
title: Textstatistik
author: T3chSynergy
version: 0.1.0
required_open_webui_version: 0.13.0
description: Zählt Wörter, Zeichen und Sätze eines Textes und schätzt die Lesezeit.
licence: MIT
"""

# Beispiel für ein Tool: Das Modell ruft die Methode selbst auf, wenn sie zur
# Anfrage passt. Name, Docstring und Typangaben der Methode werden zur
# Beschreibung, die das Modell sieht; deshalb sorgfältig formulieren.

import json
import math
import re

from pydantic import BaseModel, Field


def statistik(text: str, woerter_pro_minute: int = 200) -> dict:
    woerter = re.findall(r"\w+(?:[-']\w+)*", text, flags=re.UNICODE)
    saetze = [s for s in re.split(r"[.!?]+(?:\s|$)", text.strip()) if s.strip()]
    return {
        "woerter": len(woerter),
        "zeichen": len(text),
        "zeichen_ohne_leerzeichen": len(re.sub(r"\s", "", text)),
        "saetze": len(saetze),
        "lesezeit_minuten": math.ceil(len(woerter) / max(woerter_pro_minute, 1)) if woerter else 0,
    }


class Tools:
    class Valves(BaseModel):
        woerter_pro_minute: int = Field(default=200, description="Lesegeschwindigkeit für die Lesezeit.")

    def __init__(self):
        self.valves = self.Valves()

    def text_statistik(self, text: str) -> str:
        """
        Zählt Wörter, Zeichen und Sätze eines Textes und schätzt die Lesezeit.
        Verwende das Tool, wenn der Anwender nach Länge oder Umfang eines Textes fragt.

        :param text: Der vollständige Text, der ausgewertet werden soll.
        :return: JSON mit woerter, zeichen, zeichen_ohne_leerzeichen, saetze und lesezeit_minuten.
        """
        return json.dumps(statistik(text, self.valves.woerter_pro_minute), ensure_ascii=False)
