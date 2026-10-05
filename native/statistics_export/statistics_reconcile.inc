/* THE FIRST-LOAD RECONCILE OF THE VILLAGE STATISTICS FILES (v1.35.58).
   Included by statistics_export.c, after everything it uses.

   The owner (2026-10-04): "I want everything to reconcile with the game
   saves."  This part of the first-load cross-check (native/shared/
   crosscheck_bridge.h) puts right what the save and the patcher's own logs
   PROVE about the two files this companion keeps per slot, and nothing
   else.  It never lowers a counter and never removes an Elder.

   WHAT IS PROVEN, AND WHAT IS DONE ABOUT IT.

     Village Elders (A New Home, The Secret City, The Tree of Life).  The
     list is "every villager ever seen with Master in three or more skills"
     (docs/village-statistics-directive.md).  Each save adds the LIVING ones
     itself; what it cannot see is an elder who died or left before the list
     existed.  The Village History log keeps every villager's skills at every
     save (truncated to whole numbers: a float skill is >= 88.0 exactly when
     its whole part is >= 88), so a villager a snapshot of THIS village shows
     with Master -- the game's own threshold, the one the save-time update
     uses: 90 in A New Home, 88 in the later games -- in three or more skills
     is an elder.  Each one whose name is on no line of the list, and who is
     not alive in the village now (the save adds the living ones), gets a
     closed line: "E -1 <name> <father> <mother> 0 0" -- seen alive holding
     the status, no longer in a record.  A name already on a line is never
     added again (names repeat: one line for a name is never doubled).
     The Lost Children counts its elders itself (the game's own counter, in
     the save): nothing to repair.  New Believers' snapshots list the
     Heathens too, with nothing that tells them apart -- the Heathen Chief
     has every skill at 100 -- so its History cannot prove a believer elder
     (owner: Heathens never count): reported, not repaired.

     Villagers Buried (all five games).  A lower bound: the Death records
     of this village in its Deaths log whose Grave line names a grave (not
     "no grave ..."), and the graves the memorial holds now.  The counter is
     raised to it when below.

     Twins Birthed (The Lost Children: the patcher's counter, counted at
     conception).  A lower bound: this village's Conception records with
     "Babies in pregnancy: 2".

     Chiefs Robed (The Secret City).  A lower bound: 1 while a robed Tribal
     Chief lives.

   Every other row prints a counter the GAME keeps in the save (Highest
   Population, Oldest Villager, Babies Made, ...), so the log always shows
   exactly the save's value; or one no save field or log can bound (Food
   Gathered, Debris Cleared, Heathens Converted -- the Arrived records'
   "Converted from the Heathens" also follows the Maker's conversions, which
   do not count).  Those are reported by scripts/vvfp_consistency_check.py.

   ONLY THIS VILLAGE'S FILES.  Nothing is asked about, and nothing changed,
   unless the slot's Village Roster says the files are this village's
   (village_changed: ROSTER_SAME); a different village's files are set aside
   by the save, as always.

   ASK FIRST.  VvfpStatsScanReconcile (scan: reads only) lists what it found
   for the prompt; VvfpStatsRepairReconcile takes the answer.  After Repair,
   at the next save -- after the flush and the living-elder update, before
   the log is written, so the log shows the result -- the plan is made again
   from the files as they are then, each file that changes is backed up
   ("<file>.before-v1.35.58-repair", never replacing one), every change is
   listed in the Repairs log (native/shared/repairs_log.h) BEFORE it is
   made, and the files are written atomically.  "Not now" changes nothing
   and the next load asks again.  No marker: once repaired, the scan finds
   nothing, so the question is never asked again for the same files. */

#include "repairs_log.h"

#define RC_NAME 40
#define RC_ELDERS_MAX 256
#define RC_TEXT_MAX (32u * 1024u * 1024u)

struct rc_elder {
    char name[RC_NAME];
    char father[RC_NAME];
    char mother[RC_NAME];
};

