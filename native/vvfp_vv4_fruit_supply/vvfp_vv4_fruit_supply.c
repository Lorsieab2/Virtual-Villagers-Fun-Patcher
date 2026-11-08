/* VVFP VV4 Fruit Supply -- "Yellow Fruit Trees are No Longer Unlimited", The Tree of Life.

   THE STOCK GAME.  Once the Cooking Pit is restored (puzzle 6, the CFruitwells object, vtable 0x48E890, built by
   0x436510), the yellow fruit tree never runs out.  A villager dropped on it (the tree's area handler 0x435970,
   message 0) starts "Attempting to retrieve fruit" (action 100, 0x4343A0); a Farming choice may be sent there by
   the farming dispatcher, which offers the fruit whenever the Cooking Pit is restored and the game is not
   catching up (0x463A1B..0x463A40); a player task 2 (never set by the stock game) asks for it through the task
   gate (0x46364E).  A trip that reaches the food bin credits 3 food (job event 15, 0x46456C: push 3 / the food
   writer 0x41D920); a trip whose stomped fruit is diverted to the stew (0x4349A3 -> action 0x90) puts it in the pot
   when it is dropped at the cauldron (the stew's item listener 0x42EA30, item 0x37 -> 0x42EAE7); while catching up
   the Cooking Pit bonus (0x468A7A..0x468AC5) adds 5 food (x Food Mastery) for a working villager on
   rand(100) < Farming - 25, or always with task 2 (0x468AAB).

   WHAT THIS CHANGES.  The tree holds at most 1,000 fruit, kept by this companion:
     * a trip's food-bin credit (job event 15) takes 3 fruit; with fewer than 3 left it credits no food and takes
       nothing (the jump goes to the event's own end, 0x464EB0);
     * a stomped fruit that goes into the stew takes 3 fruit at the moment the cauldron takes it (0x42EAE7; down to
       0 -- the stew itself is the game's);
     * the Cooking Pit bonus takes 5 fruit each time it pays; with fewer than 5 left it pays nothing (and skips its
       Farming practice check, 0x468AB7..0x468AC5: there was no fruit to work with); its rand(100) is still drawn;
     * with fewer than 3 fruit left, a villager dropped on the tree gets the game's own refusal for an empty food
       source -- the blackberry bush's (0x46F881..0x46F89C): action 0x3F with "There is not enough to harvest."
       (text 0xA7) -- and the farming dispatcher and the task gate do not offer the fruit;
     * the tree is refilled to 1,000 every 40 age units -- counted as the game counts them: each age unit the life
       tick 0x468430 processes for one living villager (the reference, re-chosen when it dies), at 0x468AD6, which
       every processed unit reaches, live and while catching up (time away, as clamped by the game's own aging, and
       Time Warp alike) -- 4 hours of play on Normal, 2 on Fast, 6 h 40 min on Slow;
     * a Custom Island Event's "Refill the food sources" fills the tree to 1,000 (VvfpYellowFruitRefill, called by
       VVFP Story Upgrades.dll; no stock island event refills the tree);
     * one more island event, "A Closer Look" about the breadfruit (THE EVENT below), adds FS_EVENT_GAIN fruit;
     * clicking the tree (its area handler's message 2, which the stock game ignores for the tree) shows
       "Fruit remaining: N" on the game's own status line (0x4DB8E8 via 0x44C3A0), as the blackberry bush shows
       "Berries remaining: N" (0x46F82A, text 0x115).
   Nothing else: the trips, the Farming check, the stew and the bonus odds are the game's own.

   THE FILE.  The count is kept per save in
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Fruit Trees\
           Virtual Villagers 4 Yellow Fruit Tree - Save <S>.dat
   (sidecar_io.h: atomic writes, an unreadable file never replaced, an invalid one set aside), written when the
   game saves the Cooking Pit (CFruitwells vtable slot 4, 0x433CB0, called by the puzzles' save 0x438810), with
   the living villagers' identities (gender, name and parents' names, as the Origins companion's fingerprint).  It
   is used for the village only while at least one of those villagers is alive in it; otherwise -- a new village,
   Start Over, another village in the slot -- the tree starts full.  After the game loads the puzzles (slot 3,
   0x433820) the file is read again.  Start Over also empties the save's folder (native/shared/save_reset.c).
   The save itself is never written: without this companion the game is exactly stock.

   THE EVENT.  The owner (2026-11-08): a second "A Closer Look", for the yellow fruit tree.  The island-event
   selector 0x418000 collects every slot 1..49 of the event table 0x4CCA28 that holds an object whose condition
   (vtable +0x04) holds, and picks one of them uniformly (rand(n), 0x4180A6); a NULL slot is skipped
   (0x418057).  Slot 19 is NULL in the stock game (the table builder 0x416FF0 never writes it: The Salty Air
   has strings and no object), so this companion puts its own object there, once, at install: the event then
   takes an equal share like any other slot whose condition holds, and nothing else changes -- the 8-15 h timer
   and the Island Events Seen count are the scheduler's (before and after the selector), the rescue rule
   (0x4180A5..0x4180F2) still forces slot 25, and the per-slot "shown" byte 0x4CC9F4+19 is never read.  The
   object is a copy of A Closer Look's (vtable 0x48C84C, RTTI locator included) with:
     +0x00  the teardown 0x417760 calls it with "delete" at exit: nothing (the object is this DLL's);
     +0x04  the condition: the Cooking Pit restored (0x438960(6) on 0x4D8BF8, the fruit's own test) and then
            the berry event's own condition 0x415E00 run on this object -- one living villager of any age
            (0x4679B0(-1,-1,-1,1,1,-1,0,0,0) != 0), kept at +4 as the villager shown;
     +0x0C  the text id EV_TEXT_ID (0x2E7): an id no string-table entry has and no code pushes, whose index slot
            (0x4DEA20 + 4*id, what the lookup 0x44D3D0 reads) is pointed at this DLL's entry just before the id
            is returned -- its text is the owner's, in the player's language when a translation has it;
     +0x30  the result: the tree gains FS_EVENT_GAIN fruit, to at most 1,000.  The berry event's own result also
            moves its farmer to the bushes (0x414B4A..0x414B65); no place at the tree was proven, so this one
            leaves the villager as they are.
   The title is the berry event's own (+0x08, id 0x342 "A Closer Look").  Without this companion slot 19 stays
   NULL, so the event does not exist.

   Sites, all checked stock before anything is written, and written all or none (native/shared/install_sites.h):
     0x46456C  12  the credit's push 3 / food writer call
     0x463A38  11  the dispatcher's "offer the fruit"
     0x46364E   7  the task gate's fruit start
     0x4359B8   7  the drop on the tree's fruit start
     0x43597A   5  the tree handler's message test (message 2: the readout)
     0x468AAB  12  the Cooking Pit bonus's push 5 / food writer call
     0x468AD6   8  the life tick's processed unit (lea ecx,[esi+0x20] / call 0x46AD50)
     0x42EAE7   7  the stew's "stomped fruit is in" flag
     0x48E8A0   4  CFruitwells vtable slot 4 (save)
     0x48E89C   4  CFruitwells vtable slot 3 (load)
     0x4CCA74   4  the island-event table's slot 19 (NULL): the event object

   SAFETY.  Our steps run under structured exception handling: a fault leaves the stock decision (the fruit
   offered, the food paid).  No debug output. */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/sidecar_io.h"
