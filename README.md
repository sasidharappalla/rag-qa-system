# RAG Document Q&A System

A production-style Retrieval-Augmented Generation service: upload a PDF, ask a question, get an answer grounded in the retrieved chunks with sources and latency returned alongside.

## Why this exists

This is a portfolio project. The goal is not to ship a novel paper — it's to demonstrate that every technology on the AI/ML Engineer checklist (LangChain, vector DBs, embeddings, RAG, FastAPI inference serving, prompt engineering, evaluation) is genuinely represented in working code, with tests, metrics, and a defensible set of design decisions.

---

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP
┌──────▼──────────────────────────────────────────┐
│  FastAPI Application                            │
│                                                 │
│  POST /documents      (ingest PDF)              │
│  GET  /documents      (list uploaded docs)      │
│  GET  /documents/{id} (status)                  │
│  POST /query          (ask a question)          │
│  GET  /evaluate       (run eval suite)          │
│  GET  /metrics        (Prometheus)              │
│  GET  /health         (liveness)                │
└──────┬──────────────────────────────────────────┘
       │
       ├─────────────────────┐
       │                     │
┌──────▼──────┐      ┌───────▼────────┐
│  ChromaDB   │      │  PostgreSQL    │
│  (vectors)  │      │  (metadata)    │
└─────────────┘      └────────────────┘
       ▲
       │
┌──────┴──────────────────────────────┐
│  Ingestion Pipeline                  │
│  PDF → Text → Chunks → Embeddings    │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  Generation Pipeline                  │
│  Question → Embed → Retrieve → LLM    │
└──────────────────────────────────────┘
```

**Stack:** Python 3.11, FastAPI, LangChain (orchestration), ChromaDB (vectors), sentence-transformers `all-MiniLM-L6-v2` (embeddings), PostgreSQL + SQLAlchemy (metadata), Pydantic v2, Prometheus, Docker Compose, pytest. The LLM provider is pluggable: ship with OpenAI or Anthropic, pick via env var.

---

## Quickstart

```bash
cp .env.example .env
# edit .env to set LLM_PROVIDER and the matching API key
docker compose up --build
```

Then, from another terminal:

```bash
# Generate the sample PDFs committed under data/sample/
docker compose exec app python -m scripts.generate_samples

# Upload a sample
curl -F "file=@data/sample/sample1_acme_handbook.pdf" http://localhost:8000/documents

# Ask a question
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Acme Robotics mission?", "k": 4}' | jq
```

### Without Docker

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"

# Sample PDFs + eval dataset
python -m scripts.generate_samples

# Need a local Postgres at the DATABASE_URL in .env, or override to sqlite:
export DATABASE_URL="sqlite:///./dev.db"

uvicorn app.main:app --reload
```

---

## API Reference

All routes are defined in `app/api/`. Request and response shapes live in `app/schemas/`.

### `POST /documents`

Upload a PDF. Returns 202 immediately — ingestion runs in the background. Poll `GET /documents/{id}` for status.

Request (multipart):
```bash
curl -F "file=@sample.pdf" http://localhost:8000/documents
```

Response (`202 Accepted`):
```json
{
  "id": 1,
  "filename": "sample.pdf",
  "upload_time": "2026-04-17T23:45:12.204Z",
  "status": "pending",
  "chunk_count": 0,
  "error_message": null
}
```

### `GET /documents`

List uploaded documents newest-first.

### `GET /documents/{id}`

Return a single document's row. `status` transitions `pending` → `processing` → (`ready` | `failed`).

### `POST /query`

Request:
```json
{ "question": "What benefits does Acme offer?", "k": 4 }
```

Response:
```json
{
  "answer": "Full-time employees receive medical, dental and vision insurance with 90 percent of premiums paid by Acme...",
  "sources": [
    {
      "chunk_id": "doc_1_chunk_1",
      "text": "Benefits. Full-time employees receive medical, dental, and vision insurance with 90% of premiums paid by Acme...",
      "score": 0.873,
      "document_id": 1,
      "chunk_index": 1,
      "source_page": 1,
      "source_filename": "sample1_acme_handbook.pdf"
    }
  ],
  "latency_ms": 812,
  "llm_provider": "anthropic"
}
```

If the retrieved context doesn't contain the answer, the response is exactly: `"I don't know based on the provided documents."` — this is enforced by the prompt, see `app/core/generation.py`.

### `GET /evaluate?k=4`

Runs the evaluation suite over `eval/dataset.json` and returns aggregate + per-question results. Writes a timestamped JSON file to `eval/results/`.

### `GET /health`

```json
{ "status": "ok", "postgres": "ok", "chroma": "ok" }
```

### `GET /metrics`

Prometheus exposition format. Counters: `documents_ingested_total`, `documents_failed_total`, `queries_total`, `queries_failed_total`. Histograms: `ingestion_duration_seconds`, `query_duration_seconds`, `retrieval_duration_seconds`, `generation_duration_seconds`.

---

## Evaluation

The eval suite scores three things:

