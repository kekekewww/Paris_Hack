"""Public read-only library endpoints never fetch user-supplied URLs."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "library-api.sqlite3"))
    monkeypatch.setenv("LLM_PROVIDER", "grounded_rules")
    with TestClient(create_app()) as result:
        yield result


def test_library_endpoint_returns_verified_classified_documents(client):
    response = client.get("/api/v1/library")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["categories"] and catalog["documents"]
    assert catalog["total"] == len(catalog["documents"])
    assert all(item["verification_status"] == "verified" for item in catalog["documents"])
    assert "no-store" in response.headers["cache-control"]


def test_library_search_and_unknown_category_do_not_invent_results(client):
    response = client.get("/api/v1/library", params={"query": "THIS_CODE_DOES_NOT_EXIST_999"})
    assert response.status_code == 200
    assert response.json()["documents"] == []
    assert response.json()["total"] == 0
    response = client.get("/api/v1/library", params={"category": "missing-category"})
    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_faq_has_official_sources_and_unknown_product_stays_unverified(client):
    response = client.get("/api/v1/faq")
    assert response.status_code == 200
    assert response.json() and all(item["sources"] for item in response.json())
    response = client.get("/api/v1/products/FAKE_PRODUCT_999")
    assert response.status_code == 200
    assert response.json()["verification_status"] != "verified"
    assert response.json()["versions"] == []


def test_library_rejects_oversized_input(client):
    assert client.get("/api/v1/library", params={"query": "x" * 201}).status_code == 422
    assert client.get("/api/v1/products/" + "x" * 81).status_code == 422
