# VV3-VV5 expanded-256 implementation gates

## Disposition

**VV3: ON HOLD. VV4: ON HOLD. VV5: ON HOLD.**

This is a planning and disassembly report. It does not authorize implementation,
enablement, packaging, or a game launch. The current manifests demonstrate a
substantial structural expansion, but none of the three exact builds has a
complete implementation-grade gate:

- VV3 became non-responsive while loading an expanded test build.
- VV4 failed to import a stock-sized village save. The four decoded absolute
  Origins references previously left stale are now owned by the exact VV4
  current-Origins relocation contract.
- VV5's current-feature relocation ledger now owns all 36 cross-section
  relative branches and seven decoded external absolute `.shr` references
  previously left outside the certified set.

Passing patch-range, hash, and PE-readback checks only proves that the declared
edits can be rendered without colliding. It does not prove that every required
reference was declared or that save/runtime behavior is correct.

## Exact supported executables

| Game | Size | SHA-256 |
|---|---:|---|
| VV3, *The Secret City* | 831,488 | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |
| VV4, *The Tree of Life* | 929,792 | `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` |
| VV5, *New Believers* | 991,232 | `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` |

Every address and byte in this report applies only to the corresponding exact
stock executable.

## Evidence method and limits

IDA Pro 9.4 decoded each exact stock executable and the stock-layout
all-current-feature renders. The exporter inventories:

- decoded absolute operands into the stock record pool, the moved data tail,
  `.shr`, and `.rsrc`;
- decoded direct relative calls and jumps crossing a moved `.shr` boundary;
- decoded immediates `149`, `150`, `151`, `255`, and `256`;
- instruction heads, operand file offsets, surrounding instructions, and
  section ownership.

Raw four-byte scans are retained only as candidate discovery. A raw pattern is
not called a pointer until its containing IDA item and operand are checked.
This distinction eliminated two false VV4 candidates whose four-byte windows
began on `E8` call opcodes.

The current manifest has 1,263 VV3 edits, 1,771 VV4 edits, and 1,951 VV5 edits.
Stock guards do not overlap. The historical prototype binaries and the
`prototype_sha256` values in `data/expanded_256.json` predate nine later
corrections per game:

| Game | Historical prototype SHA-256 | Later manifest operands absent from that prototype |
|---|---|---|
| VV3 | `6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601` | `0x28949`, `0x28961`, `0x7B3B1`, `0x60D46`, `0x60D4C`, `0x5F975`, `0x5FA46`, `0x35A5A`, `0x5EE69` |
| VV4 | `3697317341C23B107F8C06F6D4164BC4602BF5CB90DFB56A6B68EB7EA3C43EE1` | `0x1FC19`, `0x8910D`, `0x66845`, `0x66A15`, `0x66AE6`, `0x66045`, `0x66C9C`, `0x6683F`, `0x66A0F` |
| VV5 | `1C825CB6AC3C7E1368D3EFD9C81E844A336AB31C7EBA0971674601F25E3E8F0B` | `0x25709`, `0x9466C`, `0x6FA75`, `0x6F955`, `0x708FC`, `0x71D77`, `0x70280`, `0x705E5`, `0x70706` |

Those three hashes are historical evidence, not current certification
artifacts. Any Coding candidate must be regenerated from the current guarded
manifest and independently re-certified.

## Structural expansion ledger

### Live record pools

| Game | Manager | First record | Stride | Stock end after 150 | Moved-tail end | Expanded reservation |
|---|---:|---:|---:|---:|---:|---|
| VV3 | `0x59E110` | `0x59E124` | `0x1F8C` (8,076) | `0x6C5D2C` | `0x6C7518` | 256 logical records plus four zero padding records |
| VV4 | `0x50E568` | `0x50E5AC` | `0x2E3C` (11,836) | `0x6BFCD4` | `0x727344` | 256 records |
| VV5 | `0x554148` | `0x554190` | `0x2F44` (12,100) | `0x70F368` | `0x7B1DA4` | 256 records |

The extra VV3 padding is not four additional usable records. Stock selectors
with five-record unrolling can read the final logical group containing indices
255 through 259. Indices 256 through 259 must remain zero, non-saveable padding.

