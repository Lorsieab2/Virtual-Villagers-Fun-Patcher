/* Leave the player's Documents\LDW exactly as the harness found it.

   A harness that drives a shipped companion makes that companion write where
   it would in a game: Documents\LDW\<this exe's basename>\..., i.e. inside the
   real LDW save folder. The harnesses deleted their own files, but folders the
   companion created on the way (log and data folders, the per-exe folder, and
   LDW itself on a machine that had none) were left behind after every run --
   and several harnesses begin by emptying their folder, which would delete
   anything that was already there.

   harness_ldw_tree_begin() runs first in main(), before the harness touches
   anything. It
     1. takes a per-harness named mutex (case-folded name, since the folder it
        guards is case-insensitive) and holds it until the process ends, so
        two runs of one harness never overlap;
     2. REFUSES TO RUN if LDW\<basename> already exists, as anything at all
        (folder, file, junction): it prints the path and exits with code 2
        before the harness can empty or overwrite a single file there. A
        leftover from a run that was killed must be removed by hand.
   So everything under LDW\<basename> at exit was made by this run, and the
   exit step -- a normal return, exit(), or an unhandled crash -- removes it:
     - LDW\<basename>: its files and folders, then the folder itself; a
       reparse point (junction, symbolic link) inside it is neither entered
       nor removed;
     - LDW: only if this run created it, it is an ordinary folder (never a
       junction) and it is empty. A pre-existing LDW, including one relocated
       by a junction, is never removed.

   Paths are wide throughout, as the companions' own are, and are derived at
   run time from the Documents folder and this exe's own name, so nothing here
   names a machine-specific folder. ExitProcess() skips the CRT's exit
   handlers, so a harness using this header exits with exit() instead.

   HARNESS_LDW_DOCUMENTS(buffer) may be defined before the include to resolve
   Documents elsewhere; only harness_ldw_tree_harness.c does, to test this
   header against a throwaway folder. Link shell32. Include once per harness. */
#ifndef VVFP_HARNESS_LDW_TREE_H
#define VVFP_HARNESS_LDW_TREE_H

#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#ifndef HARNESS_LDW_DOCUMENTS
#define HARNESS_LDW_DOCUMENTS(buffer) \
    SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_PERSONAL, NULL, 0, (buffer)))
#endif

#define HARNESS_LDW_PATH 1024

static wchar_t harness_ldw_root[HARNESS_LDW_PATH];   /* Documents\LDW */
static wchar_t harness_ldw_tree[HARNESS_LDW_PATH];   /* Documents\LDW\<basename> */
static int harness_ldw_ready;
static int harness_ldw_done;
static int harness_ldw_root_existed;

/* Any entry at all, of any kind: existence is never decided by whether it is
   safe to walk. */
static int harness_ldw_exists(const wchar_t *path) {
    return GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES;
}

/* An ordinary folder: a folder that is not a junction or symbolic link. */
static int harness_ldw_plain_dir(const wchar_t *path) {
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY)
        && !(a & FILE_ATTRIBUTE_REPARSE_POINT);
}

static int harness_ldw_join(wchar_t *out, const wchar_t *folder, const wchar_t *name) {
    int n = _snwprintf(out, HARNESS_LDW_PATH, L"%ls\\%ls", folder, name);
    out[HARNESS_LDW_PATH - 1] = 0;
    return n > 0 && n < HARNESS_LDW_PATH;
}

/* Depth first below a folder this run created. A reparse point is skipped
   outright: neither entered nor removed. */
static void harness_ldw_sweep(const wchar_t *folder) {
    wchar_t pattern[HARNESS_LDW_PATH], path[HARNESS_LDW_PATH];
    WIN32_FIND_DATAW f;
    HANDLE h;
    if (!harness_ldw_join(pattern, folder, L"*")) return;
    h = FindFirstFileW(pattern, &f);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!wcscmp(f.cFileName, L".") || !wcscmp(f.cFileName, L"..")) continue;
        if (f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) continue;
        if (!harness_ldw_join(path, folder, f.cFileName)) continue;
        if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            harness_ldw_sweep(path);
            RemoveDirectoryW(path);
        } else {
            SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL);
            DeleteFileW(path);
        }
    } while (FindNextFileW(h, &f));
    FindClose(h);
}

