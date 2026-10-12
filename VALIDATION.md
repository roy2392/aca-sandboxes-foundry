# Validation scope

The initial account-specific images were built as Linux AMD64 containers and successfully invoked existing Foundry deployments using Entra authentication. Account identifiers, private resource names and raw logs are excluded from this repository.

The public edition moves Azure settings to runtime configuration. [GitHub Actions](https://github.com/roy2392/aca-sandboxes-foundry/actions) runs tests, image builds and offline startup checks without Azure credentials, cloud writes or model calls.

## Checks

- Authentication tests cover expected tenant/audience, wrong tenant/audience, malformed/expired credentials, missing files and token-file refresh between starts.
- Offline verification checks CLI versions, non-root UID `10001` and rejection of startup without credentials.
- Optional `python3 scripts/verify.py --live` checks a real response from each configured deployment and saves ignored evidence under `artifacts/`.
- The local live smoke prompt requests no tools. It does not prove a complete coding-agent task.
- **ACA runtime verified on 2026-10-12:** both imported images booted into Running sandboxes. Codex and Claude each called the configured Foundry deployment, executed Python, wrote a JSON proof file, and passed an independent file-content comparison through the ACA API. Both ran as UID `10001`; default-deny egress allowed the two configured Foundry hosts. Idle suspension was disabled and both were left Running.
- Reproduce that bounded cloud check with `scripts/start-sandboxes.py`, then `scripts/verify-sandboxes.py --agent codex` and `--agent claude`. It does not establish reliability for every repository or agent tool.

## Known limitations

1. **ACA runtime:** the bounded cloud task passed for both clients. Larger coding tasks, additional destinations and different image versions require their own validation.
2. **Model metadata:** the pinned Codex can invoke deployments absent from its built-in catalog, but may warn and use fallback metadata. Verify context limits and coding behavior for your chosen model.
3. **Token renewal:** credentials are reread at launch, not during a session. No managed identity or Azure role is provisioned.
4. **Tool sandbox:** Codex retains workspace restrictions and uses bundled bubblewrap when a system binary is absent. The cloud task exercised its shell tools successfully. Kernel/container permissions can differ in other environments. Do not disable safeguards to make a test pass.
5. **Rebuilds:** the base image and CLI packages are pinned; Debian packages resolve during build. ACA source import rebuilds and requires independent verification.
6. **Local workspace:** the helper mounts no repository and does not preserve the disposable workspace after exit.
