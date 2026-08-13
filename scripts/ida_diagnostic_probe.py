"""Report read-only IDA database status for a disposable analysis copy.

Run with IDA's ``-A -S`` options.  The probe emits one machine-readable line
to stdout and never resolves addresses, inspects instructions, infers ABIs,
or writes an export artifact.  Use only against a disposable database copy.
"""

from __future__ import annotations

import json

import ida_auto
import ida_funcs
import ida_kernwin
import ida_nalt
import idc


def _emit(payload: dict[str, object]) -> None:
    print("VVFP_IDA_DIAGNOSTIC " + json.dumps(payload, sort_keys=True))


def main() -> None:
    try:
        ida_auto.auto_wait()
        _emit(
            {
                "status": "OPEN",
                "ida_version": ida_kernwin.get_kernel_version(),
                "input_path": ida_nalt.get_input_file_path(),
                "database_path": idc.get_idb_path(),
                "function_count": ida_funcs.get_func_qty(),
            }
        )
    except Exception as exc:
        _emit(
            {
                "status": "STOP",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        idc.qexit(1)
        return
    idc.qexit(0)


main()
