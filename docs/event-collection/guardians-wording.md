# New Believers with Guardians of Isola Rewrite: the collection's and More Island Events' wording

The owner (2026-11-14), for New Believers with Guardians of Isola Rewrite (`vv5_guardians_of_isola_rewrite`)
installed: "any mention of 'heathens' should be retitled 'Isolans', any mention of 'converts, conversion' etc should
be changed to 'coming to live with our tribe' or something neutral like that."

The rules, keeping the case: Heathen -> Isolan, Heathens -> Isolans, Heathen-born -> Isolan-born; convert (a person)
-> newcomer, converts -> newcomers; converted / conversion (a Heathen joining the believers) -> "came to live with our
tribe", "coming to live with our tribe" or "joining our tribe", written to fit the sentence. Without the patch every
text below is unchanged.

Every before / after pair is listed here for the owner. Each sentence that holds one of these words was checked by
hand so the result reads naturally.

## The Isola Grand Event Collection

`scripts/collection_check.py` (check j GUARDIANS) reads this table: an event's Guardians form of a text is the text
with its rows' pairs made. Any text New Believers can show that says Heathen or convert must have that form (a title
variant, a page variant, a description variant with `{"patch": "guardians_of_isola"}`), or the check fails.

| Event | Where | Before | After |
|---|---|---|---|
| `vv5_convert_who_missed_home` | title | The Homesick Convert | The Homesick Newcomer |
| `vv5_convert_who_missed_home` | page (question) | A recently converted Isolan | An Isolan who recently came to live with our tribe |
| `vv5_convert_who_missed_home` | Pick Island Event description | A recently converted villager | A villager who recently came to live with our tribe |
| `vv5_feast_of_two_traditions` | page (question) | A converted Isolan family | An Isolan family who came to live with our tribe |
| `vv5_little_things_remember` | pages (intro, intro_parent) | A former Heathen-born villager | An Isolan-born villager |

The whole sentences, as New Believers shows them with the patch:

- The Homesick Newcomer: "An Isolan who recently came to live with our tribe is seen sitting alone, staring toward a
  familiar part of the island."
- Its Pick Island Event line: "A villager who recently came to live with our tribe sits alone, missing home: invite
  them to talk, or arrange a shared activity."
- The Feast of Two Traditions: "An Isolan family who came to live with our tribe and a village family each offer to
  host a feast, but neither agrees on how it should be prepared."
- The Little Things They Remember: "An Isolan-born villager and an Isolan visitor meet near the edge of the village.
  They recognize each other from years ago."

Every other collection event New Believers shows already says "Isolan" (the source's own word from the Guardians of
Harmony naming on) and needs no change.

## More Island Events (New Believers)

These switch by the game's own "left the tribe" words, as The Aspiring Adventurer's "heathens' tribe" line already did
(`native/vvfp_more_island_events/adv_vv345.inc` `vv5_joins_key`).

| Where | Before | After |
|---|---|---|
| The Aspiring Adventurer, the hero joins the other tribe (existing) | ...seems to have joined the heathens' tribe. | ...seems to have joined the Isolans' tribe. |
| Pick Island Event, The Remembrance Ceremony: what it needs | at least one grave and The Last Heathen achieved (every Heathen converted) | at least one grave and A Family Reunited achieved (every Isolan came to live with our tribe) |
| The Remembrance Ceremony, the Island Events log | Of them at the old Heathen hovel: | Of them at the old Isolan hovel: |

"A Family Reunited" is the name Guardians of Isola Rewrite gives the game's own "The Last Heathen" puzzle
(`data/guardians_of_isola/new/Assets/sm.xml`, `eTipPuzzleConvertLastHeathenComplete`).

## The branching engine's own words (Pick Island Event, New Believers)

What a collection event needs, and the warning before a purchase, name the villagers New Believers' events keep out
(`native/vvfp_story_upgrades/story_graph.inc` `cg_role_words`, `cg_risk`):

| Before | After |
|---|---|
| not a chief, the Retired Chief or a puzzle's Heathen | not a chief, the Retired Chief or a puzzle's Isolan |
| This event may choose a chief, the Retired Chief or a puzzle's Heathen, whom the game's story needs. | This event may choose a chief, the Retired Chief or a puzzle's Isolan, whom the game's story needs. |

## Judgement calls for the owner

- "A former Heathen-born villager" became "An Isolan-born villager": "A former Isolan-born villager" does not read
  naturally, since the villager was born among the Isolans and still was.
- "The Homesick Convert" became "The Homesick Newcomer" (the owner's rule for the noun).
- The game's own island events (Pick Island Event's list of New Believers' stock events, such as "The Heathen Toy"
  and "The Defector") are not new text and are not changed here.
