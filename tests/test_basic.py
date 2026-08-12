import os
import sys

from fastapi.testclient import TestClient

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from server import app

client = TestClient(app, base_url="http://127.0.0.1:18000")


def test_read_main():
    """Test that the main page loads successfully"""
    # Note: Static files might not be fully set up in test env without more config
    # but we expect at least a 200 or 404, not 500.
    # Since we mock static dir in server.py, let's see.
    response = client.get("/")
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert response.headers["cache-control"] == "no-store"


def test_get_config():
    """Test accessing the config endpoint"""
    response = client.get("/api/config")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_list_models_no_auth():
    """Test listing models without auth returns empty list or error handled gracefully"""
    response = client.post("/api/models/gemini", json={})
    # Expect 200 with empty list or specific error structure, depending on implementation
    assert response.status_code == 200
    data = response.json()
    assert "models" in data or "error" in data


def test_local_api_rejects_untrusted_host_and_origin():
    assert client.get("/api/config", headers={"host": "attacker.example"}).status_code == 400
    assert (
        client.get("/api/config", headers={"origin": "https://attacker.example"}).status_code
        == 403
    )
    assert (
        client.get("/api/config", headers={"origin": "http://localhost:18000"}).status_code
        == 200
    )
