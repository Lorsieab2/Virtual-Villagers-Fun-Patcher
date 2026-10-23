/* Custom Island Event: what every game's adapter shares.  Included by
   vvfp_story_upgrades.c before the per-game adapters. */

/* The game's own thiscall routines, called as __fastcall with an unused EDX:
   both pass `this` in ECX and have the callee pop the stack arguments. */
typedef int (__fastcall *tc0_fn)(void *self, void *unused_edx);
typedef int (__fastcall *tc1_fn)(void *self, void *unused_edx, int a);
typedef int (__fastcall *tc2_fn)(void *self, void *unused_edx, int a, int b);
typedef int (__fastcall *tc3_fn)(void *self, void *unused_edx, int a, int b, int c);
#define TC3(va, self, a, b, c) \
    ((tc3_fn)(uintptr_t)(va))((void *)(self), NULL, (int)(a), (int)(b), (int)(c))
typedef int (__fastcall *tc5_fn)(void *self, void *unused_edx, int a, int b, int c, int d, int e);
typedef int (__fastcall *tc7_fn)(void *self, void *unused_edx, int a, int b, int c, int d, int e,
                                 int f, int g);
#define TC0(va, self) ((tc0_fn)(uintptr_t)(va))((void *)(self), NULL)
#define TC1(va, self, a) ((tc1_fn)(uintptr_t)(va))((void *)(self), NULL, (int)(a))
#define TC2(va, self, a, b) ((tc2_fn)(uintptr_t)(va))((void *)(self), NULL, (int)(a), (int)(b))
#define TC5(va, self, a, b, c, d, e) \
    ((tc5_fn)(uintptr_t)(va))((void *)(self), NULL, (int)(a), (int)(b), (int)(c), (int)(d), (int)(e))
#define TC7(va, self, a, b, c, d, e, f, g) \
    ((tc7_fn)(uintptr_t)(va))((void *)(self), NULL, (int)(a), (int)(b), (int)(c), (int)(d), \
                              (int)(e), (int)(f), (int)(g))
typedef int (__fastcall *tc9_fn)(void *self, void *unused_edx, int a, int b, int c, int d, int e,
                                 int f, int g, int h, int i);
#define TC9(va, self, a, b, c, d, e, f, g, h, i) \
    ((tc9_fn)(uintptr_t)(va))((void *)(self), NULL, (int)(a), (int)(b), (int)(c), (int)(d), \
                              (int)(e), (int)(f), (int)(g), (int)(h), (int)(i))

/* ---- Behaviours ------------------------------------------------------------

   One "make them do it" choice: the game's own starter of that action, as a
   stock caller starts it (the research's catalogue of every villager action,
   docs/story-cheat-upgrades.md).  The villager's current activity is
   stopped first with the game's own stop routine, as stock callers do, so the
   action starts now instead of after what they were doing. */
enum {
    ACT_STOP,        /* the stop routine alone */
    ACT_RECOVER,     /* cured, full health (each game's own way) */
    ACT_CALL,        /* VV1 / VV2: routine(villager index) on the array / pool */
    ACT_CALL_ARG,    /* VV1 / VV2: routine(villager index, arg) */
    ACT_DO,          /* VV3-VV5: the game's do-action routine with action id `arg` */
    ACT_EFFECT,      /* VV1 / VV2: routine(villager index) WITHOUT a stop (an effect
                        such as a sneeze, not an activity) */
    ACT_CALL_ARG2,   /* VV1 / VV2: routine(villager index, arg, 0) -- three stack
                        arguments, as the celebration and hut-building starters
                        take them (the place, then the stock callers' 0) */
    ACT_CALL_RAW,    /* VV1 / VV2: routine on the array / pool with `arg` (0-2)
                        stack arguments from `args` -- a village-wide routine
                        (the action runner, Blessings Day's greeting) */
    ACT_DROP         /* VV3-VV5: the player's drop of the villager where they stand
                        (thiscall on `arg`, the record): it picks up the object
                        there and starts that pickup; 0 = nothing there */
};

/* The Villager Changes list shows every action under its group, sorted by
   group then label (the table's own order never moves: a queued purchase
   stores the row's index). */
