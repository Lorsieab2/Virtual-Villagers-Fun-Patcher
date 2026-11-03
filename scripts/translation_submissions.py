"""The public translations/ folder's checks: what a submission may be, the VirusTotal scan, the validator, and the
manifest of scanned files the patcher's Download from GitHub... trusts.

The owner (2026-11-02): "THERE SHOULD ALSO BE A PUBLIC FOLDER ON THE GITHUB WHERE ALL TRANSLATION FILES CAN BE
PUT ON THERE!!!!" and "PLEASE RUN EVERY SINGLE USER-SUBMITTED FILE THROUGH VIRUSTOTAL AND REJECT ANYTHING THAT IS
FLAGGED."

Commands (each run by .github/workflows/translation-pr.yml, translation-record.yml or accept-translation.yml):

  fetch-pr   the pull request's changed files under translations/, read as DATA through the GitHub API (blob by
             blob; nothing of the pull request is checked out or run) into $WORK/files/, listed in
             $WORK/files.json.  Needs GH_TOKEN, REPO, PR_NUMBER, WORK.
  scan       every fetched file: the accepted shape first (check_shape), then VirusTotal
             (scripts/virustotal_scan.py; key only from VT_API_KEY).  Writes $WORK/scan.md and scan.json;
             exit 1 unless every file is clean.
  validate   every fetched file with scripts/validate_translation.py (the patcher's own validator).  Writes
             $WORK/validate.md; exit 1 on a refusal.
  record     on the default branch's checkout: every translations/vv<N>/*.tsv scanned (again when its hash is not
             recorded clean) and validated; translations/manifest.json rewritten with sha256, scan date, verdict,
             language, code, credit and last change.  A file that is not clean and valid is left out of it.

Accepted shape (check_shape): translations/vv1/ .. vv5/<name>.tsv, <name> a language code optionally followed by
"-<credit slug>" ("-2" ...), at most MAX_BYTES, UTF-8.  Anything else under translations/ is refused (README.md
and manifest.json are the maintainers' and the workflow's own, never a contributor's).
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPTS))
import validate_translation as validator  # noqa: E402
import virustotal_scan as vt_scan  # noqa: E402
import vv_translation_format as fmt  # noqa: E402
import vv_translations as vtr  # noqa: E402

MAX_BYTES = 2 * 1024 * 1024
FOLDER = "translations"
MANIFEST = f"{FOLDER}/manifest.json"
NAME_RE = re.compile(r"^translations/vv([1-5])/([a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*(?:-[a-z0-9-]+)?)\.tsv$")
MAINTAINER_FILES = {f"{FOLDER}/README.md", MANIFEST}


def game_of(relative: str) -> int | None:
    match = NAME_RE.match(relative)
    return int(match.group(1)) if match else None


def check_shape(relative: str, data: bytes | None) -> list[str]:
    """Why a submitted file is refused before anything reads it ([] = its shape is accepted)."""
    relative = relative.replace("\\", "/")
    if relative in MAINTAINER_FILES:
        return [f"{relative} is kept by the maintainer and the workflow; a submission cannot change it"]
    if not relative.startswith(FOLDER + "/"):
        return []                                        # outside the folder: not a submission
    if not NAME_RE.match(relative):
        return [f"{relative}: only translations/vv1/ .. translations/vv5/<language code>.tsv files are accepted "
                "(for example translations/vv3/fr.tsv)"]
    if data is None:
        return []                                        # a removed file: nothing to scan
    if len(data) > MAX_BYTES:
        return [f"{relative} is larger than {MAX_BYTES // (1024 * 1024)} MB"]
    body = data[3:] if data.startswith(b"\xef\xbb\xbf") else data
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{relative} is not UTF-8 text"]
    return []


# ---- the pull request's files, as data -------------------------------------------------------------------------

def _api(path: str, token: str) -> bytes:
    if not path.startswith("/repos/"):
        raise ValueError("GitHub API path expected")
    request = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "vvfp-translation-check"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (https, fixed host)
        return response.read()


def fetch_pr(repo: str, number: int, token: str, work: Path, api=_api) -> list[dict]:
    """Every file the pull request adds or changes under translations/, written to work/files/<n>.bin (never
    under its own name: the name is data too), listed in work/files.json."""
    files = []
    page = 1
    while True:
        batch = json.loads(api(f"/repos/{repo}/pulls/{number}/files?per_page=100&page={page}", token))
        if not batch:
            break
        files += batch
        if len(batch) < 100 or page >= 30:
            break
        page += 1
    out = Path(work) / "files"
    out.mkdir(parents=True, exist_ok=True)
    listed = []
    for n, item in enumerate(files):
        name = str(item.get("filename", ""))
        if not name.startswith(FOLDER + "/"):
            continue
        entry = {"path": name, "status": str(item.get("status", "")), "local": ""}
        if entry["status"] != "removed":
            sha = str(item.get("sha", ""))
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                entry["error"] = "the file's contents could not be identified"
            else:
                blob = json.loads(api(f"/repos/{repo}/git/blobs/{sha}", token))
                size = int(blob.get("size", 0) or 0)
                if size > MAX_BYTES:
                    entry["error"] = f"larger than {MAX_BYTES // (1024 * 1024)} MB"
                else:
                    data = base64.b64decode(blob.get("content", "") or "")
                    local = out / f"{n}.bin"
                    local.write_bytes(data)
                    entry["local"] = str(local)
        listed.append(entry)
    (Path(work) / "files.json").write_text(json.dumps(listed, indent=1), encoding="utf-8")
    return listed


def _listed(work: Path) -> list[dict]:
    return json.loads((Path(work) / "files.json").read_text(encoding="utf-8"))


def _data(entry: dict) -> bytes | None:
    return Path(entry["local"]).read_bytes() if entry.get("local") else None


# ---- scan ---------------------------------------------------------------------------------------------------------

def scan(entries: list[dict], scanner=vt_scan.scan_bytes) -> tuple[bool, str, dict]:
    """(every file clean, the comment, {path: verdict dict})."""
    results, problems, verdicts = [], [], {}
    for entry in entries:
        if entry.get("status") == "removed":
            continue
        data = _data(entry)
        shape = [entry["error"]] if entry.get("error") else check_shape(entry["path"], data)
        if shape:
            problems += shape
            verdicts[entry["path"]] = {"status": "refused", "detail": "; ".join(shape)}
            continue
        if data is None:
            continue
        verdict = scanner(data, Path(entry["path"]).name)
        results.append((entry["path"], verdict))
        verdicts[entry["path"]] = verdict.as_dict()
    text = []
    if problems:
        text += ["### Refused before scanning", ""] + [f"- {validator.mask_emails(p)}" for p in problems] + [""]
    if results:
        text.append(vt_scan.markdown(results))
    if not results and not problems:
        text.append("No translation file to scan.\n")
    ok = not problems and all(v.clean for _p, v in results)
    return ok, "\n".join(text), verdicts


# ---- validate -------------------------------------------------------------------------------------------------------

def validate(entries: list[dict], work: Path) -> tuple[bool, str]:
    ok = True
    parts = ["### Translation check", ""]
    for entry in entries:
        if entry.get("status") == "removed":
            continue
        number = game_of(entry["path"])
        if number is None or not entry.get("local"):
            ok = False
            parts.append(f"- `{entry['path']}`: not a translation file")
            continue
        result = validator.check_file(Path(entry["local"]), game=vtr.TITLES[number])
        if result.tf is not None and not vtr.CODE_RE.match(result.tf.code or ""):
            result.refuse("the @code row must be a language code such as fr or pt-BR")
        if result.tf is not None and result.tf.code and not Path(entry["path"]).stem.startswith(result.tf.code):
            result.refuse(f"the file name must start with its @code ({result.tf.code})")
        result.accepted = not result.reasons
        ok = ok and result.accepted
        parts.append(validator.markdown(result, entry["path"]))
    return ok, validator.mask_emails("\n".join(parts)) + "\n"


# ---- record: the manifest on the default branch --------------------------------------------------------------------

def _last_change(relative: str, root: Path) -> str:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", relative], cwd=root, capture_output=True,
                             text=True, check=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    return out


def record(root: Path = ROOT, scanner=vt_scan.scan_bytes, now=None, last_change=_last_change) -> tuple[dict, list[str]]:
    """translations/manifest.json brought up to date: (the manifest, problems).  A file already recorded clean
    with the same SHA-256 keeps its entry; every other file is scanned and validated, and recorded only when
    both pass."""
    root = Path(root)
    path = root / MANIFEST
    try:
        old = json.loads(path.read_text(encoding="utf-8")).get("files", {})
    except (OSError, ValueError, AttributeError):
        old = {}
    stamp = (now or _dt.datetime.now(_dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    files, problems = {}, []
    for file in sorted((root / FOLDER).glob("vv[1-5]/*.tsv")):
        relative = file.relative_to(root).as_posix()
        data = file.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        shape = check_shape(relative, data)
        if shape:
            problems += shape
            continue
        number = game_of(relative)
        result = validator.check_file(file, game=vtr.TITLES[number])
        if not result.accepted or result.tf is None:
            problems.append(f"{relative}: refused by the validator: " + "; ".join(result.reasons))
            continue
        key = relative[len(FOLDER) + 1:]
        previous = old.get(key, {}) if isinstance(old, dict) else {}
        if previous.get("sha256") == sha and previous.get("verdict") == vt_scan.CLEAN:
            entry = dict(previous)
        else:
            verdict = scanner(data, file.name)
            if not verdict.clean:
                problems.append(f"{relative}: {verdict.status}: {verdict.detail} {'; '.join(verdict.engines)}".strip())
                continue
            entry = {"sha256": sha, "scanned": stamp, "verdict": vt_scan.CLEAN, "engines": verdict.engine_count}
        tf = result.tf
        entry.update({"game": f"vv{number}", "language": tf.language, "code": tf.code, "translator": tf.translator,
                      "test": vtr.is_test(tf), "changed": last_change(relative, root) or entry.get("changed", stamp)})
        files[key] = entry
    manifest = {
        "about": "Written by .github/workflows/translation-record.yml (scripts/translation_submissions.py record): "
                 "every translation file here that passed the VirusTotal scan and the validator. The patcher's "
                 "Download from GitHub... refuses any file whose SHA-256 is not listed clean.",
        "files": files,
    }
    text = json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return manifest, problems


# ---- the command line ----------------------------------------------------------------------------------------------

def _output(name: str, value: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = argv[0] if argv else ""
    work = Path(os.environ.get("WORK", "") or ".")
    if command == "fetch-pr":
        number = os.environ.get("PR_NUMBER", "")
        repo = os.environ.get("REPO", "")
        token = os.environ.get("GH_TOKEN", "")
        if not number.isdigit() or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo) or not token:
            print("PR_NUMBER, REPO and GH_TOKEN must be set", file=sys.stderr)
            return 2
        work.mkdir(parents=True, exist_ok=True)
        listed = fetch_pr(repo, int(number), token, work)
        print(f"{len(listed)} file(s) under translations/")
        return 0
    if command == "scan":
        ok, text, verdicts = scan(_listed(work))
        (work / "scan.md").write_text(text, encoding="utf-8")
        (work / "scan.json").write_text(json.dumps(verdicts, indent=1), encoding="utf-8")
        _output("scan", "clean" if ok else "refused")
        print("scan:", "clean" if ok else "refused")
        return 0 if ok else 1
    if command == "validate":
        ok, text = validate(_listed(work), work)
        (work / "validate.md").write_text(text, encoding="utf-8")
        _output("validate", "accepted" if ok else "refused")
        print("validate:", "accepted" if ok else "refused")
        return 0 if ok else 1
    if command == "record":
        manifest, problems = record(ROOT)
        work.mkdir(parents=True, exist_ok=True)
        report = [f"{len(manifest['files'])} file(s) recorded clean."] + [f"- {validator.mask_emails(p)}" for p in problems]
        (work / "record.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        print(report[0])
        for problem in problems:
            print(validator.mask_emails(problem))
        return 0
    print("usage: translation_submissions.py fetch-pr|scan|validate|record", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
