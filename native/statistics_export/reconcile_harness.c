/* Runtime harness for the first-load reconcile of the Village Elders and
   Village Statistics files (statistics_reconcile.inc).  32-bit only.

   Drives the TEST build of "VVFP Statistics Export.dll" and the shipped
   "VVFP Save Reset.dll" (copied into "Virtual Villagers Fun Patcher Files"
   beside this executable under their shipped names, as in a game), in all
   five games' geometry, against real files under
   Documents\LDW\<this exe's basename>\, which harness_ldw_tree.h leaves as it
   found it.  Linked at a fixed base (0x30000000) with the games' villager
   tables and memorials placed where the DLL reads them.

   Each game, a village "Recon Tribe" in slot 1:
     living   Alive (a Master in three skills in the History log, alive now:
              the save adds the living itself), Ann, Bo; in The Secret City
              Bo is the robed Tribal Chief; in New Believers a Heathen with
              every skill at 100
     elders   one line, "Old" (a G line)
     History  this village: Ghost (Master in 3 skills, dead, twice -- once
              with parents in the games that keep them), Old (on the list),
              Alive, Near (Master in 2), Edge (exactly the Master threshold in
              3), Edge2 (one under it in 3); another village: Stranger
     Deaths   this village: two with a grave, one "no grave"; another
              village's with a grave; the memorial holds 1 grave
     Births   (The Lost Children) twin conceptions: 2 here, 1 elsewhere
     counters villagers_buried=1; twins_birthed=0 (The Lost Children);
              chiefs_robed=0 (The Secret City)
              (New Believers: every block says "Faction: Believer", and two
              more dead villagers mastered in every skill: Pagan, "Faction:
              Heathen", and Unsure, with no Faction line)
   Expected: A New Home, The Secret City, The Tree of Life and New Believers
   add Ghost and Edge (never Pagan or Unsure); The Lost Children (the game
   counts its own elders) adds none.  Villagers Buried 1 -> 2,
   Twins 0 -> 2, Chiefs 0 -> 1.

     1. The scan finds exactly that, lists it for the prompt and writes
        nothing.
     2. A save with no answer, and after "Not now", changes nothing: no
        counter, no elder line, no backup, no Repairs log.
     3. After Repair, the save makes exactly those changes, backs each file
        up first (byte for byte the file before), and lists every change in
        the Repairs log under the village's header.
     4. Exactly once: the scan then finds nothing; another save changes
        nothing and makes no second backup.
     5. Never lowers: a counter above its bound is left alone.
     6. Another village's files (the roster shares nobody): nothing asked.
     7. Repair answered right after the game's quit save (the cross-check's
        quit prompt, native/shared/crosscheck_bridge.h), when no later save
        will come: VvfpStatisticsRepairReconcileNow makes the same changes
        there and then from that save's state (backups, Repairs log), has the
        Village Statistics log written again so it shows them (the TEST build
        counts that call: the log's writers call game routines no harness
        maps), changes nothing a second time, and does nothing for a slot the
        last save was not.
     8. Deaths logs in both "Deaths" (an older build's) and "Deaths and
        Disappearances": both are read, a record kept in both counts once,
        and an old folder is never made when there is none.

   Usage:  reconcile_harness.exe "<statistics test dll>" "<save reset dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "village_identity.h"
#include "../shared/harness_ldw_tree.h"
#include "patcher_files.h"

static int failures;
static int checks;
#define CHECK(cond, ...) do { ++checks; if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *scan_t)(int, int, char *, int);
typedef void (__stdcall *repair_t)(int, int, int);
typedef int (__stdcall *save_t)(int, int, void *);
typedef int (__stdcall *now_t)(int, int);

struct layout {
    unsigned int rva;
    int is_pointer;
    unsigned int base, stride, slots, active, name, skills, skill_count;
    int floats;
    unsigned int father, mother, chief, tribe;
    unsigned int likes, dislikes, pref_slots;
    int memorial_in_manager;
    unsigned int memorial, memorial_stride, memorial_occupied;
    int master;
};
static const struct layout LAYOUTS[5] = {
    { 0x8B614u, 1, 0, 0x3D8, 256, 0x28, 0x370, 0x3BC, 5, 0, 0, 0, 0, 0, 0x398, 0x3A8, 4,
      1, 0xA324u, 0x2C, 0x1C, 90 },
    { 0x99F24u, 1, 0, 0xE48C, 256, 0x30, 0x564, 0x7E4, 5, 0, 0x57D, 0x596, 0, 0, 0x5F0, 0x6E8, 62,
      1, 0x2EB0Cu, 0x7C, 0x74, 88 },
    { 0x19E110u, 0, 0x14, 0x1F8C, 150, 0xF10, 0xDD4, 0xEAC, 5, 0, 0xDF8, 0xE11, 0xE80, 0, 0xFB4, 0xFC0, 3,
      0, 0x197D64u, 0x30, 0x1C, 88 },
    { 0x10E568u, 0, 0x44, 0x2E3C, 150, 0x1CC4, 0x1B9C, 0x1C5C, 5, 1, 0x1BC0, 0x1BD9, 0, 0, 0x1E60, 0x1E6C, 3,
      0, 0x1025C8u, 0x5C, 0x1C, 88 },
    { 0x154148u, 0, 0x48, 0x2F44, 150, 0x1CD4, 0x1B9C, 0x1C5C, 6, 1, 0x1BC0, 0x1BD9, 0, 0x1CEC, 0x1F5C, 0x1F68, 3,
      0, 0x1481A8u, 0x5C, 0x1C, 88 },
};
static const char *SKILLS[6] = { "Farming", "Building", "Healing", "Science", "Breeding", "Spirit" };

static const struct layout *g;
static int game;
static unsigned char *module_base;
static unsigned char *table;
static unsigned char *manager;
static void *pointer_page;

static unsigned char *rec(int i) { return table + g->base + (size_t)i * g->stride; }

static void villager(int i, const char *name, int master_skills) {
    unsigned int k;
    memset(rec(i), 0, g->stride);
    rec(i)[g->active] = 1;
    strcpy((char *)rec(i) + g->name, name);
    for (k = 0; k < g->pref_slots; ++k) {
        *(int *)(rec(i) + g->likes + 4 * k) = -1;
        *(int *)(rec(i) + g->dislikes + 4 * k) = -1;
    }
    for (k = 0; k < g->skill_count; ++k) {
        int v = (int)k < master_skills ? 100 : 10;
        if (g->floats) *(float *)(rec(i) + g->skills + 4 * k) = (float)v;
        else *(int *)(rec(i) + g->skills + 4 * k) = v;
    }
}

/* ---- paths and files ------------------------------------------------------- */

