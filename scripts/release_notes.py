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
print("- A new **Ice Blue** icon is the default for SpaceTab, including Finder and notification helpers.")
print("- Settings → General → App Icon now offers **Ice Blue, Mint Orbit, Graphite and Portal**, plus custom images. Built-in choices stay selected after relaunch.")
print("- Reveal the sidebar from the left edge while a video is in element fullscreen. Switching away clears the video's fullscreen state.")
print("- **Ctrl+Tab** returns to recently selected tabs across spaces, with separate selection history for each window. Shared favorites appear once.")
print("- Automatic **Picture in Picture** returns to its source tab, including either visible split pane. Late requests cannot reopen automatic PiP over the visible source.")
print("- A combined native runtime check covers video fullscreen, real pointer hover, AppKit Ctrl+Tab input, PiP, split leave/return/expand and independent window history using an isolated local video.")
print("- Existing profiles, Keychain identity and update verification keys are retained.")
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
print("[Getting started](https://github.com/hyunchanwi/SpaceTab#install) · [한국어 안내](https://github.com/hyunchanwi/SpaceTab/blob/main/README.ko.md) · [Report a bug](https://github.com/hyunchanwi/SpaceTab/issues/new/choose)\n")
print("An independent Cra-based project. Not affiliated with Arc, Dia or The Browser Company. Browser source is private; this public repository contains downloads and maintenance tooling.")
