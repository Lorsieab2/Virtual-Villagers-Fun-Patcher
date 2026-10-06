/* THE FIRST-LOAD CROSS-CHECK (v1.35.58) -- included by vv1_parentage.c.

   WHY.  Before v1.35.57 this table was kept by record index, and A New Home
   packs its villager array when a save is loaded: after a death, everyone
   behind it comes back one record lower, and the parents went with the
   INDEX, not the villager.  v1.35.57 makes every entry follow its villager
   (vv1_follow_roster), but a table that had ALREADY drifted is stored against
   the wrong identities, and following it only carries the wrong parents
   faithfully onwards: nothing in the file itself can tell.  The owner's Lisha
   (daughter of Ghali and Onawa) was recorded as Kito and Chika's, and Silko,
   a grown arrival with no parents at all, as Ghali and Onawa's.

   THE SOURCE OF TRUTH.  Every birth this companion records is written to the
   village's Births and Conceptions log the moment it is seen, with the
   child's name, head and body and both parents' -- and the log, unlike the
   table, is never rewritten.  So once per village, the first time this build
   loads it, the parents of every LIVING villager are rebuilt from the log,
   the way the owner's own repair was done (owner, 2026-10-03: "the first time
   v1.35.57 loads a village, rebuild the parents from that village's Births
   log, once, with a backup"):

     - a villager matched to Birth records by name, head AND body (never the
       name alone: names come from a fixed pool), where every matching record
       names the same two parents and there are at least as many of those
       records as living villagers sharing the three, gets those parents;
     - matching records that disagree, or more living villagers sharing the
       three than Birth records for them, is ambiguous: the parents are set
       to unknown, never guessed;
     - a villager with no Birth record of that name at all -- a founder or a
       grown arrival -- has no parents (the owner's rule: villagers not
       spawned by a conception have none);
     - a villager whose NAME has Birth records but none with their head and
       body (an Origins appearance upgrade changed them since birth) cannot be
       confirmed either way, and is left exactly as it is;
     - a pregnant mother's stash -- the father her baby will get -- is set
       from her LAST logged conception (matched the same way) only when no
       Birth by her follows it, and only when that names a father; otherwise
       it cannot be confirmed and is left as it is.

   Departed villagers' entries, and anything else in the file, are not
   touched.

   THE PLAYER DECIDES FIRST (owner: "the player should be notified first
   before any fix runs"; 2026-10-05: never a question during gameplay).  The
   scan (Vv1ParentageCrossCheckScan) only reads.  When it finds nothing to
   change it records that it ran, silently.  When it finds something, nothing
   happens until the player allows it (native/shared/crosscheck_bridge.h):
   Repair Logs in the patcher window approves it beforehand, and it is then
   applied once the village has settled; with "Check logs automatically" on,
   the player is asked Repair / Not now when the game is closed, after its
   quit save.  "Not now" changes nothing at all and the question comes back
   the next time; "Repair" (Vv1ParentageCrossCheckApply) first copies the
   parentage file to
   "<name>.before-v1.35.58-repair" beside itself, then writes the rebuilt
   table through the same atomic save every other change uses, lists every
   change in the Repairs log, and records that the check ran.

   WHY A REPAIRS LOG.  The player has to be able to see what changed, and
   none of the existing logs is about the patcher's own records: the
   Unaccounted Villagers log is for villagers who left or arrived with no
   record of why, and the Births log is never rewritten or annotated.  So the
   note goes to "Virtual Villagers Fun Patcher Logs\Repairs\Virtual Villagers
   1 Repairs Log <n>.txt": the village's own header line (copied from its
   Births log), then one numbered "Repair <n>" record per repair, one line per
   villager changed, in the same shape as every other numbered log.

   ONCE PER VILLAGE.  "Virtual Villagers Fun Patcher Data\Cross-Check\
   Virtual Villagers 1 Cross-Check - Save N.dat" records that it ran for that
   slot.  It is written last, after the table and the note, so an
   interruption anywhere before it simply runs the check again on the next
   load -- which then finds the rebuilt table already in step and changes
   nothing.

   FAILS CLOSED.  A Births log that is there but cannot be read, a backup
   that cannot be made, a table that cannot be written: nothing is changed,
   the marker is not written, and the check runs again on the next load.  A
   slot with no Births log, or one with no Birth record for this village, has
   nothing to check against: the marker records that, and nothing is
   changed. */

#define VV1_XC_MAGIC            0x31435856u   /* 'V' 'X' 'C' '1' */
#define VV1_XC_VERSION          1u
#define VV1_XC_MAX_LOG_FILES    4096          /* the exporters' own roll-over ceiling */
#define VV1_XC_MAX_FILE_BYTES   (16u * 1024u * 1024u)
#define VV1_XC_MAX_HEADERS      64
#define VV1_XC_HEADER_CAPACITY  160
#define VV1_XC_UNSET            (-2147483647 - 1)
#define VV1_XC_BACKUP_SUFFIX    ".before-v1.35.58-repair"
#define VV1_XC_REPAIRS_PER_FILE 256
#define VV1_XC_REPAIRS_FILE_BYTES (4u * 1024u * 1024u)  /* a Repairs log this big is full: well under the read cap */
#define VV1_XC_NOTE_PER_CHANGE  512           /* the two lines one change can add, with room to spare */
#define VV1_XC_NOTE_TAIL        (MAX_PATH + 64)  /* the Backup line */
#define VV1_XC_NOTE_FIXED       (VV1_XC_HEADER_CAPACITY + 512 + VV1_XC_NOTE_TAIL)

/* What the marker says about the slot. */
#define VV1_XC_RESULT_CLEAN     1    /* checked: nothing to change */
#define VV1_XC_RESULT_REPAIRED  2    /* checked, the player chose Repair, and it was done */
#define VV1_XC_RESULT_NO_LOG    3    /* no Births log for this village: nothing to check against */

/* What the check found for one living villager. */
#define VV1_XC_SAME        0
#define VV1_XC_CORRECTED   1    /* the log names other parents than the table */
#define VV1_XC_FILLED      2    /* the table knew none; the log names them */
#define VV1_XC_CLEARED     3    /* the table names parents the log says this villager cannot have */
#define VV1_XC_AMBIGUOUS   4    /* the table names parents; the log cannot tell which are right */

typedef struct {
    char name[VV1_NAME_CAPACITY];
    int head, body;               /* VV1_XC_UNSET when the log gave none */
    int present;
    int seen;                     /* the record printed this person's line at all */
} vv1_xc_person;

typedef struct {
    int kind;                     /* 1 Birth, 2 Conception */
    int header;                   /* index into the run's header table */
    vv1_xc_person child, mother, father;
} vv1_xc_record;

