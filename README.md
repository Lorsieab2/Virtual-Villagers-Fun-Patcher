# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

**Supported game source:** This patcher only supports the games downloaded from the official **Last Day of Work (LDW) website** (ldw.com), where all five PC games are available for free — so there's no reason to get them from anywhere else. Every patch is pinned to the exact bytes of those free LDW builds. Other releases (for example the Steam version) are not tested and may have different bytes; if a game isn't the LDW download, the patcher rejects it rather than risk patching an unverified executable.

The app uses the supplied transparent `Island.png` artwork as its title-bar icon and as small image decorations around both its name and the credit:

`[Island image] Created with Codex AI. Made with love by Lorsieab2 :) [Island image]`

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
modes use the stable short `- Modded` name. The selected mode,
optional patches, hashes, and applied edits remain identified in the adjacent
`.patch-log.json`.

## Optional patches by game

Every patch below is optional and off by default. The patcher lists them
under these same game headers, sorted by name. Selecting a patch that has a
prerequisite selects the prerequisite automatically.

### Virtual Villagers - A New Home

**Birth Control**

Matches the literal VV4/VV5 Birth Control boundary on the exact VV1 build. Manual pairing rejects only a category-2 carrier at internal age>=1000; the two action-9 writer-reaching scans and the planner reject only scanned candidates at internal age>=1000; the autonomous chooser uses the VV4/VV5 score floor and 25% non-preference fallback; initiator males and older autonomous initiators retain no upper-age ceiling. Birth Control owns only its named ordinary-route checks; conception, pregnancy, delivery, direct event births, and pending delivery remain separate native paths, while automatic physical-capacity safety applies in every public mode.

- Patch ID: `vv1_birth_control`

**Builder Action Fixes**

Villagers whose selected job is Building try the stock construction dispatcher at every food level, while autonomous construction project IDs 9, 10, and 11 are eligible only after their signed progress is greater than zero; the other project gates and manual, existing-work, and repair routes remain stock.

- Patch ID: `vv1_builder_action_fixes`

**Continue Research at Max Technologies**

Researchers keep choosing the stock research action and earning tech points after all six technologies reach level 3.

- Patch ID: `vv1_continue_research_at_max_technologies`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events, Duplicate Collectibles, and Golden Child tech gains are excluded.

- Requires: vv1_enable_origins_exclusive_features
- Patch ID: `vv1_origins_village_wide_upgrades`

**Magic Fruit of Life Alters Mortality**

Completing the Magic Fruit of Life puzzle globally shifts every ordinary villager's mortality curve seven displayed years later, including during time catch-up. Finishing Enjoying magic fruit also clears that villager's sickness and restores health to 100. Eating the fruit remains reusable and stores nothing in villager likes or dislikes.

- Patch ID: `vv1_magic_fruit_alters_mortality`

**Reenable F6 Clothing Change Cheat**

The clothing shortcut cycles the selected active villager through the stock outfits: pressing F6 spends 5,000 tech points to advance to the next outfit, wrapping from outfit 19 back to outfit 0. With fewer than 5,000 tech points, F6 does nothing and charges nothing.

- Patch ID: `vv1_f6_clothing_change_cheat`

**School Lessons Grant Skill**

Each child who finishes the unlocked Going to school activity gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Patch ID: `vv1_school_lessons_grant_skill`

**Visual Mods**

Adds decorative flowers to the lagoon and love hut, clothes to the extra hut near the farm, and colorful flowers to the restored garden, by swapping four scene/map images in the game's Images folder. Purely cosmetic -- no executable, gameplay, or save bytes change. Disabling restores the exact base-game images. Credit to the original mod creators.

- Patch ID: `vv1_visual_mods`

**Write Village Statistics to Text File**

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Patch ID: `vv1_write_village_statistics`


### Virtual Villagers - The Lost Children

**Birth Control**

Matches the VV4/VV5 Birth Control boundary on the exact VV2 ordinary routes: the native chooser's score floor and 25% non-preference fallback remain in force, the two writer-reaching opcode-12 candidate scans reject candidates at internal age 1000 or greater, and the stock manual carrier/female-only gate rejects older carriers without adding a male upper-age gate. Birth Control owns only those two candidate scans; the conception roll, pregnancy writer, pregnancy, delivery, and automatic physical-capacity safety remain separate native/automatic paths in every public mode.

