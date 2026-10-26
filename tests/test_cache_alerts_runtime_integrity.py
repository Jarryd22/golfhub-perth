"""Offline integrity checks; ZIP contents are always inert test data."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from scripts import validate_alerts_runtime as validator


ROOT = Path(__file__).resolve().parents[1]


def sha256(value):
    return hashlib.sha256(value).hexdigest()


class AlertsRuntimeIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="golfhub-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "runtime.zip"
        self.manifest = self.root / "manifest.json"
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        self.guards.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("offline test")))
        self.guards.enter_context(patch("socket.create_connection", side_effect=AssertionError("offline test")))
        self.guards.enter_context(patch.object(zipfile.ZipFile, "extract", side_effect=AssertionError("never extract")))
        self.guards.enter_context(patch.object(zipfile.ZipFile, "extractall", side_effect=AssertionError("never extract")))

    def make_archive(self, entries=None, expected=None, compression=zipfile.ZIP_STORED):
        entries = entries if entries is not None else [
            ("app/__init__.py", b"raise AssertionError('archive code must not run')\n"),
            ("service/example.py", b"VALUE = 42\n"),
        ]
        hashes = {}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "w", compression=compression) as archive:
                for name, content in entries:
                    archive.writestr(name, content)
                    hashes[name.filename if isinstance(name, zipfile.ZipInfo) else name] = sha256(content)
        value = hashes if expected is None else dict(expected)
        value["bundle_sha256"] = sha256(self.archive.read_bytes())
        self.manifest.write_text(json.dumps(value), encoding="utf-8")
        return value

    def update_bundle_hash(self):
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        value["bundle_sha256"] = sha256(self.archive.read_bytes())
        self.manifest.write_text(json.dumps(value), encoding="utf-8")

    def check(self):
        return validator.validate_runtime(self.archive, self.manifest)

    def assert_rejected(self, result):
        self.assertIs(result["ok"], False, result)
        self.assertTrue(result["errors"], result)
        self.assertTrue(all(isinstance(error, str) for error in result["errors"]), result)

    def run_cli(self):
        harness = (
            "import runpy, socket, sys; from unittest.mock import patch; "
            "sys.argv = sys.argv[1:]; "
            "guards = [patch.object(socket.socket, 'connect', side_effect=AssertionError('offline')), "
            "patch('socket.create_connection', side_effect=AssertionError('offline'))]; "
            "[guard.start() for guard in guards]; runpy.run_path(sys.argv[0], run_name='__main__')"
        )
        return subprocess.run([
            sys.executable, "-c", harness, str(ROOT / "scripts" / "validate_alerts_runtime.py"),
            "--archive", str(self.archive), "--manifest", str(self.manifest),
        ], cwd=self.root, capture_output=True, text=True, timeout=15)

    def test_committed_bundle_matches_freshly_read_manifest_without_importing_it(self):
        archive = ROOT / ".github" / "alerts-runtime.zip"
        manifest_path = ROOT / ".github" / "alerts-runtime-manifest.json"
        expected = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = validator.validate_runtime(archive, manifest_path)
        self.assertIs(result["ok"], True, result)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["manifest_sha256"], sha256(manifest_path.read_bytes()))
        self.assertEqual(result["archive_sha256"], expected.pop("bundle_sha256"))
        self.assertEqual({member["name"] for member in result["members"]}, set(expected))
        for member in result["members"]:
            self.assertEqual(member["sha256"], expected[member["name"]])
            self.assertEqual(member["expected_sha256"], expected[member["name"]])

    def test_valid_archive_is_inert_and_input_files_remain_unchanged(self):
        self.make_archive()
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        with patch("importlib.import_module", side_effect=AssertionError("never import bundle modules")):
            result = self.check()
        self.assertIs(result["ok"], True, result)
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir()}, before)
        self.assertEqual({member["name"]: member["size"] for member in result["members"]}, {
            "app/__init__.py": len(b"raise AssertionError('archive code must not run')\n"),
            "service/example.py": len(b"VALUE = 42\n"),
        })

    def test_wrong_archive_hash_rejects_even_when_members_match(self):
        expected = self.make_archive()
        expected["bundle_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(expected), encoding="utf-8")
        result = self.check()
        self.assert_rejected(result)
        self.assertEqual(result["archive_sha256"], sha256(self.archive.read_bytes()))
        self.assertEqual(result["expected_archive_sha256"], "0" * 64)

    def test_member_hash_mismatch_is_not_hidden_by_matching_archive_hash(self):
        expected = self.make_archive()
        expected["service/example.py"] = "0" * 64
        self.manifest.write_text(json.dumps(expected), encoding="utf-8")
        result = self.check()
        self.assert_rejected(result)
        member = next(row for row in result["members"] if row["name"] == "service/example.py")
        self.assertNotEqual(member["sha256"], member["expected_sha256"])

    def test_crc_valid_altered_archive_fails_manifest_integrity(self):
        self.make_archive([("app/a.py", b"reviewed original")])
        original_manifest = self.manifest.read_bytes()
        self.make_archive([("app/a.py", b"synthetically changed")])
        self.manifest.write_bytes(original_manifest)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertIsNone(archive.testzip(), "Normal ZIP CRC validation accepts this fixture")
        result = self.check()
        self.assert_rejected(result)
        self.assertNotEqual(result["archive_sha256"], result["expected_archive_sha256"])
        self.assertNotEqual(result["members"][0]["sha256"], result["members"][0]["expected_sha256"])

    def test_extra_member_is_rejected(self):
        self.make_archive([("app/a.py", b"a"), ("app/extra.py", b"extra")], {"app/a.py": sha256(b"a")})
        self.assert_rejected(self.check())

    def test_missing_member_is_rejected(self):
        self.make_archive([("app/a.py", b"a")], {"app/a.py": sha256(b"a"), "app/missing.py": sha256(b"")})
        self.assert_rejected(self.check())

    def test_duplicate_members_are_rejected_even_with_identical_content(self):
        for second in (b"same", b"different"):
            with self.subTest(second=second):
                self.make_archive([("app/a.py", b"same"), ("app/a.py", second)])
                self.assert_rejected(self.check())

    def test_unsafe_archive_paths_are_rejected_even_if_manifest_lists_them(self):
        for name in ("../escape.py", "/absolute.py", "C:/drive.py", "C:\\drive.py",
                     "app\\nested.py", "app//a.py", "./a.py", "app/../a.py", "app/./a.py"):
            with self.subTest(name=name):
                self.make_archive([(name, b"inert")])
                self.assert_rejected(self.check())

    def test_windows_reserved_and_normalized_alias_paths_are_rejected(self):
        for name in ("CON", "aux.py", "app/NUL.txt", "app/LPT1.py", "app/trailing.", "app/trailing "):
            with self.subTest(name=name):
                self.make_archive([(name, b"inert")])
                self.assert_rejected(self.check())

    def test_case_aliases_are_rejected(self):
        self.make_archive([("app/main.py", b"one"), ("APP/MAIN.py", b"two")])
        self.assert_rejected(self.check())

    def test_file_directory_prefix_conflicts_are_rejected(self):
        self.make_archive([("app/module", b"file"), ("app/module/child.py", b"child")])
        self.assert_rejected(self.check())

    def test_directory_symlink_and_other_nonregular_members_are_rejected(self):
        for name, mode in (("app/", stat.S_IFDIR | 0o755),
                           ("app/link.py", stat.S_IFLNK | 0o777),
                           ("app/pipe.py", stat.S_IFIFO | 0o600)):
            with self.subTest(name=name):
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = mode << 16
                self.make_archive([(info, b"inert")])
                self.assert_rejected(self.check())

    def test_encrypted_member_flag_is_rejected_without_password_or_execution(self):
        self.make_archive([("app/a.py", b"inert")])
        data = bytearray(self.archive.read_bytes())
        central = data.index(b"PK\x01\x02")
        for offset in (6, central + 8):
            struct.pack_into("<H", data, offset, struct.unpack_from("<H", data, offset)[0] | 1)
        self.archive.write_bytes(data)
        self.update_bundle_hash()
        self.assert_rejected(self.check())

    def test_corrupt_member_is_reported_as_invalid_data(self):
        payload = b"unique uncompressed fixture content"
        self.make_archive([("app/a.py", payload)])
        data = bytearray(self.archive.read_bytes())
        data[data.index(payload)] ^= 1
        self.archive.write_bytes(data)
        self.update_bundle_hash()
        self.assert_rejected(self.check())

    def test_corrupt_deflate_returns_cli_failure_without_traceback(self):
        self.make_archive([("app/a.py", b"deflate fixture" * 32)], compression=zipfile.ZIP_DEFLATED)
        data = bytearray(self.archive.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", data, 26)
        data_start = 30 + name_length + extra_length
        data[data_start] = (data[data_start] & ~6) | 6  # Reserved DEFLATE block type.
        self.archive.write_bytes(data)
        self.update_bundle_hash()
        self.assert_rejected(self.check())
        process = self.run_cli()
        self.assertEqual(process.returncode, 1, process.stderr + process.stdout)
        self.assert_rejected(json.loads(process.stdout))
        self.assertNotIn("Traceback", process.stderr)

    def test_unsupported_compression_is_rejected_before_reading_members(self):
        self.make_archive([("app/a.py", b"inert")])
        data = bytearray(self.archive.read_bytes())
        central = data.index(b"PK\x01\x02")
        struct.pack_into("<H", data, 8, 99)
        struct.pack_into("<H", data, central + 10, 99)
        self.archive.write_bytes(data)
        self.update_bundle_hash()
        self.assert_rejected(self.check())

    def test_truncated_archive_is_reported_without_throwing(self):
        self.make_archive()
        self.archive.write_bytes(self.archive.read_bytes()[:-16])
        self.update_bundle_hash()
        self.assert_rejected(self.check())

    def test_duplicate_manifest_keys_are_rejected(self):
        expected = self.make_archive()
        for key in ("bundle_sha256", "app/__init__.py"):
            with self.subTest(key=key):
                encoded = json.dumps(expected)
                self.manifest.write_text(encoded[:-1] + "," + json.dumps(key) + ":" + json.dumps(expected[key]) + "}", encoding="utf-8")
                self.assert_rejected(self.check())

    def test_malformed_or_nonobject_manifest_is_rejected(self):
        self.make_archive()
        for value in (b"{", b"[]", b"null", b'"text"', b"\xff"):
            with self.subTest(value=value):
                self.manifest.write_bytes(value)
                self.assert_rejected(self.check())

    def test_invalid_manifest_hashes_are_rejected(self):
        for key in ("bundle_sha256", "service/example.py"):
            for value in ("bad", "z" * 64, None, 42, True, []):
                with self.subTest(key=key, value=value):
                    expected = self.make_archive()
                    expected[key] = value
                    self.manifest.write_text(json.dumps(expected), encoding="utf-8")
                    self.assert_rejected(self.check())

    def test_manifest_requires_bundle_hash_and_at_least_one_expected_member(self):
        expected = self.make_archive()
        for value in ({}, {"bundle_sha256": expected["bundle_sha256"]},
                      {"app/a.py": sha256(b"a")}):
            with self.subTest(value=value):
                self.manifest.write_text(json.dumps(value), encoding="utf-8")
                self.assert_rejected(self.check())

    def test_missing_inputs_are_reported_as_failure(self):
        self.make_archive()
        self.assert_rejected(validator.validate_runtime(self.root / "missing.zip", self.manifest))
        self.assert_rejected(validator.validate_runtime(self.archive, self.root / "missing.json"))

    def test_resource_limits_reject_oversized_inputs(self):
        self.make_archive([("app/a.py", b"1234"), ("app/b.py", b"5678")])
        limits = {
            "MAX_ARCHIVE_BYTES": self.archive.stat().st_size - 1,
            "MAX_MANIFEST_BYTES": self.manifest.stat().st_size - 1,
            "MAX_MEMBER_BYTES": 3,
            "MAX_TOTAL_BYTES": 7,
            "MAX_MEMBERS": 1,
        }
        for name, value in limits.items():
            with self.subTest(limit=name), patch.object(validator, name, value):
                self.assert_rejected(self.check())

    def test_resource_limits_accept_exact_boundaries(self):
        self.make_archive([("app/a.py", b"1234"), ("app/b.py", b"5678")])
        with patch.multiple(validator, MAX_ARCHIVE_BYTES=self.archive.stat().st_size,
                            MAX_MANIFEST_BYTES=self.manifest.stat().st_size,
                            MAX_MEMBER_BYTES=4, MAX_TOTAL_BYTES=8, MAX_MEMBERS=2):
            result = self.check()
        self.assertIs(result["ok"], True, result)

    def test_each_validation_rereads_expected_hashes(self):
        expected = self.make_archive()
        self.assertIs(self.check()["ok"], True)
        expected["bundle_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(expected), encoding="utf-8")
        result = self.check()
        self.assert_rejected(result)
        self.assertEqual(result["expected_archive_sha256"], "0" * 64)

    def test_cli_json_and_exit_code_follow_integrity_result(self):
        self.make_archive()
        for valid in (True, False):
            with self.subTest(valid=valid):
                if not valid:
                    expected = json.loads(self.manifest.read_text(encoding="utf-8"))
                    expected["bundle_sha256"] = "0" * 64
                    self.manifest.write_text(json.dumps(expected), encoding="utf-8")
                process = self.run_cli()
                self.assertEqual(process.returncode, 0 if valid else 1, process.stderr + process.stdout)
                self.assertEqual(json.loads(process.stdout)["ok"], valid)


if __name__ == "__main__":
    unittest.main()
