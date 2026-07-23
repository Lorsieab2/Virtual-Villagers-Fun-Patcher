# Virtual Villagers Fun Patcher

An offline Windows patcher for miscellaneous fun patches in all five classic Virtual Villagers PC games.

Its max-population patch uses every built-in villager slot: 256 slots in A New Home and The Lost Children, and 150 slots in The Secret City, The Tree of Life, and New Believers.

## Two patch styles

Choose the style in the patcher; the choice and all paths are remembered.

| Style | Collection behavior | Output suffix |
|---|---|---|
| Collection Progression Max Pop | The original population bonuses remain active and are required to reach the slot maximum. The Secret City also retains its level-3 magic bonus. | `- Modified Max Pop.exe` |
| Immediate Fixed Max Pop | The slot maximum is available immediately. Collections no longer change it; The Secret City's magic tech no longer changes it either. | `- Fixed Max Pop.exe` |

A New Home has no collection population bonus, so both styles use the same 256 limit but still create separately named outputs.

## VV2: Easier Healing Mastery

Enable the optional **Easier Healing Mastery (VV2)** checkbox to change the Healing job fallback in The Lost Children. When a healer or a villager who prefers Healing has no sick villager to treat, the stock job scheduler now enters its existing persistent plant-study state instead of returning "no work." The same stock state is processed during ordinary play and time catch-up.

The patch does not change healing gains, illness, food, skill thresholds, plant availability, or manual plant study. If the option is combined with Collection Progression, the output is named `Virtual Villagers - The Lost Children - Modified Max Pop + Easier Healing.exe`; Immediate Fixed uses the matching `Fixed Max Pop + Easier Healing.exe` name. Max-pop-only names remain unchanged.

## VV1: School Lessons Grant Skill

Enable **School Lessons Grant Skill (VV1)** to reward a villager once whenever the unlocked stock routine sends that villager to school. The attendee gains one point in Farming, Building, Research, Healing, or Parenting with equal odds; skills remain capped at 100. The patch does not unlock the school, change attendance selection, or alter the school action queue. Its output name adds `+ School Grants Skill.exe`.

## VV1: Continue Research at Max Technologies

Enable **Continue Research at Max Technologies (VV1)** so researchers remain eligible for the stock research action after all six technologies reach level 3. They continue using the original research queue, Research skill, Science-technology multiplier, and tech-point award routine. Its output name adds `+ Continue Max-Tech Research.exe`.

## VV2: Teaching Children Grants Skill

Enable **Teaching Children Grants Skill (VV2)** to make the stock Teaching Children activity reward every attending child once when the lesson begins. Each attendee gains exactly one point in Farming, Building, Research, Healing, or Parenting. All five choices have equal odds, and a skill already at 100 is left at 100.

The patch does not create extra lessons, change who attends, alter the teacher requirement, or reward children who are not enrolled by the stock lesson routine. Its output name adds `+ Teaching Grants Skill.exe`; selecting both VV2 options adds both tags.

## VV5: Heathen Mommy Puzzle Restoration

Enable **Heathen Mommy Puzzle Restoration (VV5)** to restore the hidden 17th Heathen Parent graphic to the Puzzles screen. The modern executable still contains and creates the original `CHeathenMommyPuzzle`, retains its stock trigger and completion logic, and includes both `puzzle_bonus_notsolved.png` and `puzzle_bonus_solved.PNG`. Its Puzzles-screen renderer is the removed piece.

The patch restores that one stock rendering branch using puzzle 17's actual completion state and the modern executable's retained images. It does not invent a replacement puzzle or change the original trigger requirements. Its output name adds `+ Heathen Mommy.exe`.

## VV5: Easier Devotee Training

Enable **Easier Devotee Training (VV5)** so any villager with positive Devotion skill can spontaneously choose the game's original **Honoring** action. The stock autonomous opportunity is confined to the Retired Chief job state; other devotees normally have to be dropped on the upgradeable statue to begin Honoring. This patch checks actual Devotion skill instead.

The normal idle scheduler and its existing timing chance remain unchanged. The patch reuses the stock Honoring action queue and skill-gain behavior, does not grant Devotion directly, and does not alter conversion, statue upgrades, manual statue assignment, or Devotion thresholds. **Spreading the Word remains a Retired Chief activity and is not assigned to ordinary devotees.** Its output name adds `+ Easier Devotee.exe`.

