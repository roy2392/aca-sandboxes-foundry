#!/usr/bin/env python3
"""Verify both local images; --live adds one small model request per image."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid
from settings import access_token, image_name, runtime_flags

ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, text=True, timeout=120, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Invoke deployed Foundry models (token charges apply).")
    args = parser.parse_args()
    token = None
    if args.live:
        token = access_token()
    report = {}
    for agent in ("codex", "claude"):
        image = image_name(agent)
        version = run(["docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none", image, agent, "--version"])
        guard = run(["docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none", image, agent, "exec" if agent == "codex" else "-p", "hello"])
        identity = run(["docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none", image, "id", "-u"])
        item = {"image": image, "version": version.stdout.strip(),
                "version_ok": version.returncode == 0, "nonroot": identity.stdout.strip() == "10001",
                "missing_token_rejected": guard.returncode == 64}
        if token:
            name = f"foundry-verify-{agent}-{uuid.uuid4().hex[:8]}"
            command = ["docker", "run", "--rm", "--platform", "linux/amd64", "--name", name, *runtime_flags(), "--env", "FOUNDRY_AUTH_TOKEN", image, agent]
            prompt = "Reply with exactly FOUNDRY_OK. Do not use tools."
            if agent == "codex":
                command += ["exec", "--skip-git-repo-check", "--sandbox", "read-only", prompt]
            else:
                command += ["-p", prompt, "--max-turns", "1", "--tools", "", "--no-session-persistence"]
            try:
                live = run(command, env={**os.environ, "FOUNDRY_AUTH_TOKEN": token})
                item["live_ok"] = live.returncode == 0 and "FOUNDRY_OK" in live.stdout
                item["live_exit_code"] = live.returncode
                # Only save sanitized diagnostics; never persist the token.
                item["live_output"] = (live.stdout + live.stderr).replace(token, "[REDACTED]")[-6000:]
            except subprocess.TimeoutExpired:
                item["live_ok"] = False
                item["live_output"] = "Timed out after 120 seconds."
            finally:
                run(["docker", "rm", "-f", name])
        report[agent] = item
        print(json.dumps(item, indent=2))
    destination = ROOT / "artifacts" / ("verification-live.json" if args.live else "verification-local.json")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n")
    if not all(all(item[k] for k in ("version_ok", "nonroot", "missing_token_rejected"))
               and item.get("live_ok", True) for item in report.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
