# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

**Supported game source:** This patcher only supports the games downloaded from the official **Last Day of Work (LDW) website** (ldw.com), where all five PC games are available for free — so there's no reason to get them from anywhere else. Every patch is pinned to the exact bytes of those free LDW builds. Other releases (for example the Steam version) are not tested and may have different bytes; if a game isn't the LDW download, the patcher rejects it rather than risk patching an unverified executable.

The app uses the supplied transparent `Island.png` artwork as its title-bar icon and as small image decorations around both its name and the credit:

`[Island image] Created with Codex AI. Made with love by Lorsieab2 :) [Island image]`

**Every feature has a "?" button.** Beside every patch, population mode, button, link and setting in the patcher window there is a small **?**. Clicking it opens a short, plain guide: what the feature does, how to use it (where it shows up in the game, what to click), and anything to watch out for -- for example that a patch needs another patch, that the game must be closed first, or that 256 Villagers (Experimental) keeps its saves in its own folder. On the All 5 Games tab, the **?** above each column of links is the guide for that link on every game's row. The guides ship with the patcher in `data/how_to_use.json`, and a test refuses any public patch, mode, button or setting without one.

The complete interface has a vertical scrollbar and supports mouse-wheel scrolling, so every patch option, game-folder field, action, and status message remains reachable on shorter displays.

Optional patches are shown under deterministic game-title headers in this order:
Virtual Villagers - A New Home; The Lost Children; The Secret City; The Tree of
Life; New Believers. Shared/all-games patches appear afterward only when they
exist, and each header is sorted by patch name and ID. Selecting a patch with a
prerequisite selects that prerequisite automatically; clearing a prerequisite
clears its dependents. The saved settings and patch logs record the resolved,
dependency-first selection. API and command-line requests that omit a required
prerequisite are rejected before any copied game folder or EXE is written.


## Three population modes

Choose the population mode in the patcher; the choice and all paths are remembered.

| Mode | Collection/progression behavior | Output EXE |
|---|---|---|
| No Population Increase | The stock population cap, collection behavior, and progression gates are preserved. Automatic physical-capacity safety still clamps allocation paths at the game's real record pool. | `(Game name) - Modded.exe` |
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `(Game name) - Modded.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `(Game name) - Modded.exe` |

### What each mode does

**No Population Increase** keeps every game's stock population cap, collection
behavior, and progression gates exactly as shipped: 90 in A New Home, 115 in
The Lost Children, 125 in The Secret City, 115 in The Tree of Life, and 105 in
New Believers. Only the automatic physical-capacity safety is applied, and that
never changes the gameplay cap -- it just stops allocations from overrunning the
game's real villager record pool.

**Collection Progression Max Pop** keeps collections meaningful: they continue
to raise the cap, so the maximum is earned rather than granted. A New Home
reaches 256. The Lost Children starts at 231 and adds 0-25 collection points.
The Secret City starts at 115 and adds 0-25 collection points plus 10 more from
Magic level 3. The Tree of Life starts at 125 and adds 0-25 collection points.
New Believers starts at 135 and adds 0-15 collection points.

**Immediate Fixed Max Pop** grants the absolute slot maximum straight away:
256 in A New Home and The Lost Children, 150 in The Secret City, The Tree of
Life, and New Believers. Collection bonuses no longer change the maximum, and
The Secret City's Magic level no longer changes it either.

The two increased modes use every verified built-in villager slot: 256 in A New
Home and The Lost Children, and 150 in The Secret City, The Tree of Life, and
New Believers. Those are hard limits of each game's own record array, not
chosen numbers.

### Resulting maximums

| Game | Stock final maximum | No Population Increase | Collection Progression maximum | Immediate Fixed maximum |
|---|---:|---:|---:|---:|
| A New Home | 90 | 90 | 256 | 256 |
| The Lost Children | 115 | 115 | 231 to 256 | 256 |
| The Secret City | 125 | 125 | 115 to 150 | 150 |
| The Tree of Life | 115 | 115 | 125 to 150 | 150 |
| New Believers | 105 | 105 | 135 to 150 | 150 |

Housing gates remain in place.

All three modes apply the game's existing automatic physical-capacity safety;
it only clamps allocations at the physical record limit and does not change
the selected mode's social cap or collection/progression behavior. All three
modes use the stable short `- Modded` name (a build with **256 Villagers
(Experimental)** ticked is named `- Modded 256` instead; see below). The selected mode,
optional patches, hashes, and applied edits remain identified in the
`.patch-log.json` in the Modded folder's `Virtual Villagers Fun Patcher Files`
folder.

In A New Home, the automatic safety also preflights the stock two-villager
creation path: when only one physical record remains it creates one villager,
and when the 256-record pool is full it skips the second creation. This keeps
the stock allocator from scanning past its physical record array.

### 256 Villagers (Experimental)

The Secret City, The Tree of Life and New Believers each have an optional
**256 Villagers (Experimental)** patch, off by default, that enlarges the game's
villager table from 150 slots to 256 (numbered 0 to 255, as the game counts
them). With it ticked, the two increased modes reach 256 instead of 150, and
No Population Increase is unchanged:

| Game | No Population Increase | Collection Progression maximum | Immediate Fixed maximum |
|---|---:|---:|---:|
| The Secret City | 125 | 221 to 256 | 256 |
| The Tree of Life | 115 | 231 to 256 | 256 |
| New Believers | 105 | 241 to 256 | 256 |

Collection Progression keeps the same bonuses as the ordinary build (The Secret
City: 0-25 collection points plus 10 from Magic level 3; The Tree of Life: 0-25;
New Believers: 0-15) on a higher base, so everything collected reaches 256.

A build with it is named **`(Game name) - Modded 256.exe`**, in a
**`(Game name) - Modded 256`** folder, and keeps its saves and the patcher's
logs in its own save folder, `Documents\LDW\(Game name) - Modded 256\`, apart
from the ordinary `- Modded` saves. The patcher does not copy any saves there;
how to bring an existing village across is in each game's entry below. The
slot-safety guards for twins, triplets and Island Events work at 256 in these
builds.

## Optional patches by game

Every patch below is optional and off by default. The patcher lists them
under these same game headers, sorted by name. Selecting a patch that has a
prerequisite selects the prerequisite automatically.

**Learning Skills Never Fails** is available for all five games. It makes the
native work-task skill roll succeed every time for Farming, Building,
Researching, Healing, and Parenting; New Believers also includes Devotion.
The stock skill gains and caps remain active. It does not change pregnancies,
food, tech-point gain, or other outcomes. In New Believers it applies only to
believers; heathens remain unchanged. This optional patch is off by default.

**Write Births and Conceptions Log to Text File** is also available for all
five games. Records made before a village's first save are held and written
at that save; none is dropped. Since v1.35.30, a held record from a villager
table where hardly anyone is still present at that save ends with a `Note:`
line saying it was probably recorded among villagers who were not in the
village (for example the game's pre-tribe simulation, or a tribe left unsaved
by Start Over). The Note is only a hint and never decides whether a record is
written. A record is still lost if the game closes without saving after it.
**The holding, the village header and creating the log at a village's first
save all need Write Village Statistics to Text File on**: with it off, each
record is written at once without the header, and a village's log first
appears with its first record rather than when the village is started or
after Start Over.

### Virtual Villagers - A New Home

**Birth Control**

Matches the literal VV4/VV5 Birth Control boundary on the exact VV1 build. Manual pairing rejects only a category-2 carrier at internal age>=1000; the two action-9 writer-reaching scans and the planner reject only scanned candidates at internal age>=1000; the autonomous chooser uses the VV4/VV5 score floor and REQUIRES the parenting preference to be checked, rejecting an unchecked villager rather than applying the VV4/VV5 25% non-preference fallback; initiator males and older autonomous initiators retain no upper-age ceiling. Birth Control owns only its named ordinary-route checks; conception, pregnancy, delivery, direct event births, and pending delivery remain separate native paths, while automatic physical-capacity safety applies in every public mode.

- Patch ID: `vv1_birth_control`

**Manual Drop-Breeding overrides Birth Control**

**In A New Home this only changes anything when Birth Control is also ticked: A New Home itself never refuses a woman aged 50 or older on a manual drop. Birth Control adds that refusal, and with both ticked this patch takes it back out for manual drops only; the rest of Birth Control is unchanged.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv1_manual_drop_breeding_overrides_birth_control`

**Builder Action Fixes**

Villagers whose selected job is Building are more likely to try the stock construction dispatcher when food is plentiful: at 400 food or more, about three times in four each time the game chooses what such a villager does, they get the construction attempt the stock game gives only below 400; the rest of the time the game chooses exactly as it always has. What they build, and in what order, is the stock game's: a new population hut first (project IDs 9, 10, and 11, started from nothing as the stock game does), then the projects already under way; the project gates and the manual, existing-work, and repair routes remain stock. On its own this patch draws its roll from the processor's time-stamp counter, never the game's random numbers. With Builders Fix Huts When Idle also selected, that patch's companion takes over this gate so both share its one roll per choice.

- Patch ID: `vv1_builder_action_fixes`

**Continue Research at Max Technologies**

Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3.

- Patch ID: `vv1_continue_research_at_max_technologies`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen's Food and Tech Point Doublers do not double Island Event, Duplicate Collectible or Golden Child tech gains.

- Requires: vv1_enable_origins_exclusive_features
- Patch ID: `vv1_origins_village_wide_upgrades`

**Numeric Keys: Zip Around the Island**

The number keys move the view to nine measured feature targets in the VV1 1680-unit map, laid out like a numeric keypad (7 8 9 across the top, 4 5 6 in the middle, 1 2 3 along the bottom), using the measured truncating tenth-of-remaining glide on the native village-update cadence. Top-row digits and keypad digits both work; holding a key does not repeat; a glide keeps going even if the view is scrolled or a villager is dragged mid-glide -- press another number key to change course. Adds the loading-screen tip "You can zip around the island with your numeric keys." **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL.

- Patch ID: `vv1_number_keys`

**Show Parents in Details Screen**

Gives A New Home the true parentage the later games keep: every villager born in the village remembers their mother and father for life. While a villager is under 18 (and again if they are ever made younger), two small, faded figures of the parents stand in the upper corners of the Details portrait -- the father on the left facing right, the mother on the right facing left -- and hovering one reads "Son of <name>" or "Daughter of <name>". The record is kept in 'Virtual Villagers 1 Parentage Records - Save <slot>.dat' in the 'Virtual Villagers Fun Patcher Data\Parentage Records' folder beside the saves (Documents\LDW\<game executable name>\), never inside a villager record or the save itself. Each villager's entry follows that villager when the game renumbers its villagers on a load, and is never erased by death, ageing or de-ageing; a new villager starts with none. Each birth is also written to the parentage log the moment it is seen, and the Village Population roster lists each villager's own parents. Founders and villagers born before this patch have no recorded parents. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL. **Needs Write Births and Conceptions Log to Text File on for the father**, which its conception hook supplies: with that patch off only the mother is recorded. **Needs Write Births and Conceptions Log to Text File on for the father (with it off only the mother is recorded) and for the "Birth" records in the parentage log.**

- Patch ID: `vv1_show_parents`

**Sort by Age/Skill/Health in Details Screen**

Adds The Lost Children's Sort By band to A New Home's Villager Detail screen, under the Age and Gender boxes: Age, Skill and Health, each with a radio. The left and right arrows then walk the villagers in that order the way the later games do -- ascending by age, by the villager's highest skill, or by health, with earlier villagers first among equals, and the place in the list is kept when the order is changed. Age is the default. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL, and the base's arrow hooks ask it which villager comes next.

- Patch ID: `vv1_sort_by`

**Improved Pathfinding**

Updates the pathfinding to resemble VV3-VV5. Hopefully villagers don't get stuck behind things anymore! A New Home has no route search: when a villager's next step toward a task is blocked, the stock game nudges them sideways a few times and then clears their whole action list, so they forget the task and drop what they carried. With this row the companion floods the game's own walkability grid from the task and walks the villager round the obstacle, corner by corner, the way The Secret City does. Bumping into a hut or the side of anything is always routed round; only a task that is truly unreachable (its own cell on an obstacle, or walled off) ends the action, at once and without the nudging, as The Secret City does. No executable bytes change: the Origins companion loads "VVFP Improved Pathfinding.dll", which installs its detour only after verifying the stock bytes at the handler. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock walk runs unchanged.

- Patch ID: `vv1_improved_pathfinding`

**Watering the Field Trains Building**

"Watering the field" now gives Building skill, but only when it makes progress towards the garden puzzle (after the lagoon puzzle is complete). Each watering that advances the garden ends with one ordinary Building practice roll, exactly like every other Building job; once the garden is restored, watering gives nothing extra. "Watering crops" and "Trying to water strange patch" are unchanged. No executable bytes change: the Origins companion loads "VVFP VV1 Watering Builds.dll", which installs its hook only after verifying the stock bytes. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock game runs unchanged.

- Patch ID: `vv1_watering_trains_building`