typedef struct {
    vv1_xc_record *items;
    int count, capacity;
    char headers[VV1_XC_MAX_HEADERS][VV1_XC_HEADER_CAPACITY];
    int header_count;
    int village_header;           /* the slot's latest header: the village the records are kept from */
    int overflow;                 /* more villages for this slot than the table holds: not read */
    unsigned long long damaged;   /* bit h: a record under header h was cut short (no name, head or body) */
} vv1_xc_log;

typedef struct {
    int index;
    int what;                     /* VV1_XC_* */
    int stash;                    /* 1 when the pregnancy stash changes too */
    int stale;                    /* 1 when a stale expected father is cleared */
    vv1_parent_entry before, after;
} vv1_xc_change;

typedef struct {
    vv1_xc_change changes[VV1_RECORD_COUNT];
    int count;
    int corrected, filled, cleared, ambiguous, stashes;
    int stale;                    /* expected fathers left on villagers who are not expecting */
} vv1_xc_plan;

/* ---- paths ------------------------------------------------------------- */

/* "<My Documents>\LDW\<exe basename>", creating both; `reserve` is what the
   caller will still append (with its backslash and NUL). */
static int vv1_xc_game_folder(char *out, size_t n, size_t reserve) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    DWORD exelen;
    if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) {
        return 0;
    }
    exelen = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (exelen == 0 || exelen >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';
    }
    if ((size_t)lstrlenA(docs) + (size_t)lstrlenA(base) + sizeof("\\LDW\\") + reserve > n) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    return 1;
}

/* "<game folder>\<a>\<b>", creating both levels. */
static int vv1_xc_subfolder(char *out, size_t n, const char *a, const char *b, size_t reserve) {
    size_t need = (size_t)lstrlenA(a) + (size_t)lstrlenA(b) + 2 + reserve;
    if (!vv1_xc_game_folder(out, n, need)) {
        return 0;
    }
    lstrcatA(out, "\\");
    lstrcatA(out, a);
    CreateDirectoryA(out, NULL);
    lstrcatA(out, "\\");
    lstrcatA(out, b);
    CreateDirectoryA(out, NULL);
    return 1;
}

static int vv1_xc_marker_path(char *out, size_t n, int slot) {
    if (!vv1_xc_subfolder(out, n, "Virtual Villagers Fun Patcher Data", "Cross-Check",
                          sizeof("\\Virtual Villagers 1 Cross-Check - Save 0.dat.tmp"))) {
        return 0;
    }
    wsprintfA(out + lstrlenA(out), "\\Virtual Villagers 1 Cross-Check - Save %d.dat", slot);
    return 1;
}

/* ---- the marker -------------------------------------------------------- */

/* The village a marker is for: FNV-1a of the village's own header line in its
   Births log ("Village: <name> (Save N)"), 0 when it has none.  A marker
   counts only for the village it names, so a slot that now holds another
   village (a save copied in, a Start Over the reset could not clear) is
   checked again. */
static unsigned int vv1_xc_village_id(const char *header) {
    unsigned int h = 2166136261u;
    while (header != NULL && *header) {
        h = (h ^ (unsigned char)*header++) * 16777619u;
    }
    return header == NULL ? 0u : (h ? h : 1u);
}

/* 1: the check has run for this village.  0: it has not (no marker, one for
   another village, or one that was not a marker and is now set aside).  -1:
   a marker is there and cannot be read, or a bad one cannot be moved: do
   nothing this load. */
static int vv1_xc_marker_state(int slot, unsigned int village) {
    char path[MAX_PATH];
    unsigned int header[12];
    HANDLE file;
    DWORD error;
    int sound;
    if (!vv1_xc_marker_path(path, sizeof(path), slot)) {
        return -1;
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        error = GetLastError();
        return (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) ? 0 : -1;
    }
    sound = vv1_read_exact(file, header, sizeof(header));
    CloseHandle(file);
    if (sound < 0) {
        return -1;
    }
    if (sound == 1 && header[0] == VV1_XC_MAGIC && header[1] == VV1_XC_VERSION
        && header[2] == 1u && header[3] == (unsigned int)slot) {
        return header[11] == village ? 1 : 0;
    }
    return vv1_set_aside(path) ? 0 : -1;
}

/* Record that the check ran: magic, version, game, slot, result, the four
   counts, when, and the village (vv1_xc_village_id).  Temporary file,
   flushed, then renamed over. */
static int vv1_xc_marker_write(int slot, int result, const vv1_xc_plan *plan, unsigned int village) {
    char path[MAX_PATH];
    char tmp[MAX_PATH];
    unsigned int data[12];
    FILETIME now;
    HANDLE file;
    DWORD wrote;
    BOOL ok;
    if (!vv1_xc_marker_path(path, sizeof(path), slot)
        || lstrlenA(path) + sizeof(".tmp") > sizeof(tmp)) {
        return 0;
    }
    lstrcpyA(tmp, path);
    lstrcatA(tmp, ".tmp");
    GetSystemTimeAsFileTime(&now);
    data[0] = VV1_XC_MAGIC;
    data[1] = VV1_XC_VERSION;
    data[2] = 1u;
    data[3] = (unsigned int)slot;
    data[4] = (unsigned int)result;
    data[5] = plan ? (unsigned int)plan->corrected : 0u;
    data[6] = plan ? (unsigned int)plan->filled : 0u;
    data[7] = plan ? (unsigned int)(plan->cleared + plan->ambiguous) : 0u;
    data[8] = plan ? (unsigned int)(plan->stashes + plan->stale) : 0u;
    data[9] = now.dwLowDateTime;
    data[10] = now.dwHighDateTime;
    data[11] = village;
    file = CreateFileA(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(file, data, sizeof(data), &wrote, NULL) && wrote == sizeof(data);
    ok = ok && FlushFileBuffers(file);
    ok = CloseHandle(file) && ok;
    if (!ok || !MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        DeleteFileA(tmp);
        return 0;
    }
    return 1;
}

/* ---- reading the Births and Conceptions log ---------------------------- */

static int vv1_xc_push(vv1_xc_log *log, const vv1_xc_record *rec) {
    if (log->count == log->capacity) {
        int grown = log->capacity ? log->capacity * 2 : 256;
        vv1_xc_record *items = log->items
            ? (vv1_xc_record *)HeapReAlloc(GetProcessHeap(), 0, log->items, (SIZE_T)grown * sizeof(*items))
            : (vv1_xc_record *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)grown * sizeof(*items));
        if (items == NULL || grown > 1000000) {
            return 0;
        }
        log->items = items;
        log->capacity = grown;
    }
    log->items[log->count++] = *rec;
    return 1;
}

static void vv1_xc_free(vv1_xc_log *log) {
    if (log->items != NULL) {
        HeapFree(GetProcessHeap(), 0, log->items);
    }
    log->items = NULL;
    log->count = log->capacity = 0;
}

