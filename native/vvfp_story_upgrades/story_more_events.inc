/* Pick Island Event: the More Island Events events.  Included by vvfp_story_upgrades.c.

   The owner (v1.35.97): Pick Island Event also picks every event of the More Island Events patch -- only when that
   patch is installed in the game played.  Its registry (native/vvfp_more_island_events/mie_pick.inc, one line per
   event) says which events the game has, their titles, and whether each can happen now by the event's own
   requirements (the owner's protected villagers included); this file only lists them and arms the pick.

   The list shows them after the game's own events.  One whose requirements do not hold is marked "not possible
   right now" and its description says what it needs; choosing it anyway (double-click, or OK) is refused with a plain
   message: "<title> needs <what it needs>."

   A pick of one is armed as any pick (the island event made due, the same lock, the ten-minute lapse, the save slot
   it was bought in, kept across a quit by the queue file) with the slot the game's chooser needs to reach the draw
   More Island Events makes: A New Home the villager encounters, The Lost Children family A (each index SM_INDEX, past
   every event of the game: the draw never reaches it), the later games the event table's slot 0 (the slot More
   Island Events keeps its events in).  The More Island Events companion's draw then asks VvfpStoryMoreEventDue which
   event is due and takes it; in A New Home and The Lost Children it says with VvfpStoryMoreEventDone whether the event
   came (the later games' slot-0 pick is delivered or refused here, as any picked event). */

#define SM_ROW 0x10000                  /* a list entry's data: SM_ROW + the registry index */
#define SM_MAX 256                      /* list entries: the registry's, then the collection's */
#define SM_COLL_BASE 0x4000             /* a list entry's k for collection entry i: SM_COLL_BASE + i */
#define SM_INDEX 0x3E                   /* A New Home / The Lost Children: the family's index of a More pick */
#define SM_QUEUE_BASE (-1000)           /* the queue file's pick_index of a More pick: SM_QUEUE_BASE - k */
#define SM_TEXT 400

typedef int (__stdcall *sm_count_fn)(void);
typedef int (__stdcall *sm_info_fn)(int k, char *title, char *description, char *needs, int cap);
typedef int (__stdcall *sm_installed_fn)(void);

static int pick_more = -1;              /* the registry index of the armed More pick, -1 none */
static story_event sm_event;            /* the armed More pick, as the pick's event (pick_event) */
static char sm_title[SM_TEXT], sm_needs[SM_TEXT], sm_desc[SM_TEXT];

/* The list's More entries, filled as the chooser opens. */
static struct {
    int count;
    int k[SM_MAX];                      /* registry index */
    int possible[SM_MAX];
    char title[SM_MAX][SM_TEXT];
    char description[SM_MAX][SM_TEXT];
    char needs[SM_MAX][SM_TEXT];
} sm_list;

static FARPROC sm_proc(const char *name) {
    HMODULE more = GetModuleHandleA("VVFP More Island Events.dll");
    return more != NULL ? GetProcAddress(more, name) : NULL;
}

/* Whether More Island Events is installed in `game`. */
static int sm_installed(int game) {
    sm_installed_fn installed = (sm_installed_fn)(void *)sm_proc("VvfpMoreIslandEventsInstalled");
    return installed != NULL && installed() == game;
}

/* Registry entry `k` of `game`: -1 not in this game, else 1 possible now / 0 not, with its words. */
static int sm_info(int game, int k, char *title, char *description, char *needs) {
    sm_info_fn info = (sm_info_fn)(void *)sm_proc("VvfpMoreIslandEventsPickInfo");
    if (!sm_installed(game) || info == NULL) {
        return -1;
    }
    return info(k, title, description, needs, SM_TEXT);
}