**Misc Text Fixes**

Corrects a handful of A New Home's English texts: "breeding" becomes "parenting" wherever the game names the skill (the skill name, the improvement message and the Fish of Fertility popup), "This villager improved at farming" gains its full stop, and "Food available to villagers" loses its stray full stop. Each text is changed in place in the game's own string table; the other languages are untouched.

- Patch ID: `vv1_misc_text_fixes`

**Magic Fruit of Life Alters Mortality**

Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.

- Patch ID: `vv1_magic_fruit_alters_mortality`

**Reenable F6 Clothing Change Cheat**

The clothing shortcut cycles the selected active villager through the stock outfits: pressing F6 spends 5,000 tech points to advance to the next outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.

- Patch ID: `vv1_f6_clothing_change_cheat`

**School Lessons Grant Skill**

Each child who finishes the unlocked Going to school activity gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Patch ID: `vv1_school_lessons_grant_skill`

**School Lessons Stop at 50**

Each child who finishes the Going to school activity still gains 7 to 9 points in one random skill, but only a skill still below 50 can be chosen, and the gain stops at exactly 50; a skill already at 50 or above is never chosen and never lowered. When every skill is at 50 the lesson awards nothing. This matches the Nursery Schools of the later games, which skip any skill at 50. **Requires School Lessons Grant Skill** (the lesson it caps). **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL.

- Patch ID: `vv1_school_lessons_cap_50`

**Healers Study Plants Regardless of Food**

Healers are more likely to keep studying plants regardless of the food supply. A villager who was studying the plant it was dropped on (the medical cactus) carries on studying when the village has 400 food or more, exactly as the stock game already does below 400 -- about three times in four each time the game chooses what the healer does; the rest of the time the game chooses exactly as it always has. With Builders Fix Huts When Idle also selected, the two share that one roll per choice. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv1_healers_study_regardless_of_food`

**Visual Mods**

Adds decorative flowers to the lagoon and love hut, clothes to the extra hut near the farm, and colorful flowers to the restored garden, by swapping four scene/map images in the game's Images folder. Purely cosmetic -- no executable, gameplay, or save bytes change. Disabling restores the exact base-game images. Credit to the original mod creators.

- Patch ID: `vv1_visual_mods`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 1 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** A New Home stores no parents on any villager record, so both parents are captured at conception; they cannot be recovered from the child afterwards. VV1 stores nothing about the father in the mother's record -- not his name, and no id that could find him -- so his details, his age included, are captured from his own record at the six conception call sites, where the game holds it briefly. A birth that reaches delivery without such a capture reports the father as not captured for that birth, rather than naming the wrong villager. **The Birth records are written by Show Parents in Details Screen, which sees every birth; with it off, only Conception records are written.** **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).** **Needs Show Parents in Details Screen on for the "Birth" records (conceptions are logged without it).**

- Patch ID: `vv1_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure. **Needs Show Parents in Details Screen on for the "Parents:" lines in the Village Population roster.**

- Patch ID: `vv1_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First, Healers Study Plants Regardless of Food and Builder Action Fixes use the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv1_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine. This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv1_builders_and_healers_work_first`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv1_super_secret_golden_mushroom`

**Villagers Have Last Names**

Every new villager gets a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. The last name is the family's: the game already gives every villager a family number from 1 to 50, and a baby takes its mother's, so children share their mother's last name. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. The Golden Child, whose family is not one of the 50, gets no last name. **Needs no other patch.**

- Patch ID: `vv1_last_names`

**Faster Village-Scrolling**

Updates the slow scrolling when selecting villagers and dragging the screen to VV3-VV5's behavior.

- Patch ID: `vv1_faster_village_scrolling`

**Fix Vanilla Bugs**

Fixes bugs in the base game. A Mysterious Vial (blue liquid): when a pregnant villager drinks it and turns back into a toddler, the pregnancy now ends completely, including the number of babies she was carrying; before, a villager who had been carrying twins or triplets kept that number and her next single pregnancy brought twins or triplets. Every default name can be chosen: the game numbers its 101 male and 101 female names from 0 but picks a number from 1, so Achak (male) and Aba (female) could never be given; now every name in each list can come up, for new villagers and twins alike. **Needs no other patch.**

- Patch ID: `vv1_fix_vanilla_bugs`

**Restore Missing Island Events**

A New Home has two island events whose story and effects are complete in the game but which the original game never picks: A Mighty Storm (a typhoon washes away all of the stored food) and The Furry Food (the stored food goes moldy: remove the moldy pieces and some villagers get stomach trouble, or throw out all the food). This adds both to the game's normal random island events, with the same chance as any other event, whenever the village has stored food to lose. Their text and effects are the game's own. **Needs no other patch.**

- Patch ID: `vv1_restore_missing_island_events`

**Show Cause of Death and Epitaphs on Graves, and Log Every Death**

Shows each dead villager's cause of death and an epitaph on their grave, the way The Secret City, The Tree of Life and New Believers do. Clicking a gravestone shows the epitaph in quotes under the name, in a box you can type in (up to 31 characters; Done keeps it), and the cause under the age, in those games' own words (Old age, Disease, Starvation, Work accident, or Unknown causes). The cause is the one that killed them -- old age, sickness, hunger or an empty food bin, an injury at work -- and "Unknown causes" for an island event and anything else, which is how those games word an island-event death. The epitaph is chosen by the rule those games use at a burial: a child's is "Curious and Playful" or "Loving and Special"; an adult's comes from the skill the grave shows (for example "Strong Arms, Big Heart" or "Inspired Architect" for a builder); a villager with no skill is a "Respected Citizen". Those games' Chief, Esteemed Elder and Scholar epitaphs have no counterpart here and are not used. A New Home keeps neither, so both are kept for each save slot in a file beside the saves ('Virtual Villagers Fun Patcher Data\Graves\Virtual Villagers 1 Graves - Save <n>.dat'); Start Over deletes it. A child's grave -- a villager who died before the age of 14 -- names their job the way The Tree of Life words a child's grave, and the way the game's own villager panel names a working child: "Apprentice Farmer" rather than Trainee, Adept or Master, on the grave and in the Deaths log alike. A child with no skill of 20 or more is "Untrained", as before. **Graves dug before this patch was installed get an epitaph the first time they are opened, but no cause: how they died was never recorded.** Every death that leaves a body is written to the Deaths log ('Virtual Villagers 1 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (The Mysterious Face and The Book, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 1 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 1 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 1 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. In A New Home a villager born here is told by their Birth record, which Show Parents in Details Screen writes: **without that patch no Arrived record is backfilled.** At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 1 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 1 Village Roster - Save <n>.dat'; Start Over deletes it. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv1_cause_of_death`

**Learning Skills Never Fails**

Villagers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv1_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set). Off by default.

- Patch ID: `vv1_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv1_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - The Lost Children

**Birth Control**

Matches the VV4/VV5 Birth Control boundary on the exact VV2 ordinary routes: the native chooser's score floor remains in force while its 25% non-preference fallback is removed so an unchecked preference is rejected outright, the two writer-reaching opcode-12 candidate scans reject candidates at internal age 1000 or greater, and the stock manual carrier/female-only gate rejects older carriers without adding a male upper-age gate. Birth Control owns only those two candidate scans; the conception roll, pregnancy writer, pregnancy, delivery, and automatic physical-capacity safety remain separate native/automatic paths in every public mode.

- Patch ID: `vv2_birth_control`

**Manual Drop-Breeding overrides Birth Control**

**Works the same with or without Birth Control: the 50-and-over refusal it lifts is The Lost Children's own, which Birth Control does not change.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv2_manual_drop_breeding_overrides_birth_control`

**Easier Healing Mastery**

Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up.

- Patch ID: `vv2_easier_healing_mastery`

**Improved Pathfinding**

Updates the pathfinding to resemble VV3-VV5. Hopefully villagers don't get stuck behind things anymore! The Lost Children already plans routes, but its route follower gives up -- clearing the villager's action list, so the task is dropped -- when a villager stands on a cell the route never reached, and it picks the first neighbour in a fixed order, cutting corners between obstacles. With this row the descent takes the neighbour nearest the task, never cuts a corner between two obstacles, and brings a stranded villager back to the route. As in The Secret City, only a task that is truly unreachable (its own cell on an obstacle, or walled off) ends the action. No executable bytes change: the Origins companion loads "VVFP Improved Pathfinding.dll", which installs its two detours only after verifying the stock bytes. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock walk runs unchanged.

- Patch ID: `vv2_improved_pathfinding`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Tech and Food Point Doublers, and Cure All Villagers, the Villager Details screen grants Youth, Full Mastery, Running, and Set Age to 18, and the Heathen mask cosmetics are included. The point doublers do not double Island Event, Duplicate Collectible or Gong of Wonder tech gains.

- Requires: vv2_enable_origins_exclusive_features
- Patch ID: `vv2_origins_village_wide_upgrades`

**Tip Wording: Numeric Keys**

Rewords the loading-screen tip "You can zip around the island with your keypad." to "You can zip around the island with your numeric keys.", matching A New Home's new tip. The keys themselves already work in The Lost Children; nothing else changes.

- Patch ID: `vv2_numeric_keys_tip_wording`

**Gong of Wonder Coconuts Fix**

When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.

- Patch ID: `vv2_gong_of_wonder_coconuts_fix`

**Hospital Recovery Heals**

A villager who completes Recovering at the hospital gains exactly 1 health point, capped at 100. Stock VV2's hospital recovery action does not change health.

- Patch ID: `vv2_hospital_recovery_heals`

**Teaching Children Grants Skill**

Each child who finishes a Teaching Children lesson gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Patch ID: `vv2_teaching_children_grants_skill`

**Teaching Children Stops at 50**

Each child who finishes a Teaching Children lesson (Attending lessons) still gains 7 to 9 points in one random skill, but only a skill still below 50 can be chosen, and the gain stops at exactly 50; a skill already at 50 or above is never chosen and never lowered. When every skill is at 50 the lesson awards nothing. This matches the Nursery Schools of the later games, which skip any skill at 50. **Requires Teaching Children Grants Skill** (the lesson it caps). **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL.

- Patch ID: `vv2_teaching_children_cap_50`

**Healers Study Plants Regardless of Food**

Healers are more likely to keep studying plants regardless of the food supply. A villager who was studying a plant (the same four-plant roll the stock game makes) carries on studying when the village has 300 food or more, exactly as the stock game already does below 300 -- about three times in four each time the game chooses what the healer does; the rest of the time the game chooses exactly as it always has. With Builders Fix Huts When Idle also selected, the two share that one roll per choice. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv2_healers_study_regardless_of_food`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 2 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. VV2 keeps the father's name on the mother's record and no father id; his head and body are copied onto her at conception, so the log reads them from her record and they stay correct even after he dies or another villager takes his name. His age, which has no copy on her, is read from his own record -- every caller that holds it passes it, the Love Note included -- so a normal birth records his real age. **Runs on the Origins-exclusive base, which is installed automatically with it and adds the Origins Upgrades buttons to the Tech and Villager Details screens**: the loader trampoline lives in the page that base appends, because VV2's own code cave is occupied by the renamed-build crash guard and has no room for it. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv2_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv2_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First and Healers Study Plants Regardless of Food use the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv2_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine. This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv2_builders_and_healers_work_first`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv2_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv2_super_secret_golden_mushroom`

**Villagers Have Last Names**

Every new villager gets a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. The last name is the family's: the game already gives every villager a family number from 1 to 50, and a baby takes its mother's, so children share their mother's last name. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv2_last_names`

**Faster Village-Scrolling**

Updates the slow scrolling when selecting villagers and dragging the screen to VV3-VV5's behavior.

- Patch ID: `vv2_faster_village_scrolling`

**Firepit: Dry Grass Drawn Above the Wood**

When both the dry grass and the firewood have been put in the unlit fire pit, the dry grass is drawn on top of the wood instead of being hidden behind it. Only the drawing order of those two pictures changes; nothing else about the fire pit, the fire puzzle or your save is touched. **Needs no other patch.**

- Patch ID: `vv2_firepit_dry_grass_above_wood`

**Fix Vanilla Bugs**

Fixes bugs in the base game. The Crystal Ball: the island event is only offered when at least one other living villager besides the one who finds the ball is there to trade places with, and if "Keep it" is ever chosen with nobody else living (for example through Pick Island Event), nothing is swapped and the game carries on instead of closing. Every default name can be chosen: the game numbers its 125 male and 125 female names from 0 but picks a number from 1 (and never the last one), so Achak and Zuri (male) and Aba and Zuna (female) could never be given; now every name in each list can come up, for new villagers and twins alike. **Needs no other patch.**

- Patch ID: `vv2_fix_vanilla_bugs`

**Restore Missing Island Events**

