/* VVFP Aspiring Adventurer -- "The Aspiring Adventurer", the owner's island event (2026-11-12), in all five games
   (the rows vvN_more_island_events).

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

#include "adv_text.inc"
#include "cave_text.inc"
#include "adv_core.inc"
#include "cave_core.inc"

static const adv_game *g_adv_game;     /* the installed game's, NULL when not installed */
static char g_vv12_title[128];         /* A New Home's / The Lost Children's title line */
enum { ADV_STAGE_NONE = 0, ADV_STAGE_INTRO, ADV_STAGE_QUESTION, ADV_STAGE_RESULT };

#include "adv_vv345.inc"
#include "adv_vv1.inc"
#include "adv_vv2.inc"

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

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
