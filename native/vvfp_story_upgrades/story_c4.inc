/* Custom Island Event: The Tree of Life.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The villager manager is
   0x50E568; record i at 0x50E5AC + i*0x2E3C, 150 records -- or, with 256
   Villagers (Experimental), 0x800000 and 256 records: both are read from the
   executable (native/shared/vv4_villager_table.h), so this one DLL serves
   either build.

   DELIVERY.  The island-event selector 0x418000 has chosen at 0x4180F7 (the
   Pick Island Event site): with a custom event armed, the changes are made
   and the presenter is handed the custom event object (story_objects.inc, a
   copy of the event base vtable 0x48C4EC) instead.  Its strings are ids
   0x32A / 0x32B, The Salty Air's, which have no event object and which no
   code names. */

#include "../shared/vv4_villager_table.h"

static unsigned int c4_table_manager;
static int c4_table_count;

/* The manager and its slot count, as the executable names them; read once.
   The image is not relocatable, so its base is 0x400000. */
static void c4_locate(void) {
    unsigned int rva, slots;
    if (c4_table_manager != 0) {
        return;
    }
    vv4_villager_table((const unsigned char *)(uintptr_t)0x400000u, &rva, &slots);
    c4_table_count = (int)slots;
    c4_table_manager = 0x400000u + rva;
}

static unsigned int c4_manager(void) {
    c4_locate();
    return c4_table_manager;
}

static int c4_count(void) {
    c4_locate();
    return c4_table_count;
}

#define C4_MANAGER c4_manager()
#define C4_RECORDS (c4_manager() + 0x44u)
#define C4_STRIDE 0x2E3Cu
#define C4_COUNT c4_count()
/* The adapter's record count at compile time: the stock table.  The adapter
   handed out at run time (c4_adapter) carries the executable's own count. */
#define C4_STOCK_COUNT 150
#define C4_FOOD 0x4D6DD0u
#define C4_TECH 0x4D6F88u
#define C4_TITLE_ID 0x32A
#define C4_BODY_ID 0x32B
#define C4_STRING_TABLE 0x4DEA20u

static unsigned char *c4_record(int index) {
    if (index < 0 || index >= C4_COUNT) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(C4_RECORDS + (unsigned int)index * C4_STRIDE);
}

/* Active, not a corpse (+0x1CC7), health above 0 -- 0x467980's test. */
static int c4_listed(const unsigned char *r) {
    return r[0x1CC4] != 0 && r[0x1CC7] == 0 && *(const int *)(r + 0x1C40) > 0;
}

/* Records in use (corpses keep theirs until buried) plus the babies on the
   way, against the records (150, or 256). */
static int c4_demand(void) {
    int i;
    int n = 0;
    for (i = 0; i < C4_COUNT; ++i) {
        unsigned char *r = c4_record(i);
        if (r[0x1CC4] != 0) {
            ++n;
            if (*(int *)(r + 0x1C4C) != 0) {
                n += *(int *)(r + 0x1C50);
            }
        }
    }
    return n;
}

static const char *c4_arm_refusal(void) {
    int i;
    for (i = 0; i < C4_COUNT; ++i) {
        unsigned char *r = c4_record(i);
        if (c4_listed(r) && *(int *)(r + 0x1B8C) >= 0x118) {
            return NULL;
        }
    }
    return "An island event needs a living adult in the village.";
}

/* The game's own room predicate 0x468350 (the mode's cap, the housing
   gates) and the physical records. */
static int c4_room(void) {
    return (TC0(0x468350u, C4_MANAGER) & 0xFF) != 0 && c4_demand() < C4_COUNT;
}

static const ce_adapter C4_ADAPTER;
static const ce_adapter *c4_adapter(void);

/* A new villager to the population count 0x467610 (active +0x1CC4, not a
   corpse +0x1CC7, health above 0, its expected babies +0x1C4C / +0x1C50),
   the record count c4_demand and the record search (ce_room_left). */
static const ce_probe_field C4_PROBE[] = {
    { 0x1CC4, 1, 1, 1 }, { 0x1C40, 4, 90, 90 }, { 0x1CC7, 1, 0, 0 }, { 0x1C4C, 4, 0, 0 },
};

