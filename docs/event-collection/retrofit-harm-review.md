# V28 retrofit: harm review (for the owner's approval)

The owner's rule (2026-11-14): only VV2 totems are always protected. Nursing mothers, babies, the Golden Child and the
VV3 Chief may be harmed only where the event's own risk makes sense, with `protected: "allow"` on that role, and every
such case is listed here: the event, the outcome, the villager, the exact text and why. VV5 story villagers (the
chief, the Retired Chief, the puzzles' Heathens) stay unharmable whatever a file says.

`python scripts/collection_check.py --allow-report` lists every `allow` on a harm-capable role for checking against
this file.

## Part A

Range: `original/`, `universal/`, `v6/`, `vv5_isolan/`, `v8/`, `v9/`, `v10/`, `v11/` (51 events).

**No entries.** The Part A retrofit adds no `protected: "allow"` and no harm to a nursing parent, a baby, the Golden
Child or the VV3 Chief.

- The one harmful effect added in Part A is the serious-injury `health_change` on The Doctors' Dilemma's patient
  (outcome "lasting effects", L1609-1610). That role keeps the default `protected: "auto"`, so nursing parents, the
  Golden Child and the VV3 Chief are never cast as the patient.
- The special villagers this range already casts take only harmless effects: The Last Song Before Sunset's nursing
  parent gains a little Parenting (no `allow` needed for a gain); The Lullaby, The Child of Legend, The Chief's
  Monumental Speech, The Chief and the Pearl and The Little Things They Remember are unchanged.

## Part B

One event in Part B's range harms a protected villager. Everything else Part B added harms no special villager:
the Golden Child scenes (V14), the Chief's events and contests (exclusive, V17) and the V27 baby events stay
harmless, and every other harm-capable role keeps the default `auto` protection (nursing parents, the Golden Child
and the Tribal Chief are never cast in it).

### Two Lives, One Decision (`all_v20_d1_two_lives`, V20 D1, source L8950-8968; since 2026-11-15 the Living Engine file L8957-9056)

- **Villager:** role `mother`, a female villager carrying a baby (special `nursing_parent`, `protected: "allow"`).
  Before the retrofit the patient was an uncast stranger (decision Q11), so nothing happened to anyone.
- **Why:** the whole event is about this risk: "A pregnant villager lies gravely ill; the healers fear for both
  mother and unborn child." The V28 addendum asks for exactly this case ("A nursing mother may lose her baby through
  illness, accident, or another event-specific tragedy"; "both may die only if the event truly endangers both").
  Every effect follows an outcome the owner wrote. The three deaths (A3, A4, B4) are very rare (2 against a normal
  20; the source gives no odds), per V28's global rule; the other outcomes keep equal weight.
- **Requirement:** the event is now drawn only when a villager is carrying a baby.

| Outcome | Exact text | Effect | Chance |
|---|---|---|---|
| A2 | "The mother survives but the child dies; a solemn mourning follows." | `baby_lost` (the pregnancy ends; the Births and Conceptions log records "Lost before birth") | 20 of 64 in choice A |
| A3 | "The child survives but the mother dies; the family remembers her courage." | `birth_then_die`, cause Unknown causes (the game's own delivery brings the baby now, early if need be; then she dies with a grave) | very rare: 2 of 64 in choice A |
| A4 | "Neither survives; the healer questions whether the decision was right." | `kill`, cause Unknown causes (the baby she carries is lost with her) | very rare: 2 of 64 in choice A |
| A5 | "Both survive, though the mother requires prolonged care." | `health_change` -30..-10 | 20 of 64 in choice A |
| B2 | "The mother survives but loses the baby." | `baby_lost` | 20 of 62 in choice B |
| B3 | "The condition worsens, demanding a desperate intervention." | `health_change` -30..-10 | 20 of 62 in choice B |
| B4 | "Both die; villagers disagree about whether waiting was a mistake." | `kill`, cause Unknown causes (and the baby) | very rare: 2 of 62 in choice B |
| C2 | "She chooses gentler care; her recovery is prolonged and uncertain." | `health_change` -30..-10 | 1 in 3 of choice C |

- **Done:** A3, "The child survives but the mother dies; the family remembers her courage." **Owner (2026-11-14):** A3 must change so the child really survives. It now uses the `birth_then_die` effect (cie-v6-binary.md 23): the game's own delivery brings the baby, then the mother dies; very rare, as a death.
- **Owner decision (2026-11-14): APPROVED as built** -- the cast pregnant villager, `baby_lost` and the very rare kills; A3's `birth_then_die` is approved with the rest of D1.

#### The owner's added outcomes (2026-11-15): A6-A15, B5-B14, C4-C37

The owner's newer copy of D1 is in the Living Event Engine file (`Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt`
L8957-9056, frozen): the same A1-A5, B1-B4 and C1-C3, word for word, with 54 outcomes added. The event now reads
that file (its V28 lines are the notes row `notes_v20_d1_v28`); every source line below is that file's.

- **Villager:** role `parent` (was `mother`): a villager 18 or older of EITHER sex carrying a baby (special
  `nursing_parent`, `protected: "allow"`). The owner's rules (2026-11-15): men can carry babies, so "mother" becomes
  "father" for a man (sex-aware role words `(parent.mother/father)`, `(parent.he/she)`, `(parent.his/her)`,
  `(parent.son/daughter)`; each change is a `sensitivity` ledger entry, the owner's sentences otherwise unchanged), and
  children are never cast as a carrying parent.
- **Wording (Q09):** "the baby is stillborn" (B9, C8) is shown as "the baby is born without signs of life", and "the
  pregnancy ends in miscarriage" (C20) as "the pregnancy ends in loss" (Q02 lists both words as hint only).
- **Effects:** a premature birth where both live is the new `deliver_early` (cie-v6-binary.md 30: the game's own birth
  now, the baby younger and weaker the earlier it is, the parent lives); a frail newborn ("very frail", "significant /
  lasting / serious health challenges", "fragile health", "born frail") loses -30..-10 health more, "dangerously low"
  -50..-30; a premature birth and the parent's death is `birth_then_die`; a stillbirth, a loss, an ended pregnancy,
  and a baby who dies soon after the birth are `baby_lost` (the game cannot show a baby that is born and then dies:
  a nursing baby is the parent's own state until birth); the parent's long or uncertain recovery is `health_change`
  -30..-10 ("dangerously weak", "collapse": -50..-30); "neither survives" and the parent's death are `kill`
  (Unknown causes). "Born healthy" (A11, B10, C9, C27) and the decisions with no harm (C17, C23, C37) change nothing.
- **Chances (the lead's brief and V28's global rule; the source gives no odds):** deaths very rare (2), serious harm
  -- a lost baby, a frail newborn -- rare (5), a premature birth both survive occasional (10), harmless outcomes 20.
  A baby who dies soon after its birth (A10, B11, C11) counts as a death: very rare (2). The original outcomes keep
  the weights the owner approved on 2026-11-14 (A2 and B2's `baby_lost` stay 20; C1-C3 now carry 20 each).
- **Held for the owner:** C38-C52 (the family's part in the decision) are in the source span as a ledger note, not
  built in this pass.

| Outcome | Exact text (as shown) | Effect | Chance |
|---|---|---|---|
| A6 | "Both survive a premature birth; the baby is small and weak but begins to recover." | `deliver_early` | occasional: 10 of 128 in choice A |
| A7 | "The baby is born prematurely and survives, but the (parent.mother/father) dies; the family mourns (parent.his/her) loss." | `birth_then_die`, cause Unknown causes | very rare: 2 of 128 in choice A |
| A8 | "The (parent.mother/father) survives, but the baby is born without life; the family grieves together." | `baby_lost` | rare: 5 of 128 in choice A |
| A9 | "Both survive, though the premature baby is very frail and faces an uncertain recovery." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 128 in choice A |
| A10 | "The (parent.mother/father) survives a difficult birth, but the premature baby dies shortly afterward." | `baby_lost` | very rare: 2 of 128 in choice A |
| A11 | "Both survive; the baby is born healthy despite the danger." | none (told) | 20 of 128 in choice A |
| A12 | "The (parent.mother/father) survives, but the pregnancy ends in loss before the baby can be born." | `baby_lost` | rare: 5 of 128 in choice A |
| A13 | "Both survive, though the newborn begins life with significant health challenges and requires prolonged care." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 128 in choice A |
| A14 | "The baby survives with lasting health difficulties; the family welcomes the child with love." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 128 in choice A |
| A15 | "The (parent.mother/father) survives, but the baby is born sleeping; the village holds a quiet remembrance." | `baby_lost` | rare: 5 of 128 in choice A |
| B5 | "The baby arrives earlier than expected; both survive, though the newborn is small and needs extra care." | `deliver_early` | occasional: 10 of 126 in choice B |
| B6 | "The (parent.mother/father) survives, but the pregnancy ends unexpectedly in loss; the family mourns the child they had hoped to meet." | `baby_lost` | rare: 5 of 126 in choice B |
| B7 | "Both survive, though the baby is born frail and struggles to regain strength." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 126 in choice B |
| B8 | "The baby is born prematurely and survives, but the (parent.mother/father) dies after the birth." | `birth_then_die`, cause Unknown causes | very rare: 2 of 126 in choice B |
| B9 | "The (parent.mother/father) survives, but the baby is born without signs of life; the family gathers to grieve." | `baby_lost` | rare: 5 of 126 in choice B |
| B10 | "Both survive, and the baby is born healthy despite the healers' fears." | none (told) | 20 of 126 in choice B |
| B11 | "The premature baby survives the birth but dies soon afterward; the (parent.mother/father) and family mourn." | `baby_lost` | very rare: 2 of 126 in choice B |
| B12 | "The (parent.mother/father) survives, and the baby is born with lasting health challenges; the family embraces their newest member." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 126 in choice B |
| B13 | "Both survive, but the newborn's health remains dangerously low." | `deliver_early` (newborn -50..-30 health more) | rare: 5 of 126 in choice B |
| B14 | "The pregnancy ends in an early loss, and the (parent.mother/father) gradually recovers with the family's support." | `baby_lost`; `health_change` -30..-10 | rare: 5 of 126 in choice B |
| C4 | "(parent.He/She) chooses intervention; (parent.his/her) premature baby survives, though both require time to recover." | `deliver_early`; `health_change` -30..-10 | occasional: 10 of 289 in choice C |
| C5 | "(parent.He/She) chooses gentler care; the baby arrives early and frail but survives." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 289 in choice C |
| C6 | "(parent.He/She) chooses intervention; the baby survives, but (parent.he/she) dies after the birth." | `birth_then_die`, cause Unknown causes | very rare: 2 of 289 in choice C |
| C7 | "(parent.He/She) chooses gentler care; the pregnancy ends in loss, and the family honors (parent.his/her) decision." | `baby_lost` | rare: 5 of 289 in choice C |
| C8 | "(parent.He/She) chooses intervention; the baby is born without signs of life, but (parent.he/she) survives." | `baby_lost` | rare: 5 of 289 in choice C |
| C9 | "(parent.He/She) chooses gentler care; both survive, and the baby is born healthy." | none (told) | 20 of 289 in choice C |
| C10 | "(parent.He/She) chooses intervention; (parent.his/her) baby survives with serious health challenges and is welcomed with love." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 289 in choice C |
| C11 | "(parent.He/She) chooses gentler care; the premature baby survives briefly before dying, leaving the family grieving." | `baby_lost` | very rare: 2 of 289 in choice C |
| C12 | "(parent.He/She) chooses intervention; both survive, though the newborn begins life in fragile health." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 289 in choice C |
| C13 | "(parent.He/She) chooses gentler care; the baby is born prematurely and survives, but (parent.he/she) does not." | `birth_then_die`, cause Unknown causes | very rare: 2 of 289 in choice C |
| C14 | "(parent.He/She) chooses intervention; the pregnancy ends in loss, but (parent.he/she) survives." | `baby_lost` | rare: 5 of 289 in choice C |
| C15 | "(parent.He/She) chooses gentler care; the baby survives with lasting health difficulties, and the family celebrates the child's arrival." | `deliver_early` (newborn -30..-10 health more); `celebrate` (the village) | rare: 5 of 289 in choice C |
| C16 | "The healers offer to end the pregnancy to protect (parent.his/her) life; (parent.he/she) accepts with tears, and the family mourns the child." | `baby_lost` | rare: 5 of 289 in choice C |
| C17 | "(parent.He/She) refuses to end the pregnancy despite the danger; the healers respect (parent.his/her) wishes, and both survive." | none (told) | 20 of 289 in choice C |
| C18 | "(parent.He/She) refuses the procedure, but (parent.his/her) condition worsens; the baby survives a premature birth, while the (parent.mother/father) dies." | `birth_then_die`, cause Unknown causes | very rare: 2 of 289 in choice C |
| C19 | "(parent.He/She) accepts the procedure after learning that (parent.his/her) life is in danger; (parent.he/she) survives, though the loss weighs heavily upon (parent.him/her)." | `baby_lost` | rare: 5 of 289 in choice C |
| C20 | "(parent.He/She) declines the procedure and chooses continued care; the pregnancy ends in loss, and the family grieves." | `baby_lost` | rare: 5 of 289 in choice C |
| C21 | "(parent.He/She) accepts the procedure with (parent.his/her) family's support; (parent.his/her) recovery is gradual, and (parent.he/she) mourns the pregnancy (parent.he/she) had hoped to continue." | `baby_lost`; `health_change` -30..-10 | rare: 5 of 289 in choice C |
| C22 | "(parent.He/She) refuses the procedure despite the healers' concerns; both survive, though the baby is born prematurely and frail." | `deliver_early` (newborn -30..-10 health more) | rare: 5 of 289 in choice C |
| C23 | "(parent.He/She) asks for more time before deciding; the healers continue caring for (parent.him/her) while (parent.he/she) considers (parent.his/her) options." | none (told) | 20 of 289 in choice C |
| C24 | "(parent.He/She) accepts the procedure, believing it is (parent.his/her) only chance to survive; afterward, (parent.he/she) feels both relief and profound sadness." | `baby_lost` | rare: 5 of 289 in choice C |
| C25 | "(parent.He/She) refuses the procedure, hoping to save (parent.his/her) baby; neither survives, leaving the healers and family grieving." | `kill`, cause Unknown causes | very rare: 2 of 289 in choice C |
| C26 | "(parent.He/She) accepts the procedure but later struggles with (parent.his/her) decision; the healers offer compassion rather than judgment." | `baby_lost` | rare: 5 of 289 in choice C |
| C27 | "(parent.He/She) refuses the procedure, and (parent.his/her) condition unexpectedly improves; the baby is eventually born healthy." | none (told) | 20 of 289 in choice C |
| C28 | "(parent.He/She) agrees to end the pregnancy, but severe bleeding follows; despite the healers' efforts, (parent.he/she) dies." | `kill`, cause Unknown causes | very rare: 2 of 289 in choice C |
| C29 | "(parent.He/She) survives the procedure, but a fever develops several days later; the healers fear (parent.his/her) condition is worsening." | `baby_lost`; `health_change` -30..-10 | rare: 5 of 289 in choice C |
| C30 | "(parent.He/She) survives the procedure but remains dangerously weak; (parent.his/her) family takes turns watching over (parent.him/her)." | `baby_lost`; `health_change` -50..-30 | rare: 5 of 289 in choice C |
| C31 | "(parent.He/She) survives the procedure, but an infection threatens (parent.his/her) recovery; the healers struggle to save (parent.him/her)." | `baby_lost`; `health_change` -30..-10 | rare: 5 of 289 in choice C |
| C32 | "(parent.He/She) accepts the procedure and initially recovers, only to collapse days later; the family fears the worst." | `baby_lost`; `health_change` -50..-30 | rare: 5 of 289 in choice C |
| C33 | "(parent.He/She) survives the procedure and its complications, though (parent.his/her) recovery is long and difficult." | `baby_lost`; `health_change` -30..-10 | rare: 5 of 289 in choice C |
| C34 | "(parent.He/She) accepts the procedure, but the healers cannot control the bleeding; the family mourns both (parent.mother/father) and child." | `kill`, cause Unknown causes | very rare: 2 of 289 in choice C |
| C35 | "(parent.He/She) survives without serious physical complications, but grieves the pregnancy (parent.he/she) had hoped to continue." | `baby_lost` | rare: 5 of 289 in choice C |
| C36 | "(parent.His/Her) partner begs (parent.him/her) to continue the pregnancy, but (parent.he/she) chooses the procedure; the healers honor (parent.his/her) wishes." | `baby_lost` | rare: 5 of 289 in choice C |
| C37 | "(parent.His/Her) father pleads with (parent.him/her) to end the pregnancy, fearing he will lose his (parent.son/daughter); (parent.he/she) refuses, and the healers respect (parent.his/her) decision." | none (told) | 20 of 289 in choice C |

- **Owner decision:** pending (2026-11-15).

## Companion K5

Range: Companion Anthology Vol 1 Part 4 N051-N069 (`companion/c5/c5dn051`-`c5dn069`) and The Lives Between Legends
001-060 (`companion/lbl/lbl001`-`lbl060`), 79 events. Line numbers are the companion source's.

One event harms a protected villager. Every other harm-capable role in this range keeps the default `auto`
protection, so nursing parents, the Golden Child and the Tribal Chief are never cast in it: LBL 016's hurt
apprentice, 025's child who falls ill, 026's injured and missing teens, 027's child who falls and 059's straining
elder. The other baby scenes (LBL 037-040, 042, 045 and N057) cast a nursing parent only harmlessly (Parenting or
nothing), and 043's bereaved mother is a woman who is not nursing (the baby is text).

### The Sudden Fever (`lbl044_sudden_fever`, LBL 044, companion L4368-4378)

- **Villager:** role `mother`, a female villager carrying a baby (special `nursing_parent`, `protected: "allow"`).
  A nursing baby is its parent's state in every game, so the baby can be reached only through her.
- **Why:** the event is about the baby's illness, and the owner wrote its fatal branch: "A baby becomes ill during a
  difficult season." The engine rules say nursing mothers and infants "are not immune to plausible fatal events"
  (L3784). The mother herself is never hurt: only her baby is lost.
- **Requirement:** the event is drawn only when a villager is carrying a baby.

| Outcome | Exact text | Effect | Chance |
|---|---|---|---|
| 1 | "Prompt care brings recovery." | small Parenting to the mother | 20 of 45 |
| 2 | "The baby remains ill and needs ongoing attention." | small Parenting to the mother (the baby cannot be made `sick`: it is not a villager) | 20 of 45 |
| 3 | "A rare fatal outcome leaves the family mourning." | `baby_lost` (the pregnancy ends; the Births and Conceptions log records "Lost before birth") | rare: 5 of 45 (the source's own "rare") |

## Companion K6

Range: The Lives Between Legends 061-120 (`companion/lbl/lbl061`-`lbl120`), 60 events, generator
`scripts/companion/gen_k6.py`. Line numbers are the companion source's.

**No entries.** No role in this range uses `protected: "allow"`. The harm-capable roles keep the default `auto`
protection, so nursing parents, the Golden Child and the Tribal Chief are never cast in them:

| Event | Outcome | Villager | Exact text | Effect | Chance |
|---|---|---|---|---|---|
| The Bottomless Pool (`lbl073_bottomless_pool`, L4753-4767) | 2 | `explorer` | "A dangerous dive causes injury." | `health_change` -30..-10 | occasional: 10 of 35 |
| The Bottomless Pool | 3 | `explorer` | "The explorer disappears and an uncertain search begins." | `vanish` (missing is not dead: no grave) | rare: 5 of 35 |
| The Dangerous Proof (`lbl082_dangerous_proof`, L4874-4884) | 3 | `teen` | "They are injured and must confront their recklessness." | `health_change` -30..-10 | occasional: 10 of 50 |

## Companion K8

Range: Stone, Spirit, Strangers & Ordinary Lives 001-067 (`companion/sss/sss001`-`sss067`), 67 events. Line numbers
are the companion source's. Generator: `scripts/companion/gen_k8.py`.

**No entries.** K8 adds no `protected: "allow"` and no harm to a nursing parent, a baby, the Golden Child or the VV3
Chief.

- The harm-capable roles keep the default `auto` protection, so nursing parents, the Golden Child and the Tribal
  Chief are never cast in them: SSS 018's worker (a serious injury or a death in the collapse) and SSS 020's worker
  (sick from the mineral dust).
- SSS 053's baby scene casts a nursing parent harmlessly (no effect).
- SSS 065 The Nursing Mother's Loss: the infant has already died, as part of the premise (the lead, 2026-11-14), so
  the mother is an adult woman who need not be nursing, and the baby is text only. Nothing is harmed.

## Living Event Engine LV-A

Range: the Living Event Engine file's fixed event volumes MED-01..31 (Experimental Medicine, Last Resorts & Comfort
Care), LIFE-01..45 (The Healer's Hands, the Farmer's Fields, and the Weaver's Dreams) and CIRCLE-01..31 (The Circle of
Life, Rights, and Remembrance): `living/lv_med`, `living/lv_life`, `living/lv_circle`, 107 events. Line numbers are
the living source's. Generator: `scripts/living_vols/gen_lv_a.py`.

**No `protected: "allow"`.** Every harm-capable role keeps `auto`: no nursing parent, Golden Child or VV3 Chief is
ever harmed. Children are harmed where the story is a sick or injured child (MED-14, LIFE-04). Every death is
`kill`, "Unknown causes". Each choice's two outcomes are weighted alternatives: harmless 20, minor setback
`occasional` 10, serious harm `rare` 5, death or amputation `very_rare` 2; two outcomes of one class are equal. MED's
consent rule holds: no effect lies on a path the patient refused, and each outcome keeps the source's consent words.

Every harm case (role ages: 14- is 14 and over; the text is the outcome's line):

| Event | Outcome | Villager | Harm | Weight | Text |
|---|---|---|---|---|---|
| `lvcir20_fungi_food` | A2 | cook (14-) | sick | equal with the other outcome | The cook becomes ill, and the village stops gathering unknown fungi. |
| `lvlife01_bitter_root` | A1 | patient (14-) | health -30..-10 | occasional (10) | The pain eases, but nausea leaves the patient unwilling to repeat it. |
| `lvlife02_draught` | A1 | patient (14-) | health -30..-10 | occasional (10) | The patient feels little pain, but remains weak and difficult to wake. |
| `lvlife02_draught` | A2 | patient (14-) | health -60..-40 | rare (5) | The patient grows dangerously still, and the healers abandon the procedure to tend to breathing. |
| `lvlife02_draught` | C2 | patient (14-) | health -30..-10 | occasional (10) | The delay allows the condition to worsen, forcing another difficult discussion. |
| `lvlife04_crooked_arm` | A2 | child (3-13) | health -30..-10 | occasional (10) | The attempt worsens the injury, and the healers must change their plan. |
| `lvlife06_bone_would` | A2 | elder (55-) | health -60..-40 | rare (5) | The wound becomes infected, and the elder's health declines. |
| `lvlife07_warm_stone` | B2 | patient (14-) | health -30..-10 | occasional (10) | Movement worsens the pain, and the healer adjusts the plan. |
| `lvlife09_fever_river` | A2 | patient (14-) | health -30..-10 | occasional (10) | The fever worsens despite attentive care. |
| `lvlife09_fever_river` | B2 | patient (14-) | health -30..-10 | occasional (10) | The herb causes stomach upset, and the healer discontinues it. |
| `lvlife10_wound_would` | A2 | fisherman (14-) | health -30..-10 | occasional (10) | The wound worsens, and the healer suspects infection. |
| `lvlife10_wound_would` | B2 | fisherman (14-) | health -30..-10 | occasional (10) | The closed wound becomes swollen, requiring urgent reassessment. |
| `lvmed01_borrowed_organ` | A1 | patient (18-) | health -60..-40 | rare (5) | The patient consents; the operation briefly improves their strength, but a later fever threatens their life. |
| `lvmed01_borrowed_organ` | A2 | patient (18-) | death (Unknown causes) | very_rare (2) | The patient consents, but the transplanted organ fails and the healer records the loss. |
| `lvmed03_blood_another` | A1 | patient (14-) | health -30..-10 | occasional (10) | The patient briefly rallies, then becomes feverish; the healers fear a harmful reaction. |
| `lvmed03_blood_another` | B2 | patient (14-) | death (Unknown causes) | very_rare (2) | The wound proves too severe, and the patient dies despite careful treatment. |
| `lvmed04_draught` | A1 | patient (14-) | health -30..-10 | occasional (10) | The patient sleeps through part of the procedure but wakes frightened and weak. |
| `lvmed04_draught` | A2 | patient (14-) | health -60..-40 | rare (5) | The patient becomes dangerously unresponsive, and the healers abandon the operation. |
| `lvmed05_limb_might` | A1 | patient (18-) | health -60..-40 | equal with the other outcome | The patient consents and survives, beginning a difficult adjustment to daily life. |
| `lvmed05_limb_might` | A1 | patient (18-) | dislikes running | equal with the other outcome | The patient consents and survives, beginning a difficult adjustment to daily life. |
| `lvmed05_limb_might` | A2 | patient (18-) | death (Unknown causes) | equal with the other outcome | The patient survives the operation but later dies from infection. |
| `lvmed05_limb_might` | B1 | patient (18-) | health -30..-10 | occasional (10) | The illness recedes, though the limb remains weak. |
| `lvmed05_limb_might` | B2 | patient (18-) | death (Unknown causes) | very_rare (2) | The illness spreads, and the patient dies with family nearby. |
| `lvmed05_limb_might` | C2 | patient (18-) | health -60..-40 | very_rare (2) | The patient chooses surgery and later trains apprentices in a new craft. |
| `lvmed05_limb_might` | C2 | patient (18-) | dislikes running | very_rare (2) | The patient chooses surgery and later trains apprentices in a new craft. |
| `lvmed06_stone_belly` | A2 | patient (14-) | death (Unknown causes) | very_rare (2) | The healer cannot reach the cause, and the patient dies after the attempt. |
| `lvmed06_stone_belly` | B2 | patient (14-) | health -60..-40 | rare (5) | The obstruction worsens, leaving the patient too weak for surgery. |
| `lvmed07_breath_fades` | A2 | patient (14-) | death (Unknown causes) | very_rare (2) | The device fails to help, and the patient dies despite the effort. |
| `lvmed07_breath_fades` | B2 | patient (14-) | health -60..-40 | rare (5) | The patient grows weaker, and the family gathers at the bedside. |
| `lvmed08_fever_will` | A2 | patient (14-) | health -60..-40 | rare (5) | The patient develops a severe reaction, forcing the healer to stop. |
| `lvmed08_fever_will` | B2 | patient (14-) | death (Unknown causes) | very_rare (2) | The infection spreads, and the patient dies. |
| `lvmed09_heart_falters` | A1 | elder (55-) | health -60..-40 | rare (5) | The patient briefly awakens, but their condition remains critical. |
| `lvmed09_heart_falters` | A2 | elder (55-) | death (Unknown causes) | very_rare (2) | The attempt fails, and the family mourns the elder. |
| `lvmed09_heart_falters` | B2 | elder (55-) | death (Unknown causes) | very_rare (2) | The elder dies peacefully with loved ones present. |
| `lvmed10_sight_behind` | A2 | patient (14-) | health -60..-40 | rare (5) | The eye becomes painful after surgery, and the villager loses further vision. |
| `lvmed11_water_must` | B2 | patient (14-) | sick | occasional (10) | Another patient becomes ill, prompting renewed questions. |
| `lvmed12_strange_thread` | A1 | patient (14-) | health -30..-10 | occasional (10) | The wound closes neatly, but swelling develops around the thread. |
| `lvmed12_strange_thread` | B2 | patient (14-) | health -30..-10 | occasional (10) | The wound reopens, and the patient requires further care. |
| `lvmed13_growing_lump` | B2 | patient (18-) | health -30..-10 | occasional (10) | The lump grows painful, and the patient asks to reconsider surgery. |
| `lvmed14_child_long` | A2 | child (3-13) | health -30..-10 | occasional (10) | The remedy causes distress and is stopped; the child remains ill. |
| `lvmed14_child_long` | B2 | child (3-13) | health -60..-40 | rare (5) | The child grows weaker, and the family requests more help. |
| `lvmed15_last_treatment` | A2 | patient (18-) | death (Unknown causes) | very_rare (2) | The attempt fails, and the patient dies after a difficult recovery. |
| `lvmed16_healer_cannot` | A2 | friend (18-) | death (Unknown causes) | very_rare (2) | The patient dies peacefully, and the healer later teaches apprentices about listening. |
| `lvmed18_healing_spring` | A2 | patient (14-) | health -30..-10 | occasional (10) | The journey exhausts the patient and worsens their condition. |
| `lvmed18_healing_spring` | B2 | patient (14-) | sick | occasional (10) | The water causes stomach illness, and the healers question its purity. |
| `lvmed19_spell_holds` | A2 | patient (14-) | death (Unknown causes) | very_rare (2) | The spell seems to fail, and the patient dies despite further care. |
| `lvmed20_vine_closes` | A2 | patient (14-) | health -30..-10 | occasional (10) | The resin irritates the wound, and the healers return to familiar care. |
| `lvmed24_visitor_cure` | B2 | patient (14-) | death (Unknown causes) | very_rare (2) | The patient dies, and some villagers blame the decision despite the uncertain claim. |
| `lvmed25_patient_wants` | A1 | patient (18-) | death (Unknown causes) | very_rare (2) | The patient dies surrounded by familiar sights and loved ones. |
| `lvmed26_scar_reopened` | A2 | patient (14-) | health -60..-40 | rare (5) | The patient survives the second procedure but remains very weak. |
| `lvmed26_scar_reopened` | B2 | patient (14-) | death (Unknown causes) | very_rare (2) | The infection spreads, and the patient dies. |
| `lvmed27_medicine_helps` | A1 | patient2 (14-) | health -30..-10 | occasional (10) | One patient improves while the other develops a troubling rash. |
| `lvmed27_medicine_helps` | B2 | patient1 (14-) | health -30..-10 | occasional (10) | The original illness worsens, requiring another approach. |
| `lvmed28_unfinished` | A1 | patient (14-) | death (Unknown causes) | very_rare (2) | The healer completes the operation, but the patient dies days later. |
| `lvmed28_unfinished` | A2 | patient (14-) | health -60..-40 | rare (5) | The patient survives, though recovery is long and uncertain. |
| `lvmed28_unfinished` | B2 | patient (14-) | death (Unknown causes) | very_rare (2) | The patient dies, leaving the healer wondering whether more could have been done. |
| `lvmed29_last_dose_hope` | C2 | patient (18-) | health -30..-10 | occasional (10) | The delay leaves one patient in pain, and the healer regrets waiting. |
| `lvmed30_animal_trial` | A2 | patient (14-) | health -30..-10 | occasional (10) | The patient develops complications, and the trial is stopped. |
## Companion K7

Range: The Four Ways of Knowing 001-060 (`companion/fwk/fwk001`-`fwk060`), 60 events. Line numbers are the companion
source's. Generator: `scripts/companion/gen_k7.py`.

| Event | Outcome | Villager | Exact text | Why |
|---|---|---|---|---|
| `fwk053_nursing_mother` The Nursing Mother's Impossible Day | choice C (L5972) | `mother`, a nursing parent (female), `protected: "allow"`: `sick` | "Overextend herself and become ill." | The event is about a nursing mother; the player's own choice says she becomes ill. Illness, not injury or death; the baby is untouched. |

- The other harm-capable roles keep the default `auto` protection: FWK 046's apprentice (choice C "Find them injured
  in an isolated place.": a minor injury, health_change -30..-10; choice D "Face an unresolved disappearance.":
  vanish, missing with no grave) and FWK 055's craftsperson (choice C "Give up and develop a dislike of the craft.":
  a dislike of work).
- Part I (001-040) has no harm at all.

## Living Event Engine LV-B

Range: the Living Event Engine file's fixed event volumes PEOPLES-01..37 (Colors, Masks, Peoples and Choice),
UNSEEN-01..39 (The Unseen Horizon, Cryptids, and the Silent Gods), WAYS-01..38 (The Many Ways of Isola) and
AUTH-01..30 (The Weight of a Name): `living/lv_peoples`, `living/lv_unseen`, `living/lv_ways`, `living/lv_auth`, 144
events. Line numbers are the living source's. Generator: `scripts/living_vols/gen_lv_b.py`.

**No `protected: "allow"`.** Every harm-capable role keeps `auto`: no nursing parent, Golden Child or VV3 Chief is
ever harmed, and no child or teen (14-25 roles are young adults) is harmed. The one death is `kill`, "Unknown causes"
(AUTH-20: an elder near death dies comforted, very rare). The three disappearances are `vanish` (missing for good, no
grave), rare: the source's own words say the villager never returns or goes missing and the search finds nothing; a
villager who comes back (UNSEEN-09 A2, UNSEEN-14 B2) is text only. Weights as LV-A: harmless 20, minor setback
`occasional` 10, serious harm or a disappearance `rare` 5, death `very_rare` 2.

Every harm case (role ages: 14- is 14 and over; the text is the outcome's line):

| Event | Outcome | Villager | Harm | Weight | Text |
|---|---|---|---|---|---|
| `lvppl01_red_hair` | C2 | villager (14-) | health -30..-10 | occasional (10) | The pigment irritates the skin, and the villager washes it away. |
| `lvuns10_footprint` | B2 | explorer (14-) | vanish (missing, no grave) | rare (5) | One explorer fails to return, and the village begins a rescue search. |
| `lvuns16_scientist` | C2 | scientist (14-25) | vanish (missing, no grave) | rare (5) | The scientist never returns, and the village searches without learning what happened. |
| `lvuns24_shrine_miracle` | A2 | patient (14-) | health -30..-10 | occasional (10) | The illness worsens, and the healers discuss comfort and treatment choices. |
| `lvuns32_watcher` | B2 | explorer (14-) | vanish (missing, no grave) | rare (5) | The explorer goes missing, and a rescue party finds only abandoned supplies. |
| `lvway01_flood_before` | A1 | adept (14-) | health -30..-10 | occasional (10) | The current bends around the huts, but the adept collapses from exhaustion. |
| `lvway09_elder_wrong` | D2 | villager (14-) | sick | occasional (10) | A villager becomes ill, prompting an urgent review. |
| `lvway13_magic_failed` | A2 | master (14-) | health -30..-10 | occasional (10) | Repeated attempts exhaust the master. |
| `lvway19_healing_debate` | A2 | patient (14-) | health -30..-10 | occasional (10) | The remedy causes discomfort and is discontinued. |
| `lvway27_parent_knew` | B2 | villager (14-25) | health -30..-10 | occasional (10) | The expedition ends in injury and a difficult homecoming. |
| `lvway31_choice` | B2 | patient (14-) | health -30..-10 | occasional (10) | The patient worsens, and the apprentice asks for help. |
| `lvway35_cost_miracle` | A1 | healer (14-) | health -30..-10 | occasional (10) | The patient improves, but the healer needs weeks to recover. |
| `lvway35_cost_miracle` | B2 | patient (14-) | health -30..-10 | occasional (10) | The illness progresses despite careful attention. |
| `lvauth06_master_healer` | A2 | patient (14-) | health -30..-10 | occasional (10) | The healer overlooks a new complication. |
| `lvauth20_elder_lesson` | A1 | elder (55-) | death (Unknown causes) | very_rare (2) | The elder dies comforted by the promise. |
| `lvauth21_master_feared` | A2 | craftsperson (14-) | sick | occasional (10) | Their knowledge risks disappearing when they fall ill. |
| `lvauth29_apprentice` | A2 | wearer (14-) | sick | occasional (10) | The master dismisses the risk and a wearer becomes ill. |

## Beyond the Horizon and Role Models and Good Examples (HZ-RM)

Range: the owner's 2026-11-15 sources "Isola - Beyond the Horizon" EVENT 001-080 (`horizon/hz_world`,
`horizon/hz_vol2`) and "Role Models and Good Examples" RM-01..RM-40 (`rolemodels/rm`), 120 events. Generators:
`scripts/horizon_rm/gen_hz.py`, `gen_rm.py`.

**No harmful effect anywhere, no `protected: "allow"`.** Every outcome of both sources is talk, imagination, a small
harmless trial, a success, a compromise or a delay; injuries, illness, war and hunger appear only as the villagers'
speculation about distant peoples (text only). The only effects are six small skill gains (Horizon 009 A1 Building,
018 A1 Research; RM-11 B1 and RM-25 A1 Building, RM-17 A1 Healing, RM-36 A2 Parenting). Both outcomes of every
choice are equally likely.
