# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

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

Its max-population modes use every verified built-in villager slot: 256 slots in A New Home and The Lost Children, and 150 slots in The Secret City, The Tree of Life, and New Believers.

## Two patch styles

Choose the style in the patcher; the choice and all paths are remembered.

| Style | Collection behavior | Output EXE |
|---|---|---|
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `(Game name) - Modded.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `(Game name) - Modded.exe` |
| Experimental Expanded 256 Villagers | VV3–VV5 expand their physical records and save layout to 256 immediately; collections no longer affect that expanded ceiling. | `(Game name) - Modded 256.exe` |
| Experimental Expanded 256 - Collection Progression | VV3–VV5 expand to 256 while their original collection and Magic Tech bonuses remain required to reach 256. | `(Game name) - Modded 256.exe` |

> **Expanded-256 release status:** both experimental 256 modes are ON HOLD for
> VV3-VV5. Exact-build reanalysis found unresolved runtime/save failures and
> incomplete optional-feature relocation coverage. Renderer success is not a
> release certification. See
> [the exact implementation gates](docs/vv3-vv5-expanded-256-implementation-gates.md).

Ordinary modes and optional-patch combinations use the stable short `- Modded`
name. Experimental 256 modes use the separate short `- Modded 256` name. The
selected mode, optional patches, hashes, and applied edits remain identified in
the adjacent `.patch-log.json`.

The **Experimental Expanded 256 Villagers** and **Experimental Expanded 256 -
Collection Progression** modes are available for VV3–VV5. They expand the
logical record and save layout from 150 to 256 and include guarded loading of
the original stock save layout. They remain experimental and are awaiting
player startup, save-recognition, and complete playthrough validation.

## VV2: Easier Healing Mastery

Enable the optional **Easier Healing Mastery (The Lost Children)** checkbox to change the Healing job fallback in The Lost Children. When a healer or a villager who prefers Healing has no sick villager to treat, the stock job scheduler now enters its existing persistent plant-study state instead of returning "no work." The same stock state is processed during ordinary play and time catch-up.

The patch does not change healing gains, illness, food, skill thresholds, plant availability, or manual plant study. Its selection is recorded in the verification log without lengthening the short Modded EXE name.

## VV1: School Lessons Grant Skill

Enable **School Lessons Grant Skill (A New Home)** to reward a child only after the unlocked stock Going to school action reaches its end. The child gains 7, 8, or 9 points in one equally random skill: Farming, Building, Research, Healing, or Parenting. Skills remain capped at 100.

That award matches VV3's code-confirmed Tribal Chief lesson: one random skill and `RNG(3)+7` points per child at the completion callback. The patch does not unlock the school, change attendance selection, or reward an interrupted lesson that never reaches the callback.

## VV1: Continue Research at Max Technologies

Enable **Continue Research at Max Technologies (A New Home)** so researchers remain eligible for the stock research action after all six technologies reach level 3. They continue using the original research queue, Research skill, Science-technology multiplier, and tech-point award routine.

## VV1: Reenable F6 Clothing Change Cheat

Enable **Reenable F6 Clothing Change Cheat (A New Home)** so pressing F6 advances the selected active villager to the next stock outfit. Each successful outfit change costs exactly 5,000 tech points. With fewer than 5,000 tech points, F6 does nothing and charges nothing. The cycle covers the game's ordinary clothing indices 0 through 19 and wraps from 19 back to 0. Pressing F6 without a valid active selection changes nothing.

The patch does not alter heads, sex, age, skills, health, jobs, movement, actions, or clothing assets. F7, F8, and all non-F6 keys retain their original behavior.

## VV1: Magic Fruit of Life Alters Mortality

Enable **Magic Fruit of Life Alters Mortality (A New Home)** to give the completed Magic Fruit puzzle a tribe-wide longevity effect. Once the puzzle's saved completion flag is set, the stock mortality routine moves every ordinary villager's complete mortality curve seven displayed years later. The same routine handles ordinary play and offline time catch-up. Medicine technology still contributes its original threshold first, and the Golden Child retains the stock exemption.

Finishing **Enjoying magic fruit** also clears that villager's sickness and restores health to 100. The cure occurs only when the final fruit-action cleanup runs, so an interrupted action awards nothing. It is reusable, does not stack another mortality bonus, and stores no state in villager names, likes, dislikes, or other record fields.

## VV1: Builder Action Fixes

Enable **Builder Action Fixes (A New Home)** so a villager whose selected job
is Building tries the game's normal construction dispatcher before general idle
activities regardless of the village's food amount. Stock VV1 skips the
preferred-job attempt when food is at least 400, which makes assigned Builders
much less likely to work on a visible scaffold or repair an eligible structure
while the village is well fed.

The patch removes that food-dependent suppression only for the Building job.
The original construction dispatcher still chooses the eligible hut, repair,
or other building task and retains all project requirements, progress awards,
Building skill gains, and completion behavior. Villagers assigned to other
jobs retain their stock high-food scheduling. The shared scheduler covers both
ordinary play and elapsed-time catch-up.

## VV1 Origins containment

The legacy **Enable Origins-Exclusive Features (A New Home)** record is
disabled, catalog-hidden, and absent from GUI, CLI, dependency resolution,
Select All, and generated transparency output. The rows documented below are
retained only as historical diagnostic evidence; they are not selectable or
emitted:

- **Time Warp** — 50,000 tech points; advances the village by exactly 3
  displayed villager years. The elapsed-clock shift scales with game speed;
  at Normal speed, six real-time hours equal those three villager years.
- **Island Event** — 30,000 tech points; queues the stock desktop Island Event.
- **Barrel of Babies** — 75,000 tech points; matches the APK's forced event
  and adds exactly three young children. If the current housing-dependent
  population limit has fewer than three spaces available, it charges nothing
  and reports **The village population is already at maximum capacity.**
- **Grant Youth** — 50,000 tech points; makes the selected living villager 35
  displayed years younger, with a minimum displayed age of 5.
- **Grant Full Mastery** — 100,000 tech points; sets all five skills of the
  selected living villager to the APK's mastery value of 90. It preserves the
  selected job, or chooses Farming when none is selected, so VV1 does not show
  the incomplete title **Master**.
- **Grant Running** — 40,000 tech points; permanently gives the selected
  living villager the Running like when a Like slot is available and removes
  Running from that villager's Dislikes. It refuses without charging when all
  three Like slots are occupied and Running is not already a Like. This
  upgrade does not write movement speed, movement initialization, or a custom
  Running flag, and it does not alter any stock movement predicate. All
  per-villager speed values and vanilla speed decisions remain untouched.
- **Set Age to 18** — 50,000 tech points; sets the selected living villager's
  age to 18.
- **Tech Point Doubler** — displayed at 500,000 tech points but temporarily
  unavailable for new purchase pending exact-build provenance verification.
  Existing ownership can be removed for zero cost with no refund; repurchase is
  temporarily disabled for this build.
- **Food Point Doubler** — displayed at 500,000 tech points with the same
  temporary safety gate. Existing ownership can be removed for zero cost with
  no refund; repurchase is temporarily disabled for this build.

The legacy Cure, Running, Time Warp, doubler, and selected-villager Origins
paths remain **STOP**. Re-enablement requires rebuilding the resource with the
exact label **Time Warp - Advances 3 Villager Years**, removing or replacing
stale Cure resources, and proving confirmation, selected/world identity and
funds reacquisition, native mutation and postverification, one deduction only
after success, and truthful no-change/no-charge and partial-failure reporting.
This containment changes no Golden Child or Island Event outcome.

The separate `vv1_full_mastery_all_stage_a_candidate` remains an isolated,
command-7-only, catalog-visible static candidate for stock Collection
Progression and Immediate Fixed. It is not the disabled Origins record;
Expanded-256 rejects before output and runtime/player confirmation remains
pending.

## VV2 Origins containment

**Containment notice:** VV2 Origins is currently disabled after a player
reported that both Time Warp and Food Point Doubler crash immediately after
their purchased/success dialog is displayed. This records the trigger only;
it does not infer whether the charge or action persisted. Both
`vv2_enable_origins_exclusive_features` and its dependent village-wide upgrade
are contained pending root-cause repair. Unrelated VV2 patches remain
available.

The rows formerly proposed by **Enable Origins-Exclusive Features (The Lost
Children)** are retained only as historical diagnostic evidence:

- **Time Warp**, **Island Event**, and the literal stock **Barrel of Babies**
  event;
- removable **Tech Point Doubler** and **Food Point Doubler** purchases stored
  only in the current saved village;
- **Grant Youth**, **Grant Full Mastery**, **Grant Running**, and **Set Age to
  18** for the selected villager.

These legacy Cure, Running, Time Warp, doubler, and selected-villager Origins
paths are not selectable or emitted. Re-enablement requires the crash root
cause, the exact Time Warp resource rebuild, legacy Cure replacement, and the
complete confirmation/reacquisition/postverification/one-deduction transaction
gates. This containment changes no Gong of Wonder or Island Event outcome.

The separate `vv2_full_mastery_all_stage_a_candidate` remains an isolated,
command-7-only, catalog-visible static candidate for stock Collection
Progression and Immediate Fixed. It excludes commands 6/8, Gong, Island Event,
and withdrawn Origins; Expanded-256 rejects before output and runtime/player
confirmation remains pending.

## VV3: Enable Origins-Exclusive Features

Enable **Enable Origins-Exclusive Features (The Secret City)** to add the
Origins **Upgrades** menus to VV3. The Tech Point and Food Point Doublers are
displayed but temporarily unavailable for new purchase and repurchase under the
exact-build **STOP** gate; existing ownership can be removed for zero cost with
no refund. The audit records 33 food writer rows (29 calls, 4 E9 tails) and 16
tech rows (13 calls, 3 E9 tails), with tail sites documented in the technical
research. Food Mastery-like award transforms are confirmed absent in this
build. Exact-build audit `4c588ffd36765d750533fe9694f8fda5c8e82736`
also confirms that Magic level 1 or higher adds a deterministic flat `+1`
tech point to each completed research callback. It does not change research
speed, duration, base award, RNG, or Research-skill gain. Native research adds
the base award, optional quarter-base bonus, Magic `+1`, timed `+1`, and
independent RNG `+1` in that order. Any future Tech Doubler must double the
complete positive native research sum once, after those additions, while
leaving collection duplicates and Island Events native. Collection dispatcher
awards are recorded, but IDA has no resolved
caller to `sub_42DEB0`, and Island Event mixed-source writers have no source
tag or proved final-delta boundary. No safe doubler hook, transient marker, or
certified cave/new section is available. The remaining Origins and
selected-villager rows retain their current-save scope and exact-build guards;
runtime/player confirmation remains pending.

## All games: Write Village Statistics to Text File

Enable **Write Village Statistics to Text File** for any game to refresh
`Village Statistics - Save N.txt` in that modified game folder after a
successful save of slot 1 through 5. Each slot receives its own text file.
Failure to write the text file never changes a successful game-save result.

VV1 and VV2 export their reachable stock lifetime counters. VV3, VV4, and VV5
also retain the inherited per-save lifetime block even though their local
Statistics screen is absent or unreachable. The later-game patch reads those
uncapped saved counters directly and restores the stock bookkeeping omissions:
VV3's Villagers Buried total, and VV4/VV5's Food Gathered and Villagers Buried
totals. The restored routes cover normal play and time catch-up where the stock
lifecycle does.

Existing later-game saves preserve every total stock already recorded; fields
that stock never updated begin at zero when this patch is first used. Fresh
saves track all exported totals from their normal initialization.

## VV2: Teaching Children Grants Skill

Enable **Teaching Children Grants Skill (The Lost Children)** to reward every attending child once after that child's full stock lesson queue finishes. Each attendee gains 7, 8, or 9 points in Farming, Building, Research, Healing, or Parenting. All five choices have equal odds, and skills remain capped at 100.

That award matches VV3's code-confirmed Tribal Chief lesson. The patch does not create extra lessons, change who attends, alter the teacher requirement, reward children who are not enrolled by the stock lesson routine, or reward an interrupted lesson that never reaches the callback.

## VV2: Hospital Recovery Heals

Enable **Hospital Recovery Heals (The Lost Children)** so a villager who
finishes **Recovering at the hospital** gains exactly 1 health point, capped at
100. The stock action builds its movement and recovery queue but does not
change health. The award runs only from a new final completion callback, so an
interrupted recovery gives no health.

## VV2: Birth Control

Enable **Birth Control (The Lost Children)** to add an internal-age-1000 ceiling
only to the two writer-reaching opcode-12 candidate scans used by ordinary
autonomous/catch-up pairing and stew recipe 15. Both exact 40-byte guarded
blocks are applied together. Candidate sex remains preserved in `EDX`, and the
already-loaded candidate age in `EAX` is compared directly with 1000.

The stock manual carrier/female-only age gate is unchanged, and no male
upper-age gate is added. Chooser scoring, the exact `work` and `learning`
tokens, planner, pregnancy and delivery, saves, RNG, food, fertility, capacity,
messages, statistics, Love Note, Gong grant, Silver Mirror clone, and all
direct/event births remain native. This exact-build implementation is based on
disassembly commit `74778bd6a7d3a17dd990636cf6d4e769466800c6` and does not
claim broader breeding parity.

## VV2: Gong of Wonder Coconuts Fix

Enable **Gong of Wonder Coconuts Fix (The Lost Children)** so the coconut outcome adds 30 to the trees' existing amount. Stock VV2 assigns the coconut resource to 30, which can erase a larger existing supply. The patch corrects both stock outcome paths and changes no other Gong result.

## VV5: Heathen Mommy Puzzle Restoration

Enable **Heathen Mommy Puzzle Restoration (New Believers)** to restore the natural-build Heathen Mommy to newly created villages and restore the hidden 17th Heathen Parent graphic to the Puzzles screen. Its full visible tile rolls over to **This milestone has not been completed!** while locked and **The Heathen Parent** when completed. The supplied natural build creates a 29th Heathen with tag 17, initializes her, and assigns one forced nursing baby. The supported modern initializer creates only 28 Heathens and omits that sequence.

The patch reproduces the natural build's exact mother arguments and nursing-baby call, then restores the retained locked/solved puzzle graphic using puzzle 17's actual completion state. The mother and baby require two physical population slots. This new-game initialization does not retroactively add a mother to an existing save.

## VV5: Enable Origins-Exclusive Features

The independently certified **VV5 Origins Full Mastery Extension Base**
(`vv5_origins_full_mastery_base_candidate`) and **Grant Full Mastery to All
Villagers** (`vv5_full_mastery_all_stage_a_candidate`) are enabled only for
the exact stock Collection Progression and Immediate Fixed builds. Their
acceptance is bound to the C99 rendered hashes, the authoritative Origins DLL,
the native `btn_trophies` resource, the certified confirmation routines and
strings, and the recorded hook/map guards. Expanded-256 is rejected before any
output is written and remains ON HOLD.

The VV5 Upgrades UI and native village-wide Full Mastery route are preserved;
the individual route targets the selected current living Believer and performs
the certified exact-100 transaction. The withdrawn Cure row/command 5 is
unavailable, bypassed, and unreachable in this candidate; no Cure purchase or
30,000-point Cure behavior is present. Other Origins actions and unrelated
VV5 features remain native and unchanged.

## VV4: Complete Fish Scales = Golden Fish in Nets

Enable **Complete Fish Scales = Golden Fish in Nets (The Tree of Life)** to delay Golden Fish eligibility until all 12 Fish Scales have been collected. Stock VV4 allows Golden Fish after only one scale and uses the chance `2 × collected scales + 1%`.

The patch changes only the eligibility threshold from 1 to 12. At full completion, the stock formula still gives a 25% Golden Fish chance. Normal fish, fishing animations, food awards, scale collection, and all other fishing outcomes remain unchanged.

## VV4: Enable Origins-Exclusive Features

Enable **Enable Origins-Exclusive Features (The Tree of Life)** to add the
icon-based Origins **Upgrades** menus to VV4. It includes the displayed-but-
currently-unavailable current-save Tech Point and Food Point Doublers, Time
Warp, Island Event, native Barrel of Babies purchase, and selected-villager
upgrades used by the other Origins ports. Existing doubler ownership can be
removed for zero cost with no refund; repurchase remains disabled pending the
exact post-Food-Mastery provenance gate. The final contract stacks after native
collectible and Food Mastery adjustments and excludes Island Event outcomes.
Grant Running only uses a free normal Like
slot, removes Running from Dislikes, and never changes movement speed. The
feature is exact-build guarded, but its native dialog and upgrade UI still need
player runtime validation.

## VV3: Grant Running to Selected Villager

`vv3_individual_grant_running_candidate` is disabled, catalog-hidden, and absent
from GUI, CLI, and Select All. The withdrawn village-wide command-6 Running row
is also absent. Its retained evidence is not publication authority.

## VV3: Full Heal / Cure All

`vv3_full_heal_cure_all_candidate` is absent because its required selected-
villager Running dependency is disabled and hidden. It must not appear in GUI,
CLI, or Select All. Its retained evidence is not publication authority.

## VV4 breeding reference

VV4 remains the untouched vanilla Breeding and Embracing reference, including
its older-mother behavior and no male upper-age gate. The historical Birth
Control candidate is rejected/superseded and is not offered or applied.

The exact-build VV4/VV5 audit confirms that both games already provide the
requested VV4-style Birth Control/Breeding behavior natively. They are therefore
no-patch references. VV1 and VV3 remain ON HOLD as separate per-game tasks.
VV2's certified optional patch is limited to its two writer-reaching opcode-12
candidate scans and does not claim broader breeding parity.

VV1 remains ON HOLD under exact-build audit `c8d268d`. Its rejected historical
proposal mistook the `0x3DBBE` food gate for an age predicate, treated live code
at `0x458D0`/`0x45930` as caves, relied on uncertified `0x56740` placement, and
applied the wrong both-sex ceiling. No VV1 Birth Control bytes are offered.
Complete carrier-only/no-male-ceiling coverage still requires the planner and
action-9 commit paths to be proved together; catch-up, direct event births, and
pending delivery remain native.

## VV3: Everyone Tries On the Robe

Enable **Everyone Tries On the Robe (The Secret City)** to make one handled
robe drop call the whole eligible village to the robe area. The dropped
initiator keeps the complete stock result and is still the only villager who
can receive the successful Tribal Chief action. Every other active, living,
non-nursing villager receives only the game's native failed-fit **Trying on the
robe** action, including its status, walk, gestures, and temporary try-on
appearance.

Followers never receive the successful-fit action, persistent Chief clothing,
or Chief state. Dead, inactive, and nursing villagers are skipped. The patch
does not read or write the robe candidate fields, and does not change the Chief
puzzle, pregnancy or nursing state, health, age, skills, preferences, or save
records. Fanout requires the original callback to report a handled drop and to
leave the initiator in its native success or failed-fit robe action.

This checkbox is optional and starts unchecked. It supports both ordinary
population modes and both Expanded-256 modes. The implementation is exact-
build guarded and statically verified; player runtime confirmation remains
pending. The robe feature itself never reads or writes candidate fields
`+0xE80` or `+0xE88`. In both Expanded modes, the patcher separately and
automatically applies the guarded Chief-candidate assignment repair; it
composes disjointly and is not a selectable feature dependency. If those
fields are still zero before automatic assignment, or no eligible candidate
exists, the native callback and robe fanout use failed-fit action 121 without
granting Chief state.

## VV3: Nature Level 1 Actually Replenishes Food Sources Faster

Enable **Nature Level 1 Actually Replenishes Food Sources Faster (The Secret City)** to make the technology description literal. At Nature level 1 or higher, fruit trees become refill-eligible after 2 hours 15 minutes instead of 3 hours, and honey becomes refill-eligible after 45 minutes instead of 1 hour.

The stock Nature fruit quantity is preserved at the shorter interval: approximately 126 fruit instead of 111 for the same stock refill group. Honey also receives the exact `42/37` proportional quantity bonus, normalized to its new 45-minute interval. Nature level 0 retains stock timing and amounts. The 3,000-unit honey cap remains unchanged.

## VV3: Nature Level 3 Actually Alters Mortality

Enable **Nature Level 3 Actually Alters Mortality (The Secret City)** to make
the otherwise-unused Nature read in VV3's aging loop affect longevity. At
Nature level 3, every ordinary villager's complete mortality curve moves seven
displayed years later. Medicine's stock threshold is calculated first, so the
benefits stack. Nature levels 0 through 2 are unchanged.

The same aging loop processes ordinary play and elapsed-time catch-up, so the
seven-year shift applies in both. The patch does not change displayed age,
health, sickness, resurrection, or the existing Medicine progression.

## VV3: Pointing Out a Rare Collectible Always Works

Enable **Pointing Out a Rare Collectible Always Works (The Secret City)** so
the Tribal Chief's completed action rerolls an ineligible rare collectible
choice instead of silently spending the full cooldown without placing
anything. Stock VV3 chooses the rare item only after the action and cooldown
have already committed, then rejects the choice when another villager is
targeting that exact item or when a particular rare category has already been
collected.

The patch retries only those stock rejection paths. It preserves the original
four rare categories, item IDs, random selection, collection restrictions,
spawn regions, Chief requirement, Leadership requirement, action duration, and
cooldown.

## VV5: Easier Devotee Training

Enable **Easier Devotee Training (New Believers)** so any villager with positive Devotion skill can spontaneously choose the game's original **Honoring** action. The stock autonomous opportunity is confined to the Retired Chief job state; other devotees normally have to be dropped on the upgradeable statue to begin Honoring. This patch checks actual Devotion skill instead.

The normal idle scheduler and its existing timing chance remain unchanged. The patch reuses the stock Honoring action queue and skill-gain behavior, does not grant Devotion directly, and does not alter conversion, statue upgrades, manual statue assignment, or Devotion thresholds. **Spreading the Word remains a Retired Chief activity and is not assigned to ordinary devotees.**

## VV5: Statue Drops — Normal Action or Honoring

Enable **Statue Drops: Normal Action or Honoring (New Believers)** for state-aware statue drops. Every applicable drop chooses with equal 50/50 odds between **Honoring** and the normal action for that state: **Building a statue** during construction, **Confused** when an upgrade lacks the necessary technology, or **Polishing the Statue** for eligible upgradeable and completed statues.

This provides a manual Devotion-training route in every statue state while preserving all three original alternatives. It does not change autonomous work, Devotion gains, statue upgrades, or Retired Chief activities.

## VV5: VV4 Nursery School Divisor Parity

Enable **VV4 Nursery School Divisor Parity (New Believers)** to change only the Nursery School's spread-lesson divisor from five to six. VV4 divides one lesson into five shares and writes those shares to five skills. VV5 writes shares to six skills, including Devotion, but retains VV4's divisor of five and therefore distributes six-fifths of a lesson when all six skills qualify.

For parity with Virtual Villagers 4, this optional patch gives each of VV5's six skills one-sixth of the spread lesson. It does not change focused strongest-skill lessons, teacher qualification, teacher selection, teacher skill totals, the under-14 eligibility rule, the approximately-50 skill ceiling, or offline catch-up. The arithmetic inconsistency is code-confirmed; whether it was intentional cannot be determined from the executable alone.

| Game | Stock final maximum | Collection Progression maximum | Immediate Fixed maximum | Experimental immediate | Experimental progression |
|---|---:|---:|---:|---:|---:|
| A New Home | 90 | 256 | 256 | 256 | 256 |
| The Lost Children | 115 | 231 to 256 | 256 | 256 | 231 to 256 |
| The Secret City | 125 | 115 to 150 | 150 | 256 | 221 to 256 |
| The Tree of Life | 115 | 125 to 150 | 150 | 256 | 231 to 256 |
| New Believers | 105 | 135 to 150 | 150 | 256 | 241 to 256 |

Housing gates remain in place.

### New Believers: Heathens and physical slots

Heathens already occupy records in New Believers' 150-record villager pool. Converting one changes that existing record from Heathen to believer; it does not create an additional villager record. The population patch therefore measures physical slot demand before allowing births: every active record counts, including unconverted Heathens and corpses that the game has not released yet, and nursing babies reserve the records they will need later.

This means births can temporarily stop below 150 displayed believers while Heathens remain, but conversions are still safe and can continue at the physical ceiling. After every Heathen has been converted and old corpse records have cleared, the full 150 slots can be believers.

## Safe twins and triplets at the ceiling

All five stock games test the population limit once before choosing a singleton, twins, or triplets. Without an additional guard, a multiple birth at maximum minus one can report maximum plus one or maximum plus two, even though no corresponding villager records remain.

Both patch styles add a slot-saturation guard at the selected mode's physical boundary:

- Three or more slots left: singleton, twin, and triplet rolls are unchanged.
- Two slots left: a rolled triplet safely becomes twins.
- One slot left: a rolled twin or triplet safely becomes a singleton.
- No slots left: the normal population predicate blocks the birth.

This lets reproduction fill the final slot without permitting the population to exceed the game's real villager array. New Believers uses physical slot demand rather than only its displayed believer count, so still-active Heathens, corpses, and nursing babies cannot make the final multiple birth overbook the shared pool.

### Island Event population safety

All five games also contain Island Events that add villagers. The patcher guards every identified direct population-adding outcome: repeated allocations stop when the selected physical pool fills, and VV4/VV5 Abandoned Infants is reduced from six babies when fewer than six physical slots remain. VV3-VV5 use their verified 150-record boundary. Events that remove villagers are unchanged. VV5 conversions and The Defector are unchanged because they reclassify existing records instead of allocating new ones.

## Use

1. Extract the latest release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Select a patch style.
4. Choose **One Game** or **All 5 Games**.
5. For one game, select its original EXE. For all five, select one folder per game.
6. Optionally choose a **Modded output location**. This is the parent folder that
   will receive each generated `(Game name) - Modded` folder. Leave it blank to
   keep the original sibling-folder behavior.
7. Validate, dry run, or create the copied-and-modified game folder set.

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The One Game tab includes clickable **Open Vanilla EXE Folder** and **Open Modified EXE Folder** links. All 5 Games provides matching Vanilla folder and Modified folder links on every game row. After patching, a compact confirmation window provides clear clickable links to both folders for every completed game.

The **Additional fun patches** section is grouped in game order, with each
game's patches sorted by patch name. It includes **Select All Patches** and
**Deselect All Patches** buttons. They change every optional fun-patch checkbox
at once without changing the selected population patch style, and the
selection is remembered normally.

For every selected game, ordinary modes create **`(Game name) - Modded`**
containing **`(Game name) - Modded.exe`**. Experimental 256 modes instead create
**`(Game name) - Modded 256`** containing
**`(Game name) - Modded 256.exe`**. By default the selected folder is beside the
supplied original; the GUI's **Modded output location** chooser can place all
selected games under another parent folder. It copies every file and subfolder
from the original game folder, verifies the copied files by SHA-256, keeps the
stock EXE in the copy, and adds the modified EXE plus its `.patch-log.json`. The
original folder and original EXE are never edited, renamed, replaced, or
deleted. Applying another patch style refreshes that mode's same short folder
after confirmation.

For an experimental 256 mode, the GUI also checks the matching vanilla save
folder. The required slot-zero control file and every numbered `.ldw` save are
copied together into the separate `(Game name) - Modded 256` save folder. If
that destination already contains saves, the patcher asks before replacing
them; declining preserves the existing Modded 256 saves. The vanilla saves are
never edited. Command-line users can request the same behavior with
`--copy-vanilla-saves`; replacing an existing Modded 256 save set additionally
requires the explicit `--replace-modded-saves` flag.

The expanded-mode confirmation now reports the actual state for VV3–VV5:
whether a vanilla slot-zero save was found, whether an existing Modded 256
slot-zero save is already ready, or whether no valid slot-zero save was found.
If no valid save exists, launch the matching Modded 256 executable once and
create a save before copying numbered files into the path shown by the prompt.

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
Expanded-256 variants remain ON HOLD/fail-closed.

## Command line

The independently recertified VV1 stock-only Full Mastery candidate is exposed
as `vv1_full_mastery_all_stage_a_candidate` for `collection_progression` and
`immediate_fixed` only. Expanded-256 rejects before output; runtime/player
confirmation remains pending.

Pass `--patch-mode collection_progression`, `--patch-mode immediate_fixed`, `--patch-mode experimental_expanded_256`, or `--patch-mode experimental_expanded_256_progression` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. Optional features use repeatable `--fun-patch` arguments. The available IDs are `vv1_school_lessons_grant_skill`, `vv1_continue_research_at_max_technologies`, `vv1_f6_clothing_change_cheat`, `vv1_magic_fruit_alters_mortality`, `vv1_builder_action_fixes`, `vv1_full_mastery_all_stage_a_candidate`, `vv2_easier_healing_mastery`, `vv2_teaching_children_grants_skill`, `vv2_hospital_recovery_heals`, `vv2_birth_control`, `vv2_gong_of_wonder_coconuts_fix`, `vv2_full_mastery_all_stage_a_candidate`, `vv3_nature_honey_refill`, `vv3_nature_level_three_alters_mortality`, `vv3_rare_collectible_retry`, `vv3_enable_origins_exclusive_features`, `vv3_full_mastery_all_stage_a_candidate`, `vv4_complete_scales_golden_fish`, `vv4_enable_origins_exclusive_features`, `vv5_heathen_mommy_puzzle`, `vv5_easier_devotee_training`, `vv5_statue_polishing_or_honoring`, `vv5_vv4_nursery_divisor_parity`, and `vv5_enable_origins_exclusive_features`. The disabled VV3 Full Heal / Cure All candidate is not a CLI or catalog ID. The per-game Village Statistics IDs are `vv1_write_village_statistics`, `vv2_write_village_statistics`, `vv3_write_village_statistics`, `vv4_write_village_statistics`, and `vv5_write_village_statistics`. VV1 and VV2 Full Mastery are stock-mode-only; both Expanded modes reject before output. The VV1/VV2 Origins IDs and both dependent village-wide records remain intentionally omitted while contained; the VV4 Origins/Full Mastery records are also omitted pending fresh recertification.

The statically certified VV2 command-7-only Full Mastery feature is catalog-visible
only for stock Collection Progression and Immediate Fixed; runtime/player
confirmation remains pending and Expanded-256 rejects before output. The corrected VV4
`vv4_full_mastery_all_stage_a_candidate` is catalog-hidden and disabled pending
fresh independent recertification after the C6 startup-crash correction. Its
candidate-only UI uses the canonical mockup crop baked into a deterministic
`Images\\btn_upgrades_297x35.png` strip (three 99x35 RGBA frames). It is loaded
through `sub_401C20` at local 72,4 with Tech event 13 and Detail event 2;
the unchanged helper/Cure/command-7/PNG/DLL bytes and the new constructor hashes
are recorded in the candidate map. The withdrawn Cure row is rendered
unavailable and command 5 is rejected before charge/0x728004 dispatch. Commands
6 and 8 remain absent, the legacy atomic village-wide records remain contained,
and Expanded-256 remains ON HOLD/fail-closed.

VV3's independent stock-only command-7 Full Mastery implementation is
emitted-byte certified under disassembly commit
`1e6ad7fd610d2fe9d80416fb218366ccd7d0656b` and available as
`vv3_full_mastery_all_stage_a_candidate`. It reacquires the fixed current-save
manager before both dry runs, uses the native skill writer and Award evaluator,
and supports only `collection_progression` and `immediate_fixed`. Both
expanded-256 modes reject the feature and remain ON HOLD. Commands 6 and 8,
ownership/Remove, raw skill stores, and save-format changes remain absent.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed --output-root "path\chosen output parent"
python src/vv_fun_patcher.py apply "path\game.exe" --patch-mode experimental_expanded_256_progression --copy-vanilla-saves --output-root "path\chosen output parent"
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed --output-root "path\chosen output parent"
```

