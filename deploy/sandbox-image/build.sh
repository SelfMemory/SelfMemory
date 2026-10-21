#!/usr/bin/env bash
# Build the agent sandbox image used by the container isolation primitive.
#
#   AGENT_URL=https://.../opencode-linux-x64 AGENT_SHA256=<sha> \
#     deploy/sandbox-image/build.sh [tag]
#
# Then point the server at it with SELFMEMORY_SANDBOX_IMAGE=<tag>, and check
# the host with `make isolation`: the agent probe must pass.
set -euo pipefail
: "${AGENT_URL:?set AGENT_URL to a Linux build of opencode}"
tag="${1:-selfmemory/sandbox:latest}"
here="$(cd "$(dirname "$0")" && pwd)"
docker build \
  --build-arg AGENT_URL="$AGENT_URL" \
  --build-arg AGENT_SHA256="${AGENT_SHA256:-}" \
  -t "$tag" "$here"
echo "built $tag"
