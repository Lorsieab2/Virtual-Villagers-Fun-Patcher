/* A save's data file, routed (per_save.h): for the companions that build
       "<save folder>\Virtual Villagers Fun Patcher Data\<kind>\<name - Save S.ext>"
   themselves.  The answer is the save's own "Virtual Villagers Fun Patcher\Save <S>\Data\<kind>\<name>"
   (its folders made) or, while the file is still there, the older layout's (its folder made, as
   before).  The older layout's folders are made only when the older place is the answer, so a new save
   never leaves an empty "Virtual Villagers Fun Patcher Data" behind.

   Needs save_folder.c linked in.  Header-only and file-static. */
#ifndef VVFP_PER_SAVE_DATA_H
#define VVFP_PER_SAVE_DATA_H

#include <windows.h>
#include "save_folder.h"
#include "per_save.h"

/* Room every caller keeps after the path, with the NUL: sidecar_io.h's ".unreadable-<ticks>-<n>". */
#define VV_PS_RESERVE ((int)sizeof(".unreadable-4294967295-999"))

/* `out` (MAX_PATH characters) = the place to read and write `name` of `kind` ("Graves", "Custom
   Titles"...).  `reserve` is what the caller still appends (with the NUL; at least 1).  1 on success;
   on failure `out` must not be used. */
static int vv_ps_data_file_w(wchar_t *out, const wchar_t *kind, const wchar_t *name, int reserve) {
    wchar_t folder[MAX_PATH], old[MAX_PATH];
    int tail;
    if (out == NULL || kind == NULL || name == NULL || reserve < 1) {
        return 0;
    }
    tail = lstrlenW(L"\\Virtual Villagers Fun Patcher Data\\") + lstrlenW(kind) + 1 + lstrlenW(name) + reserve;
    if (!vv_save_folder_w(folder, tail)) {
        return 0;
    }
    lstrcpyW(old, folder);
    lstrcatW(old, L"\\Virtual Villagers Fun Patcher Data\\");
    lstrcatW(old, kind);
    lstrcatW(old, L"\\");
    lstrcatW(old, name);
    if (!vv_ps_route_w(old, MAX_PATH - reserve + 1, 1)) {
        /* The older layout's place: its two folders, as the callers always made them. */
        wchar_t made[MAX_PATH];
        lstrcpyW(made, folder);
        lstrcatW(made, L"\\Virtual Villagers Fun Patcher Data");
        (void)CreateDirectoryW(made, NULL);
        lstrcatW(made, L"\\");
        lstrcatW(made, kind);
        (void)CreateDirectoryW(made, NULL);
    }
    lstrcpyW(out, old);
    return 1;
}

static int vv_ps_data_file_a(char *out, const char *kind, const char *name, int reserve) {
    wchar_t wide_kind[MAX_PATH], wide_name[MAX_PATH], wide[MAX_PATH];
    BOOL lossy = FALSE;
    if (out == NULL || kind == NULL || name == NULL
        || MultiByteToWideChar(CP_ACP, 0, kind, -1, wide_kind, MAX_PATH) <= 0
        || MultiByteToWideChar(CP_ACP, 0, name, -1, wide_name, MAX_PATH) <= 0
        || !vv_ps_data_file_w(wide, wide_kind, wide_name, reserve)) {
        return 0;
    }
    return WideCharToMultiByte(CP_ACP, 0, wide, -1, out, MAX_PATH - reserve + 1, NULL, &lossy) > 0 && !lossy;
}

#endif /* VVFP_PER_SAVE_DATA_H */
