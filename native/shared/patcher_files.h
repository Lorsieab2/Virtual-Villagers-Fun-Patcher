/* Where the patcher's own files are, and how a companion loads one.

   Every file the patcher adds to a patched game folder -- every companion
   DLL, "VVFP Startup.dll", the images and data only the companions read,
   the patch log and the transparency log -- is in ONE folder beside the
   executable (owner, 2026-10-04: "put all the patcher dlls and files into a
   folder 'Virtual Villagers Fun Patcher Files' to clean up the game folders
   a bit, all 5 games"):

       <game folder>\Virtual Villagers Fun Patcher Files\

   The only files elsewhere are the ones the GAME ENGINE opens by its own
   path (a replaced stock file, or an image the game's own sprite loader
   reads from Images\); src/patcher_files.py lists each with its reason.

   THE RULES EVERY COMPANION FOLLOWS.

     * The folder is found from the EXECUTABLE'S own path
       (GetModuleFileNameW(NULL)), never the current directory, so a
       shortcut or launcher that starts the game somewhere else changes
       nothing.

     * A companion is loaded by its FULL path only.  A bare name is never
       passed to LoadLibrary: the DLL search order (the system folders, the
       current directory, PATH) is never consulted, so neither a same-named
       file elsewhere nor a loose copy an older patcher left beside the
       executable is ever loaded.

     * The WIDE API is used throughout, so a game installed in a folder
       whose name the ANSI code page cannot spell (an accented or Japanese
       folder name) still finds its files; the ANSI API would hand back '?'
       for those characters and every load would fail.

     * Every failure (the path cannot be read, it does not fit, the file is
       not there) is reported as 0 / NULL, which every caller already treats
       as "that companion is not shipped": the game always runs.

   Header-only; everything is static __inline, so a companion that uses only one
   helper compiles the rest away. */
#ifndef VVFP_PATCHER_FILES_H
#define VVFP_PATCHER_FILES_H

#include <windows.h>

#define VVFP_PATCHER_FILES_FOLDER "Virtual Villagers Fun Patcher Files"

/* Room for any path built here, in WCHARs: well past MAX_PATH, so a long
   game folder is decided by Windows itself (a path it cannot open simply
   fails to load), never cut short here. */
#define VVFP_PATCHER_FILES_PATH_CAP 1024

#ifndef VVFP_PATCHER_FILES_MODULE_PATH
/* The executable's own path; a test harness may supply its own. */
#define VVFP_PATCHER_FILES_MODULE_PATH(out, cap) GetModuleFileNameW(NULL, (out), (cap))
#endif

/* Write "<executable's folder>\<folder>\<leaf>" into `out` (`cap` WCHARs),
   or "<executable's folder>\<leaf>" when `folder` is NULL.  `folder` and
   `leaf` are plain ASCII ("VVFP Fix Huts.dll", "Images\\golden_mushroom.png";
   '/' is written as '\\').  Returns the length written (without the NUL),
   or 0 -- and then `out` must not be used -- when the executable's path
   cannot be read or was cut short, a name is empty, not printable ASCII,
   absolute, or climbs out with "..", or the result does not fit. */
static __inline DWORD vvfp_exe_relative_path_w(wchar_t *out, DWORD cap, const char *folder,
                                      const char *leaf) {
    const char *parts[2];
    DWORD n;
    DWORD i;
    DWORD pos;
    DWORD slash = (DWORD)-1;
    int part;
    if (out == NULL || cap < 2 || leaf == NULL) {
        return 0;
    }
    parts[0] = folder;
    parts[1] = leaf;
    for (part = 0; part < 2; ++part) {
        const char *text = parts[part];
        if (text == NULL) {
            continue;
        }
        if (text[0] == '\0' || text[0] == '\\' || text[0] == '/') {
            return 0;
        }
        for (i = 0; text[i] != '\0'; ++i) {
            unsigned char c = (unsigned char)text[i];
            if (c < 0x20 || c >= 0x7F || c == ':') {
                return 0;
            }
            if (c == '.' && text[i + 1] == '.'
                && (i == 0 || text[i - 1] == '\\' || text[i - 1] == '/')
                && (text[i + 2] == '\0' || text[i + 2] == '\\' || text[i + 2] == '/')) {
                return 0;
            }
        }
    }
    n = VVFP_PATCHER_FILES_MODULE_PATH(out, cap);
    if (n == 0 || n >= cap) {
        return 0;                      /* unreadable, or cut short */
    }
    for (i = 0; i < n; ++i) {
        if (out[i] == L'\\' || out[i] == L'/') {
            slash = i;
        }
    }
    if (slash == (DWORD)-1) {
        return 0;
    }
    pos = slash + 1;
    for (part = 0; part < 2; ++part) {
        const char *text = parts[part];
        if (text == NULL) {
            continue;
        }
        for (i = 0; text[i] != '\0'; ++i) {
            if (pos + 1 >= cap) {
                return 0;
            }
            out[pos++] = text[i] == '/' ? L'\\' : (wchar_t)(unsigned char)text[i];
        }
        if (part == 0) {
            if (pos + 1 >= cap) {
                return 0;
            }
            out[pos++] = L'\\';
        }
    }
    out[pos] = L'\0';
    return pos;
}

/* "<executable's folder>\Virtual Villagers Fun Patcher Files\<leaf>". */
static __inline DWORD vvfp_patcher_file_path_w(wchar_t *out, DWORD cap, const char *leaf) {
    return vvfp_exe_relative_path_w(out, cap, VVFP_PATCHER_FILES_FOLDER, leaf);
}

/* "<executable's folder>\<leaf>": a file the GAME opens in place. */
static __inline DWORD vvfp_game_file_path_w(wchar_t *out, DWORD cap, const char *leaf) {
    return vvfp_exe_relative_path_w(out, cap, NULL, leaf);
}

static __inline int vvfp_file_exists_w(const wchar_t *path) {
    DWORD attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES
        && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

/* Is the patcher's file `leaf` in its folder (and not a directory)? */
static __inline int vvfp_patcher_file_exists(const char *leaf) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    return vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, leaf) != 0
        && vvfp_file_exists_w(path);
}

/* Is the game's file `leaf` (relative to the executable's folder) there? */
static __inline int vvfp_game_file_exists(const char *leaf) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    return vvfp_game_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, leaf) != 0
        && vvfp_file_exists_w(path);
}

/* Load the patcher's companion `leaf` by its full path in the patcher's
   folder; NULL when it is not shipped or cannot be loaded.  Anything it
   imports resolves from that folder first, then the system folders
   (LOAD_WITH_ALTERED_SEARCH_PATH); every companion imports only Windows
   system DLLs.  Never called from DllMain. */
static __inline HMODULE vvfp_load_patcher_dll(const char *leaf) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    if (vvfp_patcher_file_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, leaf) == 0) {
        return NULL;
    }
    return LoadLibraryExW(path, NULL, LOAD_WITH_ALTERED_SEARCH_PATH);
}

/* The companion `leaf` when it is already loaded, else loaded as above.
   GetModuleHandleA of a bare module name only looks among the modules
   already in the process; it never searches for a file. */
static __inline HMODULE vvfp_patcher_dll(const char *leaf) {
    HMODULE module = GetModuleHandleA(leaf);
    return module != NULL ? module : vvfp_load_patcher_dll(leaf);
}

#endif /* VVFP_PATCHER_FILES_H */
