#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
helm lint "${ROOT_DIR}/helm/docuquery"
helm template docuquery "${ROOT_DIR}/helm/docuquery"
