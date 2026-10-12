#!/usr/bin/env python3
"""Launch a coding CLI with a runtime Entra token, never a baked-in API key."""
import base64
import json
import os
import re
from pathlib import Path
import sys
import time

AUDIENCE = "https://cognitiveservices.azure.com"
BINARIES = {
    "codex": "/opt/codex/node_modules/.bin/codex",
    "claude": "/opt/claude/node_modules/.bin/claude",
}


def checked_token(env):
    token = env.get("FOUNDRY_AUTH_TOKEN", "")
    if not token:
        try:
            token = Path(env.get("FOUNDRY_TOKEN_FILE", "/run/secrets/foundry-token")).read_text().strip()
        except OSError:
            raise ValueError("Provide FOUNDRY_AUTH_TOKEN or a readable FOUNDRY_TOKEN_FILE at runtime.") from None
    # Routing/expiry sanity checks only. Foundry verifies the JWT signature.
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        expiry = float(claims["exp"])
    except (ValueError, KeyError, IndexError, TypeError):
        raise ValueError("Expected a Microsoft Entra JWT, not an API key.") from None
    tenant = env.get("FOUNDRY_TENANT_ID", "")
    if not tenant or tenant.startswith("YOUR_"):
        raise ValueError("Set FOUNDRY_TENANT_ID to your expected Entra tenant.")
    if claims.get("tid") != tenant:
        raise ValueError("Token belongs to a different tenant; obtain a token for the configured tenant.")
    if str(claims.get("aud", "")).rstrip("/") != AUDIENCE:
        raise ValueError("Token audience must be https://cognitiveservices.azure.com.")
    if expiry <= time.time() + 60:
        raise ValueError("Token expires within 60 seconds; refresh it before launching.")
    return token


def required(env, name):
    value = env.get(name, "")
    if not value or value.startswith("YOUR_"):
        raise ValueError(f"Set {name} to your deployed resource/model name.")
    return value


def configure(agent, env):
    resource = required(env, "FOUNDRY_RESOURCE")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]{0,62}", resource):
        raise ValueError("FOUNDRY_RESOURCE must be an Azure account name, not a URL.")
    if agent == "codex":
        model = required(env, "CODEX_MODEL")
        template = Path("/opt/foundry/codex-config.toml").read_text()
        config = template.replace('"__CODEX_MODEL__"', json.dumps(model)).replace("__FOUNDRY_RESOURCE__", resource)
        directory = Path(env.get("HOME", "/home/agent")) / ".codex"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "config.toml").write_text(config)
        # Keep config isolated from a caller's personal Codex state.
        env.pop("CODEX_HOME", None)
    else:
        env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
        env["ANTHROPIC_FOUNDRY_RESOURCE"] = resource
        env["ANTHROPIC_MODEL"] = required(env, "CLAUDE_MODEL")
        for role in ("OPUS", "SONNET", "HAIKU"):
            env[f"ANTHROPIC_DEFAULT_{role}_MODEL"] = required(env, f"CLAUDE_{role}_MODEL")


def launch(agent, args):
    env = os.environ.copy()
    if args not in (["--version"], ["--help"], ["-h"]):
        try:
            token = checked_token(env)
            configure(agent, env)
        except ValueError as exc:
            print(f"Foundry authentication: {exc}", file=sys.stderr)
            return 64
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY",
                    "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "ANTHROPIC_FOUNDRY_API_KEY",
                    "ANTHROPIC_FOUNDRY_BASE_URL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                    "FOUNDRY_AUTH_TOKEN"):
            env.pop(key, None)
        if agent == "codex":
            env["AZURE_FOUNDRY_AUTH_TOKEN"] = token
        else:
            env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
            env["ANTHROPIC_FOUNDRY_AUTH_TOKEN"] = token
    os.execve(BINARIES[agent], [BINARIES[agent], *args], env)


if __name__ == "__main__":
    sys.exit(launch(sys.argv[1], sys.argv[2:]))
