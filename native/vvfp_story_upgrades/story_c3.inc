/* Custom Island Event: The Secret City.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The village is
   0x59E110; record i at 0x59E124 + i*0x1F8C, 150 records.

   DELIVERY.  The island-event selector 0x419B30 has chosen at 0x419BDB (the
   Pick Island Event site): with a custom event armed, the changes are made
   and the presenter is handed the custom event object (story_objects.inc,
   a copy of The Fog's simple-event vtable 0x47E600) instead.  Its strings
   are ids 0x4CB / 0x4CC, the two string-table slots (0x592730) the game
   leaves empty and no code or string names.  The Origins Barrel's call of
   the same selector (every slot the barrel) never takes it. */

#define C3_VILLAGE 0x59E110u
#define C3_RECORDS 0x59E124u
#define C3_STRIDE 0x1F8Cu
#define C3_COUNT 150
#define C3_FOOD 0x582490u
#define C3_TECH 0x582644u
#define C3_TITLE_ID 0x4CB
#define C3_BODY_ID 0x4CC
#define C3_STRING_TABLE 0x592730u

static unsigned char *c3_record(int index) {
    if (index < 0 || index >= C3_COUNT) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(C3_RECORDS + (unsigned int)index * C3_STRIDE);
}

static int c3_listed(const unsigned char *r) {
    return r[0xF10] != 0 && *(const int *)(r + 0xE78) > 0;
}

/* Records in use plus the babies on the way: the 150 records are the
   physical limit, which the game's room predicate does not count. */
static int c3_demand(void) {
    int i;
    int n = 0;
    for (i = 0; i < C3_COUNT; ++i) {
        unsigned char *r = c3_record(i);
        if (r[0xF10] != 0) {
            ++n;
            if (*(int *)(r + 0xE8C) != 0) {
                n += *(int *)(r + 0xE90);
            }
        }
    }
    return n;
}

static const char *c3_arm_refusal(void) {
    int i;
    for (i = 0; i < C3_COUNT; ++i) {
        unsigned char *r = c3_record(i);
        if (c3_listed(r) && *(int *)(r + 0xDC4) >= 0x118) {
            return NULL;
        }
    }
    return "An island event needs a living adult in the village.";
}

/* The game's own room predicate 0x45FE30 (the mode's cap, the building
   gates) and the 150 records. */
static int c3_room(void) {
    return (TC0(0x45FE30u, C3_VILLAGE) & 0xFF) != 0 && c3_demand() < C3_COUNT;
}

static const ce_adapter C3_ADAPTER;

/* 0x45FF50 (thiscall on the village: family, skill, value, sex, age; ret
   0x14) -- the creator The Canoe and the Barrel use.  Family -1 is the
   game's own random; sex 0 male, 1 female. */
static int c3_spawn(const ce_spawn *s) {
    int index;
    if (!c3_room()) {
        return -1;
    }
    index = TC5(0x45FF50u, C3_VILLAGE, -1, 0, 0, s->sex == STORY_SEX_MALE ? 0 : 1, s->age);
    if (index < 0 || index >= C3_COUNT) {
        return -1;
    }
    ce_apply_spawn_record(&C3_ADAPTER, c3_record(index), s);
    return index;
}

/* The Medical Emergency's death (0x4172D9): 0x462670 (thiscall on the
   record's health block +0xE6C: value 0, cause -1). */
static int c3_kill(int index) {
    TC2(0x462670u, c3_record(index) + 0xE6C, 0, -1);
    return 1;
}

/* The Tsunami and The Low Tide (0x45D990 -> 0x45D9D1) clear the active byte;
   the selection is dropped first (0x45FCC0) when it is this villager, as the
   burial does. */
static int c3_vanish(int index) {
    unsigned char *r = c3_record(index);
    if (r[0xF11] != 0) {
        TC0(0x45FCC0u, C3_VILLAGE);
    }
    r[0xF10] = 0;
    return 1;
}

