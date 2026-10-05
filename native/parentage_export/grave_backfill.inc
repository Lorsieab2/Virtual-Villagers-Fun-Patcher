/* Every grave gets a Death record -- the graves the Deaths log never saw.
   Included by parentage_export.c; the call is RecordGravesMissingFromLog
   (native/shared/grave_backfill.h has the hand-off and the reasons).

   The Deaths log records a death when it happens: at the burial, from a hook
   "VVFP Cause of Death.dll" installs (at game start since v1.35.58, through
   "VVFP Startup.dll"; earlier, once a village was shown).  A grave dug
   before the log existed (the owner's A New Home: Kito and Chika, buried
   before v1.35.51), or while an older build was catching up on time away
   (its load-time catch-up ran before that install), has no Death record, so the
   log disagreed with the graveyard.  At each save Cause of Death hands every
   grave here, marked when it already knows the log has its record (it keeps
   that in its own file); this decides the rest and files a record for each
   grave the log lacks.

   WHICH GRAVES THE LOG ALREADY HAS.  A Death record names the villager and
   the age at death -- exactly what a grave holds, the age in the game's own
   units -- so a grave and its record share that key.  The skill line is not
   part of it: a record written another way (by hand, or by an older build)
   may word it differently, and the name with the exact age at death is
   already the strongest identity both hold.  Names repeat and two graves can
   share both, so it is a count, never a lookup: the village's Death records
   with a key (in its Deaths log files, and those still held for the next
   save), less the graves with that key already known to be covered, are
   matched to the uncovered graves with it in burial order; only the graves
   left over get a record.  A record whose grave line is "no grave ..." is a
   body that was never buried, so it is no grave's record.  So a grave is
   never recorded twice, and when in doubt the existing record is taken to be
   its record.

   WHAT THE RECORD SAYS.  The name, the age at death, the skill line, the
   epitaph and -- where the game or the patcher's graves file keeps it -- the
   cause, all from the grave.  A grave keeps no head, body, likes or
   dislikes; those come from the Village History log, which lists every
   villager at every save: the villager's last snapshot in this village
   before the grave's age (see history_details).  Where that does not settle
   it they are printed as unknown, never guessed.  Two closing lines say the
   record was made from the grave and where the details came from.

   The records are numbered on from the log's last "Death <n>" and filed like
   every other record (held for the save when the village cannot be vouched
   for).  Nothing already in a log is rewritten. */

#include "grave_backfill.h"

#define BACKFILL_NAME 64
#define BACKFILL_LINE 160

struct death_key {
    char name[BACKFILL_NAME];
    int age;
    char grave[VV_GRAVE_LINE];
    int held;              /* a record still held for the save, not on disk */
};

static struct death_key *death_keys;
static int death_key_count;
static int death_key_capacity;

static void trim_line(char *line) {
    size_t n = strlen(line);
    while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) {
        line[--n] = '\0';
    }
}

/* "  <label>: <value>" -> value, or NULL. */
static const char *line_value(const char *line, const char *label) {
    size_t n = strlen(label);
    if (line[0] != ' ' || line[1] != ' ' || strncmp(line + 2, label, n) != 0
        || line[2 + n] != ':' || line[3 + n] != ' ') {
        return NULL;
    }
    return line + 4 + n;
}

/* One Death record being read: its lines arrive one at a time. */
struct death_reader {
    int open;
    int have_name, have_age, have_grave;
    struct death_key key;
};

static int keep_death_key(const struct death_key *key) {
    if (death_key_count >= death_key_capacity) {
        int capacity = death_key_capacity == 0 ? 64 : death_key_capacity * 2;
        struct death_key *grown = (struct death_key *)realloc(
            death_keys, (size_t)capacity * sizeof(*death_keys));
        if (grown == NULL) {
            return 0;
        }
        death_keys = grown;
        death_key_capacity = capacity;
    }
    death_keys[death_key_count++] = *key;
    return 1;
}

/* Ends the record being read; 0 only when it could not be kept.  A record
   counts only when it `ended` with the blank line every record is written
   with, and has its name, age at death and grave: one cut short by an
   interrupted append (the next "Death <n>", the file's end) is no grave's
   record (Codex, #524). */
