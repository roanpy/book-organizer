from fastapi.testclient import TestClient

import book_organizer.routers.local as local_router
from server import app

client = TestClient(app)


def test_local_suggest_directories_returns_structured_response(monkeypatch):
    monkeypatch.setattr(
        local_router,
        "load_config",
        lambda: {"target_dir": "/tmp/books"},
    )
    monkeypatch.setattr(
        local_router,
        "get_available_target_directories",
        lambda target_dir: ["01_思维", "09_教育/04_学习成长"],
    )
    monkeypatch.setattr(
        local_router,
        "local_suggest_directories",
        lambda title, author, available_dirs: [available_dirs[0]],
    )

    response = client.post(
        "/api/local/suggest-directories",
        json={"title": "测试图书", "author": ""},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "suggestions": ["01_思维"]}


def test_local_categorize_accepts_frontend_tags_list():
    response = client.post(
        "/api/local/categorize",
        json={"title": "Designing Data-Intensive Applications", "tags": ["database"]},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
