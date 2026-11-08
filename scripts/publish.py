#!/usr/bin/env python3
"""Validate artifact identity and generate a signed Sparkle feed. Never executes the app."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.json").read_text())
SPARKLE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ET.register_namespace("sparkle", SPARKLE)


def validate(archive, plan):
    with zipfile.ZipFile(archive) as bundle:
        info = plistlib.loads(bundle.read("Arc Workshop.app/Contents/Info.plist"))
        feed = f'https://github.com/{CONFIG["distributionRepository"]}/releases/latest/download/appcast.xml'
        expected = {"CFBundleIdentifier": CONFIG["bundleID"], "CFBundleVersion": plan["build"],
                    "CFBundleShortVersionString": plan["version"], "SUPublicEDKey": CONFIG["publicKey"],
                    "SUFeedURL": feed, "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True}
        if any(info.get(k) != v for k, v in expected.items()) or "LSEnvironment" in info:
            raise ValueError("Release identity/update trust configuration mismatch")
        for entry in bundle.infolist():
            path = Path(entry.filename)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "Arc Workshop.app":
                raise ValueError("Unexpected release archive path")
        return info


def write_feed(archive, plan, info, signature):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Arc Workshop"
    ET.SubElement(channel, "link").text = "https://github.com/" + CONFIG["distributionRepository"]
    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = "Arc Workshop " + plan["version"]
    ET.SubElement(item, "pubDate").text = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    for key, value in [("version", plan["build"]), ("shortVersionString", plan["version"]),
                       ("minimumSystemVersion", info["LSMinimumSystemVersion"])]:
        ET.SubElement(item, "{" + SPARKLE + "}" + key).text = value
    ET.SubElement(item, "description").text = "Tested browser and Chromium/CEF maintenance update."
    ET.SubElement(item, "enclosure", {
        "url": f'https://github.com/{CONFIG["distributionRepository"]}/releases/download/v{plan["version"]}/Arc-Workshop.zip',
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
    key = os.environ["SPARKLE_PRIVATE_KEY"]
    signature = subprocess.run([str(args.sign_tool), "--ed-key-file", "-", "-p", str(args.archive)],
        input=key, text=True, capture_output=True, check=True).stdout.strip()
    feed = write_feed(args.archive, plan, info, signature)
    subprocess.run([str(args.sign_tool), "--ed-key-file", "-", str(feed)], input=key,
                   text=True, capture_output=True, check=True)
    digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    (args.archive.parent / "SHA256SUMS.txt").write_text(digest + "  Arc-Workshop.zip\n")
    public = {k: plan[k] for k in ["version", "build", "engine", "latestStableEngine", "engineBuildNeeded"]}
    (args.archive.parent / "release.json").write_text(json.dumps(public, indent=2) + "\n")
    print("Validated update archive and signed update feed.")


if __name__ == "__main__":
    main()
