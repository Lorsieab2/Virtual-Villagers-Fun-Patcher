/* Leave the player's Documents\LDW exactly as the harness found it.

   A harness that drives a shipped companion makes that companion write where
   it would in a game: Documents\LDW\<this exe's basename>\..., i.e. inside the
   real LDW save folder. The harnesses deleted their own files, but folders the
   companion created on the way (log and data folders, the per-exe folder, and
   LDW itself on a machine that had none) were left behind after every run.

   harness_ldw_tree_begin() runs first in main(). It
     1. takes a per-harness named mutex and holds it until the process ends,
        so two runs of the same harness never overlap: everything that appears
        under LDW\<basename> while it is held was made by THIS run;
     2. records whether LDW and LDW\<basename> exist (any kind of entry,
        including a junction or symbolic link), and, when the per-exe folder
        already exists, every entry below it.
   At process exit -- a normal return, exit(), or an unhandled crash -- it
   removes what this run created and nothing else:
     - nothing that existed before the run is ever removed, file or folder;
     - a reparse point (junction, symbolic link) is never removed and never
       entered, wherever it is; LDW relocated by a junction stays connected;
     - LDW\<basename> new: its files and folders are removed, then the folder;
     - LDW\<basename> already there: only new folders, and only while empty;
       no file below it is touched, new or old;
     - LDW new and now an empty ordinary folder: removed.

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
#define HARNESS_LDW_MAX_ENTRIES 512

static wchar_t harness_ldw_root[HARNESS_LDW_PATH];   /* Documents\LDW */
static wchar_t harness_ldw_tree[HARNESS_LDW_PATH];   /* Documents\LDW\<basename> */
static int harness_ldw_ready;
static int harness_ldw_done;
static int harness_ldw_root_existed;
static int harness_ldw_tree_existed;
static int harness_ldw_kept_overflow;   /* too many to record: remove nothing below */
static wchar_t (*harness_ldw_kept)[HARNESS_LDW_PATH];
static int harness_ldw_kept_count;

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

/* Every entry below `folder`, files and folders alike, never entering a
   reparse point. */
static void harness_ldw_record(const wchar_t *folder) {
    wchar_t pattern[HARNESS_LDW_PATH], path[HARNESS_LDW_PATH];
    WIN32_FIND_DATAW f;
    HANDLE h;
    if (!harness_ldw_join(pattern, folder, L"*")) { harness_ldw_kept_overflow = 1; return; }
    h = FindFirstFileW(pattern, &f);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        if (!wcscmp(f.cFileName, L".") || !wcscmp(f.cFileName, L"..")) continue;
        if (!harness_ldw_join(path, folder, f.cFileName)
            || harness_ldw_kept_count >= HARNESS_LDW_MAX_ENTRIES) {
            harness_ldw_kept_overflow = 1;
            continue;
        }
        lstrcpynW(harness_ldw_kept[harness_ldw_kept_count++], path, HARNESS_LDW_PATH);
        if ((f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            && !(f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
            harness_ldw_record(path);
        }
    } while (FindNextFileW(h, &f));
    FindClose(h);
}

static int harness_ldw_was_kept(const wchar_t *path) {
    int i;
    for (i = 0; i < harness_ldw_kept_count; ++i) {
        if (lstrcmpiW(harness_ldw_kept[i], path) == 0) return 1;
    }
    return 0;
}

/* Depth first below `folder`. A reparse point is skipped outright: neither
   entered nor removed. `owned`: the folder did not exist before this run and
   no other run of this harness can have written to it (the mutex), so its
   files go too. Otherwise only folders that are not on the start-up list go,
   and RemoveDirectory only succeeds on an empty one. */
static void harness_ldw_sweep(const wchar_t *folder, int owned) {
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
        if (!owned && harness_ldw_was_kept(path)) {
            if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) harness_ldw_sweep(path, 0);
            continue;
        }
        if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            harness_ldw_sweep(path, owned);
            RemoveDirectoryW(path);
        } else if (owned) {
            SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL);
            DeleteFileW(path);
        }
    } while (FindNextFileW(h, &f));
    FindClose(h);
}

