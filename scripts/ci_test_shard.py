"""Print the test files one CI shard runs, so the suite can be split over several GitHub runners.

    python scripts/ci_test_shard.py <shard> <shards>

The owner (2026-10-23) asked for the GitHub checks to be split up and made faster.  Files are dealt out
largest first to whichever shard holds the fewest bytes so far, so the shards take about the same time;
every file lands in exactly one shard.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def shards(count: int) -> list[list[str]]:
    files = sorted((REPO / "tests").glob("test_*.py"), key=lambda p: (-p.stat().st_size, p.name))
    groups: list[list[str]] = [[] for _ in range(count)]
    sizes = [0] * count
    for path in files:
        smallest = sizes.index(min(sizes))
        groups[smallest].append(path.relative_to(REPO).as_posix())
        sizes[smallest] += path.stat().st_size
    return groups


if __name__ == "__main__":
    which, count = int(sys.argv[1]), int(sys.argv[2])
    print(" ".join(shards(count)[which]))
