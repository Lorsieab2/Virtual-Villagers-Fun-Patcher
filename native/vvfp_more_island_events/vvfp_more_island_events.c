/* VVFP Aspiring Adventurer -- "The Aspiring Adventurer", the owner's island event (2026-11-12), in all five games
   (the rows vvN_more_island_events), with The Cave Explorers (A New Home, cave_core.inc) and The Climb (The Lost
   Children, climb_core.inc), the owner's events of the same day, and The Troubling Signs (troubling_core.inc) and
   Diving for Treasure (dive_core.inc), The Secret City's, 2026-11-13, and The Playful Dolphins (dolphin_core.inc),
   The Tree of Life's, 2026-11-13, with The Mysterious Mask (mask_core.inc), the same day's.

   An aspiring adventurer of the village sees something glinting off the safe path: "Go investigate!" or "Stay on
   the safe path".  The owner's words, odds and effects are in adv_core.inc (and src/vv_aspiring_adventurer.py, the
   one source of the words, which scripts/build_more_island_events.py writes into adv_text.inc); each game's own
   island-event machinery is in adv_vv1.inc (A New Home's encounters), adv_vv2.inc (The Lost Children's family A)
   and adv_vv345.inc (the event tables of The Secret City, The Tree of Life and New Believers).

   Started once by VVFP Startup.dll before WinMain (VvfpStartup).  Every site's stock bytes are checked first, all
   of them or none (native/shared/install_sites.h): a site that is not stock leaves the game exactly as it was, and
   the event does not exist.  Nothing is written to the save, and no file is read or written: the event is as any
   island event, gone when its popup closes.  All new code is here: the executable gets only a jump or call at each
   site.  Our steps run under structured exception handling: a fault leaves the stock behaviour.  No debug output. */
#include <windows.h>
#include <stdint.h>
#include <string.h>

#include "../shared/install_sites.h"
#include "../shared/vvfp_translate.h"
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/vvfp_multi_answer.h"
#include "../shared/vvfp_multi_answer_12.h"

#include "adv_text.inc"
#include "cave_text.inc"
#include "adv_core.inc"
#include "adv_log.inc"
#include "climb_text.inc"
#include "troubling_text.inc"
#include "dive_text.inc"
#include "dolphin_text.inc"
#include "mask_text.inc"
#include "cave_core.inc"
#include "climb_core.inc"
#include "troubling_core.inc"
#include "dive_core.inc"
#include "dolphin_core.inc"
#include "mask_core.inc"

static const adv_game *g_adv_game;     /* the installed game's, NULL when not installed */
static char g_vv12_title[128];         /* A New Home's / The Lost Children's title line */
enum { ADV_STAGE_NONE = 0, ADV_STAGE_INTRO, ADV_STAGE_QUESTION, ADV_STAGE_RESULT };

/* Pick Island Event's picks (mie_pick.inc), asked by every game's draw. */
struct adv_object;
static const adv_flow *mp_due_flow(int game);
static struct adv_object *mp_due_object(int game);
static void mp_done(int game, int delivered);

#include "adv_vv345.inc"
#include "troubling_vv3.inc"
#include "dive_vv3.inc"
#include "dolphin_vv4.inc"
#include "mask_vv4.inc"
#include "adv_vv1.inc"
#include "adv_vv2.inc"
#include "mie_pick.inc"         /* Pick Island Event: the registry of every event (one line each) */

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static int started;
    (void)shipped;
    if (started) {
        return;
    }
    started = 1;
    __try {
        if (game == 1) {
            v1_install();
        } else if (game == 2) {
            v2_install();
        } else if (game >= 3 && game <= 5) {
            t_install(game);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_adv_game = NULL;
    }
}

/* The game whose event is in (1..5), 0 when none (for the tests and the Story / Cheat Upgrades companion). */
int __stdcall VvfpMoreIslandEventsInstalled(void) {
    return g_adv_game != NULL ? g_adv_game->game : 0;
}

