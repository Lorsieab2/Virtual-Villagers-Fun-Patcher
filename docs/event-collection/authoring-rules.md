# Isola Grand Event Collection: authoring rules

These are the exact rules for turning one event of the owner's collection into a collection file. They implement
design section E3 and the binding answers in the collection decisions (Q1-Q17). `scripts/collection_check.py` checks
every rule that can be checked; a file is finished only when it prints `OK`.

The owner's two standing rules come first:

- **The owner's text is preserved exactly.** Only the mappings below and the listed grammar fixes
  ([grammar-fixes.md](grammar-fixes.md)) may differ from the source. Never polish, shorten or "improve" a sentence.
- **Protected villagers are never harmed**: nursing parents of either sex, the Golden Child, the VV3 Tribal Chief,
  VV2 totems, New Believers' Heathens and anyone stock events never pick.

## 1. Files and the workflow

1. Find the event's row in `data/event_collection/manifest.json`. Its `id`, `section`, `lines`, `games`, `choices`,
   `pools` (the bank sizes, recounted from the source) and `series` are fixed. Never edit the manifest by hand: change
   `scripts/collection_manifest.py` and rerun it.
2. Write `data/event_collection/<section>/<id>.json` (format `vvfp-cie-graph`, version 6; design section A and
   `docs/event-collection/cie-v6-binary.md`).
3. Run `python scripts/collection_check.py --format data/event_collection/<section>/<id>.json`. `--format` fills the
   `collection` block's source facts from the manifest (`source`, `lines`, `section`, the verbatim `credit`,
   `draw_weight`, `series`) and writes the canonical JSON. Never type a credit by hand.
4. Fix every problem it prints, rerun, and commit only when it says `OK`. `--report` prints the ledger summary (grammar
   fixes, text-only effects, typography) for the owner packet.

The source is the frozen copy `docs/more-island-events/Virtual_Villagers_Isola_Grand_Event_Collection_v26_user_source_credited.txt`
(SHA-256 in `data/event_collection/SOURCE.sha256`). Line numbers always mean that file.

## 2. Authoring-only keys

These keys exist for the checks and the owner packet. `collection_check.graph_for_engine` removes them before the
format sees the file; never rely on them at run time.

| Where | Key | Meaning |
|---|---|---|
| `collection` | `title_src` | The heading line that holds the title (`"L3045"`) |
| `collection` | `ledger` | Source lines (or text on a line) that are consumed but not shown (section 5) |
| `collection` | `inline_sets` | Manifest banks written as inline picks `{a\|b}` instead of a pool or branch |
| `collection` | `shared_lines` | A section's shared text an event also shows (a festival's setting paragraph); must lie in a notes row |
| node | `src` | The source lines of the node's `text` |
| node | `text_only` | `[{"src", "what", "reason"}]`: a promised change the games cannot make, and why (section 7) |
| node | `set` | On a branch node: the manifest bank its children are (`"(1)"`) |
| node | `src_pick` | `[{"src": "L592", "alt": "cancel the contest"}]`: the node shows one option of a source slash list (section 11) |
| pool | `set` | The manifest bank the pool is (`"A"`, `"(3)"`) |
| pool | `mirror_of` | The same bank with its pronouns on another role (section 10) |
| pool item, choice, variant, effect | `src` | Their source lines |
| child, pool item | `rarity` | `rare`, `very_rare` or `exceptionally_rare` (section 8) |

`grammar_fixes` is a top-level list the format itself keeps (section 13).

## 3. src tags

- `"src": "L3070-3071"` is lines 3070 to 3071; `"L102,L104,L106"` lists several; a single line is `"L3054"`.
- Every text-bearing field has one: node `text`, every `variants[].text`, every choice `label`, every pool item.
  A text made only of tokens (`"{END}"`) needs none: its items carry their own.
- The text must be found, word for word, inside the source lines its tag names (section 4). Each paragraph (`\n`) is
  checked on its own, so one node may join paragraphs from several places: `"src": "L3049-3051,L3061-3064"`.
- An effect's `src` is the instruction line it implements (`"Both gain Farming experience if supported."`).

## 4. What may differ from the source

The fidelity check compares each text with its source lines after applying, in order:

1. **Typography** (automatic): `—` becomes ` - `; `–` becomes `-`; curly quotes become `"` and `'`; `…` becomes
   `...`; `ç` `é` become `c` `e`. Write the plain form.