Lets the island events the original game contains but never runs happen. The Mosquito Swarm (some villagers fall ill and the adults take refuge in the water), The Dragonfly Migration (every villager is restored to full health and cured) and Science Awareness Day (the children gain research skill) join the game's own random island-event roll with the same chance as a typical event. Three events whose text the game ships but never shows are added as rarer no-choice events, each a third as likely as a typical event: The Tattered Diary, The Doctrine of Magicians and The Doctrine of Naturalists, pages of Isola's lore a villager finds; they change nothing else. **Needs no other patch.** With Story / Cheat Upgrades, Pick Island Event also offers the three new events.

- Patch ID: `vv2_restore_missing_island_events`

**Show Cause of Death on Graves, and Log Every Death**

Shows each dead villager's cause of death on their grave, the way The Secret City, The Tree of Life and New Believers do: clicking a gravestone shows the cause under the age, in those games' own words (Old age, Disease, Starvation, Work accident, or Unknown causes). The cause is the one that killed them -- old age, sickness, hunger or an empty food bin, an injury at work -- and "Unknown causes" for an island event and anything else, which is how those games word an island-event death. The Lost Children keeps no cause, so it is kept for each save slot in a file beside the saves ('Virtual Villagers Fun Patcher Data\Graves\Virtual Villagers 2 Graves - Save <n>.dat'); Start Over deletes it. The game's own epitaphs are unchanged. A child's grave -- a villager who died before the age of 14 -- names their job the way The Tree of Life words a child's grave, and the way the game's own villager panel names a working child: "Apprentice Farmer" rather than Trainee, Adept or Master, on the grave and in the Deaths log alike. A child with no skill of 20 or more is "Untrained", as before. **Graves dug before this patch was installed, and bodies that were already lying when it was, show no cause: how they died was never recorded.** Every death that leaves a body is written to the Deaths log ('Virtual Villagers 2 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (A Dangerous Mission and The Voices In The Brush, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 2 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 2 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 2 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 2 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 2 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 2 Village Roster - Save <n>.dat'; Start Over deletes it. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv2_cause_of_death`

**Learning Skills Never Fails**

Villagers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv2_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set). Off by default.

- Patch ID: `vv2_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event and Pick Gong of Wonder Outcome each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv2_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - The Secret City

**Birth Control**

Requires BOTH parenting skill and the checked preference before a villager will initiate Embracing. The native chooser's score floor remains in force and the scanned candidate stays in the stock internal-age 360..999 range, but the 25% non-preference fallback is removed: a roll that admitted one unchecked villager in four is the reported leak. The initiating villager has no extra upper-age rejection. Birth Control owns only the five ordinary initiator checks; the native manual category-1 carrier gate, conception, pregnancy, and delivery remain separate, while automatic physical-capacity safety applies in every public mode.

- Patch ID: `vv3_birth_control`

**Manual Drop-Breeding overrides Birth Control**

**Works the same with or without Birth Control: the 50-and-over refusal it lifts is The Secret City's own, which Birth Control does not change.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv3_manual_drop_breeding_overrides_birth_control`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Food and Tech Point Doublers, Complete all Collections, Reset all Collections, and Equal Division of Labor with and without Parenting, all supplied by the base Origins feature rather than this optional payload. The point doublers do not double Island Event or Duplicate Collectible tech gains.

- Requires: vv3_enable_origins_exclusive_features
- Patch ID: `vv3_origins_village_wide_upgrades`

**Everyone Tries On the Robe**

Dropping an active, living, non-nursing villager on the robe interrupts every other active, living, non-nursing villager and sends them to try on the robe too. Each villager receives the complete base-game success or failed-fit result, and the base game alone decides who becomes Tribal Chief.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv3_everyone_tries_on_robe`

**Nature Level 1 Actually Replenishes Food Sources Faster**

Nature level 1 or higher reduces fruit-tree refills from 3 hours to 2 hours 15 minutes and honey refills from 1 hour to 45 minutes. Fruit trees retain their stock Nature quantity bonus, while honey gains the same proportional quantity bonus.

- Patch ID: `vv3_nature_honey_refill`

**Nature Level 3 Actually Alters Mortality**

Nature level 3 shifts every ordinary villager's complete mortality curve seven displayed years later. The stock Medicine threshold is calculated first, so the benefits stack, and the shared aging loop applies the change during ordinary play and time catch-up.

- Patch ID: `vv3_nature_level_three_alters_mortality`

**Pointing Out a Rare Collectible Always Works**

When the Tribal Chief completes Pointing out a rare collectible and the stock game rejects its random choice (a collectible a villager is already after, or a special one already collected), the whole stock selection is run again, up to 20 times in all, stopping as soon as a collectible is placed. In practice a collectible almost always appears instead of the stock cooldown being spent for nothing; if every attempt is refused (for example, when every special collectible has already been found), nothing is placed, exactly as in the stock game. The original rare categories, collectible IDs, collection rules and placement logic are unchanged.

- Patch ID: `vv3_rare_collectible_retry`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 3 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. VV3 keeps the father's name on the mother's record and no father id. His HEAD and BODY are copied onto her at conception, so the log reads them from her record and they are correct even after he dies or another villager takes his name. His AGE, which has no copy on her, is read from his own record at conception -- the conception hook reads the other parent's saved record -- so a normal birth records his real age. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv3_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv3_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First uses the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv3_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine. This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv3_builders_and_healers_work_first`

**Tribal Chief Lessons Stop at 50**

The Tribal Chief's lessons stop at 50. Each child who finishes a lesson still gains 7 to 9 points in one random skill, but only a skill still below 50 can be chosen, and the gain stops at exactly 50; a skill already at 50 or above is never chosen and never lowered, and when every skill is at 50 the lesson awards nothing. This matches A New Home's and The Lost Children's lesson patches and the later games' Nursery Schools. The Secret City has no companion that runs every frame, so the row diverts the lesson award into a small stub in the page Origins appends, which calls "VVFP Lesson Cap.dll"; if the DLL cannot be loaded, the stock lesson runs and trains to 100. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv3_chief_lessons_cap_50`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv3_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv3_super_secret_golden_mushroom`

**Villagers Have Last Names**

Every new villager gets a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. The last name is the family's: the game already gives every villager a family number from 1 to 50, and a baby takes its mother's, so children share their mother's last name. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv3_last_names`

**Fix Vanilla Bugs**

Fixes bugs in the base game. The Royal Jelly: the dark vial now cures the villager's cold and raises their Healing, and the clear vial (whose text says the jelly turned bitter) changes nothing, so each vial does what its own text says. The Mysterious Vial (amber): the "flash of scientific insight" result now also gives the tribe 100 tech points, as its text promises, as well as the villager's Research gain. The Mysterious Vial (quartz): a villager who is exactly 14 now gets the text of what really happens to them (becoming an elder) instead of the text about becoming a little child. A village with exactly 150 villagers can be saved and loaded again: the base game, when it saves a full list of 150 villagers, writes past the end of that list and damages the next part of the save, so the village refused to load; now all 150 are kept and the village loads, and a village already saved that way is repaired when it is loaded. Every default name can be chosen: the game numbers its 125 male and 125 female names from 0 but picks a number from 1 (and never the last one), so Akivi and Yapili (male) and Aipi and Zucca (female) could never be given; now every name in each list can come up, for new villagers and twins alike. **Needs no other patch.**

- Patch ID: `vv3_fix_vanilla_bugs`

**Log Every Death, Disappearance and Unaccounted Villager**

Every death that leaves a body is written to the Deaths log ('Virtual Villagers 3 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (The Tsunami and The Low Tide, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 3 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 3 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 3 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 3 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 3 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 3 Village Roster - Save <n>.dat'; Start Over deletes it. The cause is the one The Secret City itself records and shows on the grave. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv3_cause_of_death`

**256 Villagers (Experimental)**

Gives The Secret City 256 villager slots (numbered 0 to 255) instead of 150. The game's villager table is moved to a new, larger place in memory, and every part of the game that goes through it -- births, Island Events, the Villager Details screen, saving and loading -- is widened to match. The population modes' caps in a 256 build: Immediate Fixed Max Pop allows 256 at once; Collection Progression Max Pop starts at 221 and adds 0-25 collection points plus 10 from Magic level 3, reaching 256 with everything; No Population Increase keeps the stock cap of 125, and only the table is larger.

**Where its saves go.** A build with this patch is named 'Virtual Villagers - The Secret City - Modded 256.exe' (in a 'Virtual Villagers - The Secret City - Modded 256' folder) and keeps its saves, and the patcher's logs and data files, in its own folder, 'Documents\LDW\Virtual Villagers - The Secret City - Modded 256\', so they never mix with the 150-slot saves of the ordinary '- Modded' build. The patcher does not fill that folder: to carry on an existing village, copy its save files (the .ldw files) from 'Documents\LDW\Virtual Villagers - The Secret City - Modded\' into it yourself. The old save loads with all its villagers. The first time the game saves it, it is written in a longer 256-slot format, and from then on it opens only in a 256 build; a 150-slot game cannot read it. Keep your ordinary '- Modded' saves as a backup.

**Needs Fix Vanilla Bugs on (it is on by default) to load a village that the base game's exactly-150-villager save bug has already damaged.** The base game damages a save made with exactly 150 villagers so that it will not load (see Fix Vanilla Bugs above); with Fix Vanilla Bugs ticked, the 256 build loads such a save with all 150 villagers and saves it in the 256 format. A 256 build cannot itself make that damage.

**This patch is experimental and off by default.** It has passed the patcher's build tests and live tests that filled the village to the last slots, but it has had far less play than the other patches. Select All Patches and Default Patches leave it off; Owner's Defaults ticks it.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv3_population_256`

**Learning Skills Never Fails**

Villagers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv3_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set). Off by default.

- Patch ID: `vv3_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv3_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - The Tree of Life

**Complete Fish Scales = Golden Fish in Nets**

Golden Fish become eligible in the fishing nets only after all 12 Fish Scales are collected. This changes the stock partial-collection threshold while preserving the completed collection's original 25% Golden Fish chance and every other fishing outcome.

- Patch ID: `vv4_complete_scales_golden_fish`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Food and Tech Point Doublers, Full Heal/Cure All, All Villagers are Exactly 18, Complete and Reset All Collections, and Equal Division of Labor with and without Parenting, the Villager Details screen grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance, and the Heathen mask cosmetics are included. The point doublers do not double Island Event or Duplicate Collectible tech gains.

- Requires: vv4_enable_origins_exclusive_features
- Patch ID: `vv4_origins_village_wide_upgrades`

**Optional Text changes**

Replaces some in-game text with wording consistent with the other Virtual Villagers games (for example, the "Scholar" title becomes "Esteemed Elder", and a few labels and event lines are capitalized and punctuated to match). When active, the game's Assets/sm.xml is swapped for the edited version; when the patch is not selected, the base-game text is left untouched. No executable bytes are changed.

- Patch ID: `vv4_optional_text_changes`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 4 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. Village seeding is excluded, so a new village does not write a record for every starting villager. The game keeps only the father's name on the mother's record. His HEAD and BODY are copied onto her at conception, so the log reads them from her record and they stay correct even after he dies or another villager takes his name. His AGE, which has no copy on her, is read from his own record at conception -- the moment the engine hands both parents to the hook -- so a normal birth records his real age. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv4_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export so existing saves are reported accurately. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv4_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First uses the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv4_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine. This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv4_builders_and_healers_work_first`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv4_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv4_super_secret_golden_mushroom`

**Villagers Have Last Names**

Every new villager gets a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. The last name is the family's: the game already gives every villager a family number from 1 to 50, and a baby takes its mother's, so children share their mother's last name. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv4_last_names`

**Manual Drop-Breeding overrides Birth Control**

**Needs no other patch: the 50-and-over refusal it lifts is The Tree of Life's own; this game has no Birth Control patch.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food, love-shack and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv4_manual_drop_breeding_overrides_birth_control`

**Log Every Death, Disappearance and Unaccounted Villager**

Every death that leaves a body is written to the Deaths log ('Virtual Villagers 4 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken with no skeleton (The Sealed Box, or the Custom Island Event's "Disappears") gets a "Disappeared" record saying what took them, and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 4 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 4 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 4 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 4 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 4 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 4 Village Roster - Save <n>.dat'; Start Over deletes it. The cause is the one The Tree of Life itself records and shows on the grave. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv4_cause_of_death`

**Fix Vanilla Bugs**

Fixes bugs in the base game. A village with exactly 150 villagers can be saved and loaded again: the base game, when it saves a full list of 150 villagers, writes past the end of that list and damages the next part of the save, so the village then refuses to load and the game offers to start a new tribe. Now all 150 villagers are kept and the village loads. A village that was already saved with 150 villagers and would not load is repaired when it is loaded. Only a village with 150 villagers is affected; the base game cannot reach 150 on its own, but the Collection Progression and Immediate Fixed population modes can. Every default name can be chosen: the game numbers its 185 male and 185 female names from 0 but picks a number from 1 (and never the last one), so Ago and Yapili (male) and Aipi and Zucca (female) could never be given; now every name in each list can come up, for new villagers and twins alike. **Needs no other patch.**

- Patch ID: `vv4_fix_vanilla_bugs`

**256 Villagers (Experimental)**

Gives The Tree of Life 256 villager slots (numbered 0 to 255) instead of 150. The game's villager table is moved to a new, larger place in memory, and every part of the game that goes through it -- births, Island Events, the Villager Details screen, saving and loading -- is widened to match. The population modes' caps in a 256 build: Immediate Fixed Max Pop allows 256 at once; Collection Progression Max Pop starts at 231 and adds 0-25 collection points, reaching 256 with everything; No Population Increase keeps the stock cap of 115, and only the table is larger.

**Where its saves go.** A build with this patch is named 'Virtual Villagers - The Tree of Life - Modded 256.exe' (in a 'Virtual Villagers - The Tree of Life - Modded 256' folder) and keeps its saves, and the patcher's logs and data files, in its own folder, 'Documents\LDW\Virtual Villagers - The Tree of Life - Modded 256\', so they never mix with the 150-slot saves of the ordinary '- Modded' build. The patcher does not fill that folder: to carry on an existing village, copy its save files (the .ldw files) from 'Documents\LDW\Virtual Villagers - The Tree of Life - Modded\' into it yourself. The old save loads with all its villagers. The first time the game saves it, it is written in a longer 256-slot format, and from then on it opens only in a 256 build; a 150-slot game cannot read it. Keep your ordinary '- Modded' saves as a backup.

**Needs Fix Vanilla Bugs on (it is on by default) to load a village that the base game's exactly-150-villager save bug has already damaged.** The base game damages a save made with exactly 150 villagers so that it will not load (see Fix Vanilla Bugs above); with Fix Vanilla Bugs ticked, the 256 build loads such a save with all 150 villagers and saves it in the 256 format. A 256 build cannot itself make that damage.

**This patch is experimental and off by default.** It has passed the patcher's build tests and live tests that filled the village to the last slots, but it has had far less play than the other patches. Select All Patches and Default Patches leave it off; Owner's Defaults ticks it.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv4_population_256`

**Learning Skills Never Fails**

Believers succeed every work-task skill roll for Farming, Building, Researching, Healing, and Parenting; the native skill gains and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv4_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set). Off by default.

- Patch ID: `vv4_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv4_story_cheat_upgrades_cost_tech_points`

### Virtual Villagers - New Believers

**Clickable Tips**

Clicking the curled vine beneath the on-screen Puzzles button shows a random in-game tip in the gray message bar (with the engine's own auto-hide timer) and plays the hou.ogg chime.

- Patch ID: `vv5_clickable_tips`

**Easier Devotee Training**

Villagers with positive Devotion skill can spontaneously use the stock Honoring action. Statue-drop Honoring remains available for training beginners, while villagers with no Devotion skill do not autonomously Honor.

- Patch ID: `vv5_easier_devotee_training`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Tech and Food Point Doublers, Full Heal/Cure All, All Villagers are Exactly 18, Complete and Reset All Collections, Equal Division of Labor with and without Parenting, and Change Appearance for All, the Villager Details screen grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance, and the Heathen mask cosmetics are included. The point doublers do not double Island Event or Duplicate Collectible tech gains. The Village-Wide Running, Full Mastery and Make Villagers Young Adults process only Believers and skip Heathens; Change Appearance for All changes every villager, Heathens included.

- Requires: vv5_enable_origins_exclusive_features
- Patch ID: `vv5_origins_village_wide_upgrades`

**Guardians of Isola Rewrite**

Overhauls the New Believers story presentation: replaces the in-game text (Assets/sm.xml) and twelve story/UI images -- the five totem strips, idol states, the blinking-eyes and mask strips, and the main menu -- with the Guardians of Isola rewrite. Purely presentational; no gameplay, executable, or save bytes change. Disabling restores the exact base-game files.

- Patch ID: `vv5_guardians_of_isola_rewrite`

**Heathen Mommy Puzzle Restoration**

Restores the natural Heathen Mommy to newly created villages as a tag-17 Heathen mother with one nursing baby, using two physical slots, and restores the hidden 17th Heathen Parent graphic and full-tile rollover messages to the Puzzles screen. Existing saves are not retroactively given a new mother.

- Patch ID: `vv5_heathen_mommy_puzzle`

**Move the "Playing in the dirt" Spot**

Moves where children go to play in the dirt. In the stock game the spot is a strip of ground that runs from the rainbow totem's side down across the river, so a child playing in the dirt wanders through the water and ends up on the bank behind the research shelves; this makes it the flower patch east of the dirt path (the worn ground with the flowers, west of the flower rock), where the owner marked it: about 305 by 205 with six random steps inside it. The action, its text, its sound and its length are unchanged.

- Patch ID: `vv5_playing_in_the_dirt_spot`

**Charitable Soul Epitaph**

When a Devotee dies and is buried, the epitaph New Believers writes on the grave is chosen at random, with equal chances, between the game's usual epitaph ("Respected Citizen", or "Respected Devotee" with Guardians of Isola Rewrite) and "Charitable Soul". In the stock game every other job already gets one of two epitaphs on a coin flip (a Farmer is "Child of the Earth" or "Nature's Friend", and so on), but a Devotee always got the usual epitaph, which an adult with no skill at all also gets. A villager's job here is the one the grave names: their highest skill. Only Devotees change: the unskilled adult keeps the usual epitaph, children and villagers with three or more master skills keep their own epitaphs, and every other job keeps its pair. The epitaph is stored in the grave like any other, so it is saved with the village, the player can still edit it, and the Deaths log records it. Graves that earlier versions of this patch wrote as "Devoted Soul" keep that epitaph.

- Patch ID: `vv5_devoted_soul_epitaph`

**Statue Drops: Normal Action or Honoring**

Dropping a villager on a completed statue gives Polishing the Statue or Honoring on a 50/50 choice, regardless of that villager's skills. Only the completed statue is affected: building an unfinished statue, the upgradeable statue's Honoring, and the Confused result when the technology is missing all keep their stock behaviour.

- Patch ID: `vv5_statue_polishing_or_honoring`

**VV4 Nursery School Divisor Parity**

For parity with Virtual Villagers 4, changes VV5's six-skill spread lesson divisor from five to six. VV5 normally distributes one-fifth of a lesson to each of six skills, an arithmetic inconsistency that awards six-fifths in total; this patch distributes exactly one-sixth to each skill without claiming whether the original inconsistency was intentional.

- Patch ID: `vv5_vv4_nursery_divisor_parity`

**Write Births and Conceptions Log to Text File**

Keeps a plain-text log of the village's conceptions and births in 'Virtual Villagers 5 Births and Conceptions Log <n>.txt', in the 'Virtual Villagers Fun Patcher Logs\Births and Conceptions' folder beside the game's saves (Documents\LDW\<game executable name>\). Each Conception record gives both parents' names, both parents' ages at conception, both head and body values, both parents' likes and dislikes, and the number of babies; the mother's age determines the child's age. Each Birth record gives the child's name, head, body, likes, dislikes and skills, and its mother's and father's names, heads and bodies. A new numbered file is started after every 256 Conception records; Birth records go into the file holding the latest conceptions and do not count toward that limit. Each Arrived record, numbered on its own, gives a villager who joined the village without being born into it -- a new village's founders, an island event's newcomers, the Barrel of Babies, the Custom Island Event's new villagers (never a birth): their name, age when they arrived, sex, head, body, likes, dislikes and skills, and how they came ("Founder", the event's title, "Barrel of Babies", "Custom Island Event", or "unknown"); villagers who arrived before this record existed get one, marked "Recorded afterwards", only once the player chooses Repair when the village is loaded. **The Arrived records are found by the Cause of Death patch ("Log Every Death ..."): with it off, none is written.** The game keeps both parents on the child's own record, and each Birth record reads them from there. Village seeding is excluded, so a new village does not write a record for every starting villager. The game keeps only the father's name on the mother's record. His HEAD and BODY are copied onto her at conception, so the log reads them from her record and they stay correct even after he dies or another villager takes his name. His AGE, which has no copy on her, is read from his own record at conception -- the moment the engine hands both parents to the hook -- so a normal birth records his real age. **Needs Write Village Statistics to Text File on for the village and savegame header at the top of the log (records are still written correctly without it, just unlabelled -- unless Cause of Death is ticked, which names the village at each save itself).**

- Patch ID: `vv5_write_parentage_log`

**Write Village Statistics to Text File**

After each successful save of slots 1 through 5, writes the save's local lifetime statistics to 'Village Statistics - Save N.txt' in the modified game folder. Later games retain the inherited per-save statistics block even where no Statistics screen is reachable; omitted stock bookkeeping is restored by exact gameplay hooks. Puzzle totals are read from the current save state during export, including an already-completed VV5 Puzzle 17 save. The original save result is preserved, and text-export failure does not turn a successful game save into a failure.

- Patch ID: `vv5_write_village_statistics`

**Builders Fix Huts When Idle**

Builders fix huts when no building projects are present, and build first. This makes builders more likely to do their building work, not certain: each time the game chooses what a builder does, the patch steps in about three times in four, and the rest of the time the game chooses exactly as it always has. When it steps in, construction always comes first -- a builder goes straight into a new hut or building project the game would let it build, even when the game's own random roll would have skipped it this time, and never fixes a hut while there is one. When no building project is available to be worked on and at least one population hut stands -- while another is unbuilt, and below Building level 3 even once every one is built -- a builder with nothing to do examines and fixes one of the huts that already stands, the game's own "Examining hut" / "Fixing hut" job, which trains Building. It only makes that job able to be chosen autonomously; the job itself, its chance of a repair and its skill roll are the game's own. Whenever there is hut work to do, a builder also does this regardless of the food supply: plentiful food no longer skips the builder's work attempt (A New Home, The Lost Children), and scarce food no longer sends the builder to farm or gather first (The Secret City, The Tree of Life, New Believers). Builders and Healers Work First uses the same roll when selected with it, so one choice is either all patched or all stock. Applies in live play and during catch-up. **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL (in The Secret City, a small stub in the page the base appends does); if the DLL cannot be loaded, the stock scheduler runs unchanged.

- Patch ID: `vv5_builders_fix_huts`

**Builders and Healers Work First**

Builders and healers are more likely to do their own work first, at any food level -- about three times in four each time the game chooses what they do; the rest of the time the game chooses exactly as it always has, and the one roll is shared with Builders Fix Huts When Idle, so a choice is either all patched or all stock. When it steps in: whenever the game looks for something for a villager whose selected job is Building to do, it first tries building work (a project, or fixing a hut) while not every population hut is built -- and, in A New Home and The Lost Children below Building level 3, whenever any hut is built; for one whose selected job is Healing it always first tries healing and study, whenever there is a patient or they can study medicine. This comes before idling, farming or gathering. When there is nothing of their own to do, they do whatever the game would have had them do. An addendum to Builders Fix Huts When Idle. **Requires Builders Fix Huts When Idle**, whose DLL loads this one (in The Secret City, whose stub does); ticking this ticks it, and it brings with it the Origins-exclusive base, which adds the Origins Upgrades buttons to the Tech and Villager Details screens.

- Patch ID: `vv5_builders_and_healers_work_first`

**VV1 Mushroom/Collectible Duplication Cheat**

Multiple children can be dropped onto a single mushroom (and collectible) and it will be multiplied.

- Patch ID: `vv5_everyone_collects_like_vv1`

**Super-Secret Golden Mushroom**

Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what it does! (Original art found in Virtual Villagers 2's files)

- Patch ID: `vv5_super_secret_golden_mushroom`

**Villagers Have Last Names**

Every new villager gets a last name after their first name, from the game's own list of 50 last names (Akikai, Alosaka, Awanata ... Wikimak) -- a list the game has always carried but never used, and the one Virtual Villagers 6 and 7 later used for villagers' last names. The last name is the family's: the game already gives every villager a family number from 1 to 50, and a baby takes its mother's, so children share their mother's last name. Only villagers named from now on get one: villagers who already have names keep them. The last name is part of the name the game stores, so it shows wherever the name does and stays in the save even if this patch is later removed. **Needs no other patch.**

- Patch ID: `vv5_last_names`

**Manual Drop-Breeding overrides Birth Control**

**Needs no other patch: the 50-and-over refusal it lifts is New Believers' own; this game has no Birth Control patch.** When you drop an adult villager onto an adult of the opposite sex, a woman aged 50 or older is no longer refused. It is not a guarantee: the game's usual chances still decide whether the pair gets along and whether a baby is conceived, exactly as for any other couple, so a drop can still fail. Every other rule of the drop is unchanged: a man and a woman, both adults, both alive and well, the woman not already expecting or nursing, and the game's own food, love-shack and population checks. The game never looks at the Parenting preference on a manual drop, and Parenting skill (the dropped villager's) only changes the chances without ever blocking a drop, so an unchecked preference or no skill never stopped one, with or without this patch. Only the manual drop is changed: villagers pairing up on their own, catch-up, events and Birth Control's own rules stay as they are. Off by default.

- Patch ID: `vv5_manual_drop_breeding_overrides_birth_control`

**Learning Skills Never Fails**

Believers succeed every work-task skill roll for Farming, Building, Researching, Healing, Parenting, and Devotion; heathens and all non-skill outcomes remain unchanged. Off by default.

- Patch ID: `vv5_learning_never_fails`

**Story / Cheat Upgrades**

Optional tools for custom stories, experiments, sandbox play and cheats, which deliberately bypass normal game progression and random island events. Every Origins Upgrade costs 0 Tech Points, and the Origins menus gain **Pick Island Event** (choose which of the game's own island events happens next, and its outcome) and **Custom Island Event** (write your own event, including two-choice events whose buttons have outcomes and chances you set). Off by default.

- Patch ID: `vv5_story_cheat_upgrades`

**Story / Cheat Upgrades cost Tech Points**

**Requires Story / Cheat Upgrades.** The Origins Upgrades keep their normal tech-point prices instead of costing 0, and Pick Island Event, Custom Island Event each cost what the Island Event upgrade costs: 30,000 tech points, paid when the event is queued (with too few, you are told and nothing is spent). Ticking Story / Cheat Upgrades ticks this too; untick it to keep every upgrade free.

- Patch ID: `vv5_story_cheat_upgrades_cost_tech_points`


That is 103 optional patches across the five games.

Three patches change files rather than executable bytes: **VV1 Visual
Mods**, **VV4 Optional Text changes**, and the **VV5 Guardians of Isola
Rewrite** swap images and text inside the copied game folder only, and
restore the exact base-game files when the patch is not selected.

**Log Every Death, Disappearance and Unaccounted Villager**

Every death that leaves a body is written to the Deaths log ('Virtual Villagers 5 Deaths Log <n>.txt' in the 'Virtual Villagers Fun Patcher Logs\Deaths' folder beside the game's saves) when it is final: when the body is buried, with the skill line and epitaph the grave was given, or when the game removes a body nobody buried ("no grave"). Each Death record gives the villager's name, head, body, likes and dislikes, their age at death in the game's own units (20 per year, as the Village Population log prints Age), the cause, the grave and the epitaph. A villager brought back to life gets no Death record. A villager taken by the Custom Island Event's "Disappears" gets a "Disappeared" record (the game itself has no such event), and editing a grave's epitaph adds an "Epitaph changed" record with the old and new text. A grave the Deaths log has no record for -- dug before the log was kept, or while the game was catching up on time away -- is given a Death record only when the player says so -- Repair Logs in the patcher window, or Repair when the game asks as it closes (with "Check logs automatically" on, and only if something is wrong); nothing is ever asked while the village is played. The record is made from the grave (name, age at death, skill line, epitaph, and the cause where the game or this patch knows it) with the head, body, likes and dislikes of the villager's last Village History snapshot ("(unknown)" when that does not settle who it was), and marked "Recorded from the grave". Which graves have their record is kept in 'Virtual Villagers Fun Patcher Data\Deaths\Virtual Villagers 5 Graves Logged - Save <n>.dat', so no grave is recorded twice; Start Over deletes it. Every villager who joins the village without being born into it -- a new village's founders, an island event's newcomer, the Barrel of Babies, the Custom Island Event's new villagers, a Heathen converted to a believer (a Heathen is never a villager) -- gets an "Arrived" record in the Births and Conceptions log ('Virtual Villagers 5 Births and Conceptions Log <n>.txt'), written at the next save: the name, the age when they arrived, sex, head, body, likes, dislikes, skills, and how they came ("Founder", the island event's title, "Barrel of Babies", "Custom Island Event", "Converted from the Heathens", or "unknown"). A birth is never an arrival. Villagers already in a village who arrived before this record existed (no Birth or Arrived record with their name, head and body) each get one the same way, only when the player says so, marked "Recorded afterwards (arrived before this log existed)", as "Founder" when the village's first Village History snapshot lists them and otherwise with how they came unknown -- exactly once: 'Virtual Villagers Fun Patcher Data\Arrivals\Virtual Villagers 5 Arrivals Recorded - Save <n>.dat' then says it is done; Start Over deletes it. A villager the save says was born here (their record keeps their parents) who has no Birth or Arrived record -- born before the log existed -- gets, the same way and only when the player says so, a Birth record written from the save, with their parents as the save keeps them, marked "Recorded afterwards (born before this log existed)" -- exactly once: 'Virtual Villagers Fun Patcher Data\Births\Virtual Villagers 5 Births Recorded - Save <n>.dat' then says it is done; Start Over deletes it. At every save, the village is checked against the one saved before: a villager who left with no Death or Disappeared record, or arrived with no birth or known arrival, is written with everything known about them to the Unaccounted Villagers log ('Virtual Villagers 5 Unaccounted Villagers Log <n>.txt' in 'Virtual Villagers Fun Patcher Logs\Unaccounted Villagers'). Both logs are headed with the village and its save slot, are created when a village is started and again after Start Over (which deletes them with the village), only ever grow, and start a new numbered file after every 256 records. The village as it was at each save is kept in 'Virtual Villagers Fun Patcher Data\Unaccounted Villagers\Virtual Villagers 5 Village Roster - Save <n>.dat'; Start Over deletes it. The cause is the one New Believers itself records and shows on the grave. **The first save after this patch is installed only starts the check: nothing is reported about anything that happened before it.** **The patch's DLL is loaded and its hooks installed as soon as the game is opened, before any village is loaded, so the deaths, burials, disappearances and arrivals of the catch-up on time away (and of a Time Warp) are recorded as they happen, like any others.** **The logs are written by Write Births and Conceptions Log to Text File's DLL: with that patch off, none of them is written.** **Runs on the Origins-exclusive base, which the patcher installs automatically with it**, so selecting this patch also adds the Origins Upgrades buttons to the Tech and Villager Details screens. That base's companion loads this patch's DLL; if the DLL cannot be loaded, the game runs unchanged.

- Patch ID: `vv5_cause_of_death`

**Fix Vanilla Bugs**

Fixes bugs in the base game. Every default name can be chosen: the game numbers its 185 male and 185 female names from 0 but picks a number from 1 (and never the last one), so Ago and Yapili (male) and Aipi and Zucca (female) could never be given; now every name in each list can come up, for new villagers and twins alike. **Needs no other patch.**

- Patch ID: `vv5_fix_vanilla_bugs`

**256 Villagers (Experimental)**

Gives New Believers 256 villager slots (numbered 0 to 255) instead of 150 (believers, Heathens and Reanimate stand-ins share them, as in the stock game). The game's villager table is moved to a new, larger place in memory, and every part of the game that goes through it -- births, Heathens, Island Events, the Villager Details screen, saving and loading -- is widened to match. The population modes' caps in a 256 build: Immediate Fixed Max Pop allows 256 at once; Collection Progression Max Pop starts at 241 and adds 0-15 collection points, reaching 256 with everything; No Population Increase keeps the stock cap of 105, and only the table is larger.

**Where its saves go.** A build with this patch is named 'Virtual Villagers - New Believers - Modded 256.exe' (in a 'Virtual Villagers - New Believers - Modded 256' folder) and keeps its saves, and the patcher's logs and data files, in its own folder, 'Documents\LDW\Virtual Villagers - New Believers - Modded 256\', so they never mix with the 150-slot saves of the ordinary '- Modded' build. The patcher does not fill that folder: to carry on an existing village, copy its save files (the .ldw files) from 'Documents\LDW\Virtual Villagers - New Believers - Modded\' into it yourself. The old save loads with all its villagers. The first time the game saves it, it is written in a longer 256-slot format, and from then on it opens only in a 256 build; a 150-slot game cannot read it. Keep your ordinary '- Modded' saves as a backup.

**This patch is experimental and off by default.** It has passed the patcher's build tests and live tests that filled the village to the last slots, but it has had far less play than the other patches. Select All Patches and Default Patches leave it off; Owner's Defaults ticks it.

- Population modes: stock, collection_progression, immediate_fixed
- Patch ID: `vv5_population_256`

## The Origins upgrades menus

Each game's **Enable Origins Tech, Details, and Village-Wide Upgrades** patch
adds two menus reached from an **Upgrades** button. Every game uses the same
wording and the same shell, so the menus read identically across all five.

### Tech screen — `Origins Upgrades`

| Upgrade | Cost |
|---|---:|
| Time Warp - Advances the Village Clock | 50,000 |
| Island Event | 30,000 |
| Barrel of Babies | 75,000 |
| Tech Point Doubler | 500,000 |
| Food Point Doubler | 500,000 |
| Full Heal / Cure All | 30,000 |
| Grant Running to All Villagers | 1,000,000 |
| Grant Full Mastery to All Villagers | 1,000,000 |
| All Villagers are Exactly 18 | 1,000,000 |
| Complete All Collections | 1,000,000 |
| Reset All Collections | 1,000,000 |
| Equal Division of Labor (Includes Parenting) | 1,000,000 |
| Equal Division of Labor (No Parenting) | 1,000,000 |
| Change Appearance for All | 450,000 |

A New Home has no Collections rows, because it has no collections to complete
or reset. Every other row it shows uses the same wording as the rest.

**Time Warp** advances the village by **three villager years on slow, six on
normal and twelve on fast**. The amount depends on the speed because the game's
own clock does: one villager year takes 3 h 20 m of real time on slow, 2 hours
on normal and 1 hour on fast, so the same purchase buys more years the faster
the village is running. The confirmation names the cost, the speed and the
exact number of years before you commit, and the result says how many years it
advanced. The cost is written the same way as every other row -- **50,000**, not
50000.

While the game is **paused** it advances nothing at all, so it is refused with
a message and costs no tech points.

**Island Event** and **Barrel of Babies** are *queued* rather than fired the
instant you buy them. Each waits a few real seconds after you close the Tech
screen before it runs, so the purchase confirmation can be read first and the
event does not arrive underneath the menu you bought it from. The delay also
keeps a natural island event that happened to be due at the same moment from
consuming the one you paid for -- the failure that made a purchased Barrel look
like it had done nothing at all.

New Believers is the one exception today: its two rows still fire on the next
scheduler tick rather than after a delay.

While one of these events is still on its way, its row reads **Why not?** in all
five games instead of offering a second purchase. Clicking it explains why and
closes nothing -- so a second copy cannot be bought and cannot be charged for.

The wording differs between games, deliberately. Virtual Villagers 3 and 5
track a purchase directly, so they can say an event *has already been bought*.
The other three read a countdown that naturally scheduled events also write,
which cannot say who queued it -- so they say an event *is already queued and on
its way*, rather than claiming the player paid for something they may not have.

The same button appears when a **Barrel of Babies** cannot be delivered because
the village has no room for the three children it brings. That message says so
explicitly, and notes that a villager who has died still occupies a slot until
they are buried, so burying any remains may free the space. The two causes are
told apart on purpose: waiting clears a queued event, but waiting will not empty
a full village.

Earlier versions drew these rows as a disabled button reading *Unavailable*,
which said that the upgrade could not be bought without saying why or whether
waiting would help -- and, being disabled, the button could not respond to a
click at all.

**Barrel of Babies** delivers three children, so it is only sold when the
village has room for all three -- that is, when the population is at or below
its current maximum minus three. Above that it refuses and deducts nothing.
Room is measured in *occupied villager records* rather than in living
villagers, which is deliberately conservative: a record counts as occupied
whether the villager in it is alive, unborn, or a skeleton, so the check never
hands out a slot that is already spoken for. `docs/duplicate-purchase-guards.md`
records that reasoning, and the one measurement question still open about it.

Because the barrel is queued, the village can fill up during the wait. The room
check therefore runs **again at delivery**, and if there is no longer space the
barrel is *held* rather than spent: it stays queued and arrives once a slot
frees. You are never charged twice. A paid barrel is delivered as the game's
own barrel event at full strength, which is what makes it three children; it
leaves nothing behind that could change a later crate, sack or barrel.

That covers a barrel losing its room *during the queue delay*. It is not a
promise that every paid barrel always delivers three children: a separate,
still-unexplained short-spawn has been reproduced in a village with plenty of
free records, and `docs/duplicate-purchase-guards.md` records what is and is
not known about it.

Results that count villagers name the number and the reason, and read correctly
at one: *"Skipped over 1 villager. Reason: already likes running."*

Every row that completes says so, including Complete and Reset All
Collections, both Equal Division of Labor rows and Change Appearance for
All. In The Tree of Life those five used to apply silently -- the purchase
worked, but nothing confirmed it.

### Villager Details screen — `Villager Upgrades`

| Upgrade | Cost |
|---|---:|
| Grant Youth (-35 years, min age 5) | 50,000 |
| Grant Full Mastery | 100,000 |
| Grant Running | 40,000 |
| Set Age to 18 | 50,000 |
| Change Appearance | 5,000 |

**Change Appearance** and **Change Appearance for All** offer every head and
body the game ships, for both sexes: **20 each in A New Home** and **30 each in
the other four**. Both choosers offer the same range, so anything you can set on
one villager you can set for the whole village.

**Change Appearance for All** adds four village-wide groups on top of that pair
of per-sex selectors, and all five games now carry the same set:

- **Village-wide Heads** -- *Off (use the Head selectors above)*, *Random (by
  gender)*, or one hair bucket for everyone: *All Black Hair*, *All Brown
  Hair*, *All Red / Ginger Hair*, *All Blonde Hair*, or *All Other Hair /
  Styles*. Picking a head for the whole village raises the same genetics
  warning the per-villager chooser does.
- **Village-wide Bodies** -- *Off (use the Body selectors above)* or *Random
  (by gender)*.
- **Village-wide Single Mask Color** -- give every villager the same mask, or
  *None (remove all masks)*.
- **Mask Distribution (all villagers)** -- *Off*, *VV5-style* (1 Chief, 4
  Purple, up to 7 Red, up to 10 Orange, rest Blue), *Random*, or *Equal Colors*
  (all five colours, balanced between the sexes).

A village-wide group set to **Off** leaves that attribute alone and greys out
nothing; set to anything else it overrides the matching per-sex selectors,
which are disabled while the override is active so the two cannot disagree. The
single-colour and distribution mask choices are one exclusive set, so a colour
and a distribution can never both be selected.

Neither chooser charges for a change it did not make. **Change Appearance**
costs nothing if you press OK on the head, body and mask the villager already
has. **Change Appearance for All** counts what actually changes rather than who
was looked at, so it charges nothing when every villager already matches your
selection -- including when you set options only for a sex your village does
not currently have.

### Buying, removing, and the green checkmarks

Choosing a row asks `Do you want to buy ... for ... tech points?` and applies
nothing unless you confirm. If an upgrade would change nothing, the game says so
and **no tech points are deducted**.

**Tech Point Doubler** and **Food Point Doubler** are the only two upgrades you
own rather than perform. Once bought, their button changes from **Buy** to
**Remove**, and removing one takes effect immediately and issues no refund.

A small green checkmark appears on **exactly two rows and nowhere else**:
**Tech Point Doubler** and **Food Point Doubler**, and only while that doubler
is owned in the current save. Nothing else is ever marked -- the Villager
Details screen shows no checkmarks at all, and a row that would currently do
nothing tells you so in its result instead.

The checkmark never means a row is unavailable. Every visible row stays
clickable, and a row that changes nothing says so and deducts no tech points.

**Switching save files clears some upgrade state, and the details differ by
game.** Two kinds of state are affected when you load a different save slot:

- **Doubler ownership.** A doubler bought in one village used to stay owned in
  another that never paid for it. A New Home and The Lost Children keep that
  flag on the village itself, so they were never affected, and returning to a
  village restores exactly what it bought. The Secret City, The Tree of Life
  and New Believers keep it in memory shared by every save, and that memory is
  not part of the saved village, so there is nothing to reload: loading a
  different village now clears it. In those three, a doubler stays owned only
  until you switch villages -- come back to the village that paid for it and
  you will need to buy it again, the same as after restarting the game.
- **A queued Island Event or Barrel of Babies.** In all five games a pending
  event no longer follows you into another save, where its row would have read
  **Unavailable** and the event could have been delivered to a village that
  never bought it. A New Home, The Lost Children and New Believers already
  behaved this way; The Secret City and The Tree of Life now do too.

Saving does not trigger either reset -- only genuinely changing slots does, so
a doubler you own survives an autosave.

Both menus close with **Cancel** or the Esc key, and each shows
`Press ESC to exit this menu.` once.

### Buying the Doublers

Both Doublers are buyable in **all five games** at 500,000 tech points each. An
owned one can be removed for zero cost with no refund, and bought again
afterwards at full price.

An earlier release briefly held new purchases in A New Home, The Secret City and
The Tree of Life while their exact-build provenance was being checked. That hold
was lifted in v1.34.14 -- the gate that set the rows "Unavailable" is gone, and
those three games buy, remove and repurchase like the rest.

### The Secret City: Magic level and research points

The audit behind that decision also established what Magic actually does to
research. Magic level 1 or higher adds a deterministic flat `+1` tech point to
each completed research callback. It does not change research speed, duration,
the base award, the RNG, or Research-skill gain. Native research adds the base
award, the optional quarter-base bonus, the Magic `+1`, a timed `+1`, and an
independent RNG `+1`, in that order.

### The Lost Children: known crash

**A player reported that both Time Warp and Food Point Doubler crash The Lost
Children immediately after the purchased/success dialog is displayed.** That
records the observed trigger only; it does not establish whether the charge or
the action persisted.

**A later playtest did not reproduce it.** The player has since confirmed that
Time Warp and the Food Point Doubler no longer crash The Lost Children. That is
one clean run against one report, so it is recorded as what it is -- the trigger
failing to reproduce -- rather than as a proven fix. The `.shr` repair described
below is the most likely reason, but nothing here establishes that it was the
cause.

Nothing is disabled because of it: the VV2 Origins patch and its dependent
village-wide upgrade are selectable, and its Doublers buy, remove and
repurchase like every other game's.

The crash audit did find `.shr` raw-offset versus virtual-address confusion in
the VV2 builder, displacing some helper and header references by `0x2000`. The
isolated VV2 builder now corrects those runtime VAs, extends the `.shr` virtual
size and execute flags, and maps the payload's `.rdata` tail as executable.
Static render and regression checks pass. That is not yet proof the reported
crash is gone -- only a playtest can establish that. Every unrelated VV2 patch
is unaffected.

Since then the machine's actual crash records have been examined, and they do
narrow the question, though they do not close it. Of 61 recorded Lost Children
crashes, the two most frequent sites happen on the **unmodified** executable as
well as the modded one. That executable contains none of this project's code, so
those two cannot be caused by it. Two further sites appear only on modded builds,
at the two instructions immediately after the mask compositor hook; both were
checked in a disassembler and the hook replays the instructions it displaced with
the correct registers, while its sweep stays inside the structure it walks. That
rules out the two ways the hook could have caused them directly. It does not
prove the patch is uninvolved by some other path -- a hook can corrupt state that
stock code dereferences later -- so this narrows the question rather than
answering it.

The full measurements, including what would falsify them, are in
[docs/crash-dump-findings.md](docs/crash-dump-findings.md).

### A New Home: a Time Warp crash, once

A player bought Time Warp in A New Home and the game crashed on returning to the
village. It has happened once, with a full memory dump, and it has not recurred.

The fault is a null pointer dereferenced without a check, in game code this
project does not patch. The bytes that fault are byte-identical to the
unmodified executable, the call reaches them through a vtable slot no patch here
touches, and no code from this project appears anywhere on that path. The
patcher's file copying is also not implicated: it copies the game folder whole
and verifies every file by size and checksum, refusing to continue on a
mismatch.

That is not the same as this project being ruled out, and it is not written as
though it were. Buying Time Warp runs this patcher's code before the game
returns to the village, so it remains possible for that to leave the game in a
state its own code then trips over. Nothing measured so far excludes it.

What is **not** established is which sequence of events leaves the game in that
state. Because that is untraced, no fix is proposed -- a change aimed at a cause
nobody has pinned down could not be shown to work, and might hide the next
occurrence. Two plausible explanations were investigated: one was ruled out from
the game's own code, and the other could not be settled from a crash dump alone,
because a dump records a single instant. The write-up records exactly what each
one rests on, so neither is re-proposed as settled.

If it happens to you, the crash dump is what makes it traceable. The measurements
are in [docs/crash-dump-findings.md](docs/crash-dump-findings.md).

### Status

These menus are verified by build-level tests -- exact bytes, dialog wording,
and the purchased/success dialog paths -- and the patcher refuses to write an
executable whose bytes it cannot account for. They have had far less **playtest**
coverage than the ordinary patches, so **runtime** confirmation in a real village
is still the last step for many rows. The VV2 **crash** above did not reproduce
in a later playtest; the A New Home one happened once and its trigger is still
untraced.
Whatever happens, the unmodified original EXE and folder are always left
untouched beside the modded copy.

## Population safety

### New Believers: Heathens and physical slots

Heathens already occupy records in New Believers' 150-record villager pool. Converting one changes that existing record from Heathen to believer; it does not create an additional villager record. The population patch therefore measures physical slot demand before allowing births: every active record counts, including unconverted Heathens and corpses that the game has not released yet, and nursing babies reserve the records they will need later.

This means births can temporarily stop below 150 displayed believers while Heathens remain, but conversions are still safe and can continue at the physical ceiling. After every Heathen has been converted and old corpse records have cleared, the full 150 slots can be believers.

## Safe twins and triplets at the ceiling

All five stock games test the population limit once before choosing a singleton, twins, or triplets. Without an additional guard, a multiple birth at maximum minus one can report maximum plus one or maximum plus two, even though no corresponding villager records remain.

All three public modes apply a slot-saturation guard at the game's physical
boundary. No Population Increase leaves the stock cap, collection behavior,
and progression untouched; Collection Progression and Immediate Fixed retain
their documented cap behavior. The safety layer is allocation-only:

- Three or more slots left: singleton, twin, and triplet rolls are unchanged.
- Two slots left: a rolled triplet safely becomes twins.
- One slot left: a rolled twin or triplet safely becomes a singleton.
- No slots left: the normal population predicate blocks the birth.

This lets reproduction fill the final slot without permitting the population to exceed the game's real villager array. New Believers uses physical slot demand rather than only its displayed believer count, so still-active Heathens, corpses, and nursing babies cannot make the final multiple birth overbook the shared pool.

### Island Event population safety

All five games also contain Island Events that add villagers. The patcher guards every identified direct population-adding outcome: repeated allocations stop when the selected physical pool fills, and VV4/VV5 Abandoned Infants is reduced from six babies when fewer than six physical slots remain. VV3-VV5 use their verified 150-record boundary, or 256 in a build with 256 Villagers (Experimental). Events that remove villagers are unchanged. VV5 conversions and The Defector are unchanged because they reclassify existing records instead of allocating new ones.

### No villager without a free record

A corpse keeps its villager record until the game removes it, and so do The
Tree of Life's ghosts and New Believers' Heathens, and every baby still owed
needs one. So "the population is below the cap" never meant "a record is
free". In every population mode, including No Population Increase, and at 256
in the 256 Villagers builds, the safety layer makes every creation ask the
records themselves, and nothing is spent when there is none:

- A delivery waits, with the pregnancy kept, until its whole litter fits.
  The original games cleared the pregnancy and lost the baby.
- The room check behind conceptions, barrels and island events counts every
  occupied record plus every baby still owed.
- A New Home's Golden Child puzzle fires only with a free record. With none,
  the original game made the Golden Child in a record past the end of the
  table, where nobody could see him, and spent the mother's pregnancy.
- A New Home's Mysterious Face, The Lost Children's Strange Request, Savage
  Child and Silver Mirror, and The Secret City's Mysterious Vial and Crystal
  of Reflections are offered only with room. The Crystal checks before it
  changes anyone's likes.
- New Believers' Reanimate is refused, with nothing spent, when no record is
  free, and the gray message bar says "There's no room in your village to
  revive this person." The original game crashed.
- Twins and triplets at conception follow the free records. Earlier patcher
  builds read A New Home's lifetime Babies Made count here, so a village that
  had made 256 babies never had twins again.

## Requirements

The patcher runs from source through the bundled launcher. It needs nothing
beyond a normal Python install.

| Requirement | Detail |
| --- | --- |
| Windows | The five games are 32-bit Windows executables and the patcher writes Windows PE files. `Launch Virtual Villagers Fun Patcher.bat` is a Windows batch file. |
| Python 3.10 or newer | Download from [python.org](https://www.python.org/downloads/). During setup keep **tcl/tk and IDLE** ticked, which is the default: the patcher's window is built with `tkinter`. |
| No extra packages | The patcher uses only the Python standard library. There is nothing to `pip install`, and no internet connection is needed to patch. The **Check for updates** link is the one feature that reaches the internet, and it is entirely optional: it just opens the patcher's GitHub page in your browser, and everything else works with no connection at all. |
| An original game | The free downloads from [ldw.com](https://ldw.com), installed normally. Only those builds are supported. |
| Free disk space | The patcher copies each game whole rather than editing your original, so each modded copy needs about as much space as the game folder itself: roughly 25-85 MB per game, or about 300 MB for all five. |

The launcher tries `py -3` first and falls back to `python`, so either the
Python launcher or `python` on your `PATH` will do. If a console window opens
and reports that Python was not found, install Python and try again.

Your original game is never modified. Every patch is written into a separate
`(Game name) - Modded` folder, so you can delete that folder at any time and
keep playing the original.

The top-right of the window shows which build you are running, next to a
**Check for updates** link. Clicking it opens the patcher's GitHub page in
your browser. It deliberately makes no judgement about which build is newer: the
GitHub page already shows the latest release, and your build version is printed
directly beside the link, so the comparison is yours to make and nothing here
can hang or report a wrong answer.

## Use

1. Extract the latest release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Select a population mode.
4. Choose **One Game** or **All 5 Games**.
5. For one game, select its original EXE. For all five, select one folder per game.
6. Optionally choose a **Modded output location**. This is the parent folder that
   will receive each generated `(Game name) - Modded` folder. Leave it blank to
   keep the original sibling-folder behavior.
7. Validate, dry run, or create the copied-and-modified game folder set.

While the patcher is working -- loading its patches at startup, validating, dry
running, or copying and patching a game folder -- it shows a **Please wait**
window with a progress bar. Copying a whole game folder takes a moment; the
window means it is working, not stuck.

The window has two tabs: **Patches** (the population mode, the patches, the output location and the One Game / All 5 Games tabs that create the modified games) and **Tools** (everything else: backing up and restoring saves, renaming a tribe, checking and repairing logs, the Family Tree Maker and the Village Matchmaker -- for the game chosen on the One Game tab, or any of the five).

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The One Game tab includes clickable **Open Vanilla EXE Folder** and **Open Modified EXE Folder** links. All 5 Games provides matching Vanilla folder and Modified folder links on every game row. After patching, a compact confirmation window provides clear clickable links to both folders for every completed game.

**Back Up Saves** copies your modded games' saves, in all five games. On the **Tools** tab, click **Back Up Saves** (the game chosen on the One Game tab), **Back up saves** on any game's row, or **Back Up Saves (All 5)...** for every game. The patcher finds each game's save folders in `Documents\LDW` (the Documents folder Windows reports, so a Documents moved to OneDrive is found): `(Game name) - Modded`, `- Modded 256` and any other `- Modded...` folder, and lets you tick which to back up. Each chosen folder -- the `.ldw` saves, the `Virtual Villagers Fun Patcher Logs` and `Virtual Villagers Fun Patcher Data` folders and everything else in it -- is copied into a new `Backups\Backup YYYY-MM-DD HH-MM-SS` folder inside that save folder, and every copied file is checked against the original by size and SHA-256. An existing backup is never replaced, and no patcher feature (Start Over included) reads, moves or deletes anything in `Backups`. If the game is running it is paused for the copy and then resumes by itself; it is never closed. These games save only when you quit them normally, so a backup taken while a game is running holds the village as of its last save. If the game cannot be paused, nothing is copied and the result says why. The result window reports the file count and size and has an **Open Backup Folder** link.

**Restore Saves...** (Tools tab, and **Restore saves...** on every game's row) lists that game's backups newest first, with the date and time, the variant it came from, the village in each save slot and the size. Restore **the whole save folder** or **one save slot only**; a confirmation lists exactly which files will be replaced, added and removed. The game must be closed -- quit it from its own menu first, because a running game writes its village over the restored save when it quits -- and the patcher never closes it for you. Before anything changes, the current saves are backed up as `Backup <date> (before restore)`, so every restore can be undone; each file is put in place only after its copy is checked against the backup, and on any failure every file already changed is put back. A one-slot restore touches only that slot's saves (`<save>N.ldw` and its two older generations `N+20` and `N+40`) and that slot's patcher files (named `Save N`, or whose log header says `(Save N)`); it is refused, with the reason, when the backup and the current saves differ in a file that belongs to no single slot, such as the game's shared slot-0 save. **Delete Backup...** removes a chosen backup after asking; a restore never changes or deletes a backup.

**Rename Tribe** changes a tribe's name inside its save, in all five games and every Modded save folder (including `- Modded 256`). On the **Tools** tab, click **Rename Tribe...**, **Rename tribe...** on any game's row, or **Rename Tribe...** below them; pick the game, its save folder and the tribe (each slot is listed with its current name), then type the new name. The game's own limit applies, with a live character counter: **31 characters in A New Home and The Lost Children, 19 in The Secret City, The Tree of Life and New Believers** -- the most each game's own name entry stores -- and only characters the game can take (A New Home and The Lost Children cannot draw `# $ % & ( ) * + ; < = > @ [ \ ] ^ _ { } | ~`). A name that breaks the rule is refused, never cut short. A name wider than the game's Change Tribe button (181 pixels, or 130 in the later three) is allowed, as the games make such names themselves; the window notes that that one screen will show it shortened. **The game must be closed** (it saves when you quit, which would put the old name back); a running game is refused and never closed. Before anything is written the save folder is backed up into `Backups\Backup YYYY-MM-DD HH-MM-SS (before rename)`, which **Restore Saves...** lists like any other backup, so a rename can be undone. The name is changed in the slot's save, its older generations and the slot list, each file written to a temporary file, swapped in and read back; any failure puts every file back. The patcher's logs keep following the village: nothing already written is changed, and each of its logs gets one line, `Tribe renamed from <old> to <new> on <date>`, which the logs and Start Over follow -- the renamed village is the same village, so its logs, statistics, stews and elders carry on.

**Check Logs...** shows, for one village, whether every log and data file the patcher keeps agrees with its save, in all five games and every Modded save folder (including `- Modded 256`). On the **Tools** tab, click **Check Logs...**, **Check logs...** on any game's row, or **Check Logs...** below them; pick the game, its save folder and the tribe. It runs the read-only checker `scripts/vvfp_consistency_check.py` (see [the cross-check](docs/first-load-cross-check.md)) inside the patcher and shows its report in a scrolling window: each file with **OK**, **WRONG**, **NOTE** or **UNCHECKED** and the details, then a summary line. It only reads -- nothing is written, moved or created, and the Backups folder is never read -- so it works while the game is running.

**Repair Logs...** (the same three places, **Repair logs...** on the rows) is your go-ahead for the game to repair that village: it repairs nothing itself, and the next time you **play** the village the game repairs everything confirmed wrong **without asking** -- A New Home's parents as soon as the village has settled, the rest at its next save (the save the game makes when you close it, at the latest) and anything still left right after that save -- each file backed up first (`<file>.before-v1.35.58-repair`) and every change listed in the Repairs log; then the go-ahead is used up. Close the game normally from its own menu so the repairs are saved. **The game must be closed** when you click it; a running game is refused and never paused or closed. The logs are checked first and the result shown -- if nothing is found wrong the window says so and offers to go ahead anyway -- then the save folder is backed up into `Backups\Backup YYYY-MM-DD HH-MM-SS (before repair re-arm)` (listed by **Restore Saves...**), that slot's "already checked" markers are cleared (`Virtual Villagers Fun Patcher Data\Cross-Check\Virtual Villagers 1 Cross-Check - Save N.dat` in A New Home, `...\Deaths\Virtual Villagers G Graves Logged - Save N.dat` and `...\Arrivals\Virtual Villagers G Arrivals Recorded - Save N.dat` in every game, `...\Births\Virtual Villagers G Births Recorded - Save N.dat` in The Lost Children to New Believers) and the go-ahead is written (`...\Cross-Check\Virtual Villagers G Repair Approved - Save N.dat`; Start Over deletes it with the village, and **Check Logs...** shows it while it waits). No log, backup or other data file is removed, and nothing is written twice: each part of the repair counts what the logs already hold before it writes.


**Repair Logs' checklist (v1.35.61).** Repair Logs first shows what it can do for the village, each line ticked or unticked by you: the game's own repair the next time you play (above); correcting like / dislike words an older patcher wrote with the wrong list; and adding to records written by an older patcher what they lack -- the **Sex** line, the **Special villager** title (Tribal Chief, Retired Heathen Chief, Heathen roles, Former Heathen, Golden Child, Esteemed Elder, Scholar), the **Custom title**, the **Mask** and, on Birth records, **Born as: Single birth / Twin / Triplet**. Each is decided from the save, the patcher's own data files and the logs themselves wherever they settle it -- a record's own skills or grave, the latest Village Population page, the mother's Conception record -- and **whatever they cannot settle is asked**: **Answer the questions...** lists each one with its own choices (a title or mask "from which Village History snapshot on", how many babies were born together, a sex nothing records); **Don't know** and **Only from now on** add nothing. Check Logs lists the same things as NOTE lines. Every log is copied beside itself first (`<file>.before-v1.35.61-repair`, never replacing a copy), rewritten through a temporary file, and the additions are listed in the Repairs log.

**Give villagers last names** (the same checklist, unticked until you **Choose...**): each living villager of the village gets the last name you pick after their name -- **Last names come from** **From the mother**, **From the father** (the default), **Equal mother/father** (a 50:50 chance of either parent's for each child, the same pick each time), **Random from list** (one of the game's 50 for each villager), **Choose from list** or **Type custom name...** (one name for every villager) -- a family is a couple and their children, so each child carries a parent's name, and a villager with no recorded parent (a founder, a newcomer, an arrival) gets a last name of their own, their family's from the game's list unless another such villager has it; then change any one, from its list (the father's and the mother's come first), by typing your own, or to none. A parent's last name is the one their name already carries, or the one being given them now, so names pass down the generations -- **in the save and in every log**, so the logs keep matching the save. Everything the patcher keeps that holds the name follows: the children's father and mother names in the save (The Lost Children to New Believers), the masks, custom titles and New Believers' Former Heathens, A New Home's parent records, the Unaccounted Villagers roster, the statistics roster and the Village Elders, and every record that names the villager by name, head and body. A record with the old name but other looks (before a Change Appearance) is asked about; a dead villager's records keep their name. The game must be closed; the save folder is backed up first (`Backups\Backup ... (before last names)`), every file is swapped in through a temporary file and read back, and any failure puts every file back as it was.

**Check logs automatically** (a tick box beside those links on both tabs; **on** by default, and remembered; the patch selection buttons leave it alone) is written into every game you create from then on -- a game already created keeps its own setting until you create it again. **Off**, the games never check or ask anything while you play: use **Check Logs...** and **Repair Logs...**. **On**, the game checks each village silently a few seconds after it loads and, only if something is confirmed wrong, asks **Repair** or **Not now** when you **close the game** -- after its own save, never while you play. **Repair** repairs everything found there and then (backed up first, listed in the Repairs log); **Not now** changes nothing, and you are asked again the next time you close the game after playing that village. The question is about the village you played last, and if nobody answers within five minutes the game simply closes, as with **Not now**. The question ends by saying how to stop these checks: untick **Check logs automatically** in the patcher and patch the game again. On the command line it is on by default; `--no-check-logs-automatically` turns it off. See [the cross-check](docs/first-load-cross-check.md).

**Family Tree Maker...** (Tools tab, **Family tree maker...** on every game's row, and below them) draws a village's family tree, in all five games and every Modded save folder: who descends from whom, read from the save and the patcher's logs, and each villager's generation -- the founders are generation I, a villager who arrived later is in the generation they first appear in, and a child is one below their younger parent. Pick the game, its save folder and the tribe, and the game's folder so each villager shows their own head (the Change Appearance menus' front view). Every villager is numbered, generation by generation; each portrait says their name, age in game units and years, and *(deceased)*, *(disappeared)* or *(left the village)*; a square is a male, a circle a female, a diamond an upcoming child; twins and triplets hang from a triangle. **Every unrelated villager has a colour of their own, and each pairing has one colour** for its whole connector -- the line joining the two parents, the line down and the line joining their children -- which their children's portraits share. **Positions** are *dynamic* (each family under its parents, stepping down a row when crowded, as in a hand-made tree) or *one straight row for each generation*; no line ever runs through a portrait. The editor (**Help (F1)** lists every control): click a villager to select them (Ctrl+click adds, Shift+click a run, Ctrl+A everyone, Shift+drag a box); **drag anything to move it** -- villagers (every selected one together, their lines following), the title, subtitle, Key, generation labels and headings -- and right-click it to put it back; **right-click anything to change its colour** (with several villagers selected, all of them at once); put any villager in another generation, or move them left or right along theirs (the Villagers tab; the numbers follow, and the genealogy report keeps the records' generations); line things up with **smart guides** (snap to other villagers' and pictures' edges and middles, and the middle of the tree), **snap to grid** (with a grid you can show) and **Align** (lefts, centres, rights, tops, middles, bottoms, centre on the tree, space evenly) -- hold Alt to drag freely; drag empty space to move around; the mouse wheel or **+** and **-** zoom; F4 hides the side panel, F11 is full screen. Retype any portrait or generation label, give special villagers a coloured border with its name in the Key (**Special Marks**: ready-made Tribal Chief, Esteemed Elder, Scholar, Golden Child, Favourite, Heathen and Founder, or your own), choose any font on the computer for any words, pick a background colour, gradient, ready-made picture from any of the five games or your own picture (with its opacity), and add **stickers** -- any picture, the games' logos -- and **text boxes**, then move, resize and rotate them with PowerPoint-style handles, flip and fade them, and right-click them to layer (bring forward, send backward...), reset or remove them; **drag any piece of a line** to slide it, its joined pieces following and its ends staying on their portraits; backgrounds, logos and pictures are chosen from thumbnails, and every font from a list written in each font. Ctrl+C, Ctrl+X, Ctrl+V (a sticker, a picture copied from anywhere, picture files copied in File Explorer, or words, which become a text box), Ctrl+D, Ctrl+Z, Ctrl+Y, Ctrl+S, Ctrl+B / I / U, Delete, F2 and the arrow keys work as in any Windows program. **Save to Save Folder** (Ctrl+S) saves the tree as an editable tree file (`<tribe> (Save N) Family Tree.vvtree`) in the save folder's own `Virtual Villagers Fun Patcher Family Trees` folder, to be worked on later (**File, Open Tree File...** opens one), and closing the editor asks *Save changes to the tree before exiting?*; **Export as Picture...** (Ctrl+Shift+S) saves a PNG or JPG anywhere. Your edits are kept in `Virtual Villagers Fun Patcher Data\Genealogy\Virtual Villagers G Genealogy Edits - Save N.json`; the tree's web page, its picture and the genealogy report (everyone by generation, and everyone in order of appearance) are written to `Virtual Villagers Fun Patcher Logs\Genealogy`. **Nothing in the save or the logs is ever changed.**

