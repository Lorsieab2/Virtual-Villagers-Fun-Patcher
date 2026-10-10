/* QUEUED STORY PURCHASES SURVIVE A QUIT -- included by vvfp_story_upgrades.c
   after the time skip.

   What this companion queues lived in its own memory only, while what the
   purchase paid for and armed in the game is saved with the village:

     Pick Island Event        pick_slot / pick_event, and the outcome
                              settings (`oc`); the island event made due in
                              the game's own (saved) timer
     Custom Island Event      ce_armed_event, a question's ce_choice; the same
                              saved timer (and Choose Time Skip Amount's
                              closing notice, armed the same way)
     Pick Gong of Wonder      oc_gong (The Lost Children)
     Choose Time Skip Amount  the years still to go and those done (each step
                              made is in the save already)

   A quit before the delivery kept the charge and the due timer -- which then
   gave the next load a RANDOM island event in place of the one bought -- and
   lost the rest of a time skip.

   So the queue is kept per slot beside the barrel's file:
     <save folder>\Virtual Villagers Fun Patcher Data\Paid Purchases\
         Virtual Villagers N Story Purchases - Save S.dat
   with the village's roster, each item with the moment it became what it is.
   It is rewritten (atomically, native/shared/paid_purchases.h) whenever the
   queue changes and deleted when it is empty -- delivered, refused, lapsed or
   cut short in the village it was queued in.  Another village never deletes
   it (it waits for its village); Start Over does (VvfpStoryVillageReset, and
   native/shared/save_reset.c).

   WHAT IS RESTORED, AND WHEN.  When a village is on screen with nothing
   queued in memory, the slot's file is read once for that village, and an
   item is put back -- with no new charge, and without making the island
   event due again (the save holds the timer the purchase set) -- only when
     - the file is this game's and slot's, of this build's layout;
     - its roster shares a strict majority with the village (the same
       village);
     - the slot's save was written after the item became what it is: the
       save holds its charge and its timer.  An item newer than the save on
       disk (a crash lost that save) is dropped, never delivered for nothing
       -- the file then says what the save holds.
   This is the file's consistency with the save: it is written as the queue
   changes, and only what a later save holds is believed, which is what
   writing it at the save would give, without missing the quit's save (the
   process ends right after it).

   NO EXTRA RANDOM EVENT.  The save's timer may fire on the first frames after
   the load, before the village's first tick.  So the restore is also made
   where the game asks for an armed pick or custom event -- drop_lapsed_pick
   and ce_drop_lapsed, which every selector and delivery hook of the five
   games calls before it decides -- so the saved timer delivers the purchase
   itself, never a random event in its place. */

#define SQ_MAGIC   0x31515356u              /* 'V' 'S' 'Q' '1' */
#define SQ_VERSION 1u
#define SQ_PICK   1u
#define SQ_CUSTOM 2u
#define SQ_GONG   4u
#define SQ_SKIP   8u
#define SQ_ITEMS  4

typedef struct {
    unsigned int magic;
    unsigned int version;
    unsigned int game;
    unsigned int slot;
    unsigned int layout[4];                 /* sizeof oc_settings, ce_event, ce_choice, this */
    unsigned int roster[256];
    unsigned int have;                      /* SQ_* */
    unsigned __int64 when[SQ_ITEMS];        /* each item's moment (FILETIME units) */
    /* Pick Island Event */
    int pick_slot;
    int pick_index;                         /* into GAMES[game].events */
    int pick_outcome;                       /* 1: `oc` armed with pick_settings */
    oc_settings pick_settings;
    /* Custom Island Event (its question, when any, follows the record) */
    int ce_is_choice;
    int ce_is_notice;
    ce_event ce;
    /* Pick Gong of Wonder Outcome */
    oc_settings gong;
    /* Choose Time Skip Amount */
    int skip_remaining;
    int skip_done;
    int skip_notice;                        /* years the closing popup is to tell, when no step is left */
} sq_file;

static int sq_slot;                         /* the village tracked: its slot ... */
static unsigned int sq_generation;          /* ... its reset generation ... */
static unsigned int sq_roster[256];         /* ... and its roster */
static int sq_have_village;
static int sq_blocked;                      /* its file is there and cannot be read: hands off */
static sq_file sq_now_state;                /* the queue as captured, and as last written */
static sq_file sq_written;
static int sq_written_known;
static ce_choice sq_choice_buf;             /* a question, read or written with the record */

