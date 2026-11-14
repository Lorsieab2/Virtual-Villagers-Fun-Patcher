# Isola Grand Event Collection: cross-review r2 (source lines 6837-8489)

Reviewer: an independent agent that did not author these files. Branch reviewed: `origin/feat/97-coll-content3` at
`b6b96bea3`. Scope: `data/event_collection/v13`, `v14`, `exclusive` and `v17` (82 files), the `v17_u`, `v17_p` and
`v17_e` pools in `shared_pools.json`, and how the V8 contest codas are attached to V17.

Method:
- Every event was re-derived from the frozen source span first: choices, outcomes, weights, pool sizes, effects and
  recipients, and games.
- Each file was then compared with that derivation.
- `simulate()` was run on 6 or more distinct paths per event in every listed game (V14 scenes have one path each). The
  popups were read as a player would.

## Checks run

| Check | Result |
|---|---|
| `scripts/collection_check.py`, one file per process | 80 of 82 print OK. `all_its_alive.json` (label off screen) and `vv5_v17_cooking.json` (role `visitor`: unknown field `named`) fail; both are pinned as known gaps in the test file. |
| `tests/test_event_collection_files.py` | 36 passed, 118 subtests passed |
| Pool sizes against the manifest | All match: Judge A6/B5/C5/D5; Panel 8; It's Alive 4/4/5; Builder 3/4/3/3; Statue 4/4/3; Verse 8 + 4/4/4/5; Idea 20 + 5/5/5; V14-02 11; V14-13 7; U 10; P 10; E 5 |
| Protected villagers | Pass. The only harm-capable roles are `researcher` (Waterfall A4) and `patient` (Hospital B2), and both are protected-excluded. The Golden Child appears only in harmless V14 roles. The VV3 Chief appears only in harmless roles (`chief` in three files). |
| Lore | Pass. No "Chief" outside VV3. Magic and Nature words appear only in VV3-VV5: It's Alive! B3 is gated by `if`, B2 has a variant, and the Builder uses `{@naturalist}`. |
| Grammar fixes | None used in scope. The doc contradicts itself (m10). |

## Counts

| Severity | Count |
|---|---|
| BLOCKER | 2 |
| MAJOR | 19 |
| MINOR | 12 |

## BLOCKER

### B1. vv5_v17_cooking: the Isolan visitor has no name, so the text shows a blank

- Where: `v17/vv5_v17_cooking.json`, nodes `contest` and `a1`, role `visitor`. Source L8385 and L8389.
- What is wrong: the role is `{"kind": "stranger", "named": true}`. `named` is not a format field, so the file fails
  `collection_check` ("role visitor: unknown fields named"). `simulate()` prints:
  - "Bo and  prepare signature dishes." (a double space where the name should be)
  - "'s dish wins fairly, and a furious villager accuses the judges..."

  The test pins this as GAP-VISITOR, but the file is still in the collection. If it ships, every VV5 cooking contest
  shows the blank.
- Suggested fix: keep the file out of the package until the format can name a stranger. Two ways to do that:
  - a pool of Isolan names drawn into the stranger;
  - a named-stranger feature.

  Ask the owner which. Do not ship it with the gap pinned.

### B2. V17 runs two branch sets per trigger (three in VV5), against the source's own rule

- Where: all 34 `v17/*.json` files, nodes `common`, `u` (VV1-4) and `politics`, `p`, `e` (VV5). Source L8054-8056,
  L8065-8075, L8348-8352.