More in the editor: **portraits** come in twelve shapes and more (square, rounded square, rectangle, circle, oval, heart, triangle, diamond, cross, X, plus, star, hexagon, octagon), drawn at their own proportions, with thin, thick, extra thick, dotted, dashed or dotted-and-dashed borders -- for every male, female or upcoming child, or for the villagers you select -- and **click one villager to resize or turn their portrait** with the same handles as a picture; set **sizes, line weights and line types in batch** (the size boxes change the tree as you type); show each villager's age in game units, in years, both or neither; make special marks a **glow** instead of a border, with its size and opacity; set the **opacity** of the words, the boxes behind them, the portraits and the lines; **right-click to add** a text box, picture, shape or logo, or **to delete** anything -- a villager, a line, the title, a whole generation label or one line of it -- and restore it from **Deleted items**; number the generations in Roman numerals or numbers; **Renumber** the villagers whose text you edited; split a long family onto **pages** (each its own tree, not joined to the page before; saving a picture saves every page); ready-made backgrounds include plain colours, gradients, rainbows across or down, and pictures (the picture's opacity works on any colour, Transparent included); **Allow diagonal lines** (off unless ticked) lets a dragged line move any way; Undo, Redo, **Update Family Tree from Logs/Saves** (F5: the save and the logs read again, every edit kept) and the Reset buttons sit under every tab, and every reset asks first. Upcoming twins and triplets are read from the mother's own record in the save.

