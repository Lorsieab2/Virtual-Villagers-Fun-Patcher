/* Popup When Believers Become Heathens (New Believers) -- included by vvfp_story_upgrades.c, after
   story_time_skip.inc.

   The owner (2026-11-08): "There should be a popup too", shown like a Custom Island Event that always comes
   when villagers turn Heathen through the Faith drift, kept apart from the game's own island events.
   "VVFP Faith Notice.dll" counts the believers New Believers' Faith drift turns Heathen, by the loss roll that
   took their Faith (native/vvfp_faith_notice); this shows them, once no conversion has come for a few seconds --
   so the conversions of a catch-up, a Time Warp or a whole Choose Time Skip Amount make one popup -- with the
   island-event notice the Time Skip's closing popup uses (time_skip_notice_arm, story_notice_arm): the game's
   own popup window, art and sound, made due as the Island Event purchase does and delivered by the game's
   trigger.  Like that notice it is kept apart from the island events: the trigger's count of it in Island
   Events Seen is taken back on delivery, the Island Events log writes nothing for it
   (VvfpStoryTimeSkipNoticeShown), and the game's own next island event keeps its time (the arm goes through
   story_island_arming, native/shared/island_timer_keep.h).

     Hard Choices
     Several of your villagers have lost faith in you due to the dire conditions and have decided to join the
     heathens' tribe.

     3 villagers have left due to starvation, 1 due to sickness and 2 due to too few believers.

   With the Guardians of Isola rewrite (its sm.xml makes the game's own bottom-bar line eSayStoppedBelieving,
   string 0x48, "A villager has left the tribe!"): "Several of your villagers have lost hope due to the dire
   conditions and have decided to join the Isolans' tribe." and "too few tribe members".  The game's string is read where the game reads it
   (0x4506D0: the entry [0x5240A8 + 4 * id], its loaded text +0xC or its built-in +8), so the popup follows the
   same file the bottom bar does.  The title is FAITH_NOTICE_TITLE, "Hard Choices" (the owner's).

   ONLY THE FAITH DRIFT.  The companion counts a believer only when the drift's own FAITH_ADD makes them a
   Heathen (the record is a believer as the life tick calls the drift and a Heathen when it returns).  An island
   event that makes a Heathen -- The Spa (0x415D02) and The Cracked Mask (0x416C51) through the setter, the
   Custom Island Event's "Becomes a Heathen" through 0x4669E0 itself -- and every Heathen an island event, a
   barrel or the Story / Cheat Upgrades makes (the creator 0x46FD20: never a believer) is never counted.

   WHEN.  It waits for a time skip to finish and for the skip's own closing popup, for an island event's popup to
   close, for the one event slot to be free (a pick, a custom event or an island event on its way goes first)
   and for the game to be running -- so it is armed only when the game's trigger will show it at once, and holds
   the slot for no more than the moment until then: it never stands in the way of an event the player buys.  The
   game's trigger needs a living adult, as for every island event; a village with none keeps the count until it
   has one.  The counts are taken from the companion only when the popup is armed. */

#define FAITH_NOTICE_GAME 5
#define FAITH_STRING_ID 0x48u            /* eSayStoppedBelieving */
#define FAITH_STRING_TABLE 0x5240A8u     /* 0x4506D0: [table + 4 * id] -> { id, name, built-in, loaded } */
/* The popup's title, the owner's (2026-11-08), with and without Guardians of Isola (one line; its translation
   row is ...FAITH_NOTICE_TITLE.s0). */
#define FAITH_NOTICE_TITLE "Hard Choices"
#define FAITH_REASONS 5                  /* starvation, hunger, sickness, too few believers, other */

typedef int (__stdcall *faith_pending_fn)(int game, int *out);
typedef void (__stdcall *faith_taken_fn)(int game);
static faith_pending_fn faith_pending_export;
static faith_taken_fn faith_taken_export;
static ce_event faith_notice_event;

#ifdef VVFP_TEST
static int test_faith_counts[FAITH_REASONS], test_faith_taken, test_faith_waiting;
#endif

/* Asks "VVFP Faith Notice.dll" (absent: nothing to say): out[0] the believers turned Heathen, out[1..5] how many
   for each reason.  Looked up until found, as the Island Events export. */
