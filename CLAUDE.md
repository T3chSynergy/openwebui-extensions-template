# Hinweise für Claude

Dieses Repo enthält Erweiterungen für Open WebUI. Die README beschreibt Aufbau und Konventionen; hier nur das, was beim Arbeiten am häufigsten schiefgeht.

- Jede Datei in `tools/` und `functions/*/` wird von Open WebUI einzeln geladen. Keine Importe aus anderen Repo-Dateien; gemeinsamen Code kopieren.
- Dateiname = ID in Open WebUI. Bestehende IDs nicht umbenennen, Modelle verweisen darauf.
- Bei jeder inhaltlichen Änderung `version` im Kopf anheben und einen Eintrag in `CHANGELOG.md` ergänzen.
- System-Prompts stehen in `models/<id>/system-prompt.md`, nie in `model.json`.
- Keine Zugangsdaten, Benutzer-IDs oder Valves mit echten Werten ins Repo.
- Vor dem Commit: `uv run python scripts/check.py` und `uv run pytest`.
- `scripts/deploy.py` und `e2e/` nie gegen eine produktive Instanz ausführen, außer der Anwender verlangt es ausdrücklich.
- Antworten an den Anwender und Texte im Repo auf Deutsch, Commit-Nachrichten auf Englisch.
