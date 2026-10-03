/* VVFP Cause of Death -- every death's cause and age in the Deaths log (all
   five games), and each grave's cause of death (and, in A New Home, its
   epitaph) on the game's own grave screen (A New Home, The Lost Children).

   The owner: "for the games that don't write a cause of death like VV1-VV2,
   can you add them please?" -- in the game, the way The Secret City, The Tree
   of Life and New Believers show it -- then "mention it for all 5 games in
   the logs, age of death too" (the age in the game's own units, 20 per year),
   and "can you also put the epitaphs for VV1-VV2 too?".

   THE WORDS.  The three later games keep a cause beside health and their
   grave dialog shows the game's own words for it (VV3 string 0x2E6 + cause,
   VV4 0x317, VV5 0x314; identical text in all three):

       -1 Unknown causes   (every island event passes -1)
        0 Disease          1 Starvation       2 Old age
        3 Work accident    4 Act of Nature    (4: no caller in any game)

   A New Home and The Lost Children keep no cause, so this companion records
   it the moment a villager dies, from the place that killed them, in those
   same words:

       old age           the aging step's old-age store       Old age
       sickness          the aging step's disease drain        Disease
       hunger, no food   the aging step's two food drains      Starvation
       a job's injury    the 2%-a-step work injuries           Work accident
       anything else     island events, the Gong, the Custom   Unknown causes
                         Island Event's "dies", an edited save

   "Anything else" is how the later games word every island event death, and
   it is noticed by this companion's per-frame tick: a villager it saw alive
   on an earlier frame who is now a skeleton, with no hooked site having
   reported the death.

   WHERE IT IS SHOWN.  A grave is written in the same step that frees the
   villager's record (the burial), and keeps only a name, a best skill and the
   age (VV1 manager+0xA31C, 50 x 0x2C; VV2 world+0x2EB0C, 50 x 0x7C).  So the
   cause recorded at death is carried, per record, to the grave slot at the
   burial, and kept in this patcher's own file beside the saves (the owner's
   rule: the game does not track it, so it goes in a .dat file):

       <save folder>\Virtual Villagers Fun Patcher Data\
           Virtual Villagers N Graves - Save S.dat

   The grave's own popup then draws one more line under "Age": the cause.
   A New Home's popup also gets the epitaph, under the name, the way The Lost
   Children's popup already shows its own (VV2 writes an epitaph into every
   grave and has a text box for it, so it gets none from here).  A grave dug
   before this patch, or for a body that was already lying when it was
   installed, has no recorded cause and shows nothing extra.

   THE EPITAPH (A New Home), the rule the later games' burial uses, in their
   words (New Believers' spelling): under 18 years (360 age units) one of
   "Curious and Playful" / "Loving and Special"; otherwise the best skill,
   compared in their order Farming, Parenting, Healing, Research, Building
   (strictly greater wins, so a tie keeps the earlier), one of two lines for
   it; every skill 0 gives "Respected Citizen".  The later games' Chief,
   Esteemed Elder and Scholar lines have no counterpart in A New Home and are
   left out (the owner: "Don't worry about the missing skill").  The two-way
   choices use this companion's own random numbers, never the game's.

   THE LOG.  Every death in every game is written as a "Death" record by
   "VVFP Parentage Export.dll" (WriteDeathRecord), into the village's Deaths
   log -- the same village header, held records and numbered roll as the
   Births and Conceptions log.  Without that DLL (the Births and Conceptions
   row off) no log is written; the graves work regardless.

   Installed at run time by VvfpCauseInstall(game, host) from the Origins
   companion; every site's stock bytes are checked first and any other build
   installs nothing.  VvfpCauseTick(game) runs every frame after that. */
#include <windows.h>
#include <string.h>
#include <stdint.h>
#include "sidecar_io.h"
#include "save_folder.h"

/* ---- Counters the tests read (TEST build only) ---------------------------- */
#ifdef VVFP_TEST
struct vvfp_cause_stats {
    int deaths;          /* deaths recorded, any route */
    int unhooked;        /* of those, found by the tick */
    int burials;         /* burials seen */
    int graves_set;      /* graves given a cause */
    int draws;           /* grave lines drawn */
    int logged;          /* WriteDeathRecord calls */
    int published;       /* .dat files written */
};
__declspec(dllexport) struct vvfp_cause_stats VvfpCauseStats = { 0 };
#define COD_COUNT(field) (++VvfpCauseStats.field)
/* The tests force the next epitaph roll (0 or 1) by writing here; -1 = draw. */
__declspec(dllexport) int VvfpCauseRollTest = -1;
#else
#define COD_COUNT(field) ((void)0)
#endif

/* ---- The game and its host ----------------------------------------------- */