### Compact save tables

| Game | Compact record stride | Added records | Inserted bytes |
|---|---:|---:|---:|
| VV3 | 284 | 106 | 30,104 |
| VV4 | 260 | 106 | 27,560 |
| VV5 | 280 | 106 | 29,680 |

The static candidate contract describes each experimental loader first trying
the expanded size, then the exact stock size. On an exact stock-size success, it
would move the compact-state tail upward and zero only the inserted 106-record
interval before normal validation and live conversion. The source save is
specified as read-only during this candidate import, and a later save is
specified to use the expanded layout. These are static route claims, not runtime
proof; import, expanded save, reload, catch-up, failed-load nonmutation, and
player gates remain ON HOLD.

The current fallback hooks and movers are:

| Game | Load hook | Fallback body | Exact tail mover |
|---|---:|---:|---|
| VV3 | file `0x28949` | file `0x7B3B1` | `0x414` dwords; expanded post-load copy count at file `0x28961` is `0x692D` dwords |
| VV4 | file `0x1FC19` | file `0x8910D` | `0x415` dwords |
| VV5 | file `0x25709` | file `0x9466C` | `0x419` dwords; compact-span guard at file `0x6FA75` changes 42,000 to 71,680 bytes |

The slot-zero profile/control loader is outside these full-village hooks and
retains its stock format.

### PE movement

All three stock files have `IMAGE_FILE_RELOCS_STRIPPED` set and a zero base
relocation directory. Relocation therefore must be complete through exact
guarded operand edits; the Windows loader cannot repair omitted absolute
addresses.

| Game | `.data` virtual size | `.shr` RVA | `.rsrc` RVA | `SizeOfImage` |
|---|---|---|---|---|
| VV3 | `0x223518` -> `0x2FC340` | `0x2C8000` -> `0x3A1000` | `0x2C9000` -> `0x3A2000` | `0x2DF000` -> `0x3B8000` |
| VV4 | `0x26F344` -> `0x3A181C` | `0x328000` -> `0x45A000` | `0x329000` -> `0x45B000` | `0x33F000` -> `0x471000` |
| VV5 | `0x2EBDA4` -> `0x424FCC` | `0x3B2000` -> `0x4EB000` | `0x3B3000` -> `0x4EC000` | `0x3C9000` -> `0x502000` |

The raw file offsets and raw section sizes do not move; the file sizes remain
831,488, 929,792, and 991,232 bytes. `.shr` keeps characteristics
`0xD0000040`. Only the virtual mapping changes.

## Index-width and sentinel boundary

The capacity operand is an exclusive bound: `256` means record indices
`0..255`. An endpoint operand is therefore changed from record 149 to record
255 where a reverse scan starts from the final record.

VV5 supplies a direct discriminator between a valid index of 255 and a
sentinel:

- `sub_46F950(this, unsigned index)` returns zero when stock `index > 0x95`;
  the expanded comparison is `index > 0xFF`. Otherwise it returns
  `this + 12100 * index + 72`.
- `sub_4708F0(unsigned index)` accepts DWORD `0xFFFFFFFF` as no selection or a
  stock index through 149; its expanded limit is 255.
- The reviewed pending-record list stores DWORD indices. Byte arrays indexed by
  record are Boolean masks, not byte-sized stored record IDs.

That path supports **256 usable VV5 slots**: index 255 is valid and DWORD `-1`
is the sentinel. It does not establish that every external cache, callback, or
save consumer is safe; those remain part of the global ON HOLD disposition.

VV3 and VV4 likewise require their final acceptance report to identify every
stored index width and sentinel independently. A literal byte value `0xFF`
cannot simultaneously represent record 255 and a no-record sentinel. Any
remaining byte-sized persisted, queued, UI, or callback index is a STOP until
its exact semantics are proved or widened.

## Current-manifest decoded coverage

The cited stock IDA reconciliation reports no unmatched decoded absolute
operand into the moving live-data tail:

| Game | Decoded moving-tail operands matched | Stock `.shr` absolute operands matched |
|---|---:|---:|
| VV3 | 656 / 656 | 4 / 4 |
| VV4 | 999 / 999 | 4 / 4 |
| VV5 | 1,168 / 1,168 | 4 / 4 |

