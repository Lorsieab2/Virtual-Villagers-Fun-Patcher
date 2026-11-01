/* Runtime harness: a record goes to the log of the save the game had loaded when it was made, and the
   per-save files a record reads (Custom Titles) are the loaded save's -- never the village header
   published at the last SAVE.  tests/test_records_go_to_their_own_save.py builds and runs it (32-bit
   MSVC only).

   The header (" (Save N)") is published only when a village is saved, so after the player saves
   village A and loads B it still names A until B is saved.  Three things read it:

     1. A HELD record (made before the village on screen was saved) was written at the next save under
        THAT save's header.  The owner's Secret City, 2026-10-31: Conceptions 312 and 316 (Save 2's
        Kiwi Jumapili and Matate Jumapili with Motu Okelani) were written into Save 1's log at Save 1's
        save.  The owner's decision: a held record goes to its own save's log -- the slot the game had
        loaded when it was made (captured then); one made with no slot loaded (the pre-tribe
        simulation, slot 0) is written as before.
     2. A record written AT ONCE under the recalled header when the table matched the tribe saved
        last: a copy of that village in another slot passed, and its records went into the first
        save's log.
     3. The Custom Title of a villager in a Death / Appearance / Name record, and the title VVFP Island
        Events compares (VillageCustomTitle): read from the recalled header's slot's file.

   The companion's source is compiled whole; the game's save manager (native/shared/game_save_slot.h)
   is a stand-in.  Documents is redirected to a throwaway folder (harness_ldw_tree.h); the statistics
   companion is a stand-in file beside this executable, removed at the end.  Exit code 0 when every
   check passes. */
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

/* A stand-in save manager whose slot field says `slot`. */
static unsigned char g_manager[0x40000];

static void game_slot(int game, int slot) {
    memset(g_manager, 0, sizeof g_manager);
    *(int *)(g_manager + VV_GAME_SAVE_SLOT_FIELD[game]) = slot;
    harness_managers[game] = g_manager;
}

#define GAME GAME_VV3
#define TRIBE_A "Village: Kalahuna Tribe 3: N (Save 1)\n"
#define TRIBE_B "Village: Kalahuna Tribe 3: M (Save 2)\n"
#define TRIBE_C "Village: Kalahuna Tribe 3: M copy (Save 3)\n"

static const struct game_layout *g;
static unsigned char *table;

static unsigned char *rec(int i) {
    return table + g->record_base + (size_t)i * g->stride;
}

static void villager(int i, const char *name, int age, int head, int body) {
    unsigned int s;
    memset(rec(i), 0, g->stride);
    rec(i)[g->active] = 1;
    *(int *)(rec(i) + g->age) = age;
    *(int *)(rec(i) + g->head) = head;
    *(int *)(rec(i) + g->body) = body;
    strncpy((char *)rec(i) + g->name, name, g->name_capacity - 1);
    for (s = 0; s < g->preference_slots; ++s) {
        *(int *)(rec(i) + g->likes + s * 4) = -1;
        *(int *)(rec(i) + g->dislikes + s * 4) = -1;
    }
}

/* The three tables the game holds in turn: the pre-tribe simulation, Save 1's tribe, Save 2's. */
static void simulation(void) {
    memset(table, 0, g->record_base + (size_t)g->slots * g->stride);
    villager(0, "Bikini", 397, 16, 5);
    villager(1, "Piko", 498, 0, 15);
    villager(2, "Aipi", 530, 13, 27);
    villager(3, "Naloto", 381, 16, 18);
}

static void tribe_a(void) {
    memset(table, 0, g->record_base + (size_t)g->slots * g->stride);
    villager(0, "Ginger Bandele", 861, 17, 12);
    villager(1, "Pio Bandele", 566, 19, 8);
    villager(2, "Lomai Uzumati", 700, 8, 28);
    villager(3, "Parai Pauwau", 650, 18, 22);
}

static void tribe_b(void) {
    memset(table, 0, g->record_base + (size_t)g->slots * g->stride);
    villager(0, "Kiwi Jumapili", 931, 3, 16);
    villager(1, "Motu Okelani", 750, 21, 2);
    villager(2, "Matate Jumapili", 890, 3, 7);
    villager(3, "Zucca Tasunke", 555, 9, 9);
}

