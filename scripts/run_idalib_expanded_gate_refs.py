"""Run the expanded-population reference exporter through IDA's Python library.

The installed ``idapro`` package initializes IDA, this wrapper opens the exact
input executable with auto-analysis enabled, and the exporter writes a JSON
ledger.  The database is closed without saving so the input and any adjacent
IDA database remain untouched.
"""

from __future__ import annotations

import argparse
import runpy
import sys

import idapro


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_exe")
    parser.add_argument("game_id", choices=("vv3", "vv4", "vv5"))
    parser.add_argument("output_json")
    parser.add_argument(
        "--exporter",
        default="scripts/ida_export_expanded_gate_refs.py",
    )
    args = parser.parse_args()

    result = idapro.open_database(args.input_exe, True)
    if result != 0:
        raise RuntimeError(f"IDA open_database failed with code {result}")
    try:
        sys.argv = [args.exporter, args.game_id, args.output_json]
        runpy.run_path(args.exporter, run_name="__main__")
    finally:
        idapro.close_database(False)


if __name__ == "__main__":
    main()
