/* VVFP VV3 Both Factions -- the Faction of Nature AND the Faction of Magic in
   one village of The Secret City (docs/vv3-both-factions.md).

   THE STOCK GAME.  A faction is not a separate value: it is the level of two
   of the seven technologies in the technology manager 0x582618 (levels at
   +4*id, read by 0x426FC0(id)): Nature is technology 5, Magic technology 6.
   The faction "chosen" is whichever of the two is above 0.  Four places make
   the two exclusive, and nothing else does:

     1. The save loader 0x427060 (called at 0x428A0D) REFUSES a save whose
        Nature and Magic are both above 0 (0x427067..0x427079), so the whole
        village load fails (0x428A74).  That is what a cheat that sets both
        does to a save.
     2. The Tech screen's purchase 0x465640 answers "You have already chosen
        your faction!" (string 0x419) when the other one is above 0
        (0x4656E6..0x465749).
     3. The world draw 0x420B30 draws the Nature herb (herb_nature.png, the
        Pitcher Plant) at Nature 2 or more, OTHERWISE the Magic herb
        (herb_magic.png, the Berry Plant) at Magic 2 or more (the `ret` at
        0x420BD5).
     4. The Tech screen draw 0x4649C0 gives the chosen faction ([screen+0xD4])
        the sunbeam (sunbeam.png, image 0x90) and darkens the other column
        (0x464AE4..0x464BE1).

   Every other reader takes one technology on its own and works for both at
   once: Nature 1 fruit refill (0x4347C3), Nature 3 longevity (0x4601C4),
   Magic 1 research point (0x4593DC), Magic 3 population (0x45FE9D), the two
   Ghostly Dream island events (0x4154F0 / 0x415630), the level pips and the
   info box of the Tech screen (0x4649C0 / 0x464C30), and the herbs
   themselves: their drop regions (cmap regions 30 and 31, handlers 0x421340
   and 0x4213D0) and their carried items (0x24 / 0x25) never read a
   technology.

   WHAT THIS COMPANION DOES.  The game's memory holds both levels, so every
   reader sees both.  The SAVE never does: the faction bought first (the
   primary) is saved as the stock game saves it, and the other one (the
   secondary) is written as 0 and kept in a per-save file,
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Factions\
           Virtual Villagers 3 Second Faction - Save <S>.dat
   which is bound to the exact save written with it (an FNV-1a fingerprint of
   the save's first 0x6CE0 bytes: every system saved before the technologies,
   the technologies themselves and the tech points).  So the stock loader's
   refusal (1) can never be reached, and a game without this companion loads
   every save with the primary faction only.

     a. SAVE (0x427D1F): after the stock copy of the levels into the save
        buffer (0x426F60), a secondary is written as 0 there and recorded in
        the file with the fingerprint.
     b. LOAD (0x428A08): after the stock loader accepted the (one-faction)
        save, the file's entry with this save's fingerprint gives the
        secondary its level back through the game's own level-up 0x426FD0,
        exactly as the stock loader restores every level.
     c. THE PURCHASE (0x4656FE, 0x465734): the "already chosen" refusal is
        removed, so the other faction is bought on the Tech screen like any
        technology, at its stock price; 0x4657D5 notes which faction was
        bought second.
     d. THE HERBS (0x420BD5): the `ret` becomes a nop, so the Berry Plant is
        also drawn when the Pitcher Plant is.
     e. THE TECH SCREEN (0x464AE4): with both factions, both get the sunbeam
        and neither column is darkened; (0x465583) both columns get their own
        floating particles (Nature's petals, Magic's sparkles), each from the
        stock emitter's own chance and art.

   Installed by VvfpStartup(game, shipped), which VVFP Startup.dll calls once
   at game start.  Only The Secret City installs, and only when every place
   holds the stock bytes; the purchase (c) is written last, so a companion
   that could not install everything never lets a second faction be bought.
   Nothing jumps into the bytes the detours overwrite (checked in the stock
   executable). */
#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "../shared/sidecar_io.h"

#define VV3_GAME 3

#define TECH 0x582618u            /* the technology manager: levels at +4*id */
#define TECH_POINTS 0x582644u     /* the village's tech points (a dword) */
#define NATURE 5
#define MAGIC 6
#define LEVEL_UP 0x426FD0u        /* thiscall(id): one level up, listeners told */
#define TECH_SAVE 0x426F60u       /* thiscall(out): the seven levels copied out */
#define TECH_LOAD 0x427060u       /* thiscall(in): the stock loader (refuses both) */
#define IMAGES 0x42E9D0u          /* the image manager (no arguments) */
#define DRAW_IMAGE 0x42EB90u      /* thiscall(image, x, y, alpha, 0x64) */
#define SUNBEAM 0x90              /* sunbeam.png */
#define NATURE_X 0x16F            /* the Tech screen's columns (0x4B1F6C + 16*id) */
#define MAGIC_X 0x283

#define SAVE_SITE 0x427D1Fu       /* mov ecx, 0x582618 / call 0x426F60 */
#define SAVE_RETURN 0x427D29u
#define LOAD_SITE 0x428A08u       /* mov ecx, 0x582618 / call 0x427060 */
#define LOAD_RETURN 0x428A12u
#define LOADER_SLOT_ARG 0x12FB4u  /* the loader's slot argument, from esp at LOAD_RETURN */
#define NOTE_SITE 0x4657D5u       /* push esi / mov ecx, 0x582618 / call 0x426FD0 */
#define NOTE_RETURN 0x4657E0u
#define SUN_SITE 0x464AE4u        /* mov eax, [edi+0xD4] / cmp eax, -1 */
#define SUN_CONTINUE 0x464AEDu    /* pop ebp / pop ebx / je 0x464BE1 */
#define SUN_DONE 0x464BE1u
#define HERB_SITE 0x420BD5u       /* ret (Nature herb drawn: Magic's never asked) */
#define BUY_MAGIC_SITE 0x4656FEu  /* jg 0x465736: Magic refused while Nature > 0 */
#define BUY_NATURE_SITE 0x465734u /* jle 0x465700: Nature allowed only while Magic is 0 */
#define PARTICLE_SITE 0x465583u   /* cmp [esi+0xD4], -1 / je 0x465624: the chosen faction's particles */
#define RAND 0x4032D0u            /* cdecl rand(n): 0..n-1 */
#define SPAWN 0x429400u           /* thiscall: one particle (8 arguments) */
#define PARTICLES 0x583B28u       /* the particle pool */
#define COLUMNS 0x4B1F6Cu         /* the Tech screen's columns: x, y at +16*id */

#define SAVE_FIRST 0x6CE0u        /* the fingerprint's span of the save buffer */
#define SAVE_TECH 0x6CC0u         /* the levels in the save buffer */
#define SAVE_POINTS 0x6CDCu       /* the tech points in the save buffer */

static const unsigned char SAVE_STOCK[10] = { 0xB9, 0x18, 0x26, 0x58, 0x00, 0xE8, 0x37, 0xF2, 0xFF, 0xFF };
static const unsigned char LOAD_STOCK[10] = { 0xB9, 0x18, 0x26, 0x58, 0x00, 0xE8, 0x4E, 0xE6, 0xFF, 0xFF };
static const unsigned char NOTE_STOCK[11] = { 0x56, 0xB9, 0x18, 0x26, 0x58, 0x00, 0xE8, 0xF0, 0x17, 0xFC, 0xFF };
static const unsigned char SUN_STOCK[9] = { 0x8B, 0x87, 0xD4, 0x00, 0x00, 0x00, 0x83, 0xF8, 0xFF };
static const unsigned char HERB_STOCK[3] = { 0xC3, 0x6A, 0x06 };     /* ret / push 6 (the Magic test) */
static const unsigned char BUY_MAGIC_STOCK[2] = { 0x7F, 0x36 };
static const unsigned char BUY_NATURE_STOCK[2] = { 0x7E, 0xCA };
static const unsigned char PARTICLE_STOCK[13] = { 0x83, 0xBE, 0xD4, 0x00, 0x00, 0x00, 0xFF,
                                                  0x0F, 0x84, 0x94, 0x00, 0x00, 0x00 };
static const unsigned char RECIPE_STOCK[10] = { 0x57, 0x53, 0x55, 0x8B, 0xF1, 0xE8, 0xC6, 0xFD, 0xFF, 0xFF };
static const unsigned char CONFIRM_STOCK[10] = { 0x83, 0xFE, 0x05, 0x74, 0x05, 0x83, 0xFE, 0x06, 0x75, 0x70 };
static const unsigned char TEXT_STOCK[12] = { 0x68, 0x18, 0x04, 0x00, 0x00, 0x8B, 0xCD,
                                              0xE8, 0x09, 0x9A, 0xFC, 0xFF };

static const unsigned char SHARK_STOCK[13] = { 0x57, 0x6A, 0x0A, 0xB9, 0x90, 0x49, 0x59, 0x00,
                                               0xE8, 0xD2, 0xF3, 0xFF, 0xFF };
#define SHARK_SITE 0x4365B1u      /* the sharks (0x436580): push edi / the puzzle's flag 0xA (0x435990) */
#define PUZZLES 0x594990u         /* the puzzle counters: 0x4358D0(id) solved, 0x435990(id) one more */
#define PUZZLE_SOLVED 0x4358D0u
#define HAS_EFFECT 0x455E10u      /* thiscall(villager; provider, id): a potion effect on the villager */
#define EFFECTS 0x582610u         /* the potion effects' provider */
#define SHARK_PUZZLE 0x0A         /* "The Sharks" (tip 0x2C6) */
#define STINK_BOMB 0x1B           /* Black Orchid x2 + Pitcher Plant: the sharks go */
#define RECIPE_SITE 0x430520u    /* the brew lookup 0x430510: push the herbs / call 0x4302F0 */
#define CONFIRM_SITE 0x46574Eu    /* the purchase: the faction confirmation's test (both 0) */
#define TEXT_SITE 0x46577Bu       /* the purchase: the confirmation's text, string 0x418 */
#define ACHIEVEMENTS 0x4B3710u    /* 0x412CD0(2): "Alchemy R Us", 50 recipes brewed */
#define ACHIEVE 0x412CD0u
#define HERB_PITCHER 0x24         /* carried herbs 0x1F..0x25: Tiger Lily, Cactus, Lotus, */
#define HERB_BERRY 0x25           /* Black Orchid, Rose, Pitcher Plant, Berry Plant */

/* The owner's text for the faction confirmation (the stock box breaks its
   lines by hand, as its own text does). */
static const char CONFIRM_TEXT[] =
    "With the power of the Fun Patcher,\n"
    "you can now embrace both Nature\n"
    "and Magic Factions. Use this\n"
    "gift wisely.\n";

/* The seven recipes that need both factions' herbs (the owner's choice).
   herb: the third herb; effect: the effect id the brew gives (0x4268F0). */
static const struct { unsigned char herb; unsigned char effect; } RECIPES[7] = {
    { 0x1F, 0x07 },   /* Tiger Lily: "Whee! What a fun potion!" */
    { 0x20, 0x23 },   /* Cactus: "In a trance" */
    { 0x21, 0x26 },   /* Lotus: "Blannesamagawa loomajoobamooga!!" */
    { 0x22, 0x16 },   /* Black Orchid: "Paralyzed" */
    { 0x23, 0x19 },   /* Rose: "A little bit lonely" */
    { 0x24, 0x21 },   /* a second Pitcher Plant: "Whoa!" */
    { 0x25, 0x28 },   /* a second Berry Plant: "Something smells YUMMY!" */
};

/* THE FILE.  One entry per save written with a second faction, newest
   last; the oldest is dropped past ENTRIES, so the backups the game and the
   patcher keep of the last saves still find theirs. */
#define FILE_MAGIC 0x46325656u    /* 'V' 'V' '2' 'F' */
#define FILE_VERSION 2u           /* 2: + the recipes found; 1 (the first preview) is still read */
#define ENTRIES 16

#pragma pack(push, 1)
typedef struct {
    unsigned int fp_lo, fp_hi;    /* the save's fingerprint */
    unsigned char secondary;      /* 5 Nature or 6 Magic */
    unsigned char secondary_level;/* 1..3 */
    unsigned char primary;        /* the faction the save holds */
    unsigned char primary_level;  /* 1..3, as the save holds it */
    unsigned int written_lo, written_hi;
    unsigned char recipes;        /* bit k: the both-herb recipe k has been brewed (version 2) */
    unsigned char reserved[3];
} faction_entry;

typedef struct {
    unsigned int magic, version, game, slot, count;
    faction_entry entry[ENTRIES];
} faction_file;
#pragma pack(pop)

#define V1_ENTRY 20u              /* a version-1 entry: everything before `recipes` */
#define V1_FILE (20u + ENTRIES * V1_ENTRY)

static int installed;
static int g_primary;             /* the faction bought first in this village (0 none) */
static int g_secondary;           /* the faction bought second (0 none) */
static unsigned int g_recipes;    /* the both-herb recipes brewed in this village (bits 0..6) */
static vv_sidecar_gate g_gate;

static int level(int id) {
    return *(volatile int *)(uintptr_t)(TECH + 4u * (unsigned int)id);
}

static int both_factions(void) {
    return level(NATURE) > 0 && level(MAGIC) > 0;
}

/* ---- the file ------------------------------------------------------------ */

/* "<Documents>\LDW\<executable's name>\Virtual Villagers Fun Patcher\Save <S>\Data\Factions\
   Virtual Villagers 3 Second Faction - Save <S>.dat"; `make` creates the folders. */
static int faction_path(int slot, char *out, int make) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base = exe, *p, *dot = NULL;
    static const char *const LEVELS[4] = {
        "\\Virtual Villagers Fun Patcher", "\\Save %d", "\\Data", "\\Factions"
    };
    char part[32];
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
    if (base[0] == '\0' || lstrlenA(docs) + lstrlenA(base) + 160 >= MAX_PATH) {
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
    wsprintfA(part, "\\Virtual Villagers 3 Second Faction - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

typedef struct {
    int slot;
} faction_ctx;

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const faction_file *f = (const faction_file *)data;
    unsigned int i, stride;
    if (len < 20u || f->magic != FILE_MAGIC || f->game != VV3_GAME
        || f->slot != (unsigned int)((faction_ctx *)ctx)->slot || f->count > ENTRIES) {
        return 0;
    }
    if (f->version == FILE_VERSION && len == sizeof(faction_file)) {
        stride = sizeof(faction_entry);
    } else if (f->version == 1u && len == V1_FILE) {
        stride = V1_ENTRY;
    } else {
        return 0;
    }
    for (i = 0; i < f->count; ++i) {
        const faction_entry *e = (const faction_entry *)(data + 20u + i * stride);
        if ((e->secondary != NATURE && e->secondary != MAGIC) || e->primary + e->secondary != NATURE + MAGIC
            || e->secondary_level < 1 || e->secondary_level > 3 || e->primary_level < 1 || e->primary_level > 3) {
            return 0;
        }
        if (stride == sizeof(faction_entry) && (e->recipes & 0x80u) != 0) {
            return 0;
        }
    }
    return 1;
}

/* Read the slot's file: 1 valid, 0 none (missing or set aside), -1 blocked.
   A version-1 file comes back as version 2 with no recipes found. */
static int read_file(int slot, faction_file *f, char *path) {
    faction_ctx ctx;
    DWORD got = 0;
    int r;
    ctx.slot = slot;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!faction_path(slot, path, 0)) {
        return -1;
    }
    memset(f, 0, sizeof *f);
    r = vv_sidecar_load(&g_gate, path, (unsigned char *)f, sizeof *f, &got, valid_file, &ctx);
    if (r == VV_SIDECAR_LOAD_BLOCKED) {
        return -1;
    }
    if (r != VV_SIDECAR_LOAD_VALID) {
        return 0;
    }
    if (f->version == 1u) {
        int i;
        for (i = (int)f->count - 1; i >= 0; --i) {
            faction_entry e;
            memcpy(&e, (unsigned char *)f + 20u + (unsigned int)i * V1_ENTRY, V1_ENTRY);
            e.recipes = 0;
            e.reserved[0] = e.reserved[1] = e.reserved[2] = 0;
            f->entry[i] = e;
        }
        f->version = FILE_VERSION;
    }
    return 1;
}

/* ---- the fingerprint ----------------------------------------------------- */

static void fnv(unsigned int *lo, unsigned int *hi, const unsigned char *data, unsigned int n) {
    unsigned __int64 h = ((unsigned __int64)*hi << 32) | *lo;
    unsigned int i;
    for (i = 0; i < n; ++i) {
        h ^= data[i];
        h *= 0x100000001B3ull;
    }
    *lo = (unsigned int)h;
    *hi = (unsigned int)(h >> 32);
}

/* The save buffer's first SAVE_POINTS bytes, then the tech points `points`
   (at a save the live value the game is about to write there; at a load the
   value the file holds there). */
static void fingerprint(const unsigned char *buffer, int points, unsigned int *lo, unsigned int *hi) {
    *lo = 0x84222325u;              /* the FNV-1a 64 offset basis */
    *hi = 0xCBF29CE4u;
    fnv(lo, hi, buffer, SAVE_POINTS);
    fnv(lo, hi, (const unsigned char *)&points, 4);
}

/* ---- the save ------------------------------------------------------------ */

/* Which of the two is the second faction, when both are above 0. */
static int pick_secondary(void) {
    if ((g_secondary == NATURE || g_secondary == MAGIC) && g_primary == NATURE + MAGIC - g_secondary) {
        return g_secondary;
    }
    if (g_primary == NATURE || g_primary == MAGIC) {
        return NATURE + MAGIC - g_primary;
    }
    return MAGIC;                   /* never seen bought: Nature is kept as the save's faction */
}

static void record(int slot, unsigned int fp_lo, unsigned int fp_hi, int secondary, int secondary_level,
                   int primary, int primary_level, unsigned int recipes) {
    static faction_file f;
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    FILETIME now;
    unsigned int i, keep = 0;
    int r = read_file(slot, &f, path);
    if (r < 0) {
        return;                     /* present but unreadable: never replaced */
    }
    if (r == 0) {
        memset(&f, 0, sizeof f);
    }
    /* This save's entry replaces an older one with the same fingerprint. */
    for (i = 0; i < f.count; ++i) {
        if (!(f.entry[i].fp_lo == fp_lo && f.entry[i].fp_hi == fp_hi)) {
            f.entry[keep++] = f.entry[i];
        }
    }
    f.count = keep;
    if (f.count == ENTRIES) {
        memmove(&f.entry[0], &f.entry[1], sizeof(faction_entry) * (ENTRIES - 1));
        f.count = ENTRIES - 1;
    }
    GetSystemTimeAsFileTime(&now);
    f.entry[f.count].fp_lo = fp_lo;
    f.entry[f.count].fp_hi = fp_hi;
    f.entry[f.count].secondary = (unsigned char)secondary;
    f.entry[f.count].secondary_level = (unsigned char)secondary_level;
    f.entry[f.count].primary = (unsigned char)primary;
    f.entry[f.count].primary_level = (unsigned char)primary_level;
    f.entry[f.count].written_lo = now.dwLowDateTime;
    f.entry[f.count].written_hi = now.dwHighDateTime;
    f.entry[f.count].recipes = (unsigned char)(recipes & 0x7Fu);
    f.entry[f.count].reserved[0] = f.entry[f.count].reserved[1] = f.entry[f.count].reserved[2] = 0;
    f.count += 1;
    f.magic = FILE_MAGIC;
    f.version = FILE_VERSION;
    f.game = VV3_GAME;
    f.slot = (unsigned int)slot;
    if (!faction_path(slot, path, 1)) {
        return;
    }
    parts[0] = &f;
    sizes[0] = sizeof f;
    (void)vv_sidecar_publish(&g_gate, path, parts, sizes, 1);
}

/* After the stock copy of the levels into the save buffer (game + 8): a
   second faction is written as 0 -- the save is always one a stock game
   loads -- and kept in the file with this save's fingerprint. */
static void __cdecl on_save(unsigned char *game, int slot) {
    unsigned char *buffer = game + 8;
    int *saved = (int *)(buffer + SAVE_TECH);
    int secondary, primary, secondary_level;
    unsigned int lo, hi;
    if (!(saved[NATURE] > 0 && saved[MAGIC] > 0)) {
        return;
    }
    secondary = pick_secondary();
    primary = NATURE + MAGIC - secondary;
    secondary_level = saved[secondary];
    saved[secondary] = 0;
    /* Slots 21..25 are the backup generation the game writes right after
       the slot itself (0x427D90): the same buffer, so the same fingerprint,
       already kept by the slot's own save. */
    if (slot < 1 || slot > 5 || secondary_level < 1 || secondary_level > 3
        || saved[primary] < 1 || saved[primary] > 3) {
        return;
    }
    fingerprint(buffer, *(volatile int *)(uintptr_t)TECH_POINTS, &lo, &hi);
    record(slot, lo, hi, secondary, secondary_level, primary, saved[primary], g_recipes);
}

/* ---- the load ------------------------------------------------------------ */

typedef void (__fastcall *level_up_fn)(void *tech, void *unused, int id);

/* After the stock loader accepted the save: this village's factions as the
   save holds them, and the second one back from the file when an entry was
   written with exactly this save. */
static void __cdecl on_load(unsigned char *game, int slot) {
    static faction_file f;
    char path[MAX_PATH];
    const unsigned char *buffer = game + 8;
    unsigned int lo, hi, i;
    int primary, secondary;
    g_secondary = 0;
    g_recipes = 0;
    g_primary = level(NATURE) > 0 ? NATURE : (level(MAGIC) > 0 ? MAGIC : 0);
    primary = g_primary;
    if (slot > 20 && slot <= 25) {
        slot -= 20;
    }
    if (primary == 0 || slot < 1 || slot > 5 || read_file(slot, &f, path) != 1) {
        return;
    }
    secondary = NATURE + MAGIC - primary;
    if (level(secondary) != 0) {
        return;
    }
    fingerprint(buffer, *(const int *)(buffer + SAVE_POINTS), &lo, &hi);
    for (i = f.count; i-- > 0;) {
        const faction_entry *e = &f.entry[i];
        int k;
        if (e->fp_lo != lo || e->fp_hi != hi || e->primary != primary || e->secondary != secondary
            || e->primary_level != level(primary)) {
            continue;
        }
        for (k = 0; k < e->secondary_level && level(secondary) < 3; ++k) {
            ((level_up_fn)(uintptr_t)LEVEL_UP)((void *)(uintptr_t)TECH, 0, secondary);
        }
        g_secondary = secondary;
        g_recipes = e->recipes & 0x7Fu;
        return;
    }
}

/* ---- the purchase -------------------------------------------------------- */

/* A technology about to go up one level on the Tech screen. */
static void __cdecl on_purchase(int id) {
    int other;
    if (id != NATURE && id != MAGIC) {
        return;
    }
    other = NATURE + MAGIC - id;
    if (level(id) == 0 && level(other) == 0) {
        g_primary = id;
        g_secondary = 0;
        g_recipes = 0;          /* a village's first faction: nothing brewed with both yet */
    } else if (level(id) == 0 && level(other) > 0) {
        g_primary = other;
        g_secondary = id;
    }
}

/* ---- the both-herb recipes ---------------------------------------------- */

typedef void (__fastcall *achieve_fn)(void *achievements, void *unused, int id);

/* A brew of herbs h1, h2, h3 in the pot: the effect of one of the seven
   both-herb recipes, or 0 for the stock lookup.  Only with both factions:
   otherwise every brew is the stock game's (a Pitcher Plant combination
   nobody knows gets the stock "failed" effect 0x18, a Berry Plant one
   nothing).  The recipes are never put in the pot's table, whose found
   flags the save keeps (0x430120): the save stays exactly as the stock game
   writes it, and the recipes found are kept in the file instead.  Like a
   table recipe, a brew counts toward the 50 recipes of "Alchemy R Us". */
static int __cdecl both_herb_recipe(const unsigned char *pot, int h1, int h2, int h3) {
    int herbs[3];
    int pitchers = 0, berries = 0, other = -1, k;
    unsigned int found, i, n;
    herbs[0] = h1;
    herbs[1] = h2;
    herbs[2] = h3;
    if (!both_factions()) {
        return 0;
    }
    for (k = 0; k < 3; ++k) {
        if (herbs[k] == HERB_PITCHER) {
            ++pitchers;
        } else if (herbs[k] == HERB_BERRY) {
            ++berries;
        } else {
            other = herbs[k];
        }
    }
    if (pitchers == 0 || berries == 0) {
        return 0;
    }
    if (pitchers == 2) {
        other = HERB_PITCHER;
    } else if (berries == 2) {
        other = HERB_BERRY;
    }
    for (k = 0; k < 7; ++k) {
        if (RECIPES[k].herb == other) {
            break;
        }
    }
    if (k == 7) {
        return 0;
    }
    g_recipes |= 1u << k;
    /* "Alchemy R Us" (0x430562..0x430589): the table's recipes found and these. */
    n = *(const unsigned int *)(pot + 0x978);
    found = 0;
    for (i = 0; i < n && i < 100u; ++i) {
        found += pot[0x2C + 0x18 * i] != 0;
    }
    for (i = 0; i < 7u; ++i) {
        found += (g_recipes >> i) & 1u;
    }
    if (found >= 50u) {
        ((achieve_fn)(uintptr_t)ACHIEVE)((void *)(uintptr_t)ACHIEVEMENTS, 0, 2);
    }
    return RECIPES[k].effect;
}

/* ---- the sharks ---------------------------------------------------------- */

typedef unsigned char (__fastcall *puzzle_fn)(void *puzzles, void *unused, int id);
typedef unsigned char (__fastcall *has_effect_fn)(void *villager, void *unused, unsigned int provider, int id);

/* THE SHARKS (0x436580, a villager with a shark potion at the Diving Rock,
   map region 0x2A).  Stock: the puzzle's flag 0xA goes up (solved at 1: tip
   0x2C6 once; 0x435990 does nothing once solved); then a villager under the
   Nature stink bomb (effect 0x1B, Black Orchid x2 + Pitcher Plant) makes the
   sharks go -- the shark object's byte (0x594BC0; saved by 0x4364E0) set
   and the sharks switched off (0x425C70), particles type 5 -- and anyone else
   (the Magic Shark Charmer Vial, effect 0x1A, Rose x2 + Berry Plant) charms
   them: particles type 6, and the shark update (0x425E20) keeps sparkling
   over the sharks while the puzzle is solved and they are there.  Both solve
   the puzzle (fishing).  The save tells the look: the byte 1 gone, 0 here.

   With both factions the latest shark potion decides the look, every time:
   the stink bomb after a charm makes them go (the stock code already does);
   the vial after the stink bomb brings them back, charmed -- the byte back
   to 0 and the stock game's three sharks put back where the world's start
   puts them (0x420EC0: 0x425DE0 at (0x47E, 0x32), (0x4E2, 0x32), (0x546,
   0x32)).  Nothing else: the puzzle, the tip and every reward are the
   stock game's, once.  One faction: stock. */
typedef unsigned char (__fastcall *add_shark_fn)(void *sharks, void *unused, int x, int y);
#define SHARK_LIST 0x5823D0u      /* six sharks of 0x18 bytes, +0 in the water */
#define ADD_SHARK 0x425DE0u

static void __cdecl shark_look(unsigned char *sharks, void *villager) {
    static const int AT[3] = { 0x47E, 0x4E2, 0x546 };
    int i, any = 0;
    if (!both_factions() || sharks[4] == 0
        || ((has_effect_fn)(uintptr_t)HAS_EFFECT)(villager, 0, EFFECTS, STINK_BOMB) != 0
        || ((puzzle_fn)(uintptr_t)PUZZLE_SOLVED)((void *)(uintptr_t)PUZZLES, 0, SHARK_PUZZLE) == 0) {
        return;
    }
    sharks[4] = 0;
    for (i = 0; i < 6; ++i) {
        any |= *(const unsigned char *)(uintptr_t)(SHARK_LIST + 0x18u * (unsigned int)i);
    }
    if (!any) {
        for (i = 0; i < 3; ++i) {
            ((add_shark_fn)(uintptr_t)ADD_SHARK)((void *)(uintptr_t)SHARK_LIST, 0, AT[i], 0x32);
        }
    }
}

/* At SHARK_SITE: esi = the shark object (+4 the "gone" byte), ebx = the
   villager.  The stock code then runs on (the puzzle's flag, the ending). */
static __declspec(naked) void shark_stub(void) {
    __asm {
        push edi
        pushad
        push ebx
        push esi
        call shark_look
        add esp, 8
        popad
        push 0x0A
        mov ecx, 0x594990
        mov eax, 0x435990
        call eax
        push 0x4365BE
        ret
    }
}
/* ---- the Tech screen ----------------------------------------------------- */

typedef void *(__cdecl *images_fn)(void);
typedef void (__fastcall *draw_fn)(void *images, void *unused, int image, int x, int y, float alpha, int mode);

static void __cdecl draw_both(void) {
    void *images = ((images_fn)(uintptr_t)IMAGES)();
    ((draw_fn)(uintptr_t)DRAW_IMAGE)(images, 0, SUNBEAM, NATURE_X - 0x28, 0, 1.0f, 0x64);
    ((draw_fn)(uintptr_t)DRAW_IMAGE)(images, 0, SUNBEAM, MAGIC_X - 0x28, 0, 1.0f, 0x64);
}

static int __cdecl both_factions_c(void) {
    return both_factions();
}

/* THE PARTICLES.  The Tech screen's frame (0x465530) gives the chosen
   faction ([screen+0xD4]) one particle in ten frames, at a random point of
   its column (x + rand(0x72), y + rand(0x162)), from the shared particle
   pool 0x583B28 (0x429400, 0x200 slots): Nature's petals (type 0xA, flag 1),
   Magic's sparkles (type 2).  With both factions each column gets its own,
   exactly as the stock frame gives the one: the same chance, the same
   random calls in the same order, the same particle. */
typedef int (__cdecl *rand_fn)(int n);
typedef void (__fastcall *spawn_fn)(void *pool, void *unused, int type, int x, int y, int a, int b,
                                    int petal, int c, int d);

static void emit(int id) {
    rand_fn rnd = (rand_fn)(uintptr_t)RAND;
    int column_x = *(const int *)(uintptr_t)(COLUMNS + 16u * (unsigned int)id);
    int column_y = *(const int *)(uintptr_t)(COLUMNS + 4u + 16u * (unsigned int)id);
    int x, y;
    if (rnd(100) >= 10) {
        return;
    }
    x = rnd(0x72) + column_x;
    y = rnd(0x162) + column_y;
    ((spawn_fn)(uintptr_t)SPAWN)((void *)(uintptr_t)PARTICLES, 0, id == NATURE ? 0xA : 2, x, y, 1, 0,
                                 id == NATURE ? 1 : 0, 0xA, 0);
}

static void __cdecl emit_both(void) {
    emit(NATURE);
    emit(MAGIC);
}

/* ---- the stubs ----------------------------------------------------------- */

/* At SAVE_SITE: esi = the game, edi = the slot, the buffer's levels pushed. */
static __declspec(naked) void save_stub(void) {
    __asm {
        mov ecx, 0x582618
        mov eax, 0x426F60
        call eax
        pushad
        push edi
        push esi
        call on_save
        add esp, 8
        popad
        push 0x427D29
        ret
    }
}

/* At LOAD_SITE: ebx = the game, the buffer's levels pushed; the loader's
   slot argument is at [esp + 0x12FB4] once the stock call has returned. */
static __declspec(naked) void load_stub(void) {
    __asm {
        mov ecx, 0x582618
        mov eax, 0x427060
        call eax
        test al, al
        je refused
        pushad
        push dword ptr [esp + 0x20 + 0x12FB4]
        push ebx
        call on_load
        add esp, 8
        popad
        mov al, 1
    refused:
        push 0x428A12
        ret
    }
}

/* At NOTE_SITE: esi = the technology bought. */
static __declspec(naked) void note_stub(void) {
    __asm {
        pushad
        push esi
        call on_purchase
        add esp, 4
        popad
        push esi
        mov ecx, 0x582618
        mov eax, 0x426FD0
        call eax
        push 0x4657E0
        ret
    }
}

/* At SUN_SITE: edi = the Tech screen; ebp and ebx are still to be popped. */
static __declspec(naked) void sun_stub(void) {
    __asm {
        pushad
        call both_factions_c
        test eax, eax
        popad
        jne both
        mov eax, dword ptr [edi + 0xD4]
        cmp eax, -1
        push 0x464AED
        ret
    both:
        pushad
        call draw_both
        popad
        pop ebp
        pop ebx
        push 0x464BE1
        ret
    }
}

/* At PARTICLE_SITE: esi = the Tech screen; on to 0x465624 (the pool's
   update) or the stock emitter 0x465590. */
static __declspec(naked) void particle_stub(void) {
    __asm {
        pushad
        call both_factions_c
        test eax, eax
        popad
        jne both
        cmp dword ptr [esi + 0xD4], -1
        je none
        push 0x465590
        ret
    none:
        push 0x465624
        ret
    both:
        pushad
        call emit_both
        popad
        push 0x465624
        ret
    }
}

/* At RECIPE_SITE (inside 0x430510, after its pushes of ebx/ebp/esi/edi):
   ecx = the pot, ebp/ebx/edi = the three herbs.  A both-herb recipe returns
   its effect through the function's own epilogue; anything else runs the
   stock lookup (0x4302F0) and goes on at 0x43052A. */
static __declspec(naked) void recipe_stub(void) {
    __asm {
        mov esi, ecx
        pushad
        push edi
        push ebx
        push ebp
        push esi
        call both_herb_recipe
        add esp, 16
        mov dword ptr [esp + 0x1C], eax
        popad
        test eax, eax
        je stock
        pop edi
        pop esi
        pop ebp
        pop ebx
        ret 0xC
    stock:
        push edi
        push ebx
        push ebp
        mov ecx, esi
        mov eax, 0x4302F0
        call eax
        push 0x43052A
        ret
    }
}

/* At CONFIRM_SITE: esi = the technology clicked.  Level 1 of either
   faction is confirmed (the stock game confirms only while both are 0);
   everything else goes on to the purchase, 0x4657C8, as in the stock game. */
static __declspec(naked) void confirm_stub(void) {
    __asm {
        cmp esi, 5
        je faction
        cmp esi, 6
        jne other
    faction:
        cmp dword ptr [esi * 4 + 0x582618], 0
        jne other
        xor eax, eax
        push 0x465778
        ret
    other:
        push 0x4657C8
        ret
    }
}

/* At TEXT_SITE: the owner's text replaces string 0x418 (the lookup
   0x42F190 is not called).  The `push 1` / `push eax` before the site are
   NOT the lookup's (it takes one argument, ret 4): they are the last two
   arguments of the text box 0x41C7A0(text, 0, 1), ret 0xC, called at
   0x46578C, so they stay on the stack.  (The first preview of this prompt
   dropped them, and the box's own ret 0xC then returned through a wrong
   address: the owner's crash at EIP 7 buying the second faction.) */
static __declspec(naked) void text_stub(void) {
    __asm {
        mov eax, offset CONFIRM_TEXT
        push 0x465787
        ret
    }
}

/* ---- installing ---------------------------------------------------------- */

static int write_code(unsigned int va, const unsigned char *bytes, int length) {
    DWORD old;
    void *at = (void *)(uintptr_t)va;
    if (!VirtualProtect(at, (SIZE_T)length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)length);
    VirtualProtect(at, (SIZE_T)length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)length);
    return 1;
}

static int is_stock(unsigned int va, const unsigned char *stock, size_t length) {
    return memcmp((const void *)(uintptr_t)va, stock, length) == 0;
}

static int write_jump(unsigned int site, void (*stub)(void), int length) {
    unsigned char bytes[16];
    unsigned int rel = (unsigned int)((uintptr_t)stub - (site + 5u));
    int i;
    bytes[0] = 0xE9;
    memcpy(bytes + 1, &rel, 4);
    for (i = 5; i < length; i++) {
        bytes[i] = 0x90;
    }
    return write_code(site, bytes, length);
}

/* Every place stock, or nothing.  The save and load go first, the purchase
   last: until the purchase is written no village can hold both. */
static void install(void) {
    static const unsigned char nop = 0x90;
    static const unsigned char buy_magic[2] = { 0x90, 0x90 };
    static const unsigned char buy_nature = 0xEB;
    if (installed
        || !is_stock(SAVE_SITE, SAVE_STOCK, sizeof SAVE_STOCK)
        || !is_stock(LOAD_SITE, LOAD_STOCK, sizeof LOAD_STOCK)
        || !is_stock(NOTE_SITE, NOTE_STOCK, sizeof NOTE_STOCK)
        || !is_stock(SUN_SITE, SUN_STOCK, sizeof SUN_STOCK)
        || !is_stock(HERB_SITE, HERB_STOCK, sizeof HERB_STOCK)
        || !is_stock(BUY_MAGIC_SITE, BUY_MAGIC_STOCK, sizeof BUY_MAGIC_STOCK)
        || !is_stock(BUY_NATURE_SITE, BUY_NATURE_STOCK, sizeof BUY_NATURE_STOCK)
        || !is_stock(PARTICLE_SITE, PARTICLE_STOCK, sizeof PARTICLE_STOCK)
        || !is_stock(RECIPE_SITE, RECIPE_STOCK, sizeof RECIPE_STOCK)
        || !is_stock(CONFIRM_SITE, CONFIRM_STOCK, sizeof CONFIRM_STOCK)
        || !is_stock(TEXT_SITE, TEXT_STOCK, sizeof TEXT_STOCK)
        || !is_stock(SHARK_SITE, SHARK_STOCK, sizeof SHARK_STOCK)) {
        return;
    }
    if (!write_jump(SAVE_SITE, save_stub, sizeof SAVE_STOCK)
        || !write_jump(LOAD_SITE, load_stub, sizeof LOAD_STOCK)
        || !write_jump(NOTE_SITE, note_stub, sizeof NOTE_STOCK)
        || !write_jump(SUN_SITE, sun_stub, sizeof SUN_STOCK)
        || !write_jump(PARTICLE_SITE, particle_stub, sizeof PARTICLE_STOCK)
        || !write_jump(RECIPE_SITE, recipe_stub, sizeof RECIPE_STOCK)
        || !write_jump(SHARK_SITE, shark_stub, sizeof SHARK_STOCK)
        || !write_jump(TEXT_SITE, text_stub, sizeof TEXT_STOCK)
        || !write_jump(CONFIRM_SITE, confirm_stub, sizeof CONFIRM_STOCK)
        || !write_code(HERB_SITE, &nop, 1)) {
        return;
    }
    if (write_code(BUY_MAGIC_SITE, buy_magic, 2) && write_code(BUY_NATURE_SITE, &buy_nature, 1)) {
        installed = 1;
    }
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (game != VV3_GAME) {
        return;
    }
    install();
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
