#!/usr/bin/env python3
"""Validate artifact identity and generate a signed Sparkle feed. Never executes the app."""
import argparse
import datetime
import hashlib
import json
import os
from collections import deque
from pathlib import Path
import plistlib
import subprocess
import stat
import shutil
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.json").read_text())
SPARKLE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ET.register_namespace("sparkle", SPARKLE)

# Bound parsing and extraction even before the signing identity is imported.
APP_ROOT = CONFIG["productName"] + ".app"
LEGACY_APP_ROOT = "Arc Workshop.app"
MAX_ARCHIVE_ENTRIES = 100_000
MAX_EXPANDED_BYTES = 4 * 1024**3
MAX_FILE_BYTES = 2 * 1024**3
MAX_PLIST_BYTES = 1024**2
MAX_LINK_BYTES = 4096


def archive_key(path):
    # The release is extracted on the default case-insensitive macOS filesystem.
    return unicodedata.normalize("NFC", path).casefold()


def validate_archive_paths(bundle, app_root=APP_ROOT):
    if app_root not in (APP_ROOT, LEGACY_APP_ROOT):
        raise ValueError("Unknown application identity")
    entries = bundle.infolist()
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise ValueError("Too many archive entries")
    seen, links, files = {}, {}, set()
    total = 0
    for entry in entries:
        name = entry.filename.rstrip("/")
        parts = name.split("/")
        if (not parts or parts[0] != app_root or len(parts) > 128
                or any(p in ("", ".", "..") for p in parts)
                or "\\" in name or "\x00" in entry.orig_filename
                or entry.filename != name + ("/" if entry.is_dir() else "")):
            raise ValueError("Unexpected release archive path")
        key = archive_key(name)
        if key in seen:
            raise ValueError("Duplicate archive entry")
        seen[key] = entry
        mode = stat.S_IFMT(entry.external_attr >> 16)
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK):
            raise ValueError("Unsupported archive file type")
        if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise ValueError("Unsupported archive encoding")
        total += entry.file_size
        if entry.file_size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES:
            raise ValueError("Archive extraction size limit exceeded")
        if mode == stat.S_IFLNK:
            if entry.is_dir() or not 0 < entry.file_size <= MAX_LINK_BYTES:
                raise ValueError("Invalid archive symlink")
            target = bundle.read(entry).decode("utf-8")
            if target.startswith("/") or "\x00" in target or "\\" in target:
                raise ValueError("Invalid archive symlink target")
            links[key] = target
        elif not entry.is_dir() and mode != stat.S_IFDIR:
            files.add(key)
        if len(parts) == 1 and (mode == stat.S_IFLNK or key in files):
            raise ValueError("Application root must be a directory")

    # Never let extraction order or a filesystem alias redirect an entry's writes.
    for key in seen:
        parts = key.split("/")
        for count in range(1, len(parts)):
            ancestor = "/".join(parts[:count])
            if ancestor in links or ancestor in files:
                raise ValueError("Archive entry has a non-directory ancestor")

    # Resolve all link components before '..', as the filesystem does. Lexical
    # normpath alone incorrectly accepts chained links which leave the bundle.
    for key, target in links.items():
        stack = key.split("/")[:-1]
        pending = deque(target.split("/"))
        hops = 0
        while pending:
            component = pending.popleft()
            if component in ("", "."):
                continue
            if component == "..":
                if len(stack) <= 1:
                    raise ValueError("Archive symlink escapes the application")
                stack.pop()
                continue
            stack.append(component)
            referenced = links.get(archive_key("/".join(stack)))
            if referenced is not None:
                hops += 1
                if hops > 40:
                    raise ValueError("Cyclic or excessive archive symlink chain")
                stack.pop()
                pending.extendleft(reversed(referenced.split("/")))


def application_root(bundle, allow_legacy_app_name=False):
    roots = {entry.filename.split("/", 1)[0] for entry in bundle.infolist()}
    return LEGACY_APP_ROOT if allow_legacy_app_name and roots == {LEGACY_APP_ROOT} else APP_ROOT


