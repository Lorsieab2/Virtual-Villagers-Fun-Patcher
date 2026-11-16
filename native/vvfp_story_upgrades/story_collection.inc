/* Isola Grand Event Collection: when the new island events come.  Included by vvfp_story_upgrades.c after
   story_graph.inc.

   THE OWNER'S RULE (2026-11-15, replacing the separate rare roll between natural events): at each NATURAL island event
   the game is about to deliver, a chance rolled at random in 30..50 percent each time; on a pass one of the new
   events comes INSTEAD -- More Island Events'
   (native/vvfp_more_island_events, its "due" paths: mie_pick.inc) and the collection's (the .cieg files and the
   Living Event Engine's pack the patcher puts in "<game folder>\Virtual Villagers Fun Patcher Files\Island Event
   Collection", with manifest.txt) -- and the game's own event does not happen that time.  When no new event can be
   cast, the game's own event comes as always.  NEVER replaced: the village's two opening events (CE_OPENING_EVENTS),
   a rescue event (the trouble guard below holds the game's own rescue rule), and nothing while the village is in
   trouble.  THE POPULATION GATE: an event that can kill a villager, make one disappear or lose a pregnancy (a kill,
   vanish, die_unrecovered, birth_then_die or baby_lost effect anywhere in it; More Island Events' by SC_MORE_DEADLY)
   is drawn only when the village has 61 or more villagers (SC_MIN_POPULATION: the living villagers the game lists,
   with the babies being carried, as the game's own rescue rule counts its population; New Believers' believers only);
   every other new event at any population, when its own requirements hold.  No Safeguards for Island Events (and Additional Events too)
   (island_events_any_time, "for masochists") lifts the gate, the opening-event and rescue rules, the trouble guard and
   the protected villagers (story_graph.inc cg_ns_cast); only the villagers each event needs remain.  Pick Island Event and Custom Island
   Events (player-chosen) ignore the gate and the chance.  The draw's weights are unchanged.

   WHEN.  Every frame (VvfpStoryInstall) the game's clock and its island timer (the second its next island event is
   due) are read.  Once, for each natural time, when it is SC_WINDOW seconds away or less and nothing else is armed or
   on its way (no Pick Island Event or Custom Island Event, no bought island event, no branching event running), and
   in New Believers no God Power is armed (the trigger's own rule): the opening events are past, the village is not
   in trouble, and the game's own random routine rolls a chance in 30..50 percent and then passes it -- then the draw
   below arms a new event (below 61 villagers, without the deadly ones).  Its arm makes the island event due as a purchase does (now + 5 seconds; New Believers 0), and
   the island timer's keeper (native/shared/island_timer_keep.h) keeps the natural time to put back after it.  As
   soon as the keeper has the arm (story_bought_on_its_way), its kept time is set (story_island_arming again, a second
   write: sc_replace_pending) to a NEW natural time after this one, drawn as the game's own trigger draws it (A New
   Home 12-23 hours later, The Lost Children 10-19, the later three 8-15: SC_NEXT_HOURS, with the game's own random
   routine) -- so the new event takes the natural event's place and the schedule goes on from it, as after the
   game's own event.  The delivery counts as one island event.

   THE TROUBLE GUARD (unchanged): the stock rescue predicate, applied in all five games ((men > women and women <= 2)
   or (men <= women and men <= 2) or the population with the babies being carried below 3; living villagers of every
   age, New Believers' believers only), food stored below 10 per villager or none, at least half the villagers sick,
   or fewer than 6 villagers of 14 or more.  A rescue can only come at a natural trigger, and that trigger is never
   replaced while the rescue predicate holds.

   MANY SMALL FILES (the owner, 2026-11-15: "an unlimited amount of files, the game picks randomly from one of them
   every time it chooses an island event"): the collection's events are listed in many small manifests,
   "Island Event Collection\manifest-<group>.txt" (the same line format; a living group's variants in
   "living-<group>.pak" beside it); an older install's single "manifest.txt" (with "living.pak") is read only when no
   split file exists.  A small index (sc_index: each file's name and draw weight -- its events' weights, a series
   counting once) is all that is kept of them; the draw loads one file at a time.

   CHOICE.  The candidates are More Island Events' entries that can happen now (when that row is installed) and the
   collection's files for this game (when its row is installed) whose STRICT cast and requirement hold now.  The draw
   picks among More Island Events' events (weight 1 each) and the files (each by its weight); a file picked is loaded
   and drawn in (sc_draw_group); when nothing in it can happen now, another file not tried yet is picked, as many as
   needed, until an event is armed or every file has been tried (then the game's own event comes).  EVERY EVENT IS EQUALLY LIKELY, whichever source it comes from (the owner, 2026-11-14): one draw over all
   of them, each More Island Events event weight 1, each collection event its draw weight (manifest, default 1), and a
   series (the V14, V17, V18 and V20 series, the Living Catalogue's templates) counts as ONE event, its members
   equally likely (collection_decisions.md Q7).  A candidate that cannot be cast is left out and the draw made again
   among the rest.  A More Island Events event is armed as Pick Island Event arms it (sm_arm), with no message and no
   charge, and marked natural (no "could not happen" notice is ever kept for it); a collection event is queued by the
   branching engine (cg_queue_origin, CG_ORIGIN_NATURAL, CG_CAST_STRICT). */

#define SC_ROW "isola_grand_event_collection"           /* the row's short id (cg_installed_has) */
#define SC_FOLDER "Island Event Collection"
#define SC_MAX STORY_TABLE_LIMIT                          /* collection entries of one game: a sanity limit (the
                                                            tables are allocated to the manifest's rows) */
#define SC_WINDOW 3                                      /* seconds before a natural event: the decision */
#define SC_REPLACE_PERCENT_MIN 30                        /* a natural event replaced by a new one: a chance */
#define SC_REPLACE_PERCENT_SPAN 21                       /* ... rolled in 30..50 percent each time */
#define SC_MIN_POPULATION 61                             /* deadly new events only from this population on */
#define SC_MIN_GROWN 6                                   /* villagers of 14 or more */
/* The game's own spacing of its natural island events, in hours (its trigger's write; island_timer_keep.h): the
   next natural time after a replaced one is drawn the same way. */
static const int SC_NEXT_HOURS[6][2] = { { 0, 0 }, { 12, 23 }, { 10, 19 }, { 8, 15 }, { 8, 15 }, { 8, 15 } };
#define SC_MANIFEST_BYTES 0x04000000u                     /* 64 MB: a sanity limit; read to its real size */

enum { SC_NONE = 0, SC_ARM = 3 };

typedef struct {
    int seen;                          /* the Island Events Seen count last read, -1 unknown */
    int decided;                       /* the natural time below was decided (rolled, or passed over) */
    unsigned int decided_for;          /* that natural time */
} sc_state;

typedef struct {
    int game;
    int counter;                       /* -1: no village (or a trigger this companion does not know) */
    int busy;
    unsigned int now;
    unsigned int natural;              /* the island timer now */
    int god_power;                     /* New Believers: a God Power armed */
    int population;                    /* forced population for the test build's draw (-1: the village's own) */
    int any_time;                      /* No Safeguards for Island Events (and Additional Events too) installed: no opening-event, rescue or trouble rule */
} sc_input;

