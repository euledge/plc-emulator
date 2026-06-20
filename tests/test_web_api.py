from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from src.web.app import create_app
from src.web.api_routes import SCRIPTS_DIR


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_get_config(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["protocol"] == "3E"
    assert data["port"] == 5000


def test_put_config(client):
    resp = client.put("/api/config", json={"protocol": "4E"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["protocol"] == "4E"


def test_get_devices(client):
    resp = client.get("/api/devices/D?start=0&count=5")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["values"]) == 5


def test_put_device(client):
    resp = client.put("/api/devices/D/100", json={"value": 1234})
    assert resp.status_code == 200
    resp = client.get("/api/devices/D?start=100&count=1")
    assert resp.json()["values"][0] == 1234


def test_latency_stats(client):
    resp = client.get("/api/latency/stats")
    assert resp.status_code == 200


def test_put_latency_config(client):
    resp = client.put("/api/latency/config", json={"mode": "fixed", "params": {"delay_ms": 50}})
    assert resp.status_code == 200


def test_get_scripts(client):
    resp = client.get("/api/scripts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_i18n(client):
    resp = client.get("/api/i18n/ja")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_save_and_load_script(client):
    test_yaml = "- type: periodic\n  interval_ms: 500\n  actions:\n    - target: D300\n      value: 42\n"
    resp = client.put("/api/scripts/test_script.yaml", json={"content": test_yaml})
    assert resp.status_code == 200
    resp = client.get("/api/scripts/test_script.yaml")
    assert resp.status_code == 200
    assert resp.json()["content"] == test_yaml
    (SCRIPTS_DIR / "test_script.yaml").unlink(missing_ok=True)


def test_start_script_nonexistent(client):
    resp = client.post("/api/scripts/nonexistent.yaml/start")
    assert resp.status_code == 404


def test_save_and_load_state(client):
    client.put("/api/devices/D/100", json={"value": 42})
    resp = client.post("/api/save", json={"name": "test_api.json"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    client.put("/api/devices/D/100", json={"value": 0})
    resp = client.post("/api/load", json={"name": "test_api.json"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    resp = client.get("/api/devices/D?start=100&count=1")
    assert resp.json()["values"][0] == 42


def test_load_nonexistent(client):
    resp = client.post("/api/load", json={"name": "no_such_file.json"})
    assert resp.status_code == 404



