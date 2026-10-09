/* Where each log file's likes and dislikes start being the game's own words.

   Until v1.35.61 the exporters printed A New Home's likes and dislikes from
   The Lost Children's list cut to 47 words, and The Secret City's from The
   Tree of Life's (frogs and soap where its exe says alchemy and potions).
   The owner (2026-10-06): the logs must say what the game's exe says, and
   Check Saves & Logs / Repair Saves & Logs must put the old words right
   (src/vv_log_tools.py).

   The words alone cannot say which list wrote them -- "rough wood", "work",
   "jokes" and four more are in both A New Home lists at different places --
   so every log file of those two games gets a BOUNDARY: the byte offset
   before which its text was written with the old list.  One text file per
   game in the save folder:

       Virtual Villagers Fun Patcher Data\Like and Dislike Words\
           Virtual Villagers N Log Words.dat

   ("Log Words" in older builds' save folders: kept and used where it is, and when both exist
   both are read, the smaller boundary of each file taken; save_layout.h)

   one line per entry, "<offset>\t<log file name>\r\n", appended, never
   rewritten; the LAST line naming a file is the one that counts.

     - Before a companion of this build first appends to a file, it records
       the file's size then (vv_log_words_appending): everything already in
       it was written by an older build, everything after is correct.  A file
       this build creates gets 0.
     - A file rewritten whole (the Village Population roster) is all correct:
       vv_log_words_rewritten records 0.
     - Repair Saves & Logs translates the text before the boundary and records 0.

   A file with no line at all is entirely old.  The other three games' lists
   were always their own: nothing is recorded for them.

   vv_log_words_fix translates one word written before a boundary; the Deaths
   log's backfill uses it for the likes it copies out of the Village History.

   Header-only and static: included once per companion. */
#ifndef VVFP_LOG_WORDS_H
#define VVFP_LOG_WORDS_H

#include <windows.h>
#include <string.h>
#include "save_folder.h"
#include "save_layout.h"

/* The words the old lists printed, by index, and the game's own. */
static const char *const VV_LOG_WORDS_VV1_OLD[47] = {
    "ants", "crowds", "resting", "laundry", "medicine", "turnips", "butterflies", "flowers",
    "bees", "the dark", "caves", "herbs", "berries", "snakes", "wind", "rocks", "heights",
    "the ocean", "playing", "exploring", "blue", "green", "red", "yellow", "drums", "bushes",
    "bananas", "coconuts", "sand", "sunlight", "rough wood", "crab meat", "whale meat", "fish",
    "fruit", "papaya", "flies", "swimming", "running", "learning", "dancing", "monkeys",
    "parrots", "work", "lifting", "surprises", "jokes",
};
static const char *const VV_LOG_WORDS_VV1_NEW[47] = {
    "ants", "crowds", "resting", "laundry", "medicine", "turnips", "butterflies", "flowers",
    "bees", "the dark", "caves", "herbs", "berries", "snakes", "wind", "rocks", "rough wood",
    "the ocean", "playing", "exploring", "blue", "green", "red", "yellow", "drums", "bushes",
    "bananas", "coconuts", "sand", "sunlight", "drift wood", "crab meat", "whale meat", "fish",
    "fruit", "papaya", "flies", "swimming", "running", "dancing", "monkeys", "birds", "work",
    "lifting", "surprises", "jokes", "sleeping",
};

/* The game's own word for `word` written by the old list, or `word`. */
static const char *vv_log_words_fix(int game, const char *word) {
    int i;
    if (word == NULL) {
        return word;
    }
    if (game == 1) {
        for (i = 0; i < 47; ++i) {
            if (strcmp(word, VV_LOG_WORDS_VV1_OLD[i]) == 0) {
                return VV_LOG_WORDS_VV1_NEW[i];
            }
        }
    } else if (game == 3) {
        if (strcmp(word, "frogs") == 0) {
            return "alchemy";
        }
        if (strcmp(word, "soap") == 0) {
            return "potions";
        }
    }
    return word;
}

static int vv_log_words_tracked(int game) {
    return game == 1 || game == 3;
}

/* The game's boundary file under each name (save_layout.h): "Like and Dislike Words", and an
   older build's "Log Words".  Neither folder is made here. */
