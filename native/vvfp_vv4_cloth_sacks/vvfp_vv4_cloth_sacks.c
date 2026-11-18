/* VVFP VV4 Cloth Sacks -- "Cloth Sacks for Yellow Fruit", The Tree of Life.

   THE OWNER (2026-11-17).  The tribe makes extra cloth bolts at the Clothing Hut; this gives them a use, for the
   yellow fruit (the breadfruit of the Cooking Pit) only.  An adult dropped on the LEFT side of the Clothing Hut,
   under its awning, takes one cloth bolt, makes a sack at the hut ("Making a sack out of cloth", the research
   look), carries the empty sack to the yellow fruit trees ("Gathering food in cloth sack"), does the game's own
   shaking and cooking, and carries the full sack to the food bin ("Carrying fruit to the food bin"): 30 fruit.
   It must work like the cutting tool on the blackberries in every respect.

   THE CUTTING TOOL (read from the stock executable, the model for everything here):
     * the drop on map area 0x31 (handler 0x46E7E0, registered at 0x46FB00): with no cutting tool on hand
       ([0x4D8618] = 0) the villager refuses -- action 0x1A with text 0x12F "They need a cutting tool for this!"
       (0x46E810..0x46E836); otherwise ONE tool is used at once (0x4369F0(1) on the tools' object 0x4D8614,
       0x46E872), before anything is known about the harvest, and the harvest starts (the tool carried, item 0x12,
       then action 0xBE, 0x451CE0);
     * the harvest (0x451CE0): "Harvesting blackberries" (text 0x280), the walk to the bushes (area 0x20), three
       cuts, the Farming check (step 9, 0x469220(0): a failed check ends the trip -- the tool is gone), the
       blackberries carried (item 0x3E), the walk to the food bin (area 8), and job event 14;
     * job event 14 (0x4644EE): n = the berries left, at most 30; the food writer 0x41D920(n) -- 1 food for each
       berry, Food Mastery (tech 4) multiplying inside the writer (level 2 +half, 3 doubled), the only technology
       that changes it; the berries -= n (not below 0); fewer than 3 left: the villager's task is cleared
       (+0x1C54 = 0); over 2,000 food: tip 0x2E5;
     * no farmer the game sends ever harvests with a tool (only the drop starts action 0xBE), and a harvest is
       never a Grand Feast item: the stew pot's listener 0x42EA30 counts only items 0 (picked berries), 0x37
       (stomped fruit), 0x38 (fish) and 0x76..0x78 (mushrooms) toward the feast (table 0x42EB4C) -- the harvest's
       0x3E is none of them and it always goes to the food bin.
   THE SACK, the same way: one cloth bolt (0x4369F0(1) on the cloth's object 0x4D8AC8, count [0x4D8ACC], the
   same routine) used at the drop; no cloth: action 0x1A with text 0x136 "They need cloth for this!" (the game's
   own words for cloth); like the tool, nothing is checked about the fruit at the drop (the owner, 2026-11-17: "if
   the cutting tools allow harvesting with less than 3 fruit, so should the sacks"); the food at the bin from this companion's job event, as event 14: n = 30, or with
   "Yellow Fruit Trees are No Longer Unlimited" the fruit left, at most 30, taken from the tree there and then
   ("VVFP VV4 Fruit Supply.dll", VvfpYellowFruitTake; without it the trees are the stock game's unlimited ones and
   a sack always holds 30); 0x41D920(n); fewer than 3 fruit left: the task cleared; over 2,000 food: tip 0x2E5.
   The full sack is carried as item 0x36 (the yellow fruit), never 0x37: like the harvest's berries it is no
   Grand Feast item and never goes into the stew (the trip's stew branch, 0x4349A3, is replaced by the food bin).
   The differences the owner asked for: the fruit (the yellow fruit trees), making the sack, the game's own
   shaking and cooking in between, and the 30.

   WHAT RUNS.
     the drop      VILLAGER DROPPED: the drop dispatcher 0x46E460 (the villager's place 0x45ED00 -> its handler)
                   is entered here first.  An adult (+0x1B8C >= 0x118, as the dispatcher's own test), not
                   expecting (+0x1C4C, the dispatcher refuses those at the hut), dropped inside SACK_BOX of the
                   finished Clothing Hut (puzzle 0x16; the hut's place is its object 0x4D82D8 +0x28/+0x2C, (400,
                   1600) in the stock game; the awning is its left part) with the Cooking Pit restored (puzzle 6):
                   no cloth: the refusal above (the fruit left is not checked, as the tool does not check the
                   berries: a sack with fewer than 30 pays what is left, even 0); all
                   four of the pit's spots taken (locks 5..8 at 0x705148, 0x46D880): the tree's own (action 0x1A,
                   text 0x13C, the task cleared, as 0x43446F); otherwise the sack trip.  Anything else (a child,
                   the hut unfinished, the pit not restored, elsewhere on the hut) is the stock drop.
     farmers       The owner (2026-11-17): "farmers should never use cutting tools or sacks on their own" --
                   as no farmer the game sends ever harvests with a cutting tool, the Farming dispatcher
                   0x4639B0 is not touched: only a villager the player drops at the hut makes a sack.
     the trip      Queued with the game's own step builders: the trip's pit spot claimed at once (a copy of its
                   own first step, so the pit cannot fill up while the sack is made, as a stock trip claims its
                   spot at once), "Making a sack out of cloth" (a text step 0x468CF0), the cloth carried (item
                   0x35), the research look without its sounds -- the Researching action's working-pose waits
                   (0x469280, step type 0x0A; its 0x469CD0 steps are sounds, step type 0x19, and are left out) --
                   then this companion's event SACK_EV_MADE (the empty sack shows), "Gathering food in cloth
                   sack", then the game's own fruit trip: do-action 0x64 (0x4343A0, which picks a free spot and
                   builds that spot's trip 0x65..0x68: the walk to the trees, the shaking, the Farming check, the
                   fruit, the cooking).  Its tail -- from its last text step ("Carrying fruit to the food bin", or
                   the stew's "Adding to the stew") -- is replaced by: "Carrying fruit to the food bin" (text
                   0x240), SACK_EV_FULL (the cooked sack shows), the full sack (item 0x36), the walk to the food
                   bin (area 8), the trip's own 1-second wait and put-down (0x4693B0(1), 0x469820), and
                   SACK_EV_CREDIT, the food above.  The game's event 15 (3 food) is not queued, so the trip pays
                   only the sack.
     the events    The job events 0x4642F0 (thiscall(villager; event)) are entered here first: SACK_EV_MADE,
                   SACK_EV_FULL and SACK_EV_CREDIT are this companion's (numbers the game's table never reaches:
                   events above 74 go to its own end, 0x464EB2, so a queue the game kept without this companion
                   does nothing with them); every other event is the game's.
     the pictures  The carried item 0x466770 draws carrying.png's 40 x 40 cell through the world draw 0x44C640
                   (call at 0x4667B4), whose fifth argument is the picture's ALPHA (1.0 for every carried item;
                   the size is the map's zoom [0x4DB9F8 + 0x3010], the same for everything).  For a villager on a
                   sack trip (its queue still holds SACK_EV_CREDIT) the sack is drawn instead, with the same call,
                   alpha and zoom: after SACK_EV_MADE, item 0x35 -> Images\vvfp_sack_empty.png and item 0x36 (the
                   shaken fruit, trees to pit) -> Images\vvfp_sack_yellow_fruit_raw.png; after SACK_EV_FULL, item
                   0x36 (the cooked fruit, pit to bin) -> Images\vvfp_sack_yellow_fruit.png.  The pictures are
                   the owner's art made carried-item size (45 %, at most CELL x CELL), centred on the cell and
                   standing on CELL_FLOOR, where carrying.png's fruit and berries end.  Built once by the game's
                   ldwImageGrid 0x40AB10 (name, 1, 1) after its PNG header says 8-bit RGBA of at most CELL x CELL; a
                   missing or wrong file: the game's own picture (the cloth, the yellow fruit).  The call goes on
                   into 0x44C640, so "VVFP Golden Mushroom.dll" (which enters there) is unaffected.

   Nothing is kept: no file, nothing in the save.  A queue the game keeps holds only the game's own steps (and
   SACK_EV_* numbers the game ignores).

   Sites, all checked stock first and written all or none (native/shared/install_sites.h):
     0x46E460  8  the drop dispatcher's entry (sub esp,8 / push esi / mov esi,[esp+0x10])
     0x4642F0  7  the job events' entry (mov eax,[esp+4] / sub esp,0x18)
     0x4667B4  5  the carried item's call of the world draw 0x44C640

   SAFETY.  Our steps run under structured exception handling: a fault leaves the stock decision.  No debug
   output. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/vvfp_translate.h"

#define CS_GAME 4

/* The game. */
#define PUZZLES 0x4D8BF8u
#define PUZZLE_SOLVED 0x438960u      /* thiscall(id) */
#define PUZZLE_PIT 6                 /* The Cooking Pit restored */
#define PUZZLE_HUT 0x16              /* The Clothing Hut finished */
#define HUT 0x4D82D8u                /* the Clothing Hut's object: its place at +0x28 / +0x2C */
#define HUT_X 0x28
#define HUT_Y 0x2C
#define HUT_STOCK_PLACE 0x4BDBF0u    /* (400, 1600): what the hut's set-up 0x430C30 copies there */
#define CLOTH 0x4D8AC8u              /* the cloth's object; its count at +4 */
#define CLOTH_COUNT 0x4D8ACCu
#define USE_UP 0x4369F0u             /* thiscall(n): n used (the cutting tools' and the cloth's own) */
#define SPOTS 0x705148u
#define SPOT_TAKEN 0x46D880u         /* thiscall(lock): the lock taken */
#define DO_ACTION 0x45DEC0u
#define POSITION 0x45ED00u           /* thiscall(villager; out): its place */
#define FOOD_STORE 0x4D6DD0u
#define FOOD_ADD 0x41D920u           /* thiscall(food): Food Mastery inside */
#define TIPS 0x4DACE0u
#define TIP 0x44B890u                /* thiscall(id, 0, 0) */
#define TIP_FOOD 0x2E5
#define FOOD_TIP_ABOVE 2000

