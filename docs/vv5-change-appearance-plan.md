# VV5 Change Appearance — safest implementation plan

Requested feature: a Villager Upgrades window showing the selected villager's
**body and head**, each with left/right arrows that loop through options; **OK**
applies the shown head+body and deducts **5,000 tech points once**; insufficient
funds changes nothing and shows "Not enough tech points". Believer-only.

This records the safest split after the exact-build audit. No binary changes are
made by this document.

## What is safe today: Change Outfit (body), believer-only

The VV5 build has a **native, save-safe outfit transaction** (action 90):

- Recheck + precharge exactly 5,000 at `0x46CEC7`/`0x46CED1`, then open
  `sub_419EC0`.
- `sub_419CE0` cycles and immediately writes the DWORD body/outfit field at
  `record+0x1BBC` (stride `0x2F44`) over exactly `0..28`, wrapping both ways.
- Accept keeps the write (button `+0x50`). Cancel (button `+0x5C`) restores the
  original field at `0x419E8E` and **refunds** exactly 5,000 at
  `0x419E94`/`0x419E9E` — a net-zero cancel. The +5,000 clothing refund return
  is `0x419EA3` (already excluded from the Tech Doubler whitelist).
- The field persists through the `+0x1B8C` save/load span and is copied through
  clone/summary; world, Detail, and chooser preview renderers consume it.

So body/outfit cycling, the 5,000 cost, cancel/refund, catalog bounds, and
save/load are **already proven and native** — exactly the mechanics the request
wants. The **only** gap versus the request is eligibility: the native path does
**not** test current faction `+0x1CEC`, so it does not enforce believer-only or
refuse current Heathens.

Safest implementation = add the believer gate on top of the native transaction,
mirroring the task9 eligibility order already used by the other upgrades
(`+0x1CD4` active ≠ 0, `+0x1CE1` mask == 0, `+0x1CEC` faction == 0, `+0x1C40`
signed health > 0), evaluated **before** the outfit chooser opens or charges;
a current Heathen is refused with no charge and no write. This reuses the game's
own atomic, save-safe outfit writer rather than a new custom persistence path.

## What is NOT safe yet: Change Head

- The head field is DWORD `record+0x1BB8`; it is constructed, inherited,
  cloned, saved/loaded, and rendered (age `>=1100` selects the native `+8` old
  row). But there is **no native head-specific 5,000 transaction and no native
  head chooser** — the only native 5,000 purchase is the clothing/outfit action.
- The complete **young/old/special/invalid head catalog is unproved**. The
  constructor's `RNG` bounds are creation bounds, not a proven list of
  user-selectable, persistently-safe heads. Writing an unvalidated index into
  `+0x1BB8` risks selecting special/invalid heads with unknown effects.
- Per the appearance contract, Change Head therefore **remains STOP** for VV5
  until the exact selectable head catalog and its persistence are independently
  proved, and it must warn "This will change the villager's head genetics."

## Recommended path

1. **Ship believer-only Change Outfit first** (body), wired as a Villager
   Upgrades row that runs the native outfit transaction behind the task9
   believer/active/living gate. This is fully spec-compliant for the body and
   uses only proven, save-safe native writes.
2. **Defer Change Head** until the selectable head catalog is proved. When the
   catalog is proved, add head cycling with its own 5,000 charge (or a combined
   single-charge OK if a safe atomic two-field commit is proved) plus the
   genetics warning.

A single combined dialog charging 5,000 once for **both** head and body — as
originally described — depends on the unproved head catalog and a proven atomic
two-field OK/Cancel commit, so it stays behind step 2. Splitting the deliverable
this way keeps every shipped write on a proven, reversible, save-safe path.

## Cross-cutting

- Believer-only, selected-active-living, validate-before-charge: same guard as
  the shipped task9 actions.
- Wire on the isolated review branch; the task9 detail menu and companion DLL
  are under active concurrent work, so reconcile at merge.
- Runtime/player confirmation remains pending (no game launched).
