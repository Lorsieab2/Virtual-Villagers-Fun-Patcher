# Experimental 256-villager expansion for VV3-VV5

## Result

Version 1.20.0 adds **Experimental Expanded 256 Villagers** as a third patch
mode. This is a structural executable expansion, not a cap-only edit.

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
| The Secret City | `0x59E124` | `0x1F8C` (8,076 bytes) | 150 | 256 | 856,056 bytes |
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

Stock 150-record saves are deliberately not loaded by this mode. The patched
games use the separate format `%sE%d.ldw` instead of stock `%s%d.ldw`.
Therefore the experimental builds neither load nor overwrite the stock-numbered
save files. VV1 and VV2 keep the stock save format because their record layout
was already 256 entries.

## Temporary arrays and record walkers

Record-selection routines contained local arrays of 150, 151, 300, or 450
indices. Their stack frames and argument displacements are expanded so the
reanalyzed executables reconstruct those arrays as 256, 257, 512, or 768
entries. Manager construction, initialization, lookup, save conversion, and
other identified record loops use 256 as their exclusive bound.

IDA Pro 9.4 was used to export decoded operands. This matters because the
Microsoft runtime contains valid code outside some named function boundaries.
A raw sliding-byte address sweep was tested, found to corrupt instructions, and
discarded. The committed manifest contains only guarded, reviewed offsets.

## Population behavior

The experimental maximum is immediately 256. Collection bonuses, and VV3's
level-3 Magic bonus, no longer change it. Multiple-birth and direct
population-adding Island Event guards use the expanded 256-record boundary.
VV5 continues counting occupied or reserved physical records, including
Heathens, unreleased corpses, and nursing-baby reservations.

## Verification completed

- Exact stock SHA-256 identification and byte guards.
- Reanalysis of expanded executables in IDA Pro.
- Reconstructed 256/257/512/768-entry temporary arrays.
- No remaining identified 150-bound record walkers; unrelated 150 constants
  such as coordinate distances and UI/runtime thresholds remain unchanged.
- PE section, resource-directory, checksum, output-size, and readback checks.
- Complete copied game folders containing `fmod.dll`, SDL2, image libraries,
  assets, and every original companion file.
- Ten-second Windows startup test: VV3, VV4, and VV5 each remained running and
  responsive and displayed its correctly titled game window.

The bare-EXE test that displayed a missing-`fmod.dll` dialog is not counted as a
game startup. A later raw-sweep prototype that crashed is also superseded and
is not the committed manifest.

## Experimental boundary

Startup and static structure are verified. A village has not yet been played
all the way to 256 villagers through births, deaths, Island Events, offline
catch-up, save, and reload. The mode is labeled experimental for that reason.
Use the patcher's complete copied game folder, keep the stock EXE, and retain
backups even though the E-numbered experimental saves are separate.
