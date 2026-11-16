# Living Event Engine: the bank, its tags and the owner's open questions

This page is for the owner's review. It lists what `data/living_events/bank.json` (format `vvfp-living-bank` v1) says about every piece of the Living Event Engine, so each decision can be checked against the source.

- **Source:** `docs/more-island-events/Isola_ALL_IN_ONE_Modular_Living_Event_Engine.txt`, the owner's final file, frozen byte for byte (SHA-256 in `data/living_events/SOURCE.sha256`). Line numbers below are that file's.
- **Three banks:**
  - **Living Engine** (`le_*`, L23812-25133): 120 seeds, 30 roles, 24 personalities, 15 lenses, 34 approaches, 38 archetypes, 7 category choice sets, the 60 MIX examples. Active.
  - **MC** (`mc_*`, L25134-26616): 95 situations with 4 approaches each and the 760 authored outcomes (L25667-26616). **Active.**
  - **MJ** (`mj_*`, L26617-26867): 35 seeds with titles and 4 approaches, no outcomes yet ("to be developed"). **Held**: parsed and tested, never drawn.
- **Credit** (L23815): "Original Isola concepts and creative direction: Lorsieab2. Modular framework and new scenario writing: ChatGPT (OpenAI)."
- **Rebuild:** `python scripts/living_bank_build.py`. **Test:** `tests/test_living_bank.py` (counts against the source, every text against its src line, ids, the compatibility table).
- **Rare roll:** each category counts as one series (owner, 2026-11-14).

## 1. The frame and the joining words

The owner's MIX SETUP lines read (for example MIX-001, L24096):

> A dog seems to have chosen the best seat at council. A warm a master parent and a private a teenager disagree about what should happen next. Their status alone does not settle the matter.

The owner asked for the villagers' names to be shown (2026-11-14), so the shipped frame is:

> `<seed> (first), <a/an> <personality> <role>, and (second), <a/an> <personality> <role>, disagree about what should happen next. Their status alone does not settle the matter.`

> Example: "A dog seems to have chosen the best seat at council. Ana, a warm master parent, and Kai, a private teenager, disagree about what should happen next. Their status alone does not settle the matter."

The only words that are not the owner's are listed in [grammar-fixes.md](grammar-fixes.md#living-event-engine) (fix `living-frame-article`), each with its reason. In short:

- the two names, each followed by a comma;
- the personality's own article, `a` or `an` (`an ambitious`, `an impatient`, `an insecure`, `an observant`), in place of the source's `A <personality> a <role>`;
- the role without its own article (`master parent`, not `a master parent`), from the role bank (L23980);
- the frame's own `and`, now with a comma before it because the second name follows.

**Names and pronouns** (owner, 2026-11-14): the names appear once, in the frame. Any later reference to the two villagers uses the role pronoun tokens `(first.he/she)`, `(first.him/her)`, `(first.his/her)`, or the name where a pronoun would be ambiguous (for example when both villagers are the same sex), as in the owner's own events (The Aspiring Adventurer, `Additional Virtual Villagers Events By Lorsieab2.txt` L82-83, mixes names and pronouns). Where an archetype says "the central villager", "the novice" or "the master", the owner's words stay. The archetype lines today contain no reference to the two villagers, so no pronoun is substituted yet.

## 2. Seeds (120)

Tags drive the compatibility rules (section 7). `games` is all five unless noted. Meaning of the tags:

| Tag | Meaning |
|---|---|
| `personal` | a purely personal matter: no prayer, magic, animal labour or experiment (source rule 5, L23825) |
| `playful` | a light, comic or everyday seed |
| `celebration` | a feast, festival, ceremony or performance |
| `supernatural` | a spirit, god, vision or cryptid claim: never resolved (source rule 9) |
| `belief` | faith or sacred matter: never a mocking approach |
| `medical` | health or care: a consent choice is mandatory; no consent-trivialising approach |
| `somber` | grief, decline, loneliness or loss |
| `child_subject` | the seed is about a child |
| `adult_only` | a romantic or adult framing: no child or teenager cast |
| `other_community` | another community or visitor; under Guardians of Isola these are Isolan communities |
| `elder_death_ok` | the only seeds where "A beloved elder dies" may be drawn |
| `chief` | the seed names the chief: a game word outside VV3 (`chief_words`) |

