/* The names of the folders and files the patcher keeps in a save folder, and the names older
   builds used (the owner, 2026-10-09: "rename the patcher-created folders and files to accurately
   explain what they contain. and sort things in separate folders, appropriately named too"; then,
   the same day: "from now on use the new renaming, but it also recognizes the old renaming").
   src/vv_save_layout.py is the patcher's side and keeps the same table.

       new name                               older builds' name
       Logs\Deaths and Disappearances         Logs\Deaths
       Logs\Repairs Made                      Logs\Repairs
       Data\Like and Dislike Words            Data\Log Words
       Data\Log Checks                        Data\Cross-Check
       Data\Parents (A New Home)              Data\Parentage Records
       Data\Unaccounted Villagers\Virtual Villagers G Villagers at Last Save - Save S.dat
                                              ...\Virtual Villagers G Village Roster - Save S.dat
       Data\Village Statistics\Villagers Counted - Save S.dat
                                              ...\Village Roster - Save S.dat
       Data\Copies Made Before Repairs\<the file's own place>   (new copies only; older ones stay
                                              beside their files, and nothing reads them)

   NOTHING IS EVER MOVED OR RENAMED.  A v1.35.64 preview moved the files to their new names while
   A New Home was still patched by v1.35.63, whose companion then found "Parentage Records" empty
   and offered to "fill in" 69 villagers' parents.  So every file stays where it is, and each
   reader and writer picks, at the point of use:

     - only the new name exists: the new one;
     - only the old name exists: the old one, for reading AND writing;
     - neither: the new name (created only when something is written);
     - both (an older and a newer build both played the village):
         a whole file (the parents, the two rosters, a Log Checks marker): the one written last,
           read and written from then on; the other is never touched (vv_layout_pick_file);
         a folder of logs appended to (Deaths, Repairs): both read, a record kept in both counted
           once, and new records written in the new folder (vv_layout_pick_dir says "new");
         the Like and Dislike Words: both read, the smaller boundary of each log file taken
           (log_words.h);
         a Repair Saves & Logs approval: acted on under neither name (crosscheck_bridge.h).

   Nothing here creates a folder to look in it, and a folder or file that cannot be examined is
   never taken for missing when the other name has data.  Header-only and file-static. */
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

/* The same names for the companions that build their paths with the ANSI API. */
#define VV_LOGS_DIR_A "Virtual Villagers Fun Patcher Logs"
#define VV_DATA_DIR_A "Virtual Villagers Fun Patcher Data"
#define VV_REPAIRS_DIR_A VV_LOGS_DIR_A "\\Repairs Made"
#define VV_REPAIRS_OLD_A VV_LOGS_DIR_A "\\Repairs"
#define VV_LOG_WORDS_DIR_A VV_DATA_DIR_A "\\Like and Dislike Words"
#define VV_LOG_WORDS_OLD_A VV_DATA_DIR_A "\\Log Words"
#define VV_LOG_CHECKS_DIR_A VV_DATA_DIR_A "\\Log Checks"
#define VV_LOG_CHECKS_OLD_A VV_DATA_DIR_A "\\Cross-Check"

/* What is at a path: 0 certainly absent ("not found"), 1 a file, 2 a folder, 3 something that
   cannot be examined (it may well be there). */
