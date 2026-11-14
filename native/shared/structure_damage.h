/* The structures an island event may damage, and the only states a damage writes: shared by "VVFP More Island
   Events.dll" (The Rumblings, ceremony_core.inc) and "VVFP Story Upgrades.dll" (the Isola Grand Event Collection's
   "damage" effect, story_graph.inc).  Moved here unchanged from ceremony_games.inc, which documents every address.

   Only structures that are not puzzles (the owner): A New Home's second and third huts; The Lost Children's three
   population huts; The Secret City's three huts and clothing hut; The Tree of Life's three huts, clothing hut, love
   shack, nursery school and hospital; New Believers' three huts, clothing hut and love shack.  A damaged structure
   gets the state a normal construction passes through with that much work done (100%: the new village's state).
   No one is hurt and nobody leaves.

   The includer gives, for The Tree of Life's nursery school (its teacher is let go), its villager records: sd_damage's
   `record` and `records` (NULL / 0 in the other games). */

#ifndef VVFP_STRUCTURE_DAMAGE_H
#define VVFP_STRUCTURE_DAMAGE_H

#define SD_MAX_STRUCTURES 8

typedef int (__fastcall *sd_tc0r)(void *self, void *unused);
typedef void (__fastcall *sd_tc1)(void *self, void *unused, int a);
typedef void (__fastcall *sd_tc2)(void *self, void *unused, int a, int b);
#define SD_TC0(va, self) ((sd_tc0r)(uintptr_t)(va))((void *)(uintptr_t)(self), NULL)
#define SD_TC1(va, self, a) ((sd_tc1)(uintptr_t)(va))((void *)(uintptr_t)(self), NULL, (int)(a))
#define SD_TC2(va, self, a, b) ((sd_tc2)(uintptr_t)(va))((void *)(uintptr_t)(self), NULL, (int)(a), (int)(b))
#define SD_V1_WORLD() (*(unsigned char **)(uintptr_t)0x48AEDCu)
#define SD_V1_ARRAY() (*(unsigned char **)(uintptr_t)0x48B614u)
#define SD_V2_WORLD() (*(unsigned char **)(uintptr_t)0x4997BCu)
#define SD_V2_POOL() (*(unsigned char **)(uintptr_t)0x499F24u)

/* ---- A New Home ------------------------------------------------------------------------------------------------ */

static const char *const SD_V1_NAMES[2] = { "the second population hut", "the third population hut" };
static const unsigned int SD_V1_FLAG[2] = { 0x9FF0u, 0x9FF8u };
static const int SD_V1_DONE_AT[2] = { 400, 600 };

static int sd_v1_finished(int k) {
    unsigned char *world = SD_V1_WORLD();
    return world != NULL && k >= 0 && k < 2 && world[SD_V1_FLAG[k]] != 0;
}

static void sd_v1_damage(int k, int loss) {
    unsigned char *world = SD_V1_WORLD();
    unsigned char *array = SD_V1_ARRAY();
    void *nav, *scene;
    world[SD_V1_FLAG[k]] = 0;
    *(int *)(world + SD_V1_FLAG[k] - 4) = SD_V1_DONE_AT[k] * (100 - loss) / 100;
    nav = *(void **)(array + 0x3E014);
    scene = *(void **)(array + 0x3E024);
    if (nav != NULL) {
        SD_TC0(0x414590u, nav);
    }
    if (scene != NULL) {
        SD_TC0(0x416380u, scene);
    }
}

/* ---- The Lost Children ---------------------------------------------------------------------------------------- */

static const char *const SD_V2_NAMES[3] = {
    "the first population hut", "the second population hut", "the third population hut" };
static const unsigned int SD_V2_FLAG[3] = { 0x2E818u, 0x2E820u, 0x2E828u };
static const int SD_V2_DONE_AT[3] = { 450, 700, 900 };
static const int SD_V2_START[3] = { 205, 0, 0 };

static int sd_v2_finished(int k) {
    unsigned char *world = SD_V2_WORLD();
    return world != NULL && k >= 0 && k < 3 && world[SD_V2_FLAG[k]] != 0;
}