static const char *const SQ_SAVE_STEMS[6] = {
    "", "Virtual Villagers", "Virtual Villagers - The Lost Children", "Virtual Villagers - The Secret City",
    "Virtual Villagers - The Tree of Life", "Virtual Villagers - New Believers",
};

/* ---- The file (a test build keeps it in memory) ---------------------------- */

#ifdef VVFP_TEST
static unsigned char sq_test_file[sizeof(sq_file) + sizeof(ce_choice)];
static unsigned int sq_test_size;           /* 0 = no file */
static int sq_test_unreadable;
static unsigned __int64 sq_test_save_time;  /* 0 = no save */

static unsigned __int64 sq_clock(void) {
    return (unsigned __int64)STORY_TICK() + 1u;
}

static int sq_save_time(int game, int slot, unsigned __int64 *out) {
    (void)game;
    (void)slot;
    *out = sq_test_save_time;
    return sq_test_save_time != 0u;
}

/* 1 read (header checked by the caller), 0 absent, -1 unreadable. */
static int sq_read(int game, int slot, sq_file *f, ce_choice *choice) {
    (void)game;
    (void)slot;
    if (sq_test_unreadable) {
        return -1;
    }
    if (sq_test_size < sizeof *f) {
        return sq_test_size == 0u ? 0 : 2;
    }
    memcpy(f, sq_test_file, sizeof *f);
    if (sq_test_size == sizeof *f + sizeof *choice) {
        memcpy(choice, sq_test_file + sizeof *f, sizeof *choice);
    } else if (sq_test_size != sizeof *f) {
        return 2;
    }
    return 1;
}

static int sq_store(int game, int slot, const sq_file *f, const ce_choice *choice) {
    (void)game;
    (void)slot;
    memcpy(sq_test_file, f, sizeof *f);
    sq_test_size = sizeof *f;
    if (choice != NULL) {
        memcpy(sq_test_file + sizeof *f, choice, sizeof *choice);
        sq_test_size += sizeof *choice;
    }
    return 1;
}

static void sq_remove(int game, int slot) {
    (void)game;
    (void)slot;
    sq_test_size = 0;
}
#else
#include "../shared/paid_purchases.h"

static unsigned __int64 sq_clock(void) {
    FILETIME t;
    GetSystemTimeAsFileTime(&t);
    return ((unsigned __int64)t.dwHighDateTime << 32) | t.dwLowDateTime;
}

static int sq_save_time(int game, int slot, unsigned __int64 *out) {
    FILETIME t;
    if (game < 1 || game > 5 || !vv_paid_stem_time(SQ_SAVE_STEMS[game], slot, &t)) {
        return 0;
    }
    *out = ((unsigned __int64)t.dwHighDateTime << 32) | t.dwLowDateTime;
    return 1;
}

/* 1 read, 0 absent, 2 malformed, -1 present but unreadable. */
static int sq_read(int game, int slot, sq_file *f, ce_choice *choice) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0, more = 0;
    BOOL ok;
    if (!vv_paid_named_path(game, slot, "Story Purchases", path, 0)) {
        return -1;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD err = GetLastError();
        return (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND) ? 0 : -1;
    }
    ok = ReadFile(h, f, sizeof *f, &got, NULL);
    if (ok && got == sizeof *f && (f->have & SQ_CUSTOM) && f->ce_is_choice) {
        ok = ReadFile(h, choice, sizeof *choice, &more, NULL) && more == sizeof *choice;
    }
    CloseHandle(h);
    if (!ok && got == 0) {
        return -1;
    }
    return ok && got == sizeof *f ? 1 : 2;
}

static int sq_store(int game, int slot, const sq_file *f, const ce_choice *choice) {
    char path[MAX_PATH];
    const void *parts[2];
    DWORD sizes[2];
    if (!vv_paid_named_path(game, slot, "Story Purchases", path, 1)) {
        return 0;
    }
    parts[0] = f;
    sizes[0] = sizeof *f;
    parts[1] = choice;
    sizes[1] = sizeof *choice;
    return vv_paid_write_parts(path, parts, sizes, choice != NULL ? 2 : 1);
}

