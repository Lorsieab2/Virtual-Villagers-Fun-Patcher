# Villager record reference

**This file is authoritative.** Its contents come from the owner's Cheat
Engine tables, which are correct by definition. Where a measurement of a
running game disagrees with this file, the measurement is wrong.

Do not "verify" these offsets by re-deriving them, and do not change one
because a scan of a live village seems to contradict it. Several of the
entries below were briefly replaced by measured values during development
and every such replacement was an error.

## How to read a Cheat Engine row

A table row shows an **address**, which is specific to one process and one
build. What belongs in code is the **offset** from the villager record's
base, which survives mods, relaunches and reallocation.

Cheat Engine states the relationship itself: opening a pointer row's
"Change address" dialog shows `base+offset = address`. For VV2's Babyplets
row that reads `0D730020+544 = 0D730564`, giving the durable fact `+0x544`.

Module bases and array addresses must always be resolved at runtime. No
absolute address from a table may be compiled into shipped code.

## VV1 — A New Home

Record base in the sampled process: `0x0C3B0F30`. Stride `0x3D8`.

| Field | Address | Offset |
|---|---|---|
| Health | `0x0C3B1274` | `+0x344` |
| Age | `0x0C3B1278` | `+0x348` |
| Nursing | `0x0C3B127C` | `+0x34C` |
| Gender | `0x0C3B1280` | `+0x350` |
| Sick | `0x0C3B1284` | `+0x354` |
| **Pregnant** | `0x0C3B1288` | **`+0x358`** |
| **Babyplets** | `0x0C3B128C` | **`+0x35C`** |
| Head | `0x0C3B1290` | `+0x360` |
| Body | `0x0C3B1294` | `+0x364` |
| Likes | `0x0C3B12CC` | `+0x39C` |
| Dislikes | `0x0C3B12D8` | `+0x3A8` |
| Parenting | `0x0C3B12EC` | `+0x3BC` |

Skills run from `+0x3BC` in the order Parenting, Building, Farming,
Healing, Research. Parenting and Breeding are the same skill.

The likes row above is the **second** slot of the likes array; the array
itself begins at `+0x398`, which is what the exporter reads. Both are
consistent — see the likes/dislikes array note in
`docs/game-data-conventions.md`.

## VV2 — The Lost Children

Record base in the sampled process: `0x0D730020`. Stride `0xE48C`.

| Field | Address | Offset |
|---|---|---|
| Health | `0x0D73054C` | `+0x52C` |
| Age | `0x0D730550` | `+0x530` |
| Nursing Timer | `0x0D730554` | `+0x534` |
| Gender (1 = male, 2 = female) | `0x0D730558` | `+0x538` |
| Sick | `0x0D73055C` | `+0x53C` |
| **Nursing** | `0x0D730560` | **`+0x540`** |
| **Babyplets** | `0x0D730564` | **`+0x544`** |
| Head | `0x0D730568` | `+0x548` |
| Body | `0x0D73056C` | `+0x54C` |
| Totem Type | `0x0D730570` | `+0x550` |
| Is Totem | `0x0D730578` | `+0x558` |
| Likes (3 slots) | `0x0D730610` | `+0x5F0` |
| Dislikes (3 slots) | `0x0D7307F4` | `+0x7D4` |
| Parenting | `0x0D730804` | `+0x7E4` |
| Is Esteemed Elder | `0x0D73081C` | `+0x7FC` |

Skills run from `+0x7E4` in the order Parenting, Building, Farming,
Healing, Research.

`+0x5E4` is **not** a pregnancy field. It is female-only, which is
superficially convincing, but holds the values 1, 3 and 5; a litter is
never 5. It was shipped in error once and must not be reinstated.

## VV3, VV4, VV5

Confirmed against the owner's tables for those games.

| Game | Pregnancy | Litter |
|---|---|---|
| VV3 — The Secret City | `+0xE8C` | `+0xE90` |
| VV4 — The Tree of Life | `+0x1C4C` | `+0x1C50` |
| VV5 — New Believers | `+0x1C4C` | `+0x1C50` |

VV4 and VV5 are corroborated in the executables, where `+0x1C4C` is
written exactly once — VV4 at `0x45E830`, VV5 at `0x465E7A` — by a pair
that copies the age clock at the moment of conception:

```
mov edx,[esi+0x1C3C]
mov [esi+0x1C4C],edx
```

## Units and states

Ages are **age units**: 20 units = 1 year. A villager the panel shows as
41 holds 836. A raw read never equals the displayed number.

**Pregnant and nursing are the same state.** The panel reads
`Nursing for: N min`; there is no separate pregnancy display to find.

A litter is **1, 2 or 3** babies in every game.