static int death_reader_close(struct death_reader *r, int ended) {
    int ok = 1;
    if (ended && r->open && r->have_name && r->have_age && r->have_grave
        && strncmp(r->key.grave, "no grave", 8) != 0) {
        ok = keep_death_key(&r->key);
    }
    memset(r, 0, sizeof(*r));
    return ok;
}

/* A line of a Deaths log, or of a held record's text (which has no "Death
   <n>" line: `open` is set by the caller). */
static int death_reader_line(struct death_reader *r, char *line) {
    const char *value;
    trim_line(line);
    if (strncmp(line, "Death ", 6) == 0 && line[6] >= '0' && line[6] <= '9') {
        if (!death_reader_close(r, 0)) {
            return 0;
        }
        r->open = 1;
        return 1;
    }
    if (line[0] != ' ') {
        return death_reader_close(r, 1);   /* a blank line, a heading, another kind */
    }
    if (!r->open) {
        return 1;
    }
    if ((value = line_value(line, "Name")) != NULL) {
        _snprintf_s(r->key.name, sizeof r->key.name, _TRUNCATE, "%s", value);
        r->have_name = 1;
    } else if ((value = line_value(line, "Age at death")) != NULL) {
        r->key.age = atoi(value);
        r->have_age = 1;
    } else if ((value = line_value(line, "Grave")) != NULL) {
        _snprintf_s(r->key.grave, sizeof r->key.grave, _TRUNCATE, "%s", value);
        r->have_grave = 1;
    }
    return 1;
}

/* Every Death record this village's Deaths log holds -- in each of its files,
   and still held for the next save -- into death_keys.  0 when a file of the
   log could not be read, so nothing is decided on half a log. */
static int read_village_deaths(const struct game_layout *g, int game_id, const char *village) {
    wchar_t folder[MAX_PATH];
    wchar_t path[MAX_LOG_PATH];
    char line[512];
    struct death_reader reader;
    int ceiling;
    int number;
    int i;

    death_key_count = 0;
    if (!build_family_log_path(g, LOG_DEATHS, 1, path)
        || !vv_save_subfolder_w(folder, family_folder(LOG_DEATHS), 64)) {
        return 0;
    }
    ceiling = highest_log_number(family_stem(g, LOG_DEATHS), folder);
    for (number = 1; number <= ceiling; ++number) {
        FILE *file;
        if (!build_family_log_path(g, LOG_DEATHS, number, path)) {
            return 0;
        }
        if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES
            || !log_belongs_to_village(path, village)) {
            continue;
        }
        file = _wfopen(path, L"rb");
        if (file == NULL) {
            return 0;
        }
        memset(&reader, 0, sizeof reader);
        while (fgets(line, (int)sizeof line, file) != NULL) {
            if (!death_reader_line(&reader, line)) {
                fclose(file);
                return 0;
            }
        }
        /* fgets stops at an I/O error as it does at the end: a log read only
           in part decides nothing (Codex, #524). */
        if (ferror(file)) {
            fclose(file);
            return 0;
        }
        fclose(file);
        if (!death_reader_close(&reader, 0)) {
            return 0;
        }
    }
    /* Held records: written at the next save.  Only those taken from the
       tribe loaded now (or whose tribe was never known) can be this village's
       (Codex, #524); a match on one is never kept as covered (VV_GRAVE_HELD). */
    {
        int now_known = tribes_ready() && take_tribe(game_id, NULL, scratch_tribe);
        for (i = 0; i < pending_count; ++i) {
            const char *at;
            int first = death_key_count;
            if (pending[i].game_id != game_id || pending[i].kind != KIND_DEATH || pending[i].text == NULL) {
                continue;
            }
            if (now_known && pending[i].tribe >= 0
                && !same_tribe(&held_tribes[pending[i].tribe], scratch_tribe, TRIBE_LOOSE)) {
                continue;
            }
            memset(&reader, 0, sizeof reader);
            reader.open = 1;
        at = pending[i].text;
        while (*at != '\0') {
            const char *end = strchr(at, '\n');
            size_t n = end != NULL ? (size_t)(end - at) : strlen(at);
            if (n >= sizeof line) {
                n = sizeof line - 1;
            }
            memcpy(line, at, n);
            line[n] = '\0';
            if (!death_reader_line(&reader, line)) {
                return 0;
            }
            at = end != NULL ? end + 1 : at + strlen(at);
            }
            if (!death_reader_close(&reader, 0)) {
                return 0;
            }
            for (; first < death_key_count; ++first) {
                death_keys[first].held = 1;
            }
        }
    }
    return 1;
}

