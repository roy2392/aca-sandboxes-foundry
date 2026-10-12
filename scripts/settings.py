"""Shared non-secret runtime configuration and explicitly scoped Azure auth."""
import json
import os
import subprocess

RUNTIME_KEYS = ("FOUNDRY_TENANT_ID", "FOUNDRY_RESOURCE", "CODEX_MODEL", "CLAUDE_MODEL",
                "CLAUDE_OPUS_MODEL", "CLAUDE_SONNET_MODEL", "CLAUDE_HAIKU_MODEL")


def required(name):
    value = os.environ.get(name, "")
    if not value or value.startswith("YOUR_"):
        raise ValueError(f"Configure {name}; see .env.example.")
    return value


def check_account():
    subscription = required("AZURE_SUBSCRIPTION_ID")
    account = json.loads(subprocess.check_output([
        "az", "account", "show", "--subscription", subscription, "-o", "json"
    ], text=True))
    if account["tenantId"] != required("FOUNDRY_TENANT_ID"):
        raise ValueError("The selected subscription belongs to a different tenant.")
    return subscription


def access_token():
    subscription = check_account()
    return subprocess.run([
        "az", "account", "get-access-token", "--subscription", subscription,
        "--resource", "https://cognitiveservices.azure.com", "--query", "accessToken", "-o", "tsv",
    ], capture_output=True, text=True, check=True, timeout=60).stdout.strip()


def image_name(agent):
    return f"{os.environ.get('IMAGE_PREFIX', 'foundry')}-{agent}:{os.environ.get('IMAGE_TAG', '20261012.2')}"


def runtime_flags():
    flags = []
    for key in RUNTIME_KEYS:
        if key in os.environ:
            flags += ["--env", key]
    return flags
