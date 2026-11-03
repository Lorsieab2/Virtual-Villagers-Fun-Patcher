"""The public translations/ folder on GitHub (the owner, 2026-11-02): its layout and file names, its README, the
VirusTotal scan every submission goes through, the pull request checks and the manifest they write, the release
leaving (TEST) files out, and the patcher's Download from GitHub....

VirusTotal and GitHub are mocked: nothing here reaches the network, and no file reaches a real Recycle Bin.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import translation_submissions as subs  # noqa: E402
import virustotal_scan as vts  # noqa: E402
import vv_translation_format as fmt  # noqa: E402
import vv_translations as tr  # noqa: E402
import vv_translations_github as gh  # noqa: E402
import vv_translations_window as w  # noqa: E402

GAME = 3
TITLE = tr.TITLES[GAME]


def make_file(path: Path, *, language="Français", code="fr", translator="Ana", game=TITLE) -> Path:
    english = ["New Game", "%s has learned %d new skills!", "Welcome to {village}", "Quit"]
    rows = [fmt.Row(fmt.make_key("menu", f"item{i}", e), e) for i, e in enumerate(english)]
    tf = fmt.template_file(rows, game, language, code, translator)
    for row, value in zip(tf.rows, ["Nouvelle partie", "%s a appris %d nouvelles compétences !",
                                    "Bienvenue à {village}", ""]):
        row.translation = value
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt.write_file(path, tf)
    return path


class Temp(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="vvfp-public-"))
        self.addCleanup(shutil.rmtree, self.temp, True)
        for name, value in (("TRANSLATIONS_DIR", self.temp / "Installed translations"),
                            ("LEGACY_DIR", self.temp / "translations")):
            patcher = mock.patch.object(tr, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)


# ---- names ---------------------------------------------------------------------------------------------------------

class NamingTests(unittest.TestCase):
    def test_the_credit_slug(self) -> None:
        self.assertEqual(tr.credit_slug("Zoë B."), "zoe-b")
        self.assertEqual(tr.credit_slug("  Ana_Maria 2 "), "ana-maria-2")
        self.assertEqual(tr.credit_slug("小明"), "translator")
        self.assertEqual(tr.credit_slug("(TEST) - French AI Translation"), "test-french-ai-translation")

    def test_a_new_language_is_its_code(self) -> None:
        self.assertEqual(tr.public_name("fr", "Ana", {}), "fr.tsv")
        self.assertEqual(tr.public_name("pt-BR", "Ana", {"fr.tsv": "Ana"}), "pt-BR.tsv")

    def test_nobodys_file_is_overwritten(self) -> None:
        existing = {"fr.tsv": "Ana"}
        self.assertEqual(tr.public_name("fr", "Zoë B.", existing), "fr-zoe-b.tsv")
        existing["fr-zoe-b.tsv"] = "Zoe B"                 # another person with the same slug
        self.assertEqual(tr.public_name("fr", "Zoë B.", existing), "fr-zoe-b-2.tsv")
        existing["fr-zoe-b-2.tsv"] = "ZOE b?"
        self.assertEqual(tr.public_name("fr", "Zoë B.", existing), "fr-zoe-b-3.tsv")

    def test_the_same_translator_updates_their_own_file(self) -> None:
        existing = {"fr.tsv": "Ana", "fr-zoe-b.tsv": "Zoë B."}
        self.assertEqual(tr.public_name("fr", "ana", existing), "fr.tsv")
        self.assertEqual(tr.public_name("fr", "Zoë B.", existing), "fr-zoe-b.tsv")

    def test_a_bad_code_is_refused(self) -> None:
        for code in ("", "French", "../fr", "fr/x", "FR"):
            with self.subTest(code=code), self.assertRaises(fmt.FormatError):
                tr.public_name(code, "Ana", {})


class LocalLayoutTests(Temp):
    def test_installs_go_to_installed_translations_with_public_names(self) -> None:
        first = tr.install_file(GAME, make_file(self.temp / "a.txt", translator="Ana"))
        second = tr.install_file(GAME, make_file(self.temp / "b.txt", translator="Zoë B."))
        self.assertEqual(first, tr.game_dir(GAME) / "fr.tsv")
        self.assertEqual(second, tr.game_dir(GAME) / "fr-zoe-b.tsv")
        self.assertEqual(tr.game_dir(GAME), self.temp / "Installed translations" / "vv3")
        self.assertEqual(sorted(i.label for i in tr.installed(GAME)), ["Français, by Ana", "Français, by Zoë B."])

    def test_old_layout_and_shipped_files_are_read_and_test_files_are_not_shipped(self) -> None:
        make_file(tr.legacy_dir(GAME) / f"{TITLE} - Deutsch.txt", language="Deutsch", code="de")
        make_file(tr.shipped_dir(GAME) / "es.tsv", language="Español", code="es")
        make_file(tr.shipped_dir(GAME) / "fr.tsv", translator="(TEST) - French AI Translation")
        labels = [i.label for i in tr.installed(GAME)]
        self.assertEqual(labels, ["Deutsch, by Ana", "Español, by Ana"])
        self.assertTrue(tr.is_test_translation(tr.shipped_dir(GAME) / "fr.tsv"))


# ---- the release -----------------------------------------------------------------------------------------------------

class ReleaseTests(unittest.TestCase):
    def test_accepted_files_ship_and_test_files_never_do(self) -> None:
        import build_release
        temp = Path(tempfile.mkdtemp(prefix="vvfp-release-"))
        self.addCleanup(shutil.rmtree, temp, True)
        make_file(temp / "translations" / "vv3" / "fr.tsv")
        make_file(temp / "translations" / "vv3" / "de.tsv", language="(TEST) Deutsch", code="de")
        make_file(temp / "translations" / "vv1" / "fr.tsv", game=tr.TITLES[1],
                  translator="(TEST) - French AI Translation")
        (temp / "translations" / "README.md").write_text("x", encoding="utf-8")
        with mock.patch.object(build_release, "ROOT", temp):
            shipped, tests = build_release._public_translation_files()
        self.assertEqual(shipped, ["translations/vv3/fr.tsv"])
        self.assertEqual(sorted(tests), ["translations/vv1/fr.tsv", "translations/vv3/de.tsv"])
        with mock.patch.object(build_release, "TEST_TRANSLATION_FILES", tests):
            with self.assertRaises(RuntimeError):
                build_release._assert_no_test_translations(["src/x.py", "translations/vv1/fr.tsv"])
            build_release._assert_no_test_translations(["src/x.py", "translations/vv3/fr.tsv"])

    def test_the_real_release_lists_exclude_every_test_file(self) -> None:
        import build_release
        for relative in build_release.TEST_TRANSLATION_FILES:
            self.assertNotIn(relative, build_release.FILES)
        for relative in build_release.TRANSLATION_FILES:
            self.assertIn(relative, build_release.FILES)
            self.assertFalse(tr.is_test_translation(ROOT / relative))
        source = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn(':(exclude){relative}" for relative in TEST_TRANSLATION_FILES', source)
        self.assertIn("_assert_no_test_translations(members)", source)


# ---- the README --------------------------------------------------------------------------------------------------------

class ReadmeTests(unittest.TestCase):
    def test_the_readme(self) -> None:
        text = (ROOT / "translations" / "README.md").read_text(encoding="utf-8")
        quoted = "\n".join(line[2:] if line.startswith("> ") else line[1:] for line in text.splitlines()
                           if line.startswith(">"))
        self.assertEqual(quoted, w.SHARE_PROMPT)                      # word for word
        for words in ("Add file", "Upload files", "pull request", "Download from GitHub...", "Make a translation",
                      "VirusTotal", "Email addresses are rejected", "credit", "vv1/", "vv5/", "(TEST)",
                      "<code>-<credit>.tsv"):
            self.assertIn(words, text)


# ---- VirusTotal (mocked) -----------------------------------------------------------------------------------------------

class FakeVT:
    """VirusTotal's API v3, in memory; a fake clock that sleep() advances."""

    def __init__(self, known=None, analysis_after=1, limited=0, never_completes=False, down=False):
        self.known = dict(known or {})
        self.analysis_after = analysis_after
        self.limited = limited
        self.never = never_completes
        self.down = down
        self.now = 0.0
        self.calls: list[tuple[str, str, float]] = []
        self.polls = 0
        self.keys: set[str] = set()

    def sleep(self, seconds):
        self.now += seconds

    def clock(self):
        return self.now

    def request(self, method, url, headers, body):
        self.keys.add(headers.get("x-apikey"))
        self.calls.append((method, url, self.now))
        if self.down:
            raise OSError("unreachable")
        if self.limited:
            self.limited -= 1
            return vts._Answer(429, b"{}")
        path = url[len(vts.API):]
        if method == "GET" and path.startswith("/files/"):
            sha = path.split("/")[2]
            if sha in self.known:
                return vts._Answer(200, json.dumps({"data": {"attributes": self.known[sha]}}).encode())
            return vts._Answer(404, b"{}")
        if method == "POST" and path == "/files":
            return vts._Answer(200, json.dumps({"data": {"id": "abc123"}}).encode())
        if method == "GET" and path == "/analyses/abc123":
            self.polls += 1
            done = not self.never and self.polls >= self.analysis_after
            attributes = {"status": "completed" if done else "queued",
                          "stats": {"malicious": 0, "suspicious": 0, "undetected": 60, "harmless": 5},
                          "results": {"EngineA": {"category": "undetected", "result": None}}}
            return vts._Answer(200, json.dumps({"data": {"attributes": attributes}}).encode())
        return vts._Answer(500, b"")

    def client(self, key="secret-key"):
        return vts.Client(key, request=self.request, sleep=self.sleep, clock=self.clock)


