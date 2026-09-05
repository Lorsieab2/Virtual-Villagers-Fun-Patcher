# VV4's 150-slot safety guards read a lifetime total; now they count

Recorded 2026-08-31 while investigating the reported VV4 Barrel of Babies
behaviour ("the event cues but no children are added"), **corrected twice
since**. Read the correction notice before the history.

> **This file has carried a wrong explanation twice.** It was originally
> titled "VV4's 150-slot safety guards never fire" and claimed nothing wrote
> `0x4D6DE8`. That was a disassembly error, already corrected in
> `tests/test_slot_guard_population_source.py`; a later edit to this file
> reintroduced it. The address *is* written. The guards were never inert --
> they eventually fire forever. Both the finding and the fix below are stated
> against verified bytes.

## What was actually wrong

All five guards decided from a single static address:

```asm
00489080  cmp dword ptr [0x4D6DE8], 0x96   ; barrel first child
0048908A  jge 0x489096                     ; skip when "full"
```

`0x4D6DE8` **is written**, by a single instruction:

```asm
0045E91C  add dword ptr [0x4d6de8], ecx    ; ecx = [record+0x1C50]
```

where `[record+0x1C50]` is how many babies a confirmed pregnancy still owes.
Nothing anywhere **decrements** it -- the address appears exactly once in the
image -- so it is a **lifetime total of babies ever conceived**, not live
demand.

The consequence is the opposite of inertness. Early in a save the total is
below 150 and the guards never fire; once enough babies have ever been
conceived it passes 150 permanently, and from then on the guards suppress
twins, triplets, event children and barrel children **for the rest of that
save**, no matter how empty the village is.

### The decoding mistake, kept deliberately

The "nothing writes it" claim came from decoding at an arbitrary byte offset.
Starting one byte late turns `01 0D E8 6D 4D 00` into `0D E8 6D 4D 00`:

```asm
0045E91C  add dword ptr [0x4d6de8], ecx    ; real boundary -- a writer
0045E91D  or  eax, 0x4d6de8                ; one byte late -- writer vanishes
```

Both decode cleanly and both re-synchronise at `0x45E922`, which is why the
wrong one looked plausible. **Always decode forward from a boundary you
reached by disassembly, never from an address of interest.** VV3's `0x5824A8`
has the identical shape (`add [0x5824A8], ecx`) and the identical trap.

## Current state: the guards use a real counter

All five now call a record-counting helper. Verified by disassembling a
rendered VV4 executable, not by reading the generator:

```asm
00489020  call 0x4890f0 ; cmp eax, 0x93 ; jg  ...   ; triplets
00489040  call 0x4890f0 ; cmp eax, 0x94 ; jg  ...   ; twins
00489060  call 0x4890f0 ; cmp eax, 0x96 ; jge ...   ; event newcomer
00489080  call 0x4890f0 ; cmp eax, 0x96 ; jge ...   ; first barrel child
004890C0  call 0x4890f0 ; neg eax ; add eax, 0x96   ; abandoned infants
```

The helper at `0x4890F0`, complete rather than abbreviated -- the conditional
jumps and the loop decrement matter, because without them the listing would
read as counting inactive records and adding babies regardless of pregnancy:

```asm
004890F0  push ecx
004890F1  push edx
004890F2  xor  eax, eax
004890F4  mov  edx, 0x50e5ac                 ; first record
004890F9  mov  ecx, 0x96                     ; 150 slots
004890FE  cmp  byte ptr [edx + 0x1cc4], 0    ; occupied?
00489105  je   0x489119                      ;   no -> next record
00489107  add  eax, 1
0048910A  cmp  dword ptr [edx + 0x1c4c], 0   ; pregnant?
00489111  je   0x489119                      ;   no -> next record
00489113  add  eax, dword ptr [edx + 0x1c50] ; + babies still owed
00489119  add  edx, 0x2e3c                   ; next record
0048911F  sub  ecx, 1
00489122  jne  0x4890fe
00489124  pop  edx
00489125  pop  ecx
00489126  ret
```

That is live physical **demand** -- occupied records plus babies owed -- and it
falls as villagers die, which the lifetime total never did.

| Offset | Purpose |
| --- | --- |
| `0x89020` | keep triplets only when three villager slots remain |
| `0x89040` | keep twins only when two villager slots remain |
| `0x89060` | skip the event newcomer at physical capacity |
| `0x89080` | skip the first barrel child at capacity, retaining the stock later-child cap |
| `0x890C0` | reserve no more than the lesser of six abandoned infants or remaining slots |
| `0x890F0` | count physical demand: occupied records plus each pregnant mother's babies |

## The liveness reasoning still applies

The counter was never the risky half. A guard cannot simply skip a creation
whose return value the caller consumes:

```asm
004148CF  call 0x467D10     ; creates the Island Event newcomer
004148D4  mov  esi, eax     ; <-- consumed immediately
```

Skipping that and resuming would leave `ESI` stale. The barrel site is
friendlier: resuming at `0x414DC5` (`mov ecx, 0x50E568`) does not consume
`EAX`. Each guard therefore has a resume target chosen for its own site, which
is why `0x89060` resumes the complete stock outcome rather than skipping
outright. Anyone retuning these must redo that per-site liveness check.

## Still outstanding: the runtime playtest

Everything above is **static evidence** -- rendered disassembly and automated
tests. The original plan's fourth step was a playtest of a full village
against every affected event, and that has not happened.
`docs/island-event-population-research.md` still classifies these guards as
code-confirmed only. Do not treat this document as player-tested.

## Relationship to the reported symptoms

The old guard **could** have caused VV4's "event presents, no children" report:
once the lifetime conception total passed 150 it suppressed children
permanently, regardless of free records. That is a live hypothesis for VV4, not
a ruled-out one.

It must not be conflated with the **VV2** short-spawn recorded in
`docs/duplicate-purchase-guards.md`. That reproduction -- 31 living villagers
against a 256-slot pool -- is a different game with a different mechanism, and
it remains unexplained. Applying the VV2 measurement to VV4 would be a category
error; each needs its own evidence.

## Related

- `tests/test_slot_guard_population_source.py` -- why a guard must count rather
  than read a running total, for both VV3 and VV4.
- `tests/test_vv4_slot_guards_use_a_real_counter.py` -- pins the guards and the
  counter against the rendered image.
- `tests/test_vv5_slot_guard_control_flow.py` -- VV5's mirror bug, where guards
  fired and returned from mid-function.