static char root[MAX_PATH], exe_dir[MAX_PATH];
/* "<exe_dir>\Virtual Villagers Fun Patcher Files": where the companions are,
   as in a patched game (native/shared/patcher_files.h). */
static char files_dir[MAX_PATH];

static int locate(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\');
    if (base == NULL) return 0;
    lstrcpynA(exe_dir, exe, (int)(base - exe) + 1);
    _snprintf(files_dir, MAX_PATH, "%s\\" VVFP_PATCHER_FILES_FOLDER, exe_dir);
    files_dir[MAX_PATH - 1] = 0;
    ++base;
    dot = strrchr(base, '.');
    if (dot) *dot = 0;
    _snprintf(root, MAX_PATH, "%s\\LDW\\%s", docs, base);
    root[MAX_PATH - 1] = 0;
    return 1;
}

static void make_dirs(const char *path) {
    char buf[MAX_PATH];
    char *p;
    lstrcpynA(buf, path, MAX_PATH);
    for (p = buf + 3; *p; ++p) {
        if (*p == '\\') { *p = 0; CreateDirectoryA(buf, NULL); *p = '\\'; }
    }
    CreateDirectoryA(buf, NULL);
}

static void remove_tree(const char *dir) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", dir);
    h = FindFirstFileA(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (strcmp(f.cFileName, ".") == 0 || strcmp(f.cFileName, "..") == 0) continue;
            _snprintf(path, MAX_PATH, "%s\\%s", dir, f.cFileName);
            if (f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) continue;
            if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) { remove_tree(path); RemoveDirectoryA(path); }
            else DeleteFileA(path);
        } while (FindNextFileA(h, &f));
        FindClose(h);
    }
}

/* Binary: exactly these bytes (the DLLs read CRLF and LF alike). */
static void write_file(const char *rel, const char *text) {
    char path[MAX_PATH], dir[MAX_PATH], *slash;
    FILE *f;
    _snprintf(path, MAX_PATH, "%s\\%s", root, rel);
    lstrcpynA(dir, path, MAX_PATH);
    slash = strrchr(dir, '\\');
    if (slash) { *slash = 0; make_dirs(dir); }
    f = fopen(path, "wb");
    if (f) { fwrite(text, 1, strlen(text), f); fclose(f); }
}

static char text[1 << 16];
static long read_rel(const char *rel) {
    char path[MAX_PATH];
    FILE *f;
    long n;
    _snprintf(path, MAX_PATH, "%s\\%s", root, rel);
    f = fopen(path, "rb");
    if (f == NULL) { text[0] = 0; return -1; }
    n = (long)fread(text, 1, sizeof text - 1, f);
    text[n] = 0;
    fclose(f);
    return n;
}