#include "../shared/game_save_slot.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vvfp_translate.h"

#define FS_GAME 4
#define FS_FULL 1000
#define FS_TRIP 3                    /* fruit a food-bin credit or a stewed fruit takes */
#define FS_BONUS 5                   /* fruit a Cooking Pit bonus takes */
#define FS_REFILL_UNITS 40           /* age units between refills */

#define FOOD_STORE 0x4D6DD0u
#define FOOD_ADD 0x41D920u
#define DO_ACTION 0x45DEC0u
#define STATUS_LINE 0x4DB8E8u
#define STATUS_SHOW 0x44C3A0u        /* thiscall(text): the status line shows it for 5 seconds */
#define REFUSE_ACTION 0x3F
#define REFUSE_TEXT 0xA7             /* eSayNotEnoughToHarvest */
#define LIFE_ADVANCE 0x46AD50u

/* The villager record. */
#define REC_STRIDE 0x2E3Cu
#define REC_FIRST 0x44u              /* the manager's first record */
#define REC_SEX 0x1B90u
#define REC_NAME 0x1B9Cu
#define REC_FATHER 0x1BC0u
#define REC_MOTHER 0x1BD9u
#define REC_PROC_AGE 0x1C3Cu         /* the life tick's esi */
#define REC_OCCUPIED 0x1CC4u
#define ROSTER_MAX 256