**Village Matchmaker...** (the same places) suggests who to pair, by rules you tick -- every rule is yours to switch on or off: an age window of 18-49 (**Allow 50 and older**, or **Plan ahead** for any age), **close in age** within a number of years you set, **no shared ancestors** (since the tribe began, or within the generations you set), **related by at most** a percentage you set, no parent and child, full siblings, half siblings, grandparent and grandchild, aunt or uncle and niece or nephew, or first cousins, **not already expecting**, **different last names**, and **fresh blood first**. Relatedness is worked out from the whole recorded family (double cousins included). It suggests one partner each, least related first, and lists every allowed partner for each woman; when the rules allow no pair it shows the least related pairs instead. The suggestions are also saved as `Virtual Villagers Fun Patcher Family Trees\Virtual Villagers G Village Matchmaker - Save N.txt` in the save folder, beside the family tree files, and your ticks are remembered. It only suggests: nothing in the game is changed.

The **Additional fun patches** section is grouped in game order, with each
game's patches sorted by patch name. It includes **Select All Patches**,
**Default Patches**, **Owner's Defaults** (every patch except Learning Skills
Never Fails, so Story / Cheat Upgrades and 256 Villagers (Experimental) too) and
**Deselect All Patches** buttons. They change every optional
fun-patch checkbox at once without changing the selected population mode, and the
selection is remembered normally.

