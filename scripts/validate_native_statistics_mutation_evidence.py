"""Validate the disabled VV3-VV5 native statistics mutation evidence gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from native_statistics_mutation_evidence import validate_contract_file  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "evidence_json",
        nargs="?",
        type=Path,
        default=ROOT / "data" / "native_statistics_mutation_evidence.json",
    )
    args = parser.parse_args(argv)
    result = validate_contract_file(args.evidence_json)
    print(json.dumps(result.as_dict(), indent=2))
    # The checked-in artifact is intentionally incomplete and disabled.  A
    # non-zero result prevents it from being mistaken for a native GO.
    return 0 if result.publication_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())