struct rc_plan {
    int elders_ok;                 /* the elders file was read (or is not there yet) */
    int elders_add;
    struct rc_elder elders[RC_ELDERS_MAX];
    int counters_ok;               /* the counters file was read */
    long long buried_was, buried_to;
    long long twins_was, twins_to;
    long long chiefs_was, chiefs_to;
    int changes;
};

/* The player's answer, per slot, this session. */
static signed char g_rc_repair[6];

/* ---- reading the logs ---------------------------------------------------- */

/* A whole file, NUL-terminated, or NULL (`*missing` 1 when it is not there). */
static char *rc_read(const wchar_t *path, int *missing) {
    HANDLE f;
    DWORD size, got = 0;
    char *text;
    *missing = 0;
    f = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError();
        *missing = e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND;
        return NULL;
    }
    size = GetFileSize(f, NULL);
    if (size == INVALID_FILE_SIZE || size > RC_TEXT_MAX) {
        CloseHandle(f);
        return NULL;
    }
    text = (char *)malloc((size_t)size + 1u);
    if (text == NULL || !(ReadFile(f, text, size, &got, NULL) && got == size)) {
        free(text);
        CloseHandle(f);
        return NULL;
    }
    CloseHandle(f);
    text[size] = '\0';
    return text;
}

/* The next line of `*cursor` without its line end, or NULL at the end. */
static char *rc_line(char **cursor) {
    char *start = *cursor;
    char *end;
    if (start == NULL || *start == '\0') {
        return NULL;
    }
    end = strchr(start, '\n');
    if (end != NULL) {
        *end = '\0';
        *cursor = end + 1;
    } else {
        *cursor = start + strlen(start);
    }
    end = start + strlen(start);
    while (end > start && (end[-1] == '\r' || end[-1] == ' ')) {
        *--end = '\0';
    }
    return start;
}

/* Every numbered file "<stem> <n>.txt" in the logs subfolder `sub`, in
   number order, handed to `visit`.  The directory is asked (never a run of
   numbers guessed: resets leave gaps).  1 read, 0 a file could not be read
   (nothing may then be decided). */
typedef void (*rc_visit_fn)(char *text, void *context);

static int rc_each_log(const wchar_t *sub, const wchar_t *stem, rc_visit_fn visit, void *context) {
    wchar_t folder[MAX_PATH];
    wchar_t pattern[MAX_PATH];
    wchar_t path[MAX_PATH];
    WIN32_FIND_DATAW found;
    HANDLE find;
    int numbers[4096];
    int count = 0;
    int i, j;
    size_t stem_len = wcslen(stem);
    if (!vv_save_subfolder_w(folder, sub, 64)
        || _snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%ls\\%ls *.txt", folder, stem) < 0) {
        return 0;
    }
    find = FindFirstFileW(pattern, &found);
    if (find != INVALID_HANDLE_VALUE) {
        do {
            const wchar_t *p = found.cFileName + stem_len;
            int n = 0;
            if (wcsncmp(found.cFileName, stem, stem_len) != 0 || *p != L' ' || p[1] < L'1' || p[1] > L'9') {
                continue;
            }
            for (++p; *p >= L'0' && *p <= L'9' && n < 100000; ++p) {
                n = n * 10 + (*p - L'0');
            }
            if (wcscmp(p, L".txt") == 0 && count < 4096) {
                numbers[count++] = n;
            }
        } while (FindNextFileW(find, &found));
        FindClose(find);
    }
    for (i = 1; i < count; ++i) {
        for (j = i; j > 0 && numbers[j - 1] > numbers[j]; --j) {
            int t = numbers[j];
            numbers[j] = numbers[j - 1];
            numbers[j - 1] = t;
        }
    }
    for (i = 0; i < count; ++i) {
        int missing;
        char *text;
        if (_snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%ls\\%ls %d.txt", folder, stem, numbers[i]) < 0) {
            return 0;
        }
        text = rc_read(path, &missing);
        if (text == NULL) {
            if (missing) {
                continue;             /* gone since the listing */
            }
            return 0;
        }
        visit(text, context);
        free(text);
    }
    return 1;
}

