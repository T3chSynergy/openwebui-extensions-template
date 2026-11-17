"""Tests für scripts/: Prüfung, Platzhalter, Modell-Formulare und Export-Bereinigung."""

import json
import shutil

import pytest

import check
import owui_lib
from conftest import ROOT
from export import model_files


def test_repository_passes_check():
    errors, warnings = check.check()
    assert errors == []
    assert warnings == []


def copy_repo(tmp_path):
    for folder in ("tools", "functions", "models"):
        shutil.copytree(ROOT / folder, tmp_path / folder)
    return tmp_path


def test_check_finds_convention_violations(tmp_path):
    root = copy_repo(tmp_path)
    (root / "tools" / "Falscher-Name.py").write_text('"""\ntitle: X\n"""\nclass Tools:\n    pass\n', encoding="utf-8")
    (root / "functions" / "actions" / "doppelt.py").write_text(
        '"""\ntitle: D\nversion: 1.0\ndescription: d\nrequired_open_webui_version: 0.13.0\n"""\n'
        "from text_statistik import statistik\nclass Action:\n    pass\nclass Pipe:\n    pass\n",
        encoding="utf-8",
    )
    model = json.loads((root / "models/beispiel-assistent/model.json").read_text(encoding="utf-8"))
    model["user_id"] = "123"
    model["params"]["system"] = "inline"
    model["meta"]["toolIds"].append("gibt_es_nicht")
    (root / "models/beispiel-assistent/model.json").write_text(json.dumps(model), encoding="utf-8")

    errors, warnings = check.check(root)
    text = "\n".join(errors)
    assert "Falscher-Name" in text and "Kopfzeile „version:“ fehlt" in text
    assert "version „1.0“" in text
    assert "enthält zusätzlich Pipe" in text
    assert "importiert text_statistik" in text
    assert "instanzbezogene Felder entfernen: user_id" in text
    assert "params.system" in text
    assert any("gibt_es_nicht" in w for w in warnings)


def test_placeholders():
    env = {"A": "eins", "LEER": ""}
    assert owui_lib.resolve_placeholders("${A}-${B:-zwei}-${LEER:-drei}", env) == "eins-zwei-drei"
    assert owui_lib.resolve_placeholders({"x": ["${A}"]}, env) == {"x": ["eins"]}
    with pytest.raises(KeyError):
        owui_lib.resolve_placeholders("${FEHLT}", env)


def test_build_model_form_reads_prompt_and_defaults(monkeypatch):
    monkeypatch.delenv("BEISPIEL_BASISMODELL", raising=False)
    [model] = [m for m in owui_lib.discover_models() if m.id == "beispiel-assistent"]
    form = owui_lib.build_model_form(model)
    assert form["base_model_id"] == "echo"
    assert form["params"]["system"].startswith("Du bist ein Beispiel-Assistent")
    assert form["meta"]["filterIds"] == ["datum_einfuegen"]
    monkeypatch.setenv("BEISPIEL_BASISMODELL", "gpt-x")
    assert owui_lib.build_model_form(model)["base_model_id"] == "gpt-x"


def test_export_strips_instance_data():
    exported = {
        "id": "m", "name": "M", "base_model_id": "b", "user_id": "u", "access_grants": [{"x": 1}],
        "created_at": 1, "updated_at": 2, "version_id": "v", "is_active": True,
        "params": {"system": "Prompt  \n", "temperature": 0.1},
        "meta": {"profile_image_url": "/static/favicon.png", "description": "d", "knowledge": None, "tags": []},
    }
    model_json, prompt = model_files(exported)
    data = json.loads(model_json)
    assert set(data) == {"id", "name", "base_model_id", "params", "meta", "is_active"}
    assert data["params"] == {"temperature": 0.1}
    assert data["meta"] == {"description": "d"}
    assert prompt == "Prompt\n"


def test_frontmatter_parser_matches_open_webui():
    assert owui_lib.parse_frontmatter('"""\ntitle: A\nversion: 1.2.3\n"""\nx') == {"title": "A", "version": "1.2.3"}
    assert owui_lib.parse_frontmatter('# kein Kopf\n"""\ntitle: A\n"""') == {}


def test_export_keeps_placeholders_when_value_matches():
    local = {"id": "m", "name": "M", "base_model_id": "${BASIS:-echo}", "meta": {"x": "${X}"}, "params": {}}
    remote = {"id": "m", "name": "M", "base_model_id": "echo", "meta": {"x": "anders"}, "params": {}}
    data = json.loads(model_files(remote, local, environ={"X": "wert"})[0])
    assert data["base_model_id"] == "${BASIS:-echo}"   # passt -> Platzhalter bleibt
    assert data["meta"]["x"] == "anders"               # geändert -> echter Wert
