#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="${REPO_ROOT}/.pytest.lock"
RUN_TIMEOUT="${TEST_RUN_TIMEOUT:-240}"
CASE_TIMEOUT="${TEST_CASE_TIMEOUT:-60}"

cd "$REPO_ROOT"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Tests are already running in this repository. Skipping parallel run."
  exit 0
fi

if [[ -x "${REPO_ROOT}/.venv/bin/pytest" ]]; then
  PYTEST_BIN="${REPO_ROOT}/.venv/bin/pytest"
else
  PYTEST_BIN="pytest"
fi

EXTRA_ARGS=()
if "$PYTEST_BIN" --help 2>/dev/null | grep -q -- "--timeout"; then
  EXTRA_ARGS+=(--timeout="$CASE_TIMEOUT" --timeout-method=thread)
fi

echo "Running tests with repo lock: ${LOCK_FILE}"
echo "Global timeout: ${RUN_TIMEOUT}s"

timeout "$RUN_TIMEOUT" "$PYTEST_BIN" -q --maxfail=1 "${EXTRA_ARGS[@]}" "$@"
