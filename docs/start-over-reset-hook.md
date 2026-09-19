# Where "Start Over" actually happens, in all five games

Reference for the Start Over reset. Every address below was read out of the five
stock executables, not inferred.

## The menu string is not the hook

`"Start Over"` exists in all five binaries, but its only reference is a
**localisation string table**, not code:

| game | string VA | referenced from |
|---|---|---|
| VV1 | `0x47C958` | `0x4883C8` |
| VV2 | `0x48CA44` | `0x497138` |
| VV3 | `0x498AF4` | `0x4AD2E8` |
| VV4 | `0x4A2158` | `0x4C6BD0` |
| VV5 | `0x4B0410` | `0x4D5AD8` |

Dumping the VV2 table shows English/German pairs with a numeric id — `"Play"` /
`"Spiel"` / `0xC0`, then `"Start Over"` / `"Neu starten"` / `0xC1`, then
`"Options"` / `"Optionen"`. The menu dispatches on the id, so nothing in code
refers to the text and the string is a dead end for hooking.

## deleteSave(slot) is the hook

Each game imports `DeleteFileA` and calls it from exactly **one** site, inside
the CRT's `remove()` wrapper. That wrapper in turn has exactly one caller: a
small game function that erases one save slot.

```asm
; VV5 0x403900 -- VV4 identical in shape
mov  eax, [ecx]          ; this->vtable
mov  edx, [esp+4]        ; slot
mov  eax, [eax+0x0C]     ; vtable +0xC = buildSavePath
push edx
call eax                 ; "<base><slot>.ldw"
push eax
call <remove>            ; delete it
pop  ecx
ret  4
```

```asm
; VV1 0x403120 -- VV2 and VV3 identical in shape
mov  edx, [esp+4]        ; slot
mov  eax, [ecx]          ; this->vtable
push edx
call [eax+0x0C]          ; buildSavePath, called indirectly
push eax
call <remove>
pop  ecx
ret  4
```

The two families differ only in the order of the first two `mov`s and in whether
`buildSavePath` is called directly or through the memory operand. Semantics are
the same: **take a slot, build that slot's save path, delete it.**

| game | `remove()` wrapper | `deleteSave` | prologue | `int3` padding before |
|---|---|---|---|---|
| VV1 | `0x44B886` | `0x403120` | `8B5424048B0152FF500C` | 12 |
| VV2 | `0x468906` | `0x4033B0` | `8B5424048B0152FF500C` | 12 |
| VV3 | `0x46F616` | `0x4034F0` | `8B5424048B0152FF500C` | 12 |
| VV4 | `0x4722A2` | `0x403970` | `8B018B5424048B400C52` | 14 |
| VV5 | `0x47D582` | `0x403900` | `8B018B5424048B400C52` | 14 |

Each `deleteSave` has exactly one direct caller and **zero** data references, so
it is not reached through a vtable:

| game | caller |
|---|---|
| VV1 | `0x40317A` |
| VV2 | `0x40340A` |
| VV3 | `0x40354A` |
| VV4 | `0x4039E0` |
| VV5 | `0x403970` |

The callers are structurally identical too, guarding on the slot before calling:

```asm
mov  edi, [esp+0x218]    ; 0x220 in VV4/VV5
test edi, edi
mov  esi, ecx
jle  <skip>
lea  ebx, [edi+0x14]
push ebx
call <deleteSave>
```

## CORRECTION: deleteSave is NOT the Start Over event

The reasoning below was wrong, and disk evidence disproves it.

`deleteSave` is called from a **save** routine that rotates backups. Its caller
passes `ebx = slot + 0x14`, not the raw slot:

```asm
mov  edi, [esp+0x218]   ; the slot
test edi, edi
jle  <skip>
lea  ebx, [edi+0x14]    ; slot + 20
push ebx
call <deleteSave>       ; delete the OLDEST backup
... then writes a new save through vtable +0xC with mode "wb"
```

The save files on disk confirm it. VV1's folder holds `Virtual Villagers1.ldw`,
`...21.ldw` and `...41.ldw` -- the same size, different hashes, written about ten
minutes apart in descending order. They are three generations of ONE village,
and `21 = 1 + 20`, `41 = 21 + 20`. The routine writes the new save and drops the
oldest generation.

So `deleteSave` fires on **every ordinary save**. Hooking it to delete
patcher state would destroy a player's masks and logs continuously during normal
play -- the precise "do not fix reset by breaking persistence" failure.

The owner also reports there are **two** ways to reset a tribe: Start Over, and
deleting the tribe outright from the save-slot screen. Both still need locating,
and neither is this function.

## Why buildSavePath is also not the event

`buildSavePath` (VV5 `0x403600`) is the choke point the per-slot mask sidecar
already hooks, and it is the wrong place for a reset: it runs on **every** save
and load and cannot distinguish Start Over from ordinary play. Hooking it to
delete anything would destroy state during normal use.

Neither function is the reset. Both run during ordinary play, so both would
destroy persistence rather than reset it. The reset event is still unlocated;
see the correction above.

## Hooking space

Every `deleteSave` prologue is at least 10 clean bytes, enough for a 5-byte
`jmp rel32`, and each is preceded by 12–14 bytes of `int3` compiler padding.
No code cave hunt is needed.

## What the reset must delete

Only patcher-owned files belonging to the slot being erased, resolved through
the same `vv_save_folder` used to write them (see
`native/shared/save_folder.h`). A failed path resolution must abort rather than
fall back to any other directory: the reset deletes, and a wrong folder is a
wrong deletion target.