typedef struct {
    char id[64];
    char title[CE_TITLE_BYTES + 32];
    char series[48];
    char description[160];             /* the Pick Island Event list's sentence ("" = none: the generic line) */
    int weight;
} sc_entry;

static sc_state sc;
static int sc_game;

/* The collection's small manifests (sc_index): each file's group name ("" for an older install's single
   "manifest.txt") and its draw weight. */
#define SC_GROUP_BYTES 32
#define SC_GROUP_FILE_MAX 0x00100000u      /* a group's manifest: 1 MB (a sanity limit; past it the file is skipped) */
#define SC_GROUP_ROWS_MAX 4096
typedef struct {
    char name[SC_GROUP_BYTES];
    int weight;
} sc_group;
static sc_group *sc_groups;
static int sc_group_count, sc_group_cap;
static int sc_cur_group = -1;                    /* the group sc_list holds */
static char lv_want_group[SC_GROUP_BYTES];       /* story_living.inc: the pack the loaded group's living rows use */
/* Pick Island Event's rows: each list row's group and its row in that group's manifest (sc_pick_fill). */
static int *sc_ref_group, *sc_ref_row;
static int sc_ref_count, sc_ref_cap;
static unsigned int sc_replace_natural;  /* the natural time a new event is taking the place of */
static story_village sc_village;

static sc_entry *sc_list;              /* sc_cap entries (sc_reserve), sc_count of them used */
static int sc_count, sc_cap;
static short *lv_entry_seed;           /* story_living.inc: each sc_list entry's pack seed, -1 when not a living row */
static unsigned char *sc_left;         /* the draw's working arrays (sc_choose_and_arm), one per entry */
static short *sc_head, *sc_members_left;

/* The entry tables grown to `need` entries (together); 1 when they hold them. */
static int sc_reserve(int need) {
    int cap = sc_cap, c1 = sc_cap, c2 = sc_cap, c3 = sc_cap, c4 = sc_cap;
    if (need <= sc_cap) {
        return 1;
    }
    if (!story_grow((void **)&sc_list, &cap, need, sizeof(sc_entry))
        || !story_grow((void **)&lv_entry_seed, &c1, need, sizeof(short))
        || !story_grow((void **)&sc_left, &c2, need, 1)
        || !story_grow((void **)&sc_head, &c3, need, sizeof(short))
        || !story_grow((void **)&sc_members_left, &c4, need, sizeof(short))) {
        return 0;
    }
    sc_cap = cap;
    return 1;
}

/* A problem the player should be able to find (a manifest past its sanity limit, a table that could not grow): one
   line, once per session each, appended to "Virtual Villagers Fun Patcher Files\Island Event Collection\
   Problems.txt" beside the collection (never the save). */
static void sc_problem(const char *line) {
    static char said[8][160];
    static int said_count;
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    HANDLE h;
    DWORD wrote = 0;
    int k;
    for (k = 0; k < said_count; ++k) {
        if (lstrcmpA(said[k], line) == 0) {
            return;
        }
    }
    if (said_count < 8) {
        lstrcpynA(said[said_count++], line, (int)sizeof said[0]);
    }
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, SC_FOLDER "\\Problems.txt") == 0) {
        return;
    }
    h = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return;
    }
    WriteFile(h, line, (DWORD)lstrlenA(line), &wrote, NULL);
    WriteFile(h, "\r\n", 2, &wrote, NULL);
    CloseHandle(h);
}

#ifdef VVFP_TEST
static int sc_test_trouble = -1;       /* -1: the village's own; else forced */
static const char *sc_test_manifest;   /* the manifest text instead of the file */
static unsigned int sc_test_more_ok;   /* bit k: More Island Events' entry k arms */
static unsigned int sc_test_coll_ok;   /* bit i: collection entry i arms */
static int sc_test_trace[64];          /* each arm tried: source << 16 | index */
static int sc_test_traced;
static int sc_test_population = -1;    /* -1: the village's own; else forced */
static const unsigned char *sc_test_cieg;   /* every entry's compiled file instead of the folder's */
static unsigned int sc_test_cieg_size;
#endif

/* ---- The game's own rand, clock and island timer ------------------------------------------------------------ */

static int sc_rand(int game, int n) {
    const ce_adapter *a = ce_adapter_for(game);
    return a != NULL ? ce_random_below(a, n) : 0;
}

/* The game's clock now and its island timer (the second its next island event is due).  0 without a village. */
static int sc_clock(int game, unsigned int *now, unsigned int **timer) {
    unsigned char *world;
    switch (game) {
    case 1:
        world = *(unsigned char **)(uintptr_t)VV1_WORLD_GLOBAL;
        if (world == NULL) {
            return 0;
        }
        *timer = (unsigned int *)(world + VV1_COUNTDOWN);
        *now = (unsigned int)((clock_fn)(uintptr_t)VV1_CLOCK)(world, NULL);
        return 1;
    case 2:
        world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
        if (world == NULL) {
            return 0;
        }
        *timer = (unsigned int *)(world + VV2_COUNTDOWN);
        *now = (unsigned int)((clock_fn)(uintptr_t)VV2_CLOCK)(world, NULL);
        return 1;
    case 3:
        world = c3_world();             /* manager+0x12EF4, on the game's clock 0x403330 */
        if (world == NULL) {
            return 0;
        }
        *timer = (unsigned int *)(world + 0x12EF4u);
        *now = (unsigned int)TC0(0x403330u, world);
        return 1;
    case 4:
        world = *(unsigned char **)(uintptr_t)VV4_WORLD_GLOBAL;
        if (world == NULL) {
            return 0;
        }
        *timer = (unsigned int *)(world + VV4_COUNTDOWN);
        *now = (unsigned int)((clock_fn)(uintptr_t)VV4_CLOCK)(world, NULL);
        return 1;
    case 5: {
        void *clock_owner = ((getter_fn)(uintptr_t)0x425950u)();   /* the clock 0x4036E0's object (story_c5.inc) */
        world = *(unsigned char **)(uintptr_t)VV5_WORLD_GLOBAL;
        if (world == NULL || clock_owner == NULL) {
            return 0;
        }
        *timer = (unsigned int *)(world + VV5_COUNTDOWN);
        *now = (unsigned int)TC0(0x4036E0u, clock_owner);
        return 1;
    }
    default:
        return 0;
    }
}

/* Anything armed or on its way, or a branching event running: the island event that comes next is not the game's
   own. */
static int sc_busy(int game) {
    if (pick_slot >= 0 || ce_armed || story_bought_on_its_way(game) || (cg.phase != CG_IDLE && cg.phase != CG_DONE)) {
        return 1;
    }
    if (game == 3 && *(volatile unsigned char *)(uintptr_t)VV3_ISLAND_FLAG != 0) {
        return 1;
    }
    return game == 5 && (read_u32(VV5_PURCHASE_FLAGS) & 0x3Cu) != 0;
}

/* ---- The trouble guard -------------------------------------------------------------------------------------- */

/* Whether `r` is sick, as each game's own sickness writes it (story_c1.inc .. story_c5.inc). */
static int sc_sick(int game, const unsigned char *r) {
    switch (game) {
    case 1: return *(const int *)(r + 0x354) != 0;
    case 2: return *(const int *)(r + 0x53C) != 0;
    case 3: return r[0xE89] != 0;
    default: return r[0x1C48] != 0;
    }
}

