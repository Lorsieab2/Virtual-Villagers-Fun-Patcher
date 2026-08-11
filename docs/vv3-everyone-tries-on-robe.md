# VV3 Everyone Tries On the Robe

`vv3_everyone_tries_on_robe` is a visible, optional VV3 patch. It is enabled in
the catalog, starts unchecked, and supports all four population modes.

## Exact behavior

The wrapper calls the original robe callback at VA `0x421960` for the dropped
initiator. Fanout occurs only when that callback reports handled (`AL = 1`),
the villager is active (`+0xF10 != 0`), living (signed health `+0xE78 > 0`),
non-nursing (`+0xE8C == 0`), and the original callback leaves action `120` or
`121` in `+0xF24`.

The wrapper then scans the exact runtime bound: 150 stock records or 256
Expanded records. Every other active, living, non-nursing record receives the
stock failed-fit action-121 sequence: random robe-area coordinates, the native
walk queue, and native `sub_455570(121, &scratch)`. The initiator is skipped.
Followers never receive success action 120 and cannot become Tribal Chief.

Failed-fit action 121 supplies the native **Trying on the robe** status, walk,
gestures, and temporary try-on appearance. It does not grant the successful fit,
persistent Chief clothing, Chief state, or puzzle mutation associated with
success action 120.

## Owned transaction

The patch owns exactly three non-checksum ranges:

| Raw range | Stock / Expanded result | Purpose |
|---|---|---|
| `0x280..0x283` | `00 10 00 00` | Widen the existing `.shr` virtual size to one mapped page. |
| `0x22B2A..0x22B2D` | `00 81 6C 00` / `00 11 7A 00` | Register the wrapper at stock VA `0x6C8100` or Expanded VA `0x7A1100`. |
| `0xB4100..0xB41EA` | 235-byte wrapper | Use the reviewed zero-filled portion of `.shr`. |

The payload SHA-256 is
`CC885281A83022F53BD690FF830AC2F779E06E903C2E163508B4C48D64EA4C46`.
The complete 235-byte cave preimage SHA-256 is
`22B94C6893BFC091BE2A9F454A045184DF6C0398CFFA2B4E90C0065DD6EEB1B0`.
The renderer recomputes the PE checksum after composition and after guarded
removal.

Authenticated isolated results are:

| Parent | Result SHA-256 | PE checksum bytes |
|---|---|---|
| Exact stock EXE | `44AEEE623533930404393BE57E8F5EFA84BDE849215141ABD0EE6FDF0ED1FDB2` | `18 9C 0D 00` |
| Reviewed Expanded prototype `6EE3361A...` | `D367A4B9184820328B248F399DBB232092CCEBE6ACC801F49E89E13A7D8B0F4F` | `CF 72 0D 00` |

These isolated hashes are evidence anchors, not universal composition hashes.
The current renderer also applies the selected population/safety transaction
and, in Expanded modes, the reviewed healer, capacity, serializer, Chief-
candidate assignment, and Details roster repairs before computing the final
hash.

## Safety and current runtime boundary

The initiator's original return value is preserved. Unknown runtime bounds,
original callbacks that do not report a handled drop, ineligible initiators,
and initiators outside actions 120/121 return without assigning any follower
action.

A live Expanded defect showed the robe candidate-selection fields at `+0xE80`
and `+0xE88` as zero across the observed restarted village. This broadcast
feature does not read, write, repair, or invent either field. In both Expanded
modes, the patcher separately and automatically applies the guarded
Chief-candidate assignment repair; it composes disjointly and is not a
selectable feature dependency. If the fields are still zero before automatic
assignment, or no eligible candidate exists, the original callback correctly
chooses native failed-fit action 121 for the initiator and eligible followers
receive that same failed-fit action without granting Chief state.

Static install, removal, exact-byte, checksum, collision, ordinary composition,
Expanded composition, and repaired Details-layout tests are automated. Player
runtime confirmation remains pending.
