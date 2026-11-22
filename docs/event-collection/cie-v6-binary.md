# CIE graph format version 6: the binary `.cieg` and the run rules

This is the contract between `src/vv_cie_graph.py` (the compiler, Track A) and
`native/vvfp_story_upgrades/story_graph.inc` (the engine, Track B). Where this file and
`collection_design.md` section A4 differ, this file wins: the differences are marked **(differs from A4)**.

Everything is little-endian. `NONE` is `0xFFFF` everywhere. Strings are NUL-ended ASCII, indexed as in v5.
Versions 1 to 5 are unchanged byte for byte (pinned by `tests/test_cie_graph_v6.py`).

## 1. Header: 96 bytes (v1-v5: 80)

| Offset | Type | v6 meaning |
|---|---|---|
| 0 | `4s` | magic `CIEG` |
| 4 | `H` | version = 6 |
| 6 | `H` | header bytes = 96 |
| 8 | `I` | file bytes |
| 12 | `I` | crc32 of the whole file with this field 0 |
| 16 | `I` | games mask (bit g-1) |
| 20 | `H` | title string |
| 22 | `H` | start node |
| 24 | `H` | requirement min_eligible (0 = none) |
| 26..40 | `H` x 8 | role, node, child, effect, cond, variant, string, patch counts (as v5) |
| 42 | `H` | the requirement's condition: `NONE`, or an `all` (op 6) whose operands are first the puzzle conds (op 8, as v3) and then, if the graph has `requirement.if`, that condition **(differs from A4: the `if` is folded in here)** |
| 44..72 | `I` x 8 | roles, nodes, children, effects, conds, variants, patches, strings offsets (as v5) |
| 76 | `I` | pools offset |
| 80 | `I` | items offset |
| 84 | `H` | pool count (at most 1000) |
| 86 | `H` | item count (at most 8000) |
| 88 | `H` | flags: bit 0 = the protected guard is on (always 1 in v6) |
| 90 | `H` | the `collection` block as one string (its canonical JSON, ASCII, `\uXXXX` escapes), or `NONE` **(differs from A4: was 0)**. Never shown in game; the engine may ignore it. |
| 92 | `H` | the first title variant in the variants table (section 18); 0 when there is none |
| 94 | `H` | the title variants' count (0 = none; a file made before section 18 holds 0 here) |
| 96 | `I` | **only when the header is 104 bytes:** the kinship relations' offset (section 21) |
| 100 | `H` | **only when the header is 104 bytes:** the relations' count (1 .. role count) |
| 102 | `H` | **only when the header is 104 bytes:** 0 |

The header is 96 bytes, or **104** when a role has a kinship relation (section 21); a file with no relation is
byte for byte as before. Section order in the file: header, roles, nodes, children, effects, conds, variants,
patches, **pools, items**, (relations), strings. The engine must use the offsets, not the order.

## 2. Role: 16 bytes (v1-v5: 8)

