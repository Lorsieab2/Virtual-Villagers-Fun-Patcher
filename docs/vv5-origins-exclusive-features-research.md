# VV5 Origins-Exclusive Features: Exact Research Handoff

## Scope and build identity

This document records the bounded static-analysis results for porting the
Origins-exclusive upgrades to **Virtual Villagers 5: New Believers**. It is a
research handoff, not an implementation manifest. No route described as
unresolved below is safe to advertise as implemented.

- Stock executable:
  `research/stock-executables/Virtual Villagers - New Believers.exe`
- Size: `991232` bytes
- SHA-256:
  `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`
- Image base: `0x400000`

All addresses in this document are virtual addresses for that exact
executable.

## Reusable menu behavior

The proven VV2 implementation uses the companion
`assets/origins/VVFP Origins Icons.dll` and its
`ShowOriginsUpgradeMenuState(mode, state)` export. The same menu contract can
be reused for VV5:

- Tech choices:
  - Time Warp: 50,000 tech points
  - Island Event: 30,000 tech points
  - Barrel of Babies: 75,000 tech points
  - Tech Point Doubler: 500,000 tech points
  - Food Point Doubler: 500,000 tech points
- Selected-villager choices:
  - Grant Youth: 50,000 tech points
  - Grant Full Mastery: 100,000 tech points
  - Grant Running: 40,000 tech points
  - Age to 18: 50,000 tech points

The DLL returns the chosen row or `-1`. Game-specific state changes must remain
inside the VV5 executable patch.

## Save-scoped ownership storage

The legacy statistics block at `0x51D388..0x51D3EF` is copied, serialized per
save, and cleared during new-save initialization. The first dword at
`0x51D388` is suitable for the two doubler ownership bits:

- bit 0: Tech Point Doubler
- bit 1: Food Point Doubler

This keeps ownership confined to the current save. The rest of the reserve
must remain untouched unless separately assigned and documented.

## World, manager, and selected-villager layout

- World base: `0x554148`
- First villager record: `0x554190`
- Villager-record stride: `0x2F44` (`12100`)
- Manager getter: `sub_425950`
- Manager size: `0x17E3C` (`97852`)
- Selected villager index: manager `+0x17E24`
- Resolve villager by index: `sub_46F950`
- Validate villager index: `sub_471840`
- Current believer population count: `sub_4713F0`

The selected record used by the detail screen is:

1. call `sub_425950`;
2. read the index at manager `+0x17E24`;
3. validate it with `sub_471840`;
4. resolve it with `sub_46F950`.

## Selected-villager fields

- Displayed/current age: record `+7052`, in twentieths of a displayed year
- Health: record `+7232`
- Skill preference: record `+7284`
- Six skill fields, all `float`:
  - record `+7260`
  - record `+7264`
  - record `+7268`
  - record `+7272`
  - record `+7276`
  - record `+7280`
- Three normal Like slots:
  - record `+8028`
  - record `+8032`
  - record `+8036`
- Three normal Dislike slots:
  - record `+8040`
  - record `+8044`
  - record `+8048`

Full Mastery must write `90.0f` (`0x42B40000`) to all six skill fields. Writing
the integer `90` would corrupt the VV5 float representation.

Running is normal preference ID `38`. Grant Running must:

1. remove ID 38 from any Dislike slot;
2. add ID 38 only to an actually free normal Like slot;
3. refuse without charging if all three Like slots are occupied;
4. never write movement-speed state.

The age menu actions are not implementation-ready. Although `+7052` is the
field rendered as age, its time-catch-up companion state has not yet been
proven. Writing that field alone is unsafe.

## Resource globals and central award functions

- Food total: `0x51D34C`
- Tech-point total: `0x51D5F8`
- Central food award: `sub_41EB40`
- Central tech-point award: `sub_4237B0`

Only positive ordinary gameplay awards should be doubled. Purchases,
consumption, penalties, and Island Event awards must not be doubled.

There is an existing statistics hook inside the food function at
`0x41EBA7`, whose stock guard is:

`01 37 8B 07 79 0B`

An Origins implementation must compose with that hook or use another proven
site. It must not independently overwrite the same bytes.

