# Execution, inference and identity

The execution layer is an ACA sandbox: an isolated microVM running the client, tools and workspace. The inference layer is your model deployment in Foundry. Packaging a client does not package model weights or grant model access.

Codex uses `https://<account>.openai.azure.com/openai/v1` and the Responses API. Claude uses native Foundry integration at `https://<account>.services.ai.azure.com/anthropic`. This sample targets standard Azure public-cloud accounts; sovereign clouds and custom gateways need an endpoint adaptation.

## Lifecycle

Build an OCI image → import it as a private disk → wait for Ready → create a sandbox by disk ID → operate it through exec/shell/file APIs → stop and resume between tasks.

Snapshots capture memory and disk. Committed images capture filesystems. Authenticated snapshots can retain credentials in memory, environment variables and files. Refresh expired credentials before resumed work.

## Networking and identity

Use deny-default egress and allow the exact Foundry hosts. Add repository/package hosts only when needed. With TLS inspection, arrange trusted certificates for the OS and client runtimes; do not disable certificate checks.

CLI access needs no public ingress. Expose a port only for an intended preview/service. Caller data-plane access and group identity are distinct from permission to invoke Foundry.

The launcher checks token tenant, audience and expiry as routing guards. The remote service validates signatures and RBAC. Tokens in the process remain accessible to equivalent-permission code. Unattended use needs token renewal and least-privilege access. Proxy-side credential injection is an alternative; this sample does not implement it.

## Costs and geography

Running sandboxes consume compute; Foundry inference is billed separately. Retained images, snapshots and volumes follow the service's storage pricing. Check the [current cost documentation](https://sandboxes.azure.com/docs/sandboxes/cost).

Sandbox region and Foundry account region are independent. Deployment type and hosting option determine processing geography; account location alone is not a residency guarantee.

## Acceptance gates

Build → offline startup → authenticated local inference → disk readiness → live microVM startup → agent task with independently inspected output → cleanup of test-only resources. Each gate establishes only its own evidence.
