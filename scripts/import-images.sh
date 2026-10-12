#!/usr/bin/env bash
# Run only after approving Azure image creation. Builds two private disk images.
set -euo pipefail
cd "$(dirname "$0")/.."
# Do not proceed until read access works with the selected CLI identity.
python3 scripts/aca-scoped.py sandboxgroup disk list -o json
test -d images/codex/vendor/node_modules || { echo "Run bash scripts/build.sh first" >&2; exit 1; }
test -d images/claude/vendor/node_modules || { echo "Run bash scripts/build.sh first" >&2; exit 1; }
mkdir -p artifacts/import-context
for agent in codex claude; do
  context="artifacts/import-context/$agent"
  mkdir -p "$context/common" "$context/$agent"
  cp images/common/launch.py "$context/common/launch.py"
  # ACA's source uploader rejects symlinks. Dereference npm's .bin links in
  # this generated context; the Dockerfiles recreate them inside Linux.
  python3 - "$agent" "$context" <<'PY'
import shutil
import sys
from pathlib import Path
agent, context = sys.argv[1:]
target = Path(context) / agent
if target.exists():
    shutil.rmtree(target)
shutil.copytree(Path("images") / agent, target, symlinks=False)
PY
  cp "images/$agent/Dockerfile" "$context/Dockerfile"
  python3 scripts/aca-scoped.py sandboxgroup disk create \
    --source "$context" --name "${IMAGE_PREFIX:-foundry}-$agent-${IMAGE_TAG:-20261012.2}" \
    --label provider=azure-foundry --label "agent=$agent" --wait-timeout 1200 -o json \
    > "artifacts/$agent-disk.json"
done
