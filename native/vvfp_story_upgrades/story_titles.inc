/* Custom Island Event: custom villager titles, persisted per save slot.
   Included by vvfp_story_upgrades.c.

   The file is native/shared/custom_titles.h's format, beside the saves:
       <save folder>\Virtual Villagers Fun Patcher Data\Custom Titles\Custom Titles - Save N.dat
   loaded and published through native/shared/sidecar_io.h (atomic publish,
   an invalid file set aside, nothing written before the slot's load
   settled).  The save slot is the one the game's Origins companion keys its
   own sidecars by (story_host.current_slot).

   A title belongs to the villager in its record whose name hashes to the
   stored fingerprint; a reused record (a birth into a dead villager's
   record) never inherits it.  The sweep drops a title once its villager has
   been seen in this session and its record then holds nobody or somebody
   else -- after titles_follow has moved it to the record its villager
   holds now, for the games renumber their villagers on every load.  Start Over deletes the file (native/shared/save_reset.c); a file
   that was present and is now missing is that reset, so the table is
   forgotten rather than written back. */

#include "../shared/mask_follow.h"

#define TITLES_CHECK_MS 2000u
#define TITLES_ROSTER VV_MASK_FOLLOW_MAX    /* every game has 150 or 256 records */

static struct {
    int game;
    int slot;                       /* the slot the table belongs to, 0 = none */
    int loaded;                     /* the load for `slot` settled */
    int file_present;               /* the file was read or written by us */
    vv_sidecar_gate gate;
    int count;
    vv_custom_title entries[VV_TITLES_MAX];
    unsigned char seen[VV_TITLES_MAX];   /* entry's villager seen this session */
    DWORD checked_at;
    char path[MAX_PATH];
    /* The last look at who is in each record (identity, and the part of it
       a rename leaves alone), for telling a rename and a reload apart from
       everything else.  Nobody at all -- a new table, or the array between
       two villages -- means the next look is a village arriving. */
    unsigned int roster[TITLES_ROSTER];
    unsigned int roster_stable[TITLES_ROSTER];
    int roster_anyone;                  /* anybody was present at that look */
} titles;

static unsigned char titles_buffer[VV_TITLES_FILE_MAX];

static void titles_forget(void) {
    titles.count = 0;
    memset(titles.seen, 0, sizeof titles.seen);
    memset(titles.roster, 0, sizeof titles.roster);
    memset(titles.roster_stable, 0, sizeof titles.roster_stable);
    titles.roster_anyone = 0;
}

static int titles_build_path(int game, int slot, char *out) {
    char folder[MAX_PATH];
    (void)game;
    if (!vv_save_subfolder(folder, VV_TITLES_SUBFOLDER, (int)sizeof("\\Custom Titles - Save 0.dat"))) {
        return 0;
    }
    return vv_titles_file_name(out, MAX_PATH, folder, slot);
}

/* Bind the table to the game's current save slot, loading that slot's file
   the first time (and again after a blocked load's retry window). */
static void titles_sync(int game) {
    int slot = story_current_slot(game);
    if (game != titles.game || slot != titles.slot) {
        titles_forget();
        titles.game = game;
        titles.slot = slot;
        titles.loaded = 0;
        titles.file_present = 0;
        titles.path[0] = '\0';
        vv_sidecar_gate_bind(&titles.gate, game * 16 + slot);
    }
    if (titles.slot <= 0 || titles.loaded || vv_sidecar_gate_throttled(&titles.gate)) {
        return;
    }
    if (titles.path[0] == '\0' && !titles_build_path(game, slot, titles.path)) {
        vv_sidecar_gate_block(&titles.gate);
        return;
    }
    {
        DWORD length = 0;
        vv_titles_check check;
        int result;
        check.game = game;
        check.slots = (unsigned int)story_record_count(game);
        result = vv_sidecar_load(&titles.gate, titles.path, titles_buffer, sizeof titles_buffer,
                                 &length, vv_titles_validate, &check);
        if (result == VV_SIDECAR_LOAD_BLOCKED) {
            return;
        }
        titles_forget();
        if (result == VV_SIDECAR_LOAD_VALID) {
            titles.count = vv_titles_parse(titles_buffer, titles.entries);
            titles.file_present = 1;
        }
        titles.loaded = 1;
        titles.checked_at = GetTickCount();
    }
}

/* A file we read or wrote that is now gone was deleted by Start Over: the
   village it described no longer exists, so its titles are forgotten. */
