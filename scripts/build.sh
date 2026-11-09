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
  echo 'Browser tests failed. No source text or diagnostic archive is published.'
  # Only numeric group IDs and one-way location fingerprints leave this private log.
  python3 - "$LOG" <<'PY'
import hashlib, pathlib, re, sys
lines = pathlib.Path(sys.argv[1]).read_text(errors='replace').splitlines()
groups = [line[4:] for line in lines if line.startswith('==> ')][:99]
for number, name in enumerate(groups, 1):
    if 'Failed: ' + name in lines:
        print('Browser check group failed:', number)
seen = set()
for line in lines:
    match = re.search(r'([A-Za-z0-9_+.-]+\.swift):(\d+):', line)
    if match and any(word in line for word in ['error:', 'Expectation failed', 'recorded an issue']):
        seen.add((hashlib.sha256(match[1].encode()).hexdigest()[:12], int(match[2])))
for fingerprint, number in sorted(seen)[:20]:
    print('Browser failure location fingerprint:', fingerprint, 'line:', number)
PY
  exit 1
fi
python3 Tests/workshop-storage-name-tests.py > "$LOG" 2>&1
echo 'All browser tests passed. Building the release application.'
if ! CRA_WORKSHOP_RELEASE=1 CRA_VERSION="$VERSION" CRA_BUILD="$BUILD" bash scripts/build-workshop.sh release > "$LOG" 2>&1; then
  echo 'Release build failed. No update will be published.'; exit 1
fi
codesign --verify --deep --strict 'build/SpaceTab.app'
echo 'Checking signed-update tampering with disposable keys.'
if ! python3 Tests/update-signature-security.py > "$LOG" 2>&1; then
  echo 'Update signature security checks failed. No update will be published.'; exit 1
fi
echo 'Checking launch, clean quit and restored state on an isolated profile.'
if ! bash Tests/smoke-launch.sh 'build/SpaceTab.app' > "$LOG" 2>&1; then
  echo 'Isolated launch/restore check failed. No update will be published.'; exit 1
fi
mkdir -p "$ROOT/dist"
ditto -c -k --keepParent 'build/SpaceTab.app' "$ROOT/dist/Arc-Workshop.zip"
echo 'Release archive built and code-sign structure verified.'
