#!/usr/bin/env python3
"""Sign validated build artifacts in the publishing job, without running browser code."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import secrets
import shlex
import subprocess
import tempfile

import publish

ROOT = Path(__file__).resolve().parents[1]
MACHO = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce",
         b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}
SECRET_ENV = {"APP_SIGNING_P12", "APP_SIGNING_PASSWORD", "SPARKLE_PRIVATE_KEY", "SOURCE_DEPLOY_KEY",
              "NOTARY_API_PRIVATE_KEY", "NOTARY_API_KEY_ID", "NOTARY_API_ISSUER", "GH_TOKEN", "GITHUB_TOKEN"}


def tool_environment():
    return {key: value for key, value in os.environ.items() if key not in SECRET_ENV}


def run(*command):
    # Errors stay generic: passwords, private key data and compiler diagnostics must not
    # enter a public Actions log. Only commands from this checked-in controller run here.
    result = subprocess.run(command, capture_output=True, text=True, env=tool_environment())
    if result.returncode:
        detail = (": " + result.stderr.strip()) if command[0] == "codesign" else ""
        raise RuntimeError(f"Release signing stopped: {Path(command[0]).name} failed{detail}")
    return result.stdout + result.stderr


def policy():
    value = json.loads((ROOT / "signing.json").read_text())
    if value["mode"] not in ("persistent-personal", "developer-id"):
        raise ValueError("Release requires a persistent signing identity; ad-hoc fallback is disabled")
    if not re.fullmatch(r"[a-f0-9]{64}", value["certificateSHA256"]):
        raise ValueError("Missing pinned signing certificate")
    if value["mode"] == "developer-id" and not re.fullmatch(r"[A-Z0-9]{10}", value.get("teamID", "")):
        raise ValueError("Developer ID releases require a pinned Apple team")
    return value


def add_to_keychain_search_list(keychain):
    # Hosted runners can keep a fixed search list. codesign's --keychain narrows its
    # identity lookup but does not reliably add imported private keys to that list.
    previous = shlex.split(run("security", "list-keychains", "-d", "user"))
    run("security", "list-keychains", "-d", "user", "-s", *previous, str(keychain))
    return previous


def write_entitlements(directory):
    # Keep CEF's JIT exceptions; release apps do not honor DYLD injection variables
    # or get-task-allow. The browser's existing storage identity is retained.
    shared = {"com.apple.security.cs." + name: True for name in
              ["allow-jit", "allow-unsigned-executable-memory", "disable-library-validation"]}
    shared.update({"com.apple.security.device.audio-input": True, "com.apple.security.device.camera": True})
    helper = directory / "helper.plist"
    host = directory / "host.plist"
    helper.write_bytes(plistlib.dumps(shared))
    host.write_bytes(plistlib.dumps(shared | {"com.apple.security.personal-information.location": True,
                                             "com.apple.security.automation.apple-events": True}))
    return host, helper


def signing_targets(app):
    """Real files only; sign every Mach-O, then containers from the inside out."""
    binaries, containers = [], []
    for path in app.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_file():
            with path.open("rb") as stream:
                if stream.read(4) in MACHO:
                    binaries.append(path)
        elif path.suffix in (".app", ".framework", ".xpc", ".docktileplugin", ".bundle"):
            containers.append(path)
    if not binaries or app / "Contents/MacOS/Cra" not in binaries:
        raise ValueError("Missing native browser executable")
    return sorted(binaries), sorted(containers, key=lambda p: (-len(p.parts), str(p))) + [app]


def sign_app(app, identity, keychain, signing_policy, certificate_sha1, directory):
    host, helper = write_entitlements(directory)
    binaries, containers = signing_targets(app)
    for target in binaries + containers:
        description = run("codesign", "-dv", str(target))
        match = re.search(r"^Identifier=(.+)$", description, re.M)
        if not match or not re.fullmatch(r"[A-Za-z0-9_.() -]+", match[1]):
            raise ValueError("Missing or unexpected nested signing identifier")
        identifier = match[1]
        args = ["codesign", "--force", "--sign", identity, "--keychain", str(keychain),
                "--identifier", identifier, "--options", "runtime"]
        if signing_policy["mode"] == "persistent-personal":
            args += ["--timestamp=none", "--requirements",
                     f'=designated => identifier "{identifier}" and certificate leaf = H"{certificate_sha1}"']
        else:
            args += ["--timestamp"]
        # Entitlements on helper binaries as well as their containers keep JIT enabled
        # when those binaries are sealed again as part of their enclosing framework.
        is_helper = any(p.suffix == ".app" and p.name.startswith("Cra Helper") for p in target.parents) or target.name.startswith("Cra Helper")
        if target == app or target == app / "Contents/MacOS/Cra":
            args += ["--entitlements", str(host)]
        elif is_helper:
            args += ["--entitlements", str(helper)]
        run(*args, str(target))
    run("codesign", "--verify", "--deep", "--strict", str(app))
    run("codesign", "--verify", "-R", f'=certificate leaf = H"{certificate_sha1}"', str(app))
    if signing_policy["mode"] == "developer-id":
        run("codesign", "--verify", "-R", '=anchor apple generic and certificate leaf[subject.OU] = "' + signing_policy["teamID"] + '"', str(app))


def notarize(app, archive, directory):
    # App Store Connect API keys avoid storing an Apple account's login password.
    key = directory / "notary.p8"
    key.write_text(os.environ["NOTARY_API_PRIVATE_KEY"])
    result = run("xcrun", "notarytool", "submit", str(archive), "--key", str(key),
                 "--key-id", os.environ["NOTARY_API_KEY_ID"], "--issuer", os.environ["NOTARY_API_ISSUER"],
                 "--wait", "--timeout", "25m", "--output-format", "json")
    if json.loads(result).get("status") != "Accepted":
        raise ValueError("Apple notarization did not accept this release")
    run("xcrun", "stapler", "staple", str(app))
    run("xcrun", "stapler", "validate", str(app))
    run("spctl", "--assess", "--type", "execute", str(app))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    signing_policy = policy()
    publish.validate(args.archive, json.loads(args.plan.read_text()))
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="workshop-signing-", dir=os.environ.get("RUNNER_TEMP")) as temp:
        directory = Path(temp)
        keychain = directory / "signing.keychain-db"
        certificate = ROOT / "signing/app-signing.cer"
        if hashlib.sha256(certificate.read_bytes()).hexdigest() != signing_policy["certificateSHA256"]:
            raise ValueError("Signing certificate fingerprint changed")
        sha1 = hashlib.sha1(certificate.read_bytes()).hexdigest().upper()
        # Parse/extract the artifact before importing the persistent signing identity.
        # Child tools also never inherit the Actions secret environment variables.
        run("ditto", "-x", "-k", str(args.archive.resolve()), str(directory / "bundle"))
        app = directory / "bundle" / publish.APP_ROOT
        signing_targets(app)
        p12 = directory / "identity.p12"
        p12.write_bytes(base64.b64decode(os.environ["APP_SIGNING_P12"], validate=True))
        keychain_password = secrets.token_urlsafe(48)
        previous_keychains = None
        try:
            run("security", "create-keychain", "-p", keychain_password, str(keychain))
            run("security", "set-keychain-settings", "-lut", "3600", str(keychain))
            run("security", "unlock-keychain", "-p", keychain_password, str(keychain))
            run("security", "import", str(p12), "-k", str(keychain), "-P", os.environ["APP_SIGNING_PASSWORD"], "-T", "/usr/bin/codesign")
            run("security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", keychain_password, str(keychain))
            previous_keychains = add_to_keychain_search_list(keychain)
            sign_app(app, sha1, keychain, signing_policy, sha1, directory)
            staged = directory / "Arc-Workshop.zip"
            run("ditto", "-c", "-k", "--keepParent", str(app), str(staged))
            if signing_policy["mode"] == "developer-id":
                notarize(app, staged, directory)
                staged.unlink()
                run("ditto", "-c", "-k", "--keepParent", str(app), str(staged))
            run("codesign", "--verify", "--deep", "--strict", str(app))
            # Replace the unsigned build only after the entire signing/notary stage succeeds.
            args.archive.write_bytes(staged.read_bytes())
        finally:
            if previous_keychains is not None:
                subprocess.run(["security", "list-keychains", "-d", "user", "-s", *previous_keychains], capture_output=True, env=tool_environment())
            subprocess.run(["security", "delete-keychain", str(keychain)], capture_output=True, env=tool_environment())
    (args.archive.parent / "signing-status.json").write_text(json.dumps({
        "mode": signing_policy["mode"], "certificateSHA256": signing_policy["certificateSHA256"],
        "notarized": signing_policy["mode"] == "developer-id"}, indent=2) + "\n")
    print("Persistent application identity verified. No ad-hoc signing fallback was used.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, (ValueError, RuntimeError)) else "Release signing failed; nothing published.")
        raise SystemExit(1)