/* The record text after "Conception <n>": enough to find it in a log. */
static int conceive(const char *mother) {
    char text[128];
    _snprintf(text, sizeof text, "  Mother: %s\n\n", mother);
    text[sizeof text - 1] = '\0';
    return emit_record(GAME, 0, table, text);
}

static int save(const char *header) {
    vv_village_publish(header);
    return ensure_parentage_log(GAME, header, table);
}

static char logtext[1 << 16];

/* Save <slot>'s Births and Conceptions log, file 1, read into logtext; 0 when it is not there. */
static int read_log(int slot) {
    char docs[MAX_PATH], exe[MAX_PATH], path[MAX_PATH * 2], *base, *dot;
    FILE *f;
    size_t n;
    logtext[0] = '\0';
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)
        || GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base != NULL ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) *dot = '\0';
    _snprintf(path, sizeof path,
              "%s\\LDW\\%s\\Virtual Villagers Fun Patcher\\Save %d\\Logs\\Births and Conceptions\\"
              "Virtual Villagers 3 Births and Conceptions Log 1.txt", docs, base, slot);
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

static int logged(int slot, const char *mother) {
    char needle[96];
    _snprintf(needle, sizeof needle, "  Mother: %s\r\n", mother);
    needle[sizeof needle - 1] = '\0';
    return read_log(slot) && strstr(logtext, needle) != NULL;
}

/* The Custom Titles file of `slot`, with one title bound to record 0 of the table as it is now. */
static int write_titles(int slot, const char *title) {
    static unsigned char data[VV_TITLES_FILE_MAX];
    vv_custom_title entry;
    char folder[MAX_PATH], path[MAX_PATH];
    DWORD size, wrote = 0;
    HANDLE h;
    char *cut;
    memset(&entry, 0, sizeof entry);
    entry.index = 0;
    entry.fingerprint = vv_title_identity(rec(0), g->name, g->name_capacity, g->likes, g->dislikes,
                                          g->preference_slots);
    lstrcpynA(entry.title, title, VV_TITLE_BYTES);
    size = vv_titles_serialise(GAME, &entry, 1, data);
    if (!vv_save_folder(folder, (int)sizeof("\\" VV_TITLES_SUBFOLDER "\\Custom Titles - Save 0.dat"))) {
        return 0;
    }
    lstrcatA(folder, "\\" VV_TITLES_SUBFOLDER);
    if (!vv_titles_file_name(path, MAX_PATH, folder, slot)) {
        return 0;
    }
    (void)vv_ps_route_a(path, MAX_PATH, 0);   /* where the companion reads it (per_save.h) */
    lstrcpynA(folder, path, MAX_PATH);
    cut = strrchr(folder, '\\');
    if (cut == NULL) {
        return 0;
    }
    *cut = '\0';
    (void)SHCreateDirectoryExA(NULL, folder, NULL);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    WriteFile(h, data, size, &wrote, NULL);
    CloseHandle(h);
    return wrote == size;
}

static const char *title_now(void) {
    static char line[96];
    if (!record_custom_title(GAME, g, rec(0), table, 0, line, sizeof line)) {
        return "";
    }
    return line;
}

