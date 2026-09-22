/* See save_folder.h for why this exists and what it guarantees. */
#include "save_folder.h"

#include <shlobj.h>
#include <stdio.h>
#include <string.h>

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
    docs_len = (int)strlen(docs);
    base_len = (int)strlen(base);
    /* docs + "\LDW\" (5) + basename + whatever the caller will append. */
    if (docs_len + 5 + base_len + reserve >= MAX_PATH) {
        return 0;
    }
    /* Create both levels. CreateDirectoryA on an existing directory fails with
       ERROR_ALREADY_EXISTS, which is not an error for us -- the game itself
       creates these, and we only need them to exist. */
    _snprintf(out, MAX_PATH,"%s\\LDW", docs);
    out[MAX_PATH - 1] = 0;
    CreateDirectoryA(out, NULL);
    _snprintf(out, MAX_PATH,"%s\\LDW\\%s", docs, base);
    out[MAX_PATH - 1] = 0;
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
    docs_len = (int)wcslen(docs);
    base_len = (int)wcslen(base);
    if (docs_len + 5 + base_len + reserve >= MAX_PATH) {
        return 0;
    }
    _snwprintf(out, MAX_PATH,L"%ls\\LDW", docs);
    out[MAX_PATH - 1] = 0;
    CreateDirectoryW(out, NULL);
    _snwprintf(out, MAX_PATH,L"%ls\\LDW\\%ls", docs, base);
    out[MAX_PATH - 1] = 0;
    CreateDirectoryW(out, NULL);
    return 1;
}

/* Create "<save folder>\<sub>" one component at a time. */
int vv_save_subfolder_w(wchar_t *out, const wchar_t *sub, int reserve) {
    wchar_t folder[MAX_PATH];
    wchar_t built[MAX_PATH];
    const wchar_t *p;
    int len;
    if (out == NULL || sub == NULL || sub[0] == L'\0' || reserve < 0) {
        return 0;
    }
    /* The base must leave room for the tail AND the caller's own append. */
    if (!vv_save_folder_w(folder, (int)wcslen(sub) + 1 + reserve)) {
        return 0;
    }
    /* Walk `sub`, creating each component as its trailing backslash (or the
       end) is reached. CreateDirectoryW on an existing directory fails with
       ERROR_ALREADY_EXISTS, which is not an error for us. */
    /* Seed with the separator: `sub` is JOINED to the save folder, never
       glued onto its name. Without this the first component was created
       as "<save folder><sub>" -- a mis-named sibling -- and the reset
       harness passed because its narrow twin made the same mistake. */
    _snwprintf(built, MAX_PATH, L"%ls\\", folder);
    built[MAX_PATH - 1] = 0;
    len = (int)wcslen(built);
    for (p = sub; ; ++p) {
        if (*p == L'\\' || *p == L'\0') {
            CreateDirectoryW(built, NULL);
            if (*p == L'\0') {
                break;
            }
        }
        if (len + 1 >= MAX_PATH) {
            return 0;
        }
        built[len++] = (*p == L'\\') ? L'\\' : *p;
        built[len] = 0;
    }
    /* Only now is `out` written: every earlier return leaves it untouched. */
    _snwprintf(out, MAX_PATH, L"%ls", built);
    out[MAX_PATH - 1] = 0;
    return 1;
}

int vv_save_subfolder(char *out, const char *sub, int reserve) {
    char folder[MAX_PATH];
    char built[MAX_PATH];
    const char *p;
    int len;
    if (out == NULL || sub == NULL || sub[0] == '\0' || reserve < 0) {
        return 0;
    }
    if (!vv_save_folder(folder, (int)strlen(sub) + 1 + reserve)) {
        return 0;
    }
    /* Seeded with the separator, as in the wide form. */
    _snprintf(built, MAX_PATH, "%s\\", folder);
    built[MAX_PATH - 1] = 0;
    len = (int)strlen(built);
    for (p = sub; ; ++p) {
        if (*p == '\\' || *p == '\0') {
            CreateDirectoryA(built, NULL);
            if (*p == '\0') {
                break;
            }
        }
        if (len + 1 >= MAX_PATH) {
            return 0;
        }
        built[len++] = *p;
        built[len] = 0;
    }
    _snprintf(out, MAX_PATH, "%s", built);
    out[MAX_PATH - 1] = 0;
    return 1;
}