/* ---- The Village History log ------------------------------------------------

   "<save folder>\Virtual Villagers Fun Patcher Logs\Tribe History\Village
   History <n>.txt" (native/population_export): at every save, a snapshot
   headed "=== <game> -- <date time> ===" and "Village: <name> (Save <n>)",
   then every villager in the village as "Villager <k>" with "  Name:",
   "  Age:", "  Head:", "  Body:" and, when the villager has one,
   "  Likes:" / "  Dislikes:".

   Which villager a grave was.  Only this village's snapshots are read.  A
   villager is told apart from a namesake by its head and body (an
   "identity": name, head, body).  The grave's villager is the identity that
   - was never listed OLDER than the grave's age at death (whoever was lived
     past that age, and their namesakes with the same looks, are not them);
   - is not in the village now;
   - was listed last at the highest age of those left (the closest to the
     age at death; two different identities tied there -> unknown);
   - and is not a better fit for another grave being recorded now.
   Its details are those of its latest snapshot.  The snapshot's date and the
   age it shows are printed with them, so a reader can see the gap. */

#define IDENTITIES_PER_GRAVE 8

struct identity {
    int head, body;
    int seen_age;          /* the age at its latest snapshot, whatever it was */
    int last_age;          /* the age at its latest snapshot within the grave's age */
    int outlived;          /* listed older than the grave's age */
    int alive;             /* in the village now */
    char likes[64];
    char dislikes[64];
    char when[32];
};

struct backfill_target {
    vv_grave_fact *fact;
    char name[BACKFILL_NAME];
    int identity_count;
    int overflow;
    struct identity identity[IDENTITIES_PER_GRAVE];
    int chosen;            /* index into identity, -1 = unknown */
    int ambiguous;
};

struct history_villager {
    int open;
    char name[BACKFILL_NAME];
    int age, head, body;
    int have_age, have_head, have_body;
    char likes[64];
    char dislikes[64];
};

static void history_villager_done(struct history_villager *v, struct backfill_target *targets,
                                  int count, const char *when) {
    int t, k;
    if (!v->open || !v->have_age || !v->have_head || !v->have_body) {
        memset(v, 0, sizeof(*v));
        return;
    }
    for (t = 0; t < count; ++t) {
        struct backfill_target *target = &targets[t];
        struct identity *id = NULL;
        if (strcmp(target->name, v->name) != 0) {
            continue;
        }
        for (k = 0; k < target->identity_count; ++k) {
            if (target->identity[k].head == v->head && target->identity[k].body == v->body) {
                id = &target->identity[k];
                break;
            }
        }
        if (id == NULL) {
            if (target->identity_count >= IDENTITIES_PER_GRAVE) {
                target->overflow = 1;
                continue;
            }
            id = &target->identity[target->identity_count++];
            memset(id, 0, sizeof(*id));
            id->head = v->head;
            id->body = v->body;
            id->last_age = -1;
            id->seen_age = -1;
        }
        /* Younger than at its last snapshot: made young again (the Origins
           Youth upgrade) or an older save restored.  Whatever age it was
           listed at before no longer says it outlived the grave (Codex,
           #524). */
        if (v->age < id->seen_age) {
            id->outlived = 0;
        }
        id->seen_age = v->age;
        if (v->age > target->fact->age) {
            id->outlived = 1;
        } else {
            /* Snapshots are read oldest first: the latest one wins. */
            id->last_age = v->age;
            lstrcpynA(id->likes, v->likes[0] ? v->likes : "(none)", (int)sizeof id->likes);
            lstrcpynA(id->dislikes, v->dislikes[0] ? v->dislikes : "(none)", (int)sizeof id->dislikes);
            lstrcpynA(id->when, when, (int)sizeof id->when);
        }
    }
    memset(v, 0, sizeof(*v));
}

