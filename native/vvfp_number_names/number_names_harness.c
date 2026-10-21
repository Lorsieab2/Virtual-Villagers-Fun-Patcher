/* Runtime harness for "VVFP Number Names.dll"'s VvfpNumberNewName: a baby
   born with the full name of a living villager is numbered at its birth (the
   owner, 2026-10-20).  32-bit only; tests/test_auto_number_names.py builds
   and runs it.

   The companion's own source is included whole, so what runs here is the
   shipped numbering and the shipped reading of the village's setting.  Only
   the "My Documents" folder is the harness's: SHGetSpecialFolderPathA
   answers the folder given on the command line, so every setting file is
   written under it and nothing under Documents\LDW.

   For each of the five games, over a villager table laid out as that game's
   (stride, record base, active byte, name field -- the geometry the
   parentage companion passes, native/parentage_export/parentage_export.c
   GAME_LAYOUTS), with the baby in the table as the game makes it:

     1. A living villager with the baby's full name: the baby is "<name> II";
        the living one keeps their name (the patcher makes them "I").
     2. Living "I" and "III": the baby is "IV" (after the highest).
     3. A living "<name> II" alone: the baby is "III".
     4. No living namesake, or one only by first name ("Chip Kenobi" and
        "Chip Wanjiko"), or a record that is not active, or (The Lost Children
        to New Believers) a record the game keeps that is no villager (a
        statue, a ghost, a stand-in): the name is left as it is.
     5. A name that would not fit the game's limit (27 / 23 characters) is
        left as it is.
     6. A baby whose name already ends in a numeral is left as it is.
     7. The village's setting off ("auto\toff" for its slot) leaves it; another
        slot's off does not; with the village not known yet (slot 0), any
        save's off leaves it, none numbers it.
     8. A pointer that is not one of the table's records changes nothing.
     9. Numbers are never given twice: a number the village's file keeps for
        the name (a dead or gone namesake's) counts like a living one's, the
        number given is added to the file (made, setting on, when there is
        none; a file that is not this patcher's is never replaced), and a
        village not known yet adds nothing.

   Exit code 0 when every check passes. */
#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>

static char g_docs[MAX_PATH];

static BOOL harness_docs(HWND owner, LPSTR path, int folder, BOOL create) {
    (void)owner;
    (void)folder;
    (void)create;
    lstrcpynA(path, g_docs, MAX_PATH);
    return TRUE;
}
#define SHGetSpecialFolderPathA harness_docs

#include "vvfp_number_names.c"

static int failures;
static int checks;

#define CHECK(cond, ...) do { ++checks; if (cond) { printf("  ok   " __VA_ARGS__); printf("\n"); } \
                              else { printf("  FAIL " __VA_ARGS__); printf("\n"); ++failures; } } while (0)

struct layout {
    int game;
    unsigned int stride, slots, base, active, name, capacity;
    unsigned int lookalike;      /* the byte vv_lookalike reads; 0: none (A New Home) */
};
/* Each game's geometry, as native/parentage_export/parentage_export.c's layout table has it. */
static const struct layout LAYOUTS[5] = {
    { 1, 0x3D8,  256, 0,    0x28,   0x370,  0x1C, 0 },
    { 2, 0xE48C, 256, 0,    0x30,   0x564,  0x18, 0x558 },
    { 3, 0x1F8C, 150, 0x14, 0xF10,  0xDD4,  0x19, 0xE94 },
    { 4, 0x2E3C, 150, 0x44, 0x1CC4, 0x1B9C, 0x19, 0x1CC7 },
    { 5, 0x2F44, 150, 0x48, 0x1CD4, 0x1B9C, 0x19, 0x1CE1 },
};

static const struct layout *g;
static unsigned char *table;
static unsigned char *rec(int i) { return table + g->base + (size_t)i * g->stride; }

static void setting_file(int slot, char *path, size_t size) {
    char folder[MAX_PATH];
    save_folder(folder, sizeof folder);
    _snprintf(path, size, "%s\\Virtual Villagers Fun Patcher Data\\Number Names\\"
              "Virtual Villagers %d Number Names - Save %d.dat", folder, g->game, slot);
    path[size - 1] = '\0';
    (void)vv_ps_route_a(path, MAX_PATH - 16, 1);
}

/* A new table and no setting files: every check starts from nothing. */
static void clear(void) {
    char path[MAX_PATH * 2];
    int s;
    memset(table, 0, g->base + (size_t)g->slots * g->stride);
    for (s = 1; s <= 5; ++s) {
        setting_file(s, path, sizeof path);
        DeleteFileA(path);
    }
}

