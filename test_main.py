from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_search_returns_results():
    r = client.get("/search?q=farming")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) > 0

def test_search_min_length():
    r = client.get("/search?q=a")
    assert r.status_code == 422  # too short

def test_code_lookup():
    r = client.get("/code/111110")
    assert r.status_code == 200

def test_code_invalid_format():
    r = client.get("/code/abc")
    assert r.status_code == 422  # fails regex

def test_code_not_found():
    r = client.get("/code/000000")
    assert r.status_code == 404