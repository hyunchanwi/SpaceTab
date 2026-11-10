#!/usr/bin/env python3
"""Human-readable release notes, using only public release metadata."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
plan = json.loads(Path(sys.argv[1]).read_text())
signing = json.loads((root / "signing.json").read_text())
print(f"## SpaceTab {plan['version']}\n")
print("A native macOS browser built around spaces, a quiet sidebar and shared favorites.\n")
print("### Install\n")
print("Download **SpaceTab.zip**, unzip it, and move **SpaceTab.app** to Applications. Apple silicon; macOS 14 or later.\n")
print("### In this release\n")
print("- Arc Workshop is now **SpaceTab**. Existing profiles, Keychain identity and update verification keys are retained.")
print("- New downloads contain **SpaceTab.app**. An in-place update may keep the existing Finder folder name; the app displays SpaceTab.")
print("- **Expand Current Split** shows the chosen pane alone and keeps the other pages as sidebar tabs. Find it in View, the command bar, or a pane's options.")
print("- Pinned tabs and favorites group their saved-address actions under **Edit Pinned Page**.")
print("- Automated browser tests and isolated launch, quit and restore checks passed.")
print("- Imported extension IDs are validated before filesystem access; release archives have stricter path, symlink and size checks.")
print("- Disposable-key update tampering checks and real-browser isolation/TLS checks passed before publication.")
print("- Update framework: Sparkle 2.10.1.")
print(f"- Chromium/CEF: `{plan['engine']['version']}`.")
if signing["mode"] == "persistent-personal":
    print("- Signed with a persistent personal certificate. This is **not Apple Developer ID signing or Apple notarization**.")
    print("- The first update from an older ad-hoc build may ask for approval to access **Workshop Storage** in your Mac Keychain. Later builds keep the same signing identity; password prompts are not an expected step for every update.")
else:
    print("- Signed with Developer ID and notarized by Apple.")
if plan.get("engineBuildNeeded"):
    if plan.get("latestStableChrome"):
        print(f"- Engine freshness needs attention: Chrome stable reports `{plan['latestStableChrome']}`; this release keeps the tested, compatible patched engine shown above.")
    else:
        print("- Engine freshness could not be confirmed; this release keeps the tested, compatible patched engine shown above.")
print("\n### Update and recovery\n")
print("Installed copies check for signed updates. Installation requires your action by default. Before updating, the app saves the previous app and browsing profile locally; recovery is manual.\n")
print("[Getting started](https://github.com/hyunchanwi/arc-workshop-updates#install) · [한국어 안내](https://github.com/hyunchanwi/arc-workshop-updates/blob/main/README.ko.md) · [Report a bug](https://github.com/hyunchanwi/arc-workshop-updates/issues/new/choose)\n")
print("An independent Cra-based project. Not affiliated with Arc, Dia or The Browser Company. Browser source is private; this public repository contains downloads and maintenance tooling.")