static void harness_ldw_tree_end(void) {
    if (!harness_ldw_ready || harness_ldw_done) return;
    harness_ldw_done = 1;
    if (harness_ldw_plain_dir(harness_ldw_tree)) {
        harness_ldw_sweep(harness_ldw_tree);
        RemoveDirectoryW(harness_ldw_tree);
    }
    if (!harness_ldw_root_existed && harness_ldw_plain_dir(harness_ldw_root)) {
        RemoveDirectoryW(harness_ldw_root);
    }
}

static LONG WINAPI harness_ldw_on_crash(EXCEPTION_POINTERS *info) {
    (void)info;
    harness_ldw_tree_end();
    return EXCEPTION_CONTINUE_SEARCH;
}

/* Exit before the harness has touched anything. */
static void harness_ldw_refuse(const wchar_t *why, const wchar_t *what) {
    fwprintf(stderr, L"harness: %ls%ls; not running\n", why, what);
    exit(2);
}

/* Call first in main(), before anything can write under Documents\LDW. */
static void harness_ldw_tree_begin(void) {
    wchar_t docs[MAX_PATH], exe[HARNESS_LDW_PATH], name[HARNESS_LDW_PATH + 32];
    wchar_t *base, *dot, *c;
    HANDLE mutex;
    int n;
    if (harness_ldw_ready) return;
    if (!HARNESS_LDW_DOCUMENTS(docs)) harness_ldw_refuse(L"cannot resolve Documents", L"");
    if (GetModuleFileNameW(NULL, exe, HARNESS_LDW_PATH) == 0) {
        harness_ldw_refuse(L"cannot resolve this executable's name", L"");
    }
    exe[HARNESS_LDW_PATH - 1] = 0;
    base = wcsrchr(exe, L'\\');
    base = base != NULL ? base + 1 : exe;
    dot = wcsrchr(base, L'.');
    if (dot != NULL) *dot = 0;
    n = _snwprintf(harness_ldw_root, HARNESS_LDW_PATH, L"%ls\\LDW", docs);
    harness_ldw_root[HARNESS_LDW_PATH - 1] = 0;
    if (*base == 0 || n <= 0 || n >= HARNESS_LDW_PATH
        || !harness_ldw_join(harness_ldw_tree, harness_ldw_root, base)) {
        harness_ldw_refuse(L"cannot form the harness folder path for ", base);
    }

    /* One run of this harness at a time, per user session. Mutex names are
       case-sensitive and the folder is not, so the name is case-folded. The
       handle is never closed: the system releases it when the process ends,
       after the exit handler has swept. An abandoned mutex (a run that was
       killed) still counts as acquired. */
    _snwprintf(name, HARNESS_LDW_PATH + 32, L"Local\\vvfp-harness-ldw-%ls", base);
    name[HARNESS_LDW_PATH + 31] = 0;
    for (c = name + 6; *c; ++c) if (*c == L'\\') *c = L'_';
    {   /* kernel32 only: not every harness links user32 */
        wchar_t folded[HARNESS_LDW_PATH + 32];
        int len = LCMapStringEx(LOCALE_NAME_INVARIANT, LCMAP_LOWERCASE, name + 6, -1,
                                folded, HARNESS_LDW_PATH + 26, NULL, NULL, 0);
        if (len <= 0) harness_ldw_refuse(L"cannot case-fold the name of ", base);
        lstrcpynW(name + 6, folded, HARNESS_LDW_PATH + 26);
    }
    mutex = CreateMutexW(NULL, FALSE, name);
    if (mutex == NULL || WaitForSingleObject(mutex, INFINITE) == WAIT_FAILED) {
        harness_ldw_refuse(L"cannot serialise runs of ", base);
    }

    /* Nothing that is already there may be emptied or overwritten. */
    if (harness_ldw_exists(harness_ldw_tree)) {
        harness_ldw_refuse(L"remove it by hand if it is a leftover -- it already exists: ",
                           harness_ldw_tree);
    }
    harness_ldw_root_existed = harness_ldw_exists(harness_ldw_root);
    harness_ldw_ready = 1;
    atexit(harness_ldw_tree_end);
    SetUnhandledExceptionFilter(harness_ldw_on_crash);
}

#endif