/* Sick is the byte +0xE89, as Bed Bugs (0x416E40) writes it. */
static int c3_sicken(int index) {
    c3_record(index)[0xE89] = 1;
    return 1;
}

/* A pregnancy, written as the conception routine 0x455AB0 writes it:
     +0xE8C = the carrier's processed age (+0xE74);
     +0xE44 = the father's family (+0xDD0);
     +0xE3C / +0xE40 = the inherited skill (none: 0 / 0);
     +0xE48 = the father's name, +0xE68 / +0xE64 his head and body;
     +0xE90 = the babies (1, 2 or 3);
   Babies Made [0x5824A8] += babies, Twins [0x5824C8] / Triplets [0x5824CC]
   +1; the carried-baby pose through the stop routine 0x460F70; and the
   parentage log with the father's record.  An unknown father is "Unknown"
   with the carrier's own head and body.  Each baby only while there is
   room; there is no sex check in the delivery (0x460341). */
static int c3_conceive(int index, int litter, int father, ce_result *result) {
    unsigned char *r = c3_record(index);
    unsigned char *f = father >= 0 ? c3_record(father) : NULL;
    int babies;
    int age;
    if (*(int *)(r + 0xE8C) != 0 || *(int *)(r + 0xDC4) < 360) {
        ++result->refused;
        return 0;
    }
    if (!c3_room()) {
        result->no_room_babies += litter;
        return 0;
    }
    age = *(int *)(r + 0xE74);
    *(int *)(r + 0xE44) = *(int *)((f != NULL ? f : r) + 0xDD0);
    *(int *)(r + 0xE3C) = 0;
    *(int *)(r + 0xE40) = 0;
    ce_write_name(r + 0xE48, 0x18, f != NULL ? (const char *)(f + 0xDD4) : "Unknown");
    *(int *)(r + 0xE68) = *(int *)((f != NULL ? f : r) + 0xDF0);
    *(int *)(r + 0xE64) = *(int *)((f != NULL ? f : r) + 0xDF4);
    *(int *)(r + 0xE90) = 1;
    *(int *)(r + 0xE8C) = age != 0 ? age : 1;
    babies = 1;
    while (babies < litter && c3_room()) {
        ++babies;
        *(int *)(r + 0xE90) = babies;
    }
    result->no_room_babies += litter - babies;
    *(int *)(uintptr_t)0x5824A8u += babies;
    if (babies == 2) {
        ++*(int *)(uintptr_t)0x5824C8u;
    } else if (babies == 3) {
        ++*(int *)(uintptr_t)0x5824CCu;
    }
    TC1(0x460F70u, r, (int)(uintptr_t)r);
    story_log_conception(3, (const void *)(uintptr_t)C3_VILLAGE, r, f);
    return babies;
}

/* Every action is started by the game's do-action 0x455570 (thiscall on
   the record: action id, a pointer to eight argument dwords; ret 8), after
   the stop 0x460F70, as every stock caller does; these ignore the
   arguments.  Offered: the ones that only look or end by themselves (the
   island events', the idle choosers', the potions' looks); the jobs that
   give food, tech or skill practice say so.  Never: puzzle actions, burial,
   pickups, new clothes, lessons and games that stop other villagers, the
   chief's own powers, or an action no stock code starts. */