/* Does `line` start with `word`? */
static int vv1_xc_starts(const char *line, const char *word) {
    return strncmp(line, word, lstrlenA(word)) == 0;
}

static int vv1_xc_int(const char *text, int *out) {
    int sign = 1, value = 0, digits = 0;
    while (*text == ' ' || *text == '\t') ++text;
    if (*text == '-') { sign = -1; ++text; }
    while (*text >= '0' && *text <= '9' && digits < 9) {
        value = value * 10 + (*text - '0');
        ++text;
        ++digits;
    }
    if (!digits) {
        return 0;
    }
    *out = sign * value;
    return 1;
}

static void vv1_xc_person_start(vv1_xc_person *p, const char *after_colon) {
    int i = 0;
    while (*after_colon == ' ' || *after_colon == '\t') ++after_colon;
    memset(p, 0, sizeof(*p));
    while (after_colon[i] && i + 1 < VV1_NAME_CAPACITY) {
        p->name[i] = after_colon[i];
        ++i;
    }
    while (i > 0 && (p->name[i - 1] == ' ' || p->name[i - 1] == '\t')) --i;
    p->name[i] = '\0';
    p->head = VV1_XC_UNSET;
    p->body = VV1_XC_UNSET;
    /* WriteParentageBirth prints a parent it never captured as "(unknown)"
       (and the logs print "(none)" for no name): no parent, never a name. */
    p->seen = 1;
    /* No villager's name begins with "(": the exporters' "(unknown)", "(none)"
       and "(not captured for this birth)" all mean no parent. */
    p->present = p->name[0] != '(';
    if (!p->present) {
        p->name[0] = '\0';
    }
}

/* The slot a "Village: <name> (Save N)" line is for, or 0. */
static int vv1_xc_header_slot(const char *line) {
    int len = lstrlenA(line);
    if (len >= 9 && line[len - 1] == ')' && line[len - 3] == ' ' && line[len - 2] >= '1' && line[len - 2] <= '5'
        && strncmp(line + len - 9, " (Save ", 7) == 0) {
        return line[len - 2] - '0';
    }
    return 0;
}

static int vv1_xc_header_index(vv1_xc_log *log, const char *line) {
    int i;
    for (i = 0; i < log->header_count; ++i) {
        if (lstrcmpA(log->headers[i], line) == 0) {
            return i;
        }
    }
    if (log->header_count >= VV1_XC_MAX_HEADERS || lstrlenA(line) >= VV1_XC_HEADER_CAPACITY) {
        return -1;
    }
    lstrcpyA(log->headers[log->header_count], line);
    return log->header_count++;
}

/* A person a record names is complete when the record leaves them out, names
   nobody ("(unknown)" parses to an empty name), or gives the name with both a
   head and a body. */
static int vv1_xc_person_whole(const vv1_xc_person *p) {
    return !p->present || p->name[0] == '\0' || (p->head != VV1_XC_UNSET && p->body != VV1_XC_UNSET);
}

/* End a record.  A Birth needs its child's name, head and body, a Conception
   its mother's, and every parent it names needs a head and a body; one of this
   village's records that falls short of that -- a log cut off or damaged
   mid-record -- is not a source of truth: the whole log is treated as
   unreadable and nothing is changed (Codex, #522: a fragment would otherwise
   count as the village's Births and clear the parents of everyone it does not
   name). */
static int vv1_xc_finish(vv1_xc_log *log, vv1_xc_record *rec, int in_slot, int header) {
    const vv1_xc_person *key_person;
    if (!in_slot || (rec->kind != 1 && rec->kind != 2)) {
        return 1;
    }
    key_person = rec->kind == 1 ? &rec->child : &rec->mother;
    /* WriteParentageBirth always prints the Mother and the Father sections --
       "(unknown)" when it has none -- so a Birth without one was cut off
       (Codex, #522). */
    if ((rec->kind == 1 && (!rec->mother.seen || !rec->father.seen))
        || !key_person->present || key_person->name[0] == '\0'
        || key_person->head == VV1_XC_UNSET || key_person->body == VV1_XC_UNSET
        || !vv1_xc_person_whole(&rec->mother) || !vv1_xc_person_whole(&rec->father)
        || !vv1_xc_person_whole(&rec->child)) {
        if (header >= 0 && header < 64) {
            log->damaged |= 1ull << header;   /* only this village's log is in doubt */
        }
        return 1;
    }
    rec->header = header;
    return vv1_xc_push(log, rec);
}

/* One file's text, in the same blocks the owner's repair tool reads: a
   "Village:" line names the village (and slot) the following records belong
   to; a record is "Birth" or "Conception <n>" up to the next blank line; a
   "Child:", "Mother:" or "Father:" line starts a person, whose first "Head:"
   and "Body:" lines after it are theirs, and a "Skills", "Babies in
   pregnancy" or "Note" line ends that person.  Returns 0 when memory ran out. */
static int vv1_xc_parse(vv1_xc_log *log, char *text, int slot) {
    vv1_xc_record rec;
    vv1_xc_person *person = NULL;
    int header = -1;              /* each file begins with its own header */
    int in_slot = 0;
    char *line = text;
    memset(&rec, 0, sizeof(rec));
    for (;;) {
        char *end = line;
        char *next;
        int last;
        while (*end && *end != '\n') ++end;
        last = *end == '\0';
        next = end + (last ? 0 : 1);
        *end = '\0';
        if (end > line && end[-1] == '\r') end[-1] = '\0';
        {
            char *trimmed = line;
            int blank;
            while (*trimmed == ' ' || *trimmed == '\t') ++trimmed;
            blank = *trimmed == '\0';
            if (blank || line[0] != ' ') {
                /* The end of a record: a blank line, or any line starting a new one. */
                if (!vv1_xc_finish(log, &rec, in_slot, header)) return 0;
                memset(&rec, 0, sizeof(rec));
                person = NULL;
            }
            if (!blank) {
                if (vv1_xc_starts(line, "Village:")) {
                    char *e = line + lstrlenA(line);
                    while (e > line && (e[-1] == ' ' || e[-1] == '\t')) *--e = '\0';
                    in_slot = vv1_xc_header_slot(line) == slot;
                    header = in_slot ? vv1_xc_header_index(log, line) : -1;
                    if (in_slot && header < 0) {
                        in_slot = 0;      /* more villages than the table holds: the latest cannot be told */
                        log->overflow = 1;
                    }
                    if (in_slot) {
                        log->village_header = header;
                    }
                } else if (line[0] != ' ') {
                    if (lstrcmpA(line, "Birth") == 0) {
                        rec.kind = 1;
                    } else if (vv1_xc_starts(line, "Conception")) {
                        rec.kind = 2;
                    }
                } else if (rec.kind) {
                    if (vv1_xc_starts(trimmed, "Child:")) {
                        person = &rec.child;
                        vv1_xc_person_start(person, trimmed + 6);
                    } else if (vv1_xc_starts(trimmed, "Mother:")) {
                        person = &rec.mother;
                        vv1_xc_person_start(person, trimmed + 7);
                    } else if (vv1_xc_starts(trimmed, "Father:")) {
                        person = &rec.father;
                        vv1_xc_person_start(person, trimmed + 7);
                    } else if (vv1_xc_starts(trimmed, "Skills") || vv1_xc_starts(trimmed, "Babies in pregnancy")
                               || vv1_xc_starts(trimmed, "Note")) {
                        person = NULL;
                    } else if (person != NULL && vv1_xc_starts(trimmed, "Head:")) {
                        if (person->head == VV1_XC_UNSET) vv1_xc_int(trimmed + 5, &person->head);
                    } else if (person != NULL && vv1_xc_starts(trimmed, "Body:")) {
                        if (person->body == VV1_XC_UNSET) vv1_xc_int(trimmed + 5, &person->body);
                    }
                }
            }
        }
        if (last) {
            break;
        }
        line = next;
    }
    /* A file that ends without a blank line still ends its last record. */
    return vv1_xc_finish(log, &rec, in_slot, header);
}

