FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git python3 python3-venv ripgrep tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /bin/bash agent \
    && mkdir -p /workspace /home/agent/.codex /etc/foundry \
    && chown -R agent:agent /workspace /home/agent
COPY codex/vendor/ /opt/codex/
COPY common/launch.py /opt/foundry/launch.py
COPY codex/codex /usr/local/bin/codex
COPY codex/config.toml /opt/foundry/codex-config.toml
RUN chmod 0755 /usr/local/bin/codex
ENV HOME=/home/agent
USER agent
WORKDIR /workspace
RUN /opt/codex/node_modules/.bin/codex --version
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]
