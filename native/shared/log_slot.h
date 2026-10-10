/* One folder of logs per save slot (the owner, 2026-10-10: "separate log per slot", then "Just put
   the logs in separate folders per slot").

       <save folder>\Virtual Villagers Fun Patcher Logs\Save <S>\<the log's own folder>\<its own name>

   e.g. "...Logs\Save 1\Births and Conceptions\Virtual Villagers 1 Births and Conceptions Log 1.txt".
   Every log keeps its folder and file names; only the parent folder is the slot's.  The slot is the
   one the village header names ("Village: <name> (Save <S>)", the LAST such marker), so a record is
   filed in the folder of the village it describes, never by a slot read at another moment.  A
   writer that knows no slot (no village named: no publisher installed) writes the shared folder
   older builds wrote, as it always did.

   OLDER SHARED LOGS ARE NEVER MOVED, SPLIT, RENAMED OR DELETED HERE.  "...Logs\<the log's folder>\"
   (and an older build's name for it, save_layout.h) stays where it is, and every reader reads it
   first -- each record kept only under its own slot's header -- and then the slot's folder, as one
   history.  Numbered records ("Conception <n>", "Death <n>", "Birth <n>", "Arrived <n>", "Island
   event <n>", "Unaccounted <n>", "Repair <n>") are numbered per GAME, as they always were, so the
   next number follows the highest already printed in any of the game's folders, shared or slot.

   Header-only and file-static (kernel32 and the C runtime's string functions). */
#ifndef VVFP_LOG_SLOT_H
#define VVFP_LOG_SLOT_H

#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <string.h>
#include "save_layout.h"

#define VV_LOG_SLOTS 5

/* The slot a village header names: the LAST " (Save <S>)" with S 1..5 directly before ")", as every
   reader of the header takes it, so a village named "(Save 2)" cannot shadow the real one.  0 when
   none (NULL, empty, no slot). */
static int vv_log_header_slot(const char *header) {
    const char *at = NULL;
    const char *scan = header;
    if (header == NULL) {
        return 0;
    }
    while ((scan = strstr(scan, " (Save ")) != NULL) {
        at = scan++;
    }
    if (at == NULL || at[7] < '1' || at[7] > '0' + VV_LOG_SLOTS || at[8] != ')') {
        return 0;
    }
    return at[7] - '0';
}

/* The folder, relative to the save folder, of `sub`'s logs ("Births and Conceptions") for `slot`:
   "Virtual Villagers Fun Patcher Logs\Save <slot>\<sub>", or, slot 0, the shared
   "Virtual Villagers Fun Patcher Logs\<sub>".  1 when it fits. */
static int vv_log_rel_w(wchar_t *out, size_t n, int slot, const wchar_t *sub) {
    int written;
    if (out == NULL || n == 0 || sub == NULL) {
        return 0;
    }
    written = slot >= 1 && slot <= VV_LOG_SLOTS
        ? _snwprintf_s(out, n, _TRUNCATE, VV_LOGS_DIR L"\\Save %d\\%ls", slot, sub)
        : _snwprintf_s(out, n, _TRUNCATE, VV_LOGS_DIR L"\\%ls", sub);
    return written > 0;
}

static int vv_log_rel_a(char *out, size_t n, int slot, const char *sub) {
    int written;
    if (out == NULL || n == 0 || sub == NULL) {
        return 0;
    }
    written = slot >= 1 && slot <= VV_LOG_SLOTS
        ? _snprintf_s(out, n, _TRUNCATE, VV_LOGS_DIR_A "\\Save %d\\%s", slot, sub)
        : _snprintf_s(out, n, _TRUNCATE, VV_LOGS_DIR_A "\\%s", sub);
    return written > 0;
}

/* Every folder (absolute, under `save`) that may hold `sub`'s logs, in reading order: the shared
   folder under an older build's name `old_sub` (NULL: none), the shared folder, then the slot
   folders -- only `slot`'s, or all five when `slot` is 0 (a game-wide count).  Nothing is created
   and nothing need exist.  The number of folders written to `out` (room for `max`). */