/* Sites. */
#define CREDIT_SITE 0x46456Cu
#define CREDIT_ON 0x464578u
#define CREDIT_END 0x464EB0u
#define OFFER_SITE 0x463A38u
#define OFFER_ON 0x463A43u
#define TASK_SITE 0x46364Eu
#define TASK_ON 0x463655u
#define TASK_EMPTY 0x463636u         /* the empty bush's own way out: the task cleared, done */
#define DROP_SITE 0x4359B8u
#define DROP_ON 0x4359BFu
#define DROP_DONE 0x4359C9u
#define CLICK_SITE 0x43597Au
#define CLICK_HELD 0x43597Fu
#define CLICK_DONE 0x4359DEu
#define BONUS_SITE 0x468AABu
#define BONUS_ON 0x468AB7u
#define BONUS_NONE 0x468ACAu
#define UNIT_SITE 0x468AD6u
#define UNIT_ON 0x468ADEu
#define STEW_SITE 0x42EAE7u
#define STEW_ON 0x42EAEEu
#define VTABLE 0x48E890u
#define SLOT_LOAD 3
#define SLOT_SAVE 4
#define STOCK_LOAD 0x433820u
#define STOCK_SAVE 0x433CB0u
#define EVENT_SLOT_VA 0x4CCA74u      /* 0x4CCA28 + 4 * 19 */
#define BERRY_VTABLE 0x48C84Cu       /* CEventACloserLook */
#define BERRY_CONDITION 0x415E00u
#define BERRY_TITLE_ID 0x414B10u     /* its +0x08: mov eax, 0x342 */
#define BERRY_TEXT_ID 0x414B20u
#define BERRY_RESULT 0x414B30u
#define PUZZLES 0x4D8BF8u
#define PUZZLE_SOLVED 0x438960u      /* thiscall(id): the puzzle solved */
#define PUZZLE_COOKING_PIT 6
#define STRING_INDEX 0x4DEA20u       /* the string lookup's pointer per id */
#define EV_TEXT_ID 0x2E7
#define FS_EVENT_GAIN 350            /* fruit the event adds (the berry event adds 350 berries, 0x414B38) */
#define SITES 11

static const unsigned char CREDIT_STOCK[12] = { 0x6A, 0x03, 0xB9, 0xD0, 0x6D, 0x4D, 0x00, 0xE8, 0xA8, 0x93, 0xFB, 0xFF };
static const unsigned char OFFER_STOCK[11] = { 0xC7, 0x44, 0xBC, 0x1C, 0x02, 0x00, 0x00, 0x00, 0x83, 0xC7, 0x01 };
static const unsigned char TASK_STOCK[7] = { 0x8D, 0x44, 0x24, 0x0C, 0x50, 0x6A, 0x64 };
static const unsigned char DROP_STOCK[7] = { 0x8D, 0x54, 0x24, 0x08, 0x52, 0x6A, 0x64 };
static const unsigned char CLICK_STOCK[5] = { 0x83, 0xE8, 0x01, 0x75, 0x5F };
static const unsigned char BONUS_STOCK[12] = { 0x6A, 0x05, 0xB9, 0xD0, 0x6D, 0x4D, 0x00, 0xE8, 0x69, 0x4E, 0xFB, 0xFF };
static const unsigned char UNIT_STOCK[8] = { 0x8D, 0x4E, 0x20, 0xE8, 0x72, 0x22, 0x00, 0x00 };
static const unsigned char STEW_STOCK[7] = { 0xC6, 0x86, 0x1F, 0x0B, 0x00, 0x00, 0x01 };
/* The other bytes the stubs rely on: the credit's call of the food writer resolves to 0x41D920, the bonus's too,
   the unit site's call to 0x46AD50 (checked through the bytes above), and the empty way out of the task gate. */
static const unsigned char TASK_EMPTY_STOCK[7] = { 0x8B, 0x96, 0x88, 0x1B, 0x00, 0x00, 0x5F };
static const unsigned char DROP_DONE_STOCK[4] = { 0xB0, 0x01, 0x59, 0xC3 };

/* ---- the tree --------------------------------------------------------------------------------------------- */

static int g_installed;
static int g_bound;                  /* the state below is a village's */
static int g_slot;                   /* its slot (0: not known) */
static int g_fruit = FS_FULL;
static int g_units;                  /* age units counted since the last refill (0..39) */
static unsigned int g_roster[ROSTER_MAX];   /* its living villagers, last seen */
static DWORD g_checked;              /* GetTickCount() of the last roster check */
static const unsigned char *g_reference;    /* the villager whose processed units are counted */
static unsigned int g_reference_id;
static vv_sidecar_gate g_gate;

static const unsigned char *g_records;
static int g_slots;

static void locate(void) {
    unsigned int rva = 0, slots = 0;
    const unsigned char *module;
    if (g_records != NULL) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleW(NULL);
    if (module == NULL) {
        return;
    }
    vv4_villager_table(module, &rva, &slots);
    g_records = module + rva + REC_FIRST;
    g_slots = (int)slots;
}

