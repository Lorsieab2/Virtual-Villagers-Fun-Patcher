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
| `wd14_what_melon_doing` | What's a Melon Doing in the Middle of the Path? | What's a Melon Doing in the Path? | 2026-11-15 | lead |
| `wd40_what_walking` | What's a Walking Stick Doing in the Middle of the Beach? | What's a Walking Stick Doing on the Beach? | 2026-11-15 | lead |

The two `lead` rows are NOT the owner's: the drafts' titles do not fit a game's title box (WD-14: 47 characters, The
Lost Children shows 46; WD-40: 56, every game shows at most 47), so the event cannot ship under them. The shortest
change is proposed here for the owner's approval; the owner's own title replaces it whenever the owner gives one.

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

## The 500 Tiny Island Moments (group D, 2026-11-15)

The owner's answers in "Completed Open Questions - Isola Events v1.35.97.txt" (frozen as source `openq97`):
Question 1, option A (125 moments, each opening with its four endings as equal random alternatives) and
Question 2, option A (one title per opening, T001-T125, written there). The old title is the first of the four
entries' "Title:" lines (`Isola_500_Tiny_Island_Moments.txt`); the new one is the owner's.

| Id | Old title (the source heading) | New title | Date | By |
|---|---|---|---|---|
| `tim001_leaf_lantern` | Lanterns: A Quiet Moment | The Leaf Lantern | 2026-11-15 | owner |
| `tim002_shells` | Lanterns 2: A Quiet Moment | Shells in the Lamplight | 2026-11-15 | owner |
| `tim003_mended_lantern` | Lanterns 3: A Quiet Moment | A Mended Lantern | 2026-11-15 | owner |
| `tim004_patterns_light` | Lanterns 4: A Quiet Moment | Patterns of Light | 2026-11-15 | owner |
| `tim005_careful_lantern` | Lanterns 5: A Quiet Moment | The Careful Lantern Bearer | 2026-11-15 | owner |
| `tim006_sibling_fleet` | Leaf Boats: A Quiet Moment | The Sibling Fleet | 2026-11-15 | owner |
| `tim007_petal_sail` | Leaf Boats 2: A Quiet Moment | A Petal Sail | 2026-11-15 | owner |
| `tim008_puddle_regatta` | Leaf Boats 3: A Quiet Moment | The Puddle Regatta | 2026-11-15 | owner |
| `tim009_folding_leaf` | Leaf Boats 4: A Quiet Moment | Folding Leaf Boats | 2026-11-15 | owner |
| `tim010_boats_bound` | Leaf Boats 5: A Quiet Moment | Boats Bound for Shore | 2026-11-15 | owner |
| `tim011_rain_roof` | Rain: A Quiet Moment | Rain on the Roof | 2026-11-15 | owner |
| `tim012_shelter` | Rain 2: A Quiet Moment | Shelter Together | 2026-11-15 | owner |
| `tim013_raindrop_races` | Rain 3: A Quiet Moment | Raindrop Races | 2026-11-15 | owner |
| `tim014_thunder_beyond` | Rain 4: A Quiet Moment | Thunder Beyond the Hut | 2026-11-15 | owner |
| `tim015_crafts_before` | Rain 5: A Quiet Moment | Crafts Before the Storm | 2026-11-15 | owner |
| `tim016_herbs_stew` | Cooking: A Quiet Moment | Herbs in the Stew | 2026-11-15 | owner |
| `tim017_roasted_root` | Cooking 2: A Quiet Moment | The Roasted Root Debate | 2026-11-15 | owner |
| `tim018_turn_stirring` | Cooking 3: A Quiet Moment | A Turn at Stirring | 2026-11-15 | owner |
| `tim019_taste_childhood` | Cooking 4: A Quiet Moment | A Taste of Childhood | 2026-11-15 | owner |
| `tim020_new_recipe` | Cooking 5: A Quiet Moment | The New Recipe | 2026-11-15 | owner |
| `tim021_bubbles_mixture` | Potions: A Quiet Moment | Bubbles in the Mixture | 2026-11-15 | owner |
| `tim022_changing` | Potions 2: A Quiet Moment | The Changing Infusion | 2026-11-15 | owner |
| `tim023_scents` | Potions 3: A Quiet Moment | Scents of Discovery | 2026-11-15 | owner |
| `tim024_careful_measure` | Potions 4: A Quiet Moment | A Careful Measure | 2026-11-15 | owner |
| `tim025_settling_shade` | Potions 5: A Quiet Moment | Settling in the Shade | 2026-11-15 | owner |
| `tim026_mending` | Nets: A Quiet Moment | Mending the Butterfly Net | 2026-11-15 | owner |
| `tim027_gentle_grip` | Nets 2: A Quiet Moment | The Gentle Grip | 2026-11-15 | owner |
| `tim028_butterflies` | Nets 3: A Quiet Moment | Butterflies Among Flowers | 2026-11-15 | owner |
| `tim029_wings_without` | Nets 4: A Quiet Moment | Wings Without Touching | 2026-11-15 | owner |
| `tim030_closer_look` | Nets 5: A Quiet Moment | A Closer Look | 2026-11-15 | owner |
| `tim031_decorations` | Holidays: A Quiet Moment | Decorations for the Holiday | 2026-11-15 | owner |
| `tim032_rehearsing_song` | Holidays 2: A Quiet Moment | Rehearsing the Song | 2026-11-15 | owner |
| `tim033_seasonal_table` | Holidays 3: A Quiet Moment | The Seasonal Table | 2026-11-15 | owner |
| `tim034_sweeping` | Holidays 4: A Quiet Moment | Sweeping for the Festival | 2026-11-15 | owner |
| `tim035_holidays` | Holidays 5: A Quiet Moment | Holidays Remembered | 2026-11-15 | owner |
| `tim036_leaf_wrapped` | Gifts: A Quiet Moment | The Leaf-Wrapped Gift | 2026-11-15 | owner |
| `tim037_shell_parent` | Gifts 2: A Quiet Moment | A Shell for a Parent | 2026-11-15 | owner |
| `tim038_bracelets` | Gifts 3: A Quiet Moment | Bracelets Between Friends | 2026-11-15 | owner |
| `tim039_apprentice_gift` | Gifts 4: A Quiet Moment | The Apprentice's Gift | 2026-11-15 | owner |
| `tim040_fruit_neighbor` | Gifts 5: A Quiet Moment | Fruit for a Neighbor | 2026-11-15 | owner |
| `tim041_basket_promise` | Promises: A Quiet Moment | The Basket Promise | 2026-11-15 | owner |
| `tim042_pact_between` | Promises 2: A Quiet Moment | A Pact Between Siblings | 2026-11-15 | owner |
| `tim043_right_time` | Promises 3: A Quiet Moment | Right on Time | 2026-11-15 | owner |
| `tim044_forgotten_visit` | Promises 4: A Quiet Moment | The Forgotten Visit | 2026-11-15 | owner |
| `tim045_shared` | Promises 5: A Quiet Moment | A Shared Responsibility | 2026-11-15 | owner |
| `tim046_splicing_rope` | Elders Teaching Skills: A Quiet Moment | Splicing the Rope | 2026-11-15 | owner |
| `tim047_grandparent_net` | Elders Teaching Skills 2: A Quiet Moment | The Grandparent's Net | 2026-11-15 | owner |
| `tim048_choosing_ripe` | Elders Teaching Skills 3: A Quiet Moment | Choosing Ripe Fruit | 2026-11-15 | owner |
| `tim049_difficult_weave` | Elders Teaching Skills 4: A Quiet Moment | The Difficult Weave | 2026-11-15 | owner |
| `tim050_reading` | Elders Teaching Skills 5: A Quiet Moment | Reading the Shoreline | 2026-11-15 | owner |
| `tim051_sorting_roots` | Parents: A Quiet Moment | Sorting Roots Together | 2026-11-15 | owner |
| `tim052_watching_parent` | Parents 2: A Quiet Moment | Watching a Parent Work | 2026-11-15 | owner |
| `tim053_helpful_load` | Parents 3: A Quiet Moment | A Helpful Load | 2026-11-15 | owner |
| `tim054_breakfast` | Parents 4: A Quiet Moment | Breakfast Lessons | 2026-11-15 | owner |
| `tim055_family_tools` | Parents 5: A Quiet Moment | The Family Tools | 2026-11-15 | owner |
| `tim056_sandal_tied` | Siblings: A Quiet Moment | A Sandal Tied | 2026-11-15 | owner |
| `tim057_gathering_twigs` | Siblings 2: A Quiet Moment | Gathering Twigs Together | 2026-11-15 | owner |
| `tim058_sibling` | Siblings 3: A Quiet Moment | A Sibling's Reassurance | 2026-11-15 | owner |
| `tim059_last_ripe_fruit` | Siblings 4: A Quiet Moment | The Last Ripe Fruit | 2026-11-15 | owner |
| `tim060_basket_two` | Siblings 5: A Quiet Moment | A Basket for Two | 2026-11-15 | owner |
| `tim061_snake_path` | Snakes: A Quiet Moment | A Snake on the Path | 2026-11-15 | owner |
| `tim062_empty_snakeskin` | Snakes 2: A Quiet Moment | The Empty Snakeskin | 2026-11-15 | owner |
| `tim063_through_tall` | Snakes 3: A Quiet Moment | Through the Tall Grass | 2026-11-15 | owner |
| `tim064_sunlit_stone` | Snakes 4: A Quiet Moment | The Sunlit Stone | 2026-11-15 | owner |
| `tim065_giving_snakes` | Snakes 5: A Quiet Moment | Giving Snakes Space | 2026-11-15 | owner |
| `tim066_skipping_stones` | Pebbles: A Quiet Moment | Skipping Stones | 2026-11-15 | owner |
| `tim067_circle_game` | Pebbles 2: A Quiet Moment | The Circle Game | 2026-11-15 | owner |
| `tim068_pebbles_color` | Pebbles 3: A Quiet Moment | Pebbles by Color | 2026-11-15 | owner |
| `tim069_tallest_pebble` | Pebbles 4: A Quiet Moment | The Tallest Pebble Tower | 2026-11-15 | owner |
| `tim070_heart_shaped` | Pebbles 5: A Quiet Moment | A Heart-Shaped Stone | 2026-11-15 | owner |
| `tim071_twisting_strong` | Ropes: A Quiet Moment | Twisting Strong Rope | 2026-11-15 | owner |
| `tim072_yesterday_knot` | Ropes 2: A Quiet Moment | Yesterday's Knot | 2026-11-15 | owner |
| `tim073_checking` | Ropes 3: A Quiet Moment | Checking the Bindings | 2026-11-15 | owner |
| `tim074_ropemaker_hands` | Ropes 4: A Quiet Moment | The Ropemaker's Hands | 2026-11-15 | owner |
| `tim075_tangled_cord` | Ropes 5: A Quiet Moment | The Tangled Cord | 2026-11-15 | owner |
| `tim076_beach_race` | Races: A Quiet Moment | The Beach Race | 2026-11-15 | owner |
| `tim077_basket` | Races 2: A Quiet Moment | The Basket Challenge | 2026-11-15 | owner |
| `tim078_winding_course` | Races 3: A Quiet Moment | A Winding Course | 2026-11-15 | owner |
| `tim079_starting_call` | Races 4: A Quiet Moment | The Starting Call | 2026-11-15 | owner |
| `tim080_famous_tumble` | Races 5: A Quiet Moment | The Famous Tumble | 2026-11-15 | owner |
| `tim081_letter` | Parchment: A Quiet Moment | A Letter on Parchment | 2026-11-15 | owner |
| `tim082_marks_scholar` | Parchment 2: A Quiet Moment | Marks of a Scholar | 2026-11-15 | owner |
| `tim083_written_recipe` | Parchment 3: A Quiet Moment | The Written Recipe | 2026-11-15 | owner |
| `tim084_notes_tomorrow` | Parchment 4: A Quiet Moment | Notes for Tomorrow | 2026-11-15 | owner |
| `tim085_copying_story` | Parchment 5: A Quiet Moment | Copying the Old Story | 2026-11-15 | owner |
| `tim086_joining` | Friendship: A Quiet Moment | Joining the Conversation | 2026-11-15 | owner |
| `tim087_room_meal` | Friendship 2: A Quiet Moment | Room at the Meal | 2026-11-15 | owner |
| `tim088_missing_friend` | Friendship 3: A Quiet Moment | The Missing Friend | 2026-11-15 | owner |
| `tim089_comfortable` | Friendship 4: A Quiet Moment | Comfortable Silence | 2026-11-15 | owner |
| `tim090_place_game` | Friendship 5: A Quiet Moment | A Place in the Game | 2026-11-15 | owner |
| `tim091_heavy_morning` | Workdays: A Quiet Moment | The Heavy Morning | 2026-11-15 | owner |
| `tim092_early_finish` | Workdays 2: A Quiet Moment | An Early Finish | 2026-11-15 | owner |
| `tim093_wandering_mind` | Workdays 3: A Quiet Moment | The Wandering Mind | 2026-11-15 | owner |
| `tim094_builder_pause` | Workdays 4: A Quiet Moment | A Builder's Pause | 2026-11-15 | owner |
| `tim095_waiting_supper` | Workdays 5: A Quiet Moment | Waiting for Supper | 2026-11-15 | owner |
| `tim096_ceremonial` | Memories: A Quiet Moment | The Ceremonial Shield | 2026-11-15 | owner |
| `tim097_repairs_across` | Memories 2: A Quiet Moment | Repairs Across Generations | 2026-11-15 | owner |
| `tim098_lantern_pattern` | Memories 3: A Quiet Moment | The Lantern Pattern | 2026-11-15 | owner |
| `tim099_two_memories` | Memories 4: A Quiet Moment | Two Memories of One Festival | 2026-11-15 | owner |
| `tim100_carvings` | Memories 5: A Quiet Moment | Carvings Old and New | 2026-11-15 | owner |
| `tim101_waiting_sprout` | Gardens: A Quiet Moment | Waiting for a Sprout | 2026-11-15 | owner |
| `tim102_neighboring` | Gardens 2: A Quiet Moment | Neighboring Garden Beds | 2026-11-15 | owner |
| `tim103_water_herbs` | Gardens 3: A Quiet Moment | Water for the Herbs | 2026-11-15 | owner |
| `tim104_reading_healthy` | Gardens 4: A Quiet Moment | Reading Healthy Leaves | 2026-11-15 | owner |
| `tim105_blossom` | Gardens 5: A Quiet Moment | The Unexpected Blossom | 2026-11-15 | owner |
| `tim106_fisher_net` | Fishing: A Quiet Moment | The Fisher's Net | 2026-11-15 | owner |
| `tim107_coiling_line` | Fishing 2: A Quiet Moment | Coiling the Line | 2026-11-15 | owner |
| `tim108_shells_tidepool` | Fishing 3: A Quiet Moment | Shells in the Tidepool | 2026-11-15 | owner |
| `tim109_reading_tides` | Fishing 4: A Quiet Moment | Reading the Tides | 2026-11-15 | owner |
| `tim110_patient_fishing` | Fishing 5: A Quiet Moment | The Patient Fishing Float | 2026-11-15 | owner |
| `tim111_drum_rehearsal` | Music: A Quiet Moment | The Drum Rehearsal | 2026-11-15 | owner |
| `tim112_trading_dance` | Music 2: A Quiet Moment | Trading Dance Steps | 2026-11-15 | owner |
| `tim113_clapping` | Music 3: A Quiet Moment | The Clapping Pattern | 2026-11-15 | owner |
| `tim114_workday_tune` | Music 4: A Quiet Moment | A Workday Tune | 2026-11-15 | owner |
| `tim115_songs_after` | Music 5: A Quiet Moment | Songs After Supper | 2026-11-15 | owner |
| `tim116_tomorrow_shade` | Rest: A Quiet Moment | Tomorrow in the Shade | 2026-11-15 | owner |
| `tim117_longer_way_home` | Rest 2: A Quiet Moment | The Longer Way Home | 2026-11-15 | owner |
| `tim118_watching_clouds` | Rest 3: A Quiet Moment | Watching the Clouds | 2026-11-15 | owner |
| `tim119_cup_solitude` | Rest 4: A Quiet Moment | A Cup in Solitude | 2026-11-15 | owner |
| `tim120_after_afternoon` | Rest 5: A Quiet Moment | After the Afternoon Nap | 2026-11-15 | owner |
| `tim121_mending_basket` | Sharing: A Quiet Moment | Mending a Basket Together | 2026-11-15 | owner |
| `tim122_supper_friend` | Sharing 2: A Quiet Moment | Supper for a Friend | 2026-11-15 | owner |
| `tim123_clearing_path` | Sharing 3: A Quiet Moment | Clearing the Path | 2026-11-15 | owner |
| `tim124_helping_carry` | Sharing 4: A Quiet Moment | Helping Carry Supplies | 2026-11-15 | owner |
| `tim125_invitation` | Sharing 5: A Quiet Moment | An Invitation to Supper | 2026-11-15 | owner |