- What is wrong:
  - **The source forbids it.** L8054 says "Choose a single contest, one game-specific setting and one branch set per
    trigger". L8056 says "do not ... run contradictory outcomes together".
  - **The files stack the branch sets.** After the contest's own question and outcome (one branch set), every file
    asks the common 4-button question (a second set). VV5 then also asks the political question (a third set).
  - **The order is backwards.** The common question's text is the source's INTRO ("Two villagers (Name1) and (Name2)
    enter a competition before an excited crowd."), but it appears after the contest has already been decided. A run
    of vv1_v17_cooking reads:
    1. "The elder praises a humble broth over an extravagant feast."
    2. "Two villagers Mira and Tala enter a competition before an excited crowd."
    3. A choice to "Trust the appointed judges and let the contest proceed."
  - **The questions repeat each other.** The contest's "Blind tasting." is followed by "Require a blind or anonymous
    test of the entries."
  - **The outcomes contradict each other.** Examples from the runs:
    - B2 "the judge awards a tie", then U4 "...furious to have lost", then coda C1 "the winner discovers that the loser
      has already gone home".
    - VV5: a contest outcome, then P1 "the competition resumes only if both sides agree", with the contest already
      over.
- Suggested fix, per contest:
  - A contest that has its own branch set (cooking, the VV1 story, the VV2 bridge, the sculptures, the VV5 contests
    with A-D) does not show the common question. It ends with U, filtered for compatibility (M2), then the coda.
  - A contest with no choices of its own (most building, research, farming, story and children's contests) shows the
    common INTRO sentence and question **before** the contest page, then U, then the coda.
  - VV5: use the political question in place of the common one (both are "for any contest"), then P, E and the coda.
  - This removes the reversed chronology and the duplicate choices.

## MAJOR

### V17 flow (just added)

**M1. The coda's pronoun belongs to nobody (all 34 V17 files)**
- Where: role `coda1` and nodes `coda_c1`, `coda_c6`, `coda_c8`. Pools `v8_c1`, `v8_c6`, `v8_c8` (source L4336-4339,
  L4371-4373, L4382-4387).
- What is wrong: `coda1` is a random-sex stranger, but C1 ("the loser"), C6 ("The losing contestant") and C8 ("A
  competitor") all mean one of the two cast competitors. Run 2 of vv1_v17_cooking had two male cooks and printed "The
  winner finds her to offer a sincere compliment."
- Fix: make `coda1` an alias of the two competitor roles (and the G2 `other` role for "the winner"), so the pronoun is
  a real competitor's.

**M2. U, P and the codas ignore the source's "choose only a compatible one"**
- Where: pools `v17_u`, `v17_p` and the coda picks, all V17 files. Source L8075, L8056, L8354.
- What is wrong:
  - **U has no `if` conditions:**
    - U7 (L8086, "recites a familiar verse") follows cooking, building and farming contests.
    - U2 and U9 ("The severe judge", "The critic is caught") follow contests with no judge or critic: VV1 and VV2
      children's games, the VV1 story. A run of the VV1 story printed U9.
    - U10 ("Nobody wins") follows outcomes that name a winner (VV1 cooking B1).
  - **The codas contradict the outcome.** Coda C9 ("announce the wrong name") and C1 ("the winner") follow ties and
    "nobody wins".
  - **The political choice does nothing.** P7 ("A joint entry wins") is drawn whatever the player picks, even when
    they did not choose "Invite the two teams to cooperate".
- Fix:
  - Give U items `if` conditions on the contest kind and outcome (visited nodes).
  - Gate C1, C6 and C9 on a contest that had a winner.
  - Gate P7 on the cooperate choice.

**M3. Children's contests cast adults as the competitors**
- Where: vv1/vv2/vv3/vv4/vv5_v17_children, roles `comp1` and `comp2` (`min_age` 14), node `common`. Source L8155-8158,
  L8205-8208, L8263-8267, L8323-8326, L8452-8461.
- What is wrong: the common question names two adults as the competitors ("Two villagers Bo and Tala enter a
  competition") in a children's contest.
- Fix: make the competitors children (`min_age` 3, `max_age` 13). In VV1, keep the Golden Child out of a competitor
  slot (L8102-8103). Or drop the common question here (B2).

**M4. VV5: "Two villagers" contradicts the Isolan competitor**
- Where: all 7 vv5_v17 files, node `common`. Source L8067-8068, L8385, L8413, L8433.
- What is wrong: every VV5 contest is between the player's tribe and Isolans, who are never cast. The common question
  still says "Two villagers (Comp1) and (comp2)".
  - In vv5_v17_cooking the second name, `comp2`, is a third person who is not the visitor in the story ("Bo and 
    prepare signature dishes ... Two villagers Bo and Lani enter a competition").
  - In the story and research contests the rival is "An Isolan storyteller" or "an Isolan investigator", yet a cast
    believer is named as the second competitor.
- Fix: in VV5, do not show the common intro. The political question replaces it (see B2).

**M5. Answer pages that only repeat the clicked label as an order**
- Where, with the source line:
  - VV1-4 `common_d` (L8072-8073);
  - VV5 `common_a`-`common_d` (L8069-8073);
  - vv2_v17_building `a` (L8176);
  - vv3_v17_sculpture `a`, `b` (L8248);
  - vv4_v17_sculpture `a`, `b` (L8308-8309);
  - vv5_v17_sculpture `a`, `b` (L8426-8427);
  - vv5_v17_story `b`, `c` (L8438-8439).
- What is wrong: after the player clicks a choice, a popup shows only that choice again as a command, for example
  "Reward the safe, reliable bridge." or "Let the public vote." VV5 shows four of these, one after each common choice.
  It reads like a stray instruction, not a result.
- Fix: route such choices straight to the next node, as VV1-4 already do for `common` A-C. Keep a page only when it
  adds the source's outcome text.

**M6. The shortened choice D**
- Where: node `common`, choice 4, in all V17 files. Source L8072-8073.
- What is wrong: the label "Allow a mixed panel of elders, practitioners and ordinary villagers" stops before "to
  judge", so the button reads unfinished. No words are lost (the answer page has the full sentence), but that page is
  the bare order criticised in M5.
- Fix: show the full sentence "...ordinary villagers to judge." on the button if it fits on two lines. If it does not,
  keep the short label but drop the echo page.

**M7. Designer instructions shown to the player as story text**
- What is wrong: these lines are rules for implementers, not story, and they appear in popups:

| File, node | Source | Text shown |
|---|---|---|
| vv1_v17_cooking a2 | L8113 | "...flees the square; discard it and postpone judging." |
| vv2_v17_building b | L8178 | "...; do not let children test an unverified bridge." |
| vv2_v17_sculpture contest | L8190-8191 | "Award separate skill and audience honors, or let the carver learn humility." |
| vv4_v17_building contest | L8296 | "No magical violation of physics is asserted as fact." |
| vv3_v17_research contest | L8242 | "No faction automatically wins." |
| vv5_v17_sculpture d | L8430 | "no community's sacred imagery is used without discussion." |
| vv5_v17_story d | L8441-8442 | "...but it must not silently overwrite sacred history." |

- Fix: ledger these clauses as `note` (as L9679-9680 and the others in the not-applied table are). Where an option
  list remains ("Award ... or let ..."), make it the contest's choices, or let the page describe one drawn result.

**M8. Answer pages that are fragments**
- What is wrong: these pages are not sentences:

| File, node | Source | Page text |
|---|---|---|
| vv1_v17_story b | L8147-8148 | "Clearly labeled as parody rather than a replacement for the tribe's history." |
| vv5_v17_children o1-o4 | L8459-8461 | "A joyful joint celebration", "A sincere apology", "An unresolved adult disagreement", "A child asking why grownups cannot lose as gracefully as children" (no full stop) |
| vv5_v17_research e1-e4 | L8417-8419 | "Honest coincidence", "Misremembered teaching", "Deliberate copying proved by evidence", "A shared improvement that neither could have made alone" |

- Fix:
  - vv1_v17_story b: keep the whole of L8147-8148 on the page ("Preserve the comic version as a separate festival
    song, clearly labeled as parody...").
  - VV5 outcome lists: propose grammar-fix rows that make each item a sentence (for example "The result is honest
    coincidence."), or show the outcome under the source's own lead "Outcomes:" / "Possible endings:" so the list reads
    as a list. Either way, the owner approves.

### V13

**M9. The Judge Who Feared No Dish: a village villager is cast as "a famous visiting cook"**
- Where: `v13/vv2_cooking_judge_who_feared.json`, role `judge` (`kind` villager), nodes `v13a_intro` and `v13a_b5`.
  Source L6868, L7596-7597; inventory part 3, section 1.1, says "offscreen NPC".
- What is wrong: one of the player's own villagers is introduced as a visitor ("A famous visiting cook, Keo, has been
  asked..."). B5's Research gain (L6969, "culinary knowledge preserved") goes to that villager. The source never says
  who receives it, and the person who shared the recipe is "An elderly villager".
- Fix: once a named stranger exists (same gap as B1), make the judge a named stranger. Give B5's gain to a cast
  elderly-villager role or the cooks, or make it text only.

**M10. Judge A2 ends without a full stop**
- Where: `v13a_a2`. Source L6907.
- What is wrong: the ledger cuts "; use the original contest's winner" and leaves "...Lani wins the judge's praise"
  with no full stop (seen in a run).
- Fix: add a grammar-fix row for L6907 that ends the sentence with ".", or cut the clause together with the
  semicolon and keep the full stop.

**M11. Judge: the temperament is a bare fragment**
- Where: `v13a_intro` `{JUDGE_TEMPER}`. Source L6874-6879.
- What is wrong: the drawn item is shown as its own paragraph with no subject and no full stop: "Thunderous,
  theatrical, and almost impossible to impress".
- Fix: show it under the source's own bank label, or put it in a sentence through an approved grammar-fix row. Owner
  decision.

**M12. Judge: shipped standalone, but the source says it plugs into the VV2 Cooking Contest**
- Where: the whole file. Source L6864-6867, L7024-7025, L7596-7598, L8046-8047.
- What is wrong: the module is "ONE OPTIONAL JUDGE BEFORE THE ORIGINAL JUDGING PHASE". As its own event:
  - the finalists are never introduced, yet A1-D5 name them;
  - outcomes stop mid-contest: A2 "use the original contest's winner routing", A3 "The judges postpone the
    competition", D3 "calls for a second blind tasting".
- Fix: attach the module to `original/vv2_cooking_contest.json` before its judging phase, as the source says. If it
  must stay standalone, ask the owner first, and add an opening page that introduces the finalists.

**M13. The Panel of Impossible Standards: no contest, and the endings ignore the choice**
- Where: `v13/all_panel_of_impossible.json`, `set_endings`, `end1`-`end8`. Source L7035-7038, L7082, L7599-7601.
- What is wrong:
  - The add-on stands alone, so "The contestant", "the work" and "the demonstration" refer to nobody.
  - The endings are drawn from all 8 whatever the choice. After "Ask for a second, independent judge", one run
    printed "THE EXPERT IS VINDICATED: The flaw appears during the demonstration.", though no demonstration was chosen.
- Fix:
  - Gate the endings on the choice: end1 and end2 after D, end3 after A or C, and so on (L7082 says "one appropriate").
  - Add an opening page naming a contestant, or attach the critic to the contests, as L7599-7601 says.

**M14. Builder and Verse: an outcome's heading sits alone in its own popup**
- Where: `all_physics_defying_builder.json` and `all_verse_that_changed_history.json`, nodes `a1`, `a2`, ... with
  `a1_story`, ... (L7219-7286, L7392-7480).
- What is wrong: each outcome's heading is a full popup by itself (just "THE COUNTERWEIGHT:"), and the story follows in
  the next popup. The other V13 files join the heading and the body on one page.
- Fix: merge each heading node with its `_story` node (text "HEADING:\nbody").

**M15. It's Alive!: a choice label runs off the screen**
- Where: node `intro`, choice 1. Source L7114.
- What is wrong: "Praise (researcher) for creating something alive." is 950-1055 px wide with the longest names (768
  allowed), in VV1-VV4. It is pinned as GAP-LABELFIT, but the owner's rule is that no text runs off the screen.
- Fix: wrap labels onto two lines in the engine. Otherwise the owner chooses the wording.

**M16. Verse B4 needs an insulted elder**
- Where: `b4_story`. Source L7431.
- What is wrong: "The elder whose honor was supposedly insulted" only makes sense after error items L7377 (the blessing
  that sounds like an insult) or L7384-7385 (the attack on the respected elder). After "sings a funeral verse to the
  melody of a drinking song", nobody was insulted.
- Fix: put `if` on the `set_b` child b4: visited the error items L7377 or L7384-7385. Draw the error as a branch so it
  can be visited, as the Statue's subject is.

**M17. The Inexplicable Idea: B1, C4 and C2 ignore the drawn idea**
- Where: `set_b` b1, `set_c` c4 and c2. Source L7491, L7609-7610.
- What is wrong:
  - **The source rule:** an ending must be "compatible with the rolled idea; never resolve a rain sign as a working
    water-cooling jar" (L7609-7610).
  - **The file:** A1 and A2 are gated, but these three are not:
    - B1 "gives a clear demonstration ... approves a supervised trial" can follow "Paint the village's shadows".
    - C4 "demonstrates the same useful principle" can follow the RAIN sign.
    - C2 "It works, but is still completely useless" can follow the useful raft or water chain.
- Fix: gate B1 and C4 on A1's useful ideas (I01-I06, I08, I18). Gate C2 on the others.

### V14

**M18. V14-02: the subject shows as a bare word**
- Where: `vv1_v14_02_worlds_simplest.json`, `scene`. Source L7661-7663.
- What is wrong: the popup ends with a lone paragraph "Medicine". The ledger removed "Choose subject:", so nothing
  says what the word is.
- Fix: keep the subject in the text (an approved grammar-fix row such as "the same subject ({subject})"), or show it
  under its own label. Owner decision.

**M19. V14-13: the discovery shows as a bare fragment**
- Where: `vv1_v14_13_curious_little.json`, `scene`, pool `discovery`. Source L7739-7741.
- What is wrong: the drawn item is a paragraph on its own: "Unusual beetle". Only the first item has an article ("A
  tiny flower"), so the items are inconsistent.
- Fix: as M18. Keep the source's "Random discovery:" as the label, or join the item into the sentence with an
  approved fix.

## MINOR

- **m1** `all_panel_of_impossible` `ask1`-`ask6` (L7042, L7048, ...): the question page repeats the quote the previous
  page just showed. Use a short lead instead, or the choices' heading L7076.
- **m2** `all_panel_of_impossible` `critic1`-`critic6` (L7040, L7046, ...): "(NAME3)" renders as "MASTER CARVER Lani:"
  without the source's parentheses. Write `\((critic)\)` so it shows "MASTER CARVER (Lani):".
- **m3** `all_panel_of_impossible` role `critic` (L7041 "An elderly craftsperson"): `min_age` 14 lets a teenager be
  "elderly". Raise `min_age` to the elder age.
- **m4** `all_its_alive` `b3` (L7157): the heading reads "BLASPHEMY AGAINST MAGIC" with no colon, because the colon was
  cut with "(VV3-VV5 ONLY)". The other headings end with ":". Keep the colon.
- **m5** `all_verse_that_changed_history` `a4_story` and `c2_story` (L7411, L7442): the goat legend and "goat metaphors"
  fit only the goat error L7378. Gate them like M16, or accept them as comedy.
- **m6** `vv1_v14_22_golden_childs_great` role `farmer` (`skill` Farming 1): the role is required on both branches, so
  with no Farming villager the whole scene never runs, even though the food page does not need one. Mark `farmer`
  optional, or move it to the farming page only.
- **m7** `vv2_secret_behind_waterfall` `a5` (L7851): "a priceless treasure chest!" gives nothing. This is already owner
  question Q10; keep it on the list.
- **m8** `vv2_hospitals_most_difficult` (L7858) and `vv2_secret_behind_waterfall` `a4` (L7850): the villager who loses
  or gains health is cast but never named ("A stubborn villager", "the researcher"). The player cannot tell who was
  hurt. Acceptable, but a token after the first mention would help (owner's call; it changes the text).
- **m9** Exclusives (L7840, "No outcome should reduce stored food or tech below zero"): I did not confirm that a food
  loss stops at zero in the native food effect (`native/vvfp_story_upgrades/story_graph.inc`). UNCONFIRMED; please
  check.
- **m10** `docs/event-collection/grammar-fixes.md` contradicts itself:
  - L6986 and L7183 are in the Fixes table and also in the Not-applied table.
  - L7684 and L8206 are in the Fixes table, but the part 3a note says no fix is applied, and no file uses them.
    `vv2_v17_children` still shows "The Children are asked".
  - Fix: either apply L7684 and L8206 or move them to Not applied, and remove the duplicate L6986 and L7183 rows.
- **m11** V8 codas on V17: Q13 attaches coda banks to "the events of their own section". V17 is not V8's section.
  The source heading L4332 ("ATTACH TO COMPATIBLE EXISTING EVENTS") allows it, so this is a note for the lead, not a
  defect. The source also calls them "RARE" codas, while Q13's 50% makes them common.
- **m12** `vv1_v17_cooking` `c1` (L8118 "Research reward"): this is mapped to tech points. It could also mean a Research
  skill gain for the cook who revealed the method. Ambiguous; list it for the owner.

## Re-derivation notes (no finding)

- **Exclusives (16):** choices, outcomes, food and tech sizes ("a little" and "small" are small; plain "tech" and
  "food" are normal; "large" is large) and the celebrate effects all match the source. The 50/50 food-or-tech split
  in Water Argument A1 and Hospital B2's loss-then-restore are faithful.
- **V14 (25):** every "Outcome:" line is mapped:
  - effects: tech by size; the apprentice's small skill gain from a random skill; the elder's +5..10 health; V14-20 as
    modest or large; V14-22 as food or Farming;
  - text-only: weather, crops, berry bush, morale and grief, each with the source's own fallback.
- **It's Alive!, Builder, Statue:** labels, banks and the `if` gating (B3 VV3-5, Statue A3 on the elder subject) are
  correct.
- **Shared pools:** `v17_u` (U1-U10), `v17_p` (P1-P10) and `v17_e` (E1-E5) match L8076-8093, L8355-8382 and
  L8464-8473 word for word. The P headings keep their "THE INSULT:" titles.