/* The Origins companion's identity (vv4_origins_icons.c vv_fingerprint): gender, name and the parents' names.
   Never 0. */
static unsigned int identity(const unsigned char *rec) {
    unsigned int h = 2166136261u;
    unsigned int sex = *(const unsigned int *)(rec + REC_SEX);
    int i;
    for (i = 0; i < 4; i++) {
        h = (h ^ ((const unsigned char *)&sex)[i]) * 16777619u;
    }
    for (i = 0; i < 25 && rec[REC_NAME + i]; i++) {
        h = (h ^ rec[REC_NAME + i]) * 16777619u;
    }
    h = (h ^ 0xFFu) * 16777619u;
    for (i = 0; i < 25 && rec[REC_FATHER + i]; i++) {
        h = (h ^ rec[REC_FATHER + i]) * 16777619u;
    }
    h = (h ^ 0xFEu) * 16777619u;
    for (i = 0; i < 25 && rec[REC_MOTHER + i]; i++) {
        h = (h ^ rec[REC_MOTHER + i]) * 16777619u;
    }
    h = (h ^ 0xFDu) * 16777619u;
    return h ? h : 1u;
}

/* The living villagers' identities, by record; how many. */
static int roster_now(unsigned int *out) {
    int i, n = 0;
    memset(out, 0, sizeof(unsigned int) * ROSTER_MAX);
    locate();
    if (g_records == NULL || g_slots <= 0 || g_slots > ROSTER_MAX) {
        return 0;
    }
    for (i = 0; i < g_slots; ++i) {
        const unsigned char *rec = g_records + (unsigned int)i * REC_STRIDE;
        if (rec[REC_OCCUPIED] != 0) {
            out[i] = identity(rec);
            ++n;
        }
    }
    return n;
}

/* At least one villager of `was` is alive in `now` (a reload builds the roster over several frames, and births
   and deaths change it: never an exact match; Start Over's founders share no one). */
static int same_village(const unsigned int *was, const unsigned int *now) {
    int i, k;
    for (i = 0; i < ROSTER_MAX; ++i) {
        if (was[i] == 0u) {
            continue;
        }
        for (k = 0; k < ROSTER_MAX; ++k) {
            if (now[k] == was[i]) {
                return 1;
            }
        }
    }
    return 0;
}

/* ---- the file --------------------------------------------------------------------------------------------- */

#define FILE_MAGIC 0x46345656u       /* 'V' 'V' '4' 'F' */
#define FILE_VERSION 1u

#pragma pack(push, 1)
typedef struct {
    unsigned int magic, version, game, slot;
    unsigned int fruit;              /* 0..1000 */
    unsigned int units;              /* age units since the last refill, 0..39 */
    unsigned int count;              /* living villagers in roster[] */
    unsigned int reserved;
    unsigned int roster[ROSTER_MAX]; /* their identities, by record (0: none) */
} fruit_file;
#pragma pack(pop)

/* "<Documents>\LDW\<executable's name>\Virtual Villagers Fun Patcher\Save <S>\Data\Fruit Trees\
   Virtual Villagers 4 Yellow Fruit Tree - Save <S>.dat"; `make` creates the folders. */
static int fruit_path(int slot, char *out, int make) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base = exe, *p, *dot = NULL;
    static const char *const LEVELS[4] = {
        "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data", "\\Fruit Trees"
    };
    char part[64];
    int i;
    DWORD n;
    if (slot < 1 || slot > 5 || !SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    for (p = exe; *p != '\0'; ++p) {
        if (*p == '\\') {
            base = p + 1;
            dot = NULL;
        } else if (*p == '.') {
            dot = p;
        }
    }
    if (dot != NULL) {
        *dot = '\0';
    }
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 170 >= MAX_PATH) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    for (i = 0; i < 4; ++i) {
        wsprintfA(part, LEVELS[i], slot);
        lstrcatA(out, part);
        if (make) {
            CreateDirectoryA(out, NULL);
        }
    }
    wsprintfA(part, "\\Virtual Villagers 4 Yellow Fruit Tree - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const fruit_file *f = (const fruit_file *)data;
    return len == sizeof(fruit_file) && f->magic == FILE_MAGIC && f->version == FILE_VERSION
           && f->game == FS_GAME && f->slot == (unsigned int)*(int *)ctx && f->fruit <= FS_FULL
           && f->units < FS_REFILL_UNITS && f->count <= ROSTER_MAX;
}