def validate(archive, plan, allow_legacy_app_name=False):
    with zipfile.ZipFile(archive) as bundle:
        app_root = application_root(bundle, allow_legacy_app_name)
        validate_archive_paths(bundle, app_root)
        manifest = bundle.getinfo(app_root + "/Contents/Info.plist")
        if manifest.file_size > MAX_PLIST_BYTES or stat.S_ISLNK(manifest.external_attr >> 16):
            raise ValueError("Invalid application manifest")
        info = plistlib.loads(bundle.read(manifest))
        feed = f'https://github.com/{CONFIG["distributionRepository"]}/releases/latest/download/appcast.xml'
        product_name = app_root.removesuffix(".app")
        expected = {"CFBundleIdentifier": CONFIG["bundleID"], "CFBundleVersion": plan["build"],
                    "CFBundleName": product_name, "CFBundleDisplayName": product_name,
                    "CFBundleShortVersionString": plan["version"], "SUPublicEDKey": CONFIG["publicKey"],
                    "SUFeedURL": feed, "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True}
        if any(info.get(k) != v for k, v in expected.items()) or "LSEnvironment" in info:
            raise ValueError("Release identity/update trust configuration mismatch")
        return info


def write_feed(archive, plan, info, signature):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = CONFIG["productName"]
    ET.SubElement(channel, "link").text = "https://github.com/" + CONFIG["distributionRepository"]
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = CONFIG["productName"] + " " + plan["version"]
    ET.SubElement(item, "pubDate").text = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    for key, value in [("version", plan["build"]), ("shortVersionString", plan["version"]),
                       ("minimumSystemVersion", info["LSMinimumSystemVersion"])]:
        ET.SubElement(item, "{" + SPARKLE + "}" + key).text = value
    notes = "Tested browser and Chromium/CEF maintenance update."
    status = json.loads((archive.parent / "signing-status.json").read_text())
    if status["mode"] == "persistent-personal":
        notes += " Uses the same personal application signing identity across versions. Not Apple notarized. The first transition from an ad-hoc build may need Keychain approval."
    else:
        notes += " Developer ID signed and Apple notarized."
    if plan.get("engineBuildNeeded"):
        notes += " Engine freshness needs attention; a newer stable engine may be awaiting a compatible patched binary. This update does not claim engine security parity with current Chrome."
    ET.SubElement(item, "description").text = notes
    ET.SubElement(item, "enclosure", {
        "url": f'https://github.com/{CONFIG["distributionRepository"]}/releases/download/v{plan["version"]}/{CONFIG["archiveName"]}',
        "type": "application/octet-stream", "length": str(archive.stat().st_size),
        "{" + SPARKLE + "}edSignature": signature})
    target = archive.parent / "appcast.xml"
    ET.ElementTree(rss).write(target, encoding="utf-8", xml_declaration=True)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--sign-tool", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    info = validate(args.archive, plan)
    status = json.loads((args.archive.parent / "signing-status.json").read_text())
    signing_policy = json.loads((ROOT / "signing.json").read_text())
    expected_status = {"mode": signing_policy["mode"], "certificateSHA256": signing_policy["certificateSHA256"],
                       "notarized": signing_policy["mode"] == "developer-id"}
    if status != expected_status:
        raise ValueError("Application signing policy was not satisfied")
    # Only the signing tool's stdin receives this key; do not copy it into child environments.
    key = os.environ.pop("SPARKLE_PRIVATE_KEY")
    signature = subprocess.run([str(args.sign_tool), "--ed-key-file", "-", "-p", str(args.archive)],
        input=key, text=True, capture_output=True, check=True).stdout.strip()
    feed = write_feed(args.archive, plan, info, signature)
    subprocess.run([str(args.sign_tool), "--ed-key-file", "-", str(feed)], input=key,
                   text=True, capture_output=True, check=True)
    digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    # Old bookmarked download URLs remain usable. Both names contain identical signed bytes.
    names = list(dict.fromkeys([CONFIG["archiveName"], CONFIG["legacyArchiveName"]]))
    for name in names:
        target = args.archive.parent / name
        if target.resolve() != args.archive.resolve():
            shutil.copyfile(args.archive, target)
    (args.archive.parent / "SHA256SUMS.txt").write_text("".join(digest + "  " + name + "\n" for name in names))
    public = {k: plan[k] for k in ["version", "build", "engine", "latestStableEngine", "engineBuildNeeded"]}
    public["latestStableChrome"] = plan.get("latestStableChrome")
    public["signing"] = status
    (args.archive.parent / "release.json").write_text(json.dumps(public, indent=2) + "\n")
    print("Validated update archive and signed update feed.")


if __name__ == "__main__":
    main()