/* The step builders (thiscall on the villager), each appending one step. */
#define STEP_TEXT 0x468CF0u          /* (text): type 5 */
#define STEP_TEXT_ID 0x468D60u       /* (text id) */
#define STEP_CARRY 0x4697C0u         /* (item): type 0x11 */
#define STEP_POSE_WAIT 0x469280u     /* (seconds): type 0x0A */
#define STEP_WAIT 0x4693B0u          /* (seconds): type 0x0E */
#define STEP_PUT_DOWN 0x469820u      /* (): type 0x12 */
#define STEP_EVENT 0x469990u         /* (event): type 0x13 */
#define STEP_WALK_AREA 0x468FC0u     /* (area, 100, 0): type 3 */
#define QUEUE_START 0x46A030u
#define CLEAR_QUEUE 0x468C60u

#define T_TEXT 5
#define T_EVENT 0x13
#define T_CLAIM 0x2E                 /* a pit spot claimed (0x46A3D8 -> 0x46D530) */
#define SPOT_ARG 0x50
#define STEP_SIZE 0x58
#define STEPS 0x50

/* The villager record. */
#define REC_AGE 0x1B8C
#define REC_PREGNANT 0x1C4C
#define REC_TASK 0x1C54
#define REC_ITEM 0x1CDC
#define REC_OF_JOB 0x1B88            /* the job events' object -> the villager (event 14's own read) */
#define ADULT_AGE 0x118