struct rc_count {
    const char *village;          /* "Village: <name> (Save S)" */
    int game;
    long long graves;             /* Death records with a grave */
    long long twins;              /* Conception records of twins */
};

/* The Deaths log: "Death <n>" records under this village's header whose
   "  Grave:" line names a grave. */
static void rc_visit_deaths(char *text, void *context) {
    struct rc_count *c = (struct rc_count *)context;
    char *cursor = text;
    char *line;
    int ours = 0, open = 0, grave = 0;
    while ((line = rc_line(&cursor)) != NULL) {
        if (strncmp(line, "Village:", 8) == 0) {
            c->graves += open && grave;
            open = grave = 0;
            ours = strcmp(line, c->village) == 0;
            continue;
        }
        if (line[0] != ' ') {
            c->graves += open && grave;
            open = ours && strncmp(line, "Death ", 6) == 0 && line[6] >= '0' && line[6] <= '9';
            grave = 0;
            continue;
        }
        if (open && strncmp(line, "  Grave: ", 9) == 0) {
            grave = strncmp(line + 9, "no grave", 8) != 0 && line[9] != '\0';
        }
    }
    c->graves += open && grave;
}

/* The Births and Conceptions log: this village's "Conception <n>" records
   with "  Babies in pregnancy: 2". */
static void rc_visit_births(char *text, void *context) {
    struct rc_count *c = (struct rc_count *)context;
    char *cursor = text;
    char *line;
    int ours = 0, open = 0;
    while ((line = rc_line(&cursor)) != NULL) {
        if (strncmp(line, "Village:", 8) == 0) {
            ours = strcmp(line, c->village) == 0;
            open = 0;
            continue;
        }
        if (line[0] != ' ') {
            open = ours && strncmp(line, "Conception ", 11) == 0;
            continue;
        }
        if (open && strcmp(line, "  Babies in pregnancy: 2") == 0) {
            ++c->twins;
            open = 0;
        }
    }
}

/* ---- the Village History log --------------------------------------------- */

struct rc_history {
    const char *village;
    int game;
    int master;
    /* Excluded: on a line of the elders list, or alive now. */
    char (*taken)[RC_NAME];
    int taken_count;
    struct rc_plan *plan;
};

static int rc_name_in(char (*names)[RC_NAME], int count, const char *name) {
    int i;
    for (i = 0; i < count; ++i) {
        if (strcmp(names[i], name) == 0) {
            return 1;
        }
    }
    return 0;
}

static void rc_copy(char *out, const char *in) {
    int i;
    for (i = 0; i < RC_NAME - 1 && in[i] != '\0'; ++i) {
        out[i] = (in[i] == '\t' || in[i] == '\r' || in[i] == '\n') ? ' ' : in[i];
    }
    out[i] = '\0';
}

/* One villager of a snapshot of this village, finished: an elder? */
static void rc_history_villager(struct rc_history *h, const struct rc_elder *v, int mastered, int whole) {
    struct rc_plan *p = h->plan;
    int i;
    if (!whole || mastered < 3 || v->name[0] == '\0' || rc_name_in(h->taken, h->taken_count, v->name)) {
        return;
    }
    for (i = 0; i < p->elders_add; ++i) {
        const struct rc_elder *e = &p->elders[i];
        if (strcmp(e->name, v->name) == 0 && strcmp(e->father, v->father) == 0
            && strcmp(e->mother, v->mother) == 0) {
            return;                   /* the same villager, in another snapshot */
        }
    }
    if (p->elders_add < RC_ELDERS_MAX) {
        p->elders[p->elders_add++] = *v;
    }
}

