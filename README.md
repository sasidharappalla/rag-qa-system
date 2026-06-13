# DocuQuery Platform Deployment Demo

## Overview

DocuQuery is a FastAPI RAG-style document service with a focused platform deployment layer.
The application retains its PDF ingestion, Chroma retrieval, OpenAI/Anthropic provider support,
evaluation suite, Prometheus metrics, and structured logging. This repository adds:

- A non-root Docker image that runs without a paid LLM key in demo mode
- Terraform for an Azure resource group and AKS cluster
- A Helm chart for Kubernetes deployment
- GitLab CI jobs for linting, testing, image build, Terraform validation, Helm validation, and manual deployment
- Kubernetes probes, resource controls, environment-based configuration, and Prometheus scrape annotations

The default platform image uses SQLite, local Chroma storage, and a deterministic mock provider.
Real providers and PostgreSQL remain available through the existing application configuration and
Docker Compose stack.

## Architecture

```text
Developer Push
     |
     v
GitLab CI Pipeline
     |
     |-- Python tests
     |-- Docker image build
     |-- Terraform validate
     |-- Helm lint/template
     |
     v
Azure AKS Cluster
     |
     v
Helm Release: DocuQuery FastAPI Service
     |
     |-- /health
     |-- /search
     |-- /ask
     |
     v
Structured Logs + Kubernetes Probes + Prometheus Annotations
```

The retained RAG workflow is:

```text
PDF upload -> text extraction -> chunking -> local embeddings -> Chroma
                                                            |
Question -> similarity search -> grounded prompt -> LLM provider -> cited answer
```

## Tech Stack

- FastAPI, Pydantic, Uvicorn
- LangChain, ChromaDB, sentence-transformers
- Docker and Docker Compose
- Terraform and Azure Kubernetes Service
- Helm and Kubernetes
- GitLab CI/CD
- Prometheus-compatible metrics and annotations
- pytest, Ruff, and structured JSON logging

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Kubernetes and container health endpoint |
| `GET` | `/search?q=...` | Retrieve relevant chunks or demo context |
| `POST` | `/ask` | Return a grounded answer in the platform-demo response shape |
| `POST` | `/documents` | Upload and ingest a PDF |
| `POST` | `/query` | Run the full RAG query flow with cited sources |
| `GET` | `/evaluate` | Run the RAG evaluation suite |
| `GET` | `/metrics` | Expose Prometheus metrics |
| `GET` | `/docs` | OpenAPI documentation |

Demo request:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is this document about?"}'
```

## Project Structure

```text
.
├── app/                    FastAPI service, requirements, Dockerfile, smoke tests
├── data/                   Sample PDFs and runtime upload location
├── eval/                   RAG evaluation dataset and ignored results
├── helm/docuquery/         Kubernetes package
├── infra/                  Terraform AKS configuration
├── scripts/                Repeatable local validation commands
├── tests/                  Existing RAG unit and integration tests
├── .gitlab-ci.yml          GitLab CI/CD pipeline
├── docker-compose.yml      PostgreSQL plus full RAG service
└── IMPLEMENTATION.md       Implementation decisions and validation checklist
```

## Local Development

Python 3.11 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install --requirement app/requirements.txt
pip install ruff==0.8.6

pytest app/tests
ruff check app tests
```

Run only the fast platform smoke tests:

```bash
cd app
pytest
```

Run the API without paid provider calls:

```bash
export DATABASE_URL="sqlite:///./docuquery.db"
export LLM_PROVIDER="mock"
export PLATFORM_DEMO_MODE="true"
export DEPENDENCY_HEALTH_CHECKS="false"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For the full PostgreSQL-backed RAG stack:

```bash
pip install --editable ".[dev]"
pytest tests