static void harness_ldw_tree_end(void) {
    if (!harness_ldw_ready || harness_ldw_done) return;
    harness_ldw_done = 1;
    /* Only ever below an ordinary LDW: a junction LDW is never entered. */
    if (!harness_ldw_plain_dir(harness_ldw_root)) return;
    if (!harness_ldw_tree_existed) {
        if (harness_ldw_plain_dir(harness_ldw_tree)) {
            harness_ldw_sweep(harness_ldw_tree, 1);
            RemoveDirectoryW(harness_ldw_tree);
        }
    } else if (harness_ldw_plain_dir(harness_ldw_tree) && !harness_ldw_kept_overflow) {
        harness_ldw_sweep(harness_ldw_tree, 0);
    }
    if (!harness_ldw_root_existed) RemoveDirectoryW(harness_ldw_root);
}

static LONG WINAPI harness_ldw_on_crash(EXCEPTION_POINTERS *info) {
    (void)info;
    harness_ldw_tree_end();
    return EXCEPTION_CONTINUE_SEARCH;
}

/* Call first in main(), before anything can write under Documents\LDW. */
static void harness_ldw_tree_begin(void) {
    wchar_t docs[MAX_PATH], exe[HARNESS_LDW_PATH], name[HARNESS_LDW_PATH + 32];
    wchar_t *base, *dot, *c;
    HANDLE mutex;
    if (harness_ldw_ready) return;
    if (!HARNESS_LDW_DOCUMENTS(docs)) return;
    if (GetModuleFileNameW(NULL, exe, HARNESS_LDW_PATH) == 0) return;
    exe[HARNESS_LDW_PATH - 1] = 0;
    base = wcsrchr(exe, L'\\');
    base = base != NULL ? base + 1 : exe;
    dot = wcsrchr(base, L'.');
    if (dot != NULL) *dot = 0;
    if (*base == 0) return;
    if (_snwprintf(harness_ldw_root, HARNESS_LDW_PATH, L"%ls\\LDW", docs) <= 0) return;
    harness_ldw_root[HARNESS_LDW_PATH - 1] = 0;
    if (!harness_ldw_join(harness_ldw_tree, harness_ldw_root, base)) return;

    /* One run of this harness at a time, per user session. The handle is
       never closed: the system releases it when the process ends, after the
       exit handler has swept. An abandoned mutex (a run that was killed)
       still counts as acquired. */
    _snwprintf(name, HARNESS_LDW_PATH + 32, L"Local\\vvfp-harness-ldw-%ls", base);
    name[HARNESS_LDW_PATH + 31] = 0;
    for (c = name + 6; *c; ++c) if (*c == L'\\') *c = L'_';
    mutex = CreateMutexW(NULL, FALSE, name);
    if (mutex == NULL) return;   /* no exclusion: clean up nothing */
    if (WaitForSingleObject(mutex, INFINITE) == WAIT_FAILED) return;

    harness_ldw_root_existed = harness_ldw_exists(harness_ldw_root);
    harness_ldw_tree_existed = harness_ldw_exists(harness_ldw_tree);
    if (harness_ldw_tree_existed && harness_ldw_plain_dir(harness_ldw_tree)
        && harness_ldw_plain_dir(harness_ldw_root)) {
        harness_ldw_kept = calloc(HARNESS_LDW_MAX_ENTRIES, sizeof *harness_ldw_kept);
        if (harness_ldw_kept == NULL) harness_ldw_kept_overflow = 1;
        else harness_ldw_record(harness_ldw_tree);
    }
    harness_ldw_ready = 1;
    atexit(harness_ldw_tree_end);
    SetUnhandledExceptionFilter(harness_ldw_on_crash);
}

#endif
