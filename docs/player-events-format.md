# Player Events: the plain-text format (v1.35.97)

The owner (2026-11-15): "if the player wants to add more they add text files to the mixer/additional events
folders/sections in the patcher in each game. or the event creator there accommodates them." ... "in that patcher
section, add a default prompt so that users can paste it into an AI and get a compatible text file." ... "add as many
features to that section as needed so they can perfectly emulate my existing added events."

The reader is `src/vv_player_events.py`; the section is `src/vv_player_events_ui.py` (each game's Island Events
section, "Player Events"); `tests/test_player_events.py` pins this page's examples, the AI prompt and the round trip
of the built-in events.

## 1. Where the files go

- **Your files:** `<patcher folder>\Player Events\VV<n> - <game name>\*.txt` (the section's "Open Player Events
  Folder"; "Add Event Files..." copies files there). Any number of files; each holds any number of events and
  pieces. `Your Rules and Themes.txt` and `Player Events Settings.json` in the same folder are the section's own.
- **The AI prompt and the tone reference:** `<patcher folder>\Player Events\Player Events - AI Prompt.txt` and
  `Island Event Tone Reference - Lorsieab2's Handwritten Events.txt` (the owner's twelve handwritten events, the
  DEFAULT source for event tone; "Choose Reference File..." swaps in your own, Cancel goes back to the owner's), and
  `Isola Island Event Style Guide.txt` (the owner's style guide, from Lorsieab2's own edits: every added event follows
  it, except the owner's handwritten ones; "Copy Style Guide" / "Show Style Guide"; the prompt tells the AI to follow
  it), and the owner's default lists: `Island Event Themes - All Added Events.txt` (every theme of the added events;
  the "favour these themes" picker offers them after your own) and `Island Event Outcomes - Every Kind.txt` (every
  kind of outcome; the prompt tells the AI to use those themes and outcome kinds, balancing the outcomes), and
  `Example Events - Lorsieab2 (S001-S020).txt` (the owner's 20 rewritten events: the format and style example the
  prompt names; reference only, never compiled or installed as playable events); each with Copy / Show buttons. The
  owner's five files ship byte for byte (also in docs/more-island-events); all six (the prompt with your rules) are
  also installed in each patched game's `Virtual Villagers Fun Patcher Files\Player Events`.
- **At patch time** (only with the game's Isola Grand Event Collection row ticked, and "Install my player events
  when patching" on), in the patched game's `Virtual Villagers Fun Patcher Files`:
  - `Island Event Collection\manifest-pl_<x>.txt`, one per file (the collection's own split-file manifests,
    `story_collection.inc`), and `pl_<x>_<nnn>.cieg`, one per event;
  - `Island Event Collection\pieces-pl_<x>.pcb`, the file's mixer pieces (VPCB v1,
    [procedural-pieces.md](event-collection/procedural-pieces.md));
  - `<x>` keeps every name within A New Home's deep-folder rule (a manifest's file name at most 22 characters, the
    collection's own groups' rule): a file name of up to 6 letters and digits as it is (`events.txt`: `pl_events`),
    a longer one its first two and a hash of the whole name (`My Sea Stories.txt`: `pl_my` and four hex digits), the
    same every patch. Two files that still meet: the second takes the next hash, and the report says so;
  - the built-in collection ships its own `manifest-<group>.txt` files, so nothing of it is copied or changed;
  - `Player Events\`: the AI prompt (with your rules), the tone reference, a copy of your files and
    `Player Events Report.txt` (what was installed and what was left out, and why).
  The patcher's own earlier files there (those names only) are replaced at each patch; nothing else is touched. The
  save and the exe are never written.
- **In the game** player events are ordinary collection events: they come in the normal draw (each its draw weight,
  a series counting once), obey the content filters and Content Notes, and an event that can kill a villager, make
  one disappear or lose a pregnancy is drawn only from 61 villagers (the engine finds those effects itself).

## 2. Simple events (the owner's own layouts)

```
Title: The Coconut That Would Not Open
Applies to: VV1, VV2, VV3, VV4, VV5
Themes: comedy, food
Event:
(Name) has been trying to open the same coconut since sunrise. (He/She) has tried rocks, teeth and a firm talking-to.
Choice 1: Lend a Hand
* Outcome A: (Name) and two neighbours finally crack it open together, and the milk is the sweetest anyone has tasted.
  Effect: FOOD GAIN (small)