cp .env.example .env
# Set the selected real provider key in .env.
docker compose up --build
```

## Docker

Build and run the standalone platform image:

```bash
docker build -t docuquery:local ./app
docker run --rm -p 8000:8000 docuquery:local
curl http://localhost:8000/health
```

Expected health response:

```json
{"status":"ok","service":"docuquery","version":"1.0.0"}
```

The image runs as UID `10001` and defaults to mock/demo configuration. Override settings with
environment variables for other platform settings. Use the root Dockerfile and Docker Compose path
for the full PostgreSQL, Chroma, embeddings, and real-provider dependency set.

## Terraform AKS Provisioning

Basic formatting and validation do not require an Azure deployment:

```bash
cd infra
terraform init
terraform fmt -check
terraform validate
```

With Azure credentials available:

```bash
terraform plan -var-file="terraform.tfvars.example"
terraform apply -var-file="terraform.tfvars.example"
```

`terraform apply` creates billable Azure resources. The configuration intentionally omits a remote
state backend and automatic apply stage; configure remote state before using it beyond a demo.
Never commit local state, plan files, credentials, or kubeconfig files.

## Helm Deployment

Validate rendering without a cluster:

```bash
helm lint helm/docuquery
helm template docuquery helm/docuquery
```

Deploy after the image is available to the cluster:

```bash
helm upgrade --install docuquery helm/docuquery \
  --namespace docuquery \
  --create-namespace \
  --set image.repository="<registry>/docuquery" \
  --set image.tag="<tag>"
```

Ingress and HPA are present but disabled by default. The chart configures two replicas, readiness
and liveness probes on `/health`, resource requests and limits, a dedicated service account,
ConfigMap-based environment variables, and Prometheus annotations for `/metrics`.

## GitLab CI/CD

The pipeline uses these stages:

1. `lint`: Ruff checks the Python application and tests.
2. `test`: pytest runs the retained RAG suite and platform smoke tests.
3. `build`: Docker builds a commit-SHA-tagged image and pushes only when registry variables exist.
4. `terraform`: Terraform formatting, initialization, and static validation run without apply.
5. `helm`: Helm linting and template rendering validate the Kubernetes package.
6. `deploy`: A manual job on the default branch logs into Azure, obtains AKS credentials, and runs
   `helm upgrade --install`.

Configure protected, masked GitLab CI variables:

```text
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
AZURE_TENANT_ID
AZURE_RESOURCE_GROUP
AKS_CLUSTER_NAME
CI_REGISTRY_USER
CI_REGISTRY_PASSWORD
CI_REGISTRY
CI_REGISTRY_IMAGE
```

The pipeline does not run `terraform apply` and does not deploy automatically from feature branches.

## Observability

- JSON access logs include `service`, `endpoint`, `status`, request ID, status code, and latency.
- `/health` supports lightweight probe mode or optional PostgreSQL and Chroma dependency checks.
- `/metrics` exposes Prometheus counters and latency histograms.
- Helm pod annotations advertise the `/metrics` endpoint to annotation-based Prometheus discovery.
- Kubernetes readiness and liveness probes call `/health`.

## Security Notes

- No secrets, `.env` files, Azure credentials, Terraform state, plans, or kubeconfigs are committed.
- Application settings and deployment credentials are supplied through environment variables.
- The standalone container runs as a non-root user.
- Kubernetes disables service-account token mounting and drops Linux capabilities.
- CPU and memory requests and limits are set in Helm values.
- The AKS deployment remains manual and default-branch-only.

## Helper Scripts

```bash
./scripts/local_test.sh
./scripts/docker_build.sh
./scripts/terraform_validate.sh
./scripts/helm_lint.sh
```

## Screenshots to Add

- GitLab pipeline passing
- `terraform validate`
- `terraform plan`
- `helm lint`
- `kubectl get pods`
- `curl /health`
- Azure AKS resource view

## Resume Bullets

- Built a platform deployment demo for DocuQuery by containerizing a FastAPI RAG-style service with Docker, provisioning Azure AKS infrastructure using Terraform, packaging Kubernetes manifests with Helm, and implementing GitLab CI stages for testing, image builds, Terraform validation, Helm linting, and manual deployment.

- Added Kubernetes readiness/liveness probes, structured JSON logs, Prometheus scrape annotations, environment-based configuration, and deployment documentation to support repeatable, observable, and auditable cloud deployments.
