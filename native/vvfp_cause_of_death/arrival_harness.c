/* Runtime harness for the "Arrived" records and their one-time backfill.
   32-bit only.

   Drives the TEST build of "VVFP Cause of Death.dll" and the shipped "VVFP
   Parentage Export.dll" and "VVFP Save Reset.dll" (all copied into "Virtual
   Villagers Fun Patcher Files" beside this executable under their shipped
   names, as in a game), in all five games'
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
     5. Repair answered right after the game's quit save (the cross-check's
        quit prompt, native/shared/crosscheck_bridge.h), when no later save
        will come: VvfpCauseRepairArrivalsNow writes the same Arrived records
        there and then from the villagers that save wrote (the header read
        back from the saved file) and the marker; VvfpCauseRepairBirthsNow
        the Birth records from the save (The Lost Children on; nothing in A
        New Home); a second call writes nothing.

     6. A new village's founders seeded before the village has its slot (a
        stale slot from the host), with and without an empty creation save
        before them, get "How: Founder" at the first save holding them and
        are never Unaccounted; a load over a seeding writes nothing.

     7. The logs at village creation (cod_creation_save.inc): once a new
        village's founders are made and it has started, the game's own
        autosave is asked for once (its field set to 0); never without a
        founder waiting, outside the village's scene, before the start, twice,
        for an A New Home village started long ago, or in The Lost Children
        and The Secret City.

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
#include "patcher_files.h"
#include "arrival_backfill.h"

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
typedef void (__stdcall *created_scoped_t)(int, unsigned int, int);
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
   stock event and its label, as the creators' hook would find them; the
   seeding the startup scan runs ahead of a load (0: none in that game);
   and an event whose own call a Story / Cheat Upgrades scope call holds
   (0: none). */
