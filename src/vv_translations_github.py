"""Download from GitHub...: the translations in the patcher's public GitHub folder, read-only, with no login.

The owner (2026-11-02): "yeah there should be a button to Download translation files from my patcher github
repos too!" and "for User-Submitted Translations, make the patcher submit user-submitted translations there and
download ones from there".

* The list: the public GitHub contents API (https://api.github.com/repos/<repo>/contents/translations/vv<N>, no
  token) for the folder's files, and translations/manifest.json, which the repository's workflow writes only
  for files that passed the VirusTotal scan and the validator.  A file whose SHA-256 is not listed clean there
  is never offered (and a downloaded file whose bytes do not hash to the listed SHA-256 is refused).
* Each file's language, credit and last change come from the manifest; the last change is read from the
  commits API when it can be (one request per file, skipped once GitHub's anonymous limit is near).
* "Update available": a file of the same language and credit is installed, its bytes differ from GitHub's
  (SHA-256), and GitHub's copy changed after the installed copy did.
* Downloads are data only: at most MAX_BYTES, hashed, decoded and checked by the same validator as Add
  translation file..., then installed like it.  Nothing downloaded is ever run.
* No network, a rate limit, an error answer or a bad file: a RemoteError with a plain sentence; nothing is
  installed.
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import vv_translation_format as fmt
import vv_translations as tr

REPO = "Lorsieab2/Virtual-Villagers-Fun-Patcher"
API = "https://api.github.com"
RAW_HOSTS = ("raw.githubusercontent.com",)
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 30
UPDATE = "Update available"
INSTALLED = "Installed"
DIFFERENT = "Installed (yours differs)"


class RemoteError(Exception):
    """Why GitHub could not be read, in a sentence for the player."""


@dataclass
class RemoteFile:
    game: int
    name: str                 # "fr.tsv"
    path: str                 # "translations/vv3/fr.tsv"
    sha256: str
    language: str
    code: str
    translator: str
    changed: str              # ISO date, "" when unknown
    size: int
    download_url: str
    test: bool = False
    status: str = ""          # "", INSTALLED, UPDATE, DIFFERENT
    local: Path | None = None

    @property
    def label(self) -> str:
        return f"{self.language}, by {self.translator}" if self.translator else self.language

    @property
    def changed_text(self) -> str:
        when = parse_date(self.changed)
        return when.strftime("%Y-%m-%d") if when else "unknown"


def parse_date(text: str):
    try:
        when = _dt.datetime.fromisoformat((text or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=_dt.timezone.utc)


def _https_get(url: str) -> tuple[int, dict, bytes]:
    """GET over https only; (status, headers, body).  Raises RemoteError when GitHub cannot be reached."""
    if urllib.parse.urlsplit(url).scheme != "https":
        raise RemoteError("Only https addresses are used.")
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "Virtual-Villagers-Fun-Patcher"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 (https checked)
            return response.status, dict(response.headers), response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers or {}), error.read(4096) if error.fp else b""
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise RemoteError(f"GitHub could not be reached (no network connection?): {getattr(error, 'reason', error)}") \
            from None


class Client:
    def __init__(self, get=None, repo: str = REPO):
        self._get = get or _https_get
        self.repo = repo
        self.remaining: int | None = None

    def _checked(self, url: str) -> bytes:
        status, headers, body = self._get(url)
        lower = {str(k).lower(): v for k, v in (headers or {}).items()}
        try:
            self.remaining = int(lower.get("x-ratelimit-remaining", "")) if lower.get("x-ratelimit-remaining") \
                not in (None, "") else self.remaining
        except ValueError:
            pass
        if status in (403, 429) and (lower.get("x-ratelimit-remaining") == "0" or status == 429):
            reset = lower.get("x-ratelimit-reset", "")
            when = ""
            if str(reset).isdigit():
                when = " after " + _dt.datetime.fromtimestamp(int(reset)).strftime("%H:%M")
            raise RemoteError(f"GitHub's limit for requests without a login was reached. Try again{when}.")
        if status == 404:
            raise RemoteError("The translations folder was not found on GitHub.")
        if status != 200:
            raise RemoteError(f"GitHub answered with an error ({status}). Try again later.")
        return body

    def _json(self, url: str):
        try:
            return json.loads(self._checked(url).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise RemoteError("GitHub's answer could not be read.") from None

    def manifest(self) -> dict:
        info = self._json(f"{API}/repos/{self.repo}/contents/{tr.PUBLIC_FOLDER}/manifest.json")
        try:
            data = json.loads(base64.b64decode(info.get("content", "") or "").decode("utf-8"))
        except (ValueError, UnicodeDecodeError, AttributeError):
            raise RemoteError("The list of scanned translations on GitHub could not be read.") from None
        files = data.get("files", {}) if isinstance(data, dict) else {}
        return files if isinstance(files, dict) else {}

    def last_change(self, path: str) -> str:
        url = f"{API}/repos/{self.repo}/commits?" + urllib.parse.urlencode({"path": path, "per_page": 1})
        commits = self._json(url)
        if isinstance(commits, list) and commits:
            commit = commits[0].get("commit", {}) if isinstance(commits[0], dict) else {}
            return str((commit.get("committer") or {}).get("date", "") or "")
        return ""

    def list_game(self, game) -> list[RemoteFile]:
        """Every scanned-clean translation of `game` in the public folder (every variant of a language, each with
        its credit), by language."""
        number = tr.game_number(game)
        manifest = self.manifest()
        listing = self._json(f"{API}/repos/{self.repo}/contents/{tr.PUBLIC_FOLDER}/vv{number}")
        if not isinstance(listing, list):
            raise RemoteError("GitHub's answer could not be read.")
        out = []
        for item in listing:
            if not isinstance(item, dict) or item.get("type") != "file":
                continue
            name = str(item.get("name", ""))
            if not name.endswith(".tsv") or Path(name).name != name:
                continue
            entry = manifest.get(f"vv{number}/{name}")
            if not isinstance(entry, dict) or entry.get("verdict") != "clean" or not entry.get("sha256"):
                continue                               # not scanned clean: never offered
            url = str(item.get("download_url", "") or "")
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != "https" or parts.hostname not in RAW_HOSTS:
                continue
            out.append(RemoteFile(number, name, f"{tr.PUBLIC_FOLDER}/vv{number}/{name}", str(entry["sha256"]),
                                  str(entry.get("language", "")), str(entry.get("code", "")),
                                  str(entry.get("translator", "")), str(entry.get("changed", "") or ""),
                                  int(item.get("size", 0) or 0), url, bool(entry.get("test", False))))
        for remote in out:
            if self.remaining is not None and self.remaining <= len(out) + 2:
                break                                  # keep the anonymous limit for the downloads
            try:
                remote.changed = self.last_change(remote.path) or remote.changed
            except RemoteError:
                break
        mark_status(number, out)
        out.sort(key=lambda r: (r.language.casefold(), r.translator.casefold(), r.name))
        return out

    def fetch(self, remote: RemoteFile) -> bytes:
        status, _headers, body = self._get(remote.download_url)
        if status != 200:
            raise RemoteError(f"{remote.name} could not be downloaded ({status}).")
        if len(body) > MAX_BYTES:
            raise RemoteError(f"{remote.name} is larger than {MAX_BYTES // (1024 * 1024)} MB and was not installed.")
        if hashlib.sha256(body).hexdigest() != remote.sha256.lower():
            raise RemoteError(f"{remote.name} is not the file that was scanned (its SHA-256 differs) and was not "
                              "installed.")
        return body


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mark_status(game, remotes: list[RemoteFile]) -> None:
    """Each remote file's status against the installed ones of the same language, code and credit."""
    local = tr.installed(game)
    for remote in remotes:
        same = [i for i in local if i.code.casefold() == remote.code.casefold()
                and i.translator.strip().casefold() == remote.translator.strip().casefold()]
        remote.status, remote.local = "", None
        if not same:
            continue
        item = same[0]
        remote.local = item.path
        try:
            if sha256_file(item.path) == remote.sha256.lower():
                remote.status = INSTALLED
                continue
            mtime = _dt.datetime.fromtimestamp(item.path.stat().st_mtime, _dt.timezone.utc)
        except OSError:
            continue
        when = parse_date(remote.changed)
        remote.status = UPDATE if when is not None and when > mtime else DIFFERENT


