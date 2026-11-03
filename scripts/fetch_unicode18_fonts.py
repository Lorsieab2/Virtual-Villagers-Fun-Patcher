"""Fetch, verify and place the open fonts "Render Unicode with In-Game Fonts" and "Use Unicode Font" ship.

The owner, 2026-11-02: "please extend support to the entire Unicode 18.0 chart collection" -- "to all games".
The companions draw every character from, in order: the game's own font, the patcher-made letters, the
player's Windows fonts, then these bundled open fonts, loaded privately by the companion
(AddFontMemResourceEx: never installed, seen by no other program):

  * GNU Unifont 18.0.01 -- "Unifont" (the Basic Multilingual Plane) and "Unifont Upper" (planes 1, 2 and 3):
    a glyph for nearly every assigned character.  Dual-licensed: GNU GPLv2+ with the GNU Font Embedding
    Exception, and the SIL Open Font License 1.1 (both files shipped beside it).
  * Noto Serif Tangut and Noto Sans Cuneiform (unhinted) -- only the scripts neither Unifont nor Windows
    draws: Tangut and its components, Early Dynastic Cuneiform.  SIL Open Font License 1.1.
  * Unicode's Last Resort font 18.000 (High Efficiency) -- a block placeholder, the block's name and the
    range, for anything no other font draws.  SIL Open Font License 1.1.

Downloads are untrusted data: each run downloads into a NEW folder of its own under research/unicode18/,
checks every file against the publisher's own check (Unifont: the GNU maintainer's OpenPGP signature, verified
against the GNU keyring in a keyring folder of its own; Last Resort: the SHA-256 GitHub publishes for the
release asset, where one is published; otherwise the archive's SHA-256 is recorded) and only then copies the fonts and their licenses to assets/unicode_fonts/ and records each
file's source URL, version and SHA-256 in assets/unicode_fonts/SOURCES.json.

Usage:  python scripts/fetch_unicode18_fonts.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "unicode_fonts"
UNIFONT_VERSION = "18.0.01"
UNIFONT_BASE = f"https://ftp.gnu.org/gnu/unifont/unifont-{UNIFONT_VERSION}/"
GNU_KEYRING = "https://ftp.gnu.org/gnu/gnu-keyring.gpg"
LAST_RESORT_VERSION = "18.000"
LAST_RESORT_API = f"https://api.github.com/repos/unicode-org/last-resort-font/releases/tags/{LAST_RESORT_VERSION}"
LAST_RESORT_FILE = "LastResortHE-Regular.ttf"
LAST_RESORT_LICENSE = (f"https://raw.githubusercontent.com/unicode-org/last-resort-font/{LAST_RESORT_VERSION}/"
                       "LICENSE")
UNIFONT_FILES = (f"unifont-{UNIFONT_VERSION}.otf", f"unifont_upper-{UNIFONT_VERSION}.otf")
# The source archive is fetched only for its license files.
UNIFONT_TAR = f"unifont-{UNIFONT_VERSION}.tar.gz"
UNIFONT_LICENSES = {"OFL-1.1.txt": "Unifont-OFL-1.1.txt", "COPYING": "Unifont-GPL-2.0-COPYING.txt"}
# Noto fonts only for scripts neither Unifont nor Windows draws (measured by tests/test_unicode18.py's
# coverage report): Tangut and its components, and Early Dynastic Cuneiform.  The unhinted OpenType files.
NOTO = (
    ("notofonts/tangut", "NotoSerifTangut-v2.170", "NotoSerifTangut/unhinted/otf/NotoSerifTangut-Regular.otf",
     "NotoSerifTangut-OFL-1.1.txt"),
    ("notofonts/cuneiform", "NotoSansCuneiform-v2.001",
     "NotoSansCuneiform/unhinted/otf/NotoSansCuneiform-Regular.otf", "NotoSansCuneiform-OFL-1.1.txt"),
)


def get(url: str, dest: Path) -> bytes:
    print("fetch", url)
    req = urllib.request.Request(url, headers={"User-Agent": "VVFP-font-fetch"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    dest.write_bytes(data)
    return data


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def verify_signature(folder: Path, file: Path, sig: Path, keyring: Path) -> None:
    home = folder / "gnupg-home"
    home.mkdir(exist_ok=True)
    env_home = str(home).replace("\\", "/")
    if env_home[1:2] == ":":                       # Git for Windows' gpg takes /c/... paths
        env_home = "/" + env_home[0].lower() + env_home[2:]
    gpg = ["gpg", "--homedir", env_home, "--batch", "--no-default-keyring",
           "--keyring", _posix(keyring), "--verify", _posix(sig), _posix(file)]
    r = subprocess.run(gpg, capture_output=True, text=True)
    print(r.stderr.strip())
    if r.returncode != 0 or "Good signature" not in r.stderr:
        raise SystemExit(f"{file.name}: the OpenPGP signature does not verify -- nothing was copied")


def _posix(p: Path) -> str:
    s = str(p).replace("\\", "/")
    return "/" + s[0].lower() + s[2:] if s[1:2] == ":" else s


def main() -> None:
    folder = ROOT / "research" / "unicode18" / time.strftime("fonts-%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=False)
    keyring = folder / "gnu-keyring.gpg"
    get(GNU_KEYRING, keyring)
    record: dict = {"note": "The open fonts the Unicode companions load privately (AddFontMemResourceEx) as the "
                            "last steps of their fallback chain; fetched and verified by "
                            "scripts/fetch_unicode18_fonts.py.", "files": {}}
    for name in UNIFONT_FILES + (UNIFONT_TAR,):
        data = get(UNIFONT_BASE + name, folder / name)
        get(UNIFONT_BASE + name + ".sig", folder / (name + ".sig"))
        verify_signature(folder, folder / name, folder / (name + ".sig"), keyring)
        if name != UNIFONT_TAR:
            record["files"][name] = {"source": UNIFONT_BASE + name, "version": f"GNU Unifont {UNIFONT_VERSION}",
                                     "verified": "OpenPGP signature " + UNIFONT_BASE + name + ".sig "
                                                 "(GNU keyring " + GNU_KEYRING + ")",
                                     "license": "GPL-2.0-or-later WITH Font-exception-2.0 OR OFL-1.1",
                                     "sha256": sha(data), "bytes": len(data)}
    licenses = folder / "licenses"
    licenses.mkdir()
    with tarfile.open(folder / UNIFONT_TAR, "r:gz") as tar:
        for member in tar.getmembers():
            base = member.name.rsplit("/", 1)[-1]
            if member.isfile() and base in UNIFONT_LICENSES and member.name.count("/") == 1:
                data = tar.extractfile(member).read()
                (licenses / UNIFONT_LICENSES[base]).write_bytes(data)
                record["files"][UNIFONT_LICENSES[base]] = {
                    "source": UNIFONT_BASE + UNIFONT_TAR + " (" + member.name + ")", "sha256": sha(data),
                    "bytes": len(data)}
    if len(list(licenses.iterdir())) != len(UNIFONT_LICENSES):
        raise SystemExit("the Unifont archive does not hold both license files")
    with urllib.request.urlopen(urllib.request.Request(LAST_RESORT_API, headers={"User-Agent": "VVFP"}),
                                timeout=60) as r:
        release = json.loads(r.read())
    asset = next(a for a in release["assets"] if a["name"] == LAST_RESORT_FILE)
    data = get(asset["browser_download_url"], folder / LAST_RESORT_FILE)
    published = asset.get("digest", "").removeprefix("sha256:").upper()
    if not published or published != sha(data):
        raise SystemExit(f"{LAST_RESORT_FILE}: SHA-256 {sha(data)} is not the published {published!r}")
    record["files"][LAST_RESORT_FILE] = {"source": asset["browser_download_url"],
                                         "version": f"Last Resort {LAST_RESORT_VERSION}",
                                         "verified": "SHA-256 published for the release asset (" + LAST_RESORT_API + ")",
                                         "license": "OFL-1.1", "sha256": sha(data), "bytes": len(data)}
    lic = get(LAST_RESORT_LICENSE, licenses / "LastResort-OFL-1.1.txt")
    record["files"]["LastResort-OFL-1.1.txt"] = {"source": LAST_RESORT_LICENSE, "sha256": sha(lic), "bytes": len(lic)}
    placed = list(UNIFONT_FILES + (LAST_RESORT_FILE,))
    for repo, tag, member, license_name in NOTO:
        api = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
        with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": "VVFP"}), timeout=60) as r:
            release = json.loads(r.read())
        asset = next(a for a in release["assets"] if a["name"] == tag + ".zip")
        own = folder / tag                          # each download in a folder of its own
        own.mkdir()
        data = get(asset["browser_download_url"], own / asset["name"])
        published = (asset.get("digest") or "").removeprefix("sha256:").upper()
        if published and published != sha(data):
            raise SystemExit(f"{asset['name']}: SHA-256 {sha(data)} is not the published {published}")
        verified = ("SHA-256 published for the release asset (" + api + ")" if published else
                    "no checksum is published for this release asset; its SHA-256 is recorded here")
        # Members are read by name, never extracted (an archive's paths are untrusted).
        with zipfile.ZipFile(own / asset["name"]) as z:
            font = z.read(member)
            ofl = next(z.read(n) for n in z.namelist() if n.rsplit("/", 1)[-1] == "OFL.txt")
        name = member.rsplit("/", 1)[-1]
        (folder / name).write_bytes(font)
        (licenses / license_name).write_bytes(ofl)
        placed.append(name)
        record["files"][name] = {"source": asset["browser_download_url"] + " (" + member + ")",
                                 "version": tag, "verified": verified, "archive_sha256": sha(data),
                                 "license": "OFL-1.1", "sha256": sha(font), "bytes": len(font)}
        record["files"][license_name] = {"source": asset["browser_download_url"] + " (OFL.txt)",
                                         "sha256": sha(ofl), "bytes": len(ofl)}
    OUT.mkdir(parents=True, exist_ok=True)
    for name in placed:
        shutil.copyfile(folder / name, OUT / name)
    for f in licenses.iterdir():
        shutil.copyfile(f, OUT / f.name)
    (OUT / "SOURCES.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("placed", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
