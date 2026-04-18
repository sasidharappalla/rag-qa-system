# CLAUDE.md — RAG Document Q&A System

> This file is instructions for Claude Code (claude.ai/code) working in this repository.

## Project Summary

Build a production-style Retrieval-Augmented Generation (RAG) system that ingests PDF documents, chunks and embeds them, stores embeddings in a vector database, and serves a FastAPI endpoint that answers questions by retrieving relevant context and generating answers with an LLM. Include evaluation metrics so the system's quality can be measured, not just demoed.

The goal is a portfolio project credible enough to discuss in an AI/ML Engineer interview. Build it so that every technology claimed on the resume — LangChain, vector databases, embeddings, RAG, FastAPI inference serving, prompt engineering, evaluation — is genuinely represented in the codebase.

## Success Criteria

The project is "done" when:

1. A user can upload a PDF through an API endpoint and it gets ingested, chunked, embedded, and indexed.
2. A user can POST a question and receive an answer grounded in the retrieved chunks, with the source chunks returned alongside the answer (so the user can verify).
3. An evaluation script runs against a small held-out Q&A dataset and reports three metrics: faithfulness (did the answer stay grounded in context?), relevance (did retrieval pull the right chunks?), and latency (p50, p95).
4. The whole stack runs locally with `docker compose up` and has a working README.
5. There are at least 5 integration tests covering the happy path and key failure modes.
6. The code is clean enough that a technical interviewer could read it and say "yes, this person built this."

## Tech Stack

Lock these in. Don't substitute without a reason.

- **Python 3.11+** — main language
- **FastAPI** — inference API layer
- **LangChain** — orchestration (document loaders, text splitters, retrievers, chain composition)
- **ChromaDB** — vector store (run locally, no cloud API key needed)
- **sentence-transformers** — local embedding model (`all-MiniLM-L6-v2`) so the project works without an OpenAI key during dev
- **OpenAI API** (or Anthropic API) — LLM for answer generation (make this pluggable; see Architecture)
- **PostgreSQL** — metadata layer (uploaded docs, ingestion status, query logs)
- **SQLAlchemy** — ORM for Postgres
- **pytest** — testing
- **Prometheus client** — latency/throughput metrics exposed at `/metrics`
- **Docker + docker-compose** — local orchestration
- **Pydantic v2** — request/response validation

Do NOT add: LlamaIndex (pick LangChain, don't use both), Pinecone (keep it local with Chroma), Redis (unnecessary at this scale), Kubernetes (this is a portfolio project, not production infra).

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

The LLM provider should be pluggable via a simple interface — a `LLMProvider` abstract class with `OpenAIProvider` and `AnthropicProvider` implementations. The provider is chosen by an env var `LLM_PROVIDER=openai|anthropic`. This demonstrates clean abstraction and lets the user run with whichever key they have.

## Repository Layout

See the actual tree in the repo. The spec layout:

```
rag-qa-system/
├── README.md
├── CLAUDE.md
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/               (documents, query, evaluate, health)
│   ├── core/              (ingestion, retrieval, generation, evaluation)
│   ├── llm/               (base, openai_provider, anthropic_provider)
│   ├── db/                (models, session)
│   ├── schemas/           (Pydantic request/response)
│   └── observability/     (metrics, logging)
├── tests/                 (conftest + 5 test modules)
├── eval/                  (dataset.json, results/)
├── scripts/               (sample PDF generator)
└── data/                  (uploads/ gitignored, sample/ committed generator)
```

## Implementation Phases

Build in order. Commit at end of each phase.

1. **Skeleton + Ingestion** — PDF upload → chunks → Chroma. `feat: ingestion pipeline with PDF loader, chunking, and Chroma storage`
2. **Retrieval + Generation** — question → answer with sources. `feat: retrieval and generation with pluggable LLM providers`
3. **Evaluation** — faithfulness, retrieval relevance, latency. `feat: evaluation suite with faithfulness, retrieval relevance, and latency`
4. **Observability + Polish** — metrics, logging, health, background ingestion, integration tests. `feat: observability, background ingestion, and full integration tests`

## Key Design Decisions

- **Local embeddings (`all-MiniLM-L6-v2`)** — portfolio must run without a paid key.
- **Chroma** — local-first, same query interface as hosted alternatives.
- **LangChain for orchestration, raw SDK for LLM calls** — LangChain chain abstractions are leaky; raw calls are easier to debug.
- **LLM-as-judge for faithfulness** — industry standard but biased (self-preference, position, drift). Document the caveat.
- **Postgres for query logs** — demonstrates audit/observability thinking.

## Common Pitfalls

1. Don't mix OpenAI embeddings with sentence-transformers in one deployment — dimension mismatch corrupts retrieval silently.
2. Always pass `k` explicitly to retrieval.
3. PDF loaders are fragile — test well-formatted, scanned, and table-heavy PDFs.
4. Chunk size 1000/200 is a starting point; tune from eval results.
5. Never log raw document text — metadata only.
6. Use tenacity with exponential backoff for eval runs or you'll get 429s.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Tests
pytest tests/ -v

# Type check / lint
mypy app/
ruff check app/ tests/

# Stack
docker compose up --build

# Eval
curl http://localhost:8000/evaluate | jq
```

Always run tests after changes. Never commit `.env` or `data/uploads/`.
