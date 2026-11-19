# Procedural island events: the data side (v1.35.97)

The contract is [procedural-pieces.md](procedural-pieces.md) (VPCB v1, the composer's roll order). This page says how
the data side fills it: what `scripts/procedural_pieces.py` splits, how it tags, how events mix with each other, what
`src/vv_procedural.py` (the Python twin) reads into each open point of the contract, and what the validator checks.
The numbers of the last run are in `procedural-pieces-report.json` next to this page.

## 1. The files

- `assets/event_collection/pieces/pieces-<group>.pcb`:
  - `x_<situation>_<n>`: the cross-event files, one main situation each (section 3), at most 8 events a file
    and up to 40 guest answers;
  - `<source>_<section>`: events with no situation tags yet (they mix only within themselves), by folder;
  - `le_<cat>`: a Living Engine category; `mc_<cat>`: an MC category.
  Every file stays well under the engine's 1 MB (a group past about 900 KB is split into numbered parts).
- `data/event_collection/procedural_situations.json`: the hand-read situation tags (section 3).
- `data/event_collection/procedural_never_with.json`: the piece pairs the validator found (section 6). The build
  reads it every time, so the bits are reproducible.
- Build: `python scripts/procedural_pieces.py build`; check: `... validate`; the owner's sample: `... sample <file>`.

## 2. What becomes a piece

**Collection events** (every `data/event_collection/<source>/**.json`, as `collection_check.graph_for_engine` gives
it to the engine; never the owner's draft text files):

- **Setup:** the start's text, and any linear intro popups before the first question, joined as the event shows them
  (a new popup or a paragraph: a blank line; an appended space join: a space). Its label is the event's title in
  title case. Slots: every needed role of the event plus any role its text names.
- **Approaches:** the question's answers (label in title case). The answer's own popup, when it has one before the
  random outcomes, is the approach's text; an answer that leads straight to one ending has no text (the ending is its
  one outcome).
- **Outcomes:** each ending (a popup and the linear popups after it, joined), with every effect of that chain. An
  ending several answers share is one piece with several links. Link weights are all 1 (the owner, 2026-11-15:
  every random outcome of a random node is equally likely). AUTO LINES (flag bit 2) when the event's node has them.
- **One game's reading:** game words (`{@chief}`), game-only text variants and game-only conditions are read per
  game; games that read an event the same share one set of pieces (`_g<mask>` ids only when they differ). Guardians
  of Isola's patch variants are left to the base text (the patch-off wording).
- Content filters and notes: the source's tag table (`data/event_collection/content_tags/<source>.json`, else
  `vv_event_content.tag_graph`), over the nodes the piece covers. Speaking roles from the same table.
- Mood: serious when the event can touch a serious filter (F01-F06, F08-F12, F14, F15, F18, F19, F21, F22); else
  social with two or more villager roles; else warm.

**Not split** (they stay static events, unchanged): events with no question (random outcomes only: nothing to
answer), a second question, an outcome that branches again, effects before the question or on an answer's own
popup, pools or inline picks (no pools in pieces), alias roles, nursing-parent roles (no slot special for them), no
needed villager or stranger, `else` edges and conditions other than games. The report lists each reason with its
count.

**Living Engine** (`data/living_events/bank.json`, one file per category):

- Setups: the category's seeds (the seed sentence; the chief's words per game). Slots `first` / `second`: the
  loosest bounds of every role the seed allows there (adult-only seeds 18+).
- Approaches (family 1): the bank's 34 approaches and the category's choice set, as the living mixer labels them;
  the secret-keeping choice declares both villagers 18+ (S7).
- Outcomes: the 38 archetypes with their effects (as `archetype_effects`), linked to every approach (the owner,
  2026-11-15: keep everything), weighted by group (good 20, mixed 10, bad 10, rare 2, divided over the group's
  size). Slot ages carry the bank's role rules (`role_allows_archetype`) and `needs_elder` (55+).
- Frames: `(first), a <role>, and (second), a <role>, disagree about what should happen next. Their status alone
  does not settle the matter.` -- the living mixer's own frame, for every role pair it casts for the category's seeds
  (the MIX personalities where the MIX has them). Slots from the roles (skill requirements are not slots).
- The mixer's rules become forbidden pairs: seed x approach (`approach_allowed`: the compat table, S7, S17; the
  choice set's own list), seed x archetype (`seed_allows`), seed x frame (`possible_pair`, the compat table's
  personalities), frame x archetype (`role_allows_archetype`, `needs_elder`), frame x secret choice (S7).

**MC situations** (one file per MC category): the situation (setup), its four approaches and their two outcomes
each, as the living mixer composes them; the category's filters on every piece.

## 3. Cross-event mixing: the situation tags

The owner: "everything can be mixed with anything", where it makes sense; then (2026-11-16) "tag by situation". Every
split collection event was READ by hand (by reader agents, 25 batches of 100 events, one careful pass each) and
tagged from a fixed vocabulary. The tags live in `data/event_collection/procedural_situations.json`, one entry per
event, for review and editing; the build reads them every time.

