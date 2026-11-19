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

The source is the frozen copy `docs/more-island-events/Isola_Grand_Event_Collection_V28_Consequences_Claude_Retrofit.txt`
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
| child, pool item | `rarity` | `occasional`, `rare`, `very_rare` or `exceptionally_rare` (section 8) |

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
| `(role)`, `(Role)`, `(role.he/she)`, `(role.His/Her)` ... | any one source parenthesis group; a pronoun or role-sex word also either of its own words written bare (the owner, 2026-11-16: the Golden Child's and a carrier's words follow the villager) | `(Healer1)` for `(Healer1)`; `(patient)` for `(patient name)`; `(cook1)` for `(name1 or name2)`; `(child.he/she)` for `he` |
| `{P}`, `{P.2}` (pool) | one source parenthesis group, or the pool's own items as the source's bare `a/b/c` list | `{A.2}` for `(A, different)`; `{ING}` for `fish/mushrooms/.../a magical potion` |
| `{a\|b\|c}` (inline pick) | the source list `(a/b/c)` or bare `a/b/c`, item for item | `{relieved\|frustrated\|anxious}` |
| `{@chief}` (game word) | one of the word's values, or `Chief` / `the Chief` / `a Chief` / `Chiefs` | `{@Chief} refuses` for `The Chief refuses` |
| `\(` `\)` | a literal parenthesis | `\(Required ingredient: {ING}.\)` |

6. The first letter of a text may change case (a list item that starts a sentence).

The title may change only in case (`THE GARDENING CONTEST` becomes `The Gardening Contest`) and drop a heading's prefix
(`EVENT:`, `V13-C — UNIVERSAL:`, `01.`). It must fit 30 characters in VV3-VV5 and may not hold `"` (section 16).
An owner's rename ([owner-title-changes.md](owner-title-changes.md)) replaces the heading's title exactly as the owner
wrote it; the check then requires that new title.

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
  **In-text subroute headings are never shown** (the owner, 2026-11-14: "events should have a single event title. no
  need for subroute headings"): a paragraph-leading heading such as `ROUND ONE — THE IMPOSSIBLE INGREDIENT:` or
  `A1 — THE THUNDERCLAP:` is taken out of the page with a `structural` ledger entry -- the whole line when the heading
  stands on its own line, or a `text` cut when it leads a line of story -- and the node's `src` starts after it.
  No new fidelity rule is needed: the ledger's structural cut is the marker. Each removal is listed in
  [retrofit-log.md](retrofit-log.md).
  A shared pool item (its item is matched inside its own lines) simply drops the heading, with no ledger entry.
  A **speaker label** is not a route heading and stays (the owner, 2026-11-14): The Crafty Inspector's
  `MASTER STONEWRIGHT (NAME3):` names who is speaking, so it ships with the critic's name.
- `note`: designer notes and rules never shown (`(deliberately unsuitable container)`, "IMPLEMENTATION NOTES").
- `instruction`: a mechanical instruction (`(earn tech points)`, `Parenting skill: SIGNIFICANT GAIN`); the matching
  effect or `text_only` entry carries the same line in its `src`.
- `bank_ref`: a line that only names another bank ("use the coda bank").
- `gap`: a bank item the format cannot express yet. Give its `set` so the bank size still matches. List every gap in
  your report.
- `sensitivity`: the owner's content rules (2026-11-14: no unfortunate implications; bad things implied, never
  explicit; modern-day things in the words of people who never saw them; outsiders and found-object origins only
  speculated; past harm never shown as inflicted on purpose; nobody stigmatized). Where the owner's text breaks one,
  change the smallest piece: `{"src": "L8862", "kind": "sensitivity", "before": "an aquarium", "after": "a clear-walled
  rectangular container", "why": "rule 3 ..."}`. `before` must be on that one line; `after` replaces it in every text and in the title
  (like a grammar fix), and the line must still be consumed. `--report` lists every edit; each is for the owner's
  review.
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
| random (valid) like / dislike, a new preference | `{"do": "preference", "role": r, "like": "random"}` / `"dislike": "random"` (cie-v6-binary.md 24: one the villager does not hold, never both a like and a dislike) |
| injured, lose health, health | `{"do": "health_change", "role": r, "min": ..., "max": ...}` |
| collapses (a structure) | `{"do": "damage", "structures": "any", "min": 50, "max": 100}` |
| looks different, new hair, appearance | `{"do": "appearance", "role": r, "head": "random"}` (and/or `"body"`) |
| dies, body never found / not recovered | `{"do": "die_unrecovered", "role": r, "cause": "unknown"}` (no grave; logged as a death; always "Unknown causes", no other cause allowed) |
| loses the baby (a nursing parent) | `{"do": "baby_lost", "role": r}` on a `"special": "nursing_parent"` role with `"protected": "allow"` |
| the child survives but the mother dies | `{"do": "birth_then_die", "role": r, "cause": "unknown"}` on a `"special": "nursing_parent"` role with `"protected": "allow"` (cie-v6-binary.md 23: the baby is born now, then the parent dies with a grave) |
| looks older, the old head look | `{"do": "old_look", "role": r}` (cie-v6-binary.md 27) |
| a gender transition that changes the villager's recorded sex (explicitly chosen) | `{"do": "sex_change", "role": r}` (cie-v6-binary.md 29: refused while carrying or nursing, for special villagers, and while a companion that keeps data by the sex is in the game; the text still shows) |
| a chosen name, "asks to be called ..." | a new-name role, `{"kind": "stranger", "new_name_for": r, "sex": "same" \| "other" \| "random", "last_name": "same" \| "different" \| "random"}`, shown as `(Chosen)` (cie-v6-binary.md 28: nobody is renamed) |

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
- **Outcomes written only as instructions** ("change hair color", "random like", "skill loss"): cut the instruction,
  make the effect, and put `"auto_text": true` on that popup node (cie-v6-binary.md 25). The popup then says what
  happened in short plain lines after the text, e.g. "Ana's hair changes color.", "Ana now likes herbs.", "Ana feels
  less sure of her Farming." Never write those sentences yourself: the engine makes them from the effects.

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
| occasional, a minor setback (the V27 global rule's "minor setback/occasional"; the V28 consequence rules' "occasional"; living volumes) | 10 | `occasional` |
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
- **A chosen name** (REL events): never rename the villager. Give the event a new-name role (cie-v6-binary.md 28)
  for the villager role and name it in the text: `"chosen": {"kind": "stranger", "new_name_for": "subject",
  "sex": "other", "last_name": "same"}`, then `(Name) asks to be called (Chosen).` The name is drawn once and is the
  same on every page. Its pronouns follow the name's sex; the villager's own pronouns stay the sex they were cast
  with for the whole event (pages are laid out before a `sex_change` is made), so write names, not pronouns, after
  a change. A body-sprite change for presentation is NOT `sex_change` (that effect is not built: owner question).
