"""Validate the reviewed alert ZIP as data, without extracting or importing it.

Run before any separate runtime use:
  python scripts/validate_alerts_runtime.py --archive .github/alerts-runtime.zip \
      --manifest .github/alerts-runtime-manifest.json

Exit 0 means the archive matches the supplied manifest and this portable file
layout policy. It is not a signature, source review, or permission to run alerts.
The caller must obtain the manifest from its intended reviewed source revision.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile
import zlib


MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 512
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_COMPONENT = re.compile(r"[A-Za-z0-9_.-]+\Z")
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)
}


def _read_bounded(path, limit):
    with Path(path).open("rb") as source:
        content = source.read(limit + 1)
    if len(content) > limit:
        raise ValueError(f"{Path(path).name}: exceeds {limit}-byte input limit")
    return content


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key!r}")
        result[key] = value
    return result


def _safe_path(name):
    """Require canonical, relative, portable ASCII file names, never directories."""
    return isinstance(name, str) and all(
        part not in ("", ".", "..")
        and _COMPONENT.fullmatch(part)
        and not part.endswith((".", " "))
        and part.split(".", 1)[0].upper() not in _RESERVED
        for part in name.split("/")
    )


def _path_errors(names, label):
    errors = []
    folded = {}
    for name in names:
        if not _safe_path(name):
            errors.append(f"Unsafe {label} path: {name!r}")
            continue
        key = name.casefold()
        if key in folded and folded[key] != name:
            errors.append(f"Colliding {label} paths: {folded[key]!r}, {name!r}")
        folded[key] = name
    for key, name in folded.items():
        parts = key.split("/")
        if any("/".join(parts[:i]) in folded for i in range(1, len(parts))):
            errors.append(f"File/directory conflict in {label}: {name!r}")
    return errors


def validate_runtime(archive_path, manifest_path):
    """Return bounded integrity evidence; never extract, install, or execute code."""
    report = {
        "ok": False, "manifest_sha256": None, "archive_sha256": None,
        "expected_archive_sha256": None, "members": [], "errors": [],
    }
    errors = report["errors"]
    try:
        manifest_bytes = _read_bounded(manifest_path, MAX_MANIFEST_BYTES)
        report["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        manifest = json.loads(manifest_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(manifest, dict) or "bundle_sha256" not in manifest:
            raise ValueError("Manifest must be an object containing bundle_sha256")
        if not all(isinstance(v, str) and _SHA256.fullmatch(v) for v in manifest.values()):
            raise ValueError("Manifest hashes must be lowercase 64-digit SHA-256 values")
        report["expected_archive_sha256"] = manifest["bundle_sha256"]
        expected = {k: v for k, v in manifest.items() if k != "bundle_sha256"}
        if not 1 <= len(expected) <= MAX_MEMBERS:
            raise ValueError(f"Manifest must list 1 to {MAX_MEMBERS} files")
        errors.extend(_path_errors(expected, "manifest"))
        if errors:
            return report

        # Hash and parse the same bounded byte snapshot, avoiding a second open
        # of a mutable archive between checking its digest and reading members.
        archive_bytes = _read_bounded(archive_path, MAX_ARCHIVE_BYTES)
        report["archive_sha256"] = hashlib.sha256(archive_bytes).hexdigest()
        if report["archive_sha256"] != report["expected_archive_sha256"]:
            errors.append("Archive SHA-256 does not match bundle_sha256")
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                raise ValueError(f"Archive exceeds {MAX_MEMBERS} members")
            names = [info.filename for info in infos]
            metadata_errors = _path_errors(names, "archive")
            metadata_errors.extend(
                f"Duplicate archive member: {name!r}"
                for name, count in Counter(names).items() if count > 1
            )
            metadata_errors.extend(f"Unexpected archive member: {n!r}" for n in sorted(set(names) - expected.keys()))
            metadata_errors.extend(f"Missing archive member: {n!r}" for n in sorted(expected.keys() - set(names)))
            for info in infos:
                kind = stat.S_IFMT(info.external_attr >> 16)
                if info.orig_filename != info.filename:
                    metadata_errors.append(f"Truncated archive path: {info.orig_filename!r}")
                if info.is_dir() or kind not in (0, stat.S_IFREG) or info.external_attr & 0x10:
                    metadata_errors.append(f"Non-regular archive member: {info.filename!r}")
                if info.flag_bits & 1:
                    metadata_errors.append(f"Encrypted archive member: {info.filename!r}")
                if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    metadata_errors.append(f"Unsupported compression: {info.filename!r}")
                if info.file_size > MAX_MEMBER_BYTES:
                    metadata_errors.append(f"Member exceeds size limit: {info.filename!r}")
            if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES:
                metadata_errors.append("Archive exceeds total uncompressed size limit")
            errors.extend(metadata_errors)
            if metadata_errors:
                return report

            total = 0
            for info in infos:
                digest = hashlib.sha256()
                size = 0
                with archive.open(info) as member:
                    while chunk := member.read(65536):
                        size += len(chunk)
                        total += len(chunk)
                        if size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                            raise ValueError("Decompressed content exceeds size limit")
                        digest.update(chunk)
                actual = digest.hexdigest()
                report["members"].append({
                    "name": info.filename, "sha256": actual,
                    "expected_sha256": expected[info.filename], "size": size,
                })
                if size != info.file_size:
                    errors.append(f"Member size mismatch: {info.filename!r}")
                if actual != expected[info.filename]:
                    errors.append(f"Member SHA-256 mismatch: {info.filename!r}")
    except (OSError, ValueError, RecursionError, zipfile.BadZipFile, zlib.error,
            RuntimeError, NotImplementedError, EOFError) as exc:
        errors.append(f"Validation failed: {exc}")
    report["ok"] = not errors
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    report = validate_runtime(args.archive, args.manifest)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