/* 0x467D10 (thiscall on the manager: attribute, skill, value, sex, age; ret
   0x14) -- the creator the Daredevil Barrel uses.  Attribute -1 is the
   game's own random; sex 0 male, 1 female. */
static int c4_spawn(const ce_spawn *s) {
    int index;
    if (!c4_room()) {
        return -1;
    }
    index = TC5(0x467D10u, C4_MANAGER, -1, 0, 0, s->sex == STORY_SEX_MALE ? 0 : 1, s->age);
    if (index < 0 || index >= C4_COUNT) {
        return -1;
    }
    ce_apply_spawn_record(c4_adapter(), c4_record(index), s);
    return index;
}

/* The stock island-event death: the villager's task stops and what it holds
   is dropped (0x468C60), then health 0 with cause -1 ("Unknown causes", as
   The Sealed Box 0x415D9E and The Medical Emergency write it) through
   0x46AF00 (thiscall on the health block +0x1C34; ret 8). */
static int c4_kill(int index) {
    unsigned char *r = c4_record(index);
    TC0(0x468C60u, r);
    TC2(0x46AF00u, r + 0x1C34, 0, -1);
    return 1;
}

/* The Sealed Box's disappearance (0x415D91): the same death, then the
   record's active byte cleared, so no corpse or grave is left. */
static int c4_vanish(int index) {
    unsigned char *r = c4_record(index);
    TC0(0x468C60u, r);
    TC2(0x46AF00u, r + 0x1C34, 0, -1);
    r[0x1CC4] = 0;
    return 1;
}

/* Sick is the byte +0x1C48, as the Fungi (0x4153F4) writes it. */
static int c4_sicken(int index) {
    c4_record(index)[0x1C48] = 1;
    return 1;
}

/* A pregnancy through the conception routine 0x45E7B0 (thiscall on the
   carrier: father attribute, skill, value, father's name, head, body,
   forced; ret 0x1C) with forced = 1, which writes every pregnancy field
   (+0x1C4C, +0x1C04..+0x1C0C, the father's name, head and body, the
   litter) without its own room check, log and Babies Made, so the litter
   can be the chosen one:
     the rolled litter's Twins [0x4D6E08] / Triplets [0x4D6E0C] count is
     taken back, the chosen litter set (each baby only while there is room)
     and counted, Babies Made [0x4D6DE8] += babies, the "baby / twins /
     triplets" achievement (0x412F90, ids 0x14-0x16) as forced = 0 gives it,
     and the parentage log as the routine's own trampoline writes it.
   An unknown father is "Unknown" with the carrier's own head and body.
   There is no sex or age check in the conception or the delivery (0x4687E4)
   (the owner: any villager may be made pregnant). */
static int c4_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *r = c4_record(index);
    unsigned char *f = father >= 0 ? c4_record(father) : NULL;
    const unsigned char *source = f != NULL ? f : r;
    int rolled;
    int babies;
    if (*(int *)(r + 0x1C4C) != 0) {
        ce_refuse(result, CE_WHY_EXPECTING);
        return 0;
    }
    if (!c4_room()) {
        result->no_room_babies += litter;
        return 0;
    }
    TC7(0x45E7B0u, r, *(int *)(source + 0x1B98), 0, 0,
        (int)(uintptr_t)(f != NULL ? (const char *)(f + 0x1B9C) : "Unknown"),
        *(int *)(source + 0x1BB8), *(int *)(source + 0x1BBC), 1);
    /* The routine marks the pregnancy with the carrier's processed age
       (+0x1C3C, copied at 0x45E830); a newborn carrier's is 0, which reads as
       "not expecting", so 1 then, as New Believers' does. */
    if (*(int *)(r + 0x1C4C) == 0) {
        *(int *)(r + 0x1C4C) = 1;
    }
    rolled = *(int *)(r + 0x1C50);
    if (rolled == 2) {
        --*(int *)(uintptr_t)0x4D6E08u;
    } else if (rolled == 3) {
        --*(int *)(uintptr_t)0x4D6E0Cu;
    }
    *(int *)(r + 0x1C50) = 1;
    babies = 1;
    while (babies < litter && c4_room()) {
        ++babies;
        *(int *)(r + 0x1C50) = babies;
    }
    result->no_room_babies += litter - babies;
    if (babies == 2) {
        ++*(int *)(uintptr_t)0x4D6E08u;
    } else if (babies == 3) {
        ++*(int *)(uintptr_t)0x4D6E0Cu;
    }
    *(int *)(uintptr_t)0x4D6DE8u += babies;
    TC2(0x412F90u, 0x4CBB98u, 0x13 + babies, 1);
    story_log_conception(4, (const void *)(uintptr_t)C4_MANAGER, r, f);
    return babies;
}