/* Whether the event can happen now: at least two villagers who may go (Pick Island Event asks it). */
int __stdcall VvfpAdventurerPossible(void) {
    int possible = 0;
    __try {
        possible = adv_possible(g_adv_game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

/* Whether `record` may go on an adventure (or be the friend): the event's own test (for the tests). */
int __stdcall VvfpAdventurerEligible(const unsigned char *record) {
    return g_adv_game != NULL && record != NULL && g_adv_game->eligible(record);
}

/* The last popup's state (for the tests): out[0] the adventurer's record, [1] the friend's (-1 none), [2] female,
   [3] the find (0 nothing, 1 meat, 2 the chest), [4] Choice A's ending 1..9, [5] lost (0/1), [6] the lost ending
   1..6, [7] the healers' outcome 1..3, [8] the skill (0 Farming, 1 Building, 2 Research, 3 Healing), [9] its gain,
   [10] the injured health, [11] the reward, [12] the stranger is a woman, [13] answered, [14] the choice,
   [15] the intro's pages, [16] / [17] each choice's result pages, [18] the friend's name pointer.  Returns 19. */
int __stdcall VvfpAdventurerState(int *out) {
    if (out == NULL) {
        return 0;
    }
    out[0] = adv.hero; out[1] = adv.friend_; out[2] = adv.female; out[3] = adv.find; out[4] = adv.a_end;
    out[5] = adv.lost; out[6] = adv.lost_end; out[7] = adv.healer; out[8] = adv.skill_which;
    out[9] = adv.skill_amount; out[10] = adv.injured_health; out[11] = adv.award; out[12] = adv.stranger_female;
    out[13] = adv.answered; out[14] = adv.choice; out[15] = adv.intro.count; out[16] = adv.result[0].count;
    out[17] = adv.result[1].count; out[18] = (int)(uintptr_t)adv.friend_name;
    return 19;
}

/* Page `k` of a popup's pages (0 the question's, 1 / 2 each choice's result), as composed (for the tests). */
const char *__stdcall VvfpAdventurerPage(int set, int k) {
    const adv_pages *pages = set == 0 ? &adv.intro : (set == 1 ? &adv.result[0] : &adv.result[1]);
    if (set < 0 || set > 2 || k < 0 || k >= pages->count) {
        return NULL;
    }
    return pages->text[k];
}

/* The Cave Explorers (A New Home): whether it can happen now -- The Cave puzzle done and two villagers who may go. */
int __stdcall VvfpCaveExplorersPossible(void) {
    int possible = 0;
    __try {
        possible = cave_possible(g_adv_game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

/* Its last popup's state (for the tests): out[0] / [1] name1's / name2's record, [2] / [3] female, [4] A (1) or B
   (0) after "Proceed Further", [5] the screamer (0 name1, 1 name2), [6] what's wrong 0..3, [7] the run's ending
   (0 the argument, 1 they make up, 2 the chasm), [8] the one who slips, [9] the finder, [10] the find (0 the map,
   1 the coins, 2 the treasure map, 3 the food), [11] its award, [12] returned for food (1) or tech (0), [13] its award,
   [14] kept: 0 the researchers, 1 both die, 2 name2 dies, [15] its award, [16] the answers clicked, [17] the
   ending (-1 none yet: 0 don't, 1 the find, 2 left, 3 right, 4 return, 5 keep), [18] each question's pages (four
   bytes), [19] each ending's pages (six nibbles).  Returns 20. */
int __stdcall VvfpCaveExplorersState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    out[0] = cave.who[0]; out[1] = cave.who[1]; out[2] = cave.female[0]; out[3] = cave.female[1];
    out[4] = cave.scream_a; out[5] = cave.screamer; out[6] = cave.wrong; out[7] = cave.a_end; out[8] = cave.faller;
    out[9] = cave.finder; out[10] = cave.find; out[11] = cave.find_award; out[12] = cave.return_food;
    out[13] = cave.return_award; out[14] = cave.keep_end; out[15] = cave.keep_award; out[16] = cave.answered;
    out[17] = cave.ending;
    out[18] = 0;
    for (k = 0; k < CAVE_QUESTIONS; ++k) {
        out[18] |= (cave.question[k].count & 0xFF) << (8 * k);
    }
    out[19] = 0;
    for (k = 0; k < CAVE_ENDINGS; ++k) {
        out[19] |= (cave.endings[k].count & 0xF) << (4 * k);
    }
    return 20;
}

/* Page `k` of question `set` (0..3: the start, Proceed / Stay, the run, the stay) or, from 4, of ending set - 4. */
const char *__stdcall VvfpCaveExplorersPage(int set, int k) {
    const adv_pages *pages;
    if (set < 0 || set >= CAVE_QUESTIONS + CAVE_ENDINGS) {
        return NULL;
    }
    pages = cave_set(set);
    return k >= 0 && k < pages->count ? pages->text[k] : NULL;
}

/* The Climb (The Lost Children): whether it can happen now -- one villager who may climb. */
int __stdcall VvfpClimbPossible(void) {
    int possible = 0;
    __try {
        possible = climb_possible(g_adv_game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        possible = 0;
    }
    return possible;
}

/* Its last popup's state (for the tests): out[0] the villager's record, [1] female, [2] the fall (1) or the summit
   (0) after "Go with the plan", [3] the summit's award, [4] the advice's Research gain, [5] answered, [6] the choice
   (0 the plan, 1 the advice), [7] the ending (-1 none yet: 0 the fall, 1 the summit, 2 the advice), [8] the
   question's pages, [9] / [10] / [11] each ending's pages.  Returns 12. */
int __stdcall VvfpClimbState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    out[0] = climb.hero; out[1] = climb.female; out[2] = climb.falls; out[3] = climb.award; out[4] = climb.gain;
    out[5] = climb.answered; out[6] = climb.choice; out[7] = climb.ending; out[8] = climb.intro.count;
    for (k = 0; k < CLIMB_ENDINGS; ++k) {
        out[9 + k] = climb.endings[k].count;
    }
    return 12;
}

/* Page `k` of set `set`: 0 the question, 1..3 the endings (the fall, the summit, the advice). */
const char *__stdcall VvfpClimbPage(int set, int k) {
    const adv_pages *pages;
    if (set < 0 || set > CLIMB_ENDINGS) {
        return NULL;
    }
    pages = climb_set(set);
    return k >= 0 && k < pages->count ? pages->text[k] : NULL;
}

/* The Troubling Signs (The Secret City): whether it can happen now -- a robed chief, nine who may be picked, a
   population of 61 or more and the tribe's name. */
int __stdcall VvfpTroublingSignsPossible(void) {
    return ts_listable();
}

/* Its last popup's state (for the tests): out[0] the chief's record, [1] the chief is a woman, [2..5] the four
   advisors' records (the spiritual leaders, the magicians, the naturalists, the scientists and healers), [6..10] the
   five travellers', [11..14] each answer's award, [15] answered, [16] the answer (0..3), [17] the effects made,
   [18] the question's pages, [19..22] each answer's pages, [23] the stage (0 none, 1 the opening, 2 the question,
   3 the answer's pages), [24] the page shown, [25] the population, [26] the room the four buttons take.
   Returns 27. */
int __stdcall VvfpTroublingSignsState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    out[0] = ts.chief; out[1] = ts.female;
    for (k = 0; k < TS_ADVISORS; ++k) {
        out[2 + k] = ts.advisor[k];
    }
    for (k = 0; k < TS_TRAVELLERS; ++k) {
        out[6 + k] = ts.traveller[k];
    }
    for (k = 0; k < TS_GROUPS; ++k) {
        out[11 + k] = ts.award[k];
        out[19 + k] = ts.result[k].count;
    }
    out[15] = ts.answered; out[16] = ts.choice; out[17] = ts.effects_made; out[18] = ts.intro.count;
    out[23] = g_ts_stage; out[24] = g_ts_page;
    __try {
        out[25] = g_ts != NULL ? g_ts->population() : -1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        out[25] = -1;
    }
    out[26] = g_ts_room;
    return 27;
}

/* Page `k` of set `set`: 0 the question, 1..4 each answer's. */
const char *__stdcall VvfpTroublingSignsPage(int set, int k) {
    const adv_pages *pages;
    if (set < 0 || set > TS_GROUPS) {
        return NULL;
    }
    pages = ts_set(set);
    return k >= 0 && k < pages->count ? pages->text[k] : NULL;
}

/* The four answer buttons of the dialog showing it, top to bottom (for the tests): out[0..3]; 4. */
int __stdcall VvfpTroublingSignsButtons(void **out) {
    int k;
    if (out == NULL || g_ts_dialog == NULL) {
        return 0;
    }
    for (k = 0; k < TS_GROUPS; ++k) {
        out[k] = ts_button(g_ts_dialog, k);
    }
    return 4;
}

/* Diving for Treasure (The Secret City): whether it can happen now -- two villagers of 18 or more who may be picked
   (the diver and the head Doctor). */
int __stdcall VvfpDivingPossible(void) {
    return g_dv != NULL ? dv_listable() : 0;
}

/* Its last popup's state (for the tests): out[0] the diver's record, [1] the head Doctor's, [2] the diver is a woman,
   [3] the find (0 A, 1 B, 2 C, 3 D), [4] D: survives (1) or sinks (0), [5] sinking: 0 dies, 1 disappears, 2 rescued,
   [6] A's tech award, [7] C's food award, [8] the rescue's Healing gain, [9] "Better not"'s Parenting gain,
   [10] answered, [11] the choice (0 "Swim deeper", 1 "Better not"), [12] the ending (-1 none yet: 0 A, 1 B, 2 C,
   3 D1, 4 D2a, 5 D2b, 6 D2c, 7 "Better not"), [13] the effects made, [14] the question's pages, [15..22] each
   ending's pages.  Returns 23. */
int __stdcall VvfpDivingState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    out[0] = dv.diver; out[1] = dv.doctor; out[2] = dv.female; out[3] = dv.find; out[4] = dv.survives;
    out[5] = dv.sink; out[6] = dv.tech_award; out[7] = dv.food_award; out[8] = dv.healing_gain;
    out[9] = dv.parenting_gain; out[10] = dv.answered; out[11] = dv.choice; out[12] = dv.ending;
    out[13] = dv.effects_made; out[14] = dv.intro.count;
    for (k = 0; k < DV_ENDINGS; ++k) {
        out[15 + k] = dv.endings[k].count;
    }
    return 23;
}

/* Page `k` of set `set`: 0 the question, 1..8 the endings (A, B, C, D1, D2a, D2b, D2c, "Better not"). */
const char *__stdcall VvfpDivingPage(int set, int k) {
    const adv_pages *pages;
    if (set < 0 || set > DV_ENDINGS) {
        return NULL;
    }
    pages = dv_set(set);
    return k >= 0 && k < pages->count ? pages->text[k] : NULL;
}

/* The Playful Dolphins (The Tree of Life): whether it can happen now -- two villagers of 14 or more who may be picked
   (no puzzle needed). */
int __stdcall VvfpDolphinsPossible(void) {
    return g_dp != NULL ? dp_listable() : 0;
}

/* Its last popup's state (for the tests): out[0] the swimmer's record, [1] the swimmer is a woman, [2] the tail slap
   (1) or the hunt (0) after "Swim towards the dolphins", [3] the hunt's food award, [4] hanging back's food award,
   [5] the slap's health loss, [6] answered, [7] the choice (0 swim, 1 hang back), [8] the ending (-1 none yet: 0 the
   hunt, 1 the slap, 2 hang back), [9] the effects made, [10] the question's pages, [11..13] each ending's pages,
   [14] / [15] the health before / after the slap.  Returns 16. */
int __stdcall VvfpDolphinsState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    out[0] = dp.swimmer; out[1] = dp.female; out[2] = dp.slap; out[3] = dp.hunt_award; out[4] = dp.back_award;
    out[5] = dp.loss; out[6] = dp.answered; out[7] = dp.choice; out[8] = dp.ending; out[9] = dp.effects_made;
    out[10] = dp.intro.count;
    for (k = 0; k < DP_ENDINGS; ++k) {
        out[11 + k] = dp.endings[k].count;
    }
    out[14] = dp.health_before; out[15] = dp.health_after;
    return 16;
}

/* Page `k` of set `set`: 0 the question, 1..3 the endings (the hunt, the slap, hang back). */
const char *__stdcall VvfpDolphinsPage(int set, int k) {
    const adv_pages *pages;
    if (set < 0 || set > DP_ENDINGS) {
        return NULL;
    }
    pages = dp_set(set);
    return k >= 0 && k < pages->count ? pages->text[k] : NULL;
}

/* The Mysterious Mask (The Tree of Life): whether it can happen now -- a population of 61 or more, two children under
   14 and five villagers of 18 or more who may be picked. */
int __stdcall VvfpMysteriousMaskPossible(void) {
    return g_mk != NULL ? mk_listable() : 0;
}

/* Its last popup's state (for the tests): out[0..3] the group's records (-1 none; [0] name1, [1] name2), [4] the
   group's size, [5..9] the five volunteers', [10] name1 is a girl, [11] a walk gets home (1) or is lost (0), [12] lost:
   captured (1) or rescued (0), [13] answered, [14] the answer (0..3), [15] the ending (-1 none yet; 0..7 as
   src/vv_mysterious_mask.py ENDINGS), [16] the effects made, [17] the villagers they took, [18] the question's pages,
   [19..26] each ending's pages, [27] the lines a page holds.  Returns 28. */
int __stdcall VvfpMysteriousMaskState(int *out) {
    int k;
    if (out == NULL) {
        return 0;
    }
    for (k = 0; k < MK_GROUP_MAX; ++k) {
        out[k] = mk.group[k];
    }
    out[4] = mk.group_count;
    for (k = 0; k < MK_EXPEDITION; ++k) {
        out[5 + k] = mk.volunteer[k];
    }
    out[10] = mk.female; out[11] = mk.home; out[12] = mk.captured; out[13] = mk.answered; out[14] = mk.choice;
    out[15] = mk.ending; out[16] = mk.effects_made; out[17] = mk.gone; out[18] = mk.intro.count;
    for (k = 0; k < MK_ENDINGS; ++k) {
        out[19 + k] = mk.endings[k].count;
    }
    out[27] = g_mk_layout.lines;
    return 28;
}

/* Page `k` of set `set`: 0 the question, 1..8 the endings. */
const char *__stdcall VvfpMysteriousMaskPage(int set, int k) {
    const adv_pages *pages;
    if (set < 0 || set > MK_ENDINGS) {
        return NULL;
    }
    pages = mk_set(set);
    return k >= 0 && k < pages->count ? pages->text[k] : NULL;
}

/* The owner's protected villagers (adv_core.inc adv_is_protected_allowing): 1 when `record` of `game` may never be
   picked by these events; `allow` ADV_ALLOW_TRIBAL_CHIEF (1) lets The Secret City's Tribal Chief through, for an event
   the owner names (The Troubling Signs' speaker).  For the tests and the other events. */
int __stdcall VvfpMoreIslandEventsProtected(int game, const unsigned char *record, unsigned int allow) {
    int is_protected = 1;
    __try {
        is_protected = adv_is_protected_allowing(game, record, allow);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        is_protected = 1;
    }
    return is_protected;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
