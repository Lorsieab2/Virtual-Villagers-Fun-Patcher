/* VVFP Heathen Life -- New Believers: the Heathens' own camp life (workstream W-B of "Heathen Tribe Expansion and
   Evolution", docs/heathen-tribe-expansion-design.md sections 7, 8 and 10, with the owner's decisions of 2026-11-26
   in docs/heathen-tribe-expansion-decisions.md, which override the design).  It runs only with the row's flag file
   "VVFP Heathen Tribe Evolution.txt" (native/shared/heathen_evo.h HE_FLAG_ROW) beside it; without it nothing is
   installed and the export answers 0 (the stock rule).

   THE STOCK GAME (every address read from the stock executable with capstone).
     The life tick 0x472C90 skips a Heathen at 0x472CB7: it copies the age into the processed age and clears the
     sick byte +0x1C48, so a Heathen never eats, falls sick, loses or regains health or practises.  The believers'
     next-action picker 0x46F070 sends a Heathen (`cmp byte [edx+0x1CEC], bl; je` at 0x46F0BA) to the Heathen AI
     0x46E9E0: camp life by role, never a harvest, a facility, a skill check or a cure.  The believers' healers never
     look at a Heathen (the sick finder 0x470B50: `cmp byte [esi+0x1CEC], 0; jne` at 0x470B7F).

   WHAT THIS DOES.

   1. THE LIFE UNIT (the bridge export VvfpHeathenLifeUnit, called by "VVFP Heathen Aging.dll" from its life-tick
      splice 0x472CB7 once a unit for every aging Heathen, and every pass with HE_LIFE_IDLE to ask about the sick
      byte; heathen_evo.h section 3).  Only with HE_LIFE_ROW in the flags, for a living Heathen.  In order, as the
      believers' half of the unit (0x472EA0..0x472FC1), every chance drawn from this companion's own xorshift
      (native/shared/slider_scale.h's rule: the game's rand is never drawn more or less often):
        sickness damage   (0x472EA0..0x472ED1) on a roll of 60 or less in 100, when health is over 20 or a second
                          roll is 30 or less: -1 health, never below the floor (decision 8: 21, the options file's
                          sick_floor; the game's "low health" line is 20), written straight into +0x1C40 -- never
                          AddHealth, never a cause that can kill: a sick Heathen never dies of it;
        recovery          (0x472F44..0x472F77) a Heathen who is not sick gains 1 health (an elder, 0x46F790, only on
                          a roll under 20 in 100), at most 100.  The believers' food, hospital and Medicine gate
                          (0x472EE2..0x472F42) is not applied: the food store is the believers';
        getting sick      the believers' onset 0x465F50, rule for rule: on the easiest difficulty (game +0x17D54 = 0,
                          0x472F81 and 0x465F58) half the units never roll; Medicine 1 rand(1440) <= 3, Medicine 2
                          rand(2460) <= 3, Medicine 3 rand(5400) <= 2; then an elder (age >= 160 x Medicine + 840,
                          0x46F790) rand(1000) <= 14.  Only an ordinary Heathen (role 0..11): the puzzle Heathens
                          (12..17) keep their stock life, so no puzzle is changed.  A new sickness stops what they do
                          (0x473440) and starts the sick look below, as a believer's starts behaviour 0x20;
        being healed      (decision 8) an ordinary adult Heathen with Healing skill (role 0..11, never the puzzle
                          Heathen Doctor, role 12; not sick, not expecting, not held) is the camp's doctor: the one
                          with the best Healing goes to the patient (the believers' healer walk, 0x46CD86..0x46CDA1:
                          the patient's spot +10 down, distance 150) with the believers' healing look (0x45D060: its
                          animation 0x11, waits and gestures) while the patient waits (0x45CFD0's pose; labels in
                          section 4).  At the patient's next unit the doctor's skill check decides, by the believers'
                          own rule (0x46B270, below): pass, the sickness ends (as 0x468CCB / 0x46E1FB end it); fail,
                          another doctor or another try later.  People Cured (0x51D368, which 0x468D4D and 0x46E202
                          bump) is never written: Heathen cures never count.  With no Heathen able to heal they get
                          well on their own, 1 in 240 a unit (about once a day of game time);
        practice          (decision 17's skills; design section 10) the skill of the show action just done (below),
                          or on 1 unit in 20 the skill of the Heathen's role (1, 11 Farming; 2, 10 Research; 6-9
                          Building; 5 Parenting; 4 Healing; 0, 3 their best), for an ordinary adult Heathen who is
                          not sick.  The believers' skill check 0x46B270 rule for rule: it passes on rand(100) <=
                          skill + 33 (66 liking Learning, 16 disliking it; preference 0x27 in +0x1F5C / +0x1F68);
                          the gain (70 - skill) / 18, at least 7 from 0, halved for a disliker and doubled for a
                          liker, and when that is 0, 1 on rand(100) <= 50 and rand(100) >= skill; nothing at 100; a
                          failure at exactly 0 gives 4 (0x469D90 / 0x49893C).  With no tech bonus (Learning and
                          Spirituality are the believers' techs) and written straight into the float, clamped to
                          0..100: never the adder 0x475730 (mastery trophies) or the check itself (messages, the
                          activity stop).  Devotion is practised at the statue and at the mud hut (below).
      It answers HE_LIFE_KEEP_SICK while the Heathen is sick (Heathen Aging then keeps the byte the stock skip would
      clear) and HE_LIFE_HANDLED.

   2. SHOW ACTIONS (the run-time splice at 0x46F0BA).  When an ordinary Heathen (role 0..11) runs out of things to
      do, and it is not raining (0x477040: weather 2, 3 or 5): a sick Heathen always takes the sick look (walk to the
      encampment, walk area 0x39, at the sick pace 40, and the believers' sick pose: gesture rand(40) + 15 of
      animation 9, as 0x45C3A0 does); an adult who is not expecting, on show_percent of the picks (the options file;
      25 when unset), takes one show action from those open to it; everything else goes to the stock Heathen AI as
      before.  A show action is the game's own step adders only -- walk to an area 0x4744C0, walk to a point
      0x4745A0, gesture 0x474450, wait 0x4747E0, carry 0x474D80, drop 0x474DE0, animation 0x475160, then the
      queue's start 0x473590 -- the steps the believers' own scripts use, with their skill-check step (type 0x0A)
      and their payoff step (type 0x14, the work dispatcher 0x46CE60) left out, so no source, store, building,
      tech point or skill of the believers is touched by it:
        harvests (decision 9), each only once the puzzle that opens it to the believers is solved, carried to the
        encampment (area 0x39), never the granary (area 5):
          noni   the Fence (project 2: the noni bush handler 0x47A4B6 refuses before it), area 0x1A, the
                 believers' look (0x457910: gestures of animation 0xF, carry 0);
          crops  the Hydroponic Farm (project 5: the field's handler 0x47A525), the farm plots (area 0x52, the
                 believers' 0x457C80), carry 0 -- this is also the farm plots' visit;
          fish   The Lake (project 10: the dispatcher 0x46C600), area 0x69, the believers' 0x463B20, carry 0x38;
        facilities (decision 10), a walk, two gestures and a wait, then back to the encampment:
          the spa         the pools, area 0x7C (0x45C000's walk; its payoff step 0x16, the soak, left out);
          the statue      the Believer Idol, once carved (project 14), area 0x45 (where the believers show a baby
                          "the statue", 0x462430); Devotion practised; while carved to stage 1 or 2 (+8 of the
                          statue 0x51D950), one visit in two is the believers' Confused look (section 5);
          the science lab area 0x0E (0x45A890's walk); Research practised;
          the Love Shack  once built (project 23), its walk area (+0x14, 0x11), waiting at its door: no
                          embrace step (0x474CE0) and no conception; only at the couples' ages (18 to 49: the
                          partner search 0x470A53 / 0x470A8F, the embrace 0x468A00);
          the Clothing Hut once built (project 22), its walk area (+0x14, 0x10), looking at the clothes: no
                          clothes (work event 90 is never queued);
          a building's area is used only while the map has cells for it (read from the live map 0x718EE8, the
          area field the walk picker 0x477B90 reads: cell >> 4 & 0x7FF), so a walk never aims at a spot the game
          has not drawn;
        a show meal, at the encampment: the believers' eating look (0x457D30: animation 0x6F, gestures) with no
        payoff step 0x57, so the food store is never touched -- Heathens never eat from it and never starve;
        devotion at the mud hut: the believers' praising pose (gesture 0x1E of animation 0x10, as 0x4598A0's) on the walkable ground
        in front of the hovel (2176..2271 x 1576..1599, the Memorial Actions at the Heathen Hovel row's points);
        Devotion practised.
      AGE RULES (the owner, 2026-11-26: Heathens do only what believers of their age do).  Every action above is an
      adult's (14 or older: the picker's child test 0x46F117 sends a believer child to the children's routine
      0x46E3F0, an adult to the dispatcher, chooser and player's job, which test no age: elders do all of it), the
      Love Shack's the couples' ages.  A Heathen CHILD gets only the nursery play believer children get and Heathen
      children do not (0x46E447 skips them): walk area 0x22 ("Going to play in the nursery"), while someone is
      teaching at the nursery school (0x43A810, as 0x46E433 asks).  No adult visits the nursery.

   3. PEOPLE CURED (decision 8: a Heathen's cure never counts, a believer healer's included).  The drag-a-healer
      cure's +1 (0x468D4D) is skipped when its patient was a Heathen as the cure began (noted at 0x468C3C), the
      Village Statistics row's own guard; when that row is applied its detours are already there and are left alone
      (see SITE_CURE_BEGIN below).
      The record's behaviour id +0x1D10 is the Heathens' own camp wander 0x9C.  The stock Heathens' noni eating
      (behaviour 0x97, role 1) is vanilla and left alone.

   4. THE DETAILS TEXT (the owner, 2026-11-27: "the labels aren't super descriptive. please change them to describe
      where they are going and what they are doing", then "and practicing skills too").  A show action's Details
      text (+0x1D14, the text the Details screen and the hover line show) says where the Heathen is going; when the
      walk ends the game's own text step (type 6, added by 0x474270, which the believers' scripts use through
      0x4742E0 and 0x43821F) changes it to what they do there -- "Practising <skill> at <place>" where a skill is
      practised -- and again on the walk back ("Going back to the camp", or for a harvest what they carry).  The
      doctor's lines name the patient when they fit.  Each text is the patcher's own, in the player's language
      through "VVFP Translations.dll" (native/shared/vvfp_translate.h; rows "vvfp.heathen_life/...label.*" of
      data/translations/patcher_strings.json), and at most 37 characters in English -- the longest Details text the
      stock game writes itself -- within the field's 0x27 bytes.  A child's walk to the nursery keeps the game's own
      line (text 0x35).  Role practice (1 unit in 20) has no action of its own, so it shows no text: the Heathen
      goes on with the stock Heathen AI's action and its own line.

   5. THE HEATHENS ACT LIKE BELIEVERS (the owner, 2026-11-27: "talk to each other and do practically almost every
      action believers do. they are humans too!", look-only; 2026-11-28: "the villagers should be able to take
      primary control of the village after puzzles get completed. heathens shouldn't all en-masse do a single
      action or stay in the encampment all the time. just occasional walking and doing stuff per heathen").
        More looks, each the believers' own steps for it (walk, poses 0x4749C0 / 0x474970 / 0x474B00 / 0x474BA0 /
        0x474C40 / 0x474AB0, gestures, sounds 0x475160 and their stop 0x4751D0, effects 0x474F50) with this
        companion's numbers and never a skill-check or payoff step: the science lab with the believers' research
        poses (0x45A890), the Believer Idol with their honoring (0x45CB70); the adult chooser's leisure 0x46A3C0 --
        cooling feet in the stream (0x459110), washing in it (0x455B50), relaxing (0x459790), watching the clouds
        (0x462C00), the lake once The Lake is solved (0x457E00), the waterfall (0x45C960), dancing (0x4575D0),
        bathing (0x455CA0); a chat (0x4598A0's partner pose and talk) with an idle Heathen at the encampment or an
        idle believer (one meditating, thinking, staring, relaxing, unsure, watching the clouds, reflecting or
        wandering, carrying nothing, not held, not sick: never one at work, carrying or dropped by the player) --
        neither's Faith or anything else changes; a child's find (0x45BAB0 / 0x45BBF0's pick-up): a mushroom (0x80,
        rare 0x81, golden 0x82) or a collectible (science items 0x50..0x67, relics 0x68..0x7F) carried from where
        the believer children look (areas 0x4C, 0x51) to the encampment and set down there -- only its carry id:
        nothing is taken off the map, counted or made (the drop handler 0x4146B0 counts only at the granary, the
        lab's area 0x0D or area 0x36, never the encampment; a find cut short is taken away by a plain write of
        +0x1D0C, never the drop step).
        THE PACE.  Outings (anything that leaves the encampment) are each Heathen's own: after one, that Heathen
        waits a cool-down of life units (busyness Quiet 30, Normal 15, Lively 8), its first one staggered at
        random; at most away_cap() Heathens are out at once -- about the square root of the tribe's ordinary
        Heathens x 0.4 / 0.75 / 1.1, at least 1 (50 Heathens: 3 / 6 / 8) -- and at most 1 / 2 / 3 on one action;
        one who has not been out for 4 cool-downs goes on their next idle moment (never stuck at the
        encampment).  The believers are primary: no Heathen goes to a place while a believer stands in its walk
        area.  The options file's busyness, away_max, same_action_max and outing_cooldown set these.
        TRAINING (the owner, 2026-11-27: "the untrained heathens should be allowed to choose a skill and practice
        it and eventually master them (same rate as believers, always evenly-distributed)").  An ordinary adult
        Heathen with every skill below 20 (the Details screen's "Untrained", 0x41C680) chooses the unmastered skill
        the fewest Heathens are training (ties at random), practises it on half their show actions (Research at
        the lab, Farming at the farm plots, Devotion at the mud hut, else at the encampment with the believers'
        work look) by the believers' own check (section 1), and on mastering it (100) chooses the next.  The
        choices are kept per save slot by identity in "...\Save <S>\Data\Heathen Training\Heathen Training - Save
        <S>.dat" (native/shared/sidecar_io.h; the slot from the game's save manager, game_save_slot.h).
        MASKS.  A chase (orange) or a fright (red) is the game's own encounter 0x46E2E0, started by nearness
        (0x471C50, 0x471F70) whatever a Heathen is doing: nothing here stops it, and a Heathen chasing (behaviour
        0x14) or a believer running (0x15, 0x16) is never stopped for a sick look, a doctor's visit or a chat.

   NOT LOGGED.  The believers' logs have no sickness, recovery or skill records, so none are written for Heathens.
   Nothing depends on a Heathen's sex.

   SAFETY.  Three splices (0x46F0BA, 8 bytes; 0x468C3C, 8; 0x468D4D, 7 -- the last two only when the Statistics
   row's are not there), stock bytes checked first, all or none (native/shared/install_sites.h).  Every step
   of ours runs under structured exception handling; a fault leaves the stock behaviour.  No debug output; the only
   file written is section 5's training file, and the only text shown is the Details text of section 4. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/sidecar_io.h"
#include "../shared/game_save_slot.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/custom_titles.h"
#include "../shared/heathen_evo.h"
#include "../shared/vvfp_translate.h"

#define HL_GAME 5

/* The villager record (vv5). */
#define R_STRIDE 0x2F44u
#define R_AGE 0x1B8Cu
#define R_NAME 0x1B9Cu
#define R_NAME_CAP 0x19u
#define R_HEALTH 0x1C40u
#define R_SICK 0x1C48u
#define R_PREGNANT 0x1C4Cu
#define R_SKILLS 0x1C5Cu         /* six floats: 0 Farming 1 Parenting 2 Healing 3 Research 4 Building 5 Devotion */
#define R_PRESENT 0x1CD4u
#define R_HELD 0x1CD6u           /* the picker 0x46F070 returns at once while it is set */
#define R_LOOKALIKE 0x1CE1u
#define R_FACTION 0x1CECu
#define R_ROLE 0x1CFCu
#define R_BEHAVIOUR 0x1D10u
#define R_DOING 0x1D14u          /* the Details text, 0x27 bytes (0x47D7C0's count) */
#define R_DOING_CAP 0x27u
#define R_CARRY 0x1D0Cu          /* the carried item, -1 none (0x466420) */
#define R_LIKES 0x1F5Cu
#define R_DISLIKES 0x1F68u
#define R_PREF_SLOTS 3u

