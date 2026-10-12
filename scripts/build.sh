#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts
npm ci --prefix images/codex/vendor --os=linux --cpu=x64 --ignore-scripts --no-audit --no-fund
npm ci --prefix images/claude/vendor --os=linux --cpu=x64 --libc=glibc --ignore-scripts --no-audit --no-fund
for agent in codex claude; do
  docker build --platform linux/amd64 -f "images/$agent/Dockerfile" \
    -t "${IMAGE_PREFIX:-foundry}-$agent:${IMAGE_TAG:-20261012.2}" images
  docker image inspect "${IMAGE_PREFIX:-foundry}-$agent:${IMAGE_TAG:-20261012.2}" \
    --format '{{json .}}' > "artifacts/$agent-image.json"
done
