"""Validate a future read-only VV3 Expanded-256 IDA/reconciler evidence bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv3_expanded_256_evidence import validate_evidence_file  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_json", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_evidence_file(args.evidence_json)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error_count": 1, "errors": [str(exc)]}, indent=2))
        return 1
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
