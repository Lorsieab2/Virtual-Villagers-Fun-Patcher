/* See save_folder.h for why this exists and what it guarantees. */
#include "save_folder.h"

#include <shlobj.h>

/* Narrow and wide forms are kept as two functions rather than one generic one
   because the callers are split: the mask sidecars use the ANSI Win32 file
   API, and the log exporters use _wfopen so a player whose Documents path
   contains non-ANSI characters can still write logs. Sharing a single
   implementation through TCHAR would make that choice invisible at the call
   site, which is exactly the kind of ambiguity this header exists to remove. */

int vv_save_folder(char *out, int reserve) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    DWORD n;
    int docs_len;
    int base_len;

    if (out == NULL || reserve < 0) {
        return 0;
    }
    if (!SHGetSpecialFolderPathA(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';                /* basename without ".exe" */
    }
    if (base[0] == '\0') {
        return 0;                   /* no basename: refuse rather than guess */
    }
    docs_len = lstrlenA(docs);
    base_len = lstrlenA(base);
    /* docs + "\LDW\" (5) + basename + whatever the caller will append. */
    if (docs_len + 5 + base_len + reserve >= MAX_PATH) {
        return 0;
    }
    /* Create both levels. CreateDirectoryA on an existing directory fails with
       ERROR_ALREADY_EXISTS, which is not an error for us -- the game itself
       creates these, and we only need them to exist. */
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    return 1;
}

int vv_save_folder_w(wchar_t *out, int reserve) {
    wchar_t docs[MAX_PATH];
    wchar_t exe[MAX_PATH];
    wchar_t *base;
    wchar_t *dot;
    DWORD n;
    int docs_len;
    int base_len;

    if (out == NULL || reserve < 0) {
        return 0;
    }
    if (!SHGetSpecialFolderPathW(NULL, docs, CSIDL_PERSONAL, FALSE)) {
        return 0;
    }
    n = GetModuleFileNameW(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    base = wcsrchr(exe, L'\\');
    base = base ? base + 1 : exe;
    dot = wcsrchr(base, L'.');
    if (dot != NULL) {
        *dot = L'\0';
    }
    if (base[0] == L'\0') {
        return 0;
    }
    docs_len = lstrlenW(docs);
    base_len = lstrlenW(base);
    if (docs_len + 5 + base_len + reserve >= MAX_PATH) {
        return 0;
    }
    wsprintfW(out, L"%ls\\LDW", docs);
    CreateDirectoryW(out, NULL);
    wsprintfW(out, L"%ls\\LDW\\%ls", docs, base);
    CreateDirectoryW(out, NULL);
    return 1;
}
