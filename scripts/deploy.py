#!/usr/bin/env python3
"""Spielt Tools, Funktionen und Modelle aus dem Repo in eine Open-WebUI-Instanz ein.

Aufruf:
    python scripts/deploy.py                 # alles
    python scripts/deploy.py --only echo     # nur bestimmte IDs
    python scripts/deploy.py --dry-run       # nur anzeigen, was passieren würde

Verbindung über OWUI_URL und OWUI_API_KEY (Umgebung oder .env). Der Key muss zu
einem Admin-Konto gehören.

Verhalten:
- Unveränderte Inhalte werden übersprungen.
- Funktionen werden aktiviert. Ob eine Funktion „global“ ist, entscheidet die
  Administration in Open WebUI; das Skript ändert es nicht.
- Valves und Zugriffsrechte bestehender Einträge bleiben unverändert.
- Neue Einträge sind zunächst nur für Admins sichtbar; Freigaben in Open WebUI setzen.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check import check  # noqa: E402
from owui_lib import (  # noqa: E402
    ApiError,
    OpenWebUI,
    build_model_form,
    discover_extensions,
    discover_models,
    git_revision,
    load_dotenv,
)

# Pipes zuerst, weil Modelle sie als Basismodell nutzen können
ORDER = {"pipe": 0, "filter": 1, "action": 2, "tool": 3}


def deploy(client: OpenWebUI, only: set[str] | None = None, dry_run: bool = False,
           with_models: bool = True, log=print) -> list[tuple[str, str, str]]:
    commit_message = f"deploy {git_revision()}"
    results: list[tuple[str, str, str]] = []

    def record(kind, ident, outcome):
        results.append((kind, ident, outcome))
        log(f"  {outcome:<12} {kind:<7} {ident}")

    extensions = sorted(discover_extensions(), key=lambda e: (ORDER[e.kind], e.id))
    for ext in extensions:
        if only and ext.id not in only:
            continue
        base = "/api/v1/functions" if ext.is_function else "/api/v1/tools"
        current = client.get_or_none(f"{base}/id/{ext.id}")
        form = {
            "id": ext.id,
            "name": ext.name,
            "content": ext.content,
            "meta": {"description": ext.frontmatter.get("description", ""), "manifest": ext.frontmatter},
            "commit_message": commit_message,
        }
        if current and current.get("content") == ext.content and current.get("name") == ext.name:
            outcome = "unverändert"
        elif dry_run:
            outcome = "würde ändern" if current else "würde anlegen"
        elif current:
            client.post(f"{base}/id/{ext.id}/update", form)
            outcome = "aktualisiert"
        else:
            client.post(f"{base}/create", form)
            outcome = "angelegt"

        if ext.is_function and not dry_run:
            state = client.get(f"{base}/id/{ext.id}")
            if state.get("type") != ext.kind:
                raise SystemExit(f"{ext.relpath}: Open WebUI erkennt die Art „{state.get('type')}“ statt „{ext.kind}“.")
            if not state.get("is_active"):
                client.post(f"{base}/id/{ext.id}/toggle")
                outcome += ", aktiviert"
        record(ext.kind, ext.id, outcome)

    if with_models:
        for model in discover_models():
            if only and model.id not in only:
                continue
            form = build_model_form(model)
            current = client.get_or_none("/api/v1/models/model", {"id": model.id})
            comparable = {k: current.get(k) for k in ("name", "base_model_id", "meta", "params", "is_active")} if current else None
            wanted = {k: form[k] for k in ("name", "base_model_id", "meta", "params", "is_active")}
            if comparable is not None and _contains(comparable, wanted):
                outcome = "unverändert"
            elif dry_run:
                outcome = "würde ändern" if current else "würde anlegen"
            elif current:
                client.post("/api/v1/models/model/update", {**form, "commit_message": commit_message})
                outcome = "aktualisiert"
            else:
                client.post("/api/v1/models/create", {**form, "commit_message": commit_message})
                outcome = "angelegt"
            record("model", model.id, outcome)
    return results


def _contains(actual, wanted) -> bool:
    """True, wenn alle gewünschten Werte so in Open WebUI stehen (Zusatzfelder egal)."""
    if isinstance(wanted, dict):
        return isinstance(actual, dict) and all(_contains(actual.get(k), v) for k, v in wanted.items())
    return actual == wanted


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("OWUI_URL"), help="z. B. https://openwebui.example")
    parser.add_argument("--key", default=os.environ.get("OWUI_API_KEY"), help="API-Key eines Admin-Kontos")
    parser.add_argument("--only", nargs="+", metavar="ID", help="nur diese IDs (Dateiname bzw. Modellordner)")
    parser.add_argument("--dry-run", action="store_true", help="nichts ändern, nur anzeigen")
    parser.add_argument("--no-models", action="store_true", help="Modelle auslassen")
    args = parser.parse_args(argv)

    errors, _ = check()
    if errors:
        print("Abbruch: scripts/check.py meldet Fehler:")
        for message in errors:
            print(f"  {message}")
        return 1

    client = OpenWebUI(args.url, args.key)
    print(f"Ziel: {client.url}{' (Probelauf)' if args.dry_run else ''}")
    try:
        results = deploy(client, set(args.only) if args.only else None, args.dry_run, not args.no_models)
    except ApiError as error:
        print(f"Fehler: {error}")
        return 1
    if args.only and not results:
        print("Keine passende ID gefunden.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