/* The slot's file: 1 read (into *f), 0 none or set aside, -1 blocked. */
static int read_file(int slot, fruit_file *f) {
    char path[MAX_PATH];
    DWORD got = 0;
    int r;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!fruit_path(slot, path, 0)) {
        return -1;
    }
    r = vv_sidecar_load(&g_gate, path, (unsigned char *)f, sizeof *f, &got, valid_file, &slot);
    if (r == VV_SIDECAR_LOAD_BLOCKED) {
        return -1;
    }
    return r == VV_SIDECAR_LOAD_VALID ? 1 : 0;
}

static void write_file(void) {
    static fruit_file f, old;
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    int i, n = 0;
    if (!g_bound || g_slot == 0 || read_file(g_slot, &old) < 0) {
        return;                      /* no slot, or a file there that cannot be read: never replaced */
    }
    memset(&f, 0, sizeof f);
    f.magic = FILE_MAGIC;
    f.version = FILE_VERSION;
    f.game = FS_GAME;
    f.slot = (unsigned int)g_slot;
    f.fruit = (unsigned int)g_fruit;
    f.units = (unsigned int)g_units;
    for (i = 0; i < ROSTER_MAX; ++i) {
        f.roster[i] = g_roster[i];
        n += g_roster[i] != 0u;
    }
    f.count = (unsigned int)n;
    if (!fruit_path(g_slot, path, 1)) {
        return;
    }
    parts[0] = &f;
    sizes[0] = sizeof f;
    (void)vv_sidecar_publish(&g_gate, path, parts, sizes, 1);
}

/* ---- the village ------------------------------------------------------------------------------------------ */

/* The tree's state belongs to the village on screen: its slot and its living villagers.  A village not seen
   before takes its file when the file's villagers are still in it, and otherwise starts full.  1 when there is a
   village (anyone alive). */
static int bind_village(int force) {
    static unsigned int now[ROSTER_MAX];
    static fruit_file f;
    int slot = vv_current_save_slot(FS_GAME, 0);
    DWORD tick = GetTickCount();
    if (g_bound && !force && slot == g_slot && tick - g_checked < 500u) {
        return 1;
    }
    if (roster_now(now) == 0) {
        return g_bound;              /* no one alive (yet): nothing to tell, nothing changes */
    }
    g_checked = tick;
    if (g_bound && slot == g_slot && same_village(g_roster, now)) {
        memcpy(g_roster, now, sizeof g_roster);
        return 1;
    }
    g_fruit = FS_FULL;
    g_units = 0;
    g_reference = NULL;
    if (slot != 0 && read_file(slot, &f) == 1 && same_village(f.roster, now)) {
        g_fruit = (int)f.fruit;
        g_units = (int)f.units;
    }
    g_slot = slot;
    g_bound = 1;
    memcpy(g_roster, now, sizeof g_roster);
    return 1;
}

/* Take `n` fruit when the tree holds that many: 1 taken, 0 not.  With no one alive there is no village to keep
   a count for (it cannot happen in play): the stock game's answer. */
static int take(int n) {
    if (!bind_village(0)) {
        return 1;
    }
    if (g_fruit < n) {
        return 0;
    }
    g_fruit -= n;
    return 1;
}

/* ---- the game's moments ------------------------------------------------------------------------------------ */

/* Job event 15, the food-bin credit: 1 pays the stock 3 food (3 fruit taken), 0 pays nothing. */
static int __cdecl on_credit(void) {
    int pay = 1;
    __try {
        pay = take(FS_TRIP);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        pay = 1;
    }
    return pay;
}

/* The stomped fruit is in the stew: 3 fruit taken, down to 0. */
static void __cdecl on_stew(void) {
    __try {
        if (bind_village(0)) {
            g_fruit = g_fruit > FS_TRIP ? g_fruit - FS_TRIP : 0;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* Whether the tree can be offered to a villager (the dispatcher, the task gate). */
static int __cdecl on_offer(void) {
    int ok = 1;
    __try {
        ok = !bind_village(0) || g_fruit >= FS_TRIP;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 1;
    }
    return ok;
}

typedef char (__fastcall *do_action_fn)(void *self, void *unused, int action, void *block);

/* A villager dropped on the restored tree: 1 the stock start; 0 the tree is (nearly) empty and the villager got
   the empty bush's refusal instead. */
static int __cdecl on_drop(unsigned char *villager) {
    int ok = 1;
    __try {
        ok = on_offer();
        if (!ok) {
            int block[8];
            memset(block, 0, sizeof block);
            block[0] = REFUSE_TEXT;
            block[1] = -1;
            ((do_action_fn)(UINT_PTR)DO_ACTION)(villager, NULL, REFUSE_ACTION, block);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return ok;
}

typedef void (__fastcall *show_fn)(void *self, void *unused, const char *text);

/* The tree clicked: "Fruit remaining: N" on the game's status line. */
static void __cdecl on_click(void) {
    static char text[128], out[256];
    __try {
        const char *line;
        (void)bind_village(0);
        wsprintfA(text, "Fruit remaining: %d", g_fruit);
        line = vvfp_trf("vvfp.fruit_supply/vvfp_vv4_fruit_supply.on_click.s0", "Fruit remaining: %d", text, out,
                        sizeof out);
        ((show_fn)(UINT_PTR)STATUS_SHOW)((void *)(UINT_PTR)STATUS_LINE, NULL, line);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The catch-up Cooking Pit bonus is about to pay: 1 pays (5 fruit taken), 0 pays nothing. */
static int __cdecl on_bonus(void) {
    int pay = 1;
    __try {
        pay = take(FS_BONUS);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        pay = 1;
    }
    return pay;
}

/* The life tick is processing one age unit of the villager at `rec`: the reference's units are the village's. */
static void __cdecl on_unit(const unsigned char *rec) {
    __try {
        if (!bind_village(0)) {
            return;
        }
        if (g_reference == NULL || g_reference[REC_OCCUPIED] == 0 || identity(g_reference) != g_reference_id) {
            g_reference = rec;
            g_reference_id = identity(rec);
        }
        if (rec != g_reference) {
            return;
        }
        if (++g_units >= FS_REFILL_UNITS) {
            g_units = 0;
            g_fruit = FS_FULL;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* ---- the island event ------------------------------------------------------------------------------------ */

typedef struct {
    int id;
    const char *key;
    const char *text;
    const char *localized;
} sm_string;

typedef struct {
    const void *vtable;
    void *villager;
    int amount;
} event_object;

static unsigned int g_event_vtable[17];    /* [0] the RTTI locator, then the 16 entries */
static event_object g_event;
static sm_string g_event_text;

typedef char (__fastcall *condition_fn)(void *self, void *unused);
typedef char (__fastcall *solved_fn)(void *self, void *unused, int id);

/* The teardown's delete: the object is not the game's heap's. */
static void *__fastcall ev_delete(void *self, void *unused, int flags) {
    (void)unused;
    (void)flags;
    return self;
}

/* The condition: the Cooking Pit restored, then the berry event's own (it keeps the villager at +4). */
static char __fastcall ev_condition(void *self, void *unused) {
    char ok = 0;
    (void)unused;
    __try {
        if (g_installed && ((solved_fn)(UINT_PTR)PUZZLE_SOLVED)((void *)(UINT_PTR)PUZZLES, NULL, PUZZLE_COOKING_PIT)) {
            ok = ((condition_fn)(UINT_PTR)BERRY_CONDITION)(self, NULL);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = 0;
    }
    return ok;
}

/* The text id: its index slot pointed at the owner's text first (an empty slot, or ours). */
static int __fastcall ev_text_id(void *self, void *unused) {
    (void)self;
    (void)unused;
    __try {
        sm_string **index = (sm_string **)(UINT_PTR)STRING_INDEX;
        g_event_text.id = EV_TEXT_ID;
        g_event_text.key = "eEventACloserLookYellowFruitDesc";
        /* The owner's words, one literal (the template's row is matched against it). */
        g_event_text.text = vvfp_tr("vvfp.fruit_supply/vvfp_vv4_fruit_supply.ev_text_id.s0",
"While checking the breadfruit orchard, one of the farmers notices some leftover fruits scattered around the trees. They must have overlooked them last harvest. Turns out there were more growing up there than they had thought!",
                                    2000);
        g_event_text.localized = NULL;
        if (index[EV_TEXT_ID] == NULL || index[EV_TEXT_ID] == &g_event_text) {
            index[EV_TEXT_ID] = &g_event_text;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return EV_TEXT_ID;
}

/* The result (OK): FS_EVENT_GAIN fruit, to at most 1,000. */
static void __fastcall ev_result(void *self, void *unused) {
    (void)self;
    (void)unused;
    __try {
        if (bind_village(0)) {
            g_fruit = g_fruit + FS_EVENT_GAIN < FS_FULL ? g_fruit + FS_EVENT_GAIN : FS_FULL;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* The object, from the berry event's vtable (checked stock first). */
static int ev_build(void) {
    const unsigned int *stock = (const unsigned int *)(UINT_PTR)BERRY_VTABLE;
    static const unsigned int expect[3] = { BERRY_CONDITION, BERRY_TITLE_ID, BERRY_TEXT_ID };
    static const unsigned int result = BERRY_RESULT;
    if (!vvfp_site_holds(BERRY_VTABLE + 4u, (const unsigned char *)expect, sizeof expect)
        || !vvfp_site_holds(BERRY_VTABLE + 0x30u, (const unsigned char *)&result, sizeof result)
        || !vvfp_site_holds(BERRY_VTABLE - 4u, (const unsigned char *)(stock - 1), (int)sizeof g_event_vtable)) {
        return 0;
    }
    memcpy(g_event_vtable, stock - 1, sizeof g_event_vtable);
    g_event_vtable[1 + 0] = (unsigned int)(UINT_PTR)ev_delete;
    g_event_vtable[1 + 1] = (unsigned int)(UINT_PTR)ev_condition;
    g_event_vtable[1 + 3] = (unsigned int)(UINT_PTR)ev_text_id;
    g_event_vtable[1 + 12] = (unsigned int)(UINT_PTR)ev_result;
    memset(&g_event, 0, sizeof g_event);
    g_event.vtable = &g_event_vtable[1];
    return 1;
}

/* ---- the save and the load -------------------------------------------------------------------------------- */

typedef int (__fastcall *save_fn)(void *self, void *unused, void *out, unsigned int size);
typedef int (__fastcall *load_fn)(void *self, void *unused, const void *in);

static int __fastcall on_save(void *self, void *unused, void *out, unsigned int size) {
    (void)unused;
    __try {
        if (bind_village(1)) {
            write_file();
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return ((save_fn)(UINT_PTR)STOCK_SAVE)(self, NULL, out, size);
}

static int __fastcall on_load(void *self, void *unused, const void *in) {
    int r = ((load_fn)(UINT_PTR)STOCK_LOAD)(self, NULL, in);
    (void)unused;
    g_bound = 0;                     /* a village was loaded: its file is read at the next use */
    g_reference = NULL;
    return r;
}

/* ---- the stubs -------------------------------------------------------------------------------------------- */

static unsigned int g_food_add = FOOD_ADD;
static unsigned int g_life_advance = LIFE_ADVANCE;

/* At CREDIT_SITE: the stock push 3 / food writer when on_credit says so, else the event's end. */
__declspec(naked) static void credit_stub(void) {
    __asm {
        pushad
        call on_credit
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz none
        push 3
        mov ecx, FOOD_STORE
        call dword ptr [g_food_add]
        push CREDIT_ON
        ret
    none:
        push CREDIT_END
        ret
    }
}

/* At OFFER_SITE: the fruit joins the options only while the tree holds a trip's fruit. */
__declspec(naked) static void offer_stub(void) {
    __asm {
        pushad
        call on_offer
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz skip
        mov dword ptr [esp + edi * 4 + 0x1C], 2
        add edi, 1
    skip:
        push OFFER_ON
        ret
    }
}

/* At TASK_SITE: the fruit task starts the trip only while the tree holds a trip's fruit; else the empty bush's
   way out (the task cleared). */
__declspec(naked) static void task_stub(void) {
    __asm {
        pushad
        call on_offer
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz empty
        lea eax, [esp + 0x0C]
        push eax
        push 0x64
        push TASK_ON
        ret
    empty:
        push TASK_EMPTY
        ret
    }
}

/* At DROP_SITE (ecx = the villager): the stock start, or the refusal on_drop gave. */
__declspec(naked) static void drop_stub(void) {
    __asm {
        pushad
        push ecx
        call on_drop
        add esp, 4
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz refused
        lea edx, [esp + 8]
        push edx
        push 0x64
        push DROP_ON
        ret
    refused:
        push DROP_DONE
        ret
    }
}

/* At CLICK_SITE (eax = the message): 1 the villager-held hover (stock), 2 the readout, any other nothing. */
__declspec(naked) static void click_stub(void) {
    __asm {
        sub eax, 1
        jz held
        cmp eax, 1
        jne done
        pushad
        call on_click
        popad
    done:
        push CLICK_DONE
        ret
    held:
        push CLICK_HELD
        ret
    }
}

/* At BONUS_SITE: the stock push 5 / food writer when on_bonus says so, else past the bonus. */
__declspec(naked) static void bonus_stub(void) {
    __asm {
        pushad
        call on_bonus
        mov dword ptr [esp + 28], eax
        popad
        test eax, eax
        jz none
        push 5
        mov ecx, FOOD_STORE
        call dword ptr [g_food_add]
        push BONUS_ON
        ret
    none:
        push BONUS_NONE
        ret
    }
}

/* At UNIT_SITE (esi = record + 0x1C3C): count the unit, then the stock lea / call. */
__declspec(naked) static void unit_stub(void) {
    __asm {
        pushad
        lea eax, [esi - REC_PROC_AGE]
        push eax
        call on_unit
        add esp, 4
        popad
        lea ecx, [esi + 0x20]
        call dword ptr [g_life_advance]
        push UNIT_ON
        ret
    }
}

/* At STEW_SITE (esi = the stew's listener): the fruit taken, then the stock flag. */
__declspec(naked) static void stew_stub(void) {
    __asm {
        pushad
        call on_stew
        popad
        mov byte ptr [esi + 0xB1F], 1
        push STEW_ON
        ret
    }
}

/* ---- installing ------------------------------------------------------------------------------------------- */

static unsigned int g_expect[3];
static unsigned int g_ours[3];

static int holds(unsigned int va, const unsigned char *bytes, int length) {
    return vvfp_site_holds(va, bytes, length);
}

/* 1 when every site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpYellowFruitInstalled(void) {
    return g_installed;
}

/* "Refill the food sources" of a Custom Island Event (VVFP Story Upgrades.dll, story_c4.inc c4_refill, which finds
   this by GetProcAddress and does nothing when this companion is not loaded): the tree is filled to its full 1,000
   for the village on screen.  Its 40-unit refill clock runs on unchanged.  Nothing is written here: the file is
   written when the game next saves, with the save (a refill the save never keeps is never kept).  1 when the tree
   was filled, 0 when the sites are not installed or no villager is alive (no village to keep a count for). */
int __stdcall VvfpYellowFruitRefill(void) {
    int filled = 0;
    if (!g_installed) {
        return 0;
    }
    __try {
        if (bind_village(0)) {
            g_fruit = FS_FULL;
            filled = 1;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        filled = 0;
    }
    return filled;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write w[SITES];
    (void)shipped;
    if (g_installed || game != FS_GAME
        || !holds(TASK_EMPTY, TASK_EMPTY_STOCK, sizeof TASK_EMPTY_STOCK)
        || !holds(DROP_DONE, DROP_DONE_STOCK, sizeof DROP_DONE_STOCK)
        || !ev_build()) {
        return;
    }
    vvfp_site_branch(&w[0], CREDIT_SITE, sizeof CREDIT_STOCK, CREDIT_STOCK, 0xE9, (const void *)credit_stub);
    vvfp_site_branch(&w[1], OFFER_SITE, sizeof OFFER_STOCK, OFFER_STOCK, 0xE9, (const void *)offer_stub);
    vvfp_site_branch(&w[2], TASK_SITE, sizeof TASK_STOCK, TASK_STOCK, 0xE9, (const void *)task_stub);
    vvfp_site_branch(&w[3], DROP_SITE, sizeof DROP_STOCK, DROP_STOCK, 0xE9, (const void *)drop_stub);
    vvfp_site_branch(&w[4], CLICK_SITE, sizeof CLICK_STOCK, CLICK_STOCK, 0xE9, (const void *)click_stub);
    vvfp_site_branch(&w[5], BONUS_SITE, sizeof BONUS_STOCK, BONUS_STOCK, 0xE9, (const void *)bonus_stub);
    vvfp_site_branch(&w[6], UNIT_SITE, sizeof UNIT_STOCK, UNIT_STOCK, 0xE9, (const void *)unit_stub);
    vvfp_site_branch(&w[7], STEW_SITE, sizeof STEW_STOCK, STEW_STOCK, 0xE9, (const void *)stew_stub);
    g_expect[0] = STOCK_SAVE;
    g_ours[0] = (unsigned int)(UINT_PTR)on_save;
    vvfp_site_bytes(&w[8], VTABLE + 4u * SLOT_SAVE, 4, (const unsigned char *)&g_expect[0],
                    (const unsigned char *)&g_ours[0]);
    g_expect[1] = STOCK_LOAD;
    g_ours[1] = (unsigned int)(UINT_PTR)on_load;
    vvfp_site_bytes(&w[9], VTABLE + 4u * SLOT_LOAD, 4, (const unsigned char *)&g_expect[1],
                    (const unsigned char *)&g_ours[1]);
    g_expect[2] = 0;                 /* slot 19 holds no event */
    g_ours[2] = (unsigned int)(UINT_PTR)&g_event;
    vvfp_site_bytes(&w[10], EVENT_SLOT_VA, 4, (const unsigned char *)&g_expect[2],
                    (const unsigned char *)&g_ours[2]);
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
