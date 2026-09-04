# VV5: read the rendered image, not the manifests

This document records what VV5's Tech-menu rows 0, 1 and 2 actually do in the
shipping build, and one false claim in the manifest. It deliberately makes **no
safety determination** -- see "What this does not establish". Earlier revisions
did try, and were wrong three times running, in both directions.

## The trap

VV5 carries two copies of the Tech-menu handler:

| where | address | status |
| --- | --- | --- |
| base Origins payload; the Task9 record's `0xDB000` patch carries a MODIFIED copy of it | `0x7B2xxx` | superseded at load |
| Task9 stock menu page | `0x7C9000` | **this is what runs** |

Reading `data/vv5_origins_feature.json`, or the `0xDB000` patch inside
`data/vv5_task9_native_actions.json`, shows an old refusal path and leads
straight to the wrong conclusion. The two blobs are NOT interchangeable
either -- the Task9 copy differs from the base payload (it replaces the
handlers at `0x7B22C0` and `0x7B2600` with jumps into the `0x7C9000` page and
changes eligibility bytes), so neither one may be substituted for the other
in an audit. Both were read that way in this repository's
history, by two different people, and both times the answer was wrong.

The only reliable method is to render and disassemble:

```python
rendered, _ = patcher.render_patched_bytes(stock, build, "immediate_fixed", vv5_patches)
```

## What the shipping dispatcher does

```
0x007c98ab  test ebx, ebx
0x007c98ad  je   0x7c9a2a     ; row 0 Time Warp    -> call 0x7ca040
0x007c98b3  cmp  ebx, 1
0x007c98b6  je   0x7c9a37     ; row 1 Island Event -> call 0x7ccc00
0x007c98bc  cmp  ebx, 2
0x007c98bf  je   0x7c9a44     ; row 2 Barrel       -> call 0x7ccf00
```

All three rows are dispatched to real routines. `build_menus` says so --
"enabled only in the stock page layout (0x7C9000)" -- and emits this dispatch
**before** the `cmp ebx, 3 / jb unavailable` the older payload refused with.

In the expanded-256 layout `native_stock` is false, the dispatch is not
emitted, and rows 0..2 do fall through to `unavailable`. One source, two
behaviours.

## Consequence 1: the manifest contradicts the build

```json
"evidence_status": "STOP; no charge or native call is made for these rows"
```

False for the shipping build: a native call is made for each of the three rows.

It is not the only false claim in that file, and correcting only this one would
leave the player-facing behaviour contract wrong:

- the top-level `description` states Time Warp produces exact 3 / 6 / 12-year
  advances and names the speed in its confirmation, which the shipping
  `194400 / speed` routine does not do;
- `task9_contract.actions.time_warp` identifies the companion as the writer,
  which it is not in the stock layout.

`docs/transparency-log.md` republishes that top-level description, so all three
statements are player-facing. Any correction has to cover the set, not just the
STOP sentence. Note that the Time Warp items become TRUE if the live path is
repaired -- so sequence the metadata fix after that repair rather than
describing behaviour that is about to change.

## Consequence 2: VV5's Time Warp is still the original bug

Row 0 calls `0x7CA040`, which is
`build_vv5_task9_native_actions.py::build_time_warp`:

```
0x007ca18e  mov  eax, 0x2f760              ; 194,400
0x007ca198  div  ecx                       ; / speed
0x007ca1ae  sub  dword ptr [0x4c6250], eax ; the global clock, 64-bit
0x007ca1b4  sbb  dword ptr [0x4c6254], 0
```

That is the clamped `194400 / speed`, not the exact 3 / 6 / 12 the other four
games received. **VV5 is the only game where the owner's reported Time Warp
problem is still unfixed.**

The companion routine `vv5_time_warp_apply` is *not* what ships:
`ShowVv5TimeWarp` appears once in the rendered image, inside the `0x7B2000`
page the Task9 page replaces, so it is never called in the stock layout.

## Consequence 3: the Barrel already defers to screen close

Worth knowing before anyone adds a delay to it. `build_barrel` writes **only**
the one-shot pending token (bit 3, value 8, at `0x51D388`) when the purchase
completes. It deliberately does not arm the scheduler while the Upgrades menu
is open. A separate `barrel_close_arm` detour on the Technologies-screen close
handler later consumes that token, sets the forced-Barrel marker (bit 2), and
writes `[manager+0x17D3C] = 0`, so the native index-**26** Barrel event is
presented only after the screen closes. (Slot 25 is `CEventTheStingingWasps`
and slot 26 is `CEventBarrelOBabiesV`, per `tests/test_vv5_barrel_event_index.py`;
forcing 25 is the already-diagnosed wasps-instead-of-children bug.)

The purchase write and the arming write therefore happen at different times, in
different code. Any audit or change here has to keep that ordering in view.

## What this does not establish

This document does **not** determine whether these rows are safe with respect
to the STOP's stated concern, and must not be cited as though it does. Known
gaps:

- **The downstream tick.** Row 0 subtracts from the global epoch without
  advancing any record's `+0x1C38` marker, so the next villager tick processes
  that jump. Absence of an array loop in the dispatched routine proves only
  that it makes no *immediate* record write. The tick has not been traced.
- **The event outcomes.** Rows 1 and 2 make the engine select and run one of
  its own events; `eEventTheMaskResultA` and `eEventTheSpaResultB` change a
  named villager into a Heathen. Those firing naturally establishes stock
  behaviour, not a Believer-only property. The scheduler's target predicate has
  not been traced.
- **The companion path**, if it ever goes live, writes its last-seen marker for
  every active record *before* the faction test, so it deliberately writes
  off-faction records. Its age credit is gated on `+0x1CEC`, which is the
  engine's own test at `0x00470077` on the engine's own field `0x1B8C` -- but
  the marker write would have to be explicitly permitted by whatever contract
  replaces the STOP.

## Field offsets, with their actual status

| field | offset | status |
| --- | --- | --- |
| faction | `+0x1CEC` | the **supported** current-faction predicate |
| mask byte | `+0x1CE1` | listed in `data/equal_division_evidence.json` under `forbidden_routes` as `vv5_unproved_heathen_active_byte` -- **not** a proven Heathen indicator |

Equal Division additionally skips records whose `+0x1CE1` is non-zero. That is a
narrowing of the eligible population, but it must NOT be described as only ever
reducing what gets written: `ApplyVV5EqualDivision` assigns jobs round-robin and
advances per-sex seat counters for eligible records only, so excluding one record
shifts every later assignment and can rewrite a villager whose preference already
matched. Using that byte to *decide* a record is safe to write remains the
forbidden direction, because its meaning is unproved.

## Also worth knowing

`data/vv5_expanded_time_warp.json` is `catalog_enabled: false`, which hides it
from the public catalog but does not make it undeliverable: it is
`enabled: true` with `experimental_explicit_selection: true`, and
`_selected_playtest_disabled_fun_patches` authenticates and returns it on
explicit request in an Expanded-256 mode. Catalog visibility and deliverability
are different questions.