/* Actions and texts. */
#define ACT_FRUIT 0x64               /* the tree's start 0x4343A0 */
#define ACT_REFUSE 0x1A
#define TXT_NEED_CLOTH 0x136         /* eSayNeedCloth "They need cloth for this!" */
#define TXT_PIT_FULL 0x13C           /* the tree's own: every spot taken */
#define TXT_TO_BIN 0x240             /* eSayCarryFruitStore "Carrying fruit to the food bin" */
#define ITEM_CLOTH 0x35
#define ITEM_YELLOW 0x36
#define AREA_BIN 8

/* The sack. */
#define SACK_FRUIT 30                /* a sack's fruit, as a harvest's berries (event 14: at most 30) */
#define SACK_EV_MADE 0x75
#define SACK_EV_FULL 0x76
#define SACK_EV_CREDIT 0x77
/* The awning: the left part of the hut picture, relative to the hut's place (the hut is drawn there, its
   finished frame 200 x 200; the awning's posts stand at about +5 and +45, the bolts of cloth from +45). */
#define SACK_BOX_LEFT (-10)
#define SACK_BOX_RIGHT 55
#define SACK_BOX_TOP 40
#define SACK_BOX_BOTTOM 135
/* carrying.png's cells are 40 x 40, drawn at 1:1 with their top-left at the carried item's place; the fruit and
   berry cells' art ends about 31 pixels down.  A sack is centred on the cell and stands on that line. */
