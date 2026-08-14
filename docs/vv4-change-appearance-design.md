# VV4 Change Appearance (Body + Head) — Design & Exact-Build Evidence

Target: **Virtual Villagers - The Tree of Life**, 929,792 bytes, SHA-256
`6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220`.

This document grounds the requested full custom body+head picker in the exact
build's proven native structures, so the implementation reuses native code and
rendering instead of fabricating a sprite compositor. It supersedes the ON-HOLD
stance in `appearance-upgrades-requirements.md` per the maintainer's explicit
decision to build the full picker; the open items below remain the honest
runtime-verification boundary.

## Intended behavior (spec)

A **Change Appearance** row in the VV4 Villager Details (Origins) Upgrades
window, for the selected **active, living** villager. It opens a window showing
the villager's **body** and **head**, each flanked by left/right arrows. Each
arrow cycles that field's catalog with wraparound. **OK** applies the shown
head+body to the villager and deducts exactly **5,000 tech points once**.
**Insufficient funds** → message "Not enough tech points", nothing changed,
nothing charged. **Cancel / close** → nothing changed, nothing charged.

## Proven native facts

Record stride `0x2E3C`; selected-index state world+`0x171B0`; resolver
`sub_466040` (`0..149`); active byte `+0x1CC4`, dead byte `+0x1CC7`; tech pool
`0x4D6F88`; native signed charge helper `0x41E300`.

- **Body/outfit field:** DWORD `record+0x1BBC`, catalog **`0..28`**, wraps both
  directions (proven by the native cycler).
- **Head/genetics field:** DWORD `record+0x1BB8`, catalog **`0..29`** (30
  heads), wraps both directions. Confirmed from the game's own atlases: every
  head sheet has exactly **30 rows** (one head identity per row, 8 directional
  frames per row) — `Images/male_heads{00,10}.png` and `female_heads{00,10}.png`
  are 320x1950 (30 x 65px rows); `Images/BigHeads{00,10}.png` (Detail portraits)
  are 480x3000 (30 x 100px rows). This matches the native constructor's
  `RNG(30)`. The `00`/`10` suffix is the young/old variant, chosen by age at
  render time (`>=1100` → old sheet), so the same index `0..29` selects "the
  same person" young or old; cycling the index works for any age and both sexes
  (both sheets have 30 rows).
- **Native clothing (body) transaction:** action **71** charges exactly
  **5,000** and opens native chooser `sub_419710`.
- **Native body cycler `sub_419590`** (`this=ecx`, `dir=[esp+8]`): resolves the
  villager from slot `[this+0x509c]`; `dir>0` → `[this+0x50a0]++` wrapping
  `28→0`; `dir<0` → `[this+0x50a0]--` wrapping `-1→28`; `dir==0` → sync
  `[this+0x50a0] = [record+0x1BBC]`; then, if record active/not-dead, write
  `[record+0x1BBC] = [this+0x50a0]` **live**. Returns 1.
- **Native chooser `sub_419710`:** object vtable `0x48D38C`. Fields:
  `+0x509c`=slot, `+0x50a0`=body candidate, `+0x50a4`=world (`0x41FE70`),
  `+0x50a8`=screen manager (`0x44DA20`), `+0x50ac`=`0x408130` manager,
  layout scalars `+0x50`=4/`+0x54`=2/`+0x58`=3/`+0x5c`=0x190. It builds arrow
  controls with `alloc(0x470C5C, 0x14)` then `create-with-event-id(0x44CB60)`:
  **LEFT arrow event `0x2B` → `+0x50b4`**, **RIGHT arrow event `0x2C` →
  `+0x50b8`**, plus a label/sprite control (`0x44CB70`, id `0x99`). The villager
  **preview renders live from the record**, so writing `+0x1BBC`/`+0x1BB8`
  updates the preview.
- **Save/load & clone:** `+0x1BBC` and `+0x1BB8` persist inside the
  `+0x1B8C..+0x1C33` span and are copied by clone/summary paths — no new sidecar
  needed, so vanilla-save compatibility is preserved.
- **OK/Cancel precedent (VV5):** VV5's action-90 chooser has Accept (keep) via
  button `+0x50` and **Cancel (restore original field + refund 5,000)** at
  `0x419E8E`/`0x419E94`. This is the model for VV4 atomic OK/Cancel, which VV4's
  own clothing dialog lacks.

## Design — extend the native chooser (no fabricated renderer)

1. **Detail row.** Add "Change Appearance" (cost 5,000) to the Origins
   Villager-Details Upgrades menu next to Grant Youth / Grant Running / Set Age
   18. On select: re-resolve the selected slot, require active(`+0x1CC4`)/not
   dead(`+0x1CC7`), and require tech pool `[0x4D6F88] >= 5000`; otherwise show
   "Not enough tech points" and neither open nor charge.
2. **Extended chooser** (a cave payload that reuses `sub_419710`'s window,
   controls, and live villager rendering):
   - On open, **snapshot** the original `+0x1BBC` (body), `+0x1BB8` (head), and
     the slot-identity token.
   - **Body arrows:** reuse native events `0x2B`/`0x2C` → `sub_419590` (live
     write + live render), unchanged.
   - **Head arrows:** add two controls (e.g. events `0x2D`/`0x2E`) whose handler
     mirrors `sub_419590` on `+0x1BB8` over the sex-appropriate range, writing
     live so the native preview shows the composed head.
   - **OK button:** revalidate slot identity + active/living + funds; if body or
     head differ from the snapshot, deduct exactly **5,000 once** via the native
     charge helper (`push -5000; mov ecx,0x4D6F88; call 0x41E300`); keep the
     live values; close.
   - **Cancel button and window close:** restore snapshot `+0x1BBC`/`+0x1BB8`;
     charge nothing; close.
   - **Insufficient at OK:** restore snapshot, charge nothing, show "Not enough
     tech points".
   Net semantics = live-write + native render + snapshot rollback, identical in
   effect to VV5's native cancel-refund, but preview-only from the player's
   view because Cancel/close reverts.
3. **Placement.** New payload in the validated `.text` Origins cave with a
   companion label/message string block; collision-free with the existing
   Origins Tech/Detail payloads.

## Open items — runtime/RE confirmation required (honest STOP gates)

These are not yet proven and cannot be validated in a non-runtime environment:

1. ~~Head catalog range per sex~~ — **RESOLVED**: head range is `0..29` (30
   rows in every head atlas; `male_heads`/`female_heads`/`BigHeads` all 30 rows;
   matches constructor `RNG(30)`). One remaining sub-check: whether the game
   treats any specific row (e.g. a chief/special head) as non-selectable the way
   the body chooser excludes body row 29 — the body chooser cycles `0..28`
   despite 30 body rows. If a head special row exists it should likewise be
   excluded; otherwise cycle the full `0..29`.
2. **Added-control layout coordinates** for the head arrows + OK/Cancel within
   `sub_419710`'s window, and their hit-test/event routing through the dialog's
   message handler.
3. **Preview refresh/invalidation** after a head write (confirm the renderer
   re-reads `+0x1BB8` each frame like it does `+0x1BBC`).
4. **Exact OK-time charge timing** so 5,000 is deducted once and only on a real
   change — action 71 charges on its own path; the custom OK path must debit the
   pool directly without double-charging.
5. **Player/runtime confirmation** of rendering, clicking, wraparound, OK/Cancel,
   and the charge — not verifiable here.

Until items 1–4 are pinned by exact-build disassembly, the implementation is
built and **statically** verified (byte/instruction level, like the other
patches); in-game confirmation remains pending — consistent with the project's
evidence standard.
