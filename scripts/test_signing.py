#!/usr/bin/env python3
"""Release trust checks plus an opt-in macOS identity/Keychain continuity test."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import secrets
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
import zipfile

import codesign_app
import publish


class SigningTests(unittest.TestCase):
    def test_historical_app_name_requires_explicit_read_only_compatibility(self):
        config = publish.CONFIG
        plan = {"version": "1.0.10", "build": "20261109070613"}
        info = {"CFBundleIdentifier": config["bundleID"], "CFBundleVersion": plan["build"],
                "CFBundleShortVersionString": plan["version"], "CFBundleName": "Arc Workshop",
                "CFBundleDisplayName": "Arc Workshop", "SUPublicEDKey": config["publicKey"],
                "SUFeedURL": f'https://github.com/{config["distributionRepository"]}/releases/latest/download/appcast.xml',
                "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "old.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("Arc Workshop.app/Contents/Info.plist", plistlib.dumps(info))
            with self.assertRaises(ValueError): publish.validate(archive, plan)
            self.assertEqual(publish.validate(archive, plan, allow_legacy_app_name=True), info)
            with zipfile.ZipFile(archive, "a") as bundle:
                bundle.writestr("SpaceTab.app/payload", "fixture")
            with self.assertRaises(ValueError): publish.validate(archive, plan, allow_legacy_app_name=True)

    def test_external_tools_do_not_inherit_actions_credentials(self):
        fixture = {key: "fixture-secret" for key in codesign_app.SECRET_ENV}
        with patch.dict(os.environ, fixture), patch.object(codesign_app.subprocess, "run") as run:
            run.return_value = Mock(returncode=0, stdout="", stderr="")
            codesign_app.run("ditto", "fixture")
            environment = run.call_args.kwargs["env"]
            self.assertFalse(codesign_app.SECRET_ENV.intersection(environment))
            self.assertIn("PATH", environment)

    def test_release_entitlements_do_not_allow_dyld_environment_injection(self):
        with tempfile.TemporaryDirectory() as temp:
            for file in codesign_app.write_entitlements(Path(temp)):
                entitlements = plistlib.loads(file.read_bytes())
                self.assertNotIn("com.apple.security.cs.allow-dyld-environment-variables", entitlements)
                self.assertNotIn("com.apple.security.get-task-allow", entitlements)
                self.assertTrue(entitlements["com.apple.security.cs.allow-jit"])

    def test_release_policy_never_falls_back_to_ad_hoc(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(codesign_app, "ROOT", root):
                for bad in [{"mode": "adhoc", "certificateSHA256": "a" * 64},
                            {"mode": "persistent-personal", "certificateSHA256": ""},
                            {"mode": "developer-id", "certificateSHA256": "a" * 64}]:
                    (root / "signing.json").write_text(json.dumps(bad))
                    with self.assertRaises(ValueError): codesign_app.policy()

    def test_symlinks_are_never_signing_targets_and_nested_containers_are_first(self):
        with tempfile.TemporaryDirectory() as temp:
            app = Path(temp) / "SpaceTab.app"
            main = app / "Contents/MacOS/Cra"
            nested = app / "Contents/Frameworks/Example.framework/Versions/A/Updater.app"
            nested.mkdir(parents=True)
            main.parent.mkdir(parents=True)
            main.write_bytes(b"\xcf\xfa\xed\xfe" + b"fixture")
            (main.parent / "alias").symlink_to("Cra")
            binaries, containers = codesign_app.signing_targets(app)
            self.assertEqual(binaries, [main])
            self.assertLess(containers.index(nested), containers.index(app / "Contents/Frameworks/Example.framework"))
            self.assertEqual(containers[-1], app)

    def test_archive_rejects_links_outside_app_and_duplicate_entries(self):
        config = publish.CONFIG
        plan = {"version": "1.0.1", "build": "20261109010000"}
        info = {"CFBundleIdentifier": config["bundleID"], "CFBundleVersion": plan["build"],
                "CFBundleName": config["productName"], "CFBundleDisplayName": config["productName"],
                "CFBundleShortVersionString": plan["version"], "SUPublicEDKey": config["publicKey"],
                "SUFeedURL": f'https://github.com/{config["distributionRepository"]}/releases/latest/download/appcast.xml',
                "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "app.zip"
            for target in ["/tmp/outside", "../../outside", "Versions/A"]:
                with zipfile.ZipFile(archive, "w") as bundle:
                    bundle.writestr("SpaceTab.app/Contents/Info.plist", plistlib.dumps(info))
                    link = zipfile.ZipInfo("SpaceTab.app/Current")
                    link.create_system = 3
                    link.external_attr = (stat.S_IFLNK | 0o777) << 16
                    bundle.writestr(link, target)
                if target == "Versions/A":
                    publish.validate(archive, plan)
                else:
                    with self.assertRaises(ValueError): publish.validate(archive, plan)
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("SpaceTab.app/Contents/Info.plist", plistlib.dumps(info))
                bundle.writestr("SpaceTab.app/file", "first")
                bundle.writestr("SpaceTab.app/FILE", "second")
            with self.assertRaises(ValueError): publish.validate(archive, plan)

    @unittest.skipUnless(sys.platform == "darwin" and os.environ.get("WORKSHOP_SIGNING_INTEGRATION") == "1", "opt-in macOS test")
    def test_two_different_builds_share_identity_and_keychain_access_without_ui(self):
        with tempfile.TemporaryDirectory(prefix="workshop-signing-test-") as temp:
            directory = Path(temp)
            subprocess.run([sys.executable, str(Path(__file__).with_name("create-signing-identity.py")), temp],
                           capture_output=True, check=True)
            certificate = directory / "app-signing.cer"
            import hashlib
            sha1 = hashlib.sha1(certificate.read_bytes()).hexdigest().upper()
            keychain = directory / "test.keychain-db"
            password = secrets.token_urlsafe(32)
            run = codesign_app.run
            previous_keychains = None
            try:
                run("security", "create-keychain", "-p", password, str(keychain))
                run("security", "unlock-keychain", "-p", password, str(keychain))
                run("security", "import", str(directory / "app-signing.p12"), "-k", str(keychain),
                    "-P", (directory / "app-signing-password").read_text(), "-T", "/usr/bin/codesign")
                run("security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", password, str(keychain))
                previous_keychains = codesign_app.add_to_keychain_search_list(keychain)
                print(run("security", "find-identity", "-p", "codesigning", str(keychain)).strip())
                source = directory / "probe.swift"
                source.write_text('''import Foundation
import Security
SecKeychainSetUserInteractionAllowed(false)
var keychain: SecKeychain?
guard SecKeychainOpen(CommandLine.arguments[1], &keychain) == errSecSuccess, let keychain else { exit(10) }
let status: OSStatus
if CommandLine.arguments[2] == "create" {
    status = SecKeychainAddGenericPassword(keychain, 20, "Workshop Test Secret", 7, "fixture", 7, "private", nil)
} else {
    var list: CFArray = [keychain] as CFArray
    var length: UInt32 = 0
    var content: UnsafeMutableRawPointer?
    status = SecKeychainFindGenericPassword(list, 20, "Workshop Test Secret", 7, "fixture", &length, &content, nil)
    if let content { SecKeychainItemFreeContent(nil, content) }
}
guard status == errSecSuccess else { print("Keychain status: \\(status)"); exit(11) }
print("fixture build VERSION succeeded")
''')
                requirements = []
                for number, operation in [(1, "create"), (2, "read")]:
                    variant = directory / f"probe{number}.swift"
                    variant.write_text(source.read_text().replace("VERSION", str(number)))
                    executable = directory / f"probe{number}"
                    run("xcrun", "swiftc", str(variant), "-o", str(executable))
                    run("codesign", "--force", "--sign", sha1, "--keychain", str(keychain),
                        "--identifier", "local.workshop.identity-test", "--timestamp=none", "--requirements",
                        f'=designated => identifier "local.workshop.identity-test" and certificate leaf = H"{sha1}"', str(executable))
                    run("codesign", "--verify", "-R", f'=certificate leaf = H"{sha1}"', str(executable))
                    requirements.append(run("codesign", "-dr", "-", str(executable)).split("designated =>", 1)[1].splitlines()[0].strip())
                    result = run(str(executable), str(keychain), operation)
                    self.assertIn(f"fixture build {number} succeeded", result)
                self.assertEqual(requirements[0], requirements[1])
                self.assertNotEqual((directory / "probe1").read_bytes(), (directory / "probe2").read_bytes())
            finally:
                if previous_keychains is not None:
                    subprocess.run(["security", "list-keychains", "-d", "user", "-s", *previous_keychains], capture_output=True)
                subprocess.run(["security", "delete-keychain", str(keychain)], capture_output=True)


if __name__ == "__main__":
    unittest.main()