/* The setting file's whole text ("" when there is none). */
static const char *file_text(int slot) {
    static char text[8192];
    char path[MAX_PATH * 2];
    FILE *f;
    size_t got;
    setting_file(slot, path, sizeof path);
    text[0] = '\0';
    f = fopen(path, "rb");
    if (f != NULL) {
        got = fread(text, 1, sizeof text - 1, f);
        text[got] = '\0';
        fclose(f);
    }
    return text;
}

/* Write a setting file of these lines after its header (raw: no header when `raw`). */
static void setting_lines(int slot, const char *lines, int raw) {
    char path[MAX_PATH * 2];
    FILE *f;
    setting_file(slot, path, sizeof path);
    f = fopen(path, "wb");
    if (f == NULL) {
        printf("  FAIL cannot write %s\n", path);
        exit(2);
    }
    if (!raw) {
        fprintf(f, "VVFP NUMBER NAMES v1 game=%d\n", g->game);
    }
    fputs(lines, f);
    fclose(f);
}

static void villager(int i, const char *name) {
    rec(i)[g->active] = 1;
    memset(rec(i) + g->name, 0, g->capacity);
    strncpy((char *)rec(i) + g->name, name, g->capacity - 1);
}

static int number(int child, int slot) {
    return VvfpNumberNewName(g->game, rec(child), table + g->base, g->stride, (int)g->slots, g->active,
                             g->name, g->capacity, slot);
}

static const char *name_of_record(int i) {
    static char out[64];
    memset(out, 0, sizeof out);
    memcpy(out, rec(i) + g->name, g->capacity);
    return out;
}

