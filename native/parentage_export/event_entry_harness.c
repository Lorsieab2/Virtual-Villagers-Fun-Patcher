/* Runtime harness: a branching Custom Island Event keeps ONE entry in the Island Events log, and the log matches
   the save at every save (the owner, 2026-11-12).  tests/test_island_event_entry_log.py builds and runs it (32-bit
   MSVC only).

   "VVFP Story Upgrades.dll" (story_graph.inc) hands the entry so far to WriteVillageEventEntry after each page,
   through "VVFP Island Events.dll"; the entry's held record is replaced each time, and each save writes what it
   has gained onto the same entry, append-only:

     1. Pages 1 and 2, then a save: the log holds the entry with both pages, one "Island event <n>", left open.
     2. A quit (this companion's memory gone), a reload told what the save's log holds, page 3 and the end, then a
        save: the log reads as ONE entry with pages 1-3 in order, nothing twice, closed with its blank line.
     3. Another island event's record after it: its own record, after the blank line, numbered next.
     4. An entry left open when another record comes first: that record closes it first, and the entry's next
        part says "(continued) Island event <n>" -- never numbered, never counted -- with only its new lines.
     5. Nothing is written before a save.

   The companion's source is compiled whole; the game's save manager is a stand-in.  Documents is redirected to a
   throwaway folder (harness_ldw_tree.h); the statistics companion is a stand-in file beside this executable,
   removed at the end.  Exit code 0 when every check passes. */
#include <stdio.h>
#include <string.h>
#include <windows.h>
#include <shlobj.h>

static const unsigned char *harness_managers[6];
#define VV_GAME_SAVE_MANAGER_AT(game) ((const unsigned char *const volatile *)&harness_managers[game])

#define main parentage_export_main_unused
#include "../parentage_export/parentage_export.c"
#undef main

#include "../shared/harness_ldw_tree.h"

static int failures;
static int checks;

static void check(int ok, const char *what) {
    ++checks;
    printf("  %s %s\n", ok ? "ok  " : "FAIL", what);
    failures += !ok;
}

static unsigned char g_manager[0x40000];

#define GAME GAME_VV3
#define TRIBE "Village: Kalahuna Tribe 3: N (Save 1)\n"

static const struct game_layout *g;
static unsigned char *table;

static void villager(int i, const char *name) {
    unsigned char *r = table + g->record_base + (size_t)i * g->stride;
    unsigned int s;
    memset(r, 0, g->stride);
    r[g->active] = 1;
    *(int *)(r + g->age) = 600;
    strncpy((char *)r + g->name, name, g->name_capacity - 1);
    for (s = 0; s < g->preference_slots; ++s) {
        *(int *)(r + g->likes + s * 4) = -1;
        *(int *)(r + g->dislikes + s * 4) = -1;
    }
}

static int save(void) {
    vv_village_publish(TRIBE);
    return ensure_parentage_log(GAME, TRIBE, table);
}

static char logtext[1 << 16];

/* Save 1's Island Events log, file 1, into logtext (its carriage returns kept); 0 when it is not there. */
static int read_log(void) {
    char docs[MAX_PATH], exe[MAX_PATH], path[MAX_PATH * 2], *base, *dot;
    FILE *f;
    size_t n;
    logtext[0] = '\0';
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE) || GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base != NULL ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) *dot = '\0';
    _snprintf(path, sizeof path,
              "%s\\LDW\\%s\\Virtual Villagers Fun Patcher\\Save 1\\Logs\\Island Events\\"
              "Virtual Villagers 3 Island Events Log 1.txt", docs, base);
    path[sizeof path - 1] = '\0';
    f = fopen(path, "rb");
    if (f == NULL) {
        return 0;
    }
    n = fread(logtext, 1, sizeof logtext - 1, f);
    logtext[n] = '\0';
    fclose(f);
    return 1;
}

static int count(const char *text, const char *needle) {
    int n = 0;
    const char *p = text;
    while ((p = strstr(p, needle)) != NULL) {
        ++n;
        p += strlen(needle);
    }
    return n;
}

/* A new process: this companion's memory of held records and open entries gone (the log on disk stays). */
static void new_session(void) {
    int i;
    for (i = 0; i < pending_count; ++i) {
        free(pending[i].text);
    }
    pending_count = 0;
    memset(event_entries, 0, sizeof event_entries);
}

#define P1 "  Event: Three Gifts\n  Bea Kalahuna: Food 100 -> 200\n"
#define P2 P1 "  Bea Kalahuna: Research 0 -> 5\n"
#define P3 P2 "  Bea Kalahuna: Health 90 -> 40\n"

