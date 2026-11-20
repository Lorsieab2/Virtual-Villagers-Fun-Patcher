/* multiplier_choice.h -- a multiplier slider's number, as the patcher writes it beside a companion.

   The owner (2026-11-17): every multiplier slider goes LESS as well as more, 0.1x to its maximum in steps of 0.1,
   1x the normal game.  The patcher (src/vv_fun_patcher.py, multiplier_text) writes the number in ASCII as "2",
   "0.5" or "12.3": digits, then at most one '.' and one digit.  vvfp_read_tenths() reads it as TENTHS (2 -> 20,
   0.5 -> 5), kept within [minimum, maximum] tenths; a missing or unreadable file, or no digit before the first
   other character, is `fallback`.  A second decimal digit is ignored (the patcher never writes one).  Only the first
   15 bytes are read; nothing is written. */
#ifndef VVFP_MULTIPLIER_CHOICE_H
#define VVFP_MULTIPLIER_CHOICE_H

#include <windows.h>
#include "patcher_files.h"

/* The tenths `text` (its first `length` bytes) holds, or `fallback`; kept within [minimum, maximum]. */
static __inline unsigned int vvfp_parse_tenths(const char *text, DWORD length, unsigned int fallback,
                                      unsigned int minimum, unsigned int maximum) {
    DWORD i = 0;
    unsigned int whole = 0, tenth = 0, tenths;
    int digits = 0;
    while (i < length && (text[i] == ' ' || text[i] == '\t')) {
        ++i;
    }
    for (; i < length && text[i] >= '0' && text[i] <= '9'; ++i) {
        if (whole < 100000u) {
            whole = whole * 10u + (unsigned int)(text[i] - '0');
        }
        ++digits;
    }
    if (i < length && text[i] == '.') {
        ++i;
        if (i < length && text[i] >= '0' && text[i] <= '9') {
            tenth = (unsigned int)(text[i] - '0');
            ++digits;
        }
    }
    if (digits == 0) {
        return fallback;
    }
    tenths = whole * 10u + tenth;
    return tenths < minimum ? minimum : (tenths > maximum ? maximum : tenths);
}

/* The tenths in the patcher's file `name` (beside the companions), or `fallback`. */
static __inline unsigned int vvfp_read_tenths(const char *name, unsigned int fallback, unsigned int minimum,
                                     unsigned int maximum) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    char text[16];
    DWORD got = 0;
    HANDLE file;
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, name) == 0) {
        return fallback;
    }
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return fallback;
    }
    if (!ReadFile(file, text, (DWORD)(sizeof text - 1), &got, NULL)) {
        got = 0;
    }
    CloseHandle(file);
    return vvfp_parse_tenths(text, got, fallback, minimum, maximum);
}

#endif /* VVFP_MULTIPLIER_CHOICE_H */
