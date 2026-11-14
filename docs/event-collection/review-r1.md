# Isola Grand Event Collection: independent cross-review r1

Reviewer: independent agent (did not author these files). Branch reviewed: `origin/feat/97-coll-content4` at
`292227728` (already merges content2). Nothing in `data/event_collection/` was edited.

Scope: source lines 3520-6836 (V8, V9, V10, V11 and the V8/V9/V10 coda pools in `shared_pools.json`) and 8490-10571
(V18, V20, V21, V22, V23, V24, the `v20_relics` and `v26_*` pools). 66 event files.

Method:
- Every source span in scope was read and the choice counts, outcome counts, rarity words, bank sizes, effects and
  game variants were re-derived from the source, then compared with the file.
- `scripts/collection_check.py` was run on every file, one file per process (2 at a time), and
  `tests/test_event_collection_files.py` once in its own process.
- `vv_cie_graph.simulate()` was run on 5 distinct paths per listed game for every file (random answers, random sexes,
  tribe "Kalahuna"), and the expanded popups were read and scanned for broken text.
- Every harmful effect (kill, vanish, health loss, skill loss) was checked against its role's protection.

Results of the tools:
- `collection_check.py`: 70 files OK, 3 fail (`all_impossible_invention`, `all_unlikely_advisor`, `all_v20_r2_relic_trial`).
- `tests/test_event_collection_files.py`: 1 failed, 36 passed. The failure is `all_v20_r2_relic_trial.json`
  (not in `KNOWN_GAPS`).

Counts: **4 BLOCKER, 19 MAJOR, 13 MINOR.**

No protected-villager violation was found: every role that can be killed, vanished or lose health or skill is
`protected: auto` and none is a special role; the Golden Child, VV3 Chief and nursing parents appear only in harmless
roles (`vv3_chief_and_the_pearl` chief, `vv1_last_song_before_sunset` and `vv5_little_things_remember` nursing parent).
Every grammar fix used in scope is listed in `grammar-fixes.md` (the test passes).

---

## BLOCKER

### B1. `v20/all_v20_r2_relic_trial.json`, node `intro`, choices 2 and 3 (L9266, L9276)
- **What is wrong:** the labels `CONFINE (ACCUSED) IN A GUARDED SHELTER` and `DEFEND (ACCUSED) PUBLICLY` run off the
  screen with the longest names in VV1-VV4 (16 checker problems, up to 1057 of 768 px). `collection_check.py` fails and
  `tests/test_event_collection_files.py::test_every_file_passes` fails on the branch head; this file is not in
  `KNOWN_GAPS`.
- **Fix:** give it the same treatment the lead chooses for GAP-LABEL-NAME (impossible invention, unlikely advisor). Do
  not silence it by adding it to `KNOWN_GAPS` without the lead's decision.

