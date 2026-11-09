# Persistent application signing

## Current choice

The maintainer does not currently have a confirmed Apple Developer Program membership.
The pipeline therefore supports a persistent **self-signed personal code-signing identity**.
Every release uses the same certificate and a designated requirement bound to that
certificate and the executable's signing identifier. This avoids tying Keychain identity
to a different ad-hoc code hash for each build.

Apple documents that the Keychain tracks an app's designated requirement and can use
self-signed identities for this purpose. Gatekeeper has different trust rules; a personal
certificate does **not** make an app Apple Developer ID signed or notarized.
[Apple: macOS Code Signing In Depth](https://developer.apple.com/library/archive/technotes/tn2206/_index.html)

The first transition from older ad-hoc builds can require Keychain approval. Approval must
be granted in macOS by the user. This pipeline does not weaken the storage item's access
control, switch to a public mock encryption key or read the user's Mac password.

## Personal identity setup

`scripts/create-signing-identity.py <private-directory>` creates a long-lived certificate,
password-protected PKCS#12 archive and random archive password. It refuses to overwrite an
existing identity. Preserve these private files securely; routine builds must not regenerate them.

Only the **public** DER certificate belongs in `signing/app-signing.cer`. Pin its SHA-256 in
`signing.json` with mode `persistent-personal`. Private material must never be committed.

The public distribution repository's encrypted Actions Secrets need:

| Secret | Value |
| --- | --- |
| `APP_SIGNING_P12` | Base64-encoded PKCS#12 identity, including its private signing key. |
| `APP_SIGNING_PASSWORD` | Password for that PKCS#12 archive. |
| `SPARKLE_PRIVATE_KEY` | Separate existing update-signing key. |
| `SOURCE_DEPLOY_KEY` | Existing SSH deploy key restricted to the private source repository. |

The new app-signing secrets require the owner's approval before registration. A private
app-signing key can sign code claiming this app identity; the independent Sparkle key is
still required to produce an accepted in-app update. Do not reuse the browser encryption
key, a personal SSH key or an Apple account password.

During publishing, the identity is imported into an isolated, short-lived Keychain. Only
the system code-signing tool is granted access. No global certificate trust is installed.
The temporary Keychain and extracted files are removed after signing. Source builds never
receive the real signing identity; browser code is not executed by the publisher.

The macOS integration test signs two different fixture executables with one test certificate.
The first creates an item in an isolated test Keychain. The second reads it with user
interaction disabled. It checks both matching designated requirements and successful access;
it does not touch the live Workshop Storage item.

## Later: Developer ID and Apple notarization

For conventional distribution to other Macs:

1. Join/confirm membership in the Apple Developer Program and create a **Developer ID Application** certificate. Export its certificate and private key as a password-protected PKCS#12.
2. Replace the two app-signing secrets through an approved secure setup. Commit only its public DER certificate and SHA-256 pin. Set `signing.json` mode to `developer-id` and add `teamID`.
3. Create dedicated App Store Connect API notarization credentials. Configure `NOTARY_API_PRIVATE_KEY`, `NOTARY_API_KEY_ID` and `NOTARY_API_ISSUER` as encrypted Actions Secrets. Do not put an Apple account login password into this workflow.
4. Dispatch maintenance. Developer ID mode requires timestamped hardened-runtime signing, successful Apple notarization, stapling, ticket validation and Gatekeeper assessment before release publication.
5. Test the transition on an existing profile. The change from the personal certificate may require another Keychain approval. Keep the app's bundle ID and **Workshop Storage** service unchanged.

Example policy structure (replace the placeholders; this is not an active configuration):

```json
{
  "mode": "developer-id",
  "certificateSHA256": "<64 lowercase hexadecimal characters>",
  "teamID": "<10-character Apple team identifier>"
}
```

If credentials are missing or a certificate pin differs, publishing fails. A key loss,
expiry or compromise requires a planned rotation, not an automatically generated replacement.
The current personal certificate expires in November 2036. This does not establish a
ten-year engine-maintenance commitment.

[Apple Developer ID](https://developer.apple.com/developer-id/) ·
[Notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
