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
| 92 | `I` | 0 |

Section order in the file: header, roles, nodes, children, effects, conds, variants, patches, **pools, items**,
strings. The engine must use the offsets, not the order.

## 2. Role: 16 bytes (v1-v5: 8)

| Offset | Type | Meaning |
|---|---|---|
| 0 | `B` | kind: 0 villager, 1 stranger, **2 alias**, **3 other** (G2) |
| 1 | `B` | flags (a stranger, kind 1: 1 = **named**, section 16; nothing else): 1 optional, 2 exclude_nursing, 4 exclude_special, 8 believers_only, **16 harm_capable**, **32 exclude_protected**, 64 the author wrote protected "exclude", 128 the author wrote "allow" (64 and 128 are for decompiling only; the engine reads 32) |
| 2 | `B` | sex: 0 any, 1 male, 2 female, 3 random (strangers) |
| 3 | `B` | min_age years |
| 4 | `H` | id string |
| 6 | `B` | age-gap role + 1 (0 none) |
| 7 | `B` | age-gap years |
| 8 | `B` | max_age years, 0 = none (the villager's age in whole years must be at most this) |
| 9 | `B` | special: 0 none, 1 golden_child, 2 tribal_chief, 3 nursing_parent (the role MUST be that villager) |
| 10 | `H` | skill requirement: the skills' names, comma separated (`NONE` = no skill requirement) |
| 12 | `B` | skill min (the villager's value in at least one listed skill the game has is at least this) |
| 13 | `B` | pick: 0 random, 1 highest (keep only the villagers with the top value of the listed skills, then draw) |
| 14 | `H` | alias: member mask (bit k = role index k); other (kind 3): exactly one bit, the alias it follows; 0 for the rest |

- In v6 the compiler sets flags 2 and 4 exactly when it sets 32, so code that reads only 2 and 4 stays safe.
- `exclude_protected` (32) = keep out nursing parents of either sex, the Golden Child, the VV3 Tribal Chief, the
  VV5 special roles, VV2 totems, the VV3 stand-in record and anyone the stock pickers skip.
- `harm_capable` (16) is compiler-derived (section 7). A harm-capable role always has 32 in an owner's
  collection event; in a player's own graph the player may set `protected: "allow"` (see 7).
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
  crisis D1, whose patient is story text). Role count 0 in the header; nothing is cast; `min_eligible` is 0. A
  name or pronoun placeholder, a role condition or a villager effect in such a graph is an error.

## 2a. Node record (28 bytes, unchanged size)

`B type, B append, B paragraph, B 0, H id, H text, H variant first, H variant count, H child first, H child count,
H else, H effect first, H effect count, H summary, H outcome, H title`. As v5, except the last H (0 in v1-v5): in
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

- **Pool: 12 bytes (G3; was 8).** `H name string, H first item, H item count, B flags (1 = distinct), B 0,
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
    `lady/gentleman` -- the word of the pair that matches the role's sex (a male role: father, father, dad, brother,
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
- Labels (choice labels): placeholders, `\(` `\)` and game words `{@w}` only. At most 95 bytes in v6 (v1-v5: 39).
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

Harmful effects: `kill`, `vanish`, `sick`, `health` with max < 100, `health_change` with min < 0, `preference`
dislikes, `skill` with a negative amount, `mood` bad, `action` from the MOOD group or marked (Unsafe) in the
game's action list (`data/cie_actions.json`).

- A role is harm-capable when a harmful effect anywhere in the graph acts on it, or on an alias whose members
  include it (an alias that is harmed makes every member harm-capable). Flag 16.
- `protected`: `"auto"` (default) sets 32 exactly when 16 is set; `"exclude"` sets 32 always; `"allow"` sets 32
  never. In an owner's collection event (a graph with a `collection` block) `"allow"` on a harm-capable role
  and any `special` role that is harm-capable are errors. In a player's own graph the player decides (the owner,
  Q5): `"allow"` is accepted.
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

A role byte may name an alias; the effect goes to the member drawn.

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
- **The readable form** (the Island Events log's "Event:" line, "Disappeared in ...", Pick Island Event, the library,
  the queue's messages; `readable_title` / `cg_readable_title`): every name placeholder becomes "someone" in the
  case written (`(Name1)` -> `Someone`, `(NAME1)` -> `SOMEONE`, `(name1)` -> `someone`), every pronoun or role-sex
  word its pair as written, joined by "or": "he or she", "his or her", "woman or man", "mother or father", ...
  (the case written: `(He/She)` -> `He or she`, `(HE/SHE)` -> `HE OR SHE`). The result is cut to 47 bytes. E.g.
  "Someone's No Good, Very Bad Day". The library's file name is made from this form.
- `VvfpStoryGraphLogged` accepts the readable form, or the title armed (expanded).