#define VV_LAYOUT_ABSENT 0
#define VV_LAYOUT_FILE 1
#define VV_LAYOUT_DIR 2
#define VV_LAYOUT_UNKNOWN 3
static int vv_layout_probe_w(const wchar_t *path, FILETIME *written) {
    WIN32_FILE_ATTRIBUTE_DATA info;
    DWORD error;
    if (GetFileAttributesExW(path, GetFileExInfoStandard, &info)) {
        if (written != NULL) {
            *written = info.ftLastWriteTime;
        }
        return (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0 ? VV_LAYOUT_DIR : VV_LAYOUT_FILE;
    }
    error = GetLastError();
    return error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ? VV_LAYOUT_ABSENT : VV_LAYOUT_UNKNOWN;
}

/* A whole file kept under two names: 1 when the OLD path is the one to read and write, 0 for the
   new one.  Only the old one there (or the new one certainly absent and the old one there but
   unexaminable): the old.  Both there: the one written last (a tie, or a time that cannot be read:
   the new).  Otherwise the new. */
static int vv_layout_pick_file_w(const wchar_t *old_path, const wchar_t *new_path) {
    FILETIME old_time = {0, 0}, new_time = {0, 0};
    int old_state = vv_layout_probe_w(old_path, &old_time);
    int new_state = vv_layout_probe_w(new_path, &new_time);
    if (old_state == VV_LAYOUT_ABSENT || old_state == VV_LAYOUT_DIR) {
        return 0;
    }
    if (new_state == VV_LAYOUT_ABSENT || new_state == VV_LAYOUT_DIR) {
        return 1;
    }
    return old_state == VV_LAYOUT_FILE && new_state == VV_LAYOUT_FILE && CompareFileTime(&old_time, &new_time) > 0;
}

/* A folder kept under two names, for writing into: 1 for the OLD folder, which is used only while
   it is there and the new one is certainly not (an older build's folder is kept, never emptied
   into a new one); 0 for the new one. */
static int vv_layout_pick_dir_w(const wchar_t *old_path, const wchar_t *new_path) {
    int old_state = vv_layout_probe_w(old_path, NULL);
    return (old_state == VV_LAYOUT_DIR || old_state == VV_LAYOUT_UNKNOWN)
           && vv_layout_probe_w(new_path, NULL) == VV_LAYOUT_ABSENT;
}

static int vv_layout_widen(const char *narrow, wchar_t *wide) {
    return narrow != NULL && MultiByteToWideChar(CP_ACP, 0, narrow, -1, wide, MAX_PATH) > 0;
}

static int vv_layout_pick_file_a(const char *old_path, const char *new_path) {
    wchar_t old_wide[MAX_PATH], new_wide[MAX_PATH];
    return vv_layout_widen(old_path, old_wide) && vv_layout_widen(new_path, new_wide)
           && vv_layout_pick_file_w(old_wide, new_wide);
}

static int vv_layout_pick_dir_a(const char *old_path, const char *new_path) {
    wchar_t old_wide[MAX_PATH], new_wide[MAX_PATH];
    return vv_layout_widen(old_path, old_wide) && vv_layout_widen(new_path, new_wide)
           && vv_layout_pick_dir_w(old_wide, new_wide);
}

/* The folder name (relative to the save folder `save`) to write into: `old_rel` while only it
   exists, else `new_rel`. */
static const wchar_t *vv_layout_dir_rel_w(const wchar_t *save, const wchar_t *old_rel, const wchar_t *new_rel) {
    wchar_t old_path[MAX_PATH], new_path[MAX_PATH];
    if (save == NULL || save[0] == L'\0'
        || lstrlenW(save) + 1 + lstrlenW(old_rel) >= MAX_PATH || lstrlenW(save) + 1 + lstrlenW(new_rel) >= MAX_PATH) {
        return new_rel;
    }
    /* kernel32 only: some companions have no C runtime, some no user32. */
    lstrcpyW(old_path, save);
    lstrcatW(old_path, L"\\");
    lstrcatW(old_path, old_rel);
    lstrcpyW(new_path, save);
    lstrcatW(new_path, L"\\");
    lstrcatW(new_path, new_rel);
    return vv_layout_pick_dir_w(old_path, new_path) ? old_rel : new_rel;
}

static const char *vv_layout_dir_rel_a(const char *save, const char *old_rel, const char *new_rel) {
    char old_path[MAX_PATH], new_path[MAX_PATH];
    if (save == NULL || save[0] == '\0'
        || lstrlenA(save) + 1 + lstrlenA(old_rel) >= MAX_PATH || lstrlenA(save) + 1 + lstrlenA(new_rel) >= MAX_PATH) {
        return new_rel;
    }
    lstrcpyA(old_path, save);
    lstrcatA(old_path, "\\");
    lstrcatA(old_path, old_rel);
    lstrcpyA(new_path, save);
    lstrcatA(new_path, "\\");
    lstrcatA(new_path, new_rel);
    return vv_layout_pick_dir_a(old_path, new_path) ? old_rel : new_rel;
}

/* The "Repair <n>" records an older build's "Repairs" folder already holds in the Repairs log file
   numbered `number`, when `folder` is the new "...\Repairs Made" folder and the older one is there
   too (both an older and a newer build repaired the village).  A new record's number continues
   after them, so "Repair 1" never comes again beside the older folder's own (the owner's A New
   Home log, 2026-10-10: "Repairs\...Log 1.txt" held Repair 1-11 and "Repairs Made\...Log 1.txt"
   began again at Repair 1).  Read only; kernel32 only.  0 when there is no such file. */
static int vv_layout_older_repairs(const char *folder, int game, int number) {
    static const char made[] = "\\Repairs Made";
    char path[MAX_PATH];
    int len = lstrlenA(folder);
    int made_len = (int)sizeof made - 1;
    HANDLE file;
    DWORD size, got = 0;
    char *text;
    int count = 0;
    DWORD i;
    if (len <= made_len || lstrcmpiA(folder + len - made_len, made) != 0
        || len - made_len + 64 >= MAX_PATH) {
        return 0;
    }
    if (game < 1 || game > 9 || number < 1 || number > 99999) {
        return 0;
    }
    lstrcpynA(path, folder, len - made_len + 1);
    lstrcatA(path, "\\Repairs\\Virtual Villagers ");
    {
        char digits[8];
        int n = number, k = 0, m;
        char g[2] = { (char)('0' + game), '\0' };
        lstrcatA(path, g);
        lstrcatA(path, " Repairs Log ");
        do { digits[k++] = (char)('0' + n % 10); n /= 10; } while (n > 0);
        for (m = 0; m < k / 2; ++m) { char t = digits[m]; digits[m] = digits[k - 1 - m]; digits[k - 1 - m] = t; }
        digits[k] = '\0';
        lstrcatA(path, digits);
        lstrcatA(path, ".txt");
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    size = GetFileSize(file, NULL);
    if (size == INVALID_FILE_SIZE || size > 64u * 1024u * 1024u) {
        CloseHandle(file);
        return 0;
    }
    text = (char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)size + 1);
    if (text == NULL) {
        CloseHandle(file);
        return 0;
    }
    if (ReadFile(file, text, size, &got, NULL)) {
        for (i = 0; i < got; ++i) {
            if ((i == 0 || text[i - 1] == '\n') && i + 8 <= got && text[i] == 'R' && text[i + 1] == 'e'
                && text[i + 2] == 'p' && text[i + 3] == 'a' && text[i + 4] == 'i' && text[i + 5] == 'r'
                && text[i + 6] == ' ' && text[i + 7] >= '0' && text[i + 7] <= '9') {
                ++count;
            }
        }
    }
    HeapFree(GetProcessHeap(), 0, text);
    CloseHandle(file);
    return count;
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
