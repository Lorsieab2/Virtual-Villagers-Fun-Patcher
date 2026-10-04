/* Runtime harness for the "Arrived" records and their one-time backfill.
   32-bit only.

   Drives the TEST build of "VVFP Cause of Death.dll" and the shipped "VVFP
   Parentage Export.dll" and "VVFP Save Reset.dll" (all copied beside this
   executable under their shipped names, as in a game), in all five games'
   geometry, against real files under Documents\LDW\<this exe's basename>\,
   which harness_ldw_tree.h leaves as it found them.

   Each game, a village "Arrival Tribe" in slot 1:
     0 Huata  1090  no parents, no record             (a founder of long ago)
     1 Nishi   900  born here: a Birth record (A New Home), parents on her
                    record (the other games)
     2 Silko   663  no parents, no record             (another village's log
                                                        has an Arrived Silko)
     3 Thabo  1003  an Arrived record appended by hand, in the record's own
                    shape ("How: Custom Island Event")
     4 Dup     500  \  two alike (name, head, body); the log has one
     5 Dup     500  /  Arrived Dup
     6 Hea     400  New Believers: a Heathen (never a villager); elsewhere a
                    villager with parents
   and the Births and Conceptions log an older build wrote.
     0. The scan counts Huata, Silko and the second Dup and writes nothing (no
        log line, no marker); no answer and "Not now" record nothing at the
        save.  In A New Home without Show Parents (no Birth records) it finds
        nothing to ask about.
     1. After Repair, the save writes exactly Huata, Silko, the second Dup and
        Ponui (who arrived unseen since the last save), numbered on from the
        game's Arrived records, in the frozen format, "How: unknown" and the
        "Recorded afterwards" note; Thabo is not recorded again; Ponui is NOT
        an Unaccounted record; the marker is written.
     2. A second save and a new session write nothing; the scan says 0.
     3. Seen live: a newcomer from an island event ("How: unknown", the age
        when it arrived), the Custom Island Event's new villager ("How:
        Custom Island Event"), one who arrives and is buried before the save
        (recorded at the departure); a birth is never an arrival (the Births
        log's note; A New Home's child-creation call even without it); a
        Heathen made by the creator is not; a Heathen converted to a believer
        is ("Converted from the Heathens").  None of them is Unaccounted.
     4. Start Over deletes the marker; the new village's founders, made by the
        seeding, get "How: Founder" at its first save (and the seeding's
        records in a village saved before -- a load overwrites them -- never
        do); one not seen made is offered by the backfill.
   And each game's markers (cod_arrival_sites.inc): a birth path is never an
   arrival, a stock event's newcomer is named by the event.

   Usage:  arrival_harness.exe "<parentage dll>" "<cause of death test dll>" "<save reset dll>"
   Exit code 0 when every check passes. */
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "village_identity.h"
#include "save_reset.h"
#include "../shared/harness_ldw_tree.h"

static int failures;
#define CHECK(cond, ...) do { if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); failures++; } } while (0)

typedef int (__stdcall *ensure_village_t)(int, const char *, const void *);
typedef int (__stdcall *setup_t)(int, const void *, void *);
typedef void (__stdcall *save_done_t)(int, const void *);
typedef void (__stdcall *reset_t)(int, int);
typedef int (__stdcall *scan_t)(int, int);
typedef void (__stdcall *repair_t)(int, int, int);
typedef void (__stdcall *created_t)(int, unsigned int);
typedef void (__stdcall *void_t)(void);
typedef void (__stdcall *int_t)(int);
typedef void (__stdcall *note_t)(int, const void *);
typedef void (__stdcall *arrived_by_t)(int, int, const char *);

