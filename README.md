<div align="center">

# RAG Document Q&A System

### Ask your PDFs anything. Get answers grounded in citations, not hallucinations.

A production-style Retrieval-Augmented Generation service that ingests PDF documents, embeds them into a vector store, and answers questions with verifiable sources — wrapped in a FastAPI inference layer, measured by a built-in evaluation suite, and deployable in one command.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-1.2-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.5-FF6B6B?style=for-the-badge)](https://www.trychroma.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

[![Tests](https://img.shields.io/badge/tests-31%20passing-brightgreen?style=flat-square)]()
[![Lint](https://img.shields.io/badge/lint-ruff%20clean-000000?style=flat-square&logo=ruff)]()
[![Coverage](https://img.shields.io/badge/coverage-integration%20%2B%20unit-blue?style=flat-square)]()
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)]()

[Features](#-highlights) · [Architecture](#-architecture) · [Quick Start](#-quick-start) · [API](#-api-reference) · [Evaluation](#-evaluation) · [Design Decisions](#-design-decisions) · [Roadmap](#-roadmap)

</div>

---

## What it looks like

```
$ curl -F "file=@acme_handbook.pdf" http://localhost:8000/documents
{ "id": 1, "filename": "acme_handbook.pdf", "status": "processing", ... }

$ curl -X POST http://localhost:8000/query \
       -H "Content-Type: application/json" \
       -d '{"question": "What percentage of insurance premiums does Acme pay?", "k": 4}'

{
  "answer": "Acme pays 90% of medical, dental, and vision insurance premiums for full-time employees.",
  "sources": [
    {
      "chunk_id": "doc_1_chunk_2",
      "text": "Benefits. Full-time employees receive medical, dental, and vision insurance with 90% of premiums paid by Acme...",
      "score": 0.873,
      "source_page": 1,
      "source_filename": "acme_handbook.pdf"
    }
  ],
  "latency_ms": 812,
  "llm_provider": "anthropic"
}
```

Every answer ships with the chunks it was grounded in. No black box — the user can verify.

---

## Highlights

- **Retrieval with citations.** Every answer returns the exact chunks, scores, page numbers, and source filenames it was grounded in. Zero hallucinations: if context doesn't support an answer, the system replies *"I don't know based on the provided documents."*
- **Pluggable LLM providers.** One abstract interface, two implementations (OpenAI + Anthropic), selected by env var. Swap providers without touching a line of pipeline code.
- **Built-in evaluation suite.** LLM-as-judge faithfulness scoring, keyword-based retrieval precision, and p50/p95/p99 latency — all over a curated 20-item Q&A dataset. Results persist as timestamped JSON.
- **Production observability.** Prometheus metrics at `/metrics` (counters + histograms for every stage), structured JSON access logs with request IDs, health probes for Postgres + ChromaDB.
- **Background ingestion.** PDFs upload in one request, chunk and embed asynchronously, and clients poll for `ready` status. No request blocks on slow PDF parsing.
- **One command to run.** `docker compose up --build` brings up the entire stack — Postgres, the API, and the vector store — with zero manual setup.
- **Rigorously tested.** 31 tests across unit (ingestion, retrieval, generation, evaluation scoring) and integration (full HTTP request/response cycle) layers. Embeddings and Chroma are exercised for real; LLM calls are mocked.

---

## Architecture

```
              ┌─────────────────────┐
              │       Client        │
              └──────────┬──────────┘
                         │ HTTP/JSON
  ┌──────────────────────▼──────────────────────────────┐
  │                FastAPI Application                  │
  │                                                     │
  │  POST /documents  ─►  upload  (background ingest)   │
  │  GET  /documents  ─►  list / status                 │
  │  POST /query      ─►  retrieve + generate + log     │
  │  GET  /evaluate   ─►  run eval suite → metrics JSON │
  │  GET  /metrics    ─►  Prometheus exposition         │
  │  GET  /health     ─►  liveness + dependency probes  │
  │                                                     │
  │  middleware: request-ID + structured JSON access log│
  └─────┬──────────────────┬──────────────────┬─────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
│   ChromaDB    │  │   PostgreSQL    │  │   LLM Provider   │
│ vector chunks │  │ doc + query     │  │ OpenAI | Anthropic│
│ + metadata    │  │ metadata        │  │ (pluggable)       │
└───────▲───────┘  └─────────────────┘  └──────────────────┘
        │
        │
┌───────┴──────────────────────────────────────┐
│  Ingestion Pipeline                           │
│  PDF → PyPDFLoader → RecursiveSplitter(1k/200)│
│      → sentence-transformers → Chroma         │
└───────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│  Generation Pipeline                          │
│  Q → embed → top-k similarity → prompt → LLM  │
└──────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer             | Technology                                     | Why it's here                                                        |
| ----------------- | ---------------------------------------------- | -------------------------------------------------------------------- |
| **API**           | FastAPI + Pydantic v2                          | Async-first, auto-generated OpenAPI docs, typed request/response     |
| **Orchestration** | LangChain 1.2                                  | Document loaders, text splitters, vector-store abstraction           |
| **Vector store**  | ChromaDB (cosine distance, persisted locally)  | Runs in-process, no cloud setup, same API as hosted alternatives     |
| **Embeddings**    | sentence-transformers `all-MiniLM-L6-v2`       | Local, CPU-friendly, works offline — no paid key needed for dev      |
| **LLM**           | OpenAI GPT-4o-mini · Anthropic Claude Haiku 4.5 | Raw SDK calls behind a thin `LLMProvider` ABC, switched by env var   |
| **Metadata DB**   | PostgreSQL 16 + SQLAlchemy 2.0                 | Durable audit log of uploads and queries for observability           |
| **Resilience**    | Tenacity                                        | Exponential backoff on provider rate-limits (eval hits 429s otherwise) |
| **Metrics**       | Prometheus client                              | Counters + histograms, scraped at `/metrics`                         |
| **Logging**       | Stdlib logging + custom JSON formatter         | Structured, request-scoped, aggregator-friendly                      |
| **Containers**    | Docker + docker-compose                        | One-command local stack (Postgres + API + vector store)              |
| **Testing**       | pytest · pytest-asyncio · httpx (TestClient)   | Real ingestion path + mocked LLM = fast and deterministic            |
| **Quality**       | ruff · mypy                                    | Format, lint, and type-check the whole codebase                      |

---

## Quick Start

### With Docker (recommended)

```bash
git clone https://github.com/sasidharappalla/rag-qa-system.git
cd rag-qa-system

cp .env.example .env
# edit .env — set LLM_PROVIDER and the matching API key

docker compose up --build
```

Open **http://localhost:8000/docs** for the interactive OpenAPI UI.

### Without Docker

```bash
python -m venv .venv
# Linux/Mac:  source .venv/bin/activate
# Windows:    .venv\Scripts\activate
pip install -e ".[dev]"

# Generate sample PDFs
python -m scripts.generate_samples

# Use SQLite locally instead of Postgres
export DATABASE_URL="sqlite:///./dev.db"

uvicorn app.main:app --reload
```

### Try it

```bash
# Upload a sample document
curl -F "file=@data/sample/sample1_acme_handbook.pdf" http://localhost:8000/documents

# Ask a grounded question
curl -X POST http://localhost:8000/query \
     -H "Content-Type: application/json" \
     -d '{"question": "What is Acme Robotics mission?", "k": 4}' | jq

# Run the evaluation suite
curl http://localhost:8000/evaluate | jq
```

---

## API Reference

| Method | Endpoint              | Purpose                                                 |
| ------ | --------------------- | ------------------------------------------------------- |
| POST   | `/documents`          | Upload a PDF. Returns `202` immediately; ingests in BG. |
| GET    | `/documents`          | List all uploaded documents with status.                |
| GET    | `/documents/{id}`     | Single-document status. Poll until `ready` or `failed`. |
| POST   | `/query`              | Ask a question. Returns answer + cited source chunks.   |
| GET    | `/evaluate`           | Run the full eval suite, persist results, return report.|
| GET    | `/health`             | Liveness + Postgres + ChromaDB dependency probes.        |
| GET    | `/metrics`            | Prometheus exposition: counters + stage-latency histograms. |
| GET    | `/docs`               | Interactive Swagger UI (auto-generated).                |

**Grounding guarantee.** The `POST /query` prompt enforces:

> *"Answer ONLY from the provided context. If the context does not contain the answer, reply exactly: 'I don't know based on the provided documents.' Do not speculate, do not use outside knowledge."*

---

## Evaluation

Three metrics, all visible in the returned JSON and persisted under `eval/results/<timestamp>.json`:

| Metric                    | What it measures                                                              | How it works                                                                               |
| ------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| **Faithfulness** (0–1)    | Is every claim in the answer supported by the retrieved chunks?              | LLM-as-judge. Pragmatic and reproducible; caveats (self-preference, position bias) documented. |
| **Retrieval precision@k** | Did retrieval actually pull chunks containing the expected keywords?          | Deterministic keyword match — transparent, ~10 lines, easy to audit.                       |
| **Latency** (p50/p95/p99) | Real end-to-end query latency distribution                                    | Nearest-rank percentiles over every eval query.                                            |

Sample shape returned by `GET /evaluate`:

```json
{
  "dataset_size": 20,
  "mean_faithfulness": 0.82,
  "mean_retrieval_precision": 0.71,
  "latency": { "p50_ms": 940, "p95_ms": 1780, "p99_ms": 2050, "mean_ms": 1012.5, "count": 20 },
  "llm_provider": "anthropic",
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
}
```

Targets on the sample dataset: `mean_faithfulness > 0.7`, `mean_retrieval_precision > 0.6`.

**Why LLM-as-judge?** It's the industry-standard approach for faithfulness in 2025 and it's cheap, reproducible, and repeatable. It is also known to be biased — self-preference, position bias, score drift — and this project documents that honestly rather than pretending the number is ground truth. Swap the judge for a different provider to reduce self-preference; replace with a human-labeled set when available.

---

## Project Structure

```
rag-qa-system/
├── app/
│   ├── main.py                   FastAPI wiring (middleware + routers + lifespan)
│   ├── config.py                 Pydantic settings driven by .env
│   ├── api/                      HTTP routes (one file per resource)
│   │   ├── documents.py          upload / list / status with BackgroundTasks
│   │   ├── query.py              grounded Q&A + QueryLog persistence
│   │   ├── evaluate.py           full eval suite + results writer
│   │   └── health.py             liveness + dependency probes
│   ├── core/                     RAG pipeline
│   │   ├── vectorstore.py        cached embedder + Chroma factory
│   │   ├── ingestion.py          PDF → chunks → Chroma with status machine
│   │   ├── retrieval.py          similarity search + score normalization
│   │   ├── generation.py         grounded prompt + LLM call
│   │   └── evaluation.py         faithfulness + precision + latency
│   ├── llm/
│   │   ├── base.py               LLMProvider ABC + env-driven factory
│   │   ├── openai_provider.py    OpenAI async client with tenacity retries
│   │   └── anthropic_provider.py Anthropic async client with tenacity retries
│   ├── db/                       SQLAlchemy 2.0 models + session factory
│   ├── schemas/                  Pydantic v2 request/response models
│   └── observability/
│       ├── metrics.py            Prometheus counters + histograms
│       └── logging.py            Structured JSON logger + request middleware
├── tests/                        31 tests (unit + integration, mocked LLM)
├── eval/
│   ├── dataset.json              20 curated Q&A pairs over the sample PDFs
│   └── results/                  Timestamped eval reports (gitignored)
├── scripts/
│   └── generate_samples.py       Generates the demo PDFs via reportlab
├── data/
│   ├── sample/                   3 demo PDFs (Acme handbook, vector-DB primer, quarterly review)
│   └── uploads/                  User uploads at runtime (gitignored)
├── docker-compose.yml            Postgres + app
├── Dockerfile                    Python 3.11 slim + editable install
├── pyproject.toml                Dependencies + ruff + mypy + pytest config
├── CLAUDE.md                     Build spec / working notes for the project
└── README.md                     You are here.
```

---

## Design Decisions

These are not accidents — every choice is defensible in an interview.

<details>
<summary><b>Why local embeddings instead of OpenAI embeddings?</b></summary>

`all-MiniLM-L6-v2` runs on CPU, downloads once (~80 MB), and keeps the dev workflow fully offline. Swapping in `OpenAIEmbeddings` is a one-line change in `app/core/vectorstore.py` — but you must not mix embedders in a single deployment, because the dimension mismatch silently corrupts retrieval. The cost of a paid embedding key would land on every developer clone; not worth it for the marginal quality gain.
</details>

<details>
<summary><b>Why ChromaDB and not Pinecone / Weaviate / pgvector?</b></summary>

Local-first, works offline, no account setup. The query interface (`similarity_search_with_score`) is close enough to the hosted alternatives that the skill transfers cleanly. For a portfolio project, the operational simplicity wins; for production with billion-scale embeddings, the IVF-PQ-based hosted options are correct.
</details>

<details>
<summary><b>Why both LangChain and raw LLM SDKs?</b></summary>

LangChain is used where it adds value — document loaders, text splitters, vector-store abstraction. The actual LLM call uses the raw SDK directly. LangChain's chain abstractions are leaky in non-trivial ways, add debugging surface, and obscure failure modes. Using raw provider SDKs for the one call that matters makes rate-limit handling, retries, and streaming much easier to reason about.
</details>

<details>
<summary><b>Why a `LLMProvider` abstract class?</b></summary>

One interface, two implementations, env-driven selection. It's the kind of abstraction interview questions poke at, and the payoff is real: users with either an OpenAI or an Anthropic key can run the project without touching code. See `app/llm/base.py`.
</details>

<details>
<summary><b>Why log queries to PostgreSQL?</b></summary>

Demonstrates observability and auditability beyond metrics. In any real system you want to know what was asked, what was answered, and which chunks grounded the answer — for debugging, cost attribution, user feedback loops, and eventually retraining.
</details>

<details>
<summary><b>Why background ingestion?</b></summary>

PDFs can take several seconds to chunk and embed. Blocking the upload request on that would be bad UX and would tie up the worker. FastAPI's `BackgroundTasks` gives us async processing with zero extra infrastructure (no Celery, no Redis). In a real production system, you'd upgrade to a proper queue; at portfolio scale, BackgroundTasks is the right call.
</details>

---

## Testing

```bash
# Full suite (31 tests, ~50s on first run while MiniLM downloads)
pytest tests/ -v

# Specific phase
pytest tests/test_ingestion.py     # Phase 1: PDF → chunks → Chroma
pytest tests/test_retrieval.py     # Phase 2: similarity search returns scored chunks
pytest tests/test_generation.py    # Phase 2: prompt construction + mocked LLM
pytest tests/test_evaluation.py    # Phase 3: faithfulness, precision, latency
pytest tests/test_api.py           # Phase 4: end-to-end HTTP integration

# Lint + type-check
ruff check app/ tests/
mypy app/
```

The test suite uses real sentence-transformers embeddings and a real ChromaDB per test, so retrieval behavior is exercised for real. LLM calls are mocked via a `MockLLMProvider` wired in through `FastAPI.dependency_overrides` — no API key needed to run the tests.

---

## Roadmap

Given another week, in rough priority order:

- [ ] **Streaming answers.** Server-Sent Events so clients see tokens as they generate.
- [ ] **Multi-document scoping.** `POST /query` accepts a `document_ids` filter for targeted search.
- [ ] **Cross-encoder re-rank.** An extra re-rank step on top-k chunks typically lifts faithfulness by 5–10 points.
- [ ] **Hybrid search.** Blend BM25 with vector similarity for queries with rare proper nouns or exact-match terms.
- [ ] **Table-aware chunking.** `UnstructuredPDFLoader` fallback + table-aware splitter for PDFs with complex tables.
- [ ] **User auth + document isolation.** OAuth + row-level filtering so multi-tenant deployments are safe.
- [ ] **Human-labeled eval.** Replace LLM-as-judge with a small human-annotated set to calibrate the judge signal.
- [ ] **CI/CD.** GitHub Actions workflow: pytest + ruff + mypy on every PR, container build on main.

---

## Author

**Sasidhar Appalla** — AI/ML Engineer

[![GitHub](https://img.shields.io/badge/GitHub-sasidharappalla-181717?style=for-the-badge&logo=github)](https://github.com/sasidharappalla)
[![Email](https://img.shields.io/badge/Email-shanmukhchatadi%40gmail.com-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:shanmukhchatadi@gmail.com)

Built as a portfolio project to demonstrate end-to-end ownership of a modern RAG system — from chunking strategy to evaluation methodology, from async API design to container orchestration. Every technology here is genuinely represented in the code; nothing is resume filler.

---

<div align="center">

If this project is useful to you, star the repo. If you're hiring — let's talk.

</div>
