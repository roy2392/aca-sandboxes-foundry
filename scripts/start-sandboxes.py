#!/usr/bin/env python3
"""Create or resume both Foundry sandboxes and refresh their short-lived tokens."""
import json
import os
import shlex
from pathlib import Path

from azure.containerapps.sandbox import (
    AutoSuspendPolicy, EgressHostRule, EgressPolicy, LifecyclePolicy,
    SandboxGroupClient, endpoint_for_region,
)
from azure.identity import AzureCliCredential
from azure.core.exceptions import ResourceNotFoundError
from settings import RUNTIME_KEYS, access_token, check_account, image_name, required


def main():
    subscription = check_account()
    credential = AzureCliCredential(subscription=subscription)
    client = SandboxGroupClient(endpoint_for_region(required("ACA_REGION")), credential,
                                subscription_id=subscription,
                                resource_group=required("ACA_RESOURCE_GROUP"),
                                sandbox_group=required("ACA_SANDBOX_GROUP"))
    evidence = Path(__file__).resolve().parents[1] / "artifacts"
    evidence.mkdir(exist_ok=True)
    results = {}
    try:
        for agent in ("codex", "claude"):
            name = image_name(agent).replace(":", "-")
            matches = [s for s in client.list_sandboxes()
                       if s.labels.get("name") == name]
            if len(matches) > 1:
                raise RuntimeError(f"Multiple sandboxes named {name}; inspect before proceeding")
            if matches:
                sandbox = client.get_sandbox_client(matches[0].id)
                sandbox.ensure_running()
            else:
                disks = [d for d in client.list_disk_images()
                         if (d.name or d.labels.get("name")) == name]
                if len(disks) != 1 or disks[0].status.state != "Ready":
                    raise RuntimeError(f"Expected exactly one Ready disk named {name}")
                resource = required("FOUNDRY_RESOURCE")
                environment = {k: os.environ[k] for k in RUNTIME_KEYS if k in os.environ}
                # /dev/shm is memory-backed; credentials must not persist in disk images.
                environment["FOUNDRY_TOKEN_FILE"] = "/dev/shm/foundry-token"
                sandbox = client.begin_create_sandbox(
                    disk=None, disk_id=disks[0].id, cpu="2000m", memory="4096Mi",
                    labels={"name": name, "agent": agent}, environment=environment,
                    egress_policy=EgressPolicy(default_action="Deny", host_rules=[
                        EgressHostRule(pattern=f"{resource}.openai.azure.com"),
                        EgressHostRule(pattern=f"{resource}.services.ai.azure.com"),
                    ]), polling_timeout=600,
                ).result()
            sandbox.set_lifecycle_policy(LifecyclePolicy(auto_suspend=AutoSuspendPolicy(enabled=False)))
            state = sandbox.get()
            results[agent] = {"id": state.id, "state": state.state, "name": name}
            (evidence / "sandboxes.json").write_text(json.dumps(results, indent=2) + "\n")
            # Upload API sends token in the HTTPS body, never a command argument.
            # The file API creates files as root. Precreate as the image user;
            # replacing content then retains that user ownership.
            try:
                sandbox.delete_file("/dev/shm/foundry-token")
            except ResourceNotFoundError:
                pass
            result = sandbox.exec("umask 077; touch /dev/shm/foundry-token")
            if result.exit_code:
                raise RuntimeError(result.stderr)
            sandbox.write_file("/dev/shm/foundry-token", access_token(), mode="0600")
            result = sandbox.exec("test -r /dev/shm/foundry-token && id && stat -c '%U %a' /dev/shm/foundry-token")
            if result.exit_code:
                raise RuntimeError("Token file is not readable by the agent")
            # Portal terminals open as root. Provide an explicit non-root entry
            # point with the same configuration used by the verified SDK runs.
            assignments = [f"{k}={os.environ[k]}" for k in RUNTIME_KEYS if k in os.environ]
            assignments += ["HOME=/home/agent", "FOUNDRY_TOKEN_FILE=/dev/shm/foundry-token"]
            launch = shlex.join(["env", *assignments, f"/usr/local/bin/{agent}"])
            helper = ("#!/bin/sh\nset -eu\ncd /workspace\n"
                      f'if [ "$(id -u)" = 0 ]; then exec runuser -u agent -- {launch} "$@"; fi\n'
                      f'exec {launch} "$@"\n')
            sandbox.write_file(f"/workspace/start-{agent}", helper, mode="0755")
            print(agent, state.id, state.state, result, flush=True)
    finally:
        client.close()
        credential.close()


if __name__ == "__main__":
    main()
