# VV4's 150-slot safety guards never fire

Recorded 2026-08-31 while investigating the reported VV4 Barrel of Babies
behaviour ("the event cues but no children are added").

## Finding

VV4 has five automatic safety patches meant to stop child-creating events from
running past the 150 physical villager slots. Every one of them decides using a
single static address:

```asm
00489080  cmp dword ptr [0x4D6DE8], 0x96   ; barrel first child
0048908A  jge 0x489096                     ; skip when full
```

**Nothing ever writes `0x4D6DE8`.**

- In the stock executable it has exactly one byte-pattern match, and that is a
  coincidence inside the immediate operand of `or eax, 0x4d6de8` at `0x45E91D`
  -- not a reference to the variable at all.
- Its initial `.data` value is `0`.
- Searching every manifest, the only patch rows that mention it are the five
  guards themselves, and all five only **read** it.

So the comparison is always `0 >= 150`, which is false, and the guards always
take the "resume" path. VV4's physical-slot protection does nothing.

| Guard | Purpose | Actual behaviour |
|---|---|---|
| `0x489020` | keep triplets only when three slots remain | always keeps |
| `0x489040` | keep twins only when two slots remain | always keeps |
| `0x489060` | skip the Island Event newcomer at capacity | never skips |
| `0x489080` | skip the first barrel child at capacity | never skips |
| `0x4890C0` | clamp Abandoned Infants to remaining slots | always reserves six |

This is the mirror image of the VV5 bug fixed alongside it: VV5's guards fired
and then returned from mid-function, crashing; VV4's guards never fire at all.

## This is NOT the "barrel adds no children" cause

Because the guards never skip, they cannot be why the barrel produces no
children. That symptom is still unexplained and remains open.

## Why this was not "fixed" in the same pass

Giving VV4 a real counter is easy -- VV5's `0x4944C0` sweeps records at base
`0x554190`, stride `0x2F44`, active `+0x1CD4`, and VV4's equivalents are base
`0x50E5AC`, stride `0x2E3C`, active `+0x1CC4`. There is free zero padding at
`0x4890F0` to hold it.

Making the guards actually fire is the risky half, and at least one site cannot
be skipped naively:

```asm
004148CF  call 0x467D10     ; creates the Island Event newcomer
004148D4  mov  esi, eax     ; <-- the new villager is consumed immediately
```

Skipping that creation and resuming leaves `ESI` holding a stale value that the
rest of the function then uses. The barrel site is friendlier -- resuming at
`0x414DC5` (`mov ecx, 0x50E568`) does not consume `EAX` -- but the Island Event
and the twin/triplet sites each need their own liveness check first.

Turning these on without that analysis would convert a latent no-op into a live
crash, which is strictly worse than the current state. The correct sequence is:

1. Add the record-counting helper at `0x4890F0`.
2. For each of the five sites, establish what the creation's return value feeds
   and what the skip path must therefore leave in registers.
3. Give each guard a resume target proven safe for that site, exactly as the
   VV5 guards now do.
4. Playtest a full village against every affected event.

## Related

- `tests/test_vv5_slot_guard_control_flow.py` pins the corrected VV5 shape and
  the reasoning for when a guard may return versus resume.
