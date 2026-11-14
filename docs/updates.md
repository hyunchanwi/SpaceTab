# Update architecture

SpaceTab uses two independent signatures:

| Check | Purpose |
| --- | --- |
| Application code signing | Keep the app's identity stable across builds and seal native code and resources. Persistent personal signing is not Apple Developer ID trust. |
| Sparkle Ed25519 signatures | Authenticate the update feed and ZIP before extraction. These use a separate key from app signing and browser storage. |

## Pipeline

1. **Plan:** every six hours, inspect upstream stable source and compatible codec-enabled CEF assets. Verify engine checksums and merge into a candidate branch. No private source is printed in public logs.
2. **Test/build:** run native/model checks, build an ad-hoc intermediate artifact, and check isolated launch, quit and restore. This job has no publishing token or real app/update signing key. A separate test identity verifies code-signing and Keychain continuity.
3. **Sign:** validate the artifact bundle identifier, version, feed URL, update key and ZIP paths. Import the pinned app-signing identity into a temporary Keychain. Sign nested code from the inside out, then verify strictly. The browser is never run in the signing job.
4. **Notarize, when configured:** Developer ID mode additionally requires Apple notarization, ticket stapling and Gatekeeper assessment. Personal mode never claims notarization.
5. **Verify signed app:** on a fresh runner without app/update signing credentials or release-write permission, validate the final certificate and run isolated launch, quit, restore and browser origin/profile/TLS boundary checks on the signed app.
6. **Publish:** sign the final ZIP and appcast with the dedicated Sparkle key, upload a draft, promote the tested source, then make the release public. A failed prerequisite stops publication. After publication, send the already-public signed appcast to the release-signal service.
7. **Install:** the app verifies updates, prepares a local app/profile snapshot, and installs after the user chooses. The profile snapshot is refreshed on clean Chromium shutdown.

Source changes, engine changes and signing-policy changes trigger a build. Documentation
changes alone do not. A successful unchanged run skips the macOS build and publication.
The displayed release version is generated from the maintenance run number; gaps are normal.

The build checks Sparkle's actual signature tool with disposable keys and tampered archives
and feeds. Signing imports the persistent identity only after bounded ZIP validation,
extraction and native-binary inspection. External tools do not inherit Actions credentials.
Release entitlements retain CEF's JIT requirements but disable DYLD environment injection.

Engine freshness is checked against stable CEF availability and Google's macOS Chrome
Stable and Extended Stable version history. `release.json` records both Chrome versions
when available. A lag or failed lookup raises maintenance attention.

When a Cra source merge conflicts, the planner aborts the merge and confirms the source
tree is clean. It can still check and build a compatible engine against the existing
SpaceTab source. The full build, signing and verification checks apply to that candidate.
The conflict remains visible in the maintenance issue and release metadata.

## Release events

Connected applications receive a small version/build hint from the dedicated Cloudflare
Worker. The service accepts only appcasts signed by the existing update key; it stores the
latest hint and rejects unsigned, modified and older announcements. A hint can request only
a normal Sparkle check: it supplies no installation command or download URL to the app.
Sparkle still verifies the signed feed and archive. No additional publishing secret is used.

The client sends no tabs, profile contents, cookies or device identifier. Cloudflare handles
the connection and its ordinary network metadata. Sleep/network loss triggers reconnection,
and the latest hint is delivered when it reconnects. A busy updater retains the pending hint;
checks are rate-limited and bounded retries cover a briefly stale GitHub feed. Periodic and
manual checks remain available if signal delivery fails. Event delivery is not guaranteed
within a particular number of seconds.

## Public release files

| File | Purpose |
| --- | --- |
| `SpaceTab.zip` | Application to move into Applications. |
| `Arc-Workshop.zip` | Compatibility download alias containing the same signed bytes as SpaceTab.zip. |
| `appcast.xml` | Signed update feed used by Sparkle. |
| `release.json` | Public app/build and engine metadata, including signing status for new releases. |
| `signing-status.json` | Signing mode, public certificate fingerprint and notarization status for new releases. |
| `SHA256SUMS.txt` | SHA-256 checksum for the ZIP. |

Checksums help detect a mismatched download; Sparkle's signature is the update-authentication
mechanism. The public certificate is in `signing/app-signing.cer`. Its fingerprint is pinned
in `signing.json`; it is public verification material, not a private key.

## Boundaries

- Compatible engine binaries come from upstream Cra. Missing binaries, merge conflicts and failed checks require a maintainer; the pipeline cannot resolve every future change itself.
- GitHub schedules can be delayed. Public repositories without activity for 60 days can have schedules disabled. The owner must re-enable **Browser maintenance** in Actions.
- Updates are not a promise of immediate Chromium security-patch delivery. Inspect the engine version in each release.
- Recovery snapshots are local and manual to restore. This is not a recurring off-device backup service.
- Changes to the signing identity need an explicit review and can cause another Keychain prompt. There is no silent fallback to ad-hoc signing.

See [signing setup](signing.md) and [GitHub's schedule policy](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).

## Repository name and compatibility addresses

The public repository is `hyunchanwi/SpaceTab`. The original
`hyunchanwi/arc-workshop-updates` path remains the signed update delivery address:
GitHub redirects it to the same repository. The controller, relay and installed clients
keep that exact allowlisted address, so published signed feeds are not rewritten.
Do not create a new repository at the original path: that would remove its redirect.
The bundle ID, storage folders, Keychain service, certificates and update signing key
are independent of this display-name change and remain unchanged.
