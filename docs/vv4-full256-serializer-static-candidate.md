# VV4 full-256 serializer static candidate

Status: **STOP, disabled, hidden, and non-emitting**.

This model accepts only the exact bare Expanded VV4 parent of size `0xE3000` and SHA-256 `3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1`. Full Mastery, Full Heal, fullscreen, and Running compositions are rejected until their exact final layouts are authenticated.

The proposed `.vv4x` section occupies raw `0xE3000..0xE4000`, RVA `0x471000`, VA `0x871000`, using the unused section header at raw `0x2C0`. Proposed full-entry hooks are `0x660A0: 5355565733 -> E95BAF4000` and `0x66110: 5356578D79 -> E9EBAF4000`, targeting `0x871000` and `0x871100`.

The algorithm model requires register preservation, `ret 4`, singleton `0x41FE70 + 0xC868`, AL=0 on a null singleton, exactly one zero terminator byte only below 256 records, and a reader that clears all 256 live records before resetting the load index and succeeds on exactly 256 unterminated records without touching the tail at body offset `0x1CC60`.

D353 pins the exact ranges, hashes, and ABIs for `0x45EAA0`, `0x41FE70`, `0x45DB30`, `0x45D8A0`, and `0x45DBE0`; the model records complete serializer and deserializer instruction algorithms around those calls. Native output nevertheless remains false because safe AL-failure propagation through every caller is not proved, and the section-header preimage plus final assembled wrapper/checksum bytes are not repository-authenticated. The builder therefore supports validation-only `--dry-run`; it cannot write an executable.

D354/D355 add the stock writer entry guard `0x4039B0: 81EC04020000` and model a complete-entry `E9 rel32 + 90` replacement in the same `.vv4x` page. Its atomic contract requires a sibling `CREATE_NEW | WRITE_THROUGH` temporary file, checked exact writes, flush and checked close of both handles, no-follow reopen, reparse rejection, volume/FileId identity, exact `GetFileSizeEx == 24 + body`, and complete header/body comparison. An existing final uses `ReplaceFileA(final,temp,backup,0,NULL,NULL)`; an absent final uses `MoveFileExA` with write-through and no replace-existing, treating a raced-in final as untouched/fatal. Cleanup is limited to the identity-owned temp. Directory-entry power-loss durability remains unsupported and unproved. Six writer caller addresses are pinned, but their failure handling is still STOP. The writer target, jump bytes, dynamic resolver, and composed page bytes remain null.

```powershell
python scripts/build_vv4_full256_serializer_candidate.py --dry-run
python -m unittest tests.test_vv4_full256_serializer_candidate
```

The VV4 13-row and VV5 66-row relocation ledgers are bound but unchanged and provide no save-safety proof. Runtime, player, and publication gates remain false.