static const ce_action C3_BEHAVIOURS[] = {
    { "Stops what they are doing", ACT_STOP, 0, 0 },
    { "Recovers fully (cured, full health)", ACT_RECOVER, 0, 0 },
    { "Dances", ACT_DO, 0, 8 },
    { "Dances (another dance)", ACT_DO, 0, 85 },
    { "Secretly practices a dance", ACT_DO, 0, 181 },
    { "Performs the ceremonial dance", ACT_DO, 0, 67 },
    { "Rain dancing", ACT_DO, 0, 12 },
    { "Celebrates Isola Day", ACT_DO, 0, 66 },
    { "Relaxes", ACT_DO, 0, 13 },
    { "Relaxes at the beach", ACT_DO, 0, 21 },
    { "Reflects", ACT_DO, 0, 22 },
    { "Watches the clouds", ACT_DO, 0, 18 },
    { "Goes swimming", ACT_DO, 0, 1 },
    { "Enjoys the bath", ACT_DO, 0, 23 },
    { "Bathes", ACT_DO, 0, 143 },
    { "Cools their feet in the stream", ACT_DO, 0, 19 },
    { "Washes their face", ACT_DO, 0, 140 },
    { "Washes their hands", ACT_DO, 0, 141 },
    { "Gets a drink", ACT_DO, 0, 144 },
    { "Drinks the rain", ACT_DO, 0, 60 },
    { "Gets out of the rain", ACT_DO, 0, 142 },
    { "Cleans up after the rain", ACT_DO, 0, 196 },
    { "Washes the laundry", ACT_DO, 0, 61 },
    { "Looks at the fishies", ACT_DO, 0, 146 },
    { "Looks at the fire", ACT_DO, 0, 34 },
    { "Honors the dead", ACT_DO, 0, 10 },
    { "Stomps ants", ACT_DO, 0, 68 },
    { "Hides in a hut", ACT_DO, 0, 69 },
    { "Acts sinister", ACT_DO, 0, 62 },
    { "Jumpy!", ACT_DO, 0, 93 },
    { "Nature is calling!", ACT_DO, 0, 94 },
    { "A little bit lonely", ACT_DO, 0, 102 },
    { "Unsure what to do (wanders)", ACT_DO, 0, 123 },
    { "Sits", ACT_DO, 0, 52 },
    { "Shakes their head", ACT_DO, 0, 49 },
    { "Not feeling well (only looks it)", ACT_DO, 0, 45 },
    { "Recovers at the hospital", ACT_DO, 0, 97 },
    { "Feels faint (only looks it)", ACT_DO, 0, 152 },
    { "Tries to get warm", ACT_DO, 0, 153 },
    { "Tries to cool off", ACT_DO, 0, 154 },
    { "Itchy", ACT_DO, 0, 155 },
    { "Needs to lie down", ACT_DO, 0, 158 },
    { "Needs to sit down", ACT_DO, 0, 159 },
    { "Has an epiphany", ACT_DO, 0, 160 },
    { "In a trance", ACT_DO, 0, 161 },
    { "Stinky breath!", ACT_DO, 0, 182 },
    { "Hic!", ACT_DO, 0, 184 },
    { "Blannesamagawa loomajoobamooga!!", ACT_DO, 0, 191 },
    { "Who turned out the lights?!", ACT_DO, 0, 192 },
    { "Something smells YUMMY!", ACT_DO, 0, 193 },
    { "Listens to a story (children)", ACT_DO, 0, 96 },
    { "Watches people work (children)", ACT_DO, 0, 106 },
    { "Runs around (children)", ACT_DO, 0, 148 },
    { "Plays (children)", ACT_DO, 0, 151 },
    { "Plays in puddles (children)", ACT_DO, 0, 180 },
    { "Plays in the dirt (children)", ACT_DO, 0, 190 },
    { "Makes sandcastles (children)", ACT_DO, 0, 195 },
    { "Fishes (Farming practice, food)", ACT_DO, 0, 11 },
    { "Researches (Research practice, tech points)", ACT_DO, 0, 3 },
    { "Does exercise (Building practice)", ACT_DO, 0, 150 },
    { "Eats (uses food, heals a little)", ACT_DO, 0, 84 },
};

/* The stop routine 0x460F70 (thiscall on the record, the record; 137
   callers, e.g. The Low Tide 0x415EAF), then the action; the Origins Full
   Heal's cure: sick 0 and 0x462670(100, -1). */
static int c3_behave(int index, int behaviour) {
    static const int no_arguments[8];
    unsigned char *r = c3_record(index);
    const ce_action *act;
    if (behaviour < 0 || behaviour >= (int)(sizeof C3_BEHAVIOURS / sizeof C3_BEHAVIOURS[0])) {
        return 0;
    }
    act = &C3_BEHAVIOURS[behaviour];
    if (act->kind == ACT_RECOVER) {
        r[0xE89] = 0;
        TC2(0x462670u, r + 0xE6C, 100, -1);
    }
    TC1(0x460F70u, r, (int)(uintptr_t)r);
    if (act->kind == ACT_DO) {
        TC2(0x455570u, r, act->arg, (int)(uintptr_t)no_arguments);
    }
    return 1;
}