static void sq_remove(int game, int slot) {
    char path[MAX_PATH];
    if (vv_paid_named_path(game, slot, "Story Purchases", path, 0)) {
        DeleteFileA(path);
    }
}
#endif

/* ---- The village ------------------------------------------------------------- */

/* The roster of the village on screen; how many villagers it has. */
static int sq_roster_now(int game, unsigned int *out) {
    int i, n = 0, count = story_record_count(game);
    memset(out, 0, 256 * sizeof *out);
    for (i = 0; i < count && i < 256; ++i) {
        const unsigned char *record = story_record(game, i);
        if (record != NULL && story_record_present(game, record)) {
            out[i] = story_title_identity(game, record);
            if (out[i] == 0u) {
                out[i] = 1u;
            }
            ++n;
        }
    }
    return n;
}

/* A strict majority of the villagers in `was` are in `now`. */
static int sq_same_village(const unsigned int *was, const unsigned int *now) {
    int i, k, had = 0, kept = 0;
    for (i = 0; i < 256; ++i) {
        if (was[i] == 0u) {
            continue;
        }
        ++had;
        for (k = 0; k < 256; ++k) {
            if (now[k] == was[i]) {
                ++kept;
                break;
            }
        }
    }
    return had > 0 && kept * 2 > had;
}

/* ---- The queue ------------------------------------------------------------- */

static void sq_header(sq_file *f, int game, int slot) {
    f->magic = SQ_MAGIC;
    f->version = SQ_VERSION;
    f->game = (unsigned int)game;
    f->slot = (unsigned int)slot;
    f->layout[0] = sizeof(oc_settings);
    f->layout[1] = sizeof(ce_event);
    f->layout[2] = sizeof(ce_choice);
    f->layout[3] = sizeof(sq_file);
}

/* What is queued for the village on screen (slot, generation), into f
   (items only; the roster and the moments are the caller's). */
static void sq_capture(int game, sq_file *f) {
    int slot = story_current_slot(game);
    memset(&f->have, 0, sizeof *f - offsetof(sq_file, have));
    if (pick_slot >= 0 && pick_game == game && story_village_is(game, &pick_village) && pick_event != NULL
        && pick_event >= GAMES[game].events && pick_event < GAMES[game].events + GAMES[game].event_count) {
        f->have |= SQ_PICK;
        f->pick_slot = pick_slot;
        f->pick_index = (int)(pick_event - GAMES[game].events);
        if (oc.state == OC_ARMED && oc.game == game) {
            f->pick_outcome = 1;
            f->pick_settings = oc.set;
        }
    }
    if (ce_armed && ce_armed_event.game == game && story_village_is(game, &ce_armed_village)) {
        f->have |= SQ_CUSTOM;
        f->ce = ce_armed_event;
        f->ce_is_choice = ce_armed_is_choice;
        f->ce_is_notice = ce_armed_is_notice;
    }
    if (game == 2 && oc_gong.state == OC_ARMED && oc_gong.game == 2 && oc_gong.save_slot == slot) {
        f->have |= SQ_GONG;
        f->gong = oc_gong.set;
    }
    if (time_skip.game == game && story_village_is(game, &time_skip.village)
        && (time_skip.active || time_skip.finishing || time_skip.notice > 0)) {
        f->have |= SQ_SKIP;
        f->skip_remaining = time_skip.active ? time_skip.remaining : 0;
        f->skip_done = time_skip.done;
        f->skip_notice = time_skip.active ? 0 : (time_skip.finishing ? time_skip.done : time_skip.notice);
    }
}

/* Whether item `bit`'s own fields differ between a and b. */
static int sq_item_differs(const sq_file *a, const sq_file *b, unsigned int bit) {
    if ((a->have & bit) != (b->have & bit)) {
        return 1;
    }
    if (!(a->have & bit)) {
        return 0;
    }
    switch (bit) {
    case SQ_PICK:
        return a->pick_slot != b->pick_slot || a->pick_index != b->pick_index
            || a->pick_outcome != b->pick_outcome
            || memcmp(&a->pick_settings, &b->pick_settings, sizeof a->pick_settings) != 0;
    case SQ_CUSTOM:
        return a->ce_is_choice != b->ce_is_choice || a->ce_is_notice != b->ce_is_notice
            || memcmp(&a->ce, &b->ce, sizeof a->ce) != 0;
    case SQ_GONG:
        return memcmp(&a->gong, &b->gong, sizeof a->gong) != 0;
    default:
        return a->skip_remaining != b->skip_remaining || a->skip_done != b->skip_done
            || a->skip_notice != b->skip_notice;
    }
}

