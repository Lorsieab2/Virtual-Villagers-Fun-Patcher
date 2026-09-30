# Village Statistics — Complete Five-Game Implementation Directive

The owner's directive of 2026-09-29, recorded verbatim. It is the governing
specification for the Village Statistics log in all five games and supersedes
earlier requirement notes where they differ.

---

🚨 VILLAGE STATISTICS — COMPLETE FIVE-GAME IMPLEMENTATION DIRECTIVE
OWNER-EXPLICIT REQUIREMENTS — IMPLEMENT EXACTLY AS WRITTEN
Claude:
Implement and verify the following Village Statistics for Virtual Villagers 1, Virtual Villagers 2, Virtual Villagers 3, Virtual Villagers 4 and Virtual Villagers 5.
Read this entire directive before modifying anything.
These requirements are deliberate.
DO NOT GENERALIZE THEM.
DO NOT RENAME STATISTICS.
DO NOT ASSUME TWO SIMILARLY NAMED STATISTICS MEAN THE SAME THING.
DO NOT ASSUME THAT AN EXISTING COUNTER DOES WHAT ITS LABEL SAYS.
DO NOT CLAIM SOMETHING IS ALREADY TRACKED UNTIL YOU HAVE TRACED THE ACTUAL CODE THAT READS AND WRITES IT.
IF A REQUIRED COUNTING HOOK DOES NOT EXIST, IMPLEMENT ONE.
IF REQUIRED PERSISTENT STORAGE DOES NOT EXIST, IMPLEMENT IT.
I. COMMON STATISTICS — REQUIRED FOR VV1, VV2, VV3, VV4 AND VV5
Every one of the five games must track and display:
1. Real Hours Played
One Isola Year at Normal game speed equals:
2 real-life hours
Display and track Real Hours Played, not merely Isola Years.
Use the game's actual passage-of-time mechanics.
Verify relevant behavior across normal gameplay, game-speed changes, time catch-up and time warp where applicable.
2. Food Gathered
Track total food gathered.
3. Tech Points Earned
Track total Tech Points earned.
4. People Cured
Track total people cured.
5. Mushrooms Found
Track total mushrooms found.
6. Highest Population
Track the highest population the village has ever reached.
This is a historical maximum.
Population decreasing must NOT decrease this statistic.
7. Village Elders
EXACT DEFINITION
A Village Elder is:
A VILLAGER WHO HAS REACHED MASTER STATUS ON ANY 3 SKILLS.
This definition applies to the Village Elders statistic.
The villager must have Master status in at least three distinct skills.
Examples:

* Master in Farming + Building + Research = Village Elder.
* Master in Farming + Healing + Parenting = Village Elder.
* Master in any other valid combination of 3 skills = Village Elder.
* Master in only 2 skills = NOT a Village Elder.
* Master in 4 or more skills = still one Village Elder, not multiple Elders.

COUNT THE VILLAGER, NOT THE NUMBER OF MASTERED SKILLS.
A qualifying villager counts as:
1 Village Elder
regardless of whether that villager has mastered exactly 3 skills or more than 3.
Do not count the same villager again when they master a fourth or fifth skill.
DO NOT SUBSTITUTE ANOTHER DEFINITION
Do NOT define Village Elder based on:

* Age.
* Appearance.
* Clothing.
* Displayed title alone.
* An unrelated "elder" flag.
* A convenient variable name.
* An existing statistic label.
* Number of years lived.

The required criterion is:
MASTER STATUS IN ANY 3 SKILLS.
Inspect the actual skill data and determine when a villager satisfies this requirement.
If the game already has an authoritative Village Elder mechanism, verify from the actual code that it uses this criterion before relying on it.
If it does not, implement the required tracking.
8. Oldest Villager
Track the oldest villager using the game's actual villager-age data.
9. Island Events Seen
Track the total number of Island Events seen.
10. Babies Made
Track the number of babies made.
11. Twins Birthed
Track the number of twin birth events.
A twin birth increments:
+1
Do not count the two babies as +2 for this statistic.
12. Triplets Birthed
Track the number of triplet birth events.
A triplet birth increments:
+1
Do not count the three babies as +3 for this statistic.
13. Villagers Buried
This statistic requires BOTH retroactive initialization and ongoing tracking.
It counts deceased villagers.
For existing saves, retroactively determine the applicable historical number of dead villagers represented through:

