import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import publish  # noqa: E402
import updater  # noqa: E402

BASE = updater.PREFIX + "main/src/"
URL = updater.MANIFEST_URL


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def json(self):
        return json.loads(self._body)

    def iter_content(self, size):
        for i in range(0, len(self._body), size):
            yield self._body[i:i + size]


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append(url)
        if url not in self.routes:
            return FakeResponse(b"", 404)
        return FakeResponse(self.routes[url])


def manifest_for(version, files, zone=3, **extra):
    manifest = {
        "version": version,
        "base": BASE,
        "files": {
            name: {"zone": zone, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
            for name, data in files.items()
        },
    }
    manifest.update(extra)
    return manifest


def session_for(manifest, files, **overrides):
    routes = {URL: json.dumps(manifest).encode()}
    for name, data in files.items():
        routes[BASE + name] = data
    routes.update(overrides)
    return FakeSession(routes)


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name.replace("\\", "/") + "/"
        self.addCleanup(self._tmp.cleanup)
        self.logs = []
        self.write("screen.py", b"gammel skjerm")
        self.write("version.py", b'VERSION = "0.1.0"\n')

    def write(self, name, data):
        path = Path(self.root + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, name):
        return Path(self.root + name).read_bytes()

    def log(self, *args):
        self.logs.append(args)

    def check(self, session, current="0.1.0"):
        return updater.check(session, current, root=self.root, log=self.log)

    def release(self, version="0.2.0", **extra):
        files = {"screen.py": b"ny skjerm", "version.py": ('VERSION = "%s"\n' % version).encode()}
        return files, manifest_for(version, files, **extra)

    def test_no_update_when_same_version(self):
        files, manifest = self.release("0.1.0")
        session = session_for(manifest, files)
        self.assertEqual(self.check(session), "ingen ny")
        self.assertEqual(session.requests, [URL])

    def test_applies_new_version_and_keeps_backup(self):
        files, manifest = self.release()
        self.assertEqual(self.check(session_for(manifest, files)), "oppdatert")
        self.assertEqual(self.read("screen.py"), b"ny skjerm")
        self.assertEqual(self.read("ota/prev/screen.py"), b"gammel skjerm")
        self.assertTrue(updater.pending(self.root))
        self.assertFalse(os.path.exists(self.root + "ota/stage"))

    def test_only_changed_files_are_downloaded(self):
        files, manifest = self.release()
        self.write("starwars.py", b"samme")
        files["starwars.py"] = b"samme"
        manifest = manifest_for("0.2.0", files)
        session = session_for(manifest, files)
        self.check(session)
        self.assertNotIn(BASE + "starwars.py", session.requests)

    def test_bad_checksum_changes_nothing(self):
        files, manifest = self.release()
        session = session_for(manifest, files, **{BASE + "screen.py": b"skadet fil!"})
        self.assertEqual(self.check(session), "feilet")
        self.assertEqual(self.read("screen.py"), b"gammel skjerm")
        self.assertFalse(updater.pending(self.root))
        self.assertFalse(os.path.exists(self.root + "ota/stage"))

    def test_http_error_changes_nothing(self):
        files, manifest = self.release()
        session = session_for(manifest, {})
        self.assertEqual(self.check(session), "feilet")
        self.assertEqual(self.read("screen.py"), b"gammel skjerm")

    def test_refuses_core_files(self):
        for name in ("boot.py", "code.py", "updater.py", "settings.toml"):
            files = {name: b"x", "version.py": b'VERSION = "0.2.0"\n'}
            manifest = manifest_for("0.2.0", files)
            self.assertEqual(self.check(session_for(manifest, files)), "feilet", name)
            self.assertFalse(os.path.exists(self.root + name), name)

    def test_refuses_foreign_base_and_path_tricks(self):
        files, manifest = self.release()
        manifest["base"] = "https://example.com/"
        self.assertEqual(self.check(session_for(manifest, files)), "feilet")
        files = {"../x.py": b"x", "version.py": b"v"}
        manifest = manifest_for("0.2.0", files)
        self.assertEqual(self.check(session_for(manifest, files)), "feilet")

    def test_zone1_needs_explicit_flag(self):
        files = {"app.py": b"ny app", "version.py": b'VERSION = "0.2.0"\n'}
        self.write("app.py", b"gammel app")
        denied = manifest_for("0.2.0", files, zone=1)
        self.assertEqual(self.check(session_for(denied, files)), "feilet")
        self.assertEqual(self.read("app.py"), b"gammel app")
        allowed = manifest_for("0.2.0", files, zone=1, allow_zone1=True)
        self.assertEqual(self.check(session_for(allowed, files)), "oppdatert")
        self.assertEqual(self.read("app.py"), b"ny app")

    def test_never_older_version(self):
        files, manifest = self.release("0.0.9")
        self.assertEqual(self.check(session_for(manifest, files)), "ingen ny")

    def test_read_only_disk_is_skipped(self):
        files, manifest = self.release()
        original = updater.writable
        updater.writable = lambda root="/": False
        self.addCleanup(setattr, updater, "writable", original)
        session = session_for(manifest, files)
        self.assertEqual(self.check(session), "skrivebeskyttet")
        self.assertEqual(session.requests, [])

    def test_no_new_check_while_pending(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        files2, manifest2 = self.release("0.3.0")
        self.assertEqual(self.check(session_for(manifest2, files2), "0.2.0"), "venter på kvittering")

    def test_acknowledge_keeps_new_version(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        self.assertTrue(updater.acknowledge(self.root))
        self.assertFalse(updater.pending(self.root))
        self.assertFalse(os.path.exists(self.root + "ota/prev"))
        self.assertIsNone(updater.boot_check(self.root, log=self.log))
        self.assertEqual(self.read("screen.py"), b"ny skjerm")

    def test_boot_check_rolls_back_after_unacknowledged_starts(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        for _ in range(updater.MAX_BOOTS - 1):
            self.assertIsNone(updater.boot_check(self.root, log=self.log))
            self.assertEqual(self.read("screen.py"), b"ny skjerm")
        self.assertEqual(updater.boot_check(self.root, log=self.log), "rullet tilbake")
        self.assertEqual(self.read("screen.py"), b"gammel skjerm")
        self.assertEqual(self.read("version.py"), b'VERSION = "0.1.0"\n')
        self.assertFalse(updater.pending(self.root))

    def test_rollback_removes_created_files(self):
        files = {"ny.py": b"helt ny", "version.py": b'VERSION = "0.2.0"\n'}
        self.check(session_for(manifest_for("0.2.0", files), files))
        self.assertTrue(os.path.exists(self.root + "ny.py"))
        for _ in range(updater.MAX_BOOTS):
            updater.boot_check(self.root, log=self.log)
        self.assertFalse(os.path.exists(self.root + "ny.py"))

    def test_rolled_back_version_is_not_fetched_again(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        for _ in range(updater.MAX_BOOTS):
            updater.boot_check(self.root, log=self.log)
        session = session_for(manifest, files)
        self.assertEqual(self.check(session), "avvist versjon")
        self.assertEqual(session.requests, [URL])
        files3, manifest3 = self.release("0.3.0")
        self.assertEqual(self.check(session_for(manifest3, files3)), "oppdatert")

    def test_power_cut_halfway_through_swap_rolls_back(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        os.remove(self.root + "screen.py")  # strømmen gikk mellom sletting og bytte
        for _ in range(updater.MAX_BOOTS):
            updater.boot_check(self.root, log=self.log)
        self.assertEqual(self.read("screen.py"), b"gammel skjerm")

    def test_boot_check_survives_broken_state_file(self):
        self.write("ota/state.json", b"{ikke json")
        self.assertIsNone(updater.boot_check(self.root, log=self.log))
        self.assertFalse(updater.pending(self.root))


class FakeStorage:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def remount(self, path, readonly=False):
        self.calls.append((path, readonly))
        if self.error and not readonly:
            raise self.error


class CircuitPythonRulesTest(UpdaterTest):
    """Kode er skrivebeskyttet som standard, så alt må gå via storage.remount."""

    def install(self, usb=False, error=None):
        self.storage = FakeStorage(error)
        runtime = types.SimpleNamespace(usb_connected=usb)
        fakes = {"storage": self.storage, "supervisor": types.SimpleNamespace(runtime=runtime)}
        patcher = mock.patch.dict(sys.modules, fakes)
        patcher.start()
        self.addCleanup(patcher.stop)

    def setUp(self):
        super().setUp()
        self.install()

    def test_check_unlocks_then_locks_disk(self):
        files, manifest = self.release()
        self.assertEqual(self.check(session_for(manifest, files)), "oppdatert")
        self.assertEqual(self.storage.calls[0], ("/", False))
        self.assertEqual(self.storage.calls[-1], ("/", True))

    def test_locks_disk_when_nothing_new(self):
        files, manifest = self.release("0.1.0")
        self.assertEqual(self.check(session_for(manifest, files)), "ingen ny")
        self.assertEqual(self.storage.calls[-1], ("/", True))

    def test_pc_attached_never_touches_disk(self):
        self.install(usb=True)
        session = FakeSession({})
        self.assertEqual(self.check(session), "skrivebeskyttet")
        self.assertEqual(self.storage.calls, [])
        self.assertEqual(session.requests, [])

    def test_remount_refused_by_usb_is_read_only(self):
        self.install(error=RuntimeError("Cannot remount path when visible via USB."))
        self.assertEqual(self.check(FakeSession({})), "skrivebeskyttet")

    def test_failure_reason_is_saved(self):
        files, manifest = self.release()
        session = session_for(manifest, files, **{BASE + "screen.py": b"skadet"})
        self.assertEqual(self.check(session), "feilet")
        self.assertIn(b"feil sjekksum", self.read("ota/last.txt"))
        self.assertEqual(self.storage.calls[-1], ("/", True))

    def test_acknowledge_with_pc_attached_keeps_pending(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        self.install(usb=True)
        self.assertFalse(updater.acknowledge(self.root))
        self.assertTrue(updater.pending(self.root))

    def test_acknowledge_locks_disk_again(self):
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        self.storage.calls.clear()
        self.assertTrue(updater.acknowledge(self.root))
        self.assertEqual(self.storage.calls, [("/", False), ("/", True)])

    def test_boot_check_unlocks_even_with_pc_attached(self):
        # I boot.py har USB ikke startet, så usb_connected er uten betydning der.
        files, manifest = self.release()
        self.check(session_for(manifest, files))
        self.install(usb=True)
        updater.boot_check(self.root, log=self.log)
        self.assertEqual(self.storage.calls, [("/", False), ("/", True)])
        self.assertEqual(json.loads(self.read("ota/state.json"))["boots"], 1)

    def test_boot_check_without_pending_touches_nothing(self):
        updater.boot_check(self.root, log=self.log)
        self.assertEqual(self.storage.calls, [])


class PublishTest(unittest.TestCase):
    def files(self):
        return {
            "boot.py": b"b", "code.py": b"c", "updater.py": b"u", "app.py": b"a",
            "screen.py": b"s", "portal.py": b"p", "version.py": b'VERSION = "1.2.3"\n',
            "lib/x.mpy": b"x",
        }

    def test_default_manifest_has_zone_2_and_3_only(self):
        manifest = publish.build_manifest(self.files())
        self.assertEqual(manifest["version"], "1.2.3")
        self.assertEqual(sorted(manifest["files"]), ["portal.py", "screen.py", "version.py"])
        self.assertNotIn("allow_zone1", manifest)
        self.assertEqual(manifest["files"]["screen.py"]["sha256"], hashlib.sha256(b"s").hexdigest())

    def test_zone1_with_flag_and_never_zone0(self):
        manifest = publish.build_manifest(self.files(), allow_zone1=True)
        self.assertIn("app.py", manifest["files"])
        self.assertTrue(manifest["allow_zone1"])
        for name in ("boot.py", "code.py", "updater.py"):
            self.assertNotIn(name, manifest["files"])

    def test_unknown_file_stops_publishing(self):
        files = self.files()
        files["ukjent.py"] = b"?"
        with self.assertRaises(ValueError):
            publish.build_manifest(files)

    def test_every_src_file_has_a_zone(self):
        src = ROOT / "src"
        for path in src.rglob("*"):
            name = path.relative_to(src).as_posix()
            if path.is_dir() or name.startswith("lib/") or "__pycache__" in name:
                continue
            self.assertTrue(name in publish.ZONES or name in publish.ZONE_0, name)

    def test_publish_and_updater_agree_on_zone_0(self):
        for name in publish.ZONE_0:
            self.assertIn(name, updater.NEVER)


if __name__ == "__main__":
    unittest.main()
