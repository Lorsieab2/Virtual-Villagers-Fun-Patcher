/* Every villager who arrived before the Arrived record existed gets one --
   after the player chooses Repair.  Included by parentage_export.c, after
   grave_backfill.inc (whose line helpers and village lookup it shares); the
   call is RecordArrivalsMissingFromLog.  native/shared/arrival_backfill.h has
   the record's format, the matching rule and the hand-off.

   WHICH VILLAGERS THE LOG ALREADY HAS.  Every Birth record ("Birth", then
   "  Child: <name>", "    Head: <n>", "    Body: <n>") and every Arrived
   record ("Arrived <n>", then "  Name:", "  Head:", "  Body:") in this
   village's Births and Conceptions files, and those still held for the next
   save (only the ones taken from the tribe loaded now, as for the graves),
   gives a key: name, head and body.  Per key, the records less the villagers
   with that key already matched, in the order Cause of Death hands them over;
   only the villagers left over get a record.  A record already in the log --
   hand-appended in the same shape, or written by an earlier run -- is never
   written again.

   A RECORD KEEPS THE NAME AND LOOKS OF ITS DAY (the owner's A New Home log,
   2026-10-10: Cheop's Birth record said "Cheop" and Hoani's Arrived record
   "Hoani" when the save already called them "Cheop Bahati" and "Hoani
   Chuchip" -- last names given afterwards -- so the backfill found no record
   of theirs, wrote "Arrived 11" and "Arrived 12", and the log then held a
   Birth and an Arrived record for Cheop and two Arrived records for Hoani).
   So a record is followed through every "Appearance changed" record of its
   name (its looks now), and, when no record has the villager's name, head
   and body, a record of the same head and body whose name is the villager's
   with a last name or a number added or dropped ("Cheop" / "Cheop Bahati",
   "Kaula Bahati" / "Kaula Bahati I") or cut short by the Villager Details
   screen ("Kaula Baha" / "Kaula Bahati") is theirs -- when exactly one such
   record and exactly one villager of this village carry it. */

#include "arrival_backfill.h"

#define ARRIVAL_KEY_NAME 64

/* Which kind of record a key is. */
#define ARRIVAL_READ_NONE 0
#define ARRIVAL_READ_BIRTH 1
#define ARRIVAL_READ_ARRIVED 2
#define ARRIVAL_READ_LOOK 3               /* an "Appearance changed" record: never a key itself */

/* "Appearance changed": a villager of this name changed from these looks to those. */
struct arrival_look {
    char name[ARRIVAL_KEY_NAME];
    int old_head, old_body, new_head, new_body;
};

#define ARRIVAL_LOOKS_MAX 512
static struct arrival_look arrival_looks[ARRIVAL_LOOKS_MAX];
static int arrival_look_count;

struct arrival_key {
    char name[ARRIVAL_KEY_NAME];
    int head, body;
    int held;
    int kind;                         /* ARRIVAL_READ_BIRTH or ARRIVAL_READ_ARRIVED */
    int reserved;                     /* taken by a context villager (record_missing_core) */
};

static struct arrival_key *arrival_keys;
static int arrival_key_count;
static int arrival_key_capacity;


static int keep_arrival_key(const struct arrival_key *key) {
    if (arrival_key_count >= arrival_key_capacity) {
        int capacity = arrival_key_capacity == 0 ? 64 : arrival_key_capacity * 2;
        struct arrival_key *grown = (struct arrival_key *)realloc(
            arrival_keys, (size_t)capacity * sizeof(*arrival_keys));
        if (grown == NULL) {
            return 0;
        }
        arrival_keys = grown;
        arrival_key_capacity = capacity;
    }
    arrival_keys[arrival_key_count++] = *key;
    return 1;
}

/* One Birth or Arrived record being read, a line at a time. */

struct arrival_reader {
    int open;
    int have_name, have_head, have_body;
    int held;
    struct arrival_key key;
    int have_new_head, have_new_body;  /* an "Appearance changed" record's "New head" / "New body" */
    int new_head, new_body;
};

