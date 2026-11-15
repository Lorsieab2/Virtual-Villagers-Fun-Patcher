# Isola Grand Event Collection: the owner's title changes

The owner renamed these events in their copy of "New Island Events - Titles and Descriptions.txt" (2026-11-14). Each
new title is the owner's own text and replaces the source heading's title everywhere the event's title shows, in
every game the event is in. `scripts/collection_check.py` accepts a title equal to its row's "New title" here in place
of the source heading (`collection.title_src`), and `scripts/collection_manifest.py` writes the new title into
`data/event_collection/manifest.json` (the source's own words stay there as `source_title`).

The table is read by `scripts/collection_lib.py owner_titles()`: one row per event, the id in backticks.

| Id | Old title (the source heading) | New title | Date | By |
|---|---|---|---|---|
| `all_scholasticon` | The Grand Isolan Scholasticon | The Grand Isolan Decathlon | 2026-11-14 | owner |
| `all_great_appointment` | The Great Appointment Scandal | The Appointment Scandal | 2026-11-14 | owner |
| `all_panel_standards` | The Panel of Impossible Standards | The Crafty Inspector | 2026-11-14 | owner |
| `vv1_v14_24_boy_who` | The Boy Who Understood Grief | The Griever | 2026-11-14 | owner |
| `vv1_v14_25_child_who` | The Child Who Refused to Be an Adult | The Wise Child | 2026-11-14 | owner |
| `vv1_v14_16_child_who` | The Child Who Settled an Argument | The Mediator | 2026-11-14 | owner |
| `all_v22_3_potion` | The Great Isolan Potion-Making Trials | The Great Isolan Potion-Making Trial | 2026-11-14 | owner |
| `all_v22_2_strength` | The Great Isolan Strength Trials | A Test of Strength | 2026-11-14 | owner |
| `vv2_hospitals_most_difficult` | The Hospital's Most Difficult Patient | The Most Difficult Patient | 2026-11-14 | owner |
| `all_v18_01_warriors` | The Warriors' Tournament | The Warriors' Duel | 2026-11-14 | owner |
| `vv3_weather_dance_that_went` | The Weather Dance That Went Wrong | The Wacky Weather Dance | 2026-11-14 | owner |
| `vv5_convert_who_missed_home` | The Convert Who Missed Home | The Homesick Convert | 2026-11-14 | owner |

Notes:

- The owner's list holds 13 changed lines: "The Grand Isolan Scholasticon" is renamed on two lines of it (the universal
  events and the V17 festival list), both `all_scholasticon`.
- "The Grand Isolan Decathlon" (`all_scholasticon`) sits beside the V18 contest "The Isolan Decathlon"
  (`all_v18_decathlon`). Both are kept as the owner wrote them.
- With Guardians of Isola Rewrite installed, New Believers shows "The Homesick Convert" as "The Homesick Newcomer"
  (a title variant; [guardians-wording.md](guardians-wording.md)).

## OPEN owner questions: the same title on two different events (Companion Anthology, 2026-11-14)

Nothing below is renamed. Each pair is two different events of the Companion Anthology
(`docs/more-island-events/Isola_COMPLETE_Master_Companion_Anthology_749_Events.txt`, its own line numbers) with the
same title, so Pick Island Event and the library would list the same name twice. The owner decides: rename one (or
both), or keep both titles. A rename the owner gives goes in the table above, with its date; until then each event
keeps its source heading. These rows have no date, so `owner_titles()` does not read them.

| Title | First event | Second event | How alike |
|---|---|---|---|
| The Gods' Silence | `c5ev048_gods_silence` (Vol 1 Part 5 V048, L3669) | `lbl112_gods_silence` (The Lives Between Legends 112, L5276) | the same premise, the outcomes reworded (the closest pair in the anthology) |
| The Shared River | `c5ev046_shared_river` (V046, L3655) | `lbl110_shared_river` (Lives Between Legends 110, L5250) | the same premise, different outcomes |
| The Quiet Leader | `c5ev033_quiet_leader` (V033, L3560) | `fwk049_quiet_leader` (The Four Ways of Knowing 049, L5932) | a similar idea |
| The Night Watch | `c5b058_night_watch` (Vol 1 Part 2 058, L1642) | `c5c018_night_watch` (Vol 1 Part 3 018, L2251) | different plots |
| The Unsent Apology | `c5b024_unsent_apology` (Part 2 024, L1345) | `sss056_unsent_apology` (Stone, Spirit, Strangers 056, L6639) | a similar theme |
| The Family Resemblance | `c5b035_resemblance` (Part 2 035, L1439) | `c5c032_same_gesture` (Part 3 032, L2423) | different plots |
| The Forgotten Name | `c5b021_forgotten_name` (Part 2 021, L1317) | `fwk034_forgotten_name` (Four Ways of Knowing 034, L5780) | different plots |

Also OPEN: the same title in the Companion Anthology and in the Isola Grand Event Collection (the V28 source's own line
numbers on the left). Some are near the same premise (marked).

| Title | Grand collection event | Companion event | How alike |
|---|---|---|---|
| The False Alarm | `all_v23_5_false_alarm` (L10077) | `c5dn054_false_alarm` (L3162) | different plots |
| The Cruel Joke | `all_v27_08_cruel_joke` (L10545) | `lbl029_cruel_joke` (L4169) | similar: a child or teen mocks another's voice |
| The Midnight Raft | `all_v27_13_raft` (L10585) | `lbl026_midnight_raft` (L4130) | near the same premise: teenagers launch a homemade raft after dark |
| The Dangerous Proof | `all_v27_14_proof` (L10593) | `lbl082_dangerous_proof` (L4874) | similar: a teen tries to prove a legend |
| The Public Embarrassment | `all_v27_15_embarrass` (L10601) | `lbl017_public` (L4009) | different plots |
| The Special Friend | `all_v27_42_special` (L10817) | `lbl014_special_friend` (L3970) | near the same premise: two inseparable villagers |

## OPEN owner question: "The Unpopular Chief" outside The Secret City (Companion Anthology, 2026-11-14)

The Lives Between Legends 086 (`lbl086_unpopular_chief`, companion L4930) is in all five games, but only The Secret
City has a Chief; the scene itself says "A competent leader is disliked for a harsh manner." (no "Chief" in its text,
so nothing becomes `{@chief}`). Built now with a title variant (cie-v6-binary.md 18): The Secret City shows the source
heading "The Unpopular Chief"; A New Home, The Lost Children, The Tree of Life and New Believers show "The Unpopular
Leader" (the lead's wording, as `{@chief}` reads "the village leader" outside The Secret City). The owner decides:
keep "The Unpopular Leader", choose another word, or show "The Unpopular Chief" in every game. No date, so
`owner_titles()` does not read this row.

| Id | Source title | Title outside The Secret City (built) | Status |
|---|---|---|---|
| `lbl086_unpopular_chief` | The Unpopular Chief | The Unpopular Leader | OPEN |