static int vv_log_words_paths(int game, char *new_dat, char *old_dat, size_t size) {
    char folder[MAX_PATH];
    return vv_save_folder(folder, 96)
           && _snprintf_s(new_dat, size, _TRUNCATE, "%s\\" VV_LOG_WORDS_DIR_A "\\Virtual Villagers %d Log Words.dat",
                          folder, game) > 0
           && _snprintf_s(old_dat, size, _TRUNCATE, "%s\\" VV_LOG_WORDS_OLD_A "\\Virtual Villagers %d Log Words.dat",
                          folder, game) > 0;
}

/* The boundary file to append to: the new one, or an older build's while only it exists -- it is
   written where it is, never moved.  When both exist the new one is written; the boundaries are
   read from both (vv_log_words_recorded).  Its folder is created only here, to write. */
static int vv_log_words_path(int game, char *out, size_t size) {
    char folder[MAX_PATH], old_dat[MAX_PATH];
    const char *sub;
    if (!vv_log_words_paths(game, out, old_dat, size) || !vv_save_folder(folder, 96)) {
        return 0;
    }
    sub = vv_layout_dir_rel_a(folder, VV_LOG_WORDS_OLD_A, VV_LOG_WORDS_DIR_A);
    if (!vv_save_subfolder(folder, sub, (int)sizeof("\\Virtual Villagers 1 Log Words.dat"))) {
        return 0;
    }
    return _snprintf_s(out, size, _TRUNCATE, "%s\\Virtual Villagers %d Log Words.dat", folder, game) > 0;
}

/* The last recorded boundary of the file called `name` in one boundary file: 1 and *offset, or 0
   when none is recorded (or the boundary file cannot be read). */
static int vv_log_words_recorded_in(const char *dat, const char *name, LONGLONG *offset) {
    HANDLE file;
    DWORD size, got = 0;
    char *text, *p;
    size_t name_length = strlen(name);
    int found = 0;
    file = CreateFileA(dat, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(file, NULL);
    if (size == INVALID_FILE_SIZE || size > 16u * 1024u * 1024u) {
        CloseHandle(file);
        return 0;
    }
    text = (char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)size + 1);
    if (text == NULL || !(ReadFile(file, text, size, &got, NULL) && got == size)) {
        if (text != NULL) {
            HeapFree(GetProcessHeap(), 0, text);
        }
        CloseHandle(file);
        return 0;
    }
    CloseHandle(file);
    for (p = text; *p;) {
        char *tab = strchr(p, '\t');
        char *end = strchr(p, '\n');
        if (end == NULL) {
            end = p + strlen(p);
        }
        if (tab != NULL && tab < end) {
            size_t length = (size_t)(end - tab - 1);
            if (length > 0 && tab[length] == '\r') {
                --length;
            }
            if (length == name_length && strncmp(tab + 1, name, name_length) == 0) {
                *offset = _strtoi64(p, NULL, 10);
                found = 1;
            }
        }
        p = *end ? end + 1 : end;
    }
    HeapFree(GetProcessHeap(), 0, text);
    return found;
}

/* The boundary of the file called `name` from both boundary files: when both record it, the
   SMALLER (the owner's folder, 2026-10-09: an older build recorded 1763792 for a Village History
   whose words the newer one had already put right and recorded 0 -- the larger would turn correct
   words into wrong ones).  1 and *offset, or 0 when neither records it. */
static int vv_log_words_recorded(int game, const char *name, LONGLONG *offset) {
    char new_dat[MAX_PATH], old_dat[MAX_PATH];
    LONGLONG from_new = 0, from_old = 0;
    int in_new, in_old;
    if (!vv_log_words_paths(game, new_dat, old_dat, sizeof new_dat)) {
        return 0;
    }
    in_new = vv_log_words_recorded_in(new_dat, name, &from_new);
    in_old = vv_log_words_recorded_in(old_dat, name, &from_old);
    if (!in_new && !in_old) {
        return 0;
    }
    *offset = !in_old ? from_new : !in_new ? from_old : (from_new < from_old ? from_new : from_old);
    return 1;
}