static int faith_notice_pending(int *out) {
    HMODULE module;
#ifdef VVFP_TEST
    if (test_faith_waiting) {
        int i;
        out[0] = 0;
        for (i = 0; i < FAITH_REASONS; ++i) {
            out[1 + i] = test_faith_counts[i];
            out[0] += test_faith_counts[i];
        }
        return 1;
    }
#endif
    if (faith_pending_export == NULL || faith_taken_export == NULL) {
        module = GetModuleHandleA("VVFP Faith Notice.dll");
        if (module == NULL) {
            return 0;
        }
        faith_pending_export = (faith_pending_fn)(void *)GetProcAddress(module, "VvfpFaithNoticePending");
        faith_taken_export = (faith_taken_fn)(void *)GetProcAddress(module, "VvfpFaithNoticeTaken");
        if (faith_pending_export == NULL || faith_taken_export == NULL) {
            return 0;
        }
    }
    return faith_pending_export(FAITH_NOTICE_GAME, out) != 0;
}

static void faith_notice_taken(void) {
#ifdef VVFP_TEST
    if (test_faith_waiting) {
        test_faith_waiting = 0;
        ++test_faith_taken;
        return;
    }
#endif
    if (faith_taken_export != NULL) {
        faith_taken_export(FAITH_NOTICE_GAME);
    }
}