/* The Origins companion's host table (native/shared/story_bridge.h): only
   the slot is used here. */
typedef struct {
    int size;
    int (__stdcall *slot)(void);
} cod_host;

static int g_game;
static const cod_host *g_host;

/* ---- Words ------------------------------------------------------------- */

enum {
    CAUSE_UNKNOWN = -1, CAUSE_DISEASE = 0, CAUSE_STARVATION = 1, CAUSE_OLD_AGE = 2,
    CAUSE_WORK = 3, CAUSE_NATURE = 4,
    /* Stored for a grave whose body was already lying when this was
       installed: no cause is known, so none is shown. */
    CAUSE_NONE = 0x7F
};

static const char *const CAUSE_WORDS[6] = {
    "Unknown causes", "Disease", "Starvation", "Old age", "Work accident", "Act of Nature"
};

static char cause_scratch[32];

static const char *cod_cause_words(int cause) {
    if (cause >= -1 && cause <= 4) {
        return CAUSE_WORDS[cause + 1];
    }
    /* No caller in any game passes anything else; should one, the log says
       what the game stored rather than guessing at words for it. */
    wsprintfA(cause_scratch, "(cause %d)", cause);
    return cause_scratch;
}

/* 0 = none.  New Believers' spelling of each line. */
enum {
    EPITAPH_NONE = 0, EPITAPH_CITIZEN, EPITAPH_FARMER1, EPITAPH_FARMER2,
    EPITAPH_PARENT1, EPITAPH_PARENT2, EPITAPH_HEALER1, EPITAPH_HEALER2,
    EPITAPH_RESEARCH1, EPITAPH_RESEARCH2, EPITAPH_BUILDER1, EPITAPH_BUILDER2,
    EPITAPH_CHILD1, EPITAPH_CHILD2, EPITAPH_COUNT
};
static const char *const EPITAPHS[EPITAPH_COUNT] = {
    NULL, "Respected Citizen", "Child of the Earth", "Nature's Friend",
    "Parent, Teacher, Friend", "Dedicated to Children", "Guardian of Health",
    "Dedicated to Others", "Dedicated Student", "Inspired Inventor",
    "Inspired Architect", "Strong Arms, Big Heart", "Curious and Playful",
    "Loving and Special"
};

/* ---- A New Home and The Lost Children: geometry -------------------------- */

struct game_geometry {
    unsigned int array_global;   /* holds the villager array's address */
    unsigned int stride;
    unsigned int present;        /* u8 */
    unsigned int health;
    unsigned int age;
    unsigned int name;
    unsigned int name_capacity;
    unsigned int skills;         /* five i32, stored Parenting, Building,
                                    Farming, Healing, Research (measured live,
                                    native/population_export) */
    unsigned int totem;          /* u8, VV2's Esteemed Elder statue; 0 = none */
    unsigned int graves_owner;   /* the graves' owner from the array: manager / world */
    unsigned int graves;         /* the table's offset in its owner */
    unsigned int grave_stride;
    unsigned int grave_name_capacity;
    unsigned int grave_age;
};

#define RECORDS 256
#define GRAVES 50

static const struct game_geometry GEO[3] = {
    { 0 },
    /* A New Home: array [0x48B614]; manager = [array+0x3E010]; graves at
       manager+0xA31C (name char[0x1C] at +0, age at +0x24; 0 = empty). */
    { 0x48B614u, 0x3D8u, 0x28u, 0x344u, 0x348u, 0x370u, 0x1Cu, 0x3BCu, 0u,
      0x3E010u, 0xA31Cu, 0x2Cu, 0x1Cu, 0x24u },
    /* The Lost Children: pool [0x499F24]; world = [pool+0xE574D4]; graves at
       world+0x2EB0C (name char[0x19] at +0, age at +0x74; 0 = empty). */
    { 0x499F24u, 0xE48Cu, 0x30u, 0x52Cu, 0x530u, 0x564u, 0x18u, 0x7E4u, 0x558u,
      0xE574D4u, 0x2EB0Cu, 0x7Cu, 0x19u, 0x74u },
};

#ifdef VVFP_TEST
/* The native harness (tests/test_cause_of_death_files.py) has no game image
   at 0x48B614 / 0x499F24: it hands its own villager array here. */
static unsigned char *test_array;
#endif

static unsigned char *cod_array(void) {
    const struct game_geometry *g = &GEO[g_game];
#ifdef VVFP_TEST
    if (test_array != NULL) {
        return test_array;
    }
#endif
    return *(unsigned char *volatile *)(uintptr_t)g->array_global;
}

static unsigned char *cod_record(int index) {
    unsigned char *array = cod_array();
    return array != NULL ? array + (size_t)index * GEO[g_game].stride : NULL;
}

