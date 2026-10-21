/* THE FIRST-LOAD RECONCILE OF THE VILLAGE STATISTICS FILES (v1.35.58).
   Included by statistics_export.c, after everything it uses.

   The owner (2026-10-04): "I want everything to reconcile with the game
   saves."  This part of the first-load cross-check (native/shared/
   crosscheck_bridge.h) puts right what the save and the patcher's own logs
   PROVE about the two files this companion keeps per slot, and nothing
   else.  It never lowers a counter and never removes an Elder.

   WHAT IS PROVEN, AND WHAT IS DONE ABOUT IT.

     Village Elders (A New Home, The Secret City, The Tree of Life, New
     Believers).  The
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
     Heathens too -- the Heathen Chief has every skill at 100 -- and
     Heathens never count (owner): only a villager its snapshot calls
     "Faction: Believer" (population_export.c) is an elder there; a
     snapshot written before that line proves nothing.

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

   ASK FIRST.  VvfpStatisticsScanReconcile (scan: reads only) lists what it found
   for the cross-check (native/shared/crosscheck_bridge.h), which never asks
   while a village is played; VvfpStatisticsRepairReconcile takes the player's
   go-ahead given before a save (Repair Saves & Logs), VvfpStatisticsRepairReconcileNow
   a Repair answered right after the quit save.  After Repair,
   at the next save -- after the flush and the living-elder update, before
   the log is written, so the log shows the result -- the plan is made again
   from the files as they are then, each file that changes is backed up
   ("<file>.before-v1.35.58-repair", never replacing one), every change is
   listed in the Repairs log (native/shared/repairs_log.h) BEFORE it is
   made, and the files are written atomically.  "Not now" changes nothing
   and the next quit asks again.  No marker: once repaired, the scan finds
   nothing, so the question is never asked again for the same files. */

#include "repairs_log.h"

#define RC_NAME 40
#define RC_ELDERS_MAX 256
#define RC_TEXT_MAX (32u * 1024u * 1024u)

struct rc_elder {
    char name[RC_NAME];
    char father[RC_NAME];
    char mother[RC_NAME];
    int head, body;                /* as the History snapshot says (-1: not said); never written */
};

/* EVERY ELDER EXACTLY ONCE, BY WHO THEY ARE (the identity audit).  A History snapshot's elder used
   to be left out when anybody on the elders list or alive now had the same name, or a name it
   "grew" into ("Gata" -> "Gata Bahati"): a dead elder whose namesake lives was never counted.  Now:
     - a line of the elders list counts one History elder of its name and parents (A New Home keeps
       no parents), each line once -- a line still open is a living elder, never a dead one's;
     - a History elder with a Death or Disappeared record of her own name, head and body is a
       departed villager: counted unless a closed line already counts her;
     - only one with no such record may be a listed or living villager under a newer or older name
       (a last name or a number added or dropped, the same parents), and is then not added. */
struct rc_known {
    char name[RC_NAME];
    char father[RC_NAME];
    char mother[RC_NAME];
    unsigned char list;            /* 1 a line of the elders list, 0 a living villager */
    unsigned char open;            /* a list line still open: a living elder */
    unsigned char used;            /* this line already counts a History elder */
};

struct rc_departed {
    char name[RC_NAME];
    int head, body;
};
#define RC_DEPARTED_MAX 4096

