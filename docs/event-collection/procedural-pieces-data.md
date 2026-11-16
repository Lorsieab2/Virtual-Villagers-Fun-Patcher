# Procedural island events: the data side (v1.35.97)

The contract is [procedural-pieces.md](procedural-pieces.md) (VPCB v1, the composer's roll order). This page says how
the data side fills it: what `scripts/procedural_pieces.py` splits, how it tags, what `src/vv_procedural.py` (the
Python twin) reads into each open point of the contract, and what the validator checks. The numbers of the last run
are in `procedural-pieces-report.json` next to this page.

## 1. The files

- `assets/event_collection/pieces/pieces-<group>.pcb`, one per topic: a collection folder (`companion_c5`, `v27`,
  `living_lv_auth`, ...), a Living Engine category (`le_per`, `le_fam`, ...) or an MC category (`mc_isl`, ...). A group
  past about 900 KB is split into numbered parts (`<group>_1`, `<group>_2`), so every file stays under the engine's
  1 MB.
- `data/event_collection/procedural_never_with.json`: the piece pairs the validator found (section 5). The build
  reads it every time, so the bits are reproducible.
- Build: `python scripts/procedural_pieces.py build`; check: `... validate`; the owner's sample: `... sample <file>`.

## 2. What becomes a piece

**Collection events** (every `data/event_collection/<source>/**.json`, as `collection_check.graph_for_engine` gives
it to the engine; never the owner's draft text files):

- **Setup:** the start's text, and any linear intro popups before the first question, joined as the event shows them
  (a new popup or a paragraph: a blank line; an appended space join: a space). Its label is the event's title in
  title case. Family: the event's own number in the file. Slots: every needed role of the event plus any role its
  text names.
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
popup, pools or inline picks (no pools in pieces), alias roles, nursing-parent roles (no slot special for them),
`else` edges and conditions other than games. The report lists each reason with its count.

**Living Engine** (`data/living_events/bank.json`, one file per category):

- Setups: the category's seeds (the seed sentence; the chief's words per game). Slots `first` / `second`: the
  loosest bounds of every role the seed allows there (adult-only seeds 18+).
- Approaches (family 1): the bank's 34 approaches and the category's choice set, as the living mixer labels them;
  the secret-keeping choice declares both villagers 18+ (S7).
- Outcomes: the 38 archetypes with their effects (as `archetype_effects`), linked to every approach
  `arc_ok_after` allows, weighted by group (good 20, mixed 10, bad 10, rare 2, divided over the group's size).
  Slot ages carry the role rules: R1's archetypes 18-54 on both, S8's injuries 18+, `needs_elder` 55+.
- Frames: `(first), a <role>, and (second), a <role>, disagree about what should happen next. Their status alone
  does not settle the matter.` -- the living mixer's own frame, for every role pair it casts for the category's seeds
  (the MIX personalities where the MIX has them). Slots from the roles (skill requirements are not slots).
- The mixer's rules become forbidden pairs: seed x approach (`approach_allowed`, the choice set's own list), seed x
  archetype (`seed_allows`, S10-S17), seed x frame (`possible_pair`, S5), frame x archetype (R1-R3, `cast_ok`,
  `needs_elder`, S1 risky personalities), frame x secret choice (S7).

**MC situations** (one file per MC category): the situation (setup), its four approaches and their two outcomes
each, as the living mixer composes them; the category's filters on every piece.

## 3. Tags

- Bit 3 romance and bit 4 minor (a villager slot under 18) exactly as the contract says; a romance piece whose
  romance roles are adults is age band 1 and also tags bit 5 ("adult romance"); NEVER WITH bit 4 and bit 0.
- **Teen-teen romance (the owner: allowed).** A romance piece whose villager roles are all 13-17 is age band 2,
  tags bits 3 and 4 and is NEVER WITH bit 5 (adult romance) and bit 0. A minor-centred piece is NEVER WITH bit 3,
  except in an event of the owner's own that holds a teen-teen romance piece: there it is NEVER WITH bit 5 only.
  So a minor can never meet adult romance, and the owner's teen romance keeps its own pieces.
- Bits 0-2 (power, invalidating pain, lesser) are TAGS from the words (`POWER_RE`, `LIGHT_RE`, `LESSER_RE`) and, in
  the Living files, from the bank's own classes (mocking and comedic choices, light archetypes, "the chief
  decides"). Collection pieces only ever meet pieces of their own event (their family) so their blocks are what the
  owner wrote; in the Living files the mixer's rules give the NEVER WITH (section 2).
- Bits 6-31: the pair bits. Every forbidden pair (the Living rules, the slot merges that cannot hold, the
  validator's pairs) is covered by a greedy biclique cover: a bit tags a class of pieces with the same forbidden
  partners and is NEVER WITH on those partners, so no allowed pair is ever blocked. A file that needed more than 26
  bits would fail the build (none does).

## 4. The twin's readings of the contract

`src/vv_procedural.py compose` follows section 3 roll for roll. Where the contract is silent the twin reads:

- Weighted picks with a total of 1 make no roll (as `random_below(1)`); the running sum "passes r" means `> r`.
- Step 6's cast is the engine's own; the twin takes it as a callback (`cast(roles) -> bindings | None`). The
  validator's caster is a model village (60 villagers of every age, the Golden Child in VV1, the Chief in VV3, some
  Heathens in VV5), so its rolls are not the engine's: only steps 1-5 and the keep rules are pinned roll for roll.
- The graph (`graph_of`): the start popup and its question are ONE question node holding the start text (a v6
  question that appends to a popup is refused: "a question has choices only"); each answer a NEW popup with its
  text (nothing is open to append to once a button is clicked: "append with no popup open") or a silent branch;
  outcomes appended to the answer's popup as a paragraph (a new popup after a silent branch); a role an outcome adds
  is optional and its child holds on `role`. The engine should write the same shape, or tell the data side. The collection block is not written into the JSON the twin checks
  (vv_cie_graph's collection checks are for files).
- Title: the setup's label as written; the data side writes it in title case (the owner's rule: every word
  capitalized except a, an, the, and, but, or, nor, of, to, in, on, at, for, by, with, from, as unless first or
  last; a placeholder's word capitalized, its role prefix as written).

## 5. The validator

`python scripts/procedural_pieces.py validate` builds the files, reads them back (the twin always composes from the
bytes), draws a file per spec 4 and composes 2,000 events per game, then checks each:

1. `vv_cie_graph.validate(..., scrolling=True)` on the composed graph (fit, text, placeholders, effects, roles);
2. the owner's four blocks on the composed pieces and their merged roles (minor-adult romance by the roles' ages;
   power with romance; light words with grief, injury or distress filters; mocking with bullying or prejudice);
3. title case of the title and every label;
4. sense: every outcome links its approach; pregnancy and nursing only on carrier roles; no villager effect on a
   stranger.

A failing pair goes into `procedural_never_with.json` and the build reruns until a round finds nothing (quick rounds
of 300 a game until one is clean, then the full 2,000 a game).

Before the validator, the build forbids up front, in the Living Engine files (the only files where pieces of
different sources meet): power with romance, a light or mocking piece with grief, injury or distress (F01, F03, F05,
F06, F11, F12), a mocking piece with bullying or prejudice (F16, F17); and in every file the pairs whose slots can
never merge.

## 6. The last run (2026-11-15)

- 37 files, 2.0 MB in all, the largest 179 KB: 1,169 setups, 3,992 approaches, 5,708 outcomes, 1,112 frames, no
  flavour lines (no source has standalone opening lines; the owner's drafts are not a source).
- 914 of 1,353 collection events split; the rest stay static only (280 have no question, 38 use pools or inline
  picks, 29 have an outcome that branches again, 26 have no needed villager or stranger, 24 alias roles, 19
  nursing-parent roles, 16 effects before the question, 7 other conditions). 251 role skill requirements and 6 age
  gaps have no slot field and are dropped from the pieces (the static events keep them).
- 6 approaches are left out of VV1 / VV2: their title-case label is wider than those games show.
- Validator: 10,000 compositions (2,000 a game), every one composed, no graph, block or sense problem. Pairs the
  validator found on the way (all Living, all "portraying someone as lesser": a mocking choice with the oddity seed
  ODD-08, tagged bullying) are in `procedural_never_with.json`; the up-front rule now covers them.
