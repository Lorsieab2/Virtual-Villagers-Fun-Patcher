"""Scan a user-submitted file with VirusTotal (API v3) before anything else looks at it.

The owner (2026-11-02): "MORE SAFETY CHECKS FOR USER SUBMISSIONS: PLEASE RUN EVERY SINGLE USER-SUBMITTED FILE
THROUGH VIRUSTOTAL AND REJECT ANYTHING THAT IS FLAGGED."

* The file is looked up by its SHA-256 (GET /api/v3/files/{sha256}).  Unknown to VirusTotal (404): it is
  uploaded (POST /api/v3/files) and its analysis polled (GET /api/v3/analyses/{id}) until it completes or
  POLL_TIMEOUT passes.
* The free API allows 4 requests a minute: requests are spaced MIN_INTERVAL apart, and a 429 answer waits
  (doubling, up to MAX_BACKOFF) and tries again while the time allows.
* The verdict is CLEAN only when an analysis exists and NO engine says malicious or suspicious.  Any engine
  that does: FLAGGED, naming the engines.  No key, VirusTotal unreachable, an error answer, an analysis that
  never completes: NOT SCANNED, which fails exactly like FLAGGED.  Nothing is ever treated as a pass by
  default.
* The key is read only from the environment variable VT_API_KEY (the repository secret of the same name).
  It is sent only in the x-apikey request header: never printed, logged, written to a file or put on a
  command line, and every message this module makes is free of it.

    python -I scripts/virustotal_scan.py --json result.json --markdown comment.md FILE...

Exit code 0: every file is clean.  1: a file is flagged or was not scanned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

API = "https://www.virustotal.com/api/v3"
KEY_ENV = "VT_API_KEY"
MIN_INTERVAL = 15.5          # seconds between requests: the free API's 4 a minute, with a little room
MAX_BACKOFF = 120.0
POLL_TIMEOUT = 600.0         # an uploaded file's analysis must complete within this
REQUEST_TIMEOUT = 60
CLEAN, FLAGGED, NOT_SCANNED = "clean", "flagged", "not scanned"
BAD_CATEGORIES = ("malicious", "suspicious")
MISSING_KEY = ("not scanned: the repository secret VT_API_KEY is not set, so the file could not be sent to "
               "VirusTotal. The maintainer must add it (docs/translations-for-maintainers.md, \"VirusTotal key\").")


@dataclass
class Verdict:
    status: str                       # CLEAN, FLAGGED or NOT_SCANNED
    sha256: str
    engines: list[str] = field(default_factory=list)      # "<engine>: <category> (<result>)" for each bad one
    detail: str = ""
    engine_count: int = 0

    @property
    def clean(self) -> bool:
        return self.status == CLEAN

    def as_dict(self) -> dict:
        return {"status": self.status, "sha256": self.sha256, "engines": list(self.engines),
                "detail": self.detail, "engine_count": self.engine_count}


class _Answer:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.body = body

    def json(self) -> dict:
        try:
            value = json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}


def _urllib_request(method: str, url: str, headers: dict, body: bytes | None) -> _Answer:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310 (https only)
            return _Answer(response.status, response.read())
    except urllib.error.HTTPError as error:
        return _Answer(error.code, error.read() or b"")


class Client:
    """VirusTotal API v3 with the free API's pacing.  `request(method, url, headers, body) -> _Answer`,
    `sleep` and `clock` are replaced in tests."""

    def __init__(self, key: str, request=None, sleep=time.sleep, clock=time.monotonic,
                 min_interval: float = MIN_INTERVAL):
        self._key = key
        self._request = request or _urllib_request
        self._sleep = sleep
        self._clock = clock
        self._min_interval = min_interval
        self._last: float | None = None

    def __repr__(self) -> str:                    # never show the key
        return "Client(key=<hidden>)"

    def _pace(self) -> None:
        if self._last is not None:
            wait = self._min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def call(self, method: str, path: str, body: bytes | None = None, content_type: str | None = None,
             deadline: float | None = None) -> _Answer:
        """One request; a 429 (rate limit) waits and tries again until `deadline`."""
        if not path.startswith("/"):
            raise ValueError("path must start with /")
        backoff = self._min_interval
        while True:
            self._pace()
            headers = {"x-apikey": self._key, "accept": "application/json"}
            if content_type:
                headers["content-type"] = content_type
            try:
                answer = self._request(method, API + path, headers, body)
            except (OSError, ValueError) as error:
                return _Answer(0, str(type(error).__name__).encode())
            if answer.status != 429:
                return answer
            if deadline is not None and self._clock() + backoff > deadline:
                return answer
            self._sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verdict_from_stats(sha: str, results: dict, stats: dict) -> Verdict:
    bad = []
    if isinstance(results, dict):
        for engine, outcome in sorted(results.items()):
            if isinstance(outcome, dict) and outcome.get("category") in BAD_CATEGORIES:
                bad.append(f"{engine}: {outcome.get('category')} ({outcome.get('result') or 'no name'})")
    counts = stats if isinstance(stats, dict) else {}
    flagged_count = sum(int(counts.get(c, 0) or 0) for c in BAD_CATEGORIES)
    engine_count = sum(int(v or 0) for v in counts.values() if isinstance(v, int))
    if bad or flagged_count:
        if not bad:
            bad = [f"{flagged_count} engine(s) (names not given)"]
        return Verdict(FLAGGED, sha, bad, "flagged by VirusTotal", engine_count)
    if engine_count == 0 and not results:
        return Verdict(NOT_SCANNED, sha, [], "not scanned: VirusTotal returned no engine results")
    return Verdict(CLEAN, sha, [], "no engine reported it as malicious or suspicious", engine_count)


def _multipart(name: str, data: bytes) -> tuple[bytes, str]:
    boundary = "vvfp-" + uuid.uuid4().hex
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "._-") or "file"
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    return head + data + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def scan_bytes(data: bytes, name: str = "file", key: str | None = None, client: Client | None = None,
               poll_timeout: float = POLL_TIMEOUT) -> Verdict:
    """The verdict on `data`.  `key` defaults to the VT_API_KEY environment variable."""
    sha = sha256_of(data)
    if client is None:
        key = os.environ.get(KEY_ENV, "") if key is None else key
        if not key.strip():
            return Verdict(NOT_SCANNED, sha, [], MISSING_KEY)
        client = Client(key.strip())
    start = client._clock()
    deadline = start + poll_timeout
    answer = client.call("GET", f"/files/{sha}", deadline=deadline)
    if answer.status == 200:
        attributes = answer.json().get("data", {}).get("attributes", {})
        return _verdict_from_stats(sha, attributes.get("last_analysis_results", {}),
                                   attributes.get("last_analysis_stats", {}))
    if answer.status == 429:
        return Verdict(NOT_SCANNED, sha, [], "not scanned: VirusTotal's rate limit did not clear in time")
    if answer.status != 404:
        return Verdict(NOT_SCANNED, sha, [], f"not scanned: VirusTotal could not be reached (answer {answer.status})")
    body, content_type = _multipart(name, data)
    answer = client.call("POST", "/files", body=body, content_type=content_type, deadline=deadline)
    if answer.status != 200:
        return Verdict(NOT_SCANNED, sha, [], f"not scanned: the upload to VirusTotal failed (answer {answer.status})")
    analysis = answer.json().get("data", {}).get("id", "")
    if not isinstance(analysis, str) or not analysis or "/" in analysis or "?" in analysis:
        return Verdict(NOT_SCANNED, sha, [], "not scanned: VirusTotal gave no analysis to wait for")
    while True:
        answer = client.call("GET", f"/analyses/{analysis}", deadline=deadline)
        if answer.status == 200:
            attributes = answer.json().get("data", {}).get("attributes", {})
            if attributes.get("status") == "completed":
                return _verdict_from_stats(sha, attributes.get("results", {}), attributes.get("stats", {}))
        elif answer.status != 429:
            return Verdict(NOT_SCANNED, sha, [], f"not scanned: the analysis could not be read (answer {answer.status})")
        if client._clock() >= deadline:
            return Verdict(NOT_SCANNED, sha, [], "not scanned: VirusTotal's analysis did not finish in time")


def markdown(results: list[tuple[str, Verdict]]) -> str:
    """The PR / issue comment: every file's verdict, the flagging engines named."""
    lines = ["### VirusTotal scan", ""]
    for name, verdict in results:
        safe = name.replace("`", "'")
        if verdict.status == CLEAN:
            lines.append(f"- `{safe}`: clean ({verdict.engine_count} engines; SHA-256 `{verdict.sha256}`)")
        elif verdict.status == FLAGGED:
            lines.append(f"- `{safe}`: **FLAGGED** by VirusTotal -- refused. Engines:")
            lines += [f"  - {engine.replace('`', chr(39))}" for engine in verdict.engines]
        else:
            lines.append(f"- `{safe}`: **NOT SCANNED** -- refused until it is scanned. {verdict.detail}")
    lines += ["", "Every file sent to this repository is sent to VirusTotal; anything flagged, or not scanned, is "
              "refused. Never put private details in a translation file."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan files with VirusTotal (key: the VT_API_KEY environment variable).")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args(argv)
    results = []
    for path in args.files:
        try:
            data = path.read_bytes()
        except OSError:
            results.append((path.name, Verdict(NOT_SCANNED, "", [], "not scanned: the file could not be read")))
            continue
        results.append((path.name, scan_bytes(data, path.name)))
    if args.json:
        args.json.write_text(json.dumps({name: v.as_dict() for name, v in results}, indent=1), encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(markdown(results), encoding="utf-8")
    for name, verdict in results:
        print(f"{name}: {verdict.status}")
    return 0 if all(v.clean for _n, v in results) else 1


if __name__ == "__main__":
    sys.exit(main())