/* Each game's villager record, as both DLLs' tables have it. */
struct layout {
    int game;
    unsigned int stride, slots, base, active, age, head, body, name, name_cap, health, sex;
    unsigned int rva;
    int is_pointer;
    unsigned int likes, dislikes, pref_slots, father;
};
static const struct layout LAYOUTS[5] = {
    { 1, 0x3D8,  256, 0,    0x28,   0x348,  0x360,  0x364,  0x370,  0x1C, 0x344,  0x350,  0x8B614u,  1,
      0x398, 0x3A8, 4, 0 },
    { 2, 0xE48C, 256, 0,    0x30,   0x530,  0x548,  0x54C,  0x564,  0x18, 0x52C,  0x538,  0x99F24u,  1,
      0x5F0, 0x6E8, 62, 0x57D },
    { 3, 0x1F8C, 150, 0x14, 0xF10,  0xDC4,  0xDF0,  0xDF4,  0xDD4,  0x19, 0xE78,  0xDC8,  0x19E110u, 0,
      0xFB4, 0xFC0, 3, 0xDF8 },
    { 4, 0x2E3C, 150, 0x44, 0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1C40, 0x1B90, 0x10E568u, 0,
      0x1E60, 0x1E6C, 3, 0x1BC0 },
    { 5, 0x2F44, 150, 0x48, 0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B9C, 0x19, 0x1C40, 0x1B90, 0x154148u, 0,
      0x1F5C, 0x1F68, 3, 0x1BC0 },
};
#define VV5_FACTION 0x1CEC

/* One marker per game from cod_arrival_sites.inc: a birth, a founder, a
   stock event and its label, as the creators' hook would find them. */
static const struct { unsigned int birth, founder, event; const char *label; } MARK[5] = {
    { 0x42EFD5u, 0x41C50Eu, 0x42C3F4u, "A Mysterious Crate (watertight)" },
    { 0x44F602u, 0x4252F7u, 0x43446Cu, "Old Friends" },
    { 0x45FFD2u, 0x41B7E4u, 0x414DB4u, "The Canoe from the Other Side" },
    { 0x467D92u, 0x43B929u, 0x4148D4u, "The Canoe from the Other Side" },
    { 0x471EA2u, 0x43E317u, 0x415559u, "News From Another Tribe" },
};

static const struct layout *g;
static int game;
static unsigned char *table;
static void *pointer_page;

static unsigned char *rec(int i) { return table + g->base + (size_t)i * g->stride; }

