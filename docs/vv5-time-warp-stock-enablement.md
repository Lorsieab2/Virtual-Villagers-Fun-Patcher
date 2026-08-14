# VV5 Time Warp — stock Tech-menu enablement plan

Goal: make **Time Warp** an available "Buy" row in the VV5 stock Origins
Tech menu (currently ships **Unavailable**), advancing the village by exactly
**three displayed villager years regardless of the listed game speed**, for a
single verified 50,000 tech-point charge.

Status: reverse-engineering complete; implementation authorized (owner said
"Time Warp first" and "my changes override Codex"). Not yet wired into the
stock page. Runtime/player confirmation still pending (no game was launched).

## The mechanism already exists and matches spec

`scripts/build_expanded_time_warp.py` (`build_vv5_overlay`, lines ~516–670)
contains a fully static-reviewed VV5 Time Warp dispatcher. It is only wired
into the **expanded-256** page (`page_va = 0x904000`) and its map lists
`"stock Task9 page"` under `forbidden_mutations`, so it deliberately does not
touch stock. The dispatcher:

1. Resolves the game manager via `call 0x425950`.
2. Reads signed game speed `[manager+0x17D7C]`; rejects `<= 0` and `== 999`
   (paused).
3. Requires `[0x51D5F8]` (tech points) `>= 50000`.
4. Snapshots speed, manager pointer, tech balance, and the 64-bit village
   clock `[0x4C6250]` / `[0x4C6254]`.
5. Confirms via `MessageBoxA` (MB_OKCANCEL) against the owner HWND.
6. Re-validates every snapshot (recheck guard) before any write.
7. Charges exactly 50,000 once via `push -50000; mov ecx,0x51D5F8; call 0x4237B0`
   and verifies the new balance.
8. Computes `delta = 129600 / speed` (`mov eax,129600; xor edx,edx; div
   [speed]`) and **subtracts** it from the 64-bit clock (`sub [0x4C6250],eax;
   sbb [0x4C6254],0`), verifying the result.
9. Reports success / paused / insufficient / cancelled / recheck /
   charge_unknown / clock_unknown via `MessageBoxA`.

`129600 = 3 * 43200`; dividing by the current speed makes the *displayed*
advance a constant three villager years at any speed — exactly the spec.

## Why it is "Unavailable" in stock today

`scripts/build_vv5_task9_native_actions.py`, `tech_menu` (lines ~548–662):

- Dialog state starts `mov eax, 0x700` — bits 8/9/10 = the "Unavailable" bits
  for rows 0/1/2 (Time Warp / Island Event / Barrel of Babies). (Row-show bit
  is `1<<row`; row-unavailable bit is `1<<(8+row)`; a row with neither bit is a
  plain enabled **Buy**, which is how Full Heal row 5 renders.)
- Command dispatch: `cmp ebx,3; jb unavailable` sends commands 0/1/2 to the
  "unavailable" result. Only 3/4 (doublers) and 5 (heal) do work.
- The `time_warp` reserve (`OFF["time_warp"]=0x1040`, `SIZES["time_warp"]=0x500`)
  is present in every page (stock included) but left all-zero.

## Exact changes to enable stock Time Warp

All in `scripts/build_vv5_task9_native_actions.py` (self-contained; **no DLL
recompile** — reuse the inline-`MessageBoxA` approach so the companion
`VVFP Origins Icons.dll` and its pinned hash are untouched):

1. **Strings** — extend `build_strings` with the dispatcher's ASCII/`\0`
   strings (reuse the proven texts from `build_expanded_time_warp.py`
   lines ~477–505), keyed e.g. `tw_get`("GetOriginsOwner"),
   `tw_user32`("USER32.dll"), `tw_messagebox`("MessageBoxA"),
   `tw_title`("Origins Upgrades"), `tw_warning`(Time-Warp-specific OK/Cancel
   prompt naming the 3 years and 50,000 cost), and
   `tw_paused/insufficient/cancelled/recheck/unavailable/success/charge_unknown/clock_unknown`.
   Verify `cursor <= PAGE_SIZE` (they append after the existing 8 strings at
   `OFF["strings"]=0x7000`).

