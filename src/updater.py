"""Henter ny kode fra GitHub og ruller tilbake hvis den ikke virker. Sone 0: aldri over nett.

Se docs\\PLAN_ota.md. Kortet henter `update.json` og filene i den, sjekker sha256 og
bytter dem inn. Før bytte skrives tilstanden til `ota/state.json`, og forrige versjon
ligger i `ota/prev/`. Programmet kvitterer med `acknowledge()` etter første vellykkede
runde. Starter kortet MAX_BOOTS ganger uten kvittering, ruller `boot_check()` tilbake.
CircuitPython kan bare skrive når ingen PC holder USB-disken, så alt hoppes over da.
"""

import hashlib
import json
import os

PREFIX = "https://raw.githubusercontent.com/nilsihlen/feather-s3-tft/"
MANIFEST_URL = PREFIX + "main/update.json"
# Så mange starter uten kvittering, den siste inkludert, før forrige versjon tas tilbake.
MAX_BOOTS = 3
# Filer som aldri skal byttes over nett, uansett hva manifestet sier.
NEVER = ("boot.py", "code.py", "updater.py", "settings.toml")
ZONES_ALLOWED = (2, 3)
CHUNK = 1024


def _exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def _is_dir(path):
    return bool(os.stat(path)[0] & 0x4000)


def _sync():
    sync = getattr(os, "sync", None)
    if sync:
        sync()


def _mkdirs(root, name):
    current = root
    for part in name.split("/")[:-1]:
        current += part
        if not _exists(current):
            os.mkdir(current)
        current += "/"


def _remove_tree(path):
    if not _exists(path):
        return
    if _is_dir(path):
        for entry in os.listdir(path):
            _remove_tree(path + "/" + entry)
        os.rmdir(path)
    else:
        os.remove(path)


def _copy(source, target):
    with open(source, "rb") as src, open(target, "wb") as dst:
        while True:
            block = src.read(CHUNK)
            if not block:
                break
            dst.write(block)


def sha256_file(path):
    digest = hashlib.new("sha256")
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.digest().hex()


def _version_tuple(version):
    return tuple(int(part) for part in version.split("."))


def _read_state(root):
    try:
        with open(root + "ota/state.json") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _write_state(root, state):
    _mkdirs(root, "ota/state.json")
    with open(root + "ota/state.json", "w") as handle:
        json.dump(state, handle)
    _sync()


def pending(root="/"):
    """True mens en ny versjon ikke er kvittert."""
    return bool(_read_state(root).get("pending"))


def writable(root="/"):
    """Disken kan skrives bare når ingen PC holder den."""
    try:
        _mkdirs(root, "ota/x")
        with open(root + "ota/.probe", "w") as handle:
            handle.write("x")
        os.remove(root + "ota/.probe")
        return True
    except OSError:
        return False


def acknowledge(root="/"):
    """Programmet har kjørt og tegnet. Behold den nye versjonen. False hvis disken er låst."""
    try:
        state = _read_state(root)
        if not state.get("pending"):
            return True
        state.update(pending=False, boots=0)
        _write_state(root, state)
        _remove_tree(root + "ota/prev")
        return True
    except OSError:
        return False


def _rollback(root, state):
    created = state.get("created", [])
    for name in state.get("files", []):
        target = root + name
        saved = root + "ota/prev/" + name
        if name in created:
            if _exists(target):
                os.remove(target)
        elif _exists(saved):
            if _exists(target):
                os.remove(target)
            _copy(saved, target)
    state.update(pending=False, boots=0, bad=state.get("to"), rolled_back=True)
    _write_state(root, state)
    _remove_tree(root + "ota/prev")


def boot_check(root="/", log=print):
    """Kalles fra boot.py. Returnerer «rullet tilbake» når forrige versjon er tilbake."""
    try:
        state = _read_state(root)
        if not state.get("pending"):
            return None
        state["boots"] = state.get("boots", 0) + 1
        if state["boots"] < MAX_BOOTS:
            _write_state(root, state)
            return None
        log("oppdatering ikke kvittert, ruller tilbake til", state.get("from"))
        _rollback(root, state)
        return "rullet tilbake"
    except Exception as exc:
        log("boot_check feilet:", repr(exc))
        return None


def _validate(manifest):
    files = manifest["files"]
    if not manifest["base"].startswith(PREFIX):
        raise ValueError("base utenfor repoet")
    for name, entry in files.items():
        if name in NEVER or name.startswith("ota/") or name.startswith("/") or ".." in name:
            raise ValueError("ulovlig fil: " + name)
        zone = entry["zone"]
        if zone not in ZONES_ALLOWED and not (zone == 1 and manifest.get("allow_zone1") is True):
            raise ValueError("sone %s ikke tillatt: %s" % (zone, name))


def _download(session, url, path, size, sha):
    digest = hashlib.new("sha256")
    total = 0
    with session.get(url, timeout=30) as response:
        if response.status_code != 200:
            raise OSError("HTTP %d" % response.status_code)
        with open(path, "wb") as handle:
            for block in response.iter_content(CHUNK):
                handle.write(block)
                digest.update(block)
                total += len(block)
    if total != size or digest.digest().hex() != sha:
        raise ValueError("feil sjekksum: " + url)


def check(session, current, root="/", url=MANIFEST_URL, log=print, progress=None):
    """Henter og bytter inn ny versjon. Kaster aldri.

    Returnerer «oppdatert» (kortet må startes på nytt), «ingen ny», «skrivebeskyttet»,
    «venter på kvittering», «dårlig versjon» eller «feilet».
    """
    try:
        return _check(session, current, root, url, log, progress)
    except Exception as exc:
        log("oppdatering feilet:", repr(exc))
        try:
            _remove_tree(root + "ota/stage")
        except OSError:
            pass
        return "feilet"


def _check(session, current, root, url, log, progress):
    state = _read_state(root)
    if state.get("pending"):
        return "venter på kvittering"
    if not writable(root):
        return "skrivebeskyttet"
    with session.get(url, timeout=20) as response:
        if response.status_code != 200:
            raise OSError("HTTP %d" % response.status_code)
        manifest = response.json()
    version = manifest["version"]
    if _version_tuple(version) <= _version_tuple(current):
        return "ingen ny"
    if version == state.get("bad"):
        return "dårlig versjon"
    _validate(manifest)

    todo = []
    for name, entry in manifest["files"].items():
        local = root + name
        if not _exists(local) or sha256_file(local) != entry["sha256"]:
            todo.append(name)
    if progress:
        progress(version)
    _remove_tree(root + "ota/stage")
    for name in todo:
        entry = manifest["files"][name]
        _mkdirs(root, "ota/stage/" + name)
        _download(session, manifest["base"] + name, root + "ota/stage/" + name,
                  entry["size"], entry["sha256"])

    # Tilstanden skrives først: faller strømmen midt i byttet, ruller neste oppstart tilbake.
    created = [name for name in todo if not _exists(root + name)]
    _write_state(root, {
        "pending": True, "boots": 0, "from": current, "to": version,
        "bad": state.get("bad"), "files": todo, "created": created,
    })
    _remove_tree(root + "ota/prev")
    for name in todo:
        target = root + name
        _mkdirs(root, name)
        if name not in created:
            _mkdirs(root, "ota/prev/" + name)
            _copy(target, root + "ota/prev/" + name)
            os.remove(target)
        os.rename(root + "ota/stage/" + name, target)
    _sync()
    _remove_tree(root + "ota/stage")
    log("oppdatert til", version, todo)
    return "oppdatert"