enum {
    CE_GROUP_GENERAL, CE_GROUP_WORK, CE_GROUP_LEISURE, CE_GROUP_CELEBRATION, CE_GROUP_DEVOTION,
    CE_GROUP_FAMILY, CE_GROUP_CHILDREN, CE_GROUP_HEALTH, CE_GROUP_CURIOSITY, CE_GROUP_MOOD,
    CE_GROUP_STORY, CE_GROUPS
};
static const char *const CE_GROUP_NAMES[CE_GROUPS] = {
    "General", "Work", "Leisure", "Celebration and dance", "Devotion", "Family", "Children",
    "Health, food and drink", "Curiosity", "Moods and idle", "Puzzles and story",
};

/* What an action needs that the game passes when it starts it (the body to
   bury, ...), found at the moment of use the way the game finds it; when
   there is none the change is refused (the villager could not do that now)
   instead of the action running on nothing. */
enum { CE_SUPPLY_BODY = 1, CE_SUPPLY_OTHER, CE_SUPPLY_GLOBAL, CE_SUPPLY_CALL };
enum { CE_REFUSE_ZERO = 1, CE_REFUSE_MINUS1, CE_REFUSE_BOTH };
typedef struct {
    int what;               /* CE_SUPPLY_* */
    int as_record;          /* BODY / OTHER: the record's address instead of its index */
    unsigned int va;        /* GLOBAL: the dword; CALL: the game's finder */
    unsigned int self;      /* CALL: thiscall `this` (0: cdecl, no arguments) */
    int refuse;             /* CE_REFUSE_*: the value that means "none" */
    int slot;               /* -1 the starter's argument (VV1 / VV2), 0-7 the argument
                               block's dword (VV3-VV5), -2 neither */
    unsigned int store_va;  /* non-zero: written there first, where the game keeps it */
} ce_supply;

/* The owner (2026-10-21): every villager action is offered; one that may
   harm the game or the save ends its label with " (Unsafe)" and carries
   `unsafe`, the plain reason the dialog shows before it is confirmed.
   `args`: the argument block a stock caller passes (VV3-VV5; NULL = zeros);
   for ACT_CALL_RAW the stack arguments. */
typedef struct {
    const char *label;
    int kind;
    unsigned int routine;
    int arg;
    int group;
    const char *unsafe;
    const int *args;
    const ce_supply *supply;
} ce_action;

typedef int (__cdecl *ce_finder_fn)(void);

/* The supplied value for `act` (1), or 0 when there is none now.  `self`
   is the villager's own index; `record`, `listed` and `skeleton` are the
   game adapter's own. */
static int ce_supply_value(const ce_action *act, int self, unsigned char *(*record)(int),
                           int (*listed)(const unsigned char *), int (*skeleton)(const unsigned char *),
                           int *value) {
    const ce_supply *s = act->supply;
    int v = 0;
    int i;
    int found = 0;
    if (s == NULL) {
        return 1;
    }
    if (s->what == CE_SUPPLY_BODY || s->what == CE_SUPPLY_OTHER) {
        for (i = 0; i < 256 && !found; ++i) {
            unsigned char *r = record(i);
            if (r == NULL || (s->what == CE_SUPPLY_OTHER && i == self)) {
                continue;
            }
            if (s->what == CE_SUPPLY_BODY ? skeleton(r) : (listed(r) && !skeleton(r))) {
                v = s->as_record ? (int)(uintptr_t)r : i;
                found = 1;
            }
        }
        if (!found) {
            return 0;
        }
    } else if (s->what == CE_SUPPLY_GLOBAL) {
        v = *(const int *)(uintptr_t)s->va;
    } else if (s->what == CE_SUPPLY_CALL) {
        v = s->self != 0 ? TC0(s->va, s->self) : ((ce_finder_fn)(uintptr_t)s->va)();
    } else {
        return 0;
    }
    if ((s->refuse == CE_REFUSE_ZERO || s->refuse == CE_REFUSE_BOTH) && v == 0) {
        return 0;
    }
    if ((s->refuse == CE_REFUSE_MINUS1 || s->refuse == CE_REFUSE_BOTH) && v == -1) {
        return 0;
    }
    if (s->store_va != 0) {
        *(int *)(uintptr_t)s->store_va = v;
    }
    *value = v;
    return 1;
}

/* The later games' argument block: the row's own (or zeros), with the
   supplied value in its slot. */
static void ce_argument_block(const ce_action *act, int value, int block[8]) {
    int i;
    for (i = 0; i < 8; ++i) {
        block[i] = act->args != NULL ? act->args[i] : 0;
    }
    if (act->supply != NULL && act->supply->slot >= 0 && act->supply->slot < 8) {
        block[act->supply->slot] = value;
    }
}

