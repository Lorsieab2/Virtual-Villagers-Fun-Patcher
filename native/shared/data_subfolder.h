/* Each kind of patcher data file in its own folder.
 *
 * The owner: "please put the dat files that the games make into their
 * appropriate folders in the games' save directories."
 *
 * Every per-save data file lives under
 *
 *     <save folder>\Virtual Villagers Fun Patcher Data\<kind>\<name>
 *
 * Village Statistics, Stew Discoveries, Village Elders and Custom Titles were
 * already written that way. The four below used to be written LOOSE in
 * "Virtual Villagers Fun Patcher Data" itself, and now each has its folder:
 *
 *     Village Masks          "Virtual Villagers 1/2 Village Masks - Save S.dat"
 *                            and "Village Masks - Save S.dat" (VV3-VV5)
 *     Graves                 "Virtual Villagers 1/2 Graves - Save S.dat"
 *     Parentage Records      "Virtual Villagers 1 Parentage Records - Save S.dat"
 *     Unaccounted Villagers  "Virtual Villagers N Village Roster - Save S.dat"
 *                            (NOT "Village Roster": Village Statistics keeps a
 *                            different "Village Roster - Save S.dat" of its own)
 *
 * MOVING A FILE AN OLDER BUILD LEFT LOOSE.
 *
 * vv_data_file_path resolves the one path a companion both reads and writes
 * for a file, and moves the loose copy into the folder the first time it is
 * asked. The rules, in the order they are applied:
 *
 *   1. The file is already in the folder: use it. A loose copy beside it is
 *      left exactly where it is, never read, never overwritten, never deleted.
 *   2. Only the loose copy exists: move it with MoveFileEx and NO
 *      MOVEFILE_REPLACE_EXISTING, so a file that appears in the folder at the
 *      same moment is never overwritten. A same-volume rename moves the whole
 *      file or nothing, so an interrupted move cannot leave half a file.
 *   3. The move failed (the file locked, access denied, the folder could not
 *      be made): use the LOOSE copy, for reading and for writing. The
 *      companion keeps working on the file it already had, and its atomic
 *      ".tmp then replace" write lands beside that file. The next launch tries
 *      the move again.
 *
 *      Reading the loose copy and writing a new one in the folder instead was
 *      rejected: a write in the folder before the first read -- an empty table
 *      at village creation -- would shadow the loose records for good, and
 *      rule 1 would then never look at them again.
 *   4. The loose copy's presence cannot be established (GetFileAttributes
 *      fails for a reason other than "not found"): use the loose path. The
 *      sidecar loader then finds it blocked and writes nothing, rather than
 *      settling on an empty file in the folder that would hide it.
 *   5. Neither exists: the folder path, when the folder exists or could be
 *      made; otherwise the loose path, so the data is still kept.
 *
 * Every companion's atomic write derives its ".tmp" from the path returned
 * here, so the temporary file is always in the same folder as the file it
 * replaces.
 *
 * Header-only and static, like sidecar_io.h: each companion DLL carries its
 * own copy, and VV2 (which textually includes VV1's source) gets one through
 * the include guard. Nothing here uses the C runtime.
 */
#ifndef VV_DATA_SUBFOLDER_H
#define VV_DATA_SUBFOLDER_H

#include <windows.h>

#define VV_DATA_FOLDER "Virtual Villagers Fun Patcher Data"

#define VV_DATA_SUB_MASKS       "Village Masks"
#define VV_DATA_SUB_GRAVES      "Graves"
#define VV_DATA_SUB_PARENTAGE   "Parentage Records"
#define VV_DATA_SUB_UNACCOUNTED "Unaccounted Villagers"

/* A unit that only needs the folder names (Start Over) defines
   VV_DATA_SUBFOLDER_NAMES_ONLY, so it carries no unused static code. */
#ifndef VV_DATA_SUBFOLDER_NAMES_ONLY

/* What vv_data_file_path chose. Tests read it; companions only need "not 0". */
#define VV_DATA_PATH_FAILED   0
#define VV_DATA_PATH_FOLDER   1   /* the file in its kind's folder (rules 1, 2, 5) */
#define VV_DATA_PATH_LOOSE    2   /* the loose file in the Data folder (rules 3, 4, 5) */

/* The harness substitutes a failing move here to prove rule 3. Shipped
   builds always call MoveFileExA. */
#ifndef VV_DATA_MOVE_FILE
#define VV_DATA_MOVE_FILE(from, to) MoveFileExA((from), (to), MOVEFILE_WRITE_THROUGH)
#endif