static int arrival_reader_close(struct arrival_reader *r) {
    int ok = 1;
    if (r->open == ARRIVAL_READ_LOOK) {
        if (r->have_name && r->have_head && r->have_body && r->have_new_head && r->have_new_body
            && arrival_look_count < ARRIVAL_LOOKS_MAX) {
            struct arrival_look *look = &arrival_looks[arrival_look_count++];
            lstrcpynA(look->name, r->key.name, (int)sizeof look->name);
            look->old_head = r->key.head;
            look->old_body = r->key.body;
            look->new_head = r->new_head;
            look->new_body = r->new_body;
        }
    } else if (r->open != ARRIVAL_READ_NONE && r->have_name && r->have_head && r->have_body) {
        r->key.held = r->held;
        r->key.kind = r->open;
        r->key.reserved = 0;
        ok = keep_arrival_key(&r->key);
    }
    {
        int held = r->held;
        memset(r, 0, sizeof(*r));
        r->held = held;
    }
    return ok;
}

/* `line` with exactly `prefix` before its value, or NULL. */
static const char *arrival_value(const char *line, const char *prefix) {
    size_t n = strlen(prefix);
    return strncmp(line, prefix, n) == 0 ? line + n : NULL;
}

static int arrival_reader_line(struct arrival_reader *r, char *line) {
    const char *value;
    trim_line(line);

    if (strcmp(line, "Birth") == 0) {
        if (!arrival_reader_close(r)) {
            return 0;
        }
        r->open = ARRIVAL_READ_BIRTH;
        return 1;
    }
    if (strncmp(line, "Arrived ", 8) == 0 && line[8] >= '0' && line[8] <= '9') {
        if (!arrival_reader_close(r)) {
            return 0;
        }
        r->open = ARRIVAL_READ_ARRIVED;
        return 1;
    }
    if (strcmp(line, "Appearance changed") == 0) {
        if (!arrival_reader_close(r)) {
            return 0;
        }
        r->open = ARRIVAL_READ_LOOK;
        return 1;
    }
    if (line[0] != ' ') {
        return arrival_reader_close(r);    /* a blank line, a heading, another kind */
    }
    if (r->open == ARRIVAL_READ_BIRTH) {
        /* The child's own lines come first; the parents' Head and Body (also
           four spaces in) follow "  Mother:", by which time all three are
           had and the first ones are kept. */
        if (!r->have_name && (value = arrival_value(line, "  Child: ")) != NULL) {
            lstrcpynA(r->key.name, value, (int)sizeof r->key.name);
            r->have_name = 1;
        } else if (r->have_name && !r->have_head && (value = arrival_value(line, "    Head: ")) != NULL) {
            r->key.head = atoi(value);
            r->have_head = 1;
        } else if (r->have_name && !r->have_body && (value = arrival_value(line, "    Body: ")) != NULL) {
            r->key.body = atoi(value);
            r->have_body = 1;
        }
    } else if (r->open == ARRIVAL_READ_ARRIVED) {
        if (!r->have_name && (value = arrival_value(line, "  Name: ")) != NULL) {
            lstrcpynA(r->key.name, value, (int)sizeof r->key.name);
            r->have_name = 1;
        } else if (!r->have_head && (value = arrival_value(line, "  Head: ")) != NULL) {
            r->key.head = atoi(value);
            r->have_head = 1;
        } else if (!r->have_body && (value = arrival_value(line, "  Body: ")) != NULL) {
            r->key.body = atoi(value);
            r->have_body = 1;
        }
    } else if (r->open == ARRIVAL_READ_LOOK) {
        if (!r->have_name && (value = arrival_value(line, "  Name: ")) != NULL) {
            lstrcpynA(r->key.name, value, (int)sizeof r->key.name);
            r->have_name = 1;
        } else if (!r->have_head && (value = arrival_value(line, "  Old head: ")) != NULL) {
            r->key.head = atoi(value);
            r->have_head = 1;
        } else if (!r->have_body && (value = arrival_value(line, "  Old body: ")) != NULL) {
            r->key.body = atoi(value);
            r->have_body = 1;
        } else if (!r->have_new_head && (value = arrival_value(line, "  New head: ")) != NULL) {
            r->new_head = atoi(value);
            r->have_new_head = 1;
        } else if (!r->have_new_body && (value = arrival_value(line, "  New body: ")) != NULL) {
            r->new_body = atoi(value);
            r->have_new_body = 1;
        }
    }
    return 1;
}

