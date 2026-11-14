# Isola Grand Event Collection: cross-review R3 (source lines 1-3519, plus V13-A)

Reviewed commit: `6bb8ce7c` (origin/feat/97-coll-content1). Nothing in the event files was changed.

**Scope.** Every event file whose source lies in lines 1-3519:
- `original/`: The Cooking Contest (core L100-626, add-on 1 L632-725, add-on 2 L872-1154, and the V13-A judge L6863-7028 merged in), The Child of Legend and The Meaning of "Faith";
- `universal/`: 5 files;
- `v6/`: 10 files;
- `vv5_isolan/`: 4 files.

**Method.**
- For each event I re-derived these from the source before opening the JSON: the choices and their labels, the outcomes and their weights, the pool sizes, the effects and who receives them, and the games.
- I then compared that with the JSON.
- Expanded text was read through `vv_cie_graph.simulate()` with random casts, rolls and answers, using `sim.py` (a scratch harness: graph_for_engine, then simulate, then the popups as shown):
  - The Cooking Contest: 1,000 paths. Every node was visited except those listed in its section; I read those by hand.
  - Every other event: at least 5 paths per listed game, between 6 and 385 paths per event, so that every node was visited or read by hand.
- The universal, v6 and original/vv5_isolan groups were read by three independent sub-reviewers. I re-checked every BLOCKER they raised against the source and the JSON; those are marked **(verified)**. Their other findings are simulator-backed, but I did not recheck each one.

**Checks run.** Each ran in its own process.
- `python scripts/collection_check.py` on the 22 in-scope files: **22 of 22 OK**.
- `python -m pytest tests/test_event_collection_files.py`: **36 passed, 134 subtests passed**.

The checker passing means that the words match the source. It does not catch the routing, effect and reading problems below.

**Severity.**
- **BLOCKER:** wrong gameplay or effect, a protected-villager violation, or lost or changed owner text.
- **MAJOR:** the text reads wrong to a player.
- **MINOR:** anything else.

## Counts

| Group | BLOCKER | MAJOR | MINOR |
|---|---|---|---|
| The Cooking Contest (core, add-ons 1 and 2, V13-A) | 4 | 12 | 11 |
| The Child of Legend, The Meaning of "Faith" | 0 | 0 | 2 |
| Universal 1-5 | 3 | 5 | 9 |
| v6 (10 events) | 2 | 6 | 8 |
| VV5 Isolan (4 events) | 2 | 6 | 6 |
| **Total** | **11** | **29** | **36** |

**Protected villagers:** no violation found in any file.
- In The Cooking Contest the only harm-capable role is `cook1` (dislikes). It is protected automatically.
- The judge, the Golden Child (Child of Legend), the Chief (Monumental Speech) and the nursing parent (Lullaby) have no harmful effect.

**Lore:** no bare "Chief" can be reached outside VV3.
- `{@chief}` / `{@a_chief}` / `{@chiefs}` show as "the village leader" / "a leader" / "elders".
- Magic appears only where the owner's VV2 text puts it ("a magical prodigy", "a magical potion"), as an adjective and not a faction.

---

## 1. The Cooking Contest (`original/vv2_cooking_contest.json`)

**Re-derived from the source and matching the JSON:**
- The question "Stick with their original recipe" / "Try a new recipe" has 2 choices.
- Endings A-F (core), G/H/I (add-on 1) and (16)/(24)/(29) (add-on 2): 12 equal openings.
- Every bank count matches the manifest: A 21, B 17, C 24, F 28, D-CUISINE 27, D-STYLE 13, G 15, ingredient 12, H 25, I 27, J 19, L 18, K 22, M 16, O 20, P 18, Q 27, R 22, (1) 6, (5) 4, (8) 4, (9) 5, (13) 10, (6) 10; add-on 1 (17) 4, (18) 6, (19) 6, (27) 5, (29) 6; add-on 2 (17) 7, (22) 5, (25) 8, (26) 5, (28) 8, (30) 8, (31) 6, (32) 5.
- V13-A: temperament 5, remark 7, choices A-D with 6/5/5/5 outcomes. D4 and D5 sit at L7012-7022, just past the stated L7011.

**The reward is never paid twice.** I checked every path to `win1`, `win2` and `five1`-`five4`, and to the add-on-1 showdown's `_pay`/`_paid` split and add-on 2's (28):
- no path pays the food award or Farming 100 twice;
- the add-on 2 showdown can only follow `a2_20`, which comes before any win.

The award logic itself is correct. The problems are in routing and reading.