struct rc_plan {
    int elders_ok;                 /* the elders file was read (or is not there yet) */
    int blocked;                   /* a log or the counters file could not be read now (a lock):
                                      the scan cannot tell yet */
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
/* A quit-time repair changed the files, but the Village Statistics log has
   not been written again since: the next ...ReconcileNow writes it. */
static signed char g_rc_log_pending[6];

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

/* `folder` is absolute and is only read (never made: a reader names each place itself, and
   vv_save_subfolder_w would route a slot's older folder to the save's own -- per_save.h). */
static int rc_each_log(const wchar_t *folder, const wchar_t *stem, rc_visit_fn visit, void *context) {
    wchar_t pattern[MAX_PATH];
    wchar_t path[MAX_PATH];
    WIN32_FIND_DATAW found;
    HANDLE find;
    int numbers[4096];
    int count = 0;
    int i, j;
    size_t stem_len = wcslen(stem);
    if (_snwprintf_s(pattern, MAX_PATH, _TRUNCATE, L"%ls\\%ls *.txt", folder, stem) < 0) {
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

/* ONE FOLDER OF LOGS PER SAVE SLOT (native/shared/log_slot.h): a village's logs of `sub_name`
   ("Tribe History") are the shared folder older builds wrote, then its slot's own
   "...Logs\Save <slot>\<sub_name>" -- one history, oldest first; each record is still kept only
   under this village's header by `visit`.  `old_name` is an older build's name for the shared
   folder (read before it; NULL none).  A folder that is not there is skipped and never made; one
   that cannot be examined decides nothing (0). */
static int rc_each_slot_log(const wchar_t *sub_name, const wchar_t *old_name, const wchar_t *stem, int slot,
                            rc_visit_fn visit, void *context) {
    /* ...and after the slot's older folder, the save's own "Virtual Villagers Fun Patcher\Save <slot>\
       Logs\<sub_name>" (per_save.h): log_slot.h's reading order. */
    wchar_t root[MAX_PATH], folders[VV_LOG_READ_MAX][MAX_PATH];
    int n, i;
    int valid = slot >= 1 && slot <= VV_LOG_SLOTS;
    if (!vv_save_folder_w(root, 64)) {
        return 0;
    }
    n = vv_log_read_folders_w(root, sub_name, old_name, valid ? slot : 1, folders, VV_LOG_READ_MAX);
    if (!valid && n > (old_name != NULL ? 2 : 1)) {
        n = old_name != NULL ? 2 : 1;            /* no slot: the shared folders only, as before */
    }
    for (i = 0; i < n; ++i) {
        int kind = vv_layout_probe_w(folders[i], NULL);
        if (kind == VV_LAYOUT_UNKNOWN) {
            return 0;
        }
        if (kind == VV_LAYOUT_DIR && !rc_each_log(folders[i], stem, visit, context)) {
            return 0;
        }
    }
    return 1;
}

struct rc_count {
    const char *village;          /* "Village: <name> (Save S)" */
    int game;
    long long graves;             /* Death records with a grave */
    long long twins;              /* Conception records of twins */
    /* Each Death record with a grave counted so far, by its whole text: the
       Deaths logs are read from both "Deaths" and "Deaths and
       Disappearances" when both exist (rc_make_plan), and a record found in
       both is one burial, not two. */
    unsigned long long *seen;
    int seen_count, seen_cap;
};

static unsigned long long rc_hash_line(unsigned long long h, const char *line) {
    for (; *line != '\0'; ++line) {
        h = (h ^ (unsigned char)*line) * 1099511628211ull;      /* FNV-1a */
    }
    return (h ^ (unsigned char)'\n') * 1099511628211ull;
}

/* One grave, unless the very same record was counted already. */
static void rc_count_grave(struct rc_count *c, unsigned long long record) {
    int i;
    for (i = 0; i < c->seen_count; ++i) {
        if (c->seen[i] == record) {
            return;
        }
    }
    if (c->seen_count == c->seen_cap) {
        int cap = c->seen_cap ? c->seen_cap * 2 : 64;
        unsigned long long *more = (unsigned long long *)realloc(c->seen, (size_t)cap * sizeof *more);
        if (more == NULL) {
            ++c->graves;              /* counted, if not remembered */
            return;
        }
        c->seen = more;
        c->seen_cap = cap;
    }
    c->seen[c->seen_count++] = record;
    ++c->graves;
}

/* The Deaths log: "Death <n>" records under this village's header whose
   "  Grave:" line names a grave. */
static void rc_visit_deaths(char *text, void *context) {
    struct rc_count *c = (struct rc_count *)context;
    char *cursor = text;
    char *line;
    int ours = 0, open = 0, grave = 0;
    unsigned long long record = 0;
    while ((line = rc_line(&cursor)) != NULL) {
        if (strncmp(line, "Village:", 8) == 0) {
            if (open && grave) {
                rc_count_grave(c, record);
            }
            open = grave = 0;
            ours = strcmp(line, c->village) == 0;
            continue;
        }
        if (line[0] != ' ') {
            if (open && grave) {
                rc_count_grave(c, record);
            }
            open = ours && strncmp(line, "Death ", 6) == 0 && line[6] >= '0' && line[6] <= '9';
            grave = 0;
            record = rc_hash_line(14695981039346656037ull, line);
            continue;
        }
        if (open) {
            record = rc_hash_line(record, line);
        }
        if (open && strncmp(line, "  Grave: ", 9) == 0) {
            grave = strncmp(line + 9, "no grave", 8) != 0 && line[9] != '\0';
        }
    }
    if (open && grave) {
        rc_count_grave(c, record);
    }
}

/* The Births and Conceptions log: this village's "Conception <n>" records
   with "  Babies nursing: 2" ("  Babies in pregnancy: 2" in an older log). */
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
        if (open && (strcmp(line, "  Babies nursing: 2") == 0
                     || strcmp(line, "  Babies in pregnancy: 2") == 0)) {   /* an older log */
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
    /* The elders list's lines and the living (rc_known), and the departed by their own records. */
    struct rc_known *known;
    int known_count;
    const struct rc_departed *departed;
    int departed_count;
    /* Every History elder already decided (one villager is in many snapshots). */
    struct rc_elder *seen;
    int seen_count;
    struct rc_plan *plan;
};

static void rc_copy(char *out, const char *in) {
    int i;
    for (i = 0; i < RC_NAME - 1 && in[i] != '\0'; ++i) {
        out[i] = (in[i] == '\t' || in[i] == '\r' || in[i] == '\n') ? ' ' : in[i];
    }
    out[i] = '\0';
}

/* rc_copy from a record's field of `capacity` bytes (which may lack a terminator). */
static void rc_bounded_copy(char *out, const unsigned char *in, unsigned int capacity) {
    char buffer[RC_NAME];
    unsigned int i;
    for (i = 0; i < capacity && i < RC_NAME - 1 && in[i] != 0; ++i) {
        buffer[i] = (char)in[i];
    }
    buffer[i] = '\0';
    rc_copy(out, buffer);
}

/* 1 when `shorter` is `longer` up to a word boundary: "Cheop" and "Cheop Bahati", "Kaula Bahati" and
   "Kaula Bahati I" -- one villager given a last name or a number since the older snapshot. */
static int rc_name_grew(const char *shorter, const char *longer) {
    size_t n = strlen(shorter);
    return n >= 2 && strncmp(shorter, longer, n) == 0 && longer[n] == ' ';
}

/* The same parents, where the game keeps them (A New Home keeps none: always the same). */
static int rc_same_parents(const struct rc_history *h, const char *father, const char *mother,
                           const struct rc_elder *v) {
    return h->game == GAME_VV1 || (strcmp(father, v->father) == 0 && strcmp(mother, v->mother) == 0);
}

/* The same villager of two snapshots: name and parents -- and, where the game keeps no parents (A New
   Home), the looks too, so two namesakes are never one. */
static int rc_same_history_villager(const struct rc_history *h, const struct rc_elder *a, const struct rc_elder *b) {
    if (strcmp(a->name, b->name) != 0 || strcmp(a->father, b->father) != 0 || strcmp(a->mother, b->mother) != 0) {
        return 0;
    }
    return h->game != GAME_VV1 || (a->head == b->head && a->body == b->body);
}

/* A Death or Disappeared record of this villager's own name, head and body. */
static int rc_has_departure(const struct rc_history *h, const struct rc_elder *v) {
    int i;
    if (v->head < 0 || v->body < 0) {
        return 0;
    }
    for (i = 0; i < h->departed_count; ++i) {
        if (h->departed[i].head == v->head && h->departed[i].body == v->body
            && strcmp(h->departed[i].name, v->name) == 0) {
            return 1;
        }
    }
    return 0;
}

/* One villager of a snapshot of this village, finished: an elder to add?  (The rules are above
   struct rc_known.) */
static void rc_history_villager(struct rc_history *h, const struct rc_elder *v, int mastered, int whole) {
    struct rc_plan *p = h->plan;
    int i, departed;
    if (!whole || mastered < 3 || v->name[0] == '\0') {
        return;
    }
    for (i = 0; i < h->seen_count; ++i) {
        if (rc_same_history_villager(h, &h->seen[i], v)) {
            return;                   /* the same villager, in another snapshot: decided once */
        }
    }
    if (h->seen_count < RC_ELDERS_MAX * 4) {
        h->seen[h->seen_count++] = *v;
    }
    departed = rc_has_departure(h, v);
    /* A line of the list that counts her: her name and parents, not yet counting another -- and never
       a line still open (a living elder) for one who departed. */
    for (i = 0; i < h->known_count; ++i) {
        struct rc_known *k = &h->known[i];
        if (k->list && !k->used && !(departed && k->open) && strcmp(k->name, v->name) == 0
            && rc_same_parents(h, k->father, k->mother, v)) {
            k->used = 1;
            return;
        }
    }
    if (!departed) {
        /* No record says she departed: one listed or living under her own name, or a name a last name
           or number grew from or into (the same parents), is her (v1.35.80, Cheop -> Cheop Bahati). */
        for (i = 0; i < h->known_count; ++i) {
            const struct rc_known *k = &h->known[i];
            if ((strcmp(k->name, v->name) == 0 || rc_name_grew(v->name, k->name) || rc_name_grew(k->name, v->name))
                && rc_same_parents(h, k->father, k->mother, v)) {
                return;
            }
        }
    }
    if (p->elders_add < RC_ELDERS_MAX) {
        p->elders[p->elders_add++] = *v;
    }
}

/* A snapshot's villager whose skills count: any, with skills read; in New
   Believers only one its snapshot calls a Believer ("Faction: Believer",
   population_export.c) -- a Heathen never counts (owner), and a snapshot
   written before the Faction line cannot tell them apart, so it proves nothing. */
static int rc_counted(const struct rc_history *h, int skills, int faction) {
    return skills > 0 && (h->game != GAME_VV5 || faction == 1);
}

static void rc_visit_history(char *text, void *context) {
    struct rc_history *h = (struct rc_history *)context;
    char *cursor = text;
    char *line;
    int ours = 0, expect_village = 0;
    int open = 0, section = 0;    /* 1 Parents, 2 Skills */
    int mastered = 0, skills = 0;
    int faction = 0;              /* New Believers: 1 Believer, 2 Heathen, 0 no line */
    struct rc_elder v;
    memset(&v, 0, sizeof v);
    while ((line = rc_line(&cursor)) != NULL) {
        int top = line[0] != ' ';
        if (top) {
            if (open) {
                rc_history_villager(h, &v, mastered, rc_counted(h, skills, faction));
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
                mastered = skills = faction = 0;
                memset(&v, 0, sizeof v);
                v.head = v.body = -1;
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
            } else if (strncmp(line, "  Head: ", 8) == 0) {
                v.head = atoi(line + 8);
            } else if (strncmp(line, "  Body: ", 8) == 0) {
                v.body = atoi(line + 8);
            } else if (strcmp(line, "  Parents:") == 0) {
                section = 1;
            } else if (strcmp(line, "  Skills:") == 0) {
                section = 2;
            } else if (strcmp(line, "  Faction: Believer") == 0) {
                faction = 1;
            } else if (strcmp(line, "  Faction: Heathen") == 0) {
                faction = 2;
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
        rc_history_villager(h, &v, mastered, rc_counted(h, skills, faction));
    }
}

/* ---- the plan -------------------------------------------------------------- */

/* The elders file the save itself reads and writes (village_elders.c path_for): the save's own
   "Virtual Villagers Fun Patcher\Save <S>\Data\Village Elders\", unless the file is still in the older
   layout's folder (native/shared/per_save_data.h). */
static int rc_elders_path(int slot, wchar_t *path) {
    wchar_t name[64];
    return _snwprintf_s(name, 64, _TRUNCATE, L"Village Elders - Save %d.dat", slot) > 0
        && vv_ps_data_file_w(path, L"Village Elders", name, 64);
}

/* Every line of the elders list -- its name, parents and whether it is still open -- into `known`;
   1 read (or no file yet), 0 not a list this companion would read. */
static int rc_elder_names(int game, int slot, struct rc_known *known, int *count, int capacity) {
    wchar_t path[MAX_PATH];
    char header[64];
    char *text, *cursor, *line;
    int missing, graves_seen, rows = 0;
    if (!rc_elders_path(slot, path)) {
        return 0;
    }
    text = rc_read(path, &missing);
    if (text == NULL) {
        return missing;
    }
    cursor = text;
    _snprintf_s(header, sizeof header, _TRUNCATE, "VVFP VILLAGE ELDERS v2 game=%d", game);
    /* The same tests as the file's own loader (village_elders.c load), so a
       file it would not read is never repaired here as if it were usable:
       the header, a graves_seen of 0 or more, and every line a one-letter
       E or G followed by six tab-separated fields, at most
       VV_ELDERS_FILE_MAX lines. */
    line = rc_line(&cursor);
    if (line == NULL || strcmp(line, header) != 0 || (line = rc_line(&cursor)) == NULL
        || sscanf_s(line, "graves_seen=%d", &graves_seen) != 1 || graves_seen < 0) {
        free(text);
        return 0;
    }
    while ((line = rc_line(&cursor)) != NULL) {
        char *fields[7];
        char *p = line;
        int n = 0;
        if (line[0] == '\0') {
            continue;
        }
        fields[n++] = p;
        for (; *p != '\0' && n < 7; ++p) {
            if (*p == '\t') {
                *p = '\0';
                fields[n++] = p + 1;
            }
        }
        if (n != 7 || (fields[0][0] != 'E' && fields[0][0] != 'G') || fields[0][1] != '\0'
            || ++rows > VV_ELDERS_FILE_MAX) {
            free(text);
            return 0;
        }
        if (*count < capacity) {
            struct rc_known *k = &known[(*count)++];
            memset(k, 0, sizeof *k);
            rc_copy(k->name, fields[2]);
            rc_copy(k->father, fields[3]);
            rc_copy(k->mother, fields[4]);
            k->list = 1;
            k->open = fields[0][0] == 'E' && strcmp(fields[6], "1") == 0;
        }
    }
    free(text);
    return 1;
}

/* The Deaths and Disappearances log: this village's "Death <n>" and "Disappeared ..." records, by
   their own name, head and body. */
struct rc_departures {
    const char *village;
    struct rc_departed *out;
    int count;
};

static void rc_visit_departures(char *text, void *context) {
    struct rc_departures *d = (struct rc_departures *)context;
    char *cursor = text;
    char *line;
    int ours = 0, open = 0;
    struct rc_departed cur;
    memset(&cur, 0, sizeof cur);
    while ((line = rc_line(&cursor)) != NULL) {
        int top = strncmp(line, "Village:", 8) == 0 || line[0] != ' ';
        if (top && open && cur.name[0] != '\0' && cur.head >= 0 && cur.body >= 0 && d->count < RC_DEPARTED_MAX) {
            d->out[d->count++] = cur;
        }
        if (strncmp(line, "Village:", 8) == 0) {
            ours = strcmp(line, d->village) == 0;
            open = 0;
            continue;
        }
        if (line[0] != ' ') {
            open = ours && line[0] != '\0'
                && ((strncmp(line, "Death ", 6) == 0 && line[6] >= '0' && line[6] <= '9')
                    || strncmp(line, "Disappeared", 11) == 0);
            memset(&cur, 0, sizeof cur);
            cur.head = cur.body = -1;
            continue;
        }
        if (!open) {
            continue;
        }
        if (strncmp(line, "  Name: ", 8) == 0) {
            rc_copy(cur.name, line + 8);
        } else if (strncmp(line, "  Head: ", 8) == 0) {
            cur.head = atoi(line + 8);
        } else if (strncmp(line, "  Body: ", 8) == 0) {
            cur.body = atoi(line + 8);
        }
    }
    if (open && cur.name[0] != '\0' && cur.head >= 0 && cur.body >= 0 && d->count < RC_DEPARTED_MAX) {
        d->out[d->count++] = cur;
    }
}

/* The living villagers -- name and the parents their record keeps -- into `known`, read from the
   game's table as living_roster reads it. */
static void rc_living_known(int game_id, struct rc_known *known, int *count, int capacity) {
    struct roster_layout layout = ROSTER_LAYOUTS[game_id];
    const struct roster_layout *r = &layout;
    unsigned char *module = (unsigned char *)GetModuleHandleW(NULL);
    const unsigned char *villagers;
    unsigned int slot;
    if (module == NULL) {
        return;
    }
    if (game_id == GAME_VV3) {
        vv3_villager_table(module, &layout.villagers_rva, &layout.slots);
    } else if (game_id == GAME_VV4) {
        vv4_villager_table(module, &layout.villagers_rva, &layout.slots);
    } else if (game_id == GAME_VV5) {
        vv5_villager_table(module, &layout.villagers_rva, &layout.slots);
    }
    villagers = r->rva_is_pointer ? *(unsigned char *const *)(module + r->villagers_rva) : module + r->villagers_rva;
    if (villagers == NULL) {
        return;
    }
    for (slot = 0; slot < r->slots && *count < capacity; ++slot) {
        const unsigned char *record = villagers + r->record_base + slot * r->stride;
        struct rc_known *k;
        if (record[r->active] != 1 || vv_lookalike(r->stride, record)) {
            continue;
        }
        k = &known[(*count)++];
        memset(k, 0, sizeof *k);
        rc_bounded_copy(k->name, record + r->name, r->name_capacity);
        if (r->father_name != 0u) {
            rc_bounded_copy(k->father, record + r->father_name, r->parent_name_capacity);
            rc_bounded_copy(k->mother, record + r->mother_name, r->parent_name_capacity);
        }
    }
}

/* What the files and the save prove for `slot`'s village `village` (its
   header line, no line end), against the counters file at `counters`.
   `context` reaches the game (the memorial; The Secret City's chief). */
static void rc_make_plan(int game, int slot, const char *village, const wchar_t *counters,
                         const vvs_context *context, struct rc_plan *plan) {
    static struct rc_known known[VV_ELDERS_FILE_MAX + ROSTER_MAX];
    static struct rc_departed departed[RC_DEPARTED_MAX];
    static struct rc_elder seen[RC_ELDERS_MAX * 4];
    int known_count = 0;
    memset(plan, 0, sizeof *plan);
    plan->buried_was = plan->twins_was = plan->chiefs_was = -1;

    /* Village Elders, from the Village History log. */
    if (game == GAME_VV1 || game == GAME_VV3 || game == GAME_VV4 || game == GAME_VV5) {
        plan->elders_ok = rc_elder_names(game, slot, known, &known_count, VV_ELDERS_FILE_MAX);
        if (plan->elders_ok) {
            struct rc_history h;
            struct rc_departures d;
            wchar_t deaths_stem[64];
            /* The living (the save adds their lines itself), with the parents their records keep. */
            rc_living_known(game, known, &known_count, VV_ELDERS_FILE_MAX + ROSTER_MAX);
            /* The departed, by their own Death and Disappeared records. */
            memset(&d, 0, sizeof d);
            d.village = village;
            d.out = departed;
            _snwprintf_s(deaths_stem, 64, _TRUNCATE, L"Virtual Villagers %d Deaths Log", game);
            if (!rc_each_slot_log(L"Deaths and Disappearances", L"Deaths", deaths_stem, slot, rc_visit_departures, &d)) {
                plan->blocked = 1;
                plan->elders_ok = 0;
            }
            memset(&h, 0, sizeof h);
            h.village = village;
            h.game = game;
            h.master = game == GAME_VV1 ? 90 : 88;
            h.known = known;
            h.known_count = known_count;
            h.departed = departed;
            h.departed_count = d.count;
            h.seen = seen;
            h.plan = plan;
            if (!plan->elders_ok
                || !rc_each_slot_log(L"Tribe History", NULL, L"Village History", slot, rc_visit_history, &h)) {
                plan->blocked = 1;
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
        plan->counters_ok = 1;
        /* The Deaths logs stay where they are (save_layout.h): an older build's "Deaths", the
           shared "Deaths and Disappearances", or both when an older and a newer build both played
           the village, then the slot's own folder (log_slot.h).  Each one there is read -- none is
           ever made just to look in it -- and a record in two counts once (rc_count_grave).  A
           folder that cannot be examined decides nothing. */
        plan->counters_ok = rc_each_slot_log(L"Deaths and Disappearances", L"Deaths", stem, slot,
                                             rc_visit_deaths, &c);
        free(c.seen);
        c.seen = NULL;
        _snwprintf_s(stem, 64, _TRUNCATE, L"Virtual Villagers %d Births and Conceptions Log", game);
        if (game == GAME_VV2 && plan->counters_ok) {
            plan->counters_ok = rc_each_slot_log(L"Births and Conceptions", NULL, stem, slot, rc_visit_births, &c);
        }
        if (!plan->counters_ok) {
            plan->blocked = 1;
        }
        if (plan->counters_ok) {
            int graves = vvs_memorial_graves(context);
            if ((long long)graves > c.graves) {
                c.graves = graves;
            }
            key = vvs_counter_key(game, VVS_BURIED);
            state = vvs_counter_peek(counters, game, key, &value);
            plan->counters_ok = state == VVS_FILE_OK;
            if (state == VVS_FILE_UNREADABLE) {
                plan->blocked = 1;
            }
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
   Reset.dll" in the patcher's folder; loaded by full path). */
static int rc_saved_header(int game, int slot, char *out, int size) {
    typedef int (__stdcall *saved_header_fn)(int, int, char *, int);
    HMODULE module = vvfp_patcher_dll("VVFP Save Reset.dll");
    saved_header_fn header;
    if (module == NULL) {
        return 0;
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

#ifdef VVFP_TEST
/* The harness's stand-in for the game's world object. */
__declspec(dllexport) unsigned char *VvfpStatisticsTestWorld;
#endif

/* A New Home's and The Lost Children's memorial is in the game's world
   object (statistics_store.c: memorial_in_manager), which a scan at the load
   has no save to be handed: it is read from the game's own global, as the
   Story / Cheat Upgrades companion reads it (story_vv1.inc VV1_WORLD_GLOBAL
   0x48AEDC, story_vv2.inc VV2_WORLD_GLOBAL 0x4997BC).  NULL elsewhere, or
   while the global cannot be read (Codex, #536: without it the memorial was
   never counted at the load). */
static unsigned char *rc_scan_world(int game) {
#ifdef VVFP_TEST
    return game == GAME_VV1 || game == GAME_VV2 ? VvfpStatisticsTestWorld : NULL;
#else
    MEMORY_BASIC_INFORMATION info;
    uintptr_t global = game == GAME_VV1 ? 0x48AEDCu : game == GAME_VV2 ? 0x4997BCu : 0u;
    if (global == 0u || VirtualQuery((const void *)global, &info, sizeof info) != sizeof info
        || info.State != MEM_COMMIT || (info.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0) {
        return NULL;
    }
    return *(unsigned char **)global;
#endif
}

/* VvfpStatisticsScanReconcile(game, slot, text, cap): what the Village
   Statistics and Village Elders files of the slot's village are missing
   that the save and the logs prove -- the number of changes, with the
   prompt's lines in `text`; 0 nothing (or the files are not this
   village's); -1 cannot tell now.  Reads only. */
__declspec(dllexport) int __stdcall VvfpStatisticsScanReconcile(int game, int slot, char *text, int cap) {
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
    context.manager = rc_scan_world(game);
    rc_make_plan(game, slot, village, counters, &context, &plan);
    if (plan.blocked) {
        return -1;                    /* a log or file is locked: the bridge asks again */
    }
    if (plan.changes > 0) {
        rc_describe(&plan, text, cap);
    }
    return plan.changes;
}

__declspec(dllexport) void __stdcall VvfpStatisticsRepairReconcile(int game, int slot, int repair) {
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
static int rc_apply(int game, int slot, unsigned char *manager) {
    static struct rc_plan plan;
    char name[VV_VILLAGE_NAME_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    wchar_t elders[MAX_PATH], elders_backup[MAX_PATH], counters_backup[MAX_PATH];
    char *body;
    char leaf[MAX_PATH];
    size_t cap, len = 0;
    int none, i, ok = 1;
    if (!g_rc_save_ok || slot < 1 || slot > 5 || !g_rc_repair[slot]) {
        return 0;
    }
    if (!vv_village_name(game, manager, name) || !vv_village_header(village, sizeof village, name, slot)) {
        return 0;
    }
    rc_trim(village);
    rc_make_plan(game, slot, village, g_store.counters_path, &g_store, &plan);
    if (plan.changes == 0) {
        g_rc_repair[slot] = 0;        /* nothing left to do */
        return 0;
    }
    elders_backup[0] = counters_backup[0] = L'\0';
    if (plan.elders_add > 0 && (!rc_elders_path(slot, elders)
                                || !vv_repair_backup(elders, elders_backup, MAX_PATH, &none) || none)) {
        return 0;
    }
    if (plan.buried_was >= 0 || plan.twins_was >= 0 || plan.chiefs_was >= 0) {
        if (!vv_repair_backup(g_store.counters_path, counters_backup, MAX_PATH, &none) || none) {
            if (elders_backup[0]) {
                DeleteFileW(elders_backup);
            }
            return 0;
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
        return 0;
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
    return 1;
}

/* The log written again after a quit-time Repair.  The TEST build counts
   the call instead: the log's writers call the game's own routines (real
   hours played, the puzzle predicates), which a harness does not map --
   the shipped build always writes it (write_statistics_file, the very
   function every save uses). */
#ifdef VVFP_TEST
__declspec(dllexport) int VvfpStatisticsTestLogRewrites = 0;
#define RC_REWRITE_LOG(game, manager, slot, village) \
    ((void)(game), (void)(manager), (void)(slot), (void)(village), ++VvfpStatisticsTestLogRewrites, 1)
#else
#define RC_REWRITE_LOG(game, manager, slot, village) write_statistics_file(game, manager, slot, village)
#endif

/* VvfpStatisticsRepairReconcileNow(game, slot): the player chose Repair
   right after the game's quit save (native/shared/crosscheck_bridge.h), when
   no later save will come.  What rc_apply would have done at the next save
   is done now, from the save just written: the same manager (the game frees
   nothing before this), the store bound as that save bound it, its counters
   already flushed into the file (the reconcile only runs when that save's
   were), and the roster that save read.  Then the Village Statistics log
   is written again, so it shows the repaired counters.  Only straight after
   a successful save of this slot this session, and only when the reconcile
   could have run at it.  1 when nothing is left to repair. */
__declspec(dllexport) int __stdcall VvfpStatisticsRepairReconcileNow(int game, int slot) {
    char name[VV_VILLAGE_NAME_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    unsigned char *manager = g_last_save.manager;
    int changed;
    if (game < GAME_VV1 || game > GAME_VV5 || slot < 1 || slot > 5 || g_last_save.slot != slot
        || !g_last_save.reconcile_ok) {
        return 0;
    }
    bind_store(game, manager, slot);
    g_save_id = slot;
    g_rc_repair[slot] = 1;
    g_rc_save_ok = 1;
    changed = rc_apply(game, slot, manager);
    g_rc_save_ok = 0;
    if (g_rc_repair[slot]) {
        return 0;                     /* not done: nothing more is written now */
    }
    if (changed) {
        g_rc_log_pending[slot] = 1;
    }
    if (g_rc_log_pending[slot]) {
        if (!vv_village_name(game, manager, name) || !vv_village_header(village, sizeof village, name, slot)
            || RC_REWRITE_LOG(game, manager, slot, village) != 1) {
            return 0;                 /* the log still shows the old values: not done */
        }
        g_rc_log_pending[slot] = 0;
    }
    return 1;
}

#ifdef VVFP_TEST
/* The TEST build only (statistics_export_test.def): the part of a save the
   reconcile rides on -- the roster check, the living-elder update and the
   reconcile itself, as WriteVillageStatistics runs them after a successful
   save of the same village -- without the game's writer, clock and puzzle
   calls the harness has none of.  Returns 1 when no answer is left pending. */
__declspec(dllexport) int __stdcall VvfpStatisticsTestSave(int game, int slot, void *manager) {
    unsigned char *m = (unsigned char *)manager;
    if (game < GAME_VV1 || game > GAME_VV5 || slot < 1 || slot > 5 || m == NULL) {
        return 0;
    }
    g_save_id = slot;
    bind_store(game, m, slot);
    if (village_changed(game, slot) != ROSTER_SAME) {
        return 0;
    }
    g_elders_ready = 0;
    if (game == GAME_VV1) {
        vv1_village_elders(m);
    } else if (game != GAME_VV2) {
        village_elders_for(game);
    }
    g_rc_save_ok = 1;
    rc_apply(game, slot, m);
    /* ...and remembered as the session's last save, as SaveVillageStatistics
       remembers a real one (for VvfpStatisticsRepairReconcileNow). */
    g_last_save.slot = slot;
    g_last_save.manager = m;
    g_last_save.reconcile_ok = 1;
    g_rc_save_ok = 0;
    return g_rc_repair[slot] == 0;
}
#endif
