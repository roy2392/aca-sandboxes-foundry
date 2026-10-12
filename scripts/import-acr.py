#!/usr/bin/env python3
"""Push local images to an existing private ACR, then import immutable digests.

Creates registry tags and ACA disk images; does not create a registry, sandbox,
identity or role assignment. Registry credentials stay in memory and a temporary
Docker configuration that is deleted on exit.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from azure.containerapps.sandbox import RegistryCredentials, SandboxGroupClient, endpoint_for_region
from azure.identity import AzureCliCredential
from settings import check_account, image_name, required


def az(subscription, *args):
    result = subprocess.run(["az", *args, "--subscription", subscription, "-o", "json"],
                            capture_output=True, text=True, check=True, timeout=120)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, help="Existing Azure Container Registry name")
    args = parser.parse_args()
    subscription = check_account()
    registry = az(subscription, "acr", "show", "--name", args.registry)
    server = registry["loginServer"]
    docker_host = subprocess.check_output([
        "docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"
    ], text=True).strip()
    credential = AzureCliCredential(subscription=subscription)
    client = SandboxGroupClient(endpoint_for_region(required("ACA_REGION")), credential,
                                subscription_id=subscription,
                                resource_group=required("ACA_RESOURCE_GROUP"),
                                sandbox_group=required("ACA_SANDBOX_GROUP"))
    evidence = Path(__file__).resolve().parents[1] / "artifacts"
    evidence.mkdir(exist_ok=True)
    try:
        for agent in ("codex", "claude"):
            local_image = image_name(agent)
            target = f"{server}/{local_image}"
            disk_name = local_image.replace(":", "-")
            existing = [d for d in client.list_disk_images()
                        if (d.name or d.labels.get("name")) == disk_name]
            if existing:
                if getattr(existing[0].status, "state", None) != "Ready":
                    raise RuntimeError(f"Disk {disk_name} exists but is not Ready; inspect it before retrying.")
                print(f"Disk {disk_name} is already Ready: {existing[0].id}", flush=True)
                continue
            login = az(subscription, "acr", "login", "--name", args.registry, "--expose-token")
            with tempfile.TemporaryDirectory(prefix="foundry-acr-") as config:
                env = {**os.environ, "DOCKER_CONFIG": config, "DOCKER_HOST": docker_host}
                env.pop("DOCKER_CONTEXT", None)
                subprocess.run(["docker", "login", server, "--username",
                                "00000000-0000-0000-0000-000000000000", "--password-stdin"],
                               input=login["accessToken"], text=True, env=env, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                subprocess.run(["docker", "tag", local_image, target], env=env, check=True)
                print(f"Pushing {target}", flush=True)
                subprocess.run(["docker", "push", target], env=env, check=True)
            digest = az(subscription, "acr", "repository", "show", "--name", args.registry,
                        "--image", local_image)["digest"]
            immutable = f"{server}/{local_image.split(':')[0]}@{digest}"
            print(f"Importing {disk_name} from {immutable}", flush=True)
            disk = client.begin_create_disk_image(
                immutable, name=disk_name,
                registry_credentials=RegistryCredentials(
                    username="00000000-0000-0000-0000-000000000000", token=login["accessToken"]),
                polling_timeout=1200,
            ).result()
            result = {"id": disk.id, "name": disk.name or disk.labels.get("name"), "image": immutable,
                      "status": getattr(disk.status, "state", "unknown")}
            (evidence / f"{agent}-disk.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result), flush=True)
    finally:
        client.close()
        credential.close()


if __name__ == "__main__":
    main()
