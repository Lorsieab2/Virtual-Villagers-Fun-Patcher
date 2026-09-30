/* Exercise the statistics store (statistics_store.c) against real files.
 *
 * Built and run by scripts/build_statistics_store_harness.ps1 as a 32-bit
 * console program, like the companion itself. Every property checked here is
 * about bytes in files on a real disk and bytes in the game's memory, so it is
 * RUN rather than read: a fake manager and a fake image stand in for the game,
 * a pending bit or count is set exactly where the executable hook sets it,
 * and vvs_flush -- the companion's pre-save step -- is called as the save
 * wrapper calls it. The files go to a throwaway folder under %TEMP%.
 *
 * Prints "== N failure(s) ==" and exits non-zero on any failure.
 */
#define _CRT_SECURE_NO_WARNINGS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

#include "statistics_store.h"

static int failures = 0;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

/* ------------------------------------------------------------ fixtures */

#define MODULE_BYTES 0x300000u
#define MANAGER_BYTES 0x40000u

static unsigned char *g_module;
static unsigned char *g_manager;
static wchar_t g_folder[MAX_PATH];
static wchar_t g_counters[MAX_PATH];
static wchar_t g_stews[MAX_PATH];

/* Per-game facts the hooks and the store agree on (build_statistics_features
   and statistics_store.c). */
typedef struct {
    int game;
    unsigned int live_rva;      /* 0 = manager block */
    unsigned int saved_offset;
    unsigned int stew_bits;     /* offset in the block, 0 = no stews */
    int herbs;
    int first;
    int water;
} game_facts;

static const game_facts FACTS[5] = {
    { 1, 0, 0, 0, 0, 0, 0 },
    { 2, 0, 0, 0x2E5E8u, 6, 0x30, 0 },
    { 3, 0x1824A0u, 0x4ECu, 0x58u, 7, 0x1F, 0 },
    { 4, 0xD6DE0u, 0x850u, 0x60u, 4, 0x1F, 1 },
    { 5, 0x11D358u, 0x7B4u, 0, 0, 0, 0 },
};

static unsigned char *block_of(int game) {
    const game_facts *f = &FACTS[game - 1];
    return f->live_rva ? g_module + f->live_rva : g_manager;
}

static unsigned char *saved_of(int game) {
    const game_facts *f = &FACTS[game - 1];
    return f->live_rva ? g_manager + f->saved_offset : NULL;
}

/* A fresh process: new, zeroed game memory. Files on disk survive. */
static void restart(void) {
    memset(g_module, 0, MODULE_BYTES);
    memset(g_manager, 0, MANAGER_BYTES);
}

static vvs_context context_for(int game) {
    vvs_context c;
    c.game_id = game;
    c.manager = g_manager;
    c.module = g_module;
    _snwprintf_s(g_counters, MAX_PATH, _TRUNCATE, L"%ls\\counters_%d.dat", g_folder, game);
    _snwprintf_s(g_stews, MAX_PATH, _TRUNCATE, L"%ls\\stews_%d.dat", g_folder, game);
    c.counters_path = g_counters;
    c.stews_path = g_stews;
    return c;
}

static void remove_files(int game) {
    wchar_t path[MAX_PATH + 32];
    int i;
    context_for(game);
    DeleteFileW(g_counters);
    DeleteFileW(g_stews);
    for (i = 1; i < 5; ++i) {
        if (i == 1) {
            _snwprintf_s(path, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable", g_counters);
            DeleteFileW(path);
            _snwprintf_s(path, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable", g_stews);
            DeleteFileW(path);
        } else {
            _snwprintf_s(path, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable-%d", g_counters, i);
            DeleteFileW(path);
            _snwprintf_s(path, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable-%d", g_stews, i);
            DeleteFileW(path);
        }
    }
}

/* Exactly what the executable hook does: bts the ORDERED triple index. */
static void hook_records(int game, int h1, int h2, int h3, int salt) {
    const game_facts *f = &FACTS[game - 1];
    unsigned char *bits = block_of(game) + f->stew_bits;
    int n = f->herbs;
    int index = ((h1 - f->first) * n + (h2 - f->first)) * n + (h3 - f->first);
    if (f->water) {
        index = index * 2 + (salt ? 1 : 0);
    }
    bits[index >> 3] |= (unsigned char)(1u << (index & 7));
}

static int pending_bits_zero(int game) {
    const game_facts *f = &FACTS[game - 1];
    int bytes = ((f->herbs * f->herbs * f->herbs * (f->water ? 2 : 1)) + 31) / 32 * 4;
    int i;
    unsigned char *saved = saved_of(game);
    for (i = 0; i < bytes; ++i) {
        if (block_of(game)[f->stew_bits + i] != 0) return 0;
        if (saved != NULL && saved[f->stew_bits + i] != 0) return 0;
    }
    return 1;
}

static int stews(int game) {
    vvs_context c = context_for(game);
    int value = -1;
    vvs_stews_value(&c, &value);
    return value;
}

static int flush(int game) {
    vvs_context c = context_for(game);
    return vvs_flush(&c);
}

static int read_text(const wchar_t *path, char *out, int size) {
    HANDLE f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD got = 0;
    if (f == INVALID_HANDLE_VALUE) {
        out[0] = '\0';
        return 0;
    }
    ReadFile(f, out, (DWORD)size - 1, &got, NULL);
    CloseHandle(f);
    out[got] = '\0';
    return 1;
}

static void write_text(const wchar_t *path, const char *text) {
    HANDLE f = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD written = 0;
    if (f != INVALID_HANDLE_VALUE) {
        WriteFile(f, text, (DWORD)strlen(text), &written, NULL);
        CloseHandle(f);
    }
}

static int exists(const wchar_t *path) {
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

static int count_lines_with(const char *text, const char *needle) {
    int n = 0;
    const char *p = text;
    while ((p = strstr(p, needle)) != NULL) {
        ++n;
        p += strlen(needle);
    }
    return n;
}

/* ------------------------------------------------------------- stews */

static void stew_identity_properties(int game) {
    const game_facts *f = &FACTS[game - 1];
    int n = f->herbs;
    int seen[128];
    int distinct = 0;
    int a, b, c, s;
    int all_orders_agree = 1;
    int in_range = 1;
    char what[128];
    memset(seen, 0, sizeof seen);
    for (s = 0; s <= f->water; ++s) {
        for (a = 0; a < n; ++a) {
            for (b = 0; b < n; ++b) {
                for (c = 0; c < n; ++c) {
                    int x = f->first;
                    int id = vvs_stew_identity(game, a + x, b + x, c + x, s);
                    int perms[6];
                    int p;
                    perms[0] = vvs_stew_identity(game, a + x, c + x, b + x, s);
                    perms[1] = vvs_stew_identity(game, b + x, a + x, c + x, s);
                    perms[2] = vvs_stew_identity(game, b + x, c + x, a + x, s);
                    perms[3] = vvs_stew_identity(game, c + x, a + x, b + x, s);
                    perms[4] = vvs_stew_identity(game, c + x, b + x, a + x, s);
                    perms[5] = id;
                    for (p = 0; p < 6; ++p) {
                        if (perms[p] != id) all_orders_agree = 0;
                    }
                    if (id < 0 || id >= 128) {
                        in_range = 0;
                        continue;
                    }
                    if (!seen[id]) {
                        seen[id] = 1;
                        ++distinct;
                    }
                }
            }
        }
    }
    sprintf(what, "VV%d: every order of the same herbs is one identity (Test F)", game);
    check(all_orders_agree, what);
    sprintf(what, "VV%d: every identity is in range", game);
    check(in_range, what);
    sprintf(what, "VV%d: distinct multisets are distinct identities (%d)", game, distinct);
    check(distinct == (n + 2) * (n + 1) * n / 6 * (f->water ? 2 : 1), what);
    sprintf(what, "VV%d: a herb outside the game's set has no identity", game);
    check(vvs_stew_identity(game, f->first - 1, f->first, f->first, 0) == -1
          && vvs_stew_identity(game, f->first + n, f->first, f->first, 0) == -1, what);
}

static void stew_regression(int game) {
    const game_facts *f = &FACTS[game - 1];
    int x = f->first;
    char text[8192];
    char what[160];
    int before;

    printf("VV%d stews\n", game);
    remove_files(game);
    restart();
    stew_identity_properties(game);

    sprintf(what, "VV%d: missing file is an empty history", game);
    check(stews(game) == 0 && vvs_probe_file(g_stews, game, 1) == VVS_FILE_MISSING, what);

    /* Test A: first discovery. */
    hook_records(game, x, x + 1, x + 2, 0);
    sprintf(what, "VV%d A: a pending discovery counts before the save", game);
    check(stews(game) == 1, what);
    check(flush(game) & 2, "flush writes the stew file");
    read_text(g_stews, text, sizeof text);
    sprintf(what, "VV%d A: .dat holds recipe A, count 1", game);
    check(stews(game) == 1 && count_lines_with(text, "stew=") == 1, what);
    sprintf(what, "VV%d A: pending bits zeroed in the live block and the save buffer", game);
    check(pending_bits_zero(game), what);

    /* Test B: the same recipe again, in another order (Test F too). */
    hook_records(game, x + 2, x, x + 1, 0);
    flush(game);
    read_text(g_stews, text, sizeof text);
    sprintf(what, "VV%d B: duplicate (reordered) recipe is +0, stored once", game);
    check(stews(game) == 1 && count_lines_with(text, "stew=") == 1, what);

    /* Test C: a second recipe. */
    hook_records(game, x, x, x, 0);
    flush(game);
    read_text(g_stews, text, sizeof text);
    sprintf(what, "VV%d C: second recipe is +1, .dat holds A and B", game);
    check(stews(game) == 2 && count_lines_with(text, "stew=") == 2, what);

    /* Test D: restart -- fresh process memory, the .dat re-read. */
    restart();
    sprintf(what, "VV%d D: after a restart the count is re-read from the .dat", game);
    check(stews(game) == 2, what);
    hook_records(game, x + 1, x + 2, x, 0);
    flush(game);
    sprintf(what, "VV%d D: recipe A again after the restart is +0", game);
    check(stews(game) == 2, what);

    /* Test E: a new recipe after the restart. */
    hook_records(game, x + 1, x + 1, x, 0);
    flush(game);
    read_text(g_stews, text, sizeof text);
    sprintf(what, "VV%d E: new recipe after the restart is +1, .dat holds A, B, C", game);
    check(stews(game) == 3 && count_lines_with(text, "stew=") == 3, what);

    if (f->water) {
        /* Test G: the same herbs with fresh and with salt water. */
        before = stews(game);
        hook_records(game, x + 3, x + 3, x + 2, 0);
        hook_records(game, x + 2, x + 3, x + 3, 1);
        flush(game);
        read_text(g_stews, text, sizeof text);
        check(stews(game) == before + 2,
              "VV4 G: fresh and salt versions of one herb set are two identities");
        check(strstr(text, "herbs=21,22,22 water=fresh") != NULL
              && strstr(text, "herbs=21,22,22 water=salt") != NULL,
              "VV4 G: both are stored distinctly in the .dat");
    }

    /* Union: a valid file with identities the memory never saw is kept. */
    {
        char valid[256];
        sprintf(valid, "VVFP STEW DISCOVERIES v1 game=%d\n", game);
        write_text(g_stews, valid);
        restart();
        hook_records(game, x, x, x + 1, 0);
        flush(game);
        hook_records(game, x + 1, x + 1, x + 1, 0);
        flush(game);
        read_text(g_stews, text, sizeof text);
        sprintf(what, "VV%d: each flush is the union; no identity is dropped", game);
        check(count_lines_with(text, "stew=") == 2 && stews(game) == 2, what);
    }

    /* No temporary left behind by the atomic replace. */
    {
        wchar_t tmp[MAX_PATH + 8];
        _snwprintf_s(tmp, MAX_PATH + 8, _TRUNCATE, L"%ls.tmp", g_stews);
        sprintf(what, "VV%d: the atomic replace leaves no .tmp", game);
        check(!exists(tmp), what);
    }

    /* Corrupt file: kept (renamed aside), nothing invented. */
    {
        wchar_t aside[MAX_PATH + 32];
        char kept[256];
        write_text(g_stews, "garbage that is not a stew file\n");
        restart();
        sprintf(what, "VV%d: a corrupt file reads as corrupt", game);
        check(vvs_probe_file(g_stews, game, 1) == VVS_FILE_CORRUPT, what);
        sprintf(what, "VV%d: a corrupt file invents no discoveries", game);
        check(stews(game) == 0, what);
        hook_records(game, x, x + 1, x + 1, 0);
        flush(game);
        _snwprintf_s(aside, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable", g_stews);
        read_text(aside, kept, sizeof kept);
        sprintf(what, "VV%d: the corrupt file is kept, byte for byte, aside", game);
        check(strcmp(kept, "garbage that is not a stew file\n") == 0, what);
        read_text(g_stews, text, sizeof text);
        sprintf(what, "VV%d: the new file holds only the proven discovery", game);
        check(count_lines_with(text, "stew=") == 1 && stews(game) == 1, what);
    }

    /* Another game's file and another version are not this game's history. */
    {
        char other[256];
        wchar_t aside[MAX_PATH + 32];
        sprintf(other, "VVFP STEW DISCOVERIES v1 game=%d\nstew=0 herbs=%02X,%02X,%02X\n",
                game == 2 ? 3 : 2, game == 2 ? 0x1F : 0x30, game == 2 ? 0x1F : 0x30,
                game == 2 ? 0x1F : 0x30);
        remove_files(game);
        write_text(g_stews, other);
        restart();
        sprintf(what, "VV%d: another game's file is refused and invents nothing", game);
        check(vvs_probe_file(g_stews, game, 1) == VVS_FILE_CORRUPT && stews(game) == 0, what);
        flush(game);
        _snwprintf_s(aside, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable", g_stews);
        sprintf(what, "VV%d: another game's file is set aside, not destroyed", game);
        check(exists(aside), what);
        sprintf(other, "VVFP STEW DISCOVERIES v2 game=%d\n", game);
        write_text(g_stews, other);
        sprintf(what, "VV%d: another version is refused", game);
        check(vvs_probe_file(g_stews, game, 1) == VVS_FILE_CORRUPT, what);
        /* A second unreadable file does not overwrite the first aside. */
        flush(game);
        _snwprintf_s(aside, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable-2", g_stews);
        sprintf(what, "VV%d: a second aside does not overwrite the first", game);
        check(exists(aside), what);
    }

    /* A line whose herbs disagree with its identity is corrupt, not trusted. */
    {
        char bad[256];
        sprintf(bad, "VVFP STEW DISCOVERIES v1 game=%d\nstew=0 herbs=%02X,%02X,%02X%s\n",
                game, x, x, x + 1, f->water ? " water=fresh" : "");
        write_text(g_stews, bad);
        sprintf(what, "VV%d: a line inconsistent with its identity is corrupt", game);
        check(vvs_probe_file(g_stews, game, 1) == VVS_FILE_CORRUPT, what);
        sprintf(bad, "VVFP STEW DISCOVERIES v1 game=%d\nstew=0 herbs=%02X,%02X,%02X%s\n"
                "stew=0 herbs=%02X,%02X,%02X%s\n",
                game, x, x, x, f->water ? " water=fresh" : "",
                x, x, x, f->water ? " water=fresh" : "");
        write_text(g_stews, bad);
        sprintf(what, "VV%d: a duplicated identity is corrupt", game);
        check(vvs_probe_file(g_stews, game, 1) == VVS_FILE_CORRUPT, what);
    }

    /* A file that cannot be read (held open without sharing) is not replaced,
       and the pending discovery stays pending -- in memory and in the save. */
    {
        char valid[256];
        HANDLE lock;
        sprintf(valid, "VVFP STEW DISCOVERIES v1 game=%d\n", game);
        remove_files(game);
        write_text(g_stews, valid);
        restart();
        hook_records(game, x + 1, x + 1, x + 2, 0);
        lock = CreateFileW(g_stews, GENERIC_READ, 0, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
        sprintf(what, "VV%d: an unreadable file is left alone and nothing is zeroed", game);
        check(lock != INVALID_HANDLE_VALUE && !(flush(game) & 2) && !pending_bits_zero(game), what);
        CloseHandle(lock);
        flush(game);
        sprintf(what, "VV%d: once readable again, the held discovery is recorded", game);
        check(stews(game) == 1 && pending_bits_zero(game), what);
    }

    /* Every ordered triple the hook can record lands on its multiset. */
    {
        int n = f->herbs;
        int a, b, c, s;
        int ok = 1;
        for (s = 0; s <= f->water; ++s) {
            for (a = 0; a < n && ok; ++a) {
                for (b = 0; b < n && ok; ++b) {
                    for (c = 0; c < n && ok; ++c) {
                        remove_files(game);
                        restart();
                        hook_records(game, a + x, b + x, c + x, s);
                        flush(game);
                        read_text(g_stews, text, sizeof text);
                        {
                            int v[3];
                            int t;
                            char want[96];
                            v[0] = a; v[1] = b; v[2] = c;
                            if (v[0] > v[1]) { t = v[0]; v[0] = v[1]; v[1] = t; }
                            if (v[1] > v[2]) { t = v[1]; v[1] = v[2]; v[2] = t; }
                            if (v[0] > v[1]) { t = v[0]; v[0] = v[1]; v[1] = t; }
                            sprintf(want, "stew=%d herbs=%02X,%02X,%02X%s\n",
                                    vvs_stew_identity(game, a + x, b + x, c + x, s),
                                    v[0] + x, v[1] + x, v[2] + x,
                                    f->water ? (s ? " water=salt" : " water=fresh") : "");
                            if (strstr(text, want) == NULL
                                || count_lines_with(text, "stew=") != 1) {
                                ok = 0;
                                printf("    mismatch for %d,%d,%d,%d:\n%s", a, b, c, s, text);
                            }
                        }
                    }
                }
            }
        }
        sprintf(what, "VV%d: every ordered triple is stored as its sorted multiset", game);
        check(ok, what);
    }
    remove_files(game);
}

/* ------------------------------------------------------------ counters */

typedef struct {
    int game;
    int kind;
    const char *key;
    unsigned int pending;
    unsigned int frozen;
    unsigned int marker;
} counter_facts;

static const counter_facts COUNTERS[] = {
    { 1, VVS_BURIED, "villagers_buried", 0x9E9Cu, 0x9E84u, 0x9E88u },
    { 2, VVS_BURIED, "villagers_buried", 0x2E5E0u, 0x2E5D4u, 0x2E5DCu },
    { 2, VVS_TWINS, "twins_birthed", 0x2E5E4u, 0x2E5D8u, 0 },
    { 3, VVS_BURIED, "villagers_buried", 0x4Cu, 0x38u, 0x3Cu },
    { 3, VVS_DIED, "villagers_died", 0x50u, 0x40u, 0 },
    { 3, VVS_CHIEFS, "chiefs_robed", 0x54u, 0x44u, 0x48u },
    { 4, VVS_BURIED, "villagers_buried", 0x50u, 0x3Cu, 0x40u },
    { 4, VVS_DIED, "villagers_died", 0x54u, 0x48u, 0 },
    { 4, VVS_DEBRIS, "debris_cleared", 0x58u, 0x44u, 0 },
    { 4, VVS_FOOD, "food_gathered", 0x5Cu, 0x0Cu, 0 },
    { 5, VVS_BURIED, "villagers_buried", 0x44u, 0x38u, 0x3Cu },
    { 5, VVS_DIED, "villagers_died", 0x48u, 0x40u, 0 },
    { 5, VVS_HEATHENS, "heathens_converted", 0x4Cu, 0x34u, 0 },
    { 5, VVS_FOOD, "food_gathered", 0x50u, 0x0Cu, 0 },
};

static int counter(int game, int kind) {
    vvs_context c = context_for(game);
    int value = -12345;
    if (!vvs_counter_value(&c, kind, &value)) {
        return -99999;
    }
    return value;
}

static int dword_at(unsigned char *base, unsigned int offset) {
    return *(int *)(base + offset);
}

static void put_dword(unsigned char *base, unsigned int offset, int value) {
    *(int *)(base + offset) = value;
}

/* Occupy `n` memorial records the way each game's burial writer does. */
static void occupy_memorial(int game, int n) {
    int i;
    for (i = 0; i < n; ++i) {
        switch (game) {
        case 1: put_dword(g_manager, 0xA324u + i * 0x2Cu + 0x1Cu, 40 + i); break;
        case 2: put_dword(g_manager, 0x2EB0Cu + i * 0x7Cu + 0x74u, 1); break;
        case 3: put_dword(g_module, 0x197D64u + i * 0x30u + 0x1Cu, 40 + i); break;
        case 4: put_dword(g_module, 0x1025C8u + i * 0x5Cu + 0x1Cu, 40 + i); break;
        case 5: put_dword(g_module, 0x1481A8u + i * 0x5Cu + 0x1Cu, 40 + i); break;
        }
    }
}

static void counter_regression(const counter_facts *k) {
    unsigned char *block = block_of(k->game);
    unsigned char *saved = saved_of(k->game);
    char text[4096];
    char want[128];
    char what[200];
    int start;

    remove_files(k->game);
    restart();
    printf("VV%d %s\n", k->game, k->key);

    /* Migration from the frozen field of an existing save, once. */
    put_dword(block, k->frozen, 7);
    if (saved != NULL) {
        put_dword(saved, k->frozen, 7);
    }
    start = 7;
    if (k->kind == VVS_BURIED) {
        occupy_memorial(k->game, 9);
        start = 9;       /* max(frozen 7, memorial 9) */
    }
    sprintf(what, "VV%d %s: before any .dat the row shows the migrated start %d",
            k->game, k->key, start);
    check(counter(k->game, k->kind) == start, what);
    put_dword(block, k->pending, 1);
    if (saved != NULL) {
        put_dword(saved, k->pending, 1);
    }
    check(flush(k->game) & 1, "flush writes the counters file");
    read_text(g_counters, text, sizeof text);
    sprintf(want, "%s=%d\n", k->key, start + 1);
    sprintf(what, "VV%d %s: increment -> PreSave -> .dat total is start + 1", k->game, k->key);
    check(strstr(text, want) != NULL && counter(k->game, k->kind) == start + 1, what);
    sprintf(want, "migrated.%s=%d\n", k->key, start);
    sprintf(what, "VV%d %s: the migration is recorded in the .dat", k->game, k->key);
    check(strstr(text, want) != NULL, what);
    sprintf(what, "VV%d %s: the pending field is zeroed in live memory and the save buffer",
            k->game, k->key);
    check(dword_at(block, k->pending) == 0
          && (saved == NULL || dword_at(saved, k->pending) == 0), what);
    sprintf(what, "VV%d %s: the frozen field is never written", k->game, k->key);
    check(dword_at(block, k->frozen) == 7
          && (saved == NULL || dword_at(saved, k->frozen) == 7), what);

    /* Reloading an older backup (frozen value still 7, pending 0) cannot add
       the migration a second time, and a plain save adds nothing. */
    restart();
    put_dword(block, k->frozen, 7);
    if (k->kind == VVS_BURIED) {
        occupy_memorial(k->game, 9);
    }
    flush(k->game);
    sprintf(what, "VV%d %s: reloading an older save does not double count", k->game, k->key);
    check(counter(k->game, k->kind) == start + 1, what);

    /* Two increments across a restart. */
    put_dword(block, k->pending, 2);
    flush(k->game);
    restart();
    sprintf(what, "VV%d %s: totals persist across a restart", k->game, k->key);
    check(counter(k->game, k->kind) == start + 3, what);

    /* A corrupt counters file is set aside and the history restarts from what
       the save proves -- never from invented values. */
    write_text(g_counters, "VVFP VILLAGE STATISTICS v1 game=9\nvillagers_buried=999\n");
    restart();
    put_dword(block, k->frozen, 7);
    if (k->kind == VVS_BURIED) {
        occupy_memorial(k->game, 9);
    }
    flush(k->game);
    {
        wchar_t aside[MAX_PATH + 32];
        _snwprintf_s(aside, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable", g_counters);
        sprintf(what, "VV%d %s: a corrupt counters file is kept aside, not trusted",
                k->game, k->key);
        check(exists(aside) && counter(k->game, k->kind) == start, what);
    }

    /* An unreadable counters file keeps the count pending. */
    {
        HANDLE lock;
        put_dword(block, k->pending, 4);
        lock = CreateFileW(g_counters, GENERIC_READ, 0, NULL, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, NULL);
        sprintf(what, "VV%d %s: an unreadable counters file zeroes nothing", k->game, k->key);
        check(lock != INVALID_HANDLE_VALUE && !(flush(k->game) & 1)
              && dword_at(block, k->pending) == 4, what);
        CloseHandle(lock);
        flush(k->game);
        sprintf(what, "VV%d %s: the held count is recorded once the file is readable",
                k->game, k->key);
        check(counter(k->game, k->kind) == start + 4 && dword_at(block, k->pending) == 0, what);
    }
    remove_files(k->game);
}

static void chiefs_baseline(void) {
    unsigned char *block = block_of(3);
    unsigned char *record;
    printf("VV3 chiefs_robed baseline\n");
    remove_files(3);
    restart();
    /* A living chief in slot 2 (active +0xF10 == 1, chief flag +0xE80). */
    record = g_module + 0x19E110u + 0x14u + 2u * 0x1F8Cu;
    record[0xF10] = 1;
    record[0xE80] = 1;
    check(counter(3, VVS_CHIEFS) == 1,
          "an unseeded save with a living chief starts Chiefs Robed at 1");
    put_dword(block, 0x48u, 0x56433131);   /* the earlier seed ran */
    check(counter(3, VVS_CHIEFS) == 0,
          "a save the earlier build already seeded keeps its own value");
    put_dword(block, 0x48u, 0);
    record[0xF10] = 0;
    check(counter(3, VVS_CHIEFS) == 0, "a dead chief is not a living one");
    remove_files(3);
}

static void burial_uses_memorial_only_as_a_floor(void) {
    unsigned char *block = block_of(4);
    printf("VV4 villagers_buried floor\n");
    remove_files(4);
    restart();
    put_dword(block, 0x3Cu, 30);
    occupy_memorial(4, 12);
    check(counter(4, VVS_BURIED) == 30,
          "a frozen counter above the memorial is kept (max, not sum)");
    remove_files(4);
}

static void games_without_a_counter(void) {
    int value = 5;
    vvs_context c = context_for(1);
    check(!vvs_counter_value(&c, VVS_TWINS, &value), "VV1 has no Twins counter here");
    check(!vvs_stews_value(&c, &value), "VV1 has no stews");
    c = context_for(5);
    check(!vvs_stews_value(&c, &value), "VV5 has no stews");
    check(vvs_stew_identity(1, 0x30, 0x30, 0x30, 0) == -1, "VV1 has no stew identities");
}

int main(void) {
    wchar_t temp[MAX_PATH];
    int i;
    GetTempPathW(MAX_PATH, temp);
    _snwprintf_s(g_folder, MAX_PATH, _TRUNCATE, L"%lsvvfp_store_harness_%lu",
                 temp, (unsigned long)GetCurrentProcessId());
    CreateDirectoryW(g_folder, NULL);
    g_module = (unsigned char *)VirtualAlloc(NULL, MODULE_BYTES, MEM_COMMIT | MEM_RESERVE,
                                             PAGE_READWRITE);
    g_manager = (unsigned char *)VirtualAlloc(NULL, MANAGER_BYTES, MEM_COMMIT | MEM_RESERVE,
                                              PAGE_READWRITE);
    if (g_module == NULL || g_manager == NULL) {
        printf("allocation failed\n");
        return 2;
    }
    wprintf(L"folder: %ls\n", g_folder);

    stew_regression(2);
    stew_regression(3);
    stew_regression(4);
    for (i = 0; i < (int)(sizeof COUNTERS / sizeof COUNTERS[0]); ++i) {
        counter_regression(&COUNTERS[i]);
    }
    chiefs_baseline();
    burial_uses_memorial_only_as_a_floor();
    games_without_a_counter();

    for (i = 1; i <= 5; ++i) {
        remove_files(i);
    }
    RemoveDirectoryW(g_folder);
    printf("== %d failure(s) ==\n", failures);
    return failures == 0 ? 0 : 1;
}