* Graveyard graves
* Mausoleum records
* Roster of the Dead records

COUNT EACH DEAD VILLAGER EXACTLY ONCE.
If multiple game systems represent the same deceased villager, do NOT count that death multiple times.
After establishing the historical baseline:
+1 for every villager skeleton picked up.
Do not increment repeatedly for the same skeleton.
Investigate each game's actual death/burial systems individually.
Do not assume all five games store this information identically.
14. Puzzles Solved
Display:
Puzzles Solved: X out of Y
where X is the number solved and Y is the applicable maximum number of puzzles.
The maximum is usually:
16
For VV5 with the Heathen Mommy patch active, the maximum is:
17
Do not universally hard-code 16.
II. EXACT VV1 STATISTICS
VV1 must contain:

1. Real Hours Played
2. Food Gathered
3. Tech Points Earned
4. People Cured
5. Mushrooms Found
6. Highest Population
7. Village Elders
8. Oldest Villager
9. Island Events Seen
10. Babies Made
11. Twins Birthed
12. Triplets Birthed
13. Villagers Buried
14. Puzzles Solved: X out of Y

There are no additional game-specific statistics currently requested for VV1.
DO NOT INVENT ANY.
III. EXACT VV2 STATISTICS
VV2 must contain:

1. Real Hours Played
2. Food Gathered
3. Tech Points Earned
4. People Cured
5. Mushrooms Found
6. Highest Population
7. Village Elders
8. Oldest Villager
9. Island Events Seen
10. Babies Made
11. Twins Birthed
12. Triplets Birthed
13. Villagers Buried
14. Puzzles Solved: X out of Y
15. Special Stews Found
16. Total Stews Found

VV2 — Special Stews Found
This should correspond to the game's actual Special Stews Found statistic.
However:
DO NOT ASSUME AN EXISTING COUNTER IS CORRECT PURELY BECAUSE ITS LABEL SAYS "SPECIAL STEWS FOUND."
Trace the actual implementation.
Determine what causes it to increment, what combinations it recognizes, whether duplicate recipes increment it and whether it persists correctly.
Only after inspecting the actual code may you state what the existing counter does.
VV2 — Total Stews Found
`Total Stews Found` means:
THE NUMBER OF UNIQUE PLANT/HERB INGREDIENT COMBINATIONS SUCCESSFULLY MADE.
There are NO Special Stew restrictions for this statistic.
If combination A is successfully made for the first time:
+1
If combination A is successfully made again:
+0
If combination B is successfully made for the first time:
+1
Therefore:
50 STEWS MADE FROM ONLY 3 UNIQUE COMBINATIONS = TOTAL STEWS FOUND: 3
IV. EXACT VV3 STATISTICS
VV3 must contain:

1. Real Hours Played
2. Food Gathered
3. Tech Points Earned
4. People Cured
5. Mushrooms Found
6. Highest Population
7. Village Elders
8. Oldest Villager
9. Island Events Seen
10. Babies Made
11. Twins Birthed
12. Triplets Birthed
13. Villagers Buried
14. Puzzles Solved: X out of Y
15. Chiefs Robed
16. Stews Found

VV3 — Chiefs Robed
Count everyone successfully made Chief using the robe who actually bears the title:
Tribal Chief
A successful new Chief:
+1
Merely interacting with the robe is NOT sufficient.
An unsuccessful attempt is NOT sufficient.
Determine the actual game condition that establishes that the villager became Tribal Chief.
VV3 — Stews Found
Track:
THE NUMBER OF UNIQUE PLANT/HERB INGREDIENT COMBINATIONS SUCCESSFULLY MADE.
Include all applicable herb combinations, including faction-specific herbs.
Repeatedly making the same combination must NOT increase the statistic.
V. EXACT VV4 STATISTICS
VV4 must contain:

1. Real Hours Played
2. Food Gathered
3. Tech Points Earned
4. People Cured
5. Mushrooms Found
6. Highest Population
7. Village Elders
8. Oldest Villager
9. Island Events Seen
10. Babies Made
11. Twins Birthed
12. Triplets Birthed
13. Villagers Buried
14. Puzzles Solved: X out of Y
15. Debris Cleared
16. Stews Found

VV4 — Debris Cleared
Track debris cleared from the stream using the game's actual debris units.
An existing trophy is awarded for clearing:
1000 units of debris
Investigate the actual underlying debris counter and execution path.
Do not infer the statistic's behavior merely from trophy text or variable labels.
VV4 — Stews Found
Track:
THE NUMBER OF UNIQUE PLANT/HERB + WATER-TYPE COMBINATIONS SUCCESSFULLY MADE.
VV4 recipe identity includes BOTH:
PLANT/HERB COMBINATION
and
WATER TYPE
Water type must distinguish:

* Fresh water
* Salty water

Therefore:
Herbs A+B+C + Fresh Water
and
Herbs A+B+C + Salty Water
are:
TWO DIFFERENT UNIQUE STEWS.
Making the same fresh-water recipe repeatedly counts once.
Making its salty-water counterpart for the first time counts as another unique discovery.
VI. EXACT VV5 STATISTICS
VV5 must contain:

1. Real Hours Played
2. Food Gathered
3. Tech Points Earned
4. People Cured
5. Mushrooms Found
6. Highest Population
7. Village Elders
8. Oldest Villager
9. Island Events Seen
10. Babies Made
11. Twins Birthed
12. Triplets Birthed
13. Villagers Buried
14. Puzzles Solved: X out of Y
15. Heathens Converted

VV5 — Heathens Converted
Count conversions of:

* Heathen Chief
* Red Masks
* Purple Masks
* Blue Masks
* Orange Masks
* Heathen Mommy

Normal applicable heathens count:
+1 each
Heathen Mommy counts:
+2
Therefore:
One normal applicable heathen + Heathen Mommy =
+3 Heathens Converted
Do not omit Heathen Mommy because she originates from a patch.
When the Heathen Mommy patch is active, she participates in this statistic.
The Heathen Mommy patch also changes the puzzle maximum:
Puzzles Solved: X out of 17
VII. UNIQUE STEW DISCOVERY — VV2, VV3 AND VV4
This is an explicit owner requirement.
VV2, VV3 AND VV4 MUST TRACK WHICH ACTUAL INGREDIENT COMBINATIONS HAVE BEEN DISCOVERED.
A simple integer that says `3 recipes found` is NOT sufficient by itself.
The implementation must remember which three recipes produced that count so it can determine whether the next stew is new or a duplicate.
VIII. STORE DISCOVERED STEW INGREDIENT COMBINATIONS IN A SEPARATE `.DAT` FILE
MANDATORY STORAGE REQUIREMENT
The tracked/discovered stew ingredient combinations must be persisted in a:
SEPARATE `.DAT` FILE.
Do NOT store the discovered-recipe set solely in:

* Process memory
* A temporary file
* The executable
* The DLL
* A source-code constant
* The ordinary statistics integer
* A transient runtime structure

The `.dat` file must contain sufficient information to reconstruct the set of already-discovered stew combinations.
The displayed statistic may use the number of unique recipe identities contained in that persistent set.
KEEP THE GAMES SEPARATE
VV2, VV3 and VV4 have different ingredient systems.
Their discovered-recipe data must never contaminate one another.
Use separate game-specific `.dat` files or another clearly separated `.dat` organization that prevents cross-game collisions.
Do not treat a VV2 recipe as discovered in VV3 or VV4.
PERSISTENCE
After:

1. Discovering recipe A.
2. Closing the game.
3. Reopening the game.
4. Making recipe A again.