* Outcome B: The coconut flies out of everyone's hands and rolls into the sea. (Name) waves goodbye to it.
Choice 2: Leave (Him/Her) to It
* Outcome A: By sunset (name) has invented a clever splitting wedge, and the builders want one too.
  Effect: SKILL + Building a little
* Outcome B: (Name) falls asleep hugging the coconut, still unopened.
```

- An event starts at `Title:` (at the start of a line) or at the owner's heading `NEW-001 — THE BASKET LEFT IN THE
  RAIN   [VV1, VV2, VV3, VV4, VV5]` (a title in capitals is shown in Title Case). It ends where the next one starts.
  Lines of `====`, `----`, `####` and lines starting with `#` are ignored.
- **Title and choices are in Title Case** (small words such as a, the, of, in, to may stay small; all capitals is
  accepted, the game shows it in title case). Check File reports anything else with the fixed form.
- `Applies to:` VV1..VV5, game names, `all`, `VV1-VV4`. Default: all five.
- `Event:` the opening story; each line is one paragraph. In the `NEW-` layout the lines after the heading are the
  story.
- `Choice 1:` / `Choice A:` / `Choice:` / `[Choice] ...` a button (2 to 7). Text lines right after a choice (before
  its first outcome) are shown first, then the random outcome on the same page.
- `* Outcome A:` / `Outcome 1:` / `(Random outcome 1 of 2)` a random outcome of that choice, equally likely;
  `* Outcome A (weight 3):` three times as likely. One outcome: no roll. Lines after it are its story.
- `Effect: ...` under an outcome (several lines, or `;` between): section 4. In the `NEW-` layout an effect may also
  sit in the effect table anywhere in the file: `NEW-001 | A1 | FOOD GAIN (small) | "quote"` (choice A, outcome 1;
  the quote must be the start of that outcome's text).
- `Filters: F05, Grief and bereavement` under an outcome: that outcome is dropped when that content filter is ticked
  (the patcher also tags every outcome by its effects and words, as it does the collection). At the top: the whole
  event.
- `Solidarity: raise|lower|neutral` under an outcome: that page's Village Solidarity tag (the graph node's
  `solidarity`, cie-v6-binary.md 32). Any other word is a problem. Text only unless the Village Solidarity patch is on.
- `Coda:` a closing paragraph shown after every outcome.
- `Auto Lines: yes` (top, or under one outcome): the game's automatic lines after the text ("Kai gains some
  Building skill.").