/* Read every "Virtual Villagers 1 Births and Conceptions Log <n>.txt", in
   number order, keeping this slot's records.  1: read (records may be none);
   0: there is no Births log for this village at all; -1: a file is there and
   could not be read whole -- the caller changes nothing. */
static int vv1_xc_read_log(vv1_xc_log *log, int slot) {
    char folder[MAX_PATH];
    char pattern[MAX_PATH];
    char path[MAX_PATH];
    static int numbers[VV1_XC_MAX_LOG_FILES];
    int count = 0, i, j;
    WIN32_FIND_DATAA found;
    HANDLE find;
    memset(log, 0, sizeof(*log));
    log->village_header = -1;
    if (!vv1_xc_subfolder(folder, sizeof(folder), "Virtual Villagers Fun Patcher Logs",
                          "Births and Conceptions",
                          sizeof("\\Virtual Villagers 1 Births and Conceptions Log 4294967295.txt"))) {
        return -1;
    }
    wsprintfA(pattern, "%s\\Virtual Villagers 1 Births and Conceptions Log *.txt", folder);
    find = FindFirstFileA(pattern, &found);
    if (find == INVALID_HANDLE_VALUE) {
        DWORD error = GetLastError();
        return (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND || error == ERROR_NO_MORE_FILES) ? 0 : -1;
    }
    do {
        const char *tail = found.cFileName + sizeof("Virtual Villagers 1 Births and Conceptions Log ") - 1;
        int n = 0, digits = 0;
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        while (*tail >= '0' && *tail <= '9' && digits < 6) { n = n * 10 + (*tail - '0'); ++tail; ++digits; }
        if (!digits || lstrcmpiA(tail, ".txt") != 0 || n < 1) continue;
        if (count >= VV1_XC_MAX_LOG_FILES) { FindClose(find); return -1; }
        numbers[count++] = n;
    } while (FindNextFileA(find, &found));
    FindClose(find);
    for (i = 1; i < count; ++i) {             /* number order: 2 before 10 */
        int v = numbers[i];
        for (j = i; j > 0 && numbers[j - 1] > v; --j) numbers[j] = numbers[j - 1];
        numbers[j] = v;
    }
    for (i = 0; i < count; ++i) {
        HANDLE file;
        DWORD size, got = 0;
        char *text;
        int ok;
        wsprintfA(path, "%s\\Virtual Villagers 1 Births and Conceptions Log %d.txt", folder, numbers[i]);
        file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                           NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
        if (file == INVALID_HANDLE_VALUE) {
            vv1_xc_free(log);
            return -1;
        }
        size = GetFileSize(file, NULL);
        if (size == INVALID_FILE_SIZE || size > VV1_XC_MAX_FILE_BYTES) {
            CloseHandle(file);
            vv1_xc_free(log);
            return -1;
        }
        text = (char *)HeapAlloc(GetProcessHeap(), 0, (SIZE_T)size + 1);
        if (text == NULL) {
            CloseHandle(file);
            vv1_xc_free(log);
            return -1;
        }
        ok = size == 0 || (ReadFile(file, text, size, &got, NULL) && got == size);
        CloseHandle(file);
        text[ok ? size : 0] = '\0';
        if (ok) {
            DWORD k;
            for (k = 0; k < size; ++k) {
                if (text[k] == '\0') text[k] = ' ';   /* a stray NUL never cuts a file short */
            }
            ok = vv1_xc_parse(log, text, slot);
        }
        HeapFree(GetProcessHeap(), 0, text);
        if (!ok) {
            vv1_xc_free(log);
            return -1;
        }
    }
    if (log->overflow
        || (log->village_header >= 0 && (log->damaged & (1ull << log->village_header)) != 0)) {
        vv1_xc_free(log);
        return -1;                        /* which village is the latest, or what a record says, cannot be told: change nothing */
    }
    return log->village_header >= 0 ? 1 : 0;
}

/* ---- the plan ---------------------------------------------------------- */

static int vv1_xc_same_person(const vv1_xc_person *a, const vv1_xc_person *b) {
    return a->present == b->present && a->head == b->head && a->body == b->body
        && strncmp(a->name, b->name, VV1_NAME_CAPACITY) == 0;
}

/* The child of record `r` is this living villager: name, head and body. */
static int vv1_xc_is(const vv1_xc_person *p, const char *name, int head, int body) {
    return p->present && p->head == head && p->body == body
        && strncmp(p->name, name, VV1_NAME_CAPACITY) == 0;
}

static void vv1_xc_set(unsigned char *head, unsigned char *body, char *name, const vv1_xc_person *p) {
    if (p->present && p->name[0]) {
        *head = p->head == VV1_XC_UNSET ? 0 : vv1_plus_one(p->head);
        *body = p->body == VV1_XC_UNSET ? 0 : vv1_plus_one(p->body);
        memset(name, 0, VV1_NAME_CAPACITY);
        lstrcpynA(name, p->name, VV1_NAME_CAPACITY);
    } else {
        *head = 0;
        *body = 0;
        memset(name, 0, VV1_NAME_CAPACITY);
    }
}

static int vv1_xc_parents_equal(const vv1_parent_entry *a, const vv1_parent_entry *b) {
    return a->father_head == b->father_head && a->father_body == b->father_body
        && a->mother_head == b->mother_head && a->mother_body == b->mother_body
        && strncmp(a->father_name, b->father_name, VV1_NAME_CAPACITY) == 0
        && strncmp(a->mother_name, b->mother_name, VV1_NAME_CAPACITY) == 0;
}