/* Every action is started by the game's do-action 0x45DEC0 (thiscall on
   the record: action id, a pointer to its parameter; ret 8) after the stop
   0x468C60, exactly as the game's own group starter 0x4671A0 does; these
   read no parameter.  Offered: the ones that only look or end by
   themselves; the jobs that give food, tech or skill practice say so.
   Never: puzzle actions, burial, pickups, new clothes, cooking, building,
   games that stop other villagers, or an action no stock code starts. */
static const ce_action C4_BEHAVIOURS[] = {
    { "Stops what they are doing", ACT_STOP, 0, 0 },
    { "Recovers fully (cured, full health)", ACT_RECOVER, 0, 0 },
    { "Dances", ACT_DO, 0, 0x7 },
    { "Dances (another dance)", ACT_DO, 0, 0x2D },
    { "Rain dancing", ACT_DO, 0, 0xA },
    { "Celebrates Isola Day", ACT_DO, 0, 0x28 },
    { "Celebrates the Banyan Festival", ACT_DO, 0, 0xC1 },
    { "Relaxes", ACT_DO, 0, 0xB },
    { "Relaxes at the beach", ACT_DO, 0, 0x16 },
    { "Reflects", ACT_DO, 0, 0x17 },
    { "Watches the clouds", ACT_DO, 0, 0x13 },
    { "Enjoys the pond", ACT_DO, 0, 0x18 },
    { "Swims in the ocean", ACT_DO, 0, 0xC3 },
    { "Takes a shower", ACT_DO, 0, 0xB9 },
    { "Cools their feet in the stream", ACT_DO, 0, 0x14 },
    { "Drinks from the stream", ACT_DO, 0, 0x86 },
    { "Gets a drink", ACT_DO, 0, 0x15 },
    { "Drinks the rain", ACT_DO, 0, 0x24 },
    { "Gets out of the rain", ACT_DO, 0, 0x44 },
    { "Cleans up after the rain", ACT_DO, 0, 0x62 },
    { "Washes the laundry", ACT_DO, 0, 0x25 },
    { "Honors the dead", ACT_DO, 0, 0x9 },
    { "Admires a lei in the tree", ACT_DO, 0, 0x9E },
    { "Wanders around", ACT_DO, 0, 0x30 },
    { "Unsure what to do", ACT_DO, 0, 0x42 },
    { "Jumpy!", ACT_DO, 0, 0x32 },
    { "Nature is calling!", ACT_DO, 0, 0x33 },
    { "A little bit lonely", ACT_DO, 0, 0x3A },
    { "Sits", ACT_DO, 0, 0x22 },
    { "Shakes their head", ACT_DO, 0, 0x20 },
    { "Not feeling well (only looks it)", ACT_DO, 0, 0x1B },
    { "Feels faint (only looks it)", ACT_DO, 0, 0x48 },
    { "Tries to get warm", ACT_DO, 0, 0x49 },
    { "Tries to cool off", ACT_DO, 0, 0x4A },
    { "Itchy", ACT_DO, 0, 0x4B },
    { "Needs to lie down", ACT_DO, 0, 0x4E },
    { "Needs to sit down", ACT_DO, 0, 0x4F },
    { "Has an epiphany", ACT_DO, 0, 0x50 },
    { "In a trance", ACT_DO, 0, 0x51 },
    { "Hic!", ACT_DO, 0, 0x5A },
    { "That tasted soapy!", ACT_DO, 0, 0x59 },
    { "Runs away from wasps!", ACT_DO, 0, 0xC6 },
    { "Curious about the carvings", ACT_DO, 0, 0xC8 },
    { "Curious about the majestic fish statue", ACT_DO, 0, 0xCA },
    { "Curious about the hole in the tree", ACT_DO, 0, 0xC7 },
    { "Tells a story", ACT_DO, 0, 0x34 },
    { "Listens to a story (children)", ACT_DO, 0, 0x35 },
    { "Watches people work (children)", ACT_DO, 0, 0x3D },
    { "Runs around (children)", ACT_DO, 0, 0x46 },
    { "Plays in puddles (children)", ACT_DO, 0, 0x58 },
    { "Plays in the dirt (children)", ACT_DO, 0, 0x5F },
    { "Makes sandcastles (children)", ACT_DO, 0, 0x61 },
    { "Races! (children)", ACT_DO, 0, 0xBF },
    { "Researches (Research practice, tech points)", ACT_DO, 0, 0x2 },
    { "Harvests blackberries (Farming practice, food)", ACT_DO, 0, 0x63 },
    { "Does exercise (Building practice)", ACT_DO, 0, 0x47 },
    { "Eats (uses food)", ACT_DO, 0, 0x2C },
};