static int vv_log_read_folders_w(const wchar_t *save, const wchar_t *sub, const wchar_t *old_sub, int slot,
                                 wchar_t (*out)[MAX_PATH], int max) {
    int count = 0;
    int k;
    if (save == NULL || save[0] == L'\0' || sub == NULL || out == NULL) {
        return 0;
    }
    if (old_sub != NULL && count < max
        && _snwprintf_s(out[count], MAX_PATH, _TRUNCATE, L"%ls\\" VV_LOGS_DIR L"\\%ls", save, old_sub) > 0) {
        ++count;
    }
    if (count < max && _snwprintf_s(out[count], MAX_PATH, _TRUNCATE, L"%ls\\" VV_LOGS_DIR L"\\%ls", save, sub) > 0) {
        ++count;
    }
    for (k = 1; k <= VV_LOG_SLOTS && count < max; ++k) {
        if (slot != 0 && k != slot) {
            continue;
        }
        if (_snwprintf_s(out[count], MAX_PATH, _TRUNCATE, L"%ls\\" VV_LOGS_DIR L"\\Save %d\\%ls", save, k, sub) > 0) {
            ++count;
        }
    }
    return count;
}

static int vv_log_read_folders_a(const char *save, const char *sub, const char *old_sub, int slot,
                                 char (*out)[MAX_PATH], int max) {
    int count = 0;
    int k;
    if (save == NULL || save[0] == '\0' || sub == NULL || out == NULL) {
        return 0;
    }
    if (old_sub != NULL && count < max
        && _snprintf_s(out[count], MAX_PATH, _TRUNCATE, "%s\\" VV_LOGS_DIR_A "\\%s", save, old_sub) > 0) {
        ++count;
    }
    if (count < max && _snprintf_s(out[count], MAX_PATH, _TRUNCATE, "%s\\" VV_LOGS_DIR_A "\\%s", save, sub) > 0) {
        ++count;
    }
    for (k = 1; k <= VV_LOG_SLOTS && count < max; ++k) {
        if (slot != 0 && k != slot) {
            continue;
        }
        if (_snprintf_s(out[count], MAX_PATH, _TRUNCATE, "%s\\" VV_LOGS_DIR_A "\\Save %d\\%s", save, k, sub) > 0) {
            ++count;
        }
    }
    return count;
}

/* The records in one file whose line begins `marker` ("Repair ", "Death "), and the highest number
   printed straight after it (0 when none).  Read only; kernel32 only.  0 when the file is absent or
   unreadable, -1 when it is there but cannot be read. */
static int vv_log_marker_numbers_a(const char *path, const char *marker, int *count, long *highest) {
    HANDLE file;
    DWORD size, got = 0, i;
    char *text;
    size_t m = strlen(marker);
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ? 0 : -1;
    }
    size = GetFileSize(file, NULL);
    if (size == INVALID_FILE_SIZE || size > 256u * 1024u * 1024u) {
        CloseHandle(file);
        return -1;
    }
    text = (char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)size + 1);
    if (text == NULL) {
        CloseHandle(file);
        return -1;
    }
    if (!ReadFile(file, text, size, &got, NULL)) {
        HeapFree(GetProcessHeap(), 0, text);
        CloseHandle(file);
        return -1;
    }
    for (i = 0; i < got; ++i) {
        if ((i == 0 || text[i - 1] == '\n') && i + m <= got && strncmp(text + i, marker, m) == 0) {
            long n = 0;
            DWORD j = i + (DWORD)m;
            ++*count;
            while (j < got && text[j] >= '0' && text[j] <= '9' && n < 100000000L) {
                n = n * 10 + (text[j] - '0');
                ++j;
            }
            if (n > *highest) {
                *highest = n;
            }
        }
    }
    HeapFree(GetProcessHeap(), 0, text);
    CloseHandle(file);
    return 1;
}

#endif /* VVFP_LOG_SLOT_H */