static void rc_visit_history(char *text, void *context) {
    struct rc_history *h = (struct rc_history *)context;
    char *cursor = text;
    char *line;
    int ours = 0, expect_village = 0;
    int open = 0, section = 0;    /* 1 Parents, 2 Skills */
    int mastered = 0, skills = 0;
    struct rc_elder v;
    memset(&v, 0, sizeof v);
    while ((line = rc_line(&cursor)) != NULL) {
        int top = line[0] != ' ';
        if (top) {
            if (open) {
                rc_history_villager(h, &v, mastered, skills > 0);
            }
            open = 0;
            section = 0;
            if (strncmp(line, "=== ", 4) == 0) {
                ours = 0;
                expect_village = 1;
                continue;
            }
            if (expect_village && line[0] != '\0') {
                expect_village = 0;
                ours = strcmp(line, h->village) == 0;
                continue;
            }
            if (ours && strncmp(line, "Villager ", 9) == 0) {
                open = 1;
                mastered = skills = 0;
                memset(&v, 0, sizeof v);
            }
            continue;
        }
        if (!open) {
            continue;
        }
        if (strncmp(line, "  ", 2) == 0 && line[2] != ' ') {
            section = 0;
            if (strncmp(line, "  Name: ", 8) == 0) {
                rc_copy(v.name, line + 8);
            } else if (strcmp(line, "  Parents:") == 0) {
                section = 1;
            } else if (strcmp(line, "  Skills:") == 0) {
                section = 2;
            }
            continue;
        }
        if (section == 1 && h->game != GAME_VV1) {
            /* A New Home's lines keep no parents (the record has none). */
            if (strncmp(line, "    Father: ", 12) == 0) {
                rc_copy(v.father, line + 12);
            } else if (strncmp(line, "    Mother: ", 12) == 0) {
                rc_copy(v.mother, line + 12);
            }
        } else if (section == 2 && strncmp(line, "    ", 4) == 0) {
            const char *last = strrchr(line, ' ');
            char *stop = NULL;
            long value = last != NULL ? strtol(last + 1, &stop, 10) : 0;
            if (last != NULL && stop != NULL && *stop == '\0' && stop != last + 1) {
                ++skills;
                mastered += value >= h->master;
            }
        }
    }
    if (open) {
        rc_history_villager(h, &v, mastered, skills > 0);
    }
}

/* ---- the plan -------------------------------------------------------------- */

static int rc_elders_path(int slot, wchar_t *path) {
    wchar_t folder[MAX_PATH];
    return vv_save_subfolder_w(folder, L"Virtual Villagers Fun Patcher Data\\Village Elders", 64)
        && _snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%ls\\Village Elders - Save %d.dat", folder, slot) > 0;
}

/* The names on the elders list (field 3 of every line), into `taken`;
   1 read (or no file yet), 0 not a list this companion would read. */
static int rc_elder_names(int game, int slot, char (*taken)[RC_NAME], int *count, int capacity) {
    wchar_t path[MAX_PATH];
    char header[64];
    char *text, *cursor, *line;
    int missing;
    if (!rc_elders_path(slot, path)) {
        return 0;
    }
    text = rc_read(path, &missing);
    if (text == NULL) {
        return missing;
    }
    cursor = text;
    _snprintf_s(header, sizeof header, _TRUNCATE, "VVFP VILLAGE ELDERS v2 game=%d", game);
    line = rc_line(&cursor);
    if (line == NULL || strcmp(line, header) != 0 || (line = rc_line(&cursor)) == NULL
        || strncmp(line, "graves_seen=", 12) != 0) {
        free(text);
        return 0;
    }
    while ((line = rc_line(&cursor)) != NULL) {
        char *a, *b;
        if (line[0] == '\0') {
            continue;
        }
        a = strchr(line, '\t');
        b = a != NULL ? strchr(a + 1, '\t') : NULL;
        if ((line[0] != 'E' && line[0] != 'G') || b == NULL) {
            free(text);
            return 0;
        }
        a = b + 1;
        b = strchr(a, '\t');
        if (b == NULL) {
            free(text);
            return 0;
        }
        *b = '\0';
        if (*count < capacity) {
            rc_copy(taken[(*count)++], a);
        }
    }
    free(text);
    return 1;
}

/* What the files and the save prove for `slot`'s village `village` (its
   header line, no line end), against the counters file at `counters`.
   `context` reaches the game (the memorial; The Secret City's chief). */
