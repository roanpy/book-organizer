import sys
from types import SimpleNamespace

from book_organizer.gemini_client import shutdown_gemini_clients


def test_shutdown_closes_loaded_gemini_clients_without_importing_sdk(monkeypatch):
    closed = []
    client = SimpleNamespace(close=lambda: closed.append(True))
    module = SimpleNamespace(_client_manager=SimpleNamespace(clients={"rest": client}))
    monkeypatch.setitem(sys.modules, "google.generativeai.client", module)

    shutdown_gemini_clients()

    assert closed == [True]
    assert module._client_manager.clients == {}