- **Faithfulness** — LLM-as-judge, in [0, 1], where 1.0 means every factual claim in the answer is directly supported by the retrieved context. This is the industry-standard approach today and it is also known to be biased (self-preference, position bias, score drift). The honest answer to "how do you know your evaluator is correct?" is: *I don't, fully — it's the best available proxy without human labels.* In this project the same provider is used as both generator and judge, which amplifies self-preference; in a richer setup you'd use a different provider as judge.
- **Retrieval precision@k** — fraction of retrieved chunks that contain at least one expected keyword for that question. Deterministic and transparent; the code is ~10 lines in `app/core/evaluation.py`.
- **Latency** — p50, p95, p99, and mean over the eval run.

### Running it

```bash
curl http://localhost:8000/evaluate | jq
```

Sample output (shape):

```json
{
  "dataset_size": 20,
  "mean_faithfulness": 0.82,
  "mean_retrieval_precision": 0.71,
  "latency": { "p50_ms": 940, "p95_ms": 1780, "p99_ms": 2050, "mean_ms": 1012.5, "count": 20 },
  "items": [ { "question": "...", "faithfulness": 0.9, "retrieval_precision": 0.75, "...": "..." } ],
  "llm_provider": "anthropic",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

Reasonable targets on the sample dataset: `mean_faithfulness > 0.7`, `mean_retrieval_precision > 0.6`.

---

## Key Design Decisions

**Why local embeddings (`all-MiniLM-L6-v2`) and not OpenAI embeddings?**
This project has to run on any laptop without a paid API key for dev work. MiniLM is small, fast on CPU, and a reasonable default. Swapping in `OpenAIEmbeddings` is a one-line change in `app/core/vectorstore.py` — but you must not mix embedders in one deployment, because dimension mismatch silently corrupts retrieval.

**Why Chroma and not Pinecone/Weaviate?**
Local-first. Works offline. No account setup. The query interface (`similarity_search_with_relevance_scores`) is broadly the same across hosted alternatives, so the skill transfers.

**Why both LangChain and raw LLM SDKs?**
LangChain is used where it adds value: document loaders, text splitters, vector store abstraction. The actual LLM call goes through the raw SDK (OpenAI / Anthropic). LangChain's chain abstractions are leaky — extra debugging surface for questionable reuse — so we stop at the retriever and write the prompt and provider call ourselves.

**Why a `LLMProvider` abstract class?**
Two providers, one interface, chosen by env var. Makes it trivial to run with whichever key the user has, and demonstrates the kind of abstraction interview questions poke at. See `app/llm/base.py`.

**Why persist query logs to Postgres?**
Demonstrates thinking about observability and auditability beyond metrics — which queries were asked, what answers were given, which chunks were used. In a real system you'd also want this for retraining, cost attribution, and user feedback loops.

**Why LLM-as-judge for faithfulness?**
Industry standard; cheap; reproducible. The well-documented caveats (self-preference, position bias, score drift) are in the bullet above. The goal is defensibility in an interview — not pretending the number is gospel.

---

## Project Layout

```
app/
  main.py                   FastAPI wiring (middleware + routers + lifespan)
  config.py                 Pydantic settings, env-driven
  api/                      HTTP routes (one module per resource)
  core/                     RAG pipeline: ingestion, retrieval, generation, evaluation + vectorstore helper
  llm/                      LLMProvider ABC + OpenAI/Anthropic implementations
  db/                       SQLAlchemy models + session factory
  schemas/                  Pydantic request/response models
  observability/            Prometheus metrics + structured JSON logging
tests/                      conftest + 5 test modules (ingestion, retrieval, generation, evaluation, api)
eval/
  dataset.json              20 Q&A pairs over the sample PDFs
  results/                  gitignored; one JSON per eval run
scripts/
  generate_samples.py       Creates the sample PDFs under data/sample/
data/
  sample/                   Regenerated by the script above (not committed)
  uploads/                  User uploads at runtime (gitignored)
```

---

## Running the Tests

```bash
pytest tests/ -v           # all tests
pytest tests/test_api.py   # just integration tests
ruff check app/ tests/
mypy app/
```

The first test run downloads `all-MiniLM-L6-v2` (~80 MB) and caches it in `~/.cache/huggingface/`. Subsequent runs are fast. No network calls to any LLM happen in tests — the provider is mocked by `tests/conftest.py::MockLLMProvider`.

---

## Future Work

Given another week, in rough priority order:

1. **Streaming answers.** Current `/query` blocks until the LLM finishes. Stream tokens via Server-Sent Events so the client sees output as it generates.
2. **Multi-document queries.** Add a `document_ids` filter to `/query` so a user can constrain search to specific uploads.
3. **Better chunking for tables.** `RecursiveCharacterTextSplitter` treats tables as prose. Add an `UnstructuredPDFLoader` fallback + a table-aware splitter for known table-heavy PDFs.
4. **User auth + per-user document scoping.** Right now anyone with network access to the API can query every document. Add OAuth + row-level filtering.
5. **Re-rank step.** A cross-encoder re-rank on the top-k chunks before passing to the LLM usually lifts faithfulness by 5–10 points.
6. **Hybrid search.** Blend BM25 with vector similarity for queries with rare proper nouns.
7. **Evaluation against a human-labeled set.** Replace the LLM-as-judge baseline with a small human-annotated set to calibrate the judge.
