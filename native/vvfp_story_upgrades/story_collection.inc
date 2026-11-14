/* Isola Grand Event Collection: the separate rare roll.  Included by vvfp_story_upgrades.c after story_graph.inc.

   THE OWNER'S RULES (2026-11-14): the stock island events' chances never change; the new events are rare, but a
   seven-day playthrough sees some; they never replace a rescue event.  So nothing here touches a game's own draw.
   More Island Events' nine events (native/vvfp_more_island_events, only their "due" paths: mie_pick.inc) and the
   collection's events (the .cieg files the patcher puts in "<game folder>\Virtual Villagers Fun Patcher Files\Island
   Event Collection", with manifest.txt) come only through this roll and Pick Island Event.

   WHEN.  Every frame (VvfpStoryInstall) the game's Island Events Seen count (ce_event_counter) is read.  When it went
   up while, in the frame before, nothing was armed or on its way -- no Pick Island Event or Custom Island Event, no
   bought island event (the island timer's keeper, story_bought_on_its_way), no branching event running, nothing of
   this roll's own -- the event the game just delivered was its own NATURAL island event.  On that edge, once the
   village's two opening events are past (CE_OPENING_EVENTS), the game's own random routine rolls once: with
   probability SC_P_PERCENT (A New Home 30%, The Lost Children 25%, the later three 20%: about three in seven days of
   game time in each game) a collection roll is due at now + (natural - now) x U[0.30, 0.70], the natural time being
   the one the game's trigger has just written into its island timer -- so ours always falls between two natural
   events, never on one.  The due time is kept beside the save (sc_store), with the village's roster: used only for
   the same village (a strict majority of its villagers), deleted when delivered or cancelled.  A lost file loses
   one rare event, nothing else.

   AT DUE.  It waits (a frame at a time) while anything else is armed or on its way, while a branching event runs,
   while the game's next natural event is 60 seconds away or less (the natural one goes first), and in New Believers
   while a God Power is armed (the trigger's own rule).  If the next natural event's time passes first, ours is gone.
   THE TROUBLE GUARD cancels it (never delays it) -- and it is asked at the roll too: the stock rescue predicate,
   applied in all five games ((men > women and women <= 2) or (men <= women and men <= 2) or the population with the
   babies being carried below 3; living villagers of every age, New Believers' believers only), food stored below 10
   per villager or none, at least half the villagers sick, or fewer than 6 villagers of 14 or more.  So a rescue,
   which can only come at a natural trigger, is never displaced: natural triggers keep their time (the keeper), and
   we never arm near one or while the rescue predicate holds.

   CHOICE.  The candidates are More Island Events' entries that can happen now (when that row is installed) and the
   collection's files for this game (when its row is installed) whose STRICT cast and requirement hold now.  The two
   sources are 1:1 when both have candidates; within More Island Events each event is equally likely; within the
   collection each event has its draw weight (manifest, default 1), and a series counts as ONE event's weight, its
   members equally likely (collection_decisions.md Q7).  A candidate that cannot be cast is left out and the draw
   made again among the rest.

   ARM.  A More Island Events event is armed as Pick Island Event arms it (sm_arm), with no message and no charge,
   and marked natural (no "could not happen" notice is ever kept for it); a collection event is queued by the
   branching engine (cg_queue_origin, CG_ORIGIN_NATURAL, CG_CAST_STRICT).  Both make the island event due through
   story_island_arming, so the island timer's keeper puts the game's natural next time back after delivery
   (island_timer_keep.h): the delivery counts as one island event (the trigger counts it), the natural schedule is
   untouched. */

#define SC_ROW "isola_grand_event_collection"           /* the row's short id (cg_installed_has) */
#define SC_FOLDER "Island Event Collection"
#define SC_MAX 256                                       /* collection entries of one game */
#define SC_GAP 60u                                       /* seconds kept clear of a natural event */
#define SC_FRAC_MIN 300                                  /* the due point, per mille of the gap: 300..700 */
#define SC_FRAC_SPAN 401
#define SC_MIN_GROWN 6                                   /* villagers of 14 or more */
#define SC_MANIFEST_BYTES 262144
#define SC_MAGIC 0x52435356u                             /* 'V' 'S' 'C' 'R' */
#define SC_VERSION 1u

/* The probability of a roll after each natural island event, percent, by game: the one tunable table. */
static const int SC_P_PERCENT[6] = { 0, 30, 25, 20, 20, 20 };