#define SKILL_FARMING 0
#define SKILL_PARENTING 1
#define SKILL_HEALING 2
#define SKILL_RESEARCH 3
#define SKILL_BUILDING 4
#define SKILL_DEVOTION 5
#define PREF_LEARNING 0x27
#define ADULT 280                /* 14 years: the Heathen AI's child test 0x46EA5E */
#define ORDINARY_LAST 11         /* roles 12..17 are the puzzle Heathens */
#define CURE_UNITS 1             /* the doctor's visit is judged at the patient's next unit */
#define SELF_CURE 240            /* no Heathen able to heal: 1 in 240 a unit */
#define PRACTICE_ROLL 20         /* role practice on 1 unit in 20 */
#define SHOW_PERCENT_OWN 25      /* show_percent unset (0) */

/* The game. */
#define G_GAME 0x425950u               /* cdecl: the village object */
#define G_DIFFICULTY 0x17D54u          /* +: 0 the easiest */
#define G_MEDICINE 0x51D5D0u           /* the tech levels 0x51D5CC, Medicine [1] */
#define G_WEATHER 0x718EA0u            /* 2, 3, 5 rain (0x477040) */
#define G_MAP 0x718EE8u                /* 320 x 320 cells; walk area = cell >> 4 & 0x7FF (0x477C30) */
#define G_MAP_CELLS 102400u
#define G_AREA_BOXES 0x87              /* the walk picker's per-area boxes (0x4775B4: 135 of them) */
#define G_PUZZLE_PROGRESS 0x51E008u    /* +p*8 */
#define G_PUZZLE_NEEDED 0x51DF30u      /* +p*4 */
#define G_SITES 0x4CBDC0u              /* the building sites: object pointers (0x463C41) */
#define SITE_PROJECT 0x08u             /* the building's project (its constructor's 0x43ABB0 id) */
#define SITE_AREA 0x14u                /* its walk area: the vtable's +0x60 answer (0x463C4A) */
#define G_TEXTS 0x450D40u              /* cdecl: the string table */
#define G_TEXT 0x4506D0u               /* thiscall on it: (id) -> char *; ret 4 */
#define G_STOP 0x473440u               /* thiscall on the record */
#define G_START 0x473590u              /* thiscall on the record: start the queue */
#define G_WALK_AREA 0x4744C0u          /* (area, distance, 0); ret 0xC */
#define G_WALK_POINT 0x4745A0u         /* (x, y, distance, 0); ret 0x10 */
#define G_GESTURE 0x474450u            /* (count, animation); ret 8 */
#define G_WAIT 0x4747E0u               /* (seconds); ret 4 */
#define G_CARRY 0x474D80u              /* (item); ret 4 */
#define G_DROP 0x474DE0u               /* ret */
#define G_ANIM 0x475160u               /* (animation, float speed, count); ret 0xC */
#define G_POSITION 0x466350u           /* (int out[2]) -> out; ret 4 */
/* More of the game's step adders (section 5), each (n) ret 4 unless noted; each step only sets a pose of the
   villager's animator (+0x1C78, 0x4510E0) when the queue's start 0x473590 reaches it, or plays or stops a sound or
   shows an effect from the step runner 0x473B30 -- never a store, a skill or a building. */