/* The stop routine 0x468C60 (thiscall on the record), then the action; the
   Origins Full Heal's cure: sick 0 and 0x46AF00(100, -1). */
static int c4_behave(int index, int behaviour) {
    static const int no_parameter[8];
    unsigned char *r = c4_record(index);
    const ce_action *act;
    if (behaviour < 0 || behaviour >= (int)(sizeof C4_BEHAVIOURS / sizeof C4_BEHAVIOURS[0])) {
        return 0;
    }
    act = &C4_BEHAVIOURS[behaviour];
    if (act->kind == ACT_RECOVER) {
        r[0x1C48] = 0;
        TC2(0x46AF00u, r + 0x1C34, 100, -1);
    }
    TC0(0x468C60u, r);
    if (act->kind == ACT_DO) {
        TC2(0x45DEC0u, r, act->arg, (int)(uintptr_t)no_parameter);
    }
    return 1;
}

/* ---- Pregnancy: none, a different number of babies, the father --------- */

/* "0 babies": the pregnancy +0x1C4C and its litter +0x1C50 cleared, then
   the stop 0x468C60, which also releases the place the pregnancy held
   (0x45ED50(-1)), as the delivery does.  Babies Made is left as counted. */
static int c4_cancel(int index) {
    unsigned char *r = c4_record(index);
    if (*(int *)(r + 0x1C4C) == 0) {
        return 0;
    }
    *(int *)(r + 0x1C4C) = 0;
    *(int *)(r + 0x1C50) = 0;
    TC0(0x468C60u, r);
    return 1;
}

/* The litter +0x1C50 (0 or 1 one baby, 2, 3: the delivery 0x4688CD tests
   > 1 and == 3); each added baby only while there is room. */
static int c4_relitter(int index, int litter, ce_result *result) {
    unsigned char *r = c4_record(index);
    int field = *(int *)(r + 0x1C50);
    int babies = field >= 3 ? 3 : field == 2 ? 2 : 1;
    int added = 0;
    if (litter < babies) {
        *(int *)(r + 0x1C50) = litter;
        return 0;
    }
    while (babies < litter && c4_room()) {
        ++babies;
        ++added;
        *(int *)(r + 0x1C50) = babies;
    }
    result->no_room_babies += litter - babies;
    return added;
}

/* The father the delivery hands the creator: name +0x1C10 (0x18 bytes),
   head +0x1C30, body +0x1C2C. */
static int c4_unborn(int index, const ce_change *c) {
    unsigned char *r = c4_record(index);
    if ((c->unborn_head != CE_KEEP && (c->unborn_head < 0 || c->unborn_head >= 30))
        || (c->unborn_body != CE_KEEP && (c->unborn_body < 0 || c->unborn_body >= 30))) {
        return 0;
    }
    if (c->unborn_name[0] != '\0' && !ce_write_name(r + 0x1C10, 0x18, c->unborn_name)) {
        return 0;
    }
    if (c->unborn_head != CE_KEEP) *(int *)(r + 0x1C30) = c->unborn_head;
    if (c->unborn_body != CE_KEEP) *(int *)(r + 0x1C2C) = c->unborn_body;
    return 1;
}

