/* Exercise vv_reset_slot_state against real files on disk.
 *
 * The properties that matter here cannot be established by reading the source:
 * that the right files are deleted, that neighbouring slots and the game's own
 * saves survive, and that an unresolvable path deletes nothing. So this creates
 * actual files, runs the real reset, and checks what is left.
 *
 * It runs as a 32-bit console program because that is what the companions are.
 * The save folder is resolved from the exe basename, so the harness copies
 * itself nowhere and instead reports which folder it resolved -- the caller
 * points it at a throwaway Documents via the usual environment.
 */
#include <stdio.h>
#include <windows.h>

#include "save_folder.h"
#include "save_reset.h"
#include "harness_ldw_tree.h"

/* the reset's internal guards, exposed by VV_RESET_TESTABLE */
int delete_if_present(const char *path);
int delete_if_present_w(const wchar_t *path);
int vv_save_folder_w(wchar_t *out, int reserve);
extern int vv_reset_refused_paths;

static int failures = 0;

static void check(int condition, const char *what) {
    printf("  [%s] %s\n", condition ? "PASS" : "FAIL", what);
    if (!condition) {
        ++failures;
    }
}

static void touch(const char *path) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD written = 0;
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, "x", 1, &written, NULL);
        CloseHandle(h);
    }
}

static void write_text(const char *path, const char *text) {
    HANDLE h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                           FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD written = 0;
    if (h != INVALID_HANDLE_VALUE) {
        WriteFile(h, text, (DWORD)lstrlenA(text), &written, NULL);
        CloseHandle(h);
    }
}

static int exists(const char *path) {
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

/* ---- START OVER WIPES THE WHOLE SAVE (the owner, v1.35.79) -------------------------------------- */
extern int vv_reset_wipe_kept_unclear;
extern int vv_reset_wipe_not_deleted;
extern int vv_reset_wipe_links;

/* `folder`\`rel`, its folders made, holding `text`. */
static void put(const char *folder, const char *rel, const char *text) {
    char path[MAX_PATH];
    char *p;
    wsprintfA(path, "%s\\%s", folder, rel);
    for (p = path + 3; *p != '\0'; ++p) {
        if (*p == '\\') {
            *p = '\0';
            CreateDirectoryA(path, NULL);
            *p = '\\';
        }
    }
    write_text(path, text);
}

static int there(const char *folder, const char *rel) {
    char path[MAX_PATH];
    wsprintfA(path, "%s\\%s", folder, rel);
    return exists(path);
}

/* The whole of `folder`\`rel` removed (the harness's own fixtures; no junction is entered). */
static void clear(const char *folder, const char *rel) {
    char path[MAX_PATH];
    wchar_t wide[MAX_PATH];
    wsprintfA(path, "%s\\%s", folder, rel);
    if (MultiByteToWideChar(CP_ACP, 0, path, -1, wide, MAX_PATH) > 0) {
        harness_docs_remove(wide);
    }
}

/* Does the file `folder`\`rel` contain `needle`? */
static int holds(const char *folder, const char *rel, const char *needle) {
    char path[MAX_PATH];
    static char text[65536 + 1024];
    DWORD got = 0;
    HANDLE h;
    wsprintfA(path, "%s\\%s", folder, rel);
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ReadFile(h, text, (DWORD)sizeof text - 1, &got, NULL);
    CloseHandle(h);
    text[got] = '\0';
    return strstr(text, needle) != NULL;
}

/* The files under `dir` (no junction is entered). */
static int files_in(const char *dir) {
    char filter[MAX_PATH], path[MAX_PATH];
    WIN32_FIND_DATAA found;
    HANDLE search;
    int count = 0;
    wsprintfA(filter, "%s\\*", dir);
    search = FindFirstFileA(filter, &found);
    if (search == INVALID_HANDLE_VALUE) {
        return 0;
    }
    do {
        if (lstrcmpA(found.cFileName, ".") == 0 || lstrcmpA(found.cFileName, "..") == 0) {
            continue;
        }
        wsprintfA(path, "%s\\%s", dir, found.cFileName);
        if (found.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) {
            ++count;
        } else if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            count += files_in(path);
        } else {
            ++count;
        }
    } while (FindNextFileA(search, &found));
    FindClose(search);
    return count;
}

/* `folder`\`rel` is there, as a folder holding no file at all. */
static int emptied(const char *folder, const char *rel) {
    char path[MAX_PATH];
    DWORD attributes;
    wsprintfA(path, "%s\\%s", folder, rel);
    attributes = GetFileAttributesA(path);
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) && files_in(path) == 0;
}

static void clear_all(const char *folder) {
    clear(folder, "Virtual Villagers Fun Patcher");
    clear(folder, "Virtual Villagers Fun Patcher Logs");
    clear(folder, "Virtual Villagers Fun Patcher Data");
    clear(folder, "Virtual Villagers Fun Patcher Family Trees");
    clear(folder, "Backups");
}

#define OWN1 "Virtual Villagers Fun Patcher\\Save 1"
#define OWN2 "Virtual Villagers Fun Patcher\\Save 2"
#define OLD1 "Virtual Villagers Fun Patcher Logs\\Save 1"
#define OLD2 "Virtual Villagers Fun Patcher Logs\\Save 2"
#define DATA "Virtual Villagers Fun Patcher Data"
#define TREES "Virtual Villagers Fun Patcher Family Trees"
#define REPORT "Virtual Villagers Fun Patcher\\Start Over Report - Save 1.txt"