CLEAN_STATS = {"last_analysis_stats": {"malicious": 0, "suspicious": 0, "undetected": 70},
               "last_analysis_results": {"EngineA": {"category": "undetected", "result": None}}}
FLAGGED_STATS = {"last_analysis_stats": {"malicious": 1, "suspicious": 1, "undetected": 68},
                 "last_analysis_results": {"EngineA": {"category": "malicious", "result": "Trojan.X"},
                                           "EngineB": {"category": "suspicious", "result": "Heur"},
                                           "EngineC": {"category": "undetected", "result": None}}}
DATA = b"Key\tEnglish\tTranslation\r\n"
SHA = hashlib.sha256(DATA).hexdigest()


class VirusTotalTests(unittest.TestCase):
    def test_clean(self) -> None:
        fake = FakeVT({SHA: CLEAN_STATS})
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=fake.client())
        self.assertEqual(verdict.status, vts.CLEAN)
        self.assertEqual(verdict.engine_count, 70)
        self.assertEqual([c[0] for c in fake.calls], ["GET"])

    def test_flagged_names_the_engines(self) -> None:
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=FakeVT({SHA: FLAGGED_STATS}).client())
        self.assertEqual(verdict.status, vts.FLAGGED)
        self.assertEqual(verdict.engines, ["EngineA: malicious (Trojan.X)", "EngineB: suspicious (Heur)"])
        comment = vts.markdown([("fr.tsv", verdict)])
        self.assertIn("FLAGGED", comment)
        self.assertIn("EngineA", comment)

    def test_unknown_is_uploaded_and_polled(self) -> None:
        fake = FakeVT(analysis_after=3)
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=fake.client())
        self.assertEqual(verdict.status, vts.CLEAN)
        self.assertEqual([(m, u[len(vts.API):]) for m, u, _t in fake.calls],
                         [("GET", f"/files/{SHA}"), ("POST", "/files")] + [("GET", "/analyses/abc123")] * 3)
        times = [t for _m, _u, t in fake.calls]
        self.assertTrue(all(b - a >= vts.MIN_INTERVAL for a, b in zip(times, times[1:])))   # 4 a minute

    def test_a_timeout_is_not_scanned(self) -> None:
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=FakeVT(never_completes=True).client(), poll_timeout=120)
        self.assertEqual(verdict.status, vts.NOT_SCANNED)
        self.assertFalse(verdict.clean)
        self.assertIn("did not finish in time", verdict.detail)

    def test_a_missing_key_is_not_scanned(self) -> None:
        with mock.patch.dict(os.environ, {vts.KEY_ENV: ""}):
            verdict = vts.scan_bytes(DATA, "fr.tsv")
        self.assertEqual(verdict.status, vts.NOT_SCANNED)
        self.assertIn("VT_API_KEY", verdict.detail)
        self.assertFalse(verdict.clean)

    def test_unreachable_is_not_scanned(self) -> None:
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=FakeVT(down=True).client())
        self.assertEqual(verdict.status, vts.NOT_SCANNED)

    def test_the_rate_limit_backs_off_and_retries(self) -> None:
        fake = FakeVT({SHA: CLEAN_STATS}, limited=2)
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=fake.client())
        self.assertEqual(verdict.status, vts.CLEAN)
        times = [t for _m, _u, t in fake.calls]
        self.assertEqual(len(times), 3)
        self.assertGreater(times[2] - times[1], times[1] - times[0] - 0.01)    # waits longer each time
        self.assertGreaterEqual(times[1] - times[0], vts.MIN_INTERVAL)

    def test_a_limit_that_never_clears_is_not_scanned(self) -> None:
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=FakeVT(limited=10 ** 6).client(), poll_timeout=300)
        self.assertEqual(verdict.status, vts.NOT_SCANNED)

    def test_the_key_is_never_in_a_message(self) -> None:
        fake = FakeVT(never_completes=True)
        client = fake.client("TOP-SECRET-KEY")
        verdict = vts.scan_bytes(DATA, "fr.tsv", client=client, poll_timeout=60)
        self.assertEqual(fake.keys, {"TOP-SECRET-KEY"})                          # only in the header
        self.assertNotIn("TOP-SECRET-KEY", repr(client) + json.dumps(verdict.as_dict())
                         + vts.markdown([("x", verdict)]))
        source = (ROOT / "scripts" / "virustotal_scan.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"print\([^)]*_key")


class ShapeTests(unittest.TestCase):
    def test_too_big_and_wrong_types_are_refused(self) -> None:
        good = "translations/vv3/fr.tsv"
        self.assertEqual(subs.check_shape(good, DATA), [])
        self.assertEqual(subs.check_shape("translations/vv3/fr-zoe-b.tsv", DATA), [])
        self.assertIn("larger than 2 MB", subs.check_shape(good, b"x" * (2 * 1024 * 1024 + 1))[0])
        self.assertIn("not UTF-8", subs.check_shape(good, b"\xff\xfe\x00bad\xc0")[0])
        for path in ("translations/vv3/fr.txt", "translations/vv3/fr.exe", "translations/vv6/fr.tsv",
                     "translations/fr.tsv", "translations/vv3/sub/fr.tsv", "translations/vv3/French.tsv",
                     "translations/manifest.json", "translations/README.md"):
            with self.subTest(path=path):
                self.assertTrue(subs.check_shape(path, DATA))

    def test_scan_refuses_the_shape_before_virustotal(self) -> None:
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp, True)
        (temp / "a.bin").write_bytes(DATA)
        seen = []
        ok, text, verdicts = subs.scan([{"path": "translations/vv3/fr.exe", "status": "added",
                                         "local": str(temp / "a.bin")}],
                                       scanner=lambda data, name: seen.append(name))
        self.assertFalse(ok)
        self.assertEqual(seen, [])
        self.assertIn("Refused before scanning", text)


