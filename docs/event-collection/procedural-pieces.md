# Procedural island events: the piece files and the composer (v1.35.97)

The owner (2026-11-15): "so everything has a chance of showing up and can be mixed with anything. procedural
generation." Besides the static events and the Living Event Engine's pre-built variants, "VVFP Story Upgrades.dll"
composes events at draw time from pieces kept in many small files. This is the contract between the files the data
side writes and the engine (and its Python twin, which must make exactly the same choices from the same rolls).

## 1. Files

`<game folder>\Virtual Villagers Fun Patcher Files\Events\<group>.pcb`

- `<group>`: `[a-z0-9_]`, at most 24 characters. One file per topic (or topic and mood); a file holds every kind of
  piece its events need, so most compositions use one file.
- Sanity limit: 1 MB a file. A file past it, damaged (CRC, offsets, counts) or of another version is skipped whole
  and logged once in `Events\Problems.txt`; the other files still work.
- All numbers little-endian. Strings are ASCII (the games' text set: letters, digits, space, `. , ! ? : - ' "` and
  the placeholders below), NUL-ended, in one string table; a string reference is a u32 offset into it,
  `0xFFFFFFFF` = none.

## 2. Layout (VPCB v1)

### 2.1 Header (64 bytes)

| Offset | Type | Field |
|---|---|---|
| 0 | 4s | `"VPCB"` |
| 4 | u16 | version = 1 |
| 6 | u16 | header bytes = 64 |
| 8 | u32 | file size |
| 12 | u32 | CRC-32 of the whole file with this field 0 (the `.cieg`'s CRC) |
| 16 | u8 | games mask (bit g-1: game g) |
| 17 | u8 | 0 |
| 18 | u16 | 0 |
| 20 | u32 | piece count |
| 24 | u32 | pieces at |
| 28 | u32 | strings at |
| 32 | u32 | strings size |
| 36 | u32 | effects at |
| 40 | u32 | effect count |
| 44 | u32 | slots at |
| 48 | u32 | slot count |
| 52 | u32 | links at |
| 56 | u32 | link count |
| 60 | u32 | 0 |

### 2.2 Piece record (64 bytes)

| Offset | Type | Field |
|---|---|---|
| 0 | u32 | id (string; unique in the file, `[a-z0-9_]`) |
| 4 | u8 | kind: 1 setup, 2 approach, 3 outcome, 4 opening / flavour line, 5 personality frame |
| 5 | u8 | mood: 0 warm, 1 social, 2 serious |
| 6 | u8 | flags: bit 0 DEADLY (an effect that kills, makes a villager disappear, `die_unrecovered`, `birth_then_die` or `baby_lost`; the engine also counts a piece DEADLY when one of its own effects is one of those codes); bit 1 New Believers only; bit 2 (an outcome) AUTO LINES, its effects told in automatic lines (cie-v6-binary.md 25); bits 3-7 0 |
| 7 | u8 | games mask (bit g-1) |
| 8 | u32 | topic bits (the file's own topic numbering, 32 at most) |
| 12 | u32 | family: a setup the question family it asks; an approach the family it answers; else 0 |
| 16 | u32 | content filters (bit n-1: Fnn, F01..F28; `src/vv_event_content.py`) |
| 20 | u32 | content notes (bit k: the k-th label of `vv_event_content.NOTE_LABELS`, in its order) |
| 24 | u32 | NEVER WITH: tag bits this piece must never be composed with (below) |
| 28 | u32 | TAGS: this piece's own tag bits |
| 32 | u32 | text (string): a setup's opening text, an approach's result text, an outcome's text, a flavour line, a frame line |
| 36 | u32 | label (string): an approach's button label (title case, the engine's `cg_title_case`); a setup's event title; else none |
| 40 | u32 | first slot (index into the slots table) |
| 44 | u16 | slot count |
| 46 | u16 | weight (1..1000) |
| 48 | u32 | first effect |
| 52 | u16 | effect count |
| 54 | u16 | age band: 0 any; for romance pieces 1 = every romance role 18 or more, 2 = every romance role 14-17 and of one age band (never a minor with an adult) |
| 56 | u32 | first link |
| 60 | u16 | link count |
| 62 | u16 | 0 |

Every kind uses the same record; fields a kind does not use are 0 (strings `0xFFFFFFFF`).

Required (else the whole file is refused): a setup has a text and a label (its title); an approach a label (its
text may be none: the answer then goes straight to its outcome, with no popup of its own); an outcome, a flavour
line and a frame a text. At most 64 slots a piece. A setup's id is at most 100 characters.

### 2.3 Tag bits (u32; NEVER WITH and TAGS)

The owner's four mixer blocks, then free topic tags:

| Bit | Tag |
|---|---|
| 0 | power dynamics (a piece that puts one villager in charge of another's life or body) |
| 1 | invalidating pain (a piece that waves away grief, injury or fear) |
| 2 | portraying anyone as lesser |
| 3 | romance |
| 4 | minor (a role younger than 18 is central) |
| 5..31 | the data side's own (contradictions found by the validator, section 5) |

Two pieces may be composed only when neither's NEVER WITH meets the other's TAGS. The data side sets bit 3 on every
romance piece and bit 4 on every piece centred on a minor, and NEVER WITH bit 4 on romance pieces (and bit 3 on
minor-centred ones), so minor-adult romance can never be composed.

### 2.4 Slot record (16 bytes): a role the piece needs

| Offset | Type | Field |
|---|---|---|
| 0 | u32 | name (string): the role's name, shared across pieces (`subject`, `friend`, `elder`, ...) |
| 4 | u8 | kind: 0 villager, 1 stranger |
| 5 | u8 | sex: 0 any, 1 male, 2 female |
| 6 | u8 | min age, years (0 none) |
| 7 | u8 | max age, years (0 none) |
| 8 | u8 | special: 0 none, 1 Golden Child, 2 Tribal Chief, 3 a carrier (born female unless flag bit 5, 18 or more) |
| 9 | u8 | flags: bit 0 optional, bit 1 believers only, bit 2 SPEAKS, bit 3 harm-capable, bit 4 a conversion role (a Heathen may take it), bit 5 any birth sex (special 3) |
| 10 | u16 | 0 |
| 12 | u32 | 0 |

Slots with the same name in the composed pieces are ONE role: their constraints merge (the larger min age, the smaller
max age, the flags OR'ed except bit 0; sexes must agree or one be "any"; specials must agree or one be 0; kinds must
agree). A merge that cannot hold rejects the composition. The role is optional only when EVERY slot merged into it
is optional or is an outcome's own (section 3, step 6). At most 16 roles an event.

How a role is written in the `.cieg` (cie-v6-binary.md 2):

- min age 0 means no minimum (a child may be cast): give every slot that must be grown its min age.
- special 3 (a carrier): min age at least 18, sex female unless flag bit 5; written as special 0.
- a piece's age band 1: every slot of that piece at least 18; band 2: every slot 14 to 17.
- believers only (role flag 8) on every villager role except a conversion role (flag bit 4), so New Believers'
  Heathens are cast only where a conversion is the role's purpose (and then only as the engine allows).
- harm-capable: flag bit 3, or a harmful effect of a composed outcome on it (cie-v6-binary.md 7's list, without the
  action words); it is then kept from the protected villagers (role flags 16, 32, 2, 4), except a special role
  (Golden Child, Tribal Chief), which is the author's "allow" (16 only).
- SPEAKS: role byte 13 bit 0x80 (a story-mute villager is never cast).
- a stranger (kind 1): named, sex "random" when any.
- the first role is the first needed villager role (else the first stranger); no needed villager and no stranger
  rejects the composition.

### 2.5 Effect record (16 bytes)

The `.cieg` effect encoding (docs/event-collection/cie-v6-binary.md), with the role byte a SLOT INDEX local to the
piece (0 .. slot count-1, `0xFF` every villager where the effect allows it) and the string a u32 offset. For
`pregnant` (28), `nursing` (29) and `body_swap` (31) the value `a` is a local slot too (255 none, for 28 and 29):

| Offset | Type | Field |
|---|---|---|
| 0 | u8 | effect code (cie-v6-binary.md: 1..34, never 23 or 25) |
| 1 | u8 | local slot |
| 2 | u8 | flags (as in the `.cieg`) |
| 3 | u8 | 0 |
| 4 | i32 | a |
| 8 | i32 | b |
| 12 | u32 | string (the effect's word, cause or skills list) |

### 2.5a Version 2 (VPCB v2, 2026-11-16): the effect record is 20 bytes

The header's version 2 (everything else as v1; a v1 file is still read, its effects 16 bytes with byte 3 and the
extra 0). The effect record:

| Offset | Type | Field |
|---|---|---|
| 0 | u8 | effect code (cie-v6-binary.md: 1..40, never 25) |
| 1 | u8 | local slot, or a role byte kept as it is: `0xFF` every villager, `0xFE` a GROUP, `0xFD` the newest villager the event made ($newest), `0xFC` the one before it ($previous) |
| 2 | u8 | flags (as in the `.cieg`) |
| 3 | u8 | the group's selector (role `0xFE` only: 1 all, 2 by skill, 3 N random, 4 elders, 5 children, 6 teens, 7 adults); else 0 |
| 4 | i32 | a (for `pregnant`, `nursing`, `body_swap`: a local slot, 255 none, or `0xFD` / `0xFC`) |
| 8 | i32 | b |
| 12 | u32 | string (the effect's word, cause or skills list) |
| 16 | u32 | EXTRA -> the `.cieg` effect's last H: a group's N (selector 3, 1..255); the skill's name (selector 2: a string offset, written into the event's string table); `change_age`'s cap in years (0..120); else 0 |

### 2.6 Link record (8 bytes): what an outcome answers

| Offset | Type | Field |
|---|---|---|
| 0 | u32 | the approach's id (string) |
| 4 | u32 | weight for that approach (1..1000) |

An outcome may answer several approaches; an approach with no outcome answering it in the file is never used.

### 2.7 Placeholders in texts

The Custom Island Event placeholders (cie-v6-binary.md 5), with a slot NAME as the role: `(subject)`, `(friend.he/she)`,
`(elder.Name)`, ... No pools, no inline picks. A text names only slots its own piece declares.

## 3. The composer (run time; the Python twin must follow it exactly)

Every roll is the game's own random routine, `random_below(n)` (`ce_random_below`: 0 .. n-1; no roll when n is at
most 1), in exactly this order. "Weighted" means: total = the sum of the candidates' weights, r = random_below(total),
the first candidate (in file order) whose running sum passes r.

Inputs: the game; the ticked filters (bits); the 61-villager gate (deadly pieces left out below 61 villagers, the
natural draw only; No Safeguards lifts it); Content Notes on or off; the village (for casting).

A piece is USABLE when its games mask has the game, its filters meet no ticked filter, it is not DEADLY while the gate
holds, and (flags bit 1) the game is New Believers or the flag is clear.

1. **Setup.** Candidates: the file's usable setups. Weighted pick (roll 1). None: the file gives nothing.
2. **Approaches.** n = 2 + random_below(3) (roll 2, always made). Then n times: the candidates are the usable
   approaches whose family EQUALS the setup's, not picked yet, compatible (2.3) with every piece chosen so far, and
   answered by at least one usable outcome in the file; pick one weighted (one roll). No candidate: stop early. Fewer
   than 2 picked: the composition is rejected.
3. **Outcomes,** for each approach in the order picked: m = 1 + random_below(3) (one roll, always made). Then m times:
   the candidates are the usable outcomes linking it (2.6), not picked for it yet, compatible with the setup and that
   approach; pick one weighted by its link weight (one roll). No candidate: stop early.
4. **Flavour.** random_below(100) < 50 (one roll): pick a flavour line of the setup's mood, usable and compatible with
   every piece chosen so far (the outcomes included), weighted (one roll; none: skipped, no roll).
5. **Frame.** random_below(100) < 30 (one roll): pick a frame the same way, any mood (one roll; none: skipped).
6. **Keep and cast.** An outcome is PLAIN when every slot it declares is a needed (not optional) slot of the setup,
   of its own approach, of the flavour line or of the frame. An approach is kept when at least one of its outcomes is
   plain; fewer than 2 kept: the composition is rejected (no roll). The roles are merged in this order: the setup, the
   kept approaches (in pick order), the flavour, the frame, then the kept approaches' outcomes; a role an outcome adds
   is optional, and that outcome's branch child holds only when its optional roles are cast (a `role` condition), so
   an outcome whose villagers cannot be cast is left out at run time and a plain one is always there. The engine then
   casts it as any event (STRICT, the protected villagers, No Safeguards and its Heathen/totem rules, Guardians of Isola
   untouched); a cast that fails rejects the composition.
7. **Graph.** The engine writes a version 6 `.cieg` in memory:
   - start: a popup with the flavour line (when picked), the setup's text and the frame line (when picked), each its
     own paragraph; with Content Notes on and any note bit in the composed pieces, "Content note: <labels>" first;
   - a question with one answer per kept approach (the approach's label), in pick order;
   - each answer: a popup with the approach's text (none: a silent branch) whose children are its outcomes
     (weights: the link weights; the cond: its optional roles cast; the guard: `harmable` for the roles it harms
     that are kept from the protected villagers);
   - each outcome: a popup appended to the approach's as its own paragraph (a new popup after a silent branch), with
     its text and its effects (the local slots mapped to the composed roles), auto lines when its flag says so;
   - the title: the setup's label as written (it must pass the engine's title check);
   - the content note's labels are those of the pieces the event holds (not a dropped approach's), in
     `NOTE_LABELS` order, joined by ", ";
   - the collection block (header +90): `{"procedural":"<group>/<setup id>"}`, so the engine's collection rules
     (random food and tech sizes from 61 villagers) apply.
   The engine's own file checks (`cg_load`) run on it; a graph that fails is discarded.
