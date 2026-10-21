/* Custom Island Event: The Secret City.  Included by vvfp_story_upgrades.c.

   Every address below was traced in the stock executable and is identical in
   the three renders (docs/story-cheat-upgrades.md).  The village is
   0x59E110; record i at 0x59E124 + i*0x1F8C, 150 records -- or, with 256
   Villagers (Experimental), 0x800000 and 256 records: both are read from the
   executable (native/shared/vv3_villager_table.h), so this one DLL serves
   either build.

   DELIVERY.  The island-event selector 0x419B30 has chosen at 0x419BDB (the
   Pick Island Event site): with a custom event armed, the changes are made
   and the presenter is handed the custom event object (story_objects.inc,
   a copy of The Fog's simple-event vtable 0x47E600) instead.  Its strings
   are ids 0x4CB / 0x4CC, the two string-table slots (0x592730) the game
   leaves empty and no code or string names.  The Origins Barrel's call of
   the same selector (every slot the barrel) never takes it. */

#include "../shared/vv3_villager_table.h"

static unsigned int c3_table_village;
static int c3_table_count;

/* The village (population manager) and its slot count, as the executable
   names them; read once.  The image is not relocatable, so its base is
   0x400000. */
static void c3_locate(void) {
    unsigned int rva, slots;
    if (c3_table_village != 0) {
        return;
    }
    vv3_villager_table((const unsigned char *)(uintptr_t)0x400000u, &rva, &slots);
    c3_table_count = (int)slots;
    c3_table_village = 0x400000u + rva;
}

static unsigned int c3_village(void) {
    c3_locate();
    return c3_table_village;
}

static int c3_count(void) {
    c3_locate();
    return c3_table_count;
}

#define C3_VILLAGE c3_village()
#define C3_RECORDS (c3_village() + 0x14u)
#define C3_STRIDE 0x1F8Cu
#define C3_COUNT c3_count()
/* The adapter's record count at compile time: the stock table.  The adapter
   handed out at run time (c3_adapter) carries the executable's own count. */
#define C3_STOCK_COUNT 150
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

/* Records in use plus the babies on the way: the records (150, or 256) are
   the physical limit, which the game's room predicate does not count. */
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
   gates) and the physical records. */
static int c3_room(void) {
    return (TC0(0x45FE30u, C3_VILLAGE) & 0xFF) != 0 && c3_demand() < C3_COUNT;
}

static const ce_adapter C3_ADAPTER;
static const ce_adapter *c3_adapter(void);

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
    ce_apply_spawn_record(c3_adapter(), c3_record(index), s);
    return index;
}

/* The Medical Emergency's death (0x4172D9): 0x462670 (thiscall on the
   record's health block +0xE6C: value 0, cause -1). */
static int c3_kill(int index) {
    TC2(0x462670u, c3_record(index) + 0xE6C, 0, -1);
    return 1;
}

/* Health through the same arbiter (value, cause -1: the living value, as
   c3_revive writes it). */