### B2. Rare outcomes have normal weight (V22)
- `v22/all_v22_1_drawing_contest.json` `set_c` -> `c3` "The Picture That Changed" (L9608-9610, "Rare supernatural
  mystery").
- `v22/all_v22_3_potion_making.json` `set_b` -> `b4` "The Impossible Result" (L9741-9743, "rare supernatural mystery"),
  `set_e` -> `e2` "The Potion of Hiccups" (L9773, "A rare comic magical mishap"), `set_e` -> `e3` "The Temporary
  Transformation" (L9775, "A rare magical potion").
- **What is wrong:** decision Q4 / authoring rule 8: "rare" = weight 5 against 20. These children have no weight, so
  they are as likely as the ordinary outcomes. (V23 and V24 apply rarity correctly.)
- **Fix:** `"weight": 5, "rarity": "rare"` on those children and `"weight": 20` on their siblings.

### B3. `v24/all_v24_revolutionary.json`: the Discovery opening and the title rule are lost (L10149-10157, L10178-10185)
- **What is wrong:** the owner's title rule says each run is titled THE REVOLUTIONARY INVENTION or THE REVOLUTIONARY
  DISCOVERY by its central action, and "Neither title is a placeholder for the other." The file always uses the
  Invention title and the Invention opening; the Discovery opening (L10178-10185, with its
  `[beach / forest / ... / night sky]` pick) is cut by a ledger `note` that says "GAP ... lead to decide", while the
  authoring rules require kind `gap`. Discovery subjects such as A NEW RULE OF NATURE (L10229), AN UNUSUAL CRYSTAL,
  A COLOR-CHANGING LIQUID, THE NEW GEOMETRY, THE BETTER CALENDAR and THE IMPOSSIBLE PROOF are therefore shown under the
  wrong title and opening. The commit message calls this a placeholder.
- **Fix:** split the subject bank into invention and discovery subjects behind a first silent branch, with two openings.
  The title needs either a per-run title (a format change for the lead) or two event files with the bank split between
  them. At minimum, change the ledger entry to kind `gap` and list it for the owner.

### B4. V20 relic events: the game-specific relic variants are not shipped (L9332-9341)
- **Files:** `v20/all_v20_r1_should_not_exist.json`, `all_v20_r2_relic_trial.json`, `all_v20_r3_isola_discovered.json`,
  `all_v20_r4_relic_outlived.json`.
- **What is wrong:** the owner's "GAME-SPECIFIC RELIC VARIANTS" are filed by the manifest as a notes row
  (`notes_v20_relic_variants_codas`) and never shown. They are VV1 (the Golden Child recognizes a function), VV2 (a Lost
  Child), VV3 (the Tribal Chief, magicians, naturalists), VV4 (Tree of Life roots) and VV5 (villagers and
  Heathens/Isolans). These are per-game variants of these events, and the parallel V21 block was shipped as variants in
  `all_v21_c3_crafts_fair`. That is owner text lost, and it is handled differently from V21.
- **Fix:** add `variants` with `if: {game: [n]}` on `all_v20_r1_should_not_exist` `intro`, and on R2/R3 where they fit.
  The VV1 Golden Child and VV3 Chief go in harmless special roles or stay text. Or have the owner confirm that the block
  is author guidance only.

---

## MAJOR

### M1. Continuity: later beats name things an earlier draw did not produce (V8 L3533-3537, V9 L5326)
- `v8/vv2_packed_hospital.json` pool `STRAW` items L3874-3875 ("the missing inventory ledger") and L3876-3877 ("the
  missing spoon") are drawn whatever pool `A` drew; L3878-3879 ("The elder's carved sign") is drawn even when the elder
  never offered a sign (`ELDER` L3862-3863).
- `v8/vv3_unfortunate_portrait.json`: `REVISION` L3986-3987 ("the hat really was a bit much"), `EXPLAIN` L4000-4002
  (nose) and `END` L4018-4019 ("even if the nose is unforgivable") are drawn whatever `A` drew. `END` L4013-4014 (the
  portrait hangs) can follow `DECISION` L4007-4008 (declines to display it).
- `v8/vv1_last_song_before_sunset.json`: `END` L3798-3799 ("the new crab verse") is drawn without `DEV` L3783-3784.
- `v9/vv4_arbor_day_festival.json`: `JUDGING` L5006 (slug-slime exhibit) and L5007-5008 (guano) ignore the drawn
  materials, and `END` L5032 ("the wooden snail sculpture") is drawn without `PARADE` L5020.
- **Fix:** make the earlier bank a branch (one node per item) and give the dependent items `if: {visited: ...}`, as
  `vv5_little_things_remember` and `all_v24_revolutionary` already do.

### M2. Codas use random-sex strangers for the event's own characters (shared pools `v8_c2`, `v8_c4`, `v8_c16`, `v9_r7`, `v9_r13`, `v9_r18`, ...)
- **What is wrong:** the coda items bind their pronouns to `coda1` / `coda2`, which are strangers of random sex. When a
  coda speaks of "the child", "the elder" or "the accused", the player reads it as the event's named character, whose
  sex is known. Simulated: `vv1_masters_small_apprentice` with elder Keo (m) and coda `v8_c16` gives "An elder watches a
  child demonstrate a skill **she** once taught"; with child Tala (f), `v8_c2` can give "The child ... says **he** is
  still upset"; in `vv1_the_wall`, `v9_r7` "the accusation has cost **him/her** a friendship" does not follow the
  accused villager (Friend).
- **Fix:** in events where the coda's figure is an event role, bind the coda's pronouns to that role. This can be an
  event-local mirror of the coda pool, as rule 10 does with `mirror_of`, or an alias. Otherwise drop those codas from
  that event's list.

### M3. Codas are not conditioned on the path (decision Q13: "drawn equally from the bank's items whose conditions fit")
- **Files:** every v8, v9 and v10 event file, and the V18, V21 and V22 files that use the V8 codas. Only
  `all_unlikely_advisor` conditions its codas.
- **Examples:** `vv1_missing_pearl` appends `v9_r20` (L5297-5299, "The supposed victim admits staging the disappearance
  ... apologizing to those falsely accused") after "The pearl was moved by the elder and forgotten". `vv1_the_wall`
  appends `v9_r13` ("The culprit's punishment is to rebuild the object he destroyed") after "Nothing is conclusive".
  `all_no_good_very_bad_day` appends `v10_o29` ("why they are laughing at someone") on paths where nobody laughs.
  `all_v21_c1_potters_trial` and `all_v18_*` can append `v8_c8` (a rival "has knowingly cheated ... The result is
  corrected") or `v8_c9` (the judges announce the wrong winner) after outcomes with no cheating and no winner.
- **Fix:** add `if: {visited: [...]}` on each `coda_pick` child, listing the outcome pages it fits.

### M4. V8 codas are used outside V8 (decision Q13)
- **Files:** all 13 `v18/*` files, `v21/all_v21_c1_potters_trial`, `v21/all_v21_c3_crafts_fair`,
  `v22/all_v22_1_drawing_contest`, `all_v22_2_strength_trials`, `all_v22_3_potion_making`.
- **What is wrong:** Q13 makes the coda banks "optional end pools for the events of their own section". V21 and V22 have
  their own owner codas (L9538-9547, L9952-9964), which are not shipped, while V8's codas are attached instead
  (L9408 "Choose a fitting reputation coda" is the only cue).
- **Fix:** ask the lead whether cross-section codas are intended. If not, remove them, or use V21's and V22's own codas
  where they are not long-term state.

### M5. V11: a sentence is split across two popups (mid-sentence popup breaks)
- `v11/all_council_of_conundrums.json` `a5` "Most proposals fail," / `a5_2` (L6716); `b1` / `b1_2` (L6724-6727); `b2` (L6731-6735)
  "...Unfortunately," / `b2_2`; `b6` "By sunset," / `b6_2` (L6764).
- `v11/all_invention_showcase.json` `a2` (L6468-6473), `a4` "While trying to repair it," / `a4_2` (L6485), `a8` (L6521-6526),
  `b7` "After hours of arguing," (L6583-6587), `c2` (L6601-6606), `c3` "(Subject) begins with the history of coconuts," (L6610).
- `v11/all_secret_of_life.json` `a2` "Beneath it stands a figure of clay," (L6191-6196), `a4` "The experiment fails,"
  (L6210-6215), `a5` "At the decisive moment," (L6219-6225), `b2` "(Friend) explains that curiosity is welcome," (L6247-6252).
- **What is wrong:** each first page is a new popup with OK, so the player sees a popup holding three words ending in a
  comma, and the next popup starts in lower case ("but the villagers learn ..."), as simulated.
- **Fix:** split at a sentence boundary. If an outcome is too long for one page, split it after a full stop; never
  mid-sentence. Where the whole outcome fits, use one page.

### M6. Popups that hold only an outcome's heading
- `v20/all_v20_r1_should_not_exist.json` `a3` "The Destruction That Saved Them:" (L9216) and `d2` "The Second
  Discoverer:" (L9245); `v22/all_v22_1_drawing_contest.json` `b3` "The Accidental Insult:".
- **What is wrong:** the heading is a whole popup on its own (simulated P2 / P3), and the body comes in the next one.
- **Fix:** put the heading on the body's page (`a3_2`, `d2_2`, `b3_2`) and drop the stub.

### M7. `v22/all_v22_1_drawing_contest.json` nodes `intro` and `question`: the question is shown twice (L9573)
- **What is wrong:** `intro` includes L9573 "WHAT SHOULD (ARTIST) DRAW?" and `question` repeats it, so the player reads
  "WHAT SHOULD BO DRAW?" at the end of popup 1 and again as popup 2.
- **Fix:** remove L9573 from `intro`'s text and `src`.

### M8. `v22/all_v22_1_drawing_contest.json` node `a3`: a paragraph starts in lower case (L9582-9584)
- **What is wrong:** after the ledger cut "Gain exploration progress or a modest Tech reward;", the page shows
  "the contest result is disputed." as its own lower-case paragraph.
- **Fix:** keep the remainder on the first paragraph's line ("... through the island; the contest result is
  disputed."), or list a fix that capitalises "The".

### M9. `v21/all_v21_c3_crafts_fair.json` node `intro` variants: author guidance shown as story (L9517-9536)
- **What is wrong:** the "GAME-SPECIFIC ADAPTATIONS" are shown word for word.
  - VV1: "The Golden Child **may** make ... or solve ...". The "may" is designer voice.
  - VV2: "A competition **may** honor the founders, the totems, or the Great Falls".
  - VV4: "the villagers **must choose** preservation or artistic ambition", but no such choice is offered.
  - VV5: "Villagers and **Heathens/Isolans** can enter as ...". The slash pair is a note to the author, and V9 L4505 and
    V10 L5352 say VV5 narrative uses ISOLANS.
  - VV3: L9526-9527 ("Magicians and naturalists may create competing works ...") is cut as a designer rule, although its
    first sentence is setting.
- **Fix:** have the owner decide whether these blocks are display text. If they are, they need owner-approved wording,
  or they go behind a choice (VV4).

### M10. `v18/all_v18_isolan_decathlon.json`, nodes `intro` and `d3` (L8886-8888, L8893)
- **What is wrong:** the intro shows the designer description "An **optional** multi-discipline festival combines ten
  randomly selected trials from **the twelve events above**." `d3` shows "A mixed **VV5** team wins" to the player and
  is limited to VV5.
- **Fix:** ledger the designer framing as a note and ask the owner for display text. For `d3`, ask the owner (the game
  label cannot be shown).

### M11. `v8/vv4_fruity_masterpiece.json` pool `ART` item L4121-4122
- **What is wrong:** the child's playful title "the Chief of Breadfruit" becomes `{@chief} of Breadfruit`, which reads
  "insists **the village leader of Breadfruit** must be addressed properly". That is not a joke and is not what the
  owner meant: it is a child's invented title, not the village leader.
- **Fix:** have the owner choose: allow the literal "the Chief of Breadfruit" as a title (a checker exception), or reword.

### M12. V20 crises: a villager dies who is never named
- `all_v20_d2_no_such_treatment` `a3`, `b3` (L8976, L8981); `all_v20_d3_experimental_cure` `a4` (L8991);
  `all_v20_d5_last_dose` `b2` (two deaths, L9024); `all_v20_d6_physician_refused` `a2` (L9034);
  `all_v20_d11_ancient_oath` `a2` (L9073); `all_v20_d12_cannot_save_all` `a2` (L9082).
- **What is wrong:** the `patient` role is cast but no text names it, so "The patient dies" kills a random adult whom
  the player was never shown. The V8 safety filter says "Only after eligibility is established may the event name its
  target" (L4458, L4462).
- **Fix:** confirm that the kill path itself announces the villager (UNCONFIRMED in this review). If it does not, ask
  the owner to allow the `(patient)` name in these lines.

### M13. `v20/all_v20_d5_last_dose.json` `a3` and `c2`: the effect does not follow the story (L9021, L9028)
- **What is wrong:** `a3` "The medicine fails, and the physicians grieve." implies the treated patient dies, and `c2`
  "The expedition returns too late." implies a death or decline. Neither page has an effect.
- **Fix:** have the owner choose. Give `a3` a kill on `patient` and `c2` a health loss on `patient`, or record a
  `text_only` reason.

### M14. `v11/all_council_of_conundrums.json` `a3_2` and `c3_2`: the reward goes to the wrong villager (L6700-6705, L6787-6793)
- **What is wrong:** the child (a3) and "a shy villager" (c3) do the work, but the Farming/Research and Building/Healing
  experience goes to `(Subject)`, the council's founder. The source adds "child not assigned adult labor" and puts the
  reward on that outcome.
- **Fix:** cast the child as a child villager role and the shy villager as a villager role (both harmless), and give
  them the skill.

### M15. V9: the editorial weighting is not applied (L5323-5325)
- **What is wrong:** "Random choices should be weighted: ordinary, funny and tender outcomes common; violent
  confrontations, severe betrayal and custody rare." Every V9 split is equal. Examples: `vv1_the_wall` `h4` (L4634) and
  the sabotage route `i4`; `vv2_stolen_spoon` trial items L4841-4842; `vv5_trial_shattered_pearls` intentional damage
  L5164, L5176, L5186; `vv4_rotten_structure` L5052, L5058.
- **Fix:** weight those children `rare` (5 against 20). This is the source's own odds, so rule 8's "no odds" default
  does not apply.

### M16. `v20/all_v20_r4_relic_outlived.json` role `first` (L9314-9315)
- **What is wrong:** "Years or generations after **Bo** first found the object, **Tala** discovers it again. The
  original discoverer may now be elderly or dead." Both are any living adults (`min_age` 14), possibly the same age.
- **Fix:** give `first` an elder age (`min_age` 55 as the other files use).

### M17. The `v26_*` shared pools are not used by any event (decision Q13, L10432-10571)
- **What is wrong:** Q13 says "V26 materials become a shared pool used where events say 'material'", and V26 itself
  says it applies to existing events ("Do not default repeatedly to slugs, snail shells, or decaying timber", L10446).
  The pools exist in `shared_pools.json`, but `include_pools` lists none of them anywhere (`grep v26_` finds only the
  manifest).
- **Fix:** ask the lead which events draw from V26 (for example V9's `(MATERIAL)` mixing in `v26_building` and
  `v26_specimens`), or record that V26 is deferred.

### M18. Owner banks and adaptations not used, and handled differently in different sections
- V9 texture, smell, why, complication and reaction banks (L4541-4593: 5 banks, about 60 items) are in
  `bank_v9_materials` but are drawn by no event.
- V20 optional codas P1-P8 (L9343-9352); V21 long-term codas (L9538-9547); V22 cross-game adaptations and codas
  (L9932-9964); V23 cross-game notes (L10119-10126); V18 game-specific festival framing (L8509-8521).
- **What is wrong:** they are filed as notes rows, while V21's adaptations were shipped as display text (M9). The owner
  has not decided which of these are display text.
- **Fix:** list them in the owner packet as not shipped, with the reason, and apply one rule to all sections.

### M19. Pinned GAP-LABEL-NAME labels still run off the screen
- `v10/all_impossible_invention.json` `question` "TELL (SUBJECT) TO STOP BEFORE ANYONE IS HURT." (L5546), up to 1140
  of 768 px; `v10/all_unlikely_advisor.json` "INVITE (SUBJECT) TO SPEAK." (L5628), 886 of 768 px.
- **What is wrong:** the labels are pinned in `KNOWN_GAPS`, but they are still unreadable in VV1-VV4 with long names.
  They need a decision before release.

---

## MINOR

1. **Pages with no closing punctuation.** `all_v20_d6`-`d12` and `d9` outcome pages ("The patient recovers", "It
   works", ...; L9034-9087), `all_teacher_who_failed` ("The lesson goes wrong when: ... notes"), `all_v24_revolutionary`
   REACT "CHIEF SCHOLAR: ... reputation" (L10372), `all_v23_1_practical_joke` ("The Prank War: ... retaliation"). Fix:
   list a full-stop fix per line in `grammar-fixes.md`.
2. **The relic line is a bare fragment.** `all_v20_r1` / `all_v20_r4` `intro` `{v20_relics}`: it is appended as its own
   paragraph ("A sealed cylinder marked with unknown symbols", L9191-9202) with no sentence around it. Fix: keep the
   source's full stop in the pool items.
3. **V21 C2 grammar fixes L9434 and L9453 change the owner's words although a stranger role would not.** "The subject
   recognizes (subject.himself/herself)" and "forgive (helper.him/her)" keep the owner's text. Fix: have the owner
   choose; the current fixes are listed and lead-approved.
4. **`v9/vv4_rotten_structure.json` `collapse` damage is `min 50, max 100`.** G9 makes "collapses" = `size: huge`
   (75-100) (L5039).
5. **`v8/vv4_quiet_gardener.json` `END` L4190 "The elder gives the child a seed"** while `young` is `min_age` 14. Fix:
   allow a child or accept.
6. **`v8/vv5_little_things_remember.json`:** "A former Heathen-born villager" (L4281) is any believer, and the `A`
   items "gray in his/her hair", "a skilled healer" and "a child who looks just like him/her" (L4290-4292) are not tied
   to age, skill or children. Fix: add conditions where the format allows.
7. **`v20/all_v20_between_life_and_death.json`:** `healer` needs Healing 1+ and is not optional, so a village with no
   healer never gets the event. Survivors "with lasting weakness" (`a2`, `b3`, `c3`, `e2`, `g2`) lose no health. Fix:
   make `healer` optional (the `a1` skill is then skipped) and consider a small health loss.
8. **`v24/all_v24_revolutionary.json` "relevant skill" (L10296, L10302, L10345)** is a random pick from five skills
   including Parenting, whatever the subject. Fix: tie the skill to the subject group.
9. **`v26_food` / `v26_healing` items carry the author's qualifiers or a capital from the sentence start:**
   "ocean water used only in appropriate cooking processes", "rice where available", "wild mushrooms identified as
   safe", "crushed ice or snow in exceptional settings", "Breadfruit flour", "Clean cloth", "Fallen timber", "Sulfur",
   "Barkcloth". This matters once M17 is resolved.
10. **Outcomes that read as harm but have no effect:** `all_v20_d3` `a2` "others develop troubling complications"
    (L8989), `all_v20_d6` `b2` "The procedure fails" (L9036), `all_v20_d11` `b2` "It fails" (L9075). Consider a small
    health loss on `patient` or a `text_only` reason.
11. **`all_v24_revolutionary` REACT "CHIEF SCHOLAR" is shown in VV1, VV2, VV4 and VV5.** It is a scholarly title, not
    the tribal Chief, but the checker does not catch it because it is upper case. Owner awareness only.
12. **`v23/all_v23_4_missing_coconuts.json` `intro` "Several coconuts disappear from the food stores"** (L10063) has
    no food loss. Consider a small loss or a `text_only` reason.
13. **`v8/vv4_fruity_masterpiece.json` `END` L4142-4143 "The breadfruit sculpture is displayed"** but no path makes a
    sculpture (the source's continuity). Owner question.

---

## Verified as correct (spot list)

- Choice counts and labels match the source in every file reviewed: V20 BLD 7 (B and C limited to VV3-VV5), D1-D12,
  R1-R3, V21 C1-C3, V22-1 to V22-4, V23-1 to V23-6, V24 5, and all V8, V9, V10 and V11 events. Bank sizes match the
  manifest (the checker passes).
- Rarity is correct in BLD F2 (exceptionally rare), V23-3 C4 (exceptionally rare), V23-5 C4 (very rare) and V24 C3/C5.
- D1 is text only, with the patient as an uncast stranger, as Q11 requires. R2 B4 "flees into the forest" is a vanish
  on a protected-auto role. R3 A4 is a food loss. Tech sizes ("modest" = small, "large" = large) match.
- VV3-only Magician/Naturalist text is gated (`great_appointment_scandal` pool `A` `if game 3-5`; BLD B and C).
