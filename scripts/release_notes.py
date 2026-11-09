#!/usr/bin/env python3
"""Human-readable release notes, using only public release metadata."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
plan = json.loads(Path(sys.argv[1]).read_text())
signing = json.loads((root / "signing.json").read_text())
print(f"## Arc Workshop {plan['version']}\n")
print("A native macOS browser built around spaces, a quiet sidebar and shared favorites.\n")
print("### Install\n")
print("Download **Arc-Workshop.zip**, unzip it, and move **Arc Workshop.app** to Applications. Apple silicon; macOS 14 or later.\n")
print("### In this release\n")
print("- Automated browser tests and isolated launch, quit and restore checks passed.")
print(f"- Chromium/CEF: `{plan['engine']['version']}`.")
if signing["mode"] == "persistent-personal":
    print("- Signed with a persistent personal certificate. This is **not Apple Developer ID signing or Apple notarization**.")
    print("- The first update from an older ad-hoc build may ask for approval to access **Workshop Storage** in your Mac Keychain. Later builds keep the same signing identity; password prompts are not an expected step for every update.")
else:
    print("- Signed with Developer ID and notarized by Apple.")
if plan.get("engineBuildNeeded"):
    print("- A newer stable engine is awaiting a compatible patched binary; it is not included in this release.")
print("\n### Update and recovery\n")
print("Installed copies check for signed updates. Installation requires your action by default. Before updating, the app saves the previous app and browsing profile locally; recovery is manual.\n")
print("[Getting started](https://github.com/hyunchanwi/arc-workshop-updates#install) · [한국어 안내](https://github.com/hyunchanwi/arc-workshop-updates/blob/main/README.ko.md) · [Report a bug](https://github.com/hyunchanwi/arc-workshop-updates/issues/new/choose)\n")
print("An independent Cra-based project. Not affiliated with Arc, Dia or The Browser Company. Browser source is private; this public repository contains downloads and maintenance tooling.")