static void one_game(const struct layout *layout) {
    char want[64], longest[64];
    int fits;
    g = layout;
    table = (unsigned char *)calloc(1, g->base + (size_t)g->slots * g->stride);
    if (table == NULL) {
        exit(2);
    }
    printf("== Virtual Villagers %d ==\n", g->game);

    /* 1. a living namesake: II; the namesake keeps their name */
    clear();
    villager(0, "Chip Kenobi");
    villager(1, "Aipi Wanjiko");
    villager(7, "Chip Kenobi");          /* the baby, as the game has just made it */
    CHECK(number(7, 1) == 1 && strcmp(name_of_record(7), "Chip Kenobi II") == 0,
          "VV%d: a baby born with a living villager's name is \"Chip Kenobi II\" (%s)", g->game, name_of_record(7));
    CHECK(strcmp(name_of_record(0), "Chip Kenobi") == 0, "VV%d: the living namesake keeps their name", g->game);

    /* 2. I and III living: IV */
    clear();
    villager(0, "Chip Kenobi I");
    villager(3, "Chip Kenobi III");
    villager(9, "Chip Kenobi");
    CHECK(number(9, 1) == 1 && strcmp(name_of_record(9), "Chip Kenobi IV") == 0,
          "VV%d: after I and III the baby is IV (%s)", g->game, name_of_record(9));

    /* 3. II alone: III */
    clear();
    villager(2, "Soda II");
    villager(4, "Soda");
    CHECK(number(4, 1) == 1 && strcmp(name_of_record(4), "Soda III") == 0,
          "VV%d: after a living Soda II the baby is Soda III (%s)", g->game, name_of_record(4));

    /* 4. no namesake; first name only; inactive; a look-alike record */
    clear();
    villager(0, "Chip Wanjiko");
    villager(1, "Chip");
    villager(5, "Chip Kenobi");
    CHECK(number(5, 1) == 0 && strcmp(name_of_record(5), "Chip Kenobi") == 0,
          "VV%d: no living Chip Kenobi: the name is left as it is", g->game);
    clear();
    villager(0, "Chip Kenobi");
    rec(0)[g->active] = 0;
    villager(5, "Chip Kenobi");
    CHECK(number(5, 1) == 0 && strcmp(name_of_record(5), "Chip Kenobi") == 0,
          "VV%d: a record that is not active is no villager", g->game);
    if (g->lookalike != 0) {
        clear();
        villager(0, "Chip Kenobi");
        rec(0)[g->lookalike] = 1;
        villager(5, "Chip Kenobi");
        CHECK(number(5, 1) == 0 && strcmp(name_of_record(5), "Chip Kenobi") == 0,
              "VV%d: a statue, ghost or stand-in with the name is no villager", g->game);
    }

    /* 5. no room: a name at the limit stays */
    memset(longest, 0, sizeof longest);
    memset(longest, 'a', ROOM[g->game] - 2);   /* + " II" is one past the limit */
    longest[0] = 'A';
    fits = (int)strlen(longest) + 3 <= (int)ROOM[g->game];
    clear();
    villager(0, longest);
    villager(5, longest);
    CHECK(!fits && number(5, 1) == 0 && strcmp(name_of_record(5), longest) == 0,
          "VV%d: a numbered name past %u characters is left as it is", g->game, ROOM[g->game]);
    longest[ROOM[g->game] - 3] = '\0';       /* + " II" is exactly the limit */
    clear();
    villager(0, longest);
    villager(5, longest);
    _snprintf(want, sizeof want, "%s II", longest);
    CHECK(number(5, 1) == 1 && strcmp(name_of_record(5), want) == 0 && strlen(want) == ROOM[g->game],
          "VV%d: a numbered name of exactly %u characters is given", g->game, ROOM[g->game]);

    /* 6. already numbered */
    clear();
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi II");
    CHECK(number(5, 1) == 0 && strcmp(name_of_record(5), "Chip Kenobi II") == 0,
          "VV%d: a name already numbered is left as it is", g->game);

    /* 7. the village's setting */
    clear();
    setting_lines(1, "auto\toff\n", 0);
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi");
    CHECK(number(5, 1) == 0 && strcmp(name_of_record(5), "Chip Kenobi") == 0,
          "VV%d: the village's setting off: nothing is numbered", g->game);
    CHECK(number(5, 2) == 1 && strcmp(name_of_record(5), "Chip Kenobi II") == 0,
          "VV%d: another village's off is not this one's", g->game);
    clear();
    setting_lines(1, "auto\toff\n", 0);
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi");
    CHECK(number(5, 0) == 0, "VV%d: a village not known yet, with a save's setting off: left as it is", g->game);
    setting_lines(1, "auto\ton\n", 0);
    CHECK(number(5, 0) == 1 && strcmp(name_of_record(5), "Chip Kenobi II") == 0 && strstr(file_text(1), "used") == NULL,
          "VV%d: a village not known yet, every setting on: numbered by the living only, nothing kept", g->game);
    clear();
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi");
    CHECK(number(5, 3) == 1, "VV%d: no setting file is on", g->game);

    /* 9. numbers are never given twice (the owner, 2026-10-20) */
    clear();
    villager(5, "Gata Sirikit");
    CHECK(number(5, 1) == 0, "VV%d: no namesake, living or kept: no number", g->game);
    clear();
    setting_lines(1, "auto\ton\nused\tGata Sirikit\t1\nused\tGata Sirikit\t2\n", 0);
    villager(5, "Gata Sirikit");            /* Gata Sirikit I and II are dead or gone */
    CHECK(number(5, 1) == 1 && strcmp(name_of_record(5), "Gata Sirikit III") == 0,
          "VV%d: the dead's numbers are never given again: the baby is III (%s)", g->game, name_of_record(5));
    CHECK(strstr(file_text(1), "used\tGata Sirikit\t3\n") != NULL && strstr(file_text(1), "auto\ton\n") != NULL,
          "VV%d: the number given is kept in the file, the rest of it as it was", g->game);
    villager(6, "Gata Sirikit");            /* the next one, with III living */
    CHECK(number(6, 1) == 1 && strcmp(name_of_record(6), "Gata Sirikit IV") == 0,
          "VV%d: the next baby of the name is IV", g->game);
    clear();
    setting_lines(1, "auto\ton\nused\tChip Kenobi\t3\n", 0);
    villager(0, "Chip Kenobi II");          /* II living, III dead */
    villager(5, "Chip Kenobi");
    CHECK(number(5, 1) == 1 && strcmp(name_of_record(5), "Chip Kenobi IV") == 0,
          "VV%d: after a living II and a dead III, IV", g->game);
    clear();
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi");
    CHECK(number(5, 1) == 1 && strstr(file_text(1), "VVFP NUMBER NAMES v1 game=") == file_text(1)
          && strstr(file_text(1), "\nauto\ton\nused\tChip Kenobi\t2\n") != NULL,
          "VV%d: with no file yet, one is made with the setting on and the number", g->game);
    clear();
    setting_lines(1, "something else\n", 1);
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi");
    CHECK(number(5, 1) == 1 && strcmp(file_text(1), "something else\n") == 0,
          "VV%d: a file that is not this patcher's is never replaced", g->game);

    /* 8. not a record of the table */
    clear();
    villager(0, "Chip Kenobi");
    villager(5, "Chip Kenobi");
    CHECK(VvfpNumberNewName(g->game, rec(5) + 4, table + g->base, g->stride, (int)g->slots, g->active, g->name,
                            g->capacity, 1) == 0
          && strcmp(name_of_record(5), "Chip Kenobi") == 0,
          "VV%d: a pointer between records changes nothing", g->game);
    free(table);
}

int main(int argc, char **argv) {
    int k;
    if (argc != 2) {
        printf("usage: number_names_harness <documents folder>\n");
        return 2;
    }
    lstrcpynA(g_docs, argv[1], MAX_PATH);
    CreateDirectoryA(g_docs, NULL);
    for (k = 0; k < 5; ++k) {
        one_game(&LAYOUTS[k]);
    }
    printf("== %d check(s), %d failure(s) ==\n", checks, failures);
    return failures ? 1 : 0;
}