/* 1 when the village is in trouble (no natural event is replaced). */
static int sc_trouble(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    int i, men = 0, women = 0, people = 0, carried = 0, sick = 0, grown = 0, food;
#ifdef VVFP_TEST
    if (sc_test_trouble >= 0) {
        return sc_test_trouble;
    }
#endif
    if (a == NULL) {
        return 1;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        int sex;
        if (r == NULL || !a->listed(r) || (game == 5 && cg_heathen(game, r))) {
            continue;
        }
        ++people;
        sex = ce_sex(a, r);
        men += sex == STORY_SEX_MALE;
        women += sex == STORY_SEX_FEMALE;
        carried += *(const int *)(r + a->off_pregnant) != 0;
        sick += sc_sick(game, r);
        grown += ce_age(a, r) >= 14 * 20;
    }
    food = a->food != NULL ? a->food() : 0;
    return (men > women && women <= 2) || (men <= women && men <= 2) || people + carried < 3
        || food <= 0 || food < 10 * people || 2 * sick >= people || grown < SC_MIN_GROWN;
}

/* The village's population as the game's own rescue rule counts it: the living villagers the game lists and the
   babies being carried (New Believers' believers only).  -1 without a village. */
static int sc_population(int game) {
    const ce_adapter *a = ce_adapter_for(game);
    int i, people = 0;
#ifdef VVFP_TEST
    if (sc_test_population >= 0) {
        return sc_test_population;
    }
#endif
    if (a == NULL) {
        return -1;
    }
    for (i = 0; i < a->record_count && i < CE_MAX_RECORDS; ++i) {
        const unsigned char *r = a->record(i);
        if (r == NULL || !a->listed(r) || (game == 5 && cg_heathen(game, r))) {
            continue;
        }
        people += 1 + (*(const int *)(r + a->off_pregnant) != 0);
    }
    return people;
}

/* The population the gate and the food and tech sizes count, for "VVFP More Island Events.dll" (its rewards). */
__declspec(dllexport) int __stdcall VvfpStoryNewEventPopulation(int game) {
    return game >= 1 && game <= 5 ? sc_population(game) : -1;
}

/* ---- The decision (no game data here: sc_tick reads the game and makes the changes) ------------------------- */

static int sc_step(sc_state *s, const sc_input *in) {
    int left, chance;
    if (in->counter < 0) {
        s->seen = -1;
        s->decided = 0;
        return SC_NONE;
    }
    s->seen = in->counter;
    left = (int)(in->natural - in->now);
    if (in->busy || in->god_power || left < 0 || left > SC_WINDOW
        || (s->decided && s->decided_for == in->natural)) {
        return SC_NONE;                /* not the moment, or this natural event was decided already */
    }
    s->decided = 1;
    s->decided_for = in->natural;
    if (!in->any_time && in->counter < CE_OPENING_EVENTS) {
        return SC_NONE;                /* the village's two opening events are never replaced */
    }
    if (!in->any_time && sc_trouble(in->game)) {
        return SC_NONE;                /* in trouble: a rescue is never replaced */
    }
    chance = SC_REPLACE_PERCENT_MIN + sc_rand(in->game, SC_REPLACE_PERCENT_SPAN);   /* 30..50, each time */
    return sc_rand(in->game, 100) < chance ? SC_ARM : SC_NONE;
}

/* ---- The content filters (src/vv_event_content.py) ---------------------------------------------------------- */

/* The island events' content filters ticked in `game` (island_event_filter_f01 .. f28 in the installed patches'
   list): bit n-1 for Fnn.  The collection's events carry their own (each compiled event's conditions and
   requirement); More Island Events' events are kept out whole by the table below. */
static unsigned int sc_filters_on(int game) {
    unsigned int on = 0;
    int n;
    char id[32];
    cg_installed_load();
    if (cg_installed_state != 1) {
        return 0;
    }
    for (n = 1; n <= 28; ++n) {
        wsprintfA(id, "island_event_filter_f%02d", n);
        if (cg_installed_has(game, id)) {
            on |= 1u << (n - 1);
        }
    }
    return on;
}

#define SC_F(n) (1u << ((n) - 1))
/* More Island Events' entries in its registry's order (native/vvfp_more_island_events/mie_pick.inc MIE_PICKS) and
   the content filters each one's outcomes touch: The Aspiring Adventurer (a death, a disappearance), The Cave
   Explorers (a death, the eerie cave), The Climb, The Troubling Signs (a death, a disaster, animals), Diving for
   Treasure (a death, deep water), The Playful Dolphins (deep water), The Mysterious Mask, The Remembrance Ceremony
   (twice: grief), The Rumblings (a disaster). */
/* ...and those that can kill a villager, make one disappear or lose a pregnancy (the population gate): The Aspiring
   Adventurer, The Cave Explorers, The Climb, The Troubling Signs, Diving for Treasure. */
static const unsigned char SC_MORE_DEADLY[] = { 1, 1, 1, 1, 1, 0, 0, 0, 0, 0 };

static const unsigned int SC_MORE_FILTERS[] = {
    SC_F(3) | SC_F(4) | SC_F(5), SC_F(3) | SC_F(5) | SC_F(13), 0, SC_F(3) | SC_F(21) | SC_F(24),
    SC_F(3) | SC_F(5) | SC_F(22), SC_F(22), 0, SC_F(5), SC_F(5), SC_F(21),
};

/* Whether a ticked content filter keeps More Island Events' entry `k` out (before the draw, and in Pick Island
   Event's list). */
static int sc_more_filtered(int game, int k) {
    if (k < 0 || k >= (int)(sizeof SC_MORE_FILTERS / sizeof SC_MORE_FILTERS[0]) || SC_MORE_FILTERS[k] == 0) {
        return 0;
    }
    return (sc_filters_on(game) & SC_MORE_FILTERS[k]) != 0;
}

/* ---- The candidates ------------------------------------------------------------------------------------------ */

static int sc_more_on(int game) {
    return sm_installed(game);
}

static int sc_collection_on(int game) {
#ifdef VVFP_TEST
    if (sc_test_manifest != NULL) {
        return 1;
    }
#endif
    cg_installed_load();
    return cg_installed_state == 1 && cg_installed_has(game, SC_ROW);
}

/* The collection folder's file `leaf` (wide). */
static DWORD sc_path(wchar_t *out, const char *leaf) {
    char inner[MAX_PATH];
    if (lstrlenA(leaf) + lstrlenA(SC_FOLDER) + 2 >= MAX_PATH) {
        return 0;
    }
    wsprintfA(inner, SC_FOLDER "\\%s", leaf);
    return vvfp_patcher_file_path_w(out, VVFP_PATCHER_FILES_PATH_CAP, inner);
}

static int sc_read_w(const wchar_t *path, unsigned char *buf, unsigned int cap, unsigned int *size) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0, high = 0, length;
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    length = GetFileSize(h, &high);
    ok = high == 0 && length != INVALID_FILE_SIZE && length <= cap && ReadFile(h, buf, length, &got, NULL)
         && got == length;
    CloseHandle(h);
    *size = got;
    return ok;
}

