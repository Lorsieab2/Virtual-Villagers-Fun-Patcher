# Experimental 256-villager expansion for VV3-VV5

> **ON HOLD — do not package or release:** current exact-build reanalysis found
> unresolved save/runtime failures in VV3 and VV4, four stale all-feature
> `.shr` pointers in VV4, and 36 stale cross-section branches plus seven stale
> external `.shr` pointers in VV5. Passing renderer and PE-readback checks does
> not establish relocation completeness or runtime safety. See the exact
> [VV3-VV5 implementation-gate report](vv3-vv5-expanded-256-implementation-gates.md).

## Result

Version 1.21.0 attempted two expanded modes: **Experimental Expanded 256
Villagers** makes 256 available immediately, while **Experimental Expanded 256
- Collection Progression** retains the original population bonuses and requires
them to reach 256. Both are structural executable expansions, not cap-only
edits.

VV3, VV4, and VV5 originally reserve exactly 150 full villager records. The
patch expands their zero-filled `.data` storage for 106 additional records,
moves the following global-data tail and PE sections, rewrites decoded
references, grows the compact save table, expands temporary record-selection
arrays, and changes the relevant record walkers from 150 to 256.

VV1 and VV2 already contain 256 physical records, so this mode uses their
existing 256-slot fixed-cap behavior.

## Exact record expansion

| Game | First record | Record stride | Stock records | Expanded records | Added zero-filled storage |
|---|---:|---:|---:|---:|---:|
| The Secret City | `0x59E124` | `0x1F8C` (8,076 bytes) | 150 | 256 logical + 4 padding | 888,360 bytes |
| The Tree of Life | `0x50E5AC` | `0x2E3C` (11,836 bytes) | 150 | 256 | 1,254,616 bytes |
| New Believers | `0x554190` | `0x2F44` (12,100 bytes) | 150 | 256 | 1,282,600 bytes |

The raw EXE size does not increase because these records live in the
zero-initialized portion of `.data`. Its virtual size and `SizeOfImage` do
increase. The small `.shr` and `.rsrc` sections are moved to new virtual
addresses, their decoded absolute references and resource RVAs are rewritten,
and the PE checksum is recalculated.

## Save layout

The compact saved-villager tables are expanded by 106 entries:

| Game | Compact stride | Added save bytes |
|---|---:|---:|
| The Secret City | 284 | 30,104 |
| The Tree of Life | 260 | 27,560 |
| New Believers | 280 | 29,680 |

Tail fields, allocation sizes, stack buffers, writers, loaders, initializers,
and live/compact conversion loops are shifted or expanded together.

VV3 has a separate physical-padding requirement. Several stock selectors are
unrolled in groups of five. A direct 150-to-256 guard change makes their last
pass inspect indices 255 through 259. The executable therefore reserves four
zeroed, non-saveable padding records after logical slot 255. Population,
serialization, construction, and ordinary record walkers remain limited to
the intended 256 logical records; the padding only keeps the stock grouped
reads inside allocated memory and prevents indices 256-259 from becoming
false candidates.

The patched games keep the stock `%s%d.ldw` filename format. Their separately
named modified EXEs create and use separate executable-named save folders, so
changing the filenames inside those folders is unnecessary.

VV3-VV5 now use a guarded two-format loader. It first requests the expanded
payload size. If that exact size check fails, it retries with that game's exact
stock payload size. A successful stock-layout load moves the saved-state tail
upward and zeroes the inserted 106-entry compact villager gap before normal
validation and live-record conversion continue. Payload offsets are eight
bytes lower than their corresponding in-memory object offsets because the
object stores the loaded payload at `this+8`; the compatibility mover accounts
for that header. A subsequent ordinary save writes the expanded layout.
Neither failed size check nor fallback loading rewrites the source file.

Every game's required slot-zero control/profile file remains in its stock
format. In VV3-VV5, the experimental hooks affect only the full-village loader;
the separate 136-byte slot-zero loader call is byte-for-byte stock in both
expanded modes. VV1 and VV2 retain their complete stock save layouts, including
slot zero. A `0.ldw` file must accompany copied village slots in the matching
executable-named save folder; it is never expanded or rewritten as a village
record payload.

Earlier compatibility revisions contained two independent mover errors. The
first used in-memory offsets directly and zeroed eight bytes of valid saved
state. The second passed the tail's byte length directly to `rep movsd`, making
the routine copy four times the intended number of bytes, and began at the
last byte rather than the last aligned dword. That could overwrite saved-state
fields after the villager table and produce invalid gameplay data. The current
movers use aligned final-dword addresses and exact dword counts: `0x414` for
VV3, `0x415` for VV4, and `0x419` for VV5. A byte-for-byte synthetic migration
test verifies that the original prefix and tail survive unchanged while only
the 106-record gap is zero-filled.

