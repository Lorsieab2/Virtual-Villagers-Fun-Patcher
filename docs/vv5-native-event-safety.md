# VV5 native time/event rows: what actually ships, and what the manifest claims

VV5's manifest declares that three Tech-menu rows are switched off:

```json
"native_event_safety": {
  "disabled_rows": ["Time Warp", "Island Event", "Barrel of Babies"],
  "reason": "VV5 native time/event paths are not yet proven to avoid current Heathen record targeting.",
  "evidence_status": "STOP; no charge or native call is made for these rows"
}
```

**In the layout that ships, that declaration is false.** Rows 0, 1 and 2 are
dispatched to real routines and a native call is made for each. The transparency
log is generated from this metadata, so it currently tells players the opposite
of what the build does.

## How to check this correctly

This is easy to get wrong, and it was got wrong twice -- once in each direction
-- before being settled. The trap is that VV5 carries **two** copies of the
Tech-menu handler:

| where | address | status |
| --- | --- | --- |
| base Origins payload, also embedded in the Task9 record's `0xDB000` patch | `0x7B2xxx` | replaced at load; its refusal is dead for the stock layout |
| Task9 stock menu page | `0x7C9000` | **this is what runs** |

Reading `data/vv5_origins_feature.json`, or the `0xDB000` patch inside
`data/vv5_task9_native_actions.json`, shows the old refusal and leads to the
wrong conclusion. The only reliable method is to render the game and
disassemble the result:

```python
rendered, _ = patcher.render_patched_bytes(stock, build, "immediate_fixed", vv5_patches)
```

Rendered, at the stock page:

```
0x007c98a0  mov    ebx, eax
0x007c98a2  cmp    ebx, 0xd
0x007c98a5  ja     0x7c9aeb
0x007c98ab  test   ebx, ebx
0x007c98ad  je     0x7c9a2a     ; row 0 Time Warp     -> call 0x7ca040
0x007c98b3  cmp    ebx, 1
0x007c98b6  je     0x7c9a37     ; row 1 Island Event  -> call 0x7ccc00
0x007c98bc  cmp    ebx, 2
0x007c98bf  je     0x7c9a44     ; row 2 Barrel        -> call 0x7ccf00
```

`build_vv5_task9_native_actions.py::build_menus` says so in as many words --
"Time Warp (row 0), Island Event (row 1), and Barrel of Babies (row 2) are
enabled only in the stock page layout (0x7C9000)" -- and emits `tw_dispatch`
**before** the `cmp ebx, 3 / jb unavailable` that the older payload used to
refuse them with.

The refusal is not dead everywhere. In the expanded-256 layout `native_stock`
is false, `tw_dispatch` is empty, and rows 0..2 do fall through to
`unavailable`. So the same source produces a gated menu there and an open menu
in stock.

## The Expanded-256 delivery path is not closed either

`data/vv5_expanded_time_warp.json` is `catalog_enabled: false`, which hides it
from the public catalog but does **not** make it undeliverable: the record is
`enabled: true` with `experimental_explicit_selection: true`, and
`_selected_playtest_disabled_fun_patches` authenticates and returns it when its
feature id is explicitly requested in an Expanded-256 mode. Catalog visibility
and deliverability are different questions and should not be conflated.

## The Heathen-safety question the STOP names

Independently of whether the rows are gated, the reason the STOP gives is worth
answering, because it is the standard any future change here has to meet. VV5
marks villagers with two independent record bytes, per the Equal Division
contract:

| field | offset | status |
| --- | --- | --- |
| faction | `+0x1CEC` | the **supported** predicate: non-zero = off-faction |
| mask byte | `+0x1CE1` | **not** a proven Heathen indicator -- see below |

`+0x1CEC` is the only offset this repository treats as an authoritative
current-faction test. `+0x1CE1` is explicitly listed in
`data/equal_division_evidence.json` under `forbidden_routes` as
`vv5_unproved_heathen_active_byte`, so it must not be used as *the* Heathen
predicate, and this document does not claim it is one.