static int cod_index_of(const unsigned char *record) {
    unsigned char *array = cod_array();
    size_t span;
    if (array == NULL || record < array) {
        return -1;
    }
    span = (size_t)(record - array);
    if (span % GEO[g_game].stride != 0 || span / GEO[g_game].stride >= RECORDS) {
        return -1;
    }
    return (int)(span / GEO[g_game].stride);
}

static unsigned char *cod_grave(int slot) {
    unsigned char *array = cod_array();
    unsigned char *owner;
    if (array == NULL || slot < 0 || slot >= GRAVES) {
        return NULL;
    }
    owner = *(unsigned char **)(array + GEO[g_game].graves_owner);
    if (owner == NULL) {
        return NULL;
    }
    return owner + GEO[g_game].graves + (size_t)slot * GEO[g_game].grave_stride;
}

/* FNV-1a over a name (to its terminator, at most `capacity` bytes) and an
   age.  A villager's age never changes after death, and the burial copies
   both into the grave, so the same value names the skeleton and its grave.
   Never 0. */
static unsigned int cod_fingerprint(const unsigned char *name, unsigned int capacity, int age) {
    unsigned int h = 2166136261u;
    unsigned int i;
    for (i = 0; i < capacity && name[i] != 0; ++i) {
        h = (h ^ name[i]) * 16777619u;
    }
    h = (h ^ 0xFFu) * 16777619u;
    for (i = 0; i < 4; ++i) {
        h = (h ^ ((unsigned int)age >> (8 * i) & 0xFFu)) * 16777619u;
    }
    return h != 0 ? h : 1u;
}

static unsigned int cod_record_fingerprint(const unsigned char *record) {
    const struct game_geometry *g = &GEO[g_game];
    return cod_fingerprint(record + g->name, g->name_capacity, *(const int *)(record + g->age));
}

static unsigned int cod_grave_fingerprint(const unsigned char *grave) {
    const struct game_geometry *g = &GEO[g_game];
    return cod_fingerprint(grave, g->grave_name_capacity, *(const int *)(grave + g->grave_age));
}

/* The name alone, for "this record still holds the villager I saw alive". */
static unsigned int cod_name_hash(const unsigned char *record) {
    return cod_fingerprint(record + GEO[g_game].name, GEO[g_game].name_capacity, 0);
}

/* ---- Epitaph (A New Home) ------------------------------------------------ */

static unsigned int roll_state;

static int cod_roll_half(void) {
#ifdef VVFP_TEST
    if (VvfpCauseRollTest == 0 || VvfpCauseRollTest == 1) {
        return VvfpCauseRollTest;
    }
#endif
    if (roll_state == 0) {
        roll_state = GetTickCount() | 1u;
    }
    roll_state ^= roll_state << 13;
    roll_state ^= roll_state >> 17;
    roll_state ^= roll_state << 5;
    return (int)(roll_state >> 31);
}

/* The later games' burial rule, decided from the villager's record at death. */
static int cod_epitaph(const unsigned char *record) {
    /* Storage order Parenting, Building, Farming, Healing, Research; the
       comparison runs in the later games' order Farming, Parenting, Healing,
       Research, Building, strictly greater, so a tie keeps the earlier. */
    static const int ORDER[5] = { 2, 0, 3, 4, 1 };
    static const int LINE[5] = { EPITAPH_FARMER1, EPITAPH_PARENT1, EPITAPH_HEALER1,
                                 EPITAPH_RESEARCH1, EPITAPH_BUILDER1 };
    const struct game_geometry *g = &GEO[g_game];
    int best = -1;
    int best_value = 0;
    int k;
    if (*(const int *)(record + g->age) < 360) {
        return cod_roll_half() ? EPITAPH_CHILD2 : EPITAPH_CHILD1;
    }
    for (k = 0; k < 5; ++k) {
        int value = *(const int *)(record + g->skills + 4u * (unsigned int)ORDER[k]);
        if (value > best_value) {
            best_value = value;
            best = k;
        }
    }
    if (best < 0) {
        return EPITAPH_CITIZEN;
    }
    return LINE[best] + cod_roll_half();
}

/* ---- The tables and their file (A New Home, The Lost Children) ------------ */

struct cod_entry {
    unsigned int fingerprint;
    signed char cause;            /* CAUSE_*, or CAUSE_NONE */
    unsigned char epitaph;        /* EPITAPH_* */
    unsigned char valid;
    unsigned char reserved;
};

/* A body lying in record i, and grave k. */
static struct cod_entry skeletons[RECORDS];
static struct cod_entry graves[GRAVES];

