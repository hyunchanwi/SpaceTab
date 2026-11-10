#!/bin/bash
# Runs on a fresh runner with no app/update signing credentials or publishing permission.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$1"
STAGE="$(mktemp -d "${RUNNER_TEMP:-/tmp}/workshop-final-check.XXXXXX")"
LOG="$STAGE/check.log"
trap 'rm -rf "$STAGE"' EXIT
cd "$ROOT"
python3 - "$STAGE/app-root" <<'PY'
import hashlib, json, os, pathlib, sys, zipfile
sys.path.insert(0, 'scripts')
import publish
allow_legacy = os.environ.get('WORKSHOP_ALLOW_LEGACY_APP_NAME') == '1'
archive = pathlib.Path('dist/Arc-Workshop.zip')
publish.validate(archive, json.load(open('plan.json')), allow_legacy_app_name=allow_legacy)
with zipfile.ZipFile(archive) as bundle:
    pathlib.Path(sys.argv[1]).write_text(publish.application_root(bundle, allow_legacy))
policy = json.load(open('signing.json'))
certificate = pathlib.Path('signing/app-signing.cer').read_bytes()
assert hashlib.sha256(certificate).hexdigest() == policy['certificateSHA256']
status = json.load(open('dist/signing-status.json'))
assert status == {'mode': policy['mode'], 'certificateSHA256': policy['certificateSHA256'], 'notarized': policy['mode'] == 'developer-id'}
PY
ditto -x -k dist/Arc-Workshop.zip "$STAGE"
APP="$STAGE/$(cat "$STAGE/app-root")"
codesign --verify --deep --strict "$APP"
CERT_SHA1=$(openssl x509 -inform DER -in signing/app-signing.cer -noout -fingerprint -sha1 | cut -d= -f2 | tr -d ':')
codesign --verify -R "=certificate leaf = H\"$CERT_SHA1\"" "$APP"
if ! (cd "$SOURCE" && bash Tests/smoke-launch.sh "$APP") > "$LOG" 2>&1; then
  echo 'Final signed app launch/restore check failed; no update will be published.'
  exit 1
fi
echo 'Final signed app launched, quit and restored state on an isolated profile.'
if ! (cd "$SOURCE" && python3 Tests/security-runtime.py "$APP") > "$LOG" 2>&1; then
  echo 'Final browser runtime security checks failed; no update will be published.'
  # Only this fixed-format summary is public; browser logs and private source stay on the runner.
  sed -n '/^Runtime security:/p' "$LOG"
  exit 1
fi
sed -n '/^Runtime security:/p' "$LOG"
if ! (cd "$SOURCE" && python3 Tests/presentation-runtime.py "$APP") > "$LOG" 2>&1; then
  echo 'Final native presentation checks failed; no update will be published.'
  sed -n '/^Presentation runtime:/p' "$LOG"
  exit 1
fi
sed -n '/^Presentation runtime:/p' "$LOG"
if [ "$(/usr/libexec/PlistBuddy -c 'Print :SpaceTabBackgroundInspectionVersion' "$APP/Contents/Info.plist" 2>/dev/null || true)" = 1 ]; then
  if ! (cd "$SOURCE" && python3 Tests/background-inspection-runtime.py "$APP") > "$LOG" 2>&1; then
    echo 'Final background inspection checks failed; no update will be published.'
    sed -n '/^Background inspection:/p' "$LOG"
    exit 1
  fi
  sed -n '/^Background inspection:/p' "$LOG"
fi