/* ---- The Tribal Chief --------------------------------------------------- */

static const char *const C3_STATUSES[] = {
    "Becomes the Tribal Chief (refused while a chief lives)",
    "Becomes the Tribal Chief (the living chief steps down)",
};

/* The robe's own success (0x431FE0) without its celebration and message:
   the robing 0x45FBC0 (thiscall on the village, the record; it sets the
   chief byte +0xE80, the robe body and drops a dislike of dancing) and the
   chief puzzle's advance 0x435990(0) on the puzzle manager 0x594990.  The
   game keeps one chief (its robe lectures anyone dropped on it while a
   chief lives, 0x45FC00): so the living chief steps down first (his chief
   byte cleared; his robe stays, the game keeps no other body for him), or
   the change is refused.  Adults only, as the robe's chooser picks. */
static int c3_set_status(int index, int status) {
    unsigned char *r = c3_record(index);
    int i;
    if ((status != 0 && status != 1) || r[0xE80] != 0 || *(int *)(r + 0xDC4) < 0x118) {
        return 0;
    }
    if (TC0(0x45FC00u, C3_VILLAGE) & 0xFF) {
        if (status == 0) {
            return 0;
        }
        for (i = 0; i < C3_COUNT; ++i) {
            unsigned char *other = c3_record(i);
            if (other != r && c3_listed(other) && other[0xE80] != 0) {
                other[0xE80] = 0;
            }
        }
    }
    TC1(0x45FBC0u, C3_VILLAGE, (int)(uintptr_t)r);
    TC1(0x435990u, 0x594990u, 0);
    return 1;
}

/* ---- Pregnancy: none, a different number of babies, the father --------- */

/* "0 babies": the pregnancy +0xE8C and its litter +0xE90 cleared, then the
   stop 0x460F70, which also releases the place the pregnancy held
   (0x455F30(-1)), as the delivery does.  Babies Made is left as counted. */
static int c3_cancel(int index) {
    unsigned char *r = c3_record(index);
    if (*(int *)(r + 0xE8C) == 0) {
        return 0;
    }
    *(int *)(r + 0xE8C) = 0;
    *(int *)(r + 0xE90) = 0;
    TC1(0x460F70u, r, (int)(uintptr_t)r);
    return 1;
}

/* The litter +0xE90 (0 or 1 one baby, 2, 3: the delivery 0x46040F tests
   > 1 and == 3); each added baby only while there is room. */
static int c3_relitter(int index, int litter, ce_result *result) {
    unsigned char *r = c3_record(index);
    int field = *(int *)(r + 0xE90);
    int babies = field >= 3 ? 3 : field == 2 ? 2 : 1;
    int added = 0;
    if (litter < babies) {
        *(int *)(r + 0xE90) = litter;
        return 0;
    }
    while (babies < litter && c3_room()) {
        ++babies;
        ++added;
        *(int *)(r + 0xE90) = babies;
    }
    result->no_room_babies += litter - babies;
    return added;
}

/* The father the delivery hands the creator: name +0xE48 (0x18 bytes), head
   +0xE68, body +0xE64. */
static int c3_unborn(int index, const ce_change *c) {
    unsigned char *r = c3_record(index);
    if ((c->unborn_head != CE_KEEP && (c->unborn_head < 0 || c->unborn_head >= 30))
        || (c->unborn_body != CE_KEEP && (c->unborn_body < 0 || c->unborn_body >= 30))) {
        return 0;
    }
    if (c->unborn_name[0] != '\0') {
        ce_write_name(r + 0xE48, 0x18, c->unborn_name);
    }
    if (c->unborn_head != CE_KEEP) *(int *)(r + 0xE68) = c->unborn_head;
    if (c->unborn_body != CE_KEEP) *(int *)(r + 0xE64) = c->unborn_body;
    return 1;
}

