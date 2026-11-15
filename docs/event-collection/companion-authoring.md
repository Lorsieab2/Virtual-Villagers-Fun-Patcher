# Companion Anthology: authoring rules for the chunk agents

The owner's Companion Anthology (five volumes, 749 events) is the collection's SECOND frozen source. Its events ship
in the same "Isola Grand Event Collection" rows as the Grand collection's: the same v6 format, the same checker, the
same manifest.txt, the same rare roll and Pick Island Event list. Everything in [authoring-rules.md](authoring-rules.md)
applies; this file adds what is different for the companion, with examples from wave 1 chunk 1 (Vol 1 Part 1 and
Part 3 001-030, `scripts/companion/gen_c5a.py` and `gen_c5c.py`).

## 1. The source and the pipeline

- Source: `docs/more-island-events/Isola_COMPLETE_Master_Companion_Anthology_749_Events.txt`, a byte copy of the
  owner's file (SHA-256 `d39d14da...4ff16`, recorded in `data/event_collection/COMPANION.sha256`; `-text` in
  `.gitattributes`). Never edit it. Its line numbers are its own: **every `src` in a companion file means a line of
  THIS file**, never of the V28 source.
- `collection.source` is `"companion"` (`--format` fills it from the manifest row). `scripts/collection_check.py`
  checks each file against its row's source (`collection_lib.use_source`); the companion's own structural markers
  (section 3) apply only there.
- Manifest: `scripts/collection_manifest.py` finds the companion's events by their headings and writes one row per
  event (`"source": "companion"`) and one per notes section (23). `manifest.json["companion"]` holds its counts,
  uncovered lines and overlaps (all must stay empty). Never edit the manifest by hand.
- Files: `data/event_collection/companion/<section>/<id>.json`, sections `c5` (Companion Volume 5, Parts 1-5),
  `lbl` (The Lives Between Legends), `fwk` (The Four Ways of Knowing), `sss` (Stone, Spirit, Strangers & Mind and
  Belonging, both of its volumes) and `cat` (The Living Catalogue).
- Ids: the manifest's, at most 22 characters (every companion event is in A New Home): `c5a` Part 1, `c5b` Part 2,
  `c5c` Part 3, `c5dn` Part 4 (N001), `c5ev` Part 5 (V001), then `lbl`, `fwk`, `sss`, `cat`, the source number and a
  slug of the title. When the word rule leaves an id that no longer names its event, add an entry to
  `COMPANION_IDS` in `collection_manifest.py` BEFORE you author that event (chunk 1 did so for c5a007, c5a018 and
  others), then rerun the manifest.
- Credits: each row's credit is the anthology's own (L4-5) plus its volume's or part's credit lines, verbatim
  (`CREDITS["comp_*"]`). `Credits.txt` carries the companion's credit blocks (build_event_collection_features.py
  `COMPANION_CREDIT_BLOCKS`).
- Series: the Living Catalogue's templates are seven series (`cat_bodies`, `cat_fins`, `cat_foliage`,
  `cat_flowers`, `cat_magic_fish`, `cat_magic_plants`, `cat_creatures`): each counts as ONE event in the rare roll.

## 2. The owner's decisions (2026-11-14), binding

1. **Verbatim.** The owner's text ships as written, apart from GLARING grammar fixes. No prose expansion: the
   volumes' prompts that ask Claude to "expand each of the three outcome seeds into polished in-game prose" (Lives
   Between Legends L3790), "full choice-specific, non-template outcome branches" (Four Ways L6042) or "at least one
   event-specific alternate result per choice" (Stone, Spirit L6762) are notes rows, never carried out.
2. **Grammar fixes** go in [grammar-fixes.md](grammar-fixes.md) under "Companion Anthology", each row starting
   `| companion L<line> |`. Glaring only.
3. **The rare roll** weights every event equally across More Island Events, the Grand collection and the companion
   (`story_collection.inc` `sc_choose_and_arm`). A series still counts as one. Keep `draw_weight` 1.
4. **Deaths** use `"cause": "unknown"` ("Unknown causes"). **Only VV2 totems are always protected**: a nursing
   mother, a baby, the Golden Child or the VV3 Chief may be harmed only where the event's own risk makes sense, with
   `"protected": "allow"` on that role, and every such case listed in `docs/event-collection/retrofit-harm-review.md`
   (event, outcome, villager, exact text, why). New Believers' story villagers stay unharmable.
