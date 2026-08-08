# IDA 9.4 attended native-evidence runbook

This is a source-only, read-only preflight for reviewing the ten VV3-VV5
native-evidence queries. It does not launch a game, access a save, enable a
route, or create an export packet.

## Current launcher state

The installed IDA 9.4 GUI launcher is:

```text
C:\Program Files\IDA Professional 9.4\ida.exe
ProductVersion: 9.4.260610.6c3b13fe
```

The adjacent `idat.exe` is an unversioned 16,896-byte launcher in this
installation. A disposable `cmd.exe` invocation with an explicit PATH returned
exit code `2` without stdout, stderr, or a database-status line. Use the GUI
launcher for an attended review; do not treat the failed text launcher as
native evidence.

## Prepare a disposable exact-input folder

Use a self-contained folder under the declared workspace root. Copy the exact
stock executable and its adjacent `.i64` database into that folder; do not open
or modify the source copy in `research/stock-executables`. Record the executable
hash and verify it against the values in `tools/native_evidence_export.py`:

| Game | Executable | Size | SHA-256 |
| --- | --- | ---: | --- |
| VV3 | `Virtual Villagers - The Secret City.exe` | 831488 | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |
| VV4 | `Virtual Villagers - The Tree of Life.exe` | 929792 | `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` |
| VV5 | `Virtual Villagers - New Believers.exe` | 991232 | `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` |

The `.i64` hash is provenance metadata for the disposable review copy. It is
not a substitute for the executable fingerprint or for reviewed query rows.

## Open an attended session

PowerShell `Start-Process` is not suitable in this environment because its
environment construction can fail on the inherited `Path`/`PATH` collision.
Use a temporary `cmd.exe` launcher instead, replacing the two placeholders
with paths inside the disposable workspace:

```bat
@echo off
setlocal
set "PATH=C:\Program Files\IDA Professional 9.4;C:\Windows\System32;C:\Windows"
set "IDAUSR=<workspace-root>\idausr"
start "" "C:\Program Files\IDA Professional 9.4\ida.exe" "<workspace-root>\Virtual Villagers - The Secret City.exe.i64"
endlocal
```

Open one game/database at a time. Confirm the visible IDA window title and
input path identify the intended VV3, VV4, or VV5 disposable database before
reviewing anything. Close the session without saving if the executable hash,
database pairing, or input path is not exact.

## Review and export gates

The canonical query order is the ten IDs in
`data/native_evidence_queries.json`. A reviewed row must be source-derived and
contain exactly these fields:

```text
query_id, status, function_start_ea, function_end_ea, file_offset,
raw_bytes, instructions, callers, xrefs, registers, stack_cleanup,
call_convention
```

Do not fill an EA, byte string, register contract, stack cleanup, calling
convention, caller, or xref from a guess, pasted text, or a different database.
The existing `tools/ida_export_native_evidence.py` is intentionally a template:
`RESOLVED_EAS` is empty, `registers` is empty, and its stack/calling-convention
values are `REVIEW_REQUIRED` placeholders. It must remain unusable until an
attended review supplies every required source-bound value in a disposable
copy.

Only after all ten rows are complete may the existing read-only validator be
used against the exact inventory and executable bytes. It rejects partial,
reordered, synthetic, stale-byte, empty-register, and `REVIEW_REQUIRED` rows.
Until that validation succeeds, the workflow remains `STOP` with native
output, runtime, player, and publication flags false.
