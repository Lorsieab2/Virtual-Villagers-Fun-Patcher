# Traders and the new island-event effects: research (v1.35.97, the owner's spec of 2026-11-16/17)

Read in the stock executables (`inputs/vvN-stock-copy`, capstone) and the repo's adapters (`native/vvfp_story_upgrades/story_cN.inc`).
**VERIFIED** = read in the stock code or already in repo code; **UNCONFIRMED** = not seen in a running game. Nothing
here was seen live. "W1" = VV1 world `[0x48AEDC]`, "W2" = VV2 world `[0x4997BC]`, VV4 world = `[0x4CB51C]`, VV5 mgr =
`0x425950()` (the adapter's world).

## 1. What a trader can trade (real counts)

| Game | Item (effect word) | Where | Limits | How it is changed | Status |
|---|---|---|---|---|---|
| all | food (`food`) | VV1 W1+0xA2EC, VV2 W2+0x2EAA4, VV3 0x582490, VV4 0x4D6DD0, VV5 0x51D34C | 0..no cap; floor 0 | the adapter's `change_food` (plain write, gains counted in Food Gathered) | VERIFIED |
| all | tech points (`tech`) | VV1 W1+0xA2FC, VV2 W2+0x2EADC, VV3 0x582644, VV4 0x4D6F88, VV5 0x51D5F8 | no cap; kept >= 0 | the adapter's `change_tech` | VERIFIED |
| VV2 | collectibles (`collectible`) | 48 found BYTES at W2+0x2E720 (flags, no duplicates) | 0/1 | gain only: a random piece not found yet becomes found (no message; +5 room per complete set is read live). Never taken: a flag has no spare | VERIFIED code |
| VV3 | collectibles | count dwords 0x58F438 + 4*id, ids 0x34..0x63 | no cap; a negative count reads as found | gain: +1 to a random piece; loss: -1 from a piece held at least twice (a duplicate), never below 1 | VERIFIED |
| VV4 | collectibles | count dwords 0x4CC918 + 4*(id-0x46), ids 0x46..0x75 | no cap | as VV3 | VERIFIED |
| VV5 | collectibles | count dwords 0x4DBFC8 + 0x630 + 4*id, ids 0x50..0x7F | no cap | as VV3 | VERIFIED |
| VV1 | berries (`berries`) | W1+0xA2F4 | 0..5000 | the adapter's value 0 | VERIFIED |
| VV2 | coconuts (`coconuts`) | W2+0x2EACC | 0..1500 | the adapter's value 0 | VERIFIED |
| VV2 | fish (`fish`) | W2+0x2EAD0 (signed; no stock refill) | 0..2200 | the adapter's value 1 (a "fish run" is a gain) | VERIFIED |
| VV3 | honey (`honey`) | 0x5945E0 | 0..3000 (the loader refuses more) | the adapter's value 6 | VERIFIED |
| VV3 | fruit (`fruit`) | 0x594810 + 0x18*tree, planted trees only (0x594844) | 0..1000 a tree | the adapter's values 0..2: a gain fills the emptiest planted tree first, a loss takes from the fullest | VERIFIED |
| VV4 | blackberries (`blackberries`) | world+0x170F8 | 0..1000 | the adapter's value 0 | VERIFIED |
| VV4 | cutting tools, soap, cloth (`cutting_tools`, `soap`, `cloth`) | 0x4D8618, 0x4D8D98, 0x4D8ACC | 0..6 (99 with Supply Cap); soap 0..99 | PR #806's `supply`; after their puzzles | VERIFIED |
| VV5 | noni (`noni`) | mgr+0x17D58 | 0..1000 | the adapter's value 0 | VERIFIED |

Collectible gains never trigger the pickup's messages or trophies (those are paid only inside the pickup routine);
the population room each complete set gives is read live in every game, so a new piece that completes a set gives the
room at once. A loss only ever takes a duplicate, so no set and no room is lost.

## 2. Asked for, but not a count (flavor only, never changed)

| Game | Item | Why | Status |
|---|---|---|---|
| all | mushrooms | no game holds mushrooms: a picked mushroom becomes food at once (Mushrooms Found is a statistic, and VV3/VV4 events read it) | VERIFIED |
| VV1 | collectibles | A New Home has no collections | VERIFIED |
| VV3 | fish and crab | no store: each catch is paid straight into food | VERIFIED |
| VV3 | alchemy potions, herbs | no count; puzzle state (the pot, the table) | VERIFIED |
| VV4 | fish, Golden Fish, crabs, hot rocks | no store: fixed food per trip; a hot rock is a carried item | VERIFIED |
| VV4 | Yellow Fruit Trees stock / breadfruit | lives inside "VVFP VV4 Fruit Supply.dll" (`g_fruit`, per-save file) and only with that patch on; the DLL exports Refill and Partial only. **Needs a new export (`VvfpYellowFruitAdd`) before an event can give or take fruit**: not in this change | VERIFIED |
| VV4 | cooking-pit stew, herbs, firewood, dry grass, water for the Ash Key | no count (pot state, carried items, a burn timer) | VERIFIED (water: none found) |
| VV2 | the stew pot, the fire's fuel | **not flavor-safe to change**: the stew number decides heal/sicken/cure; the fire's end time halves sickness. Kept as words only, as the spec says | VERIFIED |

## 3. The new effects: feasibility per game

| Effect | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| Group behaviour (relax, swim, dance, pray, celebrate, pond, children play, elders' stories; songs/chants/speeches through the closest real action) | yes: the adapter's actions per villager | yes | yes | yes | yes (believers) |
| Group sickness / cure | yes (+0x354) | yes (+0x53C) | yes (+0xE89) | yes (+0x1C48) | yes (+0x1C48) |
| Next island event sooner / later | yes W1+0xA300 | yes W2+0x2EAE0 | yes world+0x12EF4 | yes world+0x170E0 | yes mgr+0x17D3C |
| Research progress +/- | = tech points (no game has a research meter) | = tech | = tech | = tech | = tech |
| Tech LEVEL +1/-1 (clamped) | plain write 1..3 (the game's own events do) | plain write 1..3 | raise 0x426FD0; lower plain, never below 1 (areas 0-4; the loader refuses 0) | raise 0x41E1D0; lower plain 1..3 | raise 0x423610(id, 0); lower plain 1..3 |
| Speed a construction | hut progress +N, stops at threshold-1 (the builder's next trip finishes it the stock way) | same | same (projects 21..24) | same (19..25) | same (19..24) |
| Hut damage | the existing `damage` effect | same | same | same | same |
| Weather (the game's own starter) | **not possible: A New Home has no weather** | **not possible: no weather** | 0x41FB40 on 0x4B86C4 (type, 0): clear, rain, storm, fog | 0x46BC30 on 0x6C461C: clear, sun, rain, storm, fog | 0x477060 on 0x718EA0: clear, sun, rain, storm, fog |
| Cloth as a material | words only | words only | words only | real cloth bolts (`supply`) | words only |
| Fish run | words only (no store) | fish store +N | **not possible: no store** (a new hook) | **not possible: no field** | **not possible: no store** |
| Mushroom / collectible burst | not possible: inline spawn, one slot | 0x415490 (one map object at a time) | 0x42D940(-1,0,0), at most 2 at a time | 0x413EE0(-1,..), at most 2 | 0x4141E0(-1,..), at most 2 |
| Work rush | job field +0x3B8, dispatcher 0x447CD0 | job field +0x7E0, dispatcher 0x460590 | chooser 0x459730 / dispatcher 0x45AF00; neutral "Working 'til he/she drops!" (0x3A) | dispatcher 0x4639B0, no standing job field | dispatcher 0x46C540, player job +0x1C54 |
| Temporary effects | - | - | potions 0x4583A0 (cleared by any save) | stews / glow 0x460A90, 0x437EC0 (cleared by any save) | - |

Notes that limit the last three rows: the spawn routines hold at most one or two map objects; the stock group loops
in VV3/VV4 are hard-coded to 150 records (the 256-villager fork needs per-villager loops); "Working till he/she
drops!" exists only in VV3, and no game's no-skill stand-in action was traced to prove it gives no skill.

**Update (2026-11-18, the owner: everything in .97):** the spawn burst, the work rush, the VV3/VV4 temporary effects and the VV4 yellow fruit (a new `VvfpYellowFruitAdd` export) are now built: cie-v6-binary.md 36. The work rush's no-skill busy state is VV3's own "Working 'til he/she drops!"; elsewhere "Needs to sit down" (VV4, VV5) or "Sitting" (VV1, VV2): that these give no skill is UNCONFIRMED (not traced in the exe). VV2's fish and field protection now stop at 0 (Fix Vanilla Bugs).