/* Each key's looks now: followed through the "Appearance changed" records of
   its name, in the order they were written (a chain of changes; bounded). */
static void arrival_follow_looks(void) {
    int i, k, step;
    for (i = 0; i < arrival_key_count; ++i) {
        struct arrival_key *key = &arrival_keys[i];
        for (step = 0; step < ARRIVAL_LOOKS_MAX; ++step) {
            int moved = 0;
            for (k = 0; k < arrival_look_count; ++k) {
                const struct arrival_look *look = &arrival_looks[k];
                if (look->old_head == key->head && look->old_body == key->body
                    && (look->new_head != key->head || look->new_body != key->body)
                    && strcmp(look->name, key->name) == 0) {
                    key->head = look->new_head;
                    key->body = look->new_body;
                    moved = 1;
                    break;
                }
            }
            if (!moved) {
                break;
            }
        }
    }
}

/* 1 when `record` and `living` name one villager whose name changed since
   the record: a word added or dropped at the end ("Cheop" / "Cheop Bahati",
   "Kaula Bahati" / "Kaula Bahati I"), or the living name a cut of the
   record's as the Villager Details screen cuts one (A New Home keeps 10
   characters, the others 18, a wide name a few fewer: src/vv_cut_names.py).
   Never for equal names (those are matched as they are) or a single letter. */
static int arrival_names_related(int game_id, const char *record, const char *living) {
    size_t r = strlen(record), l = strlen(living);
    size_t cut_min = game_id == GAME_VV1 ? 9u : 15u, cut_max = game_id == GAME_VV1 ? 10u : 18u;
    if (r < 2 || l < 2 || r == l) {
        return 0;
    }
    if (r < l) {
        return strncmp(living, record, r) == 0 && living[r] == ' ';
    }
    if (strncmp(record, living, l) != 0) {
        return 0;
    }
    return record[l] == ' ' || (l >= cut_min && l <= cut_max);
}

/* This village's Birth and Arrived records into arrival_keys.  Returns 1
   when read (the count of this village's files in *files), 0 when a file
   could not be read, so nothing is decided on half a log. */