static int titles_reset_detected(void) {
    DWORD error;
    if (!titles.file_present || GetFileAttributesA(titles.path) != INVALID_FILE_ATTRIBUTES) {
        return 0;
    }
    error = GetLastError();
    if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
        titles_forget();
        titles.file_present = 0;
        return 1;
    }
    return 0;
}

static int titles_publish(void) {
    const void *parts[1];
    DWORD sizes[1];
    if (!titles.loaded || titles.slot <= 0 || titles_reset_detected()) {
        return 0;
    }
    parts[0] = titles_buffer;
    sizes[0] = vv_titles_serialise(titles.game, titles.entries, titles.count, titles_buffer);
    if (!vv_sidecar_publish(&titles.gate, titles.path, parts, sizes, 1)) {
        return 0;
    }
    titles.file_present = 1;
    return 1;
}

static int titles_find(unsigned int index) {
    int i;
    for (i = 0; i < titles.count; ++i) {
        if (titles.entries[i].index == index) {
            return i;
        }
    }
    return -1;
}

static void titles_remove_at(int i) {
    --titles.count;
    titles.entries[i] = titles.entries[titles.count];
    titles.seen[i] = titles.seen[titles.count];
    titles.seen[titles.count] = 0;
}

static int titles_live_count(int game, unsigned int identity, int *where);
static void titles_pass(int game, int sweep);

/* The custom title of the villager in `record`, or NULL. */
static const char *titles_lookup(int game, const unsigned char *record) {
    int index;
    int i;
    titles_sync(game);
    if (!titles.loaded || titles.count == 0) {
        return NULL;
    }
    index = story_record_index(game, record);
    if (index < 0) {
        return NULL;
    }
    /* Never before the table has been followed against the village on
       screen: a table just read from its file still has the records of the
       last save, and after a reload one of them may hold someone else with
       the same identity -- a twin -- until the follow drops it.  So the
       first lookup of a table runs that look and follow itself -- not the
       death sweep, which stays the per-frame tick's (titles_pass). */
    if (!titles.roster_anyone) {
        titles_pass(game, 0);
        if (!titles.roster_anyone) {
            return NULL;
        }
    }
    i = titles_find((unsigned int)index);
    if (i < 0 || titles.entries[i].fingerprint != story_title_identity(game, record)) {
        return NULL;
    }
    return titles.entries[i].title;
}

/* The table as it was before titles_set changed it, put back when the change
   could not be written: memory never says what the file does not. */
static struct {
    int count;
    vv_custom_title entries[VV_TITLES_MAX];
    unsigned char seen[VV_TITLES_MAX];
} titles_before;

static int titles_commit(void) {
    if (titles_publish()) {
        return 1;
    }
    /* (titles_set has already looked for a Start Over, so the publish's own
       look finds none: this is a write that failed.) */
    titles.count = titles_before.count;
    memcpy(titles.entries, titles_before.entries, sizeof titles.entries);
    memcpy(titles.seen, titles_before.seen, sizeof titles.seen);
    return 0;
}

/* Set (text != NULL) or remove the custom title of the villager in record
   `index`.  Returns 1 when the table now says so and is published; when it
   can not be published the table is left as it was. */
static int titles_set(int game, int index, const char *text) {
    const unsigned char *record = story_record(game, index);
    int i;
    titles_sync(game);
    if (!titles.loaded || titles.slot <= 0 || record == NULL) {
        return 0;
    }
    /* A Start Over since the last write: the old village's titles go; this
       one belongs to the village there now. */
    titles_reset_detected();
    titles_before.count = titles.count;
    memcpy(titles_before.entries, titles.entries, sizeof titles.entries);
    memcpy(titles_before.seen, titles.seen, sizeof titles.seen);
    i = titles_find((unsigned int)index);
    if (text == NULL) {
        if (i >= 0) {
            titles_remove_at(i);
        }
        return titles_commit();
    }
    if (!vv_title_valid(text)) {
        return 0;
    }
    if (i < 0) {
        if (titles.count >= VV_TITLES_MAX) {
            return 0;
        }
        i = titles.count++;
    }
    titles.entries[i].index = (unsigned int)index;
    titles.entries[i].fingerprint = story_title_identity(game, record);
    memset(titles.entries[i].title, 0, sizeof titles.entries[i].title);
    lstrcpynA(titles.entries[i].title, text, VV_TITLE_BYTES);
    titles.seen[i] = 1;
    return titles_commit();
}

/* The villager in record `index` was just changed by a custom event in a
   way that changes who a title is bound to (likes / dislikes): carry its
   title over to the new identity.  `before` is the identity it had.
   Returns 1 when there was nothing to carry or the carried table is
   published; 0 when it could not be (the table is then left as it was). */