static void full_wipe_cases(const char *folder) {
    int game;
    clear_all(folder);
    for (game = 1; game <= 5; ++game) {
        char rel[MAX_PATH], text[256], what[256];
        const int other = game == 1 ? 2 : 1;
        int unclear_before = vv_reset_wipe_kept_unclear;
#define PUTF(fmt, txt) do { wsprintfA(rel, fmt, game); put(folder, rel, txt); } while (0)
#define THERE(fmt) (wsprintfA(rel, fmt, game), there(folder, rel))
#define SAY(msg) (wsprintfA(what, "game %d: " msg, game), what)
        /* The save's own folder, both slots. */
        PUTF(OWN1 "\\Logs\\Tribe History\\Village History 1.txt", "=== history ===\nVillage: Kalahuna (Save 1)\n");
        PUTF(OWN1 "\\Logs\\Repairs Made\\Virtual Villagers %d Repairs Log 1.txt", "Village: Kalahuna (Save 1)\n");
        PUTF(OWN1 "\\Data\\Elder Totems\\ElderTotems.dat", "totems");
        PUTF(OWN1 "\\Data\\Elder Totems\\Elder Totem Settings.dat", "settings");
        PUTF(OWN1 "\\Data\\Like and Dislike Words\\Virtual Villagers %d Log Words.dat", "0\tx\r\n");
        PUTF(OWN1 "\\Data\\A Kind Not Made Yet\\Anything At All.bin", "x");
        PUTF(OWN2 "\\Logs\\Tribe History\\Village History 1.txt", "=== history ===\nVillage: Elsewhere (Save 2)\n");
        PUTF(OWN2 "\\Data\\Elder Totems\\ElderTotems.dat", "totems");
        /* The older layout. */
        PUTF(OLD1 "\\Tribe History\\Village History 1.txt", "=== history ===\nVillage: Kalahuna (Save 1)\n");
        PUTF(OLD1 "\\Repairs Made\\Virtual Villagers %d Repairs Log 1.txt", "Village: Kalahuna (Save 1)\n");
        PUTF(OLD2 "\\Tribe History\\Village History 1.txt", "=== history ===\nVillage: Elsewhere (Save 2)\n");
        PUTF(DATA "\\Graves\\Virtual Villagers %d Graves - Save 1.dat", "g");
        PUTF(DATA "\\Graves\\Virtual Villagers %d Graves - Save 2.dat", "g");
        PUTF(DATA "\\A Kind Not Made Yet\\Something - Save 1.json", "{}");
        PUTF(DATA "\\Like and Dislike Words\\Virtual Villagers %d Log Words.dat", "0\tx\r\n");
        PUTF(DATA "\\Copies Made Before Repairs\\" DATA "\\Graves\\Virtual Villagers %d Graves - Save 1.dat.before-v1.35.58-repair", "c");
        /* A repair's copy under its own name (the statistics reconcile keeps its copies so). */
        put(folder, DATA "\\Copies Made Before Repairs\\" DATA "\\Village Elders\\Village Elders - Save 1.dat", "c");
        /* The family trees. */
        wsprintfA(text, "{\n \"format\": \"vvtree-1\",\n \"game\": %d,\n \"slot\": 1,\n \"tribe\": \"Kalahuna\",\n"
                        " \"edits\": {\"slot\": 2, \"x\": \"} \\\" {\"}\n}", game);
        put(folder, TREES "\\Kalahuna (Save 1) Family Tree.vvtree", text);
        wsprintfA(text, "{\"format\": \"vvtree-1\", \"game\": %d, \"slot\": 2, \"edits\": {\"slot\": 1}}", game);
        put(folder, TREES "\\Other (Save 2) Family Tree.vvtree", text);
        wsprintfA(text, "{\"format\": \"vvtree-1\", \"game\": %d, \"slot\": 1}", game);
        put(folder, TREES "\\Renamed by the player.vvtree", text);
        put(folder, TREES "\\Mixed (Save 2) Family Tree.vvtree", text);
        put(folder, TREES "\\Broken (Save 1) Family Tree.vvtree", "not a tree file");
        wsprintfA(text, "{\"format\": \"vvtree-1\", \"game\": %d, \"slot\": 1}", other);
        put(folder, TREES "\\Another Game (Save 1) Family Tree.vvtree", text);
        PUTF(TREES "\\Virtual Villagers %d Village Matchmaker - Save 1.txt", "pairs");
        PUTF(TREES "\\Virtual Villagers %d Village Matchmaker - Save 2.txt", "pairs");
        wsprintfA(rel, TREES "\\Virtual Villagers %d Village Matchmaker - Save 1.txt", other);
        put(folder, rel, "pairs");
        PUTF(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1.txt", "report");
        PUTF(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1.html", "<html>");
        PUTF(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1.png", "png");
        PUTF(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1 - Page 2.png", "png");
        PUTF(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 2.html", "<html>");
        put(folder, TREES "\\Kalahuna (Save 1) family tree 2026-10-20 10-00-00.jpg", "jpg");
        put(folder, TREES "\\notes.txt", "the player's own notes");
        PUTF("Virtual Villagers Fun Patcher Logs\\Genealogy\\Virtual Villagers %d Genealogy - Save 1.txt", "report");
        PUTF("Virtual Villagers Fun Patcher Logs\\Genealogy\\Virtual Villagers %d Genealogy - Save 1.png", "png");
        /* What is never the wipe's: the Backups and the game's own save. */
        put(folder, "Backups\\Backup 2026-10-20 10-00-00\\" OWN1 "\\Logs\\Tribe History\\Village History 1.txt", "b");
        put(folder, "Village Save1.ldw", "the game's");
        check(THERE(OWN1 "\\Data\\Elder Totems\\ElderTotems.dat") && THERE(TREES "\\notes.txt")
              && THERE(OLD1 "\\Tribe History\\Village History 1.txt"),
              SAY("full-wipe fixtures created (nonzero denominator)"));

        vv_reset_slot_state(game, 1, "Village: Kalahuna (Save 1)\n");

        /* Every file goes; the folders stay, empty, for the game's companions to write the new
           tribe's files into (they keep the paths they write to). */
        check(emptied(folder, OWN1) && emptied(folder, OWN1 "\\Data\\Elder Totems"),
              SAY("START OVER DELETES EVERYTHING IN \"Virtual Villagers Fun Patcher\\Save 1\" (its folders stay, empty)"));
        check(!THERE(OWN1 "\\Logs\\Tribe History\\Village History 1.txt"), SAY("...the slot's Village History with it"));
        check(!THERE(OWN1 "\\Data\\Elder Totems\\ElderTotems.dat"), SAY("...and its ElderTotems.dat"));
        check(THERE(OWN2 "\\Logs\\Tribe History\\Village History 1.txt") && THERE(OWN2 "\\Data\\Elder Totems\\ElderTotems.dat"),
              SAY("SAVE 2'S OWN FOLDER IS UNTOUCHED (its Village History and ElderTotems.dat)"));
        check(emptied(folder, OLD1), SAY("the older layout's \"...Logs\\Save 1\" folder is emptied, its Village History too"));
        check(THERE(OLD2 "\\Tribe History\\Village History 1.txt"), SAY("...and \"...Logs\\Save 2\" is kept"));
        check(!THERE(DATA "\\Graves\\Virtual Villagers %d Graves - Save 1.dat")
              && !THERE(DATA "\\A Kind Not Made Yet\\Something - Save 1.json"),
              SAY("the older Data folder's \" - Save 1\" files are deleted"));
        check(THERE(DATA "\\Graves\\Virtual Villagers %d Graves - Save 2.dat"), SAY("...its \" - Save 2\" files kept"));
        check(THERE(DATA "\\Like and Dislike Words\\Virtual Villagers %d Log Words.dat"),
              SAY("...and a shared file that names no save is kept"));
        check(THERE(DATA "\\Copies Made Before Repairs\\" DATA "\\Graves\\Virtual Villagers %d Graves - Save 1.dat.before-v1.35.58-repair"),
              SAY("COPIES MADE BEFORE REPAIRS ARE KEPT"));
        check(there(folder, DATA "\\Copies Made Before Repairs\\" DATA "\\Village Elders\\Village Elders - Save 1.dat"),
              SAY("...a copy under its own name too (the folder is never entered)"));
        check(!there(folder, TREES "\\Kalahuna (Save 1) Family Tree.vvtree"), SAY("SLOT 1'S .vvtree IS DELETED"));
        check(!there(folder, TREES "\\Renamed by the player.vvtree"),
              SAY("a .vvtree renamed by the player is deleted by the save it records"));
        check(there(folder, TREES "\\Other (Save 2) Family Tree.vvtree"),
              SAY("slot 2's .vvtree is kept (a \"slot\" nested in its edits is not its save)"));
        check(there(folder, TREES "\\Mixed (Save 2) Family Tree.vvtree"),
              SAY("a .vvtree whose name and contents name different saves is KEPT (never guessed)"));
        check(there(folder, TREES "\\Broken (Save 1) Family Tree.vvtree"),
              SAY("a .vvtree that records no save is KEPT (never guessed by its name)"));
        check(there(folder, TREES "\\Another Game (Save 1) Family Tree.vvtree"), SAY("another game's .vvtree is kept"));
        check(!THERE(TREES "\\Virtual Villagers %d Village Matchmaker - Save 1.txt"), SAY("SLOT 1'S VILLAGE MATCHMAKER IS DELETED"));
        check(THERE(TREES "\\Virtual Villagers %d Village Matchmaker - Save 2.txt"), SAY("...slot 2's is kept"));
        wsprintfA(rel, TREES "\\Virtual Villagers %d Village Matchmaker - Save 1.txt", other);
        check(there(folder, rel), SAY("...and another game's slot-1 matchmaker is kept"));
        check(!THERE(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1.txt")
              && !THERE(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1.html"),
              SAY("SLOT 1'S GENEALOGY REPORT (.txt, .html) IS DELETED"));
        check(THERE(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1.png")
              && THERE(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 1 - Page 2.png")
              && there(folder, TREES "\\Kalahuna (Save 1) family tree 2026-10-20 10-00-00.jpg"),
              SAY("EVERY PICTURE IS KEPT, slot 1's too"));
        check(THERE(TREES "\\Reports\\Virtual Villagers %d Genealogy - Save 2.html"), SAY("slot 2's report is kept"));
        check(there(folder, TREES "\\notes.txt"), SAY("a file that names no save is KEPT"));
        check(!THERE("Virtual Villagers Fun Patcher Logs\\Genealogy\\Virtual Villagers %d Genealogy - Save 1.txt")
              && THERE("Virtual Villagers Fun Patcher Logs\\Genealogy\\Virtual Villagers %d Genealogy - Save 1.png"),
              SAY("the older Reports folder (Logs\\Genealogy): the report goes, the picture stays"));
        check(there(folder, "Backups\\Backup 2026-10-20 10-00-00\\" OWN1 "\\Logs\\Tribe History\\Village History 1.txt"),
              SAY("THE BACKUPS ARE KEPT"));
        check(there(folder, "Village Save1.ldw"), SAY("the game's own save is kept"));
        check(vv_reset_wipe_kept_unclear - unclear_before == 3,
              SAY("exactly three files were kept because their save could not be told"));
        check(holds(folder, REPORT, "Mixed (Save 2) Family Tree.vvtree") && holds(folder, REPORT, "Broken (Save 1)")
              && holds(folder, REPORT, "notes.txt") && holds(folder, REPORT, "Village: Kalahuna (Save 1)"),
              SAY("the kept files are listed in \"Start Over Report - Save 1.txt\""));
        check(!holds(folder, REPORT, "Other (Save 2)"), SAY("...and a file of another save is not listed"));
        /* A companion that kept its file's path from before Start Over can still write it: its
           folder is there (no folder is made here). */
        wsprintfA(rel, "%s\\" OWN1 "\\Data\\Elder Totems\\ElderTotems.dat", folder);
        write_text(rel, "the new tribe's");
        check(exists(rel), SAY("A FILE PATH KEPT FROM BEFORE START OVER CAN STILL BE WRITTEN (its folder stays)"));
        clear_all(folder);
        {
            char ldw[MAX_PATH];
            wsprintfA(ldw, "%s\\Village Save1.ldw", folder);
            DeleteFileA(ldw);
        }
#undef PUTF
#undef THERE
#undef SAY
    }

    /* What stays inside the slot's own folder: the Copies Made Before Repairs, a repair copy beside
       its file and a picture; a file in use is listed, not retried; a junction is never followed. */
    {
        char target[MAX_PATH], link[MAX_PATH], kept_outside[MAX_PATH], locked_path[MAX_PATH];
        char command[MAX_PATH * 3];
        HANDLE locked;
        STARTUPINFOA si;
        PROCESS_INFORMATION pi;
        int not_deleted_before = vv_reset_wipe_not_deleted;
        int links_before = vv_reset_wipe_links;
        put(folder, OWN1 "\\Data\\Copies Made Before Repairs\\Logs\\Tribe History\\Village History 1.txt.before-v1.35.58-repair", "c");
        put(folder, OWN1 "\\Logs\\Tribe History\\Village History 1.txt.before-repair", "c");
        put(folder, OWN1 "\\Data\\Copies Made Before Repairs\\Data\\Village Elders\\Village Elders - Save 1.dat", "c");
        put(folder, OWN1 "\\Logs\\A picture.png", "png");
        put(folder, OWN1 "\\Logs\\Tribe History\\Village History 1.txt", "h");
        put(folder, OWN1 "\\Logs\\Deaths and Disappearances\\Virtual Villagers 3 Deaths Log 1.txt", "Village: Kalahuna (Save 1)\n");
        put(folder, OWN1 "\\Data\\Elder Totems\\ElderTotems.dat", "t");
        /* Outside the save folder, reached only through a junction inside the slot's folder. */
        wsprintfA(target, "%s\\..\\..\\outside the save folder", folder);
        CreateDirectoryA(target, NULL);
        wsprintfA(kept_outside, "%s\\must survive.dat", target);
        write_text(kept_outside, "x");
        wsprintfA(link, "%s\\" OWN1 "\\Data\\Linked Folder", folder);
        wsprintfA(command, "cmd.exe /c mklink /J \"%s\" \"%s\" >nul", link, target);
        ZeroMemory(&si, sizeof si);
        si.cb = sizeof si;
        ZeroMemory(&pi, sizeof pi);
        if (CreateProcessA(NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
            WaitForSingleObject(pi.hProcess, 30000);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
        }
        wsprintfA(locked_path, "%s\\" OWN1 "\\Logs\\Deaths and Disappearances\\Virtual Villagers 3 Deaths Log 1.txt", folder);
        locked = CreateFileA(locked_path, GENERIC_READ, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        check(locked != INVALID_HANDLE_VALUE && exists(kept_outside)
              && (GetFileAttributesA(link) & FILE_ATTRIBUTE_REPARSE_POINT) && GetFileAttributesA(link) != INVALID_FILE_ATTRIBUTES,
              "keep fixtures created: a junction out of the save folder and a file held open (nonzero denominator)");

        vv_reset_slot_state(3, 1, "Village: Kalahuna (Save 1)\n");

        check(there(folder, OWN1 "\\Data\\Copies Made Before Repairs\\Logs\\Tribe History\\Village History 1.txt.before-v1.35.58-repair"),
              "the slot's own Copies Made Before Repairs are kept");
        check(there(folder, OWN1 "\\Data\\Copies Made Before Repairs\\Data\\Village Elders\\Village Elders - Save 1.dat"),
              "...a copy under its own name too (the folder is never entered)");
        check(there(folder, OWN1 "\\Logs\\Tribe History\\Village History 1.txt.before-repair"),
              "a repair copy kept beside its file is kept");
        check(there(folder, OWN1 "\\Logs\\A picture.png"), "a picture in the slot's own folder is kept");
        check(!there(folder, OWN1 "\\Logs\\Tribe History\\Village History 1.txt")
              && emptied(folder, OWN1 "\\Data\\Elder Totems"), "...while everything else of the slot goes");
        check(exists(locked_path) && vv_reset_wipe_not_deleted - not_deleted_before == 1,
              "A FILE IN USE IS LEFT, COUNTED ONCE (not retried) AND THE RESET RETURNS");
        check(holds(folder, REPORT, "Virtual Villagers 3 Deaths Log 1.txt"), "...and it is listed in the report");
        check(exists(kept_outside), "A JUNCTION OUT OF THE SAVE FOLDER IS NEVER FOLLOWED: the file behind it survives");
        check(GetFileAttributesA(link) != INVALID_FILE_ATTRIBUTES && vv_reset_wipe_links - links_before == 1,
              "...the junction itself is left, and counted");
        check(holds(folder, REPORT, "Linked Folder"), "...and listed in the report");
        if (locked != INVALID_HANDLE_VALUE) {
            CloseHandle(locked);
        }
        RemoveDirectoryA(link);                  /* the junction only, never its target */
        check(exists(kept_outside), "the junction's target is untouched by removing the junction");
        DeleteFileA(kept_outside);
        RemoveDirectoryA(target);

        /* Nothing to list: the next Start Over of the save removes the last one's report. */
        vv_reset_slot_state(3, 1, "Village: Kalahuna (Save 1)\n");
        check(!there(folder, REPORT), "a Start Over with nothing to list leaves no report (the last one is removed)");
        clear_all(folder);
    }
}

int main(void) {
    harness_ldw_tree_begin();   /* first: leaves Documents\LDW as it found it */
    char folder[MAX_PATH];
    wchar_t folder_w_probe[MAX_PATH];
    char mask1[MAX_PATH], mask2[MAX_PATH], doubler1[MAX_PATH];
    char save1[MAX_PATH], other_game[MAX_PATH];
    char log1[MAX_PATH];
    int removed;
    char stats1[MAX_PATH], stats2[MAX_PATH];
    char pop1[MAX_PATH], pop2[MAX_PATH];
    char log_other[MAX_PATH];
    char popdir[MAX_PATH], pardir[MAX_PATH];   /* the moved log folders */
    static const char VILLAGE[]  = "Village: Kalahuna (Save 1)\n";
    static const char VILLAGE2[] = "Village: Elsewhere (Save 2)\n";

    if (!vv_save_folder(folder, 64)) {
        printf("could not resolve the save folder\n");
        return 2;
    }
    printf("save folder: %s\n\n", folder);
    /* NEVER THE PLAYER'S SAVES. harness_ldw_tree_begin pointed this whole process's Documents at a
       throwaway folder under %TEMP% (harness_redirect_documents.h); the folder the reset resolves must
       be inside it, or nothing below runs. */
    {
        char temp[MAX_PATH];
        const char *docs = harness_redirect_documents_path();
        DWORD n = GetTempPathA(MAX_PATH, temp);
        if (n == 0 || n >= MAX_PATH || docs[0] == '\0'
            || _strnicmp(folder, temp, n) != 0 || _strnicmp(folder, docs, strlen(docs)) != 0
            || folder[strlen(docs)] != '\\') {
            printf("the save folder is not under the throwaway Documents (%s); not running\n", docs);
            return 2;
        }
        printf("documents redirected to: %s\n\n", docs);
    }
    if (!vv_save_folder_w(folder_w_probe, 64)) {
        printf("could not resolve the wide save folder\n");
        return 2;
    }

    /* VV1 owns two sidecars per slot. Create slot 1 and slot 2, plus a game
       save and a file belonging to a different game, so the test can show what
       survives as well as what goes. */
    /* The population and parentage logs moved into the owner's log layout
       (#418); the harness follows so it tests the reset against where the
       exporters actually write. */
    if (!vv_save_subfolder(popdir, "Virtual Villagers Fun Patcher Logs\\Tribe Population", 64)
        || !vv_save_subfolder(pardir, "Virtual Villagers Fun Patcher Logs\\Births and Conceptions", 64)) {
        printf("could not resolve the log subfolders\n");
        return 2;
    }
    /* The subfolders must be INSIDE the save folder -- "<save>\\Virtual Villagers Fun Patcher Logs\\...",
       not "<save>Virtual Villagers Fun Patcher Logs..." glued onto its name. A live run found the
       helper doing exactly that while this harness passed, because the
       fixtures and the reset used the same wrong path. Checked against
       the resolved save folder, not against a literal. */
    {
        int flen = lstrlenA(folder);
        check(strncmp(popdir, folder, flen) == 0 && popdir[flen] == '\\'
              && strcmp(popdir + flen, "\\Virtual Villagers Fun Patcher Logs\\Tribe Population") == 0,
              "population subfolder is <save folder>\\Virtual Villagers Fun Patcher Logs\\Tribe Population");
        check(strncmp(pardir, folder, flen) == 0 && pardir[flen] == '\\'
              && strcmp(pardir + flen, "\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions") == 0,
              "parental subfolder is <save folder>\\Virtual Villagers Fun Patcher Logs\\Births and Conceptions");
        check(GetFileAttributesA(popdir) != INVALID_FILE_ATTRIBUTES,
              "population subfolder was actually created");
    }
    wsprintfA(mask1, "%s\\vv1_masks_1.dat", folder);
    wsprintfA(mask2, "%s\\vv1_masks_2.dat", folder);
    wsprintfA(doubler1, "%s\\vv1_doublers_1.dat", folder);
    wsprintfA(save1, "%s\\Virtual Villagers1.ldw", folder);
    wsprintfA(other_game, "%s\\vv2_masks_1.dat", folder);
    wsprintfA(log1, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);

    wsprintfA(stats1, "%s\\Village Statistics - Save 1.txt", folder);
    wsprintfA(stats2, "%s\\Village Statistics - Save 2.txt", folder);
    wsprintfA(pop1, "%s\\Village Population 1.txt", popdir);
    wsprintfA(pop2, "%s\\Village Population 2.txt", popdir);
    wsprintfA(log_other, "%s\\Virtual Villagers 1 Births and Conceptions Log 2.txt", pardir);

    touch(mask1); touch(mask2); touch(doubler1);
    touch(save1); touch(other_game);
    touch(stats1); touch(stats2);
    /* The roster is numbered by PAGE in a folder every slot shares, and each
       page opens with the title and then the village header, exactly as
       population_export.c writes it. Pages 1 and 2 are the erased village's;
       see below for the pages that are not. */
    write_text(pop1, "Virtual Villagers: A New Home Village Population\n"
                     "Village: Kalahuna (Save 1)\n\n1. Someone\n");
    write_text(pop2, "Virtual Villagers: A New Home Village Population\n"
                     "Village: Kalahuna (Save 1)\n\n257. Someone else\n");
    /* The two parentage logs carry DIFFERENT village headers: log1 belongs to
       the village being erased, log_other to a village that is not. */
    write_text(log1, VILLAGE);
    write_text(log_other, VILLAGE2);

    printf("created 6 files; resetting VV1 slot 1\n");
    check(exists(mask1) && exists(mask2) && exists(doubler1)
          && exists(save1) && exists(other_game) && exists(log1),
          "all 6 files exist before the reset (nonzero denominator)");

    removed = vv_reset_slot_state(1, 1, VILLAGE);
    printf("vv_reset_slot_state(1, 1) removed %d files\n", removed);

    check(removed >= 3, "reset reported removing at least the 3 VV1 slot-1 files");
    check(!exists(mask1), "slot 1 mask sidecar deleted");
    check(!exists(doubler1), "slot 1 doubler sidecar deleted");
    check(!exists(log1), "slot 1 parentage log deleted");
    check(exists(mask2), "SLOT 2 sidecar SURVIVES (no cross-slot deletion)");
    check(exists(save1), "the game's own .ldw SURVIVES (patcher deletes only its own)");
    check(exists(other_game), "another game's sidecar SURVIVES");

    /* THE P1 CODEX FOUND ON #380. Statistics and population logs are numbered
       by SLOT, so an unscoped walk deleted villages that were never reset. */
    check(!exists(stats1), "slot 1 statistics log deleted");
    check(exists(stats2), "SLOT 2 STATISTICS SURVIVES (was destroyed before the fix)");
    /* Population pages belong to a VILLAGE, not a slot: all of the erased
       village's pages go, whatever their numbers. */
    check(!exists(pop1), "population page 1 of the erased village deleted");
    check(!exists(pop2), "POPULATION PAGE 2 OF THE ERASED VILLAGE DELETED (slot 1 left it before the fix)");

    /* THE ROSTER IS MATCHED BY HEADER, NEVER BY SLOT.

       Before this fix the reset deleted "Village Population <slot>.txt":
       a slot-1 Start Over deleted page 1 of whichever village had saved
       last, and slots 2..5 deleted a page of someone else's roster or
       nothing at all. */
    {
        char legacy_dir[MAX_PATH], legacy1[MAX_PATH];
        static const char OTHER_PAGE[] =
            "Virtual Villagers: A New Home Village Population\n"
            "Village: Elsewhere (Save 2)\n\n1. Someone\n";
        static const char ERASED_PAGE[] =
            "Virtual Villagers: A New Home Village Population\n"
            "Village: Kalahuna (Save 1)\n\n1. Someone\n";

        /* Another village owns page 1: a slot-1 reset of Kalahuna must
           leave it, which the slot-numbered sweep did not. */
        write_text(pop1, OTHER_PAGE);
        write_text(pop2, ERASED_PAGE);
        check(exists(pop1) && exists(pop2), "roster pages recreated (nonzero denominator)");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(exists(pop1), "ANOTHER VILLAGE'S POPULATION PAGE 1 SURVIVES A SLOT-1 RESET");
        check(!exists(pop2), "the erased village's page 2 is deleted though slot is 1");

        /* The slot number is irrelevant: erasing slot 2's village deletes
           the page it owns even though that page is number 1. */
        vv_reset_slot_state(1, 2, VILLAGE2);
        check(!exists(pop1), "SLOT-2 RESET DELETES ITS VILLAGE'S PAGE 1 (slot number irrelevant)");
        /* That reset rightly took slot 2's own sidecar, statistics and
           Elsewhere's parentage log; put them back for the survivor checks
           further down. */
        touch(mask2);
        touch(stats2);
        write_text(log_other, VILLAGE2);

        /* Without a village string nothing is guessed at. */
        write_text(pop1, ERASED_PAGE);
        vv_reset_slot_state(1, 1, NULL);
        check(exists(pop1), "NULL village leaves population pages alone");
        vv_reset_slot_state(1, 1, "");
        check(exists(pop1), "empty village leaves population pages alone");

        /* A header on the FIRST line is not the roster's shape. */
        write_text(pop2, "Village: Kalahuna (Save 1)\nnot a roster\n");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(pop1), "erased village's page deleted on a real reset");
        check(exists(pop2), "a file whose FIRST line is the header is not a roster page");
        DeleteFileA(pop2);

        /* The retired folder is swept the same way, and only by header. */
        wsprintfA(legacy_dir, "%s\\VVFP Logs", folder);
        CreateDirectoryA(legacy_dir, NULL);
        wsprintfA(legacy_dir, "%s\\VVFP Logs\\Tribe Population", folder);
        CreateDirectoryA(legacy_dir, NULL);
        wsprintfA(legacy1, "%s\\Village Population 3.txt", legacy_dir);
        write_text(legacy1, ERASED_PAGE);
        write_text(pop1, OTHER_PAGE);
        check(exists(legacy1), "legacy roster page created (nonzero denominator)");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(legacy1), "erased village's page in the RETIRED folder deleted");
        check(exists(pop1), "other village's page survives the retired-folder pass");
        DeleteFileA(pop1);
        RemoveDirectoryA(legacy_dir);
        wsprintfA(legacy_dir, "%s\\VVFP Logs", folder);
        RemoveDirectoryA(legacy_dir);
    }

    /* The Story / Cheat Upgrades custom titles (native/shared/custom_titles.h)
       are per slot in every game, and the owner's rule is that the .dat
       follows the Start Over reset: slot 1's goes, slot 2's stays. */
    {
        char titles_dir[MAX_PATH], t1[MAX_PATH], t2[MAX_PATH];
        int game;
        if (!vv_save_subfolder(titles_dir, "Virtual Villagers Fun Patcher Data\\Custom Titles", 64)) {
            printf("could not resolve the custom titles folder\n");
            return 2;
        }
        wsprintfA(t1, "%s\\Custom Titles - Save 1.dat", titles_dir);
        wsprintfA(t2, "%s\\Custom Titles - Save 2.dat", titles_dir);
        for (game = 1; game <= 5; ++game) {
            char what[96];
            touch(t1);
            touch(t2);
            check(exists(t1) && exists(t2), "custom titles files exist before the reset (nonzero denominator)");
            vv_reset_slot_state(game, 1, VILLAGE);
            wsprintfA(what, "CUSTOM TITLES OF SLOT 1 DELETED BY START OVER (game %d)", game);
            check(!exists(t1), what);
            wsprintfA(what, "custom titles of slot 2 survive a slot-1 reset (game %d)", game);
            check(exists(t2), what);
            /* other_game is "vv2_masks_1.dat": the "another game's sidecar"
               fixture for the VV1 resets, but VV2's OWN slot-1 sidecar, so
               this loop's VV2 slot-1 Start Over rightly deletes it. Assert
               that, then put it back so the survivor checks further down
               still have it to test (they failed on every run from #495
               until this restore: the fixture was gone, not the reset wrong). */
            if (game == 2) {
                check(!exists(other_game), "VV2 slot-1 reset deletes VV2's own slot-1 sidecar");
                touch(other_game);
            }
        }
        DeleteFileA(t2);
    }

    /* THE LOST CHILDREN'S ELDER TOTEMS (native/vvfp_vv2_totems): ElderTotems.dat and the village's
       give-automatically setting, in the save's own "...\Save <N>\Data\Elder Totems" folder, follow
       Start Over: slot 1's go, slot 2's stay, and no other game's reset touches them. */
    {
        char dir1[MAX_PATH], dir2[MAX_PATH], e1[MAX_PATH], s1[MAX_PATH], e2[MAX_PATH];
        if (!vv_save_subfolder(dir1, "Virtual Villagers Fun Patcher\\Save 1\\Data\\Elder Totems", 64)
            || !vv_save_subfolder(dir2, "Virtual Villagers Fun Patcher\\Save 2\\Data\\Elder Totems", 64)) {
            printf("could not resolve the elder totems folders\n");
            return 2;
        }
        wsprintfA(e1, "%s\\ElderTotems.dat", dir1);
        wsprintfA(s1, "%s\\Elder Totem Settings.dat", dir1);
        wsprintfA(e2, "%s\\ElderTotems.dat", dir2);
        touch(e1);
        touch(s1);
        touch(e2);
        check(exists(e1) && exists(s1) && exists(e2), "elder totems files exist before the reset (nonzero denominator)");
        vv_reset_slot_state(2, 1, VILLAGE);
        check(!exists(e1), "ELDERTOTEMS.DAT OF SLOT 1 DELETED BY START OVER (The Lost Children)");
        check(!exists(s1), "slot 1's Elder Totem Settings.dat deleted by Start Over");
        check(exists(e2), "slot 2's ElderTotems.dat survives a slot-1 reset");
        DeleteFileA(e2);
    }

    /* EACH KIND IN ITS OWN FOLDER (native/shared/data_subfolder.h). The
       masks, the graves, A New Home's parentage records and the Unaccounted
       Villagers roster moved out of the Data folder's root into a folder
       each; a file left loose by an older build (or one that would not move)
       is still the village's. Start Over removes slot 1's at BOTH places and
       leaves slot 2's at both, in every game that writes the kind -- and a
       file of that name with anything after ".dat" (a backup the player made
       by hand, a set-aside unreadable copy) is not the patcher's live file
       and is never touched. */
    {
        /* `loose` is the name an older build gave the file loose in the Data folder; the folder and
           file names an older build used in the folder (native/shared/save_layout.h: "Parentage
           Records", "... Village Roster") are rows of their own, until they have been moved. */
        struct kind { int game; const char *sub; const char *stem; const char *loose; };
        static const struct kind KINDS[] = {
            { 1, "Village Masks", "Virtual Villagers 1 Village Masks", "Virtual Villagers 1 Village Masks" },
            { 2, "Village Masks", "Virtual Villagers 2 Village Masks", "Virtual Villagers 2 Village Masks" },
            { 3, "Village Masks", "Village Masks", "Village Masks" },
            { 4, "Village Masks", "Village Masks", "Village Masks" },
            { 5, "Village Masks", "Village Masks", "Village Masks" },
            { 1, "Parents (A New Home)", "Virtual Villagers 1 Parentage Records", "Virtual Villagers 1 Parentage Records" },
            { 1, "Parentage Records", "Virtual Villagers 1 Parentage Records", "Virtual Villagers 1 Parentage Records" },
            { 1, "Graves", "Virtual Villagers 1 Graves", "Virtual Villagers 1 Graves" },
            { 2, "Graves", "Virtual Villagers 2 Graves", "Virtual Villagers 2 Graves" },
            { 1, "Unaccounted Villagers", "Virtual Villagers 1 Villagers at Last Save", "Virtual Villagers 1 Village Roster" },
            { 2, "Unaccounted Villagers", "Virtual Villagers 2 Villagers at Last Save", "Virtual Villagers 2 Village Roster" },
            { 3, "Unaccounted Villagers", "Virtual Villagers 3 Villagers at Last Save", "Virtual Villagers 3 Village Roster" },
            { 4, "Unaccounted Villagers", "Virtual Villagers 4 Villagers at Last Save", "Virtual Villagers 4 Village Roster" },
            { 5, "Unaccounted Villagers", "Virtual Villagers 5 Villagers at Last Save", "Virtual Villagers 5 Village Roster" },
            { 1, "Unaccounted Villagers", "Virtual Villagers 1 Village Roster", "Virtual Villagers 1 Village Roster" },
            { 2, "Unaccounted Villagers", "Virtual Villagers 2 Village Roster", "Virtual Villagers 2 Village Roster" },
            { 3, "Unaccounted Villagers", "Virtual Villagers 3 Village Roster", "Virtual Villagers 3 Village Roster" },
            { 4, "Unaccounted Villagers", "Virtual Villagers 4 Village Roster", "Virtual Villagers 4 Village Roster" },
            { 5, "Unaccounted Villagers", "Virtual Villagers 5 Village Roster", "Virtual Villagers 5 Village Roster" },
        };
        char data_dir[MAX_PATH], sub_dir[MAX_PATH];
        char new1[MAX_PATH], new2[MAX_PATH], old1[MAX_PATH], old2[MAX_PATH];
        char backup1[MAX_PATH], aside1[MAX_PATH];
        int k;
        if (!vv_save_subfolder(data_dir, "Virtual Villagers Fun Patcher Data", 96)) {
            printf("could not resolve the data folder\n");
            return 2;
        }
        for (k = 0; k < (int)(sizeof KINDS / sizeof KINDS[0]); ++k) {
            char what[200];
            int other;
            wsprintfA(sub_dir, "%s\\%s", data_dir, KINDS[k].sub);
            CreateDirectoryA(sub_dir, NULL);
            wsprintfA(new1, "%s\\%s - Save 1.dat", sub_dir, KINDS[k].stem);
            wsprintfA(new2, "%s\\%s - Save 2.dat", sub_dir, KINDS[k].stem);
            wsprintfA(old1, "%s\\%s - Save 1.dat", data_dir, KINDS[k].loose);
            wsprintfA(old2, "%s\\%s - Save 2.dat", data_dir, KINDS[k].loose);
            wsprintfA(backup1, "%s\\%s - Save 1.dat.before-repair", data_dir, KINDS[k].loose);
            wsprintfA(aside1, "%s\\%s - Save 1.dat.unreadable-1-0", sub_dir, KINDS[k].stem);
            touch(new1); touch(new2); touch(old1); touch(old2); touch(backup1); touch(aside1);
            wsprintfA(what, "game %d %s: both places, both slots, exist before the reset (nonzero denominator)",
                      KINDS[k].game, KINDS[k].sub);
            check(exists(new1) && exists(new2) && exists(old1) && exists(old2), what);
            /* Another game's reset is not this file's: a renamed install can
               share a folder, and only the running game's own files go.
               A New Home is the other game for every kind but its own, and
               The Secret City is the other game for A New Home's. */
            /* Only a name that says its game ("Virtual Villagers <G> ...") can be told apart: Start
               Over wipes every " - Save 1" data file of the save folder, which is the game's own. */
            other = KINDS[k].game == 1 ? 3 : 1;
            if (strncmp(KINDS[k].stem, "Virtual Villagers ", 18) == 0) {
                vv_reset_slot_state(other, 1, VILLAGE);
                wsprintfA(what, "game %d %s: a reset of game %d leaves both copies of slot 1",
                          KINDS[k].game, KINDS[k].sub, other);
                check(exists(new1) && exists(old1), what);
            }
            vv_reset_slot_state(KINDS[k].game, 1, VILLAGE);
            wsprintfA(what, "game %d %s: START OVER DELETES SLOT 1 IN ITS FOLDER", KINDS[k].game, KINDS[k].sub);
            check(!exists(new1), what);
            wsprintfA(what, "game %d %s: START OVER DELETES SLOT 1 LEFT LOOSE", KINDS[k].game, KINDS[k].sub);
            check(!exists(old1), what);
            wsprintfA(what, "game %d %s: slot 2 survives at both places", KINDS[k].game, KINDS[k].sub);
            check(exists(new2) && exists(old2), what);
            wsprintfA(what, "game %d %s: a repair's copy beside the file is not touched",
                      KINDS[k].game, KINDS[k].sub);
            check(exists(backup1), what);
            wsprintfA(what, "game %d %s: START OVER DELETES SLOT 1'S SET-ASIDE COPY TOO (v1.35.79 full wipe)",
                      KINDS[k].game, KINDS[k].sub);
            check(!exists(aside1), what);
            DeleteFileA(new2); DeleteFileA(old2); DeleteFileA(backup1); DeleteFileA(aside1);
            RemoveDirectoryA(sub_dir);
        }
        /* The Lost Children's slot-1 resets above rightly took its loose
           root-level mask file, which the survivor checks below use as
           "another game's file"; put it back. */
        touch(other_game);
    }

    /* The statistics companion's per-slot data: the counters, the stew
       discoveries and the elders, each a .dat addressed by slot, plus the
       current "v2" statistics log. Start Over must clear slot 1's and leave
       slot 2's. The reset is run as The Secret City, one of the three games
       that make stews, and then as A New Home, which does not. */
    {
        char dat_dir[MAX_PATH], stew_dir[MAX_PATH], elder_dir[MAX_PATH], log_dir[MAX_PATH];
        char s1[MAX_PATH], s2[MAX_PATH], st1[MAX_PATH], st2[MAX_PATH];
        char e1[MAX_PATH], e2[MAX_PATH], tmp1[MAX_PATH], aside1[MAX_PATH];
        char v2log1[MAX_PATH], v2log2[MAX_PATH];
        if (!vv_save_subfolder(dat_dir, "Virtual Villagers Fun Patcher Data\\Village Statistics", 64)
            || !vv_save_subfolder(stew_dir, "Virtual Villagers Fun Patcher Data\\Stew Discoveries", 64)
            || !vv_save_subfolder(elder_dir, "Virtual Villagers Fun Patcher Data\\Village Elders", 64)
            || !vv_save_subfolder(log_dir, "Virtual Villagers Fun Patcher Logs\\Village Statistics", 64)) {
            printf("could not resolve the data subfolders\n");
            return 2;
        }
        wsprintfA(s1, "%s\\Village Statistics - Save 1.dat", dat_dir);
        wsprintfA(s2, "%s\\Village Statistics - Save 2.dat", dat_dir);
        wsprintfA(tmp1, "%s\\Village Statistics - Save 1.dat.tmp", dat_dir);
        wsprintfA(st1, "%s\\Stew Discoveries - Save 1.dat", stew_dir);
        wsprintfA(st2, "%s\\Stew Discoveries - Save 2.dat", stew_dir);
        wsprintfA(aside1, "%s\\Stew Discoveries - Save 1.dat.unreadable", stew_dir);
        wsprintfA(e1, "%s\\Village Elders - Save 1.dat", elder_dir);
        wsprintfA(e2, "%s\\Village Elders - Save 2.dat", elder_dir);
        wsprintfA(v2log1, "%s\\Village Statistics v2 - Save 1.txt", log_dir);
        wsprintfA(v2log2, "%s\\Village Statistics v2 - Save 2.txt", log_dir);
        touch(s1); touch(s2); touch(tmp1); touch(st1); touch(st2); touch(aside1);
        touch(e1); touch(e2); touch(v2log1); touch(v2log2);
        check(exists(s1) && exists(st1) && exists(e1) && exists(tmp1) && exists(v2log1),
              "statistics data files exist before the reset (nonzero denominator)");
        vv_reset_slot_state(3, 1, VILLAGE);
        check(!exists(s1), "slot 1 Village Statistics .dat deleted");
        check(!exists(tmp1), "slot 1 Village Statistics .dat.tmp deleted");
        check(!exists(st1), "slot 1 Stew Discoveries .dat deleted");
        check(!exists(e1), "slot 1 Village Elders .dat deleted");
        check(!exists(v2log1), "slot 1 Village Statistics v2 log deleted");
        check(exists(s2) && exists(st2) && exists(e2) && exists(v2log2),
              "SLOT 2 statistics data SURVIVES");
        check(!exists(aside1), "slot 1's file set aside as unreadable is deleted too (v1.35.79 full wipe)");
        touch(st1);
        touch(st2);
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(st1), "every \" - Save 1\" data file of the save folder goes, whichever game resets it");
        check(exists(st2), "...and slot 2's stays");
        DeleteFileA(s2); DeleteFileA(st1); DeleteFileA(st2); DeleteFileA(aside1);
        DeleteFileA(e2); DeleteFileA(v2log2);
    }

    /* Parentage logs roll over by count, so they are matched by header. */
    check(!exists(log1), "parentage log of the erased village deleted");
    check(exists(log_other), "ANOTHER VILLAGE'S PARENTAGE LOG SURVIVES (header mismatch)");

    /* Without a village string, parentage cannot be identified and must be
       left alone rather than deleted on a guess. */
    {
        char probe[MAX_PATH];
        wsprintfA(probe, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);
        write_text(probe, VILLAGE);
        check(exists(probe), "parentage probe recreated (nonzero denominator)");
        vv_reset_slot_state(1, 1, NULL);
        check(exists(probe), "NULL village leaves parentage logs alone");
        vv_reset_slot_state(1, 1, "");
        check(exists(probe), "empty village leaves parentage logs alone");
        DeleteFileA(probe);
    }

    /* A RESET MUST SEE PAST THE HOLES AN EARLIER RESET MADE.

       This sweep deletes the erased village's numbered logs, and the
       exporter then hands a freed number to the next village, so different
       villages legitimately end up owning non-consecutive numbers. A scan
       that stopped at the first absent number walked into the hole the
       previous reset left and stopped there, and the later village's own
       Start Over never reached its file. Found in review.

       Reproduce it exactly: leave number 1 absent and put the village being
       erased at number 2. */
    {
        char gap1[MAX_PATH];
        char gap2[MAX_PATH];
        wsprintfA(gap1, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", pardir);
        wsprintfA(gap2, "%s\\Virtual Villagers 1 Births and Conceptions Log 2.txt", pardir);
        DeleteFileA(gap1);                 /* the hole a previous reset made */
        write_text(gap2, VILLAGE);         /* the erased village, past the hole */
        check(!exists(gap1) && exists(gap2),
              "gap case set up: number 1 absent, erased village at number 2");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(gap2),
              "LOG PAST A HOLE IS DELETED (survived its own reset before the fix)");
        DeleteFileA(gap2);
    }

    /* Refusals: nothing outside a real village slot may delete anything. */
    check(vv_reset_slot_state(1, 0, VILLAGE) == -1, "slot 0 refused (meta file, not a village)");
    check(vv_reset_slot_state(1, 6, VILLAGE) == -1, "slot 6 refused (out of range)");
    check(vv_reset_slot_state(1, -1, VILLAGE) == -1, "negative slot refused");
    check(vv_reset_slot_state(0, 1, VILLAGE) == -1, "game 0 refused");
    check(vv_reset_slot_state(6, 1, VILLAGE) == -1, "game 6 refused");
    /* One check per survivor, so a failure names the file that went. */
    check(exists(mask2), "survivor: VV1 slot-2 sidecar present after all five refusals");
    check(exists(save1), "survivor: the game's own .ldw present after all five refusals");
    check(exists(other_game), "survivor: VV2 slot-1 sidecar present after all five refusals");

    /* The two guards above are easy to write and easy to get wrong. Mutation
       testing showed an earlier version of this harness could not tell a
       correct implementation from a broken one: removing the empty-path guard,
       and making vv_save_folder fall back to ".", both left it green. So both
       are now asserted directly rather than inferred from the reset's result.

       EMPTY PATH. A reset that cannot build a path must delete nothing. An
       out-of-range slot returns before any path is constructed, so if a later
       guard were removed this still proves nothing was touched. */
    {
        char probe[MAX_PATH];
        int before, after;
        wsprintfA(probe, "%s\\vv1_masks_2.dat", folder);
        before = exists(probe);
        check(vv_reset_slot_state(1, 99, VILLAGE) == -1, "slot 99 refused before any path is built");
        after = exists(probe);
        check(before && after, "refused reset deleted nothing (empty-path guard holds)");
    }

    /* CURRENT-DIRECTORY FALLBACK. If vv_save_folder ever resolved to "." the
       reset would delete files beside the executable. A "." or empty result is
       exactly the fallback that must never exist. */
    check(folder[0] != '\0', "resolved folder is not empty");
    check(!(folder[0] == '.' && folder[1] == '\0'),
          "resolved folder is not the current directory");
    check(folder[1] == ':' && folder[2] == '\\',
          "resolved folder is absolute (drive-qualified)");
    {
        /* and it is the SAVE folder, not the install folder -- the defect that
           put exported logs next to the .exe in all five games. */
        char exe[MAX_PATH];
        char *slash;
        GetModuleFileNameA(NULL, exe, MAX_PATH);
        slash = strrchr(exe, '\\');
        if (slash != NULL) {
            *slash = '\0';
        }
        check(lstrcmpiA(folder, exe) != 0,
              "resolved folder is NOT the executable's directory");
    }

    /* DIRECT CALLS. The two checks above prove the guards are not reached in
       normal operation; these prove the guards themselves are correct. Both
       mutations that survived the first mutation run -- deleting on an empty
       path, and resolving the save folder to "." -- fail here.

       A real file is created first so a wrongly-permissive guard has something
       to destroy: asserting "returns 0" against a path that does not exist
       would pass even if the guard were gone. */
    {
        char victim[MAX_PATH];
        wchar_t victim_w[MAX_PATH];

        wsprintfA(victim, "%s\\guard_probe.dat", folder);
        touch(victim);
        check(exists(victim), "guard probe file created (nonzero denominator)");

        vv_reset_refused_paths = 0;
        check(delete_if_present("") == 0, "empty path deletes nothing");
        check(vv_reset_refused_paths == 1,
              "empty path was REFUSED before any filesystem call");
        check(delete_if_present(NULL) == 0, "NULL path deletes nothing");
        check(exists(victim), "probe survived the empty/NULL path calls");

        vv_reset_refused_paths = 0;
        check(delete_if_present_w(L"") == 0, "empty wide path deletes nothing");
        check(vv_reset_refused_paths == 1,
              "empty wide path was REFUSED before any filesystem call");
        check(delete_if_present_w(NULL) == 0, "NULL wide path deletes nothing");
        check(exists(victim), "probe survived the wide empty/NULL calls");

        /* and the guard does not refuse a real path -- a guard that refused
           everything would pass every check above while breaking the reset. */
        check(delete_if_present(victim) == 1, "a real path IS deleted");
        check(!exists(victim), "probe actually removed");

        wsprintfW(victim_w, L"%ls\\guard_probe_w.dat", folder_w_probe);
        {
            HANDLE h = CreateFileW(victim_w, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                                   FILE_ATTRIBUTE_NORMAL, NULL);
            if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
        }
        check(GetFileAttributesW(victim_w) != INVALID_FILE_ATTRIBUTES,
              "wide probe created");
        check(delete_if_present_w(victim_w) == 1, "a real wide path IS deleted");
    }

    /* A RENAMED TRIBE'S LOGS GO WITH IT. Rename Tribe never rewrites a
       header; it appends "Tribe renamed from <old> to <new> on <date>". A
       Start Over of the renamed village reads the NEW name from its save, so
       the reset must follow the note to recognise the logs headed with the
       old name -- and must still leave a log that only mentions the name. */
    {
        static const char RENAMED[] = "Village: Kalahuna Two (Save 1)\n";
        static const char TWICE[] = "Village: Third Name (Save 1)\n";
        char log3[MAX_PATH];
        wsprintfA(log3, "%s\\Virtual Villagers 1 Births and Conceptions Log 3.txt", pardir);

        write_text(log1, "Village: Kalahuna (Save 1)\nConception 1\n  Mother: A\n\n"
                         "Tribe renamed from Kalahuna to Kalahuna Two on 2026-10-04\n");
        write_text(pop1, "Virtual Villagers: A New Home Village Population\n"
                         "Village: Kalahuna (Save 1)\n\n1. Someone\n"
                         "Tribe renamed from Kalahuna to Kalahuna Two on 2026-10-04\n");
        /* The old name without a note: another village now, never erased. */
        write_text(log3, "Village: Kalahuna (Save 1)\nConception 2\n");
        check(exists(log1) && exists(pop1) && exists(log3),
              "renamed-village logs created (nonzero denominator)");
        vv_reset_slot_state(1, 1, RENAMED);
        check(!exists(log1), "A RENAMED VILLAGE'S BIRTHS LOG IS DELETED BY ITS START OVER");
        check(!exists(pop1), "a renamed village's population page is deleted by its Start Over");
        check(exists(log3), "a log still headed with the old name and no note SURVIVES");

        /* Renamed twice: the notes chain in order. */
        write_text(log1, "Village: Kalahuna (Save 1)\r\n"
                         "Tribe renamed from Kalahuna to Kalahuna Two on 2026-10-04\r\n"
                         "Conception 3\r\n"
                         "Tribe renamed from Kalahuna Two to Third Name on 2026-10-05\r\n");
        vv_reset_slot_state(1, 1, RENAMED);
        check(exists(log1), "after a second rename the middle name no longer matches");
        vv_reset_slot_state(1, 1, TWICE);
        check(!exists(log1), "A TWICE-RENAMED VILLAGE'S LOG IS DELETED UNDER ITS NEWEST NAME");

        /* A note for some other name is ignored. */
        write_text(log1, "Village: Kalahuna (Save 1)\n"
                         "Tribe renamed from Somebody Else to Kalahuna Two on 2026-10-04\n");
        vv_reset_slot_state(1, 1, RENAMED);
        check(exists(log1), "a note whose old name is not the header's is ignored");
        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(log1), "and the log still belongs to its own header's village");

        /* An indented line (inside a record) is not a note. */
        write_text(log1, "Village: Kalahuna (Save 1)\n"
                         "  Tribe renamed from Kalahuna to Kalahuna Two on 2026-10-04\n");
        vv_reset_slot_state(1, 1, RENAMED);
        check(exists(log1), "an indented look-alike line is not a note");
        DeleteFileA(log1);
        DeleteFileA(log3);
    }

    /* A BACKUP SURVIVES START OVER. The patcher's Back Up Saves copies the
       whole save folder into <save folder>\Backups\Backup <date>\, with the
       same file names and log subfolders. A Start Over of the backed-up
       village must leave every one of those copies alone: they are the
       player's way back. Each copy carries the erased village's own header,
       so only the location protects it. */
    {
        char bdir[MAX_PATH], blogs[MAX_PATH], bpop[MAX_PATH], bpar[MAX_PATH];
        char bmask[MAX_PATH], bstats[MAX_PATH], bsave[MAX_PATH];
        char bpop1[MAX_PATH], blog1[MAX_PATH];
        static const char ERASED_PAGE[] =
            "Virtual Villagers: A New Home Village Population\n"
            "Village: Kalahuna (Save 1)\n\n1. Someone\n";

        wsprintfA(bdir, "%s\\Backups", folder);
        CreateDirectoryA(bdir, NULL);
        wsprintfA(bdir, "%s\\Backups\\Backup 2026-10-04 13-05-22", folder);
        CreateDirectoryA(bdir, NULL);
        wsprintfA(blogs, "%s\\Virtual Villagers Fun Patcher Logs", bdir);
        CreateDirectoryA(blogs, NULL);
        wsprintfA(bpop, "%s\\Tribe Population", blogs);
        CreateDirectoryA(bpop, NULL);
        wsprintfA(bpar, "%s\\Births and Conceptions", blogs);
        CreateDirectoryA(bpar, NULL);
        wsprintfA(bmask, "%s\\vv1_masks_1.dat", bdir);
        wsprintfA(bstats, "%s\\Village Statistics - Save 1.txt", bdir);
        wsprintfA(bsave, "%s\\Virtual Villagers1.ldw", bdir);
        wsprintfA(bpop1, "%s\\Village Population 1.txt", bpop);
        wsprintfA(blog1, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", bpar);
        touch(bmask); touch(bstats); touch(bsave);
        write_text(bpop1, ERASED_PAGE);
        write_text(blog1, VILLAGE);
        /* and the live copies the reset should take, so it demonstrably ran */
        touch(mask1); touch(stats1); write_text(log1, VILLAGE); write_text(pop1, ERASED_PAGE);
        check(exists(bmask) && exists(bstats) && exists(bsave) && exists(bpop1)
              && exists(blog1), "backup copies created (nonzero denominator)");

        removed = vv_reset_slot_state(1, 1, VILLAGE);
        check(removed >= 4 && !exists(mask1) && !exists(stats1) && !exists(log1)
              && !exists(pop1), "the reset removed the live slot-1 files");
        check(exists(bmask) && exists(bstats) && exists(bsave) && exists(bpop1)
              && exists(blog1), "A BACKUP SURVIVES START OVER (every copied file)");
    }

    /* ONE FOLDER OF LOGS PER SAVE SLOT (native/shared/log_slot.h): Start Over removes, in the
       slot's own folder, exactly what it always removed in the shared one -- the erased village's
       Births and Conceptions, Deaths and Disappearances, Unaccounted Villagers and Island Events
       files (matched by header), its Population pages (by header) and the slot's Village
       Statistics -- and, since v1.35.79, everything else in that folder too (the Village History,
       the Repairs log, another village's file), but never another slot's. */
    {
        static const char *const SUBS[8] = {
            "Births and Conceptions", "Deaths and Disappearances", "Unaccounted Villagers", "Island Events",
            "Tribe Population", "Village Statistics", "Tribe History", "Repairs Made"
        };
        static const char *const NAMES[8] = {
            "Virtual Villagers 1 Births and Conceptions Log 1.txt", "Virtual Villagers 1 Deaths Log 1.txt",
            "Virtual Villagers 1 Unaccounted Villagers Log 1.txt", "Virtual Villagers 1 Island Events Log 1.txt",
            "Village Population 1.txt", "Village Statistics v2 - Save 1.txt", "Village History 1.txt",
            "Virtual Villagers 1 Repairs Log 1.txt"
        };
        char dir[MAX_PATH], rel[MAX_PATH], file[8][MAX_PATH], other[MAX_PATH], slot2[MAX_PATH], dir2[MAX_PATH];
        int k, gone = 1;
        for (k = 0; k < 8; ++k) {
            wsprintfA(rel, "Virtual Villagers Fun Patcher Logs\\Save 1\\%s", SUBS[k]);
            vv_save_subfolder(dir, rel, 96);
            wsprintfA(file[k], "%s\\%s", dir, NAMES[k]);
            if (k == 4) {
                write_text(file[k], "Virtual Villagers: A New Home Village Population\nVillage: Kalahuna (Save 1)\n\n");
            } else if (k == 6) {
                write_text(file[k], "=== Virtual Villagers 1 -- 2026-10-10 10:00:00 ===\nVillage: Kalahuna (Save 1)\n\n");
            } else {
                write_text(file[k], VILLAGE);
            }
        }
        /* Another village in the same slot (a tribe made over it with Change Tribe). */
        vv_save_subfolder(dir, "Virtual Villagers Fun Patcher Logs\\Save 1\\Births and Conceptions", 96);
        wsprintfA(other, "%s\\Virtual Villagers 1 Births and Conceptions Log 2.txt", dir);
        write_text(other, "Village: Someone Else (Save 1)\n");
        vv_save_subfolder(dir2, "Virtual Villagers Fun Patcher Logs\\Save 2\\Births and Conceptions", 96);
        wsprintfA(slot2, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", dir2);
        write_text(slot2, VILLAGE2);
        for (k = 0; k < 8; ++k) {
            gone = gone && exists(file[k]);
        }
        check(gone && exists(other) && exists(slot2), "slot-folder fixtures created (nonzero denominator)");

        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(file[0]) && !exists(file[1]) && !exists(file[2]) && !exists(file[3]),
              "START OVER REMOVES THE SLOT FOLDER'S BIRTHS, DEATHS, UNACCOUNTED AND ISLAND EVENTS LOGS OF THE VILLAGE");
        check(!exists(file[4]) && !exists(file[5]),
              "...and its Population page and the slot's Village Statistics, as in the shared folder");
        /* START OVER WIPES THE WHOLE SAVE (the owner, v1.35.79): the Village History, the Repairs log
           and a log of another village made in the same slot are the slot's too. */
        check(!exists(file[6]), "THE SLOT FOLDER'S VILLAGE HISTORY IS DELETED BY START OVER (v1.35.79)");
        check(!exists(file[7]), "...and its Repairs log");
        check(!exists(other), "...and every other log in the slot's folder");
        check(exists(slot2), "another slot's folder is untouched");
        /* A fresh slot's log folders are in the save's own folder (save_folder.c routes them; per_save.h). */
        check(strstr(file[0], "\\Virtual Villagers Fun Patcher\\Save 1\\Logs\\Births and Conceptions\\") != NULL
              && strstr(slot2, "\\Virtual Villagers Fun Patcher\\Save 2\\Logs\\Births and Conceptions\\") != NULL,
              "the slot folders above are in the save's own folder (...\\Virtual Villagers Fun Patcher\\Save <S>\\Logs)");
        for (k = 0; k < 8; ++k) {
            DeleteFileA(file[k]);
        }
        DeleteFileA(other);
        DeleteFileA(slot2);
    }

    /* ONE FOLDER PER SAVE (per_save.h): Start Over clears BOTH places -- the older layout's
       ("...Logs\Save <S>\...", "...Data\<kind>\...") and the save's own ("...Fun Patcher\Save <S>\...")
       -- and still nothing of another slot's in either. */
    {
        char old_dir[MAX_PATH], own_dir[MAX_PATH], p[MAX_PATH];
        char old_log[MAX_PATH], own_log[MAX_PATH], old_mask[MAX_PATH], own_mask[MAX_PATH];
        char old_mask2[MAX_PATH], own_mask2[MAX_PATH], own_stats[MAX_PATH], own_log2[MAX_PATH];
        static const char *const OLD_PARTS[] = {
            "Virtual Villagers Fun Patcher Logs", "Save 1", "Births and Conceptions", NULL
        };
        static const char *const OWN_PARTS[] = {
            "Virtual Villagers Fun Patcher", "Save 1", "Logs", "Births and Conceptions", NULL
        };
        int k;
        /* Made directly, not through the routing: both layouts at once, as a player's folder can be. */
        lstrcpyA(old_dir, folder);
        for (k = 0; OLD_PARTS[k] != NULL; ++k) {
            lstrcatA(old_dir, "\\");
            lstrcatA(old_dir, OLD_PARTS[k]);
            CreateDirectoryA(old_dir, NULL);
        }
        lstrcpyA(own_dir, folder);
        for (k = 0; OWN_PARTS[k] != NULL; ++k) {
            lstrcatA(own_dir, "\\");
            lstrcatA(own_dir, OWN_PARTS[k]);
            CreateDirectoryA(own_dir, NULL);
        }
        wsprintfA(old_log, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", old_dir);
        wsprintfA(own_log, "%s\\Virtual Villagers 1 Births and Conceptions Log 1.txt", own_dir);
        wsprintfA(own_log2, "%s\\Virtual Villagers 1 Births and Conceptions Log 2.txt", own_dir);
        write_text(old_log, VILLAGE);
        write_text(own_log, VILLAGE);
        write_text(own_log2, "Village: Someone Else (Save 1)\n");
        wsprintfA(p, "%s\\Virtual Villagers Fun Patcher\\Save 1\\Logs\\Village Statistics", folder);
        CreateDirectoryA(p, NULL);
        wsprintfA(own_stats, "%s\\Village Statistics v2 - Save 1.txt", p);
        touch(own_stats);
        wsprintfA(p, "%s\\Virtual Villagers Fun Patcher Data", folder);
        CreateDirectoryA(p, NULL);
        lstrcatA(p, "\\Village Masks");
        CreateDirectoryA(p, NULL);
        wsprintfA(old_mask, "%s\\Virtual Villagers 1 Village Masks - Save 1.dat", p);
        wsprintfA(old_mask2, "%s\\Virtual Villagers 1 Village Masks - Save 2.dat", p);
        wsprintfA(p, "%s\\Virtual Villagers Fun Patcher\\Save 1\\Data", folder);
        CreateDirectoryA(p, NULL);
        lstrcatA(p, "\\Village Masks");
        CreateDirectoryA(p, NULL);
        wsprintfA(own_mask, "%s\\Virtual Villagers 1 Village Masks - Save 1.dat", p);
        wsprintfA(p, "%s\\Virtual Villagers Fun Patcher\\Save 2", folder);
        CreateDirectoryA(p, NULL);
        lstrcatA(p, "\\Data");
        CreateDirectoryA(p, NULL);
        lstrcatA(p, "\\Village Masks");
        CreateDirectoryA(p, NULL);
        wsprintfA(own_mask2, "%s\\Virtual Villagers 1 Village Masks - Save 2.dat", p);
        touch(old_mask); touch(own_mask); touch(old_mask2); touch(own_mask2);
        check(exists(old_log) && exists(own_log) && exists(own_log2) && exists(own_stats) && exists(old_mask)
              && exists(own_mask) && exists(old_mask2) && exists(own_mask2),
              "both layouts' fixtures created (nonzero denominator)");

        vv_reset_slot_state(1, 1, VILLAGE);
        check(!exists(old_log) && !exists(own_log),
              "START OVER CLEARS THE VILLAGE'S LOG IN BOTH PLACES: the older layout's and the save's own");
        check(!exists(own_stats), "...and the slot's Village Statistics in the save's own folder");
        check(!exists(old_mask) && !exists(own_mask), "...and the slot's data file in both places");
        check(!exists(own_log2), "every log in the save's own folder goes, another village's too (v1.35.79)");
        check(exists(old_mask2) && exists(own_mask2), "another slot's data files are kept, in both places");
        DeleteFileA(own_log2);
        DeleteFileA(old_mask2);
        DeleteFileA(own_mask2);
    }

    full_wipe_cases(folder);

    /* Clean up what the harness made. */
    DeleteFileA(mask2); DeleteFileA(save1); DeleteFileA(other_game);
    DeleteFileA(stats2); DeleteFileA(pop2); DeleteFileA(log_other);

    printf("\n%s (%d failure%s)\n", failures ? "FAILED" : "OK",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
