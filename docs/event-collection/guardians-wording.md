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
| `c5ev060_how_did_we_get` | page (q5, New Believers' accounts) | among the Heathens | among the Isolans |

The whole sentences, as New Believers shows them with the patch:

- The Homesick Newcomer: "An Isolan who recently came to live with our tribe is seen sitting alone, staring toward a
  familiar part of the island."
- Its Pick Island Event line: "A villager who recently came to live with our tribe sits alone, missing home: invite
  them to talk, or arrange a shared activity."
- The Feast of Two Traditions: "An Isolan family who came to live with our tribe and a village family each offer to
  host a feast, but neither agrees on how it should be prepared."
- How Did We Get Here? (companion V060), New Believers' third account: "Perhaps someone among the Isolans invited
  or warned them to come."
- The Little Things They Remember: "An Isolan-born villager and an Isolan visitor meet near the edge of the village.
  They recognize each other from years ago."

Every other collection event New Believers shows already says "Isolan" (the source's own word from the Guardians of
Harmony naming on) and needs no change.

<!-- LV-B Guardians rows: written by scripts/living_vols/gen_lv_b.py -->

## The Living Event Engine's Colors, Masks, Peoples and Choice (LV-B)

Its VV5 ONLY events say "Heathen". The source's own rule for each ("GUARDIANS OF ISOLA VARIANT:
Replace Heathens with the other Isolan tribe") is made with the pairs below, in this order, in every text
the event shows: the title, the pages, a label (PEOPLES-08's "Invite an Isolan to visit instead.", a
choice shown only with the patch) and the Pick Island Event sentence. No event says "convert". The
masks stay (narrative only); AUTH-17 The Masked Adviser is vanilla New Believers only, and AUTH-18 The
Guardians' Council shows only with the patch.

| Event | Where | Before | After |
|---|---|---|---|
| `lvppl06_mask_felt_safe` | its texts | Heathens | Isolans |
| `lvppl08_among_heathens` | its texts | a Heathen | an Isolan |
| `lvppl08_among_heathens` | its texts | Heathens | Isolans |
| `lvppl09_friend_across` | its texts | a Heathen | an Isolan |
| `lvppl11_heathen_helped` | its texts | A Heathen | An Isolan |
| `lvppl11_heathen_helped` | its texts | Heathen | Isolan |
| `lvppl12_tribe_someone` | its texts | A Heathen | An Isolan |
| `lvppl23_quiet_border` | its texts | Heathens | Isolans |
| `lvppl32_family_both` | its texts | Heathens | Isolans |
| `lvppl34_word_heathen` | its texts | Heathen | Isolan |

<!-- end of the LV-B Guardians rows -->

## Believers (the owner, 2026-11-16)

The owner: with Guardians of Isola Rewrite, the new events' "believer(s)" are reworded too, as Heathen -> Isolan:
"the believers" -> "the tribe", "a believer" -> "a tribe member" / "one of the tribe", and "the newcomers" where the
text means the arrivals as against the Isolans, each sentence as it reads best. Where "believer" is the VV5 faction
(the tribe as against the Isolans), it becomes the tribe; where it means a villager who believes as against a
skeptic, a doubter or someone who "does not believe in blessings" (most of these lines), "a tribe member" would
lose the sense (every villager is one), so it becomes "a villager of faith" / "a person of faith" / "the faithful".
Without the patch, and in every other game, the words are unchanged. `scripts/food_tech_additions.py`
(apply_guardians) writes each event's Guardians form from these rows; check j reads them.

| Event | Where | Before | After |
|---|---|---|---|
| `blf07_blessing_canoe` | Pick Island Event description (kept within its 130 characters) | A believer asks to bless the new canoe of a villager | A villager of faith asks to bless the canoe of someone |
| `blf07_blessing_canoe` | page (setup) | a believer, has asked | a villager of faith, has asked |
| `blf26_isolan_feast` | Pick Island Event description (the tribe as against the Isolans) | a believer sees an Isolan | a tribe member sees an Isolan |
| `blf27_songs_across` | Pick Island Event description (the tribe as against the Isolans) | a believer hears an Isolan | a tribe member hears an Isolan |
| `blf38_mask_carver` | page (o1) | Does that bother the believers? | Does that bother the faithful? |
| `blf45_faith_nobody` | description and page (setup) | is a believer | is a person of faith |
| `blf50_around_one_fire` | Pick Island Event description | sit believers, doubters | sit the faithful, doubters |
| `lvauth22_chief_false` | page (d1) | Believers and skeptics | The faithful and skeptics |
| `lvauth27_spiritual` | page (a2) | Some believers question | Some of the faithful question |
| `lvuns15_mask_forest` | page (b2) | disappointing a believer | disappointing a villager of faith |
| `lvuns21_gods_need` | page (a2) | A believer finds | A villager of faith finds |
| `lvuns23_silence_after` | description and page (setup) | a believer asks | a villager of faith asks |
| `lvuns23_silence_after` | page (a1) | The believer finds | The villager of faith finds |
| `lvuns23_silence_after` | page (b2) | The believer asks | The villager of faith asks |
| `lvuns31_price_legend` | page (c2) | Believers maintain | The faithful maintain |
| `lvuns34_god_may_have` | page (b1) | Believers continue | The faithful continue |
| `lvuns37_unproven` | page (c2) | A believer explains | A villager of faith explains |

Grammar (the owner, 2026-11-16: "fix any grammar mistakes automatically"): every replaced sentence was read whole for
verb agreement, articles and capitals. Each keeps its number ("The faithful maintain", "Some of the faithful
question", "A villager of faith finds", "a tribe member sees", "Two villagers of faith disagree"), so none needed a
further fix.

The Living Event Engine's bank (the mixer's variants, `src/vv_living_mixer.py` GUARDIANS_BANK): LE-BEL seed
"Two believers disagree about the meaning of a ritual." -> "Two villagers of faith disagree about the meaning of a
ritual." (its page and its New Believers row's Guardians description) and the choice "Ask a skeptic and a believer
to compare interpretations." -> "Ask a skeptic and a villager of faith to compare interpretations." (a choice shown
only without the patch, and its twin only with it). The MIX title "TWO BELIEVERS DISAGREE ..." is never shown.

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

## The GO files (rewritten and balance events)

<!-- GO Guardians wording: written by scripts/go_events/gen_go.py -->
The owner's GO files (2026-11-16): each sentence New Believers shows with the patch (docs/event-collection/guardians-wording.md "Believers": by sense).

| Event | Where | Before | After |
|---|---|---|---|
<!-- end of GO Guardians wording -->
