# V28 retrofit: change log

The owner's V28 addendum (item 8) asks that the retrofit of the earlier events be auditable. This log has one section per
event: the subroute headings removed, and each effect added (node, effect, weight, why, quoting the text), or "no change
(flavor-only)". Part A and Part B are the two retrofit agents' ranges.

## Part B

Retrofit agent B: the V13, V14, game-exclusive, V17, V18, V20-V24 and V27 events (`data/event_collection/<section>/`). Every event of the range has a section. "Headings removed" lists the subroute headings cut from the event's text (each is a `structural` ledger entry in the file, `why`: "subroute heading removed"). Effects were added only to outcomes the owner already wrote; no outcome branch or weight changed. Skill sizes: small = +5..10. Health: a minor injury or illness = -30..-10 (never kills), a recovery = +10..30 (the V20 series' own size; +10..20 where the event already used it).

### V13 competition add-ons (v13)

#### The Inexplicable Idea (`all_inexplicable_idea`)

- Headings removed (15): "IT WORKS"; "IT SORT OF WORKS"; "THE ABSOLUTE FAILURE"; "THE UNEXPECTED SIDE EFFECT"; "THE GREAT LAUGH"; "THE GENIUS"; "THE NONSENSE"; "THE INSULTED INVENTOR"; "THE BETTER QUESTION"; "THE COUNCIL IS STUMPED"; "THE QUIET COMEBACK"; "THE SPITEFUL MASTERPIECE"; "THE FORTY-SEVEN REVISIONS"; "THE LOST OPPORTUNITY"; "THE FINAL WORD".
- Node `a1`: skill +5..10 (Research) on `inventor` (small). Weight: 1 in 5 of choice "Give the inventor a modest budget and a safe trial." (unchanged; equal weights, the source gives no odds; some outcomes have path conditions). Why: "The idea solves a practical problem with ordinary materials" -- a working invention: a small Research gain (V28 2: invention).
- Node `b1`: skill +5..10 (Research) on `inventor` (small). Weight: 1 in 5 of choice "Ask the inventor to defend the idea before the council." (unchanged; equal weights, the source gives no odds; some outcomes have path conditions). Why: "(Inventor) gives a clear demonstration and anticipates every objection" -- a sound design defended before the council: a small Research gain.
- Node `c1`: skill +5..10 (Research) on `inventor` (small). Weight: 1 in 5 of choice "Reject the proposal and invite a revised version." (unchanged; equal weights, the source gives no odds; some outcomes have path conditions). Why: "returns weeks later with a smaller, more practical design" -- practice and revision: a small Research gain.
- Node `a5`: mood bad on `inventor`. Weight: 1 in 5 of choice "Give the inventor a modest budget and a safe trial." (unchanged; equal weights, the source gives no odds; some outcomes have path conditions). Why: "(Inventor) is devastated to discover that nobody believed (inventor.him/her)" -- a passing bad mood (temporary; the game's own mood).

#### It's Alive! (`all_its_alive`)

- Headings removed (13): "THE COLLAPSE"; "THE NEW CREATOR"; "THE HEARTBREAK"; "THE FRAUD"; "THE ACCUSATION"; "BLASPHEMY AGAINST NATURE"; "BLASPHEMY AGAINST MAGIC"; "THE APOLOGY"; "THE HIDDEN CORDS"; "THE WIND"; "THE UNEXPLAINED"; "THE LITTLE CREATURE"; "THE LESSON".
- Node `c1`: skill +5..10 (Building) on `researcher` (small). Weight: 1 in 5 of choice "Examine the construct before making any claims." (unchanged; equal weights, the source gives no odds). Why: "(researcher) becomes a respected maker of moving sculptures" -- crafting proxy (V28 2): a small Building gain.
- Node `a3`: mood bad on `researcher`. Weight: 1 in 4 of choice "Praise (researcher) for creating something alive." (unchanged; equal weights, the source gives no odds). Why: "(researcher) spends the night rebuilding it, sobbing" -- a passing bad mood.

#### The Crafty Inspector (`all_panel_standards`)

- Headings removed (14): "MASTER STONEWRIGHT (CRITIC)"; "MASTER CARVER (CRITIC)"; "THE STERN SCHOLAR (CRITIC)"; "THE KEEPER OF VERSES (CRITIC)"; "THE HARVEST MASTER (CRITIC)"; "THE ELDER OF RITES (CRITIC)"; "THE EXPERT IS VINDICATED"; "THE EXPERT IS HUMBLED"; "THE CROWD DISAGREES"; "THE BITTER RIVAL"; "THE UNEXPECTED MENTOR"; "THE SHAMEFUL INSULT"; "THE STUNNING MASTERPIECE"; "THE POINTLESS PERFECTION".
- Effects: no change (flavor-only).

#### The Physics-Defying Builder (`all_physics_defying`)

- Headings removed (13): "THE COUNTERWEIGHT"; "THE ROOTS"; "THE MIRAGE"; "THE MIRACLE"; "THE EMBARRASSMENT"; "THE UNSETTLING SUCCESS"; "THE EXPERT WAS WRONG"; "THE PARADE"; "THE STUNT"; "THE COLLAPSE"; "THE EXPLANATION"; "THE NON-EXPLANATION"; "THE IMPOSSIBLE CLAIM".
- Effects: no change (flavor-only).

#### The Strange Statue (`all_strange_statue`)

- Headings removed (11): "THE PEOPLE'S FAVORITE"; "THE SCANDAL"; "THE UNINTENDED INSULT"; "THE UNFORGIVING CRITIC"; "THE CHARM"; "THE NIGHTMARE"; "THE MEMORY"; "THE DIVISION"; "THE RUINED IMPROVEMENT"; "THE DOUBLE STATUE"; "THE ARTIST'S CHOICE".
- Effects: no change (flavor-only).

#### The Verse That Changed History (`all_verse_that_changed`)

- Headings removed (17): "THE NEW SONG"; "THE OFFENSE"; "THE REVELATION"; "THE LEGEND OF THE GOAT"; "THE GRACEFUL RECOVERY"; "THE WORSE APOLOGY"; "THE HUMILIATION"; "THE COMPASSION"; "THE BRILLIANT INTERPRETATION"; "THE DESPERATE EXCUSE"; "THE HEATED DISPUTE"; "THE NEW TRADITION"; "THE SCHOLARLY CRITIQUE"; "THE GREAT DISAGREEMENT"; "THE LOST ORIGINAL"; "THE BITTER SATIRIST"; "THE LEGACY".
- Node `b3`: mood bad on `reciter`. Weight: 1 in 4 of choice "Stop and apologize." (unchanged; equal weights, the source gives no odds; some outcomes have path conditions). Why: "(Reciter) flees the stage in tears." -- a passing bad mood.

### V14 Golden Child scenes (v14)

#### The Impossible Equation (`vv1_v14_01_impossible`)

- Effects: no change (flavor-only).

#### The World's Simplest Explanation (`vv1_v14_02_worlds`)

- Effects: no change (flavor-only).

#### The Little Philosopher (`vv1_v14_03_little`)

- Effects: no change (flavor-only).

#### The Living Map (`vv1_v14_04_living_map`)

- Effects: no change (flavor-only).

#### The Lesson Nobody Expected (`vv1_v14_05_lesson`)

- Effects: no change (flavor-only).

#### The Song of Isola (`vv1_v14_06_song_isola`)

- Effects: no change (flavor-only).

#### The Instrument That Never Existed (`vv1_v14_07_instrument`)

- Effects: no change (flavor-only).

#### The Tiny Conductor (`vv1_v14_08_tiny`)

- Effects: no change (flavor-only).

#### The Rainbow Maker (`vv1_v14_09_rainbow`)

- Effects: no change (flavor-only).

#### The Little Stormcaller (`vv1_v14_10_little`)

- Effects: no change (flavor-only).

#### The Thirsty Garden (`vv1_v14_11_thirsty`)

- Effects: no change (flavor-only).

#### The Berry Bush's Blessing (`vv1_v14_12_berry_bushs`)

- Effects: no change (flavor-only).

#### The Curious Little Explorer (`vv1_v14_13_curious`)

- Effects: no change (flavor-only).

#### The Stars Have Names (`vv1_v14_14_stars_have`)

- Effects: no change (flavor-only).

#### The Little Healer (`vv1_v14_15_little`)

- Effects: no change (flavor-only).

#### The Mediator (`vv1_v14_16_child_who`)

- Effects: no change (flavor-only).

#### The Golden Child's First Debate (`vv1_v14_17_golden`)

- Effects: no change (flavor-only).

#### The Little Architect (`vv1_v14_18_little`)

- Effects: no change (flavor-only).

#### The Golden Child's History Lesson (`vv1_v14_19_golden`)

- Effects: no change (flavor-only).

#### The Question That Changed Everything (`vv1_v14_20_question`)

- Effects: no change (flavor-only).

#### The Little Peacemaker (`vv1_v14_21_little`)

- Effects: no change (flavor-only).

#### The Golden Child's Great Experiment (`vv1_v14_22_golden`)

- Effects: no change (flavor-only).

#### The Little Inventor's Disaster (`vv1_v14_23_little`)

- Effects: no change (flavor-only).

#### The Griever (`vv1_v14_24_boy_who`)

- Effects: no change (flavor-only).

#### The Wise Child (`vv1_v14_25_child_who`)

- Effects: no change (flavor-only).

### Game-exclusive events (exclusive)

#### The Most Difficult Patient (`vv2_hospitals_most_difficult`)

- Node `b1`: health_change +10..+20 on `patient`. Weight: 1 in 3 of choice "Let the villager rest privately while healers remain available." (unchanged; equal weights, the source gives no odds). Why: "The villager recovers and thanks everyone" -- the exhausted patient recovers: the same +10..20 as A1's recovery.

#### The Secret Behind the Waterfall (`vv2_secret_behind_waterfall`)

- Effects: no change (flavor-only).

#### The Great Totem Dispute (`vv2_the_great_totem_dispute`)

- Effects: no change (flavor-only).

#### The Chief's Impossible Question (`vv3_chiefs_impossible_question`)

- Effects: no change (flavor-only).

#### The Child Who Claimed to Be Chief (`vv3_child_who_claimed_to_be`)

- Headings removed (4): "THE TINY TYRANT"; "THE UNEXPECTED REFORMER"; "THE ROYAL FEAST"; "THE PEOPLE'S CHIEF".
- Effects: no change (flavor-only).

#### The Statue That Judged Its Makers (`vv3_statue_that_judged_its`)

- Effects: no change (flavor-only).

#### The City's Two Histories (`vv3_the_citys_two_histories`)

- Effects: no change (flavor-only).

#### The Wacky Weather Dance (`vv3_weather_dance_that_went`)

- Effects: no change (flavor-only).

#### The Mask That Wouldn't Stay Hidden (`vv4_mask_that_wouldnt_stay`)

- Effects: no change (flavor-only).

#### The Dolphins' Strange Gift (`vv4_the_dolphins_strange_gift`)

- Effects: no change (flavor-only).

#### The Great Water Argument (`vv4_the_great_water_argument`)

- Effects: no change (flavor-only).

#### The Unwelcome Landscaper (`vv4_the_unwelcome_landscaper`)

- Effects: no change (flavor-only).

#### The Homesick Convert (`vv5_convert_who_missed_home`)

- Effects: no change (flavor-only).

#### The Feast of Two Traditions (`vv5_feast_of_two_traditions`)

- Effects: no change (flavor-only).

#### The Old Belief and the New Question (`vv5_old_belief_and_new`)

- Effects: no change (flavor-only).

#### The Guardians' Disagreement (`vv5_the_guardians_disagreement`)

- Effects: no change (flavor-only).

### V17 festival contests (v17)

#### A Shelter for the Next Storm (`vv1_v17_building`)

- Effects: no change (flavor-only).

#### The Greatest Little Champion (`vv1_v17_children`)

- Effects: no change (flavor-only).

#### The First Great Feast (`vv1_v17_cooking`)

- Effects: no change (flavor-only).

#### The Seed and Soil Trial (`vv1_v17_farming`)

- Effects: no change (flavor-only).

#### The Stone Table of Questions (`vv1_v17_research`)

- Effects: no change (flavor-only).

#### The Face of the Southern Shore (`vv1_v17_sculpture`)

- Effects: no change (flavor-only).

#### The Words We Brought With Us (`vv1_v17_story`)

- Effects: no change (flavor-only).

#### The Bridge That Should Not Stand (`vv2_v17_building`)

- Effects: no change (flavor-only).

#### The Children's Jury (`vv2_v17_children`)

- Effects: no change (flavor-only).

#### The Great Berry Challenge (`vv2_v17_farming`)

- Effects: no change (flavor-only).

#### The Great Falls Riddle (`vv2_v17_research`)

- Effects: no change (flavor-only).

#### The Totem's Unfortunate Cousin (`vv2_v17_sculpture`)

- Effects: no change (flavor-only).

#### The Founders' Ballad (`vv2_v17_story`)

- Effects: no change (flavor-only).

#### The Statue and the Impossible Arch (`vv3_v17_building`)

- Effects: no change (flavor-only).

#### The Chief for a Moment (`vv3_v17_children`)

- Effects: no change (flavor-only).

#### The Chief's Table (`vv3_v17_cooking`)

- Effects: no change (flavor-only).

#### The Garden of Rival Methods (`vv3_v17_farming`)

- Effects: no change (flavor-only).

#### Magic, Nature and Measurement (`vv3_v17_research`)

- Effects: no change (flavor-only).

#### The Chief's Most Unflattering Likeness (`vv3_v17_sculpture`)

- Effects: no change (flavor-only).

#### The Two Histories (`vv3_v17_story`)

- Effects: no change (flavor-only).

#### The Water's Unlikely Path (`vv4_v17_building`)

- Effects: no change (flavor-only).

#### The Mask-Makers' Parade (`vv4_v17_children`)

- Effects: no change (flavor-only).

#### The Roots and River Feast (`vv4_v17_cooking`)

- Effects: no change (flavor-only).

#### The Waterkeepers' Trial (`vv4_v17_farming`)

- Effects: no change (flavor-only).

#### The Question of the Tree (`vv4_v17_research`)

- Effects: no change (flavor-only).

#### The Ugliest Guardian (`vv4_v17_sculpture`)

- Effects: no change (flavor-only).

#### The Tree Remembers (`vv4_v17_story`)

- Effects: no change (flavor-only).

#### The Bridge Between Neighbors (`vv5_v17_building`)

- Effects: no change (flavor-only).

#### The Children's Peace, the Adults' Quarrel (`vv5_v17_children`)

- Effects: no change (flavor-only).

#### The Questionable Feast (`vv5_v17_cooking`)

- Effects: no change (flavor-only).

#### The Harvest and the Border (`vv5_v17_farming`)

- Effects: no change (flavor-only).

#### Who Owns a Discovery? (`vv5_v17_research`)

- Effects: no change (flavor-only).

#### The Two Faces of Isola (`vv5_v17_sculpture`)

- Effects: no change (flavor-only).

#### Who Gets to Tell Isola's History? (`vv5_v17_story`)

- Effects: no change (flavor-only).

### V18 trials (v18)

#### The Warriors' Duel (`all_v18_01_warriors`)

- Node `a3`: health_change -30..-10 on `struck`. Weight: 1 in 7 of choice "Permit a supervised contest." (unchanged; equal weights, the source gives no odds; some outcomes have path conditions). Why: "A contestant loses control and strikes too hard. The judges stop the tournament; the offender must apologize and help the healer." -- the struck contestant is hurt (the healer stood ready): a minor injury, cast as a villager.
- Role: `struck` (a villager, 14+) is cast for A3's injured contestant; no text names them.

#### The Martial Arts Tournament (`all_v18_02_martial`)

- Effects: no change (flavor-only).

#### The Great Question (`all_v18_03_question`)

- Effects: no change (flavor-only).

#### The Philosophers' Duel (`all_v18_04_duel`)

- Effects: no change (flavor-only).

#### The Alchemists' Trial (`all_v18_05_alchemists`)

- Effects: no change (flavor-only).

#### The Paradox Challenge (`all_v18_06_paradox`)

- Effects: no change (flavor-only).

#### The Sixteenth Aria (`all_v18_07_sixteenth`)

- Effects: no change (flavor-only).

#### The Poets' Tournament (`all_v18_08_poets`)

- Effects: no change (flavor-only).

#### The Great Trivia Trial (`all_v18_09_trivia`)

- Effects: no change (flavor-only).

#### The Ball Tournament (`all_v18_10_ball`)

- Effects: no change (flavor-only).

#### The Stick Game (`all_v18_11_stick_game`)

- Effects: no change (flavor-only).

#### The Hoop Tournament (`all_v18_12_hoop`)

- Effects: no change (flavor-only).

#### The Isolan Decathlon (`all_v18_decathlon`)

- Effects: no change (flavor-only).

### V20 crises and relics (v20)

#### Between Life and Death (`all_v20_between_life`)

- Headings removed (30): "A Life Forever Changed"; "One Last Conversation"; "The Unanswered Question"; "The Forest's Mercy"; "Rooted Between Worlds"; "The Price of Renewal"; "Nature Reclaims Its Own"; "The Impossible Revival"; "The Sleeping Miracle"; "The Broken Spell"; "The Price of Power"; "The Ancestors Answer"; "A Final Blessing"; "The Long Vigil"; "Silence from Beyond"; "The Apprentice's Miracle"; "Saved, But Not Unscathed"; "A Narrow Escape"; "The Cost of Desperation"; "The Unnatural Survivor"; "The Walking Dead"; "The Miracle They Condemned"; "The Forbidden Failure"; "The Patient Who Remembered Death"; "Against All Odds"; "The Long Road Back"; "The Living Sleeper"; "The Last Words"; "The Uncertain Victory"; "The Physician's Triumph".
- Effects: no change (flavor-only).

#### The Child Who Corrected the Masters (`all_v20_d10_child`)

- Effects: no change (flavor-only).

#### The Ancient Oath (`all_v20_d11_ancient`)

- Node `a1`: health_change +10..+30 on `patient`. Weight: 1 in 3 of choice "Honor it" (unchanged; equal weights, the source gives no odds). Why: "Another cure works." -- the patient recovers: the series' recovery (+10..30).

#### The Doctor Who Could Not Save Everyone (`all_v20_d12_cannot`)

- Node `c2`: health_change -30..-10 on `patient`. Weight: 1 in 3 of choice "Let healers choose independently" (unchanged; equal weights, the source gives no odds). Why: "They conflict dangerously." -- the danger reaches the critical patient: a minor health loss (as B2).

#### Two Lives, One Decision (`all_v20_d1_two_lives`)

- Node `a2`: baby_lost on `mother`. Weight: 1 in 5 of choice "Attempt the dangerous intervention." (unchanged; equal weights, the source gives no odds). Why: "The mother survives but the child dies" -- the unborn child is lost; the mother lives.
- Node `a4`: kill `mother` (cause: Unknown causes). Weight: 1 in 5 of choice "Attempt the dangerous intervention." (unchanged; equal weights, the source gives no odds). Why: "Neither survives" -- the mother dies, and the unborn child with her.
- Node `a5`: health_change -30..-10 on `mother`. Weight: 1 in 5 of choice "Attempt the dangerous intervention." (unchanged; equal weights, the source gives no odds). Why: "the mother requires prolonged care" -- a minor health loss.
- Node `b2`: baby_lost on `mother`. Weight: 1 in 4 of choice "Choose the gentler treatment." (unchanged; equal weights, the source gives no odds). Why: "The mother survives but loses the baby" -- the unborn child is lost; the mother lives.
- Node `b3`: health_change -30..-10 on `mother`. Weight: 1 in 4 of choice "Choose the gentler treatment." (unchanged; equal weights, the source gives no odds). Why: "The condition worsens" -- a minor health loss.
- Node `b4`: kill `mother` (cause: Unknown causes). Weight: 1 in 4 of choice "Choose the gentler treatment." (unchanged; equal weights, the source gives no odds). Why: "Both die" -- the mother dies, and the unborn child with her.
- Node `c2`: health_change -30..-10 on `mother`. Weight: 1 in 3 of choice "Explain the risks and ask the mother." (unchanged; equal weights, the source gives no odds). Why: "her recovery is prolonged and uncertain" -- a minor health loss.
- Role: the pregnant villager is now cast as `mother` (female, special nursing_parent, protected allow); before, decision Q11 kept her an uncast stranger. A3 ("The child survives but the mother dies") stays told only: the games keep the unborn baby as the mother's own state, so her death would end it too. Listed in retrofit-harm-review.md.

#### The Treatment That Does Not Exist (`all_v20_d2_no_such`)

- Node `a1`: health_change +10..+30 on `patient`. Weight: 1 in 4 of choice "Attempt the proposed technique." (unchanged; equal weights, the source gives no odds). Why: "It works" -- the patient is cured: the series' recovery (+10..30).

#### The Experimental Cure (`all_v20_d3_cure`)

- Effects: no change (flavor-only).

#### The Half-Translated Remedy (`all_v20_d4_half`)

- Node `a2`: health_change -30..-10 on `patient`. Weight: 1 in 4 of choice "Reconstruct and attempt the remedy." (unchanged; equal weights, the source gives no odds). Why: "The missing words warned against a dangerous plant." -- the reconstructed remedy was tried (choice A) and the plant was dangerous: a minor illness.

#### The Last Dose (`all_v20_d5_last_dose`)

- Effects: no change (flavor-only).

#### The Physician Who Refused (`all_v20_d6_physician`)

- Node `c2`: health_change -30..-10 on `patient`. Weight: 1 in 3 of choice "Convene the healers" (unchanged; equal weights, the source gives no odds). Why: "They argue too long." -- the delay costs the waiting patient: a minor health loss (as D5's 'too late').

#### The Patient Who Knew Too Much (`all_v20_d7_patient`)

- Effects: no change (flavor-only).

#### The Medicine That Works Too Well (`all_v20_d8_works_too`)

- Effects: no change (flavor-only).

#### The Healer's Secret (`all_v20_d9_healers`)

- Effects: no change (flavor-only).

#### The Thing That Should Not Exist (`all_v20_r1_should_not`)

- Headings removed (22): "The Shattered Mystery"; "The Thing That Would Not Break"; "The Destruction That Saved Them"; "The Accidental Discovery"; "The Impossible Tool"; "The Voice from Nowhere"; "The Hero of the Village"; "The Catastrophic Misunderstanding"; "The Scholar's Triumph"; "The Great Scholarly Embarrassment"; "The Forbidden Question"; "The Accused Discoverer"; "Forgotten Beneath the Earth"; "The Second Discoverer"; "The Accusation"; "The Relic That Returned"; "Reluctant Hero"; "Disgraced Scholar"; "False Prophet"; "Inventor's Curse"; "Secret Society"; "The Great Panic".
- Node `a4`: skill +5..10 (Research) on `finder` (small). Weight: 1 in 4 of choice "DESTROY IT" (unchanged; equal weights, the source gives no odds). Why: "(Finder) is suddenly praised as an inventor" -- an invention from the relic: a small Research gain.
- Node `b1`: skill +5..10 (Research) on `finder` (small). Weight: 1 in 4 of choice "TRY TO USE IT" (unchanged; equal weights, the source gives no odds). Why: "(Finder) discovers a practical function" -- a discovery by hands-on study: a small Research gain.

#### The Trial of the Impossible Relic (`all_v20_r2_relic_trial`)

- Headings removed (14): "Innocent"; "The Hidden Visitor"; "The False Confession"; "The Unexpected Spy"; "The Wrongful Prisoner"; "The Prisoner's Discovery"; "The Village Divided"; "The Escape"; "The Vindicated Explorer"; "The Unanswered Suspicion"; "The Courageous Elder"; "The Genuine Conspiracy"; "Political Prisoner"; "First Contact".
- Effects: no change (flavor-only).

#### Has Isola Been Discovered? (`all_v20_r3_isola`)

- Headings removed (3): "Secret Society"; "The Great Panic"; "First Contact".
- Effects: no change (flavor-only).

#### The Relic That Outlived Its Discoverer (`all_v20_r4_relic`)

- Headings removed (9): "The Forgotten Genius"; "Justice Across Generations"; "The Legendary Artifact"; "The Great Deception"; "The Discovery That Changed Everything"; "The Curse That Wasn't"; "The Curse That Was"; "The Last Witness"; "Political Prisoner".
- Effects: no change (flavor-only).

### V21 craft events (v21)

#### The Great Potters' Trial (`all_v21_c1_potters`)

- Headings removed (19): "The Perfect Water Jar"; "A Beautiful Sieve"; "The Great Collapse"; "The Unbreakable Bowl"; "The Vessel with Two Mouths"; "The Ancestors' Faces"; "The Ugliest Masterpiece"; "The Painted Catastrophe"; "The Stolen Pattern"; "The Speaking Pot"; "The Merciless Critic"; "The Critic Is Wrong"; "The Apprentice's Triumph"; "The Judge's Favorite"; "The Disgraced Judge Returns"; "The Forgotten Potter"; "The Artisan's Apprentice"; "The Great Design Feud"; "The Impossible Vessel".
- Node `c1`: skill +5..10 (Building) on `potter` (small). Weight: 1 in 4 of choice "ASK THE MASTER POTTER TO JUDGE AND TEACH." (unchanged; equal weights, the source gives no odds). Why: "(Potter) nearly cries, then spends days improving the work" -- practice after critique; Building is the crafting proxy (V28 2).

#### The Statue That Divided the Village (`all_v21_c2_divided`)

- Headings removed (15): "Beloved Monstrosity"; "The Unflattering Portrait"; "The Masterwork"; "The Terrible Omen"; "The Impossible Balance"; "Many Hands"; "The Artistic War"; "The Unexpected Genius"; "The Ruined Treasure"; "The Secret Favorite"; "The False Miracle"; "The Real Mystery"; "Forgotten Art"; "The Ugly Statue Becomes a Legend"; "The Artisan's Apprentice".
- Effects: no change (flavor-only).

#### The Great Isolan Crafts Fair (`all_v21_c3_crafts_fair`)

- Headings removed (18): "The Judge Who Feared No Craft"; "The Great Upset"; "The Perfectly Useless Wonder"; "The Rigged Prize"; "The Shared Victory"; "A Village of Artisans"; "The Great Barter Disaster"; "The Invention Exchange"; "The Lost Heirloom"; "The Children's Fair"; "The Night of a Hundred Lamps"; "The Uninvited Storm"; "The Mask That Chose Its Owner"; "The Feast of Reconciliation"; "The Fair Nobody Could End"; "The Disgraced Judge Returns"; "The Artisan's Apprentice"; "The Festival of Two Communities".
- Node `c5`: food loss small (scaled). Weight: 1 in 5 of choice "MAKE THE FAIR A CEREMONIAL FESTIVAL." (unchanged; equal weights, the source gives no odds). Why: "The celebrations run so long that farming and building are neglected." -- neglected farming: a small food loss.

### V22 contests (v22)

#### The Great Isolan Drawing Competition (`all_v22_1_drawing`)

- Headings removed (18): "The Island in a Single Picture"; "The Rain's Contribution"; "The Accidental Map"; "The Wrong Island"; "A Living Likeness"; "The Nose Controversy"; "The Accidental Insult"; "The Unexpected Friendship"; "The Visionary"; "The Unidentifiable Thing"; "The Picture That Changed"; "The Storyteller"; "A New Pigment"; "The Beautiful Disaster"; "The Pattern of Light"; "The Great Copying Scandal"; "The Artist's Apprentice"; "The Shared Prize".
- Effects: no change (flavor-only).

#### A Test of Strength (`all_v22_2_strength`)

- Headings removed (22): "The Walking Coconut Mountain"; "The Clever Basket"; "The Great Coconut Avalanche"; "The Patient Champion"; "Steady as Stone"; "The Unfortunate Splash"; "The Surprise Winner"; "A Sensible Withdrawal"; "The Strongest on the Shore"; "The Leverage Lesson"; "Stuck in the Sand"; "The Overconfident Champion"; "A Perfect Partnership"; "The Talking Passenger"; "The Sudden Switch"; "Teamwork Over Glory"; "The All-Around Champion"; "Too Fast, Too Soon"; "The Unlikely Victory"; "The Disputed Finish"; "The Champion Who Learned Humility"; "The Shared Prize".
- Effects: no change (flavor-only).

#### The Great Isolan Potion-Making Trial (`all_v22_3_potion`)

- Headings removed (22): "The Careful Healer"; "The Promising Discovery"; "The Beautiful Failure"; "The Misidentified Leaf"; "Strength of the Spirit"; "The Boastful Brew"; "The Potion That Worked Too Well"; "The Impossible Result"; "Exactly as Requested"; "Almost Right"; "The Endless Bubbles"; "The Unexpected Utility"; "The Thoughtful Researcher"; "The Cautious Scholar"; "The Great Mislabeling"; "The Rival's Sabotage"; "A New Principle"; "The Potion of Hiccups"; "The Temporary Transformation"; "The Council Intervenes"; "The Potion That Became Tradition"; "The Shared Prize".
- Node `a4`: skill +5..10 (Healing) on `brewer` (small). Weight: 1 in 4 of choice "THE MOST EFFECTIVE HEALING PREPARATION" (unchanged; equal weights, the source gives no odds). Why: "the healer gains a lesson in careful identification" -- a lesson from a caught mistake: a small Healing gain (V28 2: a failed attempt gives at most a small gain).

#### The Parent's Lesson (`all_v22_4_parents`)

- Headings removed (30): "Truth with Kindness"; "The Painfully Honest Critic"; "The Gentle Correction"; "The Little Investigator"; "The Patient Gardener"; "The Waiting Game"; "Patience and Action"; "The Impatient Teacher"; "The Reliable Helper"; "The Coconut Inspector"; "A Job Well Shared"; "The Helpful Troublemaker"; "The Quiet Kindness"; "Sharing Everything"; "The Thoughtful Gift"; "The Self-Appointed Kindness Officer"; "The Careful Explorer"; "The Leaf Collector"; "The Well-Meant Mistake"; "The Little Guardian"; "The Second Attempt"; "Never Give Up Asking"; "The Boastful Apprentice"; "The Teacher Learns"; "A Wise Pause"; "The Endless Thinker"; "The Prank That Became a Gift"; "The New Troublemaker"; "The Child Who Remembered"; "The Trouble That Became Talent".
- Effects: no change (flavor-only).

### V23 pranks and mysteries (v23)

#### The Practical Joke (`all_v23_1_practical`)

- Headings removed (12): "The Perfect Prank"; "The Wrong Audience"; "The Prankster Pranked"; "The Great Misunderstanding"; "The Vanishing Villager"; "The Haunted Hut"; "The Accidental Discovery"; "The Village Panic"; "The Great Conspiracy"; "The Betrayal"; "The Prank War"; "The Apology".
- Effects: no change (flavor-only).

#### The Ill-Timed Sneeze (`all_v23_2_ill_timed`)

- Headings removed (7): "The Ceremonial Disaster"; "The Ruined Feast"; "The Starch Cloud"; "The Interrupted Announcement"; "The Chain Reaction"; "The Omen"; "The Lucky Interruption".
- Effects: no change (flavor-only).

#### The Strange Coincidence (`all_v23_3_strange`)

- Headings removed (11): "Nothing Unusual"; "The Skeptic's Embarrassment"; "The Child's Explanation"; "The Hidden Prankster"; "The Natural Explanation"; "The Unanswered Mystery"; "The Unexpected Discovery"; "False Alarm"; "Lucky Warning"; "The Great Panic"; "The Prophecy Fulfilled".
- Effects: no change (flavor-only).

#### The Missing Coconuts (`all_v23_4_missing`)

- Effects: no change (flavor-only).

#### The False Alarm (`all_v23_5_false_alarm`)

- Effects: no change (flavor-only).

#### The Prank War (`all_v23_6_prank_war`)

- Effects: no change (flavor-only).

### V24 The Revolutionary Invention (v24)

#### The Revolutionary Invention (`all_v24_revolutionary`)

- Headings removed (40): "THE SENSATION"; "THE LAUGHINGSTOCK"; "THE SHRUG"; "THE HERO"; "THE OUTRAGE"; "THE NEW FAD"; "THE MASTER SCHOLAR"; "THE UNEXPECTED FLAW"; "THE SCHOLARLY FEUD"; "THE IMPOSSIBLE RESULT"; "THE FALSE DISCOVERY"; "THE ACCIDENTAL ADVANCE"; "THE PERFECTED DESIGN"; "THE SHATTERING"; "THE EXPLOSION"; "THE DISAPPEARANCE"; "THE DISINTEGRATION"; "THE SECOND MIRACLE"; "THE SMALL IMPROVEMENT"; "THE HIDDEN GENIUS"; "THE STOLEN CREDIT"; "THE TRUSTED APPRENTICE"; "THE LOST IDEA"; "THE RELUCTANT CELEBRITY"; "THE DANGEROUS RUMOR"; "OFFICIAL ADOPTION"; "THE PROHIBITION"; "THE LONG DEBATE"; "THE PUBLIC TEST"; "THE COMPROMISE"; "EVERYONE ADOPTS IT"; "EVERYONE SHUNS IT"; "THE INVENTOR IS CALLED MAD"; "COMPLETE INDIFFERENCE"; "HERO'S WELCOME"; "CHIEF SCHOLAR"; "IMITATION CRAZE"; "ACCUSATION OF TRICKERY"; "RIVALRY"; "GENERATIONAL LEGACY".
- Node `b5`: skill +5..10 (Research) on `inventor` (small). Weight: 1 in 6 of choice "SUBMIT IT TO THE RESEARCHERS" (unchanged; equal weights, the source gives no odds). Why: "(Inventor) is disappointed but gains knowledge from the attempt" -- knowledge from a careful failed experiment: a small Research gain.

### Shared pools (V17 political codas)

- Headings removed from `shared_pools.json` (the V17 P1-P10 codas the V5 contests append): "THE INSULT" (v17_p1); "THE ACCUSATION" (v17_p2); "THE SECRET ALLIANCE" (v17_p3); "THE SYMBOL" (v17_p4); "THE UNEXPECTED VOTE" (v17_p5); "THE BOYCOTT" (v17_p6); "THE SHARED VICTORY" (v17_p7); "THE DEFEAT WITH DIGNITY" (v17_p8); "THE TROPHY DISPUTE" (v17_p9); "THE UNWANTED HERO" (v17_p10). A shared item is matched inside its source lines, so the cut needs no ledger entry.

### V27 events (v27)

The 57 V27 events were authored under the V28 rules (`scripts/collection_v27.py`, the authoring record). Checked against them: casting by age and random sex, harmless/minor outcomes at normal weight, serious injury and disappearance rare, the one death (014's fall, 054's fever, 055's dive) rare, missing = `vanish` with no grave (010, 013, 024, 025, 055, 056). No V27 text says a villager died with no body recovered, so no outcome switches to `die_unrecovered`. No baby event endangers the baby (002's "careless tug", 004's "frightening search"), so no `baby_lost`. No V27 text has a subroute heading (SETUP/OUTCOME labels are structural markers already).

- The Unsolvable Cry (`all_v27_01_cry`): confirmed, no change.
- The Little Grip (`all_v27_02_little_grip`): confirmed, no change.
- The First Recognition (`all_v27_03_recognition`): confirmed, no change.
- The Crawling Expedition (`all_v27_04_crawling`): confirmed, no change.
- The Borrowed Lullaby (`all_v27_05_lullaby`): confirmed, no change.
- The Forbidden Grove (`all_v27_06_grove`): confirmed, no change.
- The Friend's Secret (`all_v27_07_secret`): confirmed, no change.
- The Cruel Joke (`all_v27_08_cruel_joke`): confirmed, no change.
- The River Kingdom (`all_v27_09_kingdom`): confirmed, no change.
- The Missing Child at Supper (`all_v27_10_supper`): confirmed, no change.
- The Hero of the Legend (`all_v27_11_legend`): confirmed, no change.
- The New Friend (`all_v27_12_new_friend`): confirmed, no change.
- The Midnight Raft (`all_v27_13_raft`): confirmed, no change.
- The Dangerous Proof (`all_v27_14_proof`): confirmed, no change.
- The Public Embarrassment (`all_v27_15_embarrass`): confirmed, no change.
- The Apprenticeship Swap (`all_v27_16_swap`): confirmed, no change.
- The Reckless Pact (`all_v27_17_pact`): confirmed, no change.
- The First Heartbreak (`all_v27_18_heartbreak`): confirmed, no change.
- The Faulty Beam (`all_v27_19_beam`): confirmed, no change.
- The Unasked Favor (`all_v27_20_favor`): confirmed, no change.
- The Loud Councilor (`all_v27_21_councilor`): confirmed, no change.
- The Secret Doubt (`all_v27_22_doubt`): confirmed, no change.
- The Night Watcher (`all_v27_23_watcher`): confirmed, no change.
- The Vanishing Explorer (`all_v27_24_explorer`): confirmed, no change.
- The Last Crossing (`all_v27_25_crossing`): confirmed, no change.
- The Stubborn Teacher (`all_v27_26_teacher`): confirmed, no change.
- The Empty Chair (`all_v27_27_empty_chair`): confirmed, no change.
- The New Beginning (`all_v27_28_beginning`): confirmed, no change.
- The Forgotten Route (`all_v27_29_route`): confirmed, no change.
- The Creature in the Basket (`all_v27_30_basket`): confirmed, no change.
- The Fierce Little Guardian (`all_v27_31_guardian`): confirmed, no change.
- The Fish That Followed (`all_v27_32_fish`): confirmed, no change.
- The Unusual Insect (`all_v27_33_insect`): confirmed, no change.
- The Unwelcome Pet (`all_v27_34_pet`): confirmed, no change.
- The Pet's Last Morning (`all_v27_35_pets_last`): confirmed, no change.
- The Strange Hatchling (`all_v27_36_hatchling`): confirmed, no change.
- The Animal That Returned (`all_v27_37_returned`): confirmed, no change.
- The Parents' Rough Patch (`all_v27_38_rough_patch`): kinship added: role `parent2` spouse_of parent1 (cie-v6-binary.md 21). Why: "Two parents disagree over chores, fatigue and how to raise their children" names the family tie; the event is now cast only where the village has it.
- The Quiet Marriage (`all_v27_39_marriage`): kinship added: role `partner2` spouse_of partner1 (cie-v6-binary.md 21). Why: "Longtime partners" names the family tie; the event is now cast only where the village has it.
- The Sibling Rivalry (`all_v27_40_siblings`): kinship added: role `sibling2` sibling_of sibling1 (cie-v6-binary.md 21). Why: "Two siblings" names the family tie; the event is now cast only where the village has it.
- The Childhood Promise (`all_v27_41_promise`): confirmed, no change.
- The Special Friend (`all_v27_42_special`): confirmed, no change.
- The Lovers' Argument (`all_v27_43_lovers`): confirmed, no change.
- The Awkward Courtship (`all_v27_44_courtship`): confirmed, no change.
- The Rival Coworkers (`all_v27_45_coworkers`): confirmed, no change.
- The Ally Who Disagreed (`all_v27_46_ally`): confirmed, no change.
- The Neighbor's Grief (`all_v27_47_grief`): confirmed, no change.
- The Unlikely Mentor (`all_v27_48_mentor`): confirmed, no change.
- The Chosen Family (`all_v27_49_chosen`): confirmed, no change.
- The Reunion That Hurt (`all_v27_50_reunion`): confirmed, no change.
- The Caregiver's Apology (`all_v27_51_apology`): kinship added: role `parent` parent_of child (cie-v6-binary.md 21). Why: "A parent realizes they unfairly blamed a child" names the family tie; the event is now cast only where the village has it.
- The Friendship Nobody Expected (`all_v27_52_unexpected`): confirmed, no change.
- The Unmarked Shore (`all_v27_53_shore`): confirmed, no change.
- The Fever After the Expedition (`all_v27_54_fever`): confirmed, no change.
- The Legend of the Deep Pool (`all_v27_55_deep_pool`): confirmed, no change.
- The Boat That Came Back Empty (`all_v27_56_empty_boat`): confirmed, no change.
- The Forbidden Bell (`all_v27_57_bell`): confirmed, no change.