static int sq_bit_index(unsigned int bit) {
    return bit == SQ_PICK ? 0 : bit == SQ_CUSTOM ? 1 : bit == SQ_GONG ? 2 : 3;
}

/* The question queued with a custom event, for the file. */
static const ce_choice *sq_choice_now(const sq_file *f) {
    return (f->have & SQ_CUSTOM) && f->ce_is_choice ? &ce_choice_store[ce_armed_store] : NULL;
}

/* Put back what the file holds and the save paid for.  Returns the items
   restored. */
static unsigned int sq_restore(int game, int slot, sq_file *f, const ce_choice *choice) {
    unsigned __int64 saved = 0;
    unsigned int restored = 0;
    int have_save = sq_save_time(game, slot, &saved);
    unsigned int bit;
    for (bit = SQ_PICK; bit <= SQ_SKIP; bit <<= 1) {
        if ((f->have & bit) && (!have_save || f->when[sq_bit_index(bit)] > saved)) {
            f->have &= ~bit;                /* newer than the save: never paid for there */
        }
    }
    if ((f->have & SQ_PICK) && pick_slot < 0 && !ce_armed
        && f->pick_index >= 0 && f->pick_index < GAMES[game].event_count
        && GAMES[game].events[f->pick_index].slot == f->pick_slot) {
        pick_slot = f->pick_slot;
        pick_game = game;
        pick_event = &GAMES[game].events[f->pick_index];
        pick_tick = STORY_TICK();           /* its ten minutes start again */
        pick_village = story_village_now(game);
        if (f->pick_outcome) {
            oc_arm(game, pick_slot, &f->pick_settings);
        }
        restored |= SQ_PICK;
    }
    if ((f->have & SQ_CUSTOM) && !ce_armed && pick_slot < 0 && f->ce.game == game
        && (!f->ce_is_choice || choice != NULL)) {
        ce_armed_event = f->ce;
        ce_armed_is_choice = f->ce_is_choice;
        ce_armed_is_notice = f->ce_is_notice;
        if (f->ce_is_choice) {
            ce_armed_store = ce_asked ? 1 - ce_asked_store : 0;
            ce_choice_store[ce_armed_store] = *choice;
        }
        ce_armed_village = story_village_now(game);
        ce_armed = 1;
        restored |= SQ_CUSTOM;
    }
    if ((f->have & SQ_GONG) && game == 2 && oc_gong.state == OC_IDLE) {
        oc_arm_set(&oc_gong, 2, OC_GONG_SLOT, &f->gong);
        oc_gong.save_slot = slot;
        restored |= oc_gong.state == OC_ARMED ? SQ_GONG : 0u;
    }
    if ((f->have & SQ_SKIP) && !(time_skip.game == game && story_village_is(game, &time_skip.village)
                                  && (time_skip.active || time_skip.finishing || time_skip.notice > 0))) {
        time_skip.game = game;
        time_skip.village = story_village_now(game);
        time_skip.remaining = f->skip_remaining > 0 ? f->skip_remaining : 0;
        time_skip.done = f->skip_done;
        time_skip.waiting = 0;
        time_skip.finishing = 0;
        time_skip.active = time_skip.remaining > 0;
        time_skip.notice = time_skip.active ? 0 : f->skip_notice;
        restored |= SQ_SKIP;
    }
    return restored;
}

/* A village is on screen: the first time this village is seen, put back
   what its file holds; afterwards keep the file what the queue is. */
static DWORD sq_roster_written;              /* when the roster in the file was last refreshed */
#ifdef VVFP_TEST
static unsigned int sq_test_restored;        /* the items the last restore put back */
#endif

