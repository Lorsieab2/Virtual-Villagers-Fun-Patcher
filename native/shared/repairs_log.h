/* The Repairs log and the repair backups, for every part of the first-load
   cross-check that a companion other than A New Home's parentage repairs
   (v1.35.58; native/shared/crosscheck_bridge.h).

   THE LOG.  "<save folder>\Virtual Villagers Fun Patcher Logs\Repairs Made\
   Virtual Villagers N Repairs Log <n>.txt" ("Repairs" while only an older
   build's folder of that name exists; save_layout.h) -- the same files, numbering and
   shape A New Home's parentage repair writes (vv1_crosscheck.inc): the
   village's own header line ("Village: <name> (Save S)") whenever the last
   one in the file is another village's, then one numbered record per
   repair:

       Repair <n>
         Date: YYYY-MM-DD HH:MM:SS
         Checked: <what was checked against what>
         <one line per change>
         Backup: <file name> | none (...)
       <blank line>

   A file holds 256 records or 4 MiB; the next number is used after that.
   Written with Windows line endings, appended, never rewritten.

   ONE FOLDER PER SAVE SLOT (log_slot.h): a repair of the village "<name> (Save S)" is written in
   "...Logs\Save S\Repairs Made\"; the shared "Repairs Made" (and an older build's "Repairs") is
   never written again, moved or split.  "Repair <n>" is numbered per GAME: after the highest
   number printed in any of the game's Repairs files -- the shared folders and every slot's -- so
   no number is ever used twice.

   THE BACKUP.  "<file>.before-v1.35.58-repair" (then "-2", "-3", ...) in
   "Virtual Villagers Fun Patcher Data\Copies Made Before Repairs", at the
   file's own place (save_layout.h), copied before the first change and never
   replacing anything: CopyFile with bFailIfExists.

   Header-only and file-static: included once per companion. */
#ifndef VVFP_REPAIRS_LOG_H
#define VVFP_REPAIRS_LOG_H

#include <windows.h>
#include <stdio.h>
#include <string.h>
#include "save_folder.h"
#include "save_layout.h"
#include "log_slot.h"

#define VV_REPAIR_BACKUP_SUFFIX L".before-v1.35.58-repair"
#define VV_REPAIRS_PER_FILE 256
#define VV_REPAIRS_FILE_BYTES (4u * 1024u * 1024u)

/* Copy `path` to its backup name.  1: copied, or there was no file (then
   `*none` is 1 and `backup` is empty); 0: the copy could not be made. */
static int vv_repair_backup(const wchar_t *path, wchar_t *backup, size_t n, int *none) {
    int k;
    *none = 0;
    backup[0] = L'\0';
    if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
        DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
            *none = 1;
            return 1;
        }
        return 0;
    }
    for (k = 1; k < 1000; ++k) {
        /* Kept in "Data\Copies Made Before Repairs", at the file's own place (save_layout.h); beside
           the file only when it is outside the save folder's Logs and Data folders. */
        wchar_t suffix[48];
        int w = k == 1 ? _snwprintf_s(suffix, 48, _TRUNCATE, VV_REPAIR_BACKUP_SUFFIX)
                       : _snwprintf_s(suffix, 48, _TRUNCATE, VV_REPAIR_BACKUP_SUFFIX L"-%d", k);
        if (w < 0) {
            break;
        }
        if (!vv_layout_copy_path(path, suffix, backup, n)) {
            w = _snwprintf_s(backup, n, _TRUNCATE, L"%ls%ls", path, suffix);
        }
        if (w < 0) {
            break;
        }
        if (CopyFileW(path, backup, TRUE)) {
            return 1;
        }
        if (GetLastError() != ERROR_FILE_EXISTS && GetLastError() != ERROR_ALREADY_EXISTS) {
            break;
        }
    }
    backup[0] = L'\0';
    return 0;
}

static int vv_repairs_starts(const char *line, const char *word) {
    return strncmp(line, word, strlen(word)) == 0;
}

/* The highest "Repair <n>" printed in any of game `game`'s Repairs files: an older build's
   "Repairs", the shared "Repairs Made" and every slot's (log_slot.h).  0 when none; -1 when a file
   that is there cannot be read (nothing is then numbered blind). */