static void sd_v2_damage(int k, int loss) {
    unsigned char *world = SD_V2_WORLD();
    unsigned char *pool = SD_V2_POOL();
    void *scene, *map;
    world[SD_V2_FLAG[k]] = 0;
    *(int *)(world + SD_V2_FLAG[k] - 4) = SD_V2_START[k] + (SD_V2_DONE_AT[k] - SD_V2_START[k]) * (100 - loss) / 100;
    scene = *(void **)(pool + 0xE574D8);
    map = *(void **)(pool + 0xE574E8);
    if (scene != NULL) {
        SD_TC0(0x418660u, scene);
    }
    if (map != NULL) {
        SD_TC0(0x41C1D0u, map);
    }
}

/* ---- The Secret City -------------------------------------------------------------------------------------------- */

static const char *const SD_V3_NAMES[4] = {
    "the first population hut", "the second population hut", "the third population hut", "the clothing hut" };
static const int SD_V3_STATE[4] = { 1, 2, 3, 3 };          /* the new village's (0x4322F0; the clothing hut's 4 -> 3) */
#define SD_V3_PROJECTS 0x594990u
#define SD_V3_HUTS 0x594620u

static int sd_v3_id(int k) {
    return *(const int *)(uintptr_t)(0x49D0D0u + 4u * (unsigned int)k);
}

static int sd_v3_done_at(int id) {
    return *(const int *)(uintptr_t)(0x49D230u + 4u * (unsigned int)id);
}

static int sd_v3_finished(int k) {
    int id = sd_v3_id(k), done_at = sd_v3_done_at(id);
    return done_at >= 1 && *(const int *)(uintptr_t)(SD_V3_PROJECTS + 8u * (unsigned int)id) >= done_at;
}

static void sd_v3_damage(int k, int loss) {
    unsigned char *hut = (unsigned char *)(uintptr_t)(SD_V3_HUTS + 4u + 0x14u * (unsigned int)k);
    int id = sd_v3_id(k), done_at = sd_v3_done_at(id);
    int left = *(const int *)(uintptr_t)(0x49D0E0u + 4u * (unsigned int)SD_V3_STATE[k]);   /* the new village's */
    int start = done_at - left;
    int progress = start + (done_at - start) * (100 - loss) / 100;
    int handle = *(int *)(hut + 0xC);
    if (handle != -1) {
        SD_TC1(0x429B00u, 0x58C338u, handle);
        *(int *)(hut + 0xC) = -1;
    }
    *(int *)(hut + 4) = SD_V3_STATE[k];
    SD_TC2(0x435970u, SD_V3_PROJECTS, id, done_at - progress);
    hut[0] = (unsigned char)(loss < 100);
    *(int *)(hut + 8) = loss < 100 ? left : 0;
}

/* ---- The Tree of Life and New Believers ------------------------------------------------------------------------ */

typedef struct {
    int id;
    unsigned int object;
} sd_building;

static const sd_building SD_V4_BUILDINGS[7] = {
    { 19, 0x4D8588u }, { 20, 0x4D8250u }, { 21, 0x4D8478u }, { 22, 0x4D82D8u }, { 23, 0x4D83F0u },
    { 24, 0x4D8500u }, { 25, 0x4D8360u } };
static const sd_building SD_V5_BUILDINGS[5] = {
    { 19, 0x51DCD8u }, { 20, 0x51DA28u }, { 21, 0x51DBC8u }, { 22, 0x51DAB0u }, { 23, 0x51DB40u } };
static const char *const SD_V45_NAMES[7] = {
    "the first population hut", "the second population hut", "the third population hut", "the clothing hut",
    "the love shack", "the nursery school", "the hospital" };

typedef struct {
    const sd_building *buildings;
    unsigned int projects, done_at, setter, pool, release;
    unsigned int set_state_slot;               /* the building's set state: vtable + this */
} sd_late;

static const sd_late SD_LATE[2] = {
    { SD_V4_BUILDINGS, 0x4D8BF8u, 0x4D8B20u, 0x438A10u, 0x4D69D0u, 0x41D6B0u, 0x40u },
    { SD_V5_BUILDINGS, 0x51E008u, 0x51DF30u, 0x43AF50u, 0x51CF40u, 0x41E710u, 0x44u },
};

static int sd_late_done(const sd_late *l, int id) {
    int done_at = *(const int *)(uintptr_t)(l->done_at + 4u * (unsigned int)id);
    return done_at >= 1 && *(const int *)(uintptr_t)(l->projects + 8u * (unsigned int)id) >= done_at;
}