static const struct {
    unsigned int birth, founder, event; const char *label; unsigned int scan, scoped; const char *scoped_label;
} MARK[5] = {
    { 0x42EFD5u, 0x414020u, 0x42C3F4u, "A Mysterious Crate (watertight)", 0x41D26Du,
      0x41974Fu, "The Mysterious Face" },
    { 0x44F602u, 0x4150B0u, 0x43446Cu, "Old Friends", 0x42641Du, 0, NULL },
    { 0x45FFD2u, 0x41B7E4u, 0x414DB4u, "The Canoe from the Other Side", 0x4285EAu,
      0x415355u, "Barrel of Babies" },
    { 0x467D92u, 0x43B929u, 0x4148D4u, "The Canoe from the Other Side", 0, 0, NULL },
    { 0x471EA2u, 0x43E317u, 0x415559u, "News From Another Tribe", 0, 0, NULL },
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
static created_scoped_t created_scoped;
static void_t arrival_tick;
static int_t vv1_births;
static int_t departed;
static note_t note_birth;
static arrived_by_t arrived_by;
static arrived_by_t arrived_parents;          /* VvfpCauseArrivedParents: the same shape */

static int host_slot_value = 1;
static int __stdcall host_slot(void) { return host_slot_value; }
static struct { int size; int (__stdcall *slot)(void); } host = { 8, host_slot };

static void load(void) {
    /* By full path in the patcher's folder, as the companions load each other. */
    parentage = vvfp_load_patcher_dll("VVFP Parentage Export.dll");
    cause = vvfp_load_patcher_dll("VVFP Cause of Death.dll");
    if (parentage == NULL || cause == NULL) { printf("cannot load the DLLs\n"); exit(2); }
    ensure_village = (ensure_village_t)GetProcAddress(parentage, "EnsureParentageLogForVillage");
    setup = (setup_t)GetProcAddress(cause, "VvfpCauseTestSetup");
    save_done = (save_done_t)GetProcAddress(cause, "VvfpCauseTestSaveDone");
    reset = (reset_t)GetProcAddress(cause, "VvfpCauseVillageReset");
    scan_arrivals = (scan_t)GetProcAddress(cause, "VvfpCauseScanArrivals");
    repair_arrivals = (repair_t)GetProcAddress(cause, "VvfpCauseRepairArrivals");
    created = (created_t)GetProcAddress(cause, "VvfpCauseTestCreated");
    created_scoped = (created_scoped_t)GetProcAddress(cause, "VvfpCauseTestCreatedScoped");
    arrival_tick = (void_t)GetProcAddress(cause, "VvfpCauseTestArrivalTick");
    vv1_births = (int_t)GetProcAddress(cause, "VvfpCauseTestVv1Births");
    departed = (int_t)GetProcAddress(cause, "VvfpCauseTestDeparted");
    note_birth = (note_t)GetProcAddress(cause, "VvfpCauseNoteArrival");
    arrived_by = (arrived_by_t)GetProcAddress(cause, "VvfpCauseArrivedBy");
    arrived_parents = (arrived_by_t)GetProcAddress(cause, "VvfpCauseArrivedParents");
    if (!ensure_village || !setup || !save_done || !reset || !scan_arrivals || !repair_arrivals || !created
        || !created_scoped || !arrival_tick || !vv1_births || !departed || !note_birth || !arrived_by || !arrived_parents
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
    _snprintf(path, MAX_PATH, "%s\\%s", files_dir, name);
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
        /* Born before Last Names gave him "Bahati": the record names him by his first name. */
        "Birth\n  Child: Cheop\n    Head: 4\n    Body: 15\n    Likes: (none)\n    Dislikes: (none)\n"
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
static void write_save_named(const char *village);

static void write_save_file(void) {
    write_save_named("Arrival Tribe");
}

static void write_save_named(const char *village) {
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
    strcpy((char *)data + HEADER[game - 1] + vv_village_name_offset(game), village);
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
   another village's first snapshot has a Silko too.  The village was renamed
   after its first snapshot (the Rename Tribe tool appends a note and never
   rewrites the old header), so that snapshot still says "Old Arrival Tribe":
   it is still the founders' snapshot (Codex, #531). */
static void write_history(void) {
    char path[MAX_PATH];
    static char h[4096];
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt", root);
    _snprintf(h, sizeof h,
        "=== Virtual Villagers -- 2026-09-01 10:00:00 ===\nVillage: Other Tribe (Save 2)\n\n"
        "Villager 1\n  Name: Silko\n  Age: 600\n  Head: 4\n  Body: 14\n\n\n"
        "=== Virtual Villagers -- 2026-09-02 10:00:00 ===\nVillage: Old Arrival Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Huata\n  Age: 400\n  Head: 8\n  Body: 1\n  Likes: ants\n\n"
        "Villager 2\n  Name: Kito\n  Age: 420\n  Head: 0\n  Body: 18\n\n\n"
        "Tribe renamed from Old Arrival Tribe to Arrival Tribe on 2026-09-02 (Save 1)\n"
        "=== Virtual Villagers -- 2026-09-03 10:00:00 ===\nVillage: Arrival Tribe (Save 1)\n\n"
        "Villager 1\n  Name: Huata\n  Age: 500\n  Head: 8\n  Body: 1\n\n"
        "Villager 2\n  Name: Silko\n  Age: 600\n  Head: 4\n  Body: 14\n\n\n");
    write_text(path, h);
}

/* ---- 5: Birth records backfilled from the save (The Lost Children on) ------

   A fresh village "Birth Tribe": every villager whose record keeps parents
   was born there.
     0 Kid    parents on the record, no record in the log    -> a Birth record
     1 Nishi  parents; her Birth record has another head (Change Appearance
              since): the only Nishi on both sides           -> none
     2 Twin \  two alike (name, head, body), parents; the log has one Birth
     3 Twin /  Twin                                           -> one
     4 Huata  no parents (an arrival, not a birth)           -> none
     5 Arr    parents, and an Arrived record of the same three -> none
     6 Sam    parents; 7 Sam no parents; the log's one Sam has another head:
              a name two villagers carry decides nothing      -> one for 6
     8 Pagan  New Believers: a Heathen with parents          -> none
   A New Home keeps no parents on the record: nothing is ever asked or
   written there. */
static void births_marker_path(char *out) {
    _snprintf(out, MAX_PATH,
              "%s\\Virtual Villagers Fun Patcher Data\\Births\\Virtual Villagers %d Births Recorded - Save 1.dat",
              root, game);
}

static void parented(int i, const char *name, int head, int body) {
    villager(i, name, 600, head, body, 1);
    if (g->father != 0) {
        strcpy((char *)rec(i) + g->father + 0x19, "Chika");      /* the mother, 0x19 on */
    }
}

/* `number`: its "Birth <n>" -- numbered like a Conception (v1.35.66), after the
   older log's unnumbered Birth records, which count. */
static int has_birth_backfill(const char *child, int head, int body, int number) {
    char want[256], looks[128];
    const char *at, *end;
    /* The child's sex (the owner: every villager in the logs shows it), then
       the looks. */
    _snprintf(want, sizeof want, "Birth %d\r\n  Child: %s\r\n    Sex: ", number, child);
    _snprintf(looks, sizeof looks, "    Head: %d\r\n    Body: %d\r\n", head, body);
    /* Any record of the child that is the backfill's (a hand-written one
       of the same child may come first). */
    for (at = strstr(text, want); at != NULL; at = strstr(at + 1, want)) {
        static const char note[] = "\r\n  Note: Recorded afterwards (born before this log existed)";
        size_t n = sizeof note - 1;
        const char *sex = at + strlen(want);
        const char *after = strstr(sex, "\r\n");
        if (after == NULL || (strncmp(sex, "Male\r\n", 6) != 0 && strncmp(sex, "Female\r\n", 8) != 0)
            || strncmp(after + 2, looks, strlen(looks)) != 0) {
            continue;
        }
        end = strstr(at, "\r\n\r\n");
        if (end != NULL && (size_t)(end - at) > n
            && strstr(at, "  Mother: Chika\r\n") != NULL && strstr(at, "  Mother: Chika\r\n") < end
            && strstr(at, "  Father: Kito\r\n") != NULL && strstr(at, "  Father: Kito\r\n") < end
            && strncmp(end - n, note, n) == 0) {
            return 1;
        }
    }
    return 0;
}

typedef int (__stdcall *now_t)(int, int);

/* 5: Repair answered right after the quit save. */
static void quit_cases(void) {
    char path[MAX_PATH], marker[MAX_PATH], bmarker[MAX_PATH], first[1 << 13];
    unsigned char *buffer;
    now_t arrivals_now = (now_t)GetProcAddress(cause, "VvfpCauseRepairArrivalsNow");
    now_t births_now = (now_t)GetProcAddress(cause, "VvfpCauseRepairBirthsNow");
    int i, done;
    CHECK(arrivals_now != NULL && births_now != NULL, "quit: the DLL exports both repairs at the quit");
    if (arrivals_now == NULL || births_now == NULL) return;
    reset(game, 1);                       /* a new village in the slot */
    clean();
    for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
    villager(0, "Huata", 1090, 8, 1, 0);
    villager(1, "Nishi", 900, 9, 3, 1);
    villager(2, "Silko", 663, 4, 14, 0);
    villager(3, "Thabo", 1003, 16, 12, 0);
    villager(4, "Dup", 500, 2, 2, 0);
    villager(5, "Dup", 500, 2, 2, 0);
    villager(17, "Thabo", 1003, 15, 12, 0);
    if (game != 1) {
        parented(19, "Kid", 4, 4);
    }
    write_old_logs();
    write_history();
    write_save_file();
    vv_village_publish("");
    buffer = save_buffer("Arrival Tribe");
    births_path(1, path);
    marker_path(marker);
    births_marker_path(bmarker);
    read_into(path);
    lstrcpynA(first, text, sizeof first);
    save_done(1, buffer);                 /* the quit save: nothing answered yet */
    read_into(path);
    CHECK(strcmp(first, text) == 0 && !file_exists(marker) && !file_exists(bmarker),
          "quit: the quit save, with no answer yet, records nothing");
    done = arrivals_now(game, 1);
    read_into(path);
    CHECK(done == 1 && has_backfill_record(4, "Huata", 1090, 8, 1, "Founder")
          && has_backfill_record(5, "Silko", 663, 4, 14, "unknown")
          && has_backfill_record(6, "Dup", 500, 2, 2, "unknown")
          && has_backfill_record(7, "Thabo", 1003, 15, 12, "unknown")
          && strstr(text, "Arrived 8") == NULL && strncmp(text, "Village: Arrival Tribe (Save 1)", 31) == 0,
          "quit: Repair right after the quit save writes Huata, Silko, the second Dup and the other Thabo"
          " there and then, in the village's own log");
    CHECK(file_exists(marker) && scan_arrivals(game, 1) == 0, "quit: ...the marker is written; the scan finds nothing");
    lstrcpynA(first, text, sizeof first);
    done = arrivals_now(game, 1);
    read_into(path);
    CHECK(done == 1 && strcmp(first, text) == 0, "quit: ...and a second Repair writes nothing");
    done = births_now(game, 1);
    read_into(path);
    if (game == 1) {
        CHECK(done == 0 && strcmp(first, text) == 0 && !file_exists(bmarker),
              "quit: A New Home keeps no parents -- no Birth records to write at the quit");
    } else {
        CHECK(done == 1 && has_birth_backfill("Kid", 4, 4, 4) && count_of(text, "born before this log existed") == 1
              && file_exists(bmarker),
              "quit: the Birth record from the save is written there and then, and its marker");
    }
    lstrcpynA(first, text, sizeof first);
    births_now(game, 1);
    read_into(path);
    CHECK(strcmp(first, text) == 0, "quit: ...and a second Repair writes nothing");
    {
        /* Repair Saves & Logs' approval for the slot (src/vv_log_tools.py) goes with
           the village at Start Over. */
        char approval[MAX_PATH];
        _snprintf(approval, MAX_PATH,
                  "%s\\Virtual Villagers Fun Patcher Data\\Log Checks\\Virtual Villagers %d Repair Approved - Save 1.dat",
                  root, game);
        write_text(approval, "VRA1");
        CHECK(file_exists(approval), "quit: (an approval for the slot is there)");
        reset(game, 1);
        vv_reset_slot_state(game, 1, "Village: Arrival Tribe (Save 1)\n");
        CHECK(!file_exists(approval), "quit: Start Over deletes the slot's Repair Saves & Logs approval");
    }
    free(buffer);
}

/* 6: a new village's founders are seeded before the game gives the village
   its slot (live, The Lost Children with a fresh profile: the host said 5,
   the village was saved in 1), and The Tree of Life and New Believers save
   the new village once before its founders are chosen (an empty roster).
   The founders still get "How: Founder" at the first save that holds them;
   a load that replaces a seeded village (a roster with villagers) writes
   nothing; and nobody is Unaccounted. */
static void stale_slot_cases(void) {
    char path[MAX_PATH], unacc[MAX_PATH];
    unsigned char *buffer;
    int i, empty_first;
    for (empty_first = 0; empty_first <= 1; ++empty_first) {
        reset(game, 1);
        vv_reset_slot_state(game, 1, VILLAGE);
        clean();
        for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
        write_save_file();
        vv_village_publish("");
        buffer = save_buffer("Arrival Tribe");
        births_path(1, path);
        unaccounted_path(unacc);
        if (empty_first) {
            save_done(1, buffer);             /* the creation save, before the founders */
        }
        host_slot_value = 5;                  /* the stale slot at the seeding */
        villager(0, "Staleone", 400, 1, 1, 0);
        created(0, MARK[game - 1].founder);
        villager(1, "Staletwo", 420, 2, 1, 0);
        created(1, MARK[game - 1].founder);
        /* The owner: 0 is a valid head, body and age in every game. */
        villager(3, "Zerozero", 0, 0, 0, 0);
        created(3, MARK[game - 1].founder);
        arrival_tick();
        host_slot_value = 1;
        arrival_tick();
        save_done(1, buffer);
        read_into(path);
        CHECK(record_has("Staleone", "  How: Founder\r\n") && record_has("Staletwo", "  How: Founder\r\n")
              && count_of(text, "  Name: Staleone\r\n") == 1,
              "stale slot%s: the founders seeded before the village had its slot get \"How: Founder\" at its"
              " first save", empty_first ? ", after an empty creation save" : "");
        CHECK(record_has("Zerozero", "  Age at arrival: 0\r\n") && record_has("Zerozero", "  Head: 0\r\n  Body: 0\r\n")
              && record_has("Zerozero", "  How: Founder\r\n"),
              "stale slot%s: a founder with head 0, body 0 and age 0 is a founder like any other",
              empty_first ? ", after an empty creation save" : "");
        read_into(unacc);
        CHECK(strstr(text, "Stale") == NULL && strstr(text, "Zerozero") == NULL, "stale slot%s: ...and neither is Unaccounted",
              empty_first ? ", after an empty creation save" : "");
        /* A seeding a load then replaces, in a village saved before with
           villagers in it: nothing. */
        host_slot_value = 5;
        villager(2, "Seedling", 300, 3, 1, 0);
        created(2, MARK[game - 1].founder);
        host_slot_value = 1;
        villager(2, "Loadedin", 900, 3, 2, 0);   /* the load's villager in that record */
        arrival_tick();
        save_done(1, buffer);
        read_into(path);
        CHECK(strstr(text, "Seedling") == NULL && strstr(text, "  Name: Loadedin\r\n") == NULL,
              "stale slot%s: a load over a seeding, in a village saved before, writes no Founder",
              empty_first ? ", after an empty creation save" : "");
        for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
        free(buffer);
    }
    reset(game, 1);
    vv_reset_slot_state(game, 1, VILLAGE);
}

/* 7: the logs at village creation (cod_creation_save.inc).  A New Home, The
   Tree of Life and New Believers make a new village's first save with nobody
   in it; once its founders are made and it has started, the game is asked for
   ONE save through its own autosave (the field set to 0) -- never for a
   village with no founder waiting, never twice, never outside the village's
   own scene, never in A New Home for a village started long ago (a load the
   seeding ran ahead of), never in The Lost Children or The Secret City (they
   save after their seeding already). */
static void creation_save_cases(void) {
    typedef int (__stdcall *creation_t)(void *, unsigned int, unsigned int);
    typedef void (__stdcall *fields_t)(int, unsigned int *);
    creation_t creation = (creation_t)GetProcAddress(cause, "VvfpCauseTestCreationSave");
    fields_t fields_of = (fields_t)GetProcAddress(cause, "VvfpCauseTestCreationFields");
    unsigned int f[5];
    unsigned char *manager;
    unsigned char *buffer;
    int i, asked;
    CHECK(creation != NULL && fields_of != NULL, "creation: the test DLL exports the probes");
    if (creation == NULL || fields_of == NULL) return;
    fields_of(game, f);
    manager = (unsigned char *)calloc(1, 0x20000);
    reset(game, 1);
    vv_reset_slot_state(game, 1, VILLAGE);
    clean();
    for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
    write_save_file();
    vv_village_publish("");
    buffer = save_buffer("Arrival Tribe");
    host_slot_value = 1;
    if (game == 2 || game == 3) {
        villager(0, "Firstone", 400, 1, 1, 0);
        created(0, MARK[game - 1].founder);
        arrival_tick();
        CHECK(creation(manager, 1000, 1010) == 0,
              "creation: The Lost Children and The Secret City are never asked (they save after the seeding)");
        save_done(1, buffer);
        free(buffer);
        free(manager);
        return;
    }
    *(int *)(manager + f[0]) = 1;
    *(unsigned int *)(manager + f[1]) = f[2];
    *(unsigned int *)(manager + f[3]) = 12345u;
    if (f[4] != 0) *(unsigned int *)(manager + f[4]) = 1000u;
    save_done(1, buffer);                                      /* the creation save, nobody in it */
    CHECK(creation(manager, 1000, 1010) == 0 && *(unsigned int *)(manager + f[3]) == 12345u,
          "creation: no founder waiting, no save asked");
    villager(0, "Firstone", 400, 1, 1, 0);
    created(0, MARK[game - 1].founder);
    villager(1, "Secondone", 420, 2, 1, 0);
    created(1, MARK[game - 1].founder);
    arrival_tick();
    *(unsigned int *)(manager + f[1]) = f[2] + 3u;            /* still the founder screen / intro */
    CHECK(creation(manager, 1000, 1010) == 0 && *(unsigned int *)(manager + f[3]) == 12345u,
          "creation: not before the village's own scene");
    *(unsigned int *)(manager + f[1]) = f[2];
    if (f[4] != 0) *(unsigned int *)(manager + f[4]) = 0u;
    CHECK(creation(manager, 0, 1010) == 0 && *(unsigned int *)(manager + f[3]) == 12345u,
          "creation: not before the village has started");
    if (f[4] != 0) *(unsigned int *)(manager + f[4]) = 1000u;
    if (game == 1) {
        CHECK(creation(manager, 1000, 1000 + 3600) == 0 && *(unsigned int *)(manager + f[3]) == 12345u,
              "creation: A New Home, a village started an hour ago is a load, never saved for this");
    }
    asked = creation(manager, 1000, 1010);
    CHECK(asked == 1 && *(unsigned int *)(manager + f[3]) == 0u,
          "creation: founders made and the village started -> the autosave field is 0 (one save, the game's own)");
    *(unsigned int *)(manager + f[3]) = 12345u;
    CHECK(creation(manager, 1000, 1011) == 0 && *(unsigned int *)(manager + f[3]) == 12345u,
          "creation: asked once per village");
    save_done(1, buffer);                                      /* that save */
    {
        char path[MAX_PATH];
        births_path(1, path);
        read_into(path);
        CHECK(record_has("Firstone", "  How: Founder\r\n") && record_has("Secondone", "  How: Founder\r\n")
              && count_of(text, "  Name: Firstone\r\n") == 1,
              "creation: that save writes the founders' Arrived records, once");
    }
    /* A new village in the same slot later (Start Over): asked again. */
    reset(game, 1);
    vv_reset_slot_state(game, 1, VILLAGE);
    villager(2, "Thirdone", 300, 3, 1, 0);
    created(2, MARK[game - 1].founder);
    arrival_tick();
    if (f[4] != 0) *(unsigned int *)(manager + f[4]) = 2000u;
    CHECK(creation(manager, 2000, 2010) == 1, "creation: a Start Over's new village is asked for its save too");
    save_done(1, buffer);
    for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
    reset(game, 1);
    vv_reset_slot_state(game, 1, VILLAGE);
    free(buffer);
    free(manager);
    creation(NULL, 0, 0);
}

static void births_cases(void) {
    char path[MAX_PATH], marker[MAX_PATH], unacc[MAX_PATH], before_log[1 << 13];
    unsigned char *buffer;
    scan_t scan_births = (scan_t)GetProcAddress(cause, "VvfpCauseScanBirths");
    repair_t repair_births = (repair_t)GetProcAddress(cause, "VvfpCauseRepairBirths");
    int i;
    CHECK(scan_births != NULL && repair_births != NULL
          && GetProcAddress(parentage, "RecordBirthsMissingFromLog") != NULL,
          "births: the DLLs export the scan, the answer and the backfill");
    if (scan_births == NULL || repair_births == NULL) return;
    reset(game, 1);                       /* the companions stay loaded: a new village in the slot */
    clean();
    for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
    parented(0, "Kid", 4, 4);
    parented(1, "Nishi", 9, 3);
    parented(2, "Twin", 6, 6);
    parented(3, "Twin", 6, 6);
    villager(4, "Huata", 1090, 8, 1, 0);
    parented(5, "Arr", 5, 5);
    parented(6, "Sam", 2, 9);
    villager(7, "Sam", 700, 3, 9, 0);
    parented(10, "Look", 3, 3);           /* born, with his Birth record */
    villager(11, "Look", 700, 3, 3, 0);   /* an arrived look-alike, no record (Codex, #536) */
    if (game == 5) {
        parented(8, "Pagan", 7, 7);
        rec(8)[VV5_FACTION] = 1;
    }
    births_path(1, path);
    write_text(path,
        "Village: Birth Tribe (Save 1)\n"
        /* Numbered with a gap and out of order, one plain (a mixed, hand-edited log): the
           backfill goes on above the highest number, 9 -- never a number already used. */
        "Birth 1\n  Child: Nishi\n    Head: 7\n    Body: 3\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: Kito\n    Head: 0\n    Body: 18\n\n"
        "Birth 9\n  Child: Twin\n    Head: 6\n    Body: 6\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: Kito\n    Head: 0\n    Body: 18\n\n"
        "Birth\n  Child: Sam\n    Head: 1\n    Body: 9\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: Kito\n    Head: 0\n    Body: 18\n\n"
        "Birth 3\n  Child: Look\n    Head: 3\n    Body: 3\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chika\n    Head: 19\n    Body: 17\n  Father: Kito\n    Head: 0\n    Body: 18\n\n"
        "Arrived 1\n  Name: Arr\n  Age at arrival: 300\n  Sex: Male\n  Head: 5\n  Body: 5\n"
        "  Likes: (none)\n  Dislikes: (none)\n  How: unknown\n\n");
    {
        /* The slot's save names "Birth Tribe" (the scan at load reads it). */
        static const DWORD HEADER[5] = { 12u, 12u, 12u, 24u, 24u };
        static const DWORD LENGTH_AT[5] = { 8u, 8u, 8u, 16u, 16u };
        static const DWORD BUFFER[5] = { 0x0ABDCu, 0x30370u, 0x12F1Cu, 0x1710Cu, 0x17D78u };
        DWORD total = HEADER[game - 1] + BUFFER[game - 1];
        unsigned char *data = (unsigned char *)calloc(1, total);
        char save[MAX_PATH];
        FILE *f;
        memcpy(data, "ldwg", 4);
        memcpy(data + LENGTH_AT[game - 1], &BUFFER[game - 1], 4);
        strcpy((char *)data + HEADER[game - 1] + vv_village_name_offset(game), "Birth Tribe");
        data[HEADER[game - 1] + vv_village_name_offset(game) + 40] = 0x7F;
        _snprintf(save, MAX_PATH, "%s\\Virtual Villagers1.ldw", root);
        f = fopen(save, "wb");
        if (f) { fwrite(data, 1, total, f); fclose(f); }
        free(data);
    }
    vv_village_publish("");
    buffer = save_buffer("Birth Tribe");
    births_marker_path(marker);
    unaccounted_path(unacc);
    read_into(path);
    lstrcpynA(before_log, text, sizeof before_log);

    if (game == 1) {
        CHECK(scan_births(1, 1) == 0, "births: A New Home keeps no parents -- nothing to ask about");
        repair_births(1, 1, 1);
        save_done(1, buffer);
        read_into(path);
        CHECK(strstr(text, "born before this log existed") == NULL && !file_exists(marker),
              "births: ...and nothing is written there, even after Repair");
        free(buffer);
        return;
    }
    CHECK(scan_births(game, 1) == 3, "births: the scan counts Kid, the second Twin and the Sam with parents"
                                     " (not Nishi, Huata, Arr or a Heathen)");
    read_into(path);
    CHECK(strcmp(before_log, text) == 0 && !file_exists(marker), "births: ...writing nothing");
    save_done(1, buffer);
    read_into(path);
    CHECK(strcmp(before_log, text) == 0 && !file_exists(marker), "births: with no answer the save writes nothing");
    repair_births(game, 1, 0);
    save_done(1, buffer);
    read_into(path);
    CHECK(strcmp(before_log, text) == 0 && !file_exists(marker), "births: \"Not now\" writes nothing");

    repair_births(game, 1, 1);
    save_done(1, buffer);
    read_into(path);
    CHECK(has_birth_backfill("Kid", 4, 4, 10) && has_birth_backfill("Sam", 2, 9, 12),
          "births: after Repair the save writes Kid's and Sam's Birth records from the save, marked"
          " \"Recorded afterwards (born before this log existed)\"");
    {
        const char *k = strstr(text, "  Child: Kid\r\n");
        const char *end = k != NULL ? strstr(k, "\r\n\r\n") : NULL;
        if (k != NULL && end != NULL) printf("%.*s\n", (int)(end - k + 2), k - 7);
    }
    CHECK(count_of(text, "  Child: Twin\r\n") == 2 && has_birth_backfill("Twin", 6, 6, 11),
          "births: two Twins, one record: one more is written");
    CHECK(count_of(text, "  Child: Nishi\r\n") == 1 && strstr(text, "  Child: Huata\r\n") == NULL
          && strstr(text, "  Child: Arr\r\n") == NULL && strstr(text, "  Child: Pagan\r\n") == NULL,
          "births: none for Nishi (looks changed, the only one of the name), Huata (no parents), Arr (an Arrived"
          " record), a Heathen");
    CHECK(count_of(text, "born before this log existed") == 3, "births: exactly three written");
    CHECK(file_exists(marker), "births: the marker is written once every record is on disk");
    read_into(unacc);
    CHECK(text[0] == 0 || (strstr(text, "  Name: Kid") == NULL && strstr(text, "  Name: Sam") == NULL),
          "births: none of them is an Unaccounted record");
    CHECK(scan_births(game, 1) == 0, "births: the scan now finds nothing");
    read_into(path);
    lstrcpynA(before_log, text, sizeof before_log);
    save_done(1, buffer);
    read_into(path);
    CHECK(strcmp(before_log, text) == 0, "births: a second save writes nothing");
    CHECK(count_of(text, "  Child: Look\r\n") == 1, "births: the born Look's Birth record is his: none written");
    /* The Arrived records' backfill of the same village: the born Look (a
       context villager there) takes his Birth record first, so his arrived
       look-alike is not taken for in the log (Codex, #536). */
    repair_arrivals(game, 1, 1);
    save_done(1, buffer);
    read_into(path);
    CHECK(strstr(text, "  Name: Look\r\n") != NULL,
          "births: the arrived Look gets his own Arrived record; the born Look's Birth record is not his");
    unload();
    load();                               /* a new session: the DLLs may load elsewhere */
    scan_births = (scan_t)GetProcAddress(cause, "VvfpCauseScanBirths");
    repair_births = (repair_t)GetProcAddress(cause, "VvfpCauseRepairBirths");
    parented(9, "Late", 4, 8);            /* after the backfill: not the backfill's */
    repair_births(game, 1, 1);
    CHECK(scan_births(game, 1) == 0, "births: a new session's scan says 0 (the marker): exactly once");
    save_done(1, buffer);
    read_into(path);
    CHECK(strstr(text, "  Child: Late\r\n") == NULL, "births: ...and its save writes no backfill");
    reset(game, 1);
    vv_reset_slot_state(game, 1, "Village: Birth Tribe (Save 1)\n");
    CHECK(!file_exists(marker), "births: Start Over deletes the marker");
    free(buffer);
}

/* 6: a record keeps the name and looks of its day (the owner's A New Home
   log, 2026-10-10: a Birth record "Cheop" and an Arrived record "Hoani"
   written before last names were given, then "Arrived 11 / Cheop Bahati"
   and "Arrived 12 / Hoani Chuchip" backfilled beside them).
     0 Cheop Bahati   the log's Birth "Cheop", same looks         -> none
     1 Hoani Chuchip  the log's Arrived "Hoani", same looks        -> none
     2 Papu (5/14)    Birth "Papu" 16/14, then "Appearance changed"
                      16/14 -> 5/14                                -> none
     3 Papu (7/7)     Arrived "Papu" 7/7                           -> none
     4 Kito Bahati \  one Birth "Kito" 0/18 either could be:
     5 Kito Wanjiko/  it decides nothing                           -> one each
     6 Founda         no record at all                             -> one */
static void renamed_cases(void) {
    char path[MAX_PATH];
    unsigned char *buffer;
    int i;
    reset(game, 1);
    clean();
    for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
    villager(0, "Cheop Bahati", 900, 4, 15, 0);
    villager(1, "Hoani Chuchip", 577, 11, 2, 0);
    villager(2, "Papu", 383, 5, 14, 0);
    villager(3, "Papu", 383, 7, 7, 0);
    villager(4, "Kito Bahati", 500, 0, 18, 0);
    villager(5, "Kito Wanjiko", 500, 0, 18, 0);
    villager(6, "Founda", 400, 1, 1, 0);
    births_path(1, path);
    write_text(path,
        "Village: Rename Tribe (Save 1)\n"
        "Birth\n  Child: Cheop\n    Head: 4\n    Body: 15\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chapa\n    Head: 18\n    Body: 0\n  Father: Usutu\n    Head: 18\n    Body: 1\n\n"
        "Birth\n  Child: Papu\n    Head: 16\n    Body: 14\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chapa\n    Head: 18\n    Body: 0\n  Father: Usutu\n    Head: 18\n    Body: 1\n\n"
        "Birth\n  Child: Kito\n    Head: 0\n    Body: 18\n    Likes: (none)\n    Dislikes: (none)\n"
        "  Mother: Chapa\n    Head: 18\n    Body: 0\n  Father: Usutu\n    Head: 18\n    Body: 1\n\n"
        "Arrived 1\n  Name: Hoani\n  Age at arrival: 88\n  Sex: Male\n  Head: 11\n  Body: 2\n"
        "  Likes: (none)\n  Dislikes: (none)\n  How: Barrel of Babies\n\n"
        "Arrived 2\n  Name: Papu\n  Age at arrival: 300\n  Sex: Male\n  Head: 7\n  Body: 7\n"
        "  Likes: (none)\n  Dislikes: (none)\n  How: unknown\n\n"
        "Appearance changed\n  Name: Papu\n  Old head: 16\n  Old body: 14\n  New head: 5\n  New body: 14\n"
        "  Changed by: an island event\n\n");
    write_save_named("Rename Tribe");
    vv_village_publish("");
    buffer = save_buffer("Rename Tribe");
    CHECK(scan_arrivals(game, 1) == 3,
          "renamed: the scan counts the two Kitos and Founda only (Cheop, Hoani and both Papus are in the log)");
    repair_arrivals(game, 1, 1);
    save_done(1, buffer);
    read_into(path);
    CHECK(strstr(text, "  Name: Cheop Bahati\r\n") == NULL,
          "renamed: Cheop Bahati's Birth record says \"Cheop\" (no last name then): no Arrived record");
    CHECK(strstr(text, "  Name: Hoani Chuchip\r\n") == NULL,
          "renamed: Hoani Chuchip's Arrived record says \"Hoani\": no second Arrived record");
    CHECK(count_of(text, "  Name: Papu\r\n") == 2,
          "renamed: the Papu whose look changed is followed through the Appearance changed record: no new"
          " record for either Papu");
    CHECK(count_of(text, "  Name: Kito Bahati\r\n") == 1 && count_of(text, "  Name: Kito Wanjiko\r\n") == 1,
          "renamed: a record either of two villagers could be decides nothing: both are written");
    CHECK(count_of(text, "  Name: Founda\r\n") == 1, "renamed: a villager with no record still gets one");
    CHECK(scan_arrivals(game, 1) == 0, "renamed: the scan then finds nothing");
    reset(game, 1);
    vv_reset_slot_state(game, 1, "Village: Rename Tribe (Save 1)\n");
    for (i = 0; i < 32; ++i) rec(i)[g->active] = 0;
    free(buffer);
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
    CreateDirectoryA(files_dir, NULL);
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", files_dir);
    if (!CopyFileA(argv[1], path, FALSE)) { printf("cannot copy %s\n", argv[1]); return 2; }
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", files_dir);
    if (!CopyFileA(argv[2], path, FALSE)) { printf("cannot copy %s\n", argv[2]); return 2; }
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", files_dir);
    if (!CopyFileA(argv[3], path, FALSE)) { printf("cannot copy %s\n", argv[3]); return 2; }
    stand_in("VVFP Statistics Export.dll", 0);

    for (game = 1; game <= 5; ++game) {
        g = &LAYOUTS[game - 1];
        printf("Virtual Villagers %d\n", game);
        clean();
        if (!alloc_game()) { printf("cannot place the tables\n"); return 2; }
        villager(0, "Huata", 1090, 8, 1, 0);
        villager(1, "Nishi", 900, 9, 3, 1);       /* her Birth record says head 7: Change Appearance since */
        villager(2, "Silko", 663, 4, 14, 0);
        villager(3, "Thabo", 1003, 16, 12, 0);
        villager(4, "Dup", 500, 2, 2, 0);
        villager(5, "Dup", 500, 2, 2, 0);
        villager(6, "Hea", 400, 9, 9, game != 5);
        villager(21, "Cheop Bahati", 901, 4, 15, 0);   /* his Birth record says "Cheop" (before Last Names) */
        if (game == 5) {
            rec(6)[VV5_FACTION] = 1;
            *(int *)(rec(6) + 0x1CFC) = 14;   /* a Heathen Master Scientist: the purple mask */
        }
        /* Kept out of the backfill: a Heathen (never a villager), and a
           villager whose record keeps parents (born here, before the log). */
        villager(17, "Thabo", 1003, 15, 12, 0);   /* Thabo's name and body, another head */
        if (game == 5) {
            villager(18, "Pagan", 900, 3, 3, 0);
            rec(18)[VV5_FACTION] = 1;
        }
        if (game != 1) {
            villager(19, "Kid", 300, 4, 4, 1);
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
            CHECK(scan_arrivals(game, 1) == 4,
                  "the scan counts Huata, Silko, the second Dup and the other Thabo (not a Heathen, not one"
                  " with parents)");
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
        CHECK(scan_arrivals(game, 1) == 5, "Ponui, arrived unseen, is found too");
        repair_arrivals(game, 1, 1);
        /* ...and in the same session, after Repair and before that save, the
           Custom Island Event makes Okwui (the owner's v1.35.58 preview: he
           got the backfill's "Recorded afterwards" record AND his own). */
        villager(20, "Okwui", 100, 19, 19, 0);
        created(20, 0);
        arrived_by(game, 20, "Custom Island Event");
        arrival_tick();
        save_done(1, buffer);
        read_into(path);
        CHECK(has_backfill_record(4, "Huata", 1090, 8, 1, "Founder")
              && has_backfill_record(5, "Silko", 663, 4, 14, "unknown")
              && has_backfill_record(6, "Dup", 500, 2, 2, "unknown")
              && has_backfill_record(7, "Ponui", 663, 9, 15, "unknown")
              && has_backfill_record(8, "Thabo", 1003, 15, 12, "unknown")
              && strstr(text, "Arrived 10") == NULL,
              "Huata, Silko, the second Dup, Ponui and the other Thabo get Arrived 4-8, in the frozen format;"
              " Huata, in the village's first History snapshot, is a Founder, Silko (later) is not");
        CHECK(strstr(text, "  Name: Cheop Bahati") == NULL,
              "Cheop Bahati, whose Birth record names him 'Cheop' (before Last Names), gets no Arrived record");
        {
            const char *okwui = arrived(9, "Okwui");
            CHECK(count_of(text, "  Name: Okwui\r\n") == 1 && okwui != NULL
                  && record_has("Okwui", "  Age at arrival: 100\r\n")
                  && record_has("Okwui", "  How: Custom Island Event\r\n\r\n"),
                  "a villager who arrives live in the session the backfill runs gets exactly one record,"
                  " his own (Arrived 9, How: Custom Island Event), never the backfill's as well");
        }
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
        CHECK(count_of(text, "  Name: Thabo\r\n") == 2,
              "Thabo's hand-appended record (name, head, body) is recognised: no duplicate;"
              " a namesake with another head is not him");
        CHECK(strstr(text, "  Name: Pagan\r\n") == NULL && strstr(text, "  Name: Kid\r\n") == NULL,
              "no record for a Heathen, nor for a villager whose record keeps parents");
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
        /* The marker names its village: another village in the slot -- a
           save copied in -- is not the one it was written for (Codex, #531),
           and is scanned again. */
        {
            typedef int (__stdcall *header_t)(int, int, char *, int);
            HMODULE reset = GetModuleHandleA("VVFP Save Reset.dll");
            header_t header = reset != NULL ? (header_t)GetProcAddress(reset, "SavedVillageHeader") : NULL;
            char line[256];
            CHECK(header != NULL && header(game, 1, line, (int)sizeof line)
                  && vv_backfill_marker_present(VV_BACKFILL_ARRIVALS, game, 1, vv_backfill_village_id(line)),
                  "the marker is written for this village (its save's \"Village:\" line)");
            write_save_named("Copied Tribe");
            CHECK(header != NULL && header(game, 1, line, (int)sizeof line)
                  && !vv_backfill_marker_present(VV_BACKFILL_ARRIVALS, game, 1, vv_backfill_village_id(line)),
                  "...and does not count for another village copied into the slot");
            write_save_file();
        }
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
        /* ...with the parents it chose (the owner, 2026-10-10): the "Parents:"
           block every Village History record has, after How. */
        arrived_parents(game, 10, "  Parents:\n    Father: Joey\n      Head: 2\n      Body: 2\n"
                                  "    Mother: Ana\n      Head: 0\n      Body: 0\n");
        villager(11, "Babe", 0, 6, 6, 1);
        created(11, MARK[game - 1].birth);   /* a birth path, with no Births log note */
        villager(15, "Canoe", 540, 7, 2, 0);
        created(15, MARK[game - 1].event);
        villager(16, "Seed", 300, 7, 3, 0);
        created(16, MARK[game - 1].founder);  /* the seeding, in a village saved before */
        if (MARK[game - 1].scoped != 0u) {
            /* The owner's v1.35.58 live pass (The Secret City): a picked
               barrel, its call held by a Story / Cheat Upgrades scope call. */
            villager(17, "Scoped", 200, 8, 3, 0);
            created_scoped(17, MARK[game - 1].scoped, 1);
        }
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
        villager(13, "Reborn", 0, 1, 1, 1);  /* the record reused before the save */
        if (game == 5) {
            arrival_tick();
            rec(6)[VV5_FACTION] = 0;         /* Hea is converted: */
            *(int *)(rec(6) + 0x1CFC) = 0;   /* the conversion clears a Master's type (0x46696F) */
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
            CHECK(c != NULL && record_has("Cie", "  How: Custom Island Event\r\n  Parents:\r\n    Father: Joey\r\n"
                                                 "      Head: 2\r\n      Body: 2\r\n    Mother: Ana\r\n"
                                                 "      Head: 0\r\n      Body: 0\r\n\r\n"),
                  "the Custom Island Event's new villager: How: Custom Island Event, then the parents it chose");
            CHECK(gone != NULL && record_has("Gone", "  Age at arrival: 650\r\n"),
                  "one who arrived and was buried before the save has the record too, at the burial");
            CHECK(strstr(text, "  Name: Reborn\r\n") == NULL, "...and whoever has the record now gets none");
            CHECK(strstr(text, "  Name: Babe\r\n") == NULL && strstr(text, "  Name: Twin\r\n") == NULL,
                  "a birth is never an arrival (its path's marker, or the Births log's note)");
            {
                char how[96];
                _snprintf(how, sizeof how, "  How: %s\r\n\r\n", MARK[game - 1].label);
                CHECK(record_has("Canoe", how), "a stock event's newcomer: How: %s", MARK[game - 1].label);
            }
            if (MARK[game - 1].scoped != 0u) {
                char how2[96];
                _snprintf(how2, sizeof how2, "  How: %s\r\n\r\n", MARK[game - 1].scoped_label);
                CHECK(record_has("Scoped", how2),
                      "an event whose call a Story / Cheat Upgrades scope call holds: How: %s (that companion"
                      " names the game's return address)", MARK[game - 1].scoped_label);
            }
            CHECK(strstr(text, "  Name: Seed\r\n") == NULL,
                  "the seeding's records in a village saved before are not founders (a load overwrites them)");
            CHECK(count_of(text, "  Name: Newcomer\r\n") == 1 && count_of(text, "  Name: Cie\r\n") == 1
                  && count_of(text, "  Name: Gone\r\n") == 1, "each written once");
            if (game == 5) {
                CHECK(strstr(text, "  Name: Pagan\r\n") == NULL, "a Heathen the creator makes is not an arrival");
                CHECK(record_has("Hea", "  How: Converted from the Heathens\r\n"),
                      "a Heathen converted to a believer is: Converted from the Heathens");
                CHECK(record_has("Hea", "  Special villager: Former Heathen Master (purple mask)\r\n"),
                      "...a Former Heathen Master: the mask the tick saw, kept in the Former Heathens file");
                {
                    char former_path[MAX_PATH];
                    unsigned char blob[64];
                    DWORD got = 0;
                    HANDLE h;
                    _snprintf(former_path, MAX_PATH,
                              "%s\\Virtual Villagers Fun Patcher Data\\Former Heathens\\Former Heathens - Save 1.dat",
                              root);
                    h = CreateFileA(former_path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
                    if (h != INVALID_HANDLE_VALUE) { ReadFile(h, blob, sizeof blob, &got, NULL); CloseHandle(h); }
                    CHECK(got == 24 && memcmp(blob, "VFH1", 4) == 0 && *(unsigned int *)(blob + 12) == 1
                          && *(unsigned int *)(blob + 20) == 3,
                          "the Former Heathens file holds one entry, the purple mask (a Master)");
                }
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
        /* The owner's v1.35.58 live pass (A New Home, The Lost Children): the
           startup scan's seeding, then a load over it -- the village's own
           villagers in those records at a first save with no Village Roster
           file -- and a "founder" whose record keeps parents. */
        if (MARK[game - 1].scan != 0u) {
            villager(4, "Loaded", 1264, 8, 1, 0);
            created(4, MARK[game - 1].scan);
        }
        if (game >= 2) {
            villager(5, "Parented", 1461, 3, 3, 1);
            created(5, MARK[game - 1].founder);
        }
        arrival_tick();
        *(int *)(rec(0) + g->age) = 410;
        save_done(1, buffer);                 /* the new village's first save */
        births_path(3, path);                 /* after the other village's file 2 */
        CHECK(read_into(path) > 0 && strncmp(text, "Village: Arrival Tribe (Save 1)", 31) == 0
              && record_has("Founda", "  Age at arrival: 400\r\n") && record_has("Founda", "  How: Founder\r\n\r\n")
              && record_has("Foundb", "  How: Founder\r\n\r\n") && strstr(text, "Note:") == NULL
              && strstr(text, "Arrived 1\r\n") == NULL,
              "the new village's founders get \"How: Founder\" at its first save, numbered on");
        CHECK(strstr(text, "  Name: Loaded\r\n") == NULL && strstr(text, "  Name: Parented\r\n") == NULL,
              "...but never a villager a load put over the startup scan's seeding, nor one with parents");
        rec(4)[g->active] = 0;
        rec(5)[g->active] = 0;
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

        births_cases();
        quit_cases();
        stale_slot_cases();
        creation_save_cases();
        renamed_cases();
        if (game == 5) {
            /* Another village loaded (another slot): a Heathen in this
               village's record and a believer in the same record of the
               next is no conversion -- the factions seen were the last
               village's (VvfpCauseTick, the game's per-frame path). */
            int_t tick = (int_t)GetProcAddress(cause, "VvfpCauseTick");
            typedef int (__stdcall *state_t)(int);
            state_t state = (state_t)GetProcAddress(cause, "VvfpCauseTestArrivalState");
            villager(20, "Heath", 300, 4, 4, 0);
            rec(20)[VV5_FACTION] = 1;
            created(20, 0);
            tick(game);
            host_slot_value = 2;
            villager(20, "Belie", 300, 4, 5, 0);
            tick(game);
            CHECK(state(20) == 0, "another village's believer in a record a Heathen held is no conversion");
            rec(20)[VV5_FACTION] = 1;
            tick(game);
            rec(20)[VV5_FACTION] = 0;
            tick(game);
            CHECK(state(20) != 0, "...while a Heathen converted in the village played is one");
            host_slot_value = 1;
            rec(20)[g->active] = 0;
        }
        unload();
        free(buffer);
        free_game();
    }
    clean();
    _snprintf(path, MAX_PATH, "%s\\VVFP Parentage Export.dll", files_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Cause of Death.dll", files_dir);
    DeleteFileA(path);
    _snprintf(path, MAX_PATH, "%s\\VVFP Save Reset.dll", files_dir);
    DeleteFileA(path);
    RemoveDirectoryA(files_dir);   /* only when empty */
    _snprintf(path, MAX_PATH, "%s\\Virtual Villagers1.ldw", root);
    DeleteFileA(path);
    printf("== %d failure(s) ==\n", failures);
    return failures == 0 ? 0 : 1;
}