Expected:
+0
The `.dat` data must establish that recipe A was already discovered.
If recipe B is then made for the first time:
+1
Recipe B must be persisted.
SAFE FILE HANDLING
Do not corrupt or destroy existing discovered-recipe history when updating the file.
Handle a missing file as a new/empty discovery history.
Do not silently erase valid history.
If corruption or an incompatible format is detected, do not invent discoveries.
Use a deterministic, documented representation so the same recipe always resolves to the same identity.
Include a format version or game identifier if necessary.
IX. EXACT RECIPE IDENTITY
For VV2 and VV3:
RECIPE IDENTITY = APPLICABLE PLANT/HERB COMBINATION
For VV4:
RECIPE IDENTITY = APPLICABLE PLANT/HERB COMBINATION + WATER TYPE
Determine from the actual code whether ingredient order matters.
If:
`A + B + C`
and:
`C + B + A`
are treated by the game as the same recipe, normalize them to one recipe identity.
If the game genuinely treats ingredient ordering as significant, preserve the distinction.
DO NOT GUESS. CHECK THE ACTUAL STEW CODE.
For VV4, fresh versus salty water remains a required distinction.
X. IF THE COUNTING HOOK DOESN'T EXIST, MAKE ONE
IF THE REQUIRED COUNTING HOOK DOES NOT EXIST, IMPLEMENT ONE.
Locate the actual successful stew-completion execution path.
The hook must obtain authoritative information sufficient to determine:

1. A stew was successfully made.
2. Which plants/herbs were used.
3. For VV4, which water type was used.
4. The normalized recipe identity.
5. Whether that identity already exists in the applicable `.dat` file.

If the recipe is new:

1. Persist it.
2. Increase the unique discovery count exactly once.

If the recipe already exists:
DO NOT INCREMENT.
Do not count merely selecting ingredients.
Do not count beginning stew preparation if successful completion has not occurred.
Do not hook an unrelated function merely because its name sounds appropriate.
XI. DO NOT TRUST LABELS — THIS APPLIES TO EVERY STATISTIC
DO NOT CLAIM THAT SOMETHING IS BEING COUNTED PURELY BECAUSE OF ITS LABEL.
You have mislabeled things before.
A variable, function, counter, comment or UI string named:
`StewsFound`
`StewCount`
`Recipes`
`SpecialStews`
`Deaths`
`Babies`
`Elders`
or anything similarly convenient is:
NOT PROOF OF WHAT IT COUNTS.
Before reusing an existing counter:

1. Find where it is initialized.
2. Find relevant reads.
3. Find relevant writes.
4. Find every applicable increment/update path.
5. Determine exactly what event changes it.
6. Determine whether duplicate events change it.
7. Determine whether it persists.
8. Determine whether catch-up or time warp changes its behavior.
9. Compare its actual behavior against MY definition.

For Village Elders specifically, verify that the implementation actually corresponds to:
ONE VILLAGER HAVING MASTER STATUS IN ANY THREE DISTINCT SKILLS.
Do not see a variable labeled `elders` and simply declare it correct.
LABELS ARE CLUES.
CODE AND RUNTIME BEHAVIOR ARE EVIDENCE.
XII. RETROACTIVE VALUES VERSUS NEW TRACKING
For every statistic, determine whether historical values can actually be reconstructed from an existing save.
Use authoritative existing data where available.
Do not invent historical values that the game never retained.
If a statistic cannot be reconstructed retroactively, state that limitation precisely.
`Villagers Buried` has the explicit retroactive requirements described above.
For Village Elders, investigate whether the intended statistic represents currently qualifying villagers, historically achieved Elders, or an existing cumulative game counter before choosing persistence behavior. Do not silently substitute one interpretation for another; preserve the owner-defined qualification criterion of Master status in any three skills and identify any historical-storage limitation.
For unique stew `.dat` files, do not pretend to know historical ingredient combinations unless existing game data actually preserves enough information to reconstruct them.
XIII. STATISTICS MUST PERSIST
Cumulative statistics must survive appropriate save/reload cycles.
They must not accidentally reset because:

* The game closes.
* The game reloads.
* The patcher runs again.
* Game speed changes.
* Time catch-up occurs.
* Time warp occurs.
* Population changes.
* A villager dies.
* A temporary runtime structure is rebuilt.
* Details-screen sorting changes.