2. **Grammar fixes** listed in the file's `grammar_fixes` (section 13).
3. **Ledger cuts**: text a ledger entry takes out of a line (designer notes, instructions).
4. **Structural markers** (automatic): `CHOICE A:` / `CHOICE A —` / `CHOICE:` prefixes; `A.` `A:` `A1 —` outcome
   letters at a line start; `- ` and `* ` bullets; a route `(3)` at the start or end of a line; `Go to (5).`;
   `— choose one:`; `(VV3–VV5 ONLY)` on a choice; a line that is only `(3)` or `(4):`.
5. **Tokens**: in the file's text, each token stands for source text:

| File | Source | Example |
|---|---|---|
| `(role)`, `(Role)`, `(role.he/she)`, `(role.His/Her)` ... | any one source parenthesis group | `(Healer1)` for `(Healer1)`; `(patient)` for `(patient name)`; `(cook1)` for `(name1 or name2)` |
| `{P}`, `{P.2}` (pool) | one source parenthesis group, or the pool's own items as the source's bare `a/b/c` list | `{A.2}` for `(A, different)`; `{ING}` for `fish/mushrooms/.../a magical potion` |
| `{a\|b\|c}` (inline pick) | the source list `(a/b/c)` or bare `a/b/c`, item for item | `{relieved\|frustrated\|anxious}` |
| `{@chief}` (game word) | one of the word's values, or `Chief` / `the Chief` / `a Chief` / `Chiefs` | `{@Chief} refuses` for `The Chief refuses` |
| `\(` `\)` | a literal parenthesis | `\(Required ingredient: {ING}.\)` |

6. The first letter of a text may change case (a list item that starts a sentence).

The title may change only in case (`THE GARDENING CONTEST` becomes `The Gardening Contest`) and drop a heading's prefix
(`EVENT:`, `V13-C — UNIVERSAL:`, `01.`). It must fit 30 characters in VV3-VV5 and may not hold `"` (section 16).

Nothing else may differ. Every other change is a fidelity failure.

## 5. Coverage and the ledger

Every non-blank line of the event's manifest lines must be consumed, and every word on a line a text consumes must be
matched by some text or taken out. A line is consumed by a `src` of a text field, by the title, or by a ledger entry.

```json
"ledger": [
  {"src": "L3044", "kind": "structural", "why": "game heading"},
  {"src": "L3046", "kind": "note", "why": "designer summary of the cast"},
  {"src": "L3071", "kind": "instruction", "text": "Both gain Farming experience if supported.", "why": "the skill effects on s1"},
  {"src": "L230", "kind": "gap", "set": "D-CUISINE", "why": "no token for the village's name"}
]
```

- `structural`: headings, bank labels (`A — APPROACH:`, `(1) SHARED GARDEN — choose one:`), routes like `(to 2)`.
- `note`: designer notes and rules never shown (`(deliberately unsuitable container)`, "IMPLEMENTATION NOTES").
- `instruction`: a mechanical instruction (`(earn tech points)`, `Parenting skill: SIGNIFICANT GAIN`); the matching
  effect or `text_only` entry carries the same line in its `src`.
- `bank_ref`: a line that only names another bank ("use the coda bank").
- `gap`: a bank item the format cannot express yet. Give its `set` so the bank size still matches. List every gap in
  your report.
- Without `text` the entry consumes the whole line(s). With `text` it cuts exactly that text from one line (the
  rest of the line must still be consumed by a text). A cut before a full stop leaves no space before it.

## 6. Instructions become effects

Map each instruction to an effect on the node whose page shows that outcome, and cut the instruction text with a
ledger entry. The effect keyword table checks this: a node whose source lines say one of these words must have an
effect of that kind, or a `text_only` entry for that line.

| Source word | Effect |
|---|---|
| food, (large award) food | `{"do": "food", "size": ..., "scaled": true}` (a loss adds `"loss": true`) |
| Tech, technology, tech points | `{"do": "tech", "size": ..., "scaled": true}` |
| experience, skill | `{"do": "skill", "role": r, "skills": [...], "min": a, "max": b}` |
| "100% skill", masters | `{"do": "skill", "role": r, "skills": [...], "set": 100}` |
| dies, death | `{"do": "kill", "role": r, "cause": "unknown"}` |
| disappears, vanishes, flees | `{"do": "vanish", "role": r}` |
| celebrates, celebrating | `{"do": "celebrate", "who": "all"}`, or a role when only named villagers celebrate |
| dislikes | `{"do": "preference", "role": r, "list": "dislikes", "preference": "<the game's own word>"}` |
| injured, lose health, health | `{"do": "health_change", "role": r, "min": ..., "max": ...}` |
| collapses (a structure) | `{"do": "damage", "structures": "any", "min": 50, "max": 100}` |