- **Special villagers** (Q17): the Golden Child (`"special": "golden_child"`, `"min_age": 0`), the VV3 Chief, a named
  nursing parent. Casting one with no token in the text is allowed (the cast is the requirement). Unnamed mentions
  ("A nursing mother nearby") stay text.
- **The Golden Child** (the owner, 2026-11-16): an event that needs him or has him act, speak or be affected is A
  New Home only and casts the real one (`"special": "golden_child"`); his words are the role's placeholders
  (`(child.he/she)`, `(child.boy/girl)`: he may be born a girl, section 4's bare-word rule keeps the source). A line
  where he acts in an all-games event shows only in A New Home and only while he is there (`special_present`, or an
  optional `golden_child` role when the line names him). A passing mention may stay in any game.
- **A carrier** (the owner, 2026-11-16): a `nursing_parent` role takes no `sex` (only villagers born female are cast
  as carriers) and its words are the role's placeholders (`(mother.mother/father)`, `(mother.he/she)`): they follow
  the villager's Gender Presentation, else the sex the game records (`collection_lib.carrier_words`).
- **A chief role** (the owner, 2026-11-16): chief events run in every game; the chief's role has
  `"prefer": "tribal_chief"` (The Secret City's robed Tribal Chief is cast when there, else any fitting villager;
  cie-v6-binary.md 35).
- **Protection** (the owner, 2026-11-14, V28; cie-v6-binary.md 7): `protected: "auto"` (the default) keeps nursing
  parents, the Golden Child and the VV3 Chief out of any role a harmful effect can reach. Only The Lost Children's
  totems are ALWAYS protected: where harming one of the others makes sense in the event (a nursing mother who loses
  her baby, the Chief hurt in a storm), write `"protected": "allow"` on that role -- a harmed `special` role needs
  it. Use judgement; ask the owner on doubtful cases. Every `allow` on a harmed role is listed by
  `python scripts/collection_check.py --allow-report` for the owner's review. VV5 roles are believers only (the
  default), and New Believers' story villagers stay out of harm whatever `protected` says.
