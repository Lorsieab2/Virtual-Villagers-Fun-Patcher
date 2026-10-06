/* Reading New Believers' Former Heathens file (native/shared/former_heathens.h)
   for the log exporters: the slot's file, read whole, validated, then asked
   for a villager's mask by identity.  No file, an unreadable or invalid one:
   nothing is known (the title falls back to what the record itself keeps).

   Needs native/shared/save_folder.h (vv_save_folder) in the including file.
   Header-only and static. */
#ifndef VV_FORMER_HEATHENS_READ_H
#define VV_FORMER_HEATHENS_READ_H

#include <windows.h>
#include "former_heathens.h"

/* Read the slot's file into `buffer` (VV_FORMER_FILE_MAX bytes).  1 when it
   was there and valid. */
static int vv_former_load(int slot, unsigned char *buffer) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    HANDLE h;
    DWORD got = 0;
    if (slot < 1 || slot > 5
        || !vv_save_folder(folder, (int)sizeof("\\" VV_FORMER_SUBFOLDER "\\Former Heathens - Save 0.dat"))) {
        return 0;
    }
    lstrcatA(folder, "\\" VV_FORMER_SUBFOLDER);
    if (!vv_former_file_name(path, MAX_PATH, folder, slot)) {
        return 0;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!ReadFile(h, buffer, VV_FORMER_FILE_MAX, &got, NULL)) {
        got = 0;
    }
    CloseHandle(h);
    return got > 0 && vv_former_validate(buffer, got);
}

/* The slot ("... (Save <n>)", the LAST such marker, as every reader takes
   it) a village header names; 0 when none. */
static int vv_former_header_slot(const char *village) {
    const char *at = NULL;
    const char *scan = village;
    while ((scan = strstr(scan, " (Save ")) != NULL) {
        at = scan++;
    }
    if (at == NULL || at[7] < '1' || at[7] > '5' || at[8] != ')') {
        return 0;
    }
    return at[7] - '0';
}

#endif /* VV_FORMER_HEATHENS_READ_H */