5. **Part 5 V051-V059** do not exist in the file; the owner will send them later. Do not invent them.
6. **Same titles**: seven companion pairs and six companion/Grand pairs are OPEN owner questions in
   [owner-title-changes.md](owner-title-changes.md). Rename nothing.

## 3. The companion's structural markers (collection_lib.COMPANION_STRUCTURAL)

Taken out of a line automatically, companion only: a `•` bullet; `RANDOM OUTCOME n -` (Vol 1 Part 1);
`WEIGHTED OUTCOME n:` and `PLAYER RESPONSE A -` (Lives Between Legends); `SCENE:`, `Premise:`, `OUTCOME:`,
`Outcome:`; a numbered `1.` at a line start (Part 4 outcomes, V060 options). The Grand collection's markers also
apply (`SETUP:`, `OUTCOME A:`, `A.` at a line start, `- ` and `* ` bullets). Anything else that is not shown is a
ledger entry: a designer tag on an outcome is a `note` cut with `text` (`"SUCCESS:"`), a heading line is
`structural`, a rule or prompt line is a `note`.

## 4. The format mapping (inventory section 4, verbatim-only)

| Source | v6 |
|---|---|
| Title line (`EVENT 001 - The Kiln's Secret`) | `title` with `collection.title_src`; an all-capitals title (Four Ways) in title case: the check compares case-free |
| Group heading above an event (`POTTERY`, `TEXTILES, CRAFTS AND HOMES` with its rules, `01 - BODIES, MINDS...`) | Part of the event's manifest lines; a `structural` ledger entry per line (`companion_common.group_heading_ledger`) |
| SETUP / SCENE / Premise / the one-sentence scene | The first page's text |
| Generic choices the same in every event (Part 1's three, Part 2's two or three, Lives Between Legends' three) | The labels, each with its own `src`; ALL lead to the SAME outcome branch (the source: outcomes are not tied to choices) |
| Event-specific choices with no outcome of their own (Part 3's six "optional prompts", Four Ways Part II) | Labels to the shared ending branch (Four Ways Part II: inventory Q5, owner's call pending) |
| True choice/outcome pairs (Stone, Spirit A/B/C + Outcome; Living Catalogue CHOICE/OUTCOME x4) | One answer page per choice |
| No-choice events | One popup: the scene, then one ending appended (`"popup": "append", "join": "paragraph"`) |
| RANDOM OUTCOME / POSSIBLE ENDINGS / WEIGHTED OUTCOME / OUTCOME A-B / ALTERNATIVE OUTCOMES | A branch with equal children (no odds given). A death branch: `very_rare` (2); "RARE FATAL": `rare` (5) |
| FOLLOW-UP HOOK, OPTIONAL CONTINUITY, TONE, TRIGGER, PERSISTENCE, EFFECTS, Contextual consequences, Context and callbacks, Context / follow-up, `CHOICE: Optional...`, `CHOICES: No choice by default...`, `Primary specialty:` | Ledger `note` (never shown) |
| Instructions inside an outcome ("gain a small skill boost", "update a preference", "where supported") | Ledger `note`/`instruction` cut plus the effect, or `text_only` |
| V060's per-game accounts | Node `variants` with `{"game": n}`; "the Chief" (L3717) as `{@chief}`; "Heathens" (L3725) needs its Guardians form |
| Living Catalogue species names | Literal text, one file per event, generated |

## 5. Casting

- The text names nobody: roles carry no token. Cast the people an effect lands on, and anyone the scene needs to
  exist (rule 10: a role with no token is allowed); a role no effect uses goes in `collection.cast_only`.
- Ages (companion_common): `VILLAGER` 14+, `GROWN` 18+, `CHILD` 3-13, `TEEN` 14-17 (the "ages 14-17 only" events),
  `ELDER` 55+ (the collection's elder age, as V27; inventory Q6 is the owner's), `ANY_AGE` 3+.
- A trade the text names as a qualification ("a healer", "a respected builder"): `skilled(VILLAGER, "Healing")`.
- Kinship the text states: `related(spec, "parent_of" | "sibling_of" | ..., other)` (cie-v6-binary.md 21). Chunk 1:
  `c5c002` two siblings, `c5c003` a father (`sexed(GROWN, "male")`) and his child, `c5c004` a parent and grown child,
  `c5c009` / `c5c025` a parent and child. Grandparents, aunts and cousins have no relation yet (gap C2): text only.
- A deceased loved one in the premise stays generic text (gap C3).

## 6. Effects (the V28 consequence rules, retrofit_brief; nothing beyond what the text supports)

- **Parenting**: a child's caregiver the text names gains a small Parenting on EVERY outcome (Parts 1-4 rules).
  Example `c5c003_crooked_braid`: `father` gains Parenting 5-10 on both endings.
- **The principal discipline** (Part 1 rule L72): the SUCCESS outcome only, a small skill to the specialist, mapped
  per inventory Q9 (Medicine, Potionmaking -> Healing; the sciences, History, Alchemy -> Research; the mechanist ->
  Building). Pottery, Combat Arts, the exploration machines, weaving: no game skill, no effect. Example
  `c5a004_misplaced_label` (Healing on o1).
- **Celebrate** only where the village celebrates (`c5a024_eclipse_watch` o3: "The village holds a nighttime festival
  to celebrate celestial cycles"). A household's or a person's celebration is `text_only` (`c5c020_missing_tooth`).
- **Harm**: injury and illness `health_change` (minor -30..-10, serious -60..-40), `sick`, `kill` (cause unknown),
  `die_unrecovered`, `vanish` (missing is not dead: no grave), `baby_lost` -- only on an EXISTING outcome whose text
  says so; weights: harmless common (20), minor setback occasional, serious or disappearance rare (5), death very rare
  (2). Never add a branch the owner did not write.
- **Effects-table words that change nothing** get `text_only` with a reason, never a fake effect: "questions about
  death" (`c5c007` e2), "why a loved one had to die" (`c5c027` scene), "a favorite food" (`c5c028` e2), "an injured
  villager" as the scene (`c5a029`), "food storage" (`c5a030`), "designs collapse" (`c5a003` o2: clay, not a
  structure).
- Rules 7-9 (reputations, councils, festivals as institutions, skills a game lacks, lasting states, memories,
  relationships): text only.

## 7. The Pick Island Event sentence

`collection.description`: one plain sentence, at most 130 characters, `. , ! ? : ; ' -` only, no spoiler of a rare
outcome. Usually the scene in fewer words; with event-specific choices, the choice after a colon
(`c5c002`: "Two siblings who argued shelter beneath the same broad leaf: let them speak first, or give them time.").
The generic choices of Part 1, Part 2 and Lives Between Legends are not named.

## 8. Workflow and checks

1. Write `scripts/companion/gen_<part>.py` on `companion_common.py` (rows from the manifest, `shown()` for page text,
   `group_heading_ledger()`, `page()`, `write_and_check()`); its table is the authoring record (roles, effects,
   descriptions, text_only reasons, one row per event). Hand-written JSON only where the event is unique.
2. `python scripts/companion/gen_<part>.py` writes the files and runs `collection_check.py --format` on them: every
   file must print OK.
3. Then `python scripts/build_event_collection_features.py` (it writes the Game Mechanics index too), and the
   test files one per process: `tests/test_event_collection_files.py`, `tests/test_event_collection_package.py`,
   `tests/test_collection_trigger.py`, `tests/test_game_mechanics_collection.py`.

## 9. Known gaps for later chunks

- **Shared pools from the companion** (Four Ways' identical "Possible resolution 1-3", K7):
  `shared_pools.json` items are checked against the V28 source only. A companion pool needs a pool-level
  `"source": "companion"` in `check_shared_pools()` (and the engine must accept or ignore that key); or write the
  pool inline in each event.
- **Pick Island Event's list holds 256 entries** (`story_more_events.inc` `SM_MAX`, More Island Events' plus the
  collection's). With the whole anthology a game lists about a thousand events: the list stops at 256 until it grows.
  The rare roll itself reads up to 2048 entries (`SC_MAX`) from a manifest of up to 1 MiB.
- C1 random preference, C2 wider kinship, C3 dead-kin condition, C4 nursing-baby target, C5 appearance modes, Q10
  bereaved nursing mothers: see the inventory; write around them as it says and list each use.
