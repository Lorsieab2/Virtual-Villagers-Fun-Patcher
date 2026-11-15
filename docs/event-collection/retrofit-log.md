# V28 retrofit: change log (auditable, V28 item 8)

The owner's V28 addendum (`docs/more-island-events/Isola_Grand_Event_Collection_V28_Consequences_Claude_Retrofit.txt`,
L10949-11125) asks for every earlier event to be reviewed and given plausible consequences where its story clearly
supports them; many ordinary events stay flavor-only. The owner's text is never changed. Effects attach only to
outcomes the text already has; no new outcome branch is added. Each section below names the event (its file, its
title and its source lines) and either says "no change (flavor-only)" with the reason, or lists each added effect:
the node, the effect, its weight (the chance of the node it sits on is unchanged unless stated), and why, quoting the
text. Removed in-text subroute headings are listed as structural changes (the owner, 2026-11-14: "events should have
a single event title. no need for subroute headings").

Sizes follow the collection's tables: a small skill gain is 5..10; an injury is `health_change` minor -30..-10 or
serious -60..-40 (it never kills).

## Part A

Range: `original/` (The Cooking Contest, The Child of Legend, The Meaning of "Faith"), `universal/`, `v6/`,
`vv5_isolan/`, `v8/`, `v9/`, `v10/`, `v11/` -- 51 events. Changed: 6 events. Added: 8 skill effects (all small gains),
1 `health_change` (serious injury). Removed: 27 subroute headings (all in The Cooking Contest). No death,
disappearance, lost baby, appearance change or kinship role was added in this range: none of these stories sets up a
credible risk the text does not already resolve ("Nobody is hurt", "before anyone is seriously hurt"), and the one
event with a real medical risk (The Doctors' Dilemma) already has its death outcome. No role in Part A uses
`protected: "allow"`.

### original/vv2_cooking_contest -- The Cooking Contest (L100-626 and its add-ons)

Structural: 27 in-text subroute headings removed. Each heading stands on its own source line; the line is now a
`structural` ledger entry and the node's text starts with the story paragraph after it.

| Node | Heading removed (source line) |
|---|---|
| a1_r1 | ROUND ONE -- THE IMPOSSIBLE INGREDIENT: (L701) |
| a1_r2 | ROUND TWO -- THE DISASTER ROUND: (L704) |
| a1_r3 | FINAL ROUND -- THEIR MAGNUM OPUS: (L707) |
| a2_r1 | ROUND ONE -- THE TEST OF SKILL (L1037); its text_only note on the heading's word "skill" went with it |
| a2_r2 | ROUND TWO -- THE TEST OF IMPROVISATION (L1047) |
| a2_r3 | ROUND THREE -- THE FINAL PLATE (L1058) |
| v13a_a1 | A1 -- THE THUNDERCLAP: (L6895) |
| v13a_a2 | A2 -- THE PERFECT DISH: (L6903) |
| v13a_a3 | A3 -- THE DISASTER THAT EVACUATED THE VILLAGE: (L6910) |
| v13a_a4 | A4 -- THE REVOLTING MASTERPIECE: (L6922) |
| v13a_a5 | A5 -- THE JUDGE IS WRONG: (L6930) |
| v13a_a6 | A6 -- THE FURIOUS APPRENTICE: (L6937) |
| v13a_b1 | B1 -- THE LESSON: (L6944) |
| v13a_b2 | B2 -- THE KINDNESS BENEATH THE RAGE: (L6950) |
| v13a_b3 | B3 -- THE USELESS LESSON: (L6956) |
| v13a_b4 | B4 -- THE TEACHER IS TESTED: (L6961) |
| v13a_b5 | B5 -- THE OLD RECIPE: (L6966) |
| v13a_c1 | C1 -- THE CHALLENGE: (L6971) |
| v13a_c2 | C2 -- THE OUTBURST: (L6977) |
| v13a_c3 | C3 -- THE BRIBE: (L6982) |
| v13a_c4 | C4 -- THE BET: (L6988) |
| v13a_c5 | C5 -- THE CRITIC'S CRITIC: (L6994) |
| v13a_d1 | D1 -- THE SURPRISE: (L7000) |
| v13a_d2 | D2 -- THE FAVORITE LOSES: (L7004) |
| v13a_d3 | D3 -- THE DRAW: (L7009) |
| v13a_d4 | D4 -- THE FATAL FLAW IN THE PLAN: (L7013) |
| v13a_d5 | D5 -- THE GREAT CRITIC'S HUMILIATION: (L7018) |

Effects added:

| Node | Effect | Weight | Why |
|---|---|---|---|
| v13a_b1 | skill Farming +5..10 on cook1; the same on cook2 (VV2's cooking skill, as the contest's own rewards) | unchanged (1 of 5 equal outcomes of "constructive instruction") | "(Judge) has the cooks prepare a simple broth ... Both improve, and the competition resumes." (L6945-6948): a lesson both cooks learn from |
| v13a_a6 | skill Farming +5..10 on cook1 | unchanged (1 of 6 equal outcomes) | "(Judge) ... prepares a modest dish from the remaining ingredients, explaining every step." (L6939-6940): cook1 watches a master explain every step |

Everything else stays as it was: the judges, saboteurs and spectators are strangers, so their food poisoning
("all-out food poisoning", L428) stays text; "Nobody is harmed" (L6918) after the Great Stench.

### original/vv1_child_of_legend -- The Child of Legend (L728-791)

No change (flavor-only). A gentle classroom scene with the Golden Child; the lesson is told and the conjured toys and
snacks already give their tech and food.

### original/vv5_meaning_of_faith -- The Meaning of "Faith" (L795-862)

| Node | Effect | Weight | Why |
|---|---|---|---|
| g2 | skill Research +5..10 on child | unchanged (1 of 6 equal grades) | "(he/she) gets full marks and an Astounding Student award." (L826): learning that earned full marks. The lower grades get nothing: "a failed lesson normally gives no gain" (V28 2), never a loss |

### universal/all_beautification -- The Great Beautification Project (L1331-1472)

No change (flavor-only). The fallen nose hurts nobody ("comes to rest in front of the Chief. Nobody says a word.");
the building work already gives its Building and tech.

### universal/all_doctors_dilemma -- The Doctors' Dilemma (L1474-1659)

| Node | Effect | Weight | Why |
|---|---|---|---|
| disability | health_change -60..-40 on patient (serious injury or illness; never kills) | unchanged (1 of the 3 existing outcomes: recovery, lasting effects, death) | "(Patient name) survives, but the illness or injury has lasting effects." (L1609-1610). The lasting disability itself stays text only (rule 9); the health loss is the illness's mark on the survivor |

The death outcome (kill, "Unknown causes", body recovered, so a grave) was already there. The patient role stays
`protected: "auto"`: nursing parents, the Golden Child and the VV3 Chief are never cast as the patient.

### universal/all_everybodys_winner -- Everybody's a Winner? (L1661-1822)

No change (flavor-only). A children's prize-giving; disappointment and arguments are told, and the ending already
gives Research or tech.

### universal/all_scholasticon -- The Grand Isolan Decathlon (L1156-1329)

No change (flavor-only). The collapsing model is a model ("before anyone touches it"); the contest already gives its
Research and tech.

### universal/all_storytelling -- The Great Isolan Storytelling Contest (L1824-2059)

No change (flavor-only). An embarrassing recitation is a joke, not a trauma ("The mistake becomes a harmless joke");
the endings already give Devotion or Research.

### v6/vv1_elders_favorite -- The Elder's Favorite Stone (L2824-2863)

No change (flavor-only). The source asks for no reward ("no skill or item reward", L2863).

### v6/vv1_unexpected -- The Unexpected Question (L2735-2822)

No change (flavor-only). A classroom question; the learning ending already gives Research.

### v6/vv2_hut_sharing_negotiation -- The Hut-Sharing Negotiation (L2920-2994)

| Node | Effect | Weight | Why |
|---|---|---|---|
| m3 | skill Building +5..10 on apprentice | unchanged (1 of 4 equal outcomes of "build or repair more space") | "The apprentices volunteer to build extra storage for their tools." (L2966): hands-on building |
| m4 | skill Building +5..10 on builder | unchanged (1 of 4 equal outcomes) | "A new doorway is installed backward. The builders fix it before anyone moves in." (L2968-2969): repairing a hut is Building (V28 2) |

### v6/vv2_veterinary_visitor -- The Veterinary Visitor (L2865-2918)

No change (flavor-only). "The animal is not injured"; the children's wish for a pet is told, and the healer's thanks
already give Healing.

### v6/vv3_chiefs_monumental_speech -- The Chief's Monumental Speech (L2996-3041)

No change (flavor-only). The source asks for no effect (L3041); the Chief is only embarrassed.

### v6/vv3_gardening_contest -- The Gardening Contest (L3043-3096)

No change (flavor-only). The shared garden already gives Farming.

### v6/vv4_breadfruit_breakdown -- The Breadfruit Breakdown (L3098-3172)

No change (flavor-only). The ending already gives food and Farming to both cooks; "One cook learns a technique from
the other" is covered by that gain (no second award).

### v6/vv4_lullaby -- The Lullaby (L3174-3235)

No change (flavor-only). The source says: "The nursing parent and infant remain protected and unassigned; this is a
social vignette, not a job or danger event."

### v6/vv5_keeper_of_little_things -- The Keeper of Little Things (L3293-3354)

No change (flavor-only). Memories and keepsakes; the ending already gives Research or Devotion.

### v6/vv5_multicultural_festival -- The Multicultural Festival (L3356-3494)

No change (flavor-only). "Nobody is hurt" when the decorations collapse; the ending already gives skills and food or
tech.

### vv5_isolan/vv5_field_day -- The Field Day (L2569-2645)

No change (flavor-only). Friendly games; the ending already gives a small skill.

### vv5_isolan/vv5_great_laundry_mishap -- The Great Laundry Mishap (L2489-2567)

No change (flavor-only). The fashion show tries a garment on and takes it off again: no lasting look to change.

### vv5_isolan/vv5_great_woodworking -- The Great Woodworking Competition (L2101-2396)

No change (flavor-only). "Nobody is injured" when an entry collapses (L2271-2273); the contest already gives Building
and tech.

### vv5_isolan/vv5_potluck_dispute -- The Potluck Dispute (L2398-2487)

No change (flavor-only). The child's dance is joined by "half the village", which no game effect can express (a
celebration is everyone or named villagers); the ending already gives food and a skill.

### v8/vv1_last_song_before -- The Last Song Before Sunset (L3761-3804)

| Node | Effect | Weight | Why |
|---|---|---|---|
| dev4 | skill Parenting +5..10 on parent (the nursing parent the event already casts; a gain is harmless, so no `allow`) | unchanged (1 of 6 equal developments) | "The baby wakes and begins crying. The parent hums the melody, and the baby gradually settles." (L3787-3788): caregiving is Parenting (V28 2) |

### v8/vv1_masters_small -- The Master's Small Apprentice (L3687-3759)

No change (flavor-only). The glued fingers and the collapsing bench are jokes ("Nobody is injured"); the ending already
gives Building.

### v8/vv2_packed_hospital -- The Packed Hospital (L3806-3894)

No change (flavor-only). "Nobody is in immediate danger"; the ending already gives Healing (and tech).

### v8/vv2_timid_child -- The Timid Child (L3896-3948)

| Node | Effect | Weight | Why |
|---|---|---|---|
| ending | skill Parenting +5..10 on adult (the caregiver) | unchanged (every run ends here) | "When a caregiver, (Adult), asks what is wrong ... (Adult) sits beside the child / keeps a respectful distance / offers a cup of water" (L3901-3903, L3913-3914): comforting a frightened child is caregiving (V28 2). The child's own "learning experience" stays text only (no game skill) |

### v8/vv3_tale_telling_elder -- The Tale-Telling Elder (L4027-4078)

No change (flavor-only). A storytelling evening; the ending already gives Research.

### v8/vv3_unfortunate_portrait -- The Unfortunate Portrait (L3950-4025)

No change (flavor-only). The portrait is mocked, not the Chief; nobody's look changes.

### v8/vv4_fruity_masterpiece -- The Fruity Masterpiece (L4080-4147)

No change (flavor-only). The ending already gives food and Farming.

### v8/vv4_quiet_gardener -- The Quiet Gardener (L4149-4197)

No change (flavor-only). The ending already gives Farming or Building to both.

### v8/vv5_gift_or_insult -- Gift or Insult? (L4199-4274)

No change (flavor-only). A misunderstanding over a carving; the ending already gives a skill.

### v8/vv5_little_things_remember -- The Little Things They Remember (L4276-4329)

No change (flavor-only). A reunion; the ending already gives Devotion.

### v9/vv1_missing_pearl -- The Missing Pearl (L4694-4731)

No change (flavor-only). An object goes missing, not a villager.

### v9/vv1_the_wall -- The Wall (L4595-4692)

No change (flavor-only). "The wall collapses harmlessly into an empty work area. Nobody is hurt."; the endings already
give Building.

### v9/vv2_experimental_remedy -- The Experimental Remedy (L4733-4794)

No change (flavor-only). The demonstration has "NO ingestion"; nobody takes the remedy.

### v9/vv2_stolen_spoon -- The Stolen Spoon (L4796-4872)

No change (flavor-only). A dispute over a spoon; everyone in it is a text figure.

### v9/vv3_chief_and_the_pearl -- The Chief and the Pearl (L4874-4934)

No change (flavor-only). An inquiry; the Chief is only exasperated.

### v9/vv3_duel_terrible_inventors -- The Duel of the Terrible Inventors (L4936-4973)

No change (flavor-only). The shoving match is stopped "before anyone is seriously hurt" (L4949), so no injury.

### v9/vv4_arbor_day_festival -- The Arbor-Day Festival (L4975-5032)

No change (flavor-only). The unsafe dish is never eaten ("IT IS NOT FOOD").

### v9/vv4_rotten_structure -- The Rotten Structure (L5034-5078)

No change (flavor-only). "Nobody is hurt"; the collapse already damages a structure.

### v9/vv5_slug_race -- The Slug Race (L5080-5141)

No change (flavor-only). A children's slug race.

### v9/vv5_trial_shattered_pearls -- The Trial of the Shattered Pearls (L5143-5222)

No change (flavor-only). Damaged art, told; everyone in it is a text figure.

### v10/all_great_appointment -- The Appointment Scandal (L5730-5848)

No change (flavor-only). The office "is a responsibility, not a magical promotion in skill" (L5736-5737).

### v10/all_invention -- The Village Idiot and the Impossible Invention (L5524-5605)

No change (flavor-only). The tests are supervised and harmless; the leaf-covered hat is a hat, not a new head.

### v10/all_teacher_who_failed -- The Teacher Who Failed (L5683-5728)

No change (flavor-only). A failed lesson gives no gain and never a loss (V28 2).

### v10/all_unlikely_advisor -- The Unlikely Advisor (L5607-5681)

No change (flavor-only). An appointment is told only (rule 7).

### v10/all_very_bad_day -- (Name1)'s No Good, Very Bad Day (L5385-5522)

No change (flavor-only). A false accusation and its social fallout; the source itself warns against treating it as
lasting harm, and nobody is hurt.

### v10/vv345_magician_naturalist -- The Magician and the Naturalist (L5850-5926)

No change (flavor-only). An argument between two text figures.

### v11/all_conundrums -- The Council of Conundrums (L6661-6810)

No change (flavor-only). The comic failures hurt nobody; the successes already give skills.

### v11/all_invention_showcase -- The Invention Showcase (L6410-6659)

No change (flavor-only). The collapsing contraption is an invention, not a structure; the successes already give
skills.

### v11/all_secret_of_life -- The Secret of Life (L6141-6408)

No change (flavor-only). The "dangerous" jar is disposed of safely before anyone opens it; the experiments already give
skills.
