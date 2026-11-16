# Procedural island events: the data side (v1.35.97)

The contract is [procedural-pieces.md](procedural-pieces.md) (VPCB v1, the composer's roll order). This page says how
the data side fills it: what `scripts/procedural_pieces.py` splits, how it tags, how events mix with each other, what
`src/vv_procedural.py` (the Python twin) reads into each open point of the contract, and what the validator checks.
The numbers of the last run are in `procedural-pieces-report.json` next to this page.

## 1. The files

- `assets/event_collection/pieces/pieces-<group>.pcb`:
  - `x_<family>_<n>`: the cross-event files, one situation family each (section 3), at most 16 events a file;
  - `<source>_<section>`: events with no situation family (they mix only within themselves), by collection folder;
  - `le_<cat>`: a Living Engine category; `mc_<cat>`: an MC category.
  Every file stays well under the engine's 1 MB (a group past about 900 KB is split into numbered parts).
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

## 3. Cross-event mixing

The owner: "everything can be mixed with anything", where it makes sense. An event whose setup names a situation
family -- food, visitor, sickness, weather, animal, craft, learning, arts, celebration, conflict, family, children,
grief, belief, mystery, sea, farming, leadership (`FAMILIES`: the family with the most of its words in the setup's
text and title) -- goes into that family's files, where every setup and approach is family 1: a setup takes answers
from any event of its file.

- **Which pieces travel, and where.** Common words (`STOP`) and the words any situation can hold (`GENERIC`:
  listen, patience, apologize, compromise, advice, ...) never count. A button's other words are all PARTICULAR (an
  answer must suit the setup it is shown under); an outcome's (or an answer popup's) particular words are those it
  shares with its own setup (they point back at that scene), and it may bring at most ONE word its own setup does
  not have (what happens next: "The patient asks for more time" can follow any setup with a patient; "The old
  traditions and new ideas mix into something everyone enjoys" tells its own story). A travelling text also has no
  dialogue, no word pointing at something its own scene showed (it, its, this, that, these, those, there, then:
  "Friends admire it.", "Respect Its Space"), at most two short sentences, no unprefixed placeholder (whose role would be its own event's
  default), and no romance (romance stays with its own couple).
- A piece then goes to every setup of its file that names all its particular words: each file picks up to 10 WORD
  BITS (the words two or more of its setups name that free the most pieces), a setup tags the word bits of the words
  it does not name, and a travelling piece is NEVER WITH the bits of its particular words. A piece with no
  particular words goes anywhere in its file; a piece whose words got no bit keeps to its own setup.
- An approach travels only with a travelling outcome, takes on that outcome's particular words too (the one that
  needs the fewest), so it is only offered where that outcome can follow it; and it brings the villagers its
  outcomes act on (their needed slots are added to it, so they are always "plain" under any setup, spec 3 step 6).
- The rules were tightened three times on the owner's sample: the first, looser readings put a grieving answer under
  a ridiculous carving, a classroom answer under a wedding and a crab's cup under a gift swap. Sense comes first, so
  most pieces still keep to their own setup; the families decide only which events share a file.
- **Everything else keeps to its own setup.** Each event in a file (at most 12) has an EVENT BIT (bits 6 and up) on
  its setups; its non-travelling pieces are NEVER WITH every other event's bit.
- **No button twice.** Approaches with the same label and text are one piece whose outcomes are every such event's;
  a travelling approach is NEVER WITH the setup of any other event that has an answer with its label.
- **Concrete answers first.** A label three or more events share (a generic one, "Offer Gentle Encouragement.")
  weighs 1; any other weighs 10.
- **The blocks** (reserved bits 0-2; only travelling pieces carry those tags): a light piece never with grief,
  injury or distress (F01, F03, F05, F06, F11, F12), a mocking piece never with bullying or prejudice (F16, F17),
  power never with a minor-centred piece or romance. Slot merges that cannot hold and the validator's pairs use the
  bits left; a file that runs out of bits is halved.
- An outcome always answers the approach it was written for (links are never invented across events).

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
4. sense: every outcome links its approach; a piece from another event names nothing particular to its own setup
   that this setup lacks; no button twice; pregnancy and nursing only on carrier roles; no villager effect on a
   stranger.

Quick rounds (300 a game) run until one is clean, then the full round (2,000 a game); a failing pair goes into
`procedural_never_with.json` and the rounds start again.

## 7. The last run (2026-11-16, the full collection of feat/97-food-tech 2cfea820c)

- 2,428 of 3,249 collection events split. The rest stay static only: 621 have no question, 49 no needed villager or
  stranger, 38 pools or inline picks, 33 nursing-parent roles, 29 an outcome that branches again, 24 alias roles,
  16 effects before the question, 11 other conditions. 260 role skill requirements and 27 age gaps have no slot field
  and are dropped from the pieces (the static events keep them).
- 2,080 events are in a situation family (in 183 `x_` files); 348 have none and mix only within themselves.
- Travelling pieces: 41 approaches and 284 outcomes (an outcome travels only behind a travelling approach); 3 shared
  answers merged into one piece each. They are the plain, kind answers that suit any scene ("Talk to a Trusted
  Friend" / "Ema2 offers warm support.", "Offer a Quiet Place", "Ask What Would Help"); every concrete answer stays
  with the setup it was written for.
- 254 files, 4.6 MB in all, none past 48 KB: 2,697 setups, 7,915 approaches, 11,440 outcomes, 1,116 frames, no
  flavour lines (no source has standalone opening lines). At most 16 bits a file used.
- 114 approaches are left out of a game where their title-case label is too wide (mostly VV1 / VV2).
- Validator: 10,000 compositions (2,000 a game), every one composed, no graph, block or sense problem; 93 retries
  ("fewer than 2 approaches"). Pairs the validator found: 4, all Living, all "portraying someone as lesser" (a mocking
  choice with the oddity seed ODD-08, tagged bullying), now also covered by the up-front rule.
- In the owner's sample, 21 of 500 events hold an answer from another event; the rest are their own event's
  answers and outcomes, reordered and subset, or the Living and MC mixes.