#define G_POSE_TALK 0x4749C0u          /* type 0x23: pose 5 (0x4656C0), the believers' talking pose */
#define G_POSE_4 0x474970u             /* type 0x0F: pose 4 (0x465690) */
#define G_POSE_10 0x474B00u            /* type 0x27: pose 0x10 (0x465780) */
#define G_POSE_29 0x474BA0u            /* type 0x29 (watching the clouds, 0x462C45) */
#define G_POSE_2E 0x474C40u            /* type 0x2E (0x465B40) */
#define G_POSE_26 0x474AB0u            /* type 0x26 */
#define G_SOUND_END 0x4751D0u          /* type 0x1C, (): stops the sound a 0x475160 step played (0x44C0A0) */
#define G_EFFECT 0x474F50u             /* type 0x16, (a, b, c); ret 0xC: an effect at the villager (0x41D460) */
#define G_GESTURE_AT 0x474370u         /* type 3, (count, 0, frame, frame); ret 0x10: Confused's head shakes (0x4594CA) */
#define G_STATUE 0x51D950u             /* the statue object: its stage at +8 (0x4271C0); 1 or 2 carved, waiting for
                                          technology (0x46CDC6, the believers' Honoring offer) */
#define STATUE_STAGE 0x08u
#define G_TEXT_STEP 0x474270u          /* (const char *text); ret 4: a step of type 6 holding the text (copied, 0x27
                                          bytes, into the step's +0x28); when the queue reaches it the queue's start
                                          0x473590 copies it into the Details text +0x1D14 (0x473743) -- the game's
                                          own mid-script text change (0x4742E0 wraps it for a string id) */

#define CAMP_WANDER 0x9C               /* the Heathens' own behaviour id (0x46F00C) */

/* Walk areas (each the first area the believers' own script walks to). */
#define A_CAMP 0x39
#define A_NONI 0x1A
#define A_CROPS 0x52
#define A_LAKE 0x69
#define A_POOLS 0x7C
#define A_STATUE 0x45
#define A_LAB 0x0E

/* Projects (0x51E008; the constructors' 0x43ABB0 ids). */
#define P_FENCE 2
#define P_FARM 5
#define P_LAKE 10
#define P_IDOL 14

/* Building sites in 0x4CBDC0 (CHouse1..3 0..2, CClothingHut 3, CLoveShack 4, CNurseryHut 5). */
#define SITE_CLOTHING 3
#define SITE_LOVE 4

/* A Heathen child's walk to the nursery: the believer children's own line (0x460F00, "Going to play in the
   nursery"), the game's text id. */
#define T_NURSERY_PLAY 0x35
/* Every other Details text is the patcher's own (labels(), below): where the Heathen is going, then what they do
   there, each changed by the game's own text step when the walk ends. */
#define LABEL_LONGEST 37               /* the longest Details text the stock game itself writes (0x268, 0x181) */

#define A_NURSERY_PLAY 0x22            /* the believer children's nursery play walks here (0x460F29) */
#define G_TEACHER 0x43A810u            /* al: someone is "Teaching at the nursery school" (0x4717A0(0x6F, 0)) */

/* Age rules (the believers'): the picker 0x46F070 sends a child (age < 280, 0x46F117) to the children's routine
   0x46E3F0 and every adult to the job dispatcher 0x46C540 / the chooser 0x46A3C0 / the player's job 0x46BCF0, which
   hold no age test of their own (no compare of +0x1B8C anywhere in 0x469D00..0x46E8FA): every adult, elders
   included, works, eats, honors and visits.  The Love Shack is the couples' (the partner search 0x470A10: both 18
   or older, 0x470A53 / 0x468A00; the partner under 50, 0x470A8F). */
#define LOVE_FIRST 360
#define LOVE_LAST 1000

#define SITE_PICKER 0x46F0BAu
#define PICK_BELIEVER 0x46F0CFu
#define PICK_HEATHEN 0x46F0C2u
#define PICK_DONE 0x46F0C9u

/* People Cured (decision 8: a Heathen's cure never counts).  The drag-a-healer cure 0x468C10 finds its patient
   with 0x4706F0, which has no faction test, and adds 1 at 0x468D4D; the purple Heathen Doctor is converted
   (0x468D0D) before the +1, so the faction is noted when the cure BEGINS, at the sickness test 0x468C3C, into the
   routine's free local dword [esp+0x18], exactly as the Village Statistics row does it
   (scripts/build_statistics_features.py).  With that row applied, the two sites already hold its detours (a jmp
   to caves that start `push dword [esi+0x1CEC]; pop dword [esp+0x18]` and `cmp byte [esp+0x18], 0`): they are
   left alone.  Any other bytes there: nothing at all is installed.  The catch-up cure 0x46E1A2 picks its patient
   through 0x470B40, which takes believers only (0x470B7F), so its +1 at 0x46E202 never sees a Heathen. */
#define SITE_CURE_BEGIN 0x468C3Cu
#define CURE_SICK 0x468C61u
#define CURE_NOT_SICK 0x468C44u
#define SITE_CURE_COUNT 0x468D4Du
#define CURE_COUNTED 0x468D54u
#define G_PEOPLE_CURED 0x51D368u

typedef void (__fastcall *tc0_fn)(void *self, void *unused_edx);
typedef void (__fastcall *tc1_fn)(void *self, void *unused_edx, int a);
typedef void (__fastcall *tc2_fn)(void *self, void *unused_edx, int a, int b);
typedef void (__fastcall *tc3_fn)(void *self, void *unused_edx, int a, int b, int c);
typedef void (__fastcall *tc4_fn)(void *self, void *unused_edx, int a, int b, int c, int d);
typedef void (__fastcall *text_step_fn)(void *self, void *unused_edx, const char *text);
typedef void (__fastcall *anim_fn)(void *self, void *unused_edx, int animation, float speed, int count);
typedef int *(__fastcall *position_fn)(void *self, void *unused_edx, int *out);
typedef void *(__cdecl *texts_fn)(void);
typedef const char *(__fastcall *text_fn)(void *self, void *unused_edx, int id);
typedef unsigned char *(__cdecl *game_fn)(void);
typedef unsigned char (__cdecl *teacher_fn)(void);

static int g_installed;
static unsigned char *g_records;
static unsigned int g_slots;
static int g_floor = HE_SICK_FLOOR_DEFAULT;
static int g_show_percent = SHOW_PERCENT_OWN;
static unsigned int g_seed = 0x9E3779B9u;
static int g_pick_result;

/* The doctors' visits, by the patient's record (index + 1; 0 none). */
static int g_doctor[256];
static unsigned int g_doctor_who[256], g_patient_who[256];
static int g_waited[256];
static int g_visiting[256];            /* by the doctor's record: the patient's index + 1 */
/* A show action's skill, practised at the record's next unit (skill + 1; 0 none). */
static int g_practice[256];
static unsigned int g_practice_who[256];

/* The walk areas the live map has cells for (looked at most every 2 s). */
static unsigned char g_area_seen[2048 / 8];
static short g_area_box[G_AREA_BOXES][4];   /* each walk area's cells' box in pixels (x0, y0, x1, y1) */
static DWORD g_areas_at;
static int g_areas_known;

/* Section 5: the outings.  By the record: the action it is out on (+1; 0 none) and whose; the life units it has
   lived (a counter of ours) and the unit its last outing began. */
static int g_out[256];
static unsigned int g_out_who[256];
static int g_away[256];                /* 1 while that outing leaves the encampment */
static int g_units[256];
static int g_last_out[256];
static unsigned int g_paced_who[256];  /* whose counters these are (a reused record starts afresh) */
static int g_busyness = 2;             /* 1 Quiet, 2 Normal, 3 Lively (the options file's busyness) */

static int visiting(int index);

/* ---- numbers and records ---------------------------------------------------------------------------------- */

static unsigned int next_number(void) {
    unsigned int x = g_seed;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g_seed = x;
    return x;
}

static int rnd(int n) {                /* 0..n-1, as the game's rand(n) */
    return n <= 1 ? 0 : (int)(next_number() % (unsigned int)n);
}

static unsigned char *rec_at(int index) {
    return g_records + (size_t)index * R_STRIDE;
}

static int rec_index(const unsigned char *record) {
    UINT_PTR at = (UINT_PTR)record, base = (UINT_PTR)g_records;
    if (g_records == NULL || at < base || (at - base) % R_STRIDE != 0 || (at - base) / R_STRIDE >= g_slots) {
        return -1;
    }
    return (int)((at - base) / R_STRIDE);
}

static int i32(const unsigned char *record, unsigned int at) {
    return *(const int *)(record + at);
}

static int living(const unsigned char *record) {
    return record[R_PRESENT] != 0 && record[R_LOOKALIKE] == 0 && i32(record, R_HEALTH) > 0;
}

static int heathen(const unsigned char *record) {
    return record[R_FACTION] != 0 && living(record);
}

static int ordinary(const unsigned char *record) {
    int role = i32(record, R_ROLE);
    return role >= 0 && role <= ORDINARY_LAST;
}

static unsigned int identity(const unsigned char *record) {
    return vv_title_identity(record, R_NAME, R_NAME_CAP, R_LIKES, R_DISLIKES, R_PREF_SLOTS);
}

static int medicine(void) {
    return *(const volatile int *)(UINT_PTR)G_MEDICINE;
}

static int elder(const unsigned char *record) {   /* 0x46F790 */
    return i32(record, R_AGE) >= 160 * medicine() + 840;
}

static int puzzle_done(int puzzle) {
    return *(const volatile int *)(UINT_PTR)(G_PUZZLE_PROGRESS + (unsigned int)puzzle * 8u)
        >= *(const volatile int *)(UINT_PTR)(G_PUZZLE_NEEDED + (unsigned int)puzzle * 4u);
}

static int raining(void) {
    int weather = *(const volatile int *)(UINT_PTR)G_WEATHER;
    return weather == 2 || weather == 3 || weather == 5;
}

static int easiest(void) {
    const unsigned char *game = ((game_fn)(UINT_PTR)G_GAME)();
    return game != NULL && *(const int *)(game + G_DIFFICULTY) == 0;
}

static float skill(const unsigned char *record, int which) {
    return *(const float *)(record + R_SKILLS + 4u * (unsigned int)which);
}

static int prefers(const unsigned char *record, unsigned int list, int what) {   /* 0x464F90 */
    unsigned int i;
    for (i = 0; i < R_PREF_SLOTS; ++i) {
        if (i32(record, list + 4u * i) == what) {
            return 1;
        }
    }
    return 0;
}

/* ---- the believers' skill check, for a Heathen (0x46B270, no tech bonus, no trophies) ----------------------- */

static int practise(unsigned char *record, int which) {
    float *at = (float *)(record + R_SKILLS + 4u * (unsigned int)which);
    int likes = prefers(record, R_LIKES, PREF_LEARNING);
    int dislikes = prefers(record, R_DISLIKES, PREF_LEARNING);
    int base = likes ? 66 : dislikes ? 16 : 33;
    int s = (int)*at;                       /* 0x47C9B0 truncates */
    int gain;
    float now;
    if (rnd(100) > s + base) {
        if (*at == 0.0f) {                  /* 0x469D90: exactly 0 */
            *at = 4.0f;                     /* 0x49893C */
        }
        return 0;
    }
    if (s >= 100) {
        return 1;
    }
    gain = (70 - s) / 18;
    if (s == 0 && gain < 7) {
        gain = 7;
    }
    if (dislikes) {
        gain /= 2;
    } else if (likes) {
        gain *= 2;
    }
    if (gain <= 0) {
        gain = 0;
        if (rnd(100) <= 50 && rnd(100) >= s) {
            gain = 1;
        }
    }
    now = *at + (float)gain;
    *at = now < 0.0f ? 0.0f : now > 100.0f ? 100.0f : now;
    return 1;
}

static int role_skill(const unsigned char *record) {
    int best = 0, k;
    switch (i32(record, R_ROLE)) {
    case 1: case 11: return SKILL_FARMING;
    case 2: case 10: return SKILL_RESEARCH;
    case 6: case 7: case 8: case 9: return SKILL_BUILDING;
    case 5: return SKILL_PARENTING;
    case 4: return SKILL_HEALING;
    default:
        for (k = 1; k < 6; ++k) {
            if (skill(record, k) > skill(record, best)) {
                best = k;
            }
        }
        return best;
    }
}

/* ---- the Details texts (the owner, 2026-11-27: "describe where they are going and what they are doing") ------ */

enum {
    L_SICK_GO, L_SICK_AT, L_WAIT_HEALER, L_HEAL_GO_ANY, L_HEAL_AT_ANY, L_BACK,
    L_NONI_GO, L_NONI_AT, L_NONI_CARRY, L_NONI_DROP, L_CROPS_GO, L_CROPS_AT, L_CROPS_CARRY, L_CROPS_DROP,
    L_FISH_GO, L_FISH_AT, L_FISH_CARRY, L_FISH_DROP,
    L_POOLS_GO, L_POOLS_AT, L_STATUE_GO, L_STATUE_AT, L_LAB_GO, L_LAB_AT, L_LOVE_GO, L_LOVE_AT,
    L_CLOTHING_GO, L_CLOTHING_AT, L_MEAL_GO, L_MEAL_AT, L_MUD_HUT_GO, L_MUD_HUT_AT, L_NURSERY_AT,
    /* section 5: the believers' own leisure, the chats, practice at the encampment, the children's finds */
    L_CHAT_GO_ANY, L_CHAT_AT_ANY, L_FEET_GO, L_FEET_AT, L_WASH_GO, L_WASH_AT, L_RELAX_GO, L_RELAX_AT,
    L_CLOUDS_GO, L_CLOUDS_AT, L_LAKE_GO, L_LAKE_AT, L_FALLS_GO, L_FALLS_AT, L_DANCE_GO, L_DANCE_AT,
    L_BATH_GO, L_BATH_AT,
    L_TRAIN_GO_FARMING, L_TRAIN_AT_FARMING, L_TRAIN_GO_PARENTING, L_TRAIN_AT_PARENTING,
    L_TRAIN_GO_HEALING, L_TRAIN_AT_HEALING, L_TRAIN_GO_RESEARCH, L_TRAIN_AT_RESEARCH,
    L_TRAIN_GO_BUILDING, L_TRAIN_AT_BUILDING,
    L_FIND_GO_MUSHROOMS, L_FIND_GO_COLLECTIBLES,
    L_FIND_MUSHROOM, L_FIND_MUSHROOM_CARRY, L_FIND_MUSHROOM_DROP,
    L_FIND_RARE, L_FIND_RARE_CARRY, L_FIND_RARE_DROP,
    L_FIND_GOLDEN, L_FIND_GOLDEN_CARRY, L_FIND_GOLDEN_DROP,
    L_FIND_LAB, L_FIND_LAB_CARRY, L_FIND_LAB_DROP,
    L_FIND_RELIC, L_FIND_RELIC_CARRY, L_FIND_RELIC_DROP, L_STATUE_CONFUSED
};

/* Each label in the player's language (Translations: native/shared/vvfp_translate.h), at most the Details text's
   0x27 bytes with its NUL; the English is at most LABEL_LONGEST characters, as the game's own. */
static const char *label(int which) {
    switch (which) {
    case L_SICK_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.sick_go", "Going home to the camp, sick", R_DOING_CAP);
    case L_SICK_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.sick_at", "Resting at the camp, sick", R_DOING_CAP);
    case L_WAIT_HEALER: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.wait_healer", "Waiting for the healer", R_DOING_CAP);
    case L_HEAL_GO_ANY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.heal_go_any", "Going to heal someone sick", R_DOING_CAP);
    case L_HEAL_AT_ANY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.heal_at_any", "Practising Healing on the sick", R_DOING_CAP);
    case L_BACK: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.back", "Going back to the camp", R_DOING_CAP);
    case L_NONI_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.noni_go", "Going to the noni bushes", R_DOING_CAP);
    case L_NONI_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.noni_at", "Practising Farming at the noni bushes", R_DOING_CAP);
    case L_NONI_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.noni_carry", "Bringing noni home to the camp", R_DOING_CAP);
    case L_NONI_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.noni_drop", "Dropping off noni at the camp", R_DOING_CAP);
    case L_CROPS_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.crops_go", "Going to the farm plots", R_DOING_CAP);
    case L_CROPS_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.crops_at", "Practising Farming at the farm plots", R_DOING_CAP);
    case L_CROPS_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.crops_carry", "Bringing crops home to the camp", R_DOING_CAP);
    case L_CROPS_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.crops_drop", "Dropping off crops at the camp", R_DOING_CAP);
    case L_FISH_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.fish_go", "Going fishing at the lake", R_DOING_CAP);
    case L_FISH_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.fish_at", "Practising Farming at the lake", R_DOING_CAP);
    case L_FISH_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.fish_carry", "Bringing a fish home to the camp", R_DOING_CAP);
    case L_FISH_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.fish_drop", "Dropping off a fish at the camp", R_DOING_CAP);
    case L_POOLS_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.pools_go", "Going to the pools", R_DOING_CAP);
    case L_POOLS_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.pools_at", "Relaxing by the pools", R_DOING_CAP);
    case L_STATUE_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.statue_go", "Going to the statue", R_DOING_CAP);
    case L_STATUE_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.statue_at", "Practising Devotion at the statue", R_DOING_CAP);
    case L_LAB_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.lab_go", "Going to the lab", R_DOING_CAP);
    case L_LAB_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.lab_at", "Practising Research at the lab", R_DOING_CAP);
    case L_LOVE_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.love_go", "Going to the love shack", R_DOING_CAP);
    case L_LOVE_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.love_at", "Waiting at the love shack", R_DOING_CAP);
    case L_CLOTHING_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.clothing_go", "Going to the clothing hut", R_DOING_CAP);
    case L_CLOTHING_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.clothing_at", "Looking at the clothes", R_DOING_CAP);
    case L_MEAL_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.meal_go", "Going to eat at the camp", R_DOING_CAP);
    case L_MEAL_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.meal_at", "Eating at the camp", R_DOING_CAP);
    case L_MUD_HUT_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.mud_hut_go", "Going to the mud hut", R_DOING_CAP);
    case L_MUD_HUT_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.mud_hut_at", "Practising Devotion at the mud hut", R_DOING_CAP);
    case L_NURSERY_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.nursery_at", "Playing in the nursery", R_DOING_CAP);
    case L_CHAT_GO_ANY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.chat_go_any", "Going to chat with someone", R_DOING_CAP);
    case L_CHAT_AT_ANY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.chat_at_any", "Chatting with a neighbour", R_DOING_CAP);
    case L_FEET_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.feet_go", "Going to the stream", R_DOING_CAP);
    case L_FEET_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.feet_at", "Cooling their feet in the stream", R_DOING_CAP);
    case L_WASH_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.wash_go", "Going to wash in the stream", R_DOING_CAP);
    case L_WASH_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.wash_at", "Washing in the stream", R_DOING_CAP);
    case L_RELAX_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.relax_go", "Going off to relax", R_DOING_CAP);
    case L_RELAX_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.relax_at", "Relaxing for a while", R_DOING_CAP);
    case L_CLOUDS_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.clouds_go", "Going to watch the clouds", R_DOING_CAP);
    case L_CLOUDS_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.clouds_at", "Watching the clouds go by", R_DOING_CAP);
    case L_LAKE_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.lake_go", "Going to the lake", R_DOING_CAP);
    case L_LAKE_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.lake_at", "Relaxing by the lake", R_DOING_CAP);
    case L_FALLS_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.falls_go", "Going to the waterfall", R_DOING_CAP);
    case L_FALLS_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.falls_at", "Admiring the waterfall", R_DOING_CAP);
    case L_DANCE_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.dance_go", "Going off to dance", R_DOING_CAP);
    case L_DANCE_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.dance_at", "Dancing for fun", R_DOING_CAP);
    case L_BATH_GO: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.bath_go", "Going to bathe", R_DOING_CAP);
    case L_BATH_AT: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.bath_at", "Having a bath", R_DOING_CAP);
    case L_TRAIN_GO_FARMING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_go_farming", "Going to practise Farming", R_DOING_CAP);
    case L_TRAIN_AT_FARMING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_at_farming", "Practising Farming at the camp", R_DOING_CAP);
    case L_TRAIN_GO_PARENTING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_go_parenting", "Going to practise Parenting", R_DOING_CAP);
    case L_TRAIN_AT_PARENTING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_at_parenting", "Practising Parenting at the camp", R_DOING_CAP);
    case L_TRAIN_GO_HEALING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_go_healing", "Going to practise Healing", R_DOING_CAP);
    case L_TRAIN_AT_HEALING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_at_healing", "Practising Healing at the camp", R_DOING_CAP);
    case L_TRAIN_GO_RESEARCH: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_go_research", "Going to practise Research", R_DOING_CAP);
    case L_TRAIN_AT_RESEARCH: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_at_research", "Practising Research at the camp", R_DOING_CAP);
    case L_TRAIN_GO_BUILDING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_go_building", "Going to practise Building", R_DOING_CAP);
    case L_TRAIN_AT_BUILDING: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.train_at_building", "Practising Building at the camp", R_DOING_CAP);
    case L_FIND_GO_MUSHROOMS: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_go_mushrooms", "Going to look for mushrooms", R_DOING_CAP);
    case L_FIND_GO_COLLECTIBLES: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_go_collectibles", "Going to look for collectibles", R_DOING_CAP);
    case L_FIND_MUSHROOM: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_mushroom", "Picking up a mushroom", R_DOING_CAP);
    case L_FIND_MUSHROOM_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_mushroom_carry", "Bringing a mushroom to camp", R_DOING_CAP);
    case L_FIND_MUSHROOM_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_mushroom_drop", "Dropping off a mushroom", R_DOING_CAP);
    case L_FIND_RARE: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_rare", "Picking up a rare mushroom", R_DOING_CAP);
    case L_FIND_RARE_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_rare_carry", "Bringing a rare mushroom to camp", R_DOING_CAP);
    case L_FIND_RARE_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_rare_drop", "Dropping off a rare mushroom", R_DOING_CAP);
    case L_FIND_GOLDEN: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_golden", "Picking up a golden mushroom", R_DOING_CAP);
    case L_FIND_GOLDEN_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_golden_carry", "Bringing a golden mushroom to camp", R_DOING_CAP);
    case L_FIND_GOLDEN_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_golden_drop", "Dropping off a golden mushroom", R_DOING_CAP);
    case L_FIND_LAB: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_lab", "Picking up lab equipment", R_DOING_CAP);
    case L_FIND_LAB_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_lab_carry", "Bringing lab equipment to camp", R_DOING_CAP);
    case L_FIND_LAB_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_lab_drop", "Dropping off lab equipment", R_DOING_CAP);
    case L_FIND_RELIC: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_relic", "Picking up a relic", R_DOING_CAP);
    case L_FIND_RELIC_CARRY: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_relic_carry", "Bringing a relic to camp", R_DOING_CAP);
    case L_FIND_RELIC_DROP: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.find_relic_drop", "Dropping off a relic", R_DOING_CAP);
    default: return vvfp_tr("vvfp.heathen_life/vvfp_heathen_life.label.statue_confused", "Confused at the unfinished statue", R_DOING_CAP);
    }
}

static int with_name(const char *format, const unsigned char *record, char *out);
static const char *kept_label(const char *got, const char *filled, char *out);

/* The chat's two labels, naming the other villager when it fits. */
static const char *chat_label(int going, const unsigned char *other, char *out) {
    char filled[R_DOING_CAP];
    if (going) {
        if (with_name("Going to chat with %s", other, filled)) {
            return kept_label(vvfp_trf("vvfp.heathen_life/vvfp_heathen_life.label.chat_go", "Going to chat with %s",
                                       filled, out, R_DOING_CAP), filled, out);
        }
        return label(L_CHAT_GO_ANY);
    }
    if (with_name("Chatting with %s", other, filled)) {
        return kept_label(vvfp_trf("vvfp.heathen_life/vvfp_heathen_life.label.chat_at", "Chatting with %s", filled,
                                   out, R_DOING_CAP), filled, out);
    }
    return label(L_CHAT_AT_ANY);
}

/* `format`'s one %s filled with the record's name into `out` (R_DOING_CAP bytes); 0 when the English would be
   longer than the game's own Details texts (then the caller shows the label without the name). */
static int with_name(const char *format, const unsigned char *record, char *out) {
    unsigned int n = 0, k;
    const char *at;
    for (at = format; *at != '\0'; ++at) {
        if (at[0] == '%' && at[1] == 's') {
            for (k = 0; k < R_NAME_CAP && record[R_NAME + k] != 0; ++k) {
                if (n >= LABEL_LONGEST) {
                    return 0;
                }
                out[n++] = (char)record[R_NAME + k];
            }
            ++at;
            continue;
        }
        if (n >= LABEL_LONGEST) {
            return 0;
        }
        out[n++] = *at;
    }
    out[n] = '\0';
    return 1;
}

/* A translated label, or the English one `filled` when vvfp_trf hands its text back (no translation companion, no
   translation, or one that does not fit): `filled` is the caller's local, so it is copied into `out`, the caller's
   own buffer, which outlives this call (Codex, PR #895). */
static const char *kept_label(const char *got, const char *filled, char *out) {
    if (got == filled) {
        lstrcpynA(out, filled, R_DOING_CAP);
        return out;
    }
    return got;
}

/* The doctor's two labels, naming the patient when it fits. */
static const char *heal_label(int at_patient, const unsigned char *patient, char *out) {
    char filled[R_DOING_CAP];
    if (at_patient) {
        if (with_name("Practising Healing on %s", patient, filled)) {
            return kept_label(vvfp_trf("vvfp.heathen_life/vvfp_heathen_life.label.heal_at", "Practising Healing on %s",
                                       filled, out, R_DOING_CAP), filled, out);
        }
        return label(L_HEAL_AT_ANY);
    }
    if (with_name("Going to heal %s", patient, filled)) {
        return kept_label(vvfp_trf("vvfp.heathen_life/vvfp_heathen_life.label.heal_go", "Going to heal %s", filled,
                                   out, R_DOING_CAP), filled, out);
    }
    return label(L_HEAL_GO_ANY);
}

/* ---- the game's step adders ------------------------------------------------------------------------------- */

static void put_doing(unsigned char *record, const char *words) {
    unsigned int i = 0;
    if (words != NULL) {
        for (; i + 1u < R_DOING_CAP && words[i] != '\0'; ++i) {
            record[R_DOING + i] = (unsigned char)words[i];
        }
    }
    record[R_DOING + i] = 0;
}

static void begin_with(unsigned char *record, const char *words) {
    ((tc0_fn)(UINT_PTR)G_STOP)(record, NULL);
    *(int *)(record + R_BEHAVIOUR) = CAMP_WANDER;
    put_doing(record, words);
}

static void begin(unsigned char *record, int which) {
    begin_with(record, label(which));
}

/* The game's text step: the Details text changes to `words` when the queue reaches it. */
static void then_say(unsigned char *record, const char *words) {
    char copy[R_DOING_CAP];
    unsigned int i = 0;
    if (words != NULL) {
        for (; i + 1u < R_DOING_CAP && words[i] != '\0'; ++i) {
            copy[i] = words[i];
        }
    }
    copy[i] = '\0';
    ((text_step_fn)(UINT_PTR)G_TEXT_STEP)(record, NULL, copy);
}

static void then(unsigned char *record, int which) {
    then_say(record, label(which));
}

static void walk_area(unsigned char *record, int area, int distance) {
    ((tc3_fn)(UINT_PTR)G_WALK_AREA)(record, NULL, area, distance, 0);
}

static void walk_point(unsigned char *record, int x, int y, int distance) {
    ((tc4_fn)(UINT_PTR)G_WALK_POINT)(record, NULL, x, y, distance, 0);
}

static void gesture(unsigned char *record, int count, int animation) {
    ((tc2_fn)(UINT_PTR)G_GESTURE)(record, NULL, count, animation);
}

static void wait_for(unsigned char *record, int seconds) {
    ((tc1_fn)(UINT_PTR)G_WAIT)(record, NULL, seconds);
}

static void carry(unsigned char *record, int item) {
    ((tc1_fn)(UINT_PTR)G_CARRY)(record, NULL, item);
}

static void drop(unsigned char *record) {
    ((tc0_fn)(UINT_PTR)G_DROP)(record, NULL);
}

static void animate(unsigned char *record, int animation) {
    ((anim_fn)(UINT_PTR)G_ANIM)(record, NULL, animation, 1.0f, 2);
}

static void start(unsigned char *record) {
    ((tc0_fn)(UINT_PTR)G_START)(record, NULL);
}

/* ---- the looks -------------------------------------------------------------------------------------------- */

static void look_sick(unsigned char *record) {           /* 0x45C3A0's pose, at the encampment */
    begin(record, L_SICK_GO);
    walk_area(record, A_CAMP, 0x28);
    then(record, L_SICK_AT);
    gesture(record, rnd(40) + 15, 9);
    wait_for(record, rnd(3) + 2);
    start(record);
}

static void look_waiting(unsigned char *record) {        /* 0x45CFD0's pose */
    begin(record, L_WAIT_HEALER);
    gesture(record, 0x3C, 0);
    start(record);
}

static void look_healing(unsigned char *doctor, const unsigned char *patient) {   /* 0x46CD86 + 0x45D060 */
    int spot[2];
    char words[R_DOING_CAP];
    int *at = ((position_fn)(UINT_PTR)G_POSITION)((void *)patient, NULL, spot);
    begin_with(doctor, heal_label(0, patient, words));
    walk_point(doctor, at[0], at[1] + 10, 0x96);
    then_say(doctor, heal_label(1, patient, words));
    animate(doctor, 0x11);
    wait_for(doctor, 3);
    gesture(doctor, 1, 1);
    wait_for(doctor, 3);
    gesture(doctor, 1, 1);
    then(doctor, L_BACK);
    walk_area(doctor, A_CAMP, 0x64);
    start(doctor);
}

/* A harvest's labels: going, there (practising Farming), bringing it home, dropping it off at the
   encampment. */
static void look_harvest(unsigned char *record, int going, int area, int item, int fish) {
    begin(record, going);
    walk_area(record, area, 0x64);
    then(record, going + 1);
    if (fish) {                                           /* 0x463B20 */
        wait_for(record, 3);
    } else {                                              /* 0x457910 / 0x457C80 */
        gesture(record, 1, 0xF);
        wait_for(record, 3);
        gesture(record, 1, 0xF);
    }
    carry(record, item);
    wait_for(record, 3);
    then(record, going + 2);
    walk_area(record, A_CAMP, 0x64);                      /* the encampment, never the granary (area 5) */
    then(record, going + 3);
    wait_for(record, 3);
    drop(record);
    start(record);
}

/* A visit's labels: going (or the game's own line for `going_text` > 0), there, then back to the encampment. */
static void look_visit(unsigned char *record, int going, int going_text, int area) {
    if (going_text > 0) {
        void *table = ((texts_fn)(UINT_PTR)G_TEXTS)();
        begin_with(record, ((text_fn)(UINT_PTR)G_TEXT)(table, NULL, going_text));
    } else {
        begin(record, going);
    }
    walk_area(record, area, 0x64);
    then(record, going_text > 0 ? L_NURSERY_AT : going + 1);
    gesture(record, rnd(4) + 2, 0);
    wait_for(record, rnd(3) + 2);
    gesture(record, rnd(4) + 2, 0);
    then(record, L_BACK);
    walk_area(record, A_CAMP, 0x64);
    start(record);
}

static void look_meal(unsigned char *record) {            /* 0x457D30 without its payoff 0x57 */
    begin(record, L_MEAL_GO);
    walk_area(record, A_CAMP, 0x64);
    then(record, L_MEAL_AT);
    animate(record, 0x6F);
    wait_for(record, rnd(2) + 2);
    gesture(record, 1, 5);
    animate(record, 0x6F);
    wait_for(record, rnd(2) + 2);
    gesture(record, 1, 5);
    start(record);
}

static void look_devotion(unsigned char *record) {        /* 0x4598A0's praising pose in front of the mud hut */
    begin(record, L_MUD_HUT_GO);
    walk_point(record, 2176 + rnd(96), 1576 + rnd(24), 0x64);
    then(record, L_MUD_HUT_AT);
    gesture(record, 0x1E, 0x10);
    wait_for(record, rnd(3) + 2);
    then(record, L_BACK);
    walk_area(record, A_CAMP, 0x64);
    start(record);
}

/* ---- what is open to a Heathen ---------------------------------------------------------------------------- */

static void look_at_map(void) {
    DWORD now = GetTickCount();
    const unsigned int *cells = (const unsigned int *)(UINT_PTR)G_MAP;
    unsigned int i;
    if (g_areas_known && now - g_areas_at < 2000u) {
        return;
    }
    memset(g_area_seen, 0, sizeof g_area_seen);
    for (i = 0; i < G_MAP_CELLS; ++i) {
        unsigned int area = (cells[i] >> 4) & 0x7FFu;
        short x = (short)((i % 320u) * 8u), y = (short)((i / 320u) * 8u);
        if (area < G_AREA_BOXES) {
            short *box = g_area_box[area];
            if (!((g_area_seen[area >> 3] >> (area & 7u)) & 1u)) {
                box[0] = box[2] = x;
                box[1] = box[3] = y;
            } else {
                box[0] = x < box[0] ? x : box[0];
                box[1] = y < box[1] ? y : box[1];
                box[2] = x > box[2] ? x : box[2];
                box[3] = y > box[3] ? y : box[3];
            }
        }
        g_area_seen[area >> 3] |= (unsigned char)(1u << (area & 7u));
    }
    g_areas_at = now;
    g_areas_known = 1;
}

static int area_drawn(int area) {
    if (area <= 0 || area >= G_AREA_BOXES) {
        return 0;
    }
    look_at_map();
    return (g_area_seen[area >> 3] >> (area & 7)) & 1;
}

/* A built building's walk area with cells on the map, else 0. */
static int building_area(int site) {
    const unsigned char *object = *(unsigned char *const *)(UINT_PTR)(G_SITES + 4u * (unsigned int)site);
    int project, area;
    if (object == NULL) {
        return 0;
    }
    project = i32(object, SITE_PROJECT);
    area = i32(object, SITE_AREA);
    if (project <= 0 || project >= 32 || !puzzle_done(project) || !area_drawn(area)) {
        return 0;
    }
    return area;
}

static void plan_practice(unsigned char *record, int which) {
    int index = rec_index(record);
    if (index >= 0) {
        g_practice[index] = which + 1;
        g_practice_who[index] = identity(record);
    }
}

/* ---- section 5: more of the believers' looks ------------------------------------------------------------- */

static void pose(unsigned char *record, unsigned int adder, int n) {
    ((tc1_fn)(UINT_PTR)adder)(record, NULL, n);
}

static void sound_end(unsigned char *record) {
    ((tc0_fn)(UINT_PTR)G_SOUND_END)(record, NULL);
}

static void effect(unsigned char *record, int a, int b, int c) {
    ((tc3_fn)(UINT_PTR)G_EFFECT)(record, NULL, a, b, c);
}

/* The science lab: the believers' research poses and sounds (0x45A890's first branch: the talking pose, pose
   0x2E, the sound 1 and its effect, pose 0x26) without its payoff step; Research practised. */
static void look_lab(unsigned char *record, int area) {
    begin(record, L_LAB_GO);
    walk_area(record, area, 0x64);
    then(record, L_LAB_AT);
    pose(record, G_POSE_TALK, 3);
    pose(record, G_POSE_2E, rnd(4) + 1);
    animate(record, 1);
    effect(record, 7, -10, -20);
    pose(record, G_POSE_26, rnd(4) + 1);
    sound_end(record);
    then(record, L_BACK);
    walk_area(record, A_CAMP, 0x64);
    start(record);
}

static int statue_stage(void) {
    return *(const volatile int *)(UINT_PTR)(G_STATUE + STATUE_STAGE);
}

/* 1 while the statue is carved to its first or second stage, its next one waiting for technology. */
static int statue_unfinished(void) {
    int stage = statue_stage();
    return !puzzle_done(P_IDOL) && (stage == 1 || stage == 2);
}

/* The Believer Idol: the believers' honoring (0x45CB70: pose 4 and gestures of animation 2, pose 0x2E, the talking
   pose) without its skill check and payoff; Devotion practised (the caller plans it).  While the statue is
   unfinished (stage 1 or 2), as for a believer dropped there with "Villagers Dropped on an Unfinished Statue May
   Honor" (the owner, 2026-11-27: "same skill practice rules apply to heathens with the heathen expansion patch
   too"): one visit in two, of this companion's numbers, is the believers' Confused look instead (behaviour 0x1F,
   0x459480: its head shakes 0x474370 and gestures; its tip, voice and message left out) -- 0 returned, nothing
   practised. */
static int look_statue(unsigned char *record, int area) {
    begin(record, L_STATUE_GO);
    walk_area(record, area, 0x64);
    if (statue_unfinished() && rnd(2) == 0) {
        then(record, L_STATUE_CONFUSED);
        ((tc4_fn)(UINT_PTR)G_GESTURE_AT)(record, NULL, 1, 0, rnd(4), rnd(4));
        ((tc4_fn)(UINT_PTR)G_GESTURE_AT)(record, NULL, 1, 0, rnd(4), rnd(4));
        ((tc4_fn)(UINT_PTR)G_GESTURE_AT)(record, NULL, 1, 0, rnd(4), rnd(4));
        gesture(record, 1, rnd(2));
        then(record, L_BACK);
        walk_area(record, A_CAMP, 0x64);
        start(record);
        return 0;
    }
    then(record, L_STATUE_AT);
    pose(record, G_POSE_4, rnd(4) + 1);
    gesture(record, rnd(2) + 2, 2);
    pose(record, G_POSE_4, rnd(4) + 1);
    gesture(record, rnd(2) + 2, 2);
    pose(record, G_POSE_2E, 2);
    pose(record, G_POSE_TALK, 3);
    then(record, L_BACK);
    walk_area(record, A_CAMP, 0x64);
    start(record);
    return 1;
}

/* The believers' own leisure (the adult chooser 0x46A3C0's), each the script's walk and poses with this companion's
   numbers; `kind` the first of its two labels. */
enum { LEISURE_FEET, LEISURE_WASH, LEISURE_RELAX, LEISURE_CLOUDS, LEISURE_LAKE, LEISURE_FALLS, LEISURE_DANCE,
       LEISURE_BATH, LEISURE_COUNT };
static const struct { int going, area; } LEISURE[LEISURE_COUNT] = {
    { L_FEET_GO, 0x73 },               /* 0x459110 Cooling feet in the stream */
    { L_WASH_GO, 0x73 },               /* 0x455B50 Washing up in the stream */
    { L_RELAX_GO, 0x75 },              /* 0x459790 Relaxing */
    { L_CLOUDS_GO, 0x75 },             /* 0x462C00 Watching the clouds */
    { L_LAKE_GO, 0x74 },               /* 0x457E00 Enjoying the lake (The Lake solved, as 0x46AAAE asks) */
    { L_FALLS_GO, 0x7E },              /* 0x45C960 Enjoying the waterfall */
    { L_DANCE_GO, 0x76 },              /* 0x4575D0 Dancing */
    { L_BATH_GO, 0x37 },               /* 0x455CA0 Bathing */
};

static void look_leisure(unsigned char *record, int kind) {
    begin(record, LEISURE[kind].going);
    walk_area(record, LEISURE[kind].area, 0x64);
    then(record, LEISURE[kind].going + 1);
    switch (kind) {
    case LEISURE_FEET:                                    /* the splash 0x59, gestures, pose 4 */
        animate(record, 0x59);
        sound_end(record);
        gesture(record, 1, 0);
        animate(record, 0x59);
        pose(record, G_POSE_4, 3);
        sound_end(record);
        gesture(record, 1, 0);
        break;
    case LEISURE_WASH:                                    /* pose 4, the splash, pose 0x2E, the splash 0x72 */
        pose(record, G_POSE_4, 1);
        animate(record, 0x59);
        pose(record, G_POSE_2E, rnd(3) + 1);
        animate(record, 0x72);
        gesture(record, 1, 0);
        pose(record, G_POSE_10, 3);
        sound_end(record);
        break;
    case LEISURE_RELAX:                                   /* gestures of animations 2 and 9 */
        gesture(record, rnd(20) + 5, 2);
        gesture(record, rnd(20) + 5, 9);
        break;
    case LEISURE_CLOUDS:
        pose(record, G_POSE_29, rnd(30) + 5);
        break;
    case LEISURE_LAKE:
        pose(record, G_POSE_4, 2);
        gesture(record, rnd(30) + 5, 9);
        break;
    case LEISURE_FALLS:
        gesture(record, rnd(10) + 5, 9);
        wait_for(record, rnd(3) + 2);
        break;
    case LEISURE_DANCE:                                   /* the talking pose (dancing), its sound stopped */
        pose(record, G_POSE_TALK, rnd(10) + 3);
        sound_end(record);
        break;
    default:                                              /* bathing: pose 0x10, the splash effect, gestures */
        pose(record, G_POSE_10, rnd(4) + 1);
        effect(record, 7, -10, 10);
        gesture(record, rnd(4) + 1, 0);
        effect(record, 7, -10, 10);
        break;
    }
    then(record, L_BACK);
    walk_area(record, A_CAMP, 0x64);
    start(record);
}

/* Practice at the encampment (section 5's training): each skill's believers' work look, without its payoff. */
static void look_training(unsigned char *record, int which) {
    static const int going[6] = { L_TRAIN_GO_FARMING, L_TRAIN_GO_PARENTING, L_TRAIN_GO_HEALING, L_TRAIN_GO_RESEARCH,
                                  L_TRAIN_GO_BUILDING, L_TRAIN_GO_FARMING };
    begin(record, going[which]);
    walk_area(record, A_CAMP, 0x64);
    then(record, going[which] + 1);
    switch (which) {
    case SKILL_FARMING:                                   /* 0x457C80's tending gestures (animation 0xF) */
        gesture(record, 1, 0xF);
        wait_for(record, 3);
        gesture(record, 1, 0xF);
        break;
    case SKILL_PARENTING:                                 /* 0x456190: the sound 0, gestures of animation 2 */
        animate(record, 0);
        gesture(record, rnd(5) + 2, 2);
        gesture(record, rnd(7) + 2, 2);
        sound_end(record);
        break;
    case SKILL_HEALING:                                   /* 0x45D060: the sound 0x11, waits and gestures */
        animate(record, 0x11);
        wait_for(record, 3);
        gesture(record, 1, 1);
        wait_for(record, 3);
        gesture(record, 1, 1);
        break;
    case SKILL_RESEARCH:                                  /* 0x45A890's poses and sound */
        pose(record, G_POSE_TALK, 3);
        pose(record, G_POSE_2E, rnd(4) + 1);
        animate(record, 1);
        effect(record, 7, -10, -20);
        sound_end(record);
        break;
    default:                                              /* building: 0x463C00's hammering 0x86 and swing; its lumber
                                                             (carry 4) left out: its drop handler is not proven harmless */
        animate(record, 0x86);
        wait_for(record, rnd(3) + 2);
        gesture(record, 1, 1);
        animate(record, 0x1C);
        wait_for(record, rnd(3) + 2);
        gesture(record, 1, 1);
        sound_end(record);
        break;
    }
    start(record);
}

/* A chat (0x4598A0): the partner stops and takes the listening pose (gesture 0x1E of animation 0x10), the Heathen
   walks up to them (+0x14, +0x4B, distance 150) and talks (gesture 4 of animation 0xF), waits, and goes back to
   the encampment when the partner was a believer.  Neither's Faith, skills or anything else changes. */
static void look_chat(unsigned char *record, unsigned char *partner, int believer) {
    int spot[2];
    char words[R_DOING_CAP], heard[R_DOING_CAP];
    int *at = ((position_fn)(UINT_PTR)G_POSITION)(partner, NULL, spot);
    int x = at[0], y = at[1];
    ((tc0_fn)(UINT_PTR)G_STOP)(partner, NULL);
    if (!believer) {
        *(int *)(partner + R_BEHAVIOUR) = CAMP_WANDER;
    }
    put_doing(partner, chat_label(0, record, heard));
    gesture(partner, 0x1E, 0x10);
    start(partner);
    begin_with(record, chat_label(1, partner, words));
    walk_point(record, x + 0x14, y + 0x4B, 0x96);
    then_say(record, chat_label(0, partner, words));
    wait_for(record, rnd(5) + 4);
    gesture(record, 4, 0xF);
    wait_for(record, rnd(5) + 4);
    if (believer) {
        then(record, L_BACK);
        walk_area(record, A_CAMP, 0x64);
    }
    start(record);
}

/* A child's find (the believer children's pick-up, 0x45BAB0 / 0x45BBF0: pose 4, the pick-up sound 0x18, carry the
   item): a mushroom or a collectible of any kind, carried to the encampment and set down there.
   FLAVOUR ONLY: nothing is taken off the map (the carried sprite is only a carry id, 0x474D80 -> 0x466420), nothing
   is counted or collected, nothing is made. */
#define ITEM_LAB_FIRST 0x50            /* 0x50..0x67 science items (0x45BC5D), 0x68..0x7F relics (0x45BC44) */
#define ITEM_RELIC_FIRST 0x68
#define ITEM_MUSHROOM 0x80             /* 0x80 a mushroom, 0x81 a rare one, 0x82 the golden mushroom (0x4136E6) */
static int look_find(unsigned char *record, int area) {
    int kind = rnd(5), item, going, first;
    switch (kind) {
    case 0: item = ITEM_MUSHROOM; first = L_FIND_MUSHROOM; break;
    case 1: item = ITEM_MUSHROOM + 1; first = L_FIND_RARE; break;
    case 2: item = ITEM_MUSHROOM + 2; first = L_FIND_GOLDEN; break;
    case 3: item = ITEM_LAB_FIRST + rnd(ITEM_RELIC_FIRST - ITEM_LAB_FIRST); first = L_FIND_LAB; break;
    default: item = ITEM_RELIC_FIRST + rnd(ITEM_MUSHROOM - ITEM_RELIC_FIRST); first = L_FIND_RELIC; break;
    }
    going = kind <= 2 ? L_FIND_GO_MUSHROOMS : L_FIND_GO_COLLECTIBLES;
    begin(record, going);
    walk_area(record, area, 0x64);
    then(record, first);
    pose(record, G_POSE_4, rnd(3) + 1);                  /* (the believers' carry(-1) first is left out: it would
                                                             hand a real carried item to its drop handler) */
    pose(record, G_POSE_4, 1);
    animate(record, 0x18);
    carry(record, item);
    sound_end(record);
    then(record, first + 1);
    walk_area(record, A_CAMP, 0x64);
    then(record, first + 2);
    animate(record, 0x0B);
    pose(record, G_POSE_4, 2);
    sound_end(record);
    drop(record);
    start(record);
    return item;
}

/* ---- section 5: training (the owner, 2026-11-27: "the untrained heathens should be allowed to choose a skill
   and practice it and eventually master them (same rate as believers, always evenly-distributed)") ---------- */

#define TRAINED 20                     /* the Details screen's first level above "Untrained" (0x41C680: 20) */
#define TR_MAGIC 0x31534856u           /* 'VHS1' ('VHT1' is the Heathen Tribe file's, PR #896) */
#define TR_VERSION 1u
#define TR_HEADER 20u
#define TR_MAX 256
#define TR_WRITE_MS 1000u
#define TR_RESERVE ((int)sizeof(".unreadable-4294967295-999"))
static struct { unsigned int identity, skill; } g_train[TR_MAX];
static int g_train_count;
static int g_train_slot;
static int g_train_blocked;
static int g_train_dirty;
static DWORD g_train_synced_at;
static vv_sidecar_gate g_train_gate;
static unsigned int g_train_buffer[(TR_HEADER + TR_MAX * 8u) / 4u + 1u];

/* <Documents>\LDW\<exe>\Virtual Villagers Fun Patcher\Save <S>\Data\Heathen Training\Heathen Training - Save <S>.dat
   (the layout "VVFP Heathen Aging.dll" uses for its files). */
static int train_path(int slot, char *out, int make) {
    char docs[MAX_PATH], exe[MAX_PATH], part[64];
    static const char *const levels[5] = { "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data",
                                           "\\Heathen Training", NULL };
    char *base = exe, *p, *dot = NULL;
    DWORD n;
    int i;
    if (slot < 1 || slot > 5 || !SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    for (p = exe; *p != '\0'; ++p) {
        if (*p == '\\') {
            base = p + 1;
            dot = NULL;
        } else if (*p == '.') {
            dot = p;
        }
    }
    if (dot != NULL) {
        *dot = '\0';
    }
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 160 >= MAX_PATH - TR_RESERVE) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    for (i = 0; levels[i] != NULL; ++i) {
        wsprintfA(part, levels[i], slot);
        lstrcatA(out, part);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    wsprintfA(part, "\\Heathen Training - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_training(const unsigned char *data, DWORD len, void *ctx) {
    const unsigned int *u = (const unsigned int *)data;
    unsigned int count, i;
    if (len < TR_HEADER || u[0] != TR_MAGIC || u[1] != TR_VERSION || u[2] != (unsigned int)HL_GAME
        || u[4] != (unsigned int)*(const int *)ctx) {
        return 0;
    }
    count = u[3];
    if (count > TR_MAX || len != TR_HEADER + count * 8u) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (u[5 + i * 2] == 0u || u[6 + i * 2] > (unsigned int)SKILL_DEVOTION) {
            return 0;
        }
    }
    return 1;
}

static void train_read(int slot) {
    char path[MAX_PATH];
    DWORD got = 0;
    int status;
    g_train_count = 0;
    g_train_dirty = 0;
    vv_sidecar_gate_bind(&g_train_gate, slot);
    g_train_blocked = 0;
    if (!train_path(slot, path, 0)) {
        vv_sidecar_gate_block(&g_train_gate);
        g_train_blocked = 1;
        return;
    }
    status = vv_sidecar_load(&g_train_gate, path, (unsigned char *)g_train_buffer, sizeof g_train_buffer, &got,
                             valid_training, &slot);
    g_train_blocked = status == VV_SIDECAR_LOAD_BLOCKED;
    if (status == VV_SIDECAR_LOAD_VALID) {
        g_train_count = (int)g_train_buffer[3];
        memcpy(g_train, g_train_buffer + 5, 8u * (size_t)g_train_count);
    }
    g_train_synced_at = GetTickCount() - TR_WRITE_MS;
}

static int train_find(unsigned int who) {
    int i;
    for (i = 0; i < g_train_count; ++i) {
        if (g_train[i].identity == who) {
            return i;
        }
    }
    return -1;
}

static void train_drop_at(int at) {
    memmove(&g_train[at], &g_train[at + 1], sizeof g_train[0] * (size_t)(g_train_count - at - 1));
    --g_train_count;
    g_train_dirty = 1;
}

/* Entries of identities no living Heathen holds now (dead, gone, joined the tribe) are dropped before a write. */
static void train_prune(void) {
    int k;
    for (k = g_train_count; k-- > 0;) {
        unsigned int i;
        int alive = 0;
        for (i = 0; i < g_slots && !alive; ++i) {
            const unsigned char *r = rec_at((int)i);
            alive = heathen(r) && identity(r) == g_train[k].identity;
        }
        if (!alive) {
            train_drop_at(k);
        }
    }
}

/* `pruned`: drop the entries no living Heathen holds -- only while the villager table is this slot's own village.
   On a switch of save slot the table already holds the NEW village, so the last slot's table is written as it is,
   unpruned and without waiting for the write throttle, or its choices would be lost (Codex, PR #899). */
static void train_write_as(int pruned, int now) {
    unsigned int header[5];
    const void *parts[2];
    DWORD sizes[2];
    char path[MAX_PATH];
    if (!g_train_dirty || g_train_slot == 0 || g_train_blocked || !vv_sidecar_gate_ready(&g_train_gate, g_train_slot)
        || (!now && GetTickCount() - g_train_synced_at < TR_WRITE_MS) || !train_path(g_train_slot, path, 1)) {
        return;
    }
    if (pruned) {
        train_prune();
    }
    g_train_synced_at = GetTickCount();
    header[0] = TR_MAGIC;
    header[1] = TR_VERSION;
    header[2] = (unsigned int)HL_GAME;
    header[3] = (unsigned int)g_train_count;
    header[4] = (unsigned int)g_train_slot;
    parts[0] = header;
    sizes[0] = sizeof header;
    parts[1] = g_train;
    sizes[1] = (DWORD)(8u * (size_t)g_train_count);
    if (vv_sidecar_publish(&g_train_gate, path, parts, sizes, g_train_count > 0 ? 2 : 1)) {
        g_train_dirty = 0;
    }
}

static void train_write(void) {
    train_write_as(1, 0);
}

/* The game's save slot now (its save manager's field): a new slot writes the last one's file first (unpruned: the
   table is the new village's) and reads its own; a read that found the file locked is tried again once the gate's
   throttle lets it (Codex, PR #899), as the other sidecar readers do; then the file is kept up to date. */
static void train_sync(void) {
    int slot = vv_game_save_slot(HL_GAME);
    if (slot != g_train_slot) {
        train_write_as(0, 1);
        g_train_slot = slot;
        g_train_count = 0;
        if (slot != 0) {
            train_read(slot);
        }
    } else if (slot != 0 && g_train_blocked && !vv_sidecar_gate_throttled(&g_train_gate)) {
        train_read(slot);
    }
    train_write();
}

/* "Always evenly-distributed": the unmastered skill of the record's that the fewest living Heathens are training,
   ties at random; -1 when every skill is mastered. */
static int train_choose(const unsigned char *record) {
    int counts[6] = { 0, 0, 0, 0, 0, 0 }, best = -1, ties = 0, k, i;
    for (i = 0; i < g_train_count; ++i) {
        counts[g_train[i].skill] += 1;
    }
    for (k = 0; k < 6; ++k) {
        if (skill(record, k) >= 100.0f) {
            continue;
        }
        if (best < 0 || counts[k] < counts[best]) {
            best = k;
            ties = 1;
        } else if (counts[k] == counts[best] && rnd(++ties) == 0) {
            best = k;
        }
    }
    return best;
}

static int untrained(const unsigned char *record) {
    int k;
    for (k = 0; k < 6; ++k) {
        if (skill(record, k) >= (float)TRAINED) {
            return 0;
        }
    }
    return 1;
}

/* At each unit of an ordinary adult Heathen who is not sick: an untrained one chooses a skill; one who has mastered
   theirs chooses the next; one with every skill mastered is done. */
static void train_update(const unsigned char *record) {
    unsigned int who = identity(record);
    int at = train_find(who), next;
    if (g_train_slot == 0 || g_train_blocked) {
        return;                                           /* no file to keep it in: nobody chooses */
    }
    if (at >= 0 && skill(record, (int)g_train[at].skill) < 100.0f) {
        return;
    }
    if (at < 0 && !untrained(record)) {
        return;
    }
    if (at >= 0) {
        train_drop_at(at);
    }
    next = train_choose(record);
    if (next >= 0 && g_train_count < TR_MAX) {
        g_train[g_train_count].identity = who;
        g_train[g_train_count].skill = (unsigned int)next;
        ++g_train_count;
        g_train_dirty = 1;
    }
}

/* The skill the record is training, or -1. */
static int training(const unsigned char *record) {
    int at = train_find(identity(record));
    return at >= 0 ? (int)g_train[at].skill : -1;
}

/* ---- section 5: the pace (the owner, 2026-11-28: "heathens shouldn't all en-masse do a single action or stay in
   the encampment all the time. just occasional walking and doing stuff per heathen") ------------------------- */

enum { ACT_NONE, ACT_NONI, ACT_CROPS, ACT_FISH, ACT_POOLS, ACT_STATUE, ACT_LAB, ACT_LOVE, ACT_CLOTHING, ACT_MEAL,
       ACT_MUD_HUT, ACT_CHAT, ACT_CHAT_BELIEVER, ACT_LEISURE, ACT_TRAINING = ACT_LEISURE + LEISURE_COUNT,
       ACT_FIND, ACT_NURSERY, ACT_COUNT };

static int g_option_away_max, g_option_same_max, g_option_cooldown;

static int isqrt(int n) {
    int r = 0;
    while ((r + 1) * (r + 1) <= n) {
        ++r;
    }
    return r;
}

/* How many Heathens may be away from the encampment at once: about the square root of the tribe's ordinary
   Heathens, x 0.4 (Quiet), 0.75 (Normal), 1.1 (Lively), at least 1 -- 50 Heathens: 3, 6, 8; 10: 2, 3, 4. */
static int away_cap(int tribe) {
    static const int tenths_of_root[4] = { 0, 40, 75, 110 };
    int root100 = isqrt(tribe * 10000), cap;
    if (g_option_away_max > 0) {
        return g_option_away_max;
    }
    cap = (root100 * tenths_of_root[g_busyness] + 9999) / 10000;
    return cap < 1 ? 1 : cap;
}

static int same_cap(void) {
    return g_option_same_max > 0 ? g_option_same_max : g_busyness;   /* 1, 2, 3 */
}

/* Life units between one Heathen's outings: 30 (Quiet), 15 (Normal), 8 (Lively) -- about 3, 1.5 and 0.8 hours
   of game time (1 in 240 a unit is about once a day). */
static int cooldown(void) {
    static const int units[4] = { 0, 30, 15, 8 };
    return g_option_cooldown > 0 ? g_option_cooldown : units[g_busyness];
}

/* A Heathen first seen (or a record reused) starts its own count, as if its last outing were a random part of a
   cool-down ago: the tribe's first outings are staggered, never all at once. */
static void paced(const unsigned char *record, int index) {
    unsigned int who = identity(record);
    if (g_paced_who[index] != who) {
        g_paced_who[index] = who;
        g_units[index] = 0;
        g_last_out[index] = -rnd(cooldown());
        g_out[index] = 0;
    }
}

static int out_on(int index) {
    const unsigned char *r = rec_at(index);
    if (g_out[index] == 0 || !living(r) || identity(r) != g_out_who[index]) {
        return ACT_NONE;
    }
    return g_out[index];
}

static void tally(int *tribe, int *away, int *same, int action) {
    unsigned int i;
    *tribe = *away = *same = 0;
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *r = rec_at((int)i);
        int doing;
        if (!heathen(r) || !ordinary(r)) {
            continue;
        }
        ++*tribe;
        doing = out_on((int)i);
        if (doing != ACT_NONE) {
            *away += g_away[i];
            *same += doing == action;
        }
    }
}

/* 1 when same_cap() Heathens are already on `action`. */
static int full(int action) {
    int tribe, away, same;
    tally(&tribe, &away, &same, action);
    return same >= same_cap();
}

static void went_out(unsigned char *record, int action, int away) {
    int index = rec_index(record);
    if (index >= 0) {
        g_out[index] = action;
        g_out_who[index] = identity(record);
        g_away[index] = away;
        if (away) {
            g_last_out[index] = g_units[index];
        }
    }
}

/* "The believers are primary": a place is in use while any believer stands in its walk area (its cells' box, 24
   px around); a Heathen then goes somewhere else. */
static int in_use(int area) {
    unsigned int i;
    const short *box;
    if (!area_drawn(area)) {
        return 1;
    }
    box = g_area_box[area];
    for (i = 0; i < g_slots; ++i) {
        unsigned char *r = rec_at((int)i);
        int spot[2], *at;
        if (r[R_FACTION] != 0 || !living(r)) {
            continue;
        }
        at = ((position_fn)(UINT_PTR)G_POSITION)(r, NULL, spot);
        if (at[0] >= box[0] - 24 && at[0] <= box[2] + 32 && at[1] >= box[1] - 24 && at[1] <= box[3] + 32) {
            return 1;
        }
    }
    return 0;
}

/* A chase or a fright in progress, or the Heathens' own mask encounter (0x46E2E0: behaviour 0x14 chasing, 0xE5 its
   own exclusion; a believer runs with 0x15 / 0x16): never stopped by anything of ours. */
static int in_encounter(const unsigned char *record) {
    int b = i32(record, R_BEHAVIOUR);
    return b == 0x14 || b == 0x15 || b == 0x16 || b == 0xE5;
}

/* The believers' idle leisure (meditating, thinking, staring, relaxing, unsure, watching the clouds, reflecting,
   wandering): only a believer doing one of these, carrying nothing, not held, not sick, an adult, is asked to
   chat -- never one at work, carrying or dropped by the player. */
static int idle_believer(const unsigned char *r) {
    static const int idle[] = { 0x0B, 0x0C, 0x0E, 0x13, 0x48, 0x86, 0x1D, 0x37 };
    int b, k;
    if (r[R_FACTION] != 0 || !living(r) || r[R_HELD] != 0 || r[R_SICK] != 0 || i32(r, R_AGE) < ADULT
        || i32(r, R_CARRY) != -1) {
        return 0;
    }
    b = i32(r, R_BEHAVIOUR);
    for (k = 0; k < (int)(sizeof idle / sizeof idle[0]); ++k) {
        if (b == idle[k]) {
            return 1;
        }
    }
    return 0;
}

static DWORD g_chatted_at[256];        /* a believer asked to chat: not asked again for 30 s */

static unsigned char *chat_partner(const unsigned char *record, int believer) {
    int count = 0, i;
    unsigned char *chosen = NULL;
    DWORD now = GetTickCount();
    for (i = 0; i < (int)g_slots; ++i) {
        unsigned char *r = rec_at(i);
        if (r == record) {
            continue;
        }
        if (believer) {
            if (!idle_believer(r) || (g_chatted_at[i] != 0 && now - g_chatted_at[i] < 30000u)) {
                continue;
            }
        } else if (!heathen(r) || !ordinary(r) || i32(r, R_AGE) < ADULT || r[R_SICK] != 0 || r[R_HELD] != 0
                   || in_encounter(r) || i32(r, R_BEHAVIOUR) != CAMP_WANDER || out_on(i) != ACT_NONE
                   || visiting(i)) {
            continue;
        }
        if (rnd(++count) == 0) {
            chosen = r;
        }
    }
    if (chosen != NULL && believer) {
        g_chatted_at[rec_index(chosen)] = now;
    }
    return chosen;
}

/* An adult's show action (the age rules: see the header's AGE RULES; the caller has checked the adult test).  Each
   choice open to the Heathen is weighed against the pace (section 5): an outing (anything that leaves the
   encampment) only while fewer than away_cap() are out and the Heathen's own cool-down has passed, no more than
   same_cap() on one action, and never to a place a believer is using. */
static int show(unsigned char *record, int may_go_out) {
    int open[ACT_COUNT], areas[ACT_COUNT], count = 0, choice, area, age = i32(record, R_AGE), k;
    int tribe, away, same, trains = training(record);
    unsigned char *partner;
    int old = elder(record);
    tally(&tribe, &away, &same, ACT_NONE);
    if (away >= away_cap(tribe)) {
        may_go_out = 0;
    }
    if (old) {
        /* An elder has retired to the encampment ("VVFP Heathen Aging.dll"; the owner, 2026-11-26: they "go to the
           encampment where younger ones will take their place"): only what is done there. */
        may_go_out = 0;
    }
#define OFFER(action, where) do { int s_, a_, t_; tally(&t_, &a_, &s_, (action)); \
        if (s_ < same_cap()) { open[count] = (action); areas[count++] = (where); } } while (0)
    if (trains >= 0 && rnd(2) == 0) {
        /* A Heathen training a skill practises it on half their show actions, where believers practise it (each
           place under the same caps as any other show action). */
        int done = 1;
        if (trains == SKILL_RESEARCH && may_go_out && area_drawn(A_LAB) && !in_use(A_LAB) && !full(ACT_LAB)) {
            look_lab(record, A_LAB);
            went_out(record, ACT_LAB, 1);
        } else if (trains == SKILL_DEVOTION && !full(ACT_MUD_HUT)) {
            look_devotion(record);
            went_out(record, ACT_MUD_HUT, 0);
        } else if (trains == SKILL_FARMING && may_go_out && puzzle_done(P_FARM) && !in_use(A_CROPS)
                   && !full(ACT_CROPS)) {
            look_harvest(record, L_CROPS_GO, A_CROPS, 0, 0);
            went_out(record, ACT_CROPS, 1);
        } else if (trains != SKILL_DEVOTION && !full(ACT_TRAINING)) {
            look_training(record, trains);
            went_out(record, ACT_TRAINING, 0);
        } else {
            done = 0;                                     /* every place full: an ordinary show action */
        }
        if (done) {
            plan_practice(record, trains);
            return 1;
        }
    }
    if (may_go_out) {
        if (puzzle_done(P_FENCE) && !in_use(A_NONI)) OFFER(ACT_NONI, A_NONI);
        if (puzzle_done(P_FARM) && !in_use(A_CROPS)) OFFER(ACT_CROPS, A_CROPS);
        if (puzzle_done(P_LAKE) && !in_use(A_LAKE)) OFFER(ACT_FISH, A_LAKE);
        if (area_drawn(A_POOLS) && !in_use(A_POOLS)) OFFER(ACT_POOLS, A_POOLS);
        if ((puzzle_done(P_IDOL) || statue_unfinished()) && area_drawn(A_STATUE) && !in_use(A_STATUE)) {
            OFFER(ACT_STATUE, A_STATUE);
        }
        if (area_drawn(A_LAB) && !in_use(A_LAB)) OFFER(ACT_LAB, A_LAB);
        if (age >= LOVE_FIRST && age < LOVE_LAST && (area = building_area(SITE_LOVE)) != 0 && !in_use(area)) {
            OFFER(ACT_LOVE, area);
        }
        if ((area = building_area(SITE_CLOTHING)) != 0 && !in_use(area)) OFFER(ACT_CLOTHING, area);
        for (k = 0; k < LEISURE_COUNT; ++k) {
            if ((k != LEISURE_LAKE || puzzle_done(P_LAKE)) && !in_use(LEISURE[k].area)) {
                OFFER(ACT_LEISURE + k, LEISURE[k].area);
            }
        }
        OFFER(ACT_CHAT_BELIEVER, 0);
    }
    OFFER(ACT_MEAL, A_CAMP);
    OFFER(ACT_MUD_HUT, A_CAMP);
    OFFER(ACT_CHAT, A_CAMP);
#undef OFFER
    if (count == 0) {
        return 0;
    }
    choice = rnd(count);
    area = areas[choice];
    switch (open[choice]) {
    case ACT_NONI: look_harvest(record, L_NONI_GO, area, 0, 0); plan_practice(record, SKILL_FARMING); break;
    case ACT_CROPS: look_harvest(record, L_CROPS_GO, area, 0, 0); plan_practice(record, SKILL_FARMING); break;
    case ACT_FISH: look_harvest(record, L_FISH_GO, area, 0x38, 1); plan_practice(record, SKILL_FARMING); break;
    case ACT_POOLS: look_visit(record, L_POOLS_GO, 0, area); break;
    case ACT_STATUE:
        if (look_statue(record, area)) {
            plan_practice(record, SKILL_DEVOTION);
        }
        break;
    case ACT_LAB: look_lab(record, area); plan_practice(record, SKILL_RESEARCH); break;
    case ACT_LOVE: look_visit(record, L_LOVE_GO, 0, area); break;
    case ACT_CLOTHING: look_visit(record, L_CLOTHING_GO, 0, area); break;
    case ACT_MEAL: look_meal(record); break;
    case ACT_MUD_HUT: look_devotion(record); plan_practice(record, SKILL_DEVOTION); break;
    case ACT_CHAT:
    case ACT_CHAT_BELIEVER:
        partner = chat_partner(record, open[choice] == ACT_CHAT_BELIEVER);
        if (partner == NULL) {
            return 0;                                     /* nobody free to talk: the stock Heathen AI */
        }
        look_chat(record, partner, open[choice] == ACT_CHAT_BELIEVER);
        if (open[choice] == ACT_CHAT) {
            went_out(partner, ACT_CHAT, 0);
        }
        break;
    default: look_leisure(record, open[choice] - ACT_LEISURE); break;
    }
    went_out(record, open[choice], area != A_CAMP);
    return 1;
}