The distinction is between skipping more and deciding more. Equal Division
additionally skips records whose `+0x1CE1` is non-zero, which is conservative:
declining to touch extra records can only reduce what a feature writes. Relying
on that byte to *decide* that a record is safe to write would be the forbidden
direction, because the byte's meaning is unproved.

**Time Warp**: the row that ships does not touch villager records at all.

Row 0 calls `0x7CA040`, and the emitted page there is
`build_vv5_task9_native_actions.py::build_time_warp` -- the ORIGINAL
implementation, still live:

```
0x007ca18e  mov  eax, 0x2f760              ; 194,400
0x007ca198  div  ecx                       ; / speed
0x007ca1ae  sub  dword ptr [0x4c6250], eax ; the global clock, 64-bit
0x007ca1b4  sbb  dword ptr [0x4c6254], 0
```

It writes only the world clock. It does not resolve `ShowVv5TimeWarp`, and it
never iterates the villager array, so it cannot target a Heathen record by
construction. Note this also means VV5 still has the ORIGINAL Time Warp bug the
owner reported: a clamped `194400 / speed`, not the exact 3 / 6 / 12.

There is a second, companion implementation -- `vv5_time_warp_apply` in
`native/vv5_task9_origins/vv5_task9_origins.c` -- which does iterate records.
**It is not what ships.** `ShowVv5TimeWarp` appears once in the rendered image,
inside the `0x7B2000` page that the Task9 stock page replaces, so it is never
called in the stock layout. Two earlier revisions of this document analysed
that routine as though it were the shipping row; it is not, and its behaviour
says nothing about what players currently get.

For whenever that companion path does become live, its record handling has to
be assessed on its own terms, and it does NOT trivially satisfy the STOP:

```c
*(int *)(rec + VV5_TW_LAST_SEEN_OFFSET) += delta;   /* EVERY active record */
if (rec[VV5_TW_FACTION_OFFSET] != 0) continue;      /* only THEN the faction test */
```

The age credit is gated on `+0x1CEC`, which is the engine's own test at
`0x00470077` on the engine's own field `0x1B8C`, and that part is sound. But
the last-seen marker is written for every active record **before** the faction
check, so it deliberately writes current off-faction and Heathen records.
Explaining why that write is necessary -- omitting it would advance the
villager by the clamped amount instead of holding them -- justifies the design;
it does not by itself satisfy a STOP whose stated requirement is to avoid
Heathen record targeting. Before that path is used as evidence for anything,
the contract has to explicitly permit and validate this marker write.

**Island Event and Barrel** write no villager record *at the trigger*: the
island row sets one dword on the manager (`[edi+0x17D3C]`), and the barrel adds
a patch-owned flag (`0x51D388`) plus the same countdown.

That is a claim about the trigger, not about the whole action, and the
distinction matters. Making the scheduler due causes the engine to select and
run one of its own events, and some VV5 events do change villagers --
`eEventTheMaskResultA` and `eEventTheSpaResultB` among them turn a named
villager into a Heathen. Those events also occur spontaneously in an unpatched
game, which establishes that the behaviour is stock; it does **not** by itself
establish the Believer-only property the STOP's wording asks for. Anyone
relying on this section for a stronger claim needs to trace the scheduler's
target predicate and the individual event outcomes, which this document does
not do.

## What should happen

0. **VV5's Time Warp is still the original bug.** The shipping row divides a
   clamped `194400 / speed` and never reaches the exact 3 / 6 / 12 work done
   for the other four games. VV5 is the only game where the owner's reported
   Time Warp problem is still unfixed.
1. The `native_event_safety` block should be corrected to describe the shipping
   build. As written it is a false published contract, and it feeds the
   transparency log.
2. If the three rows are meant to be live -- and they are live, and the owner
   reports VV5 playing correctly -- the metadata should say so, with the
   faction-gate evidence above as the basis for Time Warp.
3. If any row is meant to remain gated, the stock layout has to actually gate
   it, because today it does not.
