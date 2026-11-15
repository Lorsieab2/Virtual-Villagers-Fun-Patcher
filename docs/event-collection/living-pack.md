# Living Event Engine: the pack (VLEP v1), the history sidecar (VLEH v1) and the manifest rows

This is the contract between the Python side (`src/vv_living_mixer.py`, which writes the packs, and
`scripts/build_event_collection_features.py`, which ships them) and the engine
(`native/vvfp_story_upgrades/story_living.inc`, which reads them). Where this page and `living_design.md` differ, this
page wins. The bank is `data/living_events/bank.json` ([living-events.md](living-events.md)); every variant is an
ordinary version 6 graph ([cie-v6-binary.md](cie-v6-binary.md)).

Everything is little-endian. `NONE` is `0xFFFF` (a 16-bit field) or `0xFF` (an 8-bit field). Strings are NUL-ended
ASCII.

## 1. What ships

- **One pack per game:** `assets/event_collection/vvN/living.pak`, installed as
  `"<game folder>\Virtual Villagers Fun Patcher Files\Island Event Collection\living.pak"`, pinned in the game's
  Isola Grand Event Collection row (`data/vvN_isola_grand_event_collection_feature.json`) like every other file.
- **One manifest row per seed** in the game's `Island Event Collection\manifest.txt` (the collection's own file and
  format, `story_collection.inc sc_scan`), only for the seeds the pack holds for that game:

  | Field | Value |
  |---|---|
  | id | `living_le_<cat>_<nn>` (Living Engine seed, e.g. `living_le_per_01`, `living_le_bel_10`) or `living_mc_<cat>_<nn>` (MC situation, e.g. `living_mc_isl_01`, `living_mc_bel_15`); `<cat>` is the category code in lower case, `<nn>` the seed's number in it, two digits. At most 16 characters (VV1's 22-character id cap holds) |
  | title | the category's heading in title case (the bank's `title`, e.g. "Personal Expression"; MC "Island Businesses and Markets": no game's title can show `&`, grammar fix `living-title-ampersand`) |
  | games | the games whose pack holds at least one variant of the seed |
  | draw weight | 1 |
  | series | **one series per category** (owner, 2026-11-14): `living_le_<cat>` (12 series) and `living_mc_<cat>` (6 series). The collection's draw counts a series as one event, so each category is one entry of the rare roll and its seeds share it equally |
  | credit | the Living Engine's credit line (Living L23815), verbatim; MC uses the same line (open question Q11) |
  | description | the seed's sentence (typography made plain), in this game's words: a seed that names the chief says "The village leader" / "the village leader's" / "A village leader" outside VV3 |
  | Guardians title / description | empty (no living text says "Heathen" or "convert") |

- **The id prefix `living_`** tells the engine that the row's event is in `living.pak`, not in `<id>.cieg`. No
  `living_*.cieg` file ever ships. The manifest row's id equals the pack's seed id (2.2).
- MJ (the 35 held seeds) has no rows and no variants until the owner's outcomes arrive.

## 2. The pack: VLEP v1

Section order in the file: header, seeds, variants, outcomes, strings, blobs. The engine must use the offsets, not the
order. Every offset is from the start of the file.

### 2.1 Header (64 bytes)

| Offset | Type | Meaning |
|---|---|---|
| 0 | `4s` | magic `VLEP` |
| 4 | `H` | version = 1 |
| 6 | `H` | header bytes = 64 |
| 8 | `I` | file bytes |
| 12 | `I` | crc32 (zlib) of the whole file with this field 0. The VLEH sidecar keeps it (section 3) |
| 16 | `B` | game (1..5) |
| 17 | `B` | 0 |
| 18 | `H` | seed count S (1..2048) |
| 20 | `H` | variant count V (1..65535) |
| 22 | `H` | 0 |
| 24 | `I` | seeds offset |
| 28 | `I` | variants offset |
| 32 | `I` | outcomes offset |
| 36 | `I` | outcome count M |
| 40 | `I` | strings offset |
| 44 | `I` | strings bytes |
| 48 | `I` | blobs offset (4-aligned) |
| 52 | `I` | blobs bytes |
| 56 | `H` | role count R of the Living bank (30): the role-pair keys' range |
| 58 | `H` | archetype count A of the Living bank (38) |
| 60 | `H` | lens count L of the Living bank (15) |
| 62 | `H` | 0 |

The loader refuses a pack whose magic, version, header bytes, file bytes, crc or any offset / count does not fit
the file, or a seed's mood above 2. The engine's limits (static buffers, no heap): a pack of at most 8 MB, at most
16,384 variants, 64 roles, 255 archetypes and 255 lenses (the packs hold about 1,250 variants, 30 roles, 38
archetypes, 15 lenses).

### 2.2 Seed record (16 bytes, S of them)

