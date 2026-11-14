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
