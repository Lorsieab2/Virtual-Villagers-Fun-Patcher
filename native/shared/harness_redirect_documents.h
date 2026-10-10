/* Point a loaded companion's "Documents" at a throwaway folder.

   A harness that LoadLibrary()s a shipped companion makes it write where it
   would in a game: <Documents>\LDW\<exe basename>\...  -- the player's real
   save folder.  harness_ldw_tree.h removes what the run made, but only when
   the run ends: a harness killed part-way (a cancelled test run, a hung
   build) leaves its folders in the real LDW, and the next run refuses to
   start until they are removed by hand.

   harness_redirect_documents(dll) removes the cause instead.  It patches the
   companion's own import table so that its SHGetFolderPathA/W and
   SHGetSpecialFolderPathA/W answer CSIDL_PERSONAL with a fresh folder under
   the system temp folder (every other CSIDL goes to the real function).
   Whatever the companion writes then lands in that folder, which the harness
   removes at exit -- and if the harness is killed, the only thing left is an
   unreferenced folder in %TEMP%.  The real Documents\LDW is never touched.

   harness_redirect_documents_path() is the redirected "Documents" for the
   harness's own lookups.  Include once per harness; link shell32. */
#ifndef VVFP_HARNESS_REDIRECT_DOCUMENTS_H
#define VVFP_HARNESS_REDIRECT_DOCUMENTS_H

#include <windows.h>
#include <shlobj.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

static char harness_docs_a[MAX_PATH];
static wchar_t harness_docs_w[MAX_PATH];
static int harness_docs_made;

static HRESULT (WINAPI *harness_real_folder_a)(HWND, int, HANDLE, DWORD, LPSTR);
static HRESULT (WINAPI *harness_real_folder_w)(HWND, int, HANDLE, DWORD, LPWSTR);
static BOOL (WINAPI *harness_real_special_a)(HWND, LPSTR, int, BOOL);
static BOOL (WINAPI *harness_real_special_w)(HWND, LPWSTR, int, BOOL);

static const char *harness_redirect_documents_path(void) {
    return harness_docs_a;
}

/* The folder and everything in it (no junction is entered). */
static void harness_docs_remove(const wchar_t *folder) {
    wchar_t pattern[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAW f;
    HANDLE h;
    _snwprintf(pattern, MAX_PATH, L"%ls\\*", folder);
    pattern[MAX_PATH - 1] = 0;
    h = FindFirstFileW(pattern, &f);
    if (h != INVALID_HANDLE_VALUE) {
        do {
            if (wcscmp(f.cFileName, L".") == 0 || wcscmp(f.cFileName, L"..") == 0) continue;
            _snwprintf(path, MAX_PATH, L"%ls\\%ls", folder, f.cFileName);
            path[MAX_PATH - 1] = 0;
            if (f.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) {
                if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) RemoveDirectoryW(path);
                else DeleteFileW(path);
            } else if (f.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                harness_docs_remove(path);
            } else {
                SetFileAttributesW(path, FILE_ATTRIBUTE_NORMAL);
                DeleteFileW(path);
            }
        } while (FindNextFileW(h, &f));
        FindClose(h);
    }
    RemoveDirectoryW(folder);
}

static void harness_docs_cleanup(void) {
    if (harness_docs_made) {
        harness_docs_remove(harness_docs_w);
        harness_docs_made = 0;
    }
}

static HRESULT WINAPI harness_folder_a(HWND h, int csidl, HANDLE t, DWORD f, LPSTR out) {
    if ((csidl & 0xff) == CSIDL_PERSONAL) {
        lstrcpynA(out, harness_docs_a, MAX_PATH);
        return S_OK;
    }
    return harness_real_folder_a(h, csidl, t, f, out);
}
static HRESULT WINAPI harness_folder_w(HWND h, int csidl, HANDLE t, DWORD f, LPWSTR out) {
    if ((csidl & 0xff) == CSIDL_PERSONAL) {
        lstrcpynW(out, harness_docs_w, MAX_PATH);
        return S_OK;
    }
    return harness_real_folder_w(h, csidl, t, f, out);
}
static BOOL WINAPI harness_special_a(HWND h, LPSTR out, int csidl, BOOL create) {
    if ((csidl & 0xff) == CSIDL_PERSONAL) {
        lstrcpynA(out, harness_docs_a, MAX_PATH);
        return TRUE;
    }
    return harness_real_special_a(h, out, csidl, create);
}
static BOOL WINAPI harness_special_w(HWND h, LPWSTR out, int csidl, BOOL create) {
    if ((csidl & 0xff) == CSIDL_PERSONAL) {
        lstrcpynW(out, harness_docs_w, MAX_PATH);
        return TRUE;
    }
    return harness_real_special_w(h, out, csidl, create);
}

