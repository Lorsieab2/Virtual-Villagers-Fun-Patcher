# VV5 native time/event rows: the Heathen-safety STOP, and the evidence that clears it

VV5's Tech-menu rows 0, 1 and 2 -- Time Warp, Island Event and Barrel of
Babies -- are refused before any charge, and the manifest says why:

```json
"native_event_safety": {
  "disabled_rows": ["Time Warp", "Island Event", "Barrel of Babies"],
  "reason": "VV5 native time/event paths are not yet proven to avoid current Heathen record targeting.",
  "evidence_status": "STOP; no charge or native call is made for these rows"
}
```

The declaration is accurate, not stale. In the record that actually ships
(`data/vv5_task9_native_actions.json`, `catalog_enabled: true`) the refusal is
unconditional:

```
007b234e  cmp  ebx, 3
007b2351  jb   0x7b23bb        ; rows 0,1,2 -> preflight

007b23bb  call 0x425950
007b23c0  mov  edi, eax
007b23c2  cmp  ebx, 2
007b23c5  ja   0x7b23d1        ; NOT taken for rows 0,1,2
007b23c7  mov  eax, 0x7b2e0c   ; "Unavailable: this VV5 native path is
007b23cc  jmp  0x7b2523        ;  not verified safe for Heathens." -> status
```

Because the `ja` is not taken for rows 0..2, the `cmp ebx, 0` at `0x7b23d1`
(Time Warp) and the barrel capacity gate after it are unreachable, as is the
Time Warp companion call in `legacy_charge`. That code is correct; it simply
sits behind a closed gate.

`data/vv5_expanded_time_warp.json` is **not** an alternate delivery path for
Time Warp: that record is `catalog_enabled: false`.

## What the STOP's reason actually requires

VV5 distinguishes villagers by two independent record bytes, per the Equal
Division contract, which is the established safe pattern in this codebase:

| field | offset | meaning |
| --- | --- | --- |
| Heathen mask | `+0x1CE1` | non-zero = masked Heathen |
| faction | `+0x1CEC` | non-zero = off-faction |

"Heathen record targeting" therefore means: writing villager records without
respecting those. A feature that writes **no** villager record cannot target
anything, and a feature that writes them under the engine's own rule is by
definition no more dangerous than the base game.

## Row 1, Island Event: writes no villager record at all

```
island_event:
    mov dword ptr [edi + 0x17D3C], 0
    jmp success
```

One dword, on the **manager**, not a villager. It makes the game's own
island-event scheduler due. What follows is the engine's own native event code,
which fires spontaneously on its own schedule anyway. If that path were unsafe
for Heathens, unmodified VV5 would already be unsafe.

## Row 2, Barrel of Babies: also writes no villager record

```
barrel:
    or  dword ptr [0x51D388], 4      ; patch-owned flag word
    mov dword ptr [edi + 0x17D3C], 0 ; the same manager countdown
    jmp success
```

A patch-owned flag plus the same manager countdown. No villager record is
touched; the spawn is the engine's own.

## Row 0, Time Warp: writes records, under the ENGINE's own rule

This is the only one of the three that iterates villager records, so it is the
only one where the question is real. `vv5_time_warp_apply` writes two things:

1. **The age credit**, gated on faction:

   ```c
   /* Only the faction the engine ages gets the credit (0x00470077). */
   if (rec[VV5_TW_FACTION_OFFSET] != 0) continue;   /* 0x1CEC */
   ...
   *(int *)(rec + VV5_TW_AGE_OFFSET) += units * rate;   /* 0x1B8C */
   ```

2. **The last-seen marker**, for every occupied record.

The gate is not an invention. It is the engine's own test, on the engine's own
field, at the address the comment cites:

```
0x00470077  cmp  byte ptr [esi + 0x1cec], bl   ; faction == 0 ?
0x0047007f  jne  0x47008d                      ; otherwise no age credit
0x00470082  lea  ecx, [esi + 0x1b8c]           ; the age field
0x00470088  call 0x46f7f0                      ; apply the credit
```

Same field (`0x1CEC`), same test, same target (`0x1B8C`). Note that the engine
filters on **faction only** and not on the Heathen mask at `0x1CE1`, so
matching the engine -- rather than adding a mask test the engine does not have
-- is the correct behaviour. Time Warp cannot age a villager the base game
would not age.

The last-seen marker is deliberately universal, and skipping it would be the
harmful choice, not the safe one: that marker is what stops a villager's own
tick from putting the jump through the aging clamp. Omitting it would not hold
that villager's age, it would advance them by the clamped amount.

## Conclusion

| row | villager-record writes | verdict |
| --- | --- | --- |
| 1 Island Event | none (one manager countdown) | cannot target any record |
| 2 Barrel of Babies | none (patch flag + same countdown) | cannot target any record |
| 0 Time Warp | age credit + last-seen marker | credit gated by the engine's own faction test at `0x00470077`, on the engine's own field |

The STOP's stated reason -- "not yet proven to avoid current Heathen record
targeting" -- is answered for all three. Two of them provably touch no villager
record, and the third writes only under the rule the engine applies every tick.

The owner has also confirmed from play that VV5 behaved correctly and that
these paths already target Believers only.

## What still depends on the gate

While it is closed, all of the following are inert in VV5 even though the code
for them exists and is correct:

- Time Warp's exact per-speed advance (its per-villager rate handling is VV5-specific).
- The Island Event and Barrel queue delay that VV1, VV2 and VV4 received.
- The barrel's three-children behaviour, its free-slot purchase block, and its
  capacity disclaimer -- the owner asked for these across all five games.
