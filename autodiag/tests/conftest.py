import os
import sys
import importlib

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("GEMINI_RESEARCH_API_KEY", "")
os.environ.setdefault("OBD_MAC", "AA:BB:CC:11:22:33")

TEST_TOKEN = os.environ["API_TOKEN"]


@pytest.fixture
def app_module(tmp_path, monkeypatch):
    import app as _app
    importlib.reload(_app)

    monkeypatch.setattr(_app, "API_TOKEN", TEST_TOKEN)

    cars_file = tmp_path / "cars.json"
    cars_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(_app, "CARS_FILE", cars_file)
    monkeypatch.setattr(_app, "HISTORY_DIR", tmp_path)

    return _app


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


@pytest.fixture
def auth_headers():
    return {"X-API-Token": TEST_TOKEN}
