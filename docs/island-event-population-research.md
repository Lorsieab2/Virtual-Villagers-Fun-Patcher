# Virtual Villagers 1–5 Island Event population audit

Evidence status: static code-confirmed for the five exact Windows executables listed in `data/builds.json`. Player-facing event names are used only where the executable mapping was resolved. Developer intent is not inferred.

## Result

All five games contain Island Event outcomes that can add villagers. Several stock paths check population only when the event is selected, or only before the first of several allocations. Population can change before the outcome resolves, and repeated calls can therefore cross the physical record limit.

The patcher now applies event-capacity safety automatically:

- VV1 and VV2 guard each identified direct event allocation against 256 physical slots.
- VV3, VV4, and VV5 recheck physical capacity before an outcome's formerly unconditional first arrival.
- VV4 and VV5 clamp Abandoned Infants from six reservations to the physical slots remaining.
- Event selection, text, random choice, villager attributes, and non-population outcomes remain unchanged.
- Events that remove a villager remain unchanged.
- VV5 conversion and The Defector remain unchanged because they reclassify an existing record.

## VV1 — A New Home

`sub_427B90` implements Barrel O' Babies with one, two, or three direct calls to `sub_43C350`. `sub_42B740` contains Mysterious Crate infant outcomes with one, two, or three direct calls to the same allocator. Their twelve direct call sites now pass through a private wrapper that checks the 256-record population before every allocation.

`sub_419380` contains a Mysterious Face newcomer after a stock cap predicate. Other observed branches deactivate the selected villager, including disappearance outcomes associated with the Mysterious Face and Mysterious Book and a lethal Strange Berries outcome. Subtractive outcomes are not modified.

## VV2 — The Lost Children

`sub_433600` contains Barrel O' Babies with one, two, or three calls to `sub_44F580`, plus a separate two-newcomer outcome with two calls. Those eight calls now use a private per-record 256-slot wrapper.

The Crystal/mirror clone in `sub_4204B0` already uses a stock cap predicate. Secret-admirer pregnancy routes through `sub_44B980`, which performs its own population check. Those already-guarded routes are not redirected.

## VV3 — The Secret City

`sub_414D90` creates one adult after an earlier eligibility check, but the outcome originally allocated unconditionally. `sub_415320`, Another One of Those Barrels, created its first child unconditionally and checked only before later children.

Both outcomes now compare the physical aggregate with 150 immediately before the first allocation. Below capacity they resume the original function. Once the first child fills the final slot, the stock later-child check stops additional allocations.

## VV4 — The Tree of Life

`sub_4148B0` creates one adult unconditionally. `sub_414D90`, Daredevil Barrel, creates an unconditional first child followed by checked later children. `sub_414FC0`, Abandoned Infants, requests six pending babies through `sub_467B00`.

The adult and barrel outcomes now recheck the 150-slot physical aggregate. Abandoned Infants now passes `min(6, 150 - occupied)` to the original reservation helper and reserves none at capacity.

## VV5 — New Believers

Mapped additions:

- `CEventBarrelOBabiesV` / `sub_4151D0`: up to three believer children;
- `CEventBarrelOHeathenBabiesV` / `sub_4152B0`: up to three Heathen children;
- `CEventChutesWithoutLadders` / `sub_415410`: up to three believer children;
- `CEventNewsFromAnotherTribe1` / `sub_415510`: one adult after an existing outcome-time check;
- `CEventAbandonedInfants` / `sub_4155E0`: up to six pending babies through `sub_471A50`;
- `CEventTheDefector`: reclassifies an existing Heathen and allocates nothing.

The first three outcomes now call the physical-demand counter before their formerly unconditional first child. The counter includes every active record, regardless of faction, plus pending nursing babies. Abandoned Infants passes `min(6, 150 - demand)` to the original helper. News From Another Tribe retains its existing check. The Defector is unchanged.

## Boundary behavior

- no slots remaining: no new record or reservation;
- one slot remaining: at most one arrival;
- two slots remaining: at most two arrivals;
- enough slots remaining: the stock outcome is unchanged.

This guards physical arrays, not a lower collection-progression breeding cap. A stock Island Event can still take the village above that lower breeding cap when physical room remains.