/* What is at PATH: absent, a file, a directory, or unknown (it may exist but
   cannot be examined). GetLastError is read straight after the probe, before
   any other call can change it. */
#define VV_DATA_ABSENT    0
#define VV_DATA_FILE      1
#define VV_DATA_DIRECTORY 2
#define VV_DATA_UNKNOWN   3
static int vv_data_probe(const char *path) {
    DWORD attrs = GetFileAttributesA(path);
    DWORD err;
    if (attrs != INVALID_FILE_ATTRIBUTES) {
        return (attrs & FILE_ATTRIBUTE_DIRECTORY) ? VV_DATA_DIRECTORY : VV_DATA_FILE;
    }
    err = GetLastError();
    return (err == ERROR_FILE_NOT_FOUND || err == ERROR_PATH_NOT_FOUND)
        ? VV_DATA_ABSENT : VV_DATA_UNKNOWN;
}

/* On entry OUT holds "<save folder>\Virtual Villagers Fun Patcher Data" (the
   folder must already exist; every caller creates it first). SUB is one of the
   VV_DATA_SUB_* names and NAME the file's own name. CAP is OUT's size in
   chars; RESERVE is what the caller will still append to the returned path
   (".tmp", ".unreadable-..."), including the NUL.

   On success OUT holds the path to read and write, and the return says which
   one it is. On failure OUT is left holding the Data folder, and the caller
   must not use it as a file path. */
static int vv_data_file_path(char *out, int cap, const char *sub,
                             const char *name, int reserve) {
    char dir[MAX_PATH];
    char folder[MAX_PATH];
    char moved[MAX_PATH];
    char loose[MAX_PATH];
    int folder_ok;
    int loose_state;
    int dir_len;

    if (out == NULL || sub == NULL || name == NULL || sub[0] == '\0'
        || name[0] == '\0' || cap <= 0 || reserve < 1) {
        return VV_DATA_PATH_FAILED;
    }
    dir_len = lstrlenA(out);
    /* The longer of the two paths is the one in the folder; both have to
       fit with the caller's reserve, and in MAX_PATH for the local copies. */
    if (dir_len == 0
        || dir_len + 1 + lstrlenA(sub) + 1 + lstrlenA(name) + reserve > cap
        || dir_len + 1 + lstrlenA(sub) + 1 + lstrlenA(name) + 1 > MAX_PATH) {
        return VV_DATA_PATH_FAILED;
    }
    lstrcpyA(dir, out);
    wsprintfA(folder, "%s\\%s", dir, sub);
    wsprintfA(moved, "%s\\%s\\%s", dir, sub, name);
    wsprintfA(loose, "%s\\%s", dir, name);

    /* Rule 1: already in the folder. Anything that is not "absent" counts --
       a file present but locked is still the one to use, and the sidecar
       loader will find it blocked rather than this choosing a different one. */
    if (vv_data_probe(moved) != VV_DATA_ABSENT) {
        lstrcpyA(out, moved);
        return VV_DATA_PATH_FOLDER;
    }
    CreateDirectoryA(folder, NULL);   /* harmless when it already exists */
    folder_ok = vv_data_probe(folder) == VV_DATA_DIRECTORY;
    loose_state = vv_data_probe(loose);
    if (loose_state == VV_DATA_ABSENT || loose_state == VV_DATA_DIRECTORY) {
        /* Rule 5: nothing loose to move (a directory of that name is not
           ours). */
        lstrcpyA(out, folder_ok ? moved : loose);
        return folder_ok ? VV_DATA_PATH_FOLDER : VV_DATA_PATH_LOOSE;
    }
    if (loose_state == VV_DATA_UNKNOWN) {
        /* Rule 4: it may be there; do not guess it away. */
        lstrcpyA(out, loose);
        return VV_DATA_PATH_LOOSE;
    }
    /* Rule 2: move it. No MOVEFILE_REPLACE_EXISTING, ever. */
    if (folder_ok && VV_DATA_MOVE_FILE(loose, moved)) {
        lstrcpyA(out, moved);
        return VV_DATA_PATH_FOLDER;
    }
    /* Rule 3, unless the failure was a file appearing in the folder at that
       very moment -- then rule 1 applies after all, and the loose copy stays
       put untouched. */
    if (vv_data_probe(moved) != VV_DATA_ABSENT) {
        lstrcpyA(out, moved);
        return VV_DATA_PATH_FOLDER;
    }
    lstrcpyA(out, loose);
    return VV_DATA_PATH_LOOSE;
}

#endif /* VV_DATA_SUBFOLDER_NAMES_ONLY */

#endif /* VV_DATA_SUBFOLDER_H */