| Seed | Text | Tags | Notes |
|---|---|---|---|
| PER-01 (L23837) | A villager wants to dye their hair an unfamiliar color. | personal | proposed seed effect (Q6): appearance |
| PER-02 (L23838) | A tailor proposes clothing that mixes two regional styles. | personal |  |
| PER-03 (L23839) | A villager dislikes the ceremonial clothes chosen by their family. | personal |  |
| PER-04 (L23840) | A young artist draws an elder in an unflattering but affectionate way. | personal |  |
| PER-05 (L23841) | Someone wants to wear a mask at a celebration. | celebration, personal | games 5 |
| PER-06 (L23842) | A craftsperson creates jewelry from an unusual shell. | personal |  |
| PER-07 (L23843) | A villager regrets cutting their hair. | personal |  |
| PER-08 (L23844) | A newcomer copies a hairstyle without knowing its significance. | personal |  |
| PER-09 (L23845) | A villager wishes to change their name. | personal |  |
| PER-10 (L23846) | A shy singer wants to perform behind a screen. | celebration, personal |  |
| FAM-01 (L23849) | A child prefers spending afternoons with a neighbor. | child_subject, personal |  |
| FAM-02 (L23850) | Two siblings disagree about caring for an aging relative. | personal, somber |  |
| FAM-03 (L23851) | A parent expects a child to inherit the family trade. | child_subject, personal |  |
| FAM-04 (L23852) | A close friend reveals a secret just before a feast. | personal |  |
| FAM-05 (L23853) | An elder receives a love letter after many years alone. | adult_only, personal |  |
| FAM-06 (L23854) | A couple disagree about whether to have a child. | adult_only, personal |  |
| FAM-07 (L23855) | A family dislikes their child’s chosen companion. | adult_only, personal |  |
| FAM-08 (L23856) | Two friends both want the same treasured keepsake. | personal |  |
| FAM-09 (L23857) | A villager wants to forgive a relative who has not apologized. | personal |  |
| FAM-10 (L23858) | A grandparent tells a story the family knows is inaccurate. | personal |  |
| CEL-01 (L23861) | The chief cooks a disappointing feast. | celebration, chief, playful | chief words: "The chief" |
| CEL-02 (L23862) | A famous dancer discovers an apprentice dances better. | celebration, playful |  |
| CEL-03 (L23863) | A village game ends in a disputed tie. | celebration, playful |  |
| CEL-04 (L23864) | A child invents a festival nobody understands. | celebration, child_subject, playful |  |
| CEL-05 (L23865) | A musician refuses to play for an important guest. | celebration, playful |  |
| CEL-06 (L23866) | The feast’s centerpiece is accidentally ruined. | celebration, playful |  |
| CEL-07 (L23867) | A prank leaves a usually cheerful villager embarrassed. | celebration, personal, playful |  |
| CEL-08 (L23868) | Two storytellers claim to have invented the same tale. | celebration, playful |  |
| CEL-09 (L23869) | An animal wanders into a solemn ceremony. | celebration, playful |  |
| CEL-10 (L23870) | A wedding guest arrives wearing the same outfit as the couple. | adult_only, celebration, personal, playful |  |
| ART-01 (L23873) | An experiment unexpectedly produces a beautiful pigment. | - | proposed seed effect (Q6): tech small |
| ART-02 (L23874) | A weaver creates a tapestry that nobody likes. | - |  |
| ART-03 (L23875) | A novice discovers an old song has been remembered incorrectly. | elder_death_ok |  |
| ART-04 (L23876) | A potter’s flawed bowl becomes fashionable. | - |  |
| ART-05 (L23877) | A scientist publishes a conclusion before checking the measurements. | - |  |
| ART-06 (L23878) | A child asks why a sacred carving looks different from the legend. | belief, child_subject |  |
| ART-07 (L23879) | A healer discovers that a traditional salve has an unexpected effect. | medical |  |
| ART-08 (L23880) | A sculptor wants to depict a living person as a hero. | - |  |
| ART-09 (L23881) | A historian finds two conflicting accounts of the same event. | elder_death_ok |  |
| ART-10 (L23882) | A novice builds a useful tool but cannot explain how it works. | - | proposed seed effect (Q6): tech small |
| ANI-01 (L23885) | A beloved pet begins visiting another household. | - |  |
| ANI-02 (L23886) | A bird repeatedly steals bright objects from villagers. | playful |  |
| ANI-03 (L23887) | A wild animal seems unusually comfortable around people. | - |  |
| ANI-04 (L23888) | A farmer wants to protect a creature that eats their crops. | - |  |
| ANI-05 (L23889) | A fisher catches an unfamiliar animal and wonders whether to release it. | - |  |
| ANI-06 (L23890) | A child wants to raise a wild hatchling. | child_subject |  |
| ANI-07 (L23891) | An old working animal refuses a familiar task. | - |  |
| ANI-08 (L23892) | A rare flower appears in a heavily used footpath. | - |  |
| ANI-09 (L23893) | A mushroom grows from a treasured wooden heirloom. | - |  |
| ANI-10 (L23894) | A small predator takes shelter beside the nursery. | - |  |
| BEL-01 (L23897) | A villager claims to hear a voice in a cave. | belief, supernatural |  |
| BEL-02 (L23898) | A child asks why the gods never visit Isola. | belief, child_subject, supernatural |  |
| BEL-03 (L23899) | An atheist wants to help maintain the shrine. | belief |  |
| BEL-04 (L23900) | An elder interprets an unusual cloud as a warning. | belief, supernatural |  |
| BEL-05 (L23901) | A supposed cryptid leaves tracks near the gardens. | belief, supernatural |  |
| BEL-06 (L23902) | A villager dreams of an ancestor they never met. | belief, somber, supernatural |  |
| BEL-07 (L23903) | A sacred object appears to have moved overnight. | belief, supernatural |  |
| BEL-08 (L23904) | Two believers disagree about the meaning of a ritual. | belief |  |
| BEL-09 (L23905) | A skeptic volunteers to investigate a reported miracle. | belief, supernatural |  |
| BEL-10 (L23906) | A storyteller admits inventing part of a famous legend. | belief |  |
| GOV-01 (L23909) | The chief receives a gift from someone seeking a favor. | chief | chief words: "The chief" |
| GOV-02 (L23910) | A respected master refuses to train an apprentice. | - |  |
| GOV-03 (L23911) | A novice is asked to lead a task beyond their experience. | - |  |
| GOV-04 (L23912) | A popular villager is accused of cheating in a contest. | - |  |
| GOV-05 (L23913) | A leader wants a day without making decisions. | personal |  |
| GOV-06 (L23914) | The council must decide who receives a rare musical instrument. | - |  |
| GOV-07 (L23915) | A family claims an old rule applies only to outsiders. | - |  |
| GOV-08 (L23916) | An elder demands obedience without giving a reason. | personal |  |
| GOV-09 (L23917) | A quiet villager notices an error in the chief’s announcement. | chief | chief words: "the chief’s" |
| GOV-10 (L23918) | A respected teacher admits they no longer remember a technique. | personal, somber |  |
| OTH-01 (L23921) | A visitor’s song resembles an Isolan lullaby. | other_community |  |
| OTH-02 (L23922) | Two communities disagree about the proper way to greet elders. | other_community |  |
| OTH-03 (L23923) | A villager becomes friends with someone from another tribe. | other_community, personal |  |
| OTH-04 (L23924) | A trader offers a beautiful object with an unknown history. | other_community |  |
| OTH-05 (L23925) | An Isolan wants to join another community voluntarily. | other_community, personal |  |
| OTH-06 (L23926) | Two families interpret the same festival differently. | celebration, other_community |  |
| OTH-07 (L23927) | A traveler describes a place nobody on Isola has seen. | other_community |  |
| OTH-08 (L23928) | A visitor refuses a customary food without explaining why. | other_community, personal |  |
| OTH-09 (L23929) | A guest asks to learn a craft usually taught within families. | other_community |  |
| OTH-10 (L23930) | A child notices that two rival communities use the same proverb. | child_subject, other_community |  |
| FOO-01 (L23933) | A villager insists their strange recipe is delicious. | playful |  |
| FOO-02 (L23934) | Two cooks disagree about how spicy a feast should be. | playful |  |
| FOO-03 (L23935) | A child refuses a food that everyone else enjoys. | child_subject, personal, playful |  |
| FOO-04 (L23936) | A family keeps a fruit that smells terrible but tastes sweet. | playful |  |
| FOO-05 (L23937) | A novice accidentally invents a new way to preserve food. | playful | proposed seed effect (Q6): food small |
| FOO-06 (L23938) | Someone eats the last piece of a shared treat. | personal, playful |  |
| FOO-07 (L23939) | A villager wants to dine alone instead of joining a feast. | personal, playful |  |
| FOO-08 (L23940) | A prized cooking pot goes missing before dinner. | playful |  |
| FOO-09 (L23941) | A gardener grows a fruit nobody knows how to prepare. | playful | proposed seed effect (Q6): food small |
| FOO-10 (L23942) | A visiting family follows unfamiliar table customs. | playful |  |
| EMO-01 (L23945) | A celebrated master feels jealous of a beginner. | personal |  |
| EMO-02 (L23946) | A villager is tired of being called brave. | personal |  |
| EMO-03 (L23947) | A child feels invisible beside a talented sibling. | child_subject, personal |  |
| EMO-04 (L23948) | A cheerful villager admits they sometimes feel lonely. | personal, somber |  |
| EMO-05 (L23949) | A quiet villager dislikes being praised in public. | personal |  |
| EMO-06 (L23950) | A parent struggles to accept their grown child’s independence. | personal |  |
| EMO-07 (L23951) | A chief fears being loved only for their title. | chief, personal | chief words: "A chief" |
| EMO-08 (L23952) | A villager wants to leave a tradition they once cherished. | personal |  |
| EMO-09 (L23953) | A skilled worker no longer enjoys their craft. | personal |  |
| EMO-10 (L23954) | An elder wonders whether their life mattered. | personal, somber |  |
| RES-01 (L23957) | A tired caregiver refuses offers of rest. | medical, personal |  |
| RES-02 (L23958) | A villager asks to stop an exhausting treatment. | medical, personal, somber |  |
| RES-03 (L23959) | A healer is embarrassed to seek care for themselves. | medical, personal |  |
| RES-04 (L23960) | A child is frightened by a harmless medical instrument. | child_subject, medical, personal |  |
| RES-05 (L23961) | An elder wants to continue a hobby despite limited strength. | medical, personal |  |
| RES-06 (L23962) | A patient trusts an apprentice more than the master healer. | medical, personal |  |
| RES-07 (L23963) | A villager is recovering but feels pressured to work. | medical, personal |  |
| RES-08 (L23964) | Two caregivers disagree about what comfort means. | medical, personal |  |
| RES-09 (L23965) | A healer must admit that a condition has no known cure. | medical, personal, somber |  |
| RES-10 (L23966) | A villager wishes to spend a difficult day in solitude. | personal, somber |  |
| ODD-01 (L23969) | A parrot repeats the chief’s private complaint. | chief, playful | chief words: "the chief’s" |
| ODD-02 (L23970) | A child declares themselves the island’s new ruler. | child_subject, playful |  |
| ODD-03 (L23971) | A villager claims to have invented sleeping. | personal, playful |  |
| ODD-04 (L23972) | A goat eats an important-looking ceremonial ribbon. | playful |  |
| ODD-05 (L23973) | A scientist loses their notes to a sudden gust. | playful |  |
| ODD-06 (L23974) | A fisherman exaggerates the size of yesterday’s catch. | playful |  |
| ODD-07 (L23975) | Two villagers accidentally exchange identical sandals. | personal, playful |  |
| ODD-08 (L23976) | A musician’s instrument produces a ridiculous sound. | playful |  |
| ODD-09 (L23977) | A dog seems to have chosen the best seat at council. | playful |  |
| ODD-10 (L23978) | A villager mistakes a carved statue for a person at dusk. | playful |  |

