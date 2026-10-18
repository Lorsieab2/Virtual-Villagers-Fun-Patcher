/* One folder per save slot for everything the patcher keeps about it (the owner, 2026-10-17: "FOR
   ANYTHING IN THE SAVES FOLDER, PLEASE MAKE SEPARATE FOLDERS TO PUT ALL THE LOGS AND DATA FOR EACH
   SAVE IN ALL 5 GAMES ... I JUST WANNA DELETE EVERYTHING IN ONE FILE").  src/vv_save_layout.py
   `route` is the patcher's side and keeps the same rules.

       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Logs\<the log's own folder>\<its name>
       <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\<the kind's folder>\<... - Save <S>.dat>

   Every writer and reader still builds the OLDER layout's path ("...Logs\Save <S>\<sub>\..." or
   "...Data\<kind>\<name> - Save <S>.<ext>") and hands it to vv_ps_route_*, which puts it in ONE place,
   decided by what is already there -- never a clock, never a guess -- so writers and readers always
   agree and no history is split:

     a log: its unit is the slot's folder of that log ("Logs\Save <S>\Deaths and Disappearances").
       The new folder once it exists; else the older one while it holds anything (written where it is
       until the player moves it with Repair Saves & Logs' "Move Files to Save Folders..."); else the
       new one.  Readers read both (log_slot.h vv_log_read_folders_*), the older first.
     a data file: its unit is the file ("x - Save 1.dat" for its ".tmp" and set-aside copies too).
       Only one place has it: that one; both: the one written last (a tie or an unreadable time: the
       new); neither: the new.

   A new place that would not fit in the caller's buffer is never used: the older layout's path is
   kept, the same answer every time for that folder.  NOTHING IS MOVED, RENAMED OR DELETED HERE.
   Not one save's, and never routed: the older shared logs ("...Logs\<sub>\", no slot), the Like and
   Dislike Words of the older layout, a loose file in the Data folder itself, the Copies Made Before
   Repairs of an older-layout file, Backups, Family Trees and the game's own saves.

   The string "Virtual Villagers Fun Patcher\Save " in a companion is how the patcher tells that the
   companion knows this layout (src/vv_move_to_save_folders.py).

   Header-only, file-static, kernel32 only. */
#ifndef VVFP_PER_SAVE_H
#define VVFP_PER_SAVE_H

#include <windows.h>

#define VV_SAVES_DIR L"Virtual Villagers Fun Patcher"
#define VV_SAVES_DIR_A "Virtual Villagers Fun Patcher"
#define VV_PS_LOGS_OLD L"\\Virtual Villagers Fun Patcher Logs\\Save "
#define VV_PS_DATA_OLD L"\\Virtual Villagers Fun Patcher Data\\"
#define VV_PS_COPIES L"Copies Made Before Repairs"

/* "\Virtual Villagers Fun Patcher\Save " -- the new layout's own stem. */
static const wchar_t vv_ps_new_stem[] = L"\\" VV_SAVES_DIR L"\\Save ";

static int vv_ps_starts_i(const wchar_t *s, const wchar_t *prefix) {
    int n = lstrlenW(prefix);
    return lstrlenW(s) >= n && CompareStringW(LOCALE_INVARIANT, NORM_IGNORECASE, s, n, prefix, n) == CSTR_EQUAL;
}

/* The first case-insensitive occurrence of `needle` in `hay`, or NULL. */
static const wchar_t *vv_ps_find_i(const wchar_t *hay, const wchar_t *needle) {
    for (; *hay != L'\0'; ++hay) {
        if (vv_ps_starts_i(hay, needle)) {
            return hay;
        }
    }
    return NULL;
}

#define VV_PS_NONE   0
#define VV_PS_FOLDER 1   /* a log: its unit is the slot's folder of that log */
#define VV_PS_FILE   2   /* a data file: its unit is the file */

/* How an older-layout path maps: its kind, its slot, the length of the save folder in `path`
   (`*base`), and where the part kept as it is starts (`*rest`: after "Save <S>\" for a log, after
   "Data\" for a data file).  Names only; nothing is looked at. */