| Offset | Type | Meaning |
|---|---|---|
| 0 | `H` | id string (byte offset into the strings): the manifest id, `living_le_per_01` |
| 2 | `H` | series string: `living_le_per` |
| 4 | `H` | first variant (index into the variants) |
| 6 | `H` | variant count (1..255) |
| 8 | `B` | bank: 0 Living Engine (LE), 1 MC |
| 9 | `B` | category index within the bank (LE 0..11 in bank order PER, FAM, CEL, ART, ANI, BEL, GOV, OTH, FOO, EMO, RES, ODD; MC 0..5: ISL, DIS, AFT, LOS, TRA, BEL) |
| 10 | `H` | the seed's index in the bank's own list (LE `seeds[]` 0..119, MC `mc.situations[]` 0..94) |
| 12 | `B` | mood: 0 warm, 1 social, 2 serious -- its category's (`bank.json` `categories[].mood`, `mc.categories[].mood`; section 4.1a) |
| 13 | `3s` | 0 |

Seeds are in manifest order (LE categories in bank order, then MC), each seed's variants consecutive, in `k` order.

### 2.3 Variant record (24 bytes, V of them)

| Offset | Type | Meaning |
|---|---|---|
| 0 | `I` | blob offset, from the blobs offset (4-aligned) |
| 4 | `I` | blob bytes (at most `CG_MAX_FILE`, 0x20000) |
| 8 | `H` | seed index |
| 10 | `B` | k, the variant's number within its seed (0..K-1; the same `k` in every game's pack) |
| 11 | `B` | flags: 1 = the owner's MIX example (k = 0, section 5), 2 = its choices are the category's choice set, 4 = its choices are approaches |
| 12 | `H` | role A: the first villager's role, index into the Living bank's `roles[]` (`NONE` for MC) |
| 14 | `H` | role B: the second's (`NONE` for MC) |
| 16 | `B` | lens: index into `lenses[]` (`NONE` for MC) |
| 17 | `B` | family set: bit 0 consult, 1 act, 2 relate, 3 withdraw, 4 play (the approach families its choices come from), bit 5 the category's choice set, bit 6 an MC situation's own four approaches |
| 18 | `H` | games mask (bit g-1): the games this variant is valid in (always holds this pack's game) |
| 20 | `H` | outcome first (index into the outcomes) |
| 22 | `H` | outcome count |

The blob is the variant's `.cieg`, exactly as `cg_load` reads it (version 6, its own crc).

### 2.4 Outcome record (4 bytes, M of them)

| Offset | Type | Meaning |
|---|---|---|
| 0 | `H` | node index: the outcome node's index in the blob's node table (the run's last node when the event ends there) |
| 2 | `B` | group: 1 good, 2 mixed, 3 bad, 4 rare. MC: 1 for an approach's first outcome, 3 for its second |
| 3 | `B` | archetype: index into the Living bank's `archetypes[]` (0..37); `NONE` for MC |

A variant's outcomes are every ending node it can reach, in node order. `lv_on_finish` (the `cg_finish` hook) looks up
the run's last node among the variant's outcome records and counts the archetype (section 3); a node that is not
listed is not counted.

### 2.5 Strings

NUL-ended ASCII, referenced by byte offset from the strings offset. Only ids and series names.

## 3. The history sidecar: VLEH v1

`"<save>\...\Virtual Villagers N Living Events - Save S.dat"`, through `vv_paid_named_path(game, slot,
"Living Events", ...)`. A missing, short, damaged (crc), or foreign file (another pack crc, another roster
signature, other counts) is a **fresh history**: all zero. Start Over deletes it. It is written after each arm and
each finish.

| Offset | Type | Meaning |
|---|---|---|
| 0 | `4s` | magic `VLEH` |
| 4 | `H` | version = 1 |
| 6 | `H` | header bytes = 48 |
| 8 | `I` | file bytes |
| 12 | `I` | crc32 of the whole file with this field 0 |
| 16 | `I` | the pack's crc32 (VLEP +12) these counts belong to |
| 20 | `I` | roster signature (`lv_roster_sig`, below; Python never computes it) |
| 24 | `H` | ring used (0..64) |
| 26 | `H` | ring head: the next slot written (0..63) |
| 28 | `H` | seed count S (the pack's) |
| 30 | `H` | variant count V (the pack's) |
| 32 | `H` | role count R |
| 34 | `H` | archetype count A |
| 36 | `H` | lens count L |
| 38 | `H` | 0 |
| 40 | `I` | events armed in all |
| 44 | `I` | 0 |
| 48 | `H` x 64 | the ring: the seed index of each recent arm, `NONE` empty |
| 176 | `H` x R*R | role-pair uses, key `min(a, b) * R + max(a, b)` |
| +  | `H` x L | lens uses |
| +  | `H` x 128 | family-set uses (by the family-set byte: bits 0..6, so 128 values) |
| +  | `H` x A | archetype uses (outcomes reached) |
| +  | `H` x V | variant uses (by the pack's variant index) |

Counts stop at 65535. File bytes = 176 + 2 (R*R + L + 128 + A + V).

**The roster signature** (`lv_roster_sig`, story_living.inc): the identity (`story_title_identity`, 0 read as 1) of
the youngest villager among the village's records when the file is written -- the smallest identity among the
youngest -- or 0 when there is nobody. A file is this village's when that villager is still among its records (a
signature of 0 never matches). The youngest is the villager most likely to be there at the next event; one who has
gone since only costs a fresh history. The file is per save slot, and Start Over or a deleted tribe deletes it
(`VvfpStoryVillageReset`), so the signature only guards against a file that is not this village's at all.

## 4. Choosing at run time

### 4.1 Recency (before the draw)

W = min(64, S_game / 3) (integer division), where S_game is the number of living rows this game lists. A seed whose
index is among the last W ring entries (newest first, from ring head - 1 backwards) is left out of the draw
(`left[i] = 0`). Then the collection's draw runs as for every row (a series counts once).

### 4.1a Moods (the owner's Global Editorial Override)

The override (2026-11-14) asks for roughly one third warm / funny / ordinary, one third curious / social / mixed and
one third serious / solemn / mysterious, with no clusters of one mood. Each category has a mood (the seed record's
byte 12):

| Mood | Living Engine categories | MC categories |
|---|---|---|
| warm (0) | PER, CEL, FOO, ODD | -- |
| social (1) | FAM, ART, ANI, OTH | ISL, BEL |
| serious (2) | BEL, GOV, EMO, RES | DIS, AFT, LOS, TRA |

Before the draw, the moods of the seeds in the ring (every entry used, up to 64) are counted. When the three counts
are not all equal, every living series whose mood has the fewest weighs `LV_MOOD_BOOST` = 2 in the draw instead of 1
(a series is one category, so all its rows share the mood); every other series, and every other collection event,
keeps its weight. Python twin: `History.mood_weights` (vv_living_mixer.py).

### 4.2 Ordering a seed's variants (`lv_order`; Python twin `vv_living_mixer.lv_order`)

For each variant v of the seed in pack order, the uses `u(v)` = pair[key(A, B)] + lens[lens] + family[family set] +
variant[v] (a `NONE` role, or a `NONE` lens, adds 0). Its weight is `w(v) = max(1, 1000 / (1 + u(v)))` (integer
division). Then, up to 12 times while variants are left: `r = random_below(sum of the weights left)`
(`ce_random_below`: no roll when the sum is at most 1), `i = roll_index(weights left, r)` (`ce_roll_index`, in pack
order of those left); variant i is next in the order and is taken out. The engine tries the variants in that order
under STRICT casting; the first that casts is armed. None casts: the seed is not possible now (the draw moves on as
for any collection entry that cannot be cast).

### 4.3 Recording

- **Armed:** the seed index goes into the ring at the head (head = (head + 1) % 64, used = min(64, used + 1)); pair,
  lens, family set and variant uses go up by one; the total goes up.
- **Finished** (`lv_on_finish`): the archetype of the run's last node (2.4), when it has one, goes up by one.

### 4.4 Pick Island Event and the library

A living row is possible when any of its variants for this game casts (strict casting for Pick, the library's own
casting for a purchase). The variant used is chosen by 4.2 as well. In the library a living row's entry is named
"Isola Grand Event Collection: <title>: <its sentence>" (the seeds of a category share a title); its internal path
is `?living:<id>`, which no file can have. The library holds up to 1,024 entries (`CG_LIBRARY_MAX`).

## 5. Variants (what the mixer writes)

- **K = 10 variants per Living Engine seed** (120), numbered k = 0..9, the same numbers in every game's pack; a
  variant whose cast or seed some game cannot show is left out of that game's pack only. **An MC situation ships one
  variant (MC_K = 1, lead 2026-11-14)**: its other variants only reordered its four approaches (near duplicates, about
  2 MB a pack).
- **k = 0 of a seed with a MIX example is that MIX** (flags bit 0), with the documented changes for the 15 MIX that
  break the compatibility rules (living-events.md section 7).
- **LE variant shape:** the start is a question: the seed sentence and the frame (living-events.md section 1), with
  the two villagers' personalities as pools `PA` and `PB` (`PB` `distinct_from` `PA`; a variant's personalities are
  fixed only for a MIX) and 3 to 5 choices (the category's choice set, or approaches from different families). Each
  choice is a branch to a GOOD (weight 20), an adverse MIXED or BAD (20) and a RARE (2) archetype page. Archetype
  pages are shared nodes, carrying their effects, with automatic lines (`auto_text`) when they have any.
- **MC variant shape:** the situation's setup, its four approaches in the source order (k = 0; `mc_orders` can
  still give other orders when asked) and each approach's two authored outcomes, equally likely.
- Ordering, casting and history never change a variant's text: everything shown is in the blob.