/* ---- Revive ------------------------------------------------------------- */

/* A skeleton: present, not a mausoleum ghost (+0x1CC7, which the game's own
   burial and decay skip), health 0 or less. */
static int c4_skeleton(const unsigned char *r) {
    return r[0x1CC4] != 0 && r[0x1CC7] == 0 && *(const int *)(r + 0x1C40) <= 0;
}

/* Health through the game's own arbiter 0x46AF00 (cause back to -1), the
   last-update time +0x1C38 to the game clock 0x403750 (on 0x41FE70()),
   then the stop.  The body keeps its own record, so no room is needed
   (the owner, 2026-10-06: a revive "should just set skeletons' health ...
   bypassing that problem" -- a full village of records included). */
static int c4_revive(int index, int health, int cure) {
    unsigned char *r = c4_record(index);
    TC2(0x46AF00u, r + 0x1C34, health, -1);
    *(int *)(r + 0x1C38) = TC0(0x403750u, ((getter_fn)(uintptr_t)0x41FE70u)());
    if (cure) {
        r[0x1C48] = 0;
    }
    TC0(0x468C60u, r);
    return 1;
}

static const char *const C4_VILLAGE[] = {
    "Rain begins (as in The Rainy Season)",
    "The weather clears",
};

/* The weather, 0x46BC30 (thiscall on 0x6C461C: type, duration 0 = the
   game's own random length; ret 8): type 2 is the rain The Rainy Season and
   The Monsoon set, type 0 the clear weather the scheduler returns to. */
static int c4_village(int which) {
    switch (which) {
    case 0: TC2(0x46BC30u, 0x6C461Cu, 2, 0); return 1;
    case 1: TC2(0x46BC30u, 0x6C461Cu, 0, 0); return 1;
    default: return 0;
    }
}

static int c4_food(void) { return *(int *)(uintptr_t)C4_FOOD; }
static int c4_tech(void) { return *(int *)(uintptr_t)C4_TECH; }

/* Written directly: the food adder 0x41D920 multiplies a gain by Food
   Mastery and both adders are detoured through the Origins doubler. */
static void c4_change_food(int op, int amount) {
    int after;
    ce_amount(op, amount, c4_food(), &after);
    *(int *)(uintptr_t)C4_FOOD = after;
}

static void c4_change_tech(int op, int amount) {
    int after;
    ce_amount(op, amount, c4_tech(), &after);
    *(int *)(uintptr_t)C4_TECH = after;
}

/* The berry bushes, [world+0x170F8], to their full 1000 (the game's own
   ceiling, 0x4203CA; A Closer Look adds to them, 0x414B30). */
static int c4_refill(void) {
    unsigned char *world = *(unsigned char **)(uintptr_t)VV4_WORLD_GLOBAL;
    if (world == NULL) {
        return 0;
    }
    if (*(int *)(world + 0x170F8) < 1000) {
        *(int *)(world + 0x170F8) = 1000;
    }
    return 1;
}

/* ---- Food sources and stores --------------------------------------------- */

/* The blackberries [world+0x170F8] (the game keeps them 0..1000; seen live:
   the bushes follow within a second), the cutting tools [0x4D8618] (the
   tool object's count, 0..6 as making and using them keep it) and the bars
   of soap [0x4D8D98] (the soap object's count; making adds 3 with no cap,
   99 here).  Both counts are saved by their objects and redrawn every
   frame. */
static const ce_value_def C4_VALUES[] = {
    { "Blackberries", 0, 1000,
      "One store for every bush; the game's own ceiling is 1000. The fruit trees and "
      "fishing have no store: they never run out." },
    { "Cutting tools", 0, 6,
      "The game keeps 0-6. Whether villagers use them before The Cutting Tool is solved "
      "was not seen in play." },
    { "Bars of soap", 0, 99,
      "Making soap adds 3 at a time. Whether villagers use it before Soap Invented is "
      "solved was not seen in play." },
};

static unsigned char *c4_world(void) {
    return *(unsigned char **)(uintptr_t)VV4_WORLD_GLOBAL;
}

