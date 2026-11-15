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

### Two Lives, One Decision (`all_v20_d1_two_lives`, V20 D1, source L8950-8968)

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
