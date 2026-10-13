/* The Village Population roster and the Village History print a villager's
 * custom title (Story / Cheat Upgrades, Custom Island Event).
 *
 * population_export.c is compiled here unchanged; only the save folder is
 * replaced, by a fresh folder under %TEMP% (never Documents\LDW).  A
 * synthetic The Secret City village (the exporter's own geometry) and a
 * custom titles .dat for slot 2 are planted, the real WriteVillagePopulation
 * is called with the header "Village: Test (Save 2)", and the roster and the
 * history it writes are read back:
 *
 *   the titled villager's block carries "  Custom title: <text>" right after
 *     its name, in both files;
 *   a title whose record now holds somebody else is not printed;
 *   a header naming another slot prints no titles at all;
 *   in ALL FIVE games (run_twins, each game's own geometry): twins with one
 *     name, likes and dislikes and different looks each show their own bound
 *     title (native/shared/custom_title_shown.h, the Story companion's rule);
 *     identical twins show none; a version 2 entry (looks not known) with two
 *     carriers shows none, with one it is shown; the entry's record holding
 *     the other twin (a stale file) shows none; twins with the same looks are
 *     told apart by a skill; a pending entry shows nowhere.
 *
 * Built and run by scripts/build_custom_title_log_harness.ps1 (32-bit).
 * Exit code 0 when every check passes. */
#include <stdio.h>
#include <windows.h>

static char g_root[MAX_PATH];

int vv_save_folder(char *out, int reserve) {
    if (lstrlenA(g_root) + reserve >= MAX_PATH) {
        return 0;
    }
    lstrcpyA(out, g_root);
    CreateDirectoryA(out, NULL);
    return 1;
}

int vv_save_folder_w(wchar_t *out, int reserve) {
    char narrow[MAX_PATH];
    if (!vv_save_folder(narrow, reserve)) {
        return 0;
    }
    MultiByteToWideChar(CP_ACP, 0, narrow, -1, out, MAX_PATH);
    return 1;
}

int vv_save_subfolder(char *out, const char *sub, int reserve) {
    char built[MAX_PATH];
    int n;
    const char *p;
    if (!vv_save_folder(built, lstrlenA(sub) + 1 + reserve)) {
        return 0;
    }
    lstrcatA(built, "\\");
    for (p = sub; *p; ++p) {
        if (*p == '\\') {
            CreateDirectoryA(built, NULL);
        }
        n = lstrlenA(built);
        built[n] = *p;
        built[n + 1] = '\0';
    }
    CreateDirectoryA(built, NULL);
    lstrcpyA(out, built);
    return 1;
}

int vv_save_subfolder_w(wchar_t *out, const wchar_t *sub, int reserve) {
    char narrow_sub[MAX_PATH];
    char narrow[MAX_PATH];
    WideCharToMultiByte(CP_ACP, 0, sub, -1, narrow_sub, MAX_PATH, NULL, NULL);
    if (!vv_save_subfolder(narrow, narrow_sub, reserve)) {
        return 0;
    }
    MultiByteToWideChar(CP_ACP, 0, narrow, -1, out, MAX_PATH);
    return 1;
}

#include "population_export.c"

static int g_failures;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++g_failures;
    }
}

static char *read_all(const char *path) {
    static char text[1 << 16];
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    DWORD got = 0;
    text[0] = '\0';
    if (h != INVALID_HANDLE_VALUE) {
        ReadFile(h, text, sizeof text - 1, &got, NULL);
        CloseHandle(h);
    }
    text[got] = '\0';
    {
        /* The logs are written in text mode (CRLF); compare by line. */
        char *in = text;
        char *out = text;
        for (; *in; ++in) {
            if (*in != '\r') {
                *out++ = *in;
            }
        }
        *out = '\0';
    }
    return text;
}

#define V3_RVA 0x19E110u
#define V3_BASE 0x14u
#define V3_STRIDE 0x1F8Cu

static unsigned char *g_module;

static unsigned char *record(int index) {
    return g_module + V3_RVA + V3_BASE + (unsigned int)index * V3_STRIDE;
}

static void villager(int index, const char *name) {
    unsigned char *r = record(index);
    r[0xF10] = 1;
    lstrcpynA((char *)r + 0xDD4, name, 0x19);
    *(int *)(r + 0xDC4) = 600;
    /* Alive: the exporter lists a record only at health above 0 (population_export.c
       living_villager; VV3's health +0xE78) -- at 0 it is a body awaiting burial. */
    *(int *)(r + 0xE78) = 100;
}