static void c3_set_health(int index, int health) {
    TC2(0x462670u, c3_record(index) + 0xE6C, health, -1);
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
    if (*(int *)(r + 0xE8C) != 0) {
        ce_refuse(result, CE_WHY_EXPECTING);
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
    if (f != NULL) {
        ce_copy_record_name(r + 0xE48, 0x18, f + 0xDD4, 0x19);
    } else {
        (void)ce_write_name(r + 0xE48, 0x18, "Unknown");
    }
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
   arguments (an argument block of zeros: an action that takes a place or
   spot takes its own default).  The owner (2026-10-21): every registered
   action is offered, labelled with the text the Details screen then shows;
   one that may harm the game or the save ends " (Unsafe)" with its reason
   (shown before it is confirmed).  "Celebrating" is action 82 (its default
   spot: the village centre).  Not offered: the shared default handler, id 7
   (shows the caller's text), text-less walk steps, burial (the body the game
   last marked) and the pickups 47, 48 and 115 (they take the object the
   game passes). */
static const ce_action C3_BEHAVIOURS[] = {
    { "Stops what they are doing", ACT_STOP, 0, 0, CE_GROUP_GENERAL, NULL },
    { "Recovers fully (cured, full health)", ACT_RECOVER, 0, 0, CE_GROUP_GENERAL, NULL },
    { "Dancing", ACT_DO, 0, 8, CE_GROUP_CELEBRATION, NULL },
    { "Dancing (another dance)", ACT_DO, 0, 0x55, CE_GROUP_CELEBRATION, NULL },
    { "Secretly practicing a dance", ACT_DO, 0, 0xB5, CE_GROUP_CELEBRATION, NULL },
    { "Performing ceremonial dance", ACT_DO, 0, 0x43, CE_GROUP_DEVOTION, NULL },
    { "Rain dancing", ACT_DO, 0, 0xC, CE_GROUP_CELEBRATION, NULL },
    { "Celebrating Isola Day", ACT_DO, 0, 0x42, CE_GROUP_CELEBRATION, NULL },
    { "Relaxing", ACT_DO, 0, 0xD, CE_GROUP_LEISURE, NULL },
    { "Relaxing at the beach", ACT_DO, 0, 0x15, CE_GROUP_LEISURE, NULL },
    { "Reflecting", ACT_DO, 0, 0x16, CE_GROUP_LEISURE, NULL },
    { "Watching the clouds", ACT_DO, 0, 0x12, CE_GROUP_LEISURE, NULL },
    { "Going swimming", ACT_DO, 0, 1, CE_GROUP_LEISURE, NULL },
    { "Enjoying the bath", ACT_DO, 0, 0x17, CE_GROUP_LEISURE, NULL },
    { "Bathing", ACT_DO, 0, 0x8F, CE_GROUP_LEISURE, NULL },
    { "Cooling feet in stream", ACT_DO, 0, 0x13, CE_GROUP_LEISURE, NULL },
    { "Washing face", ACT_DO, 0, 0x8C, CE_GROUP_LEISURE, NULL },
    { "Washing hands", ACT_DO, 0, 0x8D, CE_GROUP_LEISURE, NULL },
    { "Getting a drink", ACT_DO, 0, 0x90, CE_GROUP_HEALTH, NULL },
    { "Drinking rain", ACT_DO, 0, 0x3C, CE_GROUP_HEALTH, NULL },
    { "Getting out of the rain", ACT_DO, 0, 0x8E, CE_GROUP_MOOD, NULL },
    { "Cleaning up after the rain", ACT_DO, 0, 0xC4, CE_GROUP_WORK, NULL },
    { "Washing the laundry", ACT_DO, 0, 0x3D, CE_GROUP_WORK, NULL },
    { "Looking at fishies", ACT_DO, 0, 0x92, CE_GROUP_CURIOSITY, NULL },
    { "Looking at the fire", ACT_DO, 0, 0x22, CE_GROUP_CURIOSITY, NULL },
    { "Honoring the Dead", ACT_DO, 0, 0xA, CE_GROUP_DEVOTION, NULL },
    { "Stomping ants", ACT_DO, 0, 0x44, CE_GROUP_MOOD, NULL },
    { "Hiding in hut", ACT_DO, 0, 0x45, CE_GROUP_MOOD, NULL },
    { "Acting sinister", ACT_DO, 0, 0x3E, CE_GROUP_MOOD, NULL },
    { "Jumpy!", ACT_DO, 0, 0x5D, CE_GROUP_MOOD, NULL },
    { "Nature is calling!", ACT_DO, 0, 0x5E, CE_GROUP_MOOD, NULL },
    { "A little bit lonely", ACT_DO, 0, 0x66, CE_GROUP_MOOD, NULL },
    { "Unsure what to do (wanders)", ACT_DO, 0, 0x7B, CE_GROUP_MOOD, NULL },
    { "Sitting", ACT_DO, 0, 0x34, CE_GROUP_LEISURE, NULL },
    { "Shaking head", ACT_DO, 0, 0x31, CE_GROUP_MOOD, NULL },
    { "Not feeling well (only looks it)", ACT_DO, 0, 0x2D, CE_GROUP_HEALTH, NULL },
    { "Recovering at the hospital", ACT_DO, 0, 0x61, CE_GROUP_HEALTH, NULL },
    { "Feeling faint (only looks it)", ACT_DO, 0, 0x98, CE_GROUP_HEALTH, NULL },
    { "Trying to get warm", ACT_DO, 0, 0x99, CE_GROUP_HEALTH, NULL },
    { "Trying to cool off", ACT_DO, 0, 0x9A, CE_GROUP_HEALTH, NULL },
    { "Itchy", ACT_DO, 0, 0x9B, CE_GROUP_HEALTH, NULL },
    { "Needs to lie down", ACT_DO, 0, 0x9E, CE_GROUP_HEALTH, NULL },
    { "Needs to sit down", ACT_DO, 0, 0x9F, CE_GROUP_HEALTH, NULL },
    { "Having an epiphany", ACT_DO, 0, 0xA0, CE_GROUP_DEVOTION, NULL },
    { "In a trance", ACT_DO, 0, 0xA1, CE_GROUP_DEVOTION, NULL },
    { "Stinky breath!", ACT_DO, 0, 0xB6, CE_GROUP_MOOD, NULL },
    { "Hic!", ACT_DO, 0, 0xB8, CE_GROUP_MOOD, NULL },
    { "Blannesamagawa loomajoobamooga!!", ACT_DO, 0, 0xBF, CE_GROUP_MOOD, NULL },
    { "Who turned out the lights?!", ACT_DO, 0, 0xC0, CE_GROUP_MOOD, NULL },
    { "Something smells YUMMY!", ACT_DO, 0, 0xC1, CE_GROUP_MOOD, NULL },
    { "Listening to a story (children)", ACT_DO, 0, 0x60, CE_GROUP_CHILDREN, NULL },
    { "Watching people work (children)", ACT_DO, 0, 0x6A, CE_GROUP_CHILDREN, NULL },
    { "Running around (children)", ACT_DO, 0, 0x94, CE_GROUP_CHILDREN, NULL },
    { "Playing (children)", ACT_DO, 0, 0x97, CE_GROUP_CHILDREN, NULL },
    { "Playing in puddles (children)", ACT_DO, 0, 0xB4, CE_GROUP_CHILDREN, NULL },
    { "Playing in the dirt (children)", ACT_DO, 0, 0xBE, CE_GROUP_CHILDREN, NULL },
    { "Making sandcastles (children)", ACT_DO, 0, 0xC3, CE_GROUP_CHILDREN, NULL },
    { "Fishing (Farming practice, food)", ACT_DO, 0, 0xB, CE_GROUP_WORK, NULL },
    { "Researching (Research practice, tech points)", ACT_DO, 0, 3, CE_GROUP_WORK, NULL },
    { "Doing exercise (Building practice)", ACT_DO, 0, 0x96, CE_GROUP_WORK, NULL },
    { "Eating (uses food, heals a little)", ACT_DO, 0, 0x54, CE_GROUP_HEALTH, NULL },
    { "Celebrating", ACT_DO, 0, 0x52, CE_GROUP_CELEBRATION, NULL },
    { "Caring for baby (while expecting) / Unsure what to do", ACT_DO, 0, 0, CE_GROUP_FAMILY, NULL },
    { "Going indoors", ACT_DO, 0, 6, CE_GROUP_MOOD, NULL },
    { "Gathering dry grass", ACT_DO, 0, 0xF, CE_GROUP_WORK, NULL },
    { "Gathering firewood", ACT_DO, 0, 0x10, CE_GROUP_WORK, NULL },
    { "Relaxing at the beach (another spot)", ACT_DO, 0, 0x18, CE_GROUP_LEISURE, NULL },
    { "Curious about the robe", ACT_DO, 0, 0x19, CE_GROUP_CURIOSITY, NULL },
    { "Amazed at the statue / Curious about the statue", ACT_DO, 0, 0x1A, CE_GROUP_CURIOSITY, NULL },
    { "Admiring the hidden room / Curious about the door", ACT_DO, 0, 0x1B, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the giant clam", ACT_DO, 0, 0x1C, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the bee hive", ACT_DO, 0, 0x1D, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the machine", ACT_DO, 0, 0x1E, CE_GROUP_CURIOSITY, NULL },
    { "Interested in the ruins / Curious about the rubble", ACT_DO, 0, 0x1F, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the bath", ACT_DO, 0, 0x20, CE_GROUP_CURIOSITY, NULL },
    { "Snooping around the alchemy room / Curious about this room", ACT_DO, 0, 0x21, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the thing up there", ACT_DO, 0, 0x23, CE_GROUP_CURIOSITY, NULL },
    { "Enjoying the orchard / Curious about the dark soil", ACT_DO, 0, 0x24, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the Tiger Lily", ACT_DO, 0, 0x25, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the Cactus", ACT_DO, 0, 0x26, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the Lotus", ACT_DO, 0, 0x27, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the Black Orchid", ACT_DO, 0, 0x28, CE_GROUP_CURIOSITY, NULL },
    { "Curious about the Rose", ACT_DO, 0, 0x29, CE_GROUP_CURIOSITY, NULL },
    { "Looking at the dry grass", ACT_DO, 0, 0x2A, CE_GROUP_CURIOSITY, NULL },
    { "Looking at the bush / Looking at the Roster of the Dead", ACT_DO, 0, 0x2B, CE_GROUP_CURIOSITY, NULL },
    { "Enjoying the bath (another spot)", ACT_DO, 0, 0x2E, CE_GROUP_LEISURE, NULL },
    { "Caring for baby / Worried about food / Worried about housing (or Bored)", ACT_DO, 0, 0x32, CE_GROUP_MOOD, NULL },
    { "Healing someone (cures nobody)", ACT_DO, 0, 0x33, CE_GROUP_WORK, NULL },
    { "Worried about food / Worried about housing (or Thinking)", ACT_DO, 0, 0x36, CE_GROUP_MOOD, NULL },
    { "Attending lecture (no lesson) [The Chief's Address]", ACT_DO, 0, 0x38, CE_GROUP_CHILDREN, NULL },
    { "Lecturing", ACT_DO, 0, 0x39, CE_GROUP_WORK, NULL },
    { "Working 'til he drops! / Working 'til she drops!", ACT_DO, 0, 0x3A, CE_GROUP_MOOD, NULL },
    { "Playing in the lab", ACT_DO, 0, 0x3B, CE_GROUP_CHILDREN, NULL },
    { "Honoring the dead (another way)", ACT_DO, 0, 0x3F, CE_GROUP_DEVOTION, NULL },
    { "Honoring the guiding hand", ACT_DO, 0, 0x40, CE_GROUP_DEVOTION, NULL },
    { "Honoring the dead (another place)", ACT_DO, 0, 0x41, CE_GROUP_DEVOTION, NULL },
    { "Bringing back a prize [The Mango and the Papaya, The Mysterious Crate]", ACT_DO, 0, 0x46, CE_GROUP_STORY, NULL },
    { "Bringing back a prize (another way) [The Mysterious Crate]", ACT_DO, 0, 0x47, CE_GROUP_STORY, NULL },
    { "Running to the rescue", ACT_DO, 0, 0x48, CE_GROUP_STORY, NULL },
    { "Studying strange plant (Healing practice, place 1)", ACT_DO, 0, 0x49, CE_GROUP_WORK, NULL },
    { "Studying strange plant (Healing practice, place 2)", ACT_DO, 0, 0x4A, CE_GROUP_WORK, NULL },
    { "Studying strange plant (Healing practice, place 3)", ACT_DO, 0, 0x4B, CE_GROUP_WORK, NULL },
    { "Studying strange plant (Healing practice, place 4)", ACT_DO, 0, 0x4C, CE_GROUP_WORK, NULL },
    { "Studying strange plant (Healing practice, place 5)", ACT_DO, 0, 0x4D, CE_GROUP_WORK, NULL },
    { "Studying strange plant (Healing practice, place 6)", ACT_DO, 0, 0x4E, CE_GROUP_WORK, NULL },
    { "Leaving the water", ACT_DO, 0, 0x4F, CE_GROUP_LEISURE, NULL },
    { "Enjoying the bath (a third spot)", ACT_DO, 0, 0x50, CE_GROUP_LEISURE, NULL },
    { "Playing seesaw (children)", ACT_DO, 0, 0x5C, CE_GROUP_CHILDREN, NULL },
    { "Telling a story (Parenting practice)", ACT_DO, 0, 0x5F, CE_GROUP_FAMILY, NULL },
    { "Washing baby", ACT_DO, 0, 0x67, CE_GROUP_FAMILY, NULL },
    { "Changing baby", ACT_DO, 0, 0x68, CE_GROUP_FAMILY, NULL },
    { "Showing baby the reef", ACT_DO, 0, 0x69, CE_GROUP_FAMILY, NULL },
    { "Harvesting honey (Farming practice)", ACT_DO, 0, 0x6B, CE_GROUP_WORK, NULL },
    { "Worried about food (another way)", ACT_DO, 0, 0x76, CE_GROUP_MOOD, NULL },
    { "Worried about food (briefly)", ACT_DO, 0, 0x77, CE_GROUP_MOOD, NULL },
    { "Trying on the robe (another way)", ACT_DO, 0, 0x79, CE_GROUP_CURIOSITY, NULL },
    { "Enjoying the bath (a fourth spot)", ACT_DO, 0, 0x7A, CE_GROUP_LEISURE, NULL },
    { "Trying an idea...", ACT_DO, 0, 0x7E, CE_GROUP_MOOD, NULL },
    { "Directing work", ACT_DO, 0, 0x81, CE_GROUP_WORK, NULL },
    { "Inspecting the food", ACT_DO, 0, 0x82, CE_GROUP_WORK, NULL },
    { "Inspecting the food (briefly)", ACT_DO, 0, 0x83, CE_GROUP_WORK, NULL },
    { "Proud of the tribe / Contemplating the tribe", ACT_DO, 0, 0x85, CE_GROUP_MOOD, NULL },
    { "Inspecting the labs", ACT_DO, 0, 0x86, CE_GROUP_WORK, NULL },
    { "Curing the tribe! (only the look; nobody is cured)", ACT_DO, 0, 0x88, CE_GROUP_HEALTH, NULL },
    { "Concerned about the sick", ACT_DO, 0, 0x8A, CE_GROUP_HEALTH, NULL },
    { "Thinking", ACT_DO, 0, 0x8B, CE_GROUP_MOOD, NULL },
    { "Looking for mushrooms / Looking for collectibles (children)", ACT_DO, 0, 0x91, CE_GROUP_CHILDREN, NULL },
    { "Paralyzed (only looks it)", ACT_DO, 0, 0x9C, CE_GROUP_HEALTH, NULL },
    { "Stung by jellyfish (only looks it)", ACT_DO, 0, 0xA2, CE_GROUP_HEALTH, NULL },
    { "Looking for mommy / Looking for daddy", ACT_DO, 0, 0xA4, CE_GROUP_CHILDREN, NULL },
    { "Looking for mommy (another way)", ACT_DO, 0, 0xA5, CE_GROUP_CHILDREN, NULL },
    { "Trying to get warm (briefly) [The Cold Snap]", ACT_DO, 0, 0xA6, CE_GROUP_HEALTH, NULL },
    { "Showing baby the bees", ACT_DO, 0, 0xA8, CE_GROUP_FAMILY, NULL },
    { "Showing baby the herbs", ACT_DO, 0, 0xA9, CE_GROUP_FAMILY, NULL },
    { "Inspecting hut", ACT_DO, 0, 0xAA, CE_GROUP_WORK, NULL },
    { "Hiding something", ACT_DO, 0, 0xAB, CE_GROUP_MOOD, NULL },
    { "Showing baby the orchard", ACT_DO, 0, 0xAD, CE_GROUP_FAMILY, NULL },
    { "Depositing food (only the look; adds no food)", ACT_DO, 0, 0xB1, CE_GROUP_WORK, NULL },
    { "Showing baby the amphitheater", ACT_DO, 0, 0xB2, CE_GROUP_FAMILY, NULL },
    { "Enjoying the beach with baby", ACT_DO, 0, 0xB3, CE_GROUP_FAMILY, NULL },
    { "That tasted soapy", ACT_DO, 0, 0xB7, CE_GROUP_MOOD, NULL },
    { "Hic! (briefly)", ACT_DO, 0, 0xB9, CE_GROUP_MOOD, NULL },
    { "Stinky breath! (briefly)", ACT_DO, 0, 0xBA, CE_GROUP_MOOD, NULL },
    { "That tasted soapy (briefly)", ACT_DO, 0, 0xBB, CE_GROUP_MOOD, NULL },
    { "Leading a dance poorly / Dancing poorly", ACT_DO, 0, 0xBC, CE_GROUP_CELEBRATION, NULL },
    { "Studying medicine (Healing practice)", ACT_DO, 0, 0xBD, CE_GROUP_WORK, NULL },
    { "Teaching baby words", ACT_DO, 0, 0xC2, CE_GROUP_FAMILY, NULL },
    { "Putting water on the firepit", ACT_DO, 0, 0xC5, CE_GROUP_WORK, NULL },
    { "Embracing (Unsafe)", ACT_DO, 0, 4, CE_GROUP_FAMILY, "the game pairs two villagers for this; alone they embrace nobody until it times out (no baby)" },
    { "Waiting for someone (Unsafe)", ACT_DO, 0, 5, CE_GROUP_FAMILY, "waits for a partner who never comes until it times out" },
    { "Starting a fire (Unsafe)", ACT_DO, 0, 0x11, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the fire)" },
    { "Confused (Unsafe)", ACT_DO, 0, 0x2C, CE_GROUP_MOOD, "may pop up the game's hint 0 while this villager is selected (the game passes the hint)" },
    { "Chatting / Arguing / Complaining / Teaching / Telling a story / Praising / Jumpy! (Unsafe)", ACT_DO, 0, 0x35, CE_GROUP_MOOD, "picks another villager and stops what they are doing to talk" },
    { "Attending lecture (Unsafe)", ACT_DO, 0, 0x37, CE_GROUP_CHILDREN, "the Tribal Chief's lesson: raises one skill by 7 to 9 points" },
    { "Getting new clothes! (Unsafe)", ACT_DO, 0, 0x62, CE_GROUP_STORY, "takes the new-clothes cost (5000) from the village and changes their clothes" },
    { "Repairing the lift (Unsafe)", ACT_DO, 0, 0x6C, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the lift)" },
    { "Standing on the lift (Unsafe)", ACT_DO, 0, 0x6D, CE_GROUP_STORY, "part of the lift puzzle; before the lift is repaired they stand where it would be" },
    { "Repairing the bath (Unsafe)", ACT_DO, 0, 0x6E, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the bath)" },
    { "Doing alchemy (Unsafe)", ACT_DO, 0, 0x6F, CE_GROUP_STORY, "an alchemy-room puzzle action; the puzzle may count it" },
    { "Emptying the pot (Unsafe)", ACT_DO, 0, 0x70, CE_GROUP_STORY, "empties the alchemy pot, which is puzzle state" },
    { "Using potion (Unsafe)", ACT_DO, 0, 0x71, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (a potion)" },
    { "Building scaffolding (Unsafe)", ACT_DO, 0, 0x74, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the statue)" },
    { "Pushing statue (Unsafe)", ACT_DO, 0, 0x75, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the statue)" },
    { "Trying on the robe (Unsafe)", ACT_DO, 0, 0x78, CE_GROUP_STORY, "the robe puzzle's step: may make this villager the Tribal Chief" },
    { "Clearing rubble (Building practice) (Unsafe)", ACT_DO, 0, 0x7F, CE_GROUP_STORY, "a puzzle job; the puzzle may count it" },
    { "Clearing leaves (Building practice) (Unsafe)", ACT_DO, 0, 0x80, CE_GROUP_STORY, "a puzzle job; the puzzle may count it" },
    { "Doing a weather dance (Unsafe)", ACT_DO, 0, 0x84, CE_GROUP_STORY, "the Tribal Chief's power: a puzzle step: tells the puzzle manager it happened, which may change puzzle progress" },
    { "Creating magic food! (Unsafe)", ACT_DO, 0, 0x87, CE_GROUP_STORY, "the Tribal Chief's power: adds food to the stores" },
    { "Pointing out a rare collectible (Unsafe)", ACT_DO, 0, 0x89, CE_GROUP_STORY, "the Tribal Chief's power: makes a rare collectible appear" },
    { "Trying to reach the key (Unsafe)", ACT_DO, 0, 0x93, CE_GROUP_STORY, "part of the key puzzle; the puzzle may count it" },
    { "Carrying vial to ocean (Unsafe)", ACT_DO, 0, 0xA3, CE_GROUP_STORY, "picks up the vial (a puzzle object) if it is lying around" },
    { "Drawing plans (Unsafe)", ACT_DO, 0, 0xA7, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress" },
    { "Doing aromatherapy (Unsafe)", ACT_DO, 0, 0xAE, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the burners)" },
    { "Lighting burners (Unsafe)", ACT_DO, 0, 0xAF, CE_GROUP_STORY, "a puzzle step: tells the puzzle manager it happened, which may change puzzle progress (the burners)" },
    { "Swapping the pearl (Unsafe)", ACT_DO, 0, 0xB0, CE_GROUP_STORY, "a pearl puzzle action; the puzzle may count it" },
    { "Shaping an irregular pearl (Unsafe)", ACT_DO, 0, 0xC6, CE_GROUP_STORY, "a pearl puzzle action; the puzzle may count it" },
    { "Polishing a rough pearl (Unsafe)", ACT_DO, 0, 0xC7, CE_GROUP_STORY, "a pearl puzzle action; the puzzle may count it" },
    { "Building small hut (Building practice) (Unsafe)", ACT_DO, 0, 9, CE_GROUP_STORY, "builds toward a hut at the first hut place (the game passes which), a puzzle step" },
    { "Examining hut (Unsafe)", ACT_DO, 0, 0x56, CE_GROUP_WORK, "examines the first hut place (the game passes which) and may go on to fix it" },
    { "Fixing hut (Building practice) (Unsafe)", ACT_DO, 0, 0x57, CE_GROUP_WORK, "works on the first hut place (the game passes which hut)" },
    { "Refusing (Unsafe)", ACT_DO, 0, 0x72, CE_GROUP_MOOD, "may show a blank game message while this villager is selected (the game passes the message)" },
    { "Planting tree (Unsafe)", ACT_DO, 0, 0x7C, CE_GROUP_STORY, "walks to the map corner (the game passes the spot) and counts toward the orchard puzzle" },
    { "Harvesting fruit (Farming practice) (Unsafe)", ACT_DO, 0, 0x7D, CE_GROUP_STORY, "uses the first tree's place and counts toward the orchard puzzle" },
    { "Hay fever (animation only, no Details text) [The Allergy Season]", ACT_DO, 0, 0x65, CE_GROUP_HEALTH, NULL },
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
    if (!ce_action_ready(act)) {
        return 0;
    }
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
   the change is refused.  Any age: a child becomes the Tribal Chief in the
   game itself, and every head and body serves children and adults alike
   (the owner, 2026-10-06).  The chief already is: nothing to change. */
static int c3_set_status(int index, int status) {
    unsigned char *r = c3_record(index);
    int i;
    if (status != 0 && status != 1) {
        return 0;
    }
    if (r[0xE80] != 0) {
        return 1;
    }
    if (TC0(0x45FC00u, C3_VILLAGE) & 0xFF) {
        if (status == 0) {
            return ce_because(CE_WHY_CHIEF);
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

/* ---- Recharge Chief Powers ----------------------------------------------

   The owner (2026-10-20): an Upgrades-menu purchase that makes the Tribal
   Chief's powers available at once, at the same price as Pick Gong of Wonder
   Outcome (which makes The Lost Children's Gong ready to ring at once): the
   Island Event upgrade's, 0 unless the upgrades cost tech points.

   The chief's three once-a-day powers each keep the clock time they can next
   be used in the world object (0x428B60()), on the game's clock 0x403330:
     +0x12F00  granting food (the food store hotspot 15, 0x421A30);
     +0x12EFC  educating the children (chief dropped on a child with
               Leadership 2, 0x466828);
     +0x12EF8  pointing out a rare collectible (hotspot 0x25, Leadership 3,
               0x421BE0).
   A use tests `stamp > clock` (resting: "The chief can only do this once
   every 24 hours", say 0x2A through action 0x72); otherwise the power runs
   and the stamp becomes the clock + 0x14370 (23 hours).  The game's own
   ready value is 0: the robe's success 0x431FE0 writes 0 to all three when a
   villager becomes the chief (0x432013 / 0x432022 / 0x432038).  The purchase
   writes that same 0 to each resting stamp and nothing else; the next use
   sets the stamp again as the game always does.

   Refused, nothing written and nothing charged: no living chief (the game's
   own chief test 0x45FC00); no powers yet (Leadership level 0: the
   technology [0x582618 + 4*4], read by 0x426FC0(4), gives the first power
   at level 1); or every power already ready. */
#define C3_CHIEF_POWERS 3
#define C3_RECHARGE_NO_CHIEF (-1)
#define C3_RECHARGE_NO_POWERS (-2)
#define C3_RECHARGE_READY (-3)

static const unsigned int C3_CHIEF_POWER_STAMPS[C3_CHIEF_POWERS] = { 0x12F00u, 0x12EFCu, 0x12EF8u };

static unsigned char *c3_world(void) {
    return (unsigned char *)((getter_fn)(uintptr_t)0x428B60u)();
}

/* Whether power `k` is resting now, as each use tests it (`cmp [stamp],
   clock; jbe ready`). */
static int c3_chief_power_resting(const unsigned char *world, int k) {
    return *(const unsigned int *)(world + C3_CHIEF_POWER_STAMPS[k])
           > (unsigned int)TC0(0x403330u, world);
}

/* Why the powers can not be recharged now (a C3_RECHARGE_* code), or 0. */
static int c3_recharge_refusal(void) {
    unsigned char *world;
    int k;
    if ((TC0(0x45FC00u, C3_VILLAGE) & 0xFF) == 0) {
        return C3_RECHARGE_NO_CHIEF;
    }
    if (TC1(0x426FC0u, 0x582618u, 4) < 1) {
        return C3_RECHARGE_NO_POWERS;
    }
    world = c3_world();
    if (world == NULL) {
        return C3_RECHARGE_NO_CHIEF;
    }
    for (k = 0; k < C3_CHIEF_POWERS; ++k) {
        if (c3_chief_power_resting(world, k)) {
            return 0;
        }
    }
    return C3_RECHARGE_READY;
}

/* The purchase itself: every resting power's stamp to the game's own ready
   0.  1, or the refusal (nothing written). */
static int c3_recharge_chief_powers(void) {
    unsigned char *world;
    int why = c3_recharge_refusal();
    int k;
    if (why != 0) {
        return why;
    }
    world = c3_world();
    for (k = 0; k < C3_CHIEF_POWERS; ++k) {
        if (c3_chief_power_resting(world, k)) {
            *(unsigned int *)(world + C3_CHIEF_POWER_STAMPS[k]) = 0;
        }
    }
    return 1;
}

static const char *c3_recharge_refusal_text(int why) {
    switch (why) {
    case C3_RECHARGE_NO_CHIEF:
        return "Your village has no Tribal Chief, so there are no chief powers to recharge. "
               "Nothing was bought.";
    case C3_RECHARGE_NO_POWERS:
        return "Your chief has no powers yet: the first comes with Leadership level 1. "
               "Nothing was bought.";
    default:
        return "Your chief's powers are all ready to use already. Nothing was bought.";
    }
}

/* Defined in vvfp_story_upgrades.c, after this file. */
static int story_installed(int game);
static const char *story_price_text(int game);
static int story_charged(int game, HWND owner, int (*command)(int game, HWND owner));

static int story_recharge_chief_powers(int game, HWND owner) {
    char message[400];
    int why;
    if (game != 3 || !story_installed(3)) {
        return 0;
    }
    why = c3_recharge_refusal();
    if (why != 0) {
        MessageBoxA(owner, c3_recharge_refusal_text(why), "Recharge Chief Powers",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    wsprintfA(message,
              "Do you want to buy Recharge Chief Powers for %s tech points?\r\n"
              "Your chief's powers become ready to use now.\r\n\r\n"
              "Press OK to confirm, or Cancel.", story_price_text(game));
    if (MessageBoxA(owner, message, "Origins Upgrades",
                    MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND) != IDOK) {
        return 0;
    }
    /* The village may have moved on while the box was open. */
    why = c3_recharge_chief_powers();
    if (why != 1) {
        MessageBoxA(owner, c3_recharge_refusal_text(why), "Recharge Chief Powers",
                    MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
        return 0;
    }
    MessageBoxA(owner, "Your chief's powers are ready to use now.", "Origins Upgrades",
                MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
    return 1;
}

/* The Recharge Chief Powers button of The Secret City's Upgrades menu
   (native/vv3_full_mastery_candidate): charged as Pick Gong of Wonder
   Outcome is.  1 when the powers were recharged. */
__declspec(dllexport) int __stdcall VvfpStoryRechargeChiefPowers(int game, HWND owner) {
    return story_charged(game, owner, story_recharge_chief_powers);
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
    if (c->unborn_name[0] != '\0' && !ce_write_name(r + 0xE48, 0x18, c->unborn_name)) {
        return 0;
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
   (on 0x428B60()), then the stop.  The body keeps its own record: no room
   is needed.  A dead chief comes back a chief even while another lives (the
   owner, 2026-10-06: allowed, with a "do this at your own risk" message,
   which the revive dialog shows). */
static int c3_revive(int index, int health, int cure) {
    unsigned char *r = c3_record(index);
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
        ce_count_gain((int *)(uintptr_t)0x5824ACu, after - before);
    }
}

static void c3_change_tech(int op, int amount) {
    int before = c3_tech();
    int after;
    ce_amount(op, amount, before, &after);
    *(int *)(uintptr_t)C3_TECH = after;
    if (after > before) {
        ce_count_gain((int *)(uintptr_t)0x5824A4u, after - before);
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
    /* The beehive: its honey store is the game's own 0..3000 (the owner, 2026-10-14). */
    if (*(int *)(uintptr_t)0x5945E0u < 3000) {
        *(int *)(uintptr_t)0x5945E0u = 3000;
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
    return ce_set_record_parents(c3_record(index), 0xDF8, 0xE11, 0x19, 23, 0xE2C, 0xE30, 0xE34, 0xE38,
                                 30, 30, c);
}

static const char *const C3_SKILLS[] = { "Farming", "Parenting", "Healing", "Research", "Building" };

typedef int (__cdecl *c3_rand_fn)(int bound);

/* The game's own rand(bound) 0x4032D0 (cdecl, 0..bound-1). */
static int c3_rand_below(int n) {
    return ((c3_rand_fn)(uintptr_t)0x4032D0u)(n);
}

/* What the game makes of a villager: the Tribal Chief (+0xE80, set by the
   robing 0x45FBC0; the chief search 0x45EF30 tests it). */
static int c3_role(const unsigned char *r, const char **words) {
    if (r[0xE80] != 0) {
        *words = "Tribal Chief";
        return STORY_KIND_TRIBAL_CHIEF;
    }
    return STORY_KIND_NONE;
}

/* A new villager to the population count 0x45E8F0 (present, health above
   0, its expected babies), the record count c3_demand and the record
   search. */
static const ce_probe_field C3_PROBE[] = {
    { 0xF10, 1, 1, 1 }, { 0xE78, 4, 90, 90 }, { 0xE94, 1, 0, 0 }, { 0xE8C, 4, 0, 0 },
};

static const ce_adapter C3_ADAPTER = {
    CAP_FOOD | CAP_TECH | CAP_REFILL | CAP_SPAWN | CAP_KILL | CAP_VANISH | CAP_SICK | CAP_PREGNANT
        | CAP_PREFS | CAP_APPEARANCE | CAP_SKILLS | CAP_PARENTS | CAP_TITLE | CAP_MASK
        | CAP_BEHAVIOUR | CAP_SPAWN_NAME | CAP_MALE_PREGNANCY | CAP_STATUS | CAP_VALUES
        | CAP_PUZZLES | CAP_CANCEL | CAP_RELITTER | CAP_UNBORN | CAP_REVIVE | CAP_CHOICE,
    "The Secret City",
    0x118, 1600,
    C3_STOCK_COUNT, 0x19, 23,
    0xDD4, 0xDC8, 0xDC4, 0xDF0, 0xDF4, 0xFB4, 0xFC0, 0xEAC,
    0, 1,
    3, 79,
    STORY_PREFERENCES_79_VV3,
    30, 30,
    5, 0, C3_SKILLS,
    0xDF8, 0xE11, 0xE2C, 0xE30, 0xE34, 0xE38,
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
    "- Revive: buried villagers (their record is gone) and skeletons that have already "
    "crumbled away. (A dead chief comes back a chief even while another lives: you "
    "are asked to confirm, at your own risk.)\r\n"
    "- Golden Child, faction, totems: The Secret City has none.\r\n"
    "- Joey as a parent: only The Tree of Life and New Believers have him (their default "
    "father); choose Custom to give any parent a name and looks.",
    48, 14, 30, 1,
    "Refills the beehive (its honey) and the three fruit trees.",
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
    48, 11, 48, 11, 0, 32, c3_rand_below, NULL, c3_role,
    C3_PROBE, (int)(sizeof C3_PROBE / sizeof C3_PROBE[0]),
    NULL, NULL, 0, c3_set_health
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

/* C3_ADAPTER with the executable's own slot count (150, or 256 with 256
   Villagers). */
static const ce_adapter *c3_adapter(void) {
    static ce_adapter adapter;
    static int ready;
    if (!ready) {
        adapter = C3_ADAPTER;
        adapter.record_count = c3_count();
        ready = 1;
    }
    return &adapter;
}
