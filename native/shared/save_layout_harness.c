/* native/shared/save_layout.h and log_words.h against real folders (tests/test_save_layout_names.py
   builds and runs it in a temporary folder, which stands in for the save folder).

   The owner, 2026-10-09: "from now on use the new renaming, but it also recognizes the old
   renaming".  Nothing is ever moved or renamed: a file or folder under an older build's name is
   used where it is; under neither name the new one is used; under both, a whole file is the one
   written last, new log records go to the new folder, and the Like and Dislike Words are read from
   both, the smaller boundary of each log file taken.

   Usage: save_layout_harness <empty work folder> */
#include <windows.h>
#include <stdio.h>
#include <string.h>

static char g_save[MAX_PATH];

/* The save folder is the work folder (native/shared/save_folder.h's contract). */
int vv_save_folder(char *out, int reserve) {
    (void)reserve;
    lstrcpyA(out, g_save);
    return 1;
}

int vv_save_folder_w(wchar_t *out, int reserve) {
    (void)reserve;
    return MultiByteToWideChar(CP_ACP, 0, g_save, -1, out, MAX_PATH) > 0;
}

int vv_save_subfolder(char *out, const char *sub, int reserve) {
    char *p;
    (void)reserve;
    wsprintfA(out, "%s\\%s", g_save, sub);
    for (p = out + lstrlenA(g_save) + 1; *p; ++p) {
        if (*p == '\\') {
            *p = '\0';
            CreateDirectoryA(out, NULL);
            *p = '\\';
        }
    }
    CreateDirectoryA(out, NULL);
    return 1;
}

int vv_save_subfolder_w(wchar_t *out, const wchar_t *sub, int reserve) {
    char narrow[MAX_PATH];
    wchar_t wide[MAX_PATH];
    if (WideCharToMultiByte(CP_ACP, 0, sub, -1, narrow, MAX_PATH, NULL, NULL) <= 0
        || !vv_save_subfolder((char *)wide, narrow, reserve)) {
        return 0;
    }
    return MultiByteToWideChar(CP_ACP, 0, (char *)wide, -1, out, MAX_PATH) > 0;
}

#include "log_words.h"

static int failures;

static void check(int ok, const char *what) {
    printf("%s %s\n", ok ? "PASS" : "FAIL", what);
    if (!ok) {
        ++failures;
    }
}

static void at(char *out, const char *rel) {
    wsprintfA(out, "%s\\%s", g_save, rel);
}

