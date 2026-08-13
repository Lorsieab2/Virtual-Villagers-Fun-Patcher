# VV3-VV5 native atomic-save publication evidence gate

This additive contract is evidence-only and permanently disabled in its checked-in state. It does not alter the catalog, emit native code, build a package, launch a game, or read or write saves.

Each game is pinned to its exact stock executable. Full-folder fingerprints, native header/body writers, slot-result and late-load-failure ABIs, and exact header/body/record/tail/padding shapes are currently unknown and therefore `null`. Null is STOP, never a wildcard.

Publication requires authenticated proof of a same-directory, exclusive `CREATE_NEW` temporary file opened with `FILE_FLAG_WRITE_THROUGH`; exact `WriteFile` counts; checked `FlushFileBuffers` and `CloseHandle`; and a no-follow reopen with `GetFileSizeEx`, identity checks and exact content validation. All identity and commit APIs must be dynamically resolved.

When the final exists, the only accepted commit is `ReplaceFileA(final,temp,backup,0,NULL,NULL)`. `REPLACEFILE_WRITE_THROUGH` is unsupported and rejected. When the final is absent, the only accepted commit is `MoveFileExA(temp,final,MOVEFILE_WRITE_THROUGH)` without `MOVEFILE_REPLACE_EXISTING`; if another final races into existence, the operation must fail. Numeric `slot + 40`, delete-then-move, and overwrite-on-race paths are rejected. The protocol must preserve the prior final on every failure and explicitly handle slot 0/current/backup outcomes and fatal non-return after late load mutation.

Windows does not provide the directory-handle flush primitive needed to prove directory-entry durability across power loss here. That limitation is explicit and must not be upgraded to a guarantee by runtime success receipts.

Stock backup rotation is not atomicity evidence. Serializer arithmetic without the native writer, filesystem protocol, failure boundaries and observed receipts is also nonqualifying. Direct `wb` truncation, ignored rotation results and ignored close results must be established from authenticated native evidence rather than assumed from this contract.

Run `python -B scripts/validate_native_atomic_save_publication_evidence.py`. The checked-in result is intentionally non-zero and reports STOP.

Integration onto C342 is additive: carry the six new files as a single unit. They have no catalog registration or dependency on generated native outputs. Resolve only path conflicts if C342 independently introduces the same contract ID; do not merge evidence rows by assumption or change any false publication flag.
