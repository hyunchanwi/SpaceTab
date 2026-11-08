#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
import zipfile


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


maintenance, publish = module("maintenance"), module("publish")


class MaintenanceTests(unittest.TestCase):
    def test_missing_or_unverified_engine_never_replaces_working_engine(self):
        old = {"version": "156.0.26+gabc+chromium-156.0.8078.88", "url": "old", "sha256": "a" * 64}
        new = "157.0.1+gdef+chromium-157.0.8103.39"
        release = {"tag_name": "cef-157.0.1-codecs1", "assets": [{"name": "cef_binary_macosarm64_minimal.tar.bz2",
                    "digest": None, "browser_download_url": "https://github.com/VictorKildahl/cra/releases/download/cef-157.0.1-codecs1/cef_binary_macosarm64_minimal.tar.bz2"}]}
        self.assertEqual(maintenance.choose_engine(old, [new], [release]), old)
        release["assets"][0]["digest"] = "sha256:" + "b" * 64
        self.assertEqual(maintenance.choose_engine(old, [new], [release])["version"], new)
        release["assets"][0]["browser_download_url"] = "https://example.org/substituted.tar.bz2"
        self.assertEqual(maintenance.choose_engine(old, [new], [release]), old)

    def test_engine_order_uses_chromium_and_never_downgrades(self):
        current = {"version": "156.0.26+gabc+chromium-156.0.8078.88", "url": "old", "sha256": "a" * 64}
        self.assertEqual(maintenance.choose_engine(current, ["156.0.15+gabc+chromium-156.0.8078.80"], []), current)
        self.assertGreater(maintenance.version("157.0.1+gabc+chromium-157.0.1.1"), maintenance.version(current["version"]))

    def test_source_conflict_aborts_and_keeps_personal_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def git(*args):
                return subprocess.check_output(["git", "-C", temp, *args], text=True, stderr=subprocess.DEVNULL).strip()
            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (root / "file").write_text("base\n")
            git("add", "."); git("commit", "-m", "base")
            git("checkout", "-b", "upstream")
            (root / "file").write_text("upstream change\n")
            git("commit", "-am", "upstream")
            upstream = git("rev-parse", "HEAD")
            git("checkout", "main")
            (root / "file").write_text("personal change\n")
            git("commit", "-am", "personal")
            before = git("rev-parse", "HEAD")
            with self.assertRaises(RuntimeError): maintenance.integrate(root, upstream)
            self.assertEqual(git("rev-parse", "HEAD"), before)
            self.assertEqual((root / "file").read_text(), "personal change\n")
            self.assertFalse((root / ".git/MERGE_HEAD").exists())

    def test_release_rejects_wrong_identity_key_feed_and_path(self):
        plan = {"version": "1.0.1", "build": "20261109010000"}
        config = publish.CONFIG
        good = {"CFBundleIdentifier": config["bundleID"], "CFBundleVersion": plan["build"],
                "CFBundleShortVersionString": plan["version"], "SUPublicEDKey": config["publicKey"],
                "SUFeedURL": f'https://github.com/{config["distributionRepository"]}/releases/latest/download/appcast.xml',
                "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True, "LSMinimumSystemVersion": "14.0"}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "app.zip"
            def write(info, extra=None):
                with zipfile.ZipFile(archive, "w") as z:
                    z.writestr("Arc Workshop.app/Contents/Info.plist", plistlib.dumps(info))
                    if extra: z.writestr(extra, b"unexpected")
            write(good)
            self.assertEqual(publish.validate(archive, plan), good)
            for field in ["CFBundleIdentifier", "SUPublicEDKey", "SUFeedURL", "CFBundleVersion"]:
                bad = dict(good); bad[field] = "wrong"
                write(bad)
                with self.assertRaises(ValueError): publish.validate(archive, plan)
            write(good, "Arc Workshop.app/../../outside")
            with self.assertRaises(ValueError): publish.validate(archive, plan)


if __name__ == "__main__": unittest.main()