enum { SC_NONE = 0, SC_SAVE = 1, SC_CANCEL = 2, SC_ARM = 3 };

typedef struct {
    int seen;                          /* the Island Events Seen count last read, -1 unknown */
    int busy_before;                   /* something was armed or on its way in the frame before */
    int due_set;
    unsigned int due;                  /* game-clock seconds */
    unsigned int natural;              /* the game's next natural event when the roll was made */
} sc_state;

typedef struct {
    int game;
    int counter;                       /* -1: no village (or a trigger this companion does not know) */
    int busy;
    unsigned int now;
    unsigned int natural;              /* the island timer now */
    int god_power;                     /* New Believers: a God Power armed */
} sc_input;

typedef struct {
    char id[64];
    char title[CE_TITLE_BYTES + 32];
    char series[48];
    int weight;
} sc_entry;

static sc_state sc;
static int sc_game;
static int sc_checked;                 /* the save's file was looked at for this village */
static story_village sc_village;

static sc_entry sc_list[SC_MAX];
static int sc_count;

#ifdef VVFP_TEST
static int sc_test_trouble = -1;       /* -1: the village's own; else forced */
static const char *sc_test_manifest;   /* the manifest text instead of the file */
static unsigned int sc_test_more_ok;   /* bit k: More Island Events' entry k arms */
static unsigned int sc_test_coll_ok;   /* bit i: collection entry i arms */
static int sc_test_trace[64];          /* each arm tried: source << 16 | index */
static int sc_test_traced;
static int sc_test_have_file;
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

/* 1 when the village is in trouble (the roll is not made, or the due roll is cancelled). */
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

/* ---- The roll (no game data here: sc_tick reads the game and makes the changes) ---------------------------- */

static int sc_step(sc_state *s, const sc_input *in) {
    int edge, act = SC_NONE;
    if (in->counter < 0) {
        s->seen = -1;
        s->busy_before = in->busy;
        return SC_NONE;
    }
    edge = s->seen >= 0 && in->counter > s->seen && !s->busy_before;
    s->seen = in->counter;
    s->busy_before = in->busy;
    if (edge) {
        if (s->due_set) {
            s->due_set = 0;            /* a natural event came first: ours had its place before it */
            act = SC_CANCEL;
        }
        if (in->counter >= CE_OPENING_EVENTS && (int)(in->natural - in->now) > (int)(2u * SC_GAP)
            && !sc_trouble(in->game) && sc_rand(in->game, 100) < SC_P_PERCENT[in->game]) {
            unsigned int span = in->natural - in->now;
            unsigned int frac = (unsigned int)(SC_FRAC_MIN + sc_rand(in->game, SC_FRAC_SPAN));
            s->due = in->now + (unsigned int)((unsigned __int64)span * frac / 1000u);
            s->natural = in->natural;
            s->due_set = 1;
            return SC_SAVE;
        }
        return act;
    }
    if (!s->due_set || (int)(in->now - s->due) < 0) {
        return SC_NONE;
    }
    if ((int)(in->now - s->natural) >= 0) {
        s->due_set = 0;                /* the natural event it was to come before has passed */
        return SC_CANCEL;
    }
    if (in->busy || in->god_power || (int)(in->natural - in->now) <= (int)SC_GAP) {
        return SC_NONE;                /* wait: something else first, or the natural event is about to come */
    }
    if (sc_trouble(in->game)) {
        s->due_set = 0;
        return SC_CANCEL;
    }
    return SC_ARM;
}

/* ---- The save's file ----------------------------------------------------------------------------------------- */

typedef struct {
    unsigned int magic;
    unsigned int version;
    unsigned int game;
    unsigned int slot;
    unsigned int due;
    unsigned int natural;
    unsigned int roster[256];
} sc_file;

#ifdef VVFP_TEST
static sc_file sc_test_saved;

static int sc_read(int game, int slot, sc_file *f) {
    (void)game;
    (void)slot;
    if (!sc_test_have_file) {
        return 0;
    }
    *f = sc_test_saved;
    return 1;
}

static void sc_write(int game, int slot, const sc_file *f) {
    (void)game;
    (void)slot;
    sc_test_saved = *f;
    sc_test_have_file = 1;
}