static void sq_sync(int game, int lazy) {
    static unsigned int roster[256];
    static sq_file file;
    unsigned __int64 now;
    unsigned int bit;
    int slot, read, changed = 0;
    if (game < 1 || game > 5 || !story_installed(game)) {
        return;
    }
    slot = story_current_slot(game);
    if (slot < 1 || slot > 5 || sq_roster_now(game, roster) == 0) {
        return;
    }
    if (!sq_have_village || slot != sq_slot || sq_generation != story_village_generation
        || (memcmp(sq_roster, roster, sizeof roster) != 0 && !sq_same_village(sq_roster, roster))) {
        /* Another village on screen: its own file, if any, is its own. */
        sq_have_village = 1;
        sq_slot = slot;
        sq_generation = story_village_generation;
        memcpy(sq_roster, roster, sizeof roster);
        sq_blocked = 0;
        memset(&sq_written, 0, sizeof sq_written);
        sq_written_known = 1;
        read = sq_read(game, slot, &file, &sq_choice_buf);
        if (read < 0) {
            sq_blocked = 1;                 /* there and unreadable: never written over */
        } else if (read == 1 && file.magic == SQ_MAGIC && file.version == SQ_VERSION
                   && file.game == (unsigned int)game && file.slot == (unsigned int)slot
                   && file.layout[0] == sizeof(oc_settings) && file.layout[1] == sizeof(ce_event)
                   && file.layout[2] == sizeof(ce_choice) && file.layout[3] == sizeof(sq_file)) {
            /* Not this village (or a frame of the last one while the slot is
               switched): nothing is put back, and the file stays until this
               village queues something of its own. */
            if (sq_same_village(file.roster, roster)) {
                unsigned int had = file.have;
                unsigned int restored = sq_restore(game, slot, &file,
                                                   (file.have & SQ_CUSTOM) && file.ce_is_choice ? &sq_choice_buf : NULL);
#ifdef VVFP_TEST
                sq_test_restored = restored;
#endif
                (void)restored;
                /* The file as it was: what was not put back (newer than the save,
                   or already queued anew) differs from memory, and the file is
                   rewritten below without it. */
                sq_written = file;
                sq_written.have = had;
            }
        } else if (read != 0) {
            sq_remove(game, slot);          /* malformed or another layout: nothing it says can be used */
        }
    }
    if (lazy || sq_blocked) {
        return;
    }
    memcpy(sq_roster, roster, sizeof roster);
    sq_capture(game, &sq_now_state);
    now = sq_clock();
    for (bit = SQ_PICK; bit <= SQ_SKIP; bit <<= 1) {
        int k = sq_bit_index(bit);
        if (sq_item_differs(&sq_now_state, &sq_written, bit)) {
            sq_now_state.when[k] = now;
            changed = 1;
        } else {
            sq_now_state.when[k] = sq_written.when[k];
        }
    }
    if (!changed) {
        /* A long wait while the village changes: the file keeps knowing it. */
        if (sq_now_state.have != 0u && memcmp(sq_written.roster, roster, sizeof roster) != 0
            && STORY_TICK() - sq_roster_written >= 30000u) {
            memcpy(sq_written.roster, roster, sizeof roster);
            if (sq_store(game, slot, &sq_written, sq_choice_now(&sq_written))) {
                sq_roster_written = STORY_TICK();
            }
        }
        return;
    }
    if (sq_now_state.have == 0u) {
        sq_remove(game, slot);              /* delivered, refused, lapsed or cut short */
        sq_written = sq_now_state;
        return;
    }
    sq_header(&sq_now_state, game, slot);
    memcpy(sq_now_state.roster, roster, sizeof roster);
    if (sq_store(game, slot, &sq_now_state, sq_choice_now(&sq_now_state))) {
        sq_written = sq_now_state;
        sq_roster_written = STORY_TICK();
    }
}
/* Where the game asks for an armed pick or custom event (drop_lapsed_pick,
   ce_drop_lapsed): put back a queued purchase first, so the saved timer
   delivers it rather than a random event. */
static int sq_lazy_running;
static void sq_lazy(void) {
    if (sq_game != 0 && !sq_lazy_running) {
        sq_lazy_running = 1;
        sq_sync(sq_game, 1);
        sq_lazy_running = 0;
    }
}