static int vv_ps_classify(const wchar_t *path, int *slot, int *base, const wchar_t **rest) {
    const wchar_t *at;
    if (vv_ps_find_i(path, VV_PS_DATA_OLD VV_PS_COPIES L"\\") != NULL) {
        /* A copy of an older-layout file -- a LOG's too ("...Copies Made Before Repairs\Virtual
           Villagers Fun Patcher Logs\Save <S>\...", which the log test below would otherwise take for
           the slot's log) -- stays with the older layout. */
        return VV_PS_NONE;
    }
    at = vv_ps_find_i(path, VV_PS_LOGS_OLD);
    if (at != NULL) {
        const wchar_t *s = at + lstrlenW(VV_PS_LOGS_OLD);
        if (*s >= L'1' && *s <= L'5' && (s[1] == L'\\' || s[1] == L'\0')) {
            *slot = *s - L'0';
            *base = (int)(at - path);
            *rest = s[1] == L'\\' ? s + 2 : s + 1;
            return VV_PS_FOLDER;
        }
        return VV_PS_NONE;
    }
    at = vv_ps_find_i(path, VV_PS_DATA_OLD);
    if (at != NULL) {
        const wchar_t *inside = at + lstrlenW(VV_PS_DATA_OLD);
        const wchar_t *name = inside, *p, *found = NULL;
        for (p = inside; *p != L'\0'; ++p) {
            if (*p == L'\\') {
                name = p + 1;
            }
        }
        if (name == inside) {
            return VV_PS_NONE;               /* loose in the Data folder: an older build's */
        }
        if (vv_ps_starts_i(inside, VV_PS_COPIES L"\\")) {
            return VV_PS_NONE;               /* an older-layout file's copy stays with the older layout */
        }
        {
            /* A file under an OLDER BUILD'S NAME (save_layout.h) stays where it is: the save's own
               folder holds only the newest names, and an older patch reads only the older place. */
            static const wchar_t *const OLDER_FOLDERS[4] = {
                L"Cross-Check\\", L"Parentage Records\\", L"Log Words\\", L"Genealogy\\"
            };
            int k;
            for (k = 0; k < 4; ++k) {
                if (vv_ps_starts_i(inside, OLDER_FOLDERS[k])) {
                    return VV_PS_NONE;
                }
            }
            for (p = name; *p != L'\0'; ++p) {
                if ((p == name || p[-1] == L' ') && vv_ps_starts_i(p, L"Village Roster - Save ")) {
                    return VV_PS_NONE;       /* "...Village Roster": now "Villagers at Last Save" / "Villagers Counted" */
                }
                if (vv_ps_starts_i(p, L" Genealogy Edits - Save ")) {
                    return VV_PS_NONE;       /* now "Family Tree Edits" */
                }
            }
        }
        for (p = name; *p != L'\0'; ++p) {
            if (vv_ps_starts_i(p, L" - Save ") && p[8] >= L'1' && p[8] <= L'5'
                && (p[9] == L'.' || p[9] == L'\0')) {
                found = p;                   /* the LAST " - Save <S>" directly before an extension */
            }
        }
        if (found == NULL) {
            return VV_PS_NONE;
        }
        *slot = found[8] - L'0';
        *base = (int)(at - path);
        *rest = inside;
        return VV_PS_FILE;
    }
    return VV_PS_NONE;
}

/* `dst` = `a` (its first `a_len` characters) + `b` + `c`, when it fits in `cap`. */
static int vv_ps_join(wchar_t *dst, int cap, const wchar_t *a, int a_len, const wchar_t *b, const wchar_t *c) {
    int b_len = lstrlenW(b), c_len = lstrlenW(c);
    if (a_len < 0 || a_len + b_len + c_len + 1 > cap) {
        return 0;
    }
    lstrcpynW(dst, a, a_len + 1);
    lstrcpyW(dst + a_len, b);
    lstrcpyW(dst + a_len + b_len, c);
    return 1;
}

/* The save's own place for an older-layout path: "<save>\Virtual Villagers Fun Patcher\Save <S>\Logs\
   <rest>" or "...\Data\<rest>".  0 when it is not one save's, or does not fit in `cap`. */
static int vv_ps_new_path_w(const wchar_t *path, wchar_t *out, int cap) {
    int slot = 0, base = 0;
    const wchar_t *rest = NULL;
    int kind = vv_ps_classify(path, &slot, &base, &rest);
    wchar_t middle[64];
    if (kind == VV_PS_NONE) {
        return 0;
    }
    lstrcpyW(middle, vv_ps_new_stem);
    {
        int n = lstrlenW(middle);
        middle[n] = (wchar_t)(L'0' + slot);
        middle[n + 1] = L'\0';
    }
    lstrcatW(middle, kind == VV_PS_FOLDER ? L"\\Logs" : L"\\Data");
    if (rest[0] != L'\0') {
        lstrcatW(middle, L"\\");
    }
    return vv_ps_join(out, cap, path, base, middle, rest);
}