VV3 required one additional correction: its expanded stack buffer and loader
size had been increased, but its following `rep movsd` still copied only the
77,596-byte stock payload. The copy count is now 26,925 dwords, covering the
complete 107,700-byte expanded payload. VV4 and VV5 already copied their full
expanded payloads.

VV1 and VV2 keep the stock save format because their record layout was already
256 entries.

## Temporary arrays and record walkers

Record-selection routines contained local arrays of 150, 151, 300, or 450
indices. Their stack frames and argument displacements are expanded so the
reanalyzed executables reconstruct those arrays as 256, 257, 512, or 768
entries. Manager construction, initialization, lookup, save conversion, and
other identified record loops use 256 as their exclusive bound.

The expanded build also widens the small index-validation and reverse-selection
helpers that are not written as obvious `for (i = 149)` loops. VV3's state and
record validators now accept indices through 255, and its main-world spatial
picker, mating picker, and nearby-villager picker all scan through record 255.
VV4's record lookup, selected-villager validation, world-coordinate picker,
player-to-player picker, and nearby-sick-villager picker use record-255 end
points. VV5's lookup, selected-villager validation, pending-record removal, and
reverse-selection paths are widened as well. In all three games, every reviewed
reverse-selection helper has both its loop bound and its initial pointer moved
from the stock record-149 address to the corresponding record-255 address;
widening only the loop bound makes a picker walk backwards out of the record
table and can select arbitrary records. Leaving any reviewed helper at the stock
149 endpoint causes late-record lookups to fail or reuse the wrong record even
when the larger arrays exist.

## Interaction audit

The expanded patches do not replace villager interaction rules. They only widen
the candidate records available to the stock selectors and preserve the stock
action dispatch after a target is selected. Manual drop/click selection and
autonomous selection therefore retain their original predicates, preferences,
skill checks, gender/age checks, sickness checks, and action outcomes. In
particular, the player-healing path still selects a sick villager through the
stock target picker and then calls the stock healing action; it is not redirected
to a new healer implementation. Static rendered-byte tests cover the reviewed
manual and autonomous picker bounds and endpoints for VV3, VV4, and VV5. This is
an executable-structure audit only; a complete live playthrough and save/reload
validation remains separate player QA.

IDA Pro 9.4 was used to export decoded operands. This matters because the
Microsoft runtime contains valid code outside some named function boundaries.
A raw sliding-byte address sweep was tested, found to corrupt instructions, and
discarded. The committed manifest contains only guarded, reviewed offsets.

## Population behavior

The immediate experimental mode makes 256 available at once. Collection
bonuses, and VV3's level-3 Magic bonus, no longer change that mode.

The experimental progression mode preserves each original bonus ceiling:

| Game | Expanded base | Retained bonuses | Completed maximum |
|---|---:|---:|---:|
| The Lost Children | 231 | 0-25 collections | 256 |
| The Secret City | 221 | 0-25 collections plus 0/10 Magic | 256 |
| The Tree of Life | 231 | 0-25 collections | 256 |
| New Believers | 241 | 0-15 collections | 256 |

Multiple-birth and direct population-adding Island Event guards use the
expanded 256-record boundary in both modes. VV5 continues counting occupied or
reserved physical records, including Heathens, unreleased corpses, and
nursing-baby reservations.

## Verification completed and current blockers

- Exact stock SHA-256 identification and byte guards.
- Reanalysis of expanded executables in IDA Pro.
- Reconstructed 256/257/512/768-entry temporary arrays.
- The VV5 compact-save loader's byte-span guard was separately expanded from
  `150 × 280` to `256 × 280`; this limit was encoded as `42,000` bytes rather
  than as the literal record count `150`.
- The reviewed 150-record and stride-multiplied record walkers are expanded;
  unrelated 150 constants such as coordinate distances and UI/runtime
  thresholds remain unchanged.
- PE section, resource-directory, checksum, output-size, and readback checks.
- The earlier ten-second process-alive smoke test was insufficient. Current
  player-observed validation found VV3 spinning non-responsive during load and
  VV4 failing to accept a stock-sized village slot.
- Exact current-feature relocation analysis found four stale absolute `.shr`
  operands in VV4 and 43 moved references in VV5. These are implementation
  blockers, not merely pending player validation.
- Historical prototype hashes predate nine later guarded corrections per game
  and are not current certification artifacts.

The bare-EXE test that displayed a missing-`fmod.dll` dialog is not counted as a
game startup. A later raw-sweep prototype that crashed is also superseded and
is not the committed manifest.

## Experimental boundary

Static structure is partially verified, but current relocation and
save-loading behavior are not complete. A village has not yet been played all
the way to 256 villagers through births, deaths, Island Events, offline
catch-up, save, and reload. The mode remains blocked from release until the
per-game implementation gates are closed and corrected builds are independently
certified and player-tested.