/* The Village History files, oldest first, each read once for every grave
   being recorded. */
/* A snapshot counts only when its heading names this game ("=== Virtual
   Villagers <n> -- ..."; renamed games can share a save folder, and with it
   the Village History files, under the same village name -- Codex, #524)
   and its "Village:" line names this village.  A villager counts only once
   its record has ended with the blank line the exporter writes after it: a
   record cut short (an interrupted append, the file's end) is dropped, never
   finished with "(none)" for the lines it lost (Codex, #524).

   0 when a History file that exists cannot be read to its end (locked, a
   read error): a newer snapshot in it could show a candidate outlived the
   grave, so nothing is decided from the files that could be read, and the
   graves are asked about again at the next save (Codex, #524). */
/* The Village History files, oldest first: -1 the unnumbered file an older
   build kept in the retired "VVFP Logs" folder, 0 the unnumbered file in
   today's folder (both moved to "Village History 1.txt" by the population
   exporter, which on a village's first patched save may run after this --
   Codex, #524), then "Village History <n>.txt".  0 when there is no path. */
static int history_path(const wchar_t *folder, int number, wchar_t *out) {
    if (number == -1) {
        wchar_t root[MAX_LOG_PATH];
        return vv_save_folder_w(root, 96)
            && _snwprintf_s(out, MAX_LOG_PATH, _TRUNCATE,
                            L"%ls\\VVFP Logs\\Tribe History\\Village History.txt", root) >= 0;
    }
    if (number == 0) {
        return _snwprintf_s(out, MAX_LOG_PATH, _TRUNCATE, L"%ls\\Village History.txt", folder) >= 0;
    }
    return _snwprintf_s(out, MAX_LOG_PATH, _TRUNCATE, L"%ls\\Village History %d.txt",
                        folder, number) >= 0;
}

/* The names this village's snapshots were headed with.  The Rename Tribe
   tool never rewrites a snapshot: it appends "Tribe renamed from <old> to
   <new> on YYYY-MM-DD (Save <n>)" to the newest History file
   (village_rename.h), so the snapshots before it still say "Village: <old>
   (Save <n>)" (Codex, #524).  Starting from the header now, each such note
   naming one of the headers known so far adds the header it was renamed
   from; a chain of renames is followed back to the first name. */
#define HISTORY_ALIASES 16
#define HISTORY_NOTES 64

static int history_aliases(const char *current, char notes[][256], int note_count,
                           char aliases[][256]) {
    int count = 1;
    int k;
    int grew = 1;
    lstrcpynA(aliases[0], current, 256);
    while (grew) {
        grew = 0;
        for (k = 0; k < count && count < HISTORY_ALIASES; ++k) {
            const char *save = NULL;
            const char *scan = aliases[k];
            const char *name = aliases[k] + VV_RENAME_HEADER_PREFIX_LENGTH;
            size_t name_length;
            int j;
            for (;;) {                        /* the LAST " (Save " */
                const char *hit = strstr(scan, " (Save ");
                if (hit == NULL) {
                    break;
                }
                save = hit;
                scan = hit + 1;
            }
            if (save == NULL || strncmp(aliases[k], VV_RENAME_HEADER_PREFIX, VV_RENAME_HEADER_PREFIX_LENGTH) != 0) {
                continue;
            }
            name_length = (size_t)(save - name);
            for (j = 0; j < note_count; ++j) {
                /* "Tribe renamed from <old> to <name> on YYYY-MM-DD<save>" */
                const char *note = notes[j];
                size_t length = strlen(note);
                size_t save_length = strlen(save);
                size_t tail = 4 + name_length + VV_RENAME_DATE_TAIL + save_length;   /* " to " name date save */
                char older[256];
                int m;
                int known = 0;
                if (length <= VV_RENAME_PREFIX_LENGTH + tail
                    || strcmp(note + length - save_length, save) != 0
                    || strncmp(note + length - tail, " to ", 4) != 0
                    || strncmp(note + length - tail + 4, name, name_length) != 0
                    || strncmp(note + length - save_length - VV_RENAME_DATE_TAIL, " on ", 4) != 0) {
                    continue;
                }
                _snprintf_s(older, sizeof older, _TRUNCATE, "%s%.*s%s", VV_RENAME_HEADER_PREFIX,
                            (int)(length - VV_RENAME_PREFIX_LENGTH - tail),
                            note + VV_RENAME_PREFIX_LENGTH, save);
                for (m = 0; m < count; ++m) {
                    known |= strcmp(aliases[m], older) == 0;
                }
                if (!known && count < HISTORY_ALIASES) {
                    lstrcpynA(aliases[count++], older, 256);
                    grew = 1;
                }
            }
        }
    }
    return count;
}

