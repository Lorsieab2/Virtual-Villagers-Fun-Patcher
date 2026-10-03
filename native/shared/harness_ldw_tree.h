/* Leave the player's Documents\LDW exactly as the harness found it.

   A harness that drives a shipped companion makes that companion write where
   it would in a game: Documents\LDW\<this exe's basename>\..., i.e. inside the
   real LDW save folder. The harnesses deleted their own files, but folders the
   companion created on the way (log and data folders, the per-exe folder, and
   LDW itself on a machine that had none) were left behind after every run.

   harness_ldw_tree_begin() records, before anything is written, which of those
   folders already exist. At process exit -- a normal return, exit(), or an
   unhandled crash -- it removes what this run created and nothing else:

     - LDW\<basename> did not exist: the whole tree under it is this run's own,
       so every file and folder in it is removed, then the folder itself;
     - it already existed (an earlier run that was killed, or a real folder):
       only folders that were not there at the start are removed, and only
       while empty -- no file in a pre-existing tree is ever touched;
     - LDW did not exist: it is removed too, if it is empty.

   The paths are derived at run time from the Documents folder and this exe's
   own name, the same way the companions derive theirs, so nothing here names
   a machine-specific folder. ExitProcess() skips the CRT's exit handlers, so a
   harness using this header exits with exit() instead.

   Link shell32 (SHGetSpecialFolderPathA). Include once per harness. */
#ifndef VVFP_HARNESS_LDW_TREE_H
#define VVFP_HARNESS_LDW_TREE_H

#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HARNESS_LDW_MAX_DIRS 256

static char harness_ldw_root[MAX_PATH];   /* Documents\LDW */
static char harness_ldw_tree[MAX_PATH];   /* Documents\LDW\<basename> */
static int harness_ldw_ready;
static int harness_ldw_root_existed;
static int harness_ldw_tree_existed;
static int harness_ldw_done;
static char harness_ldw_kept[HARNESS_LDW_MAX_DIRS][MAX_PATH];
static int harness_ldw_kept_count;
static int harness_ldw_kept_overflow; /* too many to record: sweep nothing */

static int harness_ldw_is_dir(const char *path) {
    DWORD a = GetFileAttributesA(path);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY) != 0
        && (a & FILE_ATTRIBUTE_REPARSE_POINT) == 0;
}

/* Every folder below `folder`, recorded so the end step can tell them apart
   from folders this run creates. */
static void harness_ldw_record(const char *folder) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", folder);
    pattern[MAX_PATH - 1] = 0;
    h = FindFirstFileA(pattern, &f);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!(f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        if (!strcmp(f.cFileName, ".") || !strcmp(f.cFileName, "..")) continue;
        _snprintf(path, MAX_PATH, "%s\\%s", folder, f.cFileName);
        path[MAX_PATH - 1] = 0;
        if (harness_ldw_kept_count < HARNESS_LDW_MAX_DIRS) {
            lstrcpynA(harness_ldw_kept[harness_ldw_kept_count++], path, MAX_PATH);
        } else {
            harness_ldw_kept_overflow = 1;
        }
        if (!(f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) harness_ldw_record(path);
    } while (FindNextFileA(h, &f));
    FindClose(h);
}

static int harness_ldw_was_kept(const char *path) {
    int i;
    for (i = 0; i < harness_ldw_kept_count; ++i) {
        if (lstrcmpiA(harness_ldw_kept[i], path) == 0) return 1;
    }
    return 0;
}

/* Depth first. `owned`: the whole tree is this run's, so files go too.
   Otherwise only new folders, and only once empty. A reparse point is never
   followed: it is removed as a link if owned, never walked into. */
static void harness_ldw_sweep(const char *folder, int owned) {
    char pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA f;
    HANDLE h;
    _snprintf(pattern, MAX_PATH, "%s\\*", folder);
    pattern[MAX_PATH - 1] = 0;
    h = FindFirstFileA(pattern, &f);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!strcmp(f.cFileName, ".") || !strcmp(f.cFileName, "..")) continue;
        _snprintf(path, MAX_PATH, "%s\\%s", folder, f.cFileName);
        path[MAX_PATH - 1] = 0;
        if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (!(f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
                harness_ldw_sweep(path, owned);
            }
            if (owned || !harness_ldw_was_kept(path)) RemoveDirectoryA(path);
        } else if (owned) {
            SetFileAttributesA(path, FILE_ATTRIBUTE_NORMAL);
            DeleteFileA(path);
        }
    } while (FindNextFileA(h, &f));
    FindClose(h);
}

static void harness_ldw_tree_end(void) {
    if (!harness_ldw_ready || harness_ldw_done) return;
    harness_ldw_done = 1;
    if (!harness_ldw_is_dir(harness_ldw_tree)) {
        /* nothing was created under the per-exe folder */
    } else if (!harness_ldw_tree_existed) {
        harness_ldw_sweep(harness_ldw_tree, 1);
        RemoveDirectoryA(harness_ldw_tree);
    } else if (!harness_ldw_kept_overflow) {
        harness_ldw_sweep(harness_ldw_tree, 0);
    }
    if (!harness_ldw_root_existed) RemoveDirectoryA(harness_ldw_root);
}

static LONG WINAPI harness_ldw_on_crash(EXCEPTION_POINTERS *info) {
    (void)info;
    harness_ldw_tree_end();
    return EXCEPTION_CONTINUE_SEARCH;
}

/* Call first in main(), before anything can write under Documents\LDW. */
static void harness_ldw_tree_begin(void) {
    char docs[MAX_PATH], exe[MAX_PATH], *base, *dot;
    if (harness_ldw_ready) return;
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) return;
    if (GetModuleFileNameA(NULL, exe, MAX_PATH) == 0) return;
    base = strrchr(exe, '\\');
    base = base != NULL ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) *dot = 0;
    if (*base == 0) return;
    _snprintf(harness_ldw_root, MAX_PATH, "%s\\LDW", docs);
    harness_ldw_root[MAX_PATH - 1] = 0;
    _snprintf(harness_ldw_tree, MAX_PATH, "%s\\%s", harness_ldw_root, base);
    harness_ldw_tree[MAX_PATH - 1] = 0;
    harness_ldw_root_existed = harness_ldw_is_dir(harness_ldw_root);
    harness_ldw_tree_existed = harness_ldw_is_dir(harness_ldw_tree);
    if (harness_ldw_tree_existed) harness_ldw_record(harness_ldw_tree);
    harness_ldw_ready = 1;
    atexit(harness_ldw_tree_end);
    SetUnhandledExceptionFilter(harness_ldw_on_crash);
}

#endif