/* One folder of logs per save slot (native/shared/log_slot.h): the roster or history of the
   village "(Save <slot>)" is in "...Logs\Save <slot>\<folder>"; slot 0 (no slot named) is the
   shared folder. */
static void log_file(char *out, int slot, const char *folder, const char *name) {
    if (slot == 0) {
        wsprintfA(out, "%s\\Virtual Villagers Fun Patcher Logs\\%s\\%s", g_root, folder, name);
    } else {
        wsprintfA(out, "%s\\Virtual Villagers Fun Patcher Logs\\Save %d\\%s\\%s", g_root, slot, folder, name);
    }
}
#define ROSTER(slot) log_file(roster, (slot), "Tribe Population", "Village Population 1.txt")

static void write_titles(int slot, const vv_custom_title *entries, int count) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    static unsigned char data[VV_TITLES_FILE_MAX];
    DWORD size = vv_titles_serialise(3, entries, count, data);
    DWORD written = 0;
    HANDLE h;
    vv_save_subfolder(folder, VV_TITLES_SUBFOLDER, 64);
    vv_titles_file_name(path, MAX_PATH, folder, slot);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    WriteFile(h, data, size, &written, NULL);
    CloseHandle(h);
}

/* ---- Twins, in all five games -------------------------------------------

   Each game's record geometry, restated from the Story / Cheat Upgrades
   companion's adapters (story_c1.inc .. story_c5.inc: off_name, name_bytes,
   off_sex, off_age, off_head, off_body, off_likes, off_dislikes, off_skills,
   pref_slots, skill_count, skills_float), with the table's place, live byte
   and health from the exporter's own layout -- so a drift between the
   companion that keeps a title's looks and the exporter that reads them
   fails here. */
static const struct twin_game {
    int game;
    unsigned int rva;
    int rva_is_pointer;
    unsigned int base, stride, slots, active, health;
    unsigned int name, name_cap, sex, age, head, body, likes, dislikes, pref_slots;
    unsigned int skills, skill_count;
    int skills_float;
} TWIN_GAMES[5] = {
    { 1, 0x8B614u, 1, 0, 0x3D8u, 256, 0x28u, 0x344u,
      0x370u, 0x1Cu, 0x350u, 0x348u, 0x360u, 0x364u, 0x398u, 0x3A8u, 4, 0x3BCu, 5, 0 },
    { 2, 0x99F24u, 1, 0, 0xE48Cu, 256, 0x30u, 0x52Cu,
      0x564u, 0x18u, 0x538u, 0x530u, 0x548u, 0x54Cu, 0x5F0u, 0x6E8u, 62, 0x7E4u, 5, 0 },
    { 3, 0x19E110u, 0, 0x14u, 0x1F8Cu, 150, 0xF10u, 0xE78u,
      0xDD4u, 0x19u, 0xDC8u, 0xDC4u, 0xDF0u, 0xDF4u, 0xFB4u, 0xFC0u, 3, 0xEACu, 5, 0 },
    { 4, 0x10E568u, 0, 0x44u, 0x2E3Cu, 150, 0x1CC4u, 0x1C40u,
      0x1B9Cu, 0x19u, 0x1B90u, 0x1B8Cu, 0x1BB8u, 0x1BBCu, 0x1E60u, 0x1E6Cu, 3, 0x1C5Cu, 5, 1 },
    { 5, 0x154148u, 0, 0x48u, 0x2F44u, 150, 0x1CD4u, 0x1C40u,
      0x1B9Cu, 0x19u, 0x1B90u, 0x1B8Cu, 0x1BB8u, 0x1BBCu, 0x1F5Cu, 0x1F68u, 3, 0x1C5Cu, 6, 1 },
};

static const struct twin_game *tg;
static unsigned char *g_twin_module;
static unsigned char *g_twin_table;

static unsigned char *twin_record(int index) {
    return g_twin_table + tg->base + (unsigned int)index * tg->stride;
}

static unsigned int twin_skill(int value) {
    if (tg->skills_float) {
        float f = (float)value;
        unsigned int raw;
        memcpy(&raw, &f, sizeof raw);
        return raw;
    }
    return (unsigned int)value;
}

