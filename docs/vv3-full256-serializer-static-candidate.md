# VV3 full-256 serializer/reader repair

This source-bound candidate repairs the static VV3 Expanded-256 serializer and reader while remaining disabled. It does not implement an atomic writer, whole-load rollback, runtime verification, player verification, catalog publication, or native output.

## Exact bindings

- Stock EXE SHA-256: `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503`.
- Expanded manifest: `data/expanded_256.json`, exactly 1,263 rows, canonical row digest `04B93127BC4D5C6787AB013DE9205813D44947DBC16A370DBC234C06588AC3FB`.
- Immediate parent: `657D321B2F1E9E6D6C223DB1FF0BBA38C2D761A97A6E7F21B98CE1826531A848`.
- Progression parent: `3A35745C00102A0964DF6E81B77707539C5BDC03501011F43FF1D2809015B211`.

Both parents are `0xCC000` bytes with six sections and `SizeOfImage=0x3B9000`. The repair adds one RX section named `.vv3sv` at raw `0xCC000`, RVA `0x3B9000`, VA `0x7B9000`, and extends the file to `0xCD000`. The exact 40-byte section header is:

`2E767633737600000010000000903B000010000000C00C0000000000000000000000000020000060`

The renderer requires a zero section-header slot at raw `0x2F0`, changes the section count at raw `0x10E` from `0600` to `0700`, changes `SizeOfImage` at raw `0x158` from `00903B00` to `00A03B00`, and recomputes the PE checksum after every other byte is final.

## Exact repair

The `.vv3sv` page is 4,096 bytes with SHA-256 `9F82D59D1436B17ACA69CD637AB40D44DF35323DA46600AAA5FD07315C249B64`:

- Serializer at raw `0xCC000` / VA `0x7B9000`, 121 bytes, SHA-256 `451EF9D65A9613247FAB9C8C586387F05329F9B6E6048CEE07D0B88E6BE4374E`.
- Reader at raw `0xCC200` / VA `0x7B9200`, 139 bytes, SHA-256 `C61D124EFBDADF63D3C128E4B23BB0F80AE2D07B031A53396E4BFFF032268775`.
- Serializer failure gate at raw `0xCC3C0` / VA `0x7B93C0`, 26 bytes, SHA-256 `A61E6CAE007E78F4A2ADC3173D3E3C7261E69DA1F9C031EAED441288C105A99B`.

The save call at raw `0x27D57` changes from `E824720300` to `E864163900`, targeting the failure gate. The load call at raw `0x28A4C` changes from `E80F3E0300` to `E8AF073900`, targeting the bounded reader. The serializer writes only logical records 0 through 255 and writes a terminator only below count 256. The reader accepts exactly 256 records without reading record 257 or the tail. Both wrappers preserve their nonvolatile registers and exact stack cleanup.

The exact in-memory results are:

- Immediate: SHA-256 `585EC60285F20A55658B5CB77E8A81D5B6A632B3A399058F01EB732B4777976B`, checksum bytes `27F40C00`.
- Progression: SHA-256 `3B93CFDD98112D54F4457AA4E84838F98E577DF0AF1B9C20903E1C4CC8F276A8`, checksum bytes `316F0D00`.

## Deliberate STOP boundary

The four stock writer callsites remain documented expectations only. No writer hook, dynamic resolver, wrapper bytes, import changes, or final writer hash is emitted. Whole-load snapshot and rollback hooks/bytes are also null. Accordingly, `enabled`, `catalog_visible`, `native_output`, `runtime_go`, `player_go`, and `publication_ready` remain false.

## Validation

Run:

```powershell
python scripts/build_vv3_full256_serializer_candidate.py --check
python scripts/build_vv3_full256_serializer_candidate.py --dry-run
python scripts/validate_vv3_full256_serializer_evidence.py
python -m unittest tests.test_vv3_full256_serializer_candidate tests.test_vv3_full256_serializer_evidence
```

The builder renders only in memory during validation. Passing static checks does not establish runtime or player proof.
