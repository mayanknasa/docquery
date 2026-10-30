import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.chunking import chunk_text

SAMPLE = (
    "FastAPI is a modern Python web framework for building APIs. "
    "Terraform is an infrastructure as code tool used to provision cloud resources. "
    "Amazon S3 stores objects such as files, and DynamoDB is a key value database. "
) * 6


def make_client(**overrides):
    settings = Settings(storage_backend="local", llm_provider="mock", chunk_size=200, chunk_overlap=30, **overrides)
    return TestClient(create_app(settings))


def test_chunking_overlap_and_progress():
    chunks = chunk_text(SAMPLE, size=200, overlap=30)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    assert chunk_text("   ", 200, 30) == []


def test_chunking_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("hello world", size=10, overlap=10)


def test_health():
    with make_client() as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_upload_and_ask_returns_sources():
    with make_client() as client:
        up = client.post("/documents", files={"file": ("notes.txt", SAMPLE.encode(), "text/plain")})
        assert up.status_code == 201
        doc_id = up.json()["doc_id"]
        assert up.json()["num_chunks"] > 1

        ask = client.post(f"/documents/{doc_id}/ask", json={"question": "What is Terraform used for?", "top_k": 2})
        assert ask.status_code == 200
        body = ask.json()
        assert len(body["sources"]) == 2
        assert "Terraform" in body["sources"][0]["snippet"]


def test_unknown_document_is_404():
    with make_client() as client:
        assert client.post("/documents/nope/ask", json={"question": "anything here"}).status_code == 404


def test_empty_file_is_422():
    with make_client() as client:
        resp = client.post("/documents", files={"file": ("empty.txt", b"   ", "text/plain")})
        assert resp.status_code == 422


def test_api_key_enforced():
    with make_client(api_key="secret") as client:
        files = {"file": ("a.txt", SAMPLE.encode(), "text/plain")}
        assert client.post("/documents", files=files).status_code == 401
        ok = client.post("/documents", files=files, headers={"X-API-Key": "secret"})
        assert ok.status_code == 201