/* What the hooks did since the last tick.  Applied to the tables at once;
   replayed onto the new village's tables when the tick finds the slot has
   changed -- the load-time catch-up of a village runs before the first tick
   that sees its slot. */
enum { EVENT_DEATH = 1, EVENT_BURIAL = 2, EVENT_DECAY = 3 };
struct cod_event {
    int type;
    int index;
    int grave;
    struct cod_entry entry;
};
#define JOURNAL 512
static struct cod_event journal[JOURNAL];
static int journal_count;

static unsigned int seen_alive[RECORDS];   /* name hash, 0 = not seen alive */

static struct {
    int slot;                 /* the slot the tables belong to, 0 = none */
    int loaded;
    int dirty;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} store;

/* FORMAT (little-endian), exactly 16 + 12 * count bytes:
       u32 magic 'VCD1', u32 version 1, u32 game (1 or 2), u32 count,
       count x { u16 kind (0 grave, 1 lying body), u16 index (grave 0..49,
                 record 0..255), u32 fingerprint, i8 cause (-1..4, or 0x7F
                 none), u8 epitaph (0..13), u16 0 } */
#define COD_MAGIC 0x31444356u
#define COD_VERSION 1u
#define COD_HEADER 16u
#define COD_ENTRY 12u
#define COD_MAX_ENTRIES (RECORDS + GRAVES)
static unsigned char file_buffer[COD_HEADER + COD_MAX_ENTRIES * COD_ENTRY];

static int cod_entry_ok(const unsigned char *e) {
    unsigned int kind = (unsigned int)(e[0] | e[1] << 8);
    unsigned int index = (unsigned int)(e[2] | e[3] << 8);
    signed char cause = (signed char)e[8];
    if (kind > 1u || index >= (kind == 0u ? (unsigned)GRAVES : (unsigned)RECORDS)) {
        return 0;
    }
    if (!((cause >= -1 && cause <= 4) || cause == CAUSE_NONE)) {
        return 0;
    }
    if (e[9] >= EPITAPH_COUNT || e[10] != 0 || e[11] != 0) {
        return 0;
    }
    return *(const unsigned int *)(e + 4) != 0u;
}

static int cod_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count;
    unsigned int i;
    (void)context;
    if (length < COD_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    if (*(const unsigned int *)data != COD_MAGIC
        || *(const unsigned int *)(data + 4) != COD_VERSION
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game
        || count > COD_MAX_ENTRIES
        || length != COD_HEADER + count * COD_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (!cod_entry_ok(data + COD_HEADER + i * COD_ENTRY)) {
            return 0;
        }
    }
    return 1;
}

static void cod_parse(const unsigned char *data) {
    unsigned int count = *(const unsigned int *)(data + 12);
    unsigned int i;
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + COD_HEADER + i * COD_ENTRY;
        unsigned int kind = (unsigned int)(e[0] | e[1] << 8);
        unsigned int index = (unsigned int)(e[2] | e[3] << 8);
        struct cod_entry *to = kind == 0u ? &graves[index] : &skeletons[index];
        to->fingerprint = *(const unsigned int *)(e + 4);
        to->cause = (signed char)e[8];
        to->epitaph = e[9];
        to->valid = 1;
    }
}

static DWORD cod_serialise(void) {
    unsigned int count = 0;
    int pass;
    for (pass = 0; pass < 2; ++pass) {
        int n = pass == 0 ? GRAVES : RECORDS;
        const struct cod_entry *table = pass == 0 ? graves : skeletons;
        int i;
        for (i = 0; i < n; ++i) {
            unsigned char *e;
            if (!table[i].valid) {
                continue;
            }
            e = file_buffer + COD_HEADER + count * COD_ENTRY;
            e[0] = (unsigned char)pass;
            e[1] = 0;
            e[2] = (unsigned char)(i & 0xFF);
            e[3] = (unsigned char)(i >> 8);
            *(unsigned int *)(e + 4) = table[i].fingerprint;
            e[8] = (unsigned char)table[i].cause;
            e[9] = table[i].epitaph;
            e[10] = 0;
            e[11] = 0;
            ++count;
        }
    }
    *(unsigned int *)file_buffer = COD_MAGIC;
    *(unsigned int *)(file_buffer + 4) = COD_VERSION;
    *(unsigned int *)(file_buffer + 8) = (unsigned int)g_game;
    *(unsigned int *)(file_buffer + 12) = count;
    return COD_HEADER + count * COD_ENTRY;
}

static int cod_build_path(int slot, char *out) {
    char folder[MAX_PATH];
    if (!vv_save_subfolder(folder, "Virtual Villagers Fun Patcher Data",
                           (int)sizeof("\\Virtual Villagers 1 Graves - Save 0.dat"))) {
        return 0;
    }
    wsprintfA(out, "%s\\Virtual Villagers %d Graves - Save %d.dat", folder, g_game, slot);
    return 1;
}

