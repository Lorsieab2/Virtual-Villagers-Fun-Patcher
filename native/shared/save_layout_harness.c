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

    printf("== %d failure(s) ==\n", failures);
    return failures ? 1 : 0;
}