static long vv_repairs_highest(int game) {
    char root[MAX_PATH];
    char folders[2 + VV_LOG_SLOTS][MAX_PATH];
    char pattern[MAX_PATH], path[MAX_PATH];
    long highest = 0;
    int n, f;
    if (!vv_save_folder(root, 64)) {
        return -1;
    }
    n = vv_log_read_folders_a(root, "Repairs Made", "Repairs", 0, folders, 2 + VV_LOG_SLOTS);
    for (f = 0; f < n; ++f) {
        WIN32_FIND_DATAA found;
        HANDLE find;
        if (_snprintf_s(pattern, sizeof pattern, _TRUNCATE, "%s\\Virtual Villagers %d Repairs Log *.txt",
                        folders[f], game) < 0) {
            return -1;
        }
        find = FindFirstFileA(pattern, &found);
        if (find == INVALID_HANDLE_VALUE) {
            continue;
        }
        do {
            int count = 0;
            if ((found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0
                || _snprintf_s(path, sizeof path, _TRUNCATE, "%s\\%s", folders[f], found.cFileName) < 0) {
                continue;
            }
            if (vv_log_marker_numbers_a(path, "Repair ", &count, &highest) < 0) {
                FindClose(find);
                return -1;
            }
        } while (FindNextFileA(find, &found));
        FindClose(find);
    }
    return highest;
}

/* Append one "Repair <n>" record: `checked` (one line, no line end) and
   `body` (whole lines, "\r\n" ended, may be empty) under `header` (the
   village's "Village: ..." line, no line end).  1 when it is on disk. */
static int vv_repairs_note(int game, const char *header, const char *checked, const char *body) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    char *text;
    char *existing = NULL;
    int number = 1, repairs = 0, need_header = 1;
    int slot = vv_log_header_slot(header);
    long highest;
    size_t cap;
    SYSTEMTIME now;
    HANDLE file;
    DWORD size, got = 0, wrote = 0;
    BOOL ok;
    if (game < 1 || game > 5 || header == NULL || checked == NULL || body == NULL) {
        return 0;
    }
    /* "Repairs Made", or an older build's "Repairs" while only it exists: written where it is,
       never moved (save_layout.h). */
    if (slot != 0) {
        /* The village's own slot folder: "...Logs\Save <slot>\Repairs Made" (log_slot.h). */
        char sub[MAX_PATH];
        if (!vv_log_rel_a(sub, sizeof sub, slot, "Repairs Made")
            || !vv_save_subfolder(folder, sub, (int)sizeof("\\Virtual Villagers 1 Repairs Log 99999.txt"))) {
            return 0;
        }
    } else if (!vv_save_folder(folder, 64)
        || !vv_save_subfolder(folder, vv_layout_dir_rel_a(folder, VV_REPAIRS_OLD_A, VV_REPAIRS_DIR_A),
                              (int)sizeof("\\Virtual Villagers 1 Repairs Log 99999.txt"))) {
        return 0;
    }
    highest = vv_repairs_highest(game);
    if (highest < 0) {
        return 0;                     /* a Repairs file there and unreadable: never numbered blind */
    }
    for (;;) {
        _snprintf_s(path, sizeof path, _TRUNCATE, "%s\\Virtual Villagers %d Repairs Log %d.txt", folder, game, number + 1);
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES || number >= 99999) {
            break;
        }
        ++number;
    }
    _snprintf_s(path, sizeof path, _TRUNCATE, "%s\\Virtual Villagers %d Repairs Log %d.txt", folder, game, number);
    {
        WIN32_FILE_ATTRIBUTE_DATA info;
        if (GetFileAttributesExA(path, GetFileExInfoStandard, &info)
            && (info.nFileSizeHigh != 0 || info.nFileSizeLow >= VV_REPAIRS_FILE_BYTES)) {
            ++number;
            _snprintf_s(path, sizeof path, _TRUNCATE, "%s\\Virtual Villagers %d Repairs Log %d.txt", folder, game, number);
        }
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        size = GetFileSize(file, NULL);
        if (size != INVALID_FILE_SIZE && size < VV_REPAIRS_FILE_BYTES + 65536u) {
            existing = (char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)size + 1);
            if (existing != NULL && !(ReadFile(file, existing, size, &got, NULL) && got == size)) {
                HeapFree(GetProcessHeap(), 0, existing);
                existing = NULL;
            }
        }
        CloseHandle(file);
        if (existing == NULL) {
            return 0;                 /* there and unreadable: never written blind */
        }
        {
            const char *p = existing;
            const char *last_header = NULL;
            while (*p) {
                if (vv_repairs_starts(p, "Repair ")) ++repairs;
                if (vv_repairs_starts(p, "Village:")) last_header = p;
                while (*p && *p != '\n') ++p;
                if (*p) ++p;
            }
            if (last_header != NULL) {
                size_t hl = strlen(header);
                need_header = !(strncmp(last_header, header, hl) == 0
                                && (last_header[hl] == '\r' || last_header[hl] == '\n' || last_header[hl] == '\0'));
            }
        }
        HeapFree(GetProcessHeap(), 0, existing);
        if (repairs >= VV_REPAIRS_PER_FILE) {
            ++number;
            _snprintf_s(path, sizeof path, _TRUNCATE, "%s\\Virtual Villagers %d Repairs Log %d.txt", folder, game, number);
            repairs = 0;
            need_header = 1;
        }
    }
    cap = strlen(header) + strlen(checked) + strlen(body) + 256;
    text = (char *)HeapAlloc(GetProcessHeap(), 0, cap);
    if (text == NULL) {
        return 0;
    }
    GetLocalTime(&now);
    _snprintf_s(text, cap, _TRUNCATE,
                "%s%s"
                "Repair %d\r\n"
                "  Date: %04u-%02u-%02u %02u:%02u:%02u\r\n"
                "  Checked: %s\r\n"
                "%s"
                "\r\n",
                need_header ? header : "", need_header ? "\r\n" : "",
                /* after an older build's "Repairs" folder's own file of the same number, as A New
                   Home's parentage repair numbers it (vv1_crosscheck.inc; save_layout.h): never a
                   second "Repair 1" beside the older folder's */
                (int)((long)(repairs + vv_layout_older_repairs(folder, game, number)) > highest
                      ? (long)(repairs + vv_layout_older_repairs(folder, game, number)) : highest) + 1,
                now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond,
                checked, body);
    file = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        HeapFree(GetProcessHeap(), 0, text);
        return 0;
    }
    ok = WriteFile(file, text, (DWORD)strlen(text), &wrote, NULL) && wrote == (DWORD)strlen(text);
    ok = FlushFileBuffers(file) && ok;
    CloseHandle(file);
    HeapFree(GetProcessHeap(), 0, text);
    return ok ? 1 : 0;
}

#endif /* VVFP_REPAIRS_LOG_H */
