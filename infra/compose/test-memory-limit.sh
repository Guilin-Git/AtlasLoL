#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

compose=(docker compose -p atlaslol-memory-probe --profile test)

cleanup() {
  "${compose[@]}" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

set +e
"${compose[@]}" up --abort-on-container-exit --exit-code-from memory-limit-probe
status=$?
set -e

container_id="$("${compose[@]}" ps -aq memory-limit-probe)"
oom_killed="$(docker inspect --format '{{.State.OOMKilled}}' "$container_id")"

if [[ "$status" -ne 137 || "$oom_killed" != "true" ]]; then
  echo "Falha: esperado encerramento por limite de memoria (exit 137 / OOMKilled=true)." >&2
  exit 1
fi

echo "Sucesso: o limite de 100 MiB conteve a alocacao de 500+ MiB."