/* A carried sprite of ours (a child's find) still shown when the look was cut short is taken away by a plain
   write: no drop step, so the game's drop handler (0x4146B0, which counts a collectible dropped at the lab or the
   granary) never sees it. */
static int g_flavour_item[256];

static void clear_flavour(unsigned char *record, int index) {
    if (g_flavour_item[index] != 0 && i32(record, R_CARRY) == g_flavour_item[index]) {
        *(int *)(record + R_CARRY) = -1;
    }
    g_flavour_item[index] = 0;
}

/* The picker's Heathen branch: 1 when a look was queued here, 0 for the stock Heathen AI. */
static int __cdecl pick(unsigned char *record) {
    __try {
        int index = rec_index(record), may_go_out, overdue, since;
        if (index < 0 || !heathen(record) || !ordinary(record) || raining()) {
            return 0;
        }
        g_out[index] = 0;                                 /* whatever it was out on has ended */
        clear_flavour(record, index);
        if (record[R_SICK] != 0) {
            look_sick(record);
            return 1;
        }
        if (visiting(index)) {                            /* a doctor between visits: the stock AI */
            return 0;
        }
        paced(record, index);
        since = g_units[index] - g_last_out[index];
        may_go_out = since >= cooldown();
        overdue = since >= 4 * cooldown();                /* "not stuck at camp either" */
        if (i32(record, R_PREGNANT) != 0 || (!overdue && rnd(100) >= g_show_percent)) {
            return 0;
        }
        if (i32(record, R_AGE) < ADULT) {
            /* A child: only what a believer child does that a Heathen child does not in stock -- play in the
               nursery while an adult teaches at the nursery school (0x46E433..0x46E472; 0x43A810), and bring a
               find home (the believer children's pick-up, flavour only). */
            int tribe, away, same, in_nursery, nursery = ((teacher_fn)(UINT_PTR)G_TEACHER)() && area_drawn(A_NURSERY_PLAY);
            int spot = rnd(2) == 0 ? 0x4C : 0x51;         /* where the believer children look (0x456C10) */
            tally(&tribe, &away, &in_nursery, ACT_NURSERY);
            tally(&tribe, &away, &same, ACT_FIND);
            if (!may_go_out || away >= away_cap(tribe)) {
                return 0;
            }
            /* The same-action cap holds for nursery play too (Codex, PR #899): a full nursery falls back to a find. */
            nursery = nursery && in_nursery < same_cap();
            if (nursery && (rnd(2) == 0 || in_use(spot))) {
                look_visit(record, 0, T_NURSERY_PLAY, A_NURSERY_PLAY);
                went_out(record, ACT_NURSERY, 1);
                return 1;
            }
            if (same < same_cap() && !in_use(spot)) {
                g_flavour_item[index] = look_find(record, spot);
                went_out(record, ACT_FIND, 1);
                return 1;
            }
            return 0;
        }
        return show(record, may_go_out);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return 0;
    }
}

