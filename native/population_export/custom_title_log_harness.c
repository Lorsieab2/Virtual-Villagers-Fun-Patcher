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
 *   a header naming another slot prints no titles at all.
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
}

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
    entries[0].fingerprint = vv_title_fingerprint(record(1) + 0xDD4, 0x19);
    lstrcpyA(entries[0].title, "Keeper of Stories");
    entries[1].index = 2;
    entries[1].fingerprint = vv_title_fingerprint((const unsigned char *)"Someone Else", 0x19);
    lstrcpyA(entries[1].title, "Not Lani's");
    write_titles(2, entries, 2);

    WriteVillagePopulation(3, g_module, "Village: Test (Save 2)\n");
    wsprintfA(roster, "%s\\Virtual Villagers Fun Patcher Logs\\Tribe Population\\Village Population 1.txt", g_root);
    wsprintfA(history, "%s\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt", g_root);

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
    text = read_all(roster);
    check(strstr(text, "  Name: Kai\n") != NULL && strstr(text, "Custom title") == NULL,
          "ANOTHER SLOT'S VILLAGE PRINTS NO TITLES");
    WriteVillagePopulation(3, g_module, "Village: Test\n");
    text = read_all(roster);
    check(strstr(text, "Custom title") == NULL, "a header with no slot prints no titles");

    printf("\n%d failure(s)\n", g_failures);
    return g_failures == 0 ? 0 : 1;
}