static void cod_forget(void) {
    memset(skeletons, 0, sizeof skeletons);
    memset(graves, 0, sizeof graves);
}

static void cod_apply(const struct cod_event *e);

/* Bind the tables to `slot`, loading its file (again after a blocked load's
   retry window).  The events since the last tick are replayed on top. */
static void cod_bind(int slot) {
    DWORD length = 0;
    int result;
    int i;
    if (slot != store.slot) {
        store.slot = slot;
        store.loaded = 0;
        store.dirty = 0;
        store.path[0] = '\0';
        memset(seen_alive, 0, sizeof seen_alive);
        vv_sidecar_gate_bind(&store.gate, g_game * 16 + slot);
        cod_forget();
    }
    if (slot <= 0 || store.loaded || vv_sidecar_gate_throttled(&store.gate)) {
        return;
    }
    if (store.path[0] == '\0' && !cod_build_path(slot, store.path)) {
        vv_sidecar_gate_block(&store.gate);
        return;
    }
    result = vv_sidecar_load(&store.gate, store.path, file_buffer, sizeof file_buffer,
                             &length, cod_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;
    }
    cod_forget();
    if (result == VV_SIDECAR_LOAD_VALID) {
        cod_parse(file_buffer);
    }
    store.loaded = 1;
    for (i = 0; i < journal_count; ++i) {
        cod_apply(&journal[i]);
    }
    if (journal_count > 0) {
        store.dirty = 1;
    }
}

static void cod_publish(void) {
    const void *parts[1];
    DWORD sizes[1];
    if (!store.loaded || store.slot <= 0 || !store.dirty) {
        return;
    }
    parts[0] = file_buffer;
    sizes[0] = cod_serialise();
    if (vv_sidecar_publish(&store.gate, store.path, parts, sizes, 1)) {
        store.dirty = 0;
        COD_COUNT(published);
    }
}

static void cod_apply(const struct cod_event *e) {
    if (e->type == EVENT_DEATH) {
        skeletons[e->index] = e->entry;
    } else if (e->type == EVENT_BURIAL) {
        graves[e->grave] = e->entry;
        skeletons[e->index].valid = 0;
    } else if (e->type == EVENT_DECAY) {
        skeletons[e->index].valid = 0;
    }
}

static void cod_event(const struct cod_event *e) {
    cod_apply(e);
    store.dirty = 1;
    if (journal_count < JOURNAL) {
        journal[journal_count++] = *e;
    }
}

/* ---- The log ------------------------------------------------------------- */

typedef int (__stdcall *write_death_fn)(int game, const void *record, int age, const char *cause);
static int log_state;            /* 0 = not tried, 1 = resolved, -1 = unavailable */
static write_death_fn write_death;

static void cod_log_death(const unsigned char *record, int age, const char *words) {
    if (log_state == 0) {
        char path[MAX_PATH];
        char *slash;
        DWORD n;
        HMODULE module;
        log_state = -1;
        n = GetModuleFileNameA(NULL, path, MAX_PATH);
        slash = n != 0 && n < MAX_PATH ? strrchr(path, '\\') : NULL;
        if (slash != NULL
            && (size_t)(slash + 1 - path) + sizeof("VVFP Parentage Export.dll") <= sizeof(path)) {
            lstrcpyA(slash + 1, "VVFP Parentage Export.dll");
            module = LoadLibraryA(path);
            if (module != NULL) {
                write_death = (write_death_fn)GetProcAddress(module, "WriteDeathRecord");
                if (write_death != NULL) {
                    log_state = 1;
                }
            }
        }
    }
    if (log_state == 1) {
        COD_COUNT(logged);
        write_death(g_game, record, age, words);
    }
}

/* ---- A death (A New Home, The Lost Children) ------------------------------ */

/* Called from a hooked site BEFORE the store that kills, or from the tick or
   the burial for a death no site reported.  The record still holds the
   villager. */
static void cod_died(const unsigned char *record, int cause) {
    struct cod_event e;
    int index = cod_index_of(record);
    if (index < 0) {
        return;
    }
    e.type = EVENT_DEATH;
    e.index = index;
    e.grave = 0;
    e.entry.fingerprint = cod_record_fingerprint(record);
    e.entry.cause = (signed char)cause;
    e.entry.epitaph = (unsigned char)(g_game == 1 ? cod_epitaph(record) : EPITAPH_NONE);
    e.entry.valid = 1;
    e.entry.reserved = 0;
    if (skeletons[index].valid && skeletons[index].fingerprint == e.entry.fingerprint
        && seen_alive[index] == 0) {
        return;                       /* already recorded */
    }
    seen_alive[index] = 0;
    cod_event(&e);
    COD_COUNT(deaths);
    cod_log_death(record, *(const int *)(record + GEO[g_game].age), cod_cause_words(cause));
}

