#!/usr/bin/env python3
"""Holt Tools, Funktionen und Modelle aus Open WebUI ins Repo zurück.

Aufruf:
    python scripts/export.py                       # alles, was es im Repo schon gibt
    python scripts/export.py --only mein_tool      # bestimmte IDs, auch neue
    python scripts/export.py --all                 # alles aus der Instanz, auch Neues

Nützlich, wenn jemand eine Erweiterung direkt in Open WebUI geändert hat.
Geschrieben werden nur Inhalte; Valves, Zugriffsrechte, Benutzer-IDs und Zeitstempel
landen nicht im Repo. Dateien mit nicht committeten Änderungen werden nur mit
--force überschrieben.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from owui_lib import (  # noqa: E402
    ID_PATTERN,
    ModelDefinition,
    KINDS,
    ROOT,
    ApiError,
    OpenWebUI,
    discover_extensions,
    discover_models,
    git_has_local_changes,
    load_dotenv,
    resolve_placeholders,
)

FOLDER_OF_KIND = {kind: folder for folder, (kind, _) in KINDS.items()}
MODEL_KEYS = ("id", "name", "base_model_id", "meta", "params", "is_active")
DEFAULT_PROFILE_IMAGE = "/static/favicon.png"


def keep_placeholders(local, remote, environ=None):
    """Behält ${VAR}-Platzhalter aus dem Repo, wenn ihr aufgelöster Wert zu Open WebUI passt."""
    if isinstance(local, str) and "${" in local:
        try:
            return local if resolve_placeholders(local, environ) == remote else remote
        except KeyError:
            return remote
    if isinstance(local, dict) and isinstance(remote, dict):
        return {k: keep_placeholders(local[k], v, environ) if k in local else v for k, v in remote.items()}
    if isinstance(local, list) and isinstance(remote, list) and len(local) == len(remote):
        return [keep_placeholders(a, b, environ) for a, b in zip(local, remote)]
    return remote


def model_files(exported: dict, local: dict | None = None, environ=None) -> tuple[str, str | None]:
    """Export-Eintrag -> (model.json-Text, system-prompt.md-Text oder None).

    local ist der bisherige Inhalt von model.json; dessen Platzhalter bleiben erhalten.
    """
    data = {key: exported.get(key) for key in MODEL_KEYS if key in exported}
    params = dict(data.get("params") or {})
    prompt = params.pop("system", None)
    data["params"] = params
    meta = dict(data.get("meta") or {})
    if meta.get("profile_image_url") == DEFAULT_PROFILE_IMAGE:
        meta.pop("profile_image_url")
    data["meta"] = {k: v for k, v in meta.items() if v not in (None, [], {})}
    if local:
        data = keep_placeholders(local, data, environ)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if prompt is not None:
        prompt = prompt.rstrip() + "\n"
    return text, prompt


def _same(path: Path, text: str) -> bool:
    current = path.read_text(encoding="utf-8")
    if current == text:
        return True
    if path.suffix == ".json":  # Formatierung egal, Inhalt zählt
        try:
            return json.loads(current) == json.loads(text)
        except ValueError:
            return False
    return False


def write(path: Path, text: str, force: bool, log) -> str:
    if path.is_file() and _same(path, text):
        return "unverändert"
    if path.is_file() and git_has_local_changes(path) and not force:
        log(f"  übersprungen {rel}: nicht committete Änderungen (mit --force überschreiben)")
        return "übersprungen"
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.is_file()
    path.write_text(text, encoding="utf-8")
    return "aktualisiert" if existed else "neu"


def export(client: OpenWebUI, only: set[str] | None = None, include_new: bool = False,
           force: bool = False, log=print) -> list[tuple[str, str, str]]:
    local = {ext.id: ext for ext in discover_extensions()}
    local_models = {m.id for m in discover_models()}
    results = []

    def wanted(ident, known):
        if only:
            return ident in only
        return include_new or known

    remote = [("tool", t) for t in client.get("/api/v1/tools/export") or []]
    remote += [(f.get("type"), f) for f in client.get("/api/v1/functions/export") or []]
    for kind, item in remote:
        ident = item.get("id", "")
        if kind not in FOLDER_OF_KIND or not wanted(ident, ident in local):
            continue
        if not ID_PATTERN.match(ident):
            log(f"  übersprungen {kind} {ident}: ID passt nicht zu den Dateinamen-Konventionen")
            continue
        if ident in local and local[ident].kind != kind:
            log(f"  übersprungen {kind} {ident}: im Repo als {local[ident].kind} vorhanden")
            continue
        path = ROOT / FOLDER_OF_KIND[kind] / f"{ident}.py"
        content = item.get("content") or ""
        outcome = write(path, content if content.endswith("\n") else content + "\n", force, log)
        results.append((kind, ident, outcome))
        log(f"  {outcome:<12} {kind:<7} {path.relative_to(ROOT).as_posix()}")

    for item in client.get("/api/v1/models/export") or []:
        ident = item.get("id", "")
        if not item.get("base_model_id") or not wanted(ident, ident in local_models):
            continue  # Basismodelle der Anbieter gehören nicht ins Repo
        folder = ROOT / "models" / ident
        definition = ModelDefinition(ident, folder)
        local = definition.load() if definition.json_path.is_file() else None
        model_json, prompt = model_files(item, local)
        outcome = write(folder / "model.json", model_json, force, log)
        if prompt is not None:
            prompt_outcome = write(folder / "system-prompt.md", prompt, force, log)
            if outcome == "unverändert":
                outcome = prompt_outcome
        results.append(("model", ident, outcome))
        log(f"  {outcome:<12} model   models/{ident}/")
    return results


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("OWUI_URL"))
    parser.add_argument("--key", default=os.environ.get("OWUI_API_KEY"))
    parser.add_argument("--only", nargs="+", metavar="ID", help="nur diese IDs, auch wenn sie im Repo noch fehlen")
    parser.add_argument("--all", action="store_true", help="auch Einträge holen, die es im Repo noch nicht gibt")
    parser.add_argument("--force", action="store_true", help="auch Dateien mit lokalen Änderungen überschreiben")
    args = parser.parse_args(argv)

    client = OpenWebUI(args.url, args.key)
    print(f"Quelle: {client.url}")
    try:
        results = export(client, set(args.only) if args.only else None, args.all, args.force)
    except ApiError as error:
        print(f"Fehler: {error}")
        return 1
    if not results:
        print("Nichts exportiert.")
    print("Danach: python scripts/check.py und git diff prüfen. Valves stehen nicht im Repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