static void rc_make_plan(int game, int slot, const char *village, const wchar_t *counters,
                         const vvs_context *context, struct rc_plan *plan) {
    static char taken[RC_ELDERS_MAX * 4 + ROSTER_MAX][RC_NAME];
    int taken_count = 0;
    int i;
    memset(plan, 0, sizeof *plan);
    plan->buried_was = plan->twins_was = plan->chiefs_was = -1;

    /* Village Elders, from the Village History log. */
    if (game == GAME_VV1 || game == GAME_VV3 || game == GAME_VV4) {
        plan->elders_ok = rc_elder_names(game, slot, taken, &taken_count, RC_ELDERS_MAX * 4);
        if (plan->elders_ok) {
            struct rc_history h;
            /* The living (the save adds their lines itself). */
            for (i = 0; i < g_roster_now_count && taken_count < RC_ELDERS_MAX * 4 + ROSTER_MAX; ++i) {
                const char *a = strchr(g_roster_now[i], '\t');
                const char *b = a != NULL ? strchr(a + 1, '\t') : NULL;
                if (b != NULL && b - a - 1 < RC_NAME) {
                    memcpy(taken[taken_count], a + 1, (size_t)(b - a - 1));
                    taken[taken_count][b - a - 1] = '\0';
                    ++taken_count;
                }
            }
            memset(&h, 0, sizeof h);
            h.village = village;
            h.game = game;
            h.master = game == GAME_VV1 ? 90 : 88;
            h.taken = taken;
            h.taken_count = taken_count;
            h.plan = plan;
            if (!rc_each_log(L"Virtual Villagers Fun Patcher Logs\\Tribe History", L"Village History",
                             rc_visit_history, &h)) {
                plan->elders_ok = 0;
                plan->elders_add = 0;
            }
        }
    }

    /* The counters. */
    {
        struct rc_count c;
        wchar_t stem[64];
        const char *key;
        long long value;
        int state;
        memset(&c, 0, sizeof c);
        c.village = village;
        c.game = game;
        _snwprintf_s(stem, 64, _TRUNCATE, L"Virtual Villagers %d Deaths Log", game);
        plan->counters_ok = rc_each_log(L"Virtual Villagers Fun Patcher Logs\\Deaths", stem, rc_visit_deaths, &c);
        _snwprintf_s(stem, 64, _TRUNCATE, L"Virtual Villagers %d Births and Conceptions Log", game);
        if (game == GAME_VV2 && plan->counters_ok) {
            plan->counters_ok = rc_each_log(L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions", stem,
                                            rc_visit_births, &c);
        }
        if (plan->counters_ok) {
            int graves = vvs_memorial_graves(context);
            if ((long long)graves > c.graves) {
                c.graves = graves;
            }
            key = vvs_counter_key(game, VVS_BURIED);
            state = vvs_counter_peek(counters, game, key, &value);
            plan->counters_ok = state == VVS_FILE_OK;
            if (state == VVS_FILE_OK && value >= 0 && value < c.graves) {
                plan->buried_was = value;
                plan->buried_to = c.graves;
            }
            if (game == GAME_VV2 && state == VVS_FILE_OK
                && vvs_counter_peek(counters, game, vvs_counter_key(game, VVS_TWINS), &value) == VVS_FILE_OK
                && value >= 0 && value < c.twins) {
                plan->twins_was = value;
                plan->twins_to = c.twins;
            }
            if (game == GAME_VV3 && state == VVS_FILE_OK && vvs_living_chief(context)
                && vvs_counter_peek(counters, game, vvs_counter_key(game, VVS_CHIEFS), &value) == VVS_FILE_OK
                && value >= 0 && value < 1) {
                plan->chiefs_was = value;
                plan->chiefs_to = 1;
            }
        }
    }
    plan->changes = plan->elders_add + (plan->buried_was >= 0) + (plan->twins_was >= 0) + (plan->chiefs_was >= 0);
}

static void rc_trim(char *s) {
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
        s[--n] = '\0';
    }
}

