# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

The app uses the supplied transparent `Island.png` artwork as its title-bar icon and as small image decorations around both its name and the credit:

`[Island image] Created with Codex AI. Made with love by Lorsieab2 :) [Island image]`

The complete interface has a vertical scrollbar and supports mouse-wheel scrolling, so every patch option, game-folder field, action, and status message remains reachable on shorter displays.

Its standard max-population modes use every built-in villager slot: 256 slots in A New Home and The Lost Children, and 150 slots in The Secret City, The Tree of Life, and New Believers. Two experimental modes structurally expand VV3-VV5 to 256 full records.

## Four patch styles

Choose the style in the patcher; the choice and all paths are remembered.

| Style | Collection behavior | Output EXE |
|---|---|---|
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `(Game name) - Modded.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `(Game name) - Modded.exe` |
| Experimental Expanded 256 Villagers | VV3-VV5 expand their physical record pool and saved-villager table from 150 to 256. VV1-VV2 use their existing 256 slots. The cap is immediate and bonuses no longer change it. | `(Game name) - Modded.exe` |
| Experimental Expanded 256 - Collection Progression | Uses the same expanded records, but collections retain their original bonuses and are required to reach 256. The Secret City's level-3 Magic bonus also remains active. | `(Game name) - Modded.exe` |

Every mode and optional-patch combination uses the same stable short EXE name. The selected mode, optional patches, hashes, and applied edits remain identified in the adjacent `.patch-log.json`.

VV3-VV5 experimental builds keep the stock save filenames. Their short `(Game name) - Modded.exe` executables use separate, short executable-named save folders, so the extra E-filename convention is unnecessary. The patcher copies the complete game folder—including `fmod.dll`, SDL2, image libraries, and all data files—then places the modified EXE inside it. Startup is verified for all three expanded games; reaching, saving, and reloading a live 256-villager village remains long-play testing, so the mode is explicitly experimental.

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

## VV2: Teaching Children Grants Skill

Enable **Teaching Children Grants Skill (The Lost Children)** to reward every attending child once after that child's full stock lesson queue finishes. Each attendee gains 7, 8, or 9 points in Farming, Building, Research, Healing, or Parenting. All five choices have equal odds, and skills remain capped at 100.

That award matches VV3's code-confirmed Tribal Chief lesson. The patch does not create extra lessons, change who attends, alter the teacher requirement, reward children who are not enrolled by the stock lesson routine, or reward an interrupted lesson that never reaches the callback.

## VV5: Heathen Mommy Puzzle Restoration

Enable **Heathen Mommy Puzzle Restoration (New Believers)** to restore the natural-build Heathen Mommy to newly created villages and restore the hidden 17th Heathen Parent graphic to the Puzzles screen. The supplied natural build creates a 29th Heathen with tag 17, initializes her, and assigns one forced nursing baby. The supported modern initializer creates only 28 Heathens and omits that sequence.

The patch reproduces the natural build's exact mother arguments and nursing-baby call, then restores the retained locked/solved puzzle graphic using puzzle 17's actual completion state. The mother and baby require two physical population slots. This new-game initialization does not retroactively add a mother to an existing save.

## VV4: Complete Fish Scales = Golden Fish in Nets

Enable **Complete Fish Scales = Golden Fish in Nets (The Tree of Life)** to delay Golden Fish eligibility until all 12 Fish Scales have been collected. Stock VV4 allows Golden Fish after only one scale and uses the chance `2 × collected scales + 1%`.

The patch changes only the eligibility threshold from 1 to 12. At full completion, the stock formula still gives a 25% Golden Fish chance. Normal fish, fishing animations, food awards, scale collection, and all other fishing outcomes remain unchanged.

## VV3: Nature Level 1 Actually Replenishes Food Sources Faster

Enable **Nature Level 1 Actually Replenishes Food Sources Faster (The Secret City)** to make the technology description literal. At Nature level 1 or higher, fruit trees become refill-eligible after 2 hours 15 minutes instead of 3 hours, and honey becomes refill-eligible after 45 minutes instead of 1 hour.

The stock Nature fruit quantity is preserved at the shorter interval: approximately 126 fruit instead of 111 for the same stock refill group. Honey also receives the exact `42/37` proportional quantity bonus, normalized to its new 45-minute interval. Nature level 0 retains stock timing and amounts. The 3,000-unit honey cap remains unchanged.

## VV5: Easier Devotee Training

Enable **Easier Devotee Training (New Believers)** so any villager with positive Devotion skill can spontaneously choose the game's original **Honoring** action. The stock autonomous opportunity is confined to the Retired Chief job state; other devotees normally have to be dropped on the upgradeable statue to begin Honoring. This patch checks actual Devotion skill instead.

The normal idle scheduler and its existing timing chance remain unchanged. The patch reuses the stock Honoring action queue and skill-gain behavior, does not grant Devotion directly, and does not alter conversion, statue upgrades, manual statue assignment, or Devotion thresholds. **Spreading the Word remains a Retired Chief activity and is not assigned to ordinary devotees.**

## VV5: Statue Drops — Polishing or Honoring

Enable **Statue Drops: Polishing or Honoring (New Believers)** so dropping a villager on either the upgradeable statue or its completed form chooses with equal 50/50 odds between the game's original **Polishing the Statue** and **Honoring** behaviors. Both original action queues remain intact; the patch changes only which one is selected for the manual drop.

This provides a manual Devotion-training route after the Heathens are gone. It does not change autonomous work, Devotion gains, statue upgrades, or Retired Chief activities.

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

All four patch styles add a slot-saturation guard at the selected mode's physical boundary:

- Three or more slots left: singleton, twin, and triplet rolls are unchanged.
- Two slots left: a rolled triplet safely becomes twins.
- One slot left: a rolled twin or triplet safely becomes a singleton.
- No slots left: the normal population predicate blocks the birth.

This lets reproduction fill the final slot without permitting the population to exceed the game's real villager array. New Believers uses physical slot demand rather than only its displayed believer count, so still-active Heathens, corpses, and nursing babies cannot make the final multiple birth overbook the shared pool.

### Island Event population safety

All five games also contain Island Events that add villagers. The patcher guards every identified direct population-adding outcome: repeated allocations stop when the selected physical pool fills, and VV4/VV5 Abandoned Infants is reduced from six babies when fewer than six physical slots remain. Standard VV3-VV5 modes use 150; the experimental mode uses 256. Events that remove villagers are unchanged. VV5 conversions and The Defector are unchanged because they reclassify existing records instead of allocating new ones.

## Use

1. Extract the latest release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Select a patch style.
4. Choose **One Game** or **All 5 Games**.
5. For one game, select its original EXE. For all five, select one folder per game.
6. Validate, dry run, or create the copied-and-modified game folder set.

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The One Game tab includes clickable **Open Vanilla EXE Folder** and **Open Modified EXE Folder** links. All 5 Games provides matching Vanilla folder and Modified folder links on every game row. After patching, a compact confirmation window provides clear clickable links to both folders for every completed game.

The **Additional fun patches** section includes **Select All Patches** and **Deselect All Patches** buttons. They change every optional fun-patch checkbox at once without changing the selected population patch style, and the selection is remembered normally.

For every selected game, the patcher creates one short sibling folder named **`(Game name) - Modded`** containing **`(Game name) - Modded.exe`**. It copies every file and subfolder from the original game folder, verifies the copied files by SHA-256, keeps the stock EXE in the copy, and adds the modified EXE plus its `.patch-log.json`. The original folder and original EXE are never edited, renamed, replaced, or deleted. Applying another patch style refreshes that game's same Modded folder after confirmation.

## Exact-build safety

Support is bound to the exact SHA-256 and size of each researched stock executable. Unknown, modified, corrupt, duplicate, or incorrectly assigned EXEs are refused. Every original byte to be changed is guarded, file size is preserved, the PE checksum is recalculated, and each result is read back and hashed.

Bulk mode validates and renders all five inputs before writing, then stages and verifies all five complete folder copies before committing them. If an existing copied folder is replaced, the patcher uses a temporary backup and restores it if the batch commit fails.

No game executable, save, extracted asset, or generated output is committed to this repository.

## Command line

Pass `--patch-mode collection_progression`, `--patch-mode immediate_fixed`, `--patch-mode experimental_expanded_256`, or `--patch-mode experimental_expanded_256_progression` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. Optional features use repeatable `--fun-patch` arguments: `vv1_school_lessons_grant_skill`, `vv1_continue_research_at_max_technologies`, `vv1_f6_clothing_change_cheat`, `vv2_easier_healing_mastery`, `vv2_teaching_children_grants_skill`, `vv3_nature_honey_refill`, `vv4_complete_scales_golden_fish`, `vv5_heathen_mommy_puzzle`, `vv5_easier_devotee_training`, `vv5_statue_polishing_or_honoring`, and `vv5_vv4_nursery_divisor_parity`.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed
python src/vv_fun_patcher.py apply "path\game.exe" --patch-mode collection_progression
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode experimental_expanded_256
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode experimental_expanded_256_progression
```

Technical evidence is in `docs/max-population-research.md`,
`docs/island-event-population-research.md`,
`docs/experimental-256-cap-research.md`, and the game-specific reports under
`docs/`.