static int sd_v45_finished(int game, int k) {
    const sd_late *l = &SD_LATE[game == 4 ? 0 : 1];
    const sd_building *b = &l->buildings[k];
    return *(const int *)(uintptr_t)(b->object + 8u) == b->id && sd_late_done(l, b->id);
}

static void sd_v45_damage(int game, int k, int loss, unsigned char *(*record)(int index), int records) {
    const sd_late *l = &SD_LATE[game == 4 ? 0 : 1];
    const sd_building *b = &l->buildings[k];
    unsigned char *o = (unsigned char *)(uintptr_t)b->object;
    int done_at = *(const int *)(uintptr_t)(l->done_at + 4u * (unsigned int)b->id);
    int progress = done_at * (100 - loss) / 100;
    void **vtable = *(void ***)o;
    int handle = *(int *)(o + 0x3C);
    if (handle != -1) {
        SD_TC1(l->release, l->pool, handle);
        *(int *)(o + 0x3C) = -1;
    }
    ((sd_tc1)vtable[l->set_state_slot / 4])(o, NULL, 3);
    if (loss < 100) {
        SD_TC2(l->setter, l->projects, b->id, done_at - progress);
    }
    o[0x30] = (unsigned char)(loss < 100);
    if (k < 3) {
        /* The "3 huts" trophy counts each population hut's completion: still locked, the damaged hut's count is
           taken back, so rebuilding it counts it again (ceremony_games.inc). */
        unsigned char *trophy = (unsigned char *)(uintptr_t)(game == 4 ? 0x4CBB98u + 0x2Du * 12u
                                                                        : 0x4DB358u + 0x31u * 12u);
        if (trophy[0] == 0 && *(int *)(trophy + 4) > 0) {
            --*(int *)(trophy + 4);
        }
    }
    if (game == 4 && b->id == 24 && record != NULL) {
        int i;
        for (i = 0; i < records; ++i) {       /* the nursery school's teacher let go (0x4377BC; the stop 0x437688) */
            unsigned char *r = record(i);
            if (r != NULL && r[0x1CC4] != 0 && *(int *)(r + 0x1C54) == 0x10) {
                *(int *)(r + 0x1C54) = 0;
                SD_TC0(0x468C60u, r);
            }
        }
    }
}

/* ---- The table -------------------------------------------------------------------------------------------------- */

/* The structures game `game` may damage (0 none). */
static int sd_structures(int game) {
    static const int COUNT[6] = { 0, 2, 3, 4, 7, 5 };
    return game >= 1 && game <= 5 ? COUNT[game] : 0;
}

/* Structure `k`'s words for the log ("the second population hut"); "" when there is none. */
static const char *sd_name(int game, int k) {
    if (k < 0 || k >= sd_structures(game)) {
        return "";
    }
    return game == 1 ? SD_V1_NAMES[k] : game == 2 ? SD_V2_NAMES[k] : game == 3 ? SD_V3_NAMES[k] : SD_V45_NAMES[k];
}

/* 1 when structure `k` is finished (so it may be damaged). */
static int sd_finished(int game, int k) {
    if (k < 0 || k >= sd_structures(game)) {
        return 0;
    }
    switch (game) {
    case 1: return sd_v1_finished(k);
    case 2: return sd_v2_finished(k);
    case 3: return sd_v3_finished(k);
    default: return sd_v45_finished(game, k);
    }
}

/* Structure `k` loses `loss` percent (1..100) of its building work. */
static void sd_damage(int game, int k, int loss, unsigned char *(*record)(int index), int records) {
    if (k < 0 || k >= sd_structures(game) || loss < 1 || loss > 100) {
        return;
    }
    switch (game) {
    case 1: sd_v1_damage(k, loss); break;
    case 2: sd_v2_damage(k, loss); break;
    case 3: sd_v3_damage(k, loss); break;
    default: sd_v45_damage(game, k, loss, record, records); break;
    }
}

/* The structure whose words are `words` (case-insensitive, "the " optional), -1 none. */
static int sd_find(int game, const char *words) {
    int k;
    if (words == NULL) {
        return -1;
    }
    for (k = 0; k < sd_structures(game); ++k) {
        const char *name = sd_name(game, k);
        if (lstrcmpiA(name, words) == 0 || (lstrlenA(name) > 4 && lstrcmpiA(name + 4, words) == 0)) {
            return k;
        }
    }
    return -1;
}

#endif