For every selected game, all three modes create **`(Game name) - Modded`**
containing **`(Game name) - Modded.exe`** (**`(Game name) - Modded 256`** and
**`(Game name) - Modded 256.exe`** when 256 Villagers (Experimental) is ticked). By default the selected folder is beside the
supplied original; the GUI's **Modded output location** chooser can place all
selected games under another parent folder. It copies every file and subfolder
from the original game folder, verifies the copied files by SHA-256, keeps the
stock EXE in the copy, and adds the modified EXE plus, in its
`Virtual Villagers Fun Patcher Files` folder, the add-ons and the
`.patch-log.json` (see below). The
original folder and original EXE are never edited, renamed, replaced, or
deleted. Asset-swap patches such as VV1 Visual Mods, VV4 Optional
Text changes, and the VV5 Guardians of Isola Rewrite replace their listed image
and text files inside that copy only; the base-game files are restored whenever
the patch is not selected. Applying another population mode refreshes that mode's same short folder
after confirmation.

### The patcher's own files

Every file the patcher adds to a Modded folder is in one subfolder,
**`Virtual Villagers Fun Patcher Files`**, beside the modified EXE: every add-on
DLL (`VVFP ... .dll`, including `VVFP Startup.dll`), the images only those
DLLs read, the `.patch-log.json` and the `VVFP Transparency Log.txt`. The game
folder itself holds only the game's own files, the modified EXE and that one
folder. The add-ons are always loaded from that folder by their full path,
built from the modified EXE's own location (never from the current folder or
the Windows DLL search order), and with Unicode paths, so a game installed in
a folder with accented or Japanese characters in its name still loads every
add-on and writes its logs. A missing folder or DLL just switches that add-on
off; the game always starts. If the Modded folder's path is so long that an
add-on's path would reach Windows' 260-character limit, the patcher says so
and writes nothing, so choose a shorter output location.