- Patch ID: `vv2_birth_control`

**Easier Healing Mastery**

Healers and villagers who prefer Healing study plants when no sick villager needs treatment, including during catch-up.

- Patch ID: `vv2_easier_healing_mastery`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events, Duplicate Collectibles, and Gong of Wonder tech gains are excluded.

- Requires: vv2_enable_origins_exclusive_features
- Patch ID: `vv2_origins_village_wide_upgrades`

**Gong of Wonder Coconuts Fix**

When the Gong of Wonder grants coconuts, adds 30 to the coconut trees instead of replacing their current amount with 30. Both normal and alternate outcome paths are corrected.

- Patch ID: `vv2_gong_of_wonder_coconuts_fix`

**Hospital Recovery Heals**

A villager who completes Recovering at the hospital gains exactly 1 health point, capped at 100. Stock VV2's hospital recovery action does not change health.

- Patch ID: `vv2_hospital_recovery_heals`

**Teaching Children Grants Skill**

Each child who finishes a Teaching Children lesson gains 7 to 9 points in one equally random skill, matching the VV3 Tribal Chief lesson award.

- Patch ID: `vv2_teaching_children_grants_skill`

**Write Village Statistics to Text File**

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Patch ID: `vv2_write_village_statistics`


### Virtual Villagers - The Secret City

**Birth Control**

Matches the VV4/VV5 Birth Control boundary on the exact VV3 ordinary action-13 route: the native chooser's score floor and 25% non-preference fallback remain in force, the scanned candidate stays in the stock internal-age 360..999 range, and the initiating villager has no extra upper-age rejection. Birth Control owns only the five ordinary initiator checks; the native manual category-1 carrier gate, conception, pregnancy, and delivery remain separate, while automatic physical-capacity safety applies in every public mode.

- Patch ID: `vv3_birth_control`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Complete all Collections, Reset all Collections, and Equal Division of Labor with and without Parenting, all supplied by the base Origins feature rather than this optional payload. Island Events and Duplicate Collectibles are excluded.

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

When the Tribal Chief completes Pointing out a rare collectible, rejected random choices are rerolled until the stock game finds an eligible rare collectible. This prevents the full stock cooldown from being spent without a collectible appearing while preserving the original rare categories, collectible IDs, collection rules, and placement logic.

- Patch ID: `vv3_rare_collectible_retry`

**Write Village Statistics to Text File**

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Patch ID: `vv3_write_village_statistics`


### Virtual Villagers - The Tree of Life

**Complete Fish Scales = Golden Fish in Nets**

Golden Fish become eligible in the fishing nets only after all 12 Fish Scales are collected. This changes the stock partial-collection threshold while preserving the completed collection's original 25% Golden Fish chance and every other fishing outcome.

- Patch ID: `vv4_complete_scales_golden_fish`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. The Tech screen also offers Time Warp, Island Event, Barrel of Babies, Food and Tech Point Doublers, Full Heal/Cure All, All Villagers are Exactly 18, Complete and Reset All Collections, and Equal Division of Labor with and without Parenting, and the Villager Details screen grants Youth, Full Mastery, Running, Set Age to 18, and Change Appearance. Island Events and Duplicate Collectibles are excluded.

- Requires: vv4_enable_origins_exclusive_features
- Patch ID: `vv4_origins_village_wide_upgrades`

**Optional Text changes**

Replaces some in-game text with wording consistent with the other Virtual Villagers games (for example, the "Scholar" title becomes "Esteemed Elder", and a few labels and event lines are capitalized and punctuated to match). When active, the game's Assets/sm.xml is swapped for the edited version; when the patch is not selected, the base-game text is left untouched. No executable bytes are changed.

- Patch ID: `vv4_optional_text_changes`

**Write Village Statistics to Text File**

After a successful save, writes the village's lifetime statistics to a Village Statistics text file.

- Patch ID: `vv4_write_village_statistics`


### Virtual Villagers - New Believers

**Clickable Tips**

