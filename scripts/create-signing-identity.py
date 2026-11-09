#!/usr/bin/env python3
"""Create one persistent personal identity locally; never rotate it implicitly."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    args.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    certificate = args.directory / "app-signing.cer"
    archive = args.directory / "app-signing.p12"
    password = args.directory / "app-signing-password"
    if any(p.exists() for p in (certificate, archive, password)):
        raise SystemExit("Signing identity already exists; refusing to replace any part of it.")
    with tempfile.TemporaryDirectory(dir=args.directory) as temp:
        root = Path(temp)
        key, pem = root / "key.pem", root / "certificate.pem"
        password.write_text(secrets.token_urlsafe(48))
        config = root / "openssl.cnf"
        config.write_text("""[req]
distinguished_name = subject
x509_extensions = extensions
prompt = no
[subject]
CN = Arc Workshop Personal Signing
O = Arc Workshop
[extensions]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
subjectKeyIdentifier = hash
""")
        commands = [
            ["openssl", "req", "-new", "-x509", "-newkey", "rsa:3072", "-nodes", "-sha256",
             "-days", "3650", "-config", str(config), "-keyout", str(key), "-out", str(pem)],
            ["openssl", "x509", "-in", str(pem), "-outform", "DER", "-out", str(certificate)],
            # Legacy PKCS#12 encryption is understood by macOS security import; the archive
            # has a random password and is stored/uploaded only as a secret, never in git.
            ["openssl", "pkcs12", "-export", "-legacy", "-inkey", str(key), "-in", str(pem),
             "-name", "Arc Workshop Personal Signing", "-passout", "file:" + str(password), "-out", str(archive)],
        ]
        for command in commands:
            subprocess.run(command, check=True, capture_output=True)
    print(json.dumps({"mode": "persistent-personal", "certificateSHA256": hashlib.sha256(certificate.read_bytes()).hexdigest(),
                      "notarized": False}, indent=2))


if __name__ == "__main__":
    main()