#define CELL 40
#define CELL_FLOOR 31

/* The pictures. */
#define ALLOC 0x470C5Cu              /* operator new */
#define GRID_CTOR 0x40AB10u          /* thiscall(name, columns, rows): ldwImageGrid */
#define GRID_SIZE 0x34
#define GRID_CELL_W 0x10
#define GRID_CELL_H 0x14
#define WORLD_DRAW 0x44C640u

/* Sites. */
#define DROP_SITE 0x46E460u
#define DROP_ON 0x46E468u
#define EVENT_SITE 0x4642F0u
#define EVENT_ON 0x4642F7u
#define DRAW_SITE 0x4667B4u
#define SITES 3

static const unsigned char DROP_STOCK[8] = { 0x83, 0xEC, 0x08, 0x56, 0x8B, 0x74, 0x24, 0x10 };
static const unsigned char EVENT_STOCK[7] = { 0x8B, 0x44, 0x24, 0x04, 0x83, 0xEC, 0x18 };
static const unsigned char DRAW_STOCK[5] = { 0xE8, 0x87, 0x5E, 0xFE, 0xFF };          /* call 0x44C640 */
/* The other stock code this relies on, checked by its first bytes: the use-up routine and the tree's start. */
static const unsigned char USE_UP_STOCK[7] = { 0x8B, 0x44, 0x24, 0x04, 0x29, 0x41, 0x04 };
static const unsigned char FRUIT_START_STOCK[5] = { 0x83, 0xEC, 0x20, 0x53, 0x33 };

static int g_installed;

/* ---- the fruit supply --------------------------------------------------------------------------------------- */

typedef int (__stdcall *fruit_left_fn)(void);
typedef int (__stdcall *fruit_take_fn)(int want);
static fruit_left_fn g_fruit_left;
static fruit_take_fn g_fruit_take;
static int g_fruit_bound;

/* "Yellow Fruit Trees are No Longer Unlimited" ("VVFP VV4 Fruit Supply.dll"), when loaded. */
static void bind_fruit(void) {
    HMODULE m;
    if (g_fruit_bound) {
        return;
    }
    m = GetModuleHandleW(L"VVFP VV4 Fruit Supply.dll");
    if (m == NULL) {
        return;                      /* not (yet) loaded: asked again next time */
    }
    g_fruit_left = (fruit_left_fn)(void *)GetProcAddress(m, "VvfpYellowFruitLeft");
    g_fruit_take = (fruit_take_fn)(void *)GetProcAddress(m, "VvfpYellowFruitTake");
    g_fruit_bound = 1;
}

/* The fruit left on the tree, or -1: the stock game's unlimited tree. */
static int fruit_left(void) {
    bind_fruit();
    return g_fruit_left != NULL ? g_fruit_left() : -1;
}

/* ---- the game's calls --------------------------------------------------------------------------------------- */

typedef char (__fastcall *solved_fn)(void *self, void *unused, int id);
typedef int (__fastcall *use_fn)(void *self, void *unused, int n);
typedef char (__fastcall *taken_fn)(void *self, void *unused, int lock);
typedef char (__fastcall *do_action_fn)(void *self, void *unused, int action, void *block);
typedef int *(__fastcall *position_fn)(void *self, void *unused, int *out);
typedef void (__fastcall *food_fn)(void *self, void *unused, int food);
typedef void (__fastcall *tip_fn)(void *self, void *unused, int id, int a, int b);
typedef void (__fastcall *step1_fn)(void *self, void *unused, int arg);
typedef void (__fastcall *step0_fn)(void *self, void *unused);
typedef void (__fastcall *walk_fn)(void *self, void *unused, int area, int speed, int front);

static int solved(int id) {
    return ((solved_fn)(UINT_PTR)PUZZLE_SOLVED)((void *)(UINT_PTR)PUZZLES, NULL, id) != 0;
}

static int cloth_on_hand(void) {
    return *(const int *)(UINT_PTR)CLOTH_COUNT > 0;
}

