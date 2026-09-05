# VV4's 150-slot safety guards: once inert, now live

Recorded 2026-08-31 while investigating the reported VV4 Barrel of Babies
behaviour ("the event cues but no children are added"), and **corrected
2026-09-04** after the guards were rebuilt against a real counter.

> **Superseded heading.** This file was previously titled "VV4's 150-slot
> safety guards never fire", and its body described the fix as future work in
> four numbered steps. All four were completed. The historical finding is kept
> below because the *reasoning* about resume targets is still why these guards
> are shaped the way they are -- but do not read the old title as a live
> defect. It is not one.

## The original finding (historical)

VV4 has five automatic safety patches meant to stop child-creating events from
running past the 150 physical villager slots. Every one of them decided using a
single static address:

```asm
00489080  cmp dword ptr [0x4D6DE8], 0x96   ; barrel first child
0048908A  jge 0x489096                     ; skip when full
```

**Nothing ever wrote `0x4D6DE8`.** Its initial `.data` value was `0`, its only
byte-pattern match in the stock executable was a coincidence inside the
immediate operand of `or eax, 0x4d6de8` at `0x45E91D`, and the only manifest
rows mentioning it were the five guards, all of which merely read it. So every
comparison was `0 >= 150`, always false, and every guard took the resume path.

## Current state: the guards use a real counter

All five now call a record-counting helper instead of reading a dead address.
Verified by disassembling a rendered VV4 executable, not by reading source:

```asm
00489020  call 0x4890f0 ; cmp eax, 0x93 ; jg  ...   ; triplets
00489040  call 0x4890f0 ; cmp eax, 0x94 ; jg  ...   ; twins
00489060  call 0x4890f0 ; cmp eax, 0x96 ; jge ...   ; event newcomer
00489080  call 0x4890f0 ; cmp eax, 0x96 ; jge ...   ; first barrel child
004890C0  call 0x4890f0 ; neg eax ; add eax, 0x96   ; abandoned infants
```

The helper at `0x4890F0` sweeps the record array exactly as the old note
proposed -- base `0x50E5AC`, stride `0x2E3C`, active byte `+0x1CC4` -- and goes
one step further by adding each pregnant mother's pending babies:

```asm
004890F0  push ecx / push edx / xor eax, eax
004890F4  mov  edx, 0x50e5ac                 ; first record
004890F9  mov  ecx, 0x96                     ; 150 slots
004890FE  cmp  byte ptr [edx + 0x1cc4], 0    ; occupied?
00489107  add  eax, 1
0048910A  cmp  dword ptr [edx + 0x1c4c], 0   ; pregnant?
00489113  add  eax, dword ptr [edx + 0x1c50] ; + pending babies
00489119  add  edx, 0x2e3c                   ; next record
00489122  jne  0x4890fe
```

That is physical *demand*, not living population -- the distinction recorded in
`docs/duplicate-purchase-guards.md`. A slot reserved for an unborn child counts
as taken, which is what a capacity guard has to do.

The manifest purposes match the disassembly:

| Offset | Purpose |
| --- | --- |
| `0x89020` | keep triplets only when three villager slots remain |
| `0x89040` | keep twins only when two villager slots remain |
| `0x89060` | skip the event newcomer at physical capacity |
| `0x89080` | skip the first barrel child at capacity, retaining the stock later-child cap |
| `0x890C0` | reserve no more than the lesser of six abandoned infants or remaining slots |
| `0x890F0` | count physical demand: occupied records plus each pregnant mother's babies |

## The liveness reasoning still applies

The risky half was never the counter; it was that a guard cannot simply skip a
creation whose return value the caller consumes:

```asm
004148CF  call 0x467D10     ; creates the Island Event newcomer
004148D4  mov  esi, eax     ; <-- the new villager is consumed immediately
```

Skipping that creation and resuming would leave `ESI` stale. The barrel site is
friendlier -- resuming at `0x414DC5` (`mov ecx, 0x50E568`) does not consume
`EAX`. Each guard therefore has a resume target chosen for its own site, which
is why `0x89060`'s purpose says "or resume the complete stock outcome below"
rather than skipping outright. Anyone retuning these must redo that per-site
liveness check; the counter alone is not the hard part.

## This is still NOT the "barrel adds no children" cause

Worth restating now that the guards do fire, because the conclusion is
unchanged while the reasoning has inverted. It used to be "the guards cannot be
the cause because they never skip". It is now "they skip only at genuine
physical capacity" -- and the reported short-spawn happened in a village with
ample free records. So they still do not explain that symptom.

That mechanism -- slot allocation versus world-space placement -- remains open.
See `docs/duplicate-purchase-guards.md` for what is known and what would settle
it.

## Related

- `tests/test_vv5_slot_guard_control_flow.py` pins the corrected VV5 shape and
  the reasoning for when a guard may return versus resume. VV5's bug was the
  mirror image: its guards fired and returned from mid-function, crashing.