/* ---- sickness and the doctors ----------------------------------------------------------------------------- */

static int onset(const unsigned char *record) {           /* 0x472F7C..0x472F9B with 0x465F50 */
    int level;
    if (easiest() && rnd(100) < 50) {                     /* 0x472F97 */
        return 0;
    }
    if (easiest() && rnd(100) < 50) {                     /* 0x465F6E */
        return 0;
    }
    level = medicine();
    if ((level == 1 && rnd(1440) <= 3) || (level == 2 && rnd(2460) <= 3) || (level == 3 && rnd(5400) <= 2)) {
        return 1;
    }
    return elder(record) && rnd(1000) <= 14;
}

static int can_heal(const unsigned char *record) {
    return heathen(record) && ordinary(record) && i32(record, R_AGE) >= ADULT && record[R_SICK] == 0
        && i32(record, R_PREGNANT) == 0 && record[R_HELD] == 0 && (int)skill(record, SKILL_HEALING) >= 1
        && !in_encounter(record);
}

static void end_visit(int patient) {
    int doctor = g_doctor[patient] - 1;
    if (doctor >= 0 && g_visiting[doctor] == patient + 1) {
        g_visiting[doctor] = 0;
    }
    g_doctor[patient] = 0;
    g_waited[patient] = 0;
}