- **Subject cast:** the seed's subject (the dog, the child who refuses food) is text, never cast. The two cast villagers are the two who disagree (the frame). So `primary_any_of` / `secondary_any_of` are left empty for all 120 seeds: the 60 MIX show the owner pairing any roles with any seed (MIX-060: a chief and a master builder disagree about two believers' ritual).
- **Medical seeds** carry `consent_choice_required`: every variant must offer "Seek the affected person's wishes", "Let the other person choose" or the category set's "Ask what the person involved actually wants."

## 3. Roles (30)

| Role | Cast spec | Games | Tags | Note |
|---|---|---|---|---|
| a chief | special tribal_chief | 3 | leader | the VV3 Tribal Chief only; open question Q5 |
| a council member | age 18+ | 1,2,3,4,5 | leader |  |
| a master healer | age 14+, Healing 50+ (highest) | 1,2,3,4,5 | master |  |
| a master builder | age 14+, Building 50+ (highest) | 1,2,3,4,5 | master |  |
| a master scientist | age 14+, Research 50+ (highest) | 1,2,3,4,5 | master |  |
| a master farmer | age 14+, Farming 50+ (highest) | 1,2,3,4,5 | master |  |
| a master fisher | age 18+ | 1,2,3,4,5 | master | no game has a fishing skill: cast as any adult (18+) |
| a master parent | age 14+, Parenting 50+ (highest) | 1,2,3,4,5 | master |  |
| a spiritual elder | age 55+ | 1,2,3,4,5 | elder | age 55+; Devotion exists only in VV5, so no skill requirement |
| a Nature practitioner | age 14+, Devotion 1+ | 5 | - | VV5 only (Devotion); open question Q5 |
| a Magic practitioner | age 14+, Devotion 1+ | 5 | - | VV5 only (Devotion); open question Q5 |
| an apprentice | age 14-24 | 1,2,3,4,5 | novice |  |
| a rookie | age 14-24 | 1,2,3,4,5 | novice |  |
| a child | age 3-13 | 1,2,3,4,5 | child, vulnerable |  |
| a teenager | age 14-17 | 1,2,3,4,5 | teen, vulnerable |  |
| an adult villager | age 18-54 | 1,2,3,4,5 | - |  |
| an elderly villager | age 55+ | 1,2,3,4,5 | elder, vulnerable |  |
| a visiting Isolan | stranger (random sex) | 1,2,3,4,5 | stranger | a stranger (no confirmed outsiders arrive; another Isolan village) |
| a skeptical observer | age 14+ | 1,2,3,4,5 | - |  |
| a shy craftsperson | age 14+, Building 1+ | 1,2,3,4,5 | - |  |
| a confident novice | age 14-24 | 1,2,3,4,5 | novice |  |
| a caretaker | age 14+, Parenting or Healing 1+ | 1,2,3,4,5 | - |  |
| a storyteller | age 14+ | 1,2,3,4,5 | - | no storytelling skill: any adult |
| a musician | age 14+ | 1,2,3,4,5 | - | no music skill: any adult |
| a weaver | age 14+ | 1,2,3,4,5 | - | no weaving skill in any game: any adult |
| a cook | age 14+ | 1,2,3,4,5 | - | no cooking skill in any game: any adult |
| a gardener | age 14+, Farming 1+ | 1,2,3,4,5 | - |  |
| a fisher | age 14+ | 1,2,3,4,5 | - |  |
| a relative | age 3+ | 1,2,3,4,5 | - |  |
| a friend | age 3+ | 1,2,3,4,5 | - |  |