The only patcher files outside that folder are ones the game itself opens
from its own folders by name, so they must stay where the game looks:

| File | Why it stays in place |
| --- | --- |
| A New Home's Visual Mods images (`Images\garden_restored.png`, `lagoon_restored.jpg`, `MapX1Y2.jpg`, `MapX2Y1.jpg`) | replace stock images the game opens from `Images` |
| `Images\mask_atlas.png` (A New Home Origins) | the game's own sprite loader opens it by name |
| `Images\vvfp_sort_band.png`, `Images\vvfp_sort_radio.png` (A New Home Sort By) | the game's own sprite loader opens them by name |
| `Images\golden_mushroom.png` (Super-Secret Golden Mushroom) | the game's own sprite loader opens it by name |
| `Images\heathen_masks.png` (The Lost Children / The Secret City Origins; written by the add-on when the game starts) | the game's own sprite loader opens it by name |
| `Images\vvfp_mask_atlas00.png`, `Images\vvfp_bighead_mask_atlas00.png` (The Tree of Life Origins) | the game's own sprite loader opens them by name |
| `Images\bigheads_masks.png` (New Believers Origins) | the game's own sprite table names it |
| `Assets\sm.xml` (The Tree of Life Optional Text Changes, New Believers Guardians of Isola Rewrite) | replaces the game's own string table |
| New Believers' Guardians of Isola Rewrite images | replace stock images the game opens from `Images` |