The event-result methods in the `0x414A30..0x416CD0` family directly call or
tail-jump to the two central award functions. Tail jumps mean a simple
return-address blacklist is incomplete. An exact exclusion mechanism for all
Island Event results remains unresolved.

## Time Warp

`sub_4036E0` returns the signed difference between current `_time64` and the
base qword at `0x4C6250`. Its backward-clock guard also updates that qword.

The exact clock-base target for Time Warp is therefore:

- base time qword: `0x4C6250`

The upgrade should subtract the chosen number of seconds from this 64-bit
base, using the current game-speed selection to determine the intended
in-game-hour amount. The manager speed field is at `+0x17D7C` and observed
values are `3`, `6`, `10`, with `999` representing pause.

## Island Event and native Barrel of Babies

The next-event timer is manager `+0x17D3C`. Resetting that timer can make the
normal scheduler run an event, but it does not by itself select a specific
event.

The native Barrel of Babies facts are:

- Event index: `30`
- Registered event object: `0x4DC8B8`
- Vtable: `0x497B3C`
- Registration/factory constructor: `sub_417790`
- Assignment of the Barrel vtable: `0x417B53`

The normal scheduler route at `0x442850` is:

1. push the main scene;
2. call `sub_4187F0`;
3. move returned `EAX` into `ECX`;
4. call `sub_418870`.

`sub_418870` builds the eligible-event list, chooses an index, passes
`dword_4DC850[index]` to `sub_418020`, opens the native event through
`sub_401CF0`, and records the seen flag in `byte_4DC814[index]`.

The safest implementation design identified by this pass is:

1. check that the current population has room for all three possible Barrel
   babies;
2. set a one-shot forced-Barrel marker;
3. make the next-event timer due;
4. hook the selection inside `sub_418870` so the one-shot marker replaces the
   chosen index with `30`, then clears itself;
5. let the unchanged native construction, dialog, choice, and result route
   continue.

This design literally uses the built-in Barrel event rather than directly
granting villagers. The exact marker location, selection-site byte guard, and
runtime effective-cap query still require proof before implementation.

## Tech-screen route

- Tech scene constructor: `sub_4405F0`
- Tech scene message handler: `sub_4415F0`
- Stock text-widget factory: `sub_40DD90`
- Stock graphic-button factory: `sub_401BD0`
- Widget registration: `sub_40C680`

The handler accepts only messages where `a1 == 8` and button IDs `0..12`.
Button ID `13` is therefore unused by that handler and is an appropriate
candidate for Upgrades.

The constructor stores and later owns its widgets. A safe additional storage
slot or a proven parent-owned widget route has not yet been established.
Allocating an untracked widget is not approved.

## Detail-screen route

- Detail draw routine: `sub_44B250`
- Detail mouse routine: `sub_44B560`

The draw routine resolves the selected villager through the exact manager
route documented above and renders all six skill fields. The mouse routine
already owns direct coordinate hit-testing for skill preferences and bottom
tabs, so a direct draw-and-hit-test Upgrades control is plausible. Exact
rendering and click-site byte guards have not yet been selected.

## Unresolved safety requirements

The following must be resolved before creating a VV5 Origins manifest or
claiming the feature works:

1. Prove all age/time-catch-up companion fields for Grant Youth and Age to 18.
2. Prove a complete Island Event exclusion mechanism for both doublers,
   including event methods that tail-jump to central award functions.
3. Select a one-shot forced-Barrel marker that is safe, correctly initialized,
   and does not steal save ownership bits.
4. Select and byte-guard the exact event-choice override inside `sub_418870`.
5. Resolve the effective population-cap query for both ordinary and
   experimental-256 builds; the Barrel guard must reserve three slots.
6. Establish safe ownership/storage for an added Tech-screen widget, or prove
   a direct-render alternative.
7. Select exact guarded draw and hit-test hooks for the Detail-screen button.
8. Allocate caves that do not overlap the statistics patch, Heathen Parent
   patch, or any other composable VV5 feature.
9. Define hook composition with the existing food-statistics hook at
   `0x41EBA7`.
10. Perform patched-executable loader, launch, save-load, menu, resource,
    event-exclusion, time-catch-up, and mixed-patch validation.

Until all ten items are satisfied, this work is exact research only.