static int read_history(int game_id, const char *village, struct backfill_target *targets, int count) {
    wchar_t folder[MAX_LOG_PATH];
    wchar_t path[MAX_LOG_PATH];
    char line[512];
    char current[256];
    char heading[32];
    char when[32];
    struct history_villager v;
    int ceiling;
    int number;
    int pass;
    size_t n;
    static char notes[HISTORY_NOTES][256];
    static char aliases[HISTORY_ALIASES][256];
    int note_count = 0;
    int alias_count = 1;

    _snprintf_s(current, sizeof current, _TRUNCATE, "%s", village);
    trim_line(current);
    _snprintf_s(heading, sizeof heading, _TRUNCATE, "=== Virtual Villagers %d -- ", game_id);
    if (!vv_save_subfolder_w(folder, L"Virtual Villagers Fun Patcher Logs\\Tribe History", 64)) {
        return 0;
    }
    ceiling = highest_log_number(L"Village History", folder);
    lstrcpynA(aliases[0], current, 256);
    /* Pass 0 gathers the rename notes, pass 1 the snapshots. */
    for (pass = 0; pass < 2; ++pass) {
    if (pass == 1) {
        alias_count = history_aliases(current, notes, note_count, aliases);
    }
    for (number = -1; number <= ceiling; ++number) {
        FILE *file;
        int ours = 0;
        int expect_village = 0;
        if (!history_path(folder, number, path)) {
            return 0;
        }
        if (GetFileAttributesW(path) == INVALID_FILE_ATTRIBUTES) {
            continue;                         /* a number never written */
        }
        file = _wfopen(path, L"rb");
        if (file == NULL) {
            return 0;
        }
        memset(&v, 0, sizeof v);
        when[0] = '\0';
        while (fgets(line, (int)sizeof line, file) != NULL) {
            const char *value;
            trim_line(line);
            if (pass == 0) {
                if (vv_rename_is_note(line) && note_count < HISTORY_NOTES) {
                    lstrcpynA(notes[note_count++], line, 256);
                }
                continue;
            }
            if (strncmp(line, "=== ", 4) == 0) {
                const char *dash = strstr(line, " -- ");
                memset(&v, 0, sizeof v);          /* a villager not ended: dropped */
                ours = 0;
                expect_village = strncmp(line, heading, strlen(heading)) == 0;
                when[0] = '\0';
                if (dash != NULL) {
                    lstrcpynA(when, dash + 4, (int)sizeof when);
                    n = strlen(when);
                    if (n >= 4 && strcmp(when + n - 4, " ===") == 0) {
                        when[n - 4] = '\0';
                    }
                }
                continue;
            }
            if (expect_village) {
                int a;
                expect_village = 0;
                ours = 0;
                for (a = 0; a < alias_count; ++a) {
                    ours |= aliases[a][0] != '\0' && strcmp(line, aliases[a]) == 0;
                }
                continue;
            }
            if (!ours) {
                continue;
            }
            if (strncmp(line, "Villager ", 9) == 0) {
                memset(&v, 0, sizeof v);          /* a villager not ended: dropped */
                v.open = 1;
                continue;
            }
            if (line[0] == '\0') {
                history_villager_done(&v, targets, count, when);
                continue;
            }
            if (!v.open) {
                continue;
            }
            if ((value = line_value(line, "Name")) != NULL) {
                lstrcpynA(v.name, value, (int)sizeof v.name);
            } else if ((value = line_value(line, "Age")) != NULL) {
                v.age = atoi(value);
                v.have_age = 1;
            } else if ((value = line_value(line, "Head")) != NULL) {
                v.head = atoi(value);
                v.have_head = 1;
            } else if ((value = line_value(line, "Body")) != NULL) {
                v.body = atoi(value);
                v.have_body = 1;
            } else if ((value = line_value(line, "Likes")) != NULL) {
                lstrcpynA(v.likes, value, (int)sizeof v.likes);
            } else if ((value = line_value(line, "Dislikes")) != NULL) {
                lstrcpynA(v.dislikes, value, (int)sizeof v.dislikes);
            }
        }
        if (ferror(file)) {
            fclose(file);
            return 0;
        }
        fclose(file);                         /* a villager still open at the end: dropped */
    }
    }
    return 1;
}