2. **`build_time_warp(page, page_va, strings)`** — port the dispatcher as a
   `ret`-terminated subroutine into `OFF["time_warp"]`:
   - Drop the expanded prefix `test ebx,ebx; jne 0x904967` (the command check
     now lives in `tech_menu`).
   - Replace the expanded tail `jmp 0x904846` with
     `add esp,0x50; pop edi; pop esi; pop ebx; pop ebp; ret`.
   - Resolve the owner HWND itself: `LoadLibraryA([tw dll string]) ->
     GetProcAddress("GetOriginsOwner") -> call`, reusing the page's existing
     `dll` string and the `[0x4951E0]`/`[0x4951DC]` import thunks.
   - Keep every absolute engine address (`0x425950`, `0x4237B0`, `0x51D5F8`,
     `0x4C6250/54`, speed `+0x17D7C`) — those are image-absolute, not page
     relative.
   - Assemble at `page_va + OFF["time_warp"]`; assert length `<= 0x500` and the
     reserve is zero before writing (mirror `put`).
   - Register it in `build_page` (`routines["time_warp"] = build_time_warp(...)`).

3. **`tech_menu`** (two edits):
   - `mov eax, 0x700` → `mov eax, 0x600` (drop only Time Warp's Unavailable
     bit; leave Island/Barrel unavailable).
   - In the dispatch, before `cmp ebx,3; jb unavailable`, add
     `test ebx,ebx; jz time_warp_row` and a `time_warp_row:` label that does
     `call 0x{page_va + OFF['time_warp']:X}; jmp done`. Commands 1/2 keep
     falling through to `unavailable`.

## Believer scope note

Time Warp is a **village-clock** action, not a per-villager mutation, so the
"believer-only, never touch masked heathens" rule (which guards the per-record
walkers via `+0x1CD4/+0x1CE1/+0x1CEC/+0x1C40`) does not apply to the clock
write itself. Aging that results from time passing is the native, faction-blind
consequence of the clock advancing, identical to normal play. No per-record
writes are performed.

## Deterministic regeneration + pin cascade (same pattern as the Full Heal fix)

1. `python scripts/build_vv5_task9_native_actions.py` — regenerates
   `data/vv5_task9_native_actions.json` (+ map) and the four page hashes.
2. Update `src/vv_fun_patcher.py`: `VV5_TASK9_SOURCE_TEXT_SHA256`
   (manifest/map), `VV5_TASK9_PAGE_SHA256` (all four modes),
   `EXPANDED_TIME_WARP_SOURCE_TEXT_SHA256["task9_builder"]`, and the vv4/vv5
   `EXPANDED_TIME_WARP_ARTIFACT_SHA256` entries.
3. Update `scripts/build_expanded_time_warp.py` base-page pins (the stock and
   expanded `task9.build_page` asserts) and re-run it to restamp the
   `vv4/vv5_expanded_time_warp.json` (+ maps).
4. Refresh `tests/test_expanded_time_warp.py` page + vv5 render goldens and
   `tests/test_vv5_task9_native_actions.py` any page-hash/geometry asserts.
5. Update the `tech_menu` provenance/description in the task9 builder to say
   Time Warp is now available (only Island Event and Barrel of Babies remain
   unavailable).

## Conflict to reconcile at merge

The `vv5_expanded_256_time_warp` feature is premised on stock being
byte-frozen (`forbidden_mutations: ["stock Task9 page"]`). Enabling Time Warp
in stock supersedes that premise; the expanded-only feature should be either
retired or reconciled. This area is under active concurrent work on
`codex/vv2-upgrade-fixes-appearance`, so do the wiring on the isolated review
branch and reconcile at merge.