Clicking the curled vine beneath the on-screen Puzzles button shows a random in-game tip in the gray message bar (with the engine's own auto-hide timer) and plays the hou.ogg chime.

- Patch ID: `vv5_clickable_tips`

**Easier Devotee Training**

Villagers with positive Devotion skill can spontaneously use the stock Honoring action. Statue-drop Honoring remains available for training beginners, while villagers with no Devotion skill do not autonomously Honor.

- Patch ID: `vv5_easier_devotee_training`

**Enable Origins Tech, Details, and Village-Wide Upgrades**

Includes the Origins Tech screen and Villager Details-screen buttons and their upgrades through the internal Origins prerequisite. The Village-Wide menu offers Running, Full Mastery, and Make Villagers Young Adults. Island Events and Duplicate Collectibles are excluded; only Believers are processed and Heathens are skipped.

- Requires: vv5_enable_origins_exclusive_features
- Patch ID: `vv5_origins_village_wide_upgrades`

**Guardians of Isola Rewrite**

Overhauls the New Believers story presentation: replaces the in-game text (Assets/sm.xml) and twelve story/UI images -- the five totem strips, idol states, the blinking-eyes and mask strips, and the main menu -- with the Guardians of Isola rewrite. Purely presentational; no gameplay, executable, or save bytes change. Disabling restores the exact base-game files.

- Patch ID: `vv5_guardians_of_isola_rewrite`

**Heathen Mommy Puzzle Restoration**

Restores the natural Heathen Mommy to newly created villages as a tag-17 Heathen mother with one nursing baby, using two physical slots, and restores the hidden 17th Heathen Parent graphic and full-tile rollover messages to the Puzzles screen. Existing saves are not retroactively given a new mother.

- Patch ID: `vv5_heathen_mommy_puzzle`

**Statue Drops: Normal Action or Honoring**

Statue drops use skill-aware choices: Honoring is available only to villagers with positive Devotion, while Building a statue and Polishing the Statue require positive Building skill. When both outcomes are eligible, the choice is 50/50; otherwise the eligible normal action is kept.

- Patch ID: `vv5_statue_polishing_or_honoring`

**VV4 Nursery School Divisor Parity**

For parity with Virtual Villagers 4, changes VV5's six-skill spread lesson divisor from five to six. VV5 normally distributes one-fifth of a lesson to each of six skills, an arithmetic inconsistency that awards six-fifths in total; this patch distributes exactly one-sixth to each skill without claiming whether the original inconsistency was intentional.

- Patch ID: `vv5_vv4_nursery_divisor_parity`

**Write Village Statistics to Text File**

After a successful save, writes the village's lifetime statistics to a Village Statistics text file, including current puzzle totals.

- Patch ID: `vv5_write_village_statistics`


That is 35 optional patches across the five games.

Three patches change files rather than executable bytes: **VV1 Visual
Mods**, **VV4 Optional Text changes**, and the **VV5 Guardians of Isola
Rewrite** swap images and text inside the copied game folder only, and
restore the exact base-game files when the patch is not selected.

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

While one of these events is still on its way, its row is disabled and reads
**Unavailable** in all five games, so a second copy cannot be clicked and cannot
be charged for.

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
frees. You are never charged twice, and a paid barrel never quietly delivers
fewer than three children. In A New Home, if the event itself cannot be created
the three-child bonus is released again rather than left waiting to attach to
whichever barrel turns up next.

Results that count villagers name the number and the reason, and read correctly
at one: *"Skipped over 1 villager. Reason: already likes running."*

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

Nothing is disabled because of it: the VV2 Origins patch and its dependent
village-wide upgrade are selectable, and its Doublers buy, remove and
repurchase like every other game's. What is still outstanding is **runtime
confirmation** -- the report has not been reproduced or cleared in a playtest.

The crash audit did find `.shr` raw-offset versus virtual-address confusion in
the VV2 builder, displacing some helper and header references by `0x2000`. The
isolated VV2 builder now corrects those runtime VAs, extends the `.shr` virtual
size and execute flags, and maps the payload's `.rdata` tail as executable.
Static render and regression checks pass. That is not yet proof the reported
crash is gone -- only a playtest can establish that. Every unrelated VV2 patch
is unaffected.

### Status

These menus are verified by build-level tests -- exact bytes, dialog wording,
and the purchased/success dialog paths -- and the patcher refuses to write an
executable whose bytes it cannot account for. They have had far less **playtest**
coverage than the ordinary patches, so **runtime** confirmation in a real village
is still the last step for many rows, and the VV2 **crash** above is unresolved.
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

All five games also contain Island Events that add villagers. The patcher guards every identified direct population-adding outcome: repeated allocations stop when the selected physical pool fills, and VV4/VV5 Abandoned Infants is reduced from six babies when fewer than six physical slots remain. VV3-VV5 use their verified 150-record boundary. Events that remove villagers are unchanged. VV5 conversions and The Defector are unchanged because they reclassify existing records instead of allocating new ones.

## Requirements

The patcher runs from source through the bundled launcher. It needs nothing
beyond a normal Python install.

| Requirement | Detail |
| --- | --- |
| Windows | The five games are 32-bit Windows executables and the patcher writes Windows PE files. `Launch Virtual Villagers Fun Patcher.bat` is a Windows batch file. |
| Python 3.10 or newer | Download from [python.org](https://www.python.org/downloads/). During setup keep **tcl/tk and IDLE** ticked, which is the default: the patcher's window is built with `tkinter`. |
| No extra packages | The patcher uses only the Python standard library. There is nothing to `pip install`, and no internet connection is needed to patch. The **Check for updates** link is the one feature that reaches the internet, and it is entirely optional: it just opens the releases page in your browser, and everything else works with no connection at all. |
| An original game | The free downloads from [ldw.com](https://ldw.com), installed normally. Only those builds are supported. |
| Free disk space | The patcher copies each game whole rather than editing your original, so each modded copy needs about as much space as the game folder itself: roughly 25-85 MB per game, or about 300 MB for all five. |

The launcher tries `py -3` first and falls back to `python`, so either the
Python launcher or `python` on your `PATH` will do. If a console window opens
and reports that Python was not found, install Python and try again.

Your original game is never modified. Every patch is written into a separate
`(Game name) - Modded` folder, so you can delete that folder at any time and
keep playing the original.

The top-right of the window shows which build you are running, next to a
**Check for updates** link. Clicking it opens the releases page in your
browser. It deliberately makes no judgement about which build is newer: the
releases page already shows what is newest, and your build version is printed
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

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The One Game tab includes clickable **Open Vanilla EXE Folder** and **Open Modified EXE Folder** links. All 5 Games provides matching Vanilla folder and Modified folder links on every game row. After patching, a compact confirmation window provides clear clickable links to both folders for every completed game.

The **Additional fun patches** section is grouped in game order, with each
game's patches sorted by patch name. It includes **Select All Patches** and
**Deselect All Patches** buttons. They change every optional fun-patch checkbox
at once without changing the selected population mode, and the
selection is remembered normally.

For every selected game, all three modes create **`(Game name) - Modded`**
containing **`(Game name) - Modded.exe`**. By default the selected folder is beside the
supplied original; the GUI's **Modded output location** chooser can place all
selected games under another parent folder. It copies every file and subfolder
from the original game folder, verifies the copied files by SHA-256, keeps the
stock EXE in the copy, and adds the modified EXE plus its `.patch-log.json`. The
original folder and original EXE are never edited, renamed, replaced, or
deleted. Asset-swap patches such as VV1 Visual Mods, VV4 Optional
Text changes, and the VV5 Guardians of Isola Rewrite replace their listed image
and text files inside that copy only; the base-game files are restored whenever
the patch is not selected. Applying another population mode refreshes that mode's same short folder
after confirmation.

## Exact-build safety

Support is bound to the exact SHA-256 and size of each researched stock executable. Unknown, modified, corrupt, duplicate, or incorrectly assigned EXEs are refused. Every original byte to be changed is guarded, file size is preserved, the PE checksum is recalculated, and each result is read back and hashed.

Bulk mode validates and renders all five inputs before writing. Each supplied
game folder is then copied directly into its short **`- Modded`** output folder
and verified before the modified EXE is written. Re-running with overwrite
updates that same Modded folder in place. The patcher does not create temporary
game copies or replacement-backup folders; the supplied original folders remain
unchanged.

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
