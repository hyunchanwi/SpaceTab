#!/usr/bin/env python3
"""Publish only the already-public, signed appcast as an optional update-check hint."""
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def publish(endpoint, feed, opener=None):
    url = urllib.parse.urlsplit(endpoint)
    if (url.scheme != "https" or not url.hostname or not url.hostname.endswith(".workers.dev")
            or url.username or url.password or url.port not in (None, 443)
            or url.path != "/publish" or url.query or url.fragment):
        raise ValueError("Invalid release signal endpoint")
    if not 0 < len(feed) <= 16384:
        raise ValueError("Invalid public feed size")
    request = urllib.request.Request(endpoint, data=feed, method="POST", headers={
        "Content-Type": "application/xml", "User-Agent": "SpaceTab-Maintenance"})
    opener = opener or urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=15) as response:
        result = json.loads(response.read(1025))
    if type(result.get("accepted")) is not bool:
        raise ValueError("Invalid signal response")
    return result["accepted"]


def main():
    config = json.loads((ROOT / "config.json").read_text())
    endpoint = config.get("releaseSignalPublishURL")
    if not endpoint:
        print("Release signal not configured; periodic/manual checks remain available.")
        return
    feed = (ROOT / "dist/appcast.xml").read_bytes()
    for attempt in range(3):
        try:
            accepted = publish(endpoint, feed)
            print("Published release signal." if accepted else "Release signal already published.")
            return
        except Exception:
            if attempt == 2:
                raise RuntimeError("Release signal delivery failed; the signed release remains available through periodic/manual checks.") from None
            time.sleep(attempt + 1)


if __name__ == "__main__":
    main()