- "(large award) food" shown in the text is `(award)`: give `"defer": true` on the food and a `{"do": "pay_award"}`
  on the same node (`Your village gains (award) food.`).
- Preference words must be the game's own (`running`, `work`, `cooking`, `herbs`, `medicine`;
  `vv_cie_graph.GAMES[g].preferences`). When the source's word is missing, use the source's own alternative and say
  so in the report.
- Skill names must exist in every game the event lists (`Parenting, Building, Farming, Healing, Research`; VV5 adds
  `Devotion`). A list (`["Research", "Healing", "Devotion"]`) picks one at random; a skill a game lacks is skipped.
- A keyword that is narrative ("One garden produces more food", "proudly celebrates its first leaves") gets a
  `text_only` entry whose reason says so.
- A kill's cause: `"unknown"` (the stock island events' words) unless the source gives grave words.
- Effects on a node are made when its page is shown. Changes before a question need a page of their own: put the
  question's lead text on a popup before it.

## 7. Text-only reasons

When the source promises a change the games cannot make, keep the text, add no effect, and give the reason:

```json
"text_only": [{"src": "L1609-1612", "what": "a lasting disability",
               "reason": "rule 9: no game has a lasting disability"}]
```

- **Rule 7**: prizes, trophies, titles, reputations, councils, hearings, bans, stalls, eateries: told only.
- **Rule 8**: a skill, effect or preference word the game lacks (Artistic, Physical, Crafting, Learning; restoring
  crops or berries; "construction progress").