static void twin_villager(int index, const char *name, int head, int body, int skill) {
    unsigned char *r = twin_record(index);
    unsigned int k;
    memset(r, 0, tg->stride);
    r[tg->active] = 1;
    *(int *)(r + tg->health) = 100;
    lstrcpynA((char *)r + tg->name, name, (int)tg->name_cap);
    *(int *)(r + tg->age) = 900;
    *(int *)(r + tg->head) = head;
    *(int *)(r + tg->body) = body;
    *(int *)(r + tg->likes) = 2;
    *(int *)(r + tg->dislikes) = 1;
    for (k = 0; k < tg->skill_count; ++k) {
        *(unsigned int *)(r + tg->skills + 4u * k) = twin_skill(skill);
    }
}

static unsigned int twin_fingerprint(int index) {
    return vv_title_identity(twin_record(index), tg->name, tg->name_cap, tg->likes, tg->dislikes, tg->pref_slots);
}

static vv_custom_title twin_entry(unsigned int index, int known, int head, int body, int skill, const char *title) {
    vv_custom_title e;
    unsigned int k;
    memset(&e, 0, sizeof e);
    e.index = index;
    e.fingerprint = twin_fingerprint(1);
    if (known) {
        e.flags = VV_TITLE_KNOWN;
        e.looks.age = 800;
        e.looks.head = head;
        e.looks.body = body;
        for (k = 0; k < tg->skill_count; ++k) {
            e.looks.skills[k] = twin_skill(skill);
        }
    }
    lstrcpyA(e.title, title);
    return e;
}

static void twin_write_titles(const vv_custom_title *entries, int count) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    static unsigned char data[VV_TITLES_FILE_MAX];
    DWORD size = vv_titles_serialise(tg->game, entries, count, data);
    DWORD written = 0;
    HANDLE h;
    vv_save_subfolder(folder, VV_TITLES_SUBFOLDER, 64);
    vv_titles_file_name(path, MAX_PATH, folder, 3);
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, 0, NULL);
    WriteFile(h, data, size, &written, NULL);
    CloseHandle(h);
}

/* The roster and the history of slot 3, after an export; the roster in `roster_out`. */
static void twin_export(char *roster_out, size_t cap) {
    char roster[MAX_PATH];
    char history[MAX_PATH];
    WriteVillagePopulation(tg->game, g_twin_module, "Village: Twins (Save 3)\n");
    log_file(roster, 3, "Tribe Population", "Village Population 1.txt");
    lstrcpynA(roster_out, read_all(roster), (int)cap);
    log_file(history, 3, "Tribe History", "Village History 1.txt");
    lstrcatA(roster_out, "\n--- history ---\n");
    {
        /* The history appends a snapshot per export: only this export's, the last. */
        const char *all = read_all(history);
        const char *last = all;
        const char *at = all;
        while ((at = strstr(at, "=== Virtual Villagers")) != NULL) {
            last = at;
            ++at;
        }
        lstrcatA(roster_out, last);
    }
}

static int count_of(const char *text, const char *what) {
    int n = 0;
    const char *at = text;
    while ((at = strstr(at, what)) != NULL) {
        ++n;
        ++at;
    }
    return n;
}

/* A failed twin check shows what the logs said. */
static void twin_check(int condition, const char *what, const char *text) {
    check(condition, what);
    if (!condition) {
        printf("----- the roster and history -----\n%.3000s\n-----\n", text);
    }
}

