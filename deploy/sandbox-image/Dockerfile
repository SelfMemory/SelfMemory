# The agent sandbox image.
#
# Why an image rather than bind-mounting the host's agent binary: a binary is
# compiled for one libc and one architecture. A macOS host cannot execute its
# `opencode` inside a Linux container at all (`exec format error`), and a glibc
# binary will not run in a musl image. Building the agent into the image removes
# that coupling, and makes the image the single artifact that behaves the same
# on a developer's machine and in production.
#
# The image contains the agent and its runtime trust store, and nothing else of
# consequence. It is not where the boundary is — the boundary is the mount set
# the container is started with (see selfmemory/wiki/sandbox.py), which decides which
# directories exist inside. This image only needs to be *able* to run the agent.
#
#   docker build \
#     --build-arg AGENT_URL=https://…/opencode-linux-x64 \
#     -t selfmemory/sandbox:latest scripts/sandbox-image
#
FROM debian:bookworm-slim

# ca-certificates is required: the agent talks to the model API over TLS.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl bash \
 && rm -rf /var/lib/apt/lists/*

ARG AGENT_URL
ARG AGENT_SHA256

RUN test -n "$AGENT_URL" \
 || (echo "AGENT_URL build-arg is required — point it at a Linux build of the agent" >&2; exit 1)

RUN curl -fsSL "$AGENT_URL" -o /usr/local/bin/opencode \
 && chmod 0755 /usr/local/bin/opencode \
 && if [ -n "$AGENT_SHA256" ]; then \
      echo "$AGENT_SHA256  /usr/local/bin/opencode" | sha256sum -c -; \
    else \
      echo "warning: no AGENT_SHA256 supplied — the binary is unverified" >&2; \
    fi

# An unprivileged account to run as by default. The container primitive passes
# --user <host uid>:<host gid> on Linux so that files written into the bind-
# mounted scopes are owned by the host user; this account is the fallback when
# the container runs on a platform where that mapping is not available.
RUN useradd --system --create-home --shell /usr/sbin/nologin agent

# The agent needs somewhere to keep its session state. Mounted read-write by the
# runner at the host's agent home, so this is only a default for a bare run.
ENV HOME=/home/agent

# No ENTRYPOINT: the runner supplies the full argv, and the probe deliberately
# executes a different command (`/bin/sh -c …`) to test confinement.
CMD ["/bin/bash"]