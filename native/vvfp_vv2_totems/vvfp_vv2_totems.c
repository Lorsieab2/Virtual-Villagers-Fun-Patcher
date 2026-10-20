/* VVFP VV2 Totems -- The Lost Children's Esteemed Elder totems live outside
   the 256 villager records (the owner, 2026-10-19).

   WHY.  The stock game makes each Esteemed Elder's totem statue in a villager
   record (0x44D190: the first record not in use) and never frees it.  In the
   owner's full village 13 of the 256 records were statues while 11 nursing
   mothers' babies waited for a record, and when a record freed, a new elder's
   totem took it before a waiting baby.  Here every totem is kept in a store of
   this companion's own, saved beside the save in
       <save folder>\Virtual Villagers Fun Patcher\Save <N>\Data\Elder Totems\ElderTotems.dat
   and drawn, labelled and dragged as the game does a totem record.  The game's
   .ldw stays the stock game's own format: it simply holds no totem.

   THE GAME, read from the stock executable (46C1503C...D677):
     world   [0x499F24]: the 256 records, record i at world + i * 0xE48C
             (+0x30 in use, +0x31 picked, +0x32 held, +0x52C health,
             +0x558 Is Totem, +0x550 Totem Type, +0x04/+0x08 x/y,
             +0x55C/+0x560 home x/y); world+0xE574D4 the game object
             (camera x/y at +8/+0xC, selected record at +0x304F0);
             world+0xE57090 the 256-entry draw order (0x44B0E0 sorts it by
             y, a totem's y + 0x23); world+0xE574D0 the renderer,
             +0xE57494 the shadow image, +0xE574CC totems.png.
     save    0x44B580 packs every record in use into the game object's save
             image: 0x2E0-byte entries (record +0x524..+0x7E3, then
             +0x7E4..+0x7FF, then 1 at +0x2DC); the loader 0x44B640 unpacks
             them and puts a totem's home x/y back as its x/y.

   HOOKS (runtime detours, every site's stock bytes verified first; any
   difference and nothing at all is installed, so the game runs stock):
     0x4249A0 load (thiscall manager, slot): after a village slot (1-5, or
              its backup 21-25) loads, the store is read from ElderTotems.dat
              and every record holding a totem statue (+0x558 set, health 0
              or less) is MOVED into it: the record is freed as the burial
              frees a body (0x46503B: +0x30 = 0, after 0x4491F0 when it was
              picked) and its +0x558 cleared.  A record with +0x558 set and
              health above 0 is a living villager, never moved.  A statue the
              store already holds (the same name, sex, head, body, family,
              parents and Totem Type: a save restored from a backup) is not
              added twice; its record is freed all the same.
     0x424BA0 save (thiscall manager, slot): before the game writes a village
              slot (1-5) the store is written to ElderTotems.dat (a temporary
              file, then a move), with the village's roster to bind it.  If
              it cannot be written the game's save of that slot is refused
              (the previous save and file stay a matching pair).
     0x424C80 world reset (new tribe, Start Over, the startup's seeding):
              the store is emptied; it belongs to no slot until saved.
     0x44D190 the totem maker (thiscall world, elder): does what the stock
              routine does -- the first-elder clock and message, the statue
              copied from the elder (0x44D25A..0x44D49E), the elder's +0x7FC
              -- but the statue goes into the store, never into a record.
     0x44D4D1 / 0x44D54C the elder pass's two "fewer than 50 totems" checks:
              with the store working, never a reason to wait (unlimited elder
              totems: a totem costs no record).  With the store not working
              (its file could not be read) the game's own checks stand.
     0x445C1C / 0x4478CD the village draw loop: before each record in the
              draw order, the store's totems that sort before it (the same y
              + 0x23 key) are drawn with the game's own calls -- the shadow
              (0x4095A0) and the totem frame Totem Type % 8 (0x4095C0) --
              and the rest after the last record; a totem being dragged last.
     0x4490BB the Map: each store totem drawn as the Map draws a totem
              (0x409610, x / 4 + 0xAF, (y - 0x41) / 4 + 0x29, frame, 0x19, 1).
     0x431071 the click's hit test (0x44D580): a store totem in front of the
              record the game found (by the draw order) is picked instead.
     0x431076 then the click ends there (the game object's selection -1), as
              a totem click selects nothing else and starts no camera drag.
     0x429A83 the selected villager's name panel: with no record selected and
              a store totem picked, "<name>`s totem" (0x476BEC), as the stock
              panel words a totem record.
     0x4308D0 the village's mouse handler (thiscall ui, event, x, y): a
              picked store totem is dragged as the game drags a totem record
              -- picked up after 5 pixels (0x431408), moved as 0x449220 moves
              one, the view's edge scroll as 0x4316DD sets it, and on release
              placed as 0x430943..0x430FED places one: kept inside the map,
              the dust and the sound where it lands (0x4309D6), the totem
              puzzle's spot (terrain 0x42, 0x430382), nudged off ground it
              cannot stand on (0x42D140), and its home x/y stored (0x449260).

   THE FILE (version 1, little-endian; src/vv_vv2_totem_store.py writes the
   same):
       "VVFP VV2 TOTEMS\0", version 1, game 2, slot, entry size 0x2E0,
       roster count R, totem count T, R roster rows (name[24], head, body,
       sex), T totems each exactly as the game saves a record (0x2E0 bytes),
       then the FNV-1a hash of everything before it.
   A file bound to another village (fewer than half its roster in the loaded
   save) is moved aside as "ElderTotems.dat.another-village-<ticks>-<n>",
   never overwritten; a file that cannot be read is moved aside as
   ".unreadable-..." (native/shared/sidecar_io.h); a file that exists but
   cannot be opened leaves this session stock (nothing moved, nothing
   written).

   EXPORTS for the Story / Cheat Upgrades and Island Events companions:
   VvfpTotemsActive, VvfpTotemCount, VvfpTotemFaceOf(elder record) and
   VvfpTotemSetFace(elder record, face). */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "../shared/sidecar_io.h"
#include "../shared/save_folder.h"
#include "../shared/per_save.h"

#define GAME 2
#define RECORDS 256
#define STRIDE 0xE48Cu
#define ENTRY 0x2E0u
#define MAX_TOTEMS 100000
#define VV_PS_RESERVE_TOTEMS 40      /* ".another-village-<ticks>-<n>" and the NUL */

/* Globals of the game. */
#define WORLD_GLOBAL 0x499F24u
/* World offsets. */
#define W_GAME 0xE574D4u
#define W_ORDER 0xE57090u
#define W_RENDERER 0xE574D0u
#define W_SHADOW 0xE57494u
#define W_TOTEMS 0xE574CCu
/* Game object offsets. */
#define G_CAMX 0x8u
#define G_CAMY 0xCu
#define G_SELECTED 0x304F0u
#define G_PUZZLE 0x2E7D4u
/* Record offsets. */
#define R_X 0x04u
#define R_Y 0x08u
#define R_IN_USE 0x30u
#define R_PICKED 0x31u
#define R_HELD 0x32u
#define R_HEALTH 0x52Cu
#define R_IS_TOTEM 0x558u
#define R_ELDER 0x7FCu
/* Saved-entry offsets (record offset - 0x524). */
#define E_TIME 0x04u
#define E_HEALTH 0x08u
#define E_AGE 0x0Cu
#define E_AGE2 0x10u
#define E_SEX 0x14u
#define E_HEAD 0x24u
#define E_BODY 0x28u
#define E_TYPE 0x2Cu
#define E_LINEAGE 0x30u
#define E_IS_TOTEM 0x34u
#define E_X 0x38u
#define E_Y 0x3Cu
#define E_NAME 0x40u
#define E_FATHER 0x59u
#define E_MOTHER 0x72u
#define E_PARENTS_LEN 0x32u
#define E_FLAG 0x2DCu
#define NAME_CAP 0x18u
/* UI (the village screen) offsets. */
#define U_PARTICLES 0x08u
#define U_GAME 0x10u
#define U_TERRAIN 0x14u
#define U_SOUND 0x18u
#define U_PUZZLE 0x24u
#define U_MOUSE_X 0x3Cu
#define U_MOUSE_Y 0x40u
#define U_PRESS_X 0x1B8u
#define U_PRESS_Y 0x1BCu
#define U_PRESSED 0x1D0u
#define U_PANNING 0x1E0u
#define U_VIEW_L 0x1E8u
#define U_VIEW_T 0x1ECu
#define U_VIEW_R 0x1F0u
#define U_VIEW_B 0x1F4u
#define U_SCROLL_X 0x228u
#define U_SCROLL_Y 0x22Cu
#define U_HOLD_X 0x238u
#define U_HOLD_Y 0x23Cu

/* ---- game routines (thiscall as __fastcall with an unused edx) ------------ */
typedef void (__fastcall *draw3_fn)(void *renderer, int, void *image, int x, int y);
typedef void (__fastcall *draw4_fn)(void *renderer, int, void *image, int x, int y, int frame);
typedef void (__fastcall *draw6_fn)(void *renderer, int, void *image, int x, int y, int frame, int a, int b);
typedef int (__fastcall *terrain_fn)(void *terrain, int, int x, int y);
typedef void (__fastcall *particles7_fn)(void *particles, int, int kind, int x, int y, int a, int b, int c, int d);
typedef void (__fastcall *particles3_fn)(void *particles, int, int kind, int x, int y);
typedef void (__fastcall *sound_fn)(void *sound, int, int id);
typedef void (__fastcall *sound_volume_fn)(void *sound, int, int id, float volume);
typedef void (__fastcall *method0_fn)(void *self, int);
typedef unsigned int (__fastcall *clock_fn)(void *game, int);
typedef void (__fastcall *message_fn)(void *game, int, int id, int show);
typedef int (__cdecl *rand_fn)(int n);
typedef int (__fastcall *hit_fn)(void *world, int, int x, int y);
typedef int (__fastcall *create_fn)(void *world, int, int elder);
typedef unsigned char (__fastcall *slot_fn)(void *manager, int, int slot);
typedef int (__fastcall *reset_fn)(void *manager, int, int arg);
typedef unsigned char (__fastcall *input_fn)(void *ui, int, int event, int x, int y);

#define DRAW_SHADOW ((draw3_fn)0x4095A0u)
#define DRAW_FRAME ((draw4_fn)0x4095C0u)
#define DRAW_MAP ((draw6_fn)0x409610u)
#define TERRAIN_AT ((terrain_fn)0x4181D0u)
#define PARTICLES ((particles7_fn)0x4239D0u)
#define SPARKLES ((particles3_fn)0x423980u)
#define SOUND ((sound_fn)0x43F010u)
#define SOUND_AT ((sound_volume_fn)0x43F030u)
#define PUZZLE_SOLVED ((method0_fn)0x41C1D0u)
#define UNPICK_ALL ((method0_fn)0x4491F0u)
#define GAME_CLOCK ((clock_fn)0x403200u)
#define MESSAGE ((message_fn)0x4257A0u)
#define RAND ((rand_fn)0x4031A0u)
#define HIT_TEST ((hit_fn)0x44D580u)

static const char LABEL_SUFFIX_AT[] = "`s totem";   /* the game's own at 0x476BEC */
#define LABEL_SUFFIX_VA 0x476BECu
#define NO_SELECTION_VA 0x47443Cu

/* ---- the store ------------------------------------------------------------ */
typedef struct {
    unsigned char e[ENTRY];
} totem_t;

static totem_t *g_t;
static int g_n, g_cap;
static int g_installed;          /* every hook in place */
static int g_active = 1;         /* 0: the file could not be opened this session -- stock behaviour */
static int g_slot;               /* the slot the store was read from or last written to; 0 none */
static vv_sidecar_gate g_gate;

static int g_selected = -1;      /* the store totem picked by a click */
static int g_pressed = -1;       /* ...and held down */
static int g_dragging;
static int g_drag_x, g_drag_y;   /* its place while dragged */
static unsigned char g_hit_store;
static char g_label[NAME_CAP + 16];

static int i32(const unsigned char *p, unsigned int at) {
    int v;
    memcpy(&v, p + at, 4);
    return v;
}

static void put32(unsigned char *p, unsigned int at, int v) {
    memcpy(p + at, &v, 4);
}

static unsigned char *world_of(void) {
    return *(unsigned char **)(uintptr_t)WORLD_GLOBAL;
}

static unsigned char *record(unsigned char *world, int i) {
    return world + (size_t)i * STRIDE;
}

static unsigned char *game_of(unsigned char *world) {
    return *(unsigned char **)(world + W_GAME);
}

static int reserve(int n) {
    totem_t *grown;
    int cap;
    if (n <= g_cap) {
        return 1;
    }
    if (n > MAX_TOTEMS) {
        return 0;
    }
    cap = g_cap ? g_cap : 1024;
    while (cap < n) {
        cap *= 2;
    }
    grown = g_t ? (totem_t *)HeapReAlloc(GetProcessHeap(), 0, g_t, (SIZE_T)cap * sizeof(totem_t))
                : (totem_t *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)cap * sizeof(totem_t));
    if (grown == NULL) {
        return 0;
    }
    g_t = grown;
    g_cap = cap;
    return 1;
}

static void forget_pick(void) {
    g_selected = -1;
    g_pressed = -1;
    g_dragging = 0;
}

static void clear_store(void) {
    g_n = 0;
    forget_pick();
}

/* What 0x44D190 copies that tells one statue from another. */
static int same_statue(const unsigned char *a, const unsigned char *b) {
    return strncmp((const char *)a + E_NAME, (const char *)b + E_NAME, NAME_CAP) == 0
        && i32(a, E_SEX) == i32(b, E_SEX) && i32(a, E_HEAD) == i32(b, E_HEAD)
        && i32(a, E_BODY) == i32(b, E_BODY) && i32(a, E_LINEAGE) == i32(b, E_LINEAGE)
        && i32(a, E_TYPE) == i32(b, E_TYPE)
        && strncmp((const char *)a + E_FATHER, (const char *)b + E_FATHER, 0x19) == 0
        && strncmp((const char *)a + E_MOTHER, (const char *)b + E_MOTHER, 0x19) == 0;
}

/* A record's saved entry, exactly as the game's packer 0x44B580 writes it. */
static void pack(const unsigned char *r, unsigned char *e) {
    memset(e, 0, ENTRY);
    memcpy(e, r + 0x524, 0x2C0);
    memcpy(e + 0x2C0, r + 0x7E4, 0x1C);
    e[E_FLAG] = 1;
}

/* ---- the file ------------------------------------------------------------- */
static const char MAGIC[16] = "VVFP VV2 TOTEMS";
#define HEADER 40u
#define ROSTER_ROW 36u

static unsigned int fnv1a(const unsigned char *p, DWORD n) {
    unsigned int h = 2166136261u;
    DWORD i;
    for (i = 0; i < n; ++i) {
        h = (h ^ p[i]) * 16777619u;
    }
    return h;
}

static int store_path(int slot, char *out) {
    char folder[MAX_PATH];
    char tail[128];
    if (slot < 1 || slot > 5) {
        return 0;
    }
    wsprintfA(tail, "\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Elder Totems\\ElderTotems.dat", slot);
    if (!vv_save_folder(folder, lstrlenA(tail) + VV_PS_RESERVE_TOTEMS)) {
        return 0;
    }
    lstrcpyA(out, folder);
    lstrcatA(out, tail);
    return 1;
}

static int valid_file(const unsigned char *d, DWORD n, void *ctx) {
    unsigned int roster, totems, hash;
    (void)ctx;
    if (n < HEADER + 4 || memcmp(d, MAGIC, 16) != 0 || i32(d, 16) != 1 || i32(d, 20) != GAME
        || (unsigned int)i32(d, 28) != ENTRY) {
        return 0;
    }
    roster = (unsigned int)i32(d, 32);
    totems = (unsigned int)i32(d, 36);
    if (roster > RECORDS || totems > MAX_TOTEMS
        || (unsigned long long)HEADER + (unsigned long long)roster * ROSTER_ROW
               + (unsigned long long)totems * ENTRY + 4 != n) {
        return 0;
    }
    memcpy(&hash, d + n - 4, 4);
    return hash == fnv1a(d, n - 4);
}

/* Whether more than half of the file's roster stands in the loaded records. */
static int bound_to(const unsigned char *d, unsigned char *world) {
    unsigned int roster = (unsigned int)i32(d, 32), k, found = 0;
    int i;
    if (roster == 0) {
        return i32(d, 36) == 0;
    }
    for (k = 0; k < roster; ++k) {
        const unsigned char *row = d + HEADER + k * ROSTER_ROW;
        for (i = 0; i < RECORDS; ++i) {
            const unsigned char *r = record(world, i);
            if (r[R_IN_USE] != 0 && r[R_IS_TOTEM] == 0
                && strncmp((const char *)row, (const char *)r + 0x564, NAME_CAP) == 0
                && i32(row, 24) == i32(r, 0x548) && i32(row, 28) == i32(r, 0x54C)
                && i32(row, 32) == i32(r, 0x538)) {
                ++found;
                break;
            }
        }
    }
    return found * 2 > roster;
}

/* Move `path` aside to "<path><tag><ticks>-<n>" without replacing anything. */
static int move_aside(const char *path, const char *tag) {
    char aside[MAX_PATH + 64];
    int n;
    for (n = 0; n < 1000; ++n) {
        wsprintfA(aside, "%s%s%u-%d", path, tag, (unsigned int)GetTickCount(), n);
        if (lstrlenA(aside) >= MAX_PATH) {
            return 0;
        }
        if (MoveFileExA(path, aside, MOVEFILE_WRITE_THROUGH)) {
            return 1;
        }
        if (GetLastError() != ERROR_ALREADY_EXISTS && GetLastError() != ERROR_FILE_EXISTS) {
            return 0;
        }
    }
    return 0;
}

/* Read the slot's file into the store.  1 = the store is the file's (or
   empty: no file, or one moved aside); 0 = it could not be opened (blocked). */
static int read_store(int slot, unsigned char *world) {
    char path[MAX_PATH];
    unsigned char *buf;
    WIN32_FILE_ATTRIBUTE_DATA info;
    DWORD cap, len = 0;
    int got;
    clear_store();
    vv_sidecar_gate_bind(&g_gate, slot);
    g_gate.state = VV_SIDECAR_UNKNOWN;
    g_gate.path[0] = '\0';
    if (!store_path(slot, path)) {
        return 0;
    }
    cap = 64;
    if (GetFileAttributesExA(path, GetFileExInfoStandard, &info)) {
        if (info.nFileSizeHigh != 0 || info.nFileSizeLow > HEADER + RECORDS * ROSTER_ROW + MAX_TOTEMS * ENTRY + 4) {
            cap = HEADER + 4;       /* too big to be ours: read a little and it is set aside */
        } else {
            cap = info.nFileSizeLow + 1;
        }
    }
    buf = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, cap);
    if (buf == NULL) {
        return 0;
    }
    got = vv_sidecar_load(&g_gate, path, buf, cap, &len, valid_file, NULL);
    if (got == VV_SIDECAR_LOAD_BLOCKED) {
        HeapFree(GetProcessHeap(), 0, buf);
        return 0;
    }
    if (got == VV_SIDECAR_LOAD_VALID) {
        if (!bound_to(buf, world)) {
            /* Another village's statues: kept, never used here or overwritten. */
            if (!move_aside(path, ".another-village-")) {
                vv_sidecar_gate_block(&g_gate);
                HeapFree(GetProcessHeap(), 0, buf);
                return 0;
            }
        } else {
            int t = i32(buf, 36);
            if (!reserve(t)) {
                vv_sidecar_gate_block(&g_gate);
                HeapFree(GetProcessHeap(), 0, buf);
                return 0;
            }
            memcpy(g_t, buf + HEADER + (unsigned int)i32(buf, 32) * ROSTER_ROW, (size_t)t * ENTRY);
            g_n = t;
        }
    }
    HeapFree(GetProcessHeap(), 0, buf);
    g_slot = slot;
    return 1;
}

/* Write the store to the slot's file, bound to the records now in memory. */
static int write_store(int slot, unsigned char *world) {
    char path[MAX_PATH];
    unsigned char header[HEADER];
    unsigned char *roster;
    unsigned int rows = 0, hash;
    const void *parts[4];
    DWORD sizes[4];
    int i, ok;
    if (!store_path(slot, path)) {
        return 0;
    }
    if (g_slot != slot || lstrcmpiA(g_gate.path, path) != 0 || g_gate.state != VV_SIDECAR_SETTLED) {
        /* The store was not read from this slot's file (a new village, or
           another slot's): whatever file is there belongs to the village
           that was in this slot before.  It is moved aside, never replaced. */
        if (GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES && !move_aside(path, ".replaced-")) {
            return 0;
        }
        vv_sidecar_gate_bind(&g_gate, slot);
        lstrcpyA(g_gate.path, path);
        g_gate.state = VV_SIDECAR_SETTLED;
    }
    roster = (unsigned char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, RECORDS * ROSTER_ROW);
    if (roster == NULL) {
        return 0;
    }
    for (i = 0; i < RECORDS; ++i) {
        const unsigned char *r = record(world, i);
        unsigned char *row = roster + rows * ROSTER_ROW;
        if (r[R_IN_USE] == 0 || r[R_IS_TOTEM] != 0) {
            continue;
        }
        lstrcpynA((char *)row, (const char *)r + 0x564, NAME_CAP);
        put32(row, 24, i32(r, 0x548));
        put32(row, 28, i32(r, 0x54C));
        put32(row, 32, i32(r, 0x538));
        ++rows;
    }
    memset(header, 0, sizeof header);
    memcpy(header, MAGIC, 16);
    put32(header, 16, 1);
    put32(header, 20, GAME);
    put32(header, 24, slot);
    put32(header, 28, (int)ENTRY);
    put32(header, 32, (int)rows);
    put32(header, 36, g_n);
    hash = 2166136261u;
    {
        const unsigned char *spans[3];
        DWORD lens[3];
        int s;
        DWORD k;
        spans[0] = header; lens[0] = HEADER;
        spans[1] = roster; lens[1] = rows * ROSTER_ROW;
        spans[2] = (const unsigned char *)g_t; lens[2] = (DWORD)g_n * ENTRY;
        for (s = 0; s < 3; ++s) {
            for (k = 0; k < lens[s]; ++k) {
                hash = (hash ^ spans[s][k]) * 16777619u;
            }
        }
    }
    parts[0] = header; sizes[0] = HEADER;
    parts[1] = roster; sizes[1] = rows * ROSTER_ROW;
    parts[2] = g_t; sizes[2] = (DWORD)g_n * ENTRY;
    parts[3] = &hash; sizes[3] = 4;
    vv_ps_make_parents_a(path);
    ok = vv_sidecar_publish(&g_gate, path, parts, sizes, 4);
    HeapFree(GetProcessHeap(), 0, roster);
    if (ok) {
        g_slot = slot;
    }
    return ok;
}

/* ---- moving the statues out of the records -------------------------------- */
static void free_record(unsigned char *world, int i) {
    unsigned char *r = record(world, i);
    unsigned char *game = game_of(world);
    if (r[R_PICKED] != 0) {
        UNPICK_ALL(world, 0);                       /* as the burial does (0x46502D) */
    }
    r[R_IN_USE] = 0;
    r[R_IS_TOTEM] = 0;
    if (game != NULL && i32(game, G_SELECTED) == i) {
        put32(game, G_SELECTED, -1);
    }
}

static int migrate(unsigned char *world) {
    int i, k, moved = 0;
    for (i = 0; i < RECORDS; ++i) {
        unsigned char *r = record(world, i);
        unsigned char e[ENTRY];
        int dup = 0;
        if (r[R_IN_USE] == 0 || r[R_IS_TOTEM] == 0 || i32(r, R_HEALTH) > 0) {
            continue;                               /* not a statue: never touched */
        }
        pack(r, e);
        for (k = 0; k < g_n; ++k) {
            if (same_statue(g_t[k].e, e)) {
                dup = 1;
                break;
            }
        }
        if (!dup) {
            if (!reserve(g_n + 1)) {
                continue;                           /* no room: it stays a record */
            }
            memcpy(g_t[g_n].e, e, ENTRY);
            ++g_n;
        }
        free_record(world, i);
        ++moved;
    }
    return moved;
}

/* ---- the hooks: load, save, reset ----------------------------------------- */
static slot_fn g_load_original;
static slot_fn g_save_original;
static reset_fn g_reset_original;
static create_fn g_create_original;
static input_fn g_input_original;

static int village_slot(int slot) {
    if (slot >= 1 && slot <= 5) {
        return slot;
    }
    if (slot >= 21 && slot <= 25) {
        return slot - 20;
    }
    return 0;
}

static unsigned char __fastcall wrap_load(void *manager, int edx, int slot) {
    unsigned char ok = g_load_original(manager, edx, slot);
    int s = village_slot(slot);
    unsigned char *world;
    if (!ok || s == 0) {
        return ok;
    }
    world = world_of();
    if (world == NULL) {
        return ok;
    }
    __try {
        g_active = read_store(s, world);
        if (g_active) {
            (void)migrate(world);
        } else {
            clear_store();
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        clear_store();
        g_active = 0;
    }
    return ok;
}

static unsigned char __fastcall wrap_save(void *manager, int edx, int slot) {
    if (slot >= 1 && slot <= 5 && g_active) {
        unsigned char *world = world_of();
        int written = 0;
        if (world != NULL) {
            __try {
                written = write_store(slot, world);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
                written = 0;
            }
        }
        if (!written && g_n > 0) {
            return 0;          /* the statues would be in neither file */
        }
    }
    return g_save_original(manager, edx, slot);
}

static int __fastcall wrap_reset(void *manager, int edx, int arg) {
    clear_store();
    g_slot = 0;
    g_active = 1;
    return g_reset_original(manager, edx, arg);
}

/* ---- the totem maker ------------------------------------------------------ */
static void make_entry(const unsigned char *elder, unsigned char *e, unsigned int clock) {
    int age = i32(elder, 0x530);
    memset(e, 0, ENTRY);
    put32(e, E_TIME, (int)clock);                       /* +0x528 = the clock (0x44D461) */
    put32(e, E_AGE, age);                               /* +0x530, +0x534 (0x44D492) */
    put32(e, E_AGE2, age);
    put32(e, E_SEX, i32(elder, 0x538));
    put32(e, E_HEAD, i32(elder, 0x548));
    put32(e, E_BODY, i32(elder, 0x54C));
    put32(e, E_TYPE, i32(elder, 0x550));
    put32(e, E_LINEAGE, i32(elder, 0x554));
    e[E_IS_TOTEM] = 1;                                  /* 0x44D485 */
    put32(e, E_X, i32(elder, R_X));                     /* 0x44D28B */
    put32(e, E_Y, i32(elder, R_Y) + 10);                /* 0x44D277 */
    lstrcpynA((char *)e + E_NAME, (const char *)elder + 0x564, NAME_CAP + 1);
    lstrcpynA((char *)e + E_FATHER, (const char *)elder + 0x57D, 0x19);
    lstrcpynA((char *)e + E_MOTHER, (const char *)elder + 0x596, 0x19);
    memcpy(e + 0x8C, elder + 0x5B0, 16);                /* +0x5B0..+0x5BF parents' looks */
    memcpy(e + 0xCC, elder + 0x5F0, 0x1F0);             /* likes and dislikes (0x44D2F0) */
    memcpy(e + 0x2C0, elder + 0x7E4, 20);               /* the five skills (0x44D311) */
    e[E_FLAG] = 1;
}

static int __fastcall my_create(void *world_ptr, int edx, int elder_index) {
    unsigned char *world = (unsigned char *)world_ptr;
    unsigned char *game = game_of(world);
    unsigned char *elder = record(world, elder_index);
    if (!g_active || !reserve(g_n + 1)) {
        return g_create_original(world_ptr, edx, elder_index);
    }
    /* 0x44D19B..0x44D1EB: the first elder's time, once. */
    if (game[0x2E778] == 0) {
        unsigned int now, hours;
        game[0x2E778] = 1;
        now = GAME_CLOCK(game, 0);
        hours = (unsigned int)(((unsigned long long)(now - (unsigned int)i32(game, 0x2E4F8)) * 0x91A2B3C5ull) >> 43);
        put32(game, 0x2E538, (int)hours);
        if (hours == 0) {
            put32(game, 0x2E538, 1);
        }
    }
    /* 0x44D1F5..0x44D216: the first-elder message, once. */
    if (game[0x1FF] != 0) {
        game[0x1FF] = 0;
        MESSAGE(game, 0, 0x1CE, 1);
    }
    make_entry(elder, g_t[g_n].e, GAME_CLOCK(game, 0));
    ++g_n;
    elder[R_ELDER] = 1;                                  /* 0x44D4A2 */
    return -1;
}

/* ---- drawing -------------------------------------------------------------- */
static int *g_order;             /* store indexes by sort key */
static int g_order_cap, g_order_n, g_next;

static int key_of(int k) {
    return i32(g_t[k].e, E_Y) + 0x23;
}

static int cmp_keys(const void *a, const void *b) {
    int ka = key_of(*(const int *)a), kb = key_of(*(const int *)b);
    if (ka != kb) {
        return ka < kb ? -1 : 1;
    }
    return *(const int *)a - *(const int *)b;
}

static void place_of(int k, int *x, int *y) {
    if (g_dragging && k == g_pressed) {
        *x = g_drag_x;
        *y = g_drag_y;
    } else {
        *x = i32(g_t[k].e, E_X);
        *y = i32(g_t[k].e, E_Y);
    }
}

static void draw_one(unsigned char *world, int k) {
    unsigned char *game = game_of(world);
    void *renderer = *(void **)(world + W_RENDERER);
    int x, y;
    place_of(k, &x, &y);
    x -= i32(game, G_CAMX);
    y -= i32(game, G_CAMY);
    DRAW_SHADOW(renderer, 0, *(void **)(world + W_SHADOW), x - 0x11, y + 0x3B);
    DRAW_FRAME(renderer, 0, *(void **)(world + W_TOTEMS), x, y, i32(g_t[k].e, E_TYPE) % 8);
}

/* A record the draw order keeps in y order: in use, not held, alive or a
   totem record (0x44B14E..0x44B173). */
static int anchor_key(unsigned char *world, int position, int *key) {
    int i = i32(world + W_ORDER, (unsigned int)position * 4);
    const unsigned char *r;
    if (i < 0 || i >= RECORDS) {
        return 0;
    }
    r = record(world, i);
    if (r[R_IN_USE] == 0 || r[R_HELD] != 0 || (i32(r, R_HEALTH) <= 0 && r[R_IS_TOTEM] == 0)) {
        return 0;
    }
    *key = i32(r, R_Y) + (r[R_IS_TOTEM] ? 0x23 : 0);
    return 1;
}

static void __cdecl draw_begin(unsigned char *world) {
    unsigned char *game = game_of(world);
    int k;
    g_order_n = 0;
    g_next = 0;
    if (game != NULL && i32(game, G_SELECTED) != -1) {
        g_selected = -1;          /* the game picked a villager */
    }
    if (g_n > g_order_cap) {
        int *grown = g_order ? (int *)HeapReAlloc(GetProcessHeap(), 0, g_order, (SIZE_T)g_cap * sizeof(int))
                             : (int *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)g_cap * sizeof(int));
        if (grown == NULL) {
            return;
        }
        g_order = grown;
        g_order_cap = g_cap;
    }
    for (k = 0; k < g_n; ++k) {
        if (!(g_dragging && k == g_pressed)) {
            g_order[g_order_n++] = k;
        }
    }
    qsort(g_order, (size_t)g_order_n, sizeof(int), cmp_keys);
}

static void __cdecl draw_before(unsigned char *world, int position) {
    int key;
    if (g_next >= g_order_n || !anchor_key(world, position, &key)) {
        return;
    }
    while (g_next < g_order_n && key_of(g_order[g_next]) <= key) {
        draw_one(world, g_order[g_next++]);
    }
}

static void __cdecl draw_end(unsigned char *world) {
    while (g_next < g_order_n) {
        draw_one(world, g_order[g_next++]);
    }
    if (g_dragging && g_pressed >= 0 && g_pressed < g_n) {
        draw_one(world, g_pressed);
    }
}

static void __cdecl draw_map(unsigned char *world) {
    void *renderer = *(void **)(world + W_RENDERER);
    void *image = *(void **)(world + W_TOTEMS);
    int k;
    for (k = 0; k < g_n; ++k) {
        int x, y;
        place_of(k, &x, &y);
        DRAW_MAP(renderer, 0, image, x / 4 + 0xAF, (y - 0x41) / 4 + 0x29, i32(g_t[k].e, E_TYPE) % 8, 0x19, 1);
    }
}

/* Where store totem k is drawn: before the record at this draw position
   (RECORDS: after the last). */
static int drawn_before(unsigned char *world, int k) {
    int p, key, want = key_of(k);
    for (p = 0; p < RECORDS; ++p) {
        if (anchor_key(world, p, &key) && key >= want) {
            return p;
        }
    }
    return RECORDS;
}

/* ---- the click ------------------------------------------------------------ */
static int __fastcall my_hit(void *world_ptr, int edx, int mx, int my) {
    unsigned char *world = (unsigned char *)world_ptr;
    unsigned char *game;
    int r = HIT_TEST(world_ptr, edx, mx, my);
    int k, best = -1, best_key = 0, rpos = -1;
    g_hit_store = 0;
    forget_pick();
    game = game_of(world);
    if (game == NULL) {
        return r;
    }
    for (k = 0; k < g_n; ++k) {
        int x = i32(g_t[k].e, E_X) - i32(game, G_CAMX);
        int y = i32(g_t[k].e, E_Y) - i32(game, G_CAMY);
        if (mx >= x && mx <= x + 0x28 && my >= y && my <= y + 0x41
            && (best < 0 || key_of(k) >= best_key)) {
            best = k;
            best_key = key_of(k);
        }
    }
    if (best < 0) {
        return r;
    }
    if (r >= 0) {
        for (k = 0; k < RECORDS; ++k) {
            if (i32(world + W_ORDER, (unsigned int)k * 4) == r) {
                rpos = k;
            }
        }
        if (rpos >= 0 && drawn_before(world, best) <= rpos) {
            return r;                                   /* the record stands in front */
        }
        record(world, r)[R_PICKED] = 0;
    }
    g_selected = best;
    g_pressed = best;
    g_hit_store = 1;
    return -1;
}

/* The name panel: "<name>`s totem" for a picked store totem. */
static const char *__cdecl label_text(void) {
    if (g_selected < 0 || g_selected >= g_n) {
        return (const char *)(uintptr_t)NO_SELECTION_VA;
    }
    lstrcpynA(g_label, (const char *)g_t[g_selected].e + E_NAME, NAME_CAP + 1);
    lstrcatA(g_label, (const char *)(uintptr_t)LABEL_SUFFIX_VA);
    return g_label;
}

/* ---- the drag ------------------------------------------------------------- */
static int trunc_div(int a, int b) {
    return a / b;                                       /* C truncates as the game's code does */
}

static void dust(unsigned char *ui, int x, int y, int with_sound) {
    int n;
    for (n = 0; n < 4; ++n) {
        int dy = RAND(0xF);
        int dx = RAND(0x23);
        int which = RAND(2);
        PARTICLES(*(void **)(ui + U_PARTICLES), 0, 6, dx + x - 0xA, dy + y + 0x28, 1, 0, 0, which);
        if (with_sound) {
            SOUND_AT(*(void **)(ui + U_SOUND), 0, 0x15, 0.2f);
        }
    }
}

static int terrain(unsigned char *ui, int x, int y) {
    return TERRAIN_AT(*(void **)(ui + U_TERRAIN), 0, x + 0x14, y + 0x41);
}

static void drag_to(unsigned char *ui, int mx, int my) {
    unsigned char *game = *(unsigned char **)(ui + U_GAME);
    int lo, hi, ex, ey;
    /* 0x431657..0x431697 */
    lo = i32(ui, U_VIEW_L) + 0x14;
    hi = i32(ui, U_VIEW_R) - 0x14;
    if (mx < lo) {
        mx = lo;
    } else if (mx > hi) {
        mx = hi;
    }
    lo = i32(ui, U_VIEW_T) + 0x14;
    hi = i32(ui, U_VIEW_B) - 0x3C;
    if (my < lo) {
        my = lo;
    } else if (my > hi) {
        my = hi;
    }
    /* 0x449220 with (mx - 5, my + 0xD) */
    g_drag_x = i32(game, G_CAMX) + (mx - 5) - 0x14;
    g_drag_y = i32(game, G_CAMY) + (my + 0xD) - 0x20;
    /* 0x4316DD..0x43174D: the edge scroll */
    ex = trunc_div(mx - 0x206, 40);
    ey = trunc_div(my - 0xF7, 40);
    put32(ui, U_SCROLL_X, abs(ex) < 3 ? 0 : ex);
    put32(ui, U_SCROLL_Y, abs(ey) < 3 ? 0 : ey);
    put32(ui, U_HOLD_X, mx);
    put32(ui, U_HOLD_Y, my);
    put32(ui, U_MOUSE_X, mx);
    put32(ui, U_MOUSE_Y, my);
}

static void drop(unsigned char *ui) {
    unsigned char *game = *(unsigned char **)(ui + U_GAME);
    unsigned char *e = g_t[g_pressed].e;
    int x = g_drag_x, y = g_drag_y, t, n;
    /* 0x43095F..0x4309A8: kept on the map */
    if (x < 1) {
        x = 2;
    } else if (x > 0x64A) {
        x = 0x649;
    }
    if (y < 1) {
        y = 2;
    } else if (y > 0x640) {
        y = 0x63F;
    }
    /* 0x4309D1..0x430A72: dust and its sound where it lands */
    t = terrain(ui, x, y);
    if (t != 0x18 && t != 0x19) {
        dust(ui, x, y, 1);
    }
    /* 0x430AC5 -> 0x42FB20 -> 0x430382: a totem set on the puzzle's spot */
    if (terrain(ui, x, y) == 0x42) {
        int s;
        SOUND(*(void **)(ui + U_SOUND), 0, 0x56);
        put32(game, G_PUZZLE, 1);
        y -= 0x32;
        for (s = 0; s < 0x1E; ++s) {
            int px = RAND(0x1E);
            int py = RAND(0x1E);
            SPARKLES(*(void **)(ui + U_PARTICLES), 0, 5, py + 0x55C, px + 0x5BA);
        }
        PUZZLE_SOLVED(*(void **)(ui + U_PUZZLE), 0);
    }
    /* 0x42D140: off ground a totem cannot stand on (terrain 1..0x18) */
    for (n = 0; n < 4096; ++n) {
        t = terrain(ui, x, y);
        if (t < 1 || t > 0x18) {
            break;
        }
        x += x < 0x31B ? 2 : -2;
        y += y < 0x5DC ? 2 : -2;
    }
    /* 0x449260: the totem's home */
    put32(e, E_X, x);
    put32(e, E_Y, y);
}

static unsigned char __fastcall wrap_input(void *ui_ptr, int edx, int event, int x, int y) {
    unsigned char *ui = (unsigned char *)ui_ptr;
    if (g_pressed >= 0 && g_pressed < g_n) {
        if (event == 1) {
            if (!g_dragging && (abs(x - i32(ui, U_PRESS_X)) >= 5 || abs(y - i32(ui, U_PRESS_Y)) >= 5)) {
                int px = i32(g_t[g_pressed].e, E_X), py = i32(g_t[g_pressed].e, E_Y);
                int t = terrain(ui, px, py);
                g_dragging = 1;
                g_drag_x = px;
                g_drag_y = py;
                if (t != 0x18 && t != 0x19) {
                    dust(ui, px, py, 0);                /* 0x431581..0x431642 */
                }
            }
            if (g_dragging) {
                drag_to(ui, x, y);
                return 1;
            }
        } else if (event == 3) {
            if (g_dragging) {
                drop(ui);
            }
            g_pressed = -1;
            g_dragging = 0;
        }
    }
    return g_input_original(ui_ptr, edx, event, x, y);
}

/* ---- naked stubs ---------------------------------------------------------- */
static void *g_back_draw_loop;      /* 0x445C25 */
static void *g_back_draw_done;      /* 0x4478DA */
static void *g_back_hit_after;      /* 0x43107F */
static void *g_click_done;          /* 0x431854 */
static void *g_back_label;          /* 0x429B31 */
static void *g_back_cap1_go;        /* 0x44D4DA */
static void *g_back_cap1_stop;      /* 0x44D57C */
static void *g_back_cap2_go;        /* 0x44D551 */
static void *g_back_cap2_stop;      /* 0x44D565 */

static __declspec(naked) void stub_draw_loop(void) {
    __asm {
        pushad
        push edi
        push esi
        call draw_before
        add esp, 8
        popad
        mov ecx, dword ptr [esi + edi * 4 + 0xE57090]
        jmp dword ptr [g_back_draw_loop]
    }
}

static __declspec(naked) void stub_draw_head(void) {
    __asm {
        pushad
        push esi
        call draw_begin
        add esp, 4
        popad
        xor edi, edi
        jmp stub_draw_loop
    }
}

static __declspec(naked) void stub_draw_tail(void) {
    __asm {
        inc edi
        cmp edi, 0x100
        jl stub_draw_loop
        pushad
        push esi
        call draw_end
        add esp, 4
        popad
        jmp dword ptr [g_back_draw_done]
    }
}

static __declspec(naked) void stub_map(void) {
    __asm {
        pushad
        push esi
        call draw_map
        add esp, 4
        popad
        pop edi
        pop esi
        pop ebp
        pop ebx
        ret
    }
}

static __declspec(naked) void stub_hit_after(void) {
    __asm {
        mov ecx, dword ptr [esi + 0x10]
        mov dword ptr [ecx + 0x304F0], eax
        cmp byte ptr [g_hit_store], 0
        jne store_totem
        jmp dword ptr [g_back_hit_after]
    store_totem:
        mov byte ptr [g_hit_store], 0
        mov byte ptr [esi + 0x1D0], 0
        mov byte ptr [esi + 0x1E0], 0
        jmp dword ptr [g_click_done]
    }
}

static __declspec(naked) void stub_label(void) {
    __asm {
        call label_text
        push eax
        jmp dword ptr [g_back_label]
    }
}

static __declspec(naked) void stub_cap1(void) {
    __asm {
        cmp dword ptr [g_active], 0
        jne go
        cmp eax, 0x32
        jl go
        jmp dword ptr [g_back_cap1_stop]
    go:
        jmp dword ptr [g_back_cap1_go]
    }
}

static __declspec(naked) void stub_cap2(void) {
    __asm {
        cmp dword ptr [g_active], 0
        jne go
        cmp eax, 0x32
        jl go
        jmp dword ptr [g_back_cap2_stop]
    go:
        jmp dword ptr [g_back_cap2_go]
    }
}

/* ---- installing ----------------------------------------------------------- */
typedef struct {
    unsigned int va;
    unsigned char stock[13];
    unsigned int len;           /* bytes replaced */
} site_t;

enum {
    S_LOAD, S_SAVE, S_RESET, S_CREATE, S_CAP1, S_CAP2, S_DRAW_HEAD, S_DRAW_TAIL, S_MAP,
    S_HIT, S_HIT_AFTER, S_INPUT, S_LABEL, S_COUNT
};

static const site_t SITES[S_COUNT] = {
    { 0x4249A0u, { 0xB8, 0x34, 0x04, 0x03, 0x00 }, 5 },
    { 0x424BA0u, { 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x0C }, 6 },
    { 0x424C80u, { 0x51, 0x53, 0x55, 0x56, 0x57, 0x8B, 0xE9 }, 7 },
    { 0x44D190u, { 0x51, 0x53, 0x55, 0x8B, 0xE9 }, 5 },
    { 0x44D4D1u, { 0x83, 0xF8, 0x32, 0x0F, 0x8D, 0xA2, 0x00, 0x00, 0x00 }, 9 },
    { 0x44D54Cu, { 0x83, 0xF8, 0x32, 0x7D, 0x14 }, 5 },
    { 0x445C1Cu, { 0x33, 0xFF, 0x8B, 0x8C, 0xBE, 0x90, 0x70, 0xE5, 0x00 }, 9 },
    { 0x4478CDu, { 0x47, 0x81, 0xFF, 0x00, 0x01, 0x00, 0x00, 0x0F, 0x8C, 0x44, 0xE3, 0xFF, 0xFF }, 13 },
    { 0x4490BBu, { 0x5F, 0x5E, 0x5D, 0x5B, 0xC3 }, 5 },
    { 0x431071u, { 0xE8, 0x0A, 0xC5, 0x01, 0x00 }, 5 },
    { 0x431076u, { 0x8B, 0x4E, 0x10, 0x89, 0x81, 0xF0, 0x04, 0x03, 0x00 }, 9 },
    { 0x4308D0u, { 0x8B, 0x44, 0x24, 0x04, 0x83, 0xEC, 0x08 }, 7 },
    { 0x429A83u, { 0x68, 0x3C, 0x44, 0x47, 0x00 }, 5 },
};

static int readable(const void *at, size_t size) {
    MEMORY_BASIC_INFORMATION info;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info) || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        return 0;
    }
    return (const unsigned char *)at + size <= (const unsigned char *)info.BaseAddress + info.RegionSize;
}

static int site_is_stock(const site_t *s) {
    const unsigned char *at = (const unsigned char *)(uintptr_t)s->va;
    return readable(at, s->len) && memcmp(at, s->stock, s->len) == 0;
}

static void put_rel(unsigned char *out, unsigned char op, unsigned int from, const void *to) {
    unsigned int rel = (unsigned int)(uintptr_t)to - (from + 5);
    out[0] = op;
    memcpy(out + 1, &rel, 4);
}

static int write_code(unsigned int va, const unsigned char *bytes, unsigned int len) {
    DWORD old;
    unsigned char *at = (unsigned char *)(uintptr_t)va;
    if (!VirtualProtect(at, len, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, len);
    VirtualProtect(at, len, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, len);
    return 1;
}

/* The trampolines: each prologue the wrappers call through, then a jump back. */
static unsigned char *g_tramps;

static void *tramp(int index, const site_t *s) {
    unsigned char *t = g_tramps + index * 32;
    memcpy(t, s->stock, s->len);
    put_rel(t + s->len, 0xE9, (unsigned int)(uintptr_t)(t + s->len), (const void *)(uintptr_t)(s->va + s->len));
    return t;
}

static int install(void) {
    static const unsigned char *const label_text_at = (const unsigned char *)(uintptr_t)LABEL_SUFFIX_VA;
    unsigned char bytes[16];
    DWORD old;
    int i;
    if (g_installed) {
        return 1;
    }
    for (i = 0; i < S_COUNT; ++i) {
        if (!site_is_stock(&SITES[i])) {
            return 0;
        }
    }
    if (!readable(label_text_at, sizeof LABEL_SUFFIX_AT)
        || memcmp(label_text_at, LABEL_SUFFIX_AT, sizeof LABEL_SUFFIX_AT) != 0) {
        return 0;
    }
    g_tramps = (unsigned char *)VirtualAlloc(NULL, 4096, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (g_tramps == NULL) {
        return 0;
    }
    g_load_original = (slot_fn)tramp(0, &SITES[S_LOAD]);
    g_save_original = (slot_fn)tramp(1, &SITES[S_SAVE]);
    g_reset_original = (reset_fn)tramp(2, &SITES[S_RESET]);
    g_create_original = (create_fn)tramp(3, &SITES[S_CREATE]);
    g_input_original = (input_fn)tramp(4, &SITES[S_INPUT]);
    if (!VirtualProtect(g_tramps, 4096, PAGE_EXECUTE_READ, &old)) {
        VirtualFree(g_tramps, 0, MEM_RELEASE);
        g_tramps = NULL;
        return 0;
    }
    FlushInstructionCache(GetCurrentProcess(), g_tramps, 4096);
    g_back_draw_loop = (void *)(uintptr_t)0x445C25u;
    g_back_draw_done = (void *)(uintptr_t)0x4478DAu;
    g_back_hit_after = (void *)(uintptr_t)0x43107Fu;
    g_click_done = (void *)(uintptr_t)0x431854u;
    g_back_label = (void *)(uintptr_t)0x429B31u;
    g_back_cap1_go = (void *)(uintptr_t)0x44D4DAu;
    g_back_cap1_stop = (void *)(uintptr_t)0x44D57Cu;
    g_back_cap2_go = (void *)(uintptr_t)0x44D551u;
    g_back_cap2_stop = (void *)(uintptr_t)0x44D565u;
    for (i = 0; i < S_COUNT; ++i) {
        const site_t *s = &SITES[i];
        const void *to;
        unsigned char op = 0xE9;
        switch (i) {
        case S_LOAD: to = (const void *)wrap_load; break;
        case S_SAVE: to = (const void *)wrap_save; break;
        case S_RESET: to = (const void *)wrap_reset; break;
        case S_CREATE: to = (const void *)my_create; break;
        case S_CAP1: to = (const void *)stub_cap1; break;
        case S_CAP2: to = (const void *)stub_cap2; break;
        case S_DRAW_HEAD: to = (const void *)stub_draw_head; break;
        case S_DRAW_TAIL: to = (const void *)stub_draw_tail; break;
        case S_MAP: to = (const void *)stub_map; break;
        case S_HIT: to = (const void *)my_hit; op = 0xE8; break;
        case S_HIT_AFTER: to = (const void *)stub_hit_after; break;
        case S_INPUT: to = (const void *)wrap_input; break;
        default: to = (const void *)stub_label; break;
        }
        memset(bytes, 0x90, sizeof bytes);
        put_rel(bytes, op, s->va, to);
        if (!write_code(s->va, bytes, s->len)) {
            return 0;            /* VirtualProtect refused: cannot happen on the game's own code */
        }
    }
    g_installed = 1;
    return 1;
}

/* ---- exports -------------------------------------------------------------- */
__declspec(dllexport) int __stdcall VvfpTotemsActive(void) {
    return g_installed && g_active;
}

__declspec(dllexport) int __stdcall VvfpTotemCount(void) {
    return g_installed ? g_n : 0;
}

/* The one store totem made for the elder record `r` (story_c2.inc
   c2_totem_of's test: the name, sex, family and both parents' names): its
   index, -1 none, -2 more than one. */
static int totem_of(const unsigned char *r) {
    int k, found = -1;
    if (r == NULL) {
        return -1;
    }
    for (k = 0; k < g_n; ++k) {
        const unsigned char *e = g_t[k].e;
        if (strncmp((const char *)e + E_NAME, (const char *)r + 0x564, NAME_CAP) != 0
            || i32(e, E_SEX) != i32(r, 0x538) || i32(e, E_LINEAGE) != i32(r, 0x554)
            || strncmp((const char *)e + E_FATHER, (const char *)r + 0x57D, 0x19) != 0
            || strncmp((const char *)e + E_MOTHER, (const char *)r + 0x596, 0x19) != 0) {
            continue;
        }
        if (found >= 0) {
            return -2;
        }
        found = k;
    }
    return found;
}

/* The face (0..7) of the elder's store totem; -1 none, -2 two agree. */
__declspec(dllexport) int __stdcall VvfpTotemFaceOf(const unsigned char *elder) {
    int k;
    if (!g_installed) {
        return -1;
    }
    k = totem_of(elder);
    return k < 0 ? k : i32(g_t[k].e, E_TYPE) % 8;
}

/* Give the elder's store totem face 0..7, keeping its Totem Type in the
   game's 1..123 (story_c2.inc c2_set_status). */
__declspec(dllexport) int __stdcall VvfpTotemSetFace(const unsigned char *elder, int face) {
    int k, value;
    if (!g_installed || face < 0 || face > 7) {
        return 0;
    }
    k = totem_of(elder);
    if (k < 0) {
        return 0;
    }
    value = i32(g_t[k].e, E_TYPE);
    value = value - (value % 8 + 8) % 8 + face;
    while (value < 1) {
        value += 8;
    }
    while (value > 123) {
        value -= 8;
    }
    put32(g_t[k].e, E_TYPE, value);
    return 1;
}

/* Called once by "VVFP Startup.dll" as the game opens. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (game == GAME) {
        (void)install();
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
