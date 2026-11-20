#!/usr/bin/env bash
# Simulate the base week, run the SQL analyses, draw figures, build the viewer and run the tests.
set -euo pipefail
cd "$(dirname "$0")/.."

SCALE="${SCALE:-1.0}"
SEED="${SEED:-7}"

python -m twin.build --scale "$SCALE" --seed "$SEED"

if command -v tsc >/dev/null 2>&1; then
  tsc -p web/tsconfig.json
else
  echo "tsc not found: using the committed web/js/viewer.js"
fi

python -m pytest -q
echo "Viewer: web/index.html"