# ---- the Action's scripts, run as the workflow runs them ----------------------------------------------------------------

class ActionScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="vvfp-action-"))
        self.addCleanup(shutil.rmtree, self.work, True)
        good = make_file(self.work / "files" / "0.bin")
        (self.work / "files.json").write_text(json.dumps([
            {"path": "translations/vv3/fr.tsv", "status": "added", "local": str(good)}]), encoding="utf-8")

    def run_script(self, command: str, **env):
        environment = {k: v for k, v in os.environ.items() if k != "VT_API_KEY"}
        environment.update(WORK=str(self.work), **env)
        return subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "translation_submissions.py"), command],
                              env=environment, capture_output=True, text=True, timeout=120)

    def test_the_validator_step_accepts_a_good_file(self) -> None:
        done = self.run_script("validate")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("passed the checks", (self.work / "validate.md").read_text(encoding="utf-8"))

    def test_the_validator_step_refuses_an_email(self) -> None:
        path = Path(json.loads((self.work / "files.json").read_text())[0]["local"])
        path.write_bytes(path.read_bytes().replace("Nouvelle partie".encode(), b"ecris-moi a.b@example.com"))
        done = self.run_script("validate")
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("a.b@example.com", (self.work / "validate.md").read_text(encoding="utf-8"))

    def test_the_scan_step_without_a_key_fails_as_not_scanned(self) -> None:
        done = self.run_script("scan")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        report = (self.work / "scan.md").read_text(encoding="utf-8")
        self.assertIn("NOT SCANNED", report)
        self.assertIn("VT_API_KEY", report)

    def test_a_file_named_for_another_code_is_refused(self) -> None:
        entries = json.loads((self.work / "files.json").read_text())
        entries[0]["path"] = "translations/vv3/de.tsv"
        ok, _text = subs.validate(entries, self.work)
        self.assertFalse(ok)


