"""Phase 4 integration tests — exercise the FastAPI app end-to-end via TestClient.

Uses the `client` fixture which overrides the LLM dependency with a deterministic
mock. Embeddings + Chroma are real (sentence-transformers MiniLM) so retrieval
behaviour is exercised for real, not mocked.
"""

from __future__ import annotations

import json

from app.db.models import DocumentStatus


def _upload(client, pdf_path):
    with open(pdf_path, "rb") as f:
        return client.post("/documents", files={"file": (pdf_path.name, f, "application/pdf")})


def test_upload_then_query_returns_grounded_answer(client, sample_pdf, mock_llm):
    mock_llm.default = "Widget Pro costs 42 dollars."

    upload_resp = _upload(client, sample_pdf)
    assert upload_resp.status_code == 202, upload_resp.text
    doc = upload_resp.json()
    assert doc["status"] in {DocumentStatus.PENDING.value, DocumentStatus.READY.value}

    # BackgroundTasks complete before the TestClient call returns — status should be ready.
    status_resp = client.get(f"/documents/{doc['id']}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == DocumentStatus.READY.value
    assert status_resp.json()["chunk_count"] > 0

    query_resp = client.post("/query", json={"question": "How much is Widget Pro?", "k": 3})
    assert query_resp.status_code == 200, query_resp.text
    body = query_resp.json()
    assert body["answer"] == "Widget Pro costs 42 dollars."
    assert len(body["sources"]) >= 1
    assert body["latency_ms"] >= 0
    assert body["llm_provider"] == "mock"


def test_upload_corrupt_pdf_marks_failed(client, corrupt_pdf):
    resp = _upload(client, corrupt_pdf)
    assert resp.status_code == 202
    doc_id = resp.json()["id"]

    status = client.get(f"/documents/{doc_id}").json()
    assert status["status"] == DocumentStatus.FAILED.value
    assert status["error_message"]


def test_query_with_no_documents_returns_idk(client, mock_llm):
    from app.core.generation import IDK_RESPONSE

    mock_llm.default = IDK_RESPONSE
    resp = client.post("/query", json={"question": "What is the meaning of life?", "k": 4})

    assert resp.status_code == 200
    assert resp.json()["answer"] == IDK_RESPONSE
    assert resp.json()["sources"] == []


def test_health_endpoint_reports_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "ok"
    assert body["chroma"] == "ok"


def test_metrics_endpoint_returns_prometheus_format(client, sample_pdf):
    # Generate a handful of events so histograms/counters have something to expose.
    _upload(client, sample_pdf)
    client.post("/query", json={"question": "Anything?", "k": 2})

    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "documents_ingested_total" in body
    assert "queries_total" in body
    assert "query_duration_seconds" in body
    assert body.startswith("# HELP") or "# HELP" in body  # Prometheus exposition format


def test_evaluate_endpoint_runs_over_tiny_dataset(client, sample_pdf, mock_llm, tmp_path, monkeypatch):
    """Swap in a tiny eval dataset so the endpoint runs quickly without hitting the full 20-item set."""
    # Write a two-item dataset.
    dataset = [
        {
            "question": "What does Acme make?",
            "expected_answer": "widgets",
            "expected_source_keywords": ["widget"],
            "source_document": "acme_sample.pdf",
        },
        {
            "question": "What is the office dog's name?",
            "expected_answer": "Pixel",
            "expected_source_keywords": ["Pixel"],
            "source_document": "acme_sample.pdf",
        },
    ]
    dataset_path = tmp_path / "eval_dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    import app.api.evaluate as evaluate_module

    monkeypatch.setattr(evaluate_module, "DEFAULT_DATASET", dataset_path)
    monkeypatch.setattr(evaluate_module, "RESULTS_DIR", tmp_path / "results")

    # Seed Chroma so retrieval has something to work with.
    upload = _upload(client, sample_pdf)
    assert upload.status_code == 202

    # The mock returns a number when the prompt looks like a faithfulness prompt,
    # otherwise a plausible answer sentence.
    def _responder(prompt: str) -> str:
        if "SCORE:" in prompt:
            return "0.9"
        return "Acme makes widgets and the office dog is Pixel."

    mock_llm.responder = _responder

    resp = client.get("/evaluate?k=2")
    assert resp.status_code == 200, resp.text
    report = resp.json()
    assert report["dataset_size"] == 2
    assert 0.0 <= report["mean_faithfulness"] <= 1.0
    assert 0.0 <= report["mean_retrieval_precision"] <= 1.0
    assert report["latency"]["count"] == 2
    assert report["llm_provider"] == "mock"
    # Results file persisted.
    results_files = list((tmp_path / "results").glob("*.json"))
    assert len(results_files) == 1
