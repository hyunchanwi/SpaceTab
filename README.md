# Arc Workshop updates

Signed update files and the generic maintenance controller for a personal macOS browser.
The browser source is private. This repository contains no browsing profiles, cookies,
passwords, tab lists or source/compiler logs.

Maintenance checks upstream stable releases and codec-enabled CEF binaries every six hours.
Source conflicts, missing engine checksums, failed tests, failed builds or unexpected app
identities stop publication. A newer stable engine without an available patched binary is
reported as requiring maintainer attention; it is never substituted with an incompatible build.

Builds run without the update signing key or release-write token. A separate job validates
the resulting app identity, signs its archive and feed, and publishes them. Only a dedicated
deploy key scoped to the private source repository is used; no personal access token is stored.
All actions are pinned by commit. Pull requests cannot run maintenance or access secrets.

Updates require their own Ed25519 signature. These personal builds are ad-hoc code signed,
not Apple-notarized releases. macOS may ask to approve this app's own Keychain item after
an update. A Developer ID certificate can be added later to stabilize that identity.

## Failure recovery

The installed app saves a local rollback copy of its previous app and browsing profile
before proceeding with an update. It refreshes the profile after Chromium shuts down.
Those backups stay on the Mac; they are never uploaded here.

Scheduled runs do no macOS build when neither source nor engine has changed. Failed
maintenance is visible in Actions and a single maintenance-attention issue.