- Skills are the games' own (Parenting, Building, Farming, Healing, Research; Devotion only in VV5). No game has fishing, weaving, cooking, music or storytelling skills, so those roles are any adult.
- "Master" is cast at skill 50 or more, choosing the most skilled villager (unclear item U2).

## 4. Personalities (24) and lenses (15)

Personalities (L23981), with their article: a humble; a proud; a curious; a cautious; an impatient; a warm; a skeptical; a devout; a playful; an insecure (insult_risk); a confident; a thoughtful; a stubborn; a generous; a private; an ambitious; a tired (ageist_risk, insult_risk); an observant; a forgetful (ageist_risk, insult_risk); a compassionate; a blunt (insult_risk); a diplomatic; a superstitious (insult_risk); a methodical.

Lenses (L23824, tags only, never shown): expertise, privacy, consent, reputation, art, tradition, beliefs, ecology, friendship, scarcity, identity, etiquette, rivalry, humor, uncertainty. A single seed can support several lenses.

## 5. Approaches (34) and the category choice sets (7)

| Id | Family | Approach | Kind | Tags |
|---|---|---|---|---|
| le_app_consult_01 | consult | Ask a specialist for advice | talk | - |
| le_app_consult_02 | consult | Ask an apprentice what they noticed | talk | - |
| le_app_consult_03 | consult | Seek the affected person’s wishes | consent | - |
| le_app_consult_04 | consult | Invite several disagreeing voices | public | consent_risk |
| le_app_consult_05 | consult | Ask the chief to decide | authority | consent_risk, chief |
| le_app_consult_06 | consult | Ask an elder to explain the tradition | talk | - |
| le_app_consult_07 | consult | Seek the perspective of another community | talk | - |
| le_app_act_01 | act | Try a small experiment | experiment | consent_risk |
| le_app_act_02 | act | Use a familiar method | talk | - |
| le_app_act_03 | act | Invent a new tool or technique | experiment | - |
| le_app_act_04 | act | Do the work by hand | talk | - |
| le_app_act_05 | act | Recruit willing helpers | talk | - |
| le_app_act_06 | act | Use animal assistance with appropriate care | animal | consent_risk |
| le_app_act_07 | act | Try a magical method if available | magic | consent_risk |
| le_app_act_08 | act | Hold a ritual or prayer if desired | prayer | - |
| le_app_relate_01 | relate | Offer kindness without demanding agreement | talk | - |
| le_app_relate_02 | relate | Speak candidly about the problem | talk | - |
| le_app_relate_03 | relate | Respectfully disagree | talk | - |
| le_app_relate_04 | relate | Stay neutral and observe | talk | - |
| le_app_relate_05 | relate | Set a firm boundary | talk | - |
| le_app_relate_06 | relate | Offer a compromise | talk | - |
| le_app_relate_07 | relate | Apologize and repair the relationship | talk | - |
| le_app_relate_08 | relate | Let the other person choose | consent | - |
| le_app_withdraw_01 | withdraw | Wait and gather evidence | talk | - |
| le_app_withdraw_02 | withdraw | Decline to participate | talk | - |
| le_app_withdraw_03 | withdraw | Keep the matter private | talk | - |
| le_app_withdraw_04 | withdraw | Leave the choice unresolved | talk | - |
| le_app_withdraw_05 | withdraw | Allow different households to do things differently | talk | - |
| le_app_withdraw_06 | withdraw | Postpone until feelings settle | talk | - |
| le_app_play_01 | play | Turn the disagreement into a friendly contest | comedic | mocking |
| le_app_play_02 | play | Make a joke if everyone is comfortable | comedic | mocking |
| le_app_play_03 | play | Celebrate the unexpected result | comedic | mocking |
| le_app_play_04 | play | Invite the villagers to improvise | play | - |
| le_app_play_05 | play | Try the idea for one day only | play | - |

The MIX examples use one fixed set of four choices per category (always in the same order):

| Set | Categories | A | B | C | D |
|---|---|---|---|---|---|
| le_cs_cel_odd | CEL, ODD | Laugh along if nobody is hurt. (comedic, mocking) | Take the matter seriously. | Invite everyone to improvise a solution. (play) | Let the person most embarrassed decide. (comedic) |
| le_cs_emo_fam_res | EMO, FAM, RES | Ask what the person involved actually wants. (consent) | Offer private support without taking control. | Invite a trusted person to mediate. | Give them space and revisit the issue later. |
| le_cs_gov_oth | GOV, OTH | Let the affected villagers speak first. | Follow the established custom. | Invite an unfamiliar or younger voice. | Negotiate a limited compromise. |
| le_cs_bel | BEL | Investigate the claim without assuming an answer. | Honor the belief without requiring agreement. | Ask a skeptic and a believer to compare interpretations. | Leave the mystery unresolved. |
| le_cs_art_per | ART, PER | Try the unfamiliar idea on a small scale. | Keep the familiar version for now. | Ask the creator to explain their intention. | Let interested villagers choose for themselves. |
| le_cs_foo | FOO | Try a new method on a small scale. | Use the familiar approach. | Ask an experienced villager for advice. | Let the participants settle it together. |
| le_cs_ani | ANI | Observe the creature or habitat before acting. | Ask a knowledgeable keeper or naturalist. | Choose the least disruptive practical response. | Allow a cautious trial and monitor its effects. |

## 6. Archetypes (38) and their effects