/* Who is in the village now: an identity still here is not a grave's. */
static void mark_alive(int game_id, struct backfill_target *targets, int count) {
    const struct game_layout *g = layout_of(game_id);
    const unsigned char *records = villager_table(game_id);
    int slot, t, k;
    if (records == NULL
        || !memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride)) {
        return;
    }
    for (slot = 0; slot < g->slots; ++slot) {
        const unsigned char *record = records + g->record_base + (size_t)slot * g->stride;
        char name[MAX_NAME_BYTES];
        int head, body;
        if (*(const unsigned char *)(record + g->active) != 1) {
            continue;
        }
        copy_villager_name(g, record, name, sizeof name);
        head = *(const int *)(record + g->head);
        body = *(const int *)(record + g->body);
        for (t = 0; t < count; ++t) {
            if (strcmp(targets[t].name, name) != 0) {
                continue;
            }
            for (k = 0; k < targets[t].identity_count; ++k) {
                if (targets[t].identity[k].head == head && targets[t].identity[k].body == body) {
                    targets[t].identity[k].alive = 1;
                }
            }
        }
    }
}

static void choose_identities(struct backfill_target *targets, int count) {
    int t, u, k;
    for (t = 0; t < count; ++t) {
        struct backfill_target *target = &targets[t];
        int best = -1;
        target->chosen = -1;
        target->ambiguous = target->overflow;
        if (target->overflow) {
            continue;
        }
        for (k = 0; k < target->identity_count; ++k) {
            const struct identity *id = &target->identity[k];
            if (id->outlived || id->alive || id->last_age < 0) {
                continue;
            }
            if (best < 0 || id->last_age > target->identity[best].last_age) {
                best = k;
                target->ambiguous = 0;
            } else if (id->last_age == target->identity[best].last_age) {
                target->ambiguous = 1;
            }
        }
        if (!target->ambiguous) {
            target->chosen = best;
        }
    }
    /* One villager, one grave: when two graves being recorded chose the same
       identity, it stays with the grave whose age at death it is closest to
       (both lose it on a tie). */
    for (t = 0; t < count; ++t) {
        const struct identity *a;
        int keep = 1;
        if (targets[t].chosen < 0) {
            continue;
        }
        a = &targets[t].identity[targets[t].chosen];
        for (u = 0; u < count; ++u) {
            const struct identity *b;
            int gap_t, gap_u;
            if (u == t || targets[u].chosen < 0 || strcmp(targets[u].name, targets[t].name) != 0) {
                continue;
            }
            b = &targets[u].identity[targets[u].chosen];
            if (b->head != a->head || b->body != a->body) {
                continue;
            }
            gap_t = targets[t].fact->age - a->last_age;
            gap_u = targets[u].fact->age - b->last_age;
            if (gap_u <= gap_t) {
                keep = 0;
            }
        }
        if (!keep) {
            targets[t].ambiguous = 1;
        }
    }
    for (t = 0; t < count; ++t) {
        if (targets[t].ambiguous) {
            targets[t].chosen = -1;
        }
    }
}

