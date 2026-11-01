"""Lager update.json fra det som er committet i src\\ (HEAD).

Bruk: python tools\\publish.py [--allow-zone1]
Deretter: git add update.json, commit og push. Kortet henter manifestet selv.
Versjonen tas fra src\\version.py. Øk den før hver publisering, ellers ser ikke kortet noe nytt.
Sjekksummene regnes av de committede filene, det raw-URL-en serverer, ikke arbeidskopien.
"""

import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

BASE = "https://raw.githubusercontent.com/nilsihlen/feather-s3-tft/main/src/"

# Sone 0 står aldri i manifestet. Sone 1 bare med --allow-zone1 (Nils har godtatt risikoen).
ZONES = {
    "app.py": 1, "netconfig.py": 1, "wifisetup.py": 1, "captive.py": 1, "guard.py": 1,
    "portal.py": 2, "vrm.py": 2, "portal_root.pem": 2,
    "screen.py": 3, "starwars.py": 3, "version.py": 3,
}
ZONE_0 = ("boot.py", "code.py", "updater.py")
IGNORED_PREFIXES = ("lib/",)


def build_manifest(files, allow_zone1=False):
    """`files` er {navn under src: innhold som bytes}. Ukjente filer stopper publiseringen."""
    match = re.search(rb'VERSION = "([0-9]+(?:\.[0-9]+)*)"', files["version.py"])
    if not match:
        raise ValueError("fant ikke VERSION i version.py")
    entries = {}
    for name, data in sorted(files.items()):
        if name in ZONE_0 or name.startswith(IGNORED_PREFIXES) or name.endswith(".pyc"):
            continue
        if name not in ZONES:
            raise ValueError("ukjent fil i src: %s. Legg den i ZONES i tools/publish.py" % name)
        zone = ZONES[name]
        if zone == 1 and not allow_zone1:
            continue
        entries[name] = {
            "zone": zone,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        }
    manifest = {"version": match.group(1).decode(), "base": BASE, "files": entries}
    if allow_zone1:
        manifest["allow_zone1"] = True
    return manifest


def _git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def main():
    repo = pathlib.Path(__file__).resolve().parent.parent
    allow_zone1 = "--allow-zone1" in sys.argv[1:]
    os.chdir(repo)
    if _git("status", "--porcelain", "src").strip():
        sys.exit("src\\ har ucommittede endringer. Commit først, så publiseres det som ligger i HEAD.")
    names = _git("ls-tree", "-r", "--name-only", "HEAD", "src").decode().split()
    files = {n[len("src/"):]: _git("show", "HEAD:" + n) for n in names}
    manifest = build_manifest(files, allow_zone1)
    (repo / "update.json").write_text(json.dumps(manifest, indent=1) + "\n", newline="\n")
    print("update.json: versjon %s, %d filer%s" % (
        manifest["version"], len(manifest["files"]), ", sone 1 med" if allow_zone1 else ""))
    print("Neste: git add update.json, commit og push.")


if __name__ == "__main__":
    main()