static int vv1_xc_has_parents(const vv1_parent_entry *e) {
    return e->father_head || e->father_body || e->mother_head || e->mother_body
        || e->father_name[0] || e->mother_name[0];
}

static int vv1_xc_has_stash(const vv1_parent_entry *e) {
    return e->stash_head || e->stash_body || e->stash_name[0];
}

/* The father of the pregnancy a mother is carrying, as the log confirms it:
   the father of her LAST logged conception (matched by name, head and body),
   when no Birth by her follows it in the log and it names a father.  1 and
   *father filled, or 0: the log cannot say. */
static int vv1_xc_last_father(const vv1_xc_log *log, const char *name, int head, int body,
                              const vv1_xc_person **father) {
    int k, last = -1;
    for (k = 0; k < log->count; ++k) {
        const vv1_xc_record *r = &log->items[k];
        if (r->kind == 2 && r->header == log->village_header && vv1_xc_is(&r->mother, name, head, body)) {
            last = k;
        }
    }
    if (last < 0) {
        return 0;
    }
    for (k = last + 1; k < log->count; ++k) {
        const vv1_xc_record *r = &log->items[k];
        if (r->kind == 1 && r->header == log->village_header && vv1_xc_is(&r->mother, name, head, body)) {
            return 0;                     /* she delivered after it: this pregnancy is not in the log */
        }
    }
    if (!log->items[last].father.present || !log->items[last].father.name[0]) {
        return 0;
    }
    *father = &log->items[last].father;
    return 1;
}

/* How many living villagers share this name, head and body. */
static int vv1_xc_shared(const unsigned char *records, const char *name, int head, int body) {
    int k, shared = 0;
    for (k = 0; k < VV1_RECORD_COUNT; ++k) {
        const unsigned char *other = records + (unsigned int)k * VV1_RECORD_STRIDE;
        char other_name[VV1_NAME_CAPACITY];
        if (!other[VV1_OCCUPIED_OFFSET]) continue;
        vv1_copy_name(other, other_name);
        if (*(const int *)(other + VV1_HEAD_OFFSET) == head && *(const int *)(other + VV1_BODY_OFFSET) == body
            && strncmp(other_name, name, VV1_NAME_CAPACITY) == 0) {
            ++shared;
        }
    }
    return shared;
}

/* THE PREGNANCIES BROUGHT INTO THE SESSION.  The load-time catch-up delivers
   most babies before the village is even on screen -- long before the player
   can be asked -- and each newborn takes its father from its mother's stash.
   A stash the old builds let drift would give the newborn, and its Birth
   record, someone else's father, and the log is never rewritten.  So when a
   village is loaded and its check has not run yet, the father the Births log
   confirms for each pregnancy is learnt here, by the mother's identity, and
   vv1_set_father uses it in place of her stash.  Nothing on disk changes:
   the stash itself is repaired only if the player chooses Repair. */
#define VV1_XC_FATHERS VV1_RECORD_COUNT
static struct {
    char mother[VV1_NAME_CAPACITY];
    int head, body;
    vv1_parent_entry father;      /* in the stash fields */
    int known;                    /* the Births log names the father */
} g_xc_fathers[VV1_XC_FATHERS];
static int g_xc_father_count;
static int g_xc_carry_ready;      /* the list below describes the village as it was loaded */

static void vv1_xc_prepare_fathers(int slot, const unsigned char *records) {
    vv1_xc_log log;
    int j;
    g_xc_father_count = 0;
    g_xc_carry_ready = 0;
    if (records == NULL || vv1_xc_read_log(&log, slot) != 1) {
        return;                       /* nothing to learn from */
    }
    if (vv1_xc_marker_state(slot, vv1_xc_village_id(log.headers[log.village_header])) != 0) {
        vv1_xc_free(&log);
        return;                       /* this village was checked already */
    }
    for (j = 0; j < VV1_RECORD_COUNT; ++j) {
        const unsigned char *rec = records + (unsigned int)j * VV1_RECORD_STRIDE;
        const vv1_xc_person *father;
        char name[VV1_NAME_CAPACITY];
        int head, body;
        if (!rec[VV1_OCCUPIED_OFFSET] || *(const int *)(rec + VV1_DUE_OFFSET) == 0) {
            continue;
        }
        vv1_copy_name(rec, name);
        head = *(const int *)(rec + VV1_HEAD_OFFSET);
        body = *(const int *)(rec + VV1_BODY_OFFSET);
        /* Every mother carrying at the load is listed -- with the father the
           log confirms, when it does -- so a stash a catch-up delivery left
           in place is never taken for a stale one (the same old save would
           deliver that pregnancy again after a crash). */
        if (vv1_xc_shared(records, name, head, body) == 1) {
            memset(&g_xc_fathers[g_xc_father_count], 0, sizeof(g_xc_fathers[0]));
            lstrcpynA(g_xc_fathers[g_xc_father_count].mother, name, VV1_NAME_CAPACITY);
            g_xc_fathers[g_xc_father_count].head = head;
            g_xc_fathers[g_xc_father_count].body = body;
            if (vv1_xc_last_father(&log, name, head, body, &father)) {
                vv1_xc_set(&g_xc_fathers[g_xc_father_count].father.stash_head,
                           &g_xc_fathers[g_xc_father_count].father.stash_body,
                           g_xc_fathers[g_xc_father_count].father.stash_name, father);
                g_xc_fathers[g_xc_father_count].known = 1;
            }
            ++g_xc_father_count;
        }
    }
    vv1_xc_free(&log);
    g_xc_carry_ready = 1;
}

/* Was this villager carrying when the village was loaded?  -1 when that is not
   known (the list was not taken for this load). */
static int vv1_xc_was_carrying(const unsigned char *mother) {
    char name[VV1_NAME_CAPACITY];
    int i, head, body;
    if (!g_xc_carry_ready) {
        return -1;
    }
    vv1_copy_name(mother, name);
    head = *(const int *)(mother + VV1_HEAD_OFFSET);
    body = *(const int *)(mother + VV1_BODY_OFFSET);
    for (i = 0; i < g_xc_father_count; ++i) {
        if (g_xc_fathers[i].head == head && g_xc_fathers[i].body == body
            && strncmp(g_xc_fathers[i].mother, name, VV1_NAME_CAPACITY) == 0) {
            return 1;
        }
    }
    return 0;
}

/* The father the log confirmed for this mother's pregnancy, if any. */
static int vv1_xc_confirmed_father(const unsigned char *mother, vv1_parent_entry *out) {
    char name[VV1_NAME_CAPACITY];
    int i, head, body;
    if (g_xc_father_count == 0) {
        return 0;
    }
    vv1_copy_name(mother, name);
    head = *(const int *)(mother + VV1_HEAD_OFFSET);
    body = *(const int *)(mother + VV1_BODY_OFFSET);
    for (i = 0; i < g_xc_father_count; ++i) {
        if (g_xc_fathers[i].known && g_xc_fathers[i].head == head && g_xc_fathers[i].body == body
            && strncmp(g_xc_fathers[i].mother, name, VV1_NAME_CAPACITY) == 0) {
            *out = g_xc_fathers[i].father;
            return 1;
        }
    }
    return 0;
}