/* ---- Revive ------------------------------------------------------------- */

/* A skeleton: present, health 0 or less, and not a record the decay skips
   (+0xE94, which the game only ever clears). */
static int c3_skeleton(const unsigned char *r) {
    return r[0xF10] != 0 && r[0xE94] == 0 && *(const int *)(r + 0xE78) <= 0;
}

/* Health through the game's own arbiter 0x462670 (the cause back to -1, the
   living value), the last-update time +0xE70 to the game clock 0x403330
   (on 0x428B60()), then the stop.  Refused for a dead chief while another
   chief lives (two chiefs); only while the room predicate 0x45FE30 says
   there is room. */
static int c3_revive(int index, int health, int cure) {
    unsigned char *r = c3_record(index);
    if (r[0xE80] != 0 && (TC0(0x45FC00u, C3_VILLAGE) & 0xFF)) {
        return 0;
    }
    if (!(TC0(0x45FE30u, C3_VILLAGE) & 0xFF)) {
        return -1;
    }
    TC2(0x462670u, r + 0xE6C, health, -1);
    *(int *)(r + 0xE70) = TC0(0x403330u, ((getter_fn)(uintptr_t)0x428B60u)());
    if (cure) {
        r[0xE89] = 0;
    }
    TC1(0x460F70u, r, (int)(uintptr_t)r);
    return 1;
}

static int c3_food(void) { return *(int *)(uintptr_t)C3_FOOD; }
static int c3_tech(void) { return *(int *)(uintptr_t)C3_TECH; }

/* Written directly (the adders 0x4263F0 / 0x427130 are detoured through the
   Origins doubler); a gain also counts in the lifetime totals [0x5824AC] /
   [0x5824A4] as the adders count it. */
static void c3_change_food(int op, int amount) {
    int before = c3_food();
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(uintptr_t)C3_FOOD = after;
    if (after > before) {
        *(int *)(uintptr_t)0x5824ACu += after - before;
    }
}

static void c3_change_tech(int op, int amount) {
    int before = c3_tech();
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(uintptr_t)C3_TECH = after;
    if (after > before) {
        *(int *)(uintptr_t)0x5824A4u += after - before;
    }
}

/* The fruit trees (object 0x5947E0, count at +0x64, at most 3): 0x4340A0
   (thiscall on the trees, the tree; ret 4) sets a tree's fruit to the full
   1000, as Bitter Brown Beans' "use the beans as fertilizer" does
   (0x415AD0). */
static int c3_refill(void) {
    unsigned char *trees = (unsigned char *)(uintptr_t)0x5947E0u;
    int count = *(int *)(trees + 0x64);
    int i;
    for (i = 0; i < count && i < 3; ++i) {
        TC1(0x4340A0u, trees, i);
    }
    return 1;
}

/* ---- Food sources ------------------------------------------------------- */

/* The fruit trees (object 0x5947E0: tree i at +0x1C + i*0x18, the count at
   +0x64): each tree's fruit +0x30 (the game keeps it 0..1000) and its kind
   +0x2C (0 banana, 1 mango, 2 papaya -- the draw indexes the art by it with
   no check, and a save keeps any value, so nothing else is ever written);
   and the honey [0x5945E0] (0..3000: the save loader refuses a village
   outside that).  Seen live: kind and fruit change the art at once. */
static const ce_value_def C3_VALUES[] = {
    { "Fruit on tree 1", 0, 1000, "Only a planted tree. The game's own ceiling is 1000." },
    { "Fruit on tree 2", 0, 1000, "Only a planted tree. The game's own ceiling is 1000." },
    { "Fruit on tree 3", 0, 1000, "Only a planted tree. The game's own ceiling is 1000." },
    { "Tree 1 kind (0 banana, 1 mango, 2 papaya)", 0, 2, "Only a planted tree." },
    { "Tree 2 kind (0 banana, 1 mango, 2 papaya)", 0, 2, "Only a planted tree." },
    { "Tree 3 kind (0 banana, 1 mango, 2 papaya)", 0, 2, "Only a planted tree." },
    { "Honey", 0, 3000,
      "Gathering it needs The Bee Hive solved; the game's own ceiling is 3000." },
};