static int c4_value_get(int which) {
    unsigned char *world = c4_world();
    switch (which) {
    case 0: return world != NULL ? *(int *)(world + 0x170F8) : -1;
    case 1: return *(int *)(uintptr_t)0x4D8618u;
    case 2: return *(int *)(uintptr_t)0x4D8D98u;
    default: return -1;
    }
}

static int c4_value_set(int which, int amount) {
    if (c4_value_get(which) < 0) {
        return 0;
    }
    switch (which) {
    case 0: *(int *)(c4_world() + 0x170F8) = amount; return 1;
    case 1: *(int *)(uintptr_t)0x4D8618u = amount; return 1;
    case 2: *(int *)(uintptr_t)0x4D8D98u = amount; return 1;
    default: return 0;
    }
}

/* ---- Puzzles ---------------------------------------------------------------

   Puzzle i is {progress, solve time} at 0x4D8BF8 + 8i, solved at the
   threshold 0x4D8B20[i] (filled when the game starts).  Solved goes through
   the game's own Advance 0x438A30 (thiscall on 0x4D8BF8, the id; ret 4) from
   one short of the threshold, as the puzzle's last step does: it stamps the
   solve time and runs the puzzle object's completion (its trophies too);
   where the object keeps its own state, that state is written first as the
   puzzle's steps leave it (seen live for The Stream: written alone, the
   stream stays dry).  Unsolved is the game's own Reset 0x438710 (progress 0
   and the object's own reset) and the solve time 0, with the terrain
   rebuilt (0x46D090 on 0x705148) where the puzzle shapes it. */
#define C4P_REFRESH 1

static const ce_puzzle_def C4_PUZZLE_DEFS[] = {
    { "The Cutting Tool", 1, 1, "Unsolved, the tools made are gone too." },
    { "The Stream", 1, 1, NULL },
    { "Boiling Water", 1, 1, NULL },
    { "Soap Invented", 1, 1, "Unsolved, the soap made is gone too." },
    { "The Butterflies", 1, 1, "Solving it again needs The Stream solved." },
    { "The Frog Rescue", 1, 1,
      "Unsolved, frogs already out may stay until the village is loaded again." },
    { "The Cooking Pit", 1, 0,
      "Not offered as unsolved: the game's reset leaves the fruit drawn on the pits and "
      "never puts the vines back." },
    { "Cloth Invented", 1, 1, "Unsolved, the cloth made is gone too." },
    { "The Nursery School", 1, 1, NULL },
    { "The Mossy Rocks", 1, 1, NULL },
    { "The Grand Feast", 1, 1, NULL },
    { "Fishing Nets", 1, 1, NULL },
    { "Pruning the Tree", 1, 1, NULL },
    { "Honoring the Tree", 1, 1, NULL },
    { "Purify Tree", 1, 1, NULL },
    { "Decorating the Tree", 1, 1, NULL },
};

#define C4_PUZZLE_COUNT ((int)(sizeof C4_PUZZLE_DEFS / sizeof C4_PUZZLE_DEFS[0]))
#define C4_PUZZLE_ENTRY(id) ((int *)(uintptr_t)(0x4D8BF8u + 8u * (unsigned int)(id)))
#define C4_THRESHOLD(id) (*(int *)(uintptr_t)(0x4D8B20u + 4u * (unsigned int)(id)))

static int c4_puzzle_solved(int which) {
    if (which < 0 || which >= C4_PUZZLE_COUNT) {
        return 0;
    }
    /* An empty table (before the game fills it) reads as unsolved, so the
       write that follows is refused rather than skipped as done. */
    return C4_THRESHOLD(which) >= 1 && C4_PUZZLE_ENTRY(which)[0] >= C4_THRESHOLD(which);
}