int main(void) {
    harness_ldw_tree_begin();       /* first: Documents is a throwaway folder from here on */
    char exe[MAX_PATH], files_dir[MAX_PATH], marker[MAX_PATH], *cut;
    HANDLE stand_in;

    printf("held records and titles go to the loaded save's files\n");
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0 || (cut = strrchr(exe, '\\')) == NULL) {
        printf("could not locate this executable\n");
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
        printf("could not create the statistics stand-in\n");
        return 2;
    }
    CloseHandle(stand_in);

    g = layout_of(GAME);
    table = (unsigned char *)calloc(1, g->record_base + (size_t)g->slots * g->stride);
    if (table == NULL) {
        return 2;
    }

    printf("-- a new session: the pre-tribe simulation, then Save 2 and Save 1 loaded in turn --\n");
    vv_village_publish("");                       /* nothing saved yet this session */
    game_slot(GAME, 0);                           /* no slot loaded */
    simulation();
    check(conceive("Bikini") == 1, "a pre-tribe simulation conception (no slot) is held");
    game_slot(GAME, 2);
    tribe_b();
    check(conceive("Kiwi Jumapili") == 1, "a conception while Save 2 is loaded is held");
    game_slot(GAME, 1);
    tribe_a();
    check(conceive("Ginger Bandele") == 1, "a conception while Save 1 is loaded is held");
    check(!read_log(1) && !read_log(2), "nothing is written before a save");

    printf("-- Save 1 is saved --\n");
    check(save(TRIBE_A) == 1, "Save 1's save creates its log");
    check(logged(1, "Ginger Bandele"), "Save 1's own conception is in Save 1's log");
    check(logged(1, "Bikini"), "the no-slot (pre-tribe simulation) conception is written at that save, as before");
    check(!logged(1, "Kiwi Jumapili"),
          "the conception made while Save 2 was loaded is NOT written into Save 1's log");
    check(!read_log(2), "...and not yet anywhere: Save 2 has not been saved");
    check(pending_count == 1 && pending[0].slot == 2, "it is still held, for slot 2");

    printf("-- Save 2 is loaded and saved --\n");
    game_slot(GAME, 2);
    tribe_b();
    check(save(TRIBE_B) == 1, "Save 2's save creates its log");
    check(logged(2, "Kiwi Jumapili"), "the held Save 2 conception is written into Save 2's log");
    check(!logged(2, "Ginger Bandele") && !logged(2, "Bikini"), "nothing of Save 1's is in Save 2's log");
    check(pending_count == 0, "nothing is held any more");

    printf("-- the tribe saved last, loaded as a copy in Save 3 (its header still names Save 2) --\n");
    game_slot(GAME, 3);                           /* the same table: a copy of Save 2's village */
    check(conceive("Matate Jumapili") == 1, "a conception in the copy is accepted");
    check(!logged(2, "Matate Jumapili"),
          "it is NOT written at once into Save 2's log, though the table matches the tribe saved last");
    check(pending_count == 1 && pending[0].slot == 3, "it is held for slot 3");
    check(save(TRIBE_C) == 1 && logged(3, "Matate Jumapili"), "Save 3's save writes it into Save 3's log");
    check(!logged(2, "Matate Jumapili"), "...and Save 2's log never gets it");

    printf("-- the village saved last, still loaded: written at once, as before --\n");
    game_slot(GAME, 2);
    vv_village_publish(TRIBE_B);
    (void)ensure_parentage_log(GAME, TRIBE_B, table);
    check(conceive("Zucca Tasunke") == 1 && logged(2, "Zucca Tasunke"),
          "the header names the loaded slot and the table matches: written straight into Save 2's log");
    harness_managers[GAME] = NULL;                /* no save manager: the old rule alone */
    check(conceive("Kiwi Jumapili II") == 1 && logged(2, "Kiwi Jumapili II"),
          "no save manager to read: the table check alone, as before");

    printf("-- Custom titles: the loaded save's file, never the one saved last --\n");
    tribe_b();
    check(write_titles(1, "Title of Save One") && write_titles(2, "Title of Save Two"),
          "Save 1's and Save 2's Custom Titles files are written");
    vv_village_publish(TRIBE_B);                  /* Save 2 was saved... */
    game_slot(GAME, 1);                           /* ...then Save 1 loaded */
    check(strstr(title_now(), "Custom title: Title of Save One") != NULL,
          "Save 2 saved, Save 1 loaded: the title is Save 1's, not the published Save 2's");
    game_slot(GAME, 2);
    check(strstr(title_now(), "Custom title: Title of Save Two") != NULL, "Save 2 loaded: Save 2's title");
    game_slot(GAME, 0);
    check(title_now()[0] == '\0', "the game has no slot loaded: no title (never the stale Save 2's)");
    game_slot(GAME, 4);
    check(title_now()[0] == '\0', "a slot with no Custom Titles file: no title");
    harness_managers[GAME] = NULL;
    check(strstr(title_now(), "Custom title: Title of Save Two") != NULL,
          "no save manager to read at all: the published header, as before");
    game_slot(GAME_VV5, 3);
    check(village_files_slot(GAME_VV5) == 3, "New Believers' Former Heathens file: the loaded slot's (3)");
    game_slot(GAME_VV5, 0);
    check(village_files_slot(GAME_VV5) == 0, "...and none while no slot is loaded");
    harness_managers[GAME_VV5] = NULL;

    DeleteFileA(marker);
    RemoveDirectoryA(files_dir);
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    exit(failures ? 1 : 0);
}
