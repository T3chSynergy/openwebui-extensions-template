"""
title: Echo (Test)
author: T3chSynergy
version: 0.1.0
required_open_webui_version: 0.13.0
description: Testmodell ohne Sprachmodell. Antwortet mit den Nachrichten, die es erhalten hat; zeigt so, was System-Prompt und Filter aus einer Anfrage machen.
licence: MIT
"""

# Beispiel für eine Pipe: erscheint in Open WebUI als eigenes Modell mit der
# ID der Datei („echo“). Eine Pipe kann ein externes System anbinden; diese
# hier gibt nur die Anfrage zurück. Das macht sie nützlich zum Testen von
# Filtern, System-Prompts und Aktionen, ohne ein echtes Modell zu bezahlen.

from pydantic import BaseModel, Field


def format_messages(messages: list, max_zeichen: int) -> str:
    teile = []
    for message in messages or []:
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        content = str(content)
        if len(content) > max_zeichen:
            content = content[:max_zeichen] + f" … ({len(content) - max_zeichen} Zeichen gekürzt)"
        teile.append(f"### {message.get('role', '?')}\n\n{content}")
    return "\n\n".join(teile) if teile else "(keine Nachrichten)"


class Pipe:
    class Valves(BaseModel):
        max_zeichen: int = Field(default=2000, description="Längere Nachrichten werden gekürzt.")

    def __init__(self):
        self.valves = self.Valves()

    def pipe(self, body: dict) -> str:
        return "**Echo** – diese Nachrichten kamen beim Modell an:\n\n" + format_messages(
            body.get("messages"), self.valves.max_zeichen
        )