/* ---- The hooked death sites ----------------------------------------------

   Each site's displaced instructions run unchanged after a check made BEFORE
   them, against the health they are about to change:

     STORE0  `mov [reg+health], 0`              alive -> dies
     DEC1    the load / lea before `dec`        health 1 -> dies
     SUB     `sub [ptr], eax` (or the load       health - eax <= 0 -> dies
             before `sub ecx, eax`)

   None of the displaced bytes is relative and no branch lands inside them
   (tests/test_cause_of_death.py checks both against the executables). */
enum { K_STORE0 = 1, K_DEC1 = 2, K_SUB = 3 };
/* The pushad order, as the stub leaves it under the saved flags. */
enum { R_EDI = 1, R_ESI, R_EBP, R_ESP, R_EBX, R_EDX, R_ECX, R_EAX };

struct death_site {
    unsigned int va;
    unsigned char length;
    unsigned char stock[10];
    signed char cause;
    unsigned char kind;
    unsigned char ra;
    unsigned char rb;          /* DEC1: the second base register */
};

#define VV1_DEATH_SITES 13
static const struct death_site VV1_SITES[VV1_DEATH_SITES] = {
    /* The aging step (tick 0x42E900, once per age unit). */
    { 0x42EF05u, 10, { 0xC7, 0x83, 0x44, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
      CAUSE_OLD_AGE, K_STORE0, R_EBX, 0 },
    { 0x42ECB7u, 7, { 0x8B, 0x8C, 0x07, 0x44, 0x03, 0x00, 0x00 },
      CAUSE_STARVATION, K_DEC1, R_EDI, R_EAX },     /* hunger, food <= 200 */
    { 0x42ED37u, 7, { 0x8B, 0x8C, 0x17, 0x44, 0x03, 0x00, 0x00 },
      CAUSE_STARVATION, K_DEC1, R_EDI, R_EDX },     /* no food */
    { 0x42EDA3u, 7, { 0x8B, 0x8C, 0x17, 0x44, 0x03, 0x00, 0x00 },
      CAUSE_DISEASE, K_DEC1, R_EDI, R_EDX },        /* sick */
    /* Work injuries: the job callbacks' 2% rand(15) / rand(10). */
    { 0x43A5B4u, 8, { 0x29, 0x03, 0x8B, 0x86, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EBX, 0 },
    { 0x43A793u, 8, { 0x29, 0x07, 0x8B, 0x86, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x43A8BAu, 8, { 0x29, 0x07, 0x8B, 0x96, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x43A9E1u, 8, { 0x29, 0x07, 0x8B, 0x96, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x43AAE7u, 8, { 0x29, 0x07, 0x8B, 0x8E, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x43AC9Bu, 8, { 0x29, 0x07, 0x8B, 0x86, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x43B112u, 8, { 0x29, 0x07, 0x8B, 0x8E, 0x10, 0xE0, 0x03, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x43B2D4u, 5, { 0x8B, 0x0B, 0x83, 0xC4, 0x04 }, CAUSE_WORK, K_SUB, R_EBX, 0 },
    { 0x43B393u, 5, { 0x8B, 0x0B, 0x83, 0xC4, 0x04 }, CAUSE_WORK, K_SUB, R_EBX, 0 },
};

#define VV2_DEATH_SITES 15
static const struct death_site VV2_SITES[VV2_DEATH_SITES] = {
    /* The aging step (tick 0x43B690). */
    { 0x43BDEEu, 10, { 0xC7, 0x83, 0x2C, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },
      CAUSE_OLD_AGE, K_STORE0, R_EBX, 0 },
    { 0x43BAEBu, 7, { 0x8D, 0x84, 0x38, 0x2C, 0x05, 0x00, 0x00 },
      CAUSE_STARVATION, K_DEC1, R_EAX, R_EDI },     /* hunger, food <= 150 */
    { 0x43BB7Eu, 7, { 0x8D, 0x84, 0x3A, 0x2C, 0x05, 0x00, 0x00 },
      CAUSE_STARVATION, K_DEC1, R_EDX, R_EDI },     /* no food */
    { 0x43BC43u, 7, { 0x8D, 0x84, 0x3A, 0x2C, 0x05, 0x00, 0x00 },
      CAUSE_DISEASE, K_DEC1, R_EDX, R_EDI },        /* sick */
    /* Work injuries: building projects' rand(15), research and the
       restorations' rand(10). */
    { 0x46299Cu, 9, { 0x29, 0x45, 0x00, 0x8B, 0x86, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EBP, 0 },
    { 0x462AD9u, 8, { 0x29, 0x07, 0x8B, 0x8E, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x462C11u, 8, { 0x29, 0x07, 0x8B, 0x86, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x462D48u, 8, { 0x29, 0x07, 0x8B, 0x96, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x462E84u, 8, { 0x29, 0x07, 0x8B, 0x96, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x462F96u, 8, { 0x29, 0x07, 0x8B, 0x96, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x463099u, 8, { 0x29, 0x07, 0x8B, 0x96, 0xD4, 0x74, 0xE5, 0x00 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x463644u, 6, { 0x8B, 0x4D, 0x00, 0x83, 0xC4, 0x04 }, CAUSE_WORK, K_SUB, R_EBP, 0 },
    { 0x4638E6u, 5, { 0x8B, 0x0F, 0x83, 0xC4, 0x04 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x46404Au, 5, { 0x8B, 0x0F, 0x83, 0xC4, 0x04 }, CAUSE_WORK, K_SUB, R_EDI, 0 },
    { 0x4641B3u, 6, { 0x8B, 0x4D, 0x00, 0x83, 0xC4, 0x04 }, CAUSE_WORK, K_SUB, R_EBP, 0 },
};

static const struct death_site *cod_sites(int *count) {
    if (g_game == 1) {
        *count = VV1_DEATH_SITES;
        return VV1_SITES;
    }
    if (g_game == 2) {
        *count = VV2_DEATH_SITES;
        return VV2_SITES;
    }
    *count = 0;
    return NULL;
}

/* regs: [0] flags, then pushad's edi, esi, ebp, esp, ebx, edx, ecx, eax. */
static void __cdecl cod_site_hit(int site, const unsigned int *regs) {
    int count;
    const struct death_site *s = cod_sites(&count);
    const int *health;
    if (s == NULL || site < 0 || site >= count) {
        return;
    }
    s += site;
    if (s->kind == K_STORE0) {
        health = (const int *)(uintptr_t)(regs[s->ra] + GEO[g_game].health);
        if (*health > 0) {
            cod_died((const unsigned char *)health - GEO[g_game].health, s->cause);
        }
    } else if (s->kind == K_DEC1) {
        health = (const int *)(uintptr_t)(regs[s->ra] + regs[s->rb] + GEO[g_game].health);
        if (*health == 1) {
            cod_died((const unsigned char *)health - GEO[g_game].health, s->cause);
        }
    } else if (s->kind == K_SUB) {
        int amount = (int)regs[R_EAX];
        health = (const int *)(uintptr_t)regs[s->ra];
        if (*health > 0 && *health - amount <= 0) {
            cod_died((const unsigned char *)health - GEO[g_game].health, s->cause);
        }
    }
}

/* The per-site stubs, generated once into a page that is written while
   read/write and then made read/execute (never both at once):

       pushad; pushfd; push esp; push <site>; call [cod_site_hit_ptr];
       add esp, 8; popfd; popad; <the displaced bytes>; jmp <site + length> */
static void (__cdecl *const cod_site_hit_ptr)(int, const unsigned int *) = cod_site_hit;
static unsigned char *stub_page;
#define STUB_BYTES 48

static unsigned char *cod_build_stubs(const struct death_site *sites, int count) {
    unsigned char *page = (unsigned char *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE,
                                                        PAGE_READWRITE);
    DWORD old;
    int i;
    if (page == NULL || count * STUB_BYTES > 4096) {
        return NULL;
    }
    for (i = 0; i < count; ++i) {
        unsigned char *p = page + i * STUB_BYTES;
        unsigned int target = (unsigned int)(uintptr_t)&cod_site_hit_ptr;
        int back;
        *p++ = 0x60;                                  /* pushad */
        *p++ = 0x9C;                                  /* pushfd */
        *p++ = 0x54;                                  /* push esp */
        *p++ = 0x68; memcpy(p, &i, 4); p += 4;        /* push site */
        *p++ = 0xFF; *p++ = 0x15; memcpy(p, &target, 4); p += 4;   /* call [ptr] */
        *p++ = 0x83; *p++ = 0xC4; *p++ = 0x08;        /* add esp, 8 */
        *p++ = 0x9D;                                  /* popfd */
        *p++ = 0x61;                                  /* popad */
        memcpy(p, sites[i].stock, sites[i].length);
        p += sites[i].length;
        *p++ = 0xE9;
        back = (int)(sites[i].va + sites[i].length) - (int)((uintptr_t)p + 4);
        memcpy(p, &back, 4);
    }
    if (!VirtualProtect(page, 4096, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(page, 0, MEM_RELEASE);
        return NULL;
    }
    FlushInstructionCache(GetCurrentProcess(), page, 4096);
    return page;
}

/* ---- Writing a detour ---------------------------------------------------- */

struct cod_site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

static int cod_bytes_are(unsigned int va, const unsigned char *stock, int length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, stock, (size_t)length) == 0;
}

static int cod_site_is_stock(const struct cod_site *s) {
    return cod_bytes_are(s->va, s->stock, s->length);
}

/* A `jmp stub` and nops over the displaced bytes. */
static int cod_write_jmp(unsigned int va, int length, const void *stub) {
    unsigned char bytes[16];
    unsigned char *at = (unsigned char *)(uintptr_t)va;
    unsigned int rel = (unsigned int)((const unsigned char *)stub - (at + 5));
    DWORD old;
    int i;
    bytes[0] = 0xE9;
    memcpy(bytes + 1, &rel, 4);
    for (i = 5; i < length; ++i) {
        bytes[i] = 0x90;
    }
    if (!VirtualProtect(at, (SIZE_T)length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)length);
    VirtualProtect(at, (SIZE_T)length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)length);
    return 1;
}

static int cod_install_site(const struct cod_site *s) {
    return cod_write_jmp(s->va, s->length, (const void *)s->stub);
}

#include "cod_vv12.inc"
#include "cod_vv345.inc"

/* ---- Exports --------------------------------------------------------------- */

static int install_state;   /* 0 = not tried, 1 = installed, -1 = refused */

__declspec(dllexport) int __stdcall VvfpCauseInstall(int game, const void *host) {
    if (install_state != 0) {
        return install_state == 1 && game == g_game;
    }
    install_state = -1;
    if (game < 1 || game > 5) {
        return 0;
    }
    g_game = game;
    if (host != NULL && ((const cod_host *)host)->size >= (int)sizeof(cod_host)) {
        g_host = (const cod_host *)host;
    }
    if (game <= 2 ? vv12_install() : v345_install()) {
        install_state = 1;
    }
    return install_state == 1;
}

/* Every frame: bind the graves file to the village's slot, notice deaths no
   site reported, and write the file when something changed. */
__declspec(dllexport) void __stdcall VvfpCauseTick(int game) {
    if (install_state != 1 || game != g_game || g_game > 2) {
        return;
    }
    vv12_tick();
}

/* Start Over erased `slot`: forget its tables before the reset deletes the
   file, so nothing held in memory is written back into the new village. */
__declspec(dllexport) void __stdcall VvfpCauseVillageReset(int game, int slot) {
    if (install_state != 1 || game != g_game || g_game > 2) {
        return;
    }
    if (slot == store.slot) {
        cod_forget();
        store.dirty = 0;
        store.loaded = 0;
        journal_count = 0;
        memset(seen_alive, 0, sizeof seen_alive);
        /* The reset deletes the file next; a fresh load then finds it
           missing and the new village starts empty. */
        vv_sidecar_gate_bind(&store.gate, -1);
        store.slot = 0;
    }
}

#ifdef VVFP_TEST
/* For the TEST build only: drive the tables and the graves file without a
   game image.  Setup takes the place of VvfpCauseInstall (no site is
   written); the others call the same routines the detours call. */
__declspec(dllexport) int __stdcall VvfpCauseTestSetup(int game, const void *host, void *array) {
    if (game < 1 || game > 2) {
        return 0;
    }
    g_game = game;
    g_host = (const cod_host *)host;
    test_array = (unsigned char *)array;
    install_state = 1;
    return 1;
}

__declspec(dllexport) void __stdcall VvfpCauseTestDied(int index, int cause) {
    unsigned char *record = cod_record(index);
    if (record != NULL) {
        cod_died(record, cause);
    }
}

__declspec(dllexport) void __stdcall VvfpCauseTestBuried(int index, int slot) {
    unsigned char *record = cod_record(index);
    if (record != NULL) {
        cod_buried(record, slot);
    }
}

__declspec(dllexport) void __stdcall VvfpCauseTestDecayed(int index) {
    unsigned char *record = cod_record(index);
    if (record != NULL) {
        cod_decayed(record);
    }
}

/* The entry the popup would draw for grave `slot`: 1 with its cause and
   epitaph when it is recorded for the grave the game holds there now. */
__declspec(dllexport) int __stdcall VvfpCauseTestGrave(int slot, int *cause, int *epitaph) {
    const unsigned char *grave = cod_grave(slot);
    if (grave == NULL || !graves[slot].valid
        || graves[slot].fingerprint != cod_grave_fingerprint(grave)) {
        return 0;
    }
    *cause = graves[slot].cause;
    *epitaph = graves[slot].epitaph;
    return 1;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