/* A record that is no longer a doctor's visit forgets it. */
static void forget_visits_of(int index) {
    int patient = g_visiting[index] - 1;
    if (patient >= 0 && g_doctor[patient] == index + 1) {
        end_visit(patient);
    }
    g_visiting[index] = 0;
}

/* 1 while the doctor in record `index` is on a visit to a patient who still needs it (a patient who died,
   converted, got well or left is forgotten here, so the doctor is free again). */
static int visiting(int index) {
    int patient = g_visiting[index] - 1;
    const unsigned char *who;
    if (patient < 0) {
        return 0;
    }
    who = rec_at(patient);
    if (g_doctor[patient] == index + 1 && heathen(who) && who[R_SICK] != 0
        && identity(who) == g_patient_who[patient]) {
        return 1;
    }
    forget_visits_of(index);
    return 0;
}

static void heal(int index, unsigned char *patient) {
    int doctor = g_doctor[index] - 1, best = -1, any = 0, i;
    float best_skill = 0.0f;
    if (doctor >= 0) {
        unsigned char *who = rec_at(doctor);
        if (can_heal(who) && identity(who) == g_doctor_who[index] && identity(patient) == g_patient_who[index]) {
            if (++g_waited[index] >= CURE_UNITS) {
                end_visit(index);
                if (practise(who, SKILL_HEALING)) {
                    patient[R_SICK] = 0;                  /* 0x468CCB; People Cured never counted */
                }
            }
            return;
        }
        end_visit(index);
    }
    for (i = 0; i < (int)g_slots; ++i) {
        unsigned char *candidate = rec_at(i);
        if (i == index || !can_heal(candidate)) {
            continue;
        }
        any = 1;
        if (!visiting(i) && (best < 0 || skill(candidate, SKILL_HEALING) > best_skill)) {
            best = i;
            best_skill = skill(candidate, SKILL_HEALING);
        }
    }
    if (best >= 0) {
        unsigned char *who = rec_at(best);
        g_doctor[index] = best + 1;
        g_doctor_who[index] = identity(who);
        g_patient_who[index] = identity(patient);
        g_waited[index] = 0;
        g_visiting[best] = index + 1;
        if (patient[R_HELD] == 0 && !in_encounter(patient)) {
            look_waiting(patient);
        }
        look_healing(who, patient);
        return;
    }
    if (!any && rnd(SELF_CURE) == 0) {
        patient[R_SICK] = 0;                              /* well on their own */
    }
}