static int read_village_arrivals(const struct game_layout *g, int game_id, const char *village,
                                 int *files) {
    wchar_t folder[MAX_PATH];
    wchar_t path[MAX_LOG_PATH];
    char line[512];
    struct arrival_reader reader;
    int ceiling;
    int number;
    int i;

    arrival_key_count = 0;
    arrival_look_count = 0;
    *files = 0;
    if (!build_family_log_path(g, LOG_BIRTHS, 1, path)
        || !vv_save_subfolder_w(folder, family_folder(LOG_BIRTHS), 64)) {
        return 0;
    }
    ceiling = highest_log_number(family_stem(g, LOG_BIRTHS), folder);
    for (number = 1; number <= ceiling; ++number) {
        FILE *file;
        if (!build_family_log_path(g, LOG_BIRTHS, number, path)) {
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
        ++*files;
        memset(&reader, 0, sizeof reader);
        while (fgets(line, (int)sizeof line, file) != NULL) {
            if (!arrival_reader_line(&reader, line)) {
                fclose(file);
                return 0;
            }
        }
        if (ferror(file)) {
            fclose(file);
            return 0;
        }
        fclose(file);
        if (!arrival_reader_close(&reader)) {
            return 0;
        }
    }
    /* Held records: a Birth's text opens with "Birth"; an Arrived record's
       has no "Arrived <n>" line yet (it is numbered when written). */
    {
        int now_known = tribes_ready() && take_tribe(game_id, NULL, scratch_tribe);
        for (i = 0; i < pending_count; ++i) {
            const char *at;
            if (pending[i].game_id != game_id || pending[i].text == NULL
                || (pending[i].kind != KIND_BIRTH && pending[i].kind != KIND_ARRIVED)) {
                continue;
            }
            if (now_known && pending[i].tribe >= 0
                && !same_tribe(&held_tribes[pending[i].tribe], scratch_tribe, TRIBE_LOOSE)) {
                continue;
            }
            memset(&reader, 0, sizeof reader);
            reader.held = 1;
            if (pending[i].kind == KIND_ARRIVED) {
                reader.open = ARRIVAL_READ_ARRIVED;
            }
            at = pending[i].text;
            while (*at != '\0') {
                const char *end = strchr(at, '\n');
                size_t n = end != NULL ? (size_t)(end - at) : strlen(at);
                if (n >= sizeof line) {
                    n = sizeof line - 1;
                }
                memcpy(line, at, n);
                line[n] = '\0';
                if (!arrival_reader_line(&reader, line)) {
                    return 0;
                }
                at = end != NULL ? end + 1 : at + strlen(at);
            }
            if (!arrival_reader_close(&reader)) {
                return 0;
            }
        }
    }
    arrival_follow_looks();
    return 1;
}

/* ---- Founders: the first Village History snapshot -------------------------

   The owner: a village's founders -- its starting villagers -- are "Founder",
   never an unknown arrival, and a founder is one "present at village creation
   / in the first History snapshot, with no Birth record".  So a villager the
   backfill records is a founder when this village's FIRST snapshot in the
   Village History log (native/population_export: "=== <game> -- <date> ===",
   "Village: <name> (Save <n>)", then "Villager <k>" with "  Name:",
   "  Head:", "  Body:") lists the same name, head and body -- or, when no one
   there has all three, the same name for exactly one villager of that
   snapshot and of the villagers being recorded (looks change with Origins'
   Change Appearance; a name repeated on either side decides nothing).
   A renamed village's first snapshot still carries its old header (the
   Rename Tribe tool appends a note, never rewrites one), so the snapshot
   headers are matched through the rename chain (history_aliases,
   grave_backfill.inc), as the graves backfill matches them. */

#define FOUNDERS_MAX 256

static struct arrival_key *founders;
static int founder_count;

static void read_first_snapshot(const char *village) {
    wchar_t folder[MAX_LOG_PATH];
    wchar_t path[MAX_LOG_PATH];
    char line[512];
    char current[256];
    int ceiling;
    int number;
    int done = 0;
    static char notes[HISTORY_NOTES][256];
    static char aliases[HISTORY_ALIASES][256];
    int note_count = 0;
    int alias_count;

    founder_count = 0;
    if (founders == NULL) {
        founders = (struct arrival_key *)calloc(FOUNDERS_MAX, sizeof(*founders));
        if (founders == NULL) {
            return;
        }
    }
    _snprintf_s(current, sizeof current, _TRUNCATE, "%s", village);
    trim_line(current);
    if (!vv_save_subfolder_w(folder, L"Virtual Villagers Fun Patcher Logs\\Tribe History", 64)) {
        return;
    }
    ceiling = highest_log_number(L"Village History", folder);
    /* The rename notes first: every file, wherever the note was appended. */
    for (number = 1; number <= ceiling; ++number) {
        FILE *file;
        if (_snwprintf_s(path, MAX_LOG_PATH, _TRUNCATE, L"%ls\\Village History %d.txt",
                         folder, number) < 0) {
            return;
        }
        file = _wfopen(path, L"rb");
        if (file == NULL) {
            continue;
        }
        while (fgets(line, (int)sizeof line, file) != NULL) {
            trim_line(line);
            if (vv_rename_is_note(line) && note_count < HISTORY_NOTES) {
                lstrcpynA(notes[note_count++], line, 256);
            }
        }
        fclose(file);
    }
    alias_count = history_aliases(current, notes, note_count, aliases);
    for (number = 1; number <= ceiling && !done; ++number) {
        FILE *file;
        int ours = 0;
        int expect_village = 0;
        int open = 0;
        struct arrival_key v;
        int have_head = 0, have_body = 0, have_name = 0;
        if (_snwprintf_s(path, MAX_LOG_PATH, _TRUNCATE, L"%ls\\Village History %d.txt",
                         folder, number) < 0) {
            return;
        }
        file = _wfopen(path, L"rb");
        if (file == NULL) {
            continue;
        }
        memset(&v, 0, sizeof v);
        while (fgets(line, (int)sizeof line, file) != NULL) {
            const char *value;
            trim_line(line);
            if (strncmp(line, "=== ", 4) == 0 || strncmp(line, "Villager ", 9) == 0 || line[0] == '\0') {
                if (open && have_name && have_head && have_body && founder_count < FOUNDERS_MAX) {
                    founders[founder_count++] = v;
                }
                open = have_name = have_head = have_body = 0;
                memset(&v, 0, sizeof v);
                if (strncmp(line, "=== ", 4) == 0) {
                    if (ours) {
                        done = 1;             /* the first snapshot is complete */
                        break;
                    }
                    expect_village = 1;
                } else if (ours && line[0] == 'V') {
                    open = 1;
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
            if (!open) {
                continue;
            }
            if ((value = line_value(line, "Name")) != NULL) {
                lstrcpynA(v.name, value, (int)sizeof v.name);
                have_name = 1;
            } else if ((value = line_value(line, "Head")) != NULL) {
                v.head = atoi(value);
                have_head = 1;
            } else if ((value = line_value(line, "Body")) != NULL) {
                v.body = atoi(value);
                have_body = 1;
            }
        }
        if (!done && open && have_name && have_head && have_body && founder_count < FOUNDERS_MAX) {
            founders[founder_count++] = v;
        }
        if (ours) {
            done = 1;                         /* the snapshot ended with the file */
        }
        fclose(file);
    }
}

/* Whether villager `i` of the ones being recorded is a founder. */
static int is_founder(int i, char (*names)[ARRIVAL_KEY_NAME], const int *heads, const int *bodies,
                      int count) {
    int k, j;
    int same_name = 0;
    for (k = 0; k < founder_count; ++k) {
        if (strcmp(founders[k].name, names[i]) != 0) {
            continue;
        }
        if (founders[k].head == heads[i] && founders[k].body == bodies[i]) {
            return 1;
        }
        ++same_name;
    }
    if (same_name != 1) {
        return 0;
    }
    for (j = 0; j < count; ++j) {
        if (j != i && strcmp(names[j], names[i]) == 0) {
            return 0;
        }
    }
    return 1;
}

static const char ARRIVAL_BACKFILL_AFTER[] =
    "  How: unknown\n"
    "  Note: Recorded afterwards (arrived before this log existed)\n";
static const char ARRIVAL_BACKFILL_FOUNDER[] =
    "  How: Founder\n"
    "  Note: Recorded afterwards (arrived before this log existed)\n";

/* The Birth record a backfill writes for a villager the save says was born
   here (compose_birth, from the record alone), with its own note. */
static const char BIRTH_BACKFILL_NOTE[] =
    "  Note: Recorded afterwards (born before this log existed)\n";

static int record_missing_core(int births, int game_id, const void *save_buffer, int slot,
                               vv_arrival_fact *facts, int count, int apply,
                               const unsigned char *context);

/* What RecordArrivalsMissingFromLog and RecordBirthsMissingFromLog share:
   `births` 0 writes Arrived records, 1 Birth records. */
static int record_missing(
    int births,
    int game_id,
    const void *save_buffer,
    int slot,
    vv_arrival_fact *facts,
    int count,
    int apply
) {
    unsigned char *context;
    int result;
    int i;

    if (game_id < GAME_VV1 || game_id > GAME_VV5 || slot < 1 || slot > 5
        || facts == NULL || count < 0 || count > TRIBE_SLOTS
        || apply < VV_ARRIVAL_COUNT || apply > VV_ARRIVAL_APPLY) {
        return -1;
    }
    /* A New Home keeps no parents on the record: nothing says who was born. */
    if (births && game_id == GAME_VV1) {
        return 0;
    }
    context = (unsigned char *)calloc((size_t)count + 1u, 1u);
    if (context == NULL) {
        return -1;
    }
    for (i = 0; i < count; ++i) {
        /* A villager this call does not record (VV_ARRIVAL_CONTEXT, set by
           the caller) is only counted: see the name rule below. */
        context[i] = (unsigned char)(facts[i].outcome == VV_ARRIVAL_CONTEXT);
        facts[i].outcome = context[i] ? VV_ARRIVAL_CONTEXT : VV_ARRIVAL_UNDECIDED;
        facts[i].before[VV_ARRIVAL_BEFORE - 1] = '\0';
    }
    result = record_missing_core(births, game_id, save_buffer, slot, facts, count, apply, context);
    free(context);
    return result;
}

static int record_missing_core(
    int births,
    int game_id,
    const void *save_buffer,
    int slot,
    vv_arrival_fact *facts,
    int count,
    int apply,
    const unsigned char *context
) {
    const struct game_layout *g;
    char village_name[VV_VILLAGE_NAME_MAX];
    char village[VV_VILLAGE_NAME_MAX + 32];
    char (*names)[ARRIVAL_KEY_NAME];
    int *heads, *bodies;
    int files = 0;
    int result = 0;
    int i, j;

    g = layout_of(game_id);
    if (!layout_is_usable(g)) {
        return -1;
    }
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
    if (!read_village_arrivals(g, game_id, village, &files)) {
        return -1;
    }
    if (count == 0 || files == 0) {
        return 0;                     /* the log has not started: nothing predates it */
    }
    if (apply == VV_ARRIVAL_APPLY && !births) {
        read_first_snapshot(village);
    }
    names = (char (*)[ARRIVAL_KEY_NAME])calloc((size_t)count, ARRIVAL_KEY_NAME);
    heads = (int *)calloc((size_t)count, sizeof(int));
    bodies = (int *)calloc((size_t)count, sizeof(int));
    if (names == NULL || heads == NULL || bodies == NULL) {
        free(names);
        free(heads);
        free(bodies);
        return -1;
    }
    /* Each villager as a record prints them; a pointer that is not one of
       the game's villager records is decided as nothing. */
    {
        const unsigned char *records = villager_table(game_id);
        int readable = records != NULL
            && memory_is_readable(records, g->record_base + (size_t)g->slots * g->stride);
        for (i = 0; i < count; ++i) {
            const unsigned char *record = (const unsigned char *)facts[i].record;
            if (!readable || !is_record_slot(g, records, record)) {
                names[i][0] = '\0';
                continue;
            }
            copy_villager_name(g, record, names[i], ARRIVAL_KEY_NAME);
            heads[i] = *(const int *)(record + g->head);
            bodies[i] = *(const int *)(record + g->body);
        }
    }
    /* A record that matches a context villager is theirs first (Codex,
       #536) -- but only a record of their own kind: a context villager of
       the Births call has no parents (an Arrived record is theirs), one of
       the Arrivals call has them (a Birth record).  So a look-alike never
       takes the record of a villager this call records.  One record each,
       on disk before held. */
    {
        int context_kind = births ? ARRIVAL_READ_ARRIVED : ARRIVAL_READ_BIRTH;
        int pass;
        for (i = 0; i < count; ++i) {
            int found = 0;
            if (names[i][0] == '\0' || !context[i]) {
                continue;
            }
            for (pass = 0; pass < 2 && !found; ++pass) {
                for (j = 0; j < arrival_key_count && !found; ++j) {
                    struct arrival_key *k = &arrival_keys[j];
                    if (!k->reserved && k->kind == context_kind && k->held == pass
                        && k->head == heads[i] && k->body == bodies[i] && strcmp(k->name, names[i]) == 0) {
                        k->reserved = 1;
                        found = 1;
                    }
                }
            }
        }
    }
    for (i = 0; i < count; ++i) {
        int on_disk = 0;
        int held = 0;
        int taken = 0;
        if (names[i][0] == '\0' || context[i]) {
            continue;                 /* not one of this call's villagers: counted below only */
        }
        for (j = 0; j < arrival_key_count; ++j) {
            const struct arrival_key *k = &arrival_keys[j];
            if (!k->reserved
                && k->head == heads[i] && k->body == bodies[i] && strcmp(k->name, names[i]) == 0) {
                if (k->held) {
                    ++held;
                } else {
                    ++on_disk;
                }
            }
        }
        for (j = 0; j < i; ++j) {
            if (heads[j] == heads[i] && bodies[j] == bodies[i] && strcmp(names[j], names[i]) == 0
                && (facts[j].outcome == VV_ARRIVAL_IN_LOG || facts[j].outcome == VV_ARRIVAL_HELD)) {
                ++taken;
            }
        }
        /* LOOKS CHANGE (Origins' Change Appearance), names rarely do: with
           no record of the same three, the name alone settles it when
           exactly one record and exactly one of these villagers carry it --
           as for a founder in the first History snapshot.  A name repeated
           on either side decides nothing. */
        if (on_disk + held <= taken) {
            int records_named = 0, villagers_named = 0;
            const struct arrival_key *only = NULL;
            for (j = 0; j < arrival_key_count; ++j) {
                if (strcmp(arrival_keys[j].name, names[i]) == 0) {
                    ++records_named;
                    only = &arrival_keys[j];
                }
            }
            for (j = 0; j < count; ++j) {
                if (strcmp(names[j], names[i]) == 0) {
                    ++villagers_named;
                }
            }
            if (records_named == 1 && villagers_named == 1 && taken == 0) {
                on_disk = !only->held;
                held = only->held;
            }
        }
        /* THE NAME CHANGED SINCE THE RECORD (a last name or a number given or
           dropped, a name cut short): one record of the same head and body
           whose name is related to this villager's, and no other villager of
           the village it could be -- nor one who carries its own name and
           looks.  The record is then this villager's alone (reserved). */
        if (on_disk + held <= taken) {
            struct arrival_key *only = NULL;
            int records_related = 0;
            for (j = 0; j < arrival_key_count; ++j) {
                struct arrival_key *k = &arrival_keys[j];
                int owners = 0, v;
                if (k->reserved || k->head != heads[i] || k->body != bodies[i]
                    || !arrival_names_related(game_id, k->name, names[i])) {
                    continue;
                }
                for (v = 0; v < count; ++v) {
                    if (names[v][0] != '\0' && heads[v] == k->head && bodies[v] == k->body
                        && (strcmp(names[v], k->name) == 0
                            || (v != i && arrival_names_related(game_id, k->name, names[v])))) {
                        ++owners;
                    }
                }
                if (owners == 0) {
                    ++records_related;
                    only = k;
                }
            }
            if (records_related == 1) {
                only->reserved = 1;
                on_disk = !only->held;
                held = only->held;
                taken = 0;
            }
        }
        if (on_disk > taken) {
            facts[i].outcome = VV_ARRIVAL_IN_LOG;
        } else if (on_disk + held > taken) {
            facts[i].outcome = VV_ARRIVAL_HELD;
        } else if (!apply) {
            facts[i].outcome = VV_ARRIVAL_MISSING;
            ++result;
        } else if (births) {
            int held_before = pending_count;
            char text[RECORD_TEXT_MAX];
            if (compose_birth(game_id, NULL, -1, -1, NULL, -1, -1, NULL, -1, -1, facts[i].record,
                              BIRTH_BACKFILL_NOTE, -1, text, sizeof text)
                && emit_record(game_id, KIND_BIRTH, NULL, text)) {
                facts[i].outcome = pending_count > held_before ? VV_ARRIVAL_QUEUED : VV_ARRIVAL_RECORDED;
                ++result;
            }
        } else {
            int held_before = pending_count;
            const char *after = is_founder(i, names, heads, bodies, count)
                ? ARRIVAL_BACKFILL_FOUNDER : ARRIVAL_BACKFILL_AFTER;
            if (WriteVillageRecord(game_id, KIND_ARRIVED, facts[i].record, 1, facts[i].before,
                                   after, 2)) {
                /* On disk, or held for the save: only a record on disk is
                   durable. */
                facts[i].outcome = pending_count > held_before ? VV_ARRIVAL_QUEUED : VV_ARRIVAL_RECORDED;
                ++result;
            }
        }
    }
    free(names);
    free(heads);
    free(bodies);
    return result;
}

__declspec(dllexport) int __stdcall RecordArrivalsMissingFromLog(
    int game_id,
    const void *save_buffer,
    int slot,
    vv_arrival_fact *facts,
    int count,
    int apply
) {
    return record_missing(0, game_id, save_buffer, slot, facts, count, apply);
}

/* native/shared/arrival_backfill.h: the Birth records a village's villagers
   born before the Births log existed are missing (The Lost Children to New
   Believers), from each villager's own record. */
__declspec(dllexport) int __stdcall RecordBirthsMissingFromLog(
    int game_id,
    const void *save_buffer,
    int slot,
    vv_arrival_fact *facts,
    int count,
    int apply
) {
    return record_missing(1, game_id, save_buffer, slot, facts, count, apply);
}