**The vocabulary** (the file's `vocabulary`):

- *Situations* (what a setup poses; what an answer can respond to): newcomer, sickness, food_shortage, lost_object,
  quarrel, strange_sign, celebration, child_problem, elder_wish, craft_problem, sea_danger, danger, grief, fear,
  new_idea, animal, weather, personal_change, feelings, leadership, tradition, kindness, contest, farming, art_story,
  secret, mistake.
- *Needs* (what must already be in the scene): healer, child, elder, food, sea, animal, visitor, tools, plant, fire,
  music, chief, group.
- *Tone*: gentle, practical, bold, funny, solemn.

**What each piece got:**

- a setup: the 1-3 situations it poses (the first is its main one), the needs its scene has, its tone;
- an answer: the situations it can sensibly answer, its needs, its tone, and MOVES (y/n): whether the button makes
  sense on its own under any setup with those situations ("Ask an Elder for Advice", "Comfort the Child", "Share
  the Remaining Food"); never for romance, punishment, deciding over someone's body or life, or a button that points
  at a thing of its own scene ("Inspect the Rope", "Keep the New Color");
- an outcome: its needs and MOVES: whether it reads naturally after its answer under any such setup ("The child
  calms down and falls asleep."), not when it continues its own scene's story or names its own things.

Only the answers and outcomes that could move at all were put to the readers (short outcomes with no dialogue, no
unprefixed placeholder, no romance): every setup (2,428), 4,646 answers and 9,078 outcomes.

**How the files use them:**

- A tagged event goes to the files of its setup's main situation, `x_<situation>_<n>` (at most 8 events a file), where
  every setup and approach is family 1.
- An answer MOVES with its moving outcomes. In its own file it may serve any other setup of that file when the
  file's situation is one of its situations. Up to 40 answers of OTHER events that suit the file's situation come in
  as GUESTS (copied into the file with their moving outcomes, `g<n>_<id>`; each file of a situation takes a
  different slice, so every moving answer reaches setups across the collection).
- Where it may appear inside the file (bits, so the engine's ordinary NEVER WITH check enforces it):
  - NEEDS: a setup tags a bit for each need it does not have; a moving piece is NEVER WITH the bits of its needs. An
    answer also carries the needs of its least-needing moving outcome, so it is only offered where an outcome can
    follow it;
  - TONE: a funny piece is NEVER WITH a serious setup (grief, sickness, fear, danger, danger at sea, or a solemn tone);
  - everything that does not move keeps to its own setup (EVENT BITS, one per event of the file);
  - no button twice: a guest is never added with a label the file already has, and a moving answer keeps away from
    another event's setup that has an answer with its label;
  - the owner's four blocks as in section 4 (reserved bits 0-4).
- A moving answer brings the villagers its moving outcomes act on (their needed slots are added to it), so its
  outcomes are always "plain" (spec 3, step 6).
- The event's own answers first, concrete ones before generic ones: an own answer weighs 40 (10 when its label is
  one three or more events share, "Offer Gentle Encouragement."), a guest 2 (1 when generic). So a setup mostly
  shows its own answers with one or two from other events among them.
- An outcome always answers the approach it was written for (links are never invented across events).
- **Adding sources later** (REWRITES, BALANCE, ...): `python scripts/procedural_pieces.py export-situations <dir>
  --missing` writes reading batches for the events the file does not hold yet; the readers write
  `batch_NN.tags.txt` beside them, following `INSTRUCTIONS.txt` (copied into the folder from
  `data/event_collection/procedural_situations_instructions.txt`: `S|`, `A|`, `O|` lines); `merge-situations <dir>`
  adds them to the file. Untagged events keep to themselves until then.

## 4. Tags

- Bit 3 romance and bit 4 minor (a villager slot under 18) as the contract says; a romance piece whose romance roles
  are adults is age band 1 and also tags bit 5 ("adult romance"); NEVER WITH bit 4 and bit 0.
- **Teen-teen romance (the owner: allowed).** A romance piece whose villager roles are all 13-17 is age band 2,
  tags bits 3 and 4 and is NEVER WITH bit 5 (adult romance) and bit 0. A minor-centred piece is NEVER WITH bit 3,
  except in an event of the owner's own that holds a teen-teen romance piece: there it is NEVER WITH bit 5 only.
- **A scene with both a child and adults and romance words** (a parent's new partner, a wedding the child attends):
  minor-centred, not romance (an age band would force the child's role to 18), NEVER WITH bit 5, never travelling.
- Bits 0-2 (power, invalidating pain, lesser) are TAGS from the words (`POWER_RE`, `LIGHT_RE`, `LESSER_RE`) and, in
  the Living files, from the bank's own classes (mocking and comedic choices, light archetypes, authority
  approaches).
- Pair bits: every forbidden pair (the Living rules, the slot merges that cannot hold, the validator's pairs) is
  covered by a greedy biclique cover: a bit tags a class of pieces with the same forbidden partners and is NEVER
  WITH on those partners, so no allowed pair is ever blocked.

## 5. The twin's readings of the contract

`src/vv_procedural.py compose` follows section 3 roll for roll. Where the contract is silent the twin reads:

- Weighted picks with a total of 1 make no roll (as `random_below(1)`); the running sum "passes r" means `> r`.
- Step 6's cast is the engine's own; the twin takes it as a callback (`cast(roles) -> bindings | None`). The
  validator's caster is a model village (60 villagers of every age, the Golden Child in VV1, the Chief in VV3, some
  Heathens in VV5), so its rolls are not the engine's: only steps 1-5 and the keep rules are pinned roll for roll.
- The graph (`graph_of`): the start popup and its question are ONE question node holding the start text (a v6
  question that appends to a popup is refused: "a question has choices only"); each answer a NEW popup with its
  text (nothing is open to append to once a button is clicked: "append with no popup open") or a silent branch;
  outcomes appended to the answer's popup as a paragraph (a new popup after a silent branch); a role an outcome adds
  is optional and its child holds on `role`. The engine should write the same shape, or tell the data side. The
  collection block is not written into the JSON the twin checks (vv_cie_graph's collection checks are for files),
  and neither is "speaks" while this branch's vv_cie_graph lacks it.
- Title: the setup's label as written; the data side writes it in title case (the owner's rule: every word
  capitalized except a, an, the, and, but, or, nor, of, to, in, on, at, for, by, with, from, as unless first or
  last; a placeholder's word capitalized, its role prefix as written). A label or title title case makes too wide
  for a game leaves that game out of the piece.

## 6. The validator

`python scripts/procedural_pieces.py validate` builds the files, reads them back (the twin always composes from the
bytes), draws a file per spec 4 and composes events per game, then checks each:

1. `vv_cie_graph.validate(..., scrolling=True)` on the composed graph (fit, text, placeholders, effects, roles);
2. the owner's four blocks, on every path a player can take (the start, one answer, one outcome): minor-adult
   romance by the roles' ages; adult romance with a minor-centred piece; power with romance; light words with
   grief, injury or distress; mocking with bullying or prejudice (two pieces of one owner event are the owner's own
   combination, never a block);
3. title case of the title and every label;
4. sense: every outcome links its approach; a piece from another event is marked as moving, suits one of this
   setup's situations, needs nothing it lacks and is not funny under a serious setup; no button twice; pregnancy
   and nursing only on carrier roles; no villager effect on a stranger.

Quick rounds (300 a game) run until one is clean, then the full round (2,000 a game); a failing pair goes into
`procedural_never_with.json` and the rounds start again.

## 7. The last run (2026-11-16, feat/97-player-events 2d58434e1: 3,922 events with the GO events)

- **The GO events** (the owner's rewritten and balance events, sources rewrites / balance) come as mixer seed pieces,
  `data/procedural_pieces/go_seeds.json` (8,855 pieces, opening lines included), read by `go_events()` beside the
  split collection; an event the seeds hold is never split again from its static form. 553 of the 673 are read from
  the seeds; 120 keep their static form's split instead: 118 because a text names a role the event's seeds do not
  have, 2 because their effects do not validate. 142 single pieces are left out because an effect has a group target
  or an age cap (the piece record has no field for the .cieg's selector byte and last field: an engine question).
  Their own opening lines (flavour, 1,898) only open their own event's setup (event bits).
- 2,525 collection events split from their static form (2,428 before the GO events, plus the GO events the seeds do
  not cover). The rest stay static only (no question, pools, nursing-parent roles, ...: the report lists each reason).
- Situation tags: 3,100 events, 6,515 answers read (the GO events in 7 more batches); 886 answers and 1,288 outcomes
  move. The GO events are almost all scene-bound (6 of their answers move), but every GO setup takes guest answers
  from the rest of the collection.
- The broad situations were audited answer by answer (celebration, newcomer, tradition: 232 moving answers re-read,
  77 narrowed to the situations they really answer, 31 set to stay home), after the sample showed a grieving answer
  at a wedding garment, a canoe signal at a house guest's goodbye and "Record Both Accounts" under a fisher who
  thanks the sea.
- 6,499 guest answers placed in the files.
- 413 files, 9.1 MB, none past 54 KB: 3,355 setups, 16,628 approaches and 24,179 outcomes (guests included), 1,898
  flavour lines, 1,116 frames.
- 116 approaches are left out of a game where their title-case label is too wide (mostly VV1 / VV2).
- Validator: 10,000 compositions (2,000 a game), every one composed, no graph, block or sense problem (a graph no
  piece pair explains now stops the run as unresolved; none). The pairs it found on the way: 4, all Living, all
  "portraying someone as lesser" (a mocking choice with the oddity seed ODD-08, tagged bullying).
- In the owner's sample, 334 of 500 events show at least one answer from another event, mostly beside the event's
  own answers; 110 sample events are GO setups (62 of them with a borrowed answer).