/* Replace one named import of `module` from shell32; the original goes to *real. */
static int harness_patch_import(HMODULE module, const char *name, void *replacement, void **real) {
    BYTE *base = (BYTE *)module;
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt;
    IMAGE_DATA_DIRECTORY dir;
    IMAGE_IMPORT_DESCRIPTOR *imp;
    int patched = 0;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    nt = (IMAGE_NT_HEADERS *)(base + dos->e_lfanew);
    dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (dir.VirtualAddress == 0) return 0;
    for (imp = (IMAGE_IMPORT_DESCRIPTOR *)(base + dir.VirtualAddress); imp->Name != 0; ++imp) {
        IMAGE_THUNK_DATA *names, *funcs;
        if (_stricmp((const char *)(base + imp->Name), "shell32.dll") != 0) continue;
        names = (IMAGE_THUNK_DATA *)(base + (imp->OriginalFirstThunk ? imp->OriginalFirstThunk : imp->FirstThunk));
        funcs = (IMAGE_THUNK_DATA *)(base + imp->FirstThunk);
        for (; names->u1.AddressOfData != 0; ++names, ++funcs) {
            IMAGE_IMPORT_BY_NAME *by_name;
            DWORD old;
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            by_name = (IMAGE_IMPORT_BY_NAME *)(base + names->u1.AddressOfData);
            if (strcmp((const char *)by_name->Name, name) != 0) continue;
            if (!VirtualProtect(&funcs->u1.Function, sizeof(funcs->u1.Function), PAGE_READWRITE, &old)) return 0;
            if (*real == NULL) *real = (void *)funcs->u1.Function;
            funcs->u1.Function = (ULONG_PTR)replacement;
            VirtualProtect(&funcs->u1.Function, sizeof(funcs->u1.Function), old, &old);
            ++patched;
        }
    }
    return patched;
}

/* Make the throwaway "Documents" and point `dll`'s shell32 imports at it.
   Returns 0 when the companion could not be redirected (then the harness
   must not run: it would write into the real Documents). */
static int harness_redirect_documents(HMODULE dll) {
    char temp[MAX_PATH];
    int found = 0;
    if (!harness_docs_made) {
        if (GetTempPathA(MAX_PATH, temp) == 0) return 0;
        _snprintf(harness_docs_a, MAX_PATH, "%svvfp_harness_docs_%lu_%lu", temp, GetCurrentProcessId(),
                  GetTickCount());
        harness_docs_a[MAX_PATH - 1] = '\0';
        if (MultiByteToWideChar(CP_ACP, 0, harness_docs_a, -1, harness_docs_w, MAX_PATH) == 0) return 0;
        if (!CreateDirectoryA(harness_docs_a, NULL)) return 0;
        harness_docs_made = 1;
        atexit(harness_docs_cleanup);
    }
    found += harness_patch_import(dll, "SHGetFolderPathA", (void *)harness_folder_a, (void **)&harness_real_folder_a);
    found += harness_patch_import(dll, "SHGetFolderPathW", (void *)harness_folder_w, (void **)&harness_real_folder_w);
    found += harness_patch_import(dll, "SHGetSpecialFolderPathA", (void *)harness_special_a,
                                  (void **)&harness_real_special_a);
    found += harness_patch_import(dll, "SHGetSpecialFolderPathW", (void *)harness_special_w,
                                  (void **)&harness_real_special_w);
    return found;
}

#endif /* VVFP_HARNESS_REDIRECT_DOCUMENTS_H */
