# Open-WebUI-Erweiterungen – Vorlage

Vorlage für Repos, in denen wir Erweiterungen für [Open WebUI](https://openwebui.com) pflegen: Tools, Funktionen (Aktionen, Filter, Pipes) und Modelle mit System-Prompt. Das Repo ist die Quelle; ein Skript spielt alles in eine Open-WebUI-Instanz ein, ein zweites holt Änderungen aus Open WebUI zurück.

Getestet mit Open WebUI 0.13.3.

## Neues Repo aus der Vorlage

1. Auf GitHub **Use this template → Create a new repository**.
2. Die Beispiele löschen oder umbauen: `tools/text_statistik.py`, `functions/*/…`, `models/beispiel-assistent/`, die passenden Tests in `tests/` und, falls nicht gebraucht, die Pipe `echo` (sie dient auch dem E2E-Test).
3. In der README dieses Abschnitts den Zweck des neuen Repos beschreiben.

## Aufbau

```
tools/                     Tools – ein Tool pro Datei
functions/actions/         Aktionen – Buttons unter einer Antwort
functions/filters/         Filter – verändern Anfrage oder Antwort
functions/pipes/           Pipes – erscheinen als eigenes Modell
models/<id>/model.json     Modell: Basismodell, Parameter, zugeordnete Tools/Aktionen/Filter
models/<id>/system-prompt.md   System-Prompt des Modells
tests/                     Unit-Tests, laden die Dateien direkt
e2e/                       Test gegen eine echte Open-WebUI-Instanz (Docker)
scripts/check.py           prüft die Konventionen
scripts/deploy.py          Repo → Open WebUI
scripts/export.py          Open WebUI → Repo
```

## Konventionen

- **Dateiname = ID in Open WebUI.** Kleinbuchstaben, Ziffern und `_`, z. B. `tools/text_statistik.py` → ID `text_statistik`. Die ID nach dem ersten Einspielen nicht mehr ändern: Modelle verweisen darauf.
- **Ein Plugin pro Datei, ohne Importe aus dem Repo.** Open WebUI lädt jede Datei einzeln. Gemeinsamen Code in die jeweilige Datei kopieren; `scripts/check.py` meldet Importe aus dem Repo.
- **Kopfzeilen** am Dateianfang, beginnend mit `"""` in Zeile 1:

  ```
  """
  title: Anzeigename
  author: T3chSynergy
  version: 1.2.3
  required_open_webui_version: 0.13.0
  description: Ein Satz, was die Erweiterung tut.
  requirements: paket1, paket2      (optional)
  licence: MIT
  """
  ```

  Bei jeder Änderung `version` anheben. Pakete aus `requirements` auch in `pyproject.toml` unter `dev` eintragen, damit die Tests sie finden.
- **Genau eine Plugin-Klasse pro Datei**: `Tools` in `tools/`, `Action`, `Filter` oder `Pipe` in `functions/…`. Enthält eine Datei mehrere, erkennt Open WebUI die Art falsch.
- **Modelle** liegen in `models/<id>/`. Der System-Prompt steht in `system-prompt.md`, nicht in `model.json`. Instanzbezogene Felder (`user_id`, `access_grants`, Zeitstempel) gehören nicht ins Repo.
- **Platzhalter** in `model.json`: `${VAR}` oder `${VAR:-Standard}` werden beim Einspielen aus der Umgebung oder `.env` ersetzt. So kann das Basismodell je Instanz verschieden sein, ohne die Datei zu ändern.

## Valves und Zugangsdaten

Valves sind die Einstellungen einer Erweiterung in Open WebUI. Im Code stehen nur unkritische Standardwerte. API-Keys, Passwörter und interne Adressen trägt die Administration in Open WebUI ein; sie kommen nie ins Repo.

`deploy.py` ändert keine Valves und keine Zugriffsrechte bestehender Einträge. `export.py` schreibt keine Valves ins Repo.

## Lokal testen

```bash
uv run python scripts/check.py
```

```bash
uv run pytest
```

Die Tests laden jede Erweiterung so, wie Open WebUI es tut, und rufen sie direkt auf. `tests/conftest.py` enthält dafür `load_extension()` und einen `emitter`, der gesendete Ereignisse sammelt.

## In Open WebUI einspielen

Einmalig `.env.example` nach `.env` kopieren und `OWUI_URL` sowie `OWUI_API_KEY` eintragen. Der Key muss zu einem Admin-Konto gehören (Einstellungen → Konto → API-Schlüssel).

```bash
uv run python scripts/deploy.py --dry-run
```

```bash
uv run python scripts/deploy.py
```

Das Skript prüft zuerst mit `check.py`, legt fehlende Einträge an, aktualisiert geänderte und überspringt unveränderte. Funktionen werden aktiviert. In der Änderungshistorie von Open WebUI steht dabei `deploy <git-Stand>`. Mit `--only <id>` lassen sich einzelne Einträge einspielen.

Neue Einträge sehen zunächst nur Admins. Freigaben für Gruppen setzt die Administration in Open WebUI; sie bleiben bei späteren Deploys erhalten. Ob eine Funktion „global“ für alle Modelle gilt, entscheidet ebenfalls die Administration. Besser ist, sie in `model.json` gezielt zuzuordnen.

## Änderungen aus Open WebUI zurückholen

Wurde etwas direkt in Open WebUI geändert:

```bash
uv run python scripts/export.py
```

Das holt alle Einträge, die es im Repo schon gibt. Mit `--only <id>` oder `--all` kommen auch neue dazu. Dateien mit nicht committeten Änderungen werden nur mit `--force` überschrieben, und Platzhalter in `model.json` bleiben erhalten, solange ihr Wert zu Open WebUI passt. Danach `git diff` prüfen und committen.

## End-to-End-Test

Startet eine frische Open-WebUI-Instanz in Docker, spielt das Repo ein und prüft:

- Einspielen ist wiederholbar.
- Tools, Funktionen und Modelle werden erkannt.
- Eine Chat-Anfrage läuft durch System-Prompt, Filter und Pipe.
- Die Aktion speichert ihre Karte im Chat.

```bash
e2e/run.sh
```

Gegen eine schon laufende Testinstanz:

```bash
OWUI_URL=http://localhost:3000 uv run pytest e2e
```

Nie gegen die produktive Instanz laufen lassen: Der Test spielt alles ein und legt Test-Chats an.

Die Open-WebUI-Version steht fest in `e2e/docker-compose.yml`. Vor einem Update der produktiven Instanz dort anheben und den Test laufen lassen.

## GitHub Actions

- `tests.yml`: Prüfung und Unit-Tests bei jedem Push auf `main` und jedem Pull Request.
- `e2e.yml`: End-to-End-Test von Hand, wöchentlich und bei Änderungen an `e2e/` oder `scripts/`. Er lädt das Open-WebUI-Image (mehrere GB) und braucht einige Minuten.

## Beispiele

| Datei | Art | Zeigt |
| --- | --- | --- |
| `tools/text_statistik.py` | Tool | Methode mit Docstring als Beschreibung für das Modell, Valves |
| `functions/actions/textstatistik_anzeigen.py` | Aktion | Meldung und eingebettete HTML-Karte, Höhe per `iframe:height` |
| `functions/filters/datum_einfuegen.py` | Filter | `inlet()` ergänzt den System-Prompt |
| `functions/pipes/echo.py` | Pipe | Testmodell ohne Sprachmodell; zeigt, was beim Modell ankommt |
| `models/beispiel-assistent/` | Modell | Basismodell als Platzhalter, Zuordnung von Tool, Aktion und Filter |

## Lizenz

MIT, siehe [LICENSE](LICENSE). Fremdbibliotheken, die eine Erweiterung einbettet, mit eigener Lizenzdatei unter `vendor/<name>/<version>/` ablegen.
