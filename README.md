# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

The app uses the supplied transparent `Island.png` artwork as its title-bar icon and as small image decorations around both its name and the credit:

`[Island image] Created with Codex AI. Made with love by Lorsieab2 :) [Island image]`

The complete interface has a vertical scrollbar and supports mouse-wheel scrolling, so every patch option, game-folder field, action, and status message remains reachable on shorter displays.

Its max-population modes use every verified built-in villager slot: 256 slots in A New Home and The Lost Children, and 150 slots in The Secret City, The Tree of Life, and New Believers.

## Two patch styles

Choose the style in the patcher; the choice and all paths are remembered.

| Style | Collection behavior | Output EXE |
|---|---|---|
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `(Game name) - Modded.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `(Game name) - Modded.exe` |
| Experimental Expanded 256 Villagers | VV3–VV5 expand their physical records and save layout to 256 immediately; collections no longer affect that expanded ceiling. | `(Game name) - Modded 256.exe` |
| Experimental Expanded 256 - Collection Progression | VV3–VV5 expand to 256 while their original collection and Magic Tech bonuses remain required to reach 256. | `(Game name) - Modded 256.exe` |

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

Enable **Reenable F6 Clothing Change Cheat (A New Home)** so pressing F6 advances the selected active villager to the next stock outfit. The cycle covers the game's ordinary clothing indices 0 through 19 and wraps from 19 back to 0. Pressing F6 without a valid active selection changes nothing.

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

## VV1: Enable Origins-Exclusive Features

Enable **Enable Origins-Exclusive Features (A New Home)** to add an
**Upgrades** button to VV1's Tech screen. It ports the supplied
Virtual Villagers: Origins APK's exclusive purchases to the supported desktop
build:

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
- **Tech Point Doubler** — 500,000 tech points; permanently doubles positive
  tech-point awards, but not costs or losses.
- **Food Point Doubler** — 500,000 tech points; permanently doubles positive
  food awards, but not spending or losses.

The Tech screen presents its five village upgrades together, and the Villager
Detail screen presents its four villager upgrades together, each with icons
and individual Buy buttons. The two doublers are stored in otherwise-unused
fields of the current saved village, so purchasing or removing one affects
only that save slot. **Bump Max Population** is deliberately omitted because
the patcher's population modes handle population limits separately.

## VV2: Enable Origins-Exclusive Features

Enable **Enable Origins-Exclusive Features (The Lost Children)** to add the
same icon-based village and selected-villager upgrade menus to VV2. The
supported desktop build receives:

- **Time Warp**, **Island Event**, and the literal stock **Barrel of Babies**
  event;
- removable **Tech Point Doubler** and **Food Point Doubler** purchases stored
  only in the current saved village;
- **Grant Youth**, **Grant Full Mastery**, **Grant Running**, and **Set Age to
  18** for the selected villager.

The prices and refusal rules match the A New Home port. Barrel of Babies calls
VV2's native three-child event path and checks the game's comprehensive
occupied-plus-reserved population count before charging. Grant Running uses
only the three normal Like slots, removes Running from the selected villager's
normal Dislike slots, and never edits movement speed.

Positive food and tech awards use VV2's central stock award routines. The
doublers do not affect deductions or Island Event awards. A paused village
cannot purchase Time Warp because VV2's paused catch-up logic discards elapsed
age. **Bump Max Population** remains omitted.

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

## VV2: Gong of Wonder Coconuts Fix

Enable **Gong of Wonder Coconuts Fix (The Lost Children)** so the coconut outcome adds 30 to the trees' existing amount. Stock VV2 assigns the coconut resource to 30, which can erase a larger existing supply. The patch corrects both stock outcome paths and changes no other Gong result.

## VV5: Heathen Mommy Puzzle Restoration

Enable **Heathen Mommy Puzzle Restoration (New Believers)** to restore the natural-build Heathen Mommy to newly created villages and restore the hidden 17th Heathen Parent graphic to the Puzzles screen. Its full visible tile rolls over to **This milestone has not been completed!** while locked and **The Heathen Parent** when completed. The supplied natural build creates a 29th Heathen with tag 17, initializes her, and assigns one forced nursing baby. The supported modern initializer creates only 28 Heathens and omits that sequence.

The patch reproduces the natural build's exact mother arguments and nursing-baby call, then restores the retained locked/solved puzzle graphic using puzzle 17's actual completion state. The mother and baby require two physical population slots. This new-game initialization does not retroactively add a mother to an existing save.

## VV4: Complete Fish Scales = Golden Fish in Nets

Enable **Complete Fish Scales = Golden Fish in Nets (The Tree of Life)** to delay Golden Fish eligibility until all 12 Fish Scales have been collected. Stock VV4 allows Golden Fish after only one scale and uses the chance `2 × collected scales + 1%`.

The patch changes only the eligibility threshold from 1 to 12. At full completion, the stock formula still gives a 25% Golden Fish chance. Normal fish, fishing animations, food awards, scale collection, and all other fishing outcomes remain unchanged.

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

No game executable, save, extracted asset, or generated output is committed to this repository.

## Command line

Pass `--patch-mode collection_progression`, `--patch-mode immediate_fixed`, `--patch-mode experimental_expanded_256`, or `--patch-mode experimental_expanded_256_progression` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. Optional features use repeatable `--fun-patch` arguments: `vv1_school_lessons_grant_skill`, `vv1_continue_research_at_max_technologies`, `vv1_f6_clothing_change_cheat`, `vv1_magic_fruit_alters_mortality`, `vv1_builder_action_fixes`, `vv1_enable_origins_exclusive_features`, `vv2_easier_healing_mastery`, `vv2_teaching_children_grants_skill`, `vv2_hospital_recovery_heals`, `vv2_gong_of_wonder_coconuts_fix`, `vv3_nature_honey_refill`, `vv3_nature_level_three_alters_mortality`, `vv4_complete_scales_golden_fish`, `vv5_heathen_mommy_puzzle`, `vv5_easier_devotee_training`, `vv5_statue_polishing_or_honoring`, and `vv5_vv4_nursery_divisor_parity`.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed --output-root "path\chosen output parent"
python src/vv_fun_patcher.py apply "path\game.exe" --patch-mode experimental_expanded_256_progression --copy-vanilla-saves --output-root "path\chosen output parent"
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed --output-root "path\chosen output parent"
```

Technical evidence is in `docs/max-population-research.md`,
`docs/island-event-population-research.md`,
`docs/experimental-256-cap-research.md`, and the game-specific reports under
`docs/`.