/* ---- The host (the game's Origins companion) ----------------------------- */

typedef struct {
    int size;
    int (__stdcall *slot)(void);
    int (__stdcall *mask_get)(void *record);
    int (__stdcall *mask_set)(void *record, int mask);
    void (__stdcall *preferences_changing)(int after);
    /* Choose Time Skip Amount (story_time_skip.inc); absent from a host
       older than that upgrade (its size stops before them). */
    int (__stdcall *time_skip_step)(int years);
    int (__stdcall *time_skip_settled)(void);
    /* Whether the game's clock runs (not paused): absent from a host that
       predates it (its size stops before it). */
    int (__stdcall *time_skip_running)(void);
    /* Called with the island-event timer and the value about to be written
       into it, just before an arm writes it, so the game's own next island
       event keeps its time (native/shared/island_timer_keep.h): absent from
       a host that predates it (its size stops before it). */
    void (__stdcall *island_arming)(void *field, unsigned int value);
} story_host;

/* The size of a host without the time skip's entries. */
#define STORY_HOST_BASE_SIZE ((int)offsetof(story_host, time_skip_step))
/* ...and of one with the step and settled entries but not running. */
#define STORY_HOST_SKIP_SIZE ((int)offsetof(story_host, time_skip_running))
/* ...and of one with every time-skip entry but not the island timer's. */
#define STORY_HOST_RUNNING_SIZE ((int)offsetof(story_host, island_arming))

static const story_host *story_hosts[6];

/* The time skip's entries of `game`'s host, or NULL when it has none. */
static const story_host *story_time_skip_host(int game) {
    const story_host *host = game >= 1 && game <= 5 ? story_hosts[game] : NULL;
    if (host == NULL || host->size < STORY_HOST_SKIP_SIZE || host->time_skip_step == NULL
        || host->time_skip_settled == NULL) {
        return NULL;
    }
    return host;
}

/* Whether `host`'s game clock runs now; a host that cannot say counts as
   running (only time between frames that run is counted at all). */
static int story_host_running(const story_host *host) {
    if (host->size < STORY_HOST_RUNNING_SIZE || host->time_skip_running == NULL) {
        return 1;
    }
    return host->time_skip_running() != 0;
}

/* Before an arm of `game` writes `value` into its island-event timer at
   `field`: the host keeps the time the game's own next event was due. */
static void story_island_arming(int game, void *field, unsigned int value) {
    const story_host *host = game >= 1 && game <= 5 ? story_hosts[game] : NULL;
    if (host != NULL && host->size >= (int)sizeof(story_host) && host->island_arming != NULL) {
        host->island_arming(field, value);
    }
}

/* Called once by each game's Origins companion (native/shared/story_bridge.h)
   with its slot and mask store.  Returns 1 when accepted. */
__declspec(dllexport) int __stdcall VvfpStoryAttachHost(int game, const story_host *host) {
    if (game < 1 || game > 5 || host == NULL
        || (host->size != STORY_HOST_BASE_SIZE && host->size != STORY_HOST_SKIP_SIZE
            && host->size != STORY_HOST_RUNNING_SIZE && host->size != (int)sizeof(story_host))
        || host->slot == NULL || host->mask_get == NULL || host->mask_set == NULL) {
        return 0;
    }
    story_hosts[game] = host;
    return 1;
}

static int story_current_slot(int game) {
    int slot;
    if (game < 1 || game > 5 || story_hosts[game] == NULL) {
        return 0;
    }
    slot = story_hosts[game]->slot();
    return slot >= 1 && slot <= 5 ? slot : 0;
}

/* The Heathen masks, as every Origins companion names them. */
static const char *const STORY_MASK_NAMES[6] = {
    "No mask", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask", "Tribal Chief Mask"
};

static int story_mask_count(int game) {
    return game >= 1 && game <= 5 && story_hosts[game] != NULL ? 5 : 0;
}

static const char *story_mask_name(int game, int mask) {
    (void)game;
    return mask >= 0 && mask <= 5 ? STORY_MASK_NAMES[mask] : "";
}

static int story_set_mask(int game, unsigned char *record, int mask) {
    if (game < 1 || game > 5 || story_hosts[game] == NULL || mask < 0 || mask > 5) {
        return 0;
    }
    return story_hosts[game]->mask_set(record, mask);
}