These are static, cited-source candidate counts for the exact stock image and
population manifest, not runtime or player evidence. They do not include
references introduced later by optional features. That second composition
layer is where VV4 and VV5 remain on hold.

## Per-game implementation gates

### VV3 - The Secret City

**Status: ON HOLD.**

Proved statically:

- The pool geometry, 256 logical bound, four-record safety padding, compact
  save growth, moved-tail references, PE movement, and resource RVAs are
  guarded in the current manifest.
- Candidate arrays originally sized 150, 151, 300, or 450 are expanded to 256,
  257, 512, or 768 entries with their stack frames and argument displacements.
- File `0x60D46` changes the main-world reverse hit-test bound from 149 to 255,
  and file `0x60D4C` moves its endpoint from record 149 to record 255.
- File `0x5F975` moves the mating spatial-scan endpoint to record 255.
- File `0x5FA46` moves the nearby-villager endpoint to record 255.
- File `0x35A5A` expands the serialized-index validator from 150 to 256.
- File `0x5EE69` expands active-record lookup from 150 to 256.
- Population additions have separately guarded capacity paths for ordinary
  birth/multiple-birth and direct Island Event/barrel additions; those edits do
  not by themselves prove end-to-end save/runtime behavior.
- The present all-current render adds Nature Honey, Nature mortality, Rare
  Collectible Retry, base Origins, and Village Statistics without a declared
  byte-range collision. No stale `.shr` relative branch or absolute pointer
  was found in that render.

Still missing:

1. The existing expanded runtime became non-responsive during load. The exact
   faulting loop/call and whether it occurs before or after fallback conversion
   have not been captured.
2. A successful stock-save import, expanded save, reload, and offline catch-up
   round trip is absent.
3. The final stored-index audit must prove that every selection, sorted roster,
   Detail navigation, planner/action queue, pairing/pregnancy, birth, death,
   skeleton/memorial, Event/puzzle, statistics, and callback path either holds
   a DWORD index or treats `0xFF` without excluding valid record 255.
4. The four VV3 padding records must remain unreachable from construction,
   selection, serialization, population counting, and statistics in every
   path, not only the reviewed unrolled selectors.
5. A late-record test matrix must exercise records 149, 150, 254, and 255 plus
   sparse holes, empty/dead records, pregnancy/birth, death/skeleton, Detail
   navigation, save/reload, and offline catch-up.

The bounded static contract in `src/vv3_expanded_256_contract.py` and
`tests/test_vv3_expanded_256_contract.py` now pins the reviewed VV3 loader
bytes, exact stock/expanded save sizes, the 106-record zero gap, logical
records 0 through 255, and four zero-only padding records. It is a byte-layout
model and regression guard; it does not execute the native loader, inspect a
player save, or close any of the runtime blockers above. Its stored-index
audit deliberately remains `incomplete` with an `unresolved` native sentinel,
so the public publication gate stays fail-closed.

No Coding artifact may be enabled until the load hang is reduced to an exact
instruction/call-state cause and the stored-index audit is closed.

### VV4 - The Tree of Life

**Status: ON HOLD.**

Proved statically:

- The pool, compact-save, PE, moved-data, temporary-array, and reviewed
  record-255 endpoint edits are guarded.
- The population manifest relocates all four stock `.shr` absolute operands and
  all four stock cross-section relative branches found by IDA.
- Birth, newcomer/event, barrel, and infant-reservation capacity checks have
  separately guarded expanded boundaries.
- The current all-feature render adds Complete Scales/Golden Fish, base
  Origins, and Village Statistics without a declared byte-range collision.

Runtime blocker:

- The tested expanded executable did not accept a stock-sized village save.
  There is no successful conversion/save/reload proof.

All-feature relocation contract (static repair):

The moved `.shr` delta is `0x132000`. The four operands previously left at the
old `.shr` address are now declared by the VV4 owner manifest and guarded by
`data/vv4_expanded_256_contract.json`:

| Operand file offset | Instruction VA/item | Old value | Required value | Current bytes | Required bytes |
|---:|---:|---:|---:|---|---|
| `0x89546` | `0x489544` | `0x728220` | `0x85A220` | `20827200` | `20A28500` |
| `0xCC1AF` | `0x7281AD` | `0x728234` | `0x85A234` | `34827200` | `34A28500` |
| `0xCC1B8` | `0x7281B6` | `0x728238` | `0x85A238` | `38827200` | `38A28500` |
| `0xCC1C1` | `0x7281BF` | `0x72823C` | `0x85A23C` | `3C827200` | `3CA28500` |

The first is the operand of `cmp dword_728220, 50465656h`. The remaining
three are operands of decoded `.shr` comparisons with zero. Two other raw
four-byte failures were classified as false candidates: the windows began on
the `E8` opcode of calls at raw `0x71FB1` and `0x7A34A`.

The base Origins feature separately relocates four existing absolute `.shr`
values (`0x728220`, `0x728224`, `0x728228`, and `0x728230`) and now owns all
four operands above. The disabled village-wide record no longer claims
ownership of the current-Origins operand.

Still missing:

1. Diagnose the stock-save import failure and prove conversion plus expanded
   save/reload/catch-up.
2. Complete the stored-index and record-255 audit across sorting/Detail,
   planner/action, pairing/pregnancy, birth, death/skeleton/memorial,
   Event/puzzle, statistics, and callback paths.
3. Exercise sparse and late records 149, 150, 254, and 255 in both expanded
   population modes and all current-feature compositions.

### VV5 - New Believers

**Status: ON HOLD.**

Proved statically:

- The pool, compact save, PE movement, reviewed record lookup/selection, and
  record-255 reverse endpoints use a 256 exclusive bound.
- The compact serializer span changes from 42,000 (`150 * 280`) to 71,680
  (`256 * 280`) bytes.
- Population accounting includes physical Heathens, unreleased corpses, and
  nursing-baby reservations where the stock logic does so. The expansion does
  not authorize replacing those predicates with a believer-only count.
- Birth and direct population-addition capacity guards have expanded-bound
  edits.
- The current all-feature render adds Heathen Mommy, Easier Devotee Training,
  Statue action selection, Nursery divisor parity, base Origins, and Village
  Statistics without a declared byte-range collision.

All-feature relocation contract (static repair):

The moved `.shr` delta is `0x139000`. Of 167 direct relative branches with a
source or target in `.shr`, 131 internal `.shr` branches remain correct because
source and target move together. The relocation ledger now declares the 36
cross-section branches previously left stale: seven `.text -> .shr` branches
and 29 moved `.shr -> .text` returns, calls, or jumps.

The seven previously stale external relative operands are:

| Operand file offset | Instruction VA | Old target | Required target | Current rel32 bytes | Required rel32 bytes |
|---:|---:|---:|---:|---|---|
| `0x18910` | `0x41890F` | `0x7B2180` | `0x8EB180` | `6C983900` | `6C284D00` |
| `0x1EB70` | `0x41EB6F` | `0x7B2B00` | `0x8EBB00` | `F67E3456` | `8CCF4C00` |
| `0x237B1` | `0x4237B0` | `0x7B2A00` | `0x8EBA00` | `8B742408` | `4B824C00` |
| `0x40A25` | `0x440A24` | `0x7B2040` | `0x8EB040` | `17163700` | `17A64A00` |
| `0x4AF13` | `0x44AF12` | `0x7B2100` | `0x8EB100` | `E9713600` | `E9014A00` |
| `0x4BC21` | `0x44BC20` | `0x7B20C0` | `0x8EB0C0` | `9B643600` | `9BF44900` |
| `0x94FBF` | `0x494FBE` | `0x7B2210` | `0x8EB210` | `4DD23100` | `4D624500` |

The first is the Island Event selector detour. The next two are the Food and
Tech Doubler hooks. Restoring those two writer hooks to stock in expanded mode
does not repair the surrounding Origins payload. Five of the 36 stale
cross-section branches are the two doubler hooks and three wrapper returns;
the other 31 remain independent blockers.

The remaining 29 previously stale relative operands originate in the moved `.shr` payload
and target unmoved `.text`. Their exact expanded instruction VAs, targets, and
required displacements are:

| Operand file offset | Expanded instruction VA | Target | Current rel32 bytes | Required rel32 bytes |
|---:|---:|---:|---|---|
| `0xDB01C` | `0x8EB01B` | `0x450D40` | `20EDC9FF` | `205DB6FF` |
| `0xDB021` | `0x8EB020` | `0x4415F8` | `D3F5C8FF` | `D365B5FF` |
| `0xDB043` | `0x8EB042` | `0x47BBDC` | `959BCCFF` | `950BB9FF` |
| `0xDB055` | `0x8EB054` | `0x44FA20` | `C7D9C9FF` | `C749B6FF` |
| `0xDB06C` | `0x8EB06B` | `0x401BD0` | `60FBC4FF` | `606BB1FF` |
| `0xDB08E` | `0x8EB08D` | `0x4015D0` | `3EF5C4FF` | `3E65B1FF` |
| `0xDB096` | `0x8EB095` | `0x40C680` | `E6A5C5FF` | `E615B2FF` |
| `0xDB0E1` | `0x8EB0E0` | `0x44BC28` | `439BC9FF` | `430BB6FF` |
| `0xDB103` | `0x8EB102` | `0x47BBDC` | `D59ACCFF` | `D50AB9FF` |
| `0xDB115` | `0x8EB114` | `0x44FA20` | `07D9C9FF` | `0749B6FF` |
| `0xDB12C` | `0x8EB12B` | `0x401BD0` | `A0FAC4FF` | `A06AB1FF` |
| `0xDB14E` | `0x8EB14D` | `0x4015D0` | `7EF4C4FF` | `7E64B1FF` |
| `0xDB156` | `0x8EB155` | `0x40C680` | `26A5C5FF` | `2615B2FF` |
| `0xDB1A0` | `0x8EB19F` | `0x418916` | `7267C6FF` | `72D7B2FF` |
| `0xDB272` | `0x8EB271` | `0x425950` | `DA36C7FF` | `DAA6B3FF` |
| `0xDB283` | `0x8EB282` | `0x471840` | `B9F5CBFF` | `B965B8FF` |
| `0xDB292` | `0x8EB291` | `0x46F950` | `BAD6CBFF` | `BA46B8FF` |
| `0xDB38D` | `0x8EB38C` | `0x425950` | `BF35C7FF` | `BFA5B3FF` |
| `0xDB3C3` | `0x8EB3C2` | `0x4944C0` | `F920CEFF` | `F990BAFF` |
| `0xDB3ED` | `0x8EB3EC` | `0x494B37` | `4627CEFF` | `4697BAFF` |
| `0xDB415` | `0x8EB414` | `0x4237B0` | `9713C7FF` | `9783B3FF` |
| `0xDB437` | `0x8EB436` | `0x4237B0` | `7513C7FF` | `7583B3FF` |
| `0xDB45A` | `0x8EB459` | `0x494EA0` | `422ACEFF` | `429ABAFF` |
| `0xDB462` | `0x8EB461` | `0x494EA0` | `3A2ACEFF` | `3A9ABAFF` |
| `0xDB46C` | `0x8EB46B` | `0x494EA0` | `302ACEFF` | `309ABAFF` |
| `0xDB7AC` | `0x8EB7AB` | `0x4237B0` | `0010C7FF` | `0080B3FF` |
| `0xDBA56` | `0x8EBA55` | `0x4237B7` | `5D0DC7FF` | `5D7DB3FF` |
| `0xDBB22` | `0x8EBB21` | `0x41EB74` | `4EC0C6FF` | `4E30B3FF` |
| `0xDBB27` | `0x8EBB26` | `0x41EBA7` | `7CC0C6FF` | `7C30B3FF` |

Of 34 raw four-byte values in the old `.shr` range, 23 payload-internal
absolute references move correctly. The seven decoded external pushes that
were previously stale are now declared in the same owner ledger:

| Operand file offset | Old address | Required address | Current bytes | Required bytes | Referenced value |
|---:|---:|---:|---|---|---|
| `0x94B80` | `0x7B2EF0` | `0x8EBEF0` | `F02E7B00` | `F0BE8E00` | `ShowOriginsVillageWideResult` |
| `0x94B85` | `0x7B2EBD` | `0x8EBEBD` | `BD2E7B00` | `BDBE8E00` | `VVFP Origins Icons.dll` |
| `0x94B94` | `0x7B2EF0` | `0x8EBEF0` | `F02E7B00` | `F0BE8E00` | `ShowOriginsVillageWideResult` |
| `0x94ED1` | `0x7B2EF0` | `0x8EBEF0` | `F02E7B00` | `F0BE8E00` | `ShowOriginsVillageWideResult` |
| `0x94ED6` | `0x7B2EBD` | `0x8EBEBD` | `BD2E7B00` | `BDBE8E00` | `VVFP Origins Icons.dll` |
| `0x94EE5` | `0x7B2EF0` | `0x8EBEF0` | `F02E7B00` | `F0BE8E00` | `ShowOriginsVillageWideResult` |
| `0x94FBA` | `0x7B2D09` | `0x8EBD09` | `092D7B00` | `09BD8E00` | `Origins Upgrades` |

All 43 previously omitted current-feature references are now declared
atomically with the base Origins ownership and uninstall model. Relocating
only the doubler references remains forbidden.

Still missing:

1. Re-certification of the Island Event selector detour and its safe
   continuation in the relocated payload.
2. A complete external stored-index/cache audit despite the proven DWORD
   selected-index path.
3. A 256-record live/save/catch-up matrix covering believers, Heathens,
   nursing reservations, corpses, sparse holes, records 149/150/254/255,
   pairing/birth, death/memorial, Events/puzzles, statistics, and Detail
   navigation.

## Adversarial static validation

The self-contained Expanded-256 adversarial suite validates the disabled
contracts without requiring either absent stock executable. VV4 and VV5
relocation ledgers have immutable canonical SHA-256 identities over every
normalized row and field, in addition to their semantic class, range, and
moved/unmoved checks. The suite rejects wrong hashes or publication enablement,
missing or duplicate VV4 current-Origins operands and eight-row payload
relocations, and VV5 ledger mutations outside the exact 23 absolute / 36
`rel32` / 7 external partition. It also rejects every per-row class, preimage,
source, target, override, and offset/purpose mutation, stale preimages,
malformed override guards, and overlapping writes. Relocation preflight is
transactional: a later failed guard leaves every earlier byte unchanged, and
stock modes remain byte-for-byte no-ops. These are static fail-closed checks
only; they do not close save, launch, runtime, or player acceptance gates.

## Current-render composition ledger

These ignored audit renders are reproducible static evidence. A `PASS` here
means the renderer accepted every declared guard/range and produced the listed
hash. It is not a runtime or completeness PASS.

| Game | Mode | Base SHA-256 | All-current SHA-256 |
|---|---|---|---|
| VV3 | Expanded immediate | `90D66177FFED851A868623202B895CB4CEDAED19C39538641BBDB52383E864A0` | `46E5CC38AA914A7D46A5F825D6F8C187487B786CBC3235B5E0253F54FB8A9888` |
| VV3 | Expanded progression | `2C08DE9A236D0841DEF24B9488CCE5B007EDC32161C1FA5351D04F2DA59ED0CF` | `74A8122B0711C6F14075123834EFABFE894281698982A4D6AAC536A20972E1B7` |
| VV4 | Expanded immediate | `428A8A8DE3B753CA813AB29960C49D15D4B3EDBE97BB49D8625C81743FEA3782` | `602824F514BFAB80883805B16C01D1E572752261A155262778CF8D535C41D887` |
| VV4 | Expanded progression | `737F475764EBB9F35BC6C68337698D46F6D03BA0560B9BE4E352F80AF48FE791` | `AC430442DE23406236903CAA6FC9A992D52DCF3269A95ED345A9EF6F18B9C30A` |
| VV5 | Expanded immediate | `3F7FDA81D5AF20C946D7CF554229C94960123035BB8762B3B9BFF4115403B83D` | `44042572653782B20A200799785F437D4D76B46F20384D597B8093F27CC88C89` |
| VV5 | Expanded progression | `7B618C6AE2D1C0024DC63940353B565FD18510344D3912B83D62A1005DA985EA` | `6BF9E0EB9BC7D3C373E32C3A7377C9A7EA35C1FA889EEDBF9B2819A25BC43E86` |

