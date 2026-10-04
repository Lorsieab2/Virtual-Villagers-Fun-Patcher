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

#define TITLES_CHECK_MS 2000u

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
} titles;

static unsigned char titles_buffer[VV_TITLES_FILE_MAX];

static void titles_forget(void) {
    titles.count = 0;
    memset(titles.seen, 0, sizeof titles.seen);
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
    i = titles_find((unsigned int)index);
    if (i < 0 || titles.entries[i].fingerprint != story_title_identity(game, record)) {
        return NULL;
    }
    {
        /* Two living villagers who carry the title's identity: which of them
           it was set for cannot be told after a reload, so neither shows it. */
        int where = -1;
        if (titles_live_count(game, titles.entries[i].fingerprint, &where) != 1) {
            return NULL;
        }
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
   guessed.  An entry left on a record another entry has just moved into
   belonged to nobody there, and is dropped (no index may be listed twice).
   Returns 1 when the table changed. */
static int titles_follow(int game) {
    static int target[VV_TITLES_MAX];         /* the record each entry's villager holds now, -1 unknown */
    int i, j, kept;
    int moved = 0;
    /* First where everyone is, before anything moves: an entry's old record
       may be the new record of an entry not yet looked at. */
    for (i = 0; i < titles.count; ++i) {
        const unsigned char *record = story_record(game, (int)titles.entries[i].index);
        int where = -1;
        int duplicate = 0;
        target[i] = -1;
        /* Still where it was.  (If another living villager carries the same
           identity, the one at this record may be the OTHER one after a
           reload -- Codex, #516 -- so titles_lookup and the exporter show an
           ambiguous title on neither; it is kept here, not guessed at.) */
        if (record != NULL && story_record_present(game, record)
            && titles.entries[i].fingerprint == story_title_identity(game, record)) {
            target[i] = (int)titles.entries[i].index;
            continue;
        }
        for (j = 0; j < titles.count; ++j) {
            duplicate |= j != i && titles.entries[j].fingerprint == titles.entries[i].fingerprint;
        }
        if (!duplicate && titles_live_count(game, titles.entries[i].fingerprint, &where) == 1) {
            target[i] = where;
        }                                     /* else away, gone, or ambiguous: not guessed */
    }
    for (i = 0, kept = 0; i < titles.count; ++i) {
        int taken = 0;
        if (target[i] < 0) {
            for (j = 0; j < titles.count; ++j) {
                taken |= j != i && target[j] == (int)titles.entries[i].index;
            }
        }
        if (taken) {
            moved = 1;                        /* its record is another villager's now: dropped */
            continue;
        }
        titles.entries[kept] = titles.entries[i];
        titles.seen[kept] = titles.seen[i];
        if (target[i] >= 0 && (unsigned int)target[i] != titles.entries[i].index) {
            titles.entries[kept].index = (unsigned int)target[i];
            titles.seen[kept] = 1;
            moved = 1;
        }
        ++kept;
    }
    for (i = kept; i < titles.count; ++i) {
        titles.seen[i] = 0;
    }
    titles.count = kept;
    return moved;
}

/* Once per frame (from the Origins companion's tick): bind to the slot,
   detect a Start Over, move titles to where their villagers are now, and
   drop the titles of villagers that are gone. */
static void titles_tick(int game) {
    int i;
    int changed = 0;
    titles_sync(game);
    if (!titles.loaded || titles.count == 0) {
        return;
    }
    if (GetTickCount() - titles.checked_at >= TITLES_CHECK_MS) {
        titles.checked_at = GetTickCount();
        if (titles_reset_detected()) {
            return;
        }
    }
    changed = titles_follow(game);
    for (i = titles.count - 1; i >= 0; --i) {
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
