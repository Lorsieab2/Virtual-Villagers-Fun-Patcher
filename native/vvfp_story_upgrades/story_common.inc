/* Custom Island Event: what every game's adapter shares.  Included by
   vvfp_story_upgrades.c before the per-game adapters. */

/* The game's own thiscall routines, called as __fastcall with an unused EDX:
   both pass `this` in ECX and have the callee pop the stack arguments. */
typedef int (__fastcall *tc0_fn)(void *self, void *unused_edx);
typedef int (__fastcall *tc1_fn)(void *self, void *unused_edx, int a);
typedef int (__fastcall *tc2_fn)(void *self, void *unused_edx, int a, int b);
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
    ACT_EFFECT       /* VV1 / VV2: routine(villager index) WITHOUT a stop (an effect
                        such as a sneeze, not an activity) */
};

typedef struct {
    const char *label;
    int kind;
    unsigned int routine;
    int arg;
} ce_action;

/* ---- The host (the game's Origins companion) ----------------------------- */

typedef struct {
    int size;
    int (__stdcall *slot)(void);
    int (__stdcall *mask_get)(void *record);
    int (__stdcall *mask_set)(void *record, int mask);
    void (__stdcall *preferences_changing)(int after);
} story_host;

static const story_host *story_hosts[6];

/* Called once by each game's Origins companion (native/shared/story_bridge.h)
   with its slot and mask store.  Returns 1 when accepted. */
__declspec(dllexport) int __stdcall VvfpStoryAttachHost(int game, const story_host *host) {
    if (game < 1 || game > 5 || host == NULL || host->size != (int)sizeof(story_host)
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

/* The preference list of The Secret City, The Tree of Life and New
   Believers (79 words; native/population_export/population_export.c). */
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
