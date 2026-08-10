# VV5 guarded post-prototype overlay

This disabled overlay applies sixteen reviewed, same-width operand repairs to the exact historical VV5 Expanded-256 prototype. It is a separate post-prototype layer: the 1,951-row Expanded manifest, central stored-index gates, save geometry evidence, and C342 Origins relocation ledger are not edited or rebound.

## Exact bindings

- Stock EXE SHA-256: `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`.
- Prototype: 991,232 bytes, checksum `98F10F00`, SHA-256 `1C825CB6AC3C7E1368D3EFD9C81E844A336AB31C7EBA0971674601F25E3E8F0B`.
- Expanded manifest: exactly 1,951 rows, digest `D0E899B112C106AF136D6D2F91C68C97CF6B431DB6F5457CBD6211852BA01431`.
- C342 Origins source-text pin: `6AFF1A8E69234C61CB2D1878C46FA91B0AAA721FC5F29C5B42A678F61BAB8528`.
- C342 relocation ledger: exactly 66 rows, digest `14E460773ADC065E053FA30921ED01D33A5F36AD49DC754CCD69127EA02C01B7`.

The overlay has zero intersections with the 66 C342 relocation writes, the 15 central stored-index candidate edits, or raw range `0xDB000..0xDC000`. File size, sections, save-layout evidence, and all other bytes remain unchanged except the PE checksum.

## Exact edits

Twelve four-byte manager/tail operands are guarded at raw `0x6F830`, `0x6F84C`, `0x71D3E`, `0x71D68`, `0x71D80`, `0x71DCF`, `0x71DE6`, `0x72188`, `0x888CF`, `0x88E3F`, `0x8ACA3`, and `0x8B34D`.

The four reviewed candidate-array locators point into their instructions. Their exact guarded instruction starts are:

- reviewed `0x71EB8`, write `0x71EB6`: `81ECD8040000 -> 81EC28080000`;
- reviewed `0x71EC3`, write `0x71EC2`: `6858020000 -> 6800040000`;
- reviewed `0x7203C`, write `0x72039`: `899C8490020000 -> 899C8438040000`;
- reviewed `0x720B3`, write `0x720B0`: `8B84B490020000 -> 8B84B438040000`.

After all guarded writes, the renderer recomputes the PE checksum to `6E3B0F00`. The exact in-memory result remains 991,232 bytes and has SHA-256 `AF537A02F0E1983F22966923E736A4595B53EDC625D4C2F20414AB55FD54BBDC`.

## STOP boundary

This is static source evidence only. `enabled`, `catalog_visible`, `native_output`, `runtime_go`, `player_go`, and `publication_ready` remain false. Runtime and player receipts are empty; no package or executable is emitted.

Run:

```powershell
python scripts/build_vv5_post_prototype_overlay.py --check
python scripts/build_vv5_post_prototype_overlay.py --dry-run
python scripts/validate_vv5_post_prototype_overlay.py
python -m unittest tests.test_vv5_post_prototype_overlay tests.test_vv5_post_prototype_overlay_evidence
```