static unsigned int c3_value_field(int which) {
    if (which >= 0 && which <= 2) {
        return 0x594810u + 0x18u * (unsigned int)which;
    }
    if (which >= 3 && which <= 5) {
        return 0x59480Cu + 0x18u * (unsigned int)(which - 3);
    }
    return which == 6 ? 0x5945E0u : 0;
}

static int c3_value_get(int which) {
    int trees = *(int *)(uintptr_t)0x594844u;
    if (which < 0 || which > 6) {
        return -1;
    }
    if (which < 6 && which % 3 >= trees) {
        return -1;                     /* no tree planted there */
    }
    return *(int *)(uintptr_t)c3_value_field(which);
}

static int c3_value_set(int which, int amount) {
    if (c3_value_get(which) < 0) {
        return 0;
    }
    *(int *)(uintptr_t)c3_value_field(which) = amount;
    return 1;
}

/* ---- Puzzles ---------------------------------------------------------------

   Puzzle i is {progress, solve time} at 0x594990 + 8i, solved at the
   threshold 0x49D230[i].  Solved writes the threshold and the solve time
   (the clock 0x426590 on 0x5825D4, as AdvancePuzzle stamps it; without it
   the Puzzles screen shows a solve time of 0); unsolved writes 0 and 0, or,
   where the puzzle object keeps its own state, the game's own ResetPuzzle
   0x435680 (progress 0 and the object reset) and the time 0.  Verified live
   (2026-10-01): every tile follows its progress, the Lift's art both ways,
   no rewrite by the game. */
#define C3P_RESET 1            /* unsolved through ResetPuzzle */
#define C3P_KEY 2              /* a door key: the keys-in-the-door count follows */

typedef struct {
    int id;
    int threshold;
    int how;
} c3_puzzle;

static const ce_puzzle_def C3_PUZZLE_DEFS[] = {
    { "The First Chief", 1, 1,
      "Marks the puzzle only; it makes no chief (the Tribal Chief status does both)." },
    { "The Bee Hive", 1, 1, NULL },
    { "The Alchemy Lab", 1, 0,
      "Solved, the lab's pieces still look as they were. Not offered as unsolved: written "
      "back to 0 with pieces placed, it could never be solved again." },
    { "The Roster of the Dead", 1, 1, NULL },
    { "Weather Dancing", 1, 1, NULL },
    { "The Lift", 1, 1,
      "Unsolved, the lift falls at once: a villager up there may be stranded." },
    { "The Ruins", 1, 1, NULL },
    { "The Ancient Bath", 1, 1, NULL },
    { "The Statue", 0, 1,
      "Not offered as solved: the statue's art and place are its own and would stay "
      "broken. Unsolved puts the statue back where it began." },
    { "The Orchard", 1, 1,
      "Unsolved, the game solves it again at once while all three trees are grown." },
    { "The Sharks", 1, 1, NULL },
    { "Aromatherapy", 1, 1, NULL },
    { "The Ash Key", 1, 0,
      "Not offered as unsolved: the door would close on anyone beyond it." },
    { "The Cliff Key", 1, 0,
      "Not offered as unsolved: the door would close on anyone beyond it." },
    { "The Clam Key", 1, 0,
      "Not offered as unsolved: the door would close on anyone beyond it." },
    { "The Chief and the Princess", 1, 1, NULL },
};

static const c3_puzzle C3_PUZZLES[] = {
    { 0, 1, 0 }, { 1, 1, 0 }, { 2, 5, 0 }, { 3, 700, 0 }, { 4, 1, 0 }, { 5, 1, 0 },
    { 6, 1800, 0 }, { 7, 1400, 0 }, { 8, 2, C3P_RESET }, { 9, 1, 0 }, { 10, 1, C3P_RESET },
    { 11, 6, C3P_RESET }, { 12, 1, C3P_KEY }, { 13, 1, C3P_KEY }, { 14, 1, C3P_KEY },
    { 15, 1, 0 },
};