static void life_unit(int index, unsigned char *record) {
    int health = i32(record, R_HEALTH), was = health, sick = record[R_SICK] != 0;
    paced(record, index);
    ++g_units[index];
    train_sync();
    if (sick && rnd(100) <= 60 && (health > 20 || rnd(100) <= 30) && health > g_floor) {
        health -= 1;                                      /* 0x472ED1, never below the floor */
    }
    if (!sick && (!elder(record) || rnd(100) < 20)) {
        health = health + 1 > 100 ? 100 : health + 1;     /* 0x472F65..0x472F77 */
    }
    if (health != was && health > 0) {
        *(int *)(record + R_HEALTH) = health;
    }
    if (!sick) {
        if (ordinary(record) && onset(record)) {
            record[R_SICK] = 1;
            forget_visits_of(index);
            if (record[R_HELD] == 0 && !in_encounter(record)) {
                look_sick(record);                        /* as 0x472FAC..0x472FC1 start behaviour 0x20 */
            }
        }
    } else {
        heal(index, record);
    }
    if (record[R_SICK] == 0 && ordinary(record) && i32(record, R_AGE) >= ADULT) {
        int planned = g_practice[index] - 1;
        train_update(record);
        if (planned >= 0 && g_practice_who[index] == identity(record)) {
            practise(record, planned);
        } else if (rnd(PRACTICE_ROLL) == 0) {
            practise(record, role_skill(record));
        }
    }
    g_practice[index] = 0;
}