/* What each puzzle's own steps leave on its object before the last one. */
static void c4_puzzle_objects(int which) {
    int f;
    switch (which) {
    case 1:                            /* The Stream: debris cleared, flowing */
        *(int *)(uintptr_t)0x4D8CF4u = 1;
        *(int *)(uintptr_t)0x4D8D04u = 0;
        break;
    case 4:                            /* The Butterflies: the last stage */
        *(int *)(uintptr_t)0x4D8CD0u = 3;
        break;
    case 6:                            /* The Cooking Pit: dug, vines cleared */
        *(int *)(uintptr_t)0x4D8A8Cu = 0;
        *(unsigned char *)(uintptr_t)0x4D8A89u = 1;
        *(unsigned char *)(uintptr_t)0x4D8A8Au = 1;
        *(unsigned char *)(uintptr_t)0x4D8A8Bu = 1;
        for (f = 0x14; f <= 0x17; ++f) {
            TC1(0x46D610u, 0x705148u, f);
        }
        *(int *)(uintptr_t)0x4D8724u = 3;
        break;
    case 11:                           /* Fishing Nets: mended */
        *(int *)(uintptr_t)0x4D86B0u = 0;
        *(int *)(uintptr_t)0x4D86B4u = 6;
        *(int *)(uintptr_t)0x4D86ACu = 4;
        break;
    case 12:                           /* Pruning the Tree: the last stage */
        *(int *)(uintptr_t)0x4D8AF4u = 3;
        break;
    default:
        break;
    }
}

static int c4_puzzle_set(int which, int solved) {
    int *entry;
    int threshold;
    if (which < 0 || which >= C4_PUZZLE_COUNT) {
        return 0;
    }
    entry = C4_PUZZLE_ENTRY(which);
    threshold = C4_THRESHOLD(which);
    if (threshold < 1) {
        return 0;                      /* the table is not filled yet */
    }
    if (solved) {
        c4_puzzle_objects(which);
        entry[0] = threshold - 1;
        TC1(0x438A30u, 0x4D8BF8u, which);
        if (which == 6) {
            TC0(0x433D80u, 0x4D8720u);     /* the fruit placed on the pits now */
        }
        return entry[0] >= threshold;
    }
    TC1(0x438710u, 0x4D8BF8u, which);
    entry[0] = 0;
    entry[1] = 0;
    if (which == 1 || which == 11) {
        TC0(0x46D090u, 0x705148u);
    }
    return 1;
}

static int c4_parents_supported(void) {
    return 1;
}

static int c4_set_parents(int index, const ce_change *c) {
    return ce_set_record_parents(c4_record(index), 0x1BC0, 0x1BD9, 0x19, 23, 0x1BF4, 0x1BF8, 0x1BFC,
                                 0x1C00, 30, 30, c);
}

static const char *const C4_SKILLS[] = { "Farming", "Parenting", "Healing", "Research", "Building" };

typedef int (__cdecl *c4_rand_fn)(int bound);

/* The game's own rand(bound) 0x4036D0 (cdecl, 0..bound-1). */
static int c4_rand_below(int n) {
    return ((c4_rand_fn)(uintptr_t)0x4036D0u)(n);
}

