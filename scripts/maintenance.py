#!/usr/bin/env python3
"""Trusted controller: integrates upstream without executing private source code."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.json").read_text())


def get_json(url):
    headers = {"User-Agent": "Arc-Workshop-Maintenance", "Accept": "application/json"}
    if url.startswith("https://api.github.com/") and os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        return json.load(response)


def version(value):
    if "+chromium-" in value:
        cef, chromium = value.split("+chromium-", 1)
        return tuple(map(int, chromium.split("."))) + tuple(map(int, cef.split("+", 1)[0].split(".")))
    return tuple(map(int, value.split(".")))


def git(root, *args, allow_failure=False):
    command = ["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode and not allow_failure:
        # Compiler/merge output may contain private source text. Never copy it to public logs.
        raise RuntimeError("Source integration failed at git " + args[0] + "; no release will be published")
    return result


def choose_engine(current, desired, releases):
    """Only official codec-enabled, checksummed arm64 binaries may be shipped."""
    options = [current]
    for candidate in desired:
        if version(candidate) < version(current["version"]):
            continue
        base = candidate.split("+", 1)[0]
        for release in releases:
            if release.get("draft") or not re.fullmatch(r"cef-" + re.escape(base) + r"-codecs[0-9]+", release["tag_name"]):
                continue
            for asset in release.get("assets", []):
                digest = asset.get("digest") or ""
                url = asset.get("browser_download_url", "")
                prefix = f'https://github.com/{CONFIG["upstreamRepository"]}/releases/download/{release["tag_name"]}/'
                if asset["name"] == "cef_binary_macosarm64_minimal.tar.bz2" and re.fullmatch(r"sha256:[a-f0-9]{64}", digest) and url.startswith(prefix):
                    options.append({"version": candidate, "url": url, "sha256": digest[7:]})
    def rank(engine):
        codec = re.search(r"-codecs([0-9]+)/", engine["url"])
        return version(engine["version"]), int(codec[1]) if codec else 0
    return max(options, key=rank)


def integrate(root, upstream_sha):
    if not re.fullmatch(r"[a-f0-9]{40}", upstream_sha):
        raise ValueError("Invalid upstream commit")
    if git(root, "merge-base", "--is-ancestor", upstream_sha, "HEAD", allow_failure=True).returncode == 0:
        return False
    result = git(root, "merge", "--no-commit", "--no-ff", upstream_sha, allow_failure=True)
    if result.returncode:
        git(root, "merge", "--abort", allow_failure=True)
        raise RuntimeError("Upstream conflicts with personal changes; maintenance needs attention")
    return True


def prepare(root, run, force):
    if not re.fullmatch(r"[0-9]+", run):
        raise ValueError("Invalid run number")
    base = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "config", "user.name", "Arc Workshop Maintenance")
    git(root, "config", "user.email", "maintenance@users.noreply.github.com")
    repo = CONFIG["upstreamRepository"]
    release = get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    tag = release["tag_name"]
    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){1,3}", tag):
        raise ValueError("Unexpected upstream release tag")
    git(root, "fetch", f"https://github.com/{repo}.git", f"refs/tags/{tag}")
    upstream = git(root, "rev-parse", "FETCH_HEAD^{commit}").stdout.strip()
    merged = integrate(root, upstream)
    current = json.loads((root / "workshop/engine.json").read_text())
    script = (root / "scripts/fetch-cef.sh").read_text()
    match = re.search(r'^CEF_VERSION="\$\{CEF_VERSION:-([^}]+)\}"', script, re.M)
    if not match:
        raise ValueError("Upstream engine recipe changed; manual integration required")
    stable = [v["cef_version"] for v in get_json("https://cef-builds.spotifycdn.com/index.json")["macosarm64"]["versions"] if v["channel"] == "stable"]
    latest = max(stable, key=version)
    releases = get_json(f"https://api.github.com/repos/{repo}/releases?per_page=100")
    engine = choose_engine(current, [match[1], latest], releases)
    waiting = version(latest) > version(engine["version"])
    try:
        published = get_json(f'https://api.github.com/repos/{CONFIG["distributionRepository"]}/releases/latest')["tag_name"]
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        published = ""
    previous_file = root / "workshop/last-release.json"
    previous = json.loads(previous_file.read_text()) if previous_file.exists() else {}
    unpublished = not published or published != "v" + previous.get("version", "")
    changed = merged or engine != current or unpublished
    plan = {"changed": changed or force, "base": base, "upstream": upstream,
            "engine": engine, "latestStableEngine": latest, "engineBuildNeeded": waiting,
            "version": "1.0." + run, "build": datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S"),
            "branch": "maintenance/candidate-" + run}
    if plan["changed"]:
        (root / "workshop/engine.json").write_text(json.dumps(engine, indent=2) + "\n")
        state = {k: plan[k] for k in ["upstream", "engine", "version", "build"]}
        (root / "workshop/last-release.json").write_text(json.dumps(state, indent=2) + "\n")
        git(root, "add", "workshop")
        git(root, "commit", "--allow-empty", "-m", "Prepare Arc Workshop " + plan["version"])
        plan["candidate"] = git(root, "rev-parse", "HEAD").stdout.strip()
        git(root, "push", "origin", "HEAD:refs/heads/" + plan["branch"])
    return plan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.source, args.run, args.force)
    args.output.write_text(json.dumps(plan, indent=2) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            for key in ["changed", "base", "candidate", "branch", "version", "build", "engineBuildNeeded"]:
                stream.write(f"{key}={str(plan.get(key, '')).lower() if isinstance(plan.get(key), bool) else plan.get(key, '')}\n")
    print("Maintenance plan prepared; source content remains private.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        detail = str(error) if isinstance(error, (RuntimeError, ValueError, urllib.error.HTTPError)) else "maintenance stopped before publication"
        print(type(error).__name__ + ": " + detail, file=sys.stderr)
        sys.exit(1)