/* Work out, read-only, what the log says each living villager's entry should
   be, against the table as it stands (already followed to its villagers).
   A villager who arrived this session, and a stash set by a conception this
   session, are not in the log FILE yet (the session's records are written at
   the next save) and are left exactly as they are. */
static void vv1_xc_plan_build(const unsigned char *records, const vv1_xc_log *log, vv1_xc_plan *plan) {
    int j, k;
    memset(plan, 0, sizeof(*plan));
    for (j = 0; j < VV1_RECORD_COUNT; ++j) {
        const unsigned char *rec = records + (unsigned int)j * VV1_RECORD_STRIDE;
        char name[VV1_NAME_CAPACITY];
        int head, body, shared = 0, matches = 0, named = 0, agree = 1, what = VV1_XC_SAME;
        const vv1_xc_record *first = NULL;
        vv1_parent_entry after;
        int stash_changed = 0, stale = 0;
        if (!rec[VV1_OCCUPIED_OFFSET] || g_session_born[j]) {
            continue;
        }
        vv1_copy_name(rec, name);
        head = *(const int *)(rec + VV1_HEAD_OFFSET);
        body = *(const int *)(rec + VV1_BODY_OFFSET);
        shared = vv1_xc_shared(records, name, head, body);
        for (k = 0; k < log->count; ++k) {
            const vv1_xc_record *r = &log->items[k];
            if (r->kind != 1 || r->header != log->village_header) continue;
            if (strncmp(r->child.name, name, VV1_NAME_CAPACITY) == 0) ++named;
            if (!vv1_xc_is(&r->child, name, head, body)) continue;
            ++matches;
            if (first == NULL) {
                first = r;
            } else if (!vv1_xc_same_person(&first->father, &r->father)
                       || !vv1_xc_same_person(&first->mother, &r->mother)) {
                agree = 0;
            }
        }
        after = g_entries[j];
        if (matches > 0 && agree && matches >= shared) {
            vv1_xc_set(&after.father_head, &after.father_body, after.father_name, &first->father);
            vv1_xc_set(&after.mother_head, &after.mother_body, after.mother_name, &first->mother);
            if (!vv1_xc_parents_equal(&after, &g_entries[j])) {
                what = vv1_xc_has_parents(&g_entries[j]) ? VV1_XC_CORRECTED : VV1_XC_FILLED;
            }
        } else if (matches > 0 || named == 0) {
            /* Ambiguous (records disagree, or more living villagers share the
               three than there are births), or no Birth record of this name
               at all: no parents. */
            vv1_xc_person none;
            memset(&none, 0, sizeof(none));
            vv1_xc_set(&after.father_head, &after.father_body, after.father_name, &none);
            vv1_xc_set(&after.mother_head, &after.mother_body, after.mother_name, &none);
            if (vv1_xc_has_parents(&g_entries[j])) {
                what = matches > 0 ? VV1_XC_AMBIGUOUS : VV1_XC_CLEARED;
            }
        }
        /* else: Birth records of this name, none with these looks -- left as it is. */

        /* The pregnancy stash, for a mother carrying now: the father of her
           last logged conception, when nothing she delivered follows it. */
        /* ... or one who WAS carrying when the village was loaded: the
           catch-up may have delivered her before the check, and a delivery
           reported before the first frame leaves her stash in place -- after
           a crash, the same old save would deliver that pregnancy again from
           it. */
        if (shared == 1 && !g_session_stash[j]) {
            const vv1_xc_person *father = NULL;
            vv1_parent_entry carried;
            vv1_xc_person from_load;
            if (*(const int *)(rec + VV1_DUE_OFFSET) != 0) {
                if (!vv1_xc_last_father(log, name, head, body, &father)) {
                    father = NULL;
                }
            } else if (vv1_xc_confirmed_father(rec, &carried)) {
                memset(&from_load, 0, sizeof(from_load));
                from_load.present = 1;
                from_load.head = carried.stash_head ? carried.stash_head - 1 : VV1_XC_UNSET;
                from_load.body = carried.stash_body ? carried.stash_body - 1 : VV1_XC_UNSET;
                memcpy(from_load.name, carried.stash_name, VV1_NAME_CAPACITY);
                father = &from_load;
            }
            if (father != NULL) {
                vv1_xc_set(&after.stash_head, &after.stash_body, after.stash_name, father);
                stash_changed = after.stash_head != g_entries[j].stash_head
                    || after.stash_body != g_entries[j].stash_body
                    || strncmp(after.stash_name, g_entries[j].stash_name, VV1_NAME_CAPACITY) != 0;
            } else if (*(const int *)(rec + VV1_DUE_OFFSET) == 0
                       && *(const int *)(rec + VV1_LITTER_OFFSET) == 0
                       && vv1_xc_was_carrying(rec) == 0 && vv1_xc_has_stash(&g_entries[j])) {
                /* A STALE STASH (owner, 2026-10-04): an expected father kept
                   on a villager who is not expecting now and was not at the
                   load either -- the game's own record says so.  It is spent
                   only when the tick sees the delivery, so a delivery the
                   catch-up made in an earlier session left it behind; the
                   owner's village had seven.  A next fatherless delivery
                   would hand it on.  Cleared.  (Since #530 the tick spends
                   such a stash itself once the mother has been seen not
                   expecting for a strike window; this still lists one the
                   check meets first, so the player sees what changes.) */
                vv1_xc_person none;
                memset(&none, 0, sizeof(none));
                vv1_xc_set(&after.stash_head, &after.stash_body, after.stash_name, &none);
                stale = 1;
            }
        }
        if (what != VV1_XC_SAME || stash_changed || stale) {
            vv1_xc_change *c = &plan->changes[plan->count++];
            c->index = j;
            c->what = what;
            c->stash = stash_changed;
            c->stale = stale;
            c->before = g_entries[j];
            c->after = after;
            if (what == VV1_XC_CORRECTED) ++plan->corrected;
            if (what == VV1_XC_FILLED) ++plan->filled;
            if (what == VV1_XC_CLEARED) ++plan->cleared;
            if (what == VV1_XC_AMBIGUOUS) ++plan->ambiguous;
            if (stash_changed) ++plan->stashes;
            if (stale) ++plan->stale;
        }
    }
}

/* ---- the backup and the Repairs log ------------------------------------ */