#define C3_PUZZLE_COUNT ((int)(sizeof C3_PUZZLES / sizeof C3_PUZZLES[0]))
#define C3_PUZZLE_PROGRESS(id) ((int *)(uintptr_t)(0x594990u + 8u * (unsigned int)(id)))

static int c3_puzzle_solved(int which) {
    if (which < 0 || which >= C3_PUZZLE_COUNT) {
        return 0;
    }
    return *C3_PUZZLE_PROGRESS(C3_PUZZLES[which].id) >= C3_PUZZLES[which].threshold;
}

static int c3_puzzle_set(int which, int solved) {
    const c3_puzzle *p;
    int *entry;
    if (which < 0 || which >= C3_PUZZLE_COUNT) {
        return 0;
    }
    p = &C3_PUZZLES[which];
    entry = C3_PUZZLE_PROGRESS(p->id);
    if (solved) {
        entry[0] = p->threshold;
        entry[1] = TC0(0x426590u, 0x5825D4u);
        if (p->how & C3P_KEY) {
            /* The keys in the door (puzzle 19): the keys now complete. */
            int keys = (*C3_PUZZLE_PROGRESS(12) >= 1) + (*C3_PUZZLE_PROGRESS(13) >= 1)
                + (*C3_PUZZLE_PROGRESS(14) >= 1);
            *C3_PUZZLE_PROGRESS(19) = keys;
        }
    } else {
        if (p->how & C3P_RESET) {
            TC1(0x435680u, 0x594990u, p->id);
        }
        entry[0] = 0;
        entry[1] = 0;
    }
    return 1;
}

static int c3_parents_supported(void) {
    return 1;
}

static int c3_set_parents(int index, const ce_change *c) {
    return ce_set_record_parents(c3_record(index), 0xDF8, 0xE11, 0x19, 0xE2C, 0xE30, 0xE34, 0xE38,
                                 30, 30, c);
}

static const char *const C3_SKILLS[] = { "Farming", "Parenting", "Healing", "Research", "Building" };

typedef int (__cdecl *c3_rand_fn)(int bound);

/* The game's own rand(bound) 0x4032D0 (cdecl, 0..bound-1). */
static int c3_rand_below(int n) {
    return ((c3_rand_fn)(uintptr_t)0x4032D0u)(n);
}