static void sc_delete(int game, int slot) {
    (void)game;
    (void)slot;
    sc_test_have_file = 0;
}
#else
static int sc_read(int game, int slot, sc_file *f) {
    char path[MAX_PATH];
    unsigned int size = 0;
    if (!vv_paid_named_path(game, slot, "Island Event Collection Roll", path, 0)) {
        return 0;
    }
    return cg_read_whole(path, (unsigned char *)f, sizeof *f, &size) && size == sizeof *f;
}

static void sc_write(int game, int slot, const sc_file *f) {
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    if (!vv_paid_named_path(game, slot, "Island Event Collection Roll", path, 1)) {
        return;
    }
    parts[0] = f;
    sizes[0] = sizeof *f;
    (void)vv_paid_write_parts(path, parts, sizes, 1);
}

static void sc_delete(int game, int slot) {
    char path[MAX_PATH];
    if (vv_paid_named_path(game, slot, "Island Event Collection Roll", path, 0)) {
        DeleteFileA(path);
    }
}
#endif

static void sc_store(int game) {
    sc_file f;
    memset(&f, 0, sizeof f);
    f.magic = SC_MAGIC;
    f.version = SC_VERSION;
    f.game = (unsigned int)game;
    f.slot = (unsigned int)story_current_slot(game);
    f.due = sc.due;
    f.natural = sc.natural;
    (void)sq_roster_now(game, f.roster);
    sc_write(game, (int)f.slot, &f);
}