Not visited in 1,000 simulated paths, read by hand: `a1_29_1_pay`, `a1_29_3b_paid`, `a1_29_5`, `a2_22_4`, `a2_28_1/2/4/5/6/7/8`, `ban_potions`, `six5`. All were fine apart from the findings below.

### BLOCKER

- **BLOCKER** | file: original/vv2_cooking_contest.json | node: f14_warn, f14_lesson -> eventually -> six (six6-six10, ban_*) | source: L592, L603, L868 (also L616) | problem: The punitive (6) decisions are reachable only after the (14) "honest mistake" pages. There the source says "Do not label an accidental mistake sabotage" (L592), "(6) ... only when consistent with its findings" (L603) and "avoid punishing an innocent cook for an unrelated illness" (L868). The player reads, for example: "The food had been kept out for too long ... The judges give her a stern warning. Eventually, the judges... throw Ana in prison for sabotage." The ban and "give up their dreams" pages also give the innocent cook a lasting *dislikes* effect (cooking, herbs, medicine or work). | fix: After f14, allow only the non-punitive six1-six5 (an `if: {"not": {"visited": "f14"}}` guard on six6-six10 or a separate `six_mild` branch). If the owner wants the punitive verdicts kept, reach them only after confirmed tampering (inv10 / (10)). The owner's L616 ("even if the judges are misguided") shows they may want unjust verdicts: **owner question**, but as built the result contradicts the later rules on every path.
- **BLOCKER** | file: original/vv2_cooking_contest.json | node: a1_26opt | source: L666, L721, L723, L1150 | problem: The rivalry and showdown aftermath is blocked after the illness investigation, the judge and the add-on openings. It is **not** blocked after confirmed sabotage (end_e or end_f -> sab1 / sab2, inv10 -> sab2). A cook just caught tampering, even one "banned from competing again", can enter the ultimate showdown and win large food plus Farming 100. Simulated (seed 7): "The judges disqualify the saboteur ... shocked at the decision ... burst out laughing ... It looks like Isola has gained two bitter culinary rivals! ... The villagers choose Ana", with Ana as the saboteur, paid. The source allows (26) only "following a fair win, joint win, or unresolved cancellation" and says "Never route a confirmed saboteur to the innocent-winner role". | fix: Add `{"visited": "sab1"}` and `{"visited": "sab2"}` to the a1_26opt exclusion list. Optionally add `d_out` (a disqualification is not a fair win).
- **BLOCKER** | file: original/vv2_cooking_contest.json | node: v13a_b5 | source: L6966-6969 | problem: "An elderly villager shares a simple family recipe ... Result: culinary knowledge preserved; optional Research experience." The Research gain (10..20) goes to the `judge`, the visiting critic who only listens, not to the elder who shares the knowledge. | fix: Give it to an optional elder villager role (`min_age` 50, harmless), or make it text-only (rule 7/8). Never give it to the judge.
- **BLOCKER** | file: original/vv2_cooking_contest.json | node: intro (grammar fix L104) | source: L104 | problem: The fix `"is.... " -> "is "` removes the owner's dramatic pause ("Tomas is.... a hopeful spirit that never gives up"). The sentence is not broken; the four dots are a deliberate beat in the owner's own manuscript of the owner's favourite event. It is a style change, not a glaring grammar mistake, so the owner's text is changed. | fix: Drop the row. Keep `is.... ` (or `is... ` if the owner prefers three dots).

### MAJOR

