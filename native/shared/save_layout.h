/* The names of the folders and files the patcher keeps in a save folder, and the move from the
   names older builds used (the owner, 2026-10-09: "rename the patcher-created folders and files to
   accurately explain what they contain. and sort things in separate folders, appropriately named
   too"; src/vv_save_layout.py is the patcher's side and keeps the same table).

       Logs\Deaths                     -> Logs\Deaths and Disappearances
       Logs\Repairs                    -> Logs\Repairs Made
       Data\Log Words                  -> Data\Like and Dislike Words
       Data\Cross-Check                -> Data\Log Checks
       Data\Parentage Records          -> Data\Parents (A New Home)
       Data\Unaccounted Villagers\Virtual Villagers G Village Roster - Save S.dat
                                       -> ...\Virtual Villagers G Villagers at Last Save - Save S.dat
       Data\Village Statistics\Village Roster - Save S.dat
                                       -> ...\Villagers Counted - Save S.dat
       a repair's copy of a file ("<file>.before-...")
                                       -> Data\Copies Made Before Repairs\<the file's own place>

   Each companion moves what it is about to use, just before it uses it: a folder is renamed whole
   (one MoveFile) when the new one does not exist yet, a file when its new name is free.  Nothing is
   ever overwritten, and nothing outside the save folder's Logs and Data folders is touched (the
   Backups folder never).  Header-only and file-static. */
#ifndef VVFP_SAVE_LAYOUT_H
#define VVFP_SAVE_LAYOUT_H

#include <windows.h>
#include <wchar.h>

#define VV_LOGS_DIR L"Virtual Villagers Fun Patcher Logs"
#define VV_DATA_DIR L"Virtual Villagers Fun Patcher Data"
#define VV_DEATHS_LOGS_DIR VV_LOGS_DIR L"\\Deaths and Disappearances"
#define VV_DEATHS_LOGS_OLD VV_LOGS_DIR L"\\Deaths"
#define VV_REPAIRS_DIR VV_LOGS_DIR L"\\Repairs Made"
#define VV_REPAIRS_OLD VV_LOGS_DIR L"\\Repairs"
#define VV_LOG_WORDS_DIR VV_DATA_DIR L"\\Like and Dislike Words"
#define VV_LOG_WORDS_OLD VV_DATA_DIR L"\\Log Words"
#define VV_LOG_CHECKS_DIR VV_DATA_DIR L"\\Log Checks"
#define VV_LOG_CHECKS_OLD VV_DATA_DIR L"\\Cross-Check"
#define VV_PARENTS_VV1_DIR VV_DATA_DIR L"\\Parents (A New Home)"
#define VV_PARENTS_VV1_OLD VV_DATA_DIR L"\\Parentage Records"
#define VV_COPIES_DIR VV_DATA_DIR L"\\Copies Made Before Repairs"

/* "<save folder>\<new>" renamed from "<save folder>\<old>" when only the old one exists.  `save`
   is the save folder itself. */
static void vv_layout_move_dir(const wchar_t *save, const wchar_t *old_rel, const wchar_t *new_rel) {
    wchar_t old_path[MAX_PATH], new_path[MAX_PATH];
    if (save == NULL || save[0] == L'\0'
        || _snwprintf_s(old_path, MAX_PATH, _TRUNCATE, L"%ls\\%ls", save, old_rel) < 0
        || _snwprintf_s(new_path, MAX_PATH, _TRUNCATE, L"%ls\\%ls", save, new_rel) < 0) {
        return;
    }
    if (GetFileAttributesW(new_path) == INVALID_FILE_ATTRIBUTES
        && (GetFileAttributesW(old_path) & FILE_ATTRIBUTE_DIRECTORY) != 0
        && GetFileAttributesW(old_path) != INVALID_FILE_ATTRIBUTES) {
        (void)MoveFileW(old_path, new_path);
    }
}

/* The same for a narrow save-folder path (the companions that build their paths with the ANSI
   API: only the folder's name is non-ASCII-free by the patcher's own naming). */
static void vv_layout_move_dir_a(const char *save, const wchar_t *old_rel, const wchar_t *new_rel) {
    wchar_t wide[MAX_PATH];
    if (save == NULL || MultiByteToWideChar(CP_ACP, 0, save, -1, wide, MAX_PATH) <= 0) {
        return;
    }
    vv_layout_move_dir(wide, old_rel, new_rel);
}

/* A file renamed from `old_path` to `new_path` when only the old one exists. */
static void vv_layout_move_file(const wchar_t *old_path, const wchar_t *new_path) {
    if (GetFileAttributesW(new_path) == INVALID_FILE_ATTRIBUTES
        && GetFileAttributesW(old_path) != INVALID_FILE_ATTRIBUTES) {
        (void)MoveFileW(old_path, new_path);
    }
}

/* Every folder from `path`'s save folder down to `path`'s own folder, created. */
static void vv_layout_make_parents(wchar_t *path) {
    wchar_t *p;
    for (p = path + 3; *p != L'\0'; ++p) {
        if (*p == L'\\') {
            *p = L'\0';
            (void)CreateDirectoryW(path, NULL);
            *p = L'\\';
        }
    }
}

/* Where a repair keeps its copy of `file` (a file under the save folder's Logs or Data folder):
   "<save folder>\Virtual Villagers Fun Patcher Data\Copies Made Before Repairs\<the file's own
   place><suffix>", its folders created.  0 when `file` is not under either folder. */
static int vv_layout_copy_path(const wchar_t *file, const wchar_t *suffix, wchar_t *out, size_t n) {
    const wchar_t *logs = wcsstr(file, L"\\" VV_LOGS_DIR L"\\");
    const wchar_t *data = wcsstr(file, L"\\" VV_DATA_DIR L"\\");
    const wchar_t *at = logs != NULL && (data == NULL || logs < data) ? logs : data;
    int written;
    if (at == NULL) {
        return 0;
    }
    written = _snwprintf_s(out, n, _TRUNCATE, L"%.*ls\\" VV_COPIES_DIR L"%ls%ls", (int)(at - file), file, at,
                           suffix != NULL ? suffix : L"");
    if (written < 0) {
        return 0;
    }
    vv_layout_make_parents(out);
    return 1;
}

#endif
