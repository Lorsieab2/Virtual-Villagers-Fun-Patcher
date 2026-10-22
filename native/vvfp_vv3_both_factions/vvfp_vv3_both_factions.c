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

/* THE FILE.  One entry per save written with a second faction, newest
   last; the oldest is dropped past ENTRIES, so the backups the game and the
   patcher keep of the last saves still find theirs. */
#define FILE_MAGIC 0x46325656u    /* 'V' 'V' '2' 'F' */
#define FILE_VERSION 1u
#define ENTRIES 16

#pragma pack(push, 1)
typedef struct {
    unsigned int fp_lo, fp_hi;    /* the save's fingerprint */
    unsigned char secondary;      /* 5 Nature or 6 Magic */
    unsigned char secondary_level;/* 1..3 */
    unsigned char primary;        /* the faction the save holds */
    unsigned char primary_level;  /* 1..3, as the save holds it */
    unsigned int written_lo, written_hi;
} faction_entry;

typedef struct {
    unsigned int magic, version, game, slot, count;
    faction_entry entry[ENTRIES];
} faction_file;
#pragma pack(pop)

static int installed;
static int g_primary;             /* the faction bought first in this village (0 none) */
static int g_secondary;           /* the faction bought second (0 none) */
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
    unsigned int i;
    if (len != sizeof(faction_file) || f->magic != FILE_MAGIC || f->version != FILE_VERSION
        || f->game != VV3_GAME || f->slot != (unsigned int)((faction_ctx *)ctx)->slot
        || f->count > ENTRIES) {
        return 0;
    }
    for (i = 0; i < f->count; ++i) {
        const faction_entry *e = &f->entry[i];
        if ((e->secondary != NATURE && e->secondary != MAGIC) || e->primary + e->secondary != NATURE + MAGIC
            || e->secondary_level < 1 || e->secondary_level > 3 || e->primary_level < 1 || e->primary_level > 3) {
            return 0;
        }
    }
    return 1;
}

/* Read the slot's file: 1 valid, 0 none (missing or set aside), -1 blocked. */
static int read_file(int slot, faction_file *f, char *path) {
    faction_ctx ctx;
    DWORD got = 0;
    int r;
    ctx.slot = slot;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!faction_path(slot, path, 0)) {
        return -1;
    }
    r = vv_sidecar_load(&g_gate, path, (unsigned char *)f, sizeof *f, &got, valid_file, &ctx);
    if (r == VV_SIDECAR_LOAD_BLOCKED) {
        return -1;
    }
    return r == VV_SIDECAR_LOAD_VALID ? 1 : 0;
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
                   int primary, int primary_level) {
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
    record(slot, lo, hi, secondary, secondary_level, primary, saved[primary]);
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
    } else if (level(id) == 0 && level(other) > 0) {
        g_primary = other;
        g_secondary = id;
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
        || !is_stock(PARTICLE_SITE, PARTICLE_STOCK, sizeof PARTICLE_STOCK)) {
        return;
    }
    if (!write_jump(SAVE_SITE, save_stub, sizeof SAVE_STOCK)
        || !write_jump(LOAD_SITE, load_stub, sizeof LOAD_STOCK)
        || !write_jump(NOTE_SITE, note_stub, sizeof NOTE_STOCK)
        || !write_jump(SUN_SITE, sun_stub, sizeof SUN_STOCK)
        || !write_jump(PARTICLE_SITE, particle_stub, sizeof PARTICLE_STOCK)
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