- **Rule 9**: any lasting state (disability, half-alive, suspended animation, rivalry, a later lesson, "a later
  corrective event", relic tracking, sequels and follow-ups). Optional long-term follow-ups are ledger `note`s.

## 8. Weights

- No odds in the source: every split and every pool is **equal** (leave `weight` out or make them all the same).
- Rare words, against a normal outcome's weight of 20 (Q4):

| Source | Weight | `rarity` |
|---|---|---|
| (normal) | 20 | none |
| rare | 5 | `rare` |
| very rare, very rarely | 2 | `very_rare` |
| exceptionally rare, extremely rare | 1 | `exceptionally_rare` |

  As soon as one child of a split has a `rarity`, every normal child has weight 20.
  Example (The Meaning of Faith, "(2) or (5) [the special conversation is a rare alternative]"):
  `"children": [{"next": "paper", "weight": 20}, {"next": "see_me", "weight": 5, "rarity": "rare"}]`.
- An outcome whose result depends on a later state ("NO GAIN if uncorrected; MODERATE if corrected") resolves at once:
  a silent branch to copies of the outcome page, one per stated result, equally likely (The Parent's Lesson A4).

## 9. Sizes

Food and tech use size words; the format expands them into each game's range (design A3) and scales them.

| Source word | Food / tech `size` | Skill `min`..`max` |
|---|---|---|
| small, a little, modest, minor | `small` | 5..10 |
| (no word), moderate, MODERATE, experience | `normal` | 10..20 |
| large, significant, SIGNIFICANT, substantial | `large` | 20..40 |
| huge, enormous | `huge` | 30..60 |

A skill loss is the same range negative (`"min": -10, "max": -5`); it makes the role harm-capable.
"Masters", "100% skill" is `"set": 100`. Never write a raw `amount` for food or tech.

## 10. Roles, pronouns and the Chief

- **Roles** are named for what they are (`gardener1`, `patient`, `teacher`). Shorthand `(Gardener1)` is the name.
  Requirements: adults `"min_age": 14`; a child `"min_age": 3, "max_age": 13`; a skill when the source names one
  (`"skill": {"names": ["Farming"], "min": 1}`).
- **Special villagers** (Q17): the Golden Child (`"special": "golden_child"`, `"min_age": 0`), the VV3 Chief, a named
  nursing parent are cast only in harmless roles. Casting one with no token in the text is allowed (the cast is the
  requirement). Unnamed mentions ("A nursing mother nearby") stay text.
- **Protection** is automatic (`protected: "auto"`): a role any harmful effect can reach keeps protected villagers
  out. Never write `"protected": "allow"` on such a role. VV5 roles are believers only (the default).
- **Pronouns are role-prefixed** whenever the event has two or more roles: `(gardener2.he/she)`,
  `(child.His/Her)`, `(child.himself/herself)`. Capitalise inside the token: `(patient.He/She)`. The source's
  lower-case `(he/she)` at a sentence start is fixed this way, with no grammar fix needed.
- A text-only figure that needs a pronoun ("One healer admits that (he/she) was mistaken") is a `stranger` role
  (`{"kind": "stranger", "sex": "random"}`). The first role must be a villager.
- **"(name1 or name2)" and "(other name)"**: the format has no "the other one of an alias" yet (gap G2). Until it
  does, keep identities consistent as the source asks: the first cook is the one "(name1 or name2)" names, the other
  is "(other name)". Where either may win, write both outcomes (`win1`, `win2`) and route to each.
- **Banks whose pronouns follow the villager they describe** ("(Name1) is (A)(B). (Name2) is (A)(B)") need one pool
  per role until pool items can follow the instance's role (gap G3): write the bank for the first role, and a copy
  with `"mirror_of"` for the second (same items, same `src`, pronouns on the other role). The bank is counted once.
- **The Chief outside VV3** becomes a game word (Q-mapping):

```json
"words": {"chief": {"3": "the Chief", "*": "the village leader"},
          "Chief": {"3": "The Chief", "*": "The village leader"}}
```

  Use `{@chief}` / `{@Chief}` where the source says "the Chief" / "The Chief". Keep the number: a singular Chief
  becomes a singular leader so the verb still agrees ("The village leader listens carefully"); the check refuses a
  singular VV3 value with a plural other. An event without VV3 has only `"*"`. A game word cannot sit inside an
  inline pick: make that list a named pool (`RULE`, `POWERS`). "Chief" in any text a non-VV3 game can show is an
  error.

## 11. Routing

- Routes `(3)`, `Go to (5)` are structural: they become `children` / `next`.
- A choice whose routing depends on which option of a slash list was drawn is written as one node per option with
  `src_pick`, which fixes that option of the source list for the fidelity check:

```json
"f14_opts": {"type": "branch", "children": [{"next": "f14_warn"}, {"next": "f14_cancel"}]},
"f14_warn": {"popup": "append", "src": "L592", "src_pick": [{"src": "L592", "alt": "give (him/her) a stern warning"}],
             "text": "The judges give (cook1.him/her) a stern warning.", "children": [{"next": "eventually"}]},
"f14_cancel": {"popup": "append", "src": "L592", "src_pick": [{"src": "L592", "alt": "cancel the contest"}],
               "text": "The judges cancel the contest.", "children": [{"next": "lead8"}]}
```

- Graphs have no cycles. "Return to A or B" after a tie-breaker is a second copy of the B page whose choices leave out
  the tie-breaker (The Cooking Contest `end_b2`, `one_again`).
- A bank of sentence fragments with no lead-in may reuse a lead-in phrase of the same event (`"Eventually, the
  judges..."`, L425), tagged with its own `src`. Say so in your report.
- A bank used in more than one place is one branch node (or pool) with its `set`; later uses point at the same node.

## 12. Choices

- Labels drop their structural prefix and keep the owner's words and case (`"FOLLOW THE ESTABLISHED RULE"`). A label
  may overflow its button (Q16).
- 5-7 choices go on one page (Q12). A choice limited to some games gets `"if": {"game": [3, 4, 5]}` (Between Life and
  Death B and C). At least two choices remain in every game.
- With 4 or more buttons, put the event's long text on a popup before the question and keep the question page short.
- No-choice events and contests are one page with an OK button (Q15).

## 13. Grammar fixes

Only a fix listed in [grammar-fixes.md](grammar-fixes.md) may be used, exactly as listed:

```json
"grammar_fixes": [{"src": "L819", "before": "There's a lot of things", "after": "There are a lot of things"}]
```

`before` is the exact text on that one line (after typography); `after` replaces every occurrence on the line. A fix may
turn a bare `his/her` into the placeholder `(his/her)`. To propose a new fix, add a row to the doc's table (glaring
mistakes only, never style) and say so in your report: the owner approves the list.

## 14. Codas, series and shared pools

- **Codas** (Q13): the V8 C1-C16, V9 R1-R26 and V10 O1-O30 banks are shared pools in
  `data/event_collection/shared_pools.json`, each item with its own `src`. An event of the same section ends with an
  optional coda 50% of the time: a branch with two equal children, a page that appends `{C}` (or `{R}`, `{O}`) and
  an empty end branch, after the event's last page:

```json
"include_pools": ["v8_codas"],
"coda": {"type": "branch", "children": [{"next": "coda_text"}, {"next": "no_coda"}]},
"coda_text": {"popup": "append", "join": "paragraph", "text": "{v8_codas}"},
"no_coda": {"type": "branch"}
```

  A coda item that only fits some events gets an `if` (for example `{"visited": "death"}`).
- **V26 materials** become the shared pool used where events say "material".
- **Series** (Q7): V14 Golden Child scenes, V17 contests, V18 trials and V20 crises. `--format` copies
  `collection.series` from the manifest; within a series every member keeps `draw_weight` 1.

## 15. VV5 "Isolans"

The source calls the non-believer community "Heathens" in its oldest text and "Isolans" from the Guardians of Harmony
naming on (L4505-4507: "call the formerly named Heathens ISOLANS throughout in-world narrative"). Write the word each
line uses, exactly; never rename one to the other (that is the owner's call, Q14). Isolans and Heathens are never cast:
an Isolan character is text only (or a `stranger` role when a pronoun is needed). The universal events' adjective
"Isolan" ("The Grand Isolan Scholasticon", "the Isolan Decathlon") also stays as written.

## 16. Characters and fit

- A v6 text holds letters, digits, space and `. , ! ? : - ' " ; / & %`, plus `\(` `\)` for literal parentheses.
  A New Home and The Lost Children show `; ( ) & %` through the engine's fallback when the Unicode Text companion is
  missing (Q10): write the real character.
- Titles: the CIE title set (no `"`), at most 30 characters in VV3-VV5 ("Between Life and Death", "The Meaning of
  Faith").
- Every popup must fit with and without Scrolling Popups. A sentence taller than a page is an error; split the page
  at a paragraph or put the text on a popup of its own.

## 17. Known format gaps (as of the pilot)

Write around these as described, list each use in your report, and never invent a mechanism:

| Id | Gap | Write-around |
|---|---|---|
| G1 | An answer's first page shares the question popup, which keeps the room of 5-7 buttons; without Scrolling Popups an outcome sentence does not fit (VV1-VV5, 7 buttons; VV1, 5) | None in content; pinned in `tests/test_event_collection_files.py` `KNOWN_GAPS` |
| G2 | No "the other member" of an alias | Fixed roles and both-winner pages (section 10) |
| G3 | Pool items cannot follow the role of the instance that uses them | `mirror_of` pools |
| G4 | A one-option inline pick `{x}` is refused; nested inline picks are refused; a game word inside an inline pick is refused | `src_pick` literal text; named pools |
| G5 | No token for the village's / tribe's name ("traditional (tribe name)") | Ledger `gap` entry with its `set` |
| G6 | Titles cannot hold `"` | Drop the quotes ("The Meaning of Faith") |
| G7 | A role must be a villager first; an event with only text figures needs one cast villager | Cast the figure the text names, harmless |
| G8 | A stranger's sex is random; the VV3 Chief named in text is not the real Chief's sex | `stranger` role for the Chief's pronouns |
| G9 | Damage has no size words; "collapses" is a choice | 50..100 percent |

## 18. A complete small example

The Gardening Contest is `data/event_collection/v6/vv3_gardening_contest.json` (design A6). The other pilots show the
remaining features:

| File | Shows |
|---|---|
| `original/vv2_cooking_contest.json` | 26 banks generated from the source, `mirror_of`, `src_pick` routing, `(award)`, skill `set` 100, dislikes, `gap` |
| `original/vv1_child_of_legend.json` | A Golden Child special role, effects on bank items (branch nodes), grammar fixes with placeholders |
| `original/vv5_meaning_of_faith.json` | Six buttons, a rare route, pool items with `visited` conditions, a game word in a VV5-only event |
| `universal/all_doctors_dilemma.json` | All five games, `{@chief}`, strangers for text figures, kill, celebrate, a reward branch |
| `v20/all_v20_between_life_and_death.json` | Seven buttons with choice `if`, an exceptionally rare outcome, many text-only reasons |
| `v22/all_v22_4_parents_lesson.json` | Seven buttons, Parenting by size, conditional gains, a small skill loss (harm-capable) |
| `v14/vv1_v14_01_the_impossible_equation.json` | A one-page Golden Child scene in a series |
| `v17/vv1_v17_research.json` | A no-choice contest with the festival's shared setting paragraph |
| `v9/vv4_rotten_structure.json` | Structure damage, banks as pools appended to a lead page |