/* A free spot at the pit (the tree's start 0x4343A0 tests locks 5..8 the same way). */
static int spot_free(void) {
    int lock;
    for (lock = 5; lock <= 8; ++lock) {
        if (!((taken_fn)(UINT_PTR)SPOT_TAKEN)((void *)(UINT_PTR)SPOTS, NULL, lock)) {
            return 1;
        }
    }
    return 0;
}

static void act(unsigned char *villager, int action, int text, int second) {
    int block[8];
    memset(block, 0, sizeof block);
    block[0] = text;
    block[1] = second;
    ((do_action_fn)(UINT_PTR)DO_ACTION)(villager, NULL, action, block);
}

static void step1(unsigned int builder, unsigned char *villager, int arg) {
    ((step1_fn)(UINT_PTR)builder)(villager, NULL, arg);
}

/* ---- the sack trips ----------------------------------------------------------------------------------------- */

/* The villagers on a sack trip and what they show: 1 the empty sack, 2 the full one. */
typedef struct {
    const unsigned char *villager;
    int shows;
} sack_mark;
#define MARKS 64
static sack_mark g_marks[MARKS];

static const unsigned char *step_at(const unsigned char *villager, int i) {
    return villager + i * STEP_SIZE;
}

/* The villager's queue still ends in a sack's food (a cleared or replaced queue: no longer a sack trip). */
static int on_sack_trip(const unsigned char *villager) {
    int i;
    for (i = 0; i < STEPS; ++i) {
        const unsigned int *s = (const unsigned int *)step_at(villager, i);
        if (s[0] == 0) {
            return 0;
        }
        if (s[0] == T_EVENT && s[1] == SACK_EV_CREDIT) {
            return 1;
        }
    }
    return 0;
}

static sack_mark *mark_of(const unsigned char *villager, int make) {
    int i;
    sack_mark *free_mark = NULL;
    for (i = 0; i < MARKS; ++i) {
        if (g_marks[i].villager == villager) {
            return &g_marks[i];
        }
        if (free_mark == NULL && (g_marks[i].villager == NULL || !on_sack_trip(g_marks[i].villager))) {
            free_mark = &g_marks[i];
        }
    }
    if (make && free_mark != NULL) {
        free_mark->villager = villager;
        free_mark->shows = 0;
        return free_mark;
    }
    return NULL;
}

static void unmark(const unsigned char *villager) {
    sack_mark *m = mark_of(villager, 0);
    if (m != NULL) {
        m->villager = NULL;
        m->shows = 0;
    }
}

/* The captions (each at most 38 letters: the villager's caption field takes 39, 0x4724E0 with 0x27). */
static const char *caption_making(void) {
    return vvfp_tr("vvfp.cloth_sacks/vvfp_vv4_cloth_sacks.caption_making.s0", "Making a sack out of cloth", 39);
}

static const char *caption_gathering(void) {
    return vvfp_tr("vvfp.cloth_sacks/vvfp_vv4_cloth_sacks.caption_gathering.s0", "Gathering food in cloth sack", 39);
}

/* The pit spot the fruit trip claims (its first step, type 0x2E, lock 5..8 at +0x50: 0x4698D0), claimed at once
   as well: a copy of that step goes before the making, at `start`, and the queue is started again when the
   villager had nothing queued before.  The stock fruit trip claims its spot at once too (its first step), so no
   one else can take the spot meanwhile; the trip's own claim still runs after the making (the lock's 45-second
   timeout, 0x46D563, then runs from there, as for a stock trip).  An interrupted trip leaves the spot to that
   timeout, as a stock trip does. */
static void hold_spot(unsigned char *villager, int start, int first) {
    int i, last;
    for (last = first; last < STEPS && *(const unsigned int *)step_at(villager, last) != 0; ++last) {
    }
    if (last >= STEPS) {
        return;                      /* a full queue: no room for the copy (the trip's own claim remains) */
    }
    for (i = first; i < last; ++i) {
        const unsigned int *s = (const unsigned int *)step_at(villager, i);
        if (s[0] == T_CLAIM && s[SPOT_ARG / 4] >= 5 && s[SPOT_ARG / 4] <= 8) {
            unsigned char claim[STEP_SIZE];
            memcpy(claim, s, STEP_SIZE);
            memmove((unsigned char *)step_at(villager, start + 1), step_at(villager, start),
                    (size_t)(last - start) * STEP_SIZE);
            memcpy((unsigned char *)step_at(villager, start), claim, STEP_SIZE);
            if (start == 0) {
                ((step0_fn)(UINT_PTR)QUEUE_START)(villager, NULL);
            }
            return;
        }
    }
}