Effects name the frame's villagers: `first`, `second`, `junior` (the novice-tagged one, else first) and `elder` (the cast villager aged 55 or more; the archetype is only possible when one is cast). Sizes follow the collection's amount table (authoring rules A3): skill small is +5..10, normal +10..20. `any` skill is one of the game's skills at random.

| Id | Archetype | Effects | Tags | Protection |
|---|---|---|---|---|
| le_arc_good_01 | The participants learn something useful and keep their dignity. | skill small (any) on first; skill small (any) on second | - | auto |
| le_arc_good_02 | The result works better than expected, though nobody claims universal proof. | none | - | auto |
| le_arc_good_03 | The choice strengthens an unexpected friendship. | mood good on first; mood good on second | - | allow |
| le_arc_good_04 | A novice gains experience while a master gains perspective. | skill normal (any) on junior | - | auto |
| le_arc_good_05 | The villagers discover a practical improvement worth remembering. | tech small | - | auto |
| le_arc_good_06 | A long-held misunderstanding is gently corrected. | none | resolves | auto |
| le_arc_good_07 | The person most affected feels heard and makes their own choice. | mood good on first | - | allow |
| le_arc_good_08 | The village enjoys a memorable day without any larger crisis. | celebrate (all) | light | auto |
| le_arc_good_09 | Two different customs coexist without either disappearing. | none | - | auto |
| le_arc_good_10 | The result inspires a new song, pattern, or story. | none | light | auto |
| le_arc_mixed_01 | The immediate problem is solved, but a relationship remains strained. | none | - | auto |
| le_arc_mixed_02 | The idea works for some villagers and not for others. | none | - | auto |
| le_arc_mixed_03 | The village gains knowledge at the cost of time and materials. | tech small; food small loss | - | auto |
| le_arc_mixed_04 | Everyone is safe, though the result is awkward and disappointing. | none | - | auto |
| le_arc_mixed_05 | The compromise satisfies neither side completely but allows cooperation. | none | - | auto |
| le_arc_mixed_06 | The experiment yields ambiguous evidence and a better question. | none | - | auto |
| le_arc_mixed_07 | The chosen approach helps today but creates work for tomorrow. | none | - | auto |
| le_arc_mixed_08 | A small success comes with an unexpected embarrassment. | mood bad on first | light, blame | allow |
| le_arc_mixed_09 | The tradition is preserved, though its meaning continues to be debated. | none | - | auto |
| le_arc_mixed_10 | The change proves useful but takes time for others to accept. | none | - | auto |
| le_arc_bad_01 | An avoidable misunderstanding damages trust. | none | - | auto |
| le_arc_bad_02 | The attempt fails and the participants must admit uncertainty. | none | - | auto |
| le_arc_bad_03 | A rushed choice wastes scarce supplies. | food small loss | blame | auto |
| le_arc_bad_04 | Someone feels excluded and withdraws from the gathering. | mood bad on second | - | allow |
| le_arc_bad_05 | The effort causes minor injury or exhaustion, requiring rest and care. | health -20..-10 on first | injury | allow |
| le_arc_bad_06 | The villagers discover that confidence was mistaken for competence. | none | blame, resolves | auto |
| le_arc_bad_07 | The action creates a new dispute that needs a separate conversation. | none | - | auto |
| le_arc_bad_08 | The affected person refuses to cooperate after their wishes were ignored. | none | - | auto |
| le_arc_bad_09 | A promising idea is abandoned before it can be evaluated fairly. | none | - | auto |
| le_arc_bad_10 | The group becomes divided over who deserves credit. | none | - | auto |
| le_arc_rare_01 | The central villager leaves for a time and their fate remains unknown. | vanish first | rare_harm, vanish | allow |
| le_arc_rare_02 | A beloved elder dies after a long illness, leaving conflicting memories and affection. | kill elder (cause unknown) | rare_harm, elder_death, needs_elder | allow |
| le_arc_rare_03 | A rare creature is glimpsed, but no one can agree what it was. | none | - | auto |
| le_arc_rare_04 | A fragile friendship ends despite sincere attempts to mend it. | mood bad on second | rare_harm | allow |
| le_arc_rare_05 | A chance observation preserves a piece of knowledge thought lost. | tech small | - | auto |
| le_arc_rare_06 | A surprising visitor returns a treasured object with no explanation. | none | - | auto |
| le_arc_rare_07 | An unexpected birth or reunion changes the day’s priorities. | none | birth | auto |
| le_arc_rare_08 | An important heirloom is lost and cannot be recovered. | none | rare_harm | auto |

- **Deaths** are rare: only "A beloved elder dies" kills (cause unknown, a grave as normal), and only where an elder is cast and the seed allows it. "The central villager leaves" is vanish.
- **Harm-capable roles** (for information): any role that can draw an archetype with kill, vanish, a health loss or a bad mood. Per the owner's correction (2026-11-14) these archetypes carry `protection: allow`, so children, nursing parents and the other special villagers may be affected where the situation makes sense; only the VV2 totems are always protected. The compatibility rules below still keep the tone right.

## 7. Compatibility: what is never combined

Owner decision (2026-11-15): the mixer keeps everything except combinations that produce (1) obviously problematic power dynamics, (2) invalidating someone's pain or trauma, (3) portraying anyone as lesser, or (4) a minor-adult romance or a minor-adult power imbalance; genuine narrative contradictions and nonsense combinations stay prevented (coherence). Everything else is allowed: embarrassment, negative interactions, injuries, failed experiments (on animals too), overconfidence, superstitious or negative personalities, humor near serious topics, friendships ending. `bank.json` keeps the rules and the expanded pairwise table (`compat.exclusions`); the test proves the table is exactly what the rules give.