static int titles_rebind(int game, int index, unsigned int before) {
    const unsigned char *record = story_record(game, index);
    int i;
    /* Only a table already loaded for this game can hold the title (it was
       set through titles_set, which loaded it); nothing loaded, nothing to
       carry, and no file is touched. */
    if (titles.game != game || !titles.loaded || titles.slot <= 0 || record == NULL) {
        return 1;
    }
    i = titles_find((unsigned int)index);
    if (i < 0 || titles.entries[i].fingerprint != before
        || titles.entries[i].fingerprint == story_title_identity(game, record)) {
        return 1;
    }
    titles_reset_detected();
    titles_before.count = titles.count;
    memcpy(titles_before.entries, titles.entries, sizeof titles.entries);
    memcpy(titles_before.seen, titles.seen, sizeof titles.seen);
    titles.entries[i].fingerprint = story_title_identity(game, record);
    return titles_commit();
}

/* How many present records carry this identity; *where gets the last. */
static int titles_live_count(int game, unsigned int identity, int *where) {
    int count = story_record_count(game);
    int n = 0;
    int r;
    for (r = 0; r < count; ++r) {
        const unsigned char *record = story_record(game, r);
        if (record != NULL && story_record_present(game, record)
            && story_title_identity(game, record) == identity) {
            ++n;
            *where = r;
        }
    }
    return n;
}

/* MAKE EACH TITLE FOLLOW ITS VILLAGER.  The games load a save packed into
   records 0, 1, 2, ...: after a death and a reload everyone behind it is in
   a lower record, and a title kept at its old record index then labelled
   nobody (its fingerprint no longer matched the record there) -- or, in a
   session that had already seen the villager, was swept away as if they had
   died.  So an entry whose record no longer holds its villager moves to the
   one record that does: the identity (name, likes, dislikes) must be held by
   exactly ONE present villager and by no other entry, else nothing is
   guessed.  Only when the villagers moved: with nothing moved, an entry
   whose record no longer holds its villager is the sweep's to judge (a
   namesake born elsewhere is not the titled villager).  An entry left on a record another entry has just moved into
   belonged to nobody there, and is dropped (no index may be listed twice).

   AMBIGUOUS AFTER A RELOAD IS DROPPED (Codex, #516).  When the villagers
   moved (`moved`: a reload, or a table first seen against a village), an
   entry whose identity two present villagers carry -- or another entry
   carries too -- could now be on either of them.  Kept and merely hidden,
   it came back the moment the ambiguity did not: a twin's death, or a
   likes change, left one carrier, who might be the twin who never had the
   title.  So it is dropped, once and for all.  With nothing moved, the
   record it was set on still holds that villager and it is kept.
   Returns 1 when the table changed. */
static int titles_follow(int game, int moved) {
    static int target[VV_TITLES_MAX];         /* the record each entry's villager holds now, -1 unknown */
    static unsigned char drop[VV_TITLES_MAX];
    int i, j, kept;
    int changed = 0;
    /* First where everyone is, before anything moves: an entry's old record
       may be the new record of an entry not yet looked at. */
    for (i = 0; i < titles.count; ++i) {
        const unsigned char *record = story_record(game, (int)titles.entries[i].index);
        int where = -1;
        int duplicate = 0;
        int carriers = titles_live_count(game, titles.entries[i].fingerprint, &where);
        target[i] = -1;
        drop[i] = 0;
        for (j = 0; j < titles.count; ++j) {
            duplicate |= j != i && titles.entries[j].fingerprint == titles.entries[i].fingerprint;
        }
        if (moved && (carriers > 1 || (duplicate && carriers > 0))) {
            drop[i] = 1;                      /* whose it is cannot be told any more */
            continue;
        }
        /* Still where it was. */
        if (record != NULL && story_record_present(game, record)
            && titles.entries[i].fingerprint == story_title_identity(game, record)) {
            target[i] = (int)titles.entries[i].index;
            continue;
        }
        if (moved) {
            target[i] = where;                /* its one carrier, or -1: away or gone */
        }                                     /* nothing moved: the sweep decides */
    }
    for (i = 0, kept = 0; i < titles.count; ++i) {
        int taken = 0;
        if (target[i] < 0) {
            for (j = 0; j < titles.count; ++j) {
                taken |= j != i && target[j] == (int)titles.entries[i].index;
            }
        }
        if (taken || drop[i]) {
            changed = 1;                      /* another villager's record now, or ambiguous: dropped */
            continue;
        }
        titles.entries[kept] = titles.entries[i];
        titles.seen[kept] = titles.seen[i];
        if (target[i] >= 0 && (unsigned int)target[i] != titles.entries[i].index) {
            titles.entries[kept].index = (unsigned int)target[i];
            titles.seen[kept] = 1;
            changed = 1;
        }
        ++kept;
    }
    for (i = kept; i < titles.count; ++i) {
        titles.seen[i] = 0;
    }
    titles.count = kept;
    return changed;
}

