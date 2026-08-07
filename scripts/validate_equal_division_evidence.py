"""Validate the disabled Equal Division evidence contract."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from native_absent_feature_evidence import validate_contract_file  # noqa: E402


def main() -> int:
    result = validate_contract_file(
        ROOT / "data" / "equal_division_evidence.json",
        "equal_division",
    )
    print(json.dumps(result.as_dict(), indent=2))
    return 0 if result.publication_allowed else 1


if __name__ == "__main__":
    raise SystemExit(main())