/* Copy the parentage file to "<name>.before-v1.35.58-repair" (or "-2", "-3"
   ... when that is taken), never replacing anything.  1 copied, 0 failed;
   *none is set when there was no file to copy. */
static int vv1_xc_backup(int slot, char *backup, size_t n, int *none) {
    char path[MAX_PATH];
    int k;
    *none = 0;
    backup[0] = '\0';
    if (!vv1_parents_path(path, sizeof(path), slot)
        || (size_t)lstrlenA(path) + sizeof(VV1_XC_BACKUP_SUFFIX "-999") > n) {
        return 0;
    }
    if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) {
        DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
            *none = 1;
            return 1;
        }
        return 0;
    }
    for (k = 1; k < 1000; ++k) {
        if (k == 1) {
            wsprintfA(backup, "%s" VV1_XC_BACKUP_SUFFIX, path);
        } else {
            wsprintfA(backup, "%s" VV1_XC_BACKUP_SUFFIX "-%d", path, k);
        }
        if (CopyFileA(path, backup, TRUE)) {
            return 1;
        }
        if (GetLastError() != ERROR_FILE_EXISTS && GetLastError() != ERROR_ALREADY_EXISTS) {
            break;
        }
    }
    backup[0] = '\0';
    return 0;
}

static void vv1_xc_who(char *out, size_t n, const vv1_parent_entry *e) {
    if (!vv1_xc_has_parents(e)) {
        lstrcpynA(out, "no parents", (int)n);
        return;
    }
    wsprintfA(out, "father %s, mother %s",
              e->father_name[0] ? e->father_name : "(unknown)",
              e->mother_name[0] ? e->mother_name : "(unknown)");
}

/* Append one "Repair <n>" record listing every change to "Virtual Villagers
   Fun Patcher Logs\Repairs\Virtual Villagers 1 Repairs Log <n>.txt", under the
   village's own header line.  A note: a failure here undoes nothing. */
static int vv1_xc_append(const char *path, const char *text) {
    HANDLE file = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    DWORD wrote;
    BOOL ok;
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    ok = WriteFile(file, text, (DWORD)lstrlenA(text), &wrote, NULL) && wrote == (DWORD)lstrlenA(text);
    ok = FlushFileBuffers(file) && ok;
    CloseHandle(file);
    return ok ? 1 : 0;
}

static int vv1_xc_note(const vv1_xc_log *log, const vv1_xc_plan *plan, const unsigned char *records,
                       const char *backup, char *path_out) {
    char folder[MAX_PATH];
    char path[MAX_PATH];
    char *text;
    char *existing = NULL;
    const char *header = log->village_header >= 0 ? log->headers[log->village_header] : "";
    int file_number = 1, repairs = 0, need_header = 1, i;
    size_t len, cap;
    SYSTEMTIME now;
    HANDLE file;
    DWORD size, got = 0;
    int ok;
    if (!vv1_xc_subfolder(folder, sizeof(folder), "Virtual Villagers Fun Patcher Logs", "Repairs",
                          sizeof("\\Virtual Villagers 1 Repairs Log 99999.txt"))) {
        return 0;
    }
    /* The highest numbered file that is there; a new one past it when full. */
    for (;;) {
        wsprintfA(path, "%s\\Virtual Villagers 1 Repairs Log %d.txt", folder, file_number + 1);
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES || file_number >= 99999) break;
        ++file_number;
    }
    wsprintfA(path, "%s\\Virtual Villagers 1 Repairs Log %d.txt", folder, file_number);
    {
        /* Full by size before its record count (an Expanded-256 note is
           long): the next number, never a refusal (Codex, #522). */
        WIN32_FILE_ATTRIBUTE_DATA info;
        if (GetFileAttributesExA(path, GetFileExInfoStandard, &info)
            && (info.nFileSizeHigh != 0 || info.nFileSizeLow >= VV1_XC_REPAIRS_FILE_BYTES)) {
            ++file_number;
            wsprintfA(path, "%s\\Virtual Villagers 1 Repairs Log %d.txt", folder, file_number);
        }
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file != INVALID_HANDLE_VALUE) {
        size = GetFileSize(file, NULL);
        if (size != INVALID_FILE_SIZE && size < VV1_XC_MAX_FILE_BYTES) {
            existing = (char *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)size + 1);
            if (existing != NULL && !(ReadFile(file, existing, size, &got, NULL) && got == size)) {
                HeapFree(GetProcessHeap(), 0, existing);
                existing = NULL;
            }
        }
        CloseHandle(file);
        if (existing == NULL) {
            return 0;
        }
        {
            const char *p = existing;
            const char *last_header = NULL;
            while (*p) {
                if (vv1_xc_starts(p, "Repair ")) ++repairs;
                if (vv1_xc_starts(p, "Village:")) last_header = p;
                while (*p && *p != '\n') ++p;
                if (*p) ++p;
            }
            if (last_header != NULL) {
                size_t hl = (size_t)lstrlenA(header);
                need_header = !(strncmp(last_header, header, hl) == 0
                                && (last_header[hl] == '\r' || last_header[hl] == '\n' || last_header[hl] == '\0'));
            }
        }
        HeapFree(GetProcessHeap(), 0, existing);
        if (repairs >= VV1_XC_REPAIRS_PER_FILE) {
            ++file_number;
            wsprintfA(path, "%s\\Virtual Villagers 1 Repairs Log %d.txt", folder, file_number);
            repairs = 0;
            need_header = 1;
        }
    }
    /* Sized from the plan, so every change is listed (Codex, #522: a fixed
       64 KiB could not hold an Expanded-256 village's worst case, and the
       entries past it were dropped from the note while the table still
       changed).  Each change takes at most VV1_XC_NOTE_PER_CHANGE bytes -- two
       lines of a 27-character name and two "father X, mother Y" texts of at
       most 95 -- and the guard below refuses rather than truncate. */
    cap = VV1_XC_NOTE_FIXED + (size_t)plan->count * VV1_XC_NOTE_PER_CHANGE;
    text = (char *)HeapAlloc(GetProcessHeap(), 0, cap);
    if (text == NULL) {
        return 0;
    }
    GetLocalTime(&now);
    text[0] = '\0';
    if (need_header) {
        wsprintfA(text, "%s\r\n", header);
    }
    len = (size_t)lstrlenA(text);
    wsprintfA(text + len,
              "Repair %d\r\n"
              "  Date: %04u-%02u-%02u %02u:%02u:%02u\r\n"
              "  Checked: the parents recorded for each living villager, against the Births and Conceptions log\r\n",
              repairs + 1, now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond);
    for (i = 0; i < plan->count; ++i) {
        const vv1_xc_change *c = &plan->changes[i];
        char name[VV1_NAME_CAPACITY];
        char was[96], now_text[96];
        len = (size_t)lstrlenA(text);
        if (len + VV1_XC_NOTE_PER_CHANGE + VV1_XC_NOTE_TAIL > cap) {
            HeapFree(GetProcessHeap(), 0, text);   /* cannot happen by the sizing above; never a short note */
            return 0;
        }
        vv1_copy_name(records + (unsigned int)c->index * VV1_RECORD_STRIDE, name);
        vv1_xc_who(was, sizeof(was), &c->before);
        vv1_xc_who(now_text, sizeof(now_text), &c->after);
        if (c->what == VV1_XC_CORRECTED) {
            wsprintfA(text + len, "  Corrected: %s -- now %s (was %s)\r\n", name, now_text, was);
        } else if (c->what == VV1_XC_FILLED) {
            wsprintfA(text + len, "  Filled in: %s -- %s\r\n", name, now_text);
        } else if (c->what == VV1_XC_CLEARED) {
            wsprintfA(text + len, "  Set to unknown: %s -- no Birth record in the log (was %s)\r\n", name, was);
        } else if (c->what == VV1_XC_AMBIGUOUS) {
            wsprintfA(text + len, "  Set to unknown: %s -- the log cannot tell (was %s)\r\n", name, was);
        }
        if (c->stale) {
            len = (size_t)lstrlenA(text);
            wsprintfA(text + len, "  Pregnancy over: %s -- expected father %s cleared (not expecting)\r\n", name,
                      c->before.stash_name[0] ? c->before.stash_name : "(unnamed)");
        }
        if (c->stash) {
            len = (size_t)lstrlenA(text);
            wsprintfA(text + len, "  Pregnancy: %s -- father %s (was %s)\r\n", name,
                      c->after.stash_name, c->before.stash_name[0] ? c->before.stash_name : "unknown");
        }
    }
    len = (size_t)lstrlenA(text);
    if (backup != NULL && backup[0]) {
        const char *leaf = strrchr(backup, '\\');
        wsprintfA(text + len, "  Backup: %s\r\n", leaf ? leaf + 1 : backup);
    } else {
        lstrcpyA(text + len, "  Backup: none (there was no parentage file)\r\n");
    }
    ok = vv1_xc_append(path, text);
    HeapFree(GetProcessHeap(), 0, text);
    if (ok && path_out != NULL) {
        lstrcpyA(path_out, path);
    }
    return ok ? 1 : 0;
}

