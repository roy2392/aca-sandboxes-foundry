#!/usr/bin/env python3
"""Run a prepared image using an explicitly selected Azure CLI account."""
import os
import subprocess
import sys
from settings import access_token, image_name, runtime_flags

if len(sys.argv) < 2 or sys.argv[1] not in ("codex", "claude"):
    raise SystemExit("Usage: python3 scripts/run-local.py codex|claude [CLI arguments...]")
agent = sys.argv[1]
token = access_token()
environment = {**os.environ, "FOUNDRY_AUTH_TOKEN": token}
command = ["docker", "run", "--rm", "--platform", "linux/amd64", "-i"]
if sys.stdin.isatty():
    command.append("-t")
command += [*runtime_flags(), "--env", "FOUNDRY_AUTH_TOKEN", image_name(agent), agent, *sys.argv[2:]]
# No host home, Azure credential cache, Docker socket, or repository is mounted.
raise SystemExit(subprocess.call(command, env=environment))