static int alloc_game(void) {
    unsigned char *at = (unsigned char *)((uintptr_t)GetModuleHandleW(NULL) + g->rva);
    unsigned int size = g->base + g->slots * g->stride;
    if (g->is_pointer) {
        pointer_page = VirtualAlloc((void *)((uintptr_t)at & ~0xFFFu), 0x1000, MEM_RESERVE | MEM_COMMIT,
                                    PAGE_READWRITE);
        table = (unsigned char *)VirtualAlloc(NULL, size + 0x1000, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (table == NULL || pointer_page == NULL) return 0;
        *(unsigned char **)at = table;
    } else {
        if (VirtualAlloc((void *)((uintptr_t)at & ~0xFFFFu), size + ((uintptr_t)at & 0xFFFFu),
                         MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE) == NULL) {
            return 0;
        }
        table = at;
    }
    return 1;
}

static void free_game(void) {
    if (g->is_pointer) {
        VirtualFree(table, 0, MEM_RELEASE);
        VirtualFree(pointer_page, 0, MEM_RELEASE);
    } else {
        VirtualFree((void *)((uintptr_t)table & ~0xFFFFu), 0, MEM_RELEASE);
    }
    table = NULL;
}

/* A living villager; `parents` names a father on the record (the games that
   keep one). */
static void villager(int i, const char *name, int age, int head, int body, int parents) {
    unsigned int k;
    memset(rec(i), 0, g->stride);
    rec(i)[g->active] = 1;
    *(int *)(rec(i) + g->health) = 90;
    *(int *)(rec(i) + g->age) = age;
    *(int *)(rec(i) + g->head) = head;
    *(int *)(rec(i) + g->body) = body;
    *(int *)(rec(i) + g->sex) = 1;
    for (k = 0; k < g->pref_slots; ++k) {
        *(int *)(rec(i) + g->likes + 4 * k) = -1;
        *(int *)(rec(i) + g->dislikes + 4 * k) = -1;
    }
    strncpy((char *)rec(i) + g->name, name, g->name_cap - 1);
    if (parents && g->father != 0) {
        strcpy((char *)rec(i) + g->father, "Kito");
    }
}

/* ---- Paths ------------------------------------------------------------------ */

static char root[MAX_PATH];
static char exe_dir[MAX_PATH];

static int locate(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return 0;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return 0;
    base = strrchr(exe, '\\');
    if (base == NULL) return 0;
    lstrcpynA(exe_dir, exe, (int)(base - exe) + 1);
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

static void write_text(const char *path, const char *text) {
    char dir[MAX_PATH], *slash;
    FILE *f;
    lstrcpynA(dir, path, MAX_PATH);
    slash = strrchr(dir, '\\');
    if (slash) { *slash = 0; make_dirs(dir); }
    f = fopen(path, "w");                 /* text mode: CRLF, as the DLLs write */
    if (f) { fwrite(text, 1, strlen(text), f); fclose(f); }
}

static char text[1 << 17];
static long read_into(const char *path) {
    FILE *f = fopen(path, "rb");
    long n;
    if (f == NULL) { text[0] = 0; return -1; }
    n = (long)fread(text, 1, sizeof text - 1, f);
    text[n] = 0;
    fclose(f);
    return n;
}

static void births_path(int number, char *out) {
    _snprintf(out, MAX_PATH,
              "%s\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions\\Virtual Villagers %d Births and Conceptions Log %d.txt",
              root, game, number);
}

static void unaccounted_path(char *out) {
    _snprintf(out, MAX_PATH,
              "%s\\Virtual Villagers Fun Patcher Logs\\Unaccounted Villagers\\Virtual Villagers %d Unaccounted Villagers Log 1.txt",
              root, game);
}

static void marker_path(char *out) {
    _snprintf(out, MAX_PATH,
              "%s\\Virtual Villagers Fun Patcher Data\\Arrivals\\Virtual Villagers %d Arrivals Recorded - Save 1.dat",
              root, game);
}

static int count_of(const char *haystack, const char *needle) {
    int n = 0;
    const char *at = haystack;
    while ((at = strstr(at, needle)) != NULL) { ++n; at += strlen(needle); }
    return n;
}

/* The record "Arrived <number>" whose name follows. */
static const char *arrived(int number, const char *name) {
    char want[160];
    _snprintf(want, sizeof want, "Arrived %d\r\n  Name: %s\r\n", number, name);
    return strstr(text, want);
}

/* Whether the record whose name follows holds `needle` (up to its closing
   blank line). */
static int record_has(const char *name, const char *needle) {
    char want[96];
    const char *at, *end, *hit;
    _snprintf(want, sizeof want, "  Name: %s\r\n", name);
    at = strstr(text, want);
    if (at == NULL) return 0;
    end = strstr(at, "\r\n\r\n");
    hit = strstr(at, needle);
    return hit != NULL && end != NULL && hit <= end + 2;
}

static int file_exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

/* ---- The DLLs ------------------------------------------------------------- */

static HMODULE parentage, cause;
static ensure_village_t ensure_village;
static setup_t setup;
static save_done_t save_done;
static reset_t reset;
static scan_t scan_arrivals;
static repair_t repair_arrivals;
static created_t created;
static void_t arrival_tick;
static int_t vv1_births;
static int_t departed;
static note_t note_birth;
static arrived_by_t arrived_by;

static int __stdcall host_slot(void) { return 1; }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static void load(void) {
    char path[MAX_PATH];
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", exe_dir);
    parentage = LoadLibraryA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
    cause = LoadLibraryA(path);
    if (parentage == NULL || cause == NULL) { printf("cannot load the DLLs\n"); exit(2); }
    ensure_village = (ensure_village_t)GetProcAddress(parentage, "EnsureParentageLogForVillage");
    setup = (setup_t)GetProcAddress(cause, "VvfpCauseTestSetup");
    save_done = (save_done_t)GetProcAddress(cause, "VvfpCauseTestSaveDone");
    reset = (reset_t)GetProcAddress(cause, "VvfpCauseVillageReset");
    scan_arrivals = (scan_t)GetProcAddress(cause, "VvfpCauseScanArrivals");
    repair_arrivals = (repair_t)GetProcAddress(cause, "VvfpCauseRepairArrivals");
    created = (created_t)GetProcAddress(cause, "VvfpCauseTestCreated");
    arrival_tick = (void_t)GetProcAddress(cause, "VvfpCauseTestArrivalTick");
    vv1_births = (int_t)GetProcAddress(cause, "VvfpCauseTestVv1Births");
    departed = (int_t)GetProcAddress(cause, "VvfpCauseTestDeparted");
    note_birth = (note_t)GetProcAddress(cause, "VvfpCauseNoteArrival");
    arrived_by = (arrived_by_t)GetProcAddress(cause, "VvfpCauseArrivedBy");
    if (!ensure_village || !setup || !save_done || !reset || !scan_arrivals || !repair_arrivals || !created
        || !arrival_tick || !vv1_births || !departed || !note_birth || !arrived_by
        || GetProcAddress(parentage, "RecordArrivalsMissingFromLog") == NULL) {
        printf("missing exports\n");
        exit(2);
    }
    setup(game, &host, table);
    vv1_births(1);
}

static void unload(void) {
    int guard;
    FreeLibrary(cause);
    for (guard = 0; guard < 8 && GetModuleHandleA("VVFP Parentage Export.dll") != NULL; ++guard) {
        FreeLibrary(GetModuleHandleA("VVFP Parentage Export.dll"));
    }
    cause = parentage = NULL;
}

static unsigned char *save_buffer(const char *name) {
    unsigned int at = vv_village_name_offset(game);
    unsigned char *buffer = (unsigned char *)calloc(1, at + VV_VILLAGE_NAME_MAX + 16);
    strcpy((char *)buffer + at, name);
    return buffer;
}

static void stand_in(const char *name, int present) {
    char path[MAX_PATH];
    _snprintf(path, MAX_PATH, "%s\\%s", exe_dir, name);
    if (present) {
        HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
        if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
    } else {
        DeleteFileA(path);
    }
}

#define VILLAGE "Village: Arrival Tribe (Save 1)\n"

/* The Births and Conceptions log an older build wrote, with the record
   appended by hand for Thabo and one for the first Dup; and another
   village's file with an Arrived Silko. */
static void write_old_logs(void) {
    char path[MAX_PATH];
    births_path(1, path);
    write_text(path,
        "Village: Arrival Tribe (Save 1)\n"
        "Conception 1\n  Mother: Chika\n    Age at conception: 527\n    Head: 19\n    Body: 17\n"
        "    Likes: (none)\n    Dislikes: (none)\n  Father: Kito\n    Age at conception: 600\n"
        "    Head: 0\n    Body: 18\n    Likes: (none)\n    Dislikes: (none)\n  Babies in pregnancy: 1\n\n"
        "Birth\n  Child: Nishi\n    Head: 7\n    Body: 3\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: Kito\n    Head: 0\n    Body: 18\n\n"
        "Birth\n  Child: Hea\n    Head: 9\n    Body: 9\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Skills:\n    Breeding   0\n"
        "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: Kito\n    Head: 0\n    Body: 18\n\n"
        "Arrived 1\n  Name: Thabo\n  Age at arrival: 980 (about; hand-written)\n  Sex: Male\n"
        "  Head: 16\n  Body: 12\n  How: Custom Island Event\n"
        "  Note: Recorded afterwards (arrived before this log existed)\n\n"
        "Arrived 3\n  Name: Dup\n  Age at arrival: 480\n  Sex: Male\n  Head: 2\n  Body: 2\n"
        "  Likes: (none)\n  Dislikes: (none)\n  How: unknown\n\n");
    births_path(2, path);
    write_text(path,
        "Village: Other Tribe (Save 2)\n"
        "Arrived 2\n  Name: Silko\n  Age at arrival: 600\n  Sex: Male\n  Head: 4\n  Body: 14\n"
        "  Likes: (none)\n  Dislikes: (none)\n  How: unknown\n\n");
}

/* The slot's own save, as the game writes it: the scan at load names the
   village from it (through "VVFP Save Reset.dll", SavedVillageHeader). */
static void write_save_file(void) {
    static const DWORD HEADER[5] = { 12u, 12u, 12u, 24u, 24u };
    static const DWORD LENGTH_AT[5] = { 8u, 8u, 8u, 16u, 16u };
    static const DWORD BUFFER[5] = { 0x0ABDCu, 0x30370u, 0x12F1Cu, 0x1710Cu, 0x17D78u };
    char path[MAX_PATH];
    DWORD total = HEADER[game - 1] + BUFFER[game - 1];
    unsigned char *data = (unsigned char *)calloc(1, total);
    FILE *f;
    if (data == NULL) return;
    memcpy(data, "ldwg", 4);
    memcpy(data + LENGTH_AT[game - 1], &BUFFER[game - 1], 4);
    strcpy((char *)data + HEADER[game - 1] + vv_village_name_offset(game), "Arrival Tribe");
    data[HEADER[game - 1] + vv_village_name_offset(game) + 40] = 0x7F;
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers1.ldw", root);
    make_dirs(root);
    f = fopen(path, "wb");
    if (f) { fwrite(data, 1, total, f); fclose(f); }
    free(data);
}

static const char *ROOT_SUBS[2] = { "Virtual Villagers Fun Patcher Logs", "Virtual Villagers Fun Patcher Data" };

static void clean(void) {
    char sub[MAX_PATH];
    int k;
    for (k = 0; k < 2; ++k) {
        _snprintf(sub, MAX_PATH, "%s\\%s", root, ROOT_SUBS[k]);
        remove_tree(sub);
        RemoveDirectoryA(sub);
    }
}

/* The record's frozen shape up to its Skills block, and after it. */
static int has_backfill_record(int number, const char *name, int age, int head, int body, const char *how) {
    char want[512];
    const char *at;
    const char *sex = game <= 2 ? "Male" : "Female";
    _snprintf(want, sizeof want,
              "Arrived %d\r\n  Name: %s\r\n  Age at arrival: (unknown)\r\n  Age when recorded: %d\r\n"
              "  Sex: %s\r\n  Head: %d\r\n  Body: %d\r\n  Likes: (none)\r\n  Dislikes: (none)\r\n  Skills:\r\n",
              number, name, age, sex, head, body);
    at = strstr(text, want);
    if (at == NULL) {
        return 0;
    }
    at = strstr(at, "\r\n  How: ");
    _snprintf(want, sizeof want,
              "\r\n  How: %s\r\n  Note: Recorded afterwards (arrived before this log existed)\r\n\r\n", how);
    return at != NULL && strncmp(at, want, strlen(want)) == 0;
}

/* The Village History log as the population exporter writes it: Huata (and
   a dead founder, Kito) in this village's first snapshot; Silko only later;
   another village's first snapshot has a Silko too. */
static void write_history(void) {
    char path[MAX_PATH];
    static char h[4096];
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt", root);
    _snprintf(h, sizeof h,
        "=== Virtual Villagers -- 2026-09-01 10:00:00 ===\nVillage: Other Tribe (Save 2)\n\n"
        "Villager 1\n  Name: Silko\n  Age: 600\n  Head: 4\n  Body: 14\n\n\n"
        "=== Virtual Villagers -- 2026-09-02 10:00:00 ===\nVillage: Arrival Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Huata\n  Age: 400\n  Head: 8\n  Body: 1\n  Likes: ants\n\n"
        "Villager 2\n  Name: Kito\n  Age: 420\n  Head: 0\n  Body: 18\n\n\n"
        "=== Virtual Villagers -- 2026-09-03 10:00:00 ===\nVillage: Arrival Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Huata\n  Age: 500\n  Head: 8\n  Body: 1\n\n"
        "Villager 2\n  Name: Silko\n  Age: 600\n  Head: 4\n  Body: 14\n\n\n");
    write_text(path, h);
}

int main(int argc, char **argv) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    char path[MAX_PATH], marker[MAX_PATH], unacc[MAX_PATH];
    char first[1 << 15];
    unsigned char *buffer;

    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 4) {
        printf("usage: arrival_harness <parentage dll> <cause of death test dll> <save reset dll>\n");
        return 2;
    }
    if (!locate()) return 2;
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", exe_dir);
    if (!CopyFileA(argv[1], path, FALSE)) { printf("cannot copy %s\n", argv[1]); return 2; }
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
    if (!CopyFileA(argv[2], path, FALSE)) { printf("cannot copy %s\n", argv[2]); return 2; }
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", exe_dir);
    if (!CopyFileA(argv[3], path, FALSE)) { printf("cannot copy %s\n", argv[3]); return 2; }
    stand_in("VVFP Statistics Export.dll", 0);

    for (game = 1; game <= 5; ++game) {
        g = &LAYOUTS[game - 1];
        printf("Virtual Villagers %d\n", game);
        clean();
        if (!alloc_game()) { printf("cannot place the tables\n"); return 2; }
        villager(0, "Huata", 1090, 8, 1, 0);
        villager(1, "Nishi", 900, 7, 3, 1);
        villager(2, "Silko", 663, 4, 14, 0);
        villager(3, "Thabo", 1003, 16, 12, 0);
        villager(4, "Dup", 500, 2, 2, 0);
        villager(5, "Dup", 500, 2, 2, 0);
        villager(6, "Hea", 400, 9, 9, game != 5);
        if (game == 5) {
            rec(6)[VV5_FACTION] = 1;
        }
        *(int *)(rec(0) + g->likes) = 0;          /* "ants": never part of the key */
        write_old_logs();
        write_history();
        write_save_file();
        vv_village_publish("");
        load();
        buffer = save_buffer("Arrival Tribe");
        births_path(1, path);
        marker_path(marker);
        unaccounted_path(unacc);
        *(int *)(rec(0) + g->likes) = -1;

        /* 0: the scan; no answer; "Not now". */
        {
            char before_log[1 << 13];
            read_into(path);
            lstrcpynA(before_log, text, sizeof before_log);
            CHECK(scan_arrivals(game, 1) == 3, "the scan counts Huata, Silko and the second Dup");
            CHECK(scan_arrivals(game, 2) == -1, "...and cannot tell for a slot with no save");
            read_into(path);
            CHECK(strcmp(before_log, text) == 0 && !file_exists(marker), "...writing nothing: no log line, no marker");
            if (game == 1) {
                vv1_births(-1);
                CHECK(scan_arrivals(game, 1) == 0,
                      "A New Home without Show Parents (no Birth records): nothing to ask about");
                vv1_births(1);
            }
            save_done(1, buffer);              /* the roster: Huata .. Hea */
            read_into(path);
            CHECK(strcmp(before_log, text) == 0 && !file_exists(marker), "with no answer the save records nothing");
            repair_arrivals(game, 1, 0);
            save_done(1, buffer);
            read_into(path);
            CHECK(strcmp(before_log, text) == 0 && !file_exists(marker), "\"Not now\": the save records nothing");
        }

        /* 1: Ponui arrived unseen since that save (the load-time catch-up);
           Repair, and the save. */
        villager(7, "Ponui", 663, 9, 15, 0);
        CHECK(scan_arrivals(game, 1) == 4, "Ponui, arrived unseen, is found too");
        repair_arrivals(game, 1, 1);
        save_done(1, buffer);
        read_into(path);
        CHECK(has_backfill_record(4, "Huata", 1090, 8, 1, "Founder")
              && has_backfill_record(5, "Silko", 663, 4, 14, "unknown")
              && has_backfill_record(6, "Dup", 500, 2, 2, "unknown")
              && has_backfill_record(7, "Ponui", 663, 9, 15, "unknown")
              && strstr(text, "Arrived 8") == NULL,
              "Huata, Silko, the second Dup and Ponui get Arrived 4-7, in the frozen format;"
              " Huata, in the village's first History snapshot, is a Founder, Silko (later) is not");
        {
            /* The record as written, for the reader of the output. */
            const char *h = strstr(text, "Arrived 4\r\n");
            const char *end = h != NULL ? strstr(h, "\r\n\r\n") : NULL;
            if (h != NULL && end != NULL) {
                printf("%.*s\n", (int)(end - h), h);
            }
        }
        if (!has_backfill_record(4, "Huata", 1090, 8, 1, "Founder")) {
            const char *h = strstr(text, "  Name: Huata");
            printf("--- got:\n%.900s\n", h != NULL ? h - 12 : text);
        }
        CHECK(count_of(text, "  Name: Thabo\r\n") == 1,
              "Thabo's hand-appended record (name, head, body) is recognised: no duplicate");
        CHECK(count_of(text, "  Name: Dup\r\n") == 2, "two Dups, two records");
        CHECK(strstr(text, "  Name: Nishi\r\n") == NULL && strstr(text, "  Name: Hea\r\n") == NULL,
              "a villager born here, and a Heathen, get no Arrived record");
        CHECK(file_exists(marker), "the marker is written once every record is on disk");
        read_into(unacc);
        CHECK(strstr(text, "Ponui") == NULL, "Ponui is not an Unaccounted record");
        CHECK(scan_arrivals(game, 1) == 0, "the scan now finds nothing");

        /* 2: again, and in a new session. */
        read_into(path);
        lstrcpynA(first, text, sizeof first);
        save_done(1, buffer);
        read_into(path);
        CHECK(strcmp(first, text) == 0, "a second save writes nothing");
        unload();
        load();
        repair_arrivals(game, 1, 1);
        villager(8, "Late", 700, 5, 6, 0);   /* unseen, after the backfill: not the backfill's */
        CHECK(scan_arrivals(game, 1) == 0, "a new session's scan says 0 (the marker): exactly once");
        save_done(1, buffer);
        read_into(path);
        CHECK(strstr(text, "  Name: Late\r\n") == NULL, "...and its save writes no backfill");
        rec(8)[g->active] = 0;
        save_done(1, buffer);

        /* 3: seen live. */
        villager(9, "Newcomer", 700, 3, 4, 0);
        created(9, 0);
        villager(10, "Cie", 800, 5, 5, 0);
        created(10, 0);
        arrived_by(game, 10, "Custom Island Event");
        villager(11, "Babe", 0, 6, 6, 1);
        created(11, MARK[game - 1].birth);   /* a birth path, with no Births log note */
        villager(15, "Canoe", 540, 7, 2, 0);
        created(15, MARK[game - 1].event);
        villager(16, "Seed", 300, 7, 3, 0);
        created(16, MARK[game - 1].founder);  /* the seeding, in a village saved before */
        villager(12, "Twin", 0, 6, 7, 1);
        created(12, 0);
        note_birth(game, rec(12));          /* the Births log's note, every game */
        villager(13, "Gone", 650, 1, 2, 0);
        created(13, 0);
        if (game == 5) {
            villager(14, "Pagan", 300, 4, 4, 0);
            rec(14)[VV5_FACTION] = 1;
            created(14, 0);
        }
        arrival_tick();
        *(int *)(rec(9) + g->age) = 720;    /* aged since it arrived */
        departed(13);                        /* buried before the save */
        rec(13)[g->active] = 0;
        if (game == 5) {
            arrival_tick();
            rec(6)[VV5_FACTION] = 0;         /* Hea is converted */
            arrival_tick();
        }
        save_done(1, buffer);
        read_into(path);
        {
            const char *n = strstr(text, "  Name: Newcomer\r\n");
            const char *c = strstr(text, "  Name: Cie\r\n");
            const char *gone = strstr(text, "  Name: Gone\r\n");
            CHECK(n != NULL && strncmp(n, "  Name: Newcomer\r\n  Age at arrival: 700\r\n  Sex: ", 46) == 0
                  && record_has("Newcomer", "  How: unknown\r\n\r\n"),
                  "an island event's newcomer: the age it arrived at, how unknown");
            CHECK(c != NULL && record_has("Cie", "  How: Custom Island Event\r\n\r\n"),
                  "the Custom Island Event's new villager: How: Custom Island Event");
            CHECK(gone != NULL && record_has("Gone", "  Age at arrival: 650\r\n"),
                  "one who arrived and was buried before the save has the record too");
            CHECK(strstr(text, "  Name: Babe\r\n") == NULL && strstr(text, "  Name: Twin\r\n") == NULL,
                  "a birth is never an arrival (its path's marker, or the Births log's note)");
            {
                char how[96];
                _snprintf(how, sizeof how, "  How: %s\r\n\r\n", MARK[game - 1].label);
                CHECK(record_has("Canoe", how), "a stock event's newcomer: How: %s", MARK[game - 1].label);
            }
            CHECK(strstr(text, "  Name: Seed\r\n") == NULL,
                  "the seeding's records in a village saved before are not founders (a load overwrites them)");
            CHECK(count_of(text, "  Name: Newcomer\r\n") == 1 && count_of(text, "  Name: Cie\r\n") == 1
                  && count_of(text, "  Name: Gone\r\n") == 1, "each written once");
            if (game == 5) {
                CHECK(strstr(text, "  Name: Pagan\r\n") == NULL, "a Heathen the creator makes is not an arrival");
                CHECK(record_has("Hea", "  How: Converted from the Heathens\r\n"),
                      "a Heathen converted to a believer is: Converted from the Heathens");
            }
        }
        read_into(unacc);
        CHECK(strstr(text, "Newcomer") == NULL && strstr(text, "  Name: Cie") == NULL && strstr(text, "Babe") == NULL,
              "none of them is an Unaccounted record");
        read_into(path);
        lstrcpynA(first, text, sizeof first);
        save_done(1, buffer);
        read_into(path);
        CHECK(strcmp(first, text) == 0, "the next save writes none of them again");

        /* 4: Start Over. */
        reset(game, 1);
        vv_reset_slot_state(game, 1, VILLAGE);
        CHECK(!file_exists(marker), "Start Over deletes the marker");
        {
            int i;
            for (i = 0; i < 32; ++i) {
                rec(i)[g->active] = 0;
            }
        }
        villager(0, "Founda", 400, 1, 1, 0);
        created(0, MARK[game - 1].founder);
        villager(1, "Foundb", 420, 2, 1, 0);
        created(1, MARK[game - 1].founder);
        arrival_tick();
        *(int *)(rec(0) + g->age) = 410;
        save_done(1, buffer);                 /* the new village's first save */
        births_path(3, path);                 /* after the other village's file 2 */
        CHECK(read_into(path) > 0 && strncmp(text, "Village: Arrival Tribe (Save 1)", 31) == 0
              && record_has("Founda", "  Age at arrival: 400\r\n") && record_has("Founda", "  How: Founder\r\n\r\n")
              && record_has("Foundb", "  How: Founder\r\n\r\n") && strstr(text, "Note:") == NULL
              && strstr(text, "Arrived 1\r\n") == NULL,
              "the new village's founders get \"How: Founder\" at its first save, numbered on");
        printf("  (scan %d, marker %d, save %d)\n", scan_arrivals(game, 1), file_exists(marker),
               file_exists(path));
        CHECK(!file_exists(marker) && scan_arrivals(game, 1) == 0,
              "...so the scan finds nothing to ask about (no marker needed)");
        /* A founder the companion did not see made (a new village before
           it was installed) is offered by the backfill, as a founder. */
        villager(2, "Foundc", 430, 3, 1, 0);
        CHECK(scan_arrivals(game, 1) == 1, "an unseen founder is offered by the backfill");
        lstrcpynA(first, text, sizeof first);
        save_done(1, buffer);
        read_into(path);
        CHECK(strcmp(first, text) == 0, "...and the next save writes nothing more");

        unload();
        free(buffer);
        free_game();
    }
    clean();
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", exe_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", exe_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", exe_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers1.ldw", root);
    DeleteFileA(path);
    printf("== %d failure(s) ==\n", failures);
    return failures == 0 ? 0 : 1;
}