static unsigned char *sc_manifest;     /* the manifest, read to its real size (sc_read_manifest) */
static unsigned int sc_manifest_cap;

/* The manifest at `path` read whole into sc_manifest (allocated to its size, NUL-ended); past SC_MANIFEST_BYTES
   only that much is read, cut at its last whole line, and the problem logged (sc_problem): the rows after it are
   left out loudly, never silently.  1 when something was read. */
static int sc_read_manifest(const wchar_t *path, unsigned int *size, unsigned int limit) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD high = 0, length, got = 0;
    unsigned int want;
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    length = GetFileSize(h, &high);
    if (length == INVALID_FILE_SIZE) {
        CloseHandle(h);
        return 0;
    }
    if ((high != 0 || length > limit) && limit < SC_MANIFEST_BYTES) {
        CloseHandle(h);
        sc_problem("A collection manifest is larger than its 1 MB limit: it was skipped.");
        return 0;
    }
    want = high != 0 || length > limit ? limit : length;
    if (want + 1u > sc_manifest_cap) {
        unsigned char *grown = sc_manifest == NULL
            ? (unsigned char *)HeapAlloc(GetProcessHeap(), 0, want + 1u)
            : (unsigned char *)HeapReAlloc(GetProcessHeap(), 0, sc_manifest, want + 1u);
        if (grown == NULL) {
            CloseHandle(h);
            sc_problem("manifest.txt could not be read: not enough memory. No collection event can come.");
            return 0;
        }
        sc_manifest = grown;
        sc_manifest_cap = want + 1u;
    }
    if (!ReadFile(h, sc_manifest, want, &got, NULL) || got != want) {
        CloseHandle(h);
        return 0;
    }
    CloseHandle(h);
    if (want < length || high != 0) {
        while (got > 0 && sc_manifest[got - 1] != '\n') {
            --got;                     /* the last whole line */
        }
        sc_problem("manifest.txt is larger than its 64 MB limit: the events after that point were left out.");
    }
    sc_manifest[got] = '\0';
    *size = got;
    return 1;
}
static unsigned char sc_bytes[CG_MAX_FILE];

/* Field `n` (0-based, tab-separated) of the line [p, end) into `out`. */
static void sc_field(const char *p, const char *end, int n, char *out, int cap) {
    int k = 0, o = 0;
    for (; p < end && k < n; ++p) {
        k += *p == '\t';
    }
    for (; p < end && *p != '\t' && o + 1 < cap; ++p) {
        out[o++] = *p;
    }
    out[o] = '\0';
}

/* Whether the games field ("3" or "1,2,3,4,5") names `game`. */
static int sc_games_has(const char *games, int game) {
    for (; *games != '\0'; ++games) {
        if (*games == (char)('0' + game) && (games[1] == '\0' || games[1] == ',')) {
            return 1;
        }
    }
    return 0;
}

/* Field `n` of the line [p, end) as sc_field reads it, without a line's last '\r'. */
static void sc_field_end(const char *p, const char *end, int n, char *out, int cap) {
    int len;
    sc_field(p, end, n, out, cap);
    len = lstrlenA(out);
    if (len > 0 && out[len - 1] == '\r') {
        out[len - 1] = '\0';
    }
}

/* The collection's events for `game` from manifest.txt: "id<TAB>title<TAB>games<TAB>weight<TAB>series<TAB>credit
   <TAB>description<TAB>Guardians title<TAB>Guardians description", one line each ('#' a comment), each with its
   "<id>.cieg" beside it.  The last two (New Believers only; empty = the same) are the event's title and sentence
   with Guardians of Isola's rewrite on: its title variant's (cie-v6-binary.md 18), as the event shows it.  The
   count. */
static int sc_scan_group(int game, int g) {
    const char *text = NULL, *p, *end;
    unsigned int size = 0;
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    sc_count = 0;
    sc_cur_group = -1;
    if (g < 0 || g >= sc_group_count) {
        return 0;
    }
    lstrcpynA(lv_want_group, sc_groups[g].name, SC_GROUP_BYTES);
#ifdef VVFP_TEST
    if (sc_test_manifest != NULL) {
        text = sc_test_manifest;
        size = (unsigned int)lstrlenA(text);
    }
#endif
    if (text == NULL) {
        char leaf[SC_GROUP_BYTES + 16];
        if (sc_groups[g].name[0] != '\0') {
            wsprintfA(leaf, "manifest-%s.txt", sc_groups[g].name);
        } else {
            lstrcpyA(leaf, "manifest.txt");
        }
        if (!sc_collection_on(game) || sc_path(path, leaf) == 0
            || !sc_read_manifest(path, &size, sc_groups[g].name[0] != '\0' ? SC_GROUP_FILE_MAX : SC_MANIFEST_BYTES)) {
            return 0;
        }
        text = (const char *)sc_manifest;
    }
    sc_cur_group = g;
    {
        /* The tables to the manifest's lines (a sanity limit of SC_MAX entries, the rest left out loudly). */
        int lines = 1;
        for (p = text; *p != '\0'; ++p) {
            lines += *p == '\n';
        }
        if (lines > SC_MAX || (sc_groups[g].name[0] != '\0' && lines > SC_GROUP_ROWS_MAX + 2)) {
            sc_problem("A collection manifest has more events than its limit: the rest were left out.");
            lines = sc_groups[g].name[0] != '\0' ? SC_GROUP_ROWS_MAX + 2 : SC_MAX;
        }
        if (!sc_reserve(lines)) {
            sc_problem("The collection's list could not be made: not enough memory. Some events were left out.");
        }
    }
    for (p = text; *p != '\0' && sc_count < sc_cap; p = *end != '\0' ? end + 1 : end) {
        char games[32], weight[16];
        sc_entry *e = &sc_list[sc_count];
        for (end = p; *end != '\0' && *end != '\n'; ++end) {
        }
        if (*p == '#' || end - p < 3) {
            continue;
        }
        sc_field(p, end, 0, e->id, sizeof e->id);
        sc_field(p, end, 1, e->title, sizeof e->title);
        sc_field(p, end, 2, games, sizeof games);
        sc_field(p, end, 3, weight, sizeof weight);
        sc_field_end(p, end, 4, e->series, sizeof e->series);
        sc_field_end(p, end, 6, e->description, sizeof e->description);
        if (game == 5 && cg_guardians_on()) {
            char alt[sizeof e->description];   /* the longer of the two: a sentence */
            sc_field_end(p, end, 7, alt, sizeof alt);
            if (alt[0] != '\0') {
                lstrcpynA(e->title, alt, sizeof e->title);
            }
            sc_field_end(p, end, 8, alt, sizeof alt);
            if (alt[0] != '\0') {
                lstrcpynA(e->description, alt, sizeof e->description);
            }
        }
        if (e->id[0] == '\0' || !sc_games_has(games, game)) {
            continue;
        }
        e->weight = 0;
        {
            const char *w;
            for (w = weight; *w >= '0' && *w <= '9'; ++w) {
                e->weight = e->weight * 10 + (*w - '0');
            }
        }
        if (e->weight <= 0) {
            e->weight = 1;
        }
        ++sc_count;
    }
    return sc_count;
}