8. **Retries.** A rejected composition starts again at step 1 with that setup left out, up to 8 tries a file; then
   the draw moves to another file (the split-file draw), and in the end to the game's own event. With the setup fixed
   (Pick Island Event, the library) the 8 tries keep that setup.

## 4. In the draw

Procedural events are one more source in the natural draw: each `<group>.pcb` counts as a file whose weight is
its usable setups' count (the static and living files keep theirs), so the owner's equal odds per event hold among
the sources; in the draw's one weighted pick they come after More Island Events' events and the collection's files,
in the order the folder lists them. Pick Island Event and the library list each usable setup as one row
("<setup title> (varies)"; the library's path `?pieces:<group>/<setup id>`). Pick Island Event's "possible now"
check composes with a private generator, never the game's own rolls; bought, the row is composed as above with the
game's rolls of that moment (Pick: STRICT; the library: its PREFER cast). Nothing about a composed event is kept
except the run file every queued event has (its `.cieg` bytes), so a quit and a restore resume it as any other.

Test build: `VvfpStoryProbeProceduralFile(data, size)` sets the one pieces file, and
`VvfpStoryProbeProceduralCompose(game, fixed_setup, gate, notes, out, cap)` composes once with the rolls
`VvfpStoryProbeSetRolls` gives and returns the `.cieg` (before casting): the Python twin's pin.

## 5. What the data side produces

1. The piece files (this format), split by topic, from the owner's sources, with every tag above.
2. The Python twin of section 3 (same rolls, same order), pinned against the engine by tests.
3. A validator that composes many events per game with the twin and checks each with `src/vv_cie_graph.py` (fit,
   text, title case, the owner's four blocks, the content rules); pairs that fail become NEVER WITH tags.
4. The content filter and note bits of every piece (`src/vv_event_content.py`'s tagging on each piece's text and
   effects).
