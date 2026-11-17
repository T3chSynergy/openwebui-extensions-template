#!/usr/bin/env python3
"""Prüft alle Erweiterungen und Modelle im Repo auf die Konventionen der Vorlage.

Aufruf: python scripts/check.py
Rückgabe: 0 ohne Fehler, 1 bei Fehlern. Hinweise allein führen nicht zum Abbruch.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from owui_lib import (  # noqa: E402
    ID_PATTERN,
    KINDS,
    MODEL_ID_PATTERN,
    PLUGIN_CLASSES,
    ROOT,
    discover_extensions,
    discover_models,
)

REQUIRED_FRONTMATTER = ("title", "version", "description", "required_open_webui_version")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
# Felder, die nur in eine bestimmte Open-WebUI-Instanz gehören
INSTANCE_FIELDS = {"user_id", "access_grants", "version_id", "created_at", "updated_at", "user", "valves", "write_access"}
MODEL_FIELDS = {"id", "name", "base_model_id", "meta", "params", "is_active"}


def check(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    extensions = discover_extensions(root)
    expected_class = {kind: cls for kind, cls in KINDS.values()}

    # Dateien außerhalb der bekannten Ordner
    for path in sorted((root / "functions").glob("*.py")) if (root / "functions").is_dir() else []:
        errors.append(f"{path.relative_to(root)}: Funktionen gehören in actions/, filters/ oder pipes/.")

    seen: dict[str, Path] = {}
    for ext in extensions:
        where = ext.path.relative_to(root).as_posix()
        if not ID_PATTERN.match(ext.id):
            errors.append(f"{where}: Dateiname ergibt die ID „{ext.id}“; erlaubt sind Kleinbuchstaben, Ziffern und _.")
        if ext.id in seen:
            errors.append(f"{where}: ID „{ext.id}“ ist bereits in {seen[ext.id].relative_to(root)} vergeben.")
        seen.setdefault(ext.id, ext.path)

        content = ext.content
        if not ext.frontmatter:
            errors.append(f'{where}: Die Datei muss mit einem Kopf-Docstring beginnen (erste Zeile genau """).')
        for key in REQUIRED_FRONTMATTER:
            if not ext.frontmatter.get(key):
                errors.append(f"{where}: Kopfzeile „{key}:“ fehlt.")
        for key in ("version", "required_open_webui_version"):
            value = ext.frontmatter.get(key)
            if value and not VERSION_PATTERN.match(value):
                errors.append(f"{where}: {key} „{value}“ ist keine Version der Form 1.2.3.")

        try:
            tree = ast.parse(content, filename=where)
        except SyntaxError as error:
            errors.append(f"{where}:{error.lineno}: Syntaxfehler: {error.msg}")
            continue
        classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        wanted = expected_class[ext.kind]
        if wanted not in classes:
            errors.append(f"{where}: Klasse {wanted} fehlt.")
        others = sorted((classes & PLUGIN_CLASSES) - {wanted})
        if others:
            errors.append(f"{where}: enthält zusätzlich {', '.join(others)}; Open WebUI würde die Art falsch erkennen.")
        imports = {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        } | {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        local = {p.stem for p in root.rglob("*.py") if ".venv" not in p.parts} - {"open_webui"}
        shared = sorted(imports & local - {ext.id})
        if shared:
            errors.append(f"{where}: importiert {', '.join(shared)} aus dem Repo. Open WebUI lädt jede Datei einzeln; "
                          "gemeinsamer Code muss in die Datei kopiert werden.")

    # Modelle
    known_ids = {ext.id: ext.kind for ext in extensions}
    for model in discover_models(root):
        where = model.folder.relative_to(root).as_posix()
        try:
            data = model.load()
        except json.JSONDecodeError as error:
            errors.append(f"{where}/model.json: ungültiges JSON ({error}).")
            continue
        if not MODEL_ID_PATTERN.match(model.id):
            errors.append(f"{where}: Ordnername „{model.id}“ ist keine gültige Modell-ID (Kleinbuchstaben, Ziffern, _ . -).")
        if data.get("id") != model.id:
            errors.append(f"{where}/model.json: id „{data.get('id')}“ muss dem Ordnernamen „{model.id}“ entsprechen.")
        for key in ("name", "base_model_id"):
            if not data.get(key):
                errors.append(f"{where}/model.json: „{key}“ fehlt.")
        leftovers = sorted(INSTANCE_FIELDS & set(data))
        if leftovers:
            errors.append(f"{where}/model.json: instanzbezogene Felder entfernen: {', '.join(leftovers)}.")
        unknown = sorted(set(data) - MODEL_FIELDS - INSTANCE_FIELDS)
        if unknown:
            warnings.append(f"{where}/model.json: unbekannte Felder werden nicht übertragen: {', '.join(unknown)}.")
        params = data.get("params") or {}
        if "system" in params:
            errors.append(f"{where}/model.json: Den System-Prompt in system-prompt.md ablegen, nicht in params.system.")
        if not model.prompt_path.is_file():
            warnings.append(f"{where}: system-prompt.md fehlt; das Modell bekommt keinen System-Prompt.")
        meta = data.get("meta") or {}
        for key, kind in (("toolIds", "tool"), ("actionIds", "action"), ("filterIds", "filter")):
            for ref in meta.get(key) or []:
                base = ref.split(".", 1)[0]
                if known_ids.get(base) != kind:
                    warnings.append(f"{where}/model.json: {key} enthält „{ref}“, das es im Repo nicht als {kind} gibt.")
        base_model = str(data.get("base_model_id") or "")
        if base_model in known_ids and known_ids[base_model] != "pipe":
            errors.append(f"{where}/model.json: base_model_id „{base_model}“ ist eine Erweiterung, aber keine Pipe.")

    return errors, warnings


def main() -> int:
    errors, warnings = check()
    for message in warnings:
        print(f"Hinweis: {message}")
    for message in errors:
        print(f"Fehler:  {message}")
    count = len(discover_extensions()) + len(discover_models())
    if errors:
        print(f"\n{len(errors)} Fehler, {len(warnings)} Hinweise in {count} Erweiterungen und Modellen.")
        return 1
    print(f"OK: {count} Erweiterungen und Modelle geprüft, {len(warnings)} Hinweise.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