/* The sack trip, queued behind whatever the villager already has (as every action handler does).  The cloth is
   used here, at once, as the cutting tool is. */
static void start_trip(unsigned char *villager) {
    int i, start, first, last_text = -1;
    ((use_fn)(UINT_PTR)USE_UP)((void *)(UINT_PTR)CLOTH, NULL, 1);
    unmark(villager);
    for (start = 0; start < STEPS && *(const unsigned int *)step_at(villager, start) != 0; ++start) {
    }
    ((step1_fn)(UINT_PTR)STEP_TEXT)(villager, NULL, (int)(UINT_PTR)caption_making());
    step1(STEP_CARRY, villager, ITEM_CLOTH);
    /* The research look, silent: the Researching action's own waits (0x4537D9, 0x45388F: step type 0x0A, the
       working pose), without its two sound steps (0x469CD0 is step type 0x19, a sound played at the villager --
       1 and 0x67 there -- not an animation). */
    step1(STEP_POSE_WAIT, villager, 6);
    step1(STEP_POSE_WAIT, villager, 6);
    step1(STEP_EVENT, villager, SACK_EV_MADE);
    ((step1_fn)(UINT_PTR)STEP_TEXT)(villager, NULL, (int)(UINT_PTR)caption_gathering());
    for (first = 0; first < STEPS && *(const unsigned int *)step_at(villager, first) != 0; ++first) {
    }
    /* The game's own fruit trip, after ours. */
    act(villager, ACT_FRUIT, 0, 0);
    for (i = first; i < STEPS; ++i) {
        const unsigned int *s = (const unsigned int *)step_at(villager, i);
        if (s[0] == 0) {
            break;
        }
        if (s[0] == T_TEXT) {
            last_text = i;
        }
    }
    hold_spot(villager, start, first);
    if (last_text < first) {
        /* The fruit trip was not built (it cannot be: every test it makes was made first): no trip at all. */
        ((step0_fn)(UINT_PTR)CLEAR_QUEUE)(villager, NULL);
        return;
    }
    for (i = last_text; i < STEPS; ++i) {
        memset((unsigned char *)step_at(villager, i), 0, STEP_SIZE);
    }
    step1(STEP_TEXT_ID, villager, TXT_TO_BIN);
    step1(STEP_EVENT, villager, SACK_EV_FULL);
    step1(STEP_CARRY, villager, ITEM_YELLOW);
    ((walk_fn)(UINT_PTR)STEP_WALK_AREA)(villager, NULL, AREA_BIN, 100, 0);
    step1(STEP_WAIT, villager, 1);
    ((step0_fn)(UINT_PTR)STEP_PUT_DOWN)(villager, NULL);
    step1(STEP_EVENT, villager, SACK_EV_CREDIT);
    (void)mark_of(villager, 1);
}

/* The villager's place is under the finished hut's awning. */
static int under_awning(unsigned char *villager) {
    int out[2];
    const int *place;
    const int *hut = (const int *)(UINT_PTR)HUT;
    int x = hut[HUT_X / 4], y = hut[HUT_Y / 4];
    if (x == 0 && y == 0) {
        x = ((const int *)(UINT_PTR)HUT_STOCK_PLACE)[0];
        y = ((const int *)(UINT_PTR)HUT_STOCK_PLACE)[1];
    }
    place = ((position_fn)(UINT_PTR)POSITION)(villager, NULL, out);
    return place[0] >= x + SACK_BOX_LEFT && place[0] < x + SACK_BOX_RIGHT
           && place[1] >= y + SACK_BOX_TOP && place[1] < y + SACK_BOX_BOTTOM;
}