class RecordTests(unittest.TestCase):
    def test_the_manifest_lists_only_clean_valid_files(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="vvfp-record-"))
        self.addCleanup(shutil.rmtree, root, True)
        make_file(root / "translations" / "vv3" / "fr.tsv")
        bad = make_file(root / "translations" / "vv3" / "de.tsv", language="Deutsch", code="de")
        bad_sha = hashlib.sha256(bad.read_bytes()).hexdigest()
        make_file(root / "translations" / "vv1" / "fr.tsv", game=tr.TITLES[1],
                  translator="(TEST) - French AI Translation")

        def scanner(data, name):
            sha = hashlib.sha256(data).hexdigest()
            status = vts.FLAGGED if sha == bad_sha else vts.CLEAN
            return vts.Verdict(status, sha, ["EngineA: malicious (X)"] if status == vts.FLAGGED else [], "", 70)

        now = dt.datetime(2026, 11, 2, 12, 0, tzinfo=dt.timezone.utc)
        manifest, problems = subs.record(root, scanner=scanner, now=now, last_change=lambda r, root: "")
        self.assertEqual(sorted(manifest["files"]), ["vv1/fr.tsv", "vv3/fr.tsv"])
        entry = manifest["files"]["vv3/fr.tsv"]
        self.assertEqual(entry["verdict"], "clean")
        self.assertEqual(entry["scanned"], "2026-11-02T12:00:00Z")
        self.assertEqual(entry["sha256"], hashlib.sha256((root / "translations/vv3/fr.tsv").read_bytes()).hexdigest())
        self.assertTrue(manifest["files"]["vv1/fr.tsv"]["test"])
        self.assertTrue(any("flagged" in p for p in problems))
        written = json.loads((root / "translations" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(written["files"], manifest["files"])
        # Unchanged files are not scanned again.
        calls = []
        subs.record(root, scanner=lambda d, n: calls.append(n) or scanner(d, n), now=now,
                    last_change=lambda r, root: "")
        self.assertEqual(calls, ["de.tsv"])


class WorkflowTests(unittest.TestCase):
    def test_the_pull_request_workflow_never_runs_the_pull_requests_code(self) -> None:
        text = (ROOT / ".github" / "workflows" / "translation-pr.yml").read_text(encoding="utf-8")
        body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        self.assertIn("pull_request_target", body)
        self.assertNotIn("pull_request.head", body)
        self.assertNotIn("github.head_ref", body)
        for ref in re.findall(r"ref: (.+)", body):
            self.assertIn(ref.strip(), ("${{ github.event.pull_request.base.sha }}",
                                        "${{ github.event.pull_request.base.ref }}"))
        for run in re.findall(r"run: (.*)", body):
            self.assertNotIn("${{", run)
        permissions = set(re.findall(r"^\s+(\w[\w-]*): write$", body, re.M))
        self.assertTrue(permissions <= {"contents", "pull-requests", "issues"}, permissions)
        self.assertIn("needs: scan", body)
        self.assertIn("VT_API_KEY: ${{ secrets.VT_API_KEY }}", body)
        for name in ("translation-record.yml", "accept-translation.yml"):
            other = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn("VT_API_KEY: ${{ secrets.VT_API_KEY }}", other)
            self.assertTrue(set(re.findall(r"^\s+(\w[\w-]*): write$", other, re.M))
                            <= {"contents", "pull-requests", "issues"})


# ---- Download from GitHub... (GitHub mocked) -----------------------------------------------------------------------------

def remote_bytes(**kwargs) -> bytes:
    temp = Path(tempfile.mkdtemp())
    try:
        return make_file(temp / "f.tsv", **kwargs).read_bytes()
    finally:
        shutil.rmtree(temp, True)


class FakeGitHub:
    def __init__(self, files: dict[str, bytes], manifest: dict | None = None, changed=None, offline=False,
                 limited=False):
        self.files = files
        self.changed = changed or {}
        self.offline = offline
        self.limited = limited
        self.urls: list[str] = []
        self.manifest = manifest if manifest is not None else {
            f"vv3/{name}": {"sha256": hashlib.sha256(data).hexdigest(), "verdict": "clean",
                            "language": fmt.parse(fmt.decode_bytes(data)).language,
                            "code": fmt.parse(fmt.decode_bytes(data)).code,
                            "translator": fmt.parse(fmt.decode_bytes(data)).translator,
                            "changed": "2026-11-01T10:00:00Z"} for name, data in files.items()}

    def get(self, url):
        self.urls.append(url)
        assert url.startswith("https://"), url
        if self.offline:
            raise gh.RemoteError("GitHub could not be reached (no network connection?): offline")
        if self.limited:
            return 403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1800000000"}, b"{}"
        headers = {"X-RateLimit-Remaining": "50"}
        base = f"{gh.API}/repos/{gh.REPO}"
        if url == f"{base}/contents/translations/manifest.json":
            content = base64.b64encode(json.dumps({"files": self.manifest}).encode()).decode()
            return 200, headers, json.dumps({"content": content}).encode()
        if url == f"{base}/contents/translations/vv3":
            return 200, headers, json.dumps([
                {"type": "file", "name": n, "size": len(d),
                 "download_url": f"https://raw.githubusercontent.com/{gh.REPO}/main/translations/vv3/{n}"}
                for n, d in self.files.items()]).encode()
        if url.startswith(f"{base}/commits?"):
            name = url.split("translations%2Fvv3%2F")[1].split("&")[0]
            date = self.changed.get(name, "2026-11-01T10:00:00Z")
            return 200, headers, json.dumps([{"commit": {"committer": {"date": date}}}]).encode()
        if url.startswith("https://raw.githubusercontent.com/"):
            return 200, {}, self.files[url.rsplit("/", 1)[1]]
        return 404, {}, b""


class DownloadTests(Temp):
    def setUp(self) -> None:
        super().setUp()
        self.fr = remote_bytes()
        self.fr2 = remote_bytes(translator="Zoë B.")
        self.de = remote_bytes(language="Deutsch", code="de", translator="Kai")

    def client(self, **kwargs) -> gh.Client:
        self.fake = FakeGitHub({"fr.tsv": self.fr, "fr-zoe-b.tsv": self.fr2, "de.tsv": self.de}, **kwargs)
        return gh.Client(get=self.fake.get)

    def test_the_list_shows_every_variant_with_its_credit_and_date(self) -> None:
        remotes = self.client(changed={"de.tsv": "2026-10-30T08:00:00Z"}).list_game(GAME)
        self.assertEqual([(r.language, r.translator, r.name) for r in remotes],
                         [("Deutsch", "Kai", "de.tsv"), ("Français", "Ana", "fr.tsv"),
                          ("Français", "Zoë B.", "fr-zoe-b.tsv")])
        self.assertEqual(remotes[0].changed_text, "2026-10-30")
        self.assertEqual({r.status for r in remotes}, {""})

    def test_files_not_scanned_clean_are_never_listed(self) -> None:
        client = self.client()
        self.fake.manifest["vv3/de.tsv"]["verdict"] = "flagged"
        del self.fake.manifest["vv3/fr-zoe-b.tsv"]
        self.assertEqual([r.name for r in client.list_game(GAME)], ["fr.tsv"])

    def test_the_update_marker(self) -> None:
        installed = tr.install_file(GAME, make_file(self.temp / "old.tsv"))        # Ana's fr, older text
        installed.write_bytes(installed.read_bytes().replace("Bienvenue".encode(), b"Salut"))
        old = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp()
        os.utime(installed, (old, old))
        tr.install_file(GAME, make_file(self.temp / "de.tsv", language="Deutsch", code="de", translator="Kai"))
        (tr.game_dir(GAME) / "de.tsv").write_bytes(self.de)                    # the same bytes as GitHub's
        remotes = {r.name: r for r in self.client().list_game(GAME)}
        self.assertNotEqual(installed.read_bytes(), self.fr)
        self.assertEqual(remotes["de.tsv"].status, gh.INSTALLED)
        self.assertEqual(remotes["fr-zoe-b.tsv"].status, "")
        # GitHub's fr changed after the installed one and differs: an update.
        self.assertEqual(remotes["fr.tsv"].status, gh.UPDATE)
        # The installed copy is newer than GitHub's: different, not an update.
        os.utime(installed, None)
        remotes = {r.name: r for r in self.client().list_game(GAME)}
        self.assertEqual(remotes["fr.tsv"].status, gh.DIFFERENT)

    def test_a_download_whose_hash_differs_is_refused(self) -> None:
        client = self.client()
        remotes = client.list_game(GAME)
        self.fake.files["fr.tsv"] = self.fr.replace("Nouvelle".encode(), b"Neuve")
        done, problems = w.download_selected(GAME, client, [r for r in remotes if r.name == "fr.tsv"])
        self.assertEqual(done, [])
        self.assertIn("not the file that was scanned", problems[0])
        self.assertEqual(tr.installed(GAME), [])

    def test_a_bad_file_is_refused_as_data(self) -> None:
        client = self.client()
        bad = remote_bytes().replace("Nouvelle partie".encode(), b"a.b@example.com")
        self.fake.files["fr.tsv"] = bad
        self.fake.manifest["vv3/fr.tsv"]["sha256"] = hashlib.sha256(bad).hexdigest()
        remotes = client.list_game(GAME)
        done, problems = w.download_selected(GAME, client, [r for r in remotes if r.name == "fr.tsv"])
        self.assertEqual(done, [])
        self.assertIn("refused", problems[0])

    def test_no_network_and_the_rate_limit_are_plain_sentences(self) -> None:
        with self.assertRaises(gh.RemoteError) as caught:
            self.client(offline=True).list_game(GAME)
        self.assertIn("no network", str(caught.exception))
        with self.assertRaises(gh.RemoteError) as caught:
            self.client(limited=True).list_game(GAME)
        self.assertIn("limit", str(caught.exception))

    def test_only_https_is_used(self) -> None:
        with self.assertRaises(gh.RemoteError):
            gh._https_get("http://api.github.com/x")
        self.client().list_game(GAME)
        self.assertTrue(all(u.startswith("https://") for u in self.fake.urls))


class DownloadDialogTests(DownloadTests):
    def setUp(self) -> None:
        super().setUp()
        from test_translations_window import _tk_root, fake_app
        self.root = _tk_root()
        if self.root is None:
            self.skipTest("no Tk display")
        self.addCleanup(self.root.destroy)
        patched = self.temp / "games" / f"{TITLE} - Modded"
        (patched / tr.PATCHER_FILES).mkdir(parents=True)
        self.app = fake_app(self.root, patched)
        for patch in (mock.patch.object(w, "_win_api", side_effect=OSError("no drag and drop in tests")),
                      mock.patch.object(w.messagebox, "showinfo"), mock.patch.object(w.messagebox, "showerror")):
            patch.start()
            self.addCleanup(patch.stop)

    def test_multi_select_download_installs_each_chosen_file(self) -> None:
        window = w.open_translations(self.app, self.app.builds[GAME - 1]).translations
        dialog = window.download_dialog(self.client())
        self.assertEqual(str(dialog.tree.cget("selectmode")), "extended")
        self.assertEqual([row[:2] for row in dialog.rows()],
                         [("Deutsch", "Kai"), ("Français", "Ana"), ("Français", "Zoë B.")])
        dialog.tree.selection_set(["1", "2"])                            # both French variants
        done, problems = dialog.download()
        self.assertEqual(problems, [])
        self.assertEqual(sorted(p.name for p in done), ["fr-zoe-b.tsv", "fr.tsv"])
        self.assertEqual((tr.game_dir(GAME) / "fr.tsv").read_bytes(), self.fr)
        self.assertEqual((tr.game_dir(GAME) / "fr-zoe-b.tsv").read_bytes(), self.fr2)
        self.assertEqual([row[3] for row in dialog.rows()], ["", gh.INSTALLED, gh.INSTALLED])
        self.assertIn("Français, by Zoë B.", window.language_labels())
        dialog.select_all()
        self.assertEqual(len(dialog.selected()), 3)
        dialog.close()
        window.close()

    def test_the_dialog_says_when_github_cannot_be_read(self) -> None:
        window = w.open_translations(self.app, self.app.builds[GAME - 1]).translations
        dialog = window.download_dialog(self.client(offline=True))
        self.assertEqual(dialog.rows(), [])
        self.assertIn("no network", dialog.status_var.get())
        dialog.close()
        window.close()


if __name__ == "__main__":
    unittest.main()