/* ---- the check --------------------------------------------------------- */

/* What the scan found: -1 cannot tell yet (no village, the table not this
   village's, a log or marker there and unreadable) -- ask again later; 0
   nothing to repair (the check had run, or it ran now and found nothing, or
   there is no Births log to check against: the marker records it); 1 found
   something: the plan is filled in and nothing has been changed. */
static int vv1_xc_scan(int slot, const unsigned char *records, vv1_xc_plan *plan) {
    vv1_xc_log log;
    int state, read, i;
    unsigned int village;
    memset(plan, 0, sizeof(*plan));
    if (records == NULL || slot < 1 || slot > 5) {
        return -1;
    }
    read = vv1_xc_read_log(&log, slot);
    if (read < 0) {
        return -1;                          /* the log is there and unreadable: later */
    }
    village = read == 1 ? vv1_xc_village_id(log.headers[log.village_header]) : 0u;
    /* Every load checks again, whatever the marker says (the owner's two
       Sukis, 2026-10-06: the check had found the village clean once, the
       table later lost their parents in a repack, and the marker kept it
       from ever looking again).  The marker is the last result's record; one
       that cannot be read still means "later". */
    state = vv1_xc_marker_state(slot, village);
    if (state < 0) {
        vv1_xc_free(&log);
        return -1;                          /* the marker cannot be read */
    }
    if (read == 1) {
        /* A log that holds this village's conceptions but not one Birth
           cannot say who was born here: as good as none.  (Every birth this
           companion records is logged as it happens, so a village with
           children has Birth records.) */
        int births = 0;
        for (i = 0; i < log.count; ++i) {
            births += log.items[i].kind == 1 && log.items[i].header == log.village_header;
        }
        if (births == 0) {
            read = 0;
        }
    }
    if (read == 0) {
        vv1_xc_free(&log);
        vv1_xc_marker_write(slot, VV1_XC_RESULT_NO_LOG, NULL, village);
        return 0;
    }
    vv1_xc_plan_build(records, &log, plan);
    vv1_xc_free(&log);
    if (plan->count == 0) {
        vv1_xc_marker_write(slot, VV1_XC_RESULT_CLEAN, plan, village);
        return 0;
    }
    return 1;
}

/* The player chose Repair: rebuild the plan from the log as it stands now
   (the same rules; a birth since the prompt is already right), back the file
   up, note every change in the Repairs log, write the table, and record that
   the check ran.  The note comes before the table so a repair is never made
   without its record: a note that cannot be written stops the repair (the
   backup just made is removed again), and a table that then cannot be
   written is noted as not applied.  1: done (or nothing was left to do); 0:
   nothing was changed, and the next load asks again. */
static int vv1_xc_apply(int slot, const unsigned char *records) {
    static vv1_xc_plan plan;
    static vv1_parent_entry saved[VV1_RECORD_COUNT];
    vv1_xc_log log;
    char backup[MAX_PATH];
    char note[MAX_PATH];
    int found, read, i, none;
    unsigned int village;
    found = vv1_xc_scan(slot, records, &plan);
    if (found <= 0) {
        return found == 0;
    }
    read = vv1_xc_read_log(&log, slot);
    if (read <= 0) {
        return 0;
    }
    if (!vv1_xc_backup(slot, backup, sizeof(backup), &none)) {
        vv1_xc_free(&log);
        return 0;
    }
    if (!vv1_xc_note(&log, &plan, records, none ? NULL : backup, note)) {
        if (!none) {
            DeleteFileA(backup);          /* this call's own copy: nothing was repaired */
        }
        vv1_xc_free(&log);
        return 0;
    }
    village = vv1_xc_village_id(log.headers[log.village_header]);
    vv1_xc_free(&log);
    memcpy(saved, g_entries, sizeof(saved));
    for (i = 0; i < plan.count; ++i) {
        g_entries[plan.changes[i].index] = plan.changes[i].after;
    }
    if (!vv1_parents_save(slot, records)) {
        memcpy(g_entries, saved, sizeof(g_entries));   /* not written: not shown either */
        vv1_xc_append(note, "  Not applied: the parentage file could not be written; nothing was changed.\r\n\r\n");
        if (!none) {
            DeleteFileA(backup);
        }
        return 0;
    }
    vv1_xc_append(note, "\r\n");          /* the record's closing blank line */
    vv1_xc_marker_write(slot, VV1_XC_RESULT_REPAIRED, &plan, village);
    g_xc_father_count = 0;            /* the stashes are the log's now */
    return 1;
}