static const ce_adapter C3_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY | CAP_STATUS | CAP_VALUES
        | CAP_PUZZLES | CAP_CANCEL | CAP_RELITTER | CAP_UNBORN | CAP_REVIVE | CAP_CHOICE,
    "The Secret City",
    0x118, 40, 1100,
    C3_COUNT, 0x19,
    0xDD4, 0xDC8, 0xDC4, 0xDF0, 0xDF4, 0xFB4, 0xFC0, 0xEAC,
    0, 1,
    3, 79,
    STORY_PREFERENCES_79,
    30, 30,
    5, 0, C3_SKILLS,
    0xDF8, 0xE11, 0x19, 0xE2C, 0xE30, 0xE34, 0xE38,
    C3_STATUSES, 2,
    C3_BEHAVIOURS, (int)(sizeof C3_BEHAVIOURS / sizeof C3_BEHAVIOURS[0]),
    NULL, 0,
    "Not in The Secret City:\r\n\r\n"
    "- A second Tribal Chief: the game keeps one (the living chief steps down instead).\r\n"
    "- Esteemed Elder is not a status here: the game shows it for any villager with three "
    "mastered skills, so set the skills instead.\r\n"
    "- Puzzles: The Statue as solved, The Alchemy Lab and the three keys as unsolved (see "
    "each one's note).\r\n"
    "- A tree kind other than banana, mango and papaya: the game draws the trees by that "
    "number with no check and would crash.\r\n"
    "- The unborn baby's starting skill: what the baby does with it at birth was not "
    "traced to the end, so only the father's name and looks are offered.\r\n"
    "- Actions that solve or advance a puzzle, burying, picking things up, new clothes, "
    "the chief's own powers, and lessons or games that stop other villagers.\r\n"
    "- Revive: buried villagers (their record is gone), skeletons that have already "
    "crumbled away, and a dead chief while another chief lives.\r\n"
    "- Golden Child, faction, totems: The Secret City has none.",
    48, 14, 30, 1, 360,
    "Refills the fruit trees.",
    "Your village gains %d food.", "Your village has lost %d food.",
    "Your village has gained %d tech points.", "Your village has lost %d tech points.",
    c3_record, c3_listed, c3_arm_refusal, c3_room, c3_spawn, c3_kill, c3_vanish, c3_sicken,
    c3_conceive, c3_set_status, c3_behave, NULL, c3_food, c3_tech, c3_change_food,
    c3_change_tech, c3_refill, c3_parents_supported, c3_set_parents,
    C3_VALUES, 7, c3_value_get, c3_value_set,
    C3_PUZZLE_DEFS, C3_PUZZLE_COUNT, c3_puzzle_solved, c3_puzzle_set,
    c3_cancel, c3_relitter, c3_unborn,
    c3_skeleton, c3_revive,
    0, 0xE8C,
    /* The two-choice popup (0x4192F0): the 432-pixel text box of the plain
       one, 11 lines for the tallest of the question and the results (the
       tallest stock two-choice text; the popup also shows the villager);
       the title stays above the result; labels of 32 characters. */
    48, 11, 48, 11, 0, 32, c3_rand_below, NULL
};

/* ---- Delivery ----------------------------------------------------------- */

static int __fastcall c3_title_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C3_TITLE_ID;
}

static int __fastcall c3_body_id(void *self, void *unused_edx) {
    (void)self;
    (void)unused_edx;
    return C3_BODY_ID;
}

/* The Fog (0x47E600) with: +0x08 / +0x0C the custom ids, +0x30 apply and
   +0x38 prepare doing nothing (the changes are already made). */
static void *c3_custom_object(void) {
    static const int slots[4] = { 2, 3, 12, 14 };
    void *functions[4];
    if (ce_deliver_object(3, C3_STRING_TABLE, C3_TITLE_ID, C3_BODY_ID, 0) == NULL) {
        return NULL;
    }
    functions[0] = (void *)c3_title_id;
    functions[1] = (void *)c3_body_id;
    functions[2] = (void *)ce_object_nothing;
    functions[3] = (void *)ce_object_nothing;
    return ce_build_object(0x47E600u, slots, functions, 4);
}

/* A question (story_objects.inc): a copy of the first two-choice event's
   vtable (0x47EA40) with the custom ids, featuring the picked or a random living villager. */
static void *c3_choice_object(void) {
    return choice_object(3, C3_STRING_TABLE, C3_TITLE_ID, C3_BODY_ID, 0, 0x47EA40u,
                         (void *)c3_title_id);
}

/* ---- Title ---------------------------------------------------------------

   The HUD 0x468C10 builds the selected villager's title in a stack buffer
   ([esp+0x28]) for the record at [esp+0x10]; both branches join at 0x468FC8
   `mov ecx,[ebp+0xE4]` before setting the label. */
static void __cdecl c3_title(const unsigned char *record, char *buffer) {
    const char *custom = titles_lookup(3, record);
    if (custom != NULL) {
        lstrcpynA(buffer, custom, VV_TITLE_BYTES);
    }
}

__declspec(naked) static void c3_title_stub(void) {
    __asm {
        pushad
        mov eax, dword ptr [esp + 0x20 + 0x10]
        lea ecx, [esp + 0x20 + 0x28]
        push ecx
        push eax
        call c3_title
        add esp, 8
        popad
        mov ecx, dword ptr [ebp + 0xE4]
        push 0x468FCE
        ret
    }
}
