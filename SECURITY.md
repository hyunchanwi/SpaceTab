# Security reports

For a sensitive vulnerability, use this repository's
[private vulnerability report](https://github.com/hyunchanwi/arc-workshop-updates/security/advisories/new).
Do not put exploit details, credentials, browsing profiles or Keychain exports into public issues.

For ordinary bugs, use the issue forms. Remove account names, personal URLs and session tokens
from screenshots or logs. The maintainer does not need your Mac login password.

SpaceTab is experimental, has not had an independent security audit, and currently
publishes personal builds without Apple notarization. Compatible CEF availability and
integration checks constrain engine-update delivery. A local recovery snapshot is not a
substitute for timely security updates.

## Current protection limits

The Cra-based engine does not currently provide Google Safe Browsing warnings for known
phishing or malware sites. Ad blocking does not replace URL/download reputation checks.
Chromium renderer sandboxing and signed updates address different boundaries.

Maintenance compares our compatible patched CEF build with both available stable CEF and
Google's macOS stable Chrome versions. A newer Chrome version can exist before a compatible
patched engine is available here; release metadata and maintenance status report that gap.
An unavailable version service is reported as unknown rather than up to date.

Release gates include hostile archive-path fixtures, extension-import checks, disposable-key
update signature tampering checks, and real-browser origin/profile/TLS checks on an isolated
runner. These checks are not an independent penetration-test certification and cannot rule out
all vulnerabilities in Chromium, CEF, extensions or this application.
