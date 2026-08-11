# Expanded Atomic Writer Integration

The real VV3, VV4, and VV5 Expanded-256 render paths install one guarded,
parameterized x86 save writer. Stock modes are unchanged. The writer creates a
unique same-directory sibling with `CREATE_NEW`, checks short writes, flushes
and closes it, reopens without following reparse points, verifies handle
identity, exact size, header, and complete body, then commits with
`ReplaceFileA` for an existing final or `MoveFileExA(...,
MOVEFILE_WRITE_THROUGH)` for an absent final. For a nonzero save slot,
`ReplaceFileA` receives the game's canonical `slot + 0x14` backup path; slot
zero passes no backup path. It never uses
`MOVEFILE_REPLACE_EXISTING`.

Cleanup is permitted only after the temporary handle identity has been proven;
it uses `SetFileInformationByHandle(FileDispositionInfo)`. Any uncertain
failure terminates the process and therefore cannot be ignored by the four
legacy callers. In particular, a false replacement result is treated as an
uncertain final-name state, not as proof that the prior final is unchanged. A
single interlocked lock serializes the writer in-process.

The PE edits are exact-build guarded: section headers, import directory,
original ten-descriptor import block, five new KERNEL32 imports, writer code,
four callsites, file size, checksum, parent SHA-256, and result SHA-256 are all
closed in `data/expanded_atomic_writer_integration.json`.

This is native output but not runtime, player, or publication proof. Those
gates remain false until a player completes save/reload and failure-path QA on
the emitted exact builds.
