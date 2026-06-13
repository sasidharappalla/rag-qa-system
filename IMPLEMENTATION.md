# Implementation Notes

## Scope

This change adds a focused platform deployment layer around the existing RAG application. It does
not add an unrelated frontend, message broker, workflow engine, monitoring stack, or automatic
cloud provisioning.

## Application Decisions

- Existing document ingestion, retrieval, generation, evaluation, and observability modules remain.
- `/search` and `/ask` provide the requested portfolio-demo API while using the real retrieval and
  generation pipeline by default.
- `PLATFORM_DEMO_MODE=true` supplies deterministic context for smoke deployments with no indexed
  documents.
- `LLM_PROVIDER=mock` avoids paid calls while preserving OpenAI and Anthropic provider support.
- `DEPENDENCY_HEALTH_CHECKS=false` keeps Kubernetes probes lightweight. The full dependency checks
  remain available for environments that deploy PostgreSQL and initialize Chroma.

## Container Decisions

- `app/Dockerfile` supports the required `docker build ... ./app` command.
- The standalone image uses Python 3.11 slim, a non-root UID, a container health check, and writable
  runtime paths under `/tmp`.
- The standalone image installs only the platform runtime. Full RAG and ML dependencies remain
  declared in `pyproject.toml` for the original application and its complete test suite.
- The root Dockerfile and Docker Compose setup remain available for the original PostgreSQL-backed
  RAG workflow.

## Infrastructure Decisions

- Terraform provisions only a resource group and managed-identity AKS cluster with one low-cost
  default node by default.
- No Terraform backend, ACR, monitoring workspace, or automatic apply stage is included.
- Helm packages a Deployment, Service, optional Ingress, ConfigMap, ServiceAccount, and optional HPA.
- The chart uses ephemeral local storage because persistent vector storage design is outside this
  demo's scope.

## CI Decisions

- Validation jobs do not require Azure credentials.
- Docker push occurs only when GitLab registry variables are present.
- AKS deployment is manual and limited to the default branch.
- Azure credentials are referenced only through CI variables.

## Validation Checklist

- [x] `cd app && pytest` (`3 passed`)
- [x] `ruff check app tests`
- [x] `docker build -t docuquery:local ./app`
- [x] Container `/health`, `/search`, and `/ask` smoke tests
- [x] Non-root container UID verification
- [x] `terraform fmt -check`
- [x] `terraform init -backend=false`
- [x] `terraform validate`
- [x] `helm lint helm/docuquery`
- [x] `helm template docuquery helm/docuquery`
- [x] Optional ingress/HPA Helm rendering
- [x] GitLab CI YAML parsing and stage-order assertion
- [x] Final secret and ignored-file review