/* A likes/dislikes write is bracketed for the game whose mask identity
   includes the lists (The Secret City's Grant Running bracket). */
static void story_preferences_changing(int game, int after) {
    if (game >= 1 && game <= 5 && story_hosts[game] != NULL
        && story_hosts[game]->preferences_changing != NULL) {
        story_hosts[game]->preferences_changing(after);
    }
}

/* ---- The parentage log ---------------------------------------------------

   With the Parentage row ticked, every conception the game makes goes to
   the Births and Conceptions log through "VVFP Parentage Export.dll"'s
   WriteParentageRecordWithFather(game, records, mother, father-or-NULL) --
   the call each game's conception trampoline makes.  A custom-event
   pregnancy makes the same call, so it is logged exactly like a natural
   one.  The row is ticked when its conception hook is in the executable
   (the site no longer holds the stock bytes; story_tables.h) -- never merely
   because a DLL file happens to be in the folder. */
typedef int (__stdcall *write_parentage_fn)(int game, const void *records, const void *mother,
                                            const void *father);

static int story_parentage_ticked(int game) {
    static const unsigned int sites[6] = {
        0, VV1_PARENTAGE_SITE, VV2_PARENTAGE_SITE, VV3_PARENTAGE_SITE, VV4_PARENTAGE_SITE,
        VV5_PARENTAGE_SITE
    };
    static const unsigned char *const stock[6] = {
        0, VV1_PARENTAGE_STOCK, VV2_PARENTAGE_STOCK, VV3_PARENTAGE_STOCK, VV4_PARENTAGE_STOCK,
        VV5_PARENTAGE_STOCK
    };
    if (game < 1 || game > 5 || !mem_readable(sites[game], 5)) {
        return 0;
    }
    return memcmp((const void *)(uintptr_t)sites[game], stock[game], 5) != 0;
}

static int story_log_conception(int game, const void *records, const void *mother,
                                const void *father) {
    static int state;                 /* 0 = not tried, 1 = resolved, -1 = unavailable */
    static write_parentage_fn write_record;
    if (!story_parentage_ticked(game)) {
        return 0;
    }
    if (state == 0) {
        HMODULE module = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
        state = -1;
        if (module != NULL) {
            write_record = (write_parentage_fn)GetProcAddress(module,
                                                              "WriteParentageRecordWithFather");
            if (write_record != NULL) {
                state = 1;
            }
        }
    }
    if (state != 1) {
        return 0;
    }
    return write_record(game, records, mother, father);
}

/* The Secret City's own list: "alchemy" and "potions" at 62 and 63. */
#define STORY_PREFERENCES_79_VV3 \
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees," \
    "the dark,caves,herbs,berries,snakes,wind,rocks,heights,the ocean," \
    "playing,exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts," \
    "sand,sunlight,wood,crab meat,whale meat,fish,fruit,papaya,flies," \
    "swimming,running,learning,dancing,monkeys,parrots,work,lifting," \
    "surprises,jokes,sleeping,jumping,cooking,fire,eating,dragonflies,owls," \
    "dreaming,children,talking,holidays,vegetables,quiet,clouds,dirt," \
    "alchemy,potions,magic,plants,rain,fog,sitting,sharks,honey,stories," \
    "coral,thunder,lightning,pearls,stars,mango,nature"

/* The preference list of The Tree of Life and New Believers (79 words,
   each exe's own; tests/test_preference_lists_match_the_exes.py). */
#define STORY_PREFERENCES_79 \
    "ants,crowds,resting,laundry,medicine,turnips,butterflies,flowers,bees," \
    "the dark,caves,herbs,berries,snakes,wind,rocks,heights,the ocean,playing," \
    "exploring,blue,green,red,yellow,drums,bushes,bananas,coconuts,sand," \
    "sunlight,wood,crab meat,whale meat,fish,fruit,papaya,flies,swimming," \
    "running,learning,dancing,monkeys,parrots,work,lifting,surprises,jokes," \
    "sleeping,jumping,cooking,fire,eating,dragonflies,owls,dreaming,children," \
    "talking,holidays,vegetables,quiet,clouds,dirt,frogs,soap,magic,plants," \
    "rain,fog,sitting,sharks,honey,stories,coral,thunder,lightning,pearls," \
    "stars,mango,nature"

/* ---- Text into a game string table entry -------------------------------- */

static char ce_title_text[CE_TITLE_BYTES];
static char ce_body_text[2048];