Patching again over a Modded folder made by an older version moves
everything into the new layout: the loose `VVFP ... .dll` files, the loose
images only the add-ons read, the old `.patch-log.json` and the old
`VVFP Transparency Log.txt` beside the EXE are removed (only files the
patcher itself installed, matched by name and, for non-DLL files, by
content), and files you added yourself are kept.

## Exact-build safety

Support is bound to the exact SHA-256 and size of each researched stock executable. Unknown, modified, corrupt, duplicate, or incorrectly assigned EXEs are refused. Every original byte to be changed is guarded, the PE checksum is recalculated, and each result is read back and hashed. File size is preserved unless a selected patch appends a new section to the executable -- the Origins-based patches do, so for example A New Home grows from 581,632 to 589,824 bytes and New Believers from 991,232 to 1,024,000 -- in which case the section is declared in the PE headers like any other.

Every build that ships a companion DLL also ships `VVFP Startup.dll` and gets
one more small section, `.vvfpst` (4,096 bytes, read and execute only). It
replaces the game's own start-up call of `WinMain`: before the game opens its
window, it loads `VVFP Startup.dll` from the `Virtual Villagers Fun Patcher
Files` folder beside the EXE (by full path, with a Unicode path),
which loads and arms the patcher companions this build ships (never a stray
DLL left in the folder), and then the game starts exactly as before. So every
patch is running before the title screen and before any village loads --
including the catch-up on time away, when most births, deaths and island
events happen. A companion that is missing or fails to load is skipped; the
game always starts.

Bulk mode validates and renders all five inputs before writing. Each supplied
game folder is then copied into a hidden temporary sibling folder
(`.<Modded folder name>.staging-<id>`), the modified EXE and its companion files
are written and verified there, and only then is it renamed into place as the
short **`- Modded`** output folder. Re-running with overwrite replaces that same
Modded folder: files you added to it are carried over, the previous folder is
moved aside to a hidden `.backup-<id>` sibling while the new one is put in
place, and that backup is deleted once the new folder verifies, or renamed back
if anything fails. If a failure leaves something that cannot be restored
automatically, it is kept in a `.recovery-<id>` sibling rather than deleted.
The supplied original folders remain unchanged.

Stock game executables, saves, and generated playtest outputs are never committed.
The disabled VV4 Full Mastery C6 candidate carries its exact mockup provenance
and baked PNG source asset under `assets/candidates/vv4_full_mastery/`; its
constructor bytes require fresh independent recertification, and all
Expanded-256 population modes are removed from the active patcher.

## Command line

Pass `--patch-mode stock`, `--patch-mode collection_progression`, or `--patch-mode immediate_fixed` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. The available IDs are all current user-selectable per-game patches, including the five combined Origins Tech, Details, and Village-Wide routes and the ordinary VV1-VV5 patches. Each combined route automatically resolves its internal Origins base prerequisite, so its Tech-screen and Villager Details-screen buttons/upgrades are applied together with the village-wide payload; duplicate base entries, individual Full Mastery entries, and other withdrawn historical records remain hidden. Runtime/player confirmation remains pending. All three population modes accept the Origins-style routes in every game; the earlier restriction to `collection_progression` and `immediate_fixed` for VV3-VV5 no longer applies, because those routes' append layouts now certify under `stock` as well. The disabled VV3 Full Heal / Cure All candidate is not a CLI or catalog ID. The per-game Village Statistics IDs are `vv1_write_village_statistics`, `vv2_write_village_statistics`, `vv3_write_village_statistics`, `vv4_write_village_statistics`, and `vv5_write_village_statistics`.
The five current combined Origins route IDs are `vv1_origins_village_wide_upgrades`, `vv2_origins_village_wide_upgrades`, `vv3_origins_village_wide_upgrades`, `vv4_origins_village_wide_upgrades`, and `vv5_origins_village_wide_upgrades`.
Historical standalone Full Mastery and individual Full Mastery records are kept
only as evidence and are not selectable or included in releases. The corrected VV4
`vv4_full_mastery_all_stage_a_candidate` is catalog-hidden and disabled pending
fresh independent recertification after the C6 startup-crash correction. Its
candidate-only UI uses the canonical mockup crop baked into a deterministic
`Images\\btn_upgrades_297x35.png` strip (three 99x35 RGBA frames). It is loaded
through `sub_401C20` at local 72,4 with Tech event 13 and Detail event 2;
the unchanged helper/Cure/command-7/PNG/DLL bytes and the new constructor hashes
are recorded in the candidate map. The withdrawn Cure row is rendered
unavailable and command 5 is rejected before charge/0x728004 dispatch. Commands
6 and 8 remain absent, and the legacy atomic village-wide records remain contained.

VV3's independent stock-only command-7 Full Mastery implementation is
emitted-byte certified under disassembly commit
`1e6ad7fd610d2fe9d80416fb218366ccd7d0656b` and available as
`vv3_full_mastery_all_stage_a_candidate`. It reacquires the fixed current-save
manager before both dry runs, uses the native skill writer and Award evaluator,
and supports only `collection_progression` and `immediate_fixed`. Commands 6 and 8,
ownership/Remove, raw skill stores, and save-format changes remain absent.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed --output-root "path\chosen output parent"
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode stock --output-root "path\chosen output parent"
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed --output-root "path\chosen output parent"
```

Technical evidence is in `docs/max-population-research.md`,
`docs/island-event-population-research.md`, and the game-specific reports under
`docs/`.

The public patcher exposes only the five current combined Origins Tech, Details,
and Village-Wide upgrades-menu routes, one per game. Each route resolves that
game's Origins menu prerequisite and includes the latest menu implementation
rather than separate Full Mastery or duplicate Origins records. VV5's native Tech and
Villager Upgrades menus provide Full Mastery, Running, Set Age to 18, and Full
Heal / Cure All for active living Believers only. VV5 records with the Heathen
mask/status set, including the sick-Heathen puzzle record, are skipped before
action-specific reads or writes. Full Heal raises only health below 80 to 100
and clears sickness; health from 80 through 100 is preserved. Native writers,
statistics, and other stock handlers remain in the call path. Runtime/player
confirmation is still pending.