static void run_twins(int game) {
    static char text[1 << 17];
    char what[160];
    vv_custom_title entries[2];
    size_t module_size;
    tg = &TWIN_GAMES[game - 1];
    printf("\nVirtual Villagers %d: twins\n", game);
    module_size = tg->rva + (tg->rva_is_pointer ? 0x1000u : tg->base + tg->slots * tg->stride + 0x1000u);
    g_twin_module = (unsigned char *)VirtualAlloc(NULL, module_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (tg->rva_is_pointer) {
        g_twin_table = (unsigned char *)VirtualAlloc(NULL, tg->base + tg->slots * tg->stride,
                                                     MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        *(unsigned char **)(g_twin_module + tg->rva) = g_twin_table;
    } else {
        g_twin_table = g_twin_module + tg->rva;
    }
    twin_villager(0, "Hina", 1, 1, 0);
    twin_villager(1, "Kai", 3, 4, 0);       /* twins: one name, likes and dislikes */
    twin_villager(2, "Kai", 5, 6, 0);
    wsprintfA(what, "setup: twin Kais [1] and [2] share one fingerprint (game %d)", game);
    twin_check(twin_fingerprint(1) == twin_fingerprint(2), what, text);

    /* Different looks: each has their own bound title (the game shows it so). */
    entries[0] = twin_entry(1, 1, 3, 4, 0, "Kai Three Four");
    entries[1] = twin_entry(2, 1, 5, 6, 0, "Kai Five Six");
    twin_write_titles(entries, 2);
    twin_export(text, sizeof text);
    wsprintfA(what, "TWINS WITH DIFFERENT LOOKS EACH SHOW THEIR OWN BOUND TITLE, ROSTER AND HISTORY (game %d)", game);
    twin_check(count_of(text, "  Name: Kai\n  Custom title: Kai Three Four\n") == 2
          && count_of(text, "  Name: Kai\n  Custom title: Kai Five Six\n") == 2
          && count_of(text, "Custom title") == 4, what, text);

    /* Identical twins: both could be the entry's villager -- nobody's. */
    twin_villager(2, "Kai", 3, 4, 0);
    entries[0] = twin_entry(1, 1, 3, 4, 0, "Kai Three Four");
    twin_write_titles(entries, 1);
    twin_export(text, sizeof text);
    wsprintfA(what, "IDENTICAL TWINS SHOW NO TITLE (game %d)", game);
    twin_check(count_of(text, "  Name: Kai\n") == 4 && strstr(text, "Custom title") == NULL, what, text);

    /* A version 2 entry (looks not known) and two carriers: nobody's. */
    twin_villager(2, "Kai", 5, 6, 0);
    entries[0] = twin_entry(1, 0, 0, 0, 0, "Version Two");
    twin_write_titles(entries, 1);
    twin_export(text, sizeof text);
    wsprintfA(what, "A VERSION 2 ENTRY WITH TWO CARRIERS SHOWS NONE (game %d)", game);
    twin_check(count_of(text, "  Name: Kai\n") == 4 && strstr(text, "Custom title") == NULL, what, text);
    /* ...and with one carrier it is shown, as before. */
    twin_villager(2, "Kaimana", 5, 6, 0);
    twin_export(text, sizeof text);
    wsprintfA(what, "a version 2 entry with one carrier is shown on its record (game %d)", game);
    twin_check(count_of(text, "  Name: Kai\n  Custom title: Version Two\n") == 2, what, text);

    /* A stale file: the entry's index holds the other twin, its villager is elsewhere. */
    twin_villager(2, "Kai", 5, 6, 0);
    entries[0] = twin_entry(1, 1, 5, 6, 0, "Stale Twin");
    twin_write_titles(entries, 1);
    twin_export(text, sizeof text);
    wsprintfA(what, "THE RECORD AT THE ENTRY'S INDEX HOLDING THE OTHER TWIN (STALE FILE) SHOWS NONE (game %d)", game);
    twin_check(count_of(text, "  Name: Kai\n") == 4 && strstr(text, "Custom title") == NULL, what, text);

    /* The same looks, told apart by the skills (ints, or floats in games 4 and 5). */
    twin_villager(1, "Kai", 3, 4, 60);
    twin_villager(2, "Kai", 3, 4, 10);
    entries[0] = twin_entry(1, 1, 3, 4, 50, "Skilled Kai");
    entries[1] = twin_entry(2, 1, 3, 4, 0, "Either Kai");
    twin_write_titles(entries, 2);
    twin_export(text, sizeof text);
    wsprintfA(what, "told apart by a skill: the twin who could be it has it, an entry both could be is nobody's (game %d)",
              game);
    twin_check(count_of(text, "  Name: Kai\n  Custom title: Skilled Kai\n") == 2 && strstr(text, "Either Kai") == NULL, what, text);

    /* A pending entry matches nobody. */
    entries[0] = twin_entry(VV_TITLE_PENDING, 1, 3, 4, 50, "Pending Kai");
    twin_write_titles(entries, 1);
    twin_export(text, sizeof text);
    wsprintfA(what, "a pending entry is shown on nobody (game %d)", game);
    twin_check(strstr(text, "Custom title") == NULL, what, text);

    if (tg->rva_is_pointer) {
        VirtualFree(g_twin_table, 0, MEM_RELEASE);
    }
    VirtualFree(g_twin_module, 0, MEM_RELEASE);
}

int main(void) {
    vv_custom_title entries[2];
    char roster[MAX_PATH];
    char history[MAX_PATH];
    char *text;
    char *kai;

    GetTempPathA(MAX_PATH, g_root);
    wsprintfA(g_root + lstrlenA(g_root), "vvfp_title_log_harness_%lu", GetCurrentProcessId());
    CreateDirectoryA(g_root, NULL);
    printf("save folder: %s\n\n", g_root);
    g_module = (unsigned char *)VirtualAlloc(NULL, V3_RVA + V3_BASE + 150 * V3_STRIDE + 0x1000,
                                            MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    villager(0, "Hina");
    villager(1, "Kai");
    villager(2, "Lani");

    memset(entries, 0, sizeof entries);
    entries[0].index = 1;
    entries[0].fingerprint = vv_title_identity(record(1), 0xDD4, 0x19, 0xFB4, 0xFC0, 3);
    lstrcpyA(entries[0].title, "Keeper of Stories");
    entries[1].index = 2;
    entries[1].fingerprint = vv_title_fingerprint((const unsigned char *)"Someone Else", 0x19);
    lstrcpyA(entries[1].title, "Not Lani's");
    write_titles(2, entries, 2);

    WriteVillagePopulation(3, g_module, "Village: Test (Save 2)\n");
    ROSTER(2);
    log_file(history, 2, "Tribe History", "Village History 1.txt");

    text = read_all(roster);
    kai = strstr(text, "  Name: Kai\n");
    check(kai != NULL, "the roster lists the villagers (nonzero denominator)");
    check(kai != NULL && strncmp(kai + 12, "  Custom title: Keeper of Stories\n", 34) == 0,
          "THE ROSTER PRINTS THE CUSTOM TITLE UNDER ITS VILLAGER'S NAME");
    check(strstr(text, "Not Lani's") == NULL, "A TITLE WHOSE RECORD HOLDS SOMEBODY ELSE IS NOT PRINTED");
    {
        int lines = 0;
        const char *at = text;
        while ((at = strstr(at, "Custom title")) != NULL) {
            ++lines;
            ++at;
        }
        check(lines == 1, "only the titled villager carries a title line");
    }
    text = read_all(history);
    check(strstr(text, "  Name: Kai\n  Custom title: Keeper of Stories\n") != NULL,
          "THE HISTORY PRINTS IT TOO");

    WriteVillagePopulation(3, g_module, "Village: Test (Save 4)\n");
    ROSTER(4);
    text = read_all(roster);
    check(strstr(text, "  Name: Kai\n") != NULL && strstr(text, "Custom title") == NULL,
          "ANOTHER SLOT'S VILLAGE PRINTS NO TITLES, IN ITS OWN SLOT'S FOLDER");
    ROSTER(2);
    text = read_all(roster);
    check(strstr(text, "  Name: Kai\n  Custom title: Keeper of Stories\n") != NULL,
          "SAVE 2'S ROSTER IS UNTOUCHED BY SAVE 4'S SAVE (two slots stay apart)");
    WriteVillagePopulation(3, g_module, "Village: Test\n");
    ROSTER(0);
    text = read_all(roster);
    check(strstr(text, "Custom title") == NULL, "a header with no slot prints no titles");

    /* A village NAMED "Trick (Save 2)" in slot 4: the header's last marker
       is its slot, so slot 2's titles must not leak into it... */
    WriteVillagePopulation(3, g_module, "Village: Trick (Save 2) (Save 4)\n");
    ROSTER(4);
    text = read_all(roster);
    check(strstr(text, "  Name: Kai\n") != NULL && strstr(text, "Custom title") == NULL,
          "A NAME CONTAINING (Save 2) DOES NOT READ SLOT 2'S TITLES");
    /* ...and the same name in slot 2 still gets them. */
    WriteVillagePopulation(3, g_module, "Village: Trick (Save 4) (Save 2)\n");
    ROSTER(2);
    text = read_all(roster);
    check(strstr(text, "  Name: Kai\n  Custom title: Keeper of Stories\n") != NULL,
          "THE LAST (Save N) MARKER IS THE SLOT");

    {
        int game;
        for (game = 1; game <= 5; ++game) {
            run_twins(game);
        }
    }

    printf("\n%d failure(s)\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}
