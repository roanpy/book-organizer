import os
import subprocess
import sys

from book_organizer import gemini_client


def test_startup_imports_do_not_load_grpc():
    script = """
import sys
import book_organizer.ai_engines
import book_organizer.routers.config
import book_organizer.routers.analysis
assert 'google.generativeai' not in sys.modules
assert 'grpc' not in sys.modules
assert 'grpc._cython.cygrpc' not in sys.modules
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.abspath("src")
    subprocess.run([sys.executable, "-c", script], env=env, check=True)


def test_configure_genai_uses_rest_transport(monkeypatch):
    class FakeGenai:
        def __init__(self):
            self.configure_kwargs = None

        def configure(self, **kwargs):
            self.configure_kwargs = kwargs

        def GenerativeModel(self, model_name):
            return {"model_name": model_name}

    fake_genai = FakeGenai()
    monkeypatch.setattr(gemini_client, "get_genai", lambda: fake_genai)

    model = gemini_client.create_gemini_model("api-key", "gemini-test")

    assert fake_genai.configure_kwargs == {
        "api_key": "api-key",
        "transport": "rest",
    }
    assert model == {"model_name": "gemini-test"}