/* Every tick of the companion (VvfpStoryInstall). */
static void sq_tick(int game) {
    sq_game = game;
    if (!sq_lazy_running) {
        sq_lazy_running = 1;
        sq_sync(game, 0);
        sq_lazy_running = 0;
    }
}

/* Start Over or a deleted tribe in `slot`: the queue belonged to the village
   that is gone. */
static void sq_village_reset(int game, int slot) {
    if (game >= 1 && game <= 5 && slot >= 1 && slot <= 5) {
        sq_remove(game, slot);
    }
    sq_have_village = 0;
    sq_written_known = 0;
}

#ifdef VVFP_TEST
/* The file as the test build holds it: copies up to `size` bytes into `out`
   and returns its size (0 = none). */
__declspec(dllexport) int __stdcall VvfpStoryProbeQueueFile(void *out, int size) {
    if (out != NULL && size > 0) {
        memcpy(out, sq_test_file, (unsigned int)size < sq_test_size ? (unsigned int)size : sq_test_size);
    }
    return (int)sq_test_size;
}

/* A file from an earlier session (size 0 = none), the slot's save time (0 =
   no save) and whether the file cannot be read; and every queued item of this
   session forgotten -- what a new process starts with. */
__declspec(dllexport) void __stdcall VvfpStoryProbeQueueSession(const void *file, int size,
                                                                 unsigned int save_time, int unreadable) {
    sq_test_size = 0;
    if (file != NULL && size > 0 && (unsigned int)size <= sizeof sq_test_file) {
        memcpy(sq_test_file, file, (unsigned int)size);
        sq_test_size = (unsigned int)size;
    }
    sq_test_save_time = save_time;
    sq_test_unreadable = unreadable;
    pick_slot = -1;
    ce_armed = 0;
    ce_armed_is_choice = 0;
    ce_armed_is_notice = 0;
    oc_arm_clear(&oc);
    oc_arm_clear(&oc_gong);
    memset(&time_skip, 0, sizeof time_skip);
    sq_test_restored = 0;
    sq_have_village = 0;
    sq_written_known = 0;
    sq_blocked = 0;
}

/* The save of the slot happens now (its time = the test clock). */
__declspec(dllexport) void __stdcall VvfpStoryProbeQueueSaved(void) {
    sq_test_save_time = sq_clock() + 1u;
}

/* What is queued in memory: out[0] pick slot (-1 none), out[1] custom armed,
   out[2] custom is a question, out[3] gong armed, out[4] skip remaining,
   out[5] skip done, out[6] skip active, out[7] skip notice, out[8] the pick's
   outcome armed. */
__declspec(dllexport) void __stdcall VvfpStoryProbeQueueState(int *out) {
    out[0] = pick_slot;
    out[1] = ce_armed;
    out[2] = ce_armed_is_choice;
    out[3] = oc_gong.state == OC_ARMED;
    out[4] = time_skip.remaining;
    out[5] = time_skip.done;
    out[6] = time_skip.active;
    out[7] = time_skip.notice;
    out[8] = oc.state == OC_ARMED;
}

/* The restore made where the game asks for an armed event (sq_lazy), for the
   game VvfpStoryInstall last ran. */
__declspec(dllexport) int __stdcall VvfpStoryProbeQueueLazy(int game) {
    (void)game;                     /* the game is the one VvfpStoryInstall named */
    return drop_lapsed_pick();
}

/* The items the last restore put back (SQ_* bits). */
__declspec(dllexport) unsigned int __stdcall VvfpStoryProbeQueueRestored(void) {
    return sq_test_restored;
}

/* The layout the file is written in: out[0] sizeof(sq_file), out[1]
   offsetof have, out[2] offsetof when, out[3] offsetof pick_slot, out[4]
   offsetof ce, out[5] offsetof skip_remaining, out[6] sizeof ce_choice. */
__declspec(dllexport) void __stdcall VvfpStoryProbeQueueLayout(int *out) {
    out[0] = (int)sizeof(sq_file);
    out[1] = (int)offsetof(sq_file, have);
    out[2] = (int)offsetof(sq_file, when);
    out[3] = (int)offsetof(sq_file, pick_slot);
    out[4] = (int)offsetof(sq_file, ce);
    out[5] = (int)offsetof(sq_file, skip_remaining);
    out[6] = (int)sizeof(ce_choice);
}
#endif