- Optional top lines: `Description:` (the Pick Island Event list's sentence), `Credit:`, `Series:` (events of one
  series count as one event in the draw), `Weight:` (draw weight 1..10000, default 1), `Themes:`, `Id:` (pl_...),
  `Title (Guardians of Isola):` (New Believers' title with the Guardians of Isola Rewrite; without it a title or text
  that says Heathen gets "Isolan" automatically, and "believer(s)" is reworded sentence by sentence as
  docs/event-collection/guardians-wording.md "Believers" says: set against the Isolans or Heathens, the tribe ("the
  believers" -> "the tribe", its verb made to agree; "a believer" -> "a tribe member"); otherwise a person of faith
  ("the believers" -> "the faithful", "a believer" -> "a villager of faith", "some believers" -> "some of the
  faithful"); "the new believers" -> "the newcomers"; "a Heathen" -> "an Isolan"; the game's name "New Believers" is
  never changed).

## 3. Names, roles, requirements, words and lists

- **Placeholders:** `(Name)` / `(name)` the main villager's full name; `(He/She)`, `(his/her)`, `(him/her)`,
  `(himself/herself)`, `(man/woman)`, `(boy/girl)`, `(son/daughter)`, `(mother/father)` follow their sex; `(name2)`
  a second villager; any other short role name `(fisher)`, `(Fisher)`, `(fisher.he/she)`; `(award)` the amount an
  AWARD effect gave; `{@chief}` / `{@Chief}` ("the Chief" in The Secret City, "the village leader" elsewhere, added
  automatically); `{@tribe}` the tribe's name; `{a|b|c}` one picked at random. Round brackets that are not a
  placeholder are shown as written.
- **Roles:** every role a text or an effect names is a villager of 14 or more (an expecting or nursing parent 18 or
  more). `Role fisher: adult, male, skill Farming 10+, speaks` sets its rules, words separated by commas:
  `adult` (18+), `child` (1-13), `teen` (14-17), `elder` (55+), `30+`, `18 to 50`, `under 14`, `any age`, `male`,
  `female`, `skill Healing 20+`, `best at Healing`, `spouse of <role>` (also parent of, child of, sibling of,
  grandparent of, grandchild of, aunt or uncle of, cousin of), `within 10 years of <role>`, `optional`, `speaks` (never
  a story-mute villager), `carrier` (18+), `golden child`, `tribal chief`, `nursing parent`, `believers only`,
  `any faith` (New Believers: a Heathen may take it -- a conversion role), `anyone` (protected villagers allowed),
  `never protected`, `stranger`, `named stranger`, `new name for <role> [same|other|random sex] [same|different|random
  last name]`, `one of a b c` (an alias), `the other of <alias>`.
- **Requirements:** `Requires: 2 villagers, population 20+, 3 children+, golden child present, chief present,
  puzzle The Cave (VV1), patch <id>, not patch <id>`. The required villagers count is the event's needed roles unless
  given. The engine has no food or tech requirement.
- **Game words:** `Word naturalist: VV3 = the Alchemist; other = the naturalist` then `{@naturalist}`.
- **Lists:** `Pool A: a crooked statue, a leaning arch` (or `Pool A:` then `- item` lines), then `{A}` in the text.

## 4. Effects in plain words

`<who>` is a role name (with or without round brackets; `villager` or nothing is the main villager). Sizes are the
game's own ranges (the same as the More Island Events rewards); food and tech scale with the village.

| Line | What happens | Engine effect |
|---|---|---|
| `FOOD GAIN (small\|normal\|large\|huge)`, `FOOD LOSS (size)`, `TECH GAIN (size)`, `TECH LOSS (size)` | food or tech points | food / tech, size |
| `FOOD GAIN 500`, `FOOD GAIN 200 TO 800` | a fixed amount or range | food / tech, amount |
| `FOOD AWARD (size)`, `TECH AWARD (size)`, `PAY AWARD` | an amount the text names with `(award)`, paid later | defer, pay_award |
| `SKILL + Research a little\|some\|a lot\|hugely`, `SKILL - ...`, `... FOR <who>` | a skill rises or falls | skill |
| `MASTER Healing`, `SKILL SET Healing 50` | the skill set to 100 / a value | skill set |
| `LIKE + swimming`, `DISLIKE + work`, `LIKE - dancing`, `DISLIKE - water`, `LIKE + random` | a like or dislike given or taken away | preference |
| `INJURY <who> [(minor\|serious\|grave)]`, `HEALTH <who> +10 TO +20`, `HEAL <who>`, `ILLNESS <who>` | health, sickness | health_change, health, sick |
| `DEATH <who> [CAUSE "words"]`, `DISAPPEARS <who>`, `LOST FOREVER <who>` | a death with a grave, a disappearance, a death with no body | kill, vanish, die_unrecovered |
| `PREGNANCY LOSS <who>`, `BIRTH THEN DEATH <who>`, `EARLY BIRTH <who>` | the expecting parent's pregnancy | baby_lost, birth_then_die, deliver_early |
| `NEW VILLAGER (child\|teen\|adult\|elder\|any)`, `DUPLICATE OF <who>`, `CLONE OF <who>`, `CLONE OF <who> (2)`, `TWO CLONES OF <who>` | a newcomer; a lookalike; an exact double, or two (never more) | new_villager, clone (count) |
| `PREGNANT <who> [WITH <who>] [(ANY BIRTH SEX)]`, `NURSING <who> [WITH <who>] [(ANY BIRTH SEX)]` | a pregnancy; a baby now | pregnant, nursing |
| `NEW LOOK (head\|body\|both) <who>`, `OLD LOOK <who>`, `SEX CHANGE <who>`, `BODY SWAP <who> WITH <who>` | looks | appearance, old_look, sex_change, body_swap |
| `LOSE NAME <who>`, `CHANGE NAME <who>`, `CHANGE NAME <who> TO Lani` | the name becomes "?"; a new name from the game's list, or that name (1-31 letters, spaces, `'`, `-`, `.`, starting with a letter) | lose_name, change_name |

**A "?" name** (LOSE NAME) only comes from a bump on the head or something like it (a fall, a fever, magic or
anything that takes the villager's memory), never from a villager choosing or being given "?" as a name. Check File
warns (a warning, not an error: the event still installs) when a LOSE NAME page's text says none of head, bump, fall,
knock, fever, forget / forgot, memory, magic, spell or charm.
| `CHANGE AGE <who> YOUNGER\|OLDER 5 YEARS`, `CHANGE AGE <who> TO child\|teen\|18\|adult\|50\|elder` | age | change_age |
| `MOOD GOOD\|BAD <who>`, `CELEBRATE [<who>\|everyone]`, `ACTION <who> "words"` | behaviour | mood, celebrate, action |
| `DAMAGE (size) [ON hut, school]` | buildings damaged | damage |
| `BECOMES HEATHEN <who>` (VV5), `STORY MUTE <who>` | faith; the story trait | status, trait |

**Casting:** PREGNANT and NURSING go to a villager born female and 18 or more; `(ANY BIRTH SEX)` (the owner's cases:
magic, or a father caring for a baby) lets any villager carry. Each effect's own engine rules hold (cie-v6-binary.md).

## 5. Full events (anything the engine can play)

A block with a `Start:` line is a FULL event: every page, question, random branch, role, list, game word, variant,
condition and effect of [cie-v6-binary.md](event-collection/cie-v6-binary.md), one line each. Values are JSON with
plain words unquoted (`[Building]`, `{min_eligible: 2}`, `"two words"`); a text's further lines start with `|`.

```
Title: The Great Beautification Project
Applies to: VV1, VV2, VV3, VV4, VV5
Version: 6
Words: {chief: {"3": "the Chief", "*": "the village leader"}, Chief: {"3": "The Chief", "*": "The village leader"}}
Patches: [guardians_of_isola]
Requirement: {min_eligible: 2}
Description: Two builders volunteer to improve an ugly old monument.
Start: intro
Role builder1: kind=villager min_age=14 skill={names: [Building], min: 1}
Role builder2: kind=villager min_age=14 skill={names: [Building], min: 1} speaks=true
Pool A:
- a statue with an enormous nose

Page intro:
  Text: The monument is {A}.
  | {@Chief} announces a competition. (Builder1) and (builder2) volunteer.
  Next: ask

Question ask:
  Text: What should {@chief} do?
  Choice: RESTORE IT CAREFULLY -> res_set
  Choice: Ask the Builders -> r2
  Choice: LET THE VILLAGERS DECIDE -> r2 if={game: [3]}

Random res_set:
  Next: r1 weight=3
  Next: r2

Page r1:
  auto_text: true
  Text: The builders discover delicate carvings beneath years of dirt.
  Effect: tech size=normal scaled=true
  Effect: SKILL + Building some FOR builder1
  Filters: F21

Page r2:
  Text: The repairs are completed without incident.
  Variant: if={patch: guardians_of_isola}
  | The Isolans help with the repairs.
```

- Top lines: `Title`, `Applies to`, `Version`, `Start`, `Collection`, `Requirement`, `Patches`, `Title Variants`,
  `Words`, `Include Pools`, `Grammar Fixes` (the graph's own fields), and `Id`, `Description`, `Description
  Variants`, `Credit`, `Series`, `Weight`, `Themes`, `Filters`, `Speakers`, `Traits`, `Auto Filters: yes|no` (the
  patcher's own tagging; default yes), `Auto Speakers: yes|no` (finding who speaks; default yes).
- `Role <id>: key=value ...` (kind, sex, min_age, max_age, skill, special, protected, believers_only, optional,
  relation, max_age_gap, named, new_name_for, last_name, of; `speaks=true`). `Pool <name>: key=value` then `- item`
  lines (an item with a weight or a condition is a `{text: ..., weight: ...}` value).
- `Page <id>:` (a popup), `Question <id>:`, `Random <id>:` (a branch), each followed by its lines: `Text:`,
  `Variant: if=<condition>` with `|` text lines, `Effect: <do> key=value ...` (or the plain words of section 4),
  `Next: <page> [weight=n] [if=<condition>] [else=<page>]`, `Choice: <label> -> <page> [if=<condition>]`,
  `Filters:`, and any other page field as `<field>: <value>` (popup, join, title, auto_text, else, name, ...).
- The built-in collection events written in this form compile to the same bytes as the collection's own build
  (`full_text`; the test round-trips 50 of them across every source).

## 6. Mixer pieces (procedural events)

A block starting `Piece: <id>` is one piece for the composer of
[procedural-pieces.md](event-collection/procedural-pieces.md) (a setup, an approach, an outcome, a flavour line or a
personality frame):

```
Piece: reef_setup
Kind: Setup
Mood: social
Family: reef
Title: The Glowing Reef
Themes: sea, mystery
Role diver: adult, speaks
Text: (Diver) comes back from the reef with hands that glow faintly blue.

Piece: reef_ask_elder
Kind: Approach
Family: reef
Label: Ask an Elder
Text: The oldest villager listens carefully and nods slowly.

Piece: reef_elder_good
Kind: Outcome
Answers: reef_ask_elder (20)
Text: The glow is a harmless algae; the elder shows everyone how to read the tides by it.
Effect: TECH GAIN (small)
```

- `Kind:` Setup, Approach, Outcome, Flavour, Frame. `Mood:` warm, social or serious. `Family:` the question a setup
  asks / an approach answers. `Title:` a setup's event title, `Label:` an approach's button (both Title Case).
  `Answers: <approach> (weight), ...` an outcome's links. `Weight:` 1..1000. `Applies to:`, `Themes:`, `Filters:`,
  `Role <name>:` (section 3 words), `Effect:` (section 4), `Text:` with `|` lines.
- **The owner's four mixer blocks:** `Tags:` and `Never With:` take `power dynamics`, `invalidating pain`, `portraying
  anyone as lesser`, `romance`, `minor` and your own words. A piece that reads as romance must say `Tags: romance`; it
  then never meets a piece about a minor (and its roles are 18 or more unless `Age Band: teen romance`, all 14-17); a
  role younger than 18 makes the piece `minor`, which never meets romance.

## 7. Your Rules and Themes

- The section's **Your Rules and Themes** box (saved as `Your Rules and Themes.txt`): everything in it goes into the
  AI prompt as a marked section the AI must follow. A line `Themes: sea, festivals` lists your themes.
- **Rules the patcher enforces** (ticks): no deaths, no disappearances, no pregnancy or births, no lasting changes
  to a villager, no food or tech losses, no new villagers. An event or piece that breaks a ticked rule is left out
  (and listed).
- **Favour these themes** (a list to choose several from: your rules' Themes line and your files' `Themes:` lines
  first, then every theme of the owner's themes list): a player event or piece with a favoured theme (the same words,
  or one inside the other: "sea" meets "dolphins and the sea") weighs 3 times as much in the draw. **Only my themes:** player events and pieces
  without a favoured theme are left out. The built-in events are never changed.
- **Events the prompt asks for:** the number box (1..50).

## 8. Check File, Preview and the Custom Island Event Library

- **Check File...** reads a file without installing it and lists every problem with its line number.
- **Preview...** shows an event as the game would (random villagers, a random answer at each question, random
  outcomes: the patcher's own walk of the compiled event). "Again" draws new ones.
- **The Custom Island Event Library** (Tools tab): "Save as Player Event..." writes the open event as a FULL player
  event (section 5); "Export as Mixer Pieces..." writes its first question as a setup, each answer as an approach and
  the pages each answer reaches as its outcomes (section 6). "Import..." also reads a player .txt file (its first
  event).

## 9. What a bad file does

A file that cannot be read, an event or piece with a problem, or a line that is not part of the format is left out
and listed (Check File, Add Event Files..., the patch's own dialog, `Player Events Report.txt`); every other event of
the file still installs, and nothing stops the patch.

Soft warnings ("Warning (not an error)": the item still installs): a LOSE NAME page with no bump, fall, fever or
magic in its text; a page told in the first or second person outside quotes (I / me / my / we / you / your; the
games' own "Your villagers gain ..." line is left alone); a like or dislike that is missing from, or does nothing in,
a game the event applies to (`data/player_events_likes_dislikes.json`, the style guide's Appendix A).

## 10. The owner's own layout (S001 / NEW-101 / MY-001 ...)

`src/vv_owner_layout.py` reads the owner's layout directly (the rewritten events, the balance events and the
example file, which itself stays reference only and is never installed):

```
S001. The Spring That Talks Back   [VV1, VV2, VV3, VV4, VV5]
WHO: one villager aged 14 or older (not protected)
EVENT TEXT
(Name) has been walking in the hills all morning ...
Choice A: Ask What to Be Good At
Choice B: Ask Nothing and Just Drink
CHOICE A: ASK WHAT TO BE GOOD AT
First popup: (Name) clears (his/her) own throat ...
Ending A1 -- THE GREEN THUMB. Chance 50%. EFFECT: gains 20 to 30 Farming; now likes farming
"Plants," says the spring ...
MIXER SEED S001
Premise: Thirsty after a long walk, (name) kneels at a fern-hung spring ...
Roles:
  seeker: one villager aged 14 or older (not protected)
Approaches: Ask What to Be Good At | Just Drink | Argue with the Spring
Outcome pool:
  - "Plants," says the spring. [answers: Ask What to Be Good At] [mood: warm] [EFFECT: gains 20 to 30 Farming]
Flavour lines:
  - A single blue dragonfly keeps guard on a reed.
```

- The event: the opening question, each choice's "First popup" as its own popup, then its endings at their chances
  (each a new popup). Lines starting `^` are the owner's notes and are skipped. WHO gives the main villager's ages
  (and a second villager's, a chief, an Isolan, born female). `(young name)` is the role `young`, `(name2.he/she)`
  the second villager's pronoun (`(friend.he/she)`), `(new name)` / `(new name 2)` the villagers the event made
  (`(made1)` / `(made2)`, engine 5ee2b3dc0, also inside count tokens), `(his/hers)` the standalone possessive; "NEW
  LOOK for three random villagers" a group appearance (each draws its own look). `(award)` in an ending names its food or tech gain (an award, paid there); with a loss the owner's
  "Your village loses (award) food." becomes the game's own automatic line.
- **EFFECT phrases** (free English, `;` between them) go through a phrase table built from the owner's own files:
  food and tech sizes; "gains 20 to 30 Farming", "skill + research (a little, +5) for (young name)", "becomes
  MASTER", "in (his/her) best skill", "every healer gains ..."; likes and dislikes, "or similar if available" (a game
  word close to it that every game of the event has, with a note); injured, permanent disability, ill, illness cured,
  "all sick villagers are cured", "three random villagers have an illness"; dies (a grave), disappears; new villagers
  (a baby, a child, an adult woman, two adults with their baby, one adult, one teen and one child ...); duplicate of,
  clone of (1 or 2); body swap (and "swapped back": nothing); loses name, changes name (random or "first name becomes
  Lani"); changes age (N years older / younger, never past elder; to child, teen, 18, adult, 50, elder or an age);
  the old and young head looks, new looks (head or clothes); every villager is happier; the damaged huts are
  repaired; pregnant (with a partner, twins or triplets, ANY BIRTH SEX with magic); nursing a foundling. "none",
  "joins the village" and the like add nothing. A phrase not in the table is a line-numbered problem (that event or
  piece is left out).
- **MIXER SEED** blocks become mixer pieces (section 6): the premise a setup (its title the event's), each approach
  an approach (its text the matching choice's first popup), each pool line an outcome (its answers, mood and effects),
  each flavour line a flavour line; the role lines are the slots, and `(name)` in a seed is its first slot.
- Coverage on the owner's files (2026-11-16, with the engine forms of 5ee2b3dc0): "315 Rewritten Events - Quick
  Draft" 237 of 239 EFFECT phrases (99.2%), 18 of 20 events compile; "Rewritten Events S020 to MY-115" 4,069 of
  4,071 (99.95%), 291 of 296 events compile. The phrases left are not engine effects (a favourite job) or name a like
  that no game has (jewelry).

Count tokens `{#babies:a baby|twins|triplets}` / `{#made:one|two|three or more}` (engines 0853e8327, 5ee2b3dc0):
body text only, 1-3 options of up to 160 bytes of plain characters and placeholders (`(name)`, `(made1)`; no braces,
line breaks or . ! ?), filled with what the page's effects made; Check File checks them, the fit takes the widest
option and Preview shows the first. `(made1)` / `(made2)` name the villagers the event made (body text only);
`(his/hers)` is the standalone possessive.
