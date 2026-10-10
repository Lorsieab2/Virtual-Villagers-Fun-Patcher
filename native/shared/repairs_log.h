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

/* Append one "Repair <n>" record: `checked` (one line, no line end) and
   `body` (whole lines, "\r\n" ended, may be empty) under `header` (the
   village's "Village: ..." line, no line end).  1 when it is on disk. */
static int vv_repairs_note(int game, const char *header, const char *checked, const char *body) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    char *text;
    char *existing = NULL;
    int number = 1, repairs = 0, need_header = 1;
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
    if (!vv_save_folder(folder, 64)
        || !vv_save_subfolder(folder, vv_layout_dir_rel_a(folder, VV_REPAIRS_OLD_A, VV_REPAIRS_DIR_A),
                              (int)sizeof("\\Virtual Villagers 1 Repairs Log 99999.txt"))) {
        return 0;
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
                repairs + 1 + vv_layout_older_repairs(folder, game, number), now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond,
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