/* 1 when the game's own eSayStoppedBelieving says "left the tribe" (the Guardians of Isola rewrite). */
static int faith_notice_left_the_tribe(void) {
    static const char WORDS[] = "left the tribe";
    int found = 0;
    __try {
        const unsigned int *entry = *(const unsigned int *const *)(UINT_PTR)(FAITH_STRING_TABLE + 4u * FAITH_STRING_ID);
        const char *text;
        int i, k;
        if (entry != NULL && entry[0] == FAITH_STRING_ID) {
            text = (const char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
            for (i = 0; text != NULL && text[i] != '\0' && i < 256 && !found; ++i) {
                for (k = 0; WORDS[k] != '\0'; ++k) {
                    char c = text[i + k];
                    if (c >= 'A' && c <= 'Z') {
                        c = (char)(c - 'A' + 'a');
                    }
                    if (c != WORDS[k]) {
                        break;
                    }
                }
                found = WORDS[k] == '\0';
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        found = 0;
    }
    return found;
}

/* Reason `k`'s words in the player's language (Guardians of Isola's for the believers when `isola`).
   "starvation", "hunger" and "sickness" are words of the game's own, so they have no row of their own. */
static const char *faith_notice_reason(int k, int isola) {
    switch (k) {
    case 0:
        return "starvation";
    case 1:
        return "hunger";
    case 2:
        return "sickness";
    case 3:
        return isola ? vvfp_tr("vvfp.story/story_faith_notice.faith_notice_reason.s0", "too few tribe members", 64)
                     : vvfp_tr("vvfp.story/story_faith_notice.faith_notice_reason.s1", "too few believers", 64);
    default:
        return isola ? vvfp_tr("vvfp.story/story_faith_notice.faith_notice_reason.s2", "a loss of hope", 64)
                     : vvfp_tr("vvfp.story/story_faith_notice.faith_notice_reason.s3", "a loss of faith", 64);
    }
}

/* "X villagers have left due to A, Y due to B and Z due to C." into `out` (`cap` bytes): every reason that
   came, in their order; the first item says "1 villager has" or "N villagers have". */
static void faith_notice_reasons(char *out, int cap, const int *counts, int isola) {
    char item[160];
    int k, listed = 0, total = 0, done = 0;
    for (k = 0; k < FAITH_REASONS; ++k) {
        total += counts[k] > 0;
    }
    out[0] = '\0';
    for (k = 0; k < FAITH_REASONS; ++k) {
        if (counts[k] <= 0) {
            continue;
        }
        if (listed == 0 && counts[k] == 1) {
            ce_tr_printf(item, sizeof item, "vvfp.story/story_faith_notice.faith_notice_reasons.s0",
                         "1 villager has left due to %s", faith_notice_reason(k, isola));
        } else if (listed == 0) {
            ce_tr_printf(item, sizeof item, "vvfp.story/story_faith_notice.faith_notice_reasons.s1",
                         "%d villagers have left due to %s", counts[k], faith_notice_reason(k, isola));
        } else {
            ce_tr_printf(item, sizeof item, "vvfp.story/story_faith_notice.faith_notice_reasons.s2",
                         "%d due to %s", counts[k], faith_notice_reason(k, isola));
        }
        ++listed;
        if (listed > 1) {
            lstrcatA(out, listed == total
                              ? vvfp_tr("vvfp.story/story_faith_notice.faith_notice_reasons.s3", " and ", 16)
                              : ", ");
        }
        if (lstrlenA(out) + lstrlenA(item) + 2 < cap) {
            lstrcatA(out, item);
            done = 1;
        }
    }
    if (done) {
        lstrcatA(out, ".");
    }
}

/* The popup's title and text for the counts (`info`: the total, then each reason's) into `e`. */
static void faith_notice_compose(ce_event *e, const int *info) {
    char why[400];
    int isola = faith_notice_left_the_tribe();
    const char *opening;
    memset(e, 0, sizeof *e);
    lstrcpynA(e->title, vvfp_tr("vvfp.story/story_faith_notice.FAITH_NOTICE_TITLE.s0", FAITH_NOTICE_TITLE,
                                sizeof e->title), sizeof e->title);
    if (isola) {
        /* (Each English on one line: the translation inventory reads one literal.) */
        opening = info[0] == 1
            ? vvfp_tr("vvfp.story/story_faith_notice.faith_notice_compose.s0",
                      "One of your villagers has lost hope due to the dire conditions and has decided to join the Isolans' tribe.", 200)
            : vvfp_tr("vvfp.story/story_faith_notice.faith_notice_compose.s1",
                      "Several of your villagers have lost hope due to the dire conditions and have decided to join the Isolans' tribe.", 200);
    } else {
        opening = info[0] == 1
            ? vvfp_tr("vvfp.story/story_faith_notice.faith_notice_compose.s2",
                      "One of your villagers has lost faith in you due to the dire conditions and has decided to join the heathens' tribe.", 200)
            : vvfp_tr("vvfp.story/story_faith_notice.faith_notice_compose.s3",
                      "Several of your villagers have lost faith in you due to the dire conditions and have decided to join the heathens' tribe.", 200);
    }
    faith_notice_reasons(why, sizeof why, info + 1, isola);
    lstrcpynA(e->text, opening, sizeof e->text);
    if (why[0] != '\0' && lstrlenA(e->text) + 2 + lstrlenA(why) < (int)sizeof e->text) {
        lstrcatA(e->text, "\n\n");          /* a paragraph of its own */
        lstrcatA(e->text, why);
    }
}

/* Called every frame (VvfpStoryInstall), after the time skip's own tick. */
static void faith_notice_tick(int game) {
    int info[1 + FAITH_REASONS];
    const story_host *host = story_time_skip_host(game);
    if (game != FAITH_NOTICE_GAME || !story_installed(game)
        || (time_skip.game == game && (time_skip.active || time_skip.finishing || time_skip.notice > 0))
        || time_skip_event_open() || (host != NULL && !story_host_running(host))
        || !faith_notice_pending(info) || info[0] <= 0) {
        return;
    }
    faith_notice_compose(&faith_notice_event, info);
    if (story_notice_arm(game, &faith_notice_event)) {
        faith_notice_taken();          /* armed: the game's own trigger shows it */
    }
}

/* Start Over or a deleted tribe (VvfpStoryVillageReset): the companion's waiting batch was that village's, so it
   is dropped there (VvfpFaithNoticeVillageReset); an armed popup goes with every other armed event. */
static void faith_notice_village_reset(int game) {
    typedef void (__stdcall *reset_fn)(int game);
    HMODULE module;
    reset_fn reset;
#ifdef VVFP_TEST
    test_faith_waiting = 0;
#endif
    if (game != FAITH_NOTICE_GAME) {
        return;
    }
    module = GetModuleHandleA("VVFP Faith Notice.dll");
    reset = module != NULL ? (reset_fn)(void *)GetProcAddress(module, "VvfpFaithNoticeVillageReset") : NULL;
    if (reset != NULL) {
        reset(game);
    }
}

#ifdef VVFP_TEST
/* Stands in for "VVFP Faith Notice.dll": how many believers turned Heathen for each reason (starvation,
   hunger, sickness, too few believers, other). */
__declspec(dllexport) void __stdcall VvfpStoryProbeFaithNotice(const int *counts) {
    int i;
    test_faith_waiting = 0;
    for (i = 0; i < FAITH_REASONS; ++i) {
        test_faith_counts[i] = counts[i];
        test_faith_waiting |= counts[i] > 0;
    }
}

/* How many times the count was taken (the popup armed). */
__declspec(dllexport) int __stdcall VvfpStoryProbeFaithNoticeTaken(void) {
    return test_faith_taken;
}

/* The armed popup's title and text (when the armed custom event is a notice), else empty. */
__declspec(dllexport) void __stdcall VvfpStoryProbeArmedNotice(char *title, char *text) {
    title[0] = text[0] = '\0';
    if (ce_armed && ce_armed_is_notice) {
        lstrcpyA(title, ce_armed_event.title);
        lstrcpyA(text, ce_armed_event.text);
    }
}
#endif