/* ---- the exports ------------------------------------------------------------------------------------------ */

/* "VVFP Heathen Aging.dll" (heathen_evo.h section 3): one unit (HE_LIFE_UNIT) or the sick-byte question
   (HE_LIFE_IDLE) for a living aging Heathen; HE_LIFE_ROW must be set.  HE_LIFE_KEEP_SICK | HE_LIFE_HANDLED, or 0
   for the stock rule. */
int __stdcall VvfpHeathenLifeUnit(unsigned char *record, int flags) {
    int answer = 0, index;
    if (!g_installed || (flags & HE_LIFE_ROW) == 0 || record == NULL) {
        return 0;
    }
    __try {
        index = rec_index(record);
        if (index < 0 || !heathen(record)) {
            if (index >= 0) {
                forget_visits_of(index);
            }
            return 0;
        }
        if ((flags & 0xFF) == HE_LIFE_UNIT) {
            life_unit(index, record);
        }
        answer = (record[R_SICK] != 0 ? HE_LIFE_KEEP_SICK : 0) | HE_LIFE_HANDLED;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        answer = 0;
    }
    return answer;
}

/* 1 when the splice is installed, else 0. */
int __stdcall VvfpHeathenLifeInstalled(void) {
    return g_installed;
}

/* ---- the splice ------------------------------------------------------------------------------------------- */

static const unsigned int g_pick_believer = PICK_BELIEVER;
static const unsigned int g_pick_heathen = PICK_HEATHEN;
static const unsigned int g_pick_done = PICK_DONE;

/* In place of 0x46F0BA's `cmp byte [edx+0x1CEC], bl; je 0x46F0CF` (esi = edx = the record, ebx = 0). */
__declspec(naked) static void pick_stub(void) {
    __asm {
        cmp byte ptr [edx + 0x1CEC], 0
        jne heathen_branch
        jmp dword ptr [g_pick_believer]
    heathen_branch:
        pushad
        push esi
        call pick
        add esp, 4
        mov dword ptr [g_pick_result], eax
        popad
        cmp dword ptr [g_pick_result], 0
        jne queued
        jmp dword ptr [g_pick_heathen]
    queued:
        jmp dword ptr [g_pick_done]
    }
}

static const unsigned char PICK_STOCK[8] = { 0x38, 0x9A, 0xEC, 0x1C, 0x00, 0x00, 0x74, 0x0D };

static const unsigned int g_cure_sick = CURE_SICK;
static const unsigned int g_cure_not_sick = CURE_NOT_SICK;
static const unsigned int g_cure_counted = CURE_COUNTED;

/* In place of 0x468C3C's `cmp byte [esi+0x1C48], bl; jne 0x468C61` (esi the patient): the patient's faction, as
   the cure begins, into the local [esp+0x18]; then the stock test. */
__declspec(naked) static void cure_begin_stub(void) {
    __asm {
        push dword ptr [esi + 0x1CEC]
        pop dword ptr [esp + 0x18]
        cmp byte ptr [esi + 0x1C48], bl
        jne patient_sick
        jmp dword ptr [g_cure_not_sick]
    patient_sick:
        jmp dword ptr [g_cure_sick]
    }
}

/* In place of 0x468D4D's `add dword [0x51D368], 1`: only a patient who was a believer when the cure began counts. */
__declspec(naked) static void cure_count_stub(void) {
    __asm {
        cmp byte ptr [esp + 0x18], 0
        jne not_counted
        add dword ptr ds:[0x51D368], 1          ; G_PEOPLE_CURED
    not_counted:
        jmp dword ptr [g_cure_counted]
    }
}

static const unsigned char CURE_BEGIN_STOCK[8] = { 0x38, 0x9E, 0x48, 0x1C, 0x00, 0x00, 0x75, 0x1D };
static const unsigned char CURE_COUNT_STOCK[7] = { 0x83, 0x05, 0x68, 0xD3, 0x51, 0x00, 0x01 };
/* The Village Statistics row's caves begin with these (scripts/build_statistics_features.py). */
static const unsigned char STATS_BEGIN_CAVE[10] = { 0xFF, 0xB6, 0xEC, 0x1C, 0x00, 0x00, 0x8F, 0x44, 0x24, 0x18 };
static const unsigned char STATS_COUNT_CAVE[5] = { 0x80, 0x7C, 0x24, 0x18, 0x00 };

/* 1 when `va` holds a jmp (then nops to `length`) to a cave that begins with `cave`. */
static int detoured_to(unsigned int va, int length, const unsigned char *cave, int cave_length) {
    static const unsigned char nops[3] = { 0x90, 0x90, 0x90 };
    const unsigned char *at = (const unsigned char *)(UINT_PTR)va;
    unsigned char opcode = 0xE9;
    if (!vvfp_site_holds(va, &opcode, 1) || length - 5 > 3 || !vvfp_site_holds(va + 5u, nops, length - 5)) {
        return 0;
    }
    return vvfp_site_holds(va + 5u + *(const unsigned int *)(at + 1), cave, cave_length);
}

/* The People Cured guard: 2 sites of ours (stock bytes), 0 (the Statistics row's guard is there), -1 neither. */
static int cure_guard(vvfp_site_write *sites) {
    if (vvfp_site_holds(SITE_CURE_BEGIN, CURE_BEGIN_STOCK, 8) && vvfp_site_holds(SITE_CURE_COUNT, CURE_COUNT_STOCK, 7)) {
        vvfp_site_branch(&sites[0], SITE_CURE_BEGIN, 8, CURE_BEGIN_STOCK, 0xE9, (const void *)cure_begin_stub);
        vvfp_site_branch(&sites[1], SITE_CURE_COUNT, 7, CURE_COUNT_STOCK, 0xE9, (const void *)cure_count_stub);
        return 2;
    }
    if (detoured_to(SITE_CURE_BEGIN, 8, STATS_BEGIN_CAVE, 10) && detoured_to(SITE_CURE_COUNT, 7, STATS_COUNT_CAVE, 5)) {
        return 0;
    }
    return -1;
}

/* Called once by the patcher's start-up chain before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[3];
    unsigned int manager_rva;
    int guard;
    (void)shipped;
    if (g_installed || game != HL_GAME || !vvfp_patcher_file_exists(HE_FLAG_ROW)) {
        return;
    }
    vv5_villager_table((const unsigned char *)GetModuleHandleA(NULL), &manager_rva, &g_slots);
    if (g_slots == 0 || g_slots > 256u) {
        return;
    }
    g_records = (unsigned char *)GetModuleHandleA(NULL) + manager_rva + 0x48u;
    g_floor = he_option(HE_OPT_SICK_FLOOR, HE_SICK_FLOOR_DEFAULT, 1, 100);
    g_show_percent = he_option(HE_OPT_SHOW_PERCENT, 0, 0, 100);
    g_busyness = he_option(HE_OPT_BUSYNESS, 2, 1, 3);
    g_option_away_max = he_option(HE_OPT_AWAY_MAX, 0, 0, 64);
    g_option_same_max = he_option(HE_OPT_SAME_MAX, 0, 0, 64);
    g_option_cooldown = he_option(HE_OPT_OUTING_COOLDOWN, 0, 0, 10000);
    if (g_show_percent == 0) {
        g_show_percent = SHOW_PERCENT_OWN;
    }
    g_seed ^= GetTickCount() ^ (GetCurrentProcessId() << 16);
    if (g_seed == 0u) {
        g_seed = 0x9E3779B9u;
    }
    guard = cure_guard(&sites[1]);
    if (guard < 0) {
        return;                                           /* all or none: People Cured could not be guarded */
    }
    vvfp_site_branch(&sites[0], SITE_PICKER, 8, PICK_STOCK, 0xE9, (const void *)pick_stub);
    if (vvfp_install_sites(sites, 1 + guard)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