| Rule | Why | When | Excludes |
|---|---|---|---|
| C3 | Medical seeds never have the chief decide a villager's care (an obviously problematic power dynamic). | seeds tagged medical | approaches: Ask the chief to decide |
| C6 | Purely personal seeds never take prayer, magic, animal labour or experiments (source L23825: nonsensical options for a purely personal issue). | seeds tagged personal | approaches: Try a small experiment, Invent a new tool or technique, Use animal assistance with appropriate care, Try a magical method if available, Hold a ritual or prayer if desired |
| C9 | Seeds with an adult-only or romantic framing (a love letter, having a child, a child's companion, a wedding) never cast a child or a teenager (minor-adult romance). | seeds tagged adult_only | roles: a child, a teenager |
| P1 | Contradiction or repeat: a devout or skeptical skeptical observer. | a skeptical observer | personalities: devout, skeptical, observant |
| P2 | Contradiction: a skeptical spiritual elder. | a spiritual elder | personalities: skeptical |
| P3 | Repeat: a confident confident novice. | a confident novice | personalities: confident |
| P4 | Contradiction: a confident shy craftsperson. | a shy craftsperson | personalities: confident |

Pairs in the expanded table: seed_approach 275, seed_choice 0, seed_archetype 0, seed_role 8, role_personality 6, role_archetype 0. Coherence in the mixer as well: an outcome naming an elder is drawn only with an elder in the scene.

### The owner's MIX examples that break a rule

These are the owner's own text. Each is its seed's variant 0 with only the offending piece swapped for the nearest compatible one; every change is in the table below ("Variant 0"). The generator never makes such a combination itself.

| MIX | Seed | Conflict |
|---|---|---|
| MIX-002 | FAM-06 | seed x role "a teenager" (a couple: minor-adult romance) |
| MIX-050 | ART-02 | role "a confident novice" x personality "confident" (repeat) |
| MIX-054 | CEL-06 | role "a skeptical observer" x personality "skeptical" (repeat) |

MIX-027 and MIX-057 cast the VV3-only chief with a VV5-only practitioner: no game has both, so the chief becomes a council member (listed below).

### The owner's world rules (2026-11-15)

- **Legendary beings and the afterlife (W1).** Legendary creatures and afterlife ideas (mermaids, aliens,
  skinwalkers, child-taking creatures, man-eating birds, monsters, cryptids, angels, demons, the underworld, heaven, a
  place where souls are judged, ancestor worship, real-world tribe-specific beings or practices) and ideas such as
  cannibals or headhunters are never named outright: only described or hinted at. Shooting stars, tide pools, sea
  urchins and starfish may be named. The whole bank (Living Engine and MC text) was scanned; two owner lines use such
  a word, "A supposed cryptid leaves tracks near the gardens." (le_bel_05) and "A popular legend portrays an old
  enemy as monsters." (mc_aft_09). Lead decision (2026-11-15), on the owner's own precedent of keeping "Monster" and
  "afterlife" as written and making minimal edits: both stay exactly as the owner wrote them. No bank line is
  changed under W1 (`tests/test_living_fidelity.py` checks that no shipped line names any other such being).

  Kept as they are (not a named being or afterlife place): "A child asks why the gods never visit Isola." (a child's
  own question; whether there are gods stays open), "A villager dreams of an ancestor they never met." (a dream, no
  worship), "An elder admits their ancestors benefited from another group's suffering." (history, no veneration).

<!-- living-mixer: begin (written by python src/vv_living_mixer.py --write-docs) -->
### The rules the mixer adds (owner decision, 2026-11-15)

The bank's rules above are extended with these; every variant obeys them (`scripts/living_check.py`).

| Rule | What is never combined |
|---|---|
| S7 | A romantic, secret-keeping or coercive frame (the adult-only seeds, a friend's secret, an elder demanding obedience, the choice to keep the matter private) casts adults only: both villagers 18 or older, never a child, a teenager or anyone younger than 18 in any role (no minor-adult romance or power imbalance). |
| S17 | A seed about love, a couple, a family's view of a companion, or a villager who is alone never has the chief decide for them (an obviously problematic power dynamic). |

### Variant 0: the MIX examples as shipped, with every change

Variant 0 of a seed is its MIX in the owner's words, with ONLY the piece that breaks a rule above swapped for the nearest compatible one, and the doubled-word grammar fix. A row marked "alternative" keeps both: the owner's original (Before) and the earlier replacement (After) are equal alternatives, and the game picks one at random (owner, 2026-11-15: archetypes are not bad). The MIX anchor test (`tests/test_living_fidelity.py`) reproduces each MIX from the source with exactly these changes.

| MIX | What | Before | After | Why |
|---|---|---|---|---|
| MIX-001 | choice A outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-001 | choice D outcome 2 (alternative) | The villagers discover that confidence was mistaken for competence. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-002 | first villager's role | a teenager | an adult villager | seed x role le_role_teenager |
| MIX-005 | choice D outcome 2 (alternative) | Someone feels excluded and withdraws from the gathering. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-005 | second villager's personality (alternative) | forgetful | thoughtful | both kept, equal chance (owner, 2026-11-15) |
| MIX-006 | choice D outcome 1 (alternative) | A long-held misunderstanding is gently corrected. | The result works better than expected, though nobody claims universal proof. | both kept, equal chance (owner, 2026-11-15) |
| MIX-007 | choice A outcome 2 (alternative) | The effort causes minor injury or exhaustion, requiring rest and care. | The action creates a new dispute that needs a separate conversation. | both kept, equal chance (owner, 2026-11-15) |
| MIX-007 | second villager's personality (alternative) | blunt | stubborn | both kept, equal chance (owner, 2026-11-15) |
| MIX-008 | first villager's personality (alternative) | tired | thoughtful | both kept, equal chance (owner, 2026-11-15) |
| MIX-008 | second villager's personality (alternative) | insecure | cautious | both kept, equal chance (owner, 2026-11-15) |
| MIX-009 | choice A outcome 1 (alternative) | The result inspires a new song, pattern, or story. | The person most affected feels heard and makes their own choice. | both kept, equal chance (owner, 2026-11-15) |
| MIX-009 | choice C outcome 1 (alternative) | A long-held misunderstanding is gently corrected. | The result works better than expected, though nobody claims universal proof. | both kept, equal chance (owner, 2026-11-15) |
| MIX-010 | choice D outcome 2 (alternative) | Someone feels excluded and withdraws from the gathering. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-015 | choice C outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-016 | choice A outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-016 | choice B outcome 1 (alternative) | The result inspires a new song, pattern, or story. | The person most affected feels heard and makes their own choice. | both kept, equal chance (owner, 2026-11-15) |
| MIX-016 | choice D outcome 1 (alternative) | A long-held misunderstanding is gently corrected. | The result works better than expected, though nobody claims universal proof. | both kept, equal chance (owner, 2026-11-15) |
| MIX-016 | choice D outcome 2 (alternative) | The villagers discover that confidence was mistaken for competence. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-020 | choice C outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-021 | first villager's personality (alternative) | insecure | cautious | both kept, equal chance (owner, 2026-11-15) |
| MIX-022 | choice A outcome 2 (alternative) | The effort causes minor injury or exhaustion, requiring rest and care. | The action creates a new dispute that needs a separate conversation. | both kept, equal chance (owner, 2026-11-15) |
| MIX-023 | choice B outcome 2 (alternative) | A small success comes with an unexpected embarrassment. | Everyone is safe, though the result is awkward and disappointing. | both kept, equal chance (owner, 2026-11-15) |
| MIX-025 | choice A outcome 1 (alternative) | A long-held misunderstanding is gently corrected. | The result works better than expected, though nobody claims universal proof. | both kept, equal chance (owner, 2026-11-15) |
| MIX-027 | second villager's personality (alternative) | tired | thoughtful | both kept, equal chance (owner, 2026-11-15) |
| MIX-027 | second villager's role | a chief | a council member | no game has both roles (the chief is VV3 only, the practitioners VV5 only) |
| MIX-029 | choice C outcome 1 (alternative) | A long-held misunderstanding is gently corrected. | The result works better than expected, though nobody claims universal proof. | both kept, equal chance (owner, 2026-11-15) |
| MIX-030 | choice C outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-030 | choice D outcome 1 (alternative) | The result inspires a new song, pattern, or story. | The person most affected feels heard and makes their own choice. | both kept, equal chance (owner, 2026-11-15) |
| MIX-031 | choice A outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-031 | choice B outcome 2 (alternative) | Someone feels excluded and withdraws from the gathering. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-031 | choice D outcome 2 (alternative) | The villagers discover that confidence was mistaken for competence. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-032 | choice A outcome 2 (alternative) | The effort causes minor injury or exhaustion, requiring rest and care. | The action creates a new dispute that needs a separate conversation. | both kept, equal chance (owner, 2026-11-15) |
| MIX-033 | second villager's personality (alternative) | superstitious | devout | both kept, equal chance (owner, 2026-11-15) |
| MIX-035 | choice D outcome 2 (alternative) | Someone feels excluded and withdraws from the gathering. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-037 | choice B outcome 2 (alternative) | The villagers discover that confidence was mistaken for competence. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-038 | first villager's personality (alternative) | superstitious | devout | both kept, equal chance (owner, 2026-11-15) |
| MIX-040 | choice B outcome 1 (alternative) | A novice gains experience while a master gains perspective. | The person most affected feels heard and makes their own choice. | both kept, equal chance (owner, 2026-11-15) |
| MIX-040 | choice D outcome 1 (alternative) | The result inspires a new song, pattern, or story. | The person most affected feels heard and makes their own choice. | both kept, equal chance (owner, 2026-11-15) |
| MIX-042 | choice B outcome 1 (alternative) | A long-held misunderstanding is gently corrected. | The result works better than expected, though nobody claims universal proof. | both kept, equal chance (owner, 2026-11-15) |
| MIX-042 | choice B outcome 2 (alternative) | The villagers discover that confidence was mistaken for competence. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-042 | choice D outcome 2 (alternative) | A small success comes with an unexpected embarrassment. | Everyone is safe, though the result is awkward and disappointing. | both kept, equal chance (owner, 2026-11-15) |
| MIX-045 | first villager's personality (alternative) | insecure | cautious | both kept, equal chance (owner, 2026-11-15) |
| MIX-047 | choice A outcome 2 (alternative) | The effort causes minor injury or exhaustion, requiring rest and care. | The action creates a new dispute that needs a separate conversation. | both kept, equal chance (owner, 2026-11-15) |
| MIX-050 | choice C outcome 2 (alternative) | A rushed choice wastes scarce supplies. | A promising idea is abandoned before it can be evaluated fairly. | both kept, equal chance (owner, 2026-11-15) |
| MIX-050 | first villager (doubled word, grammar fix) | a confident a confident novice | a confident novice | role le_role_confident_novice x personality le_pers_confident |
| MIX-051 | second villager's personality (alternative) | tired | thoughtful | both kept, equal chance (owner, 2026-11-15) |
| MIX-052 | choice A outcome 2 (alternative) | The effort causes minor injury or exhaustion, requiring rest and care. | The action creates a new dispute that needs a separate conversation. | both kept, equal chance (owner, 2026-11-15) |
| MIX-052 | choice B outcome 2 (alternative) | The villagers discover that confidence was mistaken for competence. | The attempt fails and the participants must admit uncertainty. | both kept, equal chance (owner, 2026-11-15) |
| MIX-052 | choice C outcome 1 (alternative) | Two different customs coexist without either disappearing. | The person most affected feels heard and makes their own choice. | both kept, equal chance (owner, 2026-11-15) |
| MIX-053 | choice B outcome 2 (alternative) | A small success comes with an unexpected embarrassment. | Everyone is safe, though the result is awkward and disappointing. | both kept, equal chance (owner, 2026-11-15) |
| MIX-053 | second villager's personality (alternative) | forgetful | thoughtful | both kept, equal chance (owner, 2026-11-15) |
| MIX-054 | first villager (doubled word, grammar fix) | a skeptical a skeptical observer | a skeptical observer | role le_role_skeptical_observer x personality le_pers_skeptical |
| MIX-055 | second villager's personality (alternative) | blunt | stubborn | both kept, equal chance (owner, 2026-11-15) |
| MIX-056 | first villager's personality (alternative) | tired | thoughtful | both kept, equal chance (owner, 2026-11-15) |
| MIX-056 | second villager's personality (alternative) | insecure | cautious | both kept, equal chance (owner, 2026-11-15) |
| MIX-057 | second villager's personality (alternative) | superstitious | devout | both kept, equal chance (owner, 2026-11-15) |
| MIX-057 | second villager's role | a chief | a council member | no game has both roles (the chief is VV3 only, the practitioners VV5 only) |
<!-- living-mixer: end -->

## 8. The MC bank (95 situations, 760 outcomes)

- Each situation keeps the owner's SETUP, its four approaches and its eight outcomes exactly. Location, participant and outcome-dimension pools (L25156-25158: 20 / 23 / 15) are tags only unless the owner gives a frame sentence for them.
- **Subject cast:** a stranger for every LOS situation and any setup about a visitor, stranger or traveler; a child (3-13) where the setup is about a child; otherwise a villager 14+. Effects never land on a stranger.
- **Effects** follow what each outcome line says (owner, 2026-11-14). No line in the library says that anyone dies or goes missing, so MC has no kill or vanish. Mapped lines:

| Line | Outcome | Effect |
|---|---|---|
| L25680 (ISL-02 A2) | The improved pigment costs more fruit than the seller can spare. | food small loss |
| L25686 (ISL-02 D2) | Refunding the festival orders empties the seller's supply basket. | food small loss |
| L25694 (ISL-03 C2) | The traditional dish remains unsold until the fruit spoils. | food small loss |
| L25713 (ISL-05 C1) | The preserved fish feeds the fisher's household later. | food small |
| L25714 (ISL-05 C2) | Poor drying weather ruins part of the rare catch. | food small loss |
| L25722 (ISL-06 B2) | The helpers require more supplies than the merchant expected. | food small loss |
| L25739 (ISL-08 A1) | The child begins learning a chosen craft without family pressure. | skill small (Building) on subject |
| L25750 (ISL-09 A2) | Correcting every trade consumes much of the merchant's stored supplies. | food small loss |
| L25813 (ISL-15 C1) | Experienced mask-makers teach the novice a careful painting technique. | skill small (Building) on subject |
| L25890 (DIS-03 A2) | Discarding the damaged stores leaves families with smaller meals. | food small loss |
| L25894 (DIS-03 C2) | The redistribution leaves the festival kitchen without its planned supplies. | food small loss |
| L25895 (DIS-03 D1) | Villagers learn to dry fruit more thoroughly before storing it. | tech small |
| L25896 (DIS-03 D2) | Unexpected rain spoils a new batch despite careful lessons. | food small loss |
| L25913 (DIS-05 C1) | Hardier crops survive with fewer watering trips. | tech small |
| L25914 (DIS-05 C2) | The new crops yield less food than the familiar varieties. | food small loss |
| L25919 (DIS-06 A1) | The celebration moves to a sheltered courtyard away from the insects. | celebrate (all) |
| L25923 (DIS-06 C1) | Fresh leaf ornaments brighten the festival. | celebrate (all) |
| L25974 (DIS-11 C2) | The extra work leaves fewer hands for harvesting. | food small loss |
| L25975 (DIS-11 D1) | Cleaning shared harnesses reduces new cases of illness. | tech small |
| L25981 (DIS-12 B1) | The postponed festival takes place when families feel more ready. | celebrate (all) |
| L26035 (AFT-02 D1) | The families cooperate to harvest fruit despite their disagreement. | food small |
| L26079 (AFT-07 A1) | Both families harvest the orchard on agreed days. | food small |
| L26331 (TRA-02 B1) | A friendly wave lets the newcomer join the celebration comfortably. | celebrate (all) |
| L26440 (TRA-13 A2) | The modified steps still cause discomfort, so the villager rests. | health -10..-5 on subject |
| L26444 (TRA-13 C2) | The villager leaves early when the pain returns. | health -10..-5 on subject |
| L26501 (BEL-04 B1) | Patient practice helps the child complete a simple woven band. | skill small (Building) on subject |
| L26511 (BEL-05 B1) | Children learn to mend torn garments and admire the repaired stitching. | skill small (Building) on subject |
| L26571 (BEL-11 B1) | A mentor demonstrates a difficult technique without taking over. | skill small (Building) on subject |
| L26573 (BEL-11 C1) | Specific feedback helps the apprentice improve a weak knot. | skill small (Building) on subject |
| L26575 (BEL-11 D1) | The apprentice manages real supplies under supervision. | skill small (Building) on subject |
| L26595 (BEL-13 D1) | The child pursues a chosen skill while remaining close to family. | skill small (any) on subject |

- Every other MC outcome has no effect: the contract (L25147) asks to avoid boilerplate trust and skill bonuses, and most lines are about feelings and relationships the games cannot store.
- Text-only on purpose: L25772 (a sick villager needs the healer's guidance: the sickness predates the event); L25976 (a working animal falls ill: no animal health in the games); L25872 (a high tide washes away repaired seating: not a game structure).

## 9. The MJ bank (35 seeds, held)

Contract (L26622), turned into checks for when outcomes arrive:

- no harmful effects (no kill, vanish, die_unrecovered, sick, health loss, mood bad)
- no diagnostic labels in any joining words
- no supernatural confirmation (no archetype tagged resolves)
- detention is text only (no effect)
- a suspected crime stays unproven: no outcome names a culprit by role

## 10. Open owner questions (with the recommended default)

| Q | Question | Recommended default |
|---|---|---|
| Q3 | Should a seed's MIX example be drawn first (variant 0 the first time the seed appears), or be just one variant among the K? | Just one variant, with the same chance as the others; the recency rule already spreads seeds. |
| Q5 | Which games get the Magic and Nature practitioners, and the chief? | Practitioners VV5 only (Devotion); the chief role VV3 only (the Tribal Chief); in seeds that name the chief, the other games say "the village leader". |
| Q6 | Should some seeds carry their own effect (a hair colour change for PER-01, small tech for ART-01/ART-10, small food for FOO-05/FOO-09)? | No seed effects for now: effects come only from the archetypes. The proposals stay in `seed_effects` marked proposed. |
| Q7 | Rare weights: good 20 / adverse 20 / rare 2 per choice? | Yes: 20 / 20 / 2, so a RARE outcome is about 1 in 21 per choice. |
| Q8 | Recency window: how many seeds must pass before a seed repeats? | One third of the seeds possible now (about 40 of 120). |
| Q11 | Credit for the MC and MJ banks (the file gives one credit, L23815, for the Living Engine section). | Use the same credit line for MC and MJ. |

## 11. Unclear items (decided conservatively, listed for the owner)

- **U1.** Seed tags (personal, somber, child, adult-only and the rest) are judgement calls; see section 2.
- **U2.** "Master" roles are cast at skill 50+. VV titles call a villager a master only at full skill, which few young villages have.
- **U3.** PER-05 (a mask at a celebration) is VV5 only, by source rule 9 (masks only in VV5).
- **U4.** The rule exclusions (C9, P1, P3) conflict with 3 of the owner's 60 MIX examples (section 7).
- **U5.** "Teenager" is cast at 14-17 and "child" at 3-13; "apprentice", "rookie" and "confident novice" at 14-24.