- **MAJOR** | file: original/vv2_cooking_contest.json | node: stick, new | source: L300, L305 | problem: "into a {J.2}" and every J item already starts with an article. **All 1,000 simulated paths** read "...strains the mixture into a a pot", "into a a curved-neck flask", "into a a beaker". | fix: Add a grammar-fixes row for L300 and L305, `into a (J, different from the first J)` -> `into (J, different from the first J)`. This is a glaring doubled word.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: sab1 (pool Q), sab2 (pool Q2) | source: L598 "(Other name) (Q, where the reaction makes sense)" | problem: The victim of the sabotage reacts with the full loser bank. Simulated: "Tomas whispers quietly. Bruno pretends he did not lose." and "The judges ban the culprit from competing again. Tomas considers picking a fight. Ana vows to beat him next year." Other draws include hugging or congratulating the saboteur "for the win", "stands proud at having gotten second place", "tearfully concedes". The authors filtered Q2 for `seven` (L616) but not Q/Q2 for sab1/sab2. | fix: Add `if: {"not": {"any": [{"visited": "sab1"}, {"visited": "sab2"}]}}` to the Q and Q2 items that assume a lost fair contest or friendship with the rival: L486, L488, L493, L494, L496, L497, L498, L503, L504, L507, L508, L509, L510, L511.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: v13a_c1 -> v13a_bell -> v13a_endings | source: L6971-6975, L7024-7025 | problem: "The judge orders a blind tasting and agrees to be bound by the result. (Cook1)'s dish wins." The contest then goes through all of A-F again, where cook2 can win, cook1 can poison the judges, and so on. Simulated: "Ana's dish wins ..." then "At first, the judges go to pick Ana ... all of the judges get all-out food poisoning." L7024-7025: "Do not stack contradictory endings." | fix: Route v13a_c1 to `win1`, which pays the contest's single award.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: v13a_d2 | source: L7004-7007, L7024-7025 | problem: "The village's celebrated cook loses to an unassuming apprentice ... The apprentice nearly drops the trophy." The bell then rings and the whole contest is judged again. Simulated: the trophy line, then a missing-ingredient scene and a joint win. Neither "celebrated cook" nor "apprentice" is tied to cook1 or cook2. | fix: Route D2 to a win page (the apprentice is the winner). Ask the owner which finalist is the apprentice, or route to win_either. Do not continue to the bell.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: roles.judge, v13a_intro | source: L6868, L6859-6860 | problem: "A famous visiting cook, (Judge), has been asked to examine the finalists' work..." is cast as one of the player's own villagers (an optional `villager` role). The player reads that their own villager Tomas is a famous visitor who "has served feasts for entire villages". The V13 canon notes treat visitors as off-screen NPCs. | fix: **Owner question.** Options: (a) a stranger role, which needs the name slot dropped and so an owner-approved text change; (b) accept a villager judge and ask the owner whether "visiting" may be cut. Do not ship silently.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: v13a_intro (pool JUDGE_TEMPER) | source: L6874-6879 | problem: The temperament bank is a list of descriptions with no lead-in. It shows as a bare fragment line with no subject and no full stop under the introduction: "Astonishingly fair, but prone to comparisons involving dead fish". | fix: Propose a grammar-fixes row (owner approval), for example a lead "(He/She) is (temperament)." on L6874. Or show the temperament as part of the intro sentence.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: pools F, F2 | source: L192, L194, L203 | problem: "that he underestimates themselves", "that she overestimates themselves", "that he doesn't put their talents to use". These are the same glaring pronoun errors the authors fixed on L188 and L189 of the same bank ("value their work" -> "(his/her)"), but these three were left. | fix: Add grammar-fixes rows: L192 and L194 `themselves` -> `(himself/herself)`; L203 `their talents` -> `(his/her) talents`.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: a2_28_3 ... a2_28_8 | source: L1067, L1076-1093 | problem: a2_r3 ends "After a long silence," and the (28) items keep their capital letter. The player reads "After a long silence, Both dishes are equally magnificent." The add-on 2 (17) items after "But apparently," were lower-cased correctly. | fix: Lower-case the first letter (rule 6) of a2_28_3 ("both"), 28_4 ("the judges discover"), 28_5 ("a sudden"), 28_6 ("a coconut"), 28_7 ("both chefs") and 28_8 ("the judges select").
- **MAJOR** | file: original/vv2_cooking_contest.json | node: win1, sab1 (pool Q), seven, sab2 (Q2); a2_24 (pool RESP) | source: L489, L511, L512, L1008, L1011 | problem: Bank items that end in "!" or "?" are followed by the template's full stop. The player reads `screaming "It's not fair!".`, `to another cook-off soon!.`, `says "Are you kidding me?".`, `"You could have just ASKED me for a rematch!". The judges...`, `couldn't beat me?".`. The authors removed exactly this doubled punctuation elsewhere (L2835, L3006). | fix: The same treatment: a variant or grammar-fix row so items ending in !/? are not followed by "." (for example, split the sentence end into a per-item variant). Owner approval needed.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: pool DC (D-CUISINE), intro | source: L207, L431 | problem: The designer notes say to use D-CUISINE "only when the phrase works before 'cuisine'", and to use D-STYLE for "barely edible" / "a mishmash of ingredients". All 27 items are drawn for "(cook1) prefers {DC} cuisine", so players read "prefers a mishmash of ingredients cuisine" and "prefers somewhat of an acquired taste cuisine". D-STYLE also never draws the D-CUISINE adjectives that L236 says it should. | fix: Keep the bank count and give the non-adjective items (L217, L234, and possibly L218 and L222) an `if` that keeps them out of the "cuisine" slot. Or ask the owner. Optionally let DS also draw the adjective DC items.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: endings -> a2_16 | source: L878-879, L1146 | problem: Add-on 2's (16) opens straight after the bell: "'Wait! Ana didn't do it!' ... The evidence against her seemed so convincing!" No accusation has been shown, and L1146 says "Route (16) only from an accusation with uncertain or falsified evidence". | fix: Reach a2_16 from add-on 1's accusation (a1_g), as an alternative to a1_16. Or put a short accusation page before it. Owner question if neither is wanted.
- **MAJOR** | file: original/vv2_cooking_contest.json | node: pool G (grammar fix L263) | source: L263 | problem: "the charismatic crowner" -> "the charismatic contender". The one-letter typo is almost certainly **"crooner"** ("the charismatic crooner" is a set phrase; the bank is full of flashy titles). "Contender" replaces the owner's word with a different one. | fix: Change the row to `crowner` -> `crooner`, or ask the owner.

### MINOR

- **MINOR** | node: end_c / win2 (pool O) | source: L428, L568 | problem: O is one instance, so after the illness path the quality the judges praised in cook1 is reused for cook2: "impressed by her pride and passion" (Ana) ... "laud her for pride and passion" (Mira). O's stick/new items are also conditioned on cook1's recipe choice but can praise cook2. | fix: Use a second O instance in win2 (`{O.2}` with distinct) and keep the stick/new conditions for cook1 only.
- **MINOR** | node: seven (pool Q2) | source: L616 | problem: The `seven` filter still allows L498 "stands proud at having gotten second place" right after "throw Ana in prison" (simulated). | fix: Add L498 (and L504) to the `seven` exclusion.
- **MINOR** | node: endings | source: L421, L719, L876-880 | problem: The 12 equal openings give the owner's core endings A-F only 50% of runs. The ChatGPT add-on openings take the other 50%. Rule 8 (equal) was applied mechanically. | fix: **Owner question:** should the core A-F carry more weight?
- **MINOR** | node: a2_31_1, a2_28_8 | source: L1119, L1091 | problem: "(Cook2) wins" / "The judges select a winner" end the event with no food or Farming. Add-on 1's equivalent outcome pays through (4). | fix: Owner question; routing a2_31_1 to win2 would match add-on 1.
- **MINOR** | node: a2_coda | source: L1132 | problem: The (32) quiet coda is "optional after any nonfatal, resolved outcome", but it also follows unresolved ones: a2_21 "Others remain suspicious", a2_31_3 "agree to a fair rematch", a2_17_7 "declared inconclusive". | fix: An `if` on the coda's branch that excludes a2_21 and a2_31_3.
- **MINOR** | node: a1_20 -> a1_20_post | source: L656 | problem: "The judges ... declare that the contest must go on" can be followed by "The competition is postponed." | fix: Optional; split the judges' slash list per route.
- **MINOR** | node: end_d | source: L434 | problem: "Where is the required eggs?" (also mushrooms, nuts, roots, herbs, vegetables, coconuts). This is the owner's text. | fix: Owner question only.
- **MINOR** | node: workstation | source: L297, L299 | problem: "sees their workstation" and the label "Stick with their original recipe" keep "their", while L305 "their initial recipe" was fixed. This is inconsistent, though readable. | fix: Leave as is, or fix both; owner's call.
- **MINOR** | node: v13a_a2 | source: L6907-6908 | problem: "(Name2) wins the judge's praise; use the original contest's winner routing and award rules" is built as an instant win for cook2 that skips the bell. The source may mean that normal judging continues. | fix: Owner question.
- **MINOR** | file: docs/event-collection/grammar-fixes.md | source: L1003, L1104 (and L1455 in Beautification) | problem: Assessment of the three "bank number read as a route" entries. The displayed text is right: "(25)", "(26)" and "(30)" really insert bank items into the sentence (simulated: "Ana says ... The judges suspend him from the next competition."; "explains that he was tired of competing..."). But these rows are **not grammar fixes**. They work around the checker stripping a number before a full stop, and they sit in the list the owner must approve as grammar. If the owner rejects them as "not grammar", three good files fail. | fix: Teach the checker that a `(N)` inside a sentence may be a pool token (a mapping, rule 4.5), and remove the three rows.
- **MINOR** | file: docs/event-collection/grammar-fixes.md | source: L6986 | problem: The doc contradicts itself. L6986 ("the other finalist, who had no part in the bribe") is in the Fixes table and also in "Not applied" ("Reads correctly ... wording only"). The Cooking Contest correctly does not use it. | fix: Remove the L6986 row from the Fixes table.

---

## 2. The Child of Legend (`original/vv1_child_of_legend.json`)

- **Re-derived:** 2 choices; banks (1) 9, (2) 11, (3) 4, (4) 11; tech on the L753 item; food on the L760 item (crops and berries are text only); VV1. **Matches the JSON.**
- **Simulated:** 44 paths; every node visited.
- The Golden Child is cast only in a harmless role.
- **Grammar fixes assessed:**
  - L737 (`(He/she) (random from:1).`) is glaring: the (1) items have no subject. Accept.
  - L751 and L758 (comma before "(3)") make two items match the other nine. Accept.
- No findings.

## 3. The Meaning of "Faith" (`original/vv5_meaning_of_faith.json`)

- **Re-derived:** 6 choices, each going to paper (weight 20) or the rare see_me (5, as L870 requires for all six); MANNER 15; 6 grade pages; 8 praise options keyed to the essay; small Research to the child (L836); normal Research/Healing/Devotion (L862); VV5. **Matches the JSON.**
- **Simulated:** 120 paths; see_me was reached from all six choices.
- **Grammar fixes assessed:**
  - L799 (the reopening quote mark), L819 ("There are"), and L826 and L857 ("(his/her)") are glaring. Accept.

Findings:
- **MINOR** | file: original/vv5_meaning_of_faith.json | node: words.chief / pool POWERS | source: L813 | problem: `{@chief}` shows "the leaders", which is also POWERS item 2, so "the leaders" comes up 2 times in 6. | fix: Owner question: another word value, or accept.
- **MINOR** | file: original/vv5_meaning_of_faith.json | node: g1, g2 | source: L824, L826 | problem: "use of pathos/ethos/logos" is split item by item ("gets points for ethos"). | fix: Owner question.

---

## 4. Universal events 1-5 (`universal/`)

Re-derived choices, banks and games (VV1-VV5) match the JSON for all five.
- **Simulated:** 235 base paths (8 or more per event per game), plus 150 extra Beautification and 250 extra Storytelling paths. Scholasticon `d4` and Storytelling `c3` were read by hand.
- **Lore:** checked in VV1, VV2, VV4 and VV5. `{@chief}` shows as "the village leader" everywhere.

### BLOCKER
- **BLOCKER (verified)** | file: universal/all_isolan_storytelling.json | node: v1, v2, v3 | source: L1978, L1981, L1982-1983 | problem: The source says "The winner gains Devotion experience" / "a small Devotion reward". The effects list `["Devotion","Research"]`, and the engine picks one listed skill the game has at random, so in VV5 the winner gets Research half the time. | fix: Use Devotion alone with `"if": {"game": [5]}`, plus a Research copy for VV1-VV4 (or ask whether VV1-VV4 should get any skill at all).
- **BLOCKER (verified)** | file: universal/all_great_beautification.json | node: n_repair / n_norepair | source: L1435-1446 | problem: The small Building gain for "a safe repair" is a hidden 50/50 between two identical pages. It does not follow the leader option shown on that page, so builders gain Building after "forbids anyone from touching the monument again" or "falls off again". L1446 says "No reward for merely dropping a nose". | fix: One node per leader option and per reattach result (`src_pick`). Put the effect only on outcomes that end in a safe repair ("fits perfectly", "slightly crooked").
- **BLOCKER (verified)** | file: universal/all_doctors_dilemma.json | node: after_tech | source: L1657 | problem: "a modest Tech reward" is `size: "normal"`. Rule 9 makes modest `small`. | fix: `"size": "small"`.

### MAJOR
- **MAJOR** | file: universal/all_great_beautification.json | node: n_repair / n_norepair | source: L1439-1443, L2061-2099 note 6 | problem: Both "If the nose is reattached, ..." and "If the nose remains off, ..." always show, whatever the leader chose. Seen: "The village leader forbids anyone from touching the monument again. If the nose is reattached, it is slightly crooked. If the nose remains off..." | fix: The same split as the BLOCKER above.
- **MAJOR** | file: universal/all_doctors_dilemma.json | node: pools B, C | source: L1495-1509 | problem: Two parallel lists of six that belong in pairs are drawn separately. Seen: "best course is to isolate the patient ... Bruno disagrees, arguing that another patient may need the medicine". | fix: Pair them (6 branch nodes with `src_pick`), or ask the owner.
- **MAJOR** | file: universal/all_doctors_dilemma.json | node: e3 | source: L1562 | problem: The leader's pronoun comes from a random-sex `leader` stranger. G8 ("Track D's pilot should switch from the stranger role to this") was not applied, so in VV3 the Chief's pronoun is wrong half the time. | fix: A VV3-only copy of e3 with an optional `"special": "tribal_chief"` role.
- **MAJOR** | file: universal/all_everybodys_a_winner.json | node: pools QUIET item 2, RID item 3 | source: L1797-1799, L1810 | problem: "The winner congratulates the other children" and "Eventually, the actual winner receives it" follow paths with no single winner. Seen: "...has won first place. So does every other child..." then "The winner congratulates the other children". | fix: `if: {"visited": ...}` limited to the single-winner nodes (`one`, `sp1`).
- **MAJOR** | file: universal/all_isolan_storytelling.json | node: end | source: L2044-2050 | problem: "one thoroughly embarrassed storyteller is practicing the word NOT" closes every path, including ones with no fumble ("Both competitors recite the story flawlessly ..."). | fix: Route to that ending only from the fumble aftermath (af1-af8, after c1/c3/c6).

### MINOR
- **MINOR** | universal/all_grand_isolan_scholasticon.json | j4, i4 | L1156-1329 | problem: j4 ("the child who spotted the crucial mistake") can follow paths with no child, and i4 always names a bridge whatever problem was drawn. Both follow the source's own routing. | fix: Owner question.
- **MINOR** | universal/all_great_beautification.json | quiet | L1466-1472 | problem: Every path ends with the quiet ending, which the source never routes to, so "harshest critics are impressed" is followed by "Some still think the monument is hideous". | fix: Owner question.
- **MINOR** | universal/all_great_beautification.json | v4 | L1449-1452 | problem: "the village gains a small Building or Farming reward" becomes a skill gain on the two builders. The choice is not explained in the ledger. | fix: Note it in the owner packet.
- **MINOR** | universal/all_great_beautification.json | r3-r5 | L1420-1433 | problem: The nose, crooked and backward-statue outcomes are drawn whatever monument was picked (a staircase's "enormous nose"). | fix: Owner question.
- **MINOR** | universal/all_great_beautification.json | grammar fix L1455 | L1455 | problem: This is the third "bank number read as a route" row. The reading is real: the (6) items are subjectless verb phrases ("choose contestant1 for the better workmanship") and L1455 is their only lead-in. "(judging)" maps correctly and plays right ("The judges choose Tomas for creativity."). It is still a checker workaround, not grammar; see the Cooking Contest MINOR. L1458 and L1459 (`contestant1` -> `(contestant1)`) are genuine bare placeholders and correct. | fix: As for L1003 and L1104.
- **MINOR** | universal/all_doctors_dilemma.json | — | — | problem: The patient dies in about 1 run in 3. That follows the source and the protected filter; listed so the owner knows. | fix: None.
- **MINOR** | universal/all_everybodys_a_winner.json | child Research gain | — | problem: The gain goes to a cast child the text never names. | fix: Acceptable under G7; note it.
- **MINOR** | universal/all_isolan_storytelling.json | ledger | L1824-2059 | problem: The eight "(The original teaching said: ...)" lines are ledger notes and never shown. That is probably right but UNCONFIRMED. | fix: Owner question.
- **MINOR (UNCONFIRMED)** | all five | roles | — | problem: In VV3 the real Chief may be cast as a researcher, builder, healer or devotee while the text treats "the Chief" as someone else. I did not confirm whether casting excludes the Chief. | fix: Check the engine's special-villager exclusion for non-special roles.

---

## 5. v6 events (`v6/`)

All 10 re-derived (choices, banks, games) match the JSON apart from the items below. The four grammar fixes asked about are glaring; accept them:
- L2835 and L3006: a full stop follows a quotation that already ends in "." or "...";
- L3136 and L3137: the bare words Cook1 / Cook2 would be shown.

The Chief's Monumental Speech uses G8 correctly (`special: tribal_chief`, no effects). The Lullaby's nursing parent has no effect.

### BLOCKER
- **BLOCKER (verified)** | file: v6/vv2_hut_sharing_negotiation.json | node: m1 | source: L2961-2962 | problem: "Modest Building experience" is 10..20 (normal) on the builder and the apprentice. | fix: min 5, max 10 on both.
- **BLOCKER (verified)** | file: v6/vv4_breadfruit_breakdown.json | node: end | source: L3171 | problem: "modest food reward" is `"size": "normal"`. | fix: `"size": "small"`. The Farming gain has no size word, so 10..20 stays.

### MAJOR
- **MAJOR** | v6/vv1_unexpected_question.json | intro | L2742 | problem: "The topic is {A}." puts a bank-A *question* into a statement: "The topic is If everyone learns from someone, who taught the first teacher?. Unfortunately, ..." This gives a capital mid-sentence and "?.". It is already an owner question in grammar-fixes.md, but it ships like this. | fix: Owner decision before shipping.
- **MAJOR** | v6/vv1_unexpected_question.json | g4 | L2810-2812 | problem: Designer wording is shown to the player: "If the Golden Child is present, he responds through an existing supported nonverbal gesture." The node's `if` already enforces the condition. | fix: Ledger-cut "If the Golden Child is present," as a note. Ask the owner for player wording for "an existing supported nonverbal gesture".
- **MAJOR** | v6/vv1_elders_favorite_stone.json | stone | L2852-2863 | problem: The ENDING pick is drawn independently of the OUTCOME. Seen: "A father ... returns it" then "The elder places the replacement on a shelf". "Keeps the stone safe" can also follow "Nobody finds the stone". | fix: Route the ending per outcome (`src_pick`).
- **MAJOR** | v6/vv3_chiefs_monumental_speech.json | speech (pool RESULT) | L3017-3035 | problem: RESULT is drawn independently of the B interruption. Seen: "a child loudly asks when the snacks will be served. The elder quietly helps retrieve the notes." | fix: `visited` conditions on RESULT items 2, 3 and 5, or ask the owner.
- **MAJOR** | v6/vv4_lullaby.json | roles.parent, intro | L3177, L3180, L2703-2705, L3502 | problem: "(mother/father)" loses "father". A ledger `gap` marked "TODO" cuts it, and the role is fixed to female, so nursing fathers are never cast, although the source and the casting notes include them. | fix: Add a mother/father sex-following pair (like son/daughter in PRONOUNS_V6) and write `(parent.mother/father)`; drop the gap and the sex restriction.
- **MAJOR** | v6/vv5_multicultural_festival.json | f4 | L3451 | problem: The player reads "The leader or village leader gives a brief welcome." | fix: Show one word; ledger-cut the designer alternative, or ask the owner.

### MINOR
- **MINOR** | v6/vv1_unexpected_question.json | g3 | L2808-2809 | problem: The nursing-parent line can be drawn in a village with no nursing parent. | fix: Optional gate.
- **MINOR** | v6/vv2_veterinary_visitor.json | h4 -> e2/e3 | L2907-2916 | problem: After the "animal" turns out to be a wooden toy, the endings still treat it as live. This is the owner's structure. | fix: Owner question.
- **MINOR** | v6/vv2_hut_sharing_negotiation.json | m1 | L2961-2962 | problem: "Skilled builders" but the apprentice (no Building requirement) also gains. | fix: Optional.
- **MINOR** | v6/vv5_keeper_of_little_things.json | box | L3299 | problem: "(woman/man/villager)": the neutral "villager" is never shown. | fix: List it for the owner.
- **MINOR** | v6/vv5_keeper_of_little_things.json | roles.elder | L3299 | problem: "The village's oldest" can be any villager aged 50 or more. | fix: Accept, or note it for the owner.
- **MINOR** | v6/vv5_keeper_of_little_things.json | box | L3300 | problem: "Inside are a smooth pebble." | fix: Propose a grammar-fixes row "Inside are" -> "Inside is".
- **MINOR** | v6/vv5_multicultural_festival.json | dispute | L3477 | problem: "either person abandon (his/her) beliefs": the pronoun follows only the visitor. | fix: None; owner's text.
- **MINOR (UNCONFIRMED)** | v6 (elder roles) | — | — | problem: I did not check that `min_age: 50` is the right elder age in VV1, VV2 and VV5. | fix: Check per game.

---

## 6. VV5 Isolan events (`vv5_isolan/`)

- **Re-derived:** Potluck, Laundry and Field Day match the JSON. Woodworking matches apart from the items below.
- **Integration notes:** L2647-2664 are obeyed (only believers are cast; Isolans and Heathens are text or strangers; the judge is never on a team), apart from the "winners consistent" items below.
- **Grammar fixes assessed:** L2260, L2379, L2470 and L2472 are accepted. L2379 is close to style but keeps the meaning.

### BLOCKER
- **BLOCKER (verified)** | file: vv5_isolan/vv5_great_woodworking.json | node: iso_end, iso_rare | source: L2332 | problem: "Reward: modest Building experience for participating" is 10..20 on both builders, the same as the village victory. That contradicts "no village victory bonus". | fix: min 5, max 10 on both builders in both nodes.
- **BLOCKER (verified)** | file: vv5_isolan/vv5_great_woodworking.json | node: repair (ledger cuts on L2356 "a little practical" and L2357 "experience and") | source: L2356-2357 | problem: Shown owner text is cut as an "instruction". The player reads "The teams gain a great deal of respect..." without "a little practical experience and". | fix: Remove both cuts and show the full sentence. Keep the small Building effects with `src` L2356-2357.

### MAJOR
- **MAJOR** | vv5_isolan/vv5_great_woodworking.json | pool INT item 4 | L2268-2270 | problem: "it was SHOWN to them earlier" only makes sense after choice D (the technique exchange). | fix: `"if": {"visited": "exchange"}`.
- **MAJOR** | vv5_isolan/vv5_great_woodworking.json | pool B | L2170-2174 | problem: Bank B is defined but no node uses it, so its 4 owner items are never shown. | fix: Ask the owner where B goes, or record it as an approved unused bank.
- **MAJOR** | vv5_isolan/vv5_potluck_dispute.json | intro | L2419 | problem: "The visiting Isolan organizer prefers make a compromise". Every B item is a bare verb phrase that fits only "wants to". | fix: A grammar-fixes row for L2419, "prefers (B, different)" -> "prefers to (B, different)".
- **MAJOR** | vv5_isolan/vv5_potluck_dispute.json | pool END item 2 | L2477-2478, L2656 | problem: "without anyone having to declare a winner" can follow d1 or d2, where a winner was just declared. | fix: An `if` that excludes d1 and d2.
- **MAJOR** | vv5_isolan/vv5_great_laundry_mishap.json | pool END items 1, 3 | L2555-2559 | problem: "The item is returned" and "The owner is embarrassed but grateful" can follow w2 ("Nobody claims it") and f2/s2, where no owner is found. | fix: `if` conditions.
- **MAJOR** | vv5_isolan/vv5_field_day.json | pool END items 2, 3, 5 | L2634-2639, L2656 | problem: "The winners share their prize" and "The losing team practices" can follow a tie or no score. "Nobody can prove who won" can follow c1/c2, where a winner was just announced. | fix: `if` conditions.

### MINOR
- **MINOR** | vv5_isolan/vv5_great_woodworking.json | invite (ledger gap) | L2137 | problem: The "(Isolan leader)" name slot is cut. This is justified, but it should be listed for the owner. | fix: Owner packet.
- **MINOR** | vv5_isolan/vv5_great_woodworking.json | repair / tro_rare | L2370-2376 | problem: The repair round never gets the rare ending, and RARE item 2 ("the winning team") can follow a tie. | fix: Owner question; optional `if`.
- **MINOR** | vv5_isolan/vv5_great_woodworking.json | judge, INT item 8 | L2152, L2280 | problem: "the judge" and "the judges" mixed with a JUDGE pool of single and plural judges. | fix: Add L2280 to the existing L2152 owner question.
- **MINOR** | vv5_isolan/vv5_great_laundry_mishap.json | pool END | L2554, L2660-2661 | problem: The notes say absurd endings should be rare, but all five are equal. | fix: Owner question.
- **MINOR** | vv5_isolan/vv5_field_day.json | c4 | L2604 | problem: "drops the coconut" appears whatever game was drawn. | fix: Owner question (UNCONFIRMED whether a pool-item condition exists).
- **MINOR** | vv5_isolan/vv5_field_day.json | end | L2643 | problem: The "relevant" skill is a random choice of Building, Research or Devotion, given to a villager the text never names. | fix: Acceptable under G7; owner may prefer text-only.

---

## Top BLOCKERs (fix first)

1. **Cooking Contest:** innocent cooks are punished "for sabotage", with lasting dislikes, after an honest-mistake investigation (f14 -> six).
2. **Cooking Contest:** a confirmed saboteur can enter the rivalry showdown and win large food plus Farming 100 (a1_26opt does not exclude sab1/sab2).
3. **Cooking Contest:** the owner's "is...." dramatic pause is removed by a non-glaring "grammar fix" (L104).
4. **Cooking Contest V13-A B5:** the Research gain goes to the visiting judge instead of the elder.
5. **"Modest" written as normal size** in four places: Woodworking (iso_end/iso_rare), Hut Sharing m1, Breadfruit end food, Doctors' Dilemma after_tech.
6. **Woodworking repair:** the shown owner text "a little practical experience and" is cut.
7. **Storytelling:** VV5 winners get Research instead of Devotion half the time.
8. **Beautification:** a Building gain is paid on a hidden coin flip, including after "no repair".