/* The village's due roll, from its file: only for the same village (a strict majority of its roster). */
static void sc_restore(int game) {
    sc_file f;
    unsigned int roster[256];
    int slot = story_current_slot(game);
    if (sq_roster_now(game, roster) == 0) {
        return;                        /* not loaded yet: asked again next frame */
    }
    sc_checked = 1;
    if (slot < 1 || !sc_read(game, slot, &f)) {
        return;
    }
    if (f.magic != SC_MAGIC || f.version != SC_VERSION || f.game != (unsigned int)game || f.slot != (unsigned int)slot
        || !sq_same_village(f.roster, roster)) {
        return;                        /* another village's (or unreadable): never used, left as it is */
    }
    sc.due_set = 1;
    sc.due = f.due;
    sc.natural = f.natural;
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

static unsigned char sc_manifest[SC_MANIFEST_BYTES];
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

/* The collection's events for `game` from manifest.txt: "id<TAB>title<TAB>games<TAB>weight<TAB>series<TAB>credit",
   one line each ('#' a comment), each with its "<id>.cieg" beside it.  The count. */
static int sc_scan(int game) {
    const char *text = NULL, *p, *end;
    unsigned int size = 0;
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    sc_count = 0;
#ifdef VVFP_TEST
    if (sc_test_manifest != NULL) {
        text = sc_test_manifest;
        size = (unsigned int)lstrlenA(text);
    }
#endif
    if (text == NULL) {
        if (!sc_collection_on(game) || sc_path(path, "manifest.txt") == 0
            || !sc_read_w(path, sc_manifest, SC_MANIFEST_BYTES - 1, &size)) {
            return 0;
        }
        sc_manifest[size] = '\0';
        text = (const char *)sc_manifest;
    }
    for (p = text; *p != '\0' && sc_count < SC_MAX; p = *end != '\0' ? end + 1 : end) {
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
        sc_field(p, end, 4, e->series, sizeof e->series);
        {
            int n = lstrlenA(e->series);
            if (n > 0 && e->series[n - 1] == '\r') {
                e->series[n - 1] = '\0';
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

/* Entry `i`'s compiled event into sc_bytes; 0 when it cannot be read. */
static int sc_load_entry(int i, unsigned int *size) {
    char leaf[80];
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
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
static int sc_arm_collection(int game, int i) {
    unsigned int size = 0;
#ifdef VVFP_TEST
    if (sc_test_traced < 64) {
        sc_test_trace[sc_test_traced++] = 0x10000 | i;
    }
    if (sc_test_manifest != NULL) {
        return (sc_test_coll_ok & (1u << (i & 31))) != 0;
    }
#endif
    return sc_load_entry(i, &size) && cg_queue_origin(game, sc_bytes, size, CG_ORIGIN_NATURAL, CG_CAST_STRICT);
}

/* The draw (see the header): 1 when an event was armed. */
static int sc_choose_and_arm(int game) {
    static int more[SM_MAX];
    static unsigned char left[SC_MAX];
    int n_more = 0, n_coll = 0, i;
    if (sc_more_on(game)) {
        sm_fill_more(game);
        for (i = 0; i < sm_list.count; ++i) {
            if (sm_list.possible[i] == 1) {
                more[n_more++] = sm_list.k[i];
            }
        }
    }
    if (sc_collection_on(game)) {
        n_coll = sc_scan(game);
    }
    for (i = 0; i < n_coll; ++i) {
        left[i] = 1;
    }
    while (n_more > 0 || n_coll > 0) {
        int source = n_more > 0 && n_coll > 0 ? sc_rand(game, 2) : (n_more > 0 ? 0 : 1);
        if (source == 0) {
            int j = sc_rand(game, n_more);
            if (sc_arm_more(game, more[j])) {
                return 1;
            }
            more[j] = more[--n_more];
            continue;
        }
        {
            /* The groups: each event its own (its weight), a series one (weight 1, members equally likely). */
            int total = 0, pick, chosen = -1, members = 0, m;
            for (i = 0; i < sc_count; ++i) {
                int first = 1, k;
                if (!left[i]) {
                    continue;
                }
                if (sc_list[i].series[0] != '\0') {
                    for (k = 0; k < i; ++k) {
                        if (left[k] && lstrcmpA(sc_list[k].series, sc_list[i].series) == 0) {
                            first = 0;
                            break;
                        }
                    }
                    total += first;
                } else {
                    total += sc_list[i].weight;
                }
            }
            pick = sc_rand(game, total);
            for (i = 0; i < sc_count && chosen < 0; ++i) {
                int w, k, first = 1;
                if (!left[i]) {
                    continue;
                }
                if (sc_list[i].series[0] != '\0') {
                    for (k = 0; k < i; ++k) {
                        if (left[k] && lstrcmpA(sc_list[k].series, sc_list[i].series) == 0) {
                            first = 0;
                            break;
                        }
                    }
                    w = first;
                } else {
                    w = sc_list[i].weight;
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
                int series_pick;
                for (m = 0; m < sc_count; ++m) {
                    members += left[m] && lstrcmpA(sc_list[m].series, sc_list[chosen].series) == 0;
                }
                series_pick = sc_rand(game, members);
                for (m = 0; m < sc_count; ++m) {
                    if (left[m] && lstrcmpA(sc_list[m].series, sc_list[chosen].series) == 0 && series_pick-- == 0) {
                        chosen = m;
                        break;
                    }
                }
            }
            if (sc_arm_collection(game, chosen)) {
                return 1;
            }
            left[chosen] = 0;
            --n_coll;
        }
    }
    return 0;
}

/* ---- Every frame --------------------------------------------------------------------------------------------- */

static void sc_apply(int game, int act) {
    if (act == SC_SAVE) {
        sc_store(game);
    } else if (act == SC_CANCEL) {
        sc_delete(game, story_current_slot(game));
    } else if (act == SC_ARM) {
        sc.due_set = 0;
        (void)sc_choose_and_arm(game);   /* nothing that can happen now: the roll is spent */
        sc_delete(game, story_current_slot(game));
        sc.busy_before = 1;              /* what comes next is ours, not a natural event */
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
        sc_checked = 0;
    }
    counter = ce_event_counter(game);
    memset(&in, 0, sizeof in);
    in.game = game;
    in.counter = -1;
    if (counter != NULL && sc_clock(game, &in.now, &timer)) {
        in.counter = *counter;
        in.natural = *timer;
        if (!sc_checked) {
            sc_restore(game);
        }
    }
    in.busy = sc_busy(game);
    in.god_power = game == 5 && read_u32(0x51D5A4u) != 0xFFFFFFFFu;
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
        lstrcpynA(why, "another branching island event is still running", cap);
        return why;
    }
    if (!sc_load_entry(i, &size) || !cg_load(&cg_g, sc_bytes, size)) {
        lstrcpynA(why, "its file can not be read: install the patch again", cap);
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
    int i, added = 0;
    if (!sc_collection_on(game) || sc_scan(game) == 0) {
        return 0;
    }
    for (i = 0; i < sc_count && sm_list.count < SM_MAX; ++i) {
        int m = sm_list.count;
        lstrcpynA(sm_list.title[m], sc_list[i].title, SM_TEXT);
        lstrcpynA(sm_list.description[m],
                  vvfp_tr("vvfp.story/story_collection.pick_description",
                          "An event of the Isola Grand Event Collection.", SM_TEXT), SM_TEXT);
        sm_list.k[m] = SM_COLL_BASE + i;
        sm_list.possible[m] = sc_check(game, i, sm_list.needs[m], SM_TEXT) == NULL;
        if (sm_list.possible[m]) {
            sm_list.needs[m][0] = '\0';
        }
        ++sm_list.count;
        ++added;
    }
    return added;
}

/* Collection entry `i` bought with Pick Island Event: confirmed, checked again and queued (strict cast, origin
   Pick Island Event).  1 when it is on its way. */
static int sc_pick_buy(int game, HWND owner, int i) {
    char message[1800], why[SM_TEXT];
    unsigned int size = 0;
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
    if (sc_check(game, i, why, sizeof why) != NULL || !sc_load_entry(i, &size)
        || !cg_queue_origin(game, sc_bytes, size, CG_ORIGIN_PICK, CG_CAST_STRICT)) {
        wsprintfA(message, "%.300s can not happen right now: %.600s No tech points have been deducted.",
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
    int i;
    if (!sc_collection_on(game) || sc_scan(game) == 0) {
        return;
    }
    for (i = 0; i < sc_count && cg_lib.count < CG_LIBRARY_MAX; ++i) {
        char leaf[80];
        wchar_t wide[VVFP_PATCHER_FILES_PATH_CAP];
        BOOL lossy = FALSE;
        int n;
        wsprintfA(leaf, "%s.cieg", sc_list[i].id);
        if (sc_path(wide, leaf) == 0) {
            continue;
        }
        n = WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, wide, -1, cg_lib.path[cg_lib.count], MAX_PATH, NULL,
                                &lossy);
        if (n <= 0 || lossy || GetFileAttributesA(cg_lib.path[cg_lib.count]) == INVALID_FILE_ATTRIBUTES) {
            continue;                  /* a folder the ANSI path cannot name: left out of the library only */
        }
        wsprintfA(cg_lib.label[cg_lib.count], "Isola Grand Event Collection: %.80s", sc_list[i].title);
        ++cg_lib.count;
    }
}

#ifdef VVFP_TEST
/* ---- Test build only ---------------------------------------------------------------------------------------- */

/* The roll's state machine on its own: io[0] game, [1] the Island Events Seen count (-1 none), [2] busy, [3] now,
   [4] the island timer, [5] a God Power armed, [6] the trouble guard (-1 the village's own, else forced); out:
   io[8] the action (SC_*), [9] due set, [10] due, [11] the natural time kept, [12] the count seen.  The action. */
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
    act = sc_step(&sc, &in);
    io[8] = act;
    io[9] = sc.due_set;
    io[10] = (int)sc.due;
    io[11] = (int)sc.natural;
    io[12] = sc.seen;
    return act;
}

/* A fresh roll: nothing seen, nothing due, no file, no trace. */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionReset(void) {
    memset(&sc, 0, sizeof sc);
    sc.seen = -1;
    sc_game = 0;
    sc_checked = 0;
    sc_test_trouble = -1;
    sc_test_traced = 0;
    sc_test_have_file = 0;
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

/* The trouble guard of the village in the game's own records. */
__declspec(dllexport) int __stdcall VvfpStoryProbeCollectionTrouble(int game) {
    sc_test_trouble = -1;
    return sc_trouble(game);
}

/* The save's file (kept in memory here): out[0] present, [1] due, [2] the natural time, [3] its slot.  Returns
   out[0]. */
__declspec(dllexport) int __stdcall VvfpStoryProbeCollectionFile(int *out) {
    out[0] = sc_test_have_file;
    out[1] = (int)sc_test_saved.due;
    out[2] = (int)sc_test_saved.natural;
    out[3] = (int)sc_test_saved.slot;
    return out[0];
}

/* One frame of the roll (VvfpStoryInstall's call), with the game's own memory. */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionTick(int game) {
    sc_tick(game);
}

/* The roll's state: out[0] due set, [1] due, [2] natural, [3] seen, [4] the armed pick's slot, [5] it is natural. */
__declspec(dllexport) void __stdcall VvfpStoryProbeCollectionState(int *out) {
    out[0] = sc.due_set;
    out[1] = (int)sc.due;
    out[2] = (int)sc.natural;
    out[3] = sc.seen;
    out[4] = pick_slot;
    out[5] = pick_natural;
}
#endif
