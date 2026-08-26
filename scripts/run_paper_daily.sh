#!/usr/bin/env bash
# Daily paper-trading run (Linux / macOS).
#
# Schedule shortly after the 00:00 UTC daily bar close, e.g. crontab -e:
#   10 3 * * * /path/to/scripts/run_paper_daily.sh
#
# Runs EVERY paper strategy; add a name to STRATEGIES per new survivor.
set -euo pipefail

export PYTHONIOENCODING=utf-8

# Workspace: $TRADING_BOT_HOME if set, otherwise the directory above this
# script (the repository root in a source install). Never a hardcoded path.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${TRADING_BOT_HOME:-$(dirname "$SCRIPT_DIR")}"
cd "$WORKSPACE"

# Prefer the project's virtualenv; fall back to whatever is on PATH.
TB="$WORKSPACE/.venv/bin/martex-quant"
[ -x "$TB" ] || TB="martex-quant"

STRATEGIES=(vol-target rotation crash-bounce rotation-stop)

mkdir -p data/paper
for strategy in "${STRATEGIES[@]}"; do
    "$TB" paper --strategy "$strategy" >> data/paper/runs.log 2>&1
done