static const ce_adapter C4_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_VILLAGE | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY | CAP_VALUES
        | CAP_PUZZLES | CAP_CANCEL | CAP_RELITTER | CAP_UNBORN | CAP_REVIVE | CAP_CHOICE,
    "The Tree of Life",
    0x118, 1600,
    C4_STOCK_COUNT, 0x19, 23,
    0x1B9C, 0x1B90, 0x1B8C, 0x1BB8, 0x1BBC, 0x1E60, 0x1E6C, 0x1C5C,
    0, 1,
    3, 79,
    STORY_PREFERENCES_79,
    30, 30,
    5, 1, C4_SKILLS,
    0x1BC0, 0x1BD9, 0x1BF4, 0x1BF8, 0x1BFC, 0x1C00,
    NULL, 0,
    C4_BEHAVIOURS, (int)(sizeof C4_BEHAVIOURS / sizeof C4_BEHAVIOURS[0]),
    C4_VILLAGE, 2,
    "Not in The Tree of Life:\r\n\r\n"
    "- Refill and amounts: the fruit trees and fishing have no store (they never run "
    "out).\r\n"
    "- Special statuses: Scholar and Elderly are worked out from skills and age, and "
    "\"Tribal Chief\" is never shown, so there is none to give.\r\n"
    "- The Cooking Pit as unsolved (see its note), and the stew pot, the cooks, the fire "
    "and the huts as puzzles (they are not puzzles).\r\n"
    "- The unborn baby's starting skill: what the baby does with it at birth was not "
    "traced to the end, so only the father's name and looks are offered.\r\n"
    "- Actions that solve or advance a puzzle, burying, picking things up, new clothes, "
    "cooking, building and games that stop other villagers.\r\n"
    "- Revive: the mausoleum's ghosts, buried villagers (their record is gone) and "
    "skeletons that have already crumbled away.\r\n"
    "- Weather other than rain and clear: the other types are not identified.\r\n"
    "- Golden Child, faction, totems: The Tree of Life has none.",
    48, 14, 30, 1,
    "Refills the berry bushes.",
    "Your village gains %d food.", "Your village has lost %d food.",
    "Your village has gained %d tech points.", "Your village has lost %d tech points.",
    c4_record, c4_listed, c4_arm_refusal, c4_room, c4_spawn, c4_kill, c4_vanish, c4_sicken,
    c4_conceive, NULL, c4_behave, c4_village, c4_food, c4_tech, c4_change_food, c4_change_tech,
    c4_refill, c4_parents_supported, c4_set_parents,
    C4_VALUES, 3, c4_value_get, c4_value_set,
    C4_PUZZLE_DEFS, C4_PUZZLE_COUNT, c4_puzzle_solved, c4_puzzle_set,
    c4_cancel, c4_relitter, c4_unborn,
    c4_skeleton, c4_revive,
    0, 0x1C4C,
    /* The two-choice popup (0x417790): as The Secret City's -- 48 characters,
       11 lines (the tallest stock two-choice text), the title above the
       result, labels of 34 characters (the longest stock). */
    48, 11, 48, 11, 0, 34, c4_rand_below, NULL, NULL,
    C4_PROBE, (int)(sizeof C4_PROBE / sizeof C4_PROBE[0]),
    NULL, NULL
};

/* ---- Delivery ----------------------------------------------------------- */

static int __fastcall c4_title_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C4_TITLE_ID;
}

static int __fastcall c4_body_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C4_BODY_ID;
}

/* The event base (0x48C4EC, whose condition and string ids are pure
   virtual) with: +0x04 always possible, +0x08 / +0x0C the custom ids; its
   own apply (+0x30) and prepare (+0x38) already do nothing. */
static void *c4_custom_object(void) {
    static const int slots[3] = { 1, 2, 3 };
    void *functions[3];
    if (ce_deliver_object(4, C4_STRING_TABLE, C4_TITLE_ID, C4_BODY_ID, 1) == NULL) {
        return NULL;
    }
    functions[0] = (void *)ce_object_true;
    functions[1] = (void *)c4_title_id;
    functions[2] = (void *)c4_body_id;
    return ce_build_object(0x48C4ECu, slots, functions, 3);
}

/* A question (story_objects.inc): a copy of the first two-choice event's
   vtable (0x48CB64) with The Salty Air's ids, featuring the picked or a random living villager. */
static void *c4_choice_object(void) {
    return choice_object(4, C4_STRING_TABLE, C4_TITLE_ID, C4_BODY_ID, 1, 0x48CB64u,
                         (void *)c4_title_id);
}

/* ---- Title ---------------------------------------------------------------

   The HUD 0x440150 builds the selected villager's title in [esp+0x28] for
   the record at [esp+0x10]; every branch reaches 0x4404D9 `lea ecx,
   [esp+0x28]; push ecx` before setting the label. */
static void __cdecl c4_title(const unsigned char *record, char *buffer) {
    const char *custom = titles_lookup(4, record);
    if (custom != NULL) {
        lstrcpynA(buffer, custom, VV_TITLE_BYTES);
    }
}

__declspec(naked) static void c4_title_stub(void) {
    __asm {
        pushad
        mov eax, dword ptr [esp + 0x20 + 0x10]
        lea ecx, [esp + 0x20 + 0x28]
        push ecx
        push eax
        call c4_title
        add esp, 8
        popad
        lea ecx, [esp + 0x28]
        push ecx
        push 0x4404DE
        ret
    }
}

/* C4_ADAPTER with the executable's own slot count (150, or 256 with 256
   Villagers). */
static const ce_adapter *c4_adapter(void) {
    static ce_adapter adapter;
    static int ready;
    if (!ready) {
        adapter = C4_ADAPTER;
        adapter.record_count = c4_count();
        ready = 1;
    }
    return &adapter;
}
