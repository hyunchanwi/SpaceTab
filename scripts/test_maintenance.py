#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


maintenance, publish = module("maintenance"), module("publish")


class MaintenanceTests(unittest.TestCase):
    def test_chrome_lead_is_reported_even_when_cef_has_not_caught_up(self):
        engine = "156.0.26+gabc+chromium-156.0.8078.88"
        current = {"versions": [{"version": "156.0.8078.88"}]}
        self.assertEqual(maintenance.engine_freshness(engine, engine, current), ("156.0.8078.88", False))
        self.assertEqual(maintenance.engine_freshness(engine, engine, {"versions": [
            {"version": "157.0.8103.39"}, {"version": "158.0.8127.18"}]}), ("158.0.8127.18", True))
        self.assertEqual(maintenance.engine_freshness(engine, engine, {}), (None, True))
        self.assertEqual(maintenance.engine_freshness(engine, engine, {"versions": [{"version": "not a version"}]}), (None, True))

    def test_personal_code_changes_trigger_builds_but_docs_and_release_records_do_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def stage():
                subprocess.run(["git", "-C", temp, "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "init", temp], check=True, capture_output=True)
            (root / "code.swift").write_text("first")
            (root / "README.md").write_text("first")
            (root / "workshop").mkdir()
            (root / "workshop/last-release.json").write_text("{}")
            stage(); first = maintenance.source_fingerprint(root)
            (root / "README.md").write_text("changed docs")
            (root / "workshop/last-release.json").write_text('{"version":"1.0.2"}')
            stage(); self.assertEqual(maintenance.source_fingerprint(root), first)
            (root / "code.swift").write_text("new personal feature")
            stage(); self.assertNotEqual(maintenance.source_fingerprint(root), first)

    def test_missing_or_unverified_engine_never_replaces_working_engine(self):
        old = {"version": "156.0.26+gabc+chromium-156.0.8078.88", "url": "old", "sha256": "a" * 64}
        new = "157.0.1+gdef+chromium-157.0.8103.39"
        release = {"tag_name": "cef-157.0.1-codecs1", "body": f"CEF {new} for macOS", "assets": [{"name": "cef_binary_macosarm64_minimal.tar.bz2",
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

    def test_new_patched_binary_for_same_engine_version_is_not_missed(self):
        v = "156.0.26+gabc+chromium-156.0.8078.88"
        prefix = "https://github.com/VictorKildahl/cra/releases/download/"
        old = {"version": v, "url": prefix + "cef-156.0.26-codecs2/cef_binary_macosarm64_minimal.tar.bz2", "sha256": "a" * 64}
        releases = [{"tag_name": "cef-156.0.26-codecs" + str(n), "body": f"CEF {v} for macOS", "assets": [{"name": "cef_binary_macosarm64_minimal.tar.bz2",
            "browser_download_url": prefix + "cef-156.0.26-codecs" + str(n) + "/cef_binary_macosarm64_minimal.tar.bz2",
            "digest": "sha256:" + "b" * 64}]} for n in [3, 10, 9]]
        self.assertIn("-codecs10/", maintenance.choose_engine(old, [v], releases)["url"])

    def test_patched_chromium_version_comes_from_the_published_binary_release(self):
        current = {"version": "156.0.26+gabc+chromium-156.0.8078.88", "url": "old", "sha256": "a" * 64}
        stock = "156.0.27+gdef+chromium-156.0.8078.88"
        actual = "156.0.27+gdef+chromium-156.0.8078.96"
        releases = []
        for codec in [1, 2]:
            tag = f"cef-156.0.27-codecs{codec}"
            releases.append({"tag_name": tag, "body": f"CEF {actual} for macOS", "assets": [{
                "name": "cef_binary_macosarm64_minimal.tar.bz2",
                "browser_download_url": f"https://github.com/VictorKildahl/cra/releases/download/{tag}/cef_binary_macosarm64_minimal.tar.bz2",
                "digest": "sha256:" + "b" * 64,
            }]})
        chosen = maintenance.choose_engine(current, [stock], releases)
        self.assertEqual(chosen["version"], actual)
        self.assertIn("-codecs2/", chosen["url"])
        # The stock index can still trail a patched binary on the next maintenance run.
        installed = dict(chosen, url=releases[0]["assets"][0]["browser_download_url"])
        self.assertEqual(maintenance.choose_engine(installed, [stock], releases), chosen)
        # An intermediate stable patched build remains eligible after stock moves ahead.
        newer_stock = "158.0.1+g123+chromium-158.0.8127.18"
        self.assertEqual(maintenance.choose_engine(current, [stock, newer_stock], releases), chosen)

    def test_missing_ambiguous_mismatched_and_older_binary_metadata_are_rejected(self):
        current = {"version": "156.0.26+gabc+chromium-156.0.8078.88", "url": "old", "sha256": "a" * 64}
        stock = "156.0.27+gdef+chromium-156.0.8078.88"
        actual = "156.0.27+gdef+chromium-156.0.8078.96"
        release = {"tag_name": "cef-156.0.27-codecs2", "assets": [{
            "name": "cef_binary_macosarm64_minimal.tar.bz2",
            "browser_download_url": "https://github.com/VictorKildahl/cra/releases/download/cef-156.0.27-codecs2/cef_binary_macosarm64_minimal.tar.bz2",
            "digest": "sha256:" + "b" * 64,
        }]}
        for body in [None, "CEF version unknown", f"CEF {actual}, previous {stock}",
                     "CEF 157.0.1+gdef+chromium-157.0.8103.39",
                     "CEF 156.0.27+gdef+chromium-156.0.8078.80"]:
            with self.subTest(body=body):
                release["body"] = body
                self.assertEqual(maintenance.choose_engine(current, [stock], [release]), current)

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
            with self.assertRaises(maintenance.UpstreamMergeConflict): maintenance.integrate(root, upstream)
            self.assertEqual(git("rev-parse", "HEAD"), before)
            self.assertEqual((root / "file").read_text(), "personal change\n")
            self.assertFalse((root / ".git/MERGE_HEAD").exists())

    def test_conflicting_source_keeps_previous_upstream_and_builds_new_engine(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def git(*args):
                return maintenance.git(root, *args).stdout.strip()

            git("init", "-b", "main")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (root / "behavior.swift").write_text("base\n")
            git("add", ".")
            git("commit", "-m", "base")
            previous_upstream = git("rev-parse", "HEAD")
            git("checkout", "-b", "upstream")
            (root / "behavior.swift").write_text("upstream\n")
            git("commit", "-am", "upstream")
            upstream = git("rev-parse", "HEAD")
            git("checkout", "main")
            (root / "behavior.swift").write_text("SpaceTab\n")
            (root / "scripts").mkdir()
            engine = "156.0.27+gabc+chromium-156.0.8078.96"
            (root / "scripts/fetch-cef.sh").write_text(f'CEF_VERSION="${{CEF_VERSION:-{engine}}}"\n')
            (root / "workshop").mkdir()
            (root / "workshop/engine.json").write_text(json.dumps({"version": engine, "url": "old", "sha256": "a" * 64}))
            (root / "workshop/last-release.json").write_text(json.dumps({"version": "1.0.1", "upstream": previous_upstream}))
            git("add", ".")
            git("commit", "-m", "SpaceTab")
            base = git("rev-parse", "HEAD")
            version = "156.0.28+gdef+chromium-156.0.8078.100"
            tag = "cef-156.0.28-codecs1"
            asset_name = "cef_binary_macosarm64_minimal.tar.bz2"
            upstream_repo = maintenance.CONFIG["upstreamRepository"]
            distribution = maintenance.CONFIG["distributionRepository"]
            responses = {
                f"https://api.github.com/repos/{upstream_repo}/releases/latest": {"tag_name": "v0.1.2"},
                f"https://api.github.com/repos/{upstream_repo}/releases?per_page=100": [{
                    "tag_name": tag, "body": version, "assets": [{
                        "name": asset_name, "digest": "sha256:" + "b" * 64,
                        "browser_download_url": f"https://github.com/{upstream_repo}/releases/download/{tag}/{asset_name}",
                    }],
                }],
                f"https://api.github.com/repos/{distribution}/releases/latest": {"tag_name": "v1.0.1"},
                "https://cef-builds.spotifycdn.com/index.json": {"macosarm64": {"versions": [
                    {"cef_version": version, "channel": "stable"},
                ]}},
            }
            real_git = maintenance.git

            def fixture_git(repo, *args, **kwargs):
                if args[0] == "fetch":
                    return real_git(repo, "fetch", ".", upstream)
                if args[0] == "push":
                    return real_git(repo, "branch", args[-1].split("/")[-1], "HEAD")
                return real_git(repo, *args, **kwargs)

            with patch.object(maintenance, "get_json", side_effect=responses.__getitem__), patch.object(
                maintenance, "git", side_effect=fixture_git
            ), patch.object(maintenance, "mac_chrome_versions", side_effect=[
                {"versions": [{"version": "158.0.8127.18"}]},
                {"versions": [{"version": "156.0.8078.100"}]},
            ]):
                plan = maintenance.prepare(root, "2", False)

            self.assertTrue(plan["changed"])
            self.assertTrue(plan["upstreamConflict"])
            self.assertTrue(plan["engineBuildNeeded"])
            self.assertEqual(plan["latestExtendedStableChrome"], "156.0.8078.100")
            self.assertEqual(plan["attemptedUpstream"], upstream)
            self.assertEqual(plan["engine"]["version"], version)
            self.assertEqual(git("rev-parse", "HEAD^"), base)
            self.assertEqual((root / "behavior.swift").read_text(), "SpaceTab\n")
            record = json.loads((root / "workshop/last-release.json").read_text())
            self.assertEqual(record["upstream"], previous_upstream)
            self.assertEqual(record["engine"], plan["engine"])
            self.assertEqual(git("status", "--porcelain"), "")

    def test_release_rejects_wrong_identity_key_feed_and_path(self):
        plan = {"version": "1.0.1", "build": "20261109010000"}
        config = publish.CONFIG
        good = {"CFBundleIdentifier": config["bundleID"], "CFBundleVersion": plan["build"],
                "CFBundleName": config["productName"], "CFBundleDisplayName": config["productName"],
                "CFBundleShortVersionString": plan["version"], "SUPublicEDKey": config["publicKey"],
                "SUFeedURL": f'https://github.com/{config["distributionRepository"]}/releases/latest/download/appcast.xml',
                "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True, "LSMinimumSystemVersion": "14.0"}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "app.zip"
            def write(info, extra=None):
                with zipfile.ZipFile(archive, "w") as z:
                    z.writestr("SpaceTab.app/Contents/Info.plist", plistlib.dumps(info))
                    if extra: z.writestr(extra, b"unexpected")
            write(good)
            self.assertEqual(publish.validate(archive, plan), good)
            for field in ["CFBundleIdentifier", "SUPublicEDKey", "SUFeedURL", "CFBundleVersion"]:
                bad = dict(good); bad[field] = "wrong"
                write(bad)
                with self.assertRaises(ValueError): publish.validate(archive, plan)
            write(good, "SpaceTab.app/../../outside")
            with self.assertRaises(ValueError): publish.validate(archive, plan)


if __name__ == "__main__": unittest.main()
