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

### Exact-build invocation facts (disassembly of the 991,232-byte build)

- The action-90 precharge at `0x46CEC7` is `push 0xFFFFEC78` (−5,000);
  `mov ecx, 0x51D5F8`; `call 0x4237B0` — the same tech-point charge routine
  Time Warp uses. It then does `mov ecx,[edi+0x1B88]`; `mov esi,[ecx+0x1C94]`
  (the villager slot index); `call 0x425950`; `mov [manager+0x17E08], esi` —
  i.e. it **precharges, then stashes the pending slot index** into
  `manager+0x17E08` for the chooser to read later.
- The chooser `sub_419EC0` is an **async C++ object constructor** (thiscall,
  `this` in ECX, one pushed arg, full SEH frame, installs vtable
  `0x49859C`). It builds a UI object that the **game loop** drives; it is not
  a blocking modal that can be called synchronously and returns a result.

### Why this is not a clean, robustly-safe reuse

Because precharge (`0x46CEC7`) and chooser-open (`sub_419EC0`) are separated by
the game loop, the pending slot at `manager+0x17E08` can go stale before the
chooser opens, and the open path does not re-verify occupancy, health, status,
identity, or **faction**. So faithfully reusing the native flow inherits that
revalidation gap: a believer-only guarantee cannot be enforced purely by a
pre-open gate. Enforcing it robustly requires the **custom OK-time revalidation
route** (private preview, atomic commit, re-checked eligibility) that the
appearance contract lists as **unproved** — it is more than "wire the native
action". This is the real cost of a robustly-safe believer-only Change Outfit.

## Change Head catalog — now PROVEN (static + art)

The head catalog that was previously unproved is now established for the exact
991,232-byte build:

- **Valid head indices are `0..29` (30 heads).** The constructor at `0x468560`
  sets the head from either parent inheritance (average of the two parents'
  heads ± `RNG(3)-1`, at `0x46856D`) or a flat `RNG(30)` (`0x468591`), and every
  path **clamps to `0..29`** (`0x46859B`: `< 0 -> 0`, `>= 0x1E -> 0x1D`). The
  sex-specific tables in the constructor drive the body/outfit sub-ranges and
  bias which heads spawn naturally; they do **not** gate head validity.
- **Complete art exists for all 30 indices, both sexes and both ages.** The
  world atlases `male_heads00/10.png` and `female_heads00/10.png` are each
  320x1950 = **30 rows @ 65px** (8 directional frames per row); the Detail
  portraits `BigHeads00/10.png` are 480x3000 = **30 rows @ 100px**. `00` = young,
  `10` = old is an atlas swap on the **same** index, so changing a head is
  age-safe. Visual inspection confirms all 30 rows are distinct, populated heads
  with no blank/placeholder rows.
- The head field `record+0x1BB8` is constructed, inherited, cloned, saved/loaded
  and rendered (world + Detail); persistence matches the proven outfit field.
- Masks (`vv5_heathenheads.png`) are a separate faction overlay, not part of the
  head index.

So a Change Head that offers indices `0..29` writes only renderable, in-range,
persistent values for the villager's own sex. There is still **no native head
chooser or head-specific 5,000 transaction** (the only native 5,000 purchase is
the outfit action), so a head picker must be custom; and per the contract the
picker should warn "This will change the villager's head genetics."

Residual gate: a short in-game pass to confirm the 30 indices render (world +
Detail) and survive save/reload, and that no index is reserved for a special
villager (e.g. the Golden Child). High confidence given complete art, but this
is the only step that needs the running game.

## Recommended path

1. **Ship believer-only Change Outfit first** (body). The outfit *field* write
   and cost are proven and save-safe, but the native chooser is async with a
   revalidation gap (above), so a robust believer guarantee needs a custom
   OK-time revalidation route. Two build options:
   a. **Custom believer-safe chooser** (recommended for correctness): a task9
      row that, for the selected active/living Believer, opens a preview,
      cycles the proven `0..28` outfit field, and on OK re-validates identity +
      faction `+0x1CEC` and charges 5,000 once. Larger; this is the contract's
      previously-unproved custom route, now scoped by the invocation facts above.
   b. **Gated native invocation** (smaller, weaker): precharge + open the native
      `sub_419EC0` behind a pre-open believer gate, accepting the native
      staleness/no-revalidation flaw. Not robustly believer-guaranteed.
   Either option also needs a new Villager Upgrades dialog row (companion DLL
   `row_count` 4→5 + a fifth Buy control, rebuilt with the installed MSVC/SDK
   toolchain), which cascades the load-bearing companion-DLL hash.
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