/* A villager dropped: 1 handled here (the sack trip or a refusal), 0 the stock drop. */
static int __cdecl on_drop(unsigned char *villager) {
    int handled = 0;
    __try {
        if (villager == NULL || *(const int *)(villager + REC_AGE) < ADULT_AGE
            || *(const int *)(villager + REC_PREGNANT) != 0 || !solved(PUZZLE_HUT) || !solved(PUZZLE_PIT)
            || !under_awning(villager)) {
            return 0;
        }
        handled = 1;
        if (!cloth_on_hand()) {
            act(villager, ACT_REFUSE, TXT_NEED_CLOTH, 0);
        } else if (!spot_free()) {
            *(int *)(villager + REC_TASK) = 0;
            act(villager, ACT_REFUSE, TXT_PIT_FULL, 0);
        } else {
            start_trip(villager);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return handled;
}

/* The companion's job events: 1 handled here, 0 the game's. */
static int __cdecl on_event(unsigned char *job, int event) {
    if (event != SACK_EV_MADE && event != SACK_EV_FULL && event != SACK_EV_CREDIT) {
        return 0;
    }
    __try {
        unsigned char *villager = *(unsigned char **)(job + REC_OF_JOB);
        sack_mark *m;
        if (event == SACK_EV_CREDIT) {
            int n = SACK_FRUIT, left;
            int taken;
            bind_fruit();
            taken = g_fruit_take != NULL ? g_fruit_take(SACK_FRUIT) : -1;
            if (taken >= 0) {
                n = taken;
            }
            ((food_fn)(UINT_PTR)FOOD_ADD)((void *)(UINT_PTR)FOOD_STORE, NULL, n);
            left = fruit_left();
            if (left >= 0 && left < 3 && villager != NULL) {
                *(int *)(villager + REC_TASK) = 0;
            }
            unmark(villager);
            if (*(const int *)(UINT_PTR)FOOD_STORE > FOOD_TIP_ABOVE) {
                ((tip_fn)(UINT_PTR)TIP)((void *)(UINT_PTR)TIPS, NULL, TIP_FOOD, 0, 0);
            }
        } else if (villager != NULL && (m = mark_of(villager, 1)) != NULL) {
            m->shows = event == SACK_EV_MADE ? 1 : 2;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 1;
}

/* ---- the pictures ------------------------------------------------------------------------------------------- */

typedef void *(__cdecl *alloc_fn)(unsigned int size);
typedef void *(__fastcall *grid_ctor_fn)(void *self, void *unused, const char *name, int columns, int rows);

/* The three carried sacks, each one picture already at the size of a carried item (the game draws carrying.png's
   cells, 40 x 40, at 1:1; scripts/build_vv4_cloth_sacks_features.py makes these from the owner's art at 45 %). */
#define ART_EMPTY 0
#define ART_RAW 1                    /* the shaken fruit, carried from the trees to the Cooking Pit */
#define ART_COOKED 2                 /* the cooked fruit, carried to the food bin */
#define ARTS 3
static const char *const SACK_ART[ARTS] = {
    "vvfp_sack_empty.png", "vvfp_sack_yellow_fruit_raw.png", "vvfp_sack_yellow_fruit.png",
};
static void *g_art[ARTS];
static int g_art_state[ARTS];        /* 0 not tried, 1 built, -1 not usable */

/* Images\<name> says 8-bit RGBA, at most CELL x CELL, in its PNG header. */
static int art_file_fits(const char *name) {
    static const unsigned char SIGNATURE[16] = {
        0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 'I', 'H', 'D', 'R',
    };
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char leaf[64];
    unsigned char header[26];
    DWORD got = 0;
    HANDLE file;
    int ok;
    wsprintfA(leaf, "Images\\%s", name);
    if (!vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, leaf)) {
        return 0;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = ReadFile(file, header, sizeof header, &got, NULL) && got == sizeof header
        && memcmp(header, SIGNATURE, sizeof SIGNATURE) == 0
        && header[16] == 0 && header[17] == 0 && header[18] == 0 && header[19] >= 1 && header[19] <= CELL
        && header[20] == 0 && header[21] == 0 && header[22] == 0 && header[23] >= 1 && header[23] <= CELL
        && header[24] == 8 && header[25] == 6;
    CloseHandle(file);
    return ok;
}

static void *sack_art(int which) {
    if (g_art_state[which] == 0) {
        unsigned char *made;
        g_art_state[which] = -1;
        if (!art_file_fits(SACK_ART[which])) {
            return NULL;
        }
        made = (unsigned char *)((alloc_fn)(UINT_PTR)ALLOC)(GRID_SIZE);
        if (made == NULL) {
            return NULL;
        }
        memset(made, 0, GRID_SIZE);
        ((grid_ctor_fn)(UINT_PTR)GRID_CTOR)(made, NULL, SACK_ART[which], 1, 1);
        if (*(const int *)(made + GRID_CELL_W) <= 0 || *(const int *)(made + GRID_CELL_W) > CELL
            || *(const int *)(made + GRID_CELL_H) <= 0 || *(const int *)(made + GRID_CELL_H) > CELL) {
            return NULL;             /* not loaded as one carried-size cell: never drawn (the object is kept) */
        }
        g_art[which] = made;
        g_art_state[which] = 1;
    }
    return g_art_state[which] == 1 ? g_art[which] : NULL;
}

/* The carried item about to be drawn (`args`: sprite, x, y, frame, alpha): for a villager on a sack trip, a sack's
   picture in the cell's place -- the same call, alpha and zoom as every carried item (the fifth argument of
   0x44C640 is the ALPHA, 1.0 for every carried item: it reaches 0x408DC0 as the picture's opacity; the size is the
   map's own zoom, [0x4DB9F8 + 0x3010]), centred on the 40-pixel cell and standing on the line where carrying.png's
   fruit and berries end (CELL_FLOOR). */
static void __cdecl on_draw(const unsigned char *villager, unsigned int *args) {
    __try {
        const sack_mark *m;
        int item, which;
        const unsigned char *art;
        if (villager == NULL) {
            return;
        }
        item = *(const int *)(villager + REC_ITEM);
        if (item != ITEM_CLOTH && item != ITEM_YELLOW) {
            return;
        }
        m = mark_of(villager, 0);
        if (m == NULL || m->shows == 0 || !on_sack_trip(villager)) {
            return;
        }
        if (m->shows == 1) {
            which = item == ITEM_CLOTH ? ART_EMPTY : ART_RAW;   /* the empty sack, then the shaken fruit */
        } else if (item == ITEM_YELLOW) {
            which = ART_COOKED;
        } else {
            return;
        }
        art = (const unsigned char *)sack_art(which);
        if (art == NULL) {
            return;
        }
        args[0] = (unsigned int)(UINT_PTR)art;
        args[1] += (unsigned int)((CELL - *(const int *)(art + GRID_CELL_W)) / 2);
        args[2] += (unsigned int)(CELL_FLOOR - *(const int *)(art + GRID_CELL_H));
        args[3] = 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* ---- the stubs ---------------------------------------------------------------------------------------------- */

static unsigned int g_world_draw = WORLD_DRAW;

/* At DROP_SITE ([esp+4] the villager): 1 from on_drop answers the drop (al = 1, ret 4); else the stock entry. */
__declspec(naked) static void drop_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 36]
        call on_drop
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz stock
        mov al, 1
        ret 4
    stock:
        sub esp, 8
        push esi
        mov esi, dword ptr [esp + 0x10]
        push DROP_ON
        ret
    }
}

/* At EVENT_SITE (ecx the job events' object, [esp+4] the event): ours (ret 4) or the stock entry. */
__declspec(naked) static void event_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 36]
        push ecx
        call on_event
        add esp, 8
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz stock
        ret 4
    stock:
        mov eax, dword ptr [esp + 4]
        sub esp, 0x18
        push EVENT_ON
        ret
    }
}

