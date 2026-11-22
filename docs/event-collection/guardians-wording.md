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
| `hc1_routes` | pool TASK item (L297; a twin item shown only with the patch) | between believers, | between the faithful, |
| `hc2_pleas` | pool TASK item (L297; a twin item shown only with the patch) | between believers, | between the faithful, |
| `hc3_disasters` | pool TASK item (L297; a twin item shown only with the patch) | between believers, | between the faithful, |
| `hc4_noises` | pool TASK item (L297; a twin item shown only with the patch) | between believers, | between the faithful, |
| `hc5_victories` | pool TASK item (L297; a twin item shown only with the patch) | between believers, | between the faithful, |
| `hc6_sabotage` | pool TASK item (L297; a twin item shown only with the patch) | between believers, | between the faithful, |
| `lcb07_song_stars` | Pick Island Event description | a believer each | a villager of faith each |
| `lcf22_where_does_faith` | Pick Island Event description | a believer debate | a person of faith debate |
| `lcf25_atheist_ceremony` | choice (setup, to o2; a twin choice shown only with the patch) | Let a Believer Lead | Let the Faithful Lead |
| `lcf25_atheist_ceremony` | page (o1) | The believers add | The faithful add |
| `lcf25_atheist_ceremony` | Pick Island Event description | let a believer lead | let the faithful lead |
| `lcf29_child_asks` | Pick Island Event description | a believer why | a person of faith why |

The owner's approved wordings of 2026-11-19 are the last twelve rows (the Harshest Critic's TASK item in all six of its
files, lcb07, lcf22, lcf25 and lcf29). A pool item, like a choice, keeps its text shown only without the patch and gets
a twin with the same condition shown only with it (`{"all": [its condition, {"patch": "guardians_of_isola"}]}`); the
game draws among the items whose condition holds, so exactly one of the two is ever in the draw.

Grammar (the owner, 2026-11-16: "fix any grammar mistakes automatically"): every replaced sentence was read whole for
verb agreement, articles and capitals. Each keeps its number ("The faithful maintain", "Some of the faithful
question", "A villager of faith finds", "a tribe member sees", "Two villagers of faith disagree"), so none needed a
further fix.

The Living Event Engine's bank (the mixer's variants, `src/vv_living_mixer.py` GUARDIANS_BANK): LE-BEL seed
"Two believers disagree about the meaning of a ritual." -> "Two villagers of faith disagree about the meaning of a
ritual." (its page and its New Believers row's Guardians description) and the choice "Ask a skeptic and a believer
to compare interpretations." -> "Ask a skeptic and a villager of faith to compare interpretations." (a choice shown
only without the patch, and its twin only with it). The MIX title "TWO BELIEVERS DISAGREE ..." is never shown.

## No Guardians as the villagers' name (the owner, 2026-11-19)

The owner: "don't use 'Guardians' to refer to our villagers. You can use it in other contexts like 'stone guardian,
guardian of a child, guardians of the village' etc". No event text (title, page, choice, pool item, Pick Island Event
description, and every Guardians of Isola Rewrite form above) calls the tribe, the believers or the villagers "the
Guardians"; no pair above makes such a text. Every event text across the collection, More Island Events and Story
Upgrades was read for "guardian"; only these three events used it as the villagers' name, and each is changed in every
game and with or without the patch (a title through `docs/event-collection/owner-title-changes.md`, its two new
titles approved by the owner on 2026-11-19; a page through `scripts/food_tech_additions.py` TEXT_EDITS):