static const char BACKFILL_NOTE[] =
    "  Recorded from the grave: this death was not seen when it happened (it came before\n"
    "    this log was kept, or while the game was catching up on time away)\n";

static int write_backfill(int game_id, const struct backfill_target *target) {
    char text[RECORD_TEXT_MAX];
    char looks[512];
    char source[256];
    const vv_grave_fact *f = target->fact;
    int written;
    if (target->chosen >= 0) {
        const struct identity *id = &target->identity[target->chosen];
        _snprintf_s(looks, sizeof looks, _TRUNCATE,
                    "  Head: %d\n  Body: %d\n  Likes: %s\n  Dislikes: %s\n",
                    id->head, id->body, id->likes, id->dislikes);
        _snprintf_s(source, sizeof source, _TRUNCATE,
                    "  Head, body, likes and dislikes: from the Village History snapshot of %s"
                    " (age %d then)\n", id->when, id->last_age);
    } else {
        _snprintf_s(looks, sizeof looks, _TRUNCATE, "%s",
                    "  Head: (unknown)\n  Body: (unknown)\n  Likes: (unknown)\n  Dislikes: (unknown)\n");
        _snprintf_s(source, sizeof source, _TRUNCATE, "%s",
                    target->ambiguous
                        ? "  Head, body, likes and dislikes: unknown -- the grave does not keep them, and"
                          " more than one villager in the Village History log could be this one\n"
                        : "  Head, body, likes and dislikes: unknown -- the grave does not keep them, and"
                          " the Village History log does not list this villager\n");
    }
    written = _snprintf(text, sizeof text,
                        "  Name: %s\n"
                        "  Age at death: %d\n"
                        "  Cause of death: %s\n"
                        "  Grave: %s\n"
                        "  Epitaph: %s\n"
                        "%s%s%s\n",
                        target->name, f->age, f->cause, f->grave,
                        f->epitaph[0] ? f->epitaph : "(none)", looks, BACKFILL_NOTE, source);
    if (written < 0 || (size_t)written >= sizeof text) {
        return 0;
    }
    return emit_record(game_id, KIND_DEATH, NULL, text);
}

/* The header of the village the slot's own save file holds, from "VVFP Save
   Reset.dll" in the patcher's folder (shipped with this log's row); loaded
   by full path, never from DllMain.  0 without it. */
static int saved_village_header(int game_id, int slot, char *out, int size) {
    typedef int (__stdcall *saved_header_fn)(int, int, char *, int);
    HMODULE module = vvfp_patcher_dll("VVFP Save Reset.dll");
    saved_header_fn header;
    if (module == NULL) {
        return 0;
    }
    header = (saved_header_fn)GetProcAddress(module, "SavedVillageHeader");
    return header != NULL && header(game_id, slot, out, size);
}

static int same_key(const struct death_key *key, const char *name, const vv_grave_fact *f) {
    return key->age == f->age && strcmp(key->name, name) == 0;
}