/* 0 certainly absent, 1 there, 2 there but not examinable (counted as there). */
static int vv_ps_there(const wchar_t *path, FILETIME *written, int *is_dir) {
    WIN32_FILE_ATTRIBUTE_DATA info;
    DWORD error;
    if (GetFileAttributesExW(path, GetFileExInfoStandard, &info)) {
        if (written != NULL) {
            *written = info.ftLastWriteTime;
        }
        if (is_dir != NULL) {
            *is_dir = (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
        }
        return 1;
    }
    error = GetLastError();
    return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ? 0 : 2;
}

/* Does the folder hold anything at all?  An unexaminable one counts as holding something. */
static int vv_ps_holds_anything(const wchar_t *folder) {
    wchar_t filter[MAX_PATH + 4];
    WIN32_FIND_DATAW found;
    HANDLE search;
    DWORD error;
    int any = 0;
    if (!vv_ps_join(filter, MAX_PATH + 4, folder, lstrlenW(folder), L"\\*", L"")) {
        return 1;
    }
    search = FindFirstFileW(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        error = GetLastError();
        return !(error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND || error == ERROR_DIRECTORY);
    }
    do {
        if (!(found.cFileName[0] == L'.' && (found.cFileName[1] == L'\0'
                                             || (found.cFileName[1] == L'.' && found.cFileName[2] == L'\0')))) {
            any = 1;
        }
    } while (!any && FindNextFileW(search, &found));
    FindClose(search);
    return any;
}

/* The unit of a path: for a log, the slot's folder of that log (or "Save <S>" itself); for a data
   file, the file up to the end of its " - Save <S>.<ext>".  `rest_at` is where in `path` the kept part
   starts, `kind` the kind. */
static int vv_ps_unit(const wchar_t *path, const wchar_t *rest_at, int kind, wchar_t *out, int cap) {
    const wchar_t *end = rest_at;
    if (kind == VV_PS_FOLDER) {
        while (*end != L'\0' && *end != L'\\') {
            ++end;
        }
        if (end == rest_at) {
            end = rest_at > path && rest_at[-1] == L'\\' ? rest_at - 1 : rest_at;
        }
    } else {
        const wchar_t *p, *found = NULL;
        for (p = rest_at; *p != L'\0'; ++p) {
            if (vv_ps_starts_i(p, L" - Save ") && p[8] >= L'1' && p[8] <= L'5' && (p[9] == L'.' || p[9] == L'\0')) {
                found = p;
            }
        }
        if (found == NULL) {
            return 0;
        }
        end = found + 9;
        if (*end == L'.') {
            ++end;
            while (*end != L'\0' && *end != L'.' && *end != L'\\') {
                ++end;
            }
        }
    }
    return vv_ps_join(out, cap, path, (int)(end - path), L"", L"");
}

/* 1 when the save's own folder is the place for `path` (an older-layout path), 0 for the older
   layout.  `fresh` is the save's own path (vv_ps_new_path_w). */
static int vv_ps_pick_new(const wchar_t *path, const wchar_t *fresh) {
    int slot = 0, base = 0, fresh_slot = 0, fresh_base = 0;
    const wchar_t *rest = NULL, *fresh_rest = NULL;
    wchar_t old_unit[MAX_PATH], new_unit[MAX_PATH];
    int kind = vv_ps_classify(path, &slot, &base, &rest);
    if (kind == VV_PS_NONE) {
        return 0;
    }
    /* The new path's kept part starts after "...\Save <S>\Logs\" or "...\Data\". */
    fresh_base = base + lstrlenW(vv_ps_new_stem) + 1 + 5;
    fresh_rest = fresh + fresh_base + (rest[0] != L'\0' ? 1 : 0);
    (void)fresh_slot;
    if (!vv_ps_unit(path, rest, kind, old_unit, MAX_PATH) || !vv_ps_unit(fresh, fresh_rest, kind, new_unit, MAX_PATH)) {
        return 0;
    }
    if (kind == VV_PS_FOLDER) {
        int is_dir = 0;
        if (vv_ps_there(new_unit, NULL, &is_dir) == 1 && is_dir) {
            return 1;
        }
        return !vv_ps_holds_anything(old_unit);
    }
    {
        FILETIME old_time = {0, 0}, new_time = {0, 0};
        int old_dir = 0, new_dir = 0;
        int old_state = vv_ps_there(old_unit, &old_time, &old_dir);
        int new_state = vv_ps_there(new_unit, &new_time, &new_dir);
        if (old_state == 0) {
            return 1;
        }
        if (new_state == 0) {
            return 0;
        }
        if (old_state == 1 && new_state == 1 && !old_dir && !new_dir && CompareFileTime(&old_time, &new_time) > 0) {
            return 0;
        }
        return 1;
    }
}

/* Every folder from the save folder down to `path`'s own folder, created (only for a path routed to
   the save's own folder: the older layout's folders are never made by routing). */
static void vv_ps_make_parents_w(const wchar_t *path) {
    wchar_t built[MAX_PATH];
    int i, n = lstrlenW(path);
    if (n >= MAX_PATH) {
        return;
    }
    lstrcpyW(built, path);
    for (i = 3; i < n; ++i) {
        if (built[i] == L'\\') {
            built[i] = L'\0';
            (void)CreateDirectoryW(built, NULL);
            built[i] = L'\\';
        }
    }
}

static void vv_ps_make_parents_a(const char *path) {
    wchar_t wide[MAX_PATH];
    if (path != NULL && MultiByteToWideChar(CP_ACP, 0, path, -1, wide, MAX_PATH) > 0) {
        vv_ps_make_parents_w(wide);
    }
}

/* Route `path` (an absolute path of the older layout, `cap` characters of room) in place: the save's
   own folder or the older layout, by the rules at the top.  Not one save's, or a new place that does
   not fit: left as it is.  `make` 1 creates the new place's folders (for a writer; the path's own last
   component is never created).  Returns 1 when `path` now names the save's own folder. */
static int vv_ps_route_w(wchar_t *path, int cap, int make) {
    wchar_t fresh[MAX_PATH];
    if (path == NULL || cap <= 0 || !vv_ps_new_path_w(path, fresh, cap < MAX_PATH ? cap : MAX_PATH)) {
        return 0;
    }
    if (!vv_ps_pick_new(path, fresh)) {
        return 0;
    }
    lstrcpyW(path, fresh);
    if (make) {
        vv_ps_make_parents_w(path);
    }
    return 1;
}

/* The same for an ANSI path (the companions that use the ANSI API). */
static int vv_ps_route_a(char *path, int cap, int make) {
    wchar_t wide[MAX_PATH];
    int routed;
    if (path == NULL || cap <= 0 || MultiByteToWideChar(CP_ACP, 0, path, -1, wide, MAX_PATH) <= 0) {
        return 0;
    }
    routed = vv_ps_route_w(wide, cap < MAX_PATH ? cap : MAX_PATH, make);
    if (!routed) {
        return 0;
    }
    {
        char narrow[MAX_PATH];
        BOOL lossy = FALSE;
        int n = WideCharToMultiByte(CP_ACP, 0, wide, -1, narrow, MAX_PATH, NULL, &lossy);
        if (n <= 0 || lossy || n > cap) {
            return 0;                        /* cannot be said in ANSI: the older layout, as before */
        }
        lstrcpyA(path, narrow);
    }
    return 1;
}

/* The save's own folder for an older-layout log folder ("...Logs\Save <S>\<sub>"), whether or not
   it is there (for a reader that reads both).  0 when not one save's, or it does not fit. */
static int vv_ps_new_folder_w(const wchar_t *old_folder, wchar_t *out, int cap) {
    return vv_ps_new_path_w(old_folder, out, cap);
}

static int vv_ps_new_folder_a(const char *old_folder, char *out, int cap) {
    wchar_t wide[MAX_PATH], fresh[MAX_PATH];
    BOOL lossy = FALSE;
    int n;
    if (MultiByteToWideChar(CP_ACP, 0, old_folder, -1, wide, MAX_PATH) <= 0
        || !vv_ps_new_path_w(wide, fresh, cap < MAX_PATH ? cap : MAX_PATH)) {
        return 0;
    }
    n = WideCharToMultiByte(CP_ACP, 0, fresh, -1, out, cap, NULL, &lossy);
    return n > 0 && !lossy;
}

#endif /* VVFP_PER_SAVE_H */
