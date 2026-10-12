#!/usr/bin/env python3
"""Run a bounded model-and-tool task in each existing sandbox; save private proof."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import shlex

from azure.containerapps.sandbox import SandboxGroupClient, endpoint_for_region
from azure.identity import AzureCliCredential
from settings import check_account, required


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=("codex", "claude"), required=True)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parents[1] / "artifacts"
    inventory = json.loads((evidence / "sandboxes.json").read_text())
    subscription = check_account()
    credential = AzureCliCredential(subscription=subscription)
    client = SandboxGroupClient(endpoint_for_region(required("ACA_REGION")), credential,
                                subscription_id=subscription,
                                resource_group=required("ACA_RESOURCE_GROUP"),
                                sandbox_group=required("ACA_SANDBOX_GROUP"))
    try:
        sandbox = client.get_sandbox_client(inventory[args.agent]["id"])
        sandbox.ensure_running()
        nonce = secrets.token_hex(16)
        path = f"/workspace/{args.agent}-proof.json"
        prompt = (f"Use a shell tool to run Python 3. Compute the SHA-256 of the UTF-8 string {nonce} "
                  f"and sum(range(1,101)). Write JSON to {path} with keys nonce, sha256, sum. "
                  "Read the file back using a tool, then reply VERIFIED. Do not access credentials "
                  "or network with tools. Do not merely describe commands; execute them.")
        if args.agent == "codex":
            command = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "--json", prompt]
        else:
            command = ["claude", "-p", prompt, "--max-turns", "6", "--output-format", "json",
                       "--allowedTools", "Bash(python3:*)", "Read", "Write"]
        result = sandbox.exec("timeout 240 " + shlex.join(command), working_directory="/workspace")
        (evidence / f"{args.agent}-cloud-exec.json").write_text(json.dumps({
            "exit_code": result.exit_code, "stdout": result.stdout, "stderr": result.stderr,
        }, indent=2) + "\n")
        if result.exit_code:
            raise RuntimeError(f"{args.agent} failed ({result.exit_code}); see ignored execution evidence")
        actual = json.loads(sandbox.read_file(path))
        expected = {"nonce": nonce, "sha256": hashlib.sha256(nonce.encode()).hexdigest(), "sum": 5050}
        if actual != expected:
            raise RuntimeError(f"{args.agent} produced incorrect proof")
        state = sandbox.get()
        report = {"agent": args.agent, "id": state.id, "state": state.state,
                  "tool_task_verified": True, "proof": actual}
        (evidence / f"{args.agent}-cloud-proof.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)
    finally:
        client.close()
        credential.close()


if __name__ == "__main__":
    main()