/* The draw weight of the group sc_list holds: its events' weights, each series once. */
static int sc_list_weight(void) {
    int i, k, w = 0;
    for (i = 0; i < sc_count; ++i) {
        if (sc_list[i].series[0] == '\0') {
            w += sc_list[i].weight;
            continue;
        }
        for (k = 0; k < i && lstrcmpA(sc_list[k].series, sc_list[i].series) != 0; ++k) {
        }
        w += k == i;                   /* the series' first member counts it once */
    }
    return w;
}

static int sc_add_group(const char *name) {
    sc_group *row;
    if (!story_grow((void **)&sc_groups, &sc_group_cap, sc_group_count + 1, sizeof(sc_group))) {
        sc_problem("The collection's index could not grow: not enough memory. Some files were left out.");
        return 0;
    }
    row = &sc_groups[sc_group_count++];
    lstrcpynA(row->name, name, SC_GROUP_BYTES);
    row->weight = 0;
    return 1;
}

/* The collection's index for `game`: every "manifest-<group>.txt" (a name of [a-z0-9_], at most 24 characters), or
   -- none -- an older install's "manifest.txt" as the group "", each with its draw weight (the file read once, its
   rows forgotten).  The count of groups. */
static int sc_index(int game) {
    int g;
    sc_group_count = 0;
    sc_cur_group = -1;
    if (!sc_collection_on(game)) {
        return 0;
    }
#ifdef VVFP_TEST
    if (sc_test_manifest != NULL) {
        (void)sc_add_group("");
        goto weigh;
    }
#endif
    {
        wchar_t pattern[VVFP_PATCHER_FILES_PATH_CAP];
        WIN32_FIND_DATAW found;
        HANDLE find;
        if (sc_path(pattern, "manifest-*.txt") != 0
            && (find = FindFirstFileW(pattern, &found)) != INVALID_HANDLE_VALUE) {
            do {
                char name[SC_GROUP_BYTES];
                int n = 0, ok = 1, k;
                const wchar_t *w = found.cFileName + 9;          /* past "manifest-" */
                for (k = 0; w[k] != L'\0' && !(w[k] == L'.' && lstrcmpiW(w + k, L".txt") == 0); ++k) {
                    wchar_t c = w[k];
                    if (n + 1 >= 25 || !((c >= L'a' && c <= L'z') || (c >= L'0' && c <= L'9') || c == L'_')) {
                        ok = 0;
                        break;
                    }
                    name[n++] = (char)c;
                }
                name[n] = '\0';
                if (!ok || n == 0 || (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                    sc_problem("A collection manifest's name is not manifest-<letters, digits or _>.txt: skipped.");
                    continue;
                }
                if (!sc_add_group(name)) {
                    break;
                }
            } while (FindNextFileW(find, &found));
            FindClose(find);
        }
        if (sc_group_count == 0) {
            wchar_t legacy[VVFP_PATCHER_FILES_PATH_CAP];
            if (sc_path(legacy, "manifest.txt") != 0 && GetFileAttributesW(legacy) != INVALID_FILE_ATTRIBUTES) {
                (void)sc_add_group("");          /* an older install: its single manifest */
            }
        }
    }
#ifdef VVFP_TEST
weigh:
#endif
    for (g = 0; g < sc_group_count; ++g) {
        sc_groups[g].weight = sc_scan_group(game, g) > 0 ? sc_list_weight() : 0;
    }
    sc_count = 0;
    sc_cur_group = -1;
    return sc_group_count;
}

/* Entry `i`'s compiled event into sc_bytes; 0 when it cannot be read. */
static int sc_load_entry(int i, unsigned int *size) {
    char leaf[80];
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
#ifdef VVFP_TEST
    if (sc_test_cieg != NULL && sc_test_cieg_size <= sizeof sc_bytes) {
        memcpy(sc_bytes, sc_test_cieg, sc_test_cieg_size);
        *size = sc_test_cieg_size;
        return 1;
    }
#endif
    wsprintfA(leaf, "%s.cieg", sc_list[i].id);
    return sc_path(path, leaf) != 0 && sc_read_w(path, sc_bytes, sizeof sc_bytes, size);
}

/* More Island Events' entry `k`, armed as Pick Island Event arms it, without a message or a charge. */
static int sc_arm_more(int game, int k) {
#ifdef VVFP_TEST
    if (sc_test_traced < 64) {
        sc_test_trace[sc_test_traced++] = k;
    }
    if (!(sc_test_more_ok & (1u << (k & 31)))) {
        return 0;
    }
#endif
    if (sm_describe(game, k) != 1 || !sm_arm(game, k)) {
        return 0;
    }
    pick_natural = 1;                  /* never a "could not happen" notice for the player */
    return 1;
}

/* Collection entry `i`, queued by the branching engine as a natural island event (strict cast). */
/* The draw at a natural event leaves out the deadly events (sc_gate: the village below SC_MIN_POPULATION; set only
   while that draw runs). */
static int sc_gate;

/* No Safeguards for Island Events (and Additional Events too) (island_events_any_time in the installed patches' list; the owner, 2026-11-15, "for
   masochists"): for the new events no 61-villager gate, rescue events and the two opening events may be replaced, no
   trouble guard -- only the villagers each event needs.  The game's own
   events' conditions are another companion's. */
static int sc_any_time(int game) {
    return cg_no_safeguards(game);
}

static int sc_drawing;                 /* the natural draw is running (More Island Events' possible checks) */

/* No Safeguards for "VVFP More Island Events.dll" (its own pickers and gates): installed, and its event is the
   natural draw's -- while that draw runs, or armed by it (pick_natural) -- never Pick Island Event's. */
__declspec(dllexport) int __stdcall VvfpStoryNoSafeguards(int game) {
    return game >= 1 && game <= 5 && cg_no_safeguards(game)
           && (sc_drawing || (pick_slot >= 0 && pick_game == game && pick_natural));
}

/* Whether the compiled event `data` can kill a villager, make one disappear or lose a pregnancy. */
static int sc_graph_deadly(const unsigned char *data, unsigned int size) {
    static unsigned char copy[CG_MAX_FILE];
    static cg_graph g;
    int k;
    if (size > sizeof copy) {
        return 1;
    }
    memcpy(copy, data, size);
    if (!cg_load(&g, copy, size)) {
        return 1;
    }
    for (k = 0; k < g.n_effect; ++k) {
        unsigned char code = cg_effect_at(&g, k)[0];
        if (code == CGE_KILL || code == CGE_VANISH || code == CGE_DIE_UNRECOVERED || code == CGE_BIRTH_THEN_DIE
            || code == CGE_BABY_LOST) {
            return 1;
        }
    }
    return 0;
}

static int sc_arm_collection(int game, int i) {
    unsigned int size = 0;
#ifdef VVFP_TEST
    if (sc_test_traced < 64) {
        sc_test_trace[sc_test_traced++] = 0x10000 | i;
    }
    if (sc_test_manifest != NULL && !(lv_entry_living(i) && lv_test_has_pack())) {
        return (sc_test_coll_ok & (1u << (i & 31))) != 0;
    }
#endif
    if (lv_entry_living(i)) {
        return lv_arm_entry(game, i, CG_ORIGIN_NATURAL, CG_CAST_STRICT);   /* a Living Event Engine seed */
    }
    return sc_load_entry(i, &size) && !(sc_gate && sc_graph_deadly(sc_bytes, size))
           && cg_queue_origin(game, sc_bytes, size, CG_ORIGIN_NATURAL, CG_CAST_STRICT);
}

/* The draw inside the group sc_scan_group loaded (`n_coll` entries): every event as likely as any other, a series
   one event with its members equally likely, the Living Event Engine's recency and moods; a candidate that cannot be
   armed is left out and the draw made again.  1 when an event was armed. */
static int sc_draw_group(int game, int n_coll) {
    unsigned char *left = sc_left;
    short *head = sc_head;             /* the first entry of the same series (itself when none) */
    short *members_left = sc_members_left;   /* at a series' head: its members still left */
    int i, k;
    for (i = 0; i < n_coll; ++i) {
        left[i] = 1;
        head[i] = (short)i;
        members_left[i] = 0;
        if (sc_list[i].series[0] != '\0') {
            for (k = 0; k < i; ++k) {
                if (head[k] == k && lstrcmpA(sc_list[k].series, sc_list[i].series) == 0) {
                    head[i] = (short)k;
                    break;
                }
            }
        }
        ++members_left[head[i]];
    }
    n_coll -= lv_draw_prepare(game, left);   /* the Living Event Engine's recency and moods (story_living.inc) */
    for (i = 0; i < sc_count; ++i) {
        members_left[i] = 0;                 /* a series counts only the members the living draw left in */
    }
    for (i = 0; i < sc_count; ++i) {
        if (left[i]) {
            ++members_left[head[i]];
        }
    }
    while (n_coll > 0) {
        int total = 0, pick, chosen = -1;
        for (i = 0; i < sc_count; ++i) {
            if (sc_list[i].series[0] != '\0') {
                total += head[i] == i && members_left[i] > 0 ? lv_series_weight(i) : 0;
            } else if (left[i]) {
                total += sc_list[i].weight;
            }
        }
        if (total <= 0) {
            return 0;
        }
        pick = sc_rand(game, total);
        for (i = 0; i < sc_count && chosen < 0; ++i) {
            int w;
            if (sc_list[i].series[0] != '\0') {
                w = head[i] == i && members_left[i] > 0 ? lv_series_weight(i) : 0;
            } else {
                w = left[i] ? sc_list[i].weight : 0;
            }
            if (pick < w) {
                chosen = i;
            }
            pick -= w;
        }
        if (chosen < 0) {
            return 0;
        }
        if (sc_list[chosen].series[0] != '\0') {
            int series_pick = sc_rand(game, members_left[chosen]), m;
            for (m = chosen; m < sc_count; ++m) {
                if (left[m] && head[m] == chosen && series_pick-- == 0) {
                    chosen = m;
                    break;
                }
            }
        }
        if (sc_arm_collection(game, chosen)) {
            return 1;
        }
        left[chosen] = 0;
        --members_left[head[chosen]];
        --n_coll;
    }
    return 0;
}

/* The draw (see the header): 1 when an event was armed.  More Island Events' events (weight 1 each) and the
   collection's files (each by its weight from the index) in one draw, so every event stays as likely as any other;
   a file picked is loaded and drawn in, and when nothing in it can happen now another file not tried yet is picked,
   as many as needed, until one arms an event or every file has been tried. */
static int sc_choose_and_arm(int game) {
    static int *more;
    static int more_cap;
    static unsigned char *tried;
    static int tried_cap;
    int n_more = 0, groups = 0, i, g;
    if (sc_more_on(game)) {
        sm_fill_more(game);
        if (!story_grow((void **)&more, &more_cap, sm_list.count > 0 ? sm_list.count : 1, sizeof(int))) {
            return 0;
        }
        for (i = 0; i < sm_list.count; ++i) {
            int k_more = sm_list.k[i];
            if (sm_list.possible[i] == 1
                && !(sc_gate && k_more >= 0 && k_more < (int)sizeof SC_MORE_DEADLY && SC_MORE_DEADLY[k_more])) {
                more[n_more++] = k_more;
            }
        }
    }
    if (sc_collection_on(game)) {
        groups = sc_index(game);
        if (groups > 0 && !story_grow((void **)&tried, &tried_cap, groups, 1)) {
            groups = 0;
        }
        for (g = 0; g < groups; ++g) {
            tried[g] = sc_groups[g].weight <= 0;
        }
    }
    for (;;) {
        int total = n_more, pick, n;
        for (g = 0; g < groups; ++g) {
            total += tried[g] ? 0 : sc_groups[g].weight;
        }
        if (total <= 0) {
            return 0;
        }
        pick = sc_rand(game, total);
        if (pick < n_more) {
            if (sc_arm_more(game, more[pick])) {
                return 1;
            }
            more[pick] = more[--n_more];
            continue;
        }
        pick -= n_more;
        for (g = 0; g < groups; ++g) {
            if (tried[g]) {
                continue;
            }
            if (pick < sc_groups[g].weight) {
                break;
            }
            pick -= sc_groups[g].weight;
        }
        if (g >= groups) {
            return 0;
        }
        tried[g] = 1;
        n = sc_scan_group(game, g);
        if (n > 0 && sc_draw_group(game, n)) {
            return 1;
        }
    }
}

/* ---- Every frame --------------------------------------------------------------------------------------------- */

static void sc_apply(int game, int act) {
    if (act == SC_ARM) {
        /* The natural event is about to come: one of the new events is armed in its place, without telling the
           island timer's keeper (the game then writes the next natural time itself, as after its own event). */
        sc_replace_pending = game;
        sc_replace_natural = sc.decided_for;
        /* Below 61 villagers no deadly event is in the draw -- unless No Safeguards for Island Events (and Additional Events too) is installed. */
        sc_gate = !sc_any_time(game) && sc_population(game) < SC_MIN_POPULATION;
        sc_drawing = 1;
        if (!sc_choose_and_arm(game)) {
            sc_replace_pending = 0;    /* nothing that can happen now: the game's own event comes */
        }
        sc_gate = 0;                   /* Pick Island Event and the library never see the gate */
        sc_drawing = 0;
    }
}

static void sc_tick(int game) {
    sc_input in;
    unsigned int *timer = NULL;
    const int *counter;
    if (game < 1 || game > 5 || (!sc_more_on(game) && !sc_collection_on(game))) {
        return;
    }
    if (sc_game != game || !story_village_is(game, &sc_village)) {
        memset(&sc, 0, sizeof sc);
        sc.seen = -1;
        sc_game = game;
        sc_village = story_village_now(game);
        sc_replace_pending = 0;
    }
    counter = ce_event_counter(game);
    memset(&in, 0, sizeof in);
    in.game = game;
    in.counter = -1;
    in.population = -1;
    if (counter != NULL && sc_clock(game, &in.now, &timer)) {
        in.counter = *counter;
        in.natural = *timer;
    }
    if (sc_replace_pending == game && in.counter >= 0 && in.counter != sc.seen && sc.seen >= 0) {
        sc_replace_pending = 0;        /* an island event came before the keeper had the arm: left as it is */
    }
    if (sc_replace_pending == game && timer != NULL && story_bought_on_its_way(game)) {
        /* The keeper has our arm: the time it puts back after the delivery becomes the next natural time, drawn
           as the game's own trigger draws it (a second write: itk_note keeps natural - value as the distance). */
        unsigned int gap = (unsigned int)(SC_NEXT_HOURS[game][0]
                                          + sc_rand(game, SC_NEXT_HOURS[game][1] - SC_NEXT_HOURS[game][0] + 1))
                           * 3600u + (unsigned int)sc_rand(game, 3600);
        story_island_arming(game, timer, sc_replace_natural - gap);
        sc_replace_pending = 0;
    }
    in.busy = sc_busy(game);
    in.god_power = game == 5 && read_u32(0x51D5A4u) != 0xFFFFFFFFu;
    in.any_time = sc_any_time(game);
    sc_apply(game, sc_step(&sc, &in));
}

/* ---- Pick Island Event: the collection's events in its list (story_more_events.inc) ------------------------ */

/* The event `i` loaded into the engine's graph and checked as the rare roll and Pick Island Event cast it (STRICT):
   NULL when it can happen now, else the reason (in `why`, "Nothing has been queued." left out). */
static const char *sc_check(int game, int i, char *why, int cap) {
    unsigned int size = 0, planned = 0;
    int keep_cast = cg_cast_now, keep_origin = cg_origin_now, n;
    const char *refusal;
    if (cg.phase != CG_IDLE && cg.phase != CG_DONE) {
        lstrcpynA(why, vvfp_tr("vvfp.story/story_collection.sc_check.s0",
                               "another branching island event is still running", 200), cap);
        return why;
    }
    if (lv_is_living(sc_list[i].id)) {
        refusal = lv_check_entry(game, i);   /* possible when any of its variants casts (story_living.inc) */
        if (refusal == NULL) {
            return NULL;
        }
        lstrcpynA(why, refusal, cap);
        n = lstrlenA(why);
        if (n > 25 && lstrcmpA(why + n - 25, " Nothing has been queued.") == 0) {
            why[n - 25] = '\0';
        }
        return why;
    }
    if (!sc_load_entry(i, &size) || !cg_load(&cg_g, sc_bytes, size)) {
        lstrcpynA(why, vvfp_tr("vvfp.story/story_collection.sc_check.s1",
                               "its file can not be read: install the patch again", 200), cap);
        return why;
    }
    cg_cast_now = CG_CAST_STRICT;
    cg_origin_now = CG_ORIGIN_PICK;
    refusal = cg_refusal(game, &planned);
    cg_cast_now = keep_cast;
    cg_origin_now = keep_origin;
    if (refusal == NULL) {
        return NULL;
    }
    lstrcpynA(why, refusal, cap);
    n = lstrlenA(why);
    if (n > 25 && lstrcmpA(why + n - 25, " Nothing has been queued.") == 0) {
        why[n - 25] = '\0';
    }
    return why;
}

/* Appends the collection's events for `game` to the Pick Island Event list (sm_list).  The count added. */
static int sc_pick_fill(int game) {
    int i, added = 0, g, groups;
    if (!sc_collection_on(game) || (groups = sc_index(game)) == 0) {
        return 0;
    }
    sc_ref_count = 0;
    for (g = 0; g < groups; ++g) {
    if (sc_scan_group(game, g) == 0) {
        continue;
    }
    (void)lv_map_entries(game);
    if (!sm_reserve(sm_list.count + sc_count)) {
        sc_problem("The Pick Island Event list could not hold every event: not enough memory.");
    }
    for (i = 0; i < sc_count && sm_list.count < sm_list.cap; ++i) {
        int m = sm_list.count, c1 = sc_ref_cap;
        if (!story_grow((void **)&sc_ref_group, &sc_ref_cap, sc_ref_count + 1, sizeof(int))
            || !story_grow((void **)&sc_ref_row, &c1, sc_ref_count + 1, sizeof(int))) {
            break;
        }
        sc_ref_group[sc_ref_count] = g;
        sc_ref_row[sc_ref_count] = i;
        lstrcpynA(sm_list.title[m], sc_list[i].title, SM_TEXT);
        lstrcpynA(sm_list.description[m], sc_list[i].description[0] != '\0' ? sc_list[i].description
                  : vvfp_tr("vvfp.story/story_collection.sc_pick_fill.s0", "An event of the Isola Grand Event Collection.",
                            200), SM_TEXT);
        sm_list.k[m] = SM_COLL_BASE + sc_ref_count++;   /* the list row: its group and row in sc_ref_* */
        sm_list.possible[m] = sc_check(game, i, sm_list.needs[m], SM_TEXT) == NULL;
        if (sm_list.possible[m]) {
            sm_list.needs[m][0] = '\0';
        }
        ++sm_list.count;
        ++added;
    }
    }
    return added;
}

/* Collection entry `i` bought with Pick Island Event: confirmed, checked again and queued (strict cast, origin
   Pick Island Event).  1 when it is on its way. */
static int sc_pick_buy(int game, HWND owner, int ref) {
    char message[1800], why[SM_TEXT];
    unsigned int size = 0;
    int i;
    /* The list row's group, loaded again, and its row in it. */
    if (ref < 0 || ref >= sc_ref_count || sc_scan_group(game, sc_ref_group[ref]) == 0) {
        return 0;
    }
    (void)lv_map_entries(game);
    i = sc_ref_row[ref];
    if (i < 0 || i >= sc_count) {
        return 0;
    }
    wsprintfA(message,
              vvfp_tr("vvfp.story/vvfp_story_upgrades.story_pick_island_event.s6",
                      "Do you want to buy Pick Island Event (%s) for %s tech points?%s%s\r\n\r\nPress OK to confirm, or Cancel.",
                      400), sc_list[i].title, story_price_text(game), "", "");
    if (vvfp_message_box(owner, message, "Origins Upgrades",
                         MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    if (ce_armed || GAMES[game].island_pending()) {
        MessageBoxA(owner, "That island event can not happen right now. No tech points have been deducted.",
                    "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    if (sc_check(game, i, why, sizeof why) != NULL
        || (lv_entry_living(i) ? !lv_arm_entry(game, i, CG_ORIGIN_PICK, CG_CAST_STRICT)
                               : (!sc_load_entry(i, &size)
                                  || !cg_queue_origin(game, sc_bytes, size, CG_ORIGIN_PICK, CG_CAST_STRICT)))) {
        wsprintfA(message, vvfp_tr("vvfp.story/story_collection.sc_pick_buy.s0",
                                   "%s can not happen right now: %s No tech points have been deducted.", 200),
                  sc_list[i].title, cg_queue_refusal()[0] != '\0' ? cg_queue_refusal() : why);
        vvfp_message_box(owner, message, "Pick Island Event", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    wsprintfA(message, vvfp_tr("vvfp.story/vvfp_story_upgrades.story_pick_island_event.s9", "%s is on its way.", 200),
              sc_list[i].title);
    vvfp_message_box(owner, message, "Origins Upgrades", MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* ---- The in-game library: the "Isola Grand Event Collection" group (story_graph.inc cg_library_scan) -------- */

/* Appends the collection's events for `game` to the library list, each labelled with the group's name.  Bought
   there, an event is cast as every library purchase is (CG_CAST_PREFER: a requirement nobody meets is dropped; the
   protected villagers' safety never). */
static void sc_library_add(int game) {
    int i, g, groups;
    if (!sc_collection_on(game) || (groups = sc_index(game)) == 0) {
        return;
    }
    for (g = 0; g < groups; ++g) {
    if (sc_scan_group(game, g) == 0) {
        continue;
    }
    (void)lv_map_entries(game);
    for (i = 0; i < sc_count && cg_lib_room(); ++i) {
        char leaf[80];
        wchar_t wide[VVFP_PATCHER_FILES_PATH_CAP];
        BOOL lossy = FALSE;
        int n;
        if (lv_is_living(sc_list[i].id)) {
            /* A Living Event Engine seed: its row's sentence tells the seeds of a category apart. */
            if (lv_library_entry(game, i, cg_lib.path[cg_lib.count])) {
                char text[sizeof sc_list[0].title + sizeof sc_list[0].description + 4];
                char full[sizeof text + 120];
                wsprintfA(text, "%s: %s", sc_list[i].title, sc_list[i].description);
                wsprintfA(full, vvfp_tr("vvfp.story/story_collection.sc_library_add.s0",
                                        "Isola Grand Event Collection: %s", 100), text);
                lstrcpynA(cg_lib.label[cg_lib.count], full, sizeof cg_lib.label[0]);
                ++cg_lib.count;
            }
            continue;
        }
        wsprintfA(leaf, "%s.cieg", sc_list[i].id);
        if (sc_path(wide, leaf) == 0) {
            continue;
        }
        n = WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, wide, -1, cg_lib.path[cg_lib.count], MAX_PATH, NULL,
                                &lossy);
        if (n <= 0 || lossy || GetFileAttributesA(cg_lib.path[cg_lib.count]) == INVALID_FILE_ATTRIBUTES) {
            continue;                  /* a folder the ANSI path cannot name: left out of the library only */
        }
        wsprintfA(cg_lib.label[cg_lib.count],
                  vvfp_tr("vvfp.story/story_collection.sc_library_add.s0", "Isola Grand Event Collection: %s", 100),
                  sc_list[i].title);
        ++cg_lib.count;
    }
    }
}

#ifdef VVFP_TEST
/* ---- Test build only ---------------------------------------------------------------------------------------- */

/* The decision on its own: io[0] game, [1] the Island Events Seen count (-1 none), [2] busy, [3] now, [4] the island
   timer, [5] a God Power armed, [6] the trouble guard (-1 the village's own, else forced), [7] the population (-1 the
   village's own), [13] No Safeguards for Island Events (and Additional Events too); out: io[8] the action (SC_*), [9] decided, [10] the natural time decided, [12] the count seen.  The
   action (the 50% roll is the game's own random routine: VvfpStoryProbeSetRolls). */
__declspec(dllexport) int __stdcall VvfpStoryProbeCollectionStep(int *io) {
    sc_input in;
    int act;
    in.game = io[0];
    in.counter = io[1];
    in.busy = io[2];
    in.now = (unsigned int)io[3];
    in.natural = (unsigned int)io[4];
    in.god_power = io[5];
    sc_test_trouble = io[6];
    in.population = io[7];
    in.any_time = io[13];
    sc_test_population = io[7];
    act = sc_step(&sc, &in);
    io[8] = act;
    io[9] = sc.decided;
    io[10] = (int)sc.decided_for;
    io[12] = sc.seen;
    return act;
}

/* A fresh roll: nothing seen, nothing due, no file, no trace. */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionReset(void) {
    memset(&sc, 0, sizeof sc);
    sc.seen = -1;
    sc_game = 0;
    sc_test_trouble = -1;
    sc_test_population = -1;
    sc_test_traced = 0;
    sc_replace_pending = 0;
}

/* The collection as the test gives it: the manifest's text (NULL: the real folder) and which entries arm (bit k of
   `more_ok`: More Island Events' registry entry k; bit i of `coll_ok`: collection entry i). */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionManifest(const char *text, unsigned int more_ok,
                                                                      unsigned int coll_ok) {
    sc_test_manifest = text;
    sc_test_more_ok = more_ok;
    sc_test_coll_ok = coll_ok;
}

/* The draw and the arm: every arm tried, in order, into trace[] (source << 16 | index; at most `cap`).  The count
   tried, plus 0x100 when one was armed. */
__declspec(dllexport) int __stdcall VvfpStoryProbeCollectionChoose(int game, int *trace, int cap) {
    int armed, i;
    sc_test_traced = 0;
    armed = sc_choose_and_arm(game);
    for (i = 0; i < sc_test_traced && i < cap; ++i) {
        trace[i] = sc_test_trace[i];
    }
    return sc_test_traced | (armed ? 0x100 : 0);
}

/* Every collection entry's compiled file is `data` (`size` bytes; NULL: the folder's own). */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionCieg(const unsigned char *data, unsigned int size) {
    sc_test_cieg = data;
    sc_test_cieg_size = size;
}

/* The Pick Island Event list's entry `m` as the chooser fills it (sm_fill): its title, what it needs (empty when
   possible) and the refusal shown when it is chosen anyway; returns its k (SM_COLL_BASE + i for the collection's),
   -1 past the list. */
__declspec(dllexport) int __stdcall VvfpStoryProbeMoreEntry(int game, int m, char *title, char *needs, char *refusal,
                                                            int cap) {
    sm_list.count = 0;
    sm_fill(game);
    if (m < 0 || m >= sm_list.count) {
        return -1;
    }
    lstrcpynA(title, sm_list.title[m], cap);
    lstrcpynA(needs, sm_list.needs[m], cap);
    sm_refusal_of(m, refusal, cap);
    return sm_list.k[m];
}

/* The sentence the list shows for entry `m` of the list VvfpStoryProbeMoreEntry filled last; its length, -1 past it. */
__declspec(dllexport) int __stdcall VvfpStoryProbeMoreDescription(int m, char *out, int cap) {
    if (m < 0 || m >= sm_list.count) {
        return -1;
    }
    lstrcpynA(out, sm_list.description[m], cap);
    return lstrlenA(out);
}

/* The trouble guard of the village in the game's own records. */
__declspec(dllexport) int __stdcall VvfpStoryProbeCollectionTrouble(int game) {
    sc_test_trouble = -1;
    return sc_trouble(game);
}

/* The population the gate counts (-1: the village's own records; else forced for the frame hook). */
__declspec(dllexport) int __stdcall VvfpStoryProbeCollectionPopulation(int game, int force) {
    sc_test_population = -1;
    if (force >= 0) {
        sc_test_population = force;
        return force;
    }
    return sc_population(game);
}

/* One frame of the roll (VvfpStoryInstall's call), with the game's own memory. */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionTick(int game) {
    sc_tick(game);
}

/* The decision's state: out[0] decided, [1] 0, [2] the natural time decided, [3] seen, [4] the armed pick's slot,
   [5] it is natural, [6] the keeper is not to be told of the next arm (the game it is for, 0 none). */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionState(int *out) {
    out[0] = sc.decided;
    out[1] = 0;
    out[2] = (int)sc.decided_for;
    out[3] = sc.seen;
    out[4] = pick_slot;
    out[5] = pick_natural;
    out[6] = sc_replace_pending;
}
#endif