/* The header of the village the slot's own save holds ("VVFP Save
   Reset.dll" beside the executable; loaded by full path). */
static int rc_saved_header(int game, int slot, char *out, int size) {
    typedef int (__stdcall *saved_header_fn)(int, int, char *, int);
    static const wchar_t file[] = L"VVFP Save Reset.dll";
    wchar_t path[MAX_PATH];
    wchar_t *slash;
    DWORD n;
    HMODULE module = GetModuleHandleW(file);
    saved_header_fn header;
    if (module == NULL) {
        n = GetModuleFileNameW(NULL, path, MAX_PATH);
        slash = n != 0 && n < MAX_PATH ? wcsrchr(path, L'\\') : NULL;
        if (slash == NULL || (size_t)(slash + 1 - path) + sizeof(file) / sizeof(file[0]) > MAX_PATH) {
            return 0;
        }
        wcscpy(slash + 1, file);
        module = LoadLibraryW(path);
        if (module == NULL) {
            return 0;
        }
    }
    header = (saved_header_fn)GetProcAddress(module, "SavedVillageHeader");
    if (header == NULL || !header(game, slot, out, size)) {
        return 0;
    }
    rc_trim(out);
    return strncmp(out, "Village: ", 9) == 0;
}

/* The prompt's lines for a plan. */
static void rc_describe(const struct rc_plan *p, char *text, int cap) {
    char line[512];
    text[0] = '\0';
    if (p->elders_add > 0) {
        _snprintf_s(line, sizeof line, _TRUNCATE,
                    "- %d %s the Village History log shows as %s (Master in 3 or more skills) %s missing from "
                    "the Village Elders list. %s will be added.\r\n",
                    p->elders_add, p->elders_add == 1 ? "villager" : "villagers",
                    p->elders_add == 1 ? "a Village Elder" : "Village Elders",
                    p->elders_add == 1 ? "is" : "are", p->elders_add == 1 ? "It" : "They");
        strncat_s(text, (size_t)cap, line, _TRUNCATE);
    }
    if (p->buried_was >= 0) {
        _snprintf_s(line, sizeof line, _TRUNCATE,
                    "- Villagers Buried is %I64d, but the Deaths log and the graves show %I64d burials. It will be "
                    "raised to %I64d.\r\n", p->buried_was, p->buried_to, p->buried_to);
        strncat_s(text, (size_t)cap, line, _TRUNCATE);
    }
    if (p->twins_was >= 0) {
        _snprintf_s(line, sizeof line, _TRUNCATE,
                    "- Twins Birthed is %I64d, but the Births log records %I64d twin pregnancies. It will be "
                    "raised to %I64d.\r\n", p->twins_was, p->twins_to, p->twins_to);
        strncat_s(text, (size_t)cap, line, _TRUNCATE);
    }
    if (p->chiefs_was >= 0) {
        strncat_s(text, (size_t)cap,
                  "- Chiefs Robed is 0, but a robed Tribal Chief lives. It will be raised to 1.\r\n", _TRUNCATE);
    }
}

/* ---- the scan and the answer -------------------------------------------- */

/* VvfpStatsScanReconcile(game, slot, text, cap): what the Village
   Statistics and Village Elders files of the slot's village are missing
   that the save and the logs prove -- the number of changes, with the
   prompt's lines in `text`; 0 nothing (or the files are not this
   village's); -1 cannot tell now.  Reads only. */
__declspec(dllexport) int __stdcall VvfpStatsScanReconcile(int game, int slot, char *text, int cap) {
    static struct rc_plan plan;
    char village[VV_VILLAGE_NAME_MAX + 32];
    wchar_t counters[MAX_PATH], stews[MAX_PATH];
    vvs_context context;
    int roster;
    if (text == NULL || cap < 2 || game < GAME_VV1 || game > GAME_VV5 || slot < 1 || slot > 5) {
        return -1;
    }
    text[0] = '\0';
    roster = village_changed(game, slot);
    if (roster == ROSTER_LOCKED || g_roster_now_count == 0) {
        return -1;                    /* the village is not in the records yet, or the roster is locked */
    }
    if (roster != ROSTER_SAME) {
        return 0;                     /* another village's files: the save sets them aside */
    }
    if (!rc_saved_header(game, slot, village, (int)sizeof village)
        || !vvs_build_paths(game, slot, counters, stews)) {
        return -1;
    }
    memset(&context, 0, sizeof context);
    context.game_id = game;
    context.module = (unsigned char *)GetModuleHandleW(NULL);
    rc_make_plan(game, slot, village, counters, &context, &plan);
    if (plan.changes > 0) {
        rc_describe(&plan, text, cap);
    }
    return plan.changes;
}