| Offset | Type | Meaning |
|---|---|---|
| 0 | `B` | kind: 0 villager, 1 stranger, **2 alias**, **3 other** (G2) |
| 1 | `B` | flags (a stranger, kind 1: 1 = **named**, section 16; 2 = **a new name**, section 28, always with 1; nothing else): 1 optional, 2 exclude_nursing, 4 exclude_special, 8 believers_only, **16 harm_capable**, **32 exclude_protected**, 64 the author wrote protected "exclude", 128 the author wrote "allow" (64 and 128 are for decompiling only; the engine reads 32) |
| 2 | `B` | sex: 0 any, 1 male, 2 female, 3 random (strangers) |
| 3 | `B` | min_age years |
| 4 | `H` | id string |
| 6 | `B` | age-gap role + 1 (0 none) |
| 7 | `B` | age-gap years |
| 8 | `B` | max_age years, 0 = none (the villager's age in whole years must be at most this) |
| 9 | `B` | special: 0 none, 1 golden_child, 2 tribal_chief, 3 nursing_parent (the role MUST be that villager); **4 prefer golden_child, 5 prefer tribal_chief** (section 35: taken when they may be cast) |
| 10 | `H` | skill requirement: the skills' names, comma separated (`NONE` = no skill requirement) |
| 12 | `B` | skill min (the villager's value in at least one listed skill the game has is at least this) |
| 13 | `B` | pick: 0 random, 1 highest (keep only the villagers with the top value of the listed skills, then draw) |
| 14 | `H` | alias: member mask (bit k = role index k); other (kind 3): exactly one bit, the alias it follows; 0 for the rest |

- In v6 the compiler sets flags 2 and 4 exactly when it sets 32, so code that reads only 2 and 4 stays safe.
- `exclude_protected` (32) = keep out nursing parents of either sex, the Golden Child, the VV3 Tribal Chief, the
  VV5 special roles, VV2 totems, the VV3 stand-in record and anyone the stock pickers skip.
- `harm_capable` (16) is compiler-derived (section 7). A harm-capable role has 32 unless its author wrote
  `protected: "allow"` (section 7, the owner's protection model of 2026-11-14).
- A villager role may also require a kinship relation to another role (section 21); it is kept outside the role
  record, in the relations table.
- A skill name the game does not have is ignored in that game; when none of the listed names exists in the game,
  the skill requirement does not apply there.
- Alias (kind 2): flags 16 when harm-capable, else 0; sex 0, min_age 0, no requirements. It is never cast. See 6.
- **Other (kind 3, G2):** JSON `{"kind": "other", "of": "<alias role id>"}`. It is the member of that alias's two
  members that the alias did NOT draw. The alias must have exactly 2 members. Flags 16 when harm-capable, else 0;
  never cast. Usable wherever a role is: names, pronouns, effects, `role` and `harmable` conditions.
- **The first role (G7):** a villager the event needs (not optional) or a stranger. When any effect acts on a
  villager, at least one villager role must exist. An unprefixed placeholder or effect names `subject` when
  there is one, else the first role.
- **No roles at all:** `"roles": {}` is allowed when no text, label, condition or effect names a role (e.g. V20
  crisis D1, whose patient is story text). Role count 0 in the header; nothing is cast; `min_eligible` counts the
  village's villagers (as `min_population` does; v1.35.97 counted nobody, so such an event never happened). A
  name or pronoun placeholder, a role condition or a villager effect in such a graph is an error.

## 2a. Node record (28 bytes, unchanged size)

`B type, B append, B paragraph, B flags, H id, H text, H variant first, H variant count, H child first, H child count,
H else, H effect first, H effect count, H summary, H outcome, H title`. The flags byte (0 in v1-v5 and in every
file made before section 25): bit 0 = **auto lines** (section 25), only on a v6 popup node; any other bit, or bit 0
anywhere else, is refused by the loader. As v5, except the last H (0 in v1-v5): in
v6 it is the node's **popup title** string (section 14), or `NONE` **(differs from A4; the v6 compiler wrote 0
here before per-node titles, and nothing with that shipped)**. The loader refuses a v6 node whose title is not
`NONE` or a title the game can show (section 14), and a title on a branch.

## 3. Child record (12 bytes, unchanged size)

`H next, H weight, H cond, H else, H label, H guard` **(differs from A4: the last H, 0 in v1-v5, is the guard)**

- `guard` = `NONE`, or a cond (an op 9 `harmable`, or an op 6 `all` of op 9s) the compiler adds to a child of a
  popup or branch node whose target node has a harmful effect on a role with flag 32. The child applies only when
  its `cond` AND its `guard` hold; otherwise it is replaced by its `else` (same weight) or left out, exactly as a
  failed `cond`. If no child is left and the node has no `else`, the event ends at that node.
- A question's choices are child records too: `cond` = the choice's `if` (`NONE` when none), `else` = `NONE`,
  weight 1, guard `NONE`. A choice whose `if` fails is not shown; the buttons close up (keep a button-to-choice
  map). The compiler guarantees at least 2 shown in every game and context it can know statically.

## 4. Pools and items

- **Pool: 12 bytes (G3; was 8).** `H name string, H first item, H item count, B flags (1 = distinct, **2 = linked**, section 37), B 0,
  H distinct_from (a string: the pool names, comma separated; NONE = none), H 0`.
- `distinct_from` (G3): an instance of this pool never draws an item whose TEXT equals the text of an item already
  drawn on the run by any instance of a listed pool (see 6.3).
- **Item: 8 bytes.** `H text string, H weight (1..10000), H cond (NONE = always), H 0`.
- Pool names: `[A-Za-z0-9_]{1,32}` for named pools; `@word` for game words; `_iN` (N = 1, 2, ...) for inline
  picks. Names are unique.
- Game words: each `"words"` entry `w` becomes the pool `@w` with one item per distinct text, each item's cond a
  `game` cond (op 3) of the games that use that text. Exactly one item holds in each listed game.
- Inline picks `{a|b}` / `{3:a|1:b}` never reach the binary: each becomes its own pool `_iN` and the text holds
  `{_iN}`. An alternative may hold a game word (`{the {@chief}|the elders}`, G4): the `_iN` item then holds
  `{@chief}`. Nested inline picks are refused.
- A one-option brace `{x}` (G4) whose `x` cannot be a pool or game-word name (it holds a space, or a character
  outside `[A-Za-z0-9_]` and the `.k` instance) is just the text `x`: `normalize` removes the braces, so it never
  reaches the binary. An identifier-shaped `{x}` must name a defined pool (or `{@x}` a game word); otherwise it is
  a validation error ("unknown list x"), so a misspelt list never ships as visible text.
- **`{@tribe}` and `{@Tribe}` (G5)** are built in: no pool is written for them and authors cannot define them. The
  engine fills them AT RUN TIME with the player's tribe or village name from the save (the per-game read The
  Troubling Signs uses, `native/vvfp_more_island_events/troubling_*.inc`), the capital form with its first letter
  raised; with no name, "the village" / "The village". The worst case is `W` x the longest name the game allows:
  31 in VV1/VV2, 19 in VV3-5 (`src/vv_tribe_rename.py`).

## 5. Text grammar in the binary (what `cg_text_ok` and `cg_expand` parse)

- Characters: v2's set (letters, digits, space, `. , ! ? : - ' "` and line breaks) plus `; / & %`, plus markup.
- `(token)`: a placeholder as in v5, plus:
  - v6 pronouns (male word, female word): `himself/herself`, `woman/man` (man, woman), `boy/girl`, `son/daughter`,
    each with an optional `role.` prefix and a capital form (`(Himself/Herself)`);
  - **role-sex words:** `mother/father`, `father/mother`, `mom/dad`, `sister/brother`, `aunt/uncle`, `girl/boy`,
    `lady/gentleman`, **`headman/headwoman`** (section 37) -- the word of the pair that matches the role's sex (a male role: father, father, dad, brother,
    uncle, boy, gentleman), with the optional `role.` prefix, the capital form and ALL CAPS, exactly as the pronouns
    (worst case: the longer word). E.g. The Lullaby's nursing parent: `(parent.mother/father)`. In the engine they
    are `CG_PH_MOTHER` .. `CG_PH_LADY`, after `CG_PH_SON`;
  - role shorthand `(roleid)` / `(Roleid)`: that role's name (role ids are matched ignoring case). A keyword
    (`name`, `name1`, `name2`, `award`, `award_unit`, a pronoun) always wins; the compiler refuses a role id that
    equals a keyword ignoring case, and two role ids that differ only by case.
  - **All caps** (for the owner's ALL-CAPS button labels and text): any placeholder written entirely in capitals
    -- `(NAME)`, `(NAME1)`, `(NAME2)`, `(GARDENER1)`, `(HE/SHE)`, `(HIM/HER)`, `(HIS/HER)`, `(MAN/WOMAN)`,
    `(HIMSELF/HERSELF)`, `(ROLE.HE/SHE)`, `(AWARD_UNIT)`, ... -- expands to the same word in capitals ("ANA",
    "HER", "TECH POINTS"). A role prefix is matched ignoring case. A placeholder is all caps when it has at least
    two letters and no lower-case letter. The fit check measures it as written: names `W` x name_room, the longer
    pronoun in capitals.
- `\(` and `\)`: a literal parenthesis. No other backslash appears.
- `{NAME}` or `{NAME.k}`, k = 1..8: pool `NAME`, instance k (`{NAME}` is instance 1). `NAME` is a pool name
  string (it may start with `@` or `_`). Braces never nest in the binary. A pool item's text may itself hold
  placeholders and pool tokens (not its own pool, depth at most 3, checked by the compiler).
- Labels (choice labels): placeholders, `\(` `\)` and game words `{@w}` only. At most 95 bytes in v6 (v1-v5: 39);
  with Scrolling Popups up to 4,095 (section 19).
- **Pronoun hint (labels only, section 15):** a name placeholder may end in `|` and a pronoun pair, e.g.
  `(ACCUSED|HE/SHE)`, `(Name1|his/her)`: the form its fallback takes (`he/she`, `him/her`, `his/her`,
  `himself/herself`, any case). Without a hint the fallback is `him/her`. The hint is refused in body text.
- Titles (G6): v6 titles may hold `"` too (every game's font draws it). At most 47 bytes (`CE_TITLE_BYTES` 48)
  in every game. VV1/VV2 wrap the title into the text (51 / 46 characters a line, as before). **VV3-5 (v6):** the
  dialog draws the title on ONE line, centred, in its own font (`ldwarialbold`), with no wrap and no cut (body
  draw 0x418510 / 0x416EC0 / 0x417660 calls the centred draw 0x40A070 / 0x409BE0 / 0x409EB0 with [dialog+0x54]);
  so the title is checked by its pixels in that font (`data/font_glyph_tables.json`), at most the body text's
  width: 432 px in VV3/VV4, 624 px in VV5. The engine needs no change (graph pages never apply the in-game
  editor's 30-character check, `check_title = 0`). Versions 1-5 keep the 30-character rule.

## 6. The walk (cg_walk) and the random stream

`random_below(n)` is `ce_random_below`: it consumes NO roll when n <= 1; else one roll, `% n`.
`roll_index(weights, roll)` is `ce_roll_index`.

1. **Aliases.** At the start of the run (before the first segment's first node), each alias role in role-index
   order is drawn among its members that are bound: `members[random_below(count)]` (members in role-index order).
   No member bound: the alias is unbound. Stored in the run's picks. An `other` role (G2) then binds, with no
   roll, to its alias's member not drawn; it is unbound when that member is unbound or the alias is.
2. **Per node**, in this order (v5 order plus step b):
   a. each effect's roll, in effect order (v5 rules, plus the v6 rolls below);
   b. **pools**: the node's chosen text (the variant `cg_node_text` picks; for a question also each label after
      the text, left to right) is scanned left to right; each pool instance not yet drawn on the run is drawn
      when met, and its item's text is then scanned the same way (depth first) before the scan continues;
   c. the child draw (v5), with the guard.
3. **One instance draw:** eligible = the pool's items whose cond holds now (game, patches, bound roles, the path so
   far including this node, and the runtime facts of section 8). If the pool is distinct, take out the items
   already drawn by its other instances; then, with `distinct_from`, take out every item whose text equals the
   text of an item drawn so far (on the path and this segment) by an instance of a listed pool; if what is left is
   empty, keep the full eligible list. None eligible: the
   instance is the empty text, no roll. Else `k = roll_index(weights, random_below(sum of weights))`.
   Picks are stored as (pool, instance, item index within the pool); at most 256 a run (`CG_MAX_PICKS`).
4. **v6 effect rolls** (fx a, fx b as stored in the history):
   - celebrate (11), action (12), mood (13): no roll; a = b = 0.
   - health_change (14): a = lo + random_below(hi - lo + 1).
   - skill_set (15): as skill (9): a = the skill index chosen (`cg_skills`, random_below(count of listed skills the
     game has)); b = the set value (no roll).
   - damage (16): a = lo + random_below(hi - lo + 1), the percent. The structure is chosen when the effect is
     made (game state), not in the walk.
   - skill (9) may now be negative (both of min, max in -100..-1): same roll, `lo + random_below(hi - lo + 1)`.
   - appearance (17): a = the head's, b = the body's: a fixed row is itself (no roll), "kept" is -1 (no roll),
     "random" is `random_below(rows - 1)` (the head's first, then the body's; rows = the game's count, section
     22). die_unrecovered (18), baby_lost (19), birth_then_die (20): no roll; a = b = 0.
5. **Expansion** (`CG_EXPAND_REAL`): placeholders by the bindings; `{P.k}` by the drawn item's text, expanded
   again (depth at most 3); `\(` `\)` become `(` `)`; then the glyph fallback (9) over the whole result.
   - **No "!." or "?.":** when an inserted pool item (an inline pick's and a game word's included; never
     `{@tribe}`) expands to a non-empty text ending in `!` or `?`, and the very next character of the text holding
     the token is `.`, that one `.` is dropped: `{_i1}.` with the item `Yikes!` reads `Yikes!`. It applies at every
     depth (an item's own tokens first) and in every mode that fills pools (`CG_EXPAND_AWARD`, `CG_EXPAND_WORST`,
     `CG_EXPAND_REAL`; Python `expand_v6`, `worst_v6`). Only the one character right after the token counts: a
     space, a placeholder or another token in between keeps the `.`.
6. **Worst case** (`CG_EXPAND_WORST`): names `W` x name_room; the longer pronoun; then the glyph fallback in VV1/VV2.
   - **Pages (engine).** `cg_fits` pages a popup with `CG_EXPAND_WORST`, and `cg_pool_text` returns the instance's
     DRAWN item when the run holds a pick (always, once the walk is done): pages are laid out with the drawn
     items and the longest names. Only with no pick does it take the longest eligible item by its raw bytes.
   - **Fit check (Python, `worst_v6`).** No run exists, so every pool instance is the pool's longest eligible
     item measured after its own worst-case expansion (the first on a tie). When the token is followed by `.`,
     each item is measured together with that `.` as step 5 leaves it (an item ending in `!` or `?` counts
     without it), so the widest item-and-stop is taken. That is never shorter than any item
     the engine can draw, so whatever Python accepts the engine can page; Python may refuse a little more than
     strictly needed. `simulate` returns each popup's whole text, before paging.

## 7. Harm and the protected filter

Harmful effects: `kill`, `vanish`, `die_unrecovered`, `baby_lost`, `birth_then_die`, `deliver_early`, `sick`, `health`
with max < 100, `health_change` with min < 0, `preference` dislikes, `skill` with a negative amount, `mood` bad, `action` from the
MOOD group or marked (Unsafe) in the game's action list (`data/cie_actions.json`). `appearance` is harmless.

- A role is harm-capable when a harmful effect anywhere in the graph acts on it, or on an alias whose members
  include it (an alias that is harmed makes every member harm-capable). Flag 16.
- `protected`: `"auto"` (default) sets 32 exactly when 16 is set; `"exclude"` sets 32 always; `"allow"` sets 32
  never.
- **The protection model (the owner, 2026-11-14, V28).** Only The Lost Children's totems are ALWAYS protected;
  everyone else -- nursing parents, the Golden Child, The Secret City's Tribal Chief -- may be harmed where the
  event makes sense, when its author opts in with `protected: "allow"` on that role, in a collection event as in
  a player's graph. The default `"auto"` still keeps them out, so nothing changes unless an author opts in.
  - A `special` role (it MUST be that villager) that is harm-capable needs `"allow"`: with `"auto"` its own
    villager would be kept out and the role could never be cast (an error).
  - **Always kept out of a harm-capable role, whatever its `protected`:** The Lost Children's totem statues (the
    adapter's `listed` never lists them, so they are never cast at all), The Secret City's stand-in record, New
    Believers' Heathens (believers only) and New Believers' story villagers (roles 12-17: the chief, the Retired
    Chief, the puzzles' Heathens; **UNCONFIRMED** whether harming them is safe, so they stay out: an owner
    question). The engine refuses a harmful effect on them even if they were bound (`cg_never_harmed`).
  - `scripts/collection_check.py --allow-report` lists every `allow` on a harm-capable role in the collection, for
    the owner's review.
- The guard (3) is added only for roles with flag 32.

## 8. Effect codes and cond ops (v6 additions)

Effect record unchanged (16 bytes: `B code, B role, B flags, B 0, i a, i b, H string, H 0`).

| Code | do | role | a, b | string |
|---|---|---|---|---|
| 11 | celebrate | role index, or 0xFF = every living, listed villager | 0, 0 | NONE |
| 12 | action | role index | 0, 0 | the action's label words (the game's own, as in `data/cie_actions.json`) |
| 13 | mood | role index | a = +1 good, -1 bad | NONE |
| 14 | health_change | role index | a..b signed delta; result clamped to 1..100 (never kills) | NONE |
| 15 | skill_set | role index | a = value 0..100 | the skills, comma separated |
| 16 | damage | 0xFF | a..b percent 1..100 | the structures, comma separated, or `any` |
| 17 | appearance | role index | a = head, b = body: a row 0..29, -1 random, -2 kept | NONE |
| 18 | die_unrecovered | role index | 0, 0 | `unknown` (always; the engine says "Unknown causes" whatever it holds) |
| 19 | baby_lost | role index | 0, 0 | NONE |
| 20 | birth_then_die | role index | 0, 0 | the cause (as kill's) |
| 21 | old_look | role index | 0, 0 | NONE (section 27) |
| 22 | sex_change | role index | 0, 0 | NONE (section 29) |
| 23 | presentation | role index | a = 1 the other sex's look, 0 the villager's own again; b = 0 | NONE (section 31) |
| 24 | deliver_early | role index | 0, 0, or a..b: the newborn's extra health loss (-99..-1) | NONE (section 30) |
| 25 | supply | 0xFF | a..b the change, a gain 1..9999 or a loss -9999..-1 (the three VV4 supplies: 1..99) | a good's word (sections 38, 39) |
| 41 | trade | 0xFF | a = given (1..9999), b = got (1..9999) | `give,get`: two goods' words (section 39) |
| 42 | group | role index, or 0xFF = the whole village | a = the share made sick (1..100, `sick` only), else 0; b = 0 | the kind's word (section 40) |
| 43 | village | 0xFF | a..b: hours (event_timer), points (construction), the step +1 / -1 (tech_level), 0, 0 (weather) | `event_timer`, `construction`, `tech_level` or `tech_level:<area>`, `weather:<word>` (section 41) |

A role byte may name an alias; the effect goes to the member drawn. Codes 17-19 are section 22; code 20 is section 23, code 21 section 27,
code 22 section 29, code 23 section 31, code 24 section 30, code 25 section 38. **Numbering:** the new name of section 28 is a role kind
(a stranger's flag), not an effect code.

Preference (8) in v6 may be **random** (section 24): flags bit 8 set, string `NONE` (bit 4 still says dislikes).

| Op | cond | a | Holds when |
|---|---|---|---|
| 17 | has_dead_relative | role index | the role's villager is bound, not gone, and has lost a recorded parent or a co-parent (section 21a) |
| 18 | is_special | role index | the role's villager is bound, not gone, and is A New Home's Golden Child or The Secret City's Tribal Chief (section 37) |
| 19 | has_supply | the good's word (string); the next H = at least (0..9999) | the village has at least that much of the good to give now; 0: the game keeps the good now (section 39): a run-time fact, allowed in a child's, a variant's, an item's and the requirement's `if`, never a choice's |

| Op | cond | a | Holds when |
|---|---|---|---|
| 9 | harmable | role index | the role's villager is bound, not gone, and not protected now |
| 10 | special_present | 1 golden_child, 2 tribal_chief | that villager is alive and listed |
| 11 | min_population | n | at least n living, listed villagers (VV5: believers) |
| 12 | min_children | n | at least n living, listed villagers under 14 |
| 13 | age | role index; b = min years; the last H = max years (0 = none) | the role's villager is bound, not gone, and its age in whole years is in min..max |
| 14 | skill_at_least | role index; b = min (1..100); the last H = the skill's name string | the role's villager is bound, not gone, the game has that skill, and its value is at least min (the scale of a role's skill requirement, `cg_skill_value`) |
| 15 | has_living_child | role index | the role's villager is bound, not gone, and a living, listed villager's recorded father (a male role) or mother (a female one) is it: the parent's name, head and body on the child's record (VV2-VV5; A New Home keeps no parents on its records, so it never holds there) |
| 16 | drew | pool index; b = instance (1..8); the last H = the item's index in the pool | that pool instance drew that item earlier on the path (the run's picks, this segment's included) |

JSON (items 8 and 9): `{"age": {"role": r, "min": a, "max": b}}` (years 0..120, at least one of min / max);
`{"skill_at_least": {"role": r, "skill": "Healing", "min": n}}` (a skill some game of the event has);
`{"has_living_child": r}`; `{"drew": {"pool": "P", "instance": k, "item": "slug slime"}}` -- the item by its TEXT
(instance defaults to 1; the text must be exactly one item's of that pool, a shared pool's included; the compiler
writes its index). A role-based op on an alias or other role asks about the member drawn. These are run-time facts:
the patcher's walk takes each one either way (`harmable` as well); `simulate` takes them from `facts`
(`"age:<role>:<min>:<max>"`, `"skill_at_least:<role>:<skill>:<min>"`, `"has_living_child:<role>"`, max 0 = none),
and `drew` from the run's own picks. They may stand in a variant's, a child's or an item's `if`; never in a
choice's `if` or the requirement's; `drew` never in a variant's either (a page's text is laid out once its segment
is walked, so only a child's draw and an item's draw see the picks "so far": the child after its node's own pools,
an item when its instance is drawn).

`role` (op 2) on an alias holds when the alias is bound (6.1). Choice `if` may use only game, patch, role,
special_present, not, all, any.

## 9. Glyph fallback (VV1 and VV2 only, and only without the Unicode Text companion)

Applied to the whole expanded text, character by character:
`;` -> `,`  `(` -> `-`  `)` -> `-`  `&` -> `and`  `%` -> ` percent`. Everything else unchanged.
VV3-5 never substitute.

## 10. Sizes (compile-time sugar; nothing at run time)

`{"do": "food" | "tech", "size": "small" | "normal" | "large" | "huge", "loss": false, "scaled": true}` is
expanded by `normalize` into a v5 `per_game` table (design A3); a loss is the same range negated. The `.cieg`
holds only `per_game`.

- **damage (G9):** `{"do": "damage", "size": ...}` becomes min..max percent: small 10-30, normal 25-50, large 50-75,
  huge 75-100 ("collapses", "destroyed", "falls down" = huge; 100 percent = unbuilt, as The Rumblings does).
- **skill:** `{"do": "skill", "size": ...}` becomes min..max: small 5-10, normal 10-20, large 20-40, huge 30-60
  (`"loss": true` negates it); "masters" is `"set": 100`.

## 11. Answers

2 to 7 answers in v6 (`MAX_ANSWERS = 7`). The text lines a question keeps for its buttons beyond the game's two
(`answer_room` = `story_graph.inc cg_answer_room`): `3 x (n - 2)` for n <= 4; for n = 5..7,
`ceil(2.5 x (n - 1) - 3)` (7, 10, 12: `CG_ANSWER_LINES`), and from five answers never more than the layout's lines
less the title it leads with (5 in VV1/VV2) less 3. The question's pages use the question layout.

**With Scrolling Popups installed, section 19 replaces everything below in this section (no pages, no button room, no G1).** Without it:

**G1: the answer's page.** With 2 to 4 buttons shown, the answer's first page is shown in the question's popup,
keeping the same room (unchanged). With **5 or more buttons shown**, the answer's first page starts a FRESH popup:
the NOTICE layout -- the plain popup's, which is the popup it is shown through (`story_graph.inc
cg_notice_layout`; New Believers 14 lines, not the result's 17) -- with no room for buttons (only the refusal lines
when it makes changes). It counts as one more
popup on the history. `tests/test_cie_graph_v6.py` pins Python and the engine's source together for
n = 2..7 in all five games. Labels: at most 95 bytes in v6, measured against the screen width (`label_max_px`);
the popup's inner width in pixels is UNCONFIRMED.

## 12. Python API (stable names; Track D imports these)

```python
import vv_cie_graph as cg
g, problems = cg.normalize(data, shared_pools=None)   # shape + defaults; v6 sugar expanded (size, words "*",
                                                      # include_pools, inline-pick canonical form)
g, problems = cg.validate(data, scrolling=False, shared_pools=None)   # every check (calls normalize)
g = cg.load(path_or_data, scrolling=False, shared_pools=None)         # GraphError when problems
blob = cg.compile_graph(g)            # bytes; each graph at its own version
g2 = cg.decompile_graph(blob)         # == cg.without_names(g) for a validated g
cg.harm_capable(g)                    # set of role ids
cg.simulate(g, game, rolls, bindings, answers=(), patches=(), facts=None)   # the engine's walk (section 6)
cg.chances_table(g, game)             # text
cg.SHARED_POOLS                       # default path: data/event_collection/shared_pools.json
```

`shared_pools` is a dict `{"pools": {name: POOL}}` or a path; by default `SHARED_POOLS` is read when a graph
has `include_pools`; that file is `{"pools": {name: POOL}}`, POOL as in a graph. Authoring keys kept by
`normalize` but never compiled: node `name`, `src` (on nodes, variants, choices, effects, pools and items), node
`text_only_reason`, graph `grammar_fixes`. `without_names` drops them.

## 13. Shared vectors

`tests/data/cie_v6_expand_vectors.json` (rebuilt by `python tests/test_cie_graph_v6.py --write-vectors` from
`simulate`). Each case gives the graph, the game, the rolls, the bindings, the answers, the facts and the Unicode
flag; `expect` gives the path, every effect roll `[a, b]`, every pool pick `[pool, instance, item index]` in draw
order, the aliases drawn, each popup's text before paging, the rolls used and the `.cieg` SHA-256.

- Answer segments: at each question, every SHOWN answer's segment is walked in choice order from the same state
  (each consumes its own rolls), then the clicked one is kept (as `cg_walk_answers` does today).
- `simulate` assumes the facts stay the same for the whole run.

## 14. Per-node popup titles

JSON: a popup or question node may carry `"title": "..."` (v6 only; never on a branch, which shows no text). The
title is checked exactly as the event's title (section 5, G6): its characters, at most 47 bytes, VV3-5 by its
pixels in `ldwarialbold` against the body width (432 / 432 / 624 px), VV1/VV2 by `title_width` as the event title.

**The title in force.** At the start of a run it is the event's own title. When a node with a title is reached, the
title in force becomes that string from the page that node's text starts on, and stays for every later page (the
answers of a later question included) until another titled node is reached. One exception: the answer's first page
after a question showing 2 to 4 buttons is shown in the question's own popup and keeps the title that popup shows;
a title set by a node starting on that page takes effect from the next page.

- **Pages (engine).** Each display keeps the title in force on it (`cg_state.display_title`: the string index + 1,
  0 = the event's title). A page's title is the title of the last change (the popup's starting title, then each
  titled node in it, by where its text starts in the popup's raw text) that starts before the page's end. `cg_arm`
  arms the stub with the display's title (VV3-5 draw it); `cg_show` and `cg_begin_question` compose with it (VV1/VV2
  lead the text with it). `VvfpStoryGraphLogged` accepts the event's title or the title armed.
- **Fit (both sides).** A popup is paged with its WIDEST title: of the titles in force anywhere on it (the one at
  its start and each titled node's in it), the one whose worst case wraps into the most lines (the first on a tie).
  Only VV1/VV2 lead their text with the title, so only their pages change.
- **The event's title** is still the one the Island Events log, Pick Island Event and the library show.
- **simulate** returns `titles`: for each popup, the title its first page shows (expanded as the text is).

## 15. Button labels: names fall back to pronouns

For BUTTON LABELS only (never body text): at run time a label is expanded with the real names; when that is wider
than the screen-fit limit (`label_max_px` / `ce_label_max_px`) or longer than 95 bytes, the label is expanded again
with every name placeholder in it as its role's pronoun (the role's sex; an alias's member drawn), in the case the
placeholder is written in: `(NAME1)` -> `HIM` / `HER`, `(Name1)` -> `Him` / `Her`, `(name1)` -> `him` / `her`. The
pronoun is the object form unless the placeholder carries a hint (section 5): `(ACCUSED|HE/SHE)` -> `HE` / `SHE`.

- **Engine:** `cg_label_text` (used by `cg_begin_question` for the buttons and by `cg_resolve` for the log's
  "Choice:" line) measures the real-name label with `ce_label_px` and substitutes when it is too wide.
- **Fit (Python):** a label passes when its worst case with the longest names fits, OR its worst case with every
  name as the longer pronoun of its form fits (the engine then shows the pronoun form whenever the names do not).
- **simulate** returns `labels`: for each question asked, its shown buttons' labels as the player reads them (the
  real names, or the pronoun form when they do not fit the game's screen).

## 16. Named strangers

JSON: `{"kind": "stranger", "sex": ..., "named": true}` (v6). Binary: the stranger's role flags = 1 (0 for a nameless
one; any other bit is refused). A named stranger has a first name, so `(visitor)`, `(Visitor)`, `(VISITOR)` and
`(visitor.name)` are valid for it (a nameless stranger's are still refused: "a stranger has no name").

- **The name** is drawn at bind time from the game's OWN first-name lists -- the two lists its villager creator draws
  a new villager's name from, male then female (`data/cie_villager_names.json`, built from the stock executables by
  `scripts/build_cie_villager_names.py`, pinned by `tests/test_cie_graph_v6.py`). The engine reads the list of the
  stranger's sex from the game at run time (`story_villager_names.h CG_NAMES_VA`: one comma-separated string each),
  and uses the same list built into the DLL when the game's cannot be read (not letters and commas, or not readable).
- **The draw**, in the bind's role order: the stranger's sex as for every stranger (one roll when random), then
  `random_below(count)` over the list's names that no living villager has (compared with each living villager's
  first name, the name before any space, ignoring case) and no named stranger bound earlier in the event has; when
  none is left, over the whole list. Pronouns follow the sex drawn.
- **Worst case:** `W` x the longest name in the game's two lists (A New Home 6, The Lost Children 7, the later three
  8). Python's `simulate` takes the stranger's name from `bindings` (as it does a villager's).

## 17. Placeholders in titles

A v6 title -- the event's (header +20) or a node's popup title (section 14) -- may hold placeholders: a name
(`(Name1)`, `(name)`, `(visitor.Name)`, `(Gardener1)`, a named stranger's), a pronoun (`(his/her)`, `(role.He/She)`,
the v6 pairs), in any case form (section 5), and a name's pronoun hint `(NAME1|HE/SHE)` (section 15). Nothing else:
no award, no pool, game word or inline pick, no `\(`; a parenthesis is only a placeholder. A role a title names is
never optional (an alias's or other's members included), so it is always bound. Example: `(Name1)'s No Good, Very
Bad Day`.

- **On screen** (engine, `cg_title_text`): the title expanded with the real names (`CG_EXPAND_REAL`, so the glyph
  fallback in VV1/VV2 -- titles never hold those characters). When that does not fit -- 48 bytes or more; VV3-5 wider
  than the title box in `ldwarialbold` (`story_title_widths.h`, built by `scripts/build_cie_title_widths.py` from
  `data/font_glyph_tables.json`: 432 / 432 / 624 px); VV1/VV2 longer than `title_width` (51 / 46) -- every name in
  it becomes its role's pronoun, as a label's (section 15: the object form, or the hint's, in the written case).
- **Fit (Python):** each game checks the title's worst case (names `W` x the room: a villager's `name_room`, a named
  stranger's longest list name; the longer pronoun); when that does not fit, the worst case with every name as the
  longer pronoun of its form must. The pages of VV1/VV2 (which lead the text with the title) are laid out with the
  worst case of the form that fits (names when they fit, else pronouns).
- **Before anyone is cast** (Pick Island Event, the library, Game Mechanics, the manifest, the refusals, "is on its
  way"; `cg_readable`): the title **as written**, placeholders kept, cut to 47 bytes -- e.g. "(Name1)'s No Good,
  Very Bad Day" (the owner, 2026-11-14: the "(Name1)" is intentional).
- **The Island Events log** ("Event:" line, "Disappeared in ..."; `cg_title_logged`): the title with the cast
  villagers' real names, never pronouns (the log has no title box) -- e.g. "Ana's No Good, Very Bad Day".
- **The library's file name** (`library_stem`) is made from `readable_title`: every name placeholder "someone" in
  the case written, every pronoun or role-sex word its pair joined by "or" ("he or she", "mother or father"), cut
  to 47 bytes, then letters, digits, space, - and _ only.
- `VvfpStoryGraphLogged` accepts the title as written, or the title armed (expanded).

## 18. Title variants

JSON (v6): `"title_variants": [{"if": COND, "title": "..."}]` beside `"title"`. The event's title in a game is the
first variant whose condition holds, else `"title"`. A variant's condition uses only `game`, `patch`, `not`, `all` and
`any` (it is decided before anyone is cast), and each variant title is checked exactly as the event's title
(sections 5 and 17). The first use: New Believers with Guardians of Isola Rewrite (`{"patch": "guardians_of_isola"}`)
shows "The Homesick Newcomer" for "The Homesick Convert" (docs/event-collection/guardians-wording.md).

- **Binary:** variant records (`H cond, H text`, as a node's) placed after every node's variants; header +92 the
  first, +94 the count. A file without title variants keeps 0, 0 there, so it is byte for byte as before.
- **Engine** (`story_graph.inc cg_choose_title`): `cg_refusal`, `cg_queue` and the resume of a saved run pick the
  title with the patches on now (`cg_patches_on`) into `cg_g.title`, so the popups, the log's "Event:" line, the
  refusals and `VvfpStoryGraphLogged` use it. The loader refuses a variant whose condition or title is not valid.
- **Lists made before casting** (Pick Island Event, the library's collection group) read the title from the
  collection's manifest.txt, whose New Believers lines carry the title with Guardians of Isola Rewrite on
  (`story_collection.inc sc_scan`, `cg_guardians_on`).
- **Python:** `normalize` keeps it, `compile_graph` / `decompile_graph` round-trip it, `event_title(g, game,
  patches)` gives the title, and `simulate` returns it as the first popup's title. Pinned by the shared vectors
  `title_variant_vv5_guardians`, `title_variant_vv5_plain` and `title_variant_vv3_guardians`.

## 19. One popup per island event (with Scrolling Popups)

The owner, 2026-11-14 (after The Parent's Lesson, live in A New Home, showed its title, the top of the villager's
picture and seven buttons, and no question text): every new island event (More Island Events, the Isola Grand Event
Collection, Custom Island Events; the games' own events stay as they are) appears in ONE popup.

- **The texts.** With Scrolling Popups (`cg_one_popup` = `cg_scrolls`), the run's text from the start, or from an
  answer, up to and including the next question, or the ending, is ONE text (`cg_group`; Python `one_popup`): what
  were popups of their own (a node with `popup: new`, the question) join after a blank line (`"\n\n"`,
  `ONE_POPUP_JOIN`), appended nodes as before (a space or a line break). A text is never split into pages; it is
  laid out as one page (only a text longer than the popup holds would be split, and the checks refuse one: below).
- **The choices** sit at the END of the text, INSIDE the scrolled content: Scrolling Popups draws them as rows after
  the text (each the game's own answer-button picture with the label in the body text's font, as shown: sentence
  case, section 20) and hit-tests them at their scrolled place (`native/shared/one_popup.h`, `VvfpOnePopupRows` /
  `VvfpOnePopupPick`). The keys 1 to 7 pick them. The game's own two answer buttons are never shown; its OK only
  while no choice is asked.
- **An answer** shows its text (up to the next question, or the ending) in the SAME popup, scrolled to its top; a
  question there puts its choices at its end again (`cg_resolve`). The game's OK ends the event (`cg_op_ok` returns
  0). One window from start to finish.
- **The choice picked starts its answer's text** (the owner, 2026-11-14): its label exactly as its row showed it
  (section 15's names or pronouns, section 20's label case), alone on the first line of the text's own words, then a
  blank line, then the outcome -- `"Honesty\n\nTruth with Kindness: ..."`; no "You chose:". In A New Home and The
  Lost Children it comes after the title line and the villager picture's gap the dialog keeps. An answer with no
  text of its own shows the label alone. Story Upgrades composes it into the text (`cg_op_lead`, `cg_compose_once`);
  More Island Events question events the same (`mie_one_popup.inc` `mop.lead`, its labels as its rows show them).
  It is display only: the Island Events log's "Choice:" line is unchanged and the label line is never logged.
  Python `one_popup` puts the label at its widest (`chosen_label`) and `ONE_POPUP_JOIN` before the answer's `worst`,
  so the bytes below count it. Only with Scrolling Popups; the paged popups without it have no label line.
- **Arming.** The run is armed ONCE: as a question when its start can reach a question through pages and branches
  (`cg_start_may_ask`), so its popup is the game's question popup (A New Home's and The Lost Children's encounter
  dialog, the later games' two-choice dialog), else as a plain event (one text, OK). Nothing waits for another
  island-event trigger between its texts: the owner's live A New Home bug (a picked event's question waited for the
  next trigger after its intro page and the village's opening event took it) cannot happen.
- **Effects** are made when the text that tells them is shown (an answer's at its click, with its text); the Island
  Events log keeps ONE entry (a "Choice:" line for each answer). Island Events Seen counts the event once.
- **Bytes (practically unlimited, the owner 2026-11-16).** A text may hold up to `CE_LONG_TEXT_MAX` = 100,000
  bytes at its widest (Python `LONG_TEXT_MAX`), a title or a choice's label up to 4,095 (`CE_LONG_LINE_BYTES` 4,096
  with the NUL; Python `LONG_LINE_BYTES`) -- sanity caps sized to the file (`CG_MAX_FILE` 16 MiB, read into memory as large as the file; `validate` checks the compiled size, Python `MAX_FILE_BYTES`, and one run's words against `CG_DISPLAY_BYTES` 1 MiB, `DISPLAY_BYTES`). The dialog's own
  field holds 2,000 bytes in the later games and 9,999 in A New Home and The Lost Children: a longer text is put
  there as its start (`one_popup.h op_long_text_put`: a little short of the field, at a space) and Scrolling Popups
  draws the WHOLE text (`VvfpPopupWholeText`); a label longer than `op_rows.labels` holds is handed over whole
  (`op_rows.label_text`). Lines do not count: the popup scrolls. A choice is a row that wraps its label into as many
  lines as it needs (never the screen-width rule of section 15, never pronouns for width); in the later games a
  title wider than the text box wraps at the top of the scrolled box (A New Home and The Lost Children lead the
  text with the title: its first line, the rest after the picture's gap, `cg_title_wrap`). The run file is version
  5 (`CG_DISPLAY_BYTES` 1 MiB of displays' words; versions 2 to 4 kept 49,152 and are read widened,
  `cg_file_widen`).
- **Without Scrolling Popups** the old caps stay (1,990 bytes a text, 95 a label or a title as written, the pages);
  `validate(scrolling=False)` says so in each problem, and the engine refuses to queue an event whose texts are
  longer than them where the popups do not scroll (`cg_g.long_text`, `cg_refusal`).
- **The popup's size**: the constructor's own, for its first text, with the rows and the room OK keeps below them
  (5/2 of OK's height) instead of the room for the game's buttons, capped to the screen; later texts scroll in it.
- Without Scrolling Popups everything is as before (pages, button room, G1).

### 19a. A fresh page without a question (`"new_page": true`, the owner, 2026-11-16)

A popup node (popup "new") may carry `"new_page": true` (node flags bit 1, `0x02`): with Scrolling Popups it starts
the event's one popup afresh, as an answer does, instead of joining the text before it -- so a long event never has
to cut its words to fit the game's popup (1,990 bytes; 8,000 in A New Home and The Lost Children). Without
Scrolling Popups it changes nothing (that node opens a popup of its own anyway). The fit check measures each part on
its own (`one_popup`).

## 20. Sentence case

The owner, 2026-11-14: the entire event text is shown in sentence case, the choices too ("Honesty", not
"HONESTY"); capitals that mean something stay. The source writes some labels and lines in capitals; the
data is never changed: the rule is applied to what is shown, by the same code shape in Python (`sentence_case`,
`title_case`) and in the engine (`cg_sentence_case`, `cg_title_case`), pinned equal on every collection text, label
and title by `tests/test_sentence_case.py`. It is applied to a version 6 text as shown (`cg_expand` REAL and WORST,
not the award pass; a popup's whole text; a label -- `cg_label_text`, Python `label=True` -- as a label), before
anything is filled in:

- a WORD is a run of letters (A-Z, a-z, Latin-1 0xC0-0xFF but 0xD7 and 0xF7), an apostrophe between two letters
  inside it; it has a lower-case letter or not. Placeholders `(...)`, picks `{...}`, escapes `\x`, digits and
  punctuation are not words;
- a SENTENCE ends after a run of `.` `!` `?` and at a line's end (a `:` ends nothing);
- QUOTED text is inside `"` ... `"`, the cp1252 curly quotes 0x93 ... 0x94, or `'` ... `'`: a `'` opens a
  quotation when the unit before it is not a letter, digit, placeholder or pick and something other than a space
  follows it, and closes it when no letter or digit follows it (so "DON'T" and "(NAME)'S" open nothing); a line
  break ends any quotation;
- shown in SENTENCE CASE: outside quotations, a LABEL with no lower-case letter in the whole label and a
  word of two or more letters (a "!" too: "RUN!" is "Run!"); outside quotations, a story SENTENCE with no
  lower-case letter, a word of two or more letters and no `!` ("AN ALL CAPS LINE.", "WHICH LESSON SHOULD
  (PARENT) TEACH?");
- KEPT as written: capitals in a sentence (or a label) that holds a lower-case letter -- emphasis, a word or a
  phrase ("it was HUGE", "I said DO NOT TOUCH the pot", "Parenting skill: MODERATE GAIN."); anything quoted, a
  whole sentence too ('"I HATE YOUR GUTS!"', a label that is a quotation); a story sentence in capitals with a `!`
  -- shouting, "CLOSE IT!", "WHAT IS THAT!?";
- in sentence case every letter, and every placeholder's letter, is made lower case -- so `(NAME1)` shows the name
  in its own case and `(HE)` "he" -- then the first letter of a word or placeholder that starts a sentence (the
  text's or a line's start, or after `.` `!` `?`, past spaces and quotation marks) is made a capital, the word "I" (also in "I'm", "I'll", "I've", "I'd") stays a capital, and so do the
  island's names "Isola" and "Isolan" ("Isola's" too). Villagers' names keep their own capitals (they are filled in
  afterwards);
- a pool's item is cased on its own the same way (as a label inside a label), its start not a sentence's start;
- there is no heading rule (the owner, 2026-11-14): subroute headings such as "THE TINY TYRANT:" leave the data in a
  content pass; until then a line like "THE TINY TYRANT: The child ..." is one sentence with lower-case letters and
  stays as written;
- a TITLE written in capitals (no lower-case letter, a word of two or more letters) is shown in title case: each
  word's first letter a capital, the rest lower case, a placeholder's name as written (`"(NAME)'S BIG DAY"` ->
  `"(Name)'s Big Day"`); any other title as written. The titles of section 17 (as written, logged, the library's file name) are made from it.

## 21. Kinship roles

JSON: a villager role may carry `"relation": {"spouse_of": r} | {"parent_of": r} | {"child_of": r} |
{"sibling_of": r} | {"grandparent_of": r} | {"grandchild_of": r} | {"aunt_or_uncle_of": r} | {"cousin_of": r}` --
this role's villager must be that relation of role `r`'s villager. `r` is another villager role the event needs (not
optional, not a stranger, alias or other role); one relation a role.

- **Binary:** the header grows to 104 bytes (section 1) and the relations table holds one 4-byte record per role
  with a relation: `B role, B kind (1 spouse_of, 2 parent_of, 3 child_of, 4 sibling_of, 5 grandparent_of,
  6 grandchild_of, 7 aunt_or_uncle_of, 8 cousin_of), B other role, B 0`, in role order. The loader refuses a relation whose roles are not two different villager roles, an unknown kind, or two
  relations on one role.
- **Casting.** A relation is a rule between two roles, so -- as an age gap (version 3) -- the roles are then filled
  by the search (`cg_search`, `cg_gap_ok`): each role in turn takes an eligible villager who keeps every relation
  and age gap with the roles already filled. STRICT casting (the rare roll, Pick Island Event): a relation the
  village cannot meet means the event is not drawn. PREFER (bought through the library): as every requirement, a
  role nobody can fill with its relation has its requirements dropped (the relation too); the safety rules never.
- **What each relation reads** (the game's own data; nothing is guessed, and nothing is matched by name alone):
  - *A villager's recorded parents.* The Lost Children to New Believers keep each child's father and mother on its
    own record (name, head and body: VV2 +0x57D / +0x596, VV3 +0xDF8 / +0xE11, VV4 and VV5 +0x1BC0 / +0x1BD9, as
    the Details screen reads them). A New Home keeps none on its records: there the parents come from the
    patcher's parentage sidecar ("VVFP VV1 Parentage.dll" `Vv1ParentageQueryNames` / `Vv1ParentageQuery`), only
    while that companion is loaded (the parentage log patch); without it no A New Home villager has parents here.
  - A parent field names villager X when its name, head and body are X's now (as `has_living_child`). The games'
    default fathers are never anybody: The Lost Children's Gong "?" (head 0, body 0), The Tree of Life's and New
    Believers' "Joey" / "Joey Joerson" (head 2, body 2), and A New Home's sidecar fallback "Unknown" (head 0, body
    0). **Known limit:** a parent whose look changed after the child was born (Change Appearance, an island event,
    the `appearance` effect) no longer matches the child's record, so the relation does not hold for them.
  - `parent_of`: this villager is a recorded parent (father or mother) of `r`'s. `child_of`: `r`'s villager is a
    recorded parent of this one.
  - `sibling_of`: the two share a recorded mother, or a recorded father who is not a default father (half
    siblings count).
  - `spouse_of`: **no game keeps a spouse or partner field** (no record field; the games have no marriage). The
    relation is the nearest the games record: the two are the recorded father and mother of one living villager,
    or one of them is carrying the other's baby (the expected father on the mother: VV2 +0x5C0 / +0x5E0 / +0x5DC,
    VV3 +0xE48 / +0xE68 / +0xE64, VV4 and VV5 +0x1C10 / +0x1C30 / +0x1C2C; A New Home from the sidecar's
    `Vv1ParentageQueryExpectedFather`). An owner question: whether this is what "spouse" should mean.
  - **Wider kinship** (gap C2), built from the same parent links through a LIVING, listed villager in between (a
    dead villager's own parents are on no record the engine can read, so a link through them is not known):
    - `grandparent_of`: this villager is a recorded parent of a living villager P who is a recorded parent of `r`'s.
      `grandchild_of`: the same with the two swapped.
    - `aunt_or_uncle_of`: this villager is a sibling (as `sibling_of`) of a living recorded parent of `r`'s.
    - `cousin_of`: a living recorded parent of this villager and a living recorded parent of `r`'s are siblings.
    - The role-sex words `(aunt/uncle)`, `(mother/father)` etc. (section 5) name the role's side of it.
  - **Per game:** The Lost Children to New Believers: all eight, from their records. A New Home: only with the
    parentage log patch ("VVFP VV1 Parentage.dll" loaded); without it no A New Home villager has a recorded parent,
    so only `spouse_of` through an expected father can hold, and a kinship event is never drawn there otherwise.
  - The refusal ("it needs two who are ...") names them: "spouses", "a parent and child", "siblings", "a grandparent
    and grandchild", "an aunt or uncle and a niece or nephew", "cousins".
- **Python:** `simulate` takes the bindings as given (no casting), so relations change nothing there;
  `compile_graph` / `decompile_graph` round-trip them.

## 22. Appearance, death with no body, and a lost baby

- **`{"do": "appearance", "role": r, "head": n | "random", "body": n | "random"}`** (code 17; at least one of head
  and body). The villager's head and/or body becomes that row of the game's own sprite sheets (a head or body value
  is a row): A New Home 20 heads and 20 bodies, the later four 30 and 30; every row fits every age. A fixed `n` must
  be a row in every game of the event (0..19 when A New Home is one of them, else 0..29). `"random"` is any row but
  the villager's current one: the walk's roll `k` in `0 .. rows - 2` becomes `k`, or `k + 1` from the current row
  up, when the effect is made. The write is the Custom Island Event's own (`ce_apply_fields`: the record's head and
  body fields, as Origins' Change Appearance writes them), so it is saved with the village: permanent. The head
  look (young / old) is the villager's own sidecar setting and is not touched; "Reset to original" (VVFP Original
  Look) still knows the look before the event (an island event's change is never folded into the original).
  **The Secret City's Tribal Chief keeps the chief's robe** (the game's own robing gives body 29): their body is
  not changed, only their head. The Island Events log's entry gets "<name>'s look changed." beside the
  companion's Head / Body lines and its "Appearance changed" record. Harmless.
- **`{"do": "die_unrecovered", "role": r, "cause": "unknown"}`** (code 18; the cause is always
  `"unknown"`, or left out: any other cause is refused by the validator and the checker, and the engine ignores it). The villager dies and the body is never recovered: removed with no body, no skeleton and no grave
  (the adapter's `vanish`, the stock disappearance), and told to "VVFP Cause of Death.dll" as a DEATH:
  `VvfpCauseDiedUnrecovered(game, index, words)` writes a "Death <n>" record in the Deaths and Disappearances log
  with "Cause of death: Unknown causes" (the owner: every death from the new events is "Unknown causes"; an
  author never words it) and "Grave: no grave (the body was not recovered)", with the babies a nursing
  mother carried (as every Death record). The Village Statistics' reconciliation reads that record as a departure
  (a death), never a burial: its Grave line is "no grave", so Villagers Buried does not count it (the statistics
  log has no row that counts deaths or disappearances; "Villagers Died" was removed at the owner's instruction).
  The Island Events log's entry says "<name> died (Unknown causes); the body was not recovered." With an older Cause
  of Death companion (no export) it is told as a disappearance instead. Harmful; the role is gone for the rest of
  the run.
- **`{"do": "baby_lost", "role": r}`** (code 19). The nursing parent's baby is lost: the pregnancy ends exactly as
  the Custom Island Event's "0 babies" ends it (the adapter's `cancel`, every game: the countdown and the litter
  cleared as the delivery clears them, then the game's own stop that releases the place the pregnancy held; A New
  Home +0x358 / +0x35C, The Lost Children +0x540 / +0x544, The Secret City +0xE8C / +0xE90, The Tree of Life and New
  Believers +0x1C4C / +0x1C50). The games keep a nursing baby only as the parent's state, never as a villager (the
  owner: a nursing baby vanishes with no grave), so nothing else is written. "VVFP Cause of Death.dll" is told
  first (`VvfpCauseBabyLost`): the Births and Conceptions log closes the open Conception with a "Lost before
  birth" record ("What happened: the baby was lost in <title>; never born"). Babies Made stays as counted (the games
  count at conception). The role MUST be `"special": "nursing_parent"`, so it needs `protected: "allow"` (section
  7). **Children never carry in events (the owner, 2026-11-15):** a `nursing_parent` role has `min_age` 18 or more
  (the compiler refuses less; `NURSING_PARENT_MIN_AGE`), and the engine never casts anyone under 18 years (360 age
  units) for it, strict or preferred, whatever the role says (`story_graph.inc CG_NURSING_MIN_AGE`, a safety rule:
  never relaxed). So `baby_lost` never reaches a child. A parent no longer nursing when the page is shown (the baby was born since) is a refusal ("N changes could
  not be made"). Harmful. The Island Events log's entry says "<name>'s baby was lost."

## 21a. A dead relative (gap C3)

JSON: the condition `{"has_dead_relative": r}` (op 17): role `r`'s villager is bound, not gone, and has lost a
recorded parent or a co-parent. Like `has_living_child` it is a run-time fact: it may stand in a variant's, a child's
or an item's `if` (never a choice's or the requirement's); the patcher's walk takes it either way; `simulate` takes
it from `facts` (`"has_dead_relative:<role>"`). Use it so that a text that calls a villager bereaved ("still misses
(his/her) mother") is shown only to one who is.

- **What it reads** (the same records as section 21, read only; nothing is written):
  - *a dead parent*: a recorded mother, or a recorded father who is not a default father, whom NO living, listed
    villager matches by name (the name alone, so a parent whose look changed is still found alive);
  - *a dead co-parent* ("spouse"): the villager is a recorded parent of a living villager whose other recorded parent
    (not a default father) no living, listed villager matches by name, or the villager carries a baby whose expected
    father no living, listed villager matches by name.
- **Not known:** a dead child or a dead sibling. The games keep a villager's parents on the child's own record, which
  is gone when the child dies, and the engine does not read the patcher's Deaths and Disappearances logs; so a
  villager who lost only a child or a sibling does not hold (the condition never claims a loss it cannot see).
- **Known limit:** a recorded parent who was never a villager of this village (a Custom Island Event arrival's
  parents as the player named them) has no living match and counts as lost.
- **Per game:** The Lost Children to New Believers from their records; A New Home only with the parentage log patch
  (without it no A New Home villager has a recorded parent or expected father, so the condition never holds there).

## 23. The baby is born, then the parent dies

The owner (2026-11-14), for "Two Lives, One Decision" A3 ("The child survives but the mother dies"): the child must
really survive while the mother really dies. The owner's method: "alter the time to nursing so the baby(ies) is born
at that instant, and then set the mother's health to 0".

- **`{"do": "birth_then_die", "role": r, "cause": "unknown"}`** (code 20; the cause as `kill`'s, default
  `"unknown"`: the game's own "Unknown causes"). The role MUST be `"special": "nursing_parent"`, so it needs
  `protected: "allow"` (section 7). Harmful; the role is gone for the rest of the run.
- **What the games do (traced in the stock executables).** In all five games the nursing time is ONE field on the
  parent: the parent's processed-age counter copied at the conception (A New Home +0x358 from +0x34C, The Lost
  Children +0x540 from +0x534, The Secret City +0xE8C from +0xE74, The Tree of Life and New Believers +0x1C4C from
  +0x1C3C). The baby is never a record before its birth. The game's own villager catch-up -- once per age unit,
  while the parent's processed age is below their age and their health is above 0 -- makes the babies when the
  processed age is more than 40 units past the field (A New Home 0x42EF15..0x42F0C7, The Lost Children
  0x43BDFE..0x43BF85, The Secret City 0x46037F..0x46050C, The Tree of Life 0x4687E4..0x468A17, New Believers
  0x473100..): each baby is a NEW villager record made by the game's own creators, always at age 40 units (two
  years: the length of the nursing time) with its parents, and the field and the litter are cleared. A dead parent
  is never processed again, which is why a nursing baby vanishes with its mother. No death path writes the field
  or touches another record, so a child already born lives on as its own villager.
- **The effect (the adapter's `deliver`, then its `kill`).** While the parent is nursing:
  1. `elapsed` = the parent's processed age - the field (0..40: the nursing units already gone by);
  2. the field is set so the delivery is due now (the processed age - 41), and the parent is credited ONE age unit
     (a twentieth of a year, as a one-villager, one-unit Time Warp: the age field + 1);
  3. the game's own catch-up runs once, now: A New Home's villager tick 0x42E900 and The Lost Children's 0x43B690
     on a tick object made by the game's own constructor (0x42E570 / 0x43B280: the world and the villager array),
     The Secret City 0x45FFE0, The Tree of Life 0x468430 and New Believers 0x472C90 on the villager array (0x59E110,
     0x50E568, 0x554148). It processes that one unit for the parent -- what the game's next update would do -- and
     the delivery in it makes the babies with every patch's birth hooks, as at any birth. Every other villager is
     already caught up (each update runs the catch-up before the island-event trigger), so nobody else is
     processed; the effect is made from the event's popup, never from inside the catch-up;
  4. the birth is checked (the field is 0). If the game did not deliver, the field and the age are put back and the
     effect is a refusal: the parent never dies with the babies lost;
  5. **an early birth** (the owner): each new baby (a record that was free before the catch-up and holds a living
     villager after it) is given the age the nursing time had reached: age and processed age = `elapsed`, at least
     1 (an age of 0 is the creators' "draw a random age"); a full-term birth (`elapsed` 40) keeps the game's 40. It
     loses health for being born early: `round(50 * (40 - elapsed) / 40)`, at least 5 and at most 50 (a judgement
     call: the owner asked for "a health deficit" scaled by how early), never below health 1; a full-term birth
     loses nothing;
  6. "VVFP Cause of Death.dll" is told the babies were born (`VvfpCauseDelivered(game, index)`: its per-frame copy
     of the parent's nursing state is cleared, so the Death record does not say the babies were lost with the
     parent), then the parent dies by the adapter's `kill` (the game's own death: a body and a grave), the cause
     told as `kill`'s. Should the processed unit itself have ended the parent's life (the game's own old-age or
     starvation roll), the babies are still born -- the stock delivery runs in that same unit -- and the death is
     the game's.
- Twins and triplets are the game's own chain (the litter field); each baby gets the same age and deficit. At the
  population cap the delivery is the stock one: the babies' places were counted at the conception, and a creator
  that finds no free record makes no baby, as at any birth. Nothing is keyed on a record index.
- A parent no longer nursing when the page is shown (born since) still dies: the children are already villagers.
- The Island Events log's entry says "<name>'s baby was born early; <name> died." ("babies were" for more than one;
  "was born" at full term).

## 24. A random like or dislike (gap C1)

JSON (v6): `{"do": "preference", "role": r, "like": "random"}` or `"dislike": "random"`. `"like": w` /
`"dislike": w` is the same as `"list": "likes" / "dislikes", "preference": w` (normalize writes that form); a random
one may also be written `"preference": "random"`.

- **Binary:** effect 8 with flags bit 8 (bit 4 for a dislike, as before) and string `NONE`.
- **The roll** (section 6, step a): `k = random_below(P)`, P = the game's preference count (A New Home 47, The Lost
  Children 62, the later three 79). The word is chosen there and then, from the villager as the walk finds them: the
  candidates are the game's preferences, in list order, that are in NEITHER of the villager's lists (so never one
  they have, and never a like and a dislike of one word); the effect's `a` = candidate number `k % count`, or -1 when
  there is none; `b` = 0. Python takes the villager's lists from `facts`: `"likes:<role>:<word>"`,
  `"dislikes:<role>:<word>"` (none given: none held).
- **Made** as a fixed word's preference effect (a full list: the newest takes the last one's place). `a` = -1:
  nothing is changed and nothing is refused.
- A random dislike is harmful (section 7), as a fixed one.

**24a. Taking a like or dislike away (the owner, 2026-11-15).** `{"do": "preference", "list": "likes" | "dislikes",
"preference": w | "random", "remove": true}` (or `"like"` / `"dislike"` with `"remove": true`): flags bit 16 set
(bit 4 still says dislikes, bit 8 random), a = b = 0. With a word, that like or dislike is removed; with `random`,
one the villager holds. Automatic lines (section 25): "unlike" `<R> no longer likes <W>.` and "undislike"
`<R> no longer dislikes <W>.`. Removing a like is harmful (section 7); removing a dislike is not.

## 25. Automatic outcome lines (the owner, 2026-11-14)

Some outcomes are written only as instructions ("change hair color", "random like", "skill loss"). The effect is
made, and the popup says what happened in a short plain line, in the style of the Island Events log's lines.
**Exact amounts, true changes only** (the owner, 2026-11-19): every line of a change that has an amount states the
amount the game really makes -- gains and losses alike -- after the game's limits:

- food and tech (and the `(award)` amount): never below 0, never above CE_MAX_AMOUNT, counted through the pages'
  effects in order from the store as it stands when the pages are laid out (`cg_applied`);
- a cast villager's skill (0..100), health (1..100: a change never kills) and New Believers' Faith (up to 100),
  counted from the villager as the earlier pages leave them (`cg_predicted`);
- a damage: 0 when nothing finished in its list can be damaged, else the percent (at most 100).

A village with 20 food that is to lose 40 is told "The village loses 20 food." and loses 20; a skill at 95 that is
to gain 10 is told it gains 5; a change that changes nothing (no food to lose, a skill at 100, nothing to damage)
has **no line**.

**Applied = shown.** The amount counted at the layout (`cg_applied_fx`, by effect index) is BOTH what the line
states AND what is made when the page is shown (`cg_told_amount`: the food / tech store is changed by exactly it, the
skill or health set to the villager's value plus exactly it, Faith raised by exactly it). What really changed is read
back as it is made (`cg_told`); should the village have moved between the layout and the showing (food eaten, a
skill learned, so the store or the skill no longer holds the whole of it), the page's line is put right before the
page is shown (`cg_fix_lines`: the stated line, whole, becomes the line of the true change, or goes when nothing
changed) -- or, when that line was on a page already shown, the true line is added at the end of this one. A run
restored from its file after a quit has its pages but not their counts (memory only): its changes are the rolls,
through the game's limits, as before.

**A group's change** (a `target` of the whole village or N random villagers) is written as it is made
(`cg_group_line`, like section 39's lines): each member's change read back, then one line -- how many it changed and
by how much (one amount when all alike, else the smallest to the largest), or the one villager's name when it
changed only one. Nobody changed: no line.

**Singular and plural.** "1 tech point" / "N tech points"; a good's word follows its number (`cg_good_words`:
1 cutting tool, 2 cutting tools; 1 collectible, 2 collectibles; berry, coconut, blackberry); food stays "N food".

JSON (v6): `"auto_text": true` on a popup node (node flags bit 0, section 2a). The node's text is followed by one
line for each of the node's effects that has one, in effect order, each after a line break (`"\n"`; a node with no
text of its own starts with its first line). The lines are made from the walk's rolls (section 6) BEFORE the names
are filled in: `R` is `(<role id>.Name)` and `P` is `(<role id>.his/her)` of the effect's role (an alias: its member
drawn), so they expand, take the worst case and the sentence case (none applies: every line has lower-case letters)
exactly as the author's text. `S` is the skill's name as the game lists it (`Farming`), `W` the preference word as
the game lists it (`herbs`, `the dark`).

| Effect | Line |
|---|---|
The lines with an amount (`N` the amount made, never signed: the verb says which; `C` how many villagers, `L` the
smallest change of a group's range); the full table is `CG_AUTO_LINES` (`story_graph.inc`):

| Effect | Line |
|---|---|
| food, gain / loss | `The village gains N food.` / `The village loses N food.` |
| tech, gain / loss | `The village gains N tech points.` / `The village loses N tech points.` (1: `1 tech point`) |
| pay_award | the line of the award it pays (food or tech, as above), the amount paid |
| health (set) | `R's health is now N.` |
| health_change, gain / loss | `R gains N health.` / `R loses N health.` |
| skill, gain / loss | `R gains N S skill.` / `R loses N S skill.` |
| skill, the villager's best | `R gains N skill in what H does best.` / `R loses N skill in what H does best.` (`H` the villager's he/she, a subject pronoun; a group: `what they do best`) |
| skill_set, 100 / 0 / other | `R masters S.` / `R loses all S skill.` / `R's S skill is now N.` |
| faith (New Believers) | `R's Faith rises by N.` |
| damage | `A building loses N% of its construction.` (A New Home, The Lost Children: `N percent`) |
| change_age | `R is now N years old.` |
| a group's skill | `C villagers each gain N S skill.` / `C villagers gain L to N S skill.` / `W gains N S skill.` (and "lose") |
| a group's health_change | `C villagers each gain N health.` / `C villagers gain L to N health.` / `W gains N health.` |
| a group's Faith, skill_set, health | `The Faith of C villagers rises by N each.` / `The S skill of C villagers is now N.` / `The health of C villagers is now N.` |
| supply, trade (39) | `The village gains N W.` / `The village loses N W.` / `The village gives N W.` / `The village gets N W.` |
| Village Solidarity | `Village Solidarity rises by N.` / `Village Solidarity falls by N.` |
| group sickness, the event timer, a tech level (40, 41) | `N villagers become sick.` / `The next island event will come N hours later.` / `The village's W technology rises to level N.` |

Lines with no amount keep their words: `R dies.`, `R celebrates.` (a good mood), `R shakes P head.` (a bad mood),
`R's head changes.`, `R looks older.`, `R is cured.` and the rest of the table.

No line: `action`; a deferred food or tech (its `pay_award` gives it); a change that changes nothing (an amount of
0, or one the limits take wholly away); a skill the game does not have (roll -1); a random preference with no
candidate. Identical lines are all kept.

- **The words are those the walk chose**, so the engine's pages (section 6.6: laid out once the walk is done) hold
  the real skill and word. A line whose change is then refused (the villager protected or gone since) is taken back
  as the page is shown (`cg_fix_lines`), and the page's "N changes could not be made" line says so.
- **Hand-written amounts.** An author's text that names a number the limits may cut (`"Your village loses 50
  food."`) is story: the automatic line after it states what was really made, and is the one to trust; with
  `(award)` the author's text itself shows the amount paid.
- **Fit (Python, `walk`):** each effect's line at its widest -- of the lines it can give (each listed skill the game
  has, each sign of a range, every word of the game's list for a random preference), the one whose worst case is
  the longest (the first on a tie) -- so whatever Python accepts the engine can show.
- **simulate** returns the lines in the popups, with the words its rolls and facts give.
- **Python:** `auto_lines(...)`; the line table `AUTO_LINES` is pinned equal to the engine's `CG_AUTO_LINES`
  (`story_graph.inc`) by `tests/test_cie_graph_v6.py`.

## 26. The Pick Island Event list

Each game lists its own events, then More Island Events' and the collection's (`sm_list`, at most `SM_MAX` entries,
`story_more_events.inc`; the collection's manifest at most `SC_MAX` entries, `story_collection.inc`). With the Isola
Grand Event Collection, the Companion Anthology and More Island Events that is about 1,000 entries a game, so
`SM_MAX` and `SC_MAX` are 2,048 and `SC_MANIFEST_BYTES` 1 MB. The list's words take `3 x 400` bytes an entry: 2.4 MB
of the companion's static memory, only the pages of the entries filled ever touched. The chooser's list is the Windows
list box (`IDC_PICK_LIST`, `LB_ADDSTRING`), which holds and scrolls that many rows itself; typing a letter moves to
the next row starting with it, so no filter is needed. Measured in the emulator (`tests/test_pick_collection_list.py`
AThousandEntries, A New Home and New Believers): 1,000 entries, each event loaded and its strict cast checked, fill
in more than 100 and under 400 million instructions, a fraction of a second on a real computer (each entry's .cieg
is also read from disk there, about 1,000 small files).
## 27. The old head look (the owner, 2026-11-14)

JSON (v6): `{"do": "old_look", "role": r}` (code 21; a = b = 0, string `NONE`; no roll). Health troubles may be
shown partly through the villager's look: the villager is drawn with the OLD head from then on, whatever their age --
the per-villager head look Change Appearance offers (Auto / Young / Old), set to Old.

- **How:** the engine asks "VVFP Head Look.dll" (`native/shared/head_look.h`: `VvfpHeadLookInstalled`, then
  `VvfpHeadLookSet(game, record, 2)`), exactly as Change Appearance does. The look is kept in that companion's own
  per-save file, never in a game record field; it follows the villager (patcher-data-follows-the-villager), the head
  row never changes, and it is permanent until the player changes it (Change Appearance's Head look, or Reset to
  original, which puts Auto back).
- **Harmless** (section 7): nothing in the save is written, only the companion's file.
- **When it cannot be made** -- Head Look is not in the game, or this game's draws do not follow the look (A New
  Home needs Grey Hair at 55 for its old heads), or the file write fails -- it is a refusal ("N changes could not be
  made") and nothing changes.
- The Island Events log's entry says "<name>'s head look is now Old."
- No game capability bit: whether it can be made is known only at run time, so the patcher's checks accept it in
  every game.

## 28. A new name (REL "Names & Presentation", the owner 2026-11-14)

A villager may ask to be called by another name. Nobody is renamed: the event shows a NEW NAME drawn for it.

JSON (v6): a stranger role `{"kind": "stranger", "new_name_for": r, "sex": S, "last_name": L}`. `r` is a villager role
the event needs (not optional, not an alias or other). `S` is `same` (the default: the villager's sex), `other`,
`random`, `male` or `female` -- the list the first name comes from. `L` is `same` (the default), `different` or
`random`. It is a named stranger (section 16), so `(chosen)`, `(Chosen)`, `(CHOSEN)`, `(chosen.name)` show it, in
titles and labels too; its pronouns follow `S` as drawn. No effect or condition may name it.

- **Binary:** the stranger's role record: flags 1 + 2, sex byte 1 male, 2 female, 3 random, **4 same, 5 other**,
  byte 3 the last name (0 same, 1 different, 2 random), bytes 14-15 exactly one bit: the villager role. The loader
  refuses a new name for anything but a needed villager role, flag 2 without 1, or a byte beyond those.
- **The draw** (engine `cg_new_name`, at bind time, after every villager role is bound, in role order): the sex
  (one roll only for `random`), then the first name exactly as a named stranger's (section 16: a name no living
  villager or earlier named stranger has, else any); then, only with "VVFP Last Names.dll" in the game (as the Custom
  Island Event's "Joey Joerson"), the last name: `same` the villager's own as Last Names reads it (the last word after
  the first, a trailing Roman numeral passed over; none for a one-word name), `different` `random_below` over the
  game's 50 last names but the villager's own (compared ignoring case), `random` over all 50. The list is the one the
  game's naming routine pushes and Last Names names from (`story_villager_names.h CG_LAST_*`, built by
  `scripts/build_cie_villager_names.py`; read from the game, the built-in copy when it cannot be). The name is kept in
  the run (`cg.name`, in the run's file), so every page shows the same name, a resumed run too.
- **Worst case:** the longest first name of the game's two lists, a space and the longest last name (8 + 1 + 8 in
  every game; `role_name_room`).
- **Python:** `simulate` takes the name from `bindings`, as a named stranger's.

## 29. The sex field changed (`sex_change`, code 22)

JSON (v6): `{"do": "sex_change", "role": r}` (a = b = 0, string `NONE`, no roll). The villager's record gets the other
value of the game's own sex field (the owner tested the write in Cheat Engine). Harmless (section 7). Nothing else is
written: head and body rows stay (every game has as many male as female rows, so they stay valid rows of the new
sex's sheets), the names stay, and the parents recorded on anyone's record (recorded at conception, frozen at birth)
stay as recorded.

| Game | Sex field | Male / female | Source |
|---|---|---|---|
| A New Home | +0x350 | 1 / 2 | `story_c1.inc` C1_ADAPTER, `tests/story_custom_fixtures.py` |
| The Lost Children | +0x538 | 1 / 2 | `story_c2.inc` C2_ADAPTER |
| The Secret City | +0xDC8 | 0 / 1 | `story_c3.inc` C3_ADAPTER |
| The Tree of Life | +0x1B90 | 0 / 1 | `story_c4.inc` C4_ADAPTER (the render path's compare, `vv4_origins_icons.c`) |
| New Believers | +0x1B90 | 0 / 1 | `story_c5.inc` C5_ADAPTER |

- **Made** through `native/shared/sex_change.h` `vv_sex_change_apply`, the same call Change Appearance's "Change
  sex..." button makes in all five games (`sex_change_ui.h`): the field written; a line added to the save's own
  "Sex Changes - Save S.txt" (`<old>\t<new>\t<name>`, M or F); every companion that keeps data by the sex told through
  its export `VvfpVillagerSexChanged(game, slot, record, before)` (the Story Upgrades' custom titles, Head Look,
  Original Look, the Origins masks of all five games and Heathens Keep Masks' waiting masks, Cause of Death, Faith
  Loss, Last Names, the VV1 Parentage, Parentage Export), each carrying what it keeps to the villager's new identity
  and writing its own file; and an "Appearance changed" record in the Births and Conceptions log with "Old sex" /
  "New sex" lines (the history line Repair Logs keeps). As each companion reads its own file it also reads the log,
  so a file written after the change still finds the villager when the save was not saved after it. The Python tools
  (Repair Saves, Repair Logs and the rest) follow a villager the log or the history line names (`src/vv_sex_changes.py`).
  Statistics Export and Population Export keep nothing by the sex.
- **Carrying or nursing is no refusal** (the owner, 2026-11-15): the villager goes on carrying, and stays the carrying
  parent (the mother's place) on the babies' records. Each game's own delivery runs the same with a male carrier
  (`tests/test_sex_change_carrier_all.py`: the same babies on the same tick, the same parent fields, the pregnancy
  fields cleared; the carrier's sex is read only by the small-village sex balance that picks a NEW baby's sex).
- **Refused** ("N changes could not be made"; the text still shows, nothing is written): a special villager
  (`cg_special`, `cg_never_harmed`): The Secret City's Tribal Chief and stand-in, New Believers' story villagers.
- **The Golden Child is never cast** for a role a `sex_change` effect names (`cg_sex_change_role`, even with
  protected `allow`), and Change Appearance hides its button for him (the owner: "breaks things"); an alias's member
  drawn as him is refused.
- **The run** keeps the villager by their new identity (`cg.identity`), so later effects of the event still reach
  them. Pronouns in the event stay the sex they were cast with (the pages are laid out before the change is made).
- **The log:** "<name>'s sex is now male." / "female."; the automatic line (section 25): `R's sex changes.`
- **Kinship** finds a parent by the parent FIELD on the child's record, never by the parent's sex now: the relation
  roles (section 21) always did; `has_living_child` now reads the same kinship table (either parent field; A New Home
  through its parentage sidecar), so a parent whose sex changed after the birth still has their children.
- **Parent words:** the role-sex word pairs of section 5 (`(parent.mother/father)`, `(parent.mom/dad)`, add `'s` for
  the possessive) give the word of the role's sex as cast, so an event about a carrying father says "father" with no
  other change. Text written with the plain word "mother" stays as written (an owner's sentence is never rewritten).
- **Only villagers born female carry** (the owner, 2026-11-15): a nursing_parent role, and the role a baby_lost
  effect names, cast only a villager born female (`cg_carrier_role`, `cg_born_female`: "VVFP Gender Presentation.dll"
  keeps the birth sex at the first change, else the save's Sex Changes log's first line for them, else the sex now).
  One born female who changed to male goes on carrying and may be cast; one born male is never cast as a carrier,
  even if a Custom Island Event gave them a baby. In the game a villager born male never conceives on their own
  (that companion's conception guard); the Custom Island Event's pregnancy with a chosen partner still can.
- **A cross-sex body look** keeping the sex field is section 31 (code 23): the gender presentation.

## 30. An early birth, the parent lives (`deliver_early`, code 24)

The owner's new outcomes for "Two Lives, One Decision" (2026-11-15: A6, A9, A13, A14, B5, B7, B12, B13, C4, C5, C10,
C12, C15, C22) have the baby born early -- small, frail or with lasting health difficulties -- while the carrying
parent lives. `birth_then_die` (section 23) always kills the parent, so this is its own effect.

- **`{"do": "deliver_early", "role": r}`**, optionally with `"min"` and `"max"` (both -99..-1, min <= max): the
  health each new baby loses on top of the early birth's own deficit (a frail newborn). Both left out: a = b = 0, no
  roll; with them, one roll `lo + random_below(hi - lo + 1)` at its place in the walk (as `health_change`'s). The role
  MUST be `"special": "nursing_parent"`, so it needs `protected: "allow"` (section 7). Harmful (the newborn is weaker);
  the event needs `CAP_CANCEL` (the nursing parent's pregnancy) and the adapter's `deliver`.
- **What it does:** section 23's steps 1-5 and its Cause of Death call (`VvfpCauseDelivered`), and NOT the kill: the
  game's own delivery makes the babies now; each baby born early gets the age the nursing reached and the deficit
  `round(50 * (40 - elapsed) / 40)` (5..50); each baby then loses the roll more (`ce_birth_extra`), never below
  health 1, at full term too. Twins and triplets: the same age, deficit and roll each.
- **Refused** ("N changes could not be made"; nothing changes): the parent is no longer carrying the baby (born
  since), or the game did not deliver (the field and the age are put back, as in section 23).
- **The log:** "<name>'s baby was born early." ("babies were"; "was born" at full term). No automatic line (section
  25), as `birth_then_die`.
- Not offered in the Custom Island Event library's Add menu (a collection effect for now; an owner question).

## 31. The content controls (the owner, 2026-11-15): up to 32 patch names; code 25 reserved

`src/vv_event_content.py` writes the island events' content controls into every NEW event as it is compiled (the
collection's builder and the Living Event Engine's mixer); the event files are never changed, each source's tags are
in `data/event_collection/content_tags/<source>.json`.

- **Patch names:** a graph may name up to **32** patches (the engine's `cg.patches` mask; before, 8). The content
  filters are `island_event_filter_f01` .. `f28`, the content notes `island_event_content_notes`: the patcher writes
  each ticked row in "VVFP Installed Patches.txt", which `cg_installed_has` reads.
- **Dropped outcomes:** a weighted child (never a player's choice) whose own part of the graph carries a filter gets
  `{"not": {"patch": "island_event_filter_fNN"}}` (several: `not any`).
- **Skipped events:** the requirement gets `not (any group covered)` -- a filter still reachable with its edges
  dropped, or every child of one node dropped. Strict casts (the rare roll, Pick Island Event) refuse it with "the
  island event content filters to allow it"; a bought event is refused by these parts too ("is kept out by the island
  event content filters"), never by the requirement's other parts.
- **The content note:** the first text node(s) get variants "Content note: <labels>\n<text>", each with the
  condition `island_event_content_notes` and which labels the ticked filters leave.
- **Code 25 is reserved:** it was a rest period (`rest`); the owner took the rest periods out (2026-11-15), so nothing writes it and the engine refuses a file that holds it.

## 32. Story traits (`trait`, code 26) and speaking roles (the owner, 2026-11-15)

- **`{"do": "trait", "role": r, "trait": "mute"}`** (a = the trait's bit, 1 "mute"; b 0; no string): made at its
  place, it keeps the trait for the villager in the same per-villager file as the rest periods (`story_rest.inc`),
  whatever is ticked; it follows them as every patcher sidecar does. "The Quiet Hands" (Inner Life 3, `il003_*`)
  gives it to the villager it casts (`src/vv_event_content.py` TRAIT_EVENTS writes the effect on its start, or on
  each answer's first node when the start is a question). Never a change, never a line, never logged.
- **A speaking role:** byte 13 of a villager role (the skill pick, 0 or 1) carries bit 7 (`0x80`) when the event's
  words have that role speak (a quoted line attributed to them: `speaking_roles`, kept in the source's tag table as
  `"speaks"`). Such a role never takes a villager with the trait "mute" (`cg_eligible`).
- **Dislikes talking = mute** (the owner, 2026-11-17): in a game whose like / dislike list has "talking" (The Lost
  Children .. New Believers; A New Home has none), any villager who dislikes talking counts as mute, however they
  came by it (`story_traits.inc` rs_has_trait). The "mute" trait effect also gives the villager that dislike there,
  through the preference effect's own write (24); in A New Home it keeps the trait only.
- **A sex change keeps the trait:** the file keys villagers by an identity that holds the sex, so the companion's
  `VvfpVillagerSexChanged` carries the entry to the new identity (`rs_sex_changed`); a save from before a change finds
  it through the Sex Changes log.

## 33. Count tokens: text that fits what the effects made (the owner, 2026-11-15)

Twins and triplets (pregnant / nursing flags bits 1-2), up to two clones (clone a = 2) and several new villagers come
only as far as the game's room allows, so the text says how many actually came:

- **`{#babies:A|B|C}`**: the babies the page's `pregnant` / `nursing` effects actually put on their way (each
  game's own conception, its room check included).
- **`{#made:A|B|C}`**: the villagers the page's `new_villager` and `clone` effects actually made.
- **The option:** A for 1 (and for 0 or nothing known), B for 2, C for 3 or more; with fewer options the last one
  is used for anything past it. Examples: `{#babies:a baby|twins|triplets}`, `{#babies:it|them}`,
  `{#babies:is|are}`, `{#made:one|two|three}`, `{#made:a newcomer|two newcomers|three newcomers}`.
- **Which count:** the page's own count once its effects are made (the engine fills the tokens after it makes
  them, before the page is shown); a page that makes no such effect uses the last earlier page's count of the same
  event ("the following page"). Nothing made yet on the event: A. The counts are memory only: after a quit and a
  restore between pages, A.
- **Syntax:** `{#`, the count's name (`babies` or `made`), `:`, then 1 to 3 options separated by `|`, then `}`.
  Each option is 1 to 160 bytes of the plain text set (letters, digits, space, `, : - ' "` and `; / & %`) and
  placeholders: the event's own names and pronouns (`(name)`, `(Name1)`, `(child.he/she)`, `(his/hers)`, ...; no
  label hint) and `(made1)` / `(made2)`. No pool or game word, brace, line break or `.` `!` `?` (so a page break never
  falls inside one). Body text only, never a button label or a title. Any other `{#...}` is refused by the loader.
  The option is chosen first, then its placeholders are filled (and VV1/VV2's glyph fallback made) as the rest of the
  page's were.
- **Fit:** the worst case is the widest option with its placeholders at their widest (CG_EXPAND_WORST; Python
  `worst_v6` the same), so the pages are laid out for it.

### 33a. The names of the villagers the event made: `(made1)`, `(made2)`

- **`(made1)`** is the name of the newest villager the event's `new_villager` (not a child of the newest, flags bit
  0) or `clone` effects made; **`(made2)`** the one made before it. With only one made, both are that villager (so
  `(made2)` is never empty); with none, "a newcomer". The game's own name, read after the page's effects are made
  (any case: `(Made1)` the same). Body text and count options only, never a label or a title.
- **When:** filled when the page is shown, after its effects; on a later page of the same event the same villagers
  (memory only: after a quit and a restore between pages, "a newcomer").
- **Fit:** the worst case is `W` x the game's name room.

- **`(renamed)`** (any case) is the name the event's latest `change_name` (33) gave (random or fixed), filled after
  the page's effects as `(made1)` is; before any rename, the current name of the villager the event's first
  `change_name` is for. Body text and count options only.
- **A renamed villager's role** (change_name, the lost name "?", a mind swap) keeps following them: the role's own
  `(name)` / `(Name)` and the role shorthand show the new name on every later page -- pages laid out before the
  rename have the old name put back as the new one (whole words), pages laid out after it have it already -- and the
  role's later effects still reach them (their identity, which holds the name, is taken again). The rename's own
  page keeps the names it was written with, so "(subject) is now called (renamed)." reads "Ana is now called Lani.".
  Memory only for the old pages: after a quit and a restore between pages, a page laid out before the rename may
  show the old name.

### 33c. New Believers' Heathens and Faith (the owner, 2026-11-16; "VV5 Heathen Events - What Vanilla Does")

- **A Heathen's role (`"heathen_ok": true` on a villager role):** role byte 13 bit 6 (`0x40`, beside SPEAKS `0x80`;
  the flags byte 1 is full). Keep `believers_only` as it is (true): the engine casts such a role only among the
  Heathens whatever byte 1 says, so a believer is never cast in it. In New Believers the role is cast as the
  game's own picker `0x471870` casts a Heathen (Heathens-only on, special roles off): a Heathen, never roles 12-17
  (the Heathen Doctor, the Heathen Chief, the three Masters, the Heathen Mommy), never sick, health above 0, listed
  (present, not a body or a spirit); carrying or nursing allowed; the role's own ages and sex apply (a child under
  14 for a child's story, 14 or more for an envoy). Default stays believers only. In the other games the bit is
  ignored. Vanilla casts one Heathen an event; an event may name more.
- **What may happen to a Heathen's role** (refused when the file is loaded, whatever is ticked, No Safeguards too):
  `faith`, `join`, `action` (stopped, walked, posed), `health_change` down to -30 (minor harm, as The Missing Kids),
  `sick`, `trait`. Never a death, a disappearance, an age, a skill, a like or dislike, a lower Faith.
- **`faith` (code 38):** role; a = the Faith gained, 1..35 (vanilla +5..+35); b 0; no string. The game's
  FAITH_ADD `0x468020`: a Heathen whose Faith ends above 0 joins the tribe the game's own way (its message, role,
  counters, puzzle check; below 5 becomes 55). Auto line "<R>'s Faith rises by <N>." with the Faith really gained
  (Faith stops at 100: a villager at 100 has no line; a convert's rise to 55 is told as it is), section 25.
- **`join` (code 39):** role; a = b = 0; no string. A Heathen joins: SetFaith `0x467F90`(20, 1), then
  `0x466880`(0), as The Defector. A believer already: nothing. Auto line "<R> joins the tribe."
- **`apostasy` (code 40):** role (a believer's, never a Heathen's role); a = b = 0; no string. A believer becomes a
  Heathen by their own choice (write it only where the player's answer has the believer choose it): SetFaith(-10,
  1), then `0x466880`(1), as The Spa and The Cracked Mask. Harmful (protected villagers kept out). Auto line
  "<R> becomes a Heathen."
- Only in New Believers; in the other games the three do nothing. UNCONFIRMED live: the three routines are called
  as thiscall on the villager's record, as the vanilla events call them.

### 33b. Other forms (the owner's files, 2026-11-16)

- **`(his/hers)`**: the standalone possessive ("the choice was hers"), with the role prefix, the capital and ALL
  CAPS forms as every pronoun (`(friend.his/hers)`, `(His/Hers)`, `(HIS/HERS)`). Engine `CG_PH_HIS_HERS`.
- **Role-prefixed pronouns** were already read: `(<role id>.he/she)`, `(<role id>.his/her)`, `(<role id>.him/her)`,
  `(<role id>.himself/herself)`, `(<role id>.man/woman)`, `(<role id>.woman/man)`, `(<role id>.boy/girl)`,
  `(<role id>.son/daughter)`, the role-sex words of section 5, and now `(<role id>.his/hers)`. `name1` / `name2` take
  no prefix: `(name2.his/her)` is not a form; write `(friend.his/her)` (name2 is the role `friend`).
- **Group targets by age:** role byte 254 with byte 3 = 4 every elder (55 or more), 5 every child (under 14), 6 every
  teen (14 to 17), 7 every adult (18 or more); the last H 0. A random like or dislike (preference with flags bit 8)
  may now take a group too: each member draws their own word.
- **Group targets on `appearance` (17):** role byte 254 takes `appearance` too; with a random head or body each
  member draws their own row (the game's random routine), so "a new look for three random villagers" gives three
  looks.
- **Python (the compiler, the importer):** accept the token in text, measure it as its longest option, `simulate`
  with a count of 1 unless the facts give `count:babies:<n>` / `count:made:<n>`; `normalize` keeps it as written.

## 34. The gender presentation (`presentation`, code 23; the owner, 2026-11-15)

JSON (v6): `{"do": "presentation", "role": r, "on": true}` (`on` defaults to true; a = 1 when on, 0 when off; b = 0,
string `NONE`; no roll). The villager keeps the sex the game records for them and is drawn with the other sex's heads
and bodies from then on (`on` true), or with their own again (`on` false) -- the per-villager choice Change
Appearance's "Gender presentation: use the other sex's look" offers.

- **How:** the engine asks "VVFP Gender Presentation.dll" (`native/shared/gender_presentation.h`:
  `VvfpGenderPresentationInstalled`, then `VvfpGenderPresentationSet(game, record, on)`), exactly as Change
  Appearance does. The choice is kept in that companion's own per-save file ("Gender Presentation - Save S.dat", the
  Head Looks' file shape), never in a game record field: the sex field, head and body rows are not written. It
  follows the villager (deaths, reloads, renames, a sex change) and is permanent until changed (Change Appearance's
  checkbox, or another event). Start Over clears it.
- **The draws:** the companion splices every read of the sex field inside each game's villager draw routines (A New
  Home 15, The Lost Children 22, The Secret City 3, The Tree of Life 3, New Believers 3 reads; `tests/
  test_gender_presentation.py`), handing the game the other value for a villager whose choice is on: each routine
  draws them as it draws a villager of the other sex with the same rows. Nothing else that reads the sex changes.
- **Harmless** (section 7): nothing in the save is written, only the companion's file.
- **Never cast:** a role a `presentation` effect names never casts the Golden Child, The Secret City's Tribal Chief
  or stand-in, or New Believers' story villagers (roles 12-17) -- `cg_presentation_role`, the refusal of
  `native/shared/sex_change.h` `vv_sex_change_refusal`, even with protected `allow`; an alias's member drawn as one
  of them is refused when the effect is made.
- **When it cannot be made** -- the companion is not in the game (its row, "Change Sex and Gender Presentation", is
  off), its draws could not be installed, or the file write fails -- it is a refusal ("N changes could not be made")
  and nothing changes.
- The Island Events log's entry says "<name> is now drawn with the other sex's look." (on) or "<name> is drawn with
  their own look again." (off); the automatic line (section 25): `R's look changes.`
- No game capability bit: whether it can be made is known only at run time, so the patcher's checks accept it in
  every game.

## 35. New villagers, pregnancy, nursing, clones, body swaps, names and ages (codes 27-37; the owner, 2026-11-15)

Collection effects, added only where an outcome's own text says it (`scripts/food_tech_additions.py`
EFFECT_ADDITIONS; `docs/event-collection/food-tech-log.md`). `scripts/collection_check.py` validates them (check e);
`src/vv_cie_graph.py` has their codes, so `normalize`, `_compile_v6` and `_decompile_v6` carry them (the round trip is
exact). `new_villager`'s role byte is its `copy_of` role (0xFF none). (`graph_for_engine` would leave out any of these
codes that a `vv_cie_graph` without them does not know.) The run-time side (story_graph.inc) is the engine's.

| Code | do | role byte | flags | a | b | string |
|---|---|---|---|---|---|---|
| 27 | new_villager | `copy_of` role index (or 253 / 252), or 0xFF (a random new villager) | 1 a child of the two newest villagers | age: 0 any, 1 child, 2 teen, 3 adult, 4 elder | sex: 0 random, 1 male, 2 female | NONE |
| 28 | pregnant | the carrier's role index | 1 any_birth_sex; 2 the game's multiple-birth roll, 4 twins, 6 triplets; 8 partner_may_carry | the partner's role index (or 253 / 252), or 0xFF | 0 | NONE |
| 29 | nursing | the carrier's role index | 1 any_birth_sex; 2 the game's multiple-birth roll, 4 twins, 6 triplets; 8 partner_may_carry | the partner's role index (or 253 / 252), or 0xFF | 0 | NONE |
| 30 | clone | role index | 0 | how many: 0 or 1 = one double, 2 = two | 0 | NONE |
| 31 | body_swap | role index | 0 | the other role's index | 0 | NONE |
| 32 | lose_name | role index | 0 | 0 | 0 | NONE |
| 33 | change_name | role index | 0 | 0 | 0 | the fixed name (offset 12), or NONE / empty: a random default name |
| 34 | change_age | role index | mode: 0 child (1-13), 1 teen (14-17), 2 "18", 3 adult (20-49), 4 "50", 5 elder (55-75), 6 add years | add: min years (-120..120); else 0 | add: max years (min <= max); else 0 | NONE; the last H = the age cap in years (0 none, at most 120) |
| 35 | cure | role index (or 254) | 0 | 0 | 0 | NONE |
| 36 | repair | 0xFF | 0 | 0 | 0 | the structures, comma separated, or `any` (as damage's) |
| 37 | young_look | role index (or 254) | 0 | 0 | 0 | NONE |

- **`{"do": "new_villager"}`**, optionally `"copy_of": r` and `"age": "child" | "teen" | "adult" | "elder"`: a new
  villager joins the tribe (a newcomer who stays, a castaway). With `copy_of`, the newcomer has the role's villager's
  looks (head, body, sex) but its own likes, dislikes and skills, rolled from the game's lists (a lookalike, a double).
  Never for visitors who leave.
- **`{"do": "pregnant", "role": r}`** and **`{"do": "nursing", "role": r}`**, optionally `"partner": p` and
  `"any_birth_sex": true`: the role's villager becomes pregnant, or has a nursing baby now. The carrier is cast born
  female (any current sex), 18 or older, and never a villager already pregnant or nursing (the engine checks the
  carrier when the effect applies; one that cannot carry is a refused change). The partner is `p` (the event's
  recorded spouse or partner role) or, left out, an adult of the other birth sex. Parentage is recorded at conception
  as usual. `any_birth_sex` (flags bit 0, value 1) lets a born-male villager carry: where the text involves magic (a
  spell, a blessing, an enchanted spring, a spirit, a potion), or, for `nursing`, where the text has him caring for a
  baby (his partner's, a single father, a deceased mother's child, a nursery or orphanage, an abandoned or rescued
  infant, an adopted or refugee child, someone who cannot care for their child) or a villager who transitioned from
  female to male. Otherwise born-male villagers never conceive from these events (Custom Island Events can, with Male
  Pregnancy). `"partner_may_carry": true` (flags bit 3, value 8; needs `partner`): the carrier is still checked as
  above, then, at the player's "a man may carry the baby by chance" percent (10 unless moved), the partner carries
  instead, of any birth sex, when they are 18 or older and not expecting already; else the carrier does. **Who
  carries is decided once, when the run starts (the cast made and the aliases drawn), before any page is written**
  (the owner, 2026-11-18; `story_graph.inc cg_partner_carry_decide`, `vv_cie_graph.partner_carry_pairs`): each
  such effect's pair once (an alias role as its member drawn), in effect order, one roll (none at 0 or 100 percent);
  on a yes the two roles' villagers change places for the whole run, so every page's names, pronouns and carrier
  words name the villager who carries, the effect makes that villager carry (the born-female check skipped for them)
  and the conception records the other as the other parent. Another outcome's `nursing` for the swapped role (a
  foundling the couple takes in) also goes to the villager the page names, whatever their birth sex.
  The run's file (version 5) keeps the swap (`carry_swapped`): a loaded run keeps the choice whatever the setting
  says by then; a version 4 file loads with nobody swapped. The new events set it on every couple pregnancy (`pregnant` with a partner and without `any_birth_sex`); a reason-based
  one (`any_birth_sex`), a single parent and a `nursing` foundling never do.
- **`{"do": "clone", "role": r}`**, optionally `"count": 1 | 2` (default 1; value a, 0 or 1 = one, 2 = two): an exact double of the role's villager joins the tribe (looks, likes, dislikes and
  skills copied). A clone and a `copy_of` duplicate ALWAYS get a name different from the original's.
- **`{"do": "change_name", "role": r}`**, optionally `"name": "Lani"`: a real rename, to that name or (left out) to a
  random default name from the game's own name lists (either sex's), for "a villager wants to change their name".
  A fixed name is 1-31 characters: a letter first, then letters, spaces, apostrophes, hyphens or full stops, no
  trailing space (normalize and collection_check refuse anything else).
- **`{"do": "change_age", "role": r, "to": "child" | "teen" | "18" | "adult" | "50" | "elder"}`**, or
  **`"years": n | [a, b]`** (-120..120, not 0; negative is younger): "teen" is 14-17, "adult" 20-49, "elder" 55-75;
  "years" rolls a..b once at its place in the walk.
- **Authoring (the owner, 2026-11-15):** a death is `kill` (a skeleton and a grave); a disappearance is `vanish` (no
  skeleton). A permanent disability the text states may be a health loss (`health_change`, 10-90), a dislike of
  running, work or learning (or another fitting dislike from the game's list), or the old head look (`old_look`) for
  stress. Anything a stock event of that game can already do is allowed; an outcome may stay flavor only.
- **`{"do": "body_swap", "role": a, "with": b}`**: the two villagers swap heads and bodies (looks only; names, ages,
  skills and likes stay).
- **`{"do": "lose_name", "role": r}`**: the villager's name becomes "?", as the stock bump-on-the-head event does.
- Not harmful (section 7) and no automatic line (section 25) until the engine side is built.

**The engine's further layouts (feat/97-island-events-ui 3a3651283, 8ebafe54f; the effect record is `B code, B role,
B flags, B byte 3, i a, i b, H string, H last`):**

- **`{"do": "cure", "role": r}`** (35): the villager is cured; line "<R> is cured.". **`{"do": "repair", "structures":
  "any" | [names]}`** (36): the damaged buildings are repaired; line "The damaged buildings are being repaired.".
  **`{"do": "young_look", "role": r}`** (37): the villager's young head look (section 27's twin).
- **Group targets:** `"target": {"all": true} | {"skill": "Healing"} | {"random": 3}` in place of a role, on health,
  preference (a word, never random), skill and skill set, sick, action, mood, health_change, cure, young_look,
  old_look and celebrate: role byte 254; byte 3 the selector (1 every villager, last H 0; 2 every villager with that
  skill at 50 or more, last H the skill name's string; 3 N villagers at random, last H = N, 1..255). Byte 3 and the
  last H are 0 on every other effect (change_age's cap aside). No automatic line from the compiler (the engine's).
- **The best skill:** skill (9) and skill set (15) with `"best": true` in place of the skills: flags bit 32, the
  string "best"; line "<R> gains <N> skill in what <H> does best." (<H> the role's he/she).
- **The event's new villagers:** `"$newest"` (role byte 253) and `"$previous"` (252), the villagers this event's
  new_villager or clone made, stand for a role in any villager effect, as a pregnant / nursing partner (a) and as
  new_villager's `copy_of`; no role is declared for them. new_villager also takes `"sex": "male" | "female"` (b;
  random when left out) and `"child_of_newest": true` (flags bit 0: a child of the two newest villagers).
- **change_age's cap:** `"max_age": 75` (the last H): never past that age ("never past elder").
- **The babies of pregnant / nursing:** `"babies": "roll" | 2 | 3` (left out: one): flags bit 1 the game's own
  multiple-birth roll (7% more than one, a quarter of those triplets) without its technology gate; bit 2 twins; bits 1
  and 2 triplets; any other bit is refused.

## 36. Count tokens and the other new forms: the compiler's side (engine 0853e8327; section 33 is the engine's)

`{#babies:A|B|C}` and `{#made:A|B|C}` stand in BODY text only (a page, a variant, a pool item), never in a button label
or a title. They show A for a count of 1 (or 0, or unknown), B for 2, C for 3 or more (a missing option: the last one
given): `#babies` counts the babies the event's pregnancy or nursing effect brought, `#made` the villagers its
new_villager and clone effects made. One to three options, each 1-160 bytes: letters, digits, space,
`, : - ' " ; / & %` and placeholders (engine 5ee2b3dc0) -- no braces, line breaks or `. ! ?`.

The compiler keeps the token as written (it is never an inline pick; the engine shows the option). A page is measured
by the token's widest option, its placeholders at their widest. `simulate` shows the count of 1 unless its facts give `count:babies:<n>` or
`count:made:<n>`. `collection_check` reads a count token's options as the source's "(A/B/C)".

**More text (engine 5ee2b3dc0):**

- **`(made1)` / `(made2)`** (any capitals, `(Made1)`, `(MADE1)`; no role prefix): the name of the newest villager this
  event made (new_villager, clone) and of the one before (the effects' `$newest` / `$previous`). Body text only, never
  a button label or a title; measured as a full name.
- **`(his/hers)`**, with capitals (`(His/Hers)`, `(HIS/HERS)`) and a role prefix (`(friend.his/hers)`): the possessive
  that stands alone ("the choice was hers").
- **appearance (17) takes a group target** (`"target"`, role byte 254) like the effects of section 35.
- **`(renamed)`** (any capitals; engine a4f4f1d0b, section 33a): the latest change_name's new
  name (before any rename, the current name of the first change_name's villager). Body text and count options only,
  never a label or a title; measured as a full name. `expand_v6` shows the binding `"$renamed"` when given, else the
  graph's fixed change_name name, else "Renamed".

**A cast Heathen (`"heathen_ok": true`, VV5; the owner, 2026-11-16).** As vanilla does, a New Believers event about an
Isolan who lives on the island casts a real Heathen villager for that one role (never a Heathen role character such
as their Chief or a Master, never sick); a traveller from elsewhere stays a stranger. Such a role takes only faith,
join, actions and minor harm (health -5..-30, sick); collection_check refuses anything more. Until the engine's own
role flag is in `src/vv_cie_graph.py`, `collection_check.graph_for_engine` gives the engine the role as
`believers_only: false`. The roles (`scripts/food_tech_additions.py` HEATHEN_ROLES, applied on disk and by the
generators): blf26_isolan_feast friend, blf27_songs_across friend, vv5_v17_cooking isolan, vv5_great_laundry_mishap
isolan, vv5_great_woodworking isoleader, vv5_potluck_dispute isolan, vv5_gift_or_insult visitor,
vv5_multicultural_festival visitor (each a villager of 14 or more; none takes an effect).

## 37. Preferred special villagers, the chief's title and words that follow the villager (the owner, 2026-11-16)

**A role that prefers a special villager.** JSON (v6): a villager role's `"prefer": "golden_child"` or
`"prefer": "tribal_chief"` (never with `special`). Binary: the role's byte 9 = **4** (prefer the Golden Child) or
**5** (prefer the Tribal Chief); the loader refuses more than 5. Unlike `special` (1-3: the role MUST be that
villager), the role is cast as usual -- every requirement, safety rule and the protected filter -- and then, among
the villagers that may take it (the ones that keep the other roles fillable, after a `"pick": "highest"`), the
Golden Child (A New Home) or The Secret City's Tribal Chief is taken when one of them is there (`cg_bind`; only one
lives, so no roll); else any of them, by the usual draw. Allowed in every game (only A New Home has a Golden Child,
only The Secret City a Tribal Chief). A protected role (section 7) keeps them out as before.

**Cond op 18, `is_special`.** JSON `{"is_special": r}` (a role; on an alias, its member drawn): the role's villager
is bound, not gone, and is the game's special villager (A New Home's Golden Child, The Secret City's Tribal Chief),
by the game's own kind (`cg_special_kind`), whatever No Safeguards says. A run-time fact like `age` (section 8):
`simulate` takes it from `facts` (`"is_special:<role>"`); never in a requirement or a choice's `if`.

**The chief's title (linked pools).** A game word named `chief`, `Chief`, `a_chief`, `A_chief`,
`chiefs_possessive`, `village_chief`, `tribal_chief` or `Tribal_chief` (or a label's title-case copy, `w_tc` /
`w_tcN`) whose texts hold a chief or leader noun is the chief's title (`vv_cie_graph.CHIEF_WORDS`). `lower` writes
its pool `@w` as:

1. one item per distinct text with its games (`{"game": [...]}`, weight 1) -- the author's words, as every game
   word; `lift` reads back only these;
2. then, for each of those texts in the same order, the text with its noun replaced by each other title of
   `CHIEF_TITLES` -- "chief", "leader", "elder", "headman" / "headwoman", "council head" -- with the same games
   (`{"all": [{"game": [...]}, ...]}`, weight 1), plus `{"not": {"is_special": c}}` when the event has a chief role
   `c` (a villager role whose `special` or `prefer` is `tribal_chief`). "elder" is left out when any text puts an
   article before a chief word ("A {@chief}"); a noun after "a" in the word's own text takes "an" before "elder".
   "headman" is only for a chief role: the role-sex word `(c.headman/headwoman)` (section 5's list, after `his/hers`:
   `CG_PH_HEADMAN`). The title takes the noun's case: capitals for a capital noun alone or a label's word ("Council
   Head"), a capital first letter when the noun opens the text, else lower case.

Every title of a game is equally likely; with the real Tribal Chief cast in the chief role only the author's VV3
word is eligible ("the Chief"). The pools have flags bit **2 (linked)**. **The draw** (section 6.3): an instance of a
linked pool, when the run (the path's picks, then the segment's) already holds a pick of a linked pool with an item,
takes that item NUMBER -- no roll, no condition asked again -- so every chief word of the run says the same title,
and a resumed run (its picks are in the run's file) shows the same word. Otherwise it is drawn as any pool. Linked
pools of one event hold the same games and titles in the same order (`lower` links them only then). The fit check
measures the longest item as for every pool.

**Words that follow the villager.** A role's words (pronouns and role-sex words, section 5) follow the sex the game
records for the villager -- and, for a carrier (a `nursing_parent` role, or the role a `baby_lost` effect names) and
a role that is or prefers the Tribal Chief, the sex they are DRAWN as with "VVFP Gender Presentation.dll" (section
34: `VvfpGenderPresentationGet`; without the companion, the recorded sex): `story_graph.inc cg_word_female`. A
`sex_change` (section 29) and a `presentation` effect (section 34) set the role's words again, so later pages follow
the change (pages are laid out with the longer word). The Golden Child's words are his recorded sex (his presentation
is never changed).
## 38. The Tree of Life's supplies (`supply`, code 25; the owner, 2026-11-17)

JSON (v6): `{"do": "supply", "item": "cutting_tools" | "soap" | "cloth", "min": a, "max": b}` (the village's; role
byte 0xFF; a..b a gain 1..99 or a loss -99..-1, `min <= max`; the string is the item word). The walk rolls the change
as `damage`'s percent (a..b, each equally likely). An island event's words about The Tree of Life's cutting tools,
bars of soap or cloth bolts change the real count: **a "sack" in an event is a cloth bolt** (the sacks are made per
trip, "Cloth Sacks for Yellow Fruit").

- **The counts** (story_c4.inc `C4_SUPPLY_*`): each object's own saved dword, cutting tools [0x4D8618], bars of soap
  [0x4D8D98], cloth bolts [0x4D8ACC] (`native/vvfp_vv4_supply_cap/vvfp_vv4_supply_cap.c` lists the stock code).
- **The limits:** cutting tools and cloth bolts 0..6, the stock game's own cap; 0..99 when Up to 99 Cutting
  Tools/Soap/Cloth is in place ("VVFP VV4 Supply Cap.dll" loaded and its export `VvfpSupplyCapInstalled` says 1, every
  site written). Soap has no stock cap: an event keeps it within 0..99. Never below 0. A gain never lowers a count
  already above its cap (a save made with the cap raised, opened without it, keeps its count as the stock game does).
- **Not invented yet:** before the item's puzzle is solved (The Cutting Tool, Soap Invented, Cloth Invented; the
  adapter's `puzzle_solved`, the flag the game's Puzzles screen reads) the effect changes nothing: the words are
  story only.
- **Other games:** nothing (the effect is The Tree of Life's). The patcher refuses it in an event whose games do not
  include 4; an event for all five games keeps its words as story elsewhere.
- **The log:** one line in the event's Island Events log entry, `  Cutting tools: 4 -> 6` (`Bars of soap`, `Cloth
  bolts`), only when the count changed.
- **No automatic line** (section 25): whether it changes anything is known only in the game, so the event's own words
  say it.
- **Harmless** (section 7): nobody is changed.
- Tests: `tests/test_vv4_supply_effect.py` (the stock The Tree of Life executable in the emulator: 6 and 99, never
  below 0, the cap kept, nothing before the puzzle, the log line; every new supply event, every choice).

## 39. Goods and traders (`supply`, `trade`, `has_supply`; the owner, 2026-11-16/17)

> Merge note (v1.35.97): #813 numbered these sections 33-35 and its codes trade 26, group 27, village 28 and
> cond has_supply 18; round 6 already held those numbers, so they are sections 39-41, codes 41, 42, 43 and
> cond 19 here. Any other 26/27/28/18 below that means trade/group/village/has_supply reads 41/42/43/19.


docs/event-collection/traders-and-effects-research.md lists every address and its evidence; the engine is
`native/vvfp_story_upgrades/story_graph_village.inc` (`CG_GOODS`).

- **The goods** (`vv_cie_graph.GOODS`): `food`, `tech` (every game); `berries` (VV1); `coconuts`, `fish` (VV2);
  `honey`, `fruit` (VV3: the three trees, a gain to the emptiest planted tree, a loss from the fullest);
  `blackberries`, `cutting_tools`, `soap`, `cloth` (VV4); `noni` (VV5); `collectible` (VV2-VV5). A word the game does
  not keep is story only there; the patcher refuses an effect no game of the event keeps.
- **Never below 0; a gain stops at the game's own ceiling** (the adapter's value limits: berries 5000, coconuts 1500,
  fish 2200, honey 3000, a tree 1000, blackberries 1000, noni 1000; The Tree of Life's three supplies as section 38).
- **Collectibles**: a gain is +1 to a random piece (VV2: a piece not found yet becomes found); a loss takes only a
  duplicate (a count above 1), never a piece's last one, so no set and no population room is ever lost. VV2 has no
  duplicates: it never gives one. The pickup's own messages and trophies are not paid (only the pickup pays them);
  each game reads a set's room live, so a piece that completes a set gives its room at once.
- **`trade`** (code 41): `{"do": "trade", "give": g, "give_amount": n, "get": h, "get_amount": m}`. All or nothing:
  nothing happens when the village has less than n of g, when the game keeps either good not, or when it has no room
  for any more of h. No roll.
- **`has_supply`** (op 19): `{"has_supply": {"item": g, "min": n}}`: the village has at least n of g to give now
  (collectibles: duplicates); `"min": 0` holds when the game keeps the good now (VV3's fruit with a tree planted, The
  Tree of Life's supplies once invented). A trader event offers a trade only behind both (what it gives, n; what it
  gets, 0), so nothing is offered that the village cannot give or the game cannot keep. In Python it is a fact (`has_supply:<item>:<n>`) taken either way.
- **The log**: one line a change, `  Honey: 2990 -> 3000` (food and tech are in the entry's own comparison).
- **No automatic line** (section 25).
- Tests: `tests/test_traders_and_village_effects.py`.

## 40. Group behaviours (`group`, code 42)

`{"do": "group", "kind": k, "who": "all" | role}`, and `"percent": p` for `sick`. Every living, listed villager (VV5:
believers; never The Secret City's stand-in record) of the kind's ages takes the game's closest real action
(`CG_GROUPS`): `relax`, `swim`, `dance`, `pray` (VV5 Praising), `celebrate`, `pond`, `play` (children only),
`stories` (elders 55+ tell, children listen), and **songs, chants and speeches** -- `song`, `chant`, `speech` -- through
each game's celebration, dance, Chief's Address (VV3), praising or honoring (VV5): the song itself is the event's
words. With a role, that villager alone takes the kind's action. `sick` makes p% (rounded up) of the villagers no harm
may reach not (section 7) sick by the adapter's own sickening; `cure` clears every villager's sickness field. Both are
the whole village's only. No roll; no automatic line.

## 41. The village (`village`, code 43)

- `{"what": "event_timer", "min": a, "max": b}`: below 0, the next island event comes as the Gong of Wonder's "luck" brings it (VV2 0x44ECE1: the timer set to now + 60 s), never later than it already was; above 0, a..b hours later (1..72), never past now + the game's own longest gap after an event (A New Home 23 h, The Lost Children 19 h, the later three 15 h). Never before now; which event comes and its odds are never touched. Each game's own timer and clock (`sc_clock`). Every stock write of the timer (VV1 0x41C4AE / 0x42386D..0x423A6F / 0x42E930, VV2 0x4252A2 / 0x42EF7D..0x42F17F / 0x43B6C8, VV3 0x4280B9 / 0x428C8B / 0x4687E5..0x4688D4, VV4 0x41F322 / 0x420359 / 0x43FAE7..0x43FBD0, VV5 0x42485B / 0x425E54 / 0x44279E..0x442834) is a new village's, the pause's shift, or the scheduler's when an event fires -- before its popup shows -- so an event's own write is never overwritten by the event that carries it.
- `{"what": "tech_level", "step": 1 | -1, "area": name?}`: one area (named, or any that can move) up or down within
  1..3. Up by the game's own raise in The Secret City (0x426FD0), The Tree of Life (0x41E1D0) and New Believers
  (0x423610, no trophy); A New Home and The Lost Children by a plain write, as their island events do. Down is a plain
  write (no game lowers a level; every reader reads it live; what was built stays). The Secret City's Nature and Magic
  are never moved from 0 (that would choose the faction) nor back to it. An event with this effect is not gated on tech.
- (words only since the owner's final list) `{"what": "construction", "min": a, "max": b}`: a..b more points (1..2000) on one hut a builder has begun, at random;
  it stops one short of the hut's total so the builder's next trip finishes it the stock way.
- `{"what": "weather", "weather": w}`: `clear`, `sun`, `rain`, `storm`, `fog` by the game's own starter, as its island
  events call it (type, 0): The Secret City 0x41FB40 (no sun), The Tree of Life 0x46BC30, New Believers 0x477060.
  **A New Home and The Lost Children have no weather**: nothing there.
- Each change has its log line (`  Tech level (Science): 2 -> 3`, `  Construction: 1200 -> 1350 of 2000`,
  `  Weather: rain`, `  The next island event: 3 hours sooner`). No automatic line.
- **Not possible:** a fish run outside VV2 (no store: VV2's is `supply fish`). The spawn burst, the work rush and the
  temporary effects are section 42.

## 42. Work rush, a spawn burst, temporary effects, yellow fruit (the owner, 2026-11-18)

> Merge note (v1.35.97): #813 numbered this section 36 and the next 37; sections 36-41 were taken, so they are 42
> and 43 here.

- **Work rush** (`group`, string `work:<Skill>`, the whole village only): `{"do": "group", "kind": "work", "skill":
  "Farming" | "Building" | "Research" | "Healing" | "Parenting" | "Devotion"}`. **That skill's workers** (the owner,
  2026-11-18) are every listed adult (14+; VV5 believers) who has that job ticked on the Details screen
  (VV1 [+0x3D0] 1..5, VV2 [+0x7F8] 1..5, VV3 [+0xEC0], VV4 [+0x1C70], VV5 [+0x1C74] a skill index, -1 none), or who has
  no job ticked and whose highest skill it is (the owner, 2026-11-18: the highest number on the Details screen; a tie
  is the skill the Village screen's Action bar shows under "Skill", its own routine: VV1 0x43B520 (from 0x41FB34) and
  VV2 0x44B4D0 (from 0x429B75) read Parenting, Building, Healing, Farming, Research, the earlier kept; VV3 0x462460
  (from 0x468DDE) Farming, Parenting, Healing, Research, Building, the earlier kept; VV4 0x46AC20 (from 0x4402EA) and
  VV5 0x4755C0 (from 0x442E8B, Devotion sixth) the same order of float skills, each against the best so far cut to a
  whole number (_ftol): 40.2 after 40.7 wins, 40.0 does not). Another job ticked: never. They take the game's own job action for it (`CG_WORK`, the adapters' labels: Foraging, Harvesting coconuts,
  Fishing (VV3), Harvesting blackberries, Harvesting noni; Researching; Fixing hut / Exercising / Doing exercise;
  Healing someone / Studying medicine / Health chanting; Telling a story; Praising). Every other adult takes the busy
  state with no skill: **VV3 "Working 'til he/she drops!"** (action 0x3A), VV4 / VV5 "Needs to sit down" (0x4F /
  0x55), VV1 / VV2 "Sitting". Children are left as they are, and so is anyone carrying a baby (the adapter's
  `off_pregnant`) or sick (`cg_is_sick`): the stock games never send them to work (the owner, 2026-11-19). A game with
  no action for the skill leaves everyone as they are. That the busy states give no skill is traced in the emulator (`tests/test_work_rush_rest_gives_no_skill.py`:
  ten runs of each to its end change no skill, while ten Research / job trips do).
  **The busy state is done at the job's site** (the owner, 2026-11-18; the adapters' `behave_at`): the job's own
  starter runs for the busy villager and picks the place it would give a worker (its first walk step: VV1-VV4 type 3,
  VV5 type 4), none of its steps is kept; then VV1 / VV2 queue that walk (0x4399F0 / 0x449B70) before Sitting, and
  VV3-VV5 queue the busy action and replace its own walks with that one walk, its other steps kept in order. A job that
  walks nowhere (VV1 / VV2 Healing someone: it heals where the healer stands) leaves the busy villager where they
  stand. The tips a VV1 / VV2 job starter leaves for the selected villager are put back. **Crowded:** a spot within 20
  pixels of one already taken (every worker's first, then each busy villager's) is crowded; the busy villager is
  given the nearest free spot among up to 8 of the job's own picks (its starter run again), or the first when every
  pick is crowded (VV2's palm has one foot: they share it). Tests: `tests/test_work_rush_busy_at_job_site.py`.
- **Spawn burst** (words only: the owner's final list, 2026-11-18) (`village`, `{"what": "spawn"}`): the game's own random spawner fills its free map spots: VV2 0x415490
  (one spot, only when empty, 0x4152D0), VV3 0x42D940 (-1, 0, 0) and VV4 0x413EE0 (-1, 0, 0) twice (two spots),
  VV5 0x4141E0 (-1, 0, 0, 1, 1, 1, 1) twice (random items take a spot only while fewer than two lie out). A New Home
  makes its mushroom inline in its update: nothing there. One log line, `  Something new lies on the island`.
- **Temporary effects** (words only: the owner's final list, 2026-11-18; no vanilla island event makes any; the compiler refuses them) (`group`, string `effect:<word>`; one role or the whole village): `{"do": "group", "kind":
  "effect", "effect": w, "who": ...}`, each by its game's own setter, so each is an entry of the game's own effect list
  and Fix Vanilla Bugs' effect timers (PRs #773/#782: paused with the game, kept only by the autosave, ended only by
  its own action) cover it with no bookkeeping:
  - VV3 potions, 0x4583A0 on the villager (the pot's source 0x582610, the potion's id; its own switch sets the length):
    `smarter` 3, `inspired` 4, `healing` 9, `bouncy` 11, `hiccups` 18, `swift` 24, `stinky_breath` 36, `soapy_taste` 37,
    `nonsense_talk` 38. Never 26/27 (the vial: The Sharks), never the harmful or owner-question ones.
  - VV4: `clean` (0x437EC0 on 0x4D8B18, mode 1: the soapy pond's sparkles, 240 s), `glow` (mode 0: the meditation's,
    240 s; research x3), `gunk` (0x438CA0 on 0x4D8CCC, 180 s; wiped off on the tree), `stew_wait` (0x460A90, the pit's
    source 0x4D6F50, stew 8: a little health and the 600 s "no more stew so soon" wait; a bare wait has no setter).
    **Allowed together (the owner, 2026-11-18):** `clean` and `glow` are the two marks The Tree of Life's purification test asks of a villager (0x45EBE0 / 0x45EB90), so a villager with both counts as pure of body for Purify Tree: dropped on the Tree within their 240 s (with Dendrology 3) it purifies it, the bath and the meditation skipped. An effect alone never advances a puzzle.
- **Yellow fruit** (`supply` / `trade` / `has_supply` word `yellow_fruit`, The Tree of Life): "VVFP VV4 Fruit
  Supply.dll"'s own count through its new export `VvfpYellowFruitAdd(delta)` (0..1,000; 0 reads; -1 not installed or
  no village; nothing written until the next save). Without "Yellow Fruit Trees are No Longer Unlimited" the tree has no
  count: words only. PRs #794 and #805 also change that DLL: this change only adds the export after the refill.
- Tests: `tests/test_traders_and_village_effects.py` (`WorkRushSpawnTempEffects`), `tests/test_vv4_yellow_fruit_trees_limited.py`
  (`IslandEventAdd`; it needs research/game-data/vv4).

## 43. The owner's final list (2026-11-18): what is real, what is words only

Anything not real is words only: an event may say it, the game never changes for it, and the patcher refuses it as an
effect (`group` kinds and `village` whats not listed, `effect:<word>`).

| Effect | Real? | Notes |
|---|---|---|
| `supply` / `trade` / `has_supply` (food, tech, items, collectibles; PR #806's VV4 supplies; yellow fruit) | real | never below 0; a gain never completes a collection set; never a VV3 Tablet piece |
| Cloth as a material (VV4) | real | PR #806's `supply cloth` |
| `group`: relax, swim, dance, pray, celebrate, pond, play, stories, song, chant, speech | real | actions only: the adapters' non-"Unsafe" stock actions, no stored value, no skill unless the stock action trains one |
| `group`: sick / cure | real | as the vanilla events: protected villagers are never made sick |
| `group work:<Skill>` (work rush) | real | the ticked job, or (none ticked) the highest skill, a tie the Action bar's pick; others take the busy state at the job's site with no skill; Parenting is storytelling only (VV2, VV3), nothing where there is none (VV1, VV4, VV5) |
| `village tech_level` | real | exactly one level, within 1..3 |
| `village weather` | real | VV3-VV5 only |
| `food` / `tech` (pre-.97) | real | unchanged |
| `damage` (hut damage, pre-#806) | real | any building, the owner's ruling |
| `village event_timer` | real | sooner = the Gong of Wonder's luck (VV2 0x44ECE1: now + 60 s), never later than it was; later = the hours given, never past now + the game's longest gap (23 / 19 / 15 / 15 / 15 h); never before now; which event and its odds are untouched |
| `effect:` potions, clean, gunk, glow, stew wait | words only | refused |
| fish run, research progress | words only | no such effect is made (VV2's fish stays a trade good) |
| `village construction`, `village spawn` | words only | refused |

Effects the engine had before PRs #806 / #813 (codes 1-24 and conds 1-17: food, tech, pay_award, kill, vanish,
status, health, preference, skill, sick, celebrate, action, mood, health_change, skill_set, damage, appearance,
die_unrecovered, baby_lost, birth_then_die, old_look, sex_change, presentation, deliver_early) are not part of this
cut and are unchanged.

The work rush's busy villagers go to the job's site (section 42). Parenting rushes are storytelling only (VV2, VV3), nothing elsewhere, so the Birth Control patches are never bypassed.

## 44. Village Solidarity tags (the owner, 2026-11-17)

A page (`popup` or `question` node, never a `branch`) may carry `"solidarity": "raise" | "lower" | "neutral"`, in
every format version. In the .cieg it is the node flags byte (offset 3), bits 2-3: 1 raise, 2 lower, 3 neutral
(`SOLIDARITY_CODES`, `NODE_SOLIDARITY_MASK` 12; bit 1 is section 19a's new page); bit 0 stays the automatic outcome lines (25). An untagged node keeps
0, so an untagged graph compiles to the same bytes as before. With "VVFP Village Solidarity.dll" in the game, the
Story companion passes a reached page's tag on (`VvfpVillageScoreTag`: raise +5, lower -5, kept within 0..100) and
weights a chance split's children by the tags of their next pages (`VvfpVillageScoreFactor`); without it the tag is
only a word in the file. The collection's tags are kept apart from the event files, in
`data/event_collection/solidarity_tags.json` (`scripts/tag_village_solidarity.py`), and applied when the collection
is built; an event's own kind (`cooperative` / `repair`) is the manifest's tenth column.

Every added event's every ending is tagged (the owner, 2026-11-20: "add tags to every single event"), by the owner's
rule as code (`src/vv_solidarity_endings.py`: the effects first, then the words of the village as a whole): the
collection's (`solidarity_tags.json`, with the reviewed judgement calls in `solidarity_review.json` and the Living
Culture drafts' own `[Solidarity: ...]` tags), the Living Event Engine's (`data/living_events/solidarity_tags.json`:
each outcome archetype and MC outcome, written on every variant's ending), the procedural pieces' (an outcome piece's
flags bits 3-4, the same codes, which the Story companion writes into the composed page's node flags bits 2-3), the
Custom Island Event Library's two examples (`data/cie_graphs`), and More Island Events' own endings (its DLL calls
`VvfpVillageScoreTag` once with each ending's effects, only when the companion is loaded).
`tests/test_solidarity_added_events.py` fails on any untagged shipped ending.