static void vv_log_words_note(const char *dat, LONGLONG offset, const char *name) {
    char line[MAX_PATH + 32];
    HANDLE file;
    DWORD wrote = 0;
    int length = _snprintf_s(line, sizeof line, _TRUNCATE, "%I64d\t%s\r\n", offset, name);
    if (length <= 0) {
        return;
    }
    file = CreateFileA(dat, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    (void)WriteFile(file, line, (DWORD)length, &wrote, NULL);
    CloseHandle(file);
}

/* The file's path inside the save folder ("Virtual Villagers Fun Patcher
   Logs\Tribe History\Village History.txt"), in UTF-8: two folders can hold
   files of the same name (an older build's "VVFP Logs" history). */
static int vv_log_words_name(const wchar_t *path, char *name, int size) {
    wchar_t root[MAX_PATH];
    const wchar_t *inside;
    size_t length;
    if (!vv_save_folder_w(root, 1)) {
        return 0;
    }
    length = wcslen(root);
    if (_wcsnicmp(path, root, length) != 0 || path[length] != L'\\') {
        return 0;                     /* not in the save folder: nothing recorded */
    }
    inside = path + length + 1;
    {
        /* A file in a folder that was renamed keeps the name it was recorded under: the Deaths
           log's folder is "Deaths and Disappearances" now (save_layout.h), its records "Deaths". */
        static const wchar_t renamed[] = VV_DEATHS_LOGS_DIR L"\\";
        static const wchar_t recorded_as[] = VV_DEATHS_LOGS_OLD L"\\";
        const size_t n = sizeof renamed / sizeof renamed[0] - 1;
        if (_wcsnicmp(inside, renamed, n) == 0) {
            wchar_t keyed[MAX_PATH];
            if (_snwprintf_s(keyed, MAX_PATH, _TRUNCATE, L"%ls%ls", recorded_as, inside + n) < 0) {
                return 0;
            }
            return WideCharToMultiByte(CP_UTF8, 0, keyed, -1, name, size, NULL, NULL) > 0;
        }
    }
    return WideCharToMultiByte(CP_UTF8, 0, inside, -1, name, size, NULL, NULL) > 0;
}

/* The offset before which `path` holds old-list words: 0 when none (or the
   game's list was always right), the recorded boundary, or the whole file
   when nothing is recorded. */
static LONGLONG vv_log_words_boundary(int game, const wchar_t *path) {
    char name[MAX_PATH];
    LONGLONG recorded;
    if (!vv_log_words_tracked(game) || path == NULL || !vv_log_words_name(path, name, sizeof name)) {
        return 0;
    }
    return vv_log_words_recorded(game, name, &recorded) ? recorded : 0x7FFFFFFFFFFFFFFFLL;
}

/* Before this build first appends to `path`: everything already in it was
   written with the old list. */
static void vv_log_words_appending(int game, const wchar_t *path) {
    char dat[MAX_PATH], name[MAX_PATH];
    LONGLONG recorded;
    WIN32_FILE_ATTRIBUTE_DATA info;
    LONGLONG size = 0;
    if (!vv_log_words_tracked(game) || path == NULL || !vv_log_words_name(path, name, sizeof name)
        || vv_log_words_recorded(game, name, &recorded) || !vv_log_words_path(game, dat, sizeof dat)) {
        return;
    }
    if (GetFileAttributesExW(path, GetFileExInfoStandard, &info)) {
        size = ((LONGLONG)info.nFileSizeHigh << 32) | info.nFileSizeLow;
    } else if (GetLastError() != ERROR_FILE_NOT_FOUND && GetLastError() != ERROR_PATH_NOT_FOUND) {
        return;                       /* there but unreadable: nothing is claimed */
    }
    vv_log_words_note(dat, size, name);
}

/* `path` was just written whole by this build: all of it is correct. */
static void vv_log_words_rewritten(int game, const wchar_t *path) {
    char dat[MAX_PATH], name[MAX_PATH];
    LONGLONG recorded = -1;
    if (!vv_log_words_tracked(game) || path == NULL || !vv_log_words_name(path, name, sizeof name)) {
        return;
    }
    if ((!vv_log_words_recorded(game, name, &recorded) || recorded != 0)
        && vv_log_words_path(game, dat, sizeof dat)) {
        vv_log_words_note(dat, 0, name);
    }
}

#endif
