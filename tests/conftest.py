"""Hilfen für die Tests: Erweiterungen direkt aus ihren Dateien laden.

Open WebUI lädt jede Datei einzeln als Modul. Die Tests machen es genauso,
damit ein versehentlicher Import aus dem Repo sofort auffällt.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def load_extension(relpath: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(f"ext_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Emitter:
    """Sammelt, was eine Erweiterung über __event_emitter__ sendet."""

    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)

    def of_type(self, kind):
        return [e for e in self.events if e.get("type") == kind]


@pytest.fixture
def emitter():
    return Emitter()