The current feature sets in those all-current renders are:

- VV3: Nature Honey, Nature mortality, Rare Collectible Retry, base Origins,
  Village Statistics.
- VV4: Complete Scales/Golden Fish, base Origins, Village Statistics.
- VV5: Heathen Mommy, Easier Devotee Training, Statue action selection,
  Nursery divisor parity, base Origins, Village Statistics.

## Save compatibility, removal, and recovery

- Stock saves are imported into a larger in-memory/serialized layout only after
  an exact stock-size load succeeds.
- Expanded saves are not proved readable by the stock executable. There is no
  reverse expanded-to-stock migration contract.
- Removing the executable expansion while retaining an expanded save is
  unsafe.
- The structural edit has no certified in-place uninstall transaction. A
  reversible patcher route must regenerate the exact stock executable from the
  untouched exact-build source and separately preserve or migrate saves.
- A failed guard, unexpected file size, unexpected section layout, unexpected
  owner byte, or unrecognized save size must stop before writing.

## Required acceptance matrix before GO

Each game must close every row independently:

| Gate | Required proof |
|---|---|
| Exact image | Exact size/SHA, all old-byte guards, current regenerated image hash, checksum/readback |
| Allocation | Manager/pool construction, zero initialization, full physical reservation, no out-of-range group reads |
| Indexing | Every stored or transported index width; index 255 versus all no-record sentinels |
| Walkers | Selection, targeting, sorting, Detail roster/navigation, planners/actions, sparse holes, late records |
| Family lifecycle | Manual/autonomous pairing, pregnancy, birth, multiple births, nursing reservations |
| Death lifecycle | Death, corpse/skeleton, pickup/burial, grave/mausoleum/roster, capacity and eviction |
| Special paths | Every Island Event, puzzle, newcomer, clone/special birth, direct population writer |
| Time | Live tick, save/load, offline/catch-up, delayed actions/events |
| Statistics | Population and lifetime counters use intended record predicates and include/exclude special records natively |
| Save | Stock import, expanded save, reload, rotation/backup generation, failed-load nonmutation |
| Relocation | Every absolute and cross-section relative reference, including optional-feature payloads |
| Composition | Both expanded modes plus every current feature; owner ordering, collision, corrupt-guard failure |
| Removal | Exact executable restoration and an explicit safe policy for expanded saves |

Minimum runtime fixtures are sparse and dense pools with occupied/empty/dead
records at 149, 150, 254, and 255. VV3 additionally needs assertions that
padding indices 256 through 259 remain zero and unreachable. VV5 needs mixed
believer/Heathen/corpse/nursing-reservation fixtures.

## Reproducible analysis tools

The following scripts are evidence tools only; they do not edit an executable:

- `scripts/ida_export_expanded_gate_refs.py`
- `scripts/run_idalib_expanded_gate_refs.py`
- `scripts/ida_inspect_offsets.py`
- `scripts/run_idalib_inspect_offsets.py`
- `scripts/reconcile_expanded_256_gate_refs.py`
- `scripts/audit_expanded_shr_relocations.py`
- `scripts/render_expanded_256_gate_variants.py`

IDA databases are opened with auto-analysis and closed without saving. Rendered
executables and JSON ledgers remain under ignored `outputs/` or `research/`
paths and are not repository artifacts.

## Coding handoff

Coding must keep both expanded modes experimental and unavailable for packaging.
The next admissible artifacts are disabled candidates only:

1. regenerate from the current manifest rather than any historical prototype;
2. close the VV3 load hang before any additional feature work;
3. retain and independently validate the four VV4 Origins absolute operands in
   one exact ownership/uninstall contract;
4. retain and independently validate all 43 declared VV5 current-feature
   references atomically, not only the doubler subset;
5. return deterministic stock/both-expanded/all-current renders for independent
   byte certification;
6. keep gameplay launch and packaging blocked until the per-game runtime/save
   acceptance matrix passes.
