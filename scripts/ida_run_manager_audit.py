"""Run the manager audit through IDA's standalone idalib Python interface."""

from __future__ import annotations

import idapro  # IDA requires this to be the first non-stdlib import.

import argparse

import ida_export_manager_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable")
    parser.add_argument("output")
    args = parser.parse_args()
    idapro.enable_console_messages(True)
    result = idapro.open_database(args.executable, True)
    if result != 0:
        raise RuntimeError(f"IDA could not open the database: error {result}")
    try:
        ida_export_manager_audit.sys.argv = [
            ida_export_manager_audit.__file__,
            args.output,
        ]
        ida_export_manager_audit.main()
    finally:
        idapro.close_database(False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
