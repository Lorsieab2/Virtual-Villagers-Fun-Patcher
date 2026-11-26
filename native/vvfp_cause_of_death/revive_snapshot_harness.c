/* Revive snapshots (native/shared/revive_snapshot.h, cod_revive.inc), every game: a villager with every byte of
   their record set departs, the Cause of Death companion keeps their saved windows, the save writes them to the
   slot's own file, and the restore onto a record the game's creator made gives back every persistent byte and
   nothing else.

   The companion's whole source is compiled in (the TEST build) with the Documents folder redirected to the folder
   given on the command line, so every file it touches is inside that folder -- never the real Documents\LDW.

     revive_snapshot_harness <docs folder>

   For each game, at a record index of the stock table (7) and, for The Secret City to New Believers, of the
   256-villager table (200): two villagers in turn in the SAME record (the slot reused at the population cap), each
   departing; one save; the file holds both, oldest first, each byte for byte its own; then the restore checks,
   the file's checks, a departure of another slot's village (never written) and Start Over (the file deleted).
   Exit code 0 when every check passes.  Built and run by scripts/build_revive_snapshot_harness.ps1
   (tests/test_revive_snapshot_harness.py). */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static char g_docs[MAX_PATH];
static wchar_t g_docs_w[MAX_PATH];

static BOOL WINAPI harness_special_a(HWND owner, LPSTR out, int csidl, BOOL create) {
    (void)owner; (void)csidl; (void)create;
    lstrcpyA(out, g_docs);
    return TRUE;
}

static BOOL WINAPI harness_special_w(HWND owner, LPWSTR out, int csidl, BOOL create) {
    (void)owner; (void)csidl; (void)create;
    lstrcpyW(out, g_docs_w);
    return TRUE;
}

static HRESULT WINAPI harness_folder_a(HWND owner, int csidl, HANDLE token, DWORD flags, LPSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyA(out, g_docs);
    return S_OK;
}

static HRESULT WINAPI harness_folder_w(HWND owner, int csidl, HANDLE token, DWORD flags, LPWSTR out) {
    (void)owner; (void)csidl; (void)token; (void)flags;
    lstrcpyW(out, g_docs_w);
    return S_OK;
}

#define SHGetSpecialFolderPathA harness_special_a
#define SHGetSpecialFolderPathW harness_special_w
#define SHGetFolderPathA harness_folder_a
#define SHGetFolderPathW harness_folder_w
#define VVFP_TEST 1
#include "../shared/save_folder.c"
#include "vvfp_cause_of_death.c"
#undef SHGetSpecialFolderPathA
#undef SHGetSpecialFolderPathW
#undef SHGetFolderPathA
#undef SHGetFolderPathW

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

#define SLOT 1
static int game;
static int host_slot_value;
static int __stdcall host_slot(void) { return host_slot_value; }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static unsigned char *table;
static unsigned char villager_a[0xF000], villager_b[0xF000], made[0xF000], backup[0xF000];

/* Record `i` where the companion reads it (cod_record): the table plus the game's first-record offset. */
static unsigned char *rec(int i) { return table + REC[game].record_base + (size_t)i * REC[game].stride; }

/* A villager whose every byte is set (`seed` makes each one its own), alive, with a name the matching can read. */
static void fill(unsigned char *r, int seed) {
    unsigned int k, stride = REC[game].stride;
    const vv_rs_layout *l = &VV_RS_LAYOUT[game];
    for (k = 0; k < stride; ++k) {
        r[k] = (unsigned char)(((k * 31u + (unsigned int)seed * 97u) ^ (k >> 5)) | 1u);
    }
    r[REC[game].present] = 1;
    switch (stride) {   /* never a statue, ghost or stand-in (villager_lookalike.h) */
    case 0xE48Cu: r[0x558] = 0; break;
    case 0x1F8Cu: r[0xE94] = 0; break;
    case 0x2E3Cu: r[0x1CC7] = 0; break;
    case 0x2F44u: r[0x1CE1] = 0; break;
    default: break;
    }
    *(int *)(r + REC[game].health) = 40 + seed;
    memset(r + l->name, 0, l->name_bytes);
    _snprintf((char *)r + l->name, l->name_bytes - 1, seed == 1 ? "Kaia Kotori" : "Rongo Tane");
    if (l->faction != 0u) {
        r[l->faction] = (unsigned char)(seed & 1);
    }
}

static void snapshot_path(char *out) {
    char exe[MAX_PATH], *base, *dot;
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    base = strrchr(exe, '\\') + 1;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(out, MAX_PATH,
              "%s\\LDW\\%s\\Virtual Villagers Fun Patcher\\Save %d\\Data\\Revive Snapshots\\"
              "Virtual Villagers %d Revive Snapshots - Save %d.dat", g_docs, base, SLOT, game, SLOT);
    out[MAX_PATH - 1] = 0;
}

static unsigned char file[VV_RS_HEADER + 8 * sizeof(vv_rs_entry)];

static long read_file(void) {
    char path[MAX_PATH];
    FILE *f;
    long n;
    snapshot_path(path);
    f = fopen(path, "rb");
    if (f == NULL) return -1;
    n = (long)fread(file, 1, sizeof file, f);
    fclose(f);
    return n;
}

static const vv_rs_entry *entry(int k) {
    return (const vv_rs_entry *)(file + VV_RS_HEADER + (size_t)k * sizeof(vv_rs_entry));
}

/* Whether `e` holds exactly record `r`'s saved windows. */
static int holds(const vv_rs_entry *e, const unsigned char *r) {
    int n, i;
    const vv_rs_span *s = vv_rs_saved(game, &n);
    for (i = 0; i < n; ++i) {
        const unsigned char *at = vv_rs_at(e, s[i].offset, s[i].size);
        if (at == NULL || memcmp(at, r + s[i].offset, s[i].size) != 0) return 0;
    }
    return 1;
}

static int is_kept(unsigned int k) {
    int n, i;
    const vv_rs_span *s = vv_rs_keep(game, &n);
    for (i = 0; i < n; ++i) {
        if (k >= s[i].offset && k < (unsigned int)s[i].offset + s[i].size) return 1;
    }
    return 0;
}

static void run(int index, int slots) {
    unsigned int k, stride = REC[game].stride;
    int kept_wrong, other_wrong;
    long n;
    char path[MAX_PATH];
    const vv_rs_layout *l = &VV_RS_LAYOUT[game];
    vv_rs_entry e;
    REC[game].slots = (unsigned int)slots;
    snapshot_path(path);
    DeleteFileA(path);
    printf("Virtual Villagers %d, %d records, record %d\n", game, slots, index);

    /* Two villagers in turn in the same record: the first departs, the slot is reused, the second departs. */
    fill(villager_a, 1);
    fill(villager_b, 2);
    memcpy(rec(index), villager_a, stride);
    roster_departed(index, rec(index));
    memset(rec(index), 0, stride);
    memcpy(rec(index), villager_b, stride);
    roster_departed(index, rec(index));
    memset(rec(index), 0, stride);
    CHECK(rvs_pending_count == 2, "both departures are kept until the save (%d)", rvs_pending_count);
    CHECK(read_file() < 0, "nothing is written before the save");
    revive_saved(SLOT);
    n = read_file();
    CHECK(n == (long)(VV_RS_HEADER + 2 * sizeof(vv_rs_entry)) && vv_rs_file_valid(file, (DWORD)n, game),
          "the save writes one valid file with both (%ld bytes)", n);
    CHECK(n > 0 && holds(entry(0), villager_a) && holds(entry(1), villager_b),
          "each snapshot is its own villager's, byte for byte, oldest first (the reused record never mixes them)");
    CHECK(n > 0 && entry(0)->bytes == vv_rs_data_bytes(game) && entry(0)->flags == 0,
          "every saved window is kept (%u bytes); no patcher file was there to read", entry(0)->bytes);
    memcpy(&e, entry(0), sizeof e);

    /* The restore onto what the creator made: every persistent byte is the villager's, nothing else moves. */
    fill(made, 3);
    if (l->faction != 0u) made[l->faction] = villager_a[l->faction];
    memcpy(backup, made, stride);
    CHECK(vv_rs_apply(&e, made, villager_b, 0) == 1, "the restore writes and reads back every persistent field");
    kept_wrong = other_wrong = 0;
    for (k = 0; k < stride; ++k) {
        if (is_kept(k)) {
            kept_wrong += made[k] != villager_a[k];
        } else if (!(l->chief != 0u && k == l->chief)) {
            other_wrong += made[k] != backup[k];
        }
    }
    CHECK(kept_wrong == 0, "field for field the villager's own (%d bytes differ)", kept_wrong);
    CHECK(other_wrong == 0, "the age and every transient byte stay the creator's (%d bytes differ)", other_wrong);
    CHECK(memcmp(made + l->age, backup + l->age, 4) == 0, "the age is the creator's (age 5)");
    if (l->chief != 0u) {
        CHECK(made[l->chief] == backup[l->chief], "the Tribal Chief flag stays the creator's while another Chief lives");
        memcpy(made, backup, stride);
        CHECK(vv_rs_apply(&e, made, villager_b, 1) == 1 && made[l->chief] == villager_a[l->chief],
              "...and is theirs when no other Chief lives");
    }
    if (l->faction != 0u) {
        memcpy(made, backup, stride);
        made[l->faction] = (unsigned char)!villager_a[l->faction];
        memcpy(villager_b, made, stride);
        CHECK(vv_rs_apply(&e, made, backup, 0) == 0 && memcmp(made, villager_b, stride) == 0,
              "a faction the creator did not make is refused, the record untouched");
    }

    /* Checks: a damaged snapshot or file is never used, and nothing is written into the record. */
    fill(made, 3);
    if (l->faction != 0u) made[l->faction] = villager_a[l->faction];
    memcpy(villager_b, made, stride);
    e.data[3] ^= 0x5A;
    CHECK(vv_rs_apply(&e, made, backup, 0) == 0 && memcmp(made, villager_b, stride) == 0,
          "a snapshot whose checksum fails is refused, the record untouched");
    file[VV_RS_HEADER + 40] ^= 1;
    CHECK(!vv_rs_file_valid(file, (DWORD)n, game), "a damaged file is not read as snapshots");
    file[VV_RS_HEADER + 40] ^= 1;
    CHECK(!vv_rs_file_valid(file, (DWORD)n, game == 5 ? 4 : game + 1), "another game's file is not read");

    /* A departure of another slot's village (left without a save) never reaches this one. */
    fill(villager_a, 4);
    memcpy(rec(index), villager_a, stride);
    roster_departed(index, rec(index));
    rvs_pending_slot[rvs_pending_count - 1] = SLOT + 1;
    revive_saved(SLOT);
    n = read_file();
    CHECK(n == (long)(VV_RS_HEADER + 2 * sizeof(vv_rs_entry)) && rvs_pending_count == 0,
          "another village's departure is dropped, the file as it was");
    /* ...and one more of this village is added after the others. */
    roster_departed(index, rec(index));
    revive_saved(SLOT);
    n = read_file();
    CHECK(n == (long)(VV_RS_HEADER + 3 * sizeof(vv_rs_entry)) && holds(entry(2), villager_a),
          "the next save adds the next departure after the others");
    /* Start Over: the snapshots go with the village. */
    revive_reset(SLOT);
    CHECK(read_file() < 0, "Start Over deletes the slot's snapshots");
    memset(rec(index), 0, stride);
}

/* ---- What the patcher's files keep, on every departure path (Codex, PR #880) --------------------------------
   The companions answer only for a villager still present in their roster: these stand-ins answer as they do, and
   nothing once the presence byte is cleared.  Each path frees the record before it reaches roster_departed, so the
   answers must come from what the per-frame tick kept while the villager was there. */
static int __stdcall fake_head_look(int g, const void *record) {
    return ((const unsigned char *)record)[REC[g].present] ? 2 : 0;
}
static int __stdcall fake_presentation(int g, const void *record) {
    return ((const unsigned char *)record)[REC[g].present] ? 1 : 0;
}
static int __stdcall fake_traits(int g, const void *record) {
    return ((const unsigned char *)record)[REC[g].present] ? 1 : 0;
}
static int __stdcall fake_original(int g, const void *record, int *head, int *body, int *mask) {
    if (!((const unsigned char *)record)[REC[g].present]) {
        return 0;
    }
    *head = 4;
    *body = 11;
    *mask = 0;
    return 1;
}
static FARPROC fake_export(const char *dll, const char *name) {
    (void)dll;
    if (lstrcmpA(name, "VvfpHeadLookGet") == 0) return (FARPROC)(void *)fake_head_look;
    if (lstrcmpA(name, "VvfpGenderPresentationGet") == 0) return (FARPROC)(void *)fake_presentation;
    if (lstrcmpA(name, "VvfpStoryTraitsOf") == 0) return (FARPROC)(void *)fake_traits;
    if (lstrcmpA(name, "VvfpOriginalLookGet") == 0) return (FARPROC)(void *)fake_original;
    return NULL;
}

enum { PATH_BURIAL, PATH_REMOVAL, PATH_UNRECOVERED, PATH_HEATHENS, PATH_COUNT };
static const char *const PATH_NAMES[PATH_COUNT] = {
    "a burial (the record freed first, as cod_vv12.inc / cod_vv345.inc see it)",
    "an unburied body's removal after the store that frees it (A New Home, The Lost Children)",
    "a Custom Island Event's death with no body (VvfpCauseDiedUnrecovered)",
    "a Heathen who died among the Heathens (VvfpCauseDiedAmongHeathens)" };

/* One departure by `path` of a villager whose files hold every value: the snapshot keeps them.  `keep`: the tick
   ran while they were there (0: the control, the old behaviour). */
static int depart_keeps(int path, int keep) {
    const int index = 7;
    unsigned int stride = REC[game].stride;
    int k, before = rvs_pending_count;
    const vv_rs_entry *e;
    memset(rvs_kept, 0, sizeof rvs_kept);
    fill(rec(index), 1);
    if (keep) {
        for (k = 0; k <= (int)REC[game].slots / RVS_PER_TICK + 1; ++k) {
            revive_tick();               /* the per-frame tick while they live */
        }
    }
    rec(index)[REC[game].present] = 0;   /* the game frees the record */
    switch (path) {
    case PATH_BURIAL:
        roster_departed(index, rec(index));
        break;
    case PATH_REMOVAL:
        *(int *)(rec(index) + REC[game].health) = 0;
        cod_decayed(rec(index));
        break;
    case PATH_UNRECOVERED:
        VvfpCauseDiedUnrecovered(game, index, NULL);
        break;
    default:
        VvfpCauseDiedAmongHeathens(game, index, CAUSE_OLD_AGE);
        break;
    }
    memset(rec(index), 0, stride);
    if (rvs_pending_count != before + 1) {
        return 0;
    }
    e = &rvs_pending[rvs_pending_count - 1];
    return e->head_look == 2 && e->presentation == 1 && e->traits == 1u && (e->flags & VV_RS_ORIGINAL)
        && e->original_head == 4 && e->original_body == 11;
}

static void run_sidecars(void) {
    int path;
    printf("Virtual Villagers %d, what the patcher's files keep, every departure path\n", game);
    rvs_test_export = fake_export;
    for (path = 0; path < PATH_COUNT; ++path) {
        if ((path == PATH_REMOVAL && game > 2) || (path == PATH_HEATHENS && game != 5)) {
            continue;
        }
        CHECK(depart_keeps(path, 1), "%s: the head look, presentation, traits and original look are kept",
              PATH_NAMES[path]);
    }
    CHECK(!depart_keeps(PATH_BURIAL, 0), "(the control: asked only once the record is freed, they would be lost)");
    rvs_test_export = NULL;
    rvs_pending_count = 0;
}
int main(int argc, char **argv) {
    if (argc != 2) {
        printf("usage: revive_snapshot_harness <docs folder>\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    MultiByteToWideChar(CP_ACP, 0, g_docs, -1, g_docs_w, MAX_PATH);
    table = (unsigned char *)VirtualAlloc(NULL, (size_t)0xE48C * 256 + 0x100000, MEM_COMMIT | MEM_RESERVE,
                                          PAGE_READWRITE);
    if (table == NULL) {
        printf("no memory\n");
        return 2;
    }
    for (game = 1; game <= 5; ++game) {
        int stock = (int)REC[game].slots;
        host_slot_value = SLOT;
        VvfpCauseTestSetup(game, &host, table);
        run(7, stock);
        run_sidecars();
        if (game >= 3) {
            run(200, 256);
            REC[game].slots = (unsigned int)stock;
        } else {
            run(200, stock);
        }
    }
    printf(failures ? "== %d failure(s) ==\n" : "== 0 failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