static void put(const char *rel, const char *text, int seconds_ago) {
    char p[MAX_PATH], *s;
    HANDLE f;
    DWORD wrote;
    FILETIME ft;
    ULARGE_INTEGER t;
    at(p, rel);
    for (s = p + lstrlenA(g_save) + 1; *s; ++s) {
        if (*s == '\\') {
            *s = '\0';
            CreateDirectoryA(p, NULL);
            *s = '\\';
        }
    }
    f = CreateFileA(p, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    WriteFile(f, text, (DWORD)strlen(text), &wrote, NULL);
    GetSystemTimeAsFileTime(&ft);
    t.LowPart = ft.dwLowDateTime;
    t.HighPart = ft.dwHighDateTime;
    t.QuadPart -= (ULONGLONG)seconds_ago * 10000000ull;
    ft.dwLowDateTime = t.LowPart;
    ft.dwHighDateTime = t.HighPart;
    SetFileTime(f, NULL, NULL, &ft);
    CloseHandle(f);
}

static void make_dir(const char *rel) {
    char p[MAX_PATH];
    at(p, rel);
    CreateDirectoryA(p, NULL);
}

static int exists(const char *rel) {
    char p[MAX_PATH];
    at(p, rel);
    return GetFileAttributesA(p) != INVALID_FILE_ATTRIBUTES;
}

static const char *text_of(const char *rel) {
    static char buffer[1024];
    char p[MAX_PATH];
    HANDLE f;
    DWORD got = 0;
    at(p, rel);
    buffer[0] = '\0';
    f = CreateFileA(p, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f != INVALID_HANDLE_VALUE) {
        ReadFile(f, buffer, sizeof buffer - 1, &got, NULL);
        buffer[got] = '\0';
        CloseHandle(f);
    }
    return buffer;
}

/* 1 when the pick for this whole file is the old path. */
static int pick(const char *old_rel, const char *new_rel) {
    char o[MAX_PATH], n[MAX_PATH];
    at(o, old_rel);
    at(n, new_rel);
    return vv_layout_pick_file_a(o, n);
}

static void remove_tree(const char *rel) {
    char p[MAX_PATH], pattern[MAX_PATH], child[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE find;
    at(p, rel);
    wsprintfA(pattern, "%s\\*", p);
    find = FindFirstFileA(pattern, &found);
    if (find != INVALID_HANDLE_VALUE) {
        do {
            if (lstrcmpA(found.cFileName, ".") == 0 || lstrcmpA(found.cFileName, "..") == 0) {
                continue;
            }
            wsprintfA(child, "%s\\%s", rel, found.cFileName);
            if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                remove_tree(child);
            } else {
                char c[MAX_PATH];
                at(c, child);
                DeleteFileA(c);
            }
        } while (FindNextFileA(find, &found));
        FindClose(find);
    }
    RemoveDirectoryA(p);
}

/* ---- One folder per save (native/shared/per_save.h) ------------------------------------------ */

static char g_label[512];

static const char *label(const char *what, int game, int slot) {
    wsprintfA(g_label, "%s (VV%d, Save %d)", what, game, slot);
    return g_label;
}

/* `rel` (a path inside the save folder) routed in place with `cap` characters of room (0: MAX_PATH);
   `out_rel` is the answer inside the save folder.  Returns vv_ps_route_w's result. */
static int route_rel(const char *rel, int cap, int make, char *out_rel) {
    wchar_t path[MAX_PATH];
    char abs_path[MAX_PATH];
    int routed, n = lstrlenA(g_save);
    wsprintfA(abs_path, "%s\\%s", g_save, rel);
    MultiByteToWideChar(CP_ACP, 0, abs_path, -1, path, MAX_PATH);
    routed = vv_ps_route_w(path, cap > 0 ? cap : MAX_PATH, make);
    WideCharToMultiByte(CP_ACP, 0, path, -1, abs_path, MAX_PATH, NULL, NULL);
    lstrcpyA(out_rel, _strnicmp(abs_path, g_save, n) == 0 && abs_path[n] == '\\' ? abs_path + n + 1 : abs_path);
    return routed;
}

static int routes_to(const char *rel, const char *expect_rel) {
    char got[MAX_PATH];
    route_rel(rel, 0, 0, got);
    if (lstrcmpiA(got, expect_rel) != 0) {
        printf("    %s\n      -> %s\n      expected %s\n", rel, got, expect_rel);
        return 0;
    }
    return 1;
}

/* vv_ps_new_path_w of `rel`, inside the save folder ("" when it has none). */
static const char *new_path_rel(const char *rel) {
    static char out[MAX_PATH];
    wchar_t path[MAX_PATH], fresh[MAX_PATH];
    char abs_path[MAX_PATH];
    int n = lstrlenA(g_save);
    wsprintfA(abs_path, "%s\\%s", g_save, rel);
    MultiByteToWideChar(CP_ACP, 0, abs_path, -1, path, MAX_PATH);
    out[0] = '\0';
    if (vv_ps_new_path_w(path, fresh, MAX_PATH)) {
        WideCharToMultiByte(CP_ACP, 0, fresh, -1, abs_path, MAX_PATH, NULL, NULL);
        lstrcpyA(out, abs_path + n + 1);
    }
    return out;
}

/* Give `rel_b` exactly `rel_a`'s last-write time. */
static void same_time(const char *rel_a, const char *rel_b) {
    char a[MAX_PATH], b[MAX_PATH];
    FILETIME written;
    HANDLE fa, fb;
    at(a, rel_a);
    at(b, rel_b);
    fa = CreateFileA(a, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    fb = CreateFileA(b, FILE_WRITE_ATTRIBUTES, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (fa != INVALID_HANDLE_VALUE && fb != INVALID_HANDLE_VALUE && GetFileTime(fa, NULL, NULL, &written)) {
        SetFileTime(fb, NULL, NULL, &written);
    }
    if (fa != INVALID_HANDLE_VALUE) CloseHandle(fa);
    if (fb != INVALID_HANDLE_VALUE) CloseHandle(fb);
}

static void per_save_clear(void) {
    remove_tree("Virtual Villagers Fun Patcher");
    remove_tree("Virtual Villagers Fun Patcher Data");
    remove_tree("Virtual Villagers Fun Patcher Logs");
}

static void per_save_cases(void) {
    /* Every game, every slot: a data file of its own kind and a log folder of its own. */
    static const char *const kind[5] = {
        "Village Masks", "Graves", "Village Masks", "Unaccounted Villagers", "Custom Titles"
    };
    static const char *const stem[5] = {
        "Virtual Villagers 1 Village Masks", "Virtual Villagers 2 Graves", "Village Masks",
        "Virtual Villagers 4 Villagers at Last Save", "Virtual Villagers 5 Custom Titles"
    };
    static const char *const log_folder[5] = {
        "Deaths and Disappearances", "Tribe History", "Births and Conceptions", "Repairs Made", "Tribe Population"
    };
    int game;
    for (game = 1; game <= 5; ++game) {
        int slot = game;
        char old_data[MAX_PATH], new_data[MAX_PATH], old_log[MAX_PATH], new_log[MAX_PATH];
        char old_log2[MAX_PATH], new_log2[MAX_PATH], old_log_dir[MAX_PATH], new_log_dir[MAX_PATH];
        char tmp_old[MAX_PATH], tmp_new[MAX_PATH], got[MAX_PATH];
        wsprintfA(old_data, "Virtual Villagers Fun Patcher Data\\%s\\%s - Save %d.dat", kind[game - 1], stem[game - 1], slot);
        wsprintfA(new_data, "Virtual Villagers Fun Patcher\\Save %d\\Data\\%s\\%s - Save %d.dat",
                  slot, kind[game - 1], stem[game - 1], slot);
        wsprintfA(old_log_dir, "Virtual Villagers Fun Patcher Logs\\Save %d\\%s", slot, log_folder[game - 1]);
        wsprintfA(new_log_dir, "Virtual Villagers Fun Patcher\\Save %d\\Logs\\%s", slot, log_folder[game - 1]);
        wsprintfA(old_log, "%s\\Virtual Villagers %d Log 1.txt", old_log_dir, game);
        wsprintfA(new_log, "%s\\Virtual Villagers %d Log 1.txt", new_log_dir, game);
        wsprintfA(old_log2, "%s\\Virtual Villagers %d Log 2.txt", old_log_dir, game);
        wsprintfA(new_log2, "%s\\Virtual Villagers %d Log 2.txt", new_log_dir, game);
        wsprintfA(tmp_old, "%s.tmp", old_data);
        wsprintfA(tmp_new, "%s.tmp", new_data);
        per_save_clear();

        check(lstrcmpiA(new_path_rel(old_data), new_data) == 0 && lstrcmpiA(new_path_rel(old_log), new_log) == 0,
              label("the save's own place: ...\\Save <S>\\Data\\<kind>\\<name> and ...\\Save <S>\\Logs\\<folder>\\<name>",
                    game, slot));
        check(routes_to(old_data, new_data) && routes_to(old_log, new_log) && routes_to(tmp_old, tmp_new)
              && !exists("Virtual Villagers Fun Patcher") && !exists("Virtual Villagers Fun Patcher Data")
              && !exists("Virtual Villagers Fun Patcher Logs"),
              label("fresh: a data file and a log go to the save's own folder, nothing made to look", game, slot));
        check(route_rel(old_data, 0, 1, got) && lstrcmpiA(got, new_data) == 0 && !exists(new_data),
              label("a writer's route makes the save's own folders, never the file", game, slot));
        {
            char folder[MAX_PATH];
            lstrcpyA(folder, new_data);
            *strrchr(folder, '\\') = '\0';
            check(exists(folder) && !exists("Virtual Villagers Fun Patcher Data"),
                  label("... and nothing of the older layout's", game, slot));
        }
        per_save_clear();

        /* A data file already in the older layout: there, its .tmp with it; nothing made. */
        put(old_data, "old", 60);
        check(routes_to(old_data, old_data) && routes_to(tmp_old, tmp_old) && !exists("Virtual Villagers Fun Patcher"),
              label("a data file in the older layout: read and written where it is, its .tmp beside it", game, slot));
        /* Both: the one written last; a tie: the save's own. */
        put(new_data, "new", 3600);
        check(routes_to(old_data, old_data) && strcmp(text_of(new_data), "new") == 0,
              label("both data files: the older layout's when it was written last", game, slot));
        put(new_data, "new", 1);
        check(routes_to(old_data, new_data) && strcmp(text_of(old_data), "old") == 0,
              label("... the save's own when it was written last, the other left as it is", game, slot));
        same_time(old_data, new_data);
        check(routes_to(old_data, new_data), label("... and a tie: the save's own", game, slot));
        remove_tree("Virtual Villagers Fun Patcher Data");
        check(routes_to(old_data, new_data), label("only the save's own: that one", game, slot));
        per_save_clear();

        /* A log: its unit is the slot's folder of that log. */
        put(old_log, "older records", 60);
        check(routes_to(old_log, old_log) && routes_to(old_log2, old_log2) && !exists("Virtual Villagers Fun Patcher"),
              label("a log folder of the older layout holding anything: every file of it written where it is",
                    game, slot));
        {
            char other[MAX_PATH], other_new[MAX_PATH];
            wsprintfA(other, "Virtual Villagers Fun Patcher Logs\\Save %d\\Village Statistics\\Virtual Villagers %d "
                             "Village Statistics - Save %d.txt", slot, game, slot);
            wsprintfA(other_new, "Virtual Villagers Fun Patcher\\Save %d\\Logs\\Village Statistics\\Virtual Villagers %d "
                                 "Village Statistics - Save %d.txt", slot, game, slot);
            check(routes_to(other, other_new),
                  label("... while another log of that slot, with no folder of its own there, goes to the save's own",
                        game, slot));
        }
        {
            char p[MAX_PATH];
            at(p, old_log);
            DeleteFileA(p);
        }
        check(exists(old_log_dir) && routes_to(old_log, new_log),
              label("an empty log folder of the older layout: the save's own", game, slot));
        put(old_log, "older records", 60);
        put(new_log2, "", 1);
        {
            char p[MAX_PATH];
            at(p, new_log2);
            DeleteFileA(p);
        }
        check(exists(new_log_dir) && routes_to(old_log, new_log) && routes_to(old_log2, new_log2)
              && strcmp(text_of(old_log), "older records") == 0,
              label("the save's own log folder there (even empty): new records go to it, the older kept", game, slot));
        per_save_clear();

        /* The ANSI form. */
        {
            char path[MAX_PATH], expect[MAX_PATH];
            wsprintfA(path, "%s\\%s", g_save, old_data);
            wsprintfA(expect, "%s\\%s", g_save, new_data);
            check(vv_ps_route_a(path, MAX_PATH, 0) && lstrcmpiA(path, expect) == 0,
                  label("vv_ps_route_a: the same answer", game, slot));
        }
        /* Too long for the caller's room: the older layout's path, every time.  (A log's two places
           are the same length -- "...Fun Patcher Logs\Save <S>\" and "...Fun Patcher\Save <S>\Logs\" --
           so only a data file's can be too long where the older one fits.) */
        {
            int room = lstrlenA(g_save) + 1 + lstrlenA(old_data) + 1;
            check(lstrlenA(new_data) > lstrlenA(old_data) && lstrlenA(new_log) == lstrlenA(old_log)
                  && !route_rel(old_data, room, 1, got) && lstrcmpiA(got, old_data) == 0
                  && !route_rel(old_data, room, 1, got) && lstrcmpiA(got, old_data) == 0
                  && route_rel(old_data, room + lstrlenA(new_data) - lstrlenA(old_data), 0, got)
                  && lstrcmpiA(got, new_data) == 0
                  && !exists("Virtual Villagers Fun Patcher"),
                  label("a save's own path too long for the caller's room: the older layout's, every time, nothing made",
                        game, slot));
        }
        per_save_clear();
    }

    /* Never routed: not one save's, or an older build's name. */
    {
        static const char *const kept[] = {
            "Virtual Villagers Fun Patcher Data\\Cross-Check\\Virtual Villagers 2 Repair Approved - Save 1.dat",
            "Virtual Villagers Fun Patcher Data\\Parentage Records\\Virtual Villagers 1 Parentage Records - Save 1.dat",
            "Virtual Villagers Fun Patcher Data\\Log Words\\Virtual Villagers 3 Log Words.dat",
            "Virtual Villagers Fun Patcher Data\\Genealogy\\Virtual Villagers 3 Genealogy Edits - Save 2.dat",
            "Virtual Villagers Fun Patcher Data\\Family Tree\\Virtual Villagers 5 Genealogy Edits - Save 4.dat",
            "Virtual Villagers Fun Patcher Data\\Unaccounted Villagers\\Virtual Villagers 4 Village Roster - Save 5.dat",
            "Virtual Villagers Fun Patcher Data\\Village Statistics\\Village Roster - Save 3.dat",
            "Virtual Villagers Fun Patcher Data\\Village Masks - Save 1.dat",
            "Virtual Villagers Fun Patcher Data\\Virtual Villagers 2 Graves - Save 2.dat",
            "Virtual Villagers Fun Patcher Data\\Copies Made Before Repairs\\Virtual Villagers Fun Patcher Data\\Graves\\"
                "Virtual Villagers 2 Graves - Save 1.dat.before-v1.35.59-repair",
            "Virtual Villagers Fun Patcher Data\\Copies Made Before Repairs\\Virtual Villagers Fun Patcher Logs\\Save 1\\"
                "Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt.before-repair",
            "Virtual Villagers Fun Patcher Data\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat",
            "Virtual Villagers Fun Patcher Logs\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt",
            "Virtual Villagers Fun Patcher Logs\\Tribe Population\\Village Population 1.txt",
            "Virtual Villagers Fun Patcher Logs\\Save 6\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt",
            "Virtual Villagers Fun Patcher Logs\\Save 12\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt",
            "Virtual Villagers Fun Patcher Data\\Graves\\Virtual Villagers 2 Graves - Save 6.dat",
            "Backups\\Virtual Villagers Fun Patcher Data\\x.dat",
            "Virtual Villagers 1 save 1.vvs",
        };
        int i, all = 1;
        char got[MAX_PATH];
        per_save_clear();
        for (i = 0; i < (int)(sizeof kept / sizeof kept[0]); ++i) {
            const char *fresh = new_path_rel(kept[i]);
            int routed = route_rel(kept[i], 0, 1, got);
            if (fresh[0] != '\0' || routed || lstrcmpA(got, kept[i]) != 0) {
                printf("    routed: %s -> %s / %s\n", kept[i], got, fresh);
                all = 0;
            }
        }
        check(all && !exists("Virtual Villagers Fun Patcher"),
              "never routed: older names, loose Data files, Copies Made Before Repairs of the older layout, "
              "shared logs and words, no slot 1-5");
    }

    /* Copies Made Before Repairs of a file in a save's own folder: in that folder too. */
    {
        wchar_t file[MAX_PATH], copy[MAX_PATH], expect[MAX_PATH];
        wsprintfW(file, L"%hs\\Virtual Villagers Fun Patcher\\Save 2\\Logs\\Repairs Made\\Virtual Villagers 3 Repairs Log 1.txt",
                  g_save);
        wsprintfW(expect, L"%hs\\Virtual Villagers Fun Patcher\\Save 2\\Data\\Copies Made Before Repairs\\Logs\\Repairs Made\\"
                          L"Virtual Villagers 3 Repairs Log 1.txt.before", g_save);
        check(vv_layout_copy_path(file, L".before", copy, MAX_PATH) && lstrcmpiW(copy, expect) == 0,
              "a repair's copy of a file in the save's own folder: ...\\Save <S>\\Data\\Copies Made Before Repairs\\<its place>");
        wsprintfW(file, L"%hs\\Virtual Villagers Fun Patcher Data\\Graves\\Virtual Villagers 2 Graves - Save 1.dat", g_save);
        wsprintfW(expect, L"%hs\\" VV_COPIES_DIR L"\\Virtual Villagers Fun Patcher Data\\Graves\\"
                          L"Virtual Villagers 2 Graves - Save 1.dat.before", g_save);
        check(vv_layout_copy_path(file, L".before", copy, MAX_PATH) && lstrcmpiW(copy, expect) == 0,
              "... and of an older-layout file: the older layout's Copies Made Before Repairs, as before");
        per_save_clear();
    }

    /* The Like and Dislike Words of a log in a save's own folder: that save's own file. */
    {
        static const char own_name[] = "Virtual Villagers Fun Patcher\\Save 2\\Logs\\Tribe History\\Village History 1.txt";
        static const char own_dat[] =
            "Virtual Villagers Fun Patcher\\Save 2\\Data\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat";
        char dat[MAX_PATH], expect[MAX_PATH];
        wchar_t log_path[MAX_PATH];
        per_save_clear();
        at(expect, own_dat);
        check(vv_log_words_path_for(1, own_name, dat, sizeof dat) && lstrcmpiA(dat, expect) == 0,
              "the words of a log in the save's own folder: ...\\Save <S>\\Data\\Like and Dislike Words");
        put(own_name, "0123456789", 1);
        wsprintfW(log_path, L"%hs\\%hs", g_save, own_name);
        vv_log_words_appending(1, log_path);
        check(strstr(text_of(own_dat), "10\tVirtual Villagers Fun Patcher\\Save 2\\Logs\\Tribe History\\Village History 1.txt")
                  != NULL
              && vv_log_words_boundary(1, log_path) == 10
              && !exists("Virtual Villagers Fun Patcher Data\\Like and Dislike Words"),
              "... its boundary is recorded and read there, nothing in the shared words");
        per_save_clear();
    }
}

#define ROSTER_OLD "Virtual Villagers Fun Patcher Data\\Unaccounted Villagers\\Virtual Villagers 1 Village Roster - Save 1.dat"
#define ROSTER_NEW "Virtual Villagers Fun Patcher Data\\Unaccounted Villagers\\Virtual Villagers 1 Villagers at Last Save - Save 1.dat"
#define WORDS_OLD "Virtual Villagers Fun Patcher Data\\Log Words\\Virtual Villagers 1 Log Words.dat"
#define WORDS_NEW "Virtual Villagers Fun Patcher Data\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat"
#define DEATHS_OLD "Virtual Villagers Fun Patcher Logs\\Deaths"
#define DEATHS_NEW "Virtual Villagers Fun Patcher Logs\\Deaths and Disappearances"

int main(int argc, char **argv) {
    char dat[MAX_PATH], expect[MAX_PATH];
    wchar_t history[MAX_PATH];
    LONGLONG offset = -1;
    if (argc < 2) {
        printf("usage: save_layout_harness <empty work folder>\n");
        return 2;
    }
    lstrcpyA(g_save, argv[1]);

    /* A whole file: each of the four cases. */
    check(!pick(ROSTER_OLD, ROSTER_NEW), "a whole file under neither name: the new name");
    put(ROSTER_OLD, "old", 60);
    check(pick(ROSTER_OLD, ROSTER_NEW), "only under the older build's name: used where it is");
    put(ROSTER_NEW, "new", 3600);
    check(pick(ROSTER_OLD, ROSTER_NEW),
          "under both, the one written last: the owner's rosters (the older build's 15:21 over the new 14:13)");
    put(ROSTER_NEW, "new", 1);
    check(!pick(ROSTER_OLD, ROSTER_NEW), "... or the new one when it was written last");
    remove_tree("Virtual Villagers Fun Patcher Data\\Unaccounted Villagers");
    put(ROSTER_NEW, "new", 1);
    check(!pick(ROSTER_OLD, ROSTER_NEW), "only under the new name: the new one");
    check(strcmp(text_of(ROSTER_NEW), "new") == 0 && !exists(ROSTER_OLD), "... and nothing is moved or made");

    /* A folder of logs. */
    {
        wchar_t root[MAX_PATH];
        MultiByteToWideChar(CP_ACP, 0, g_save, -1, root, MAX_PATH);
        check(lstrcmpW(vv_layout_dir_rel_w(root, VV_DEATHS_LOGS_OLD, VV_DEATHS_LOGS_DIR), VV_DEATHS_LOGS_DIR) == 0
              && !exists(DEATHS_NEW) && !exists(DEATHS_OLD),
              "a log folder under neither name: written in the new one, nothing made to look");
        make_dir("Virtual Villagers Fun Patcher Logs");
        make_dir(DEATHS_OLD);
        check(lstrcmpW(vv_layout_dir_rel_w(root, VV_DEATHS_LOGS_OLD, VV_DEATHS_LOGS_DIR), VV_DEATHS_LOGS_OLD) == 0
              && !exists(DEATHS_NEW),
              "only the older build's Deaths: written where it is, never moved");
        make_dir(DEATHS_NEW);
        check(lstrcmpW(vv_layout_dir_rel_w(root, VV_DEATHS_LOGS_OLD, VV_DEATHS_LOGS_DIR), VV_DEATHS_LOGS_DIR) == 0
              && exists(DEATHS_OLD),
              "both: new records go to Deaths and Disappearances, the older folder kept");
    }

    /* The Like and Dislike Words. */
    wsprintfW(history, L"%hs\\Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt", g_save);
    check(vv_log_words_boundary(1, history) == 0x7FFFFFFFFFFFFFFFLL,
          "the words: no boundary file under either name, the whole file is old");
    put(WORDS_OLD, "1763792\tVirtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt\r\n", 60);
    check(vv_log_words_boundary(1, history) == 1763792, "only the older build's Log Words: read where it is");
    check(vv_log_words_path(1, dat, sizeof dat) && (at(expect, WORDS_OLD), lstrcmpA(dat, expect) == 0)
          && !exists("Virtual Villagers Fun Patcher Data\\Like and Dislike Words"),
          "... and written where it is, no new folder made");
    put(WORDS_NEW, "0\tVirtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt\r\n", 3600);
    check(vv_log_words_boundary(1, history) == 0,
          "both (the owner's: 1763792 in the older one, 0 in the new): the smaller, so correct words stay correct");
    check(vv_log_words_recorded(1, "Virtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt", &offset)
          && offset == 0, "... read from both files");
    check(vv_log_words_path(1, dat, sizeof dat) && (at(expect, WORDS_NEW), lstrcmpA(dat, expect) == 0),
          "... and new boundaries are written to the new one");
    put(WORDS_NEW, "5\tVirtual Villagers Fun Patcher Logs\\Deaths\\Virtual Villagers 1 Deaths Log 1.txt\r\n", 3600);
    put(WORDS_OLD, "9\tVirtual Villagers Fun Patcher Logs\\Deaths\\Virtual Villagers 1 Deaths Log 1.txt\r\n"
                   "7\tVirtual Villagers Fun Patcher Logs\\Tribe History\\Village History 1.txt\r\n", 60);
    check(vv_log_words_boundary(1, history) == 7, "a file only one of them records: that one's boundary");
    remove_tree("Virtual Villagers Fun Patcher Data\\Log Words");
    check(vv_log_words_boundary(1, history) == 0x7FFFFFFFFFFFFFFFLL
          && vv_log_words_path(1, dat, sizeof dat) && (at(expect, WORDS_NEW), lstrcmpA(dat, expect) == 0),
          "only the new one: read and written there");

    /* One folder per save, in a save folder of its own (the stubs above read g_save). */
    {
        char own[MAX_PATH];
        wsprintfA(own, "%s\\per save", argv[1]);
        CreateDirectoryA(own, NULL);
        lstrcpyA(g_save, own);
        per_save_cases();
    }

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