__declspec(dllexport) void __stdcall VvfpStatsRepairReconcile(int game, int slot, int repair) {
    if (game < GAME_VV1 || game > GAME_VV5 || slot < 1 || slot > 5) {
        return;
    }
    g_rc_repair[slot] = (signed char)(repair != 0);
}

/* Append the closed lines to the elders file (rewritten whole, atomically). */
static int rc_write_elders(int slot, const struct rc_plan *p) {
    wchar_t path[MAX_PATH], temporary[MAX_PATH];
    char *text, *grown;
    size_t len, cap;
    int missing, i;
    HANDLE f;
    DWORD put = 0;
    if (!rc_elders_path(slot, path) || _snwprintf_s(temporary, MAX_PATH, _TRUNCATE, L"%ls.reconcile.tmp", path) < 0) {
        return 0;
    }
    text = rc_read(path, &missing);
    if (text == NULL) {
        return 0;                     /* the save writes the file first: not there is a failure here */
    }
    len = strlen(text);
    cap = len + (size_t)p->elders_add * (3u * RC_NAME + 32u) + 4u;
    grown = (char *)realloc(text, cap);
    if (grown == NULL) {
        free(text);
        return 0;
    }
    text = grown;
    if (len > 0 && text[len - 1] != '\n') {
        lstrcpyA(text + len, "\r\n");
        len += 2;
    }
    for (i = 0; i < p->elders_add; ++i) {
        const struct rc_elder *e = &p->elders[i];
        len += (size_t)_snprintf_s(text + len, cap - len, _TRUNCATE, "E\t-1\t%s\t%s\t%s\t0\t0\r\n",
                                   e->name, e->father, e->mother);
    }
    f = CreateFileW(temporary, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (f == INVALID_HANDLE_VALUE) {
        free(text);
        return 0;
    }
    if (!WriteFile(f, text, (DWORD)len, &put, NULL) || put != (DWORD)len || !FlushFileBuffers(f)) {
        CloseHandle(f);
        DeleteFileW(temporary);
        free(text);
        return 0;
    }
    CloseHandle(f);
    free(text);
    if (!MoveFileExW(temporary, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileW(temporary);
        return 0;
    }
    return 1;
}

static void rc_leaf(char *out, size_t n, const wchar_t *path) {
    const wchar_t *slash = wcsrchr(path, L'\\');
    _snprintf_s(out, n, _TRUNCATE, "%ls", slash != NULL ? slash + 1 : path);
}

/* At a save of `slot` after Repair (from WriteVillageStatistics, after the
   elders update): make the plan again, back up, note, change.  The answer
   is kept until the changes are on disk, so a failure is retried by the
   next save. */
static void rc_apply(int game, int slot, unsigned char *manager) {
    static struct rc_plan plan;
    char name[VV_VILLAGE_NAME_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    wchar_t elders[MAX_PATH], elders_backup[MAX_PATH], counters_backup[MAX_PATH];
    char *body;
    char leaf[MAX_PATH];
    size_t cap, len = 0;
    int none, i, ok = 1;
    if (!g_rc_save_ok || slot < 1 || slot > 5 || !g_rc_repair[slot]) {
        return;
    }
    if (!vv_village_name(game, manager, name) || !vv_village_header(village, sizeof village, name, slot)) {
        return;
    }
    rc_trim(village);
    rc_make_plan(game, slot, village, g_store.counters_path, &g_store, &plan);
    if (plan.changes == 0) {
        g_rc_repair[slot] = 0;        /* nothing left to do */
        return;
    }
    elders_backup[0] = counters_backup[0] = L'\0';
    if (plan.elders_add > 0 && (!rc_elders_path(slot, elders)
                                || !vv_repair_backup(elders, elders_backup, MAX_PATH, &none) || none)) {
        return;
    }
    if (plan.buried_was >= 0 || plan.twins_was >= 0 || plan.chiefs_was >= 0) {
        if (!vv_repair_backup(g_store.counters_path, counters_backup, MAX_PATH, &none) || none) {
            if (elders_backup[0]) {
                DeleteFileW(elders_backup);
            }
            return;
        }
    }
    cap = (size_t)plan.elders_add * (RC_NAME * 3 + 96) + 2048;
    body = (char *)malloc(cap);
    if (body == NULL) {
        ok = 0;
    } else {
        body[0] = '\0';
        for (i = 0; i < plan.elders_add; ++i) {
            const struct rc_elder *e = &plan.elders[i];
            char parents[2 * RC_NAME + 32];
            parents[0] = '\0';
            if (e->father[0] || e->mother[0]) {
                _snprintf_s(parents, sizeof parents, _TRUNCATE, " (father %s, mother %s)",
                            e->father[0] ? e->father : "(none)", e->mother[0] ? e->mother : "(none)");
            }
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Village Elder added: %s%s -- Master in 3 or more skills in the "
                                       "Village History log\r\n", e->name, parents);
        }
        if (plan.buried_was >= 0) {
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Villagers Buried raised: %I64d -> %I64d (the Deaths log and the graves)\r\n",
                                       plan.buried_was, plan.buried_to);
        }
        if (plan.twins_was >= 0) {
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Twins Birthed raised: %I64d -> %I64d (twin conceptions in the Births log)\r\n",
                                       plan.twins_was, plan.twins_to);
        }
        if (plan.chiefs_was >= 0) {
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE,
                                       "  Chiefs Robed raised: %I64d -> 1 (a robed Tribal Chief lives)\r\n",
                                       plan.chiefs_was);
        }
        if (elders_backup[0]) {
            rc_leaf(leaf, sizeof leaf, elders_backup);
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE, "  Backup: %s\r\n", leaf);
        }
        if (counters_backup[0]) {
            rc_leaf(leaf, sizeof leaf, counters_backup);
            len += (size_t)_snprintf_s(body + len, cap - len, _TRUNCATE, "  Backup: %s\r\n", leaf);
        }
        ok = vv_repairs_note(game, village,
                             "the Village Elders and Village Statistics files, against the Village History, "
                             "Deaths and Births logs and the save", body);
        free(body);
    }
    if (!ok) {
        /* No note, no change: this call's own backups go again. */
        if (elders_backup[0]) {
            DeleteFileW(elders_backup);
        }
        if (counters_backup[0]) {
            DeleteFileW(counters_backup);
        }
        return;
    }
    {
        long long was;
        int done = 1;
        if (plan.elders_add > 0) {
            if (rc_write_elders(slot, &plan)) {
                if (g_elders_ready && g_elders_value >= 0) {
                    g_elders_value += plan.elders_add;
                }
            } else {
                done = 0;
            }
        }
        if (plan.buried_was >= 0
            && vvs_counter_raise(g_store.counters_path, game, vvs_counter_key(game, VVS_BURIED), plan.buried_to, &was) < 0) {
            done = 0;
        }
        if (plan.twins_was >= 0
            && vvs_counter_raise(g_store.counters_path, game, vvs_counter_key(game, VVS_TWINS), plan.twins_to, &was) < 0) {
            done = 0;
        }
        if (plan.chiefs_was >= 0
            && vvs_counter_raise(g_store.counters_path, game, vvs_counter_key(game, VVS_CHIEFS), plan.chiefs_to, &was) < 0) {
            done = 0;
        }
        if (done) {
            g_rc_repair[slot] = 0;
        }
    }
}
