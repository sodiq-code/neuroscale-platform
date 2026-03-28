#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${ROOT_DIR}/.ci/rendered"
CHART_DIR="${ROOT_DIR}/infrastructure/backstage"
OUT_FILE="${OUT_DIR}/backstage.rendered.yaml"

mkdir -p "${OUT_DIR}"

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is required but not found on PATH" >&2
  exit 1
fi

if [ ! -d "${CHART_DIR}/charts" ] || ! ls -1 "${CHART_DIR}/charts"/*.tgz >/dev/null 2>&1; then
  # No vendored dependencies; attempt to fetch them.
  helm dependency build "${CHART_DIR}" >/dev/null
fi

helm template neuroscale-backstage "${CHART_DIR}" -f "${CHART_DIR}/values.yaml" > "${OUT_FILE}"

if ! grep -q "kind: Deployment" "${OUT_FILE}"; then
  echo "Rendered output does not contain a Deployment; check chart render" >&2
  exit 1
fi

# Guard against the most common regression from the incident:
# values nesting errors causing probe settings to silently revert to defaults.
# These greps are intentionally minimal and stable.
grep -q "startupProbe:" "${OUT_FILE}"
grep -q "initialDelaySeconds: 120" "${OUT_FILE}"

echo "Rendered Backstage chart to: ${OUT_FILE}"