static int exists_rel(const char *rel) {
    char path[MAX_PATH];
    _snprintf(path, MAX_PATH, "%s\\%s", root, rel);
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

#define DATA "Virtual Villagers Fun Patcher Data"
#define LOGS "Virtual Villagers Fun Patcher Logs"
#define ELDERS DATA "\\Village Elders\\Village Elders - Save 1.dat"
#define COUNTERS DATA "\\Village Statistics\\Village Statistics - Save 1.dat"
#define ROSTER DATA "\\Village Statistics\\Villagers Counted - Save 1.dat"   /* "Village Roster" before */
#define REPAIRS_DIR LOGS "\\Repairs Made"
#define SUFFIX ".before-v1.35.58-repair"
/* A repair's copies: "Data\Copies Made Before Repairs", at the file's own place (native/shared/save_layout.h). */
#define ELDERS_COPY DATA "\\Copies Made Before Repairs\\" ELDERS
#define COUNTERS_COPY DATA "\\Copies Made Before Repairs\\" COUNTERS
#define DEATHS_DIR (game % 2 ? "Deaths" : "Deaths and Disappearances")

static void write_save_file(void) {
    static const DWORD HEADER[5] = { 12u, 12u, 12u, 24u, 24u };
    static const DWORD LENGTH_AT[5] = { 8u, 8u, 8u, 16u, 16u };
    static const DWORD BUFFER[5] = { 0x0ABDCu, 0x30370u, 0x12F1Cu, 0x1710Cu, 0x17D78u };
    char path[MAX_PATH];
    static const char *STEMS[5] = { "Virtual Villagers", "Virtual Villagers - The Lost Children",
                                    "Virtual Villagers - The Secret City", "Virtual Villagers - The Tree of Life",
                                    "Virtual Villagers - New Believers" };
    DWORD total = HEADER[game - 1] + BUFFER[game - 1];
    unsigned char *data = (unsigned char *)calloc(1, total);
    FILE *f;
    memcpy(data, "ldwg", 4);
    memcpy(data + LENGTH_AT[game - 1], &BUFFER[game - 1], 4);
    strcpy((char *)data + HEADER[game - 1] + vv_village_name_offset(game), "Recon Tribe");
    data[HEADER[game - 1] + vv_village_name_offset(game) + 40] = 0x7F;
    _snprintf(path, MAX_PATH, "%s\\%s1.ldw", root, STEMS[game - 1]);
    make_dirs(root);
    f = fopen(path, "wb");
    if (f) { fwrite(data, 1, total, f); fclose(f); }
    free(data);
}

/* New Believers' snapshots say each villager's faction (population_export.c);
   `faction` overrides it for the next block only (NULL: the line left out, as
   a snapshot written before it had none). */
static const char *next_faction = "Believer";
static int next_faction_set = 0;

/* One villager block of a History snapshot. */
static void history_villager(char *out, size_t cap, int number, const char *name, int value, int masters,
                             int parents) {
    char block[1024];
    unsigned int k;
    size_t len;
    const char *faction = next_faction_set ? next_faction : "Believer";
    next_faction_set = 0;
    _snprintf(block, sizeof block, "Villager %d\r\n  Name: %s\r\n  Age: 500\r\n  Sex: Male\r\n",
              number, name);
    if (game == 5 && faction != NULL) {
        len = strlen(block);
        _snprintf(block + len, sizeof block - len, "  Faction: %s\r\n", faction);
    }
    strcat(block, "  Head: 1\r\n  Body: 2\r\n");
    if (parents) {
        strcat(block, "  Parents:\r\n    Father: Pa\r\n      Head: 3\r\n      Body: 4\r\n"
                      "    Mother: Ma\r\n      Head: 5\r\n      Body: 6\r\n");
    }
    strcat(block, "  Skills:\r\n");
    for (k = 0; k < g->skill_count; ++k) {
        len = strlen(block);
        _snprintf(block + len, sizeof block - len, "    %-10s %d\r\n", SKILLS[k], (int)k < masters ? value : 12);
    }
    strcat(block, "\r\n");
    len = strlen(out);
    _snprintf(out + len, cap - len, "%s", block);
}

static void write_files(int buried, int twins, int chiefs) {
    static char h[32768];
    char line[512];
    int master = g->master;
    int parents = g->father != 0;
    h[0] = 0;
    _snprintf(h, sizeof h, "=== Virtual Villagers -- 2026-09-01 10:00:00 ===\r\nVillage: Recon Tribe (Save 1)\r\n\r\n");
    history_villager(h, sizeof h, 1, "Ghost", 100, 3, parents);
    history_villager(h, sizeof h, 2, "Old", 100, 4, 0);
    history_villager(h, sizeof h, 3, "Alive", 100, 3, 0);
    history_villager(h, sizeof h, 4, "Near", 100, 2, 0);
    history_villager(h, sizeof h, 5, "Edge", master, 3, 0);
    history_villager(h, sizeof h, 6, "Edge2", master - 1, 4, 0);
    /* New Believers: a dead Heathen with every skill mastered, and a villager
       from a snapshot written before the Faction line -- neither proves an
       elder (Heathens never count); elsewhere both are ordinary elders'
       blocks with no faction, so they are given another village. */
    if (game == 5) {
        next_faction = "Heathen"; next_faction_set = 1;
        history_villager(h, sizeof h, 7, "Pagan", 100, 6, 0);
        next_faction = NULL; next_faction_set = 1;
        history_villager(h, sizeof h, 8, "Unsure", 100, 6, 0);
    }
    strcat(h, "\r\n=== Virtual Villagers -- 2026-09-02 10:00:00 ===\r\nVillage: Other Tribe (Save 1)\r\n\r\n");
    history_villager(h, sizeof h, 1, "Stranger", 100, 5, 0);
    strcat(h, "\r\n=== Virtual Villagers -- 2026-09-03 10:00:00 ===\r\nVillage: Recon Tribe (Save 1)\r\n\r\n");
    history_villager(h, sizeof h, 1, "Ghost", 100, 3, parents);
    history_villager(h, sizeof h, 2, "Alive", 100, 3, 0);
    write_file(LOGS "\\Tribe History\\Village History 1.txt", h);

    _snprintf(line, sizeof line, "VVFP VILLAGE ELDERS v2 game=%d\r\ngraves_seen=1\r\nG\t-1\tOld\t\t\t1\t0\r\n", game);
    write_file(ELDERS, line);

    _snprintf(h, sizeof h,
        "Village: Recon Tribe (Save 1)\r\n"
        "Death 1\r\n  Name: Mia\r\n  Age at death: 1000\r\n  Cause of death: Old age\r\n  Grave: Master Builder\r\n"
        "  Epitaph: (none)\r\n\r\n"
        "Death 2\r\n  Name: Lua\r\n  Age at death: 300\r\n  Cause of death: Disease\r\n"
        "  Grave: no grave (never buried: the game removed the body)\r\n\r\n"
        "Death 3\r\n  Name: Rex\r\n  Age at death: 900\r\n  Cause of death: Old age\r\n  Grave: Untrained\r\n\r\n");
    /* In the odd games the logs are where an older build kept them, "Deaths": the reconcile reads them
       there and never moves them (native/shared/save_layout.h). */
    _snprintf(line, sizeof line, LOGS "\\%s\\Virtual Villagers %d Deaths Log 1.txt", DEATHS_DIR, game);
    write_file(line, h);
    _snprintf(h, sizeof h,
        "Village: Other Tribe (Save 1)\r\n"
        "Death 4\r\n  Name: Zed\r\n  Age at death: 1000\r\n  Cause of death: Old age\r\n  Grave: Master Farmer\r\n\r\n");
    _snprintf(line, sizeof line, LOGS "\\%s\\Virtual Villagers %d Deaths Log 2.txt", DEATHS_DIR, game);
    write_file(line, h);
    if (game == 2) {
        _snprintf(h, sizeof h,
            "Village: Recon Tribe (Save 1)\r\n"
            "Conception 1\r\n  Mother: Ann\r\n  Babies in pregnancy: 2\r\n\r\n"
            "Conception 2\r\n  Mother: Ann\r\n  Babies in pregnancy: 1\r\n\r\n"
            "Conception 3\r\n  Mother: Ann\r\n  Babies nursing: 2\r\n\r\n"
            "Village: Other Tribe (Save 1)\r\n"
            "Conception 4\r\n  Mother: Zoe\r\n  Babies in pregnancy: 2\r\n\r\n");
        write_file(LOGS "\\Births and Conceptions\\Virtual Villagers 2 Births and Conceptions Log 1.txt", h);
    }
    {
        char c[512];
        c[0] = 0;
        _snprintf(c, sizeof c, "VVFP VILLAGE STATISTICS v1 game=%d\n", game);
        if (game == 3) {
            _snprintf(c + strlen(c), sizeof c - strlen(c), "chiefs_robed=%d\nmigrated.chiefs_robed=0\n", chiefs);
        }
        if (game == 2) {
            _snprintf(c + strlen(c), sizeof c - strlen(c), "migrated.twins_birthed=0\n");
        }
        _snprintf(c + strlen(c), sizeof c - strlen(c), "migrated.villagers_buried=1\n");
        if (game == 2) {
            _snprintf(c + strlen(c), sizeof c - strlen(c), "twins_birthed=%d\n", twins);
        }
        _snprintf(c + strlen(c), sizeof c - strlen(c), "villagers_buried=%d\n", buried);
        write_file(COUNTERS, c);
    }
    write_file(ROSTER, "VVFP VILLAGE ROSTER v1\r\n0\tAlive\t-\r\n1\tAnn\t-\r\n2\tBo\t-\r\n");
    write_save_file();
}

static void clean(void) {
    char sub[MAX_PATH];
    _snprintf(sub, MAX_PATH, "%s\\" LOGS, root);
    remove_tree(sub);
    RemoveDirectoryA(sub);
    _snprintf(sub, MAX_PATH, "%s\\" DATA, root);
    remove_tree(sub);
    RemoveDirectoryA(sub);
}

/* A snapshot of every file the reconcile may touch. */
static char before_elders[4096], before_counters[4096];
static void snapshot(void) {
    read_rel(ELDERS);
    lstrcpynA(before_elders, text, sizeof before_elders);
    read_rel(COUNTERS);
    lstrcpynA(before_counters, text, sizeof before_counters);
}
static int unchanged(void) {
    int same;
    read_rel(ELDERS);
    same = strcmp(before_elders, text) == 0;
    read_rel(COUNTERS);
    return same && strcmp(before_counters, text) == 0 && !exists_rel(ELDERS_COPY SUFFIX) && !exists_rel(COUNTERS_COPY SUFFIX)
        && !exists_rel(REPAIRS_DIR);
}

static long long counter(const char *key) {
    char want[64];
    const char *at;
    read_rel(COUNTERS);
    _snprintf(want, sizeof want, "\n%s=", key);
    at = strstr(text, want);
    return at != NULL ? _atoi64(at + strlen(want)) : -1;
}

static void place_game(void) {
    unsigned char *at = module_base + g->rva;
    if (g->is_pointer) {
        pointer_page = VirtualAlloc((void *)((uintptr_t)at & ~0xFFFu), 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        table = (unsigned char *)VirtualAlloc(NULL, g->base + g->slots * g->stride + 0x1000, MEM_RESERVE | MEM_COMMIT,
                                              PAGE_READWRITE);
        *(unsigned char **)at = table;
    } else {
        table = at;
        memset(table, 0, g->base + g->slots * g->stride);
    }
    manager = (unsigned char *)calloc(1, 0x40000);
    strcpy((char *)manager + 8 + vv_village_name_offset(game), "Recon Tribe");
    {
        /* One grave in the memorial. */
        unsigned char *memorial = g->memorial_in_manager ? manager + g->memorial : module_base + g->memorial;
        memset(memorial, 0, 500u * g->memorial_stride > 0x10000 ? 0x10000 : 500u * g->memorial_stride);
        if (g->memorial_in_manager) memset(memorial, 0, 50u * g->memorial_stride);
        *(int *)(memorial + g->memorial_occupied) = 1;
    }
}

static void unplace_game(void) {
    if (g->is_pointer) {
        VirtualFree(table, 0, MEM_RELEASE);
        VirtualFree(pointer_page, 0, MEM_RELEASE);
    }
    free(manager);
}

int main(int argc, char **argv) {
    harness_ldw_tree_begin();
    char path[MAX_PATH], prompt[1536];
    HMODULE dll;
    scan_t scan;
    repair_t repair;
    save_t save;
    now_t now;
    int *rewrites;
    unsigned char **world;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 3) {
        printf("usage: reconcile_harness <statistics test dll> <save reset dll>\n");
        return 2;
    }
    if (!locate()) return 2;
    module_base = (unsigned char *)GetModuleHandleW(NULL);
    if (VirtualAlloc(module_base + 0x100000u, 0x300000u, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) == NULL) {
        printf("cannot place the tables\n");
        return 2;
    }
    CreateDirectoryA(files_dir, NULL);
    _snprintf(path, MAX_PATH, "%s\\VVFP Statistics Export.dll", files_dir);
    if (!CopyFileA(argv[1], path, FALSE)) { printf("cannot copy %s\n", argv[1]); return 2; }
    /* By full path in the patcher's folder, as the companions load each other. */
    dll = vvfp_load_patcher_dll("VVFP Statistics Export.dll");
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", files_dir);
    if (!CopyFileA(argv[2], path, FALSE)) { printf("cannot copy %s\n", argv[2]); return 2; }
    scan = dll ? (scan_t)GetProcAddress(dll, "VvfpStatisticsScanReconcile") : NULL;
    repair = dll ? (repair_t)GetProcAddress(dll, "VvfpStatisticsRepairReconcile") : NULL;
    save = dll ? (save_t)GetProcAddress(dll, "VvfpStatisticsTestSave") : NULL;
    now = dll ? (now_t)GetProcAddress(dll, "VvfpStatisticsRepairReconcileNow") : NULL;
    rewrites = dll ? (int *)GetProcAddress(dll, "VvfpStatisticsTestLogRewrites") : NULL;
    world = dll ? (unsigned char **)GetProcAddress(dll, "VvfpStatisticsTestWorld") : NULL;
    if (scan == NULL || repair == NULL || save == NULL || now == NULL || rewrites == NULL || world == NULL) {
        printf("missing exports\n");
        return 2;
    }

    for (game = 1; game <= 5; ++game) {
        int elders_expected = game != 2;
        int expect = 1 + (elders_expected ? 2 : 0) + (game == 2) + (game == 3);
        int found;
        g = &LAYOUTS[game - 1];
        printf("Virtual Villagers %d\n", game);
        clean();
        place_game();
        villager(0, "Alive", 3);
        villager(1, "Ann", 0);
        villager(2, "Bo", 1);
        if (g->chief) rec(2)[g->chief] = 1;
        if (g->tribe) {
            villager(3, "Chief", 6);
            rec(3)[g->tribe] = 1;
        }
        write_files(1, 0, 0);
        snapshot();
        /* The world object the load-time scan reads A New Home's and The Lost
           Children's memorial from (the game's own global, in the game). */
        *world = manager;

        if (g->memorial_in_manager) {
            /* 0. A memorial with more graves than the Deaths log shows: the
               scan at the load counts it (Codex, #536). */
            unsigned char *memorial = manager + g->memorial;
            *(int *)(memorial + g->memorial_stride + g->memorial_occupied) = 1;
            *(int *)(memorial + 2u * g->memorial_stride + g->memorial_occupied) = 1;
            found = scan(game, 1, prompt, (int)sizeof prompt);
            CHECK(strstr(prompt, "the Deaths log and the graves show 3 burials") != NULL,
                  "the load-time scan counts the memorial's 3 graves (the world object, read at the load)");
            *(int *)(memorial + g->memorial_stride + g->memorial_occupied) = 0;
            *(int *)(memorial + 2u * g->memorial_stride + g->memorial_occupied) = 0;
        }

        /* 1. The scan. */
        found = scan(game, 1, prompt, (int)sizeof prompt);
        printf("%s", prompt);
        CHECK(found == expect, "the scan finds %d change(s) (got %d)", expect, found);
        CHECK(strstr(prompt, "Villagers Buried is 1, but the Deaths log and the graves show 2 burials. It will be "
                             "raised to 2.") != NULL,
              "Villagers Buried: two Death records with a grave, not the \"no grave\" one nor another village's");
        if (elders_expected) {
            CHECK(strstr(prompt, "- 2 villagers the Village History log shows as Village Elders") != NULL,
                  "Village Elders: Ghost and Edge (not Old, on the list; Alive, alive; Near, Edge2, Stranger)");
        } else {
            CHECK(strstr(prompt, "Village Elders") == NULL,
                  "Village Elders: none (the game counts its own)");
        }
        if (game == 2) {
            CHECK(strstr(prompt, "Twins Birthed is 0, but the Births log records 2 twin pregnancies") != NULL,
                  "Twins Birthed: this village's two twin conceptions");
        }
        if (game == 3) {
            CHECK(strstr(prompt, "Chiefs Robed is 0, but a robed Tribal Chief lives") != NULL,
                  "Chiefs Robed: a robed chief lives");
        }
        CHECK(unchanged(), "the scan writes nothing");

        /* 2. No answer; Not now.  A save updates the elders file itself (the
           living elder, Alive, gets her open line): that is the save's, not
           the reconcile's. */
        save(game, 1, manager);
        {
            int no_lines;
            read_rel(ELDERS);
            no_lines = strstr(text, "\tGhost\t") == NULL && strstr(text, "\tEdge\t") == NULL;
            read_rel(COUNTERS);
            CHECK(no_lines && strcmp(before_counters, text) == 0
                  && !exists_rel(ELDERS_COPY SUFFIX) && !exists_rel(COUNTERS_COPY SUFFIX) && !exists_rel(REPAIRS_DIR),
                  "a save with no answer makes none of the reconcile's changes");
        }
        snapshot();
        repair(game, 1, 0);
        save(game, 1, manager);
        CHECK(unchanged(), "a save after \"Not now\" changes nothing: no counter, no line, no backup, no Repairs log");
        CHECK(scan(game, 1, prompt, (int)sizeof prompt) == expect, "...and the next load asks again");

        /* 3. Repair. */
        repair(game, 1, 1);
        CHECK(save(game, 1, manager) == 1, "Repair: the save makes the changes");
        CHECK(counter("villagers_buried") == 2, "Villagers Buried raised to exactly 2");
        if (game == 2) CHECK(counter("twins_birthed") == 2, "Twins Birthed raised to exactly 2");
        if (game == 3) CHECK(counter("chiefs_robed") == 1, "Chiefs Robed raised to exactly 1");
        read_rel(COUNTERS_COPY SUFFIX);
        CHECK(strcmp(text, before_counters) == 0, "the counters file was backed up first, byte for byte");
        read_rel(ELDERS);
        if (elders_expected) {
            char ghost[96];
            _snprintf(ghost, sizeof ghost, "E\t-1\tGhost\t%s\t%s\t0\t0\r\n", g->father ? "Pa" : "", g->father ? "Ma" : "");
            CHECK(strstr(text, ghost) != NULL && strstr(text, "E\t-1\tEdge\t\t\t0\t0\r\n") != NULL,
                  "the elders file gains Ghost%s and Edge, as closed lines", g->father ? " (Pa, Ma)" : "");
            CHECK(strstr(text, "\tNear\t") == NULL && strstr(text, "\tEdge2\t") == NULL && strstr(text, "\tStranger\t") == NULL
                  && strstr(strstr(text, "\tOld\t") + 1, "\tOld\t") == NULL,
                  "no line for Near (2 masteries), Edge2 (under the threshold), Stranger (another village) or a second Old");
            if (game == 5) {
                CHECK(strstr(text, "\tPagan\t") == NULL && strstr(text, "\tUnsure\t") == NULL,
                      "New Believers: no line for Pagan (a Heathen) or Unsure (no Faction line: proves nothing)");
            }
            CHECK(strstr(text, "G\t-1\tOld\t\t\t1\t0") != NULL, "the existing line is kept as it was");
            {
                int ghosts = 0;
                const char *p = text;
                while ((p = strstr(p, "\tGhost\t")) != NULL) { ++ghosts; ++p; }
                CHECK(ghosts == 1, "Ghost, in two snapshots, gets one line");
            }
            CHECK(exists_rel(ELDERS_COPY SUFFIX), "the elders file was backed up first");
        } else {
            CHECK(!exists_rel(ELDERS_COPY SUFFIX), "the elders file is not touched (nothing to add)");
        }
        {
            char repairs[MAX_PATH];
            _snprintf(repairs, MAX_PATH, REPAIRS_DIR "\\Virtual Villagers %d Repairs Log 1.txt", game);
            read_rel(repairs);
            printf("%s", text);
            CHECK(strncmp(text, "Village: Recon Tribe (Save 1)\r\nRepair 1\r\n", 41) == 0
                  && strstr(text, "  Villagers Buried raised: 1 -> 2 (the Deaths log and the graves)\r\n") != NULL
                  && strstr(text, "  Backup: Village Statistics - Save 1.dat" SUFFIX "\r\n") != NULL
                  && (!elders_expected || (strstr(text, "  Village Elder added: Ghost") != NULL
                                           && strstr(text, "  Village Elder added: Edge -- Master in 3 or more skills") != NULL
                                           && strstr(text, "  Backup: Village Elders - Save 1.dat" SUFFIX "\r\n") != NULL)),
                  "every change is listed in the Repairs log, under the village's header, with the backups");
        }

        /* 4. Exactly once. */
        snapshot();
        CHECK(scan(game, 1, prompt, (int)sizeof prompt) == 0, "the scan then finds nothing");
        repair(game, 1, 1);
        save(game, 1, manager);
        read_rel(ELDERS);
        {
            int same = strcmp(before_elders, text) == 0;
            read_rel(COUNTERS);
            CHECK(same && strcmp(before_counters, text) == 0 && !exists_rel(COUNTERS_COPY SUFFIX "-2")
                  && !exists_rel(ELDERS_COPY SUFFIX "-2"), "another save changes nothing and makes no second backup");
        }

        /* 5. Never lowers. */
        clean();
        write_files(9, 7, 3);
        snapshot();
        found = scan(game, 1, prompt, (int)sizeof prompt);
        CHECK(strstr(prompt, "Villagers Buried") == NULL && strstr(prompt, "Twins") == NULL
              && strstr(prompt, "Chiefs") == NULL && found == (elders_expected ? 2 : 0),
              "counters above what the logs prove are never lowered (only the elders are asked about)");
        repair(game, 1, 1);
        save(game, 1, manager);
        CHECK(counter("villagers_buried") == 9 && (game != 2 || counter("twins_birthed") == 7)
              && (game != 3 || counter("chiefs_robed") == 3), "...and stay as they were after Repair");

        /* 6. Another village's files. */
        clean();
        write_files(1, 0, 0);
        write_file(ROSTER, "VVFP VILLAGE ROSTER v1\r\n0\tXena\t-\r\n1\tYuri\t-\r\n2\tZack\t-\r\n");
        CHECK(scan(game, 1, prompt, (int)sizeof prompt) == 0,
              "another village's files (the roster shares nobody): nothing is asked");

        /* 7. Repair answered right after the quit save. */
        *rewrites = 0;
        clean();
        write_files(1, 0, 0);
        repair(game, 1, 0);
        save(game, 1, manager);                       /* the quit save: no answer yet */
        snapshot();
        CHECK(counter("villagers_buried") == 1 && !exists_rel(COUNTERS_COPY SUFFIX),
              "the quit save, with no answer yet, changes nothing");
        CHECK(now(game, 2) == 0 && unchanged(), "Repair at the quit does nothing for a slot the last save was not");
        CHECK(now(game, 1) == 1, "Repair right after the quit save: done there and then");
        CHECK(counter("villagers_buried") == 2 && (game != 2 || counter("twins_birthed") == 2)
              && (game != 3 || counter("chiefs_robed") == 1),
              "...the same changes a save after Repair makes");
        read_rel(ELDERS);
        if (elders_expected) {
            CHECK(strstr(text, "\tGhost\t") != NULL && strstr(text, "E\t-1\tEdge\t\t\t0\t0\r\n") != NULL
                  && exists_rel(ELDERS_COPY SUFFIX), "...the elders file gains Ghost and Edge, backed up first");
        } else {
            CHECK(!exists_rel(ELDERS_COPY SUFFIX), "...the elders file is not touched (nothing to add)");
        }
        {
            char repairs[MAX_PATH];
            int listed, backed;
            _snprintf(repairs, MAX_PATH, REPAIRS_DIR "\\Virtual Villagers %d Repairs Log 1.txt", game);
            read_rel(repairs);
            listed = strstr(text, "  Villagers Buried raised: 1 -> 2 (the Deaths log and the graves)\r\n") != NULL;
            read_rel(COUNTERS_COPY SUFFIX);
            backed = strstr(text, "villagers_buried=1") != NULL;
            CHECK(listed && backed, "...listed in the Repairs log, the counters file backed up first");
        }
        CHECK(*rewrites == 1, "...and the Village Statistics log is written again, to show them");
        snapshot();
        {
            int again = now(game, 1), same;
            read_rel(ELDERS);
            same = strcmp(before_elders, text) == 0;
            read_rel(COUNTERS);
            same = same && strcmp(before_counters, text) == 0 && !exists_rel(COUNTERS_COPY SUFFIX "-2")
                   && !exists_rel(ELDERS_COPY SUFFIX "-2");
            CHECK(again == 1 && same && scan(game, 1, prompt, (int)sizeof prompt) == 0 && *rewrites == 1,
                  "...a second Repair changes nothing (no file, no second backup, not the log), and the scan finds"
                  " nothing left");
        }

        /* 7b. An older build's "Repairs" folder beside "Repairs Made": the record is written in the
           new folder and numbered after the older folder's own file of the same number, as A New
           Home's parentage repair numbers it (save_layout.h vv_layout_older_repairs) -- never a
           second "Repair 1". */
        clean();
        write_files(1, 0, 0);
        {
            char old_log[MAX_PATH], repairs[MAX_PATH], made[MAX_PATH];
            _snprintf(old_log, MAX_PATH, LOGS "\\Repairs\\Virtual Villagers %d Repairs Log 1.txt", game);
            write_file(old_log, "Village: Recon Tribe (Save 1)\r\nRepair 1\r\n  Date: 2026-10-04 10:00:00\r\n\r\n"
                                "Repair 2\r\n  Date: 2026-10-04 10:00:01\r\n\r\nRepair 3\r\n  Date: 2026-10-04 10:00:02\r\n\r\n");
            _snprintf(made, MAX_PATH, "%s\\" REPAIRS_DIR, root);
            make_dirs(made);
            repair(game, 1, 1);
            save(game, 1, manager);
            _snprintf(repairs, MAX_PATH, REPAIRS_DIR "\\Virtual Villagers %d Repairs Log 1.txt", game);
            read_rel(repairs);
            CHECK(strstr(text, "\r\nRepair 4\r\n") != NULL && strstr(text, "Repair 1\r\n") == NULL,
                  "an older build's Repairs folder beside Repairs Made: the repair is Repair 4, after its Repair 3");
        }

        /* 8. Both "Deaths" and "Deaths and Disappearances" (Codex, #577): the
           old folder cannot be moved over the new one, so both are read, and
           a record found in both is one burial. */
        clean();
        write_files(1, 0, 0);
        scan(game, 1, prompt, (int)sizeof prompt);
        CHECK(game % 2 ? exists_rel(LOGS "\\Deaths") && !exists_rel(LOGS "\\Deaths and Disappearances")
                       : !exists_rel(LOGS "\\Deaths") && exists_rel(LOGS "\\Deaths and Disappearances"),
              "one folder: an older build's \"Deaths\" is read where it is, never moved, and no other folder is made");
        {
            char other[MAX_PATH];
            _snprintf(other, MAX_PATH, LOGS "\\%s\\Virtual Villagers %d Deaths Log 1.txt",
                      game % 2 ? "Deaths and Disappearances" : "Deaths", game);
            clean();
            write_files(1, 0, 0);
            /* Mia's record again, word for word (the same record), and a burial only this folder holds. */
            write_file(other,
                "Village: Recon Tribe (Save 1)\r\n"
                "Death 1\r\n  Name: Mia\r\n  Age at death: 1000\r\n  Cause of death: Old age\r\n  Grave: Master Builder\r\n"
                "  Epitaph: (none)\r\n\r\n"
                "Death 5\r\n  Name: Kai\r\n  Age at death: 800\r\n  Cause of death: Old age\r\n  Grave: Master Farmer\r\n\r\n");
            scan(game, 1, prompt, (int)sizeof prompt);
            CHECK(strstr(prompt, "Villagers Buried is 1, but the Deaths log and the graves show 3 burials.") != NULL
                  && exists_rel(LOGS "\\Deaths") && exists_rel(LOGS "\\Deaths and Disappearances"),
                  "both folders: Mia, Rex and Kai are 3 burials -- the old folder's records are read, Mia's twice-kept"
                  " record counts once");
        }

        unplace_game();
    }
    clean();
    FreeLibrary(dll);
    _snprintf(path, MAX_PATH, "%s\\VVFP Statistics Export.dll", files_dir);
    DeleteFileA(path);
    if (GetModuleHandleA("VVFP Save Reset.dll")) FreeLibrary(GetModuleHandleA("VVFP Save Reset.dll"));
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", files_dir);
    DeleteFileA(path);
    RemoveDirectoryA(files_dir);   /* only when empty */
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