/* The More entries of `game` (none without More Island Events). */
static void sm_fill_more(int game) {
    sm_count_fn count = (sm_count_fn)(void *)sm_proc("VvfpMoreIslandEventsPickCount");
    int k, n = count != NULL && sm_installed(game) ? count() : 0;
    sm_list.count = 0;
    for (k = 0; k < n && sm_list.count < SM_MAX; ++k) {
        int i = sm_list.count;
        int state = sm_info(game, k, sm_list.title[i], sm_list.description[i], sm_list.needs[i]);
        if (state < 0 || sm_list.title[i][0] == '\0') {
            continue;
        }
        sm_list.k[i] = k;
        sm_list.possible[i] = state;
        ++sm_list.count;
    }
}

/* The list's entries after the game's own: More Island Events' events, then the Isola Grand Event Collection's
   (when that row is installed: story_collection.inc sc_pick_fill), each possible now or with what it needs. */
static void sm_fill(int game) {
    sm_fill_more(game);
    (void)sc_pick_fill(game);
}

/* "<title> needs <what it needs>." */
static void sm_refusal(const char *title, const char *needs, char *out, int cap) {
    char text[SM_TEXT * 3];
    wsprintfA(text, vvfp_tr("vvfp.story/story_more_events.sm_refusal.s0", "%s needs %s.", 200), title, needs);
    lstrcpynA(out, text, cap);
}

/* The plain refusal of list entry `m` chosen while it can not happen. */
static void sm_refusal_of(int m, char *out, int cap) {
    if (sm_list.k[m] >= SM_COLL_BASE) {
        wsprintfA(out, vvfp_tr("vvfp.story/story_more_events.sm_refusal_of.s0", "%.300s can not happen right now: %.600s",
                               200), sm_list.title[m], sm_list.needs[m]);
        return;
    }
    sm_refusal(sm_list.title[m], sm_list.needs[m], out, cap);
}

typedef int (__stdcall *sm_single_fn)(int k);

/* Whether registry entry `k` is a single-result event (The Remembrance Ceremony, The Rumblings): A New Home's and
   The Lost Children's island events, not their two-choice ones (VvfpMoreIslandEventsPickSingle). */
static int sm_single(int k) {
    sm_single_fn single = (sm_single_fn)(void *)sm_proc("VvfpMoreIslandEventsPickSingle");
    return single != NULL && single(k) == 1;
}

/* The family slot registry entry `k` is armed with: A New Home the villager encounters, or its island events for a
   single-result event; The Lost Children family A, or family C; the later games the event table's slot 0. */
static int sm_slot_of(int game, int k) {
    switch (game) {
    case 1: return ((sm_single(k) ? VV1_FAMILY_ISLAND : VV1_FAMILY_ENCOUNTER) << 6) | SM_INDEX;
    case 2: return ((sm_single(k) ? VV2_FAMILY_C : VV2_FAMILY_A) << 6) | SM_INDEX;
    default: return 0;                  /* the event table's slot 0 */
    }
}

/* Whether `slot` is one a More pick of `game` is armed with. */
static int sm_slot_ok(int game, int slot) {
    switch (game) {
    case 1: return slot == ((VV1_FAMILY_ENCOUNTER << 6) | SM_INDEX) || slot == ((VV1_FAMILY_ISLAND << 6) | SM_INDEX);
    case 2: return slot == ((VV2_FAMILY_A << 6) | SM_INDEX) || slot == ((VV2_FAMILY_C << 6) | SM_INDEX);
    default: return slot == 0;
    }
}

/* The pick's event for registry entry `k` (its title and what it needs, for the "could not happen" notice). */
static int sm_describe(int game, int k) {
    int state = sm_info(game, k, sm_title, sm_desc, sm_needs);
    sm_event.slot = sm_slot_of(game, k);
    sm_event.title = sm_title;
    sm_event.variant = "";
    sm_event.description = sm_desc;
    sm_event.requires = sm_needs;
    return state;
}

/* Arms registry entry `k` for `game` (the event already checked): 1 on success. */
static int sm_arm(int game, int k) {
    if (!GAMES[game].arm()) {
        return 0;
    }
    pick_slot = sm_slot_of(game, k);
    pick_game = game;
    pick_tick = STORY_TICK();
    pick_event = &sm_event;
    pick_village = story_village_now(game);
    pick_more = k;
    pick_natural = 0;
    return 1;
}

