#!/usr/bin/env bash
# Launch the operations dashboard (Linux / macOS).
#
# Serves http://127.0.0.1:8765 and opens it in the default browser.
set -euo pipefail

export PYTHONIOENCODING=utf-8

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${MARTEX_QUANT_HOME:-$(dirname "$SCRIPT_DIR")}"
cd "$WORKSPACE"

TB="$WORKSPACE/.venv/bin/martex-quant"
[ -x "$TB" ] || TB="martex-quant"

exec "$TB" dashboard "$@"