- **Kinship** (cie-v6-binary.md 21): `"relation": {"spouse_of" | "parent_of" | "child_of" | "sibling_of" |
  "grandparent_of" | "grandchild_of" | "aunt_or_uncle_of" | "cousin_of": role}` when the text needs the two
  villagers to be family ("(Parent) watches (his/her) son (Child)"). The other role must be a villager the event
  needs. A New Home knows parents only with the parentage log patch; no game keeps a spouse (the engine takes
  co-parents); the wider four need the villager between them alive; so a kinship event may be drawn rarely.
- **A bereaved villager** (cie-v6-binary.md 21a): a text that says a villager lost someone ("still misses (his/her)
  mother") goes in a variant (or a way on) with `{"if": {"has_dead_relative": r}}`, and the plain text stays the
  usual one. It holds for a lost parent or co-parent only (a dead child or sibling is on no record).
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
- **The chief's title is drawn per run** (the owner, 2026-11-16; cie-v6-binary.md 35): a chief word (`chief`,
  `Chief`, `a_chief`, `tribal_chief` ...) shows one of "Chief", "leader", "elder", "headman" / "headwoman" (a
  cast chief's presentation) or "council head" in every game, the same on every page of the run and after a
  resume; the real Tribal Chief cast in the event's chief role is always the word's VV3 text. Write the words as
  before: the compiler adds the other titles. Titles keep their `title_variants`.

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
- The game shows every new event's labels in title case (the owner, 2026-11-15; never a stock event's):
  `collection_lib.title_case_graph_labels`, applied as each event is compiled (`collection_check.graph_for_engine`,
  the Living mixer's variants). A label all in capitals is lowered first ("Follow the Established Rule"); small words
  stay lower case unless first or last; a pronoun placeholder takes its capital form (`(friend.He/She)`), a name in
  capitals its capital one (`(Name1)`); a game word whose words change gets a word of its own (`{@chief_tc}`). The file
  keeps the owner's words as written; a `label_case: "title"` file is written in title case already. A file with
  `label_case: "source"` keeps the owner's case: only `lvmed22_dream_kidney`, whose "Seek the donor's prior consent
  and study anatomy without operating." would run 3 pixels off A New Home's and The Lost Children's screens in title
  case.
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
- **V26 materials**: gone. The owner's V28 source (2026-11-14) removed the V26 section, and with it the v26_*
  shared pools; no event used them.
- **Series** (Q7): V14 Golden Child scenes, V17 contests, V18 trials and V20 crises. `--format` copies
  `collection.series` from the manifest; within a series every member keeps `draw_weight` 1.

## 15. VV5 "Isolans"

The source calls the non-believer community "Heathens" in its oldest text and "Isolans" from the Guardians of Harmony
naming on (L4505-4507: "call the formerly named Heathens ISOLANS throughout in-world narrative"). Write the word each
line uses, exactly; never rename one to the other (that is the owner's call, Q14). Isolans and Heathens are never cast:
an Isolan character is text only (or a `stranger` role when a pronoun is needed). The universal events' adjective
"Isolan" ("The Grand Isolan Decathlon", "the Isolan Decathlon") also stays as written.

**With Guardians of Isola Rewrite** (the owner, 2026-11-14) New Believers says neither "Heathen" nor "convert": every
text an event can show there with one of those words (title, page, variant, label, list item, description) gets a
form with `{"patch": "guardians_of_isola"}` -- a `title_variants` entry, the node's FIRST variant, or a
`description_variants` entry -- that is the text with the event's pairs of [guardians-wording.md](guardians-wording.md)
made (check j). Add the pair to that table first; the owner reads it. A choice label cannot have a variant: write
it twice, the source's label with `"if": {"not": {"patch": "guardians_of_isola"}}` and its Guardians form (same
`next`, same `src`) with `"if": {"patch": "guardians_of_isola"}`; the pair counts as one button (LV-B's PEOPLES-08).

## 15b. The third source: the Living Event Engine's fixed event volumes

The owner's all-in-one Living Event Engine file
(`docs/more-island-events/Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt`, byte for byte, SHA-256 in
`data/event_collection/LIVING.sha256`) holds fixed event volumes (MED-, LIFE-, CIRCLE-, PEOPLES-, ...) that ship as
collection events. Files: `data/event_collection/living/<section>/<id>.json`, `collection.source` `"living"`; every
`src` means a line of that file. `scripts/collection_manifest.py` `LIVING_VOLUMES` lists the volumes (rows, notes,
credits); the manifest's `living` block checks coverage inside them only (the rest of the file is the Living Event
bank's). Generators: `scripts/living_vols/gen_<chunk>.py` on `living_common.py`, which documents the event shape
(the setup is the question; each choice has its own two weighted outcomes), the weights and the effects. Grammar
fixes for this source are rows `| living L<line> |` in grammar-fixes.md. A label too wide for a game's screen shows
its first words on the button, and its whole sentence opens each of its outcome pages (`living_common.build`).
Four-choice volumes (A-D: WAYS-, AUTH-) are `LIVING_CHOICES`; a heading's "(VV5 ONLY)" tag is the row's games, and a
setup's "VV5 ONLY:" tag is a structural ledger cut. The source's lower-case "chief" is `{@chief}` with
`{"3": "chief", "*": "leader"}` (the check's Chief rule accepts "chief" as well as "Chief").

## 15c. The fourth and fifth sources: Beyond the Horizon, Role Models and Good Examples

Two owner files of 2026-11-15, each its own frozen source (byte for byte, SHA-256 in `data/event_collection/
HORIZON.sha256` / `ROLEMODELS.sha256`, `-text` in .gitattributes): "Isola - Beyond the Horizon"
(`docs/more-island-events/Isola_Beyond_the_Horizon_Expanded_80_Events.txt`, `collection.source` `"horizon"`, files
in `data/event_collection/horizon/hz_world|hz_vol2/`) and "Role Models and Good Examples"
(`docs/more-island-events/Role_Models_and_Good_Examples_40_Events.txt`, the owner's CRLF ends kept, `"rolemodels"`,
files in `data/event_collection/rolemodels/rm/`). Rows: `_horizon_rows` / `_rolemodel_rows` in
`scripts/collection_manifest.py` (the manifest's `horizon` and `rolemodels` blocks check every line of each file).
Generators: `scripts/horizon_rm/gen_hz.py`, `gen_rm.py` on `hzrm_common.py` (living_common's roles, effects and
weights), which documents the shape: the setup is the question, each choice has its own two equally likely
alternative outcomes. Beyond the Horizon's PARTs I-V are one series each and its Expansion Volume II is one more;
its "Content note:" / "VV3:" lines are ledger notes. A Role Models event is ONE source line: every page's `src` is
that line (the fidelity check finds each page's text inside it), the heading "EVENT RM-nn - TITLE SETUP:" is a
structural cut, and a node whose line carries an effect-table word from another page has a text_only entry saying
so. Grammar fixes would be rows `| horizon L<line> |` / `| rolemodels L<line> |` in grammar-fixes.md (none yet).
Titles and choice labels are title case (the owner, 2026-11-15: titles and choice options are always title case,
small words lower case unless first or last). Titles use the pipeline's `title_case`; these two sources' files set
`collection.label_case: "title"`, so each label is `collection_lib.title_case_label` of the owner's words (the
fidelity check matches the label case-blind, then requires exactly that form). The older sources' labels switch after
the merge.

## 15d. The owner-approved drafts, set A (2026-11-15)

Twelve draft files the owner approved ("the drafts are ok as long as they stick to our rules"): Inner Life I-X
(events 1-200), What's That Doing Here (WD-01..50) and Luck, Omens and Lavastones (LO-01..50). Each is its own frozen
source, byte for byte under its own name in `docs/more-island-events/` (`-text`; SHA-256 in
`data/event_collection/drafts_a/DA_<ID>.sha256`), listed in `collection_lib.DRAFTS_A`: source, section and series
`da_il01` .. `da_il10`, `da_wd`, `da_lo`; files `data/event_collection/drafts_a/<source>/<id>.json`; ids `il001_`,
`wd01_`, `lo01_` and a slug. Rows: `_draft_rows` in `scripts/collection_manifest.py` (the manifest's `drafts_a` block
checks every line of each file): each heading is an event, the lines before the first heading (the title, the notes
to the owner, Part II's ChatGPT preamble) and the closing NOTES FOR THE OWNER are notes rows. One series per file, so
each file counts as one draw in the rare roll.

Generators: `scripts/drafts_a/gen_<id>.py` on `da_common.py`, which documents the shape (the casting line is a ledger
note; the setup is the question; each label leads to its own answer page; a single popup has no choice; LO's
"(About 6 in 10)" lines are alternatives weighted by the text's own odds, each child naming them in the
authoring-only key `odds`, which the CHANCES check accepts in place of a rarity; "[effect: ...]" is an instruction
cut with its effect on that page). (name1) is the role `subject` and (name2) `friend`; pronouns follow the name
mentioned last, with per-page overrides; labels are title case (`label_case: "title"`; the check compares a label's
words around its placeholders). The owner's naming rule (2026-11-15): a person the draft names only by role ("a
visitor") is cast and named at the first mention, a ledger entry of kind `casting` (checked like a sensitivity
edit). The text is otherwise kept as written: no swaps for animals or objects a game lacks (narrative is not
gameplay); near-duplicates the notes flag are built and listed. Grammar fixes are rows `| da_il07 L<line> |`
(`(his/hers)` has no placeholder). "The Quiet Hands" (Inner Life 3): TODO story trait "mute", pending the engine.

## 15e. The approved draft event files, group B

Eight owner-approved draft files of 2026-11-15 ("the drafts are ok as long as they stick to our rules"): "New Events -
Humor and Absurdity", "Tall Tales and Self-Interest", "Honesty and Accountability", "Justice and Consequences",
"Departures and Exile", "Dreams and Ambitions", "Fears and Doubts" and "Good, Bad and Ordinary Days" (draft for
owner).txt in `docs/more-island-events/`, each its own frozen source (byte for byte, `-text`, SHA-256 in
`data/event_collection/DRAFT_<X>.sha256`; `collection_lib.DRAFTS_B` lists them: source ids `draft_hum`, `draft_tt`,
`draft_hon`, `draft_jus`, `draft_dep`, `draft_drm`, `draft_fea`, `draft_day`). Files:
`data/event_collection/drafts_b/dr_<x>/<id>.json`. Rows: `_drafts_b_rows` in `scripts/collection_manifest.py` (lines 1-5
and the closing NOTES block are notes rows; one series per file). Generator: `scripts/drafts_b/gen_drafts_b.py` on
`drafts_b_parse.py`, reading the per-event annotations in `scripts/drafts_b/annotations/<x>.txt` (whose each pronoun
is, the roles' ages, the role figures, the Pick Island Event sentence, the 15-point review).

- The setup is the question page; each label leads to its own one outcome (no odds in the drafts). A few events are
  one popup with no choice. The casting line is a ledger note carried out as the roles' ages; `(name1)` / `(name2)`
  are the roles `subject` / `friend`. An `[effect: ...]` is an instruction cut from its outcome and made as its effect.
- The owner (2026-11-15): "use names and pronouns where possible instead of vague 'a fisher', 'a healer', 'an elder'":
  a single person of the village called only by a role word is a cast villager of its own (harmless, cast only) and
  its mentions show the name, each change a `sensitivity` ledger entry (before -> after) listed by `--report`.
- Grammar fixes are rows `| draft_<x> L<line> |` in grammar-fixes.md (the nine `(his/hers)`: the format has no such
  placeholder).

## 15f. The approved draft event files, group C

Eight more owner-approved draft files of 2026-11-15, wired exactly as group B (15e): "New Events - Healing, Psychology
and Medicine", "Advice and Decisions", "Relationships, Singlehood and Family", "Belief and Identity", "Nature, Ecology
and Animals", "Disability and Diversity", "History and Collective Memory" and "Pondering How Life Has Gone" (draft for
owner).txt, `collection_lib.DRAFTS_C` (source ids `draft_hea`, `draft_adv`, `draft_fam2`, `draft_blf`, `draft_nat`,
`draft_div`, `draft_his`, `draft_lif`; four of the files keep the owner's CRLF line ends). Files:
`data/event_collection/drafts_c/dr_<x>/<id>.json`; rows `_drafts_c_rows`; generator
`scripts/drafts_c/gen_drafts_c.py` on `drafts_c_parse.py` and `scripts/drafts_c/annotations/<x>.txt`. Differences:

- `(name3)` / `(name4)` are the roles `third` / `fourth`; HEA-15 offers three choices.
- Pronoun owners: `drafts_c_parse.guess` (the last name before the pronoun; for a `(him/her)` whose nearest name is in
  its own sentence, the last other name), with the annotation's `FIX` lines where a reading found it wrong.
  `python scripts/drafts_c/drafts_c_parse.py HEA [HEA-01 ...]` prints the review sheet.
- "(where the game records it)": the annotation's `REL` line makes the cie-v6-binary.md 21 relation (partners are
  `spouse_of`, the games' co-parents; a "relative" is a recorded parent). The text never changes. The engine has no
  "prefer" relation, so the rare roll and Pick Island Event draw such an event only where the relation holds; bought
  through the library, the relation is dropped when nobody meets it and any fitting villager is cast. Where no game
  records the relation (a dead partner, a new partner's child, who shares a hut, same-sex partners), no relation is
  cast and the casting is the ages alone.
- A heading's "(VV5 only)" (BLF-26, BLF-27) makes the row New Believers only and is cut from the title; their Isolan is
  a named stranger (15). Neither says Heathen or convert, so no Guardians of Isola variant is needed.
- FAM2-40's carrying or nursing parent is the game's nursing parent (`"special": "nursing_parent"`); FAM2-11/28's teens
  are at most two years apart (`max_age_gap`).
- BLF-36's same-sex couple follows the owner's rule (cast by sex, the relationship as story text):
  `gen_drafts_c.same_sex_variants` (annotation `WORD: same_sex`) makes two men (`men1`, `men2`, needed) and two women
  (`women1`, `women2`, optional) and starts with a branch of two equal children, each to its own copy of the pages
  (same `src`); the women's child is taken only when both women are cast. The checker needs a page for every cast,
  so one pair must be needed: where both pairs can be cast the two versions are equally likely.

## 15g. The approved files, group D

Eight more owner-approved files of 2026-11-15, each frozen byte for byte as its own source
(`collection_lib.DRAFTS_D`, SHA-256 in `data/event_collection/<ID>.sha256`, `-text` in .gitattributes) and each one
series (its section), so a file counts as one draw in the rare roll. Files:
`data/event_collection/drafts_d/dr_<x>/<id>.json`; rows `_drafts_d_rows`; generator `scripts/drafts_d/gen_drafts_d.py`
on `scripts/drafts_d/annotations/<source id>.txt` (`--sheet <source id>` prints the review sheet).

| Source id | File | Events | Shape |
|---|---|---|---|
| `draft_rm2` | New Events - Role Models RM-41 to RM-90 (draft for owner).txt | 50 | setup, A-D, two outcomes each |
| `draft_hz2` | New Events - Beyond the Horizon 081 to 130 (draft for owner).txt | 50 | setup, A-C, two outcomes each |
| `fathers30` | Isola_30_Fathers_Pregnancy_Parenthood_and_Humanity_Events.txt | 30 | setup, A-D, "Outcome 1/2:" |
| `moments500` | Isola_500_Tiny_Island_Moments.txt | 125 | moment: one opening, four endings |
| `draft_tim2` | New Events - Tiny Island Moments T126 to T175 (draft for owner).txt | 50 | moment: "Opening:", "Ending 1-4:" |
| `openq97` | Completed Open Questions - Isola Events v1.35.97.txt | 35 | M01-M35: opening + follow-up, one popup |
| `armor45` | Isola_Armor_Weapons_and_Inherited_Traditions.txt | 45 | "NN. Title - sentences", one popup |
| `draft_arm2` | New Events - Armor and Heirlooms ARM-46 to ARM-95 (draft for owner).txt | 50 | as armor45 |

- A choice event: the setup is the question page (labels in title case); each label leads to a branch of its two
  outcomes, equally likely (no outcome harms anyone).
- A moment (the owner's Question 1, answer A): a branch of equally likely pages, each the opening and one ending (src
  the opening's and the ending's lines). The 500 file's four entries of one opening are one row; the owner's titles
  T001-T125 (Question 2, answer A) are owner-title-changes.md rows over the first entry's "Title:" line; the other
  entries' "[Mnnn]" and "Title:" lines are structural ledger entries.
- The armor files' events are one line each, one after another: their rows carry `one_line` (no blank-line boundary
  check). Their "LIVING EVENT ENGINE - FLAVOR TEXT" blocks are notes rows (mixer seed: pending; the 35 lines of the
  first are built as M01-M35 from the Completed Open Questions file, the owner's titles and follow-ups).
- Names (the owner, 2026-11-15: "use names and pronouns instead of vague roles"): the person the event is about,
  named by a role word in the setup / opening / sentence, is the cast villager shown by name, the role word kept as
  flavor ("(Name1), an elder, ..."; a bare "a villager" or "Someone" becomes the name); one `sensitivity` ledger entry
  per changed line. The other people keep the source's words. An event about a group casts one villager it does not
  show.
- Fathers 01-08: the carrier is a trans man. This base has no birth-sex condition, so 01-04 and 08 (pregnant)
  cast a male `nursing_parent`, and 05-07 (after the birth) a man who is a recorded parent (`parent_of`) of a
  cast-only child aged 0-3 (05, 06) or 0-7 (07); each ledger has the TODO "birth-sex check pending engine
  (feat/97-presentation)".
- No effects: none of these files marks one; every effect-table word gets a text_only reason.

## 15h. The Animals anthology's newest volumes

The owner's all-in-one file of 2026-11-15, "Isola_ALL_IN_ONE_Animals_Reptiles_Fur_Feathers_Scales_Claws_Hooves_COMPLETE
.txt", frozen byte for byte (`collection_lib.ANTHOLOGY`, source id `anthology`, SHA-256 in `ANTHOLOGY.sha256`), is the
Living Event Engine file with the GLOBAL EDITORIAL OVERRIDE in front and new volumes after it. Only its newest volumes
are rows (`collection_manifest.ANTHOLOGY_VOLUMES`, `_anthology_rows`; "uncovered" is checked inside them): MOM-01..08,
REL-01..36, CHILD-01..47, FAM-01..24, JOY-01..38, EVENT-HS-001..042, EVENT-AGE-001..036, EVENT-JUSTICE-001..032,
EVENT-EXPRESSION-001..074, EVENT-FAUNA-001..024, 361 events, each volume one series (section `an_<x>`) with its
contract block a notes row. Files: `data/event_collection/anthology/an_<x>/<id>.json`; generator
`scripts/anthology_new/gen_anthology.py` on `scripts/anthology_new/annotations/an_<x>.txt` (`--sheet an_<x>` prints the
review sheet). The shape is 15b's (the setup asks; each label leads to its own two equally likely outcomes) with two
(MOM) or four choices, no CALLBACKS line, and an optional `ELIGIBILITY:` line: the casting, a ledger note.

- Text verbatim (minimal editing; no swaps or rule-driven rewording). Names instead of vague roles: a person the text
  names by a role word is a cast villager shown by name -- "the villager", "a friend" become the name, and a job or a
  description met with "a"/"an" keeps its words after the name ("Kai, a researcher, explains"); "Two elders ..." become
  "Ana and Kai, two elders, ..."; a relative clause the name leaves dangling gets its commas. Each change is a ledger
  "sensitivity" entry. Choice labels and titles keep their words. A person the text keeps anonymous (an unsigned
  artist, a critic who will not be named, "a repeat offender") stays unnamed; group scenes cast nobody.
- Chosen names (REL-09, 10, 15, 16, 17, 19, 28, 31, 34; CHILD-21) are the new-name role (cie-v6-binary.md 28), shown
  where the text first gives the name; nobody is renamed. REL-15's gender change is `sex_change` (code 22); a change of
  look that keeps the villager's identity (REL-13, 16, 18, 20, 36) needs the cross-sex look (code 23, not built): story
  text and a ledger TODO.
- Romance: teens only with teens at most two years apart (`max_age_gap`), children's crushes the same; adult couples at
  most 15 years apart; never a minor with an adult. REL-04 and REL-26's same-sex pair (the text gives no sex) follows
  the owner's rule as BLF-36 (annotation `SAMESEX`): two men or two women, two equally likely versions of the pages,
  the women's taken only where both can be cast.
- Nursing mothers (AGE-019..024, EXPRESSION-040, JOY-01) are the game's nursing parent, female, 18+, with a ledger TODO:
  the engine reads the sex field, not a birth sex.
- Family words between cast people are recorded relations (a parent with their child, siblings, cousins, HS-007's
  grandparent).
- Effects only where an outcome's own words make one: hair dye the villager keeps is the random head look (MOM-06's
  "[hair color change]", cut as an instruction; REL-30 A1, B1, C1); REL-05 and JOY-18's couple celebrate. Injuries in a
  setup are the premise; everything else is story text (text_only with a reason).
- "The chief" stays the game word `{@chief}` / `{@Chief}` (a label in title case: collection_check compares a game word
  as the word it stands for); a title with "Chief" has a "Leader" title variant outside VV3. Nobody is cast as the chief.

## 15i. More Island Events (mixer only) and heathen_ok roles (2026-11-16)

The owner's "Additional Virtual Villagers Events By Lorsieab2.txt" (the nine events "VVFP More Island Events.dll"
runs) is frozen byte for byte (`collection_lib.MIE`, source id `mie`, SHA-256 in `data/event_collection/MIE.sha256`);
rows `_mie_rows` in `scripts/collection_manifest.py` (the header and The Cooking Contest's draft are notes rows);
files `data/event_collection/mie/mie/<id>.json`, written by `scripts/go_events/gen_mie.py` (one hand-mapped function
per event). Each has `collection.mixer_only: true`: it compiles and validates and gets its mixer versions, but its
static form is in no manifest, the Credits list or the Game Mechanics index (the DLL runs the originals). The owner's
odds are repeated children (the engine draws children equally); what the format cannot say is listed in
`collection.approximations` (an authoring key) and printed by the generator.

**heathen_ok** (the owner: "Heathens may be involved if needed for the event to make sense"): a New Believers villager
role with `believers_only: false` must also say `"heathen_ok": true`, and a paragraph that names the role must say
Isolan or Heathen. Only faith gain (+5..+35), joining the tribe, actions and minor harm (health -5..-30, sickness)
may reach it; never kill, vanish, age, re-skill or less faith (`collection_check.heathen_ok_problems`). The engine's
role flag (a real Heathen villager, never a Heathen role character or a sick one) is pending: `graph_for_engine`
leaves the key out until it lands. In use: S027 The Isolan at the Fire and S070 The Isolan Healer.

## 15a. The Pick Island Event sentence

`collection.description` (authoring key; it ships in each game's manifest.txt) is the one sentence Pick Island Event
shows for the event: what happens and, with a question, what the choice is, in the style of More Island Events'
lines ("A villager sees dolphins playing: swim towards them, or hang back."). Sentence case, at most 130 characters,
letters, digits, space and `. , ! ? : ; ' -` only: no placeholder, brace or role id, no spoiler of a rare outcome,
the same words in every game (no "Chief" unless the event is VV3 only). Check i.

## 16. Characters and fit

- A v6 text holds letters, digits, space and `. , ! ? : - ' " ; / & %`, plus `\(` `\)` for literal parentheses.
  A New Home and The Lost Children show `; ( ) & %` through the engine's fallback when the Unicode Text companion is
  missing (Q10): write the real character.
- Titles: the CIE title set (no `"`), at most 30 characters in VV3-VV5 ("Between Life and Death", "The Meaning of
  Faith").
- The collection's rows require Scrolling Popups, so every popup is checked with scrolling on: any height fits, and a
  popup's text must still stay within the engine's byte limit. Split long pages at a paragraph or sentence, never
  inside a sentence.

## 17. Known format gaps (as of the pilot)

Write around these as described, list each use in your report, and never invent a mechanism:

| Id | Gap | Write-around |
|---|---|---|
| G1 | An answer's first page shares the question popup, which keeps the room of 5-7 buttons; without Scrolling Popups an outcome sentence does not fit (VV1-VV5, 7 buttons; VV1, 5) | Closed: the collection requires Scrolling Popups, so its popups are checked scrolling |
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
| `v20/all_v20_between_life.json` | Seven buttons with choice `if`, an exceptionally rare outcome, many text-only reasons |
| `v22/all_v22_4_parents.json` | Seven buttons, Parenting by size, conditional gains, a small skill loss (harm-capable) |
| `v14/vv1_v14_01_impossible.json` | A one-page Golden Child scene in a series |
| `v17/vv1_v17_research.json` | A no-choice contest with the festival's shared setting paragraph |
| `v9/vv4_rotten_structure.json` | Structure damage, banks as pools appended to a lead page |