/* Who is present in each record now: identity and the part of it a rename
   leaves alone, 0 for a record nobody is in.  Returns how many are present. */
static int titles_take_roster(int game, unsigned int *ids, unsigned int *stable) {
    int count = story_record_count(game);
    int r, n = 0;
    memset(ids, 0, TITLES_ROSTER * sizeof(unsigned int));
    memset(stable, 0, TITLES_ROSTER * sizeof(unsigned int));
    for (r = 0; r < count && r < TITLES_ROSTER; ++r) {
        const unsigned char *record = story_record(game, r);
        if (record != NULL && story_record_present(game, record)) {
            ids[r] = story_title_identity(game, record);
            stable[r] = story_title_stable(game, record);
            ++n;
        }
    }
    return n;
}

/* Once per frame (from the Origins companion's tick): bind to the slot,
   detect a Start Over, move titles to where their villagers are now, and
   drop the titles of villagers that are gone. */
static void titles_pass(int game, int sweep) {
    static unsigned int now[TITLES_ROSTER];
    static unsigned int now_stable[TITLES_ROSTER];
    int i;
    int changed = 0;
    int present;
    int moved;
    int renamed;
    titles_sync(game);
    if (!titles.loaded) {
        return;
    }
    /* Every tick, titled or not, so the last look is never stale when a
       title is set. */
    present = titles_take_roster(game, now, now_stable);
    moved = !titles.roster_anyone || vv_roster_moved(TITLES_ROSTER, titles.roster, now);
    renamed = vv_roster_renamed(TITLES_ROSTER, titles.roster, titles.roster_stable, now, now_stable);
    /* A RENAME (Codex, #516): the identity hashes the name, so the title of
       a villager the player renamed no longer matched their record and the
       sweep threw it away.  One record changed, the rest of the identity
       unchanged: the same villager, and the title takes the new identity. */
    if (renamed >= 0) {
        moved = 0;                            /* one villager renamed: nobody moved */
        for (i = 0; i < titles.count; ++i) {
            if (titles.entries[i].index == (unsigned int)renamed
                && titles.entries[i].fingerprint == titles.roster[renamed]) {
                titles.entries[i].fingerprint = now[renamed];
                changed = 1;
            }
        }
    }
    memcpy(titles.roster, now, sizeof now);
    memcpy(titles.roster_stable, now_stable, sizeof now_stable);
    titles.roster_anyone = present > 0;
    if (titles.count == 0) {
        return;
    }
    if (GetTickCount() - titles.checked_at >= TITLES_CHECK_MS) {
        titles.checked_at = GetTickCount();
        if (titles_reset_detected()) {
            return;
        }
    }
    changed |= titles_follow(game, moved);
    for (i = titles.count - 1; sweep && i >= 0; --i) {
        const unsigned char *record = story_record(game, (int)titles.entries[i].index);
        int match = record != NULL && story_record_present(game, record)
            && titles.entries[i].fingerprint == story_title_identity(game, record);
        if (match) {
            titles.seen[i] = 1;
        } else if (titles.seen[i]) {
            titles_remove_at(i);
            changed = 1;
        }
    }
    if (changed) {
        titles_publish();
    }
}

static void titles_tick(int game) {
    titles_pass(game, 1);
}

/* A villager's custom title for "VVFP Island Events.dll", which logs a Custom
   Island Event's title change as "old -> new": the table in memory, as the
   villager panel shows it -- the file is published later, so it can not say
   at the moment of the event.  `out` gets the title or "" (none).  0 when
   there is no record or no table for this game's slot yet. */
__declspec(dllexport) int __stdcall VvfpStoryCustomTitle(int game, const void *record, char *out, int size) {
    const char *title;
    if (out == NULL || size <= 0 || record == NULL || game < 1 || game > 5) {
        return 0;
    }
    out[0] = '\0';
    if (story_record_index(game, (const unsigned char *)record) < 0) {
        return 0;
    }
    titles_sync(game);
    if (!titles.loaded) {
        return 0;
    }
    title = titles_lookup(game, (const unsigned char *)record);
    if (title != NULL) {
        lstrcpynA(out, title, size);
    }
    return 1;
}