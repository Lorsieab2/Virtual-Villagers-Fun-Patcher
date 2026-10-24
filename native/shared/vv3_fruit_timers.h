/* The Secret City's fruit trees on a schedule of the patcher's own, kept beside the save
   (docs/vv3-fruit-tree-timing.md).  Shared by two companions, one feature each, which the
   patcher never ships together:

     "VVFP VV3 Trees Refill Together.dll"  (VV3_FRUIT_MODE 1, All Fruit Trees Refill at the
                                            Same Time): every tree refills at the same moment;
     "VVFP VV3 Trees Take Turns.dll"       (VV3_FRUIT_MODE 2, Fruit Trees Take Turns
                                            Refilling): the trees' refills are spread evenly
                                            over the refill interval, one tree at a time.

   THE STOCK GAME.  The fruit trees are one object (0x5947E0) with up to three trees (live count
   +0x64), one 0x18-byte record each from +0x1C: x, y, planted time, refill timer, kind, fruit.
   Its update 0x434760 (vtable 0x49D1D0 slot 8, run by the world objects' update 0x435880) loops
   over the trees (0x43478A..0x43481A): a tree whose timer is at least the interval old (10,800
   game seconds; 8,100 at Nature 1 with the patcher's Nature patch, whose test is at 0x4347AA)
   gains floor(elapsed * factor / 3600) fruit (factor 37, at Nature 1 or more the immediate at
   0x4347CE: 42, or 56 with the Nature patch) and its timer is set to now; every tree's fruit is
   then held to 1,000.  The clock is 0x426590 on 0x5825D4.  Planting (0x4349FD) sets the
   planted time and the timer to now and the fruit to 1,000; the update's tail (0x43487F)
   removes a dead tree by closing the list up.  The trees are saved by 0x433EC0 (header, the
   records, the count: 0x60 bytes) and loaded by 0x433E40.

   WHAT THE COMPANION DOES.  The game's own timers (+0x28) stay exactly what the stock game
   would hold, so every save is one the unpatched game continues as if the patch had never been
   there: each pass moves a tree's own timer to now whenever the stock test would have.  The
   fruit follows the patcher's schedule instead, from two values per tree kept in the companion:
   the time its last refill was paid up to (`credit`) and the moment of its next refill (`due`).
   At `due` a tree gains the stock amount for the time since `credit` -- floor((now - credit) *
   factor / 3600), the same formula, factor and Nature rules -- and both move on (credit = now,
   due = now + the interval).  So every tree earns fruit at exactly the stock rate for exactly
   the time that passed; only WHEN it is paid changes.  After every change the dues are laid out
   again: the earliest keeps its moment and the others follow it by 0 (together) or by
   interval / number of trees (in turns), in the order they were due.

   A tree the companion has not seen yet (a newly planted one, or every tree of a village loaded
   without a matching entry in the file) starts from its own stock timer, as the stock game
   would pay it, and joins the schedule.  A removed tree simply leaves it.

   THE FILE.  The schedule is kept per save in
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Fruit Trees\
           Virtual Villagers 3 Fruit Tree Timers - Save <S>.dat
   (sidecar_io.h: atomic writes, an unreadable file never replaced, an invalid one set aside),
   one entry per save written, bound to that save by an FNV-1a fingerprint of the trees' saved
   bytes, the last 16 kept.  An entry is used only by the companion that wrote it (the mode), so
   switching between the two patches starts each from the stock timers.  Start Over deletes the
   file (native/shared/save_reset.c).

   Sites, all checked stock before anything is written, and written all or none:
     0x43478A  mov eax,[esi+0x64] / xor ebx,ebx  -> the pass; on at 0x43481B (the stock loop is
                                                    not run)
     0x433E40  the loader's first 7 bytes          -> the stock loader, then the file's entry
     0x433EC0  the saver's first 7 bytes           -> the file's entry, then the stock saver
   The interval and the Nature factor are read from the game's own bytes, which must be the
   stock ones or the patcher's Nature patch exactly; anything else installs nothing. */
#ifndef VV3_FRUIT_TIMERS_H
#define VV3_FRUIT_TIMERS_H

#include <windows.h>
#include <shlobj.h>
#include <string.h>
#include "sidecar_io.h"
#include "game_save_slot.h"

#if !defined(VV3_FRUIT_MODE) || (VV3_FRUIT_MODE != 1 && VV3_FRUIT_MODE != 2)
#error "define VV3_FRUIT_MODE 1 (together) or 2 (in turns) before including vv3_fruit_timers.h"
#endif

#define VV3_GAME 3

#define TREES 0x5947E0u
#define TREE_MAX 3
#define TREE_RECORDS 0x1Cu        /* x, y, planted, timer, kind, fruit (6 dwords each) */
#define TREE_HEADER 0x08u         /* the 5 dwords saved before the records */
#define TREE_COUNT 0x64u
#define FRUIT_FULL 1000
#define CLOCK_OBJECT 0x5825D4u
#define CLOCK 0x426590u           /* thiscall(), the game clock in game seconds */
#define TECH 0x582618u            /* the technology levels: Nature is +4*5 */
#define NATURE 5

#define PASS_SITE 0x43478Au
#define PASS_DONE 0x43481Bu
#define LOAD_SITE 0x433E40u
#define LOAD_CONTINUE 0x433E47u
#define SAVE_SITE 0x433EC0u
#define SAVE_CONTINUE 0x433EC7u
#define SAVED_BYTES 0x60

#define TEST_SITE 0x4347AAu       /* the stock interval test, or the Nature patch's jump */
#define FACTOR_SITE 0x4347BEu     /* mov ebp, 37 */
#define NATURE_FACTOR_SITE 0x4347CDu  /* mov ebp, 42 (56 with the Nature patch) */
#define NATURE_CAVE 0x47B380u     /* the Nature patch's interval test */

static const unsigned char PASS_STOCK[5] = { 0x8B, 0x46, 0x64, 0x33, 0xDB };
static const unsigned char LOAD_STOCK[7] = { 0x53, 0x8B, 0x5C, 0x24, 0x08, 0x55, 0x56 };
static const unsigned char SAVE_STOCK[7] = { 0x8B, 0xC1, 0x83, 0x7C, 0x24, 0x08, 0x60 };
static const unsigned char TEST_STOCK[13] = {
    0x8B, 0x4F, 0xF8, 0x81, 0xC1, 0x30, 0x2A, 0x00, 0x00, 0x3B, 0xC1, 0x72, 0x4A };
/* The patcher's "Nature Level 1 Actually Replenishes Food Sources Faster" (data/builds.json,
   vv3_nature_honey_refill): the test jumps to its cave, which uses 8,100 s at Nature 1 or more. */
static const unsigned char TEST_NATURE[13] = {
    0xE9, 0xD1, 0x6B, 0x04, 0x00, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
static const unsigned char CAVE_NATURE[49] = {
    0x50, 0x6A, 0x05, 0xB9, 0x18, 0x26, 0x58, 0x00, 0xE8, 0x33, 0xBC, 0xFA, 0xFF, 0x83, 0xF8, 0x01,
    0x58, 0x8B, 0x4F, 0xF8, 0x7C, 0x08, 0x81, 0xC1, 0xA4, 0x1F, 0x00, 0x00, 0xEB, 0x06, 0x81, 0xC1,
    0x30, 0x2A, 0x00, 0x00, 0x3B, 0xC1, 0x0F, 0x82, 0x55, 0x94, 0xFB, 0xFF, 0xE9, 0x06, 0x94, 0xFB,
    0xFF };

typedef struct {
    int x, y, planted, kind;      /* who the tree is */
    unsigned int credit;          /* its fruit is paid up to here */
    unsigned int due;             /* its next refill */
} tree_timer;

static int installed;
static unsigned int g_interval[2];   /* below Nature 1, and at Nature 1 or more */
static unsigned int g_factor[2];
static tree_timer g_tree[TREE_MAX];
static int g_count = -1;             /* -1: no tree known yet */
static unsigned int g_laid_out;      /* the interval the dues were laid out with (0: none) */
static vv_sidecar_gate g_gate;

static int *record(const unsigned char *trees, int i) {
    return (int *)(trees + TREE_RECORDS + 0x18u * (unsigned int)i);
}

/* The trees that stay: the update's tail (0x43487F) ends the list at the first tree with no
   position, kind -1 or no planted time, so a dying tree never joins (or pulls) the schedule. */
static int live_count(const unsigned char *trees) {
    int n = *(const volatile int *)(trees + TREE_COUNT), i;
    if (n > TREE_MAX) {
        n = TREE_MAX;
    }
    for (i = 0; i < n; ++i) {
        const int *r = record(trees, i);
        if ((r[0] == 0 && r[1] == 0) || r[4] == -1 || r[2] == 0) {
            break;
        }
    }
    return i;
}

static int nature_index(void) {
    return *(const volatile int *)(uintptr_t)(TECH + 4u * NATURE) >= 1 ? 1 : 0;
}

typedef unsigned int (__fastcall *clock_fn)(void *self, void *unused);

static unsigned int game_clock(void) {
    return ((clock_fn)(uintptr_t)CLOCK)((void *)(uintptr_t)CLOCK_OBJECT, 0);
}

/* ---- the schedule -------------------------------------------------------------------- */

/* The live trees, matched to the ones known by who they are (a removal closes the list up);
   one not known starts from its own stock timer.  1 when anything changed. */
static int reconcile(const unsigned char *trees, unsigned int interval) {
    tree_timer next[TREE_MAX];
    int n = live_count(trees), i, j, changed = n != g_count;
    for (i = 0; i < n; ++i) {
        const int *r = record(trees, i);
        int found = -1;
        for (j = 0; j < g_count; ++j) {
            if (g_tree[j].x == r[0] && g_tree[j].y == r[1] && g_tree[j].planted == r[2]
                && g_tree[j].kind == r[4]) {
                found = j;
                break;
            }
        }
        if (found >= 0) {
            next[i] = g_tree[found];
            changed |= found != i;
        } else {
            next[i].x = r[0];
            next[i].y = r[1];
            next[i].planted = r[2];
            next[i].kind = r[4];
            next[i].credit = (unsigned int)r[3];
            next[i].due = (unsigned int)r[3] + interval;
            changed = 1;
        }
    }
    memcpy(g_tree, next, sizeof(tree_timer) * (size_t)n);
    g_count = n;
    return changed;
}

/* The earliest due keeps its moment; the others follow it, in the order they were due, by
   `spacing` each (0 together; the interval over the number of trees in turns). */
static void lay_out(unsigned int interval) {
    int order[TREE_MAX], i, j;
    unsigned int spacing = VV3_FRUIT_MODE == 2 && g_count > 0 ? interval / (unsigned int)g_count : 0u;
    for (i = 0; i < g_count; ++i) {
        order[i] = i;
    }
    for (i = 1; i < g_count; ++i) {
        for (j = i; j > 0 && g_tree[order[j]].due < g_tree[order[j - 1]].due; --j) {
            int t = order[j];
            order[j] = order[j - 1];
            order[j - 1] = t;
        }
    }
    for (i = 1; i < g_count; ++i) {
        g_tree[order[i]].due = g_tree[order[0]].due + spacing * (unsigned int)i;
    }
    g_laid_out = interval;
}

/* The live trees known, and their dues counted with today's interval (Nature 1 can shorten it).
   1 when the dues must be laid out again. */
static int settle(const unsigned char *trees, unsigned int interval) {
    int changed = reconcile(trees, interval), i;
    if (interval != g_laid_out) {
        for (i = 0; i < g_count; ++i) {
            g_tree[i].due = g_tree[i].credit + interval;
        }
        changed = 1;
    }
    return changed;
}

/* The trees' update, in place of the stock loop (0x43478A..0x43481A). */
static void __cdecl pass(unsigned char *trees) {
    unsigned int now = game_clock();
    int nature = nature_index(), i;
    unsigned int interval = g_interval[nature], factor = g_factor[nature];
    int changed = settle(trees, interval);
    for (i = 0; i < g_count; ++i) {
        int *r = record(trees, i);
        /* The tree's own timer, as the stock loop moves it (the save keeps this one). */
        if (now >= (unsigned int)r[3] + interval) {
            r[3] = (int)now;
        }
        if (now >= g_tree[i].due) {
            r[5] += (int)(((now - g_tree[i].credit) * factor) / 3600u);
            g_tree[i].credit = now;
            g_tree[i].due = now + interval;
            changed = 1;
        }
        if (r[5] > FRUIT_FULL) {
            r[5] = FRUIT_FULL;
        }
    }
    if (changed) {
        lay_out(interval);
    }
}

/* ---- the file ------------------------------------------------------------------------ */

#define FILE_MAGIC 0x54335656u    /* 'V' 'V' '3' 'T' */
#define FILE_VERSION 1u
#define ENTRIES 16

#pragma pack(push, 1)
typedef struct {
    unsigned int fp_lo, fp_hi;    /* the trees' saved bytes */
    unsigned char mode;           /* VV3_FRUIT_MODE of the companion that wrote it */
    unsigned char count;          /* trees */
    unsigned char unused[2];
    unsigned int interval;        /* the interval the dues were laid out with */
    unsigned int credit[TREE_MAX];
    unsigned int due[TREE_MAX];
} timer_entry;

typedef struct {
    unsigned int magic, version, game, slot, count;
    timer_entry entry[ENTRIES];
} timer_file;
#pragma pack(pop)

/* "<Documents>\LDW\<executable's name>\Virtual Villagers Fun Patcher\Save <S>\Data\Fruit Trees\
   Virtual Villagers 3 Fruit Tree Timers - Save <S>.dat"; `make` creates the folders. */
static int timer_path(int slot, char *out, int make) {
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
    wsprintfA(part, "\\Virtual Villagers 3 Fruit Tree Timers - Save %d.dat", slot);
    lstrcatA(out, part);
    return 1;
}

static int valid_file(const unsigned char *data, DWORD len, void *ctx) {
    const timer_file *f = (const timer_file *)data;
    unsigned int i;
    if (len != sizeof(timer_file) || f->magic != FILE_MAGIC || f->version != FILE_VERSION
        || f->game != VV3_GAME || f->slot != (unsigned int)*(int *)ctx || f->count > ENTRIES) {
        return 0;
    }
    for (i = 0; i < f->count; ++i) {
        const timer_entry *e = &f->entry[i];
        if ((e->mode != 1 && e->mode != 2) || e->count > TREE_MAX || e->interval == 0) {
            return 0;
        }
    }
    return 1;
}

/* Read the slot's file: 1 valid, 0 none (missing or set aside), -1 blocked. */
static int read_file(int slot, timer_file *f, char *path) {
    DWORD got = 0;
    int r;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (!timer_path(slot, path, 0)) {
        return -1;
    }
    r = vv_sidecar_load(&g_gate, path, (unsigned char *)f, sizeof *f, &got, valid_file, &slot);
    if (r == VV_SIDECAR_LOAD_BLOCKED) {
        return -1;
    }
    return r == VV_SIDECAR_LOAD_VALID ? 1 : 0;
}

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

/* The trees as the saver writes them: the header, `count` records and the count. */
static void fingerprint(const unsigned char *header, const unsigned char *records, int count,
                        unsigned int *lo, unsigned int *hi) {
    *lo = 0x84222325u;              /* the FNV-1a 64 offset basis */
    *hi = 0xCBF29CE4u;
    fnv(lo, hi, header, 0x14u);
    fnv(lo, hi, records, 0x18u * (unsigned int)count);
    fnv(lo, hi, (const unsigned char *)&count, 4u);
}

/* ---- the save and the load ----------------------------------------------------------- */

/* Before the stock saver writes the trees (`size` is the room it was given). */
static void __cdecl on_save(unsigned char *trees, unsigned int size) {
    static timer_file f;
    char path[MAX_PATH];
    const void *parts[1];
    DWORD sizes[1];
    unsigned int lo, hi, i, keep = 0;
    int slot = vv_game_save_slot(VV3_GAME), n, r;
    unsigned int interval;
    if (size < SAVED_BYTES || slot == 0) {
        return;
    }
    interval = g_interval[nature_index()];
    if (settle(trees, interval)) {
        lay_out(interval);
    }
    n = *(const volatile int *)(trees + TREE_COUNT);     /* the count the saver writes */
    if (n < 0 || n > TREE_MAX) {
        return;
    }
    fingerprint(trees + TREE_HEADER, trees + TREE_RECORDS, n, &lo, &hi);
    n = g_count;
    r = read_file(slot, &f, path);
    if (r < 0) {
        return;                     /* present but unreadable: never replaced */
    }
    if (r == 0) {
        memset(&f, 0, sizeof f);
    }
    /* This save's entry replaces one with the same fingerprint; the other patch's go. */
    for (i = 0; i < f.count; ++i) {
        if (f.entry[i].mode == VV3_FRUIT_MODE && !(f.entry[i].fp_lo == lo && f.entry[i].fp_hi == hi)) {
            f.entry[keep++] = f.entry[i];
        }
    }
    f.count = keep;
    if (f.count == ENTRIES) {
        memmove(&f.entry[0], &f.entry[1], sizeof(timer_entry) * (ENTRIES - 1));
        f.count = ENTRIES - 1;
    }
    memset(&f.entry[f.count], 0, sizeof(timer_entry));
    f.entry[f.count].fp_lo = lo;
    f.entry[f.count].fp_hi = hi;
    f.entry[f.count].mode = VV3_FRUIT_MODE;
    f.entry[f.count].count = (unsigned char)n;
    f.entry[f.count].interval = g_laid_out;
    for (i = 0; i < (unsigned int)n; ++i) {
        f.entry[f.count].credit[i] = g_tree[i].credit;
        f.entry[f.count].due[i] = g_tree[i].due;
    }
    f.count += 1;
    f.magic = FILE_MAGIC;
    f.version = FILE_VERSION;
    f.game = VV3_GAME;
    f.slot = (unsigned int)slot;
    if (!timer_path(slot, path, 1)) {
        return;
    }
    parts[0] = &f;
    sizes[0] = sizeof f;
    (void)vv_sidecar_publish(&g_gate, path, parts, sizes, 1);
}

/* After the stock loader filled the trees from `in` (the saved bytes): the schedule written
   with exactly this save, or none (every tree then starts from its stock timer). */
static void __cdecl on_load(unsigned char *trees, const unsigned char *in) {
    static timer_file f;
    char path[MAX_PATH];
    unsigned int lo, hi, i;
    int slot = vv_game_save_slot(VV3_GAME), saved = *(const int *)(in + 0x5C), n = live_count(trees), k;
    g_count = -1;
    g_laid_out = 0;
    if (slot == 0 || saved < 0 || saved > TREE_MAX || read_file(slot, &f, path) != 1) {
        return;
    }
    fingerprint(in, in + 0x14, saved, &lo, &hi);
    for (i = f.count; i-- > 0;) {
        const timer_entry *e = &f.entry[i];
        if (e->mode != VV3_FRUIT_MODE || e->fp_lo != lo || e->fp_hi != hi) {
            continue;
        }
        if (n > e->count) {
            n = e->count;
        }
        for (k = 0; k < n; ++k) {
            const int *r = record(trees, k);
            g_tree[k].x = r[0];
            g_tree[k].y = r[1];
            g_tree[k].planted = r[2];
            g_tree[k].kind = r[4];
            g_tree[k].credit = e->credit[k];
            g_tree[k].due = e->due[k];
        }
        g_count = n;
        g_laid_out = e->interval;
        return;
    }
}

/* ---- the stubs ----------------------------------------------------------------------- */

/* At PASS_SITE: esi = the trees; ebx, esi and edi are the routine's own pushes. */
static __declspec(naked) void pass_stub(void) {
    __asm {
        pushad
        push esi
        call pass
        add esp, 4
        popad
        push PASS_DONE
        ret
    }
}

/* The stock loader's first 7 bytes, then on into it. */
static __declspec(naked) void load_trampoline(void) {
    __asm {
        push ebx
        mov ebx, dword ptr [esp + 8]
        push ebp
        push esi
        push LOAD_CONTINUE
        ret
    }
}

/* At LOAD_SITE (thiscall, ret 4): the stock loader runs first, then on_load. */
static __declspec(naked) void load_stub(void) {
    __asm {
        push ecx
        push dword ptr [esp + 8]
        call load_trampoline
        pop ecx
        pushad
        push dword ptr [esp + 0x24]
        push ecx
        call on_load
        add esp, 8
        popad
        ret 4
    }
}

/* At SAVE_SITE (thiscall(out, size), ret 8): on_save, then the stock saver from its start. */
static __declspec(naked) void save_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x28]
        push ecx
        call on_save
        add esp, 8
        popad
        mov eax, ecx
        cmp dword ptr [esp + 8], 0x60
        push SAVE_CONTINUE
        ret
    }
}

/* ---- installing ---------------------------------------------------------------------- */

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

static int is_bytes(unsigned int va, const unsigned char *bytes, size_t length) {
    return memcmp((const void *)(uintptr_t)va, bytes, length) == 0;
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

/* The interval and the factors the game's own pass uses: stock, or the Nature patch. */
static int read_rules(void) {
    const unsigned char *base = (const unsigned char *)(uintptr_t)FACTOR_SITE;
    const unsigned char *nature = (const unsigned char *)(uintptr_t)NATURE_FACTOR_SITE;
    if (base[0] != 0xBD || nature[0] != 0xBD) {
        return 0;
    }
    memcpy(&g_factor[0], base + 1, 4);
    memcpy(&g_factor[1], nature + 1, 4);
    g_interval[0] = 10800u;
    if (is_bytes(TEST_SITE, TEST_STOCK, sizeof TEST_STOCK)) {
        g_interval[1] = 10800u;
    } else if (is_bytes(TEST_SITE, TEST_NATURE, sizeof TEST_NATURE)
               && is_bytes(NATURE_CAVE, CAVE_NATURE, sizeof CAVE_NATURE)) {
        g_interval[1] = 8100u;
    } else {
        return 0;
    }
    return g_factor[0] > 0u && g_factor[0] < 1000u && g_factor[1] > 0u && g_factor[1] < 1000u;
}

/* Every site stock, or nothing: the save and load first, the pass last (until it is written
   the stock loop pays the fruit); a write that fails puts back what was written. */
static void install(void) {
    if (installed
        || !is_bytes(PASS_SITE, PASS_STOCK, sizeof PASS_STOCK)
        || !is_bytes(LOAD_SITE, LOAD_STOCK, sizeof LOAD_STOCK)
        || !is_bytes(SAVE_SITE, SAVE_STOCK, sizeof SAVE_STOCK)
        || !read_rules()) {
        return;
    }
    if (!write_jump(LOAD_SITE, load_stub, sizeof LOAD_STOCK)) {
        return;
    }
    if (!write_jump(SAVE_SITE, save_stub, sizeof SAVE_STOCK)) {
        write_code(LOAD_SITE, LOAD_STOCK, sizeof LOAD_STOCK);
        return;
    }
    if (!write_jump(PASS_SITE, pass_stub, sizeof PASS_STOCK)) {
        write_code(SAVE_SITE, SAVE_STOCK, sizeof SAVE_STOCK);
        write_code(LOAD_SITE, LOAD_STOCK, sizeof LOAD_STOCK);
        return;
    }
    installed = 1;
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

#endif /* VV3_FRUIT_TIMERS_H */