Prevent duplicate counting caused by events being processed repeatedly.
XIV. MANDATORY VILLAGE ELDER TESTS
Perform these tests for each applicable game.
TEST A — TWO MASTER SKILLS
Villager has Master status in exactly two skills.
Expected:
NOT A VILLAGE ELDER
TEST B — THIRD MASTER SKILL
The same villager reaches Master status in a third distinct skill.
Expected:
VILLAGER QUALIFIES AS ONE VILLAGE ELDER
TEST C — FOURTH MASTER SKILL
That villager subsequently masters a fourth skill.
Expected:
DO NOT COUNT THE SAME VILLAGER AS AN ADDITIONAL ELDER
The villager remains one qualifying Village Elder.
TEST D — DIFFERENT THREE-SKILL COMBINATION
A different villager masters another valid combination of three skills.
Expected:
THAT VILLAGER ALSO QUALIFIES AS A VILLAGE ELDER
The particular three skills do not matter.
TEST E — AGE
Verify that age alone does NOT cause Village Elder qualification.
TEST F — RELOAD/PERSISTENCE
Verify the intended Elder statistic remains correct after save/reload according to the game's actual storage and the required semantics.
XV. MANDATORY STEW REGRESSION TESTS
Perform separately for VV2, VV3 and VV4.
TEST A — FIRST DISCOVERY
Make recipe A.
Expected:
Unique stew count +1
`.dat` contains recipe A.
TEST B — DUPLICATE
Make recipe A again.
Expected:
+0
No duplicate identity should be stored.
TEST C — SECOND UNIQUE RECIPE
Make recipe B.
Expected:
+1
`.dat` represents A and B.
TEST D — RESTART
Close and reopen the game.
Make recipe A again.
Expected:
+0
TEST E — NEW RECIPE AFTER RESTART
Make previously undiscovered recipe C.
Expected:
+1
`.dat` now represents A, B and C.
TEST F — INGREDIENT ORDER
Where permitted, make equivalent ingredients in another order.
Result must follow the actual game's recipe semantics.
Do not assume whether ordering matters.
VV4 TEST G — WATER TYPE
Make the same applicable plant combination with fresh water and salty water.
Expected:
TWO DISTINCT UNIQUE RECIPE IDENTITIES
Verify both are represented distinctly in persistent `.dat` data.
XVI. TEST EVERY STATISTIC
For each game, produce a verification matrix:
STATISTIC → ACTUAL SOURCE/HOOK → INITIALIZATION → UPDATE CONDITION → PERSISTENCE → TEST → RESULT
Do not test only the stews or the new statistics.
Test all required statistics.
Important examples:
Village Elders: villager qualifies upon reaching Master status in any 3 distinct skills and is not duplicated for additional mastered skills.
Highest Population: population rises and falls; historical maximum remains.
Twins Birthed: twin birth increments exactly once.
Triplets Birthed: triplet birth increments exactly once.
Villagers Buried: historical baseline contains each applicable deceased villager exactly once; subsequent skeleton pickups increment once.
VV2 Total Stews Found: duplicate recipes do not increment.
VV3 Chiefs Robed: only successful Tribal Chiefs count.
VV3 Stews Found: unique combinations count once.
VV4 Debris Cleared: actual debris units are tracked.
VV4 Stews Found: plant combination AND water type determine recipe identity.
VV5 Heathen Mommy: conversion increments Heathens Converted by exactly 2.
VV5 Heathen Mommy patch: puzzle maximum becomes 17.
Test live gameplay, time catch-up and time warp wherever applicable.
XVII. EXACT FINAL ACCEPTANCE COUNTS
Report separately:
VV1 — 14/14 required statistics verified
VV2 — 16/16 required statistics verified
VV3 — 16/16 required statistics verified
VV4 — 16/16 required statistics verified
VV5 — 15/15 required statistics verified
For VV2, VV3 and VV4, verification additionally requires proving the separate `.dat` recipe-discovery data behaves correctly.
A statistic that merely appears in the UI is not verified.
A counter that increments incorrectly is not verified.
A counter that does not persist correctly is not verified.
A Village Elder implementation that does not actually evaluate Master status in any 3 skills is not verified.
A correct integer with an incorrect discovered-recipe set is not verified.
A working source implementation absent from the release is not verified.
XVIII. COMMIT IT, SHIP IT AND VERIFY THE ACTUAL DOWNLOAD
Every authorized implementation must progress through:
IMPLEMENTED
→ TESTED
→ COMMITTED
→ PUSHED
→ INTEGRATED INTO THE CORRECT RELEASE SOURCE
→ BUILT
→ PACKAGED
→ PUBLISHED
→ VERIFIED IN THE ACTUAL DOWNLOAD
This includes:

* Counting hooks
* Village Elder detection
* Statistics logic
* Persistence logic
* `.dat` handling
* Required DLL changes
* Executable patches
* Assets
* Patcher changes
* Build scripts
* Packaging configuration

Do not leave fixes in uncommitted files.
Do not leave them on abandoned branches.
Do not test one binary and ship another.
Do not omit required implementation from the packaged release.
Where the environment permits, download the published prerelease into a clean location and verify the actual shipped files and behavior.
IF THE THING PEOPLE DOWNLOAD DOES NOT CONTAIN THE FIX, THE FIX IS NOT SHIPPED.
XIX. FINAL REPORT
For EACH GAME report:

1. Every required statistic.
2. What the statistic actually measures.
3. The actual code/hook responsible for tracking it.
4. How it is initialized.
5. How it is persisted.
6. Tests actually performed.
7. Results.
8. Remaining limitations.

For Village Elders specifically report:

1. Where skill mastery is represented.
2. How Master status is identified.
3. How the number of distinct Mastered skills is calculated.
4. How the implementation detects the transition to 3 Mastered skills.
5. How duplicate counting is prevented when the villager masters additional skills.
6. Tests proving the implementation follows the any 3 skills requirement.

For VV2, VV3 and VV4 additionally report:

1. Stew-completion hook used.
2. Ingredient data captured.
3. Recipe normalization rules.
4. Whether ingredient order matters and the evidence establishing this.
5. `.dat` filename/location and format.
6. Number of recipe identities stored.
7. Duplicate-detection behavior.
8. Reload/persistence test results.
9. For VV4, fresh/salty water distinction test results.

If something is unverified:
SAY EXACTLY WHAT IS UNVERIFIED.
Do not hide it behind an overall success claim.
FINAL STANDING ORDERS
VILLAGE ELDER = ONE VILLAGER WHO HAS REACHED MASTER STATUS IN ANY 3 SKILLS.
THREE DISTINCT MASTERED SKILLS QUALIFY.
THE PARTICULAR THREE SKILLS DO NOT MATTER.
MASTERING ADDITIONAL SKILLS DOES NOT CREATE ADDITIONAL ELDERS FROM THE SAME VILLAGER.
IMPLEMENT MY DEFINITIONS, NOT YOUR INTERPRETATION OF THEIR LABELS.
CHECK THE ACTUAL CODE.
TRACE THE ACTUAL COUNTERS.
TRACE THE ACTUAL HOOKS.
IF THE HOOK DOESN'T EXIST, MAKE ONE.
STORE VV2/VV3/VV4 DISCOVERED STEW COMBINATIONS IN SEPARATE PERSISTENT `.DAT` DATA.
TRACK THE ACTUAL INGREDIENT COMBINATIONS.
VV4 MUST INCLUDE FRESH/SALTY WATER IN RECIPE IDENTITY.
DO NOT COUNT DUPLICATE RECIPES TWICE.
DO NOT INVENT HISTORICAL DATA THAT DOES NOT EXIST.
TEST EVERY STATISTIC PER GAME.
COMMIT THE IMPLEMENTATION.
SHIP THE IMPLEMENTATION.
VERIFY THE IMPLEMENTATION IN THE ACTUAL THING PEOPLE DOWNLOAD.
NO LABEL-BASED ASSUMPTIONS.
NO FAKE COUNTERS.
NO LOCAL-ONLY FIXES.
NO "IT SHOULD WORK."
PROVE THAT IT WORKS.