/* At DRAW_SITE, called in place of 0x44C640 ([esp] the return, then sprite, x, y, frame, scale; the villager is
   the carried-item draw's first argument, [esp+0x2C]): the arguments perhaps changed, then 0x44C640. */
__declspec(naked) static void draw_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 36]
        push eax
        push dword ptr [esp + 0x50]
        call on_draw
        add esp, 8
        popad
        jmp dword ptr [g_world_draw]
    }
}

/* ---- installing --------------------------------------------------------------------------------------------- */

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpClothSacksInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[SITES];
    (void)shipped;
    if (g_installed || game != CS_GAME
        || !vvfp_site_holds(USE_UP, USE_UP_STOCK, sizeof USE_UP_STOCK)
        || !vvfp_site_holds(0x4343A0u, FRUIT_START_STOCK, sizeof FRUIT_START_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], DROP_SITE, sizeof DROP_STOCK, DROP_STOCK, 0xE9, (const void *)drop_stub);
    vvfp_site_branch(&w[1], EVENT_SITE, sizeof EVENT_STOCK, EVENT_STOCK, 0xE9, (const void *)event_stub);
    vvfp_site_branch(&w[2], DRAW_SITE, sizeof DRAW_STOCK, DRAW_STOCK, 0xE8, (const void *)draw_stub);
    if (vvfp_install_sites(w, SITES)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