Technical evidence is in `docs/max-population-research.md`,
`docs/island-event-population-research.md`,
`docs/experimental-256-cap-research.md`, and the game-specific reports under
`docs/`.

The five legacy Origins village-wide feature records are currently fail-closed and
absent from the catalog because commands 6/7/8 share one atomic payload whose
Full Mastery path has not received a complete GO gate as an atomic bundle. The disabled
diagnostic IDs are `vv1_origins_village_wide_upgrades` through
`vv5_origins_village_wide_upgrades`. Their payload bytes are retained for
evidence but are not applied. Each historically depends on that game's
`enable_origins_exclusive_features` prerequisite and adds the three
1,000,000-tech-point rows: All Villagers Like Running, Grant Full Mastery to All
Villagers, and All Villagers are 18. VV3's corrected command-6-only
`vv3_all_villagers_like_running` feature is HARD WITHDRAWN and catalog-hidden
after the intermittent Run2 status-2 crash; runtime fault capture remains
required and commands 7/8 remain absent. VV4's
independent command-7-only Full Mastery implementation is emitted-byte
certified under `91a01eba0dc561b1244184301837b7199868c490` and enabled without
exposing commands 6/8 or the legacy atomic village-wide record.
VV5's former command-7-only Full Mastery package at commit `5e52be5` was
withdrawn after an immediate startup auto-close. The corrected constructors
were independently certified under `7970cd9`, and M2 passed startup and Full
Mastery live testing. The disabled geometry candidate now uses cached
`Images\\btn_trophies.png`, native resource `0x6A` (96x39), at local `(137,2)`
for both Tech and Detail, preserving event 13, `sub_401BD0`, and `0x40C680`
ownership; independent emitted-byte recertification remains required.
The VV5 Full Mastery and Running candidates remain disabled and catalog-hidden.
The stock `sub_44B560` routine is the Detail input/hit-test method and is
forbidden for event 13 routing. Authenticated historical C99/C260 evidence
mechanically proves the offline `0x44BC20` event detour and ownership chain,
but hot uninstall, current composition, runtime, player, and publication
remain STOP.
The feature is inspired by the
selected exclusive upgrades in the Virtual Villagers 1 mobile port. VV5
excludes Heathens; all games leave movement speed, nursing/pregnancy timers,
and unrelated Like slots untouched.
