"""Open an exact executable read-only and inspect selected file offsets."""

from __future__ import annotations

import argparse
import runpy
import sys

import idapro


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_exe")
    parser.add_argument("output_json")
    parser.add_argument("file_offsets", nargs="+")
    parser.add_argument(
        "--inspector",
        default="scripts/ida_inspect_offsets.py",
    )
    args = parser.parse_args()

    result = idapro.open_database(args.input_exe, True)
    if result != 0:
        raise RuntimeError(f"IDA open_database failed with code {result}")
    try:
        sys.argv = [args.inspector, args.output_json, *args.file_offsets]
        runpy.run_path(args.inspector, run_name="__main__")
    finally:
        idapro.close_database(False)


if __name__ == "__main__":
    main()
