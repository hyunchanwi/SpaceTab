#!/bin/bash
# This runs without publishing/signing credentials. Private compiler output stays on the runner.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$1"
cd "$SOURCE"
LOG="${RUNNER_TEMP:-/tmp}/workshop-build.log"
trap 'rm -f "$LOG"' EXIT
echo 'Running browser model, native harness and migration checks.'
if ! bash scripts/test.sh > "$LOG" 2>&1; then
  echo 'Browser tests failed. No source text or diagnostic archive is published.'; exit 1
fi
python3 Tests/workshop-storage-name-tests.py > "$LOG" 2>&1
echo 'All browser tests passed. Building the release application.'
if ! CRA_WORKSHOP_RELEASE=1 CRA_VERSION="$VERSION" CRA_BUILD="$BUILD" bash scripts/build-workshop.sh release > "$LOG" 2>&1; then
  echo 'Release build failed. No update will be published.'; exit 1
fi
codesign --verify --deep --strict 'build/Arc Workshop.app'
echo 'Checking launch, clean quit and restored state on an isolated profile.'
if ! bash Tests/smoke-launch.sh 'build/Arc Workshop.app' > "$LOG" 2>&1; then
  echo 'Isolated launch/restore check failed. No update will be published.'; exit 1
fi
mkdir -p "$ROOT/dist"
ditto -c -k --keepParent 'build/Arc Workshop.app' "$ROOT/dist/Arc-Workshop.zip"
echo 'Release archive built and code-sign structure verified.'
