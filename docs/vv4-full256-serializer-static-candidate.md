# VV4 full-256 serializer static candidate

Status: **serializer/reader static GO; atomic writer, runtime, player, and publication STOP**. The candidate remains disabled, hidden, and non-emitting.

This model accepts only the exact bare Expanded VV4 parent of size `0xE3000` and SHA-256 `3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1`. Full Mastery, Full Heal, fullscreen, and Running compositions are rejected until their exact final layouts are authenticated.

The reviewed `.vv4x` section occupies raw `0xE3000..0xE4000`, RVA `0x471000`, VA `0x871000`, using the zero section header at raw `0x2C0`. The exact zero-padded section page SHA-256 is `F33DEFF4EF943EB4371AFD3AC80F3F35BC1DB21865ADCC5F115BDF2E20A37D45`. It contains the 119-byte serializer at `0x871000`, the 102-byte reader at `0x871100`, and the 26-byte serializer failure gate at `0x871180`.

The source-bound caller repairs are `0x1F125: E8766F0400 -> E856204500` (`call 0x871180`) and `0x1FD34: E8D7630400 -> E8C7134500` (`call 0x871100`). The renderer requires the exact five-section PE32 parent, zero header slot, `SizeOfImage 0x471000`, and checksum `F6A80E00`; it installs the RX section, advances the section count and `SizeOfImage`, and only then recomputes the checksum to `4FDF0E00`. The exact in-memory candidate SHA-256 is `364E35167E4DA8D9407030E42D41306A78FB50B73C7532B2D5166729EA447C43`.

The algorithm model requires register preservation, `ret 4`, singleton `0x41FE70 + 0xC868`, AL=0 on a null singleton, exactly one zero terminator byte only below 256 records, and a reader that clears all 256 live records before resetting the load index and succeeds on exactly 256 unterminated records without touching the tail at body offset `0x1CC60`.

D353 pins the exact ranges, hashes, and ABIs for `0x45EAA0`, `0x41FE70`, `0x45DB30`, `0x45D8A0`, and `0x45DBE0`; the reviewed routines preserve the specified nonvolatile registers, cap both directions at 256, avoid a terminator write at a full 256 records, and avoid reading a 257th record. The builder supports validation and an in-memory source-bound `--dry-run`; it cannot write an executable.

D354/D355 retain the stock writer entry guard `0x4039B0: 81EC04020000` but do not hook it. Its modeled atomic contract still requires a sibling `CREATE_NEW | WRITE_THROUGH` temporary file, checked exact writes, flush and checked close of both handles, no-follow reopen, reparse rejection, volume/FileId identity, exact `GetFileSizeEx == 24 + body`, and complete header/body comparison. Six writer caller addresses are pinned, but their failure handling, writer target, jump bytes, and dynamic resolver remain null/STOP. Directory-entry power-loss durability remains unsupported and unproved.

```powershell
python scripts/build_vv4_full256_serializer_candidate.py --dry-run
python scripts/build_vv4_full256_serializer_candidate.py --dry-run --parent <exact-expanded-vv4.exe>
python -m unittest tests.test_vv4_full256_serializer_candidate
```

The VV4 13-row and VV5 66-row relocation ledgers are bound but unchanged and provide no save-safety proof. Runtime, player, and publication gates remain false.
