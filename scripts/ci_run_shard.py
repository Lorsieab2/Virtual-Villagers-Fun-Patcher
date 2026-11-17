"""Run one CI shard's test files, each in a pytest process of its own, and merge their JUnit reports.

    python scripts/ci_run_shard.py <shard> <shards> [junit.xml]

Why one process a file: on the GitHub Windows runners a shard's single pytest process died with exit code 139
("Windows fatal exception: access violation") in ordinary Python code -- #778 shard 4 in test_work_first, #780
shard 3 and #782 shard 3 in test_event_collection_files -- after hundreds of passing tests and never on a rerun
or locally (CI shard 3's 121 files in one process locally: 1002 passed, no crash).  Many files drive the games'
code in the unicorn emulator in-process; native state one file leaves behind (an emulator finalized by the
cyclic garbage collector in the middle of a later file is the likely one) then kills whatever runs next, the
whole shard is lost, and no JUnit report is written.  Each file in its own process ends that: a file's native
state dies with its process.

A file whose process dies of a native fault (anything but pytest's own 0 passed, 1 failed, 5 nothing collected)
is run once more, alone, as the local runner does (scripts/run_tests_parallel.py: "only failures that persist
alone count"); a second crash is a failure.  Each crash is listed in the log, and in the merged report as a
<system-out> note, so it stays visible.  A test that fails is never re-run.

The merged report has a <testsuites> root holding every file's <testsuite> (scripts/summarise_test_run.py reads
both forms); a file with no report (it crashed twice) gets a suite of its own with one error case naming it.
Exit code 0 only when every file passed.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import ci_test_shard  # noqa: E402

PYTEST_OK = (0, 5)            # passed; nothing collected
PYTEST_FAILED = 1             # a test failed: a real result, never re-run


def run_file(path: str, report: Path) -> int:
    cmd = [sys.executable, "-X", "faulthandler", "-m", "pytest", path, "-q", "-rf", "-p", "no:cacheprovider",
           "-o", "faulthandler_timeout=600", f"--junit-xml={report}"]
    sys.stdout.flush()
    return subprocess.call(cmd, cwd=REPO, env=dict(os.environ))


def crash_suite(path: str, codes: list[int]) -> ET.Element:
    suite = ET.Element("testsuite", name=path, tests="1", errors="1", failures="0", skipped="0")
    case = ET.SubElement(suite, "testcase", classname=path, name="native crash")
    err = ET.SubElement(case, "error", message=f"the test process died twice (exit codes {codes})")
    err.text = f"{path}: the pytest process died of a native fault twice (exit codes {codes})"
    return suite


def main(argv: list[str]) -> int:
    which, count = int(argv[0]), int(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else REPO / "junit.xml"
    parts = REPO / "junit-parts"
    parts.mkdir(exist_ok=True)
    files = ci_test_shard.shards(count)[which]
    root = ET.Element("testsuites")
    failed, crashed_once = [], []
    t0 = time.time()
    for k, path in enumerate(files, 1):
        report = parts / f"{k:04d}.xml"
        print(f"\n===== [{k}/{len(files)}] {path}", flush=True)
        codes = [run_file(path, report)]
        if codes[0] not in PYTEST_OK and codes[0] != PYTEST_FAILED:
            print(f"===== NATIVE CRASH (exit {codes[0]}) in {path}: running it again, alone", flush=True)
            report.unlink(missing_ok=True)
            codes.append(run_file(path, report))
            crashed_once.append(f"{path} (exit {codes[0]}, then {codes[1]})")
        last = codes[-1]
        if last not in PYTEST_OK:
            failed.append(path)
        if report.exists():
            try:
                rep = ET.parse(report).getroot()
                suites = [rep] if rep.tag == "testsuite" else list(rep.iter("testsuite"))
            except ET.ParseError:
                suites = [crash_suite(path, codes)]
        else:
            suites = [crash_suite(path, codes)] if last not in PYTEST_OK else []
        for suite in suites:
            if len(codes) > 1:
                note = ET.SubElement(suite, "system-out")
                note.text = f"{path}: crashed once (exit {codes[0]}), then exit {codes[1]} alone"
            root.append(suite)
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    print(f"\n===== shard {which}/{count}: {len(files)} files in {time.time() - t0:.0f} s; "
          f"failed: {len(failed)}: {', '.join(failed) or 'none'}; "
          f"crashed once then re-run alone: {len(crashed_once)}: {', '.join(crashed_once) or 'none'}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
