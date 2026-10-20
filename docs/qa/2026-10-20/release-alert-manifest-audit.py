"""Verify public manifest bytes against the separately captured release metadata.

Downloads only two small JSON manifests per repository; never installer/APK bytes.
Signature verification requires a trusted updater key and is not performed here.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent


def small_download(url):
    with urlopen(url, timeout=25) as response:
        value = response.read(65537)
    if len(value) > 65536:
        raise ValueError("Manifest exceeds 64 KiB bound")
    return value


def main():
    metadata = json.loads((HERE / "release-alert-metadata.json").read_text())
    checks = []
    for repo in metadata["repos"]:
        release = repo["latest_release"]
        manifest_asset = next(a for a in release["assets"] if a["name"].endswith("update.json"))
        manifest_url = manifest_asset["url"]
        alias_url = f'https://github.com/{repo["repository"]}/releases/latest/download/{manifest_asset["name"]}'
        content = small_download(manifest_url)
        alias = small_download(alias_url)
        envelope = json.loads(content)
        payload = json.loads(base64.b64decode(envelope["payload"], validate=True))
        signature = base64.b64decode(envelope["signature"], validate=True)
        binary = next(a for a in release["assets"] if a["url"] == payload["url"])
        digest = hashlib.sha256(content).hexdigest()
        check = {
            "repository": repo["repository"],
            "version": payload["version"],
            "manifest_url": manifest_url,
            "latest_alias_url": alias_url,
            "manifest_sha256": digest,
            "manifest_size": len(content),
            "manifest_hash_matches_current_github_metadata": manifest_asset["digest"] == f"sha256:{digest}",
            "manifest_size_matches_current_github_metadata": manifest_asset["size"] == len(content),
            "latest_alias_bytes_match_versioned_manifest": alias == content,
            "payload_binary_metadata_matches_current_github_metadata": binary["digest"] == f'sha256:{payload["sha256"]}' and binary["size"] == payload["size"],
            "signature_present": len(signature) == 64,
            "signature_verified": None,
            "signature_verification_reason": "Trusted updater public key and updater source are absent from this checkout; prior signature verdicts are not reused.",
            "binary_downloaded_or_installed": False,
            "native_device_tested": False,
            "payload": payload,
        }
        for name in ("manifest_hash_matches_current_github_metadata", "manifest_size_matches_current_github_metadata", "latest_alias_bytes_match_versioned_manifest", "payload_binary_metadata_matches_current_github_metadata", "signature_present"):
            assert check[name], (repo["repository"], name)
        checks.append(check)
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Current published manifest bytes and separately captured release API metadata only. No binary download, installation, signature verification, or device testing.",
        "checks": checks,
    }
    (HERE / "release-alert-manifests.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps([{k: c[k] for k in ("repository", "version", "manifest_hash_matches_current_github_metadata", "latest_alias_bytes_match_versioned_manifest", "payload_binary_metadata_matches_current_github_metadata")} for c in checks], indent=2))


if __name__ == "__main__":
    main()
