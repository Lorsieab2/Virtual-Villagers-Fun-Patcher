"""Run the whole test suite in parallel: one pytest process per test file, several at a time.

The owner (2026-10-23): "please do things in parallel more often" -- the full suite run one test after another
took nearly five hours; split over 12 workers it takes about a quarter of an hour.

    python scripts/run_tests_parallel.py [out dir] [workers]

Every file runs with --release, the source folder on PYTHONPATH (some files import the patcher without adding
it themselves) and its own short --basetemp (deep temp paths pass the 260-character limit).  Every file that
fails is then run again on its own, and only the files that still fail alone are reported as failing.  The
summary is printed and written to <out dir>/summary.txt.  inputs/ and research/stock-executables/ must be in
place, or the tests that need the stock games skip.
"""
import concurrent.futures as cf
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUMMARY = re.compile(r"(\d+) (passed|failed|skipped|error|errors)")


def run(test: Path, tag: str, out: Path, short: Path) -> tuple[str, int, dict, float]:
    log = out / f"{tag}_{test.stem}.log"
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    start = time.time()
    with log.open("w", encoding="utf-8", errors="replace") as fh:
        rc = subprocess.call([sys.executable, "-m", "pytest", "-q", "--release", "-p", "no:cacheprovider",
                              f"--basetemp={short / f'{tag}_{test.stem}'}", str(test.relative_to(REPO))],
                             cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT)
    tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-1:] or [""]
    return test.name, rc, {k: int(n) for n, k in SUMMARY.findall(tail[0])}, time.time() - start


def total(results: list) -> dict:
    counts: dict = {}
    for _, _, found, _ in results:
        for key, value in found.items():
            counts[key] = counts.get(key, 0) + value
    return counts


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "vvfp-parallel-tests"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    short = Path(tempfile.gettempdir()) / "vvp"
    out.mkdir(parents=True, exist_ok=True)
    files = sorted((REPO / "tests").glob("test_*.py"), key=lambda p: p.stat().st_size, reverse=True)
    began = time.time()
    with cf.ThreadPoolExecutor(workers) as pool:
        first = list(pool.map(lambda f: run(f, "par", out, short), files))
    failed = [name for name, rc, _, _ in first if rc not in (0, 5)]          # 5: no tests collected
    again = [run(REPO / "tests" / name, "solo", out, short) for name in failed]
    still = [name for name, rc, _, _ in again if rc not in (0, 5)]
    lines = [f"files: {len(files)}  workers: {workers}  wall: {time.time() - began:.0f} s",
             f"parallel totals: {total(first)}",
             f"failed in parallel: {len(failed)}: {', '.join(failed) or 'none'}",
             f"run again alone: {total(again)}",
             f"STILL FAILING ALONE: {len(still)}: {', '.join(still) or 'none'}"]
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 1 if still else 0


if __name__ == "__main__":
    raise SystemExit(main())