## VV5: Statue Drops — Polishing or Honoring

Enable **Statue Drops: Polishing or Honoring (VV5)** so dropping a villager on either the upgradeable statue or its completed form chooses with equal 50/50 odds between the game's original **Polishing the Statue** and **Honoring** behaviors. Both original action queues remain intact; the patch changes only which one is selected for the manual drop.

This provides a manual Devotion-training route after the Heathens are gone. It does not change autonomous work, Devotion gains, statue upgrades, or Retired Chief activities. Its output name adds `+ Random Statue Training.exe`.

| Game | Stock final maximum | Collection Progression maximum | Immediate Fixed maximum |
|---|---:|---:|---:|
| A New Home | 90 | 256 | 256 |
| The Lost Children | 115 | 231 to 256 | 256 |
| The Secret City | 125 | 115 to 150 | 150 |
| The Tree of Life | 115 | 125 to 150 | 150 |
| New Believers | 105 | 135 to 150 | 150 |

Housing gates remain in place.

## Safe twins and triplets at the ceiling

All five stock games test the population limit once before choosing a singleton, twins, or triplets. Without an additional guard, a multiple birth at maximum minus one can report maximum plus one or maximum plus two, even though no corresponding villager records remain.

Both patch styles add a slot-saturation guard:

- Three or more slots left: singleton, twin, and triplet rolls are unchanged.
- Two slots left: a rolled triplet safely becomes twins.
- One slot left: a rolled twin or triplet safely becomes a singleton.
- No slots left: the normal population predicate blocks the birth.

This lets reproduction fill the final slot without permitting the population to exceed the game's real villager array.

## Use

1. Extract the latest release ZIP.
2. Double-click `Launch Virtual Villagers Fun Patcher.bat`.
3. Select a patch style.
4. Choose **One Game** or **All 5 Games**.
5. For one game, select its original EXE. For all five, select one folder per game.
6. Validate, dry run, or create the modified EXE set.

**Find All 5 in Parent Folder...** can fill the five folder fields when the original EXEs are in the chosen folder or one folder below it.

The original EXEs are never edited, renamed, replaced, or deleted. Outputs and their `.patch-log.json` verification logs are placed beside the originals in their respective game folders. Both styles can coexist.

## Exact-build safety

Support is bound to the exact SHA-256 and size of each researched stock executable. Unknown, modified, corrupt, duplicate, or incorrectly assigned EXEs are refused. Every original byte to be changed is guarded, file size is preserved, the PE checksum is recalculated, and each result is read back and hashed.

Bulk mode validates and renders all five inputs before writing, then stages and verifies all five outputs before placing them into the game folders.

No game executable, save, extracted asset, or generated output is committed to this repository.

## Command line

Pass `--patch-mode collection_progression` or `--patch-mode immediate_fixed` to `dry-run`, `apply`, `dry-run-all`, or `apply-all`. Optional features use repeatable `--fun-patch` arguments: `vv1_school_lessons_grant_skill`, `vv1_continue_research_at_max_technologies`, `vv2_easier_healing_mastery`, `vv2_teaching_children_grants_skill`, `vv5_heathen_mommy_puzzle`, `vv5_easier_devotee_training`, and `vv5_statue_polishing_or_honoring`.

```text
python src/vv_fun_patcher.py dry-run "path\game.exe" --patch-mode immediate_fixed
python src/vv_fun_patcher.py apply "path\game.exe" --patch-mode collection_progression
python src/vv_fun_patcher.py apply-all --vv1 "path\vv1 folder" --vv2 "path\vv2 folder" --vv3 "path\vv3 folder" --vv4 "path\vv4 folder" --vv5 "path\vv5 folder" --patch-mode immediate_fixed
```

Technical evidence is in `docs/max-population-research.md`, `docs/vv2-easier-healing-research.md`, `docs/vv2-teaching-children-research.md`, `docs/vv1-school-lessons-research.md`, `docs/vv1-max-tech-research.md`, `docs/vv5-heathen-mommy-research.md`, `docs/vv5-easier-devotee-research.md`, and `docs/vv5-statue-training-research.md`.
