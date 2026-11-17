"""Gemeinsame Hilfsfunktionen für check.py, deploy.py und export.py.

Nur Standardbibliothek, damit die Skripte ohne Installation laufen.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Ordner -> (Art in Open WebUI, erwartete Klasse)
KINDS = {
    "tools": ("tool", "Tools"),
    "functions/actions": ("action", "Action"),
    "functions/filters": ("filter", "Filter"),
    "functions/pipes": ("pipe", "Pipe"),
}
PLUGIN_CLASSES = {"Tools", "Action", "Filter", "Pipe"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_FRONTMATTER_LINE = re.compile(r"^\s*([a-z_]+):\s*(.*)\s*$", re.IGNORECASE)
_ENV_PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


# --- Erweiterungen im Repo ------------------------------------------------------

@dataclass
class Extension:
    kind: str  # tool, action, filter, pipe
    id: str
    path: Path
    frontmatter: dict = field(default_factory=dict)

    @property
    def content(self) -> str:
        return self.path.read_text(encoding="utf-8")

    @property
    def name(self) -> str:
        return self.frontmatter.get("title") or self.id

    @property
    def is_function(self) -> bool:
        return self.kind != "tool"

    @property
    def relpath(self) -> str:
        return self.path.relative_to(ROOT).as_posix()


@dataclass
class ModelDefinition:
    id: str
    folder: Path

    @property
    def json_path(self) -> Path:
        return self.folder / "model.json"

    @property
    def prompt_path(self) -> Path:
        return self.folder / "system-prompt.md"

    @property
    def relpath(self) -> str:
        return self.folder.relative_to(ROOT).as_posix()

    def load(self) -> dict:
        return json.loads(self.json_path.read_text(encoding="utf-8"))


def parse_frontmatter(content: str) -> dict:
    """Liest den Kopf-Docstring so, wie Open WebUI ihn liest."""
    lines = content.splitlines()
    if not lines or lines[0].strip() != '"""':
        return {}
    result = {}
    for line in lines[1:]:
        if '"""' in line:
            break
        match = _FRONTMATTER_LINE.match(line)
        if match:
            result[match.group(1).strip()] = match.group(2).strip()
    return result


def discover_extensions(root: Path = ROOT) -> list[Extension]:
    found = []
    for folder, (kind, _) in KINDS.items():
        for path in sorted((root / folder).glob("*.py")):
            if path.name.startswith("_"):
                continue
            content = path.read_text(encoding="utf-8")
            found.append(Extension(kind, path.stem, path, parse_frontmatter(content)))
    return found


def discover_models(root: Path = ROOT) -> list[ModelDefinition]:
    base = root / "models"
    if not base.is_dir():
        return []
    return [ModelDefinition(p.name, p) for p in sorted(base.iterdir()) if (p / "model.json").is_file()]


def resolve_placeholders(value, environ=None):
    """Ersetzt ${VAR} und ${VAR:-Standard} in allen Zeichenketten."""
    environ = os.environ if environ is None else environ
    if isinstance(value, str):
        def substitute(match):
            name, default = match.group(1), match.group(2)
            if name in environ and environ[name] != "":
                return environ[name]
            if default is not None:
                return default
            raise KeyError(f"Umgebungsvariable {name} ist nicht gesetzt und hat keinen Standardwert")
        return _ENV_PLACEHOLDER.sub(substitute, value)
    if isinstance(value, list):
        return [resolve_placeholders(v, environ) for v in value]
    if isinstance(value, dict):
        return {k: resolve_placeholders(v, environ) for k, v in value.items()}
    return value


def build_model_form(model: ModelDefinition, environ=None) -> dict:
    """model.json + system-prompt.md -> Formular für die Open-WebUI-API."""
    data = resolve_placeholders(model.load(), environ)
    params = dict(data.get("params") or {})
    if model.prompt_path.is_file():
        params["system"] = model.prompt_path.read_text(encoding="utf-8").rstrip() + "\n"
    return {
        "id": data["id"],
        "name": data["name"],
        "base_model_id": data.get("base_model_id"),
        "meta": data.get("meta") or {},
        "params": params,
        "is_active": data.get("is_active", True),
    }


# --- Konfiguration und Git ---------------------------------------------------------

def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Liest einfache KEY=VALUE-Zeilen; vorhandene Umgebungsvariablen gewinnen."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def git_revision() -> str:
    try:
        revision = subprocess.run(
            ["git", "describe", "--always", "--dirty"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        return revision or "unbekannt"
    except (OSError, subprocess.CalledProcessError):
        return "unbekannt"


def git_has_local_changes(path: Path) -> bool:
    try:
        output = subprocess.run(
            ["git", "status", "--porcelain", "--", str(path)], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        return any(line[:2].strip() and not line.startswith("??") for line in output.splitlines())
    except (OSError, subprocess.CalledProcessError):
        return False


# --- Open-WebUI-API ----------------------------------------------------------------

class ApiError(RuntimeError):
    def __init__(self, status: int, path: str, detail: str):
        super().__init__(f"HTTP {status} bei {path}: {detail}")
        self.status = status


class OpenWebUI:
    def __init__(self, url: str, api_key: str, timeout: float = 60):
        if not url:
            raise SystemExit("OWUI_URL fehlt (Umgebungsvariable, .env oder --url).")
        if not api_key:
            raise SystemExit("OWUI_API_KEY fehlt (Umgebungsvariable, .env oder --key).")
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, method: str, path: str, payload=None, params: dict | None = None):
        url = self.url + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            try:
                detail = json.loads(detail).get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise ApiError(error.code, path, str(detail)[:500]) from None
        return json.loads(body) if body else None

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def post(self, path, payload=None):
        return self.request("POST", path, payload if payload is not None else {})

    def get_or_none(self, path, params=None):
        try:
            result = self.get(path, params)
        except ApiError as error:
            if error.status in (401, 404):
                return None
            raise
        return result or None


def signin_without_auth(url: str) -> str:
    """Token einer Instanz mit WEBUI_AUTH=False holen (nur für lokale Tests)."""
    request = urllib.request.Request(
        url.rstrip("/") + "/api/v1/auths/signin",
        data=json.dumps({"email": "", "password": ""}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())["token"]