| Event | Where | Before | After |
|---|---|---|---|
| blf26_isolan_feast | page (setup) | The village is holding a feast for the Guardians, | The village is holding a feast for the whole tribe, |
| blf26_isolan_feast | Pick Island Event description (and its Guardians form) | At the feast for the Guardians, | At a great feast, |
| vv5_the_guardians_disagreement | title (and its question page's name) | The Guardians' Disagreement | The Villagers' Disagreement |
| lvauth18_guardians | title (shown only with the patch) | The Guardians' Council | The Two Communities' Council |

(The ids here are not in backticks: these rows are not Guardians of Isola Rewrite pairs.) Every other "guardian" in
the events is an ordinary use the owner keeps: a child's guardian(s), a pet's guardian, a guardian spirit, sea or
unseen guardians, the river guardians (lch27, lcj19), the guardian dance (lcc41), the carved Ugliest Guardian (V17),
the Fierce Little Guardian (V27-31), the Harshest Critic's "guardian of the nursery" and similar job names, a
guardian in a story (my066, my069, my093, my102) and the machine guardians (hz079). `tests/test_no_guardians_name.py`
fails if any event text uses Guardian(s) as a name for the people.

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
| (what a role needs) ..., a believer | ..., a tribe member |
| (what an event needs) at least N believers / fewer than N believers | at least N tribe members / fewer than N tribe members |
| "..." can not happen in this village right now: it needs at least N believers. | ... it needs at least N tribe members. |
| (an outcome's automatic line, "status" and "apostasy") (Name) becomes a Heathen. | (Name) becomes an Isolan. |
| (the Island Events log) (Name) became a Heathen. | (Name) became an Isolan. |

The last five rows (v1.35.98) are the faction sense (the villagers an event can cast, as against the Isolans):
"believers" -> "tribe members", "a believer" -> "a tribe member", "a Heathen" -> "an Isolan" (`cg_believers_word`,
`cg_auto_guardians`).

## Procedural events (v1.35.98)

A procedural event (story_procedural.inc) is composed from pieces cut from the events above. Until v1.35.98 every
piece kept the patch-off wording, so with the patch New Believers' composed events still said Heathen and believer(s).
Now each piece New Believers can draw that says one of these words carries its Guardians form (VPCB piece flag 0x20:
the form is the string right after the text and after the label): the text with its own event's pairs above made (a
Living Engine bank piece: the bank's pairs), nothing else changed. `scripts/procedural_pieces.py` (guardians_forms)
writes them and fails the build if a piece is left with such a word, except one awaiting the owner:

- s027_isolan_fire's procedural setup (its own shorter wording, not the collection page): "...and sits on the very
  edge of the believers' circle with (isolan.his/her) hands held out to the warmth." No approved pair covers "the
  believers' circle"; proposed (as "the believers' fire" -> "the faithful's fire"): "the faithful's circle". Until
  the owner answers it shows as written.

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
| `s027_isolan_fire` | page (ask) | The believers have crowded round the big cooking fire with the stew pot steaming in the middle, and everyone is wrapped up to the eyes. | The faithful have crowded round the big cooking fire with the stew pot steaming in the middle, and everyone is wrapped up to the eyes. |
| `s027_isolan_fire` | page (ask) | Should (friend) offer the soaked Isolan a bowl of stew, or ask (subject.him/her) to leave the believers' fire? | Should (friend) offer the soaked Isolan a bowl of stew, or ask (subject.him/her) to leave the tribe's fire? |
| `s027_isolan_fire` | page (c1o2) | About the old ways of the island, from before the believers came. | About the old ways of the island, from before the faithful came. |
| `s027_isolan_fire` | page (c2) | "This is the believers' fire," (friend.he/she) says, not unkindly, but not kindly either. | "This is the faithful's fire," (friend.he/she) says, not unkindly, but not kindly either. |
| `s070_isolan_healer` | page (ask) | (friend) has been sick for days now, and the believers' healers are worried. | (friend) has been sick for days now, and the faithful's healers are worried. |
| `s070_isolan_healer` | page (ask) | "If you'll let me." Isolans and believers have kept apart for a long time, and some of the healers look doubtful. | "If you'll let me." Isolans and tribe members have kept apart for a long time, and some of the healers look doubtful. |
| `s070_isolan_healer` | page (c1o1) | The believers' healers have a great many questions for (subject). | The faithful's healers have a great many questions for (subject). |
| `s070_isolan_healer` | page (c1o2) | The believers' healers stay too, and watch everything (subject.he/she) does: how (subject.he/she) holds a wrist to count the heartbeat, which leaves (subject.he/she) uses for what, how (subject.he/she) mixes them. | The faithful's healers stay too, and watch everything (subject.he/she) does: how (subject.he/she) holds a wrist to count the heartbeat, which leaves (subject.he/she) uses for what, how (subject.he/she) mixes them. |
| `s070_isolan_healer` | page (c2) | (healer), the oldest of the believers' healers, steps forward. | (healer), the oldest of the faithful's healers, steps forward. |
| `s070_isolan_healer` | Pick Island Event description | Another villager has been sick for days now, and the believers' healers are worried. | Another villager has been sick for days now, and the faithful's healers are worried. |
<!-- end of GO Guardians wording -->

## More Island Events

<!-- MIE Guardians wording: written by scripts/go_events/gen_mie.py -->
The owner's More Island Events file (2026-11-16): the owner's own Guardians of Isola form.

| Event | Where | Before | After |
|---|---|---|---|
| `mie_adventurer` | page (lost2_vv5) | heathens' tribe | Isolans' tribe |
<!-- end of MIE Guardians wording -->