__declspec(dllexport) int __stdcall RecordGravesMissingFromLog(
    int game_id,
    const void *save_buffer,
    int slot,
    vv_grave_fact *graves,
    int count,
    int apply
) {
    const struct game_layout *g;
    char village_name[VV_VILLAGE_NAME_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    struct backfill_target *targets;
    char (*names)[BACKFILL_NAME];
    int target_count = 0;
    int recorded = 0;
    int i, j;

    if (game_id < GAME_VV1 || game_id > GAME_VV5
        || slot < 1 || slot > 5 || graves == NULL || count <= 0 || count > 500) {
        return -1;
    }
    for (i = 0; i < count; ++i) {
        graves[i].outcome = VV_GRAVE_UNDECIDED;
        graves[i].identified = 0;
    }
    g = layout_of(game_id);
    if (!layout_is_usable(g)) {
        return -1;
    }
    /* The village this save is, exactly as its logs are headed
       (PublishVillageAtSave); a village just loaded, from its save file. */
    if (save_buffer != NULL) {
        if (!vv_village_name(game_id, (const unsigned char *)save_buffer - 8, village_name)) {
            village_name[0] = '\0';
        }
        if (!vv_village_header(village, sizeof village, village_name, slot)) {
            village[0] = '\0';
        }
    } else if (!saved_village_header(game_id, slot, village, (int)sizeof village)) {
        village[0] = '\0';
    }
    if (village[0] == '\0') {
        return -1;
    }
    if (!read_village_deaths(g, game_id, village)) {
        return -1;
    }
    names = (char (*)[BACKFILL_NAME])calloc((size_t)count, BACKFILL_NAME);
    targets = (struct backfill_target *)calloc((size_t)count, sizeof(*targets));
    if (names == NULL || targets == NULL) {
        free(names);
        free(targets);
        return -1;
    }
    /* The name as a Death record prints it. */
    for (i = 0; i < count; ++i) {
        graves[i].name[VV_GRAVE_NAME - 1] = '\0';
        graves[i].grave[VV_GRAVE_LINE - 1] = '\0';
        graves[i].cause[VV_GRAVE_CAUSE - 1] = '\0';
        graves[i].epitaph[VV_GRAVE_EPITAPH - 1] = '\0';
        copy_name_field((const unsigned char *)graves[i].name, names[i], BACKFILL_NAME,
                        g->name_capacity < VV_GRAVE_NAME - 1 ? g->name_capacity : VV_GRAVE_NAME - 1);
    }
    /* Which uncovered graves the log already has a record for: per key, the
       records less the covered graves, in burial order -- first those on
       disk (VV_GRAVE_IN_LOG), then those still held (VV_GRAVE_HELD). */
    for (i = 0; i < count; ++i) {
        int on_disk = 0;
        int held = 0;
        int taken = 0;
        if (graves[i].covered) {
            continue;
        }
        for (j = 0; j < death_key_count; ++j) {
            if (same_key(&death_keys[j], names[i], &graves[i])) {
                if (death_keys[j].held) {
                    ++held;
                } else {
                    ++on_disk;
                }
            }
        }
        for (j = 0; j < count; ++j) {
            if (j == i || graves[j].age != graves[i].age || strcmp(names[j], names[i]) != 0) {
                continue;
            }
            if (graves[j].covered || graves[j].outcome == VV_GRAVE_IN_LOG
                || graves[j].outcome == VV_GRAVE_HELD) {
                ++taken;
            }
        }
        if (on_disk > taken) {
            graves[i].outcome = VV_GRAVE_IN_LOG;
        } else if (on_disk + held > taken) {
            graves[i].outcome = VV_GRAVE_HELD;
        } else if (!apply) {
            graves[i].outcome = VV_GRAVE_MISSING;
            ++recorded;
        } else {
            targets[target_count].fact = &graves[i];
            lstrcpynA(targets[target_count].name, names[i], BACKFILL_NAME);
            ++target_count;
        }
    }
    if (target_count > 0 && !read_history(game_id, village, targets, target_count)) {
        for (i = 0; i < count; ++i) {
            graves[i].outcome = VV_GRAVE_UNDECIDED;
        }
        free(names);
        free(targets);
        return -1;
    }
    if (target_count > 0) {
        mark_alive(game_id, targets, target_count);
        choose_identities(targets, target_count);
        for (i = 0; i < target_count; ++i) {
            int held_before = pending_count;
            vv_grave_fact *f = targets[i].fact;
            if (write_backfill(game_id, &targets[i])) {
                /* On disk, or held for the save (a publisher not yet run, a
                   locked log): only a record on disk is durable. */
                f->outcome = pending_count > held_before ? VV_GRAVE_QUEUED : VV_GRAVE_RECORDED;
                if (targets[i].chosen >= 0) {
                    f->identified = 1;
                    f->head = targets[i].identity[targets[i].chosen].head;
                    f->body = targets[i].identity[targets[i].chosen].body;
                }
                ++recorded;
            }
        }
    }
    free(names);
    free(targets);
    return recorded;
}
