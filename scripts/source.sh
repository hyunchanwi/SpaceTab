#!/bin/bash
# The deploy key is limited to the private source repository. Never persist a user token.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KEY_DIR="$(mktemp -d)"
trap 'rm -rf "$KEY_DIR"' EXIT
chmod 700 "$KEY_DIR"
printf '%s\n' "$SOURCE_DEPLOY_KEY" > "$KEY_DIR/key"
chmod 600 "$KEY_DIR/key"
unset SOURCE_DEPLOY_KEY
# GitHub's published host keys, committed and reviewed with this controller.
export GIT_SSH_COMMAND="ssh -i $KEY_DIR/key -o IdentitiesOnly=yes -o UserKnownHostsFile=$ROOT/github-known-hosts -o StrictHostKeyChecking=yes"
MODE="$1"; SOURCE="$2"
case "$MODE" in
  plan)
    git -c core.hooksPath=/dev/null clone --quiet git@github.com:hyunchanwi/arc-workshop.git "$SOURCE"
    python3 "$ROOT/scripts/maintenance.py" "$SOURCE" --run "$RUN_NUMBER" --output "$ROOT/plan.json" ${FORCE:+--force}
    ;;
  checkout)
    [[ "$CANDIDATE" =~ ^[0-9a-f]{40}$ ]]
    git -c core.hooksPath=/dev/null clone --quiet git@github.com:hyunchanwi/arc-workshop.git "$SOURCE"
    git -C "$SOURCE" -c core.hooksPath=/dev/null checkout --quiet "$CANDIDATE"
    ;;
  promote)
    [[ "$CANDIDATE" =~ ^[0-9a-f]{40}$ && "$BASE" =~ ^[0-9a-f]{40}$ ]]
    git -c core.hooksPath=/dev/null clone --quiet git@github.com:hyunchanwi/arc-workshop.git "$SOURCE"
    [ "$(git -C "$SOURCE" rev-parse HEAD)" = "$BASE" ] || { echo 'Source changed during build; publication stopped'; exit 1; }
    git -C "$SOURCE" merge-base --is-ancestor "$BASE" "$CANDIDATE"
    git -C "$SOURCE" push --quiet origin "$CANDIDATE:refs/heads/main"
    ;;
  *) exit 2 ;;
esac