int main(void) {
    harness_ldw_tree_begin();       /* first: Documents is a throwaway folder from here on */
    char exe[MAX_PATH], files_dir[MAX_PATH], marker[MAX_PATH], *cut;
    HANDLE stand_in;

    printf("a branching event's one Island Events log entry, matching the save at every save\n");
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0 || (cut = strrchr(exe, '\\')) == NULL) {
        return 2;
    }
    *cut = '\0';
    _snprintf(files_dir, MAX_PATH, "%s\\Virtual Villagers Fun Patcher Files", exe);
    files_dir[MAX_PATH - 1] = '\0';
    _snprintf(marker, MAX_PATH, "%s\\VVFP Statistics Export.dll", files_dir);
    marker[MAX_PATH - 1] = '\0';
    CreateDirectoryA(files_dir, NULL);
    stand_in = CreateFileA(marker, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    if (stand_in == INVALID_HANDLE_VALUE) {
        return 2;
    }
    CloseHandle(stand_in);

    g = layout_of(GAME);
    table = (unsigned char *)calloc(1, g->record_base + (size_t)g->slots * g->stride);
    if (table == NULL) {
        return 2;
    }
    memset(g_manager, 0, sizeof g_manager);
    *(int *)(g_manager + VV_GAME_SAVE_SLOT_FIELD[GAME]) = 1;
    harness_managers[GAME] = g_manager;
    villager(0, "Bea Kalahuna");
    villager(1, "Adam Kalahuna");
    last_table[GAME] = table;
    check(save() == 1, "the village is saved (its logs made)");

    printf("-- pages 1 and 2, then a save --\n");
    check(WriteVillageEventEntry(GAME, 7, P1, -1, 0) == 1, "page 1's entry is held");
    check(WriteVillageEventEntry(GAME, 7, P2, -1, 0) == 1, "page 2's replaces it");
    read_log();
    check(strstr(logtext, "Three Gifts") == NULL, "nothing is written before a save");
    check(save() == 1 && read_log(), "the save writes the log");
    check(count(logtext, "Island event ") == 1 && strstr(logtext,
          "Island event 1\r\n  Event: Three Gifts\r\n  Bea Kalahuna: Food 100 -> 200\r\n"
          "  Bea Kalahuna: Research 0 -> 5\r\n") != NULL,
          "the log matches the save: ONE entry with pages 1 and 2 (full names)");
    check(strlen(logtext) >= 4 && strcmp(logtext + strlen(logtext) - 4, "\r\n\r\n") != 0,
          "...left open while the event goes on");

    printf("-- a quit; the reload, page 3 and the end, then a save --\n");
    new_session();
    check(WriteVillageEventEntry(GAME, 7, P2, (int)strlen(P2), 0) == 1, "the reload tells the log what it holds");
    check(WriteVillageEventEntry(GAME, 7, P3, -1, 1) == 1, "page 3, and the event is over");
    check(save() == 1 && read_log(), "the save writes the log");
    check(count(logtext, "Island event ") == 1 && count(logtext, "Food 100 -> 200") == 1
          && count(logtext, "Research 0 -> 5") == 1 && strstr(logtext,
          "Island event 1\r\n  Event: Three Gifts\r\n  Bea Kalahuna: Food 100 -> 200\r\n"
          "  Bea Kalahuna: Research 0 -> 5\r\n  Bea Kalahuna: Health 90 -> 40\r\n\r\n") != NULL,
          "ONE entry with pages 1-3 in order, nothing twice, closed with its blank line");

    printf("-- another island event after it --\n");
    check(WriteVillageEventRecord(GAME, "  Event: The Strange Berries\n  Changes: none\n") == 1 && save() == 1
          && read_log(), "another event's record, at the next save");
    check(strstr(logtext, "\r\n\r\nIsland event 2\r\n  Event: The Strange Berries\r\n") != NULL
          && strstr(logtext, "\r\n\r\n\r\nIsland event 2") == NULL, "its own record, numbered next, one blank line between");

    printf("-- an entry left open, another record first, then the entry goes on --\n");
    check(WriteVillageEventEntry(GAME, 9, "  Event: Two Paths\n  Choice: Left\n  Adam Kalahuna: Sick no -> yes\n",
                                 -1, 0) == 1 && save() == 1, "the entry's first part, at a save");
    check(WriteVillageEventRecord(GAME, "  Event: The Canoe\n  Changes: none\n") == 1 && save() == 1 && read_log(),
          "another record before the entry goes on");
    check(strstr(logtext, "Sick no -> yes\r\n\r\nIsland event 4\r\n") != NULL,
          "the open entry is closed first: the records never run together");
    check(WriteVillageEventEntry(GAME, 9, "  Event: Two Paths\n  Choice: Left\n  Adam Kalahuna: Sick no -> yes\n"
                                 "  Adam Kalahuna: Health 90 -> 50\n", -1, 1) == 1 && save() == 1 && read_log(),
          "the entry's next part");
    check(strstr(logtext, "(continued) Island event 3\r\n  Adam Kalahuna: Health 90 -> 50\r\n\r\n") != NULL
          && count(logtext, "Sick no -> yes") == 1 && count(logtext, "\nIsland event ") == 4,
          "a marked continuation of entry 3: only its new lines, never numbered or counted");

    DeleteFileA(marker);
    RemoveDirectoryA(files_dir);
    harness_ldw_tree_end();
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures == 0 ? 0 : 1;
}