/* The armed More pick's registry index for `game`, or -1. */
static int sm_armed(int game) {
    return pick_slot >= 0 && pick_game == game && pick_event == &sm_event && pick_more >= 0
               && sm_slot_ok(game, pick_slot) ? pick_more : -1;
}

/* Called by "VVFP More Island Events.dll" as its draw runs: the registry index of the event Pick Island Event has
   due in `game` now, or -1. */
__declspec(dllexport) int __stdcall VvfpStoryMoreEventDue(int game) {
    if (game < 1 || game > 5 || install_state[game] != 1) {
        return -1;
    }
    drop_lapsed_pick();
    if (!story_village_is(game, &pick_village)) {
        return -1;
    }
    return sm_armed(game);
}

/* Called by "VVFP More Island Events.dll" (A New Home, The Lost Children) once it took the due pick: `delivered`
   1 the event came, 0 it could not happen (the game's own choice runs; the next chooser says why). */
__declspec(dllexport) void __stdcall VvfpStoryMoreEventDone(int game, int delivered) {
    if (sm_armed(game) < 0) {
        return;
    }
    pick_slot = -1;
    pick_more = -1;
    if (delivered) {
        STORY_COUNT(delivered);
        last_failed_event = NULL;
    } else {
        STORY_COUNT(refused);
        last_failed_event = pick_natural ? NULL : &sm_event;
        last_failed_lapsed = 0;
    }
}

/* The purchase of registry entry `k` once chosen in the list: confirmed, checked again, armed. */
static int sm_buy(int game, HWND owner, int k) {
    char message[1800];
    int state;
    if (k >= SM_COLL_BASE) {
        return sc_pick_buy(game, owner, k - SM_COLL_BASE);   /* an Isola Grand Event Collection event */
    }
    state = sm_describe(game, k);
    if (state < 0) {
        return 0;
    }
    wsprintfA(message,
              vvfp_tr("vvfp.story/vvfp_story_upgrades.story_pick_island_event.s6",
                      "Do you want to buy Pick Island Event (%s) for %s tech points?%s%s\r\n\r\nPress OK to confirm, or Cancel.",
                      400), sm_title, story_price_text(game), "", "");
    if (vvfp_message_box(owner, message, "Origins Upgrades",
                         MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    /* The village may have moved on while the boxes were open. */
    state = sm_describe(game, k);
    if (state != 1) {
        sm_refusal(sm_title, sm_needs, message, sizeof message);
        vvfp_message_box(owner, message, "Pick Island Event", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if (ce_armed || GAMES[game].island_pending() || !sm_arm(game, k)) {
        MessageBoxA(owner, "That island event can not happen right now. No tech points have been deducted.",
                    "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    wsprintfA(message, vvfp_tr("vvfp.story/vvfp_story_upgrades.story_pick_island_event.s9", "%s is on its way.", 200),
              sm_title);
    vvfp_message_box(owner, message, "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* The queue file (story_queue.inc): a More pick's pick_index, and its restore.  Builds before this one find the
   index outside the game's table and leave it. */
static int sm_queue_index(int game) {
    int k = sm_armed(game);
    return k >= 0 ? SM_QUEUE_BASE - k : 0x7FFFFFFF;
}

static int sm_queue_restore(int game, int pick_index, int slot) {
    int k = SM_QUEUE_BASE - pick_index;
    if (pick_index > SM_QUEUE_BASE || sm_describe(game, k) < 0 || slot != sm_slot_of(game, k)) {
        return 0;
    }
    pick_slot = slot;
    pick_game = game;
    pick_event = &sm_event;
    pick_tick = STORY_TICK();           /* its ten minutes start again */
    pick_village = story_village_now(game);
    pick_more = k;
    pick_natural = 0;
    return 1;
}