def install(remote: RemoteFile, data: bytes, check) -> Path:
    """Install downloaded bytes like Add translation file...: `check(path) -> Checked` (the window's
    check_translation) must accept them; the file then goes into the player's Installed translations under
    its own name rules (an update replaces the same translator's file)."""
    folder = Path(tempfile.mkdtemp(prefix="vvfp-download-"))
    try:
        temp = folder / "download.tsv"
        temp.write_bytes(data)
        checked = check(temp)
        if not checked.ok:
            raise RemoteError(f"{remote.name} was refused: " + "; ".join(checked.refused or ["it cannot be read"]))
        if checked.tf.code.casefold() != remote.code.casefold() or \
                (checked.tf.game and checked.tf.game.casefold() != tr.TITLES[remote.game].casefold()):
            raise RemoteError(f"{remote.name} is not the {remote.label} translation it was listed as.")
        if remote.local is not None and remote.local.parent == tr.game_dir(remote.game):
            target = remote.local
            tr._atomic_copy(temp, target)
            return target
        return tr.install_file(remote.game, temp)
    except (OSError, fmt.FormatError) as error:
        raise RemoteError(f"{remote.name} could not be installed: {error}") from None
    finally:
        for child in folder.glob("*"):
            try:
                child.unlink()
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass
