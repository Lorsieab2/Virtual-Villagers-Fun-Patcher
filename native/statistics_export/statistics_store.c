/* See statistics_store.h. Patcher-owned statistics, persisted in .dat files.
 *
 * FILE FORMATS. Both files are ASCII, one record per line, "\n" line ends
 * (a "\r\n" is accepted on reading), written in a fixed canonical order so
 * the same state always produces the same bytes.
 *
 * "Village Statistics - Save N.dat"
 *
 *     VVFP VILLAGE STATISTICS v1 game=<1..5>
 *     <key>=<decimal total>
 *     migrated.<key>=<the frozen save value the total started from>
 *
 *   sorted by key. Keys: villagers_buried, twins_birthed, chiefs_robed,
 *   debris_cleared, food_gathered, heathens_converted, villagers_died. A key
 *   this build does not know is kept as it is.
 *
 * "Stew Discoveries - Save N.dat"
 *
 *     VVFP STEW DISCOVERIES v1 game=<2..4>
 *     stew=<identity> herbs=<h1>,<h2>,<h3>[ water=fresh|salt]
 *
 *   one line per discovered identity, ascending. The herbs are the game's own
 *   ids in two-digit upper-case hex, sorted ascending, so a line alone is
 *   enough to reconstruct the combination.
 *
 * STEW IDENTITY. Every one of these games matches a recipe on how many of
 * each herb the pot holds, never on the order they went in (VV2 0x425B60
 * counts occurrences; VV3 0x430270 and VV4 0x42DB70 pack per-herb counts), so
 * a combination is a MULTISET of three herbs. With the herbs mapped to
 * 0..n-1 (herb - first id) and sorted a <= b <= c, the identity is the
 * combinatorial-number-system rank of the multiset
 *
 *     identity = C(c+2, 3) + C(b+1, 2) + a
 *
 * which numbers every multiset exactly once from 0 to C(n+2, 3) - 1:
 *     VV2  herbs 0x30..0x35, n = 6   ->  56 identities, 0..55
 *     VV3  herbs 0x1F..0x25, n = 7   ->  84 identities, 0..83
 *     VV4  herbs 0x1F..0x22, n = 4   ->  20 herb identities, and the water
 *          makes it 40: identity = herb identity + 20 for salt water
 *          (0..19 fresh, 20..39 salt).
 * For example VV2 herbs 30,30,30 -> 0; 30,30,31 -> 1; 35,35,35 -> 55.
 *
 * SAFE HANDLING. A missing file is an empty history. A file that cannot be
 * opened for a reason other than absence is left alone and nothing is
 * flushed, so the pending bits and counts stay in memory and in the save until
 * a later save can record them. A file that opens but is not a valid file of
 * this format for this game (corrupt, another game, another version) is never
 * overwritten and nothing is invented from it: it is renamed aside to
 * "<name>.unreadable" (or "-2", "-3", ...), and the history starts again from
 * what the save itself proves. Every write goes to "<name>.tmp" first and
 * replaces the real file with MoveFileEx, so a crash leaves either the old
 * file or the new one, never a torn one, and a new file is always the UNION
 * of the old set and the new discoveries -- an identity is never dropped.
 */
/* Every _snprintf below is followed by an explicit terminator. */
#ifndef _CRT_SECURE_NO_WARNINGS
#define _CRT_SECURE_NO_WARNINGS
#endif
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "statistics_store.h"
#include "save_folder.h"
#include "vv3_villager_table.h"

enum {
    GAME_VV1 = 1, GAME_VV2, GAME_VV3, GAME_VV4, GAME_VV5
};

#define MAX_ENTRIES 64
#define MAX_KEY 48
#define MAX_FILE_BYTES 65536
#define MAX_STEW_IDENTITIES 128

/* Seed markers the earlier builds wrote beside their counters. */
#define ROBING_BASELINE_MARKER 0x56433131 /* 'VC11' */

typedef struct {
    int kind;
    const char *key;
    unsigned int pending;      /* offset of the pending dword in the block */
    unsigned int frozen;       /* offset of the frozen earlier counter */
    unsigned int frozen_marker;/* offset of its seed marker, or 0 */
} counter_def;

typedef struct {
    int game_id;
    /* 0: the pending block is the manager itself (VV1, VV2). Otherwise the
       RVA of the game's live statistics block, whose copy inside the manager
       at saved_offset is what the writer serialises. */
    unsigned int live_rva;
    unsigned int saved_offset;
    unsigned int block_size;
    counter_def counters[6];
    int counter_count;
    /* The memorial the burial baseline counts: in the manager or the image. */
    int memorial_in_manager;
    unsigned int memorial_offset;
    unsigned int memorial_stride;
    unsigned int memorial_occupied;
    unsigned int memorial_capacity;
    /* Living villagers, for the one-time Chiefs Robed baseline. */
    unsigned int villagers_rva;
    unsigned int villager_base;
    unsigned int villager_stride;
    unsigned int villager_slots;
    unsigned int villager_active;
    unsigned int villager_chief;
    /* Stews: pending ordered-triple bits, herb set, and water. */
    unsigned int stew_bits;
    int stew_herbs;
    int stew_first;
    int stew_water;
} game_layout;

static const game_layout LAYOUTS[5] = {
    /* A New Home. Manager block; memorial of 50 graves, stride 0x2C, with the
       occupancy dword the game's recount 0x41CF10 tests at +0x24 from the
       grave base 0xA31C -- 0xA324 + 0x1C. Frozen burial counter +0x9E84 and
       its VBS2 seed marker +0x9E88; pending +0x9E9C. */
    { GAME_VV1, 0, 0, 0,
      { { VVS_BURIED, "villagers_buried", 0x9E9Cu, 0x9E84u, 0x9E88u } }, 1,
      1, 0xA324u, 0x2Cu, 0x1Cu, 50u,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0 },
    /* The Lost Children. Manager block; memorial of 50 at +0x2EB0C, stride
       0x7C, occupancy +0x74 (the allocator 0x464CD0). Frozen burial +0x2E5D4
       (marker +0x2E5DC) and twins +0x2E5D8; pending +0x2E5E0, +0x2E5E4 and
       the stew bits at +0x2E5E8. */
    { GAME_VV2, 0, 0, 0,
      { { VVS_BURIED, "villagers_buried", 0x2E5E0u, 0x2E5D4u, 0x2E5DCu },
        { VVS_TWINS, "twins_birthed", 0x2E5E4u, 0x2E5D8u, 0 } }, 2,
      1, 0x2EB0Cu, 0x7Cu, 0x74u, 50u,
      0, 0, 0, 0, 0, 0,
      0x2E5E8u, 6, 0x30, 0 },
    /* The Secret City. Live block 0x5824A0 (0x98 bytes, copied to and from
       manager+0x4EC by 0x4264A0/0x426480). Roster Of The Dead at 0x597D64,
       500 records of 0x30, occupancy +0x1C -- the roster only. Villagers at
       0x59E110 (+0x14, stride 0x1F8C, 150), active +0xF10, chief +0xE80. */
    { GAME_VV3, 0x1824A0u, 0x4ECu, 0x98u,
      { { VVS_BURIED, "villagers_buried", 0x4Cu, 0x38u, 0x3Cu },
        { VVS_DIED, "villagers_died", 0x50u, 0x40u, 0 },
        { VVS_CHIEFS, "chiefs_robed", 0x54u, 0x44u, 0x48u } }, 3,
      0, 0x197D64u, 0x30u, 0x1Cu, 500u,
      0x19E110u, 0x14u, 0x1F8Cu, 150u, 0xF10u, 0xE80u,
      0x58u, 7, 0x1F, 0 },
    /* The Tree of Life. Live block 0x4D6DE0 (manager+0x850). Mausoleum at
       0x5025C8, 500 x 0x5C, occupancy +0x1C. +0x4C is the Village Elders seed
       marker and is not touched here. */
    { GAME_VV4, 0xD6DE0u, 0x850u, 0x98u,
      { { VVS_BURIED, "villagers_buried", 0x50u, 0x3Cu, 0x40u },
        { VVS_DIED, "villagers_died", 0x54u, 0x48u, 0 },
        { VVS_DEBRIS, "debris_cleared", 0x58u, 0x44u, 0 },
        { VVS_FOOD, "food_gathered", 0x5Cu, 0x0Cu, 0 } }, 4,
      0, 0x1025C8u, 0x5Cu, 0x1Cu, 500u,
      0, 0, 0, 0, 0, 0,
      0x60u, 4, 0x1F, 1 },
    /* New Believers. Live block 0x51D358 (manager+0x7B4). Memorial at
       0x5481A8, 500 x 0x5C, occupancy +0x1C. +0x30 is Origins' flag word. */
    { GAME_VV5, 0x11D358u, 0x7B4u, 0x98u,
      { { VVS_BURIED, "villagers_buried", 0x44u, 0x38u, 0x3Cu },
        { VVS_DIED, "villagers_died", 0x48u, 0x40u, 0 },
        { VVS_HEATHENS, "heathens_converted", 0x4Cu, 0x34u, 0 },
        { VVS_FOOD, "food_gathered", 0x50u, 0x0Cu, 0 } }, 4,
      0, 0x1481A8u, 0x5Cu, 0x1Cu, 500u,
      0, 0, 0, 0, 0, 0,
      0, 0, 0, 0 },
};

static const game_layout *layout_for(int game_id) {
    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return NULL;
    }
    return &LAYOUTS[game_id - 1];
}

static int read_dword(const unsigned char *base, unsigned int offset) {
    return *(const int *)(base + offset);
}

/* The block the hooks increment. */
static unsigned char *pending_block(const vvs_context *c, const game_layout *g) {
    if (g->live_rva == 0) {
        return c->manager;
    }
    return c->module == NULL ? NULL : c->module + g->live_rva;
}

/* The copy of that block inside the save buffer, or NULL when the block IS
   the manager. */
static unsigned char *saved_block(const vvs_context *c, const game_layout *g) {
    if (g->live_rva == 0 || c->manager == NULL) {
        return NULL;
    }
    return c->manager + g->saved_offset;
}

/* ------------------------------------------------------------------ files */

typedef struct {
    char key[MAX_KEY];
    long long value;
} entry;

typedef struct {
    entry entries[MAX_ENTRIES];
    int count;
} counter_file;

typedef struct {
    unsigned char present[MAX_STEW_IDENTITIES];
} stew_file;

static int read_whole(const wchar_t *path, char *buffer, DWORD *size) {
    HANDLE f;
    DWORD got = 0;
    LARGE_INTEGER length;
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
            return VVS_FILE_MISSING;
        }
        return VVS_FILE_UNREADABLE;
    }
    if (!GetFileSizeEx(f, &length)) {
        CloseHandle(f);
        return VVS_FILE_UNREADABLE;
    }
    if (length.QuadPart >= MAX_FILE_BYTES) {
        CloseHandle(f);
        return VVS_FILE_CORRUPT;     /* far larger than any file we write */
    }
    if (!ReadFile(f, buffer, (DWORD)length.QuadPart, &got, NULL)
        || got != (DWORD)length.QuadPart) {
        CloseHandle(f);
        return VVS_FILE_UNREADABLE;
    }
    CloseHandle(f);
    buffer[got] = '\0';
    *size = got;
    return VVS_FILE_OK;
}

/* Split the next line off `cursor`, stripping "\n" or "\r\n". Returns NULL at
   the end. A NUL byte inside the text ends it early, which makes a binary file
   fail the header or line checks rather than read as valid. */
static char *next_line(char **cursor) {
    char *start = *cursor;
    char *end;
    if (start == NULL || *start == '\0') {
        return NULL;
    }
    end = strchr(start, '\n');
    if (end == NULL) {
        *cursor = start + strlen(start);
    } else {
        *end = '\0';
        *cursor = end + 1;
    }
    end = start + strlen(start);
    if (end > start && end[-1] == '\r') {
        end[-1] = '\0';
    }
    return start;
}

static int valid_key(const char *key) {
    const char *p;
    if (key[0] == '\0' || strlen(key) >= MAX_KEY) {
        return 0;
    }
    for (p = key; *p; ++p) {
        if (!((*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9')
              || *p == '_' || *p == '.')) {
            return 0;
        }
    }
    return 1;
}

static entry *find_entry(counter_file *file, const char *key) {
    int i;
    for (i = 0; i < file->count; ++i) {
        if (strcmp(file->entries[i].key, key) == 0) {
            return &file->entries[i];
        }
    }
    return NULL;
}

static int set_entry(counter_file *file, const char *key, long long value) {
    entry *e = find_entry(file, key);
    if (e == NULL) {
        if (file->count >= MAX_ENTRIES || !valid_key(key)) {
            return 0;
        }
        e = &file->entries[file->count++];
        lstrcpynA(e->key, key, MAX_KEY);
    }
    e->value = value;
    return 1;
}

static int read_counter_file(const wchar_t *path, int game_id, counter_file *file) {
    static char buffer[MAX_FILE_BYTES + 1];
    char expected[64];
    char rendered[MAX_KEY + 32];
    char *cursor;
    char *line;
    DWORD size = 0;
    int state;

    file->count = 0;
    state = read_whole(path, buffer, &size);
    if (state != VVS_FILE_OK) {
        return state;
    }
    if (strlen(buffer) != size) {
        return VVS_FILE_CORRUPT;     /* an embedded NUL: not our text */
    }
    cursor = buffer;
    line = next_line(&cursor);
    _snprintf(expected, sizeof expected, "VVFP VILLAGE STATISTICS v1 game=%d", game_id);
    expected[sizeof expected - 1] = '\0';
    if (line == NULL || strcmp(line, expected) != 0) {
        return VVS_FILE_CORRUPT;
    }
    while ((line = next_line(&cursor)) != NULL) {
        char *equals = strchr(line, '=');
        char key[MAX_KEY];
        long long value;
        char *stop = NULL;
        if (equals == NULL || equals - line >= MAX_KEY) {
            return VVS_FILE_CORRUPT;
        }
        memcpy(key, line, (size_t)(equals - line));
        key[equals - line] = '\0';
        if (!valid_key(key) || equals[1] == '\0') {
            return VVS_FILE_CORRUPT;
        }
        value = _strtoi64(equals + 1, &stop, 10);
        if (stop == NULL || *stop != '\0') {
            return VVS_FILE_CORRUPT;
        }
        /* Only the canonical spelling is accepted ("007", "+7", " 7" are not
           something this writer produces). */
        _snprintf(rendered, sizeof rendered, "%s=%I64d", key, value);
        rendered[sizeof rendered - 1] = '\0';
        if (strcmp(rendered, line) != 0) {
            return VVS_FILE_CORRUPT;
        }
        if (find_entry(file, key) != NULL) {
            return VVS_FILE_CORRUPT;     /* a key twice: which one is true? */
        }
        if (!set_entry(file, key, value)) {
            return VVS_FILE_CORRUPT;
        }
    }
    return VVS_FILE_OK;
}

static int compare_entries(const void *left, const void *right) {
    return strcmp(((const entry *)left)->key, ((const entry *)right)->key);
}

/* Write `text` to "<path>.tmp" and move it over `path`. */
static int replace_file(const wchar_t *path, const char *text, size_t length) {
    wchar_t temporary[MAX_PATH + 8];
    HANDLE f;
    DWORD written = 0;
    if (_snwprintf_s(temporary, MAX_PATH + 8, _TRUNCATE, L"%ls.tmp", path) < 0) {
        return 0;
    }
    f = CreateFileW(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!WriteFile(f, text, (DWORD)length, &written, NULL)
        || written != (DWORD)length
        || !FlushFileBuffers(f)) {
        CloseHandle(f);
        DeleteFileW(temporary);
        return 0;
    }
    CloseHandle(f);
    if (!MoveFileExW(temporary, path,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}

static int write_counter_file(const wchar_t *path, int game_id, counter_file *file) {
    static char text[MAX_FILE_BYTES];
    size_t used;
    int i;
    int n;
    qsort(file->entries, (size_t)file->count, sizeof(entry), compare_entries);
    n = _snprintf(text, sizeof text, "VVFP VILLAGE STATISTICS v1 game=%d\n", game_id);
    if (n < 0) {
        return 0;
    }
    used = (size_t)n;
    for (i = 0; i < file->count; ++i) {
        n = _snprintf(text + used, sizeof text - used, "%s=%I64d\n",
                      file->entries[i].key, file->entries[i].value);
        if (n < 0 || (size_t)n >= sizeof text - used) {
            return 0;
        }
        used += (size_t)n;
    }
    return replace_file(path, text, used);
}

/* ------------------------------------------------------------------ stews */

static int ordered_bits(const game_layout *g) {
    int n = g->stew_herbs;
    return n * n * n * (g->stew_water ? 2 : 1);
}

static int multiset_rank(int a, int b, int c) {
    /* a <= b <= c. C(c+2,3) + C(b+1,2) + a. */
    return (c + 2) * (c + 1) * c / 6 + (b + 1) * b / 2 + a;
}

static int herb_identities(const game_layout *g) {
    int n = g->stew_herbs;
    return (n + 2) * (n + 1) * n / 6;
}

int vvs_stew_identity(int game_id, int h1, int h2, int h3, int salt) {
    const game_layout *g = layout_for(game_id);
    int v[3];
    int t;
    if (g == NULL || g->stew_herbs == 0) {
        return -1;
    }
    v[0] = h1 - g->stew_first;
    v[1] = h2 - g->stew_first;
    v[2] = h3 - g->stew_first;
    for (t = 0; t < 3; ++t) {
        if (v[t] < 0 || v[t] >= g->stew_herbs) {
            return -1;
        }
    }
    if (v[0] > v[1]) { t = v[0]; v[0] = v[1]; v[1] = t; }
    if (v[1] > v[2]) { t = v[1]; v[1] = v[2]; v[2] = t; }
    if (v[0] > v[1]) { t = v[0]; v[0] = v[1]; v[1] = t; }
    return multiset_rank(v[0], v[1], v[2])
        + ((g->stew_water && salt) ? herb_identities(g) : 0);
}

/* The canonical line for an identity, or 0 if the identity is out of range. */
static int render_stew_line(const game_layout *g, int identity, char *out, size_t size) {
    int herbs = herb_identities(g);
    int total = herbs * (g->stew_water ? 2 : 1);
    int rank;
    int a, b, c;
    int n = g->stew_herbs;
    if (identity < 0 || identity >= total) {
        return 0;
    }
    rank = identity % herbs;
    for (c = 0; c < n; ++c) {
        for (b = 0; b <= c; ++b) {
            for (a = 0; a <= b; ++a) {
                if (multiset_rank(a, b, c) == rank) {
                    if (g->stew_water) {
                        _snprintf(out, size, "stew=%d herbs=%02X,%02X,%02X water=%s",
                                  identity, a + g->stew_first, b + g->stew_first,
                                  c + g->stew_first,
                                  identity >= herbs ? "salt" : "fresh");
                    } else {
                        _snprintf(out, size, "stew=%d herbs=%02X,%02X,%02X",
                                  identity, a + g->stew_first, b + g->stew_first,
                                  c + g->stew_first);
                    }
                    out[size - 1] = '\0';
                    return 1;
                }
            }
        }
    }
    return 0;
}

static int read_stew_file(const wchar_t *path, const game_layout *g, stew_file *file) {
    static char buffer[MAX_FILE_BYTES + 1];
    char expected[64];
    char rendered[96];
    char *cursor;
    char *line;
    DWORD size = 0;
    int state;
    int last = -1;

    memset(file->present, 0, sizeof file->present);
    state = read_whole(path, buffer, &size);
    if (state != VVS_FILE_OK) {
        return state;
    }
    if (strlen(buffer) != size) {
        return VVS_FILE_CORRUPT;
    }
    cursor = buffer;
    line = next_line(&cursor);
    _snprintf(expected, sizeof expected, "VVFP STEW DISCOVERIES v1 game=%d", g->game_id);
    expected[sizeof expected - 1] = '\0';
    if (line == NULL || strcmp(line, expected) != 0) {
        return VVS_FILE_CORRUPT;
    }
    while ((line = next_line(&cursor)) != NULL) {
        int identity;
        char *stop = NULL;
        if (strncmp(line, "stew=", 5) != 0) {
            return VVS_FILE_CORRUPT;
        }
        identity = (int)strtol(line + 5, &stop, 10);
        if (stop == line + 5) {
            return VVS_FILE_CORRUPT;
        }
        /* The whole line must be exactly what this identity renders to: the
           herbs and the water are checked against the identity, not trusted
           beside it. */
        if (!render_stew_line(g, identity, rendered, sizeof rendered)
            || strcmp(rendered, line) != 0) {
            return VVS_FILE_CORRUPT;
        }
        if (identity <= last) {
            return VVS_FILE_CORRUPT;     /* out of order, or a duplicate */
        }
        last = identity;
        file->present[identity] = 1;
    }
    return VVS_FILE_OK;
}

static int write_stew_file(const wchar_t *path, const game_layout *g, const stew_file *file) {
    static char text[MAX_FILE_BYTES];
    char line[96];
    size_t used;
    int identity;
    int total = herb_identities(g) * (g->stew_water ? 2 : 1);
    int n = _snprintf(text, sizeof text, "VVFP STEW DISCOVERIES v1 game=%d\n", g->game_id);
    if (n < 0) {
        return 0;
    }
    used = (size_t)n;
    for (identity = 0; identity < total; ++identity) {
        if (!file->present[identity]) {
            continue;
        }
        if (!render_stew_line(g, identity, line, sizeof line)) {
            return 0;
        }
        n = _snprintf(text + used, sizeof text - used, "%s\n", line);
        if (n < 0 || (size_t)n >= sizeof text - used) {
            return 0;
        }
        used += (size_t)n;
    }
    return replace_file(path, text, used);
}

/* OR the pending ordered-triple bits into `file` as canonical identities.
   Returns the number of pending bits seen. */
static int merge_pending_stews(const game_layout *g, const unsigned char *bits, stew_file *file) {
    int n = g->stew_herbs;
    int total = ordered_bits(g);
    int index;
    int seen = 0;
    if (bits == NULL) {
        return 0;
    }
    for (index = 0; index < total; ++index) {
        int triple;
        int salt = 0;
        int identity;
        if (!(bits[index >> 3] & (1u << (index & 7)))) {
            continue;
        }
        ++seen;
        triple = index;
        if (g->stew_water) {
            salt = triple & 1;
            triple >>= 1;
        }
        identity = vvs_stew_identity(
            g->game_id,
            triple / (n * n) + g->stew_first,
            (triple / n) % n + g->stew_first,
            triple % n + g->stew_first,
            salt);
        if (identity >= 0) {
            file->present[identity] = 1;
        }
    }
    return seen;
}

static int stew_bytes(const game_layout *g) {
    /* The hook's bts writes whole dwords, so clear whole dwords. */
    return ((ordered_bits(g) + 31) / 32) * 4;
}

/* ------------------------------------------------------------ migration */

static int count_memorial(const vvs_context *c, const game_layout *g) {
    const unsigned char *base;
    unsigned int i;
    int total = 0;
    if (g->memorial_in_manager) {
        base = c->manager == NULL ? NULL : c->manager + g->memorial_offset;
    } else {
        base = c->module == NULL ? NULL : c->module + g->memorial_offset;
    }
    if (base == NULL) {
        return 0;
    }
    for (i = 0; i < g->memorial_capacity; ++i) {
        if (read_dword(base + i * g->memorial_stride, g->memorial_occupied) != 0) {
            ++total;
        }
    }
    return total;
}

static int living_chief(const vvs_context *c, const game_layout *g) {
    unsigned int i;
    unsigned int table = g->villagers_rva;
    unsigned int slots = g->villager_slots;
    const unsigned char *villagers;
    if (g->villagers_rva == 0 || c->module == NULL) {
        return 0;
    }
    if (g->game_id == GAME_VV3) {
        vv3_villager_table(c->module, &table, &slots);
    }
    villagers = c->module + table;
    for (i = 0; i < slots; ++i) {
        const unsigned char *record = villagers + g->villager_base + i * g->villager_stride;
        if (record[g->villager_active] == 1 && record[g->villager_chief] != 0) {
            return 1;
        }
    }
    return 0;
}

/* The starting total for a counter the .dat has never held: the frozen field
   the earlier builds counted into, raised where the game itself still proves
   more. */
static long long migration_value(const vvs_context *c, const game_layout *g,
                                 const counter_def *d, const unsigned char *block) {
    long long value = block == NULL ? 0 : read_dword(block, d->frozen);
    if (value < 0) {
        value = 0;
    }
    if (d->kind == VVS_BURIED) {
        /* The owner: max(migrated value, memorial occupied count). */
        long long memorial = count_memorial(c, g);
        if (memorial > value) {
            value = memorial;
        }
    } else if (d->kind == VVS_CHIEFS && block != NULL && d->frozen_marker != 0
               && read_dword(block, d->frozen_marker) != ROBING_BASELINE_MARKER) {
        /* The earlier seed never ran for this save: a village with a living
           chief has had at least one. */
        if (living_chief(c, g) && value < 1) {
            value = 1;
        }
    }
    return value;
}

static void migrated_key(const counter_def *d, char *out, size_t size) {
    _snprintf(out, size, "migrated.%s", d->key);
    out[size - 1] = '\0';
}

/* Rename a file this build cannot read out of the way, never over another. */
static int set_aside(const wchar_t *path) {
    wchar_t aside[MAX_PATH + 32];
    int attempt;
    for (attempt = 1; attempt < 100; ++attempt) {
        if (attempt == 1) {
            _snwprintf_s(aside, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable", path);
        } else {
            _snwprintf_s(aside, MAX_PATH + 32, _TRUNCATE, L"%ls.unreadable-%d", path, attempt);
        }
        if (MoveFileExW(path, aside, 0)) {
            return 1;
        }
        if (GetLastError() != ERROR_ALREADY_EXISTS && GetLastError() != ERROR_FILE_EXISTS) {
            return 0;
        }
    }
    return 0;
}

/* ------------------------------------------------------------- public */

static int flush_counters(const vvs_context *c, const game_layout *g) {
    static counter_file file;
    unsigned char *block = pending_block(c, g);
    unsigned char *saved = saved_block(c, g);
    int state;
    int i;
    if (g->counter_count == 0 || block == NULL || c->counters_path == NULL
        || c->counters_path[0] == L'\0') {
        return 0;
    }
    state = read_counter_file(c->counters_path, g->game_id, &file);
    if (state == VVS_FILE_UNREADABLE) {
        return 0;                     /* keep everything pending */
    }
    if (state == VVS_FILE_CORRUPT) {
        if (!set_aside(c->counters_path)) {
            return 0;
        }
        file.count = 0;
    }
    if (state != VVS_FILE_OK) {
        file.count = 0;
    }
    for (i = 0; i < g->counter_count; ++i) {
        const counter_def *d = &g->counters[i];
        entry *e = find_entry(&file, d->key);
        long long total;
        if (e == NULL) {
            char marker[MAX_KEY + 16];
            total = migration_value(c, g, d, block);
            migrated_key(d, marker, sizeof marker);
            if (!set_entry(&file, marker, total)) {
                return 0;
            }
        } else {
            total = e->value;
        }
        total += read_dword(block, d->pending);
        if (!set_entry(&file, d->key, total)) {
            return 0;
        }
    }
    if (!write_counter_file(c->counters_path, g->game_id, &file)) {
        return 0;                     /* not recorded: stays pending */
    }
    for (i = 0; i < g->counter_count; ++i) {
        const counter_def *d = &g->counters[i];
        *(int *)(block + d->pending) = 0;
        if (saved != NULL) {
            *(int *)(saved + d->pending) = 0;
        }
    }
    return 1;
}

static int flush_stews(const vvs_context *c, const game_layout *g) {
    static stew_file file;
    unsigned char *block = pending_block(c, g);
    unsigned char *saved = saved_block(c, g);
    int state;
    if (g->stew_herbs == 0 || block == NULL || c->stews_path == NULL
        || c->stews_path[0] == L'\0') {
        return 0;
    }
    state = read_stew_file(c->stews_path, g, &file);
    if (state == VVS_FILE_UNREADABLE) {
        return 0;
    }
    if (state == VVS_FILE_CORRUPT) {
        if (!set_aside(c->stews_path)) {
            return 0;
        }
        memset(file.present, 0, sizeof file.present);
    }
    if (state == VVS_FILE_MISSING) {
        memset(file.present, 0, sizeof file.present);
    }
    merge_pending_stews(g, block + g->stew_bits, &file);
    if (!write_stew_file(c->stews_path, g, &file)) {
        return 0;
    }
    memset(block + g->stew_bits, 0, (size_t)stew_bytes(g));
    if (saved != NULL) {
        memset(saved + g->stew_bits, 0, (size_t)stew_bytes(g));
    }
    return 1;
}

int vvs_flush(const vvs_context *context) {
    const game_layout *g;
    int flushed = 0;
    if (context == NULL || context->manager == NULL) {
        return 0;
    }
    g = layout_for(context->game_id);
    if (g == NULL) {
        return 0;
    }
    if (flush_counters(context, g)) {
        flushed |= 1;
    }
    if (flush_stews(context, g)) {
        flushed |= 2;
    }
    return flushed;
}

int vvs_counter_value(const vvs_context *context, int kind, int *value) {
    static counter_file file;
    const game_layout *g;
    const counter_def *d = NULL;
    unsigned char *block;
    long long total;
    entry *e = NULL;
    int i;
    if (context == NULL || value == NULL) {
        return 0;
    }
    g = layout_for(context->game_id);
    if (g == NULL) {
        return 0;
    }
    for (i = 0; i < g->counter_count; ++i) {
        if (g->counters[i].kind == kind) {
            d = &g->counters[i];
        }
    }
    if (d == NULL) {
        return 0;
    }
    block = pending_block(context, g);
    if (context->counters_path != NULL
        && read_counter_file(context->counters_path, g->game_id, &file) == VVS_FILE_OK) {
        e = find_entry(&file, d->key);
    }
    total = e != NULL ? e->value : migration_value(context, g, d, block);
    if (block != NULL) {
        total += read_dword(block, d->pending);
    }
    if (total > 0x7FFFFFFF) {
        total = 0x7FFFFFFF;
    }
    *value = (int)total;
    return 1;
}

int vvs_stews_value(const vvs_context *context, int *value) {
    static stew_file file;
    const game_layout *g;
    unsigned char *block;
    int identity;
    int total = 0;
    if (context == NULL || value == NULL) {
        return 0;
    }
    g = layout_for(context->game_id);
    if (g == NULL || g->stew_herbs == 0) {
        return 0;
    }
    if (context->stews_path == NULL
        || read_stew_file(context->stews_path, g, &file) != VVS_FILE_OK) {
        memset(file.present, 0, sizeof file.present);
    }
    block = pending_block(context, g);
    if (block != NULL) {
        merge_pending_stews(g, block + g->stew_bits, &file);
    }
    for (identity = 0; identity < MAX_STEW_IDENTITIES; ++identity) {
        total += file.present[identity];
    }
    *value = total;
    return 1;
}

int vvs_probe_file(const wchar_t *path, int game_id, int stews) {
    const game_layout *g = layout_for(game_id);
    if (g == NULL) {
        return VVS_FILE_CORRUPT;
    }
    if (stews) {
        static stew_file file;
        return read_stew_file(path, g, &file);
    } else {
        static counter_file file;
        return read_counter_file(path, game_id, &file);
    }
}

int vvs_build_paths(int game_id, int save_id, wchar_t *counters, wchar_t *stews) {
    wchar_t folder[MAX_PATH];
    const game_layout *g = layout_for(game_id);
    if (g == NULL || save_id < 1 || save_id > 5 || counters == NULL || stews == NULL) {
        return 0;
    }
    counters[0] = L'\0';
    stews[0] = L'\0';
    /* 64 covers the longest tail appended below and by the helpers:
       "\\Village Statistics - Save 5.dat" + ".unreadable-99" + ".tmp". */
    if (!vv_save_subfolder_w(folder,
            L"Virtual Villagers Fun Patcher Data\\Village Statistics", 64)) {
        return 0;
    }
    if (_snwprintf_s(counters, MAX_PATH, _TRUNCATE,
                     L"%ls\\Village Statistics - Save %d.dat", folder, save_id) < 0) {
        return 0;
    }
    if (g->stew_herbs != 0) {
        if (!vv_save_subfolder_w(folder,
                L"Virtual Villagers Fun Patcher Data\\Stew Discoveries", 64)) {
            return 0;
        }
        if (_snwprintf_s(stews, MAX_PATH, _TRUNCATE,
                         L"%ls\\Stew Discoveries - Save %d.dat", folder, save_id) < 0) {
            return 0;
        }
    }
    return 1;
}

/* ------------------------------------------------- the first-load reconcile

   statistics_reconcile.inc raises a counter that is below what the save or
   the logs prove, never lowers one.  These read and change one counter of a
   slot's counters file, through the same reader and writer as the flush. */

const char *vvs_counter_key(int game_id, int kind) {
    const game_layout *g = layout_for(game_id);
    int i;
    if (g == NULL) {
        return NULL;
    }
    for (i = 0; i < g->counter_count; ++i) {
        if (g->counters[i].kind == kind) {
            return g->counters[i].key;
        }
    }
    return NULL;
}

int vvs_counter_peek(const wchar_t *path, int game_id, const char *key, long long *value) {
    static counter_file file;
    entry *e;
    int state;
    *value = -1;
    if (path == NULL || path[0] == L'\0' || key == NULL) {
        return VVS_FILE_UNREADABLE;
    }
    state = read_counter_file(path, game_id, &file);
    if (state == VVS_FILE_OK && (e = find_entry(&file, key)) != NULL) {
        *value = e->value;
    }
    return state;
}

int vvs_counter_raise(const wchar_t *path, int game_id, const char *key, long long to, long long *was) {
    static counter_file file;
    entry *e;
    *was = -1;
    if (path == NULL || key == NULL || read_counter_file(path, game_id, &file) != VVS_FILE_OK
        || (e = find_entry(&file, key)) == NULL) {
        return -1;
    }
    *was = e->value;
    if (e->value >= to) {
        return 0;                     /* never lowered */
    }
    e->value = to;
    return write_counter_file(path, game_id, &file) ? 1 : -1;
}

int vvs_memorial_graves(const vvs_context *context) {
    const game_layout *g = context != NULL ? layout_for(context->game_id) : NULL;
    if (g == NULL || g->memorial_capacity == 0u
        || (g->memorial_in_manager ? context->manager == NULL : context->module == NULL)) {
        return -1;
    }
    return count_memorial(context, g);
}

int vvs_living_chief(const vvs_context *context) {
    const game_layout *g = context != NULL ? layout_for(context->game_id) : NULL;
    if (g == NULL || g->villagers_rva == 0u) {
        return 0;
    }
    return living_chief(context, g);
}
