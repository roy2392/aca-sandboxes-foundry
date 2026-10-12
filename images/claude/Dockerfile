FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git python3 python3-venv ripgrep tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /bin/bash agent \
    && mkdir -p /workspace /home/agent/.claude \
    && chown -R agent:agent /workspace /home/agent
COPY claude/vendor/ /opt/claude/
RUN node /opt/claude/node_modules/@anthropic-ai/claude-code/install.cjs
COPY common/launch.py /opt/foundry/launch.py
COPY claude/claude /usr/local/bin/claude
RUN chmod 0755 /usr/local/bin/claude
ENV HOME=/home/agent \
    CLAUDE_CODE_USE_FOUNDRY=1 \
    DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
USER agent
WORKDIR /workspace
RUN /opt/claude/node_modules/.bin/claude --version
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]
