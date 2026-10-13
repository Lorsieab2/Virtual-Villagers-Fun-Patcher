/* Custom Island Event: custom villager titles, persisted per save slot.
   Included by vvfp_story_upgrades.c.

   The file is native/shared/custom_titles.h's format, beside the saves:
       <save folder>\Virtual Villagers Fun Patcher Data\Custom Titles\Custom Titles - Save N.dat
   loaded and published through native/shared/sidecar_io.h (atomic publish,
   an invalid file set aside, nothing written before the slot's load
   settled).  The save slot is the one the game's Origins companion keys its
   own sidecars by (story_host.current_slot).

   A title belongs to the villager in its record whose name, likes and
   dislikes hash to the stored fingerprint; a reused record (a birth into a
   dead villager's record) never inherits it.  The sweep drops a title once
   its villager has been seen in this session and its record then holds
   nobody or somebody else -- after titles_follow has moved it to the record
   its villager holds now, for the games renumber their villagers on every
   load.  A title whose villager can not be told apart after a load is kept
   PENDING (custom_titles.h), shown on nobody, never dropped for it.  Start
   Over deletes the file (native/shared/save_reset.c); a file that was
   present and is now missing is that reset, so the table is forgotten
   rather than written back. */

#include "../shared/mask_follow.h"
#include "../shared/identity_in_place.h"
#include "../shared/foreign_sidecar.h"   /* vv_roster_shares: another array is not play */

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
    /* ...and what a likes / dislikes change leaves of it, and the age, for
       telling such a change apart (identity_in_place.h). */
    unsigned int roster_keep[TITLES_ROSTER];
    int roster_age[TITLES_ROSTER];
    int roster_anyone;                  /* anybody was present at that look */
    /* A WHOLE OTHER ARRAY (the title screen's founders after a quit to the
       menu): nothing is judged, moved or written until the next array
       arrives -- a load. */
    int frozen;
    /* Each record's villager as first seen in it this session: the age and
       skills a title is kept with (a later save of theirs never holds less;
       custom_titles.h). */
    int base_age[TITLES_ROSTER];
    unsigned int base_skills[TITLES_ROSTER][VV_TITLE_SKILLS];
} titles;

static unsigned char titles_buffer[VV_TITLES_FILE_MAX];

static int titles_unpublished;

static void titles_forget(void) {
    titles_unpublished = 0;
    titles.count = 0;
    memset(titles.seen, 0, sizeof titles.seen);
    memset(titles.roster, 0, sizeof titles.roster);
    memset(titles.roster_stable, 0, sizeof titles.roster_stable);
    memset(titles.roster_keep, 0, sizeof titles.roster_keep);
    memset(titles.roster_age, 0, sizeof titles.roster_age);
    titles.roster_anyone = 0;
    titles.frozen = 0;
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

static void titles_pass(int game, int sweep);
static void titles_relook(int game);

/* What the villager in record `r` is kept by besides the fingerprint: the
   head, body and sex as they are now, and the age and skills they were first
   seen with in that record this session -- when the last look saw them
   there; before any look, or for someone new in the record, as they are. */
static void titles_looks_now(int game, int r, const unsigned char *record, vv_title_looks *out) {
    story_title_looks(game, record, out);
    if (titles.roster_anyone && r >= 0 && r < TITLES_ROSTER && titles.roster[r] != 0
        && titles.roster[r] == story_title_identity(game, record)) {
        out->age = titles.base_age[r];
        memcpy(out->skills, titles.base_skills[r], sizeof out->skills);
    }
    /* Kept as the corrupted-skill reset leaves them (custom_titles.h). */
    vv_title_normalise_skills(out, story_title_skills_float(game));
}

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
       the same identity -- a twin -- until the follow makes it pending.  So the
       first lookup of a table runs that look and follow itself -- not the
       death sweep, which stays the per-frame tick's (titles_pass). */
    if (!titles.roster_anyone) {
        titles_pass(game, 0);
        if (!titles.roster_anyone) {
            return NULL;
        }
    }
    i = titles_find((unsigned int)index);
    if (i >= 0 && titles.entries[i].fingerprint != story_title_identity(game, record)) {
        /* The villager's likes or dislikes may have changed since the last
           tick -- "VVFP Island Events.dll" asks right after the event that
           changed them, in the same frame (Alapai, "Faces in the Night":
           "Custom title: Moon Mother -> none").  One more look carries the
           title to the new identity when that is what happened -- in
           memory only; the next tick writes it (titles_relook). */
        titles_relook(game);
        i = titles_find((unsigned int)index);
    }
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
    titles.entries[i].flags = VV_TITLE_KNOWN;
    titles_looks_now(game, index, record, &titles.entries[i].looks);
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

/* The lower of two skill dwords (both already normalised): floats compare as
   floats in The Tree of Life and New Believers, ints in the other games. */
static unsigned int titles_skill_lower(unsigned int a, unsigned int b, int skills_float) {
    return (skills_float ? vv_title_skill_float(b) < vv_title_skill_float(a) : (int)b < (int)a) ? b : a;
}

/* The villager in record `index` was just given a new age and / or skills by
   a custom event (Villager changes: Age, the skills): a REAL, KNOWN change
   the patcher made itself.  What the title is kept by follows it DOWN only:
   each stored age and skill (the entry's looks and the age and skills the
   villager is first seen with) becomes the LOWER of what it was and what the
   villager has now, and the last look's age is the new age (a younger age
   than the last look reads as a namesake born into a freed record,
   titles_reborn, and would take the title away).  Lower, never higher: the
   file published here is read after an Alt-F4 or a crash, when the save still
   holds the values from before the event, and a stored value above them would
   leave nobody who "could be" the entry (v1.35.72).  The caller asks only when
   the event actually changed the age or a skill.  Only an entry bound to this
   very record and this very identity moves.  Returns 1 when there was nothing
   to follow or the followed table is published; 0 when it could not be (the
   table, the bases and the last look's age are then left as they were). */
static int titles_rebase(int game, int index) {
    const unsigned char *record = story_record(game, index);
    vv_title_looks now;
    int floats = story_title_skills_float(game);
    int saved_base_age, saved_roster_age;
    unsigned int saved_base_skills[VV_TITLE_SKILLS];
    int i, k;
    /* Not before the table has been followed against the village on screen
       (the bases and the last look exist only then). */
    if (titles.game != game || !titles.loaded || titles.slot <= 0 || !titles.roster_anyone || record == NULL
        || index < 0 || index >= TITLES_ROSTER) {
        return 1;
    }
    i = titles_find((unsigned int)index);
    if (i < 0 || titles.entries[i].fingerprint != story_title_identity(game, record)) {
        return 1;
    }
    story_title_looks(game, record, &now);
    vv_title_normalise_skills(&now, floats);
    titles_reset_detected();
    titles_before.count = titles.count;
    memcpy(titles_before.entries, titles.entries, sizeof titles.entries);
    memcpy(titles_before.seen, titles.seen, sizeof titles.seen);
    saved_base_age = titles.base_age[index];
    saved_roster_age = titles.roster_age[index];
    memcpy(saved_base_skills, titles.base_skills[index], sizeof saved_base_skills);
    if (titles.entries[i].flags & VV_TITLE_KNOWN) {
        if (now.age < titles.entries[i].looks.age) {
            titles.entries[i].looks.age = now.age;
        }
        for (k = 0; k < VV_TITLE_SKILLS; ++k) {
            titles.entries[i].looks.skills[k] = titles_skill_lower(
                vv_title_skill_normalised(titles.entries[i].looks.skills[k], floats), now.skills[k], floats);
        }
    } else {
        titles.entries[i].looks = now;
        titles.entries[i].flags |= VV_TITLE_KNOWN;
    }
    if (now.age < titles.base_age[index]) {
        titles.base_age[index] = now.age;
    }
    for (k = 0; k < VV_TITLE_SKILLS; ++k) {
        titles.base_skills[index][k] = titles_skill_lower(
            vv_title_skill_normalised(titles.base_skills[index][k], floats), now.skills[k], floats);
    }
    titles.roster_age[index] = now.age;
    if (!titles_commit()) {
        titles.base_age[index] = saved_base_age;
        titles.roster_age[index] = saved_roster_age;
        memcpy(titles.base_skills[index], saved_base_skills, sizeof saved_base_skills);
        return 0;
    }
    return 1;
}

/* Origins' Change Appearance just gave the villager in `record` a new head
   and body (native/shared/appearance_log.h tells us in the same call that
   logs it).  The title's stored head and body follow at once, published
   before the call returns: a log written in the same frame -- a Death, a
   Disappeared record -- reads the file, and with the old head and body in it
   would find nobody who "could be" the entry and leave the title out until
   the next tick republished it (v1.35.72).  Only the entry bound to this very
   record and identity moves, and only its head and body: the age and skills
   stay as they were first seen.  Returns 1 when there was nothing to follow
   or the followed table is published; 0 when it could not be (the table is
   then left as it was). */
static int titles_appearance_changed(int game, const unsigned char *record, int head, int body) {
    int index = record != NULL ? story_record_index(game, record) : -1;
    int i;
    titles_sync(game);
    /* Not before the table has been followed against the village on screen:
       a table just read from its file may still hold a twin's record. */
    if (index < 0 || !titles.loaded || titles.slot <= 0 || !titles.roster_anyone) {
        return 1;
    }
    i = titles_find((unsigned int)index);
    if (i < 0 || !(titles.entries[i].flags & VV_TITLE_KNOWN)
        || titles.entries[i].fingerprint != story_title_identity(game, record)
        || (titles.entries[i].looks.head == head && titles.entries[i].looks.body == body)) {
        return 1;
    }
    titles_reset_detected();
    titles_before.count = titles.count;
    memcpy(titles_before.entries, titles.entries, sizeof titles.entries);
    memcpy(titles_before.seen, titles.seen, sizeof titles.seen);
    titles.entries[i].looks.head = head;
    titles.entries[i].looks.body = body;
    return titles_commit();
}

/* Could the villager in record `r` be the one entry `e` belongs to?  Present,
   the fingerprint (name, likes, dislikes), and -- once the entry's looks are
   known -- the same head, body and sex, and no younger and no less skilled
   than stored (custom_titles.h vv_title_looks_could_be). */
static int titles_could_be(int game, const vv_custom_title *e, int r) {
    const unsigned char *record = story_record(game, r);
    vv_title_looks now;
    if (record == NULL || !story_record_present(game, record)
        || story_title_identity(game, record) != e->fingerprint) {
        return 0;
    }
    if (!(e->flags & VV_TITLE_KNOWN)) {
        return 1;                             /* a version 2 entry: the fingerprint is all it has */
    }
    titles_looks_now(game, r, record, &now);
    return vv_title_looks_could_be(&e->looks, &now, story_title_skills_float(game));
}

/* How many present villagers could be entry `e`'s; *where gets the last.
   *carriers gets how many carry its fingerprint at all. */
static int titles_candidates(int game, const vv_custom_title *e, int *where, int *carriers) {
    int count = story_record_count(game);
    int n = 0;
    int r;
    *carriers = 0;
    for (r = 0; r < count; ++r) {
        const unsigned char *record = story_record(game, r);
        if (record != NULL && story_record_present(game, record)
            && story_title_identity(game, record) == e->fingerprint) {
            ++*carriers;
        }
        if (titles_could_be(game, e, r)) {
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
   died.  So when the villagers moved (`moved`: a reload, or a table first
   seen against a village) every entry goes to the one present villager who
   has its WHOLE identity (titles_could_be: the fingerprint, the head, body
   and sex, an age and skills no lower than stored) -- a record index is
   never trusted after a move, for a namesake packed into the title's old
   record carries the same fingerprint.  With nothing moved, a bound entry
   whose record no longer holds its villager is the sweep's to judge (a
   namesake born elsewhere is not the titled villager).

   AMBIGUOUS IS PENDING, NEVER DROPPED (the owner, v1.35.70; replaces "dropped
   once and for all", Codex #516).  An entry two present villagers could
   both be, or none, or whose one villager another entry claims too, is not
   guessed at: it is kept PENDING (index VV_TITLE_PENDING), shown on nobody,
   and written to the file so.  A pending entry binds again -- on a move, a
   change in the roster, or the periodic check (`resolve`) -- only when
   exactly one present villager has its whole identity and no other entry
   claims that villager; until then it waits, and the read-only
   reconciliation asks the player (src/vv_reconcile.py).  NEVER A GUESS (the
   owner): an entry that two or more villagers could be at once is marked
   CONTESTED (custom_titles.h), and when the others later die or leave it is
   NOT given to the one left -- it waits for the player.  A LOAD IS NEVER A
   DEATH: after a move an entry whose villager was seen this session (`seen`)
   and whose name and likes nobody present carries any more -- renamed and
   reloaded without a save, or gone -- waits PENDING (on the tick: a
   lookup's first look has no roster to tell a load by, and leaves it on
   its record); only the sweep, with
   nothing moved, drops the title of a villager seen to die.  An entry never
   seen this session whose fingerprint NOBODY present carries (the villager
   away, or gone) stays on its record, shown on nobody there, for the sweep to
   judge -- unless another entry's villager is in that record now, when it
   waits pending.
   Returns 1 when the table changed. */
static int titles_follow(int game, int moved, int sweep, int resolve) {
    /* The record each entry goes to (>= 0), PENDING (-1), as it is (-2), or
       as it is unless another entry goes to its record (-3). */
    static int target[VV_TITLES_MAX];
    static unsigned char clash[VV_TITLES_MAX];
    int i, j, kept;
    int changed = 0;
    /* First where everyone is, before anything moves: an entry's old record
       may be the new record of an entry not yet looked at. */
    for (i = 0; i < titles.count; ++i) {
        vv_custom_title *e = &titles.entries[i];
        int where = -1;
        int carriers = 0;
        int n;
        target[i] = -2;
        clash[i] = 0;
        if (!moved && (e->index != VV_TITLE_PENDING || !resolve)) {
            continue;                         /* nothing moved: a bound entry stays, the sweep judges it */
        }
        n = titles_candidates(game, e, &where, &carriers);
        if (n >= 2 && !(e->flags & VV_TITLE_CONTESTED)) {
            /* Two or more could be them at once: whoever is left later
               (the others died or left) is not taken for them -- a guess. */
            e->flags |= VV_TITLE_CONTESTED;
            changed = 1;
        }
        if (n == 1 && e->index == VV_TITLE_PENDING && (e->flags & VV_TITLE_CONTESTED)) {
            target[i] = -1;                   /* one left of several: the player decides, never a guess */
        } else if (n == 1) {
            target[i] = where;
        } else if (carriers == 0 && e->index != VV_TITLE_PENDING && !(moved && sweep && titles.seen[i])) {
            target[i] = -3;                   /* nobody carries it: away or gone, the sweep judges */
        } else {
            target[i] = -1;                   /* two or more could be them, or none: pending */
        }
    }
    /* No villager is given two titles' entries: one that another entry goes
       to, or that a bound entry left as it is holds, is nobody's for certain. */
    for (i = 0; i < titles.count; ++i) {
        if (target[i] < 0) {
            continue;
        }
        for (j = 0; j < titles.count; ++j) {
            int at = target[j] >= 0 ? target[j]
                : (target[j] == -2 && titles.entries[j].index != VV_TITLE_PENDING
                   ? (int)titles.entries[j].index : -1);
            if (j != i && at == target[i]) {
                clash[i] = 1;
            }
        }
    }
    for (i = 0, kept = 0; i < titles.count; ++i) {
        titles.entries[kept] = titles.entries[i];
        titles.seen[kept] = titles.seen[i];
        if (target[i] == -3) {
            for (j = 0; j < titles.count; ++j) {
                if (target[j] >= 0 && !clash[j] && (unsigned int)target[j] == titles.entries[i].index) {
                    target[i] = -1;           /* another entry's villager is in its record now */
                }
            }
        }
        if (target[i] >= 0 && !clash[i]) {
            if ((unsigned int)target[i] != titles.entries[kept].index) {
                titles.entries[kept].index = (unsigned int)target[i];
                changed = 1;
            }
            titles.seen[kept] = 1;
        } else if (target[i] == -1 || target[i] >= 0) {
            if (titles.entries[kept].index != VV_TITLE_PENDING) {
                titles.entries[kept].index = VV_TITLE_PENDING;
                changed = 1;
            }
            titles.seen[kept] = 0;
        }
        ++kept;
    }
    for (i = kept; i < titles.count; ++i) {
        titles.seen[i] = 0;
    }
    titles.count = kept;
    return changed;
}

/* Keep each bound entry's looks those of its villager now (a Change
   Appearance, an island event's new head, the age and skills of a new
   session): the next load is matched against them.  Returns 1 when any
   changed. */
static int titles_refresh_looks(int game) {
    int i;
    int changed = 0;
    for (i = 0; i < titles.count; ++i) {
        vv_custom_title *e = &titles.entries[i];
        const unsigned char *record = e->index == VV_TITLE_PENDING ? NULL : story_record(game, (int)e->index);
        vv_title_looks now;
        if (record == NULL || !story_record_present(game, record)
            || story_title_identity(game, record) != e->fingerprint) {
            continue;
        }
        titles_looks_now(game, (int)e->index, record, &now);
        if (!(e->flags & VV_TITLE_KNOWN) || memcmp(&e->looks, &now, sizeof now) != 0) {
            e->looks = now;
            e->flags |= VV_TITLE_KNOWN;
            changed = 1;
        }
    }
    return changed;
}

/* Who is present in each record now: identity and the part of it a rename
   leaves alone, 0 for a record nobody is in.  Returns how many are present. */
static int titles_take_roster(int game, unsigned int *ids, unsigned int *stable, unsigned int *keep,
                              int *age) {
    int count = story_record_count(game);
    int r, n = 0;
    memset(ids, 0, TITLES_ROSTER * sizeof(unsigned int));
    memset(stable, 0, TITLES_ROSTER * sizeof(unsigned int));
    memset(keep, 0, TITLES_ROSTER * sizeof(unsigned int));
    memset(age, 0, TITLES_ROSTER * sizeof(int));
    for (r = 0; r < count && r < TITLES_ROSTER; ++r) {
        const unsigned char *record = story_record(game, r);
        if (record != NULL && story_record_present(game, record)) {
            ids[r] = story_title_identity(game, record);
            stable[r] = story_title_stable(game, record);
            keep[r] = story_title_keep(game, record);
            age[r] = story_title_age(game, record);
            ++n;
        }
    }
    return n;
}

/* titles_unpublished: a change carried by titles_relook, or made while the
   village was away (titles.frozen), and not yet in the file; the next tick
   in the village publishes it. */

/* Note the age and skills each record's villager is first seen with: every
   record on a move (a load: the save's own values), else each record whose
   villager is new there -- not one renamed or whose likes changed in place,
   who is the same villager -- or REBORN there (titles_reborn). */
static int titles_reborn(int r, const unsigned int *now, const int *now_age) {
    /* The same fingerprint in the record but younger than at the last look:
       a newborn namesake (the same name and likes) put into the record of a
       villager who died between two looks -- at the 256 cap every birth
       takes a freed record.  Nobody grows younger. */
    return titles.roster_anyone && now[r] != 0 && now[r] == titles.roster[r] && now_age[r] < titles.roster_age[r];
}

static void titles_note_bases(int game, const unsigned int *now, const int *now_age, int moved, int renamed,
                              const unsigned char *in_place, int in_place_count) {
    int r;
    for (r = 0; r < TITLES_ROSTER; ++r) {
        const unsigned char *record;
        vv_title_looks looks;
        if (now[r] == 0 || (!moved && !titles_reborn(r, now, now_age)
                            && (titles.roster[r] == now[r] || r == renamed
                                || (in_place_count > 0 && in_place[r])))) {
            continue;
        }
        record = story_record(game, r);
        if (record == NULL) {
            continue;
        }
        story_title_looks(game, record, &looks);
        titles.base_age[r] = looks.age;
        memcpy(titles.base_skills[r], looks.skills, sizeof looks.skills);
    }
}

/* The lookup's look between two ticks: only a likes / dislikes change in
   place (identity_in_place.h) is carried, in memory, and the roster taken
   as the last look; anything else is left for the tick to judge, with no
   file touched here.  (The lookup runs inside the game's own drawing and
   island-event code.) */
static void titles_relook(int game) {
    static unsigned int now[TITLES_ROSTER];
    static unsigned int now_stable[TITLES_ROSTER];
    static unsigned int now_keep[TITLES_ROSTER];
    static int now_age[TITLES_ROSTER];
    static unsigned char in_place[TITLES_ROSTER];
    int i, present, in_place_count;
    if (!titles.loaded || !titles.roster_anyone || titles.frozen) {
        return;
    }
    present = titles_take_roster(game, now, now_stable, now_keep, now_age);
    in_place_count = present == 0 ? 0
        : vv_roster_changed_in_place(TITLES_ROSTER, titles.roster, titles.roster_keep, titles.roster_age, now,
                                     now_keep, now_age, in_place);
    if (in_place_count <= 0) {
        return;
    }
    for (i = 0; i < titles.count; ++i) {
        unsigned int r = titles.entries[i].index;
        if (r < TITLES_ROSTER && in_place[r] && titles.entries[i].fingerprint == titles.roster[r]) {
            titles.entries[i].fingerprint = now[r];
            titles_unpublished = 1;
        }
    }
    titles_note_bases(game, now, now_age, 0, -1, in_place, in_place_count);
    memcpy(titles.roster, now, sizeof now);
    memcpy(titles.roster_stable, now_stable, sizeof now_stable);
    memcpy(titles.roster_keep, now_keep, sizeof now_keep);
    memcpy(titles.roster_age, now_age, sizeof now_age);
}

/* Once per frame (from the Origins companion's tick): bind to the slot,
   detect a Start Over, move titles to where their villagers are now, bind
   pending titles whose villager can be told again, and drop the titles of
   villagers that are gone. */
static void titles_pass(int game, int sweep) {
    static unsigned int now[TITLES_ROSTER];
    static unsigned int now_stable[TITLES_ROSTER];
    static unsigned int now_keep[TITLES_ROSTER];
    static int now_age[TITLES_ROSTER];
    static unsigned char in_place[TITLES_ROSTER];
    static unsigned char reborn[TITLES_ROSTER];
    int i;
    int changed = 0;
    int present;
    int moved;
    int renamed;
    int in_place_count;
    int foreign;
    int roster_changed;
    int periodic = 0;
    titles_sync(game);
    if (!titles.loaded) {
        return;
    }
    /* Every tick, titled or not, so the last look is never stale when a
       title is set. */
    present = titles_take_roster(game, now, now_stable, now_keep, now_age);
    renamed = vv_roster_renamed(TITLES_ROSTER, titles.roster, titles.roster_stable, now, now_stable);
    /* LIKES OR DISLIKES CHANGED (v1.35.68): an island event, the Custom
       Island Event, a vial, the Crystal of Reflections or an upgrade gave a
       villager new likes or dislikes, so the identity the title is kept by
       changed -- and the title was swept away as if the villager had gone
       (The Tree of Life, "Faces in the Night": "Custom title: Moon Mother ->
       none").  The same villager stayed in the same record, with the same
       name, sex and age, and nobody moved (identity_in_place.h): the title
       takes the new identity below.  Like a rename, it is play, never
       another array (a village of one whose likes changed shares no
       identity with the last look). */
    in_place_count = renamed < 0 && titles.roster_anyone
        ? vv_roster_changed_in_place(TITLES_ROSTER, titles.roster, titles.roster_keep, titles.roster_age,
                                     now, now_keep, now_age, in_place)
        : 0;
    /* A WHOLE OTHER ARRAY IS NOT PLAY (native/shared/foreign_sidecar.h).
       Nobody of the last look is on screen: the game has put another village
       in the records with the slot unchanged -- the title screen after a
       quit to the menu, whose slot list leaves seeded founders there. */
    foreign = renamed < 0 && in_place_count == 0 && titles.roster_anyone && present > 0
        && vv_roster_shares(TITLES_ROSTER, titles.roster, now) == 0;
    moved = !titles.roster_anyone || foreign || vv_roster_moved(TITLES_ROSTER, titles.roster, now);
    if (in_place_count > 0 && !titles.frozen) {
        moved = 0;                            /* the same villagers, in the same records */
        for (i = 0; i < titles.count; ++i) {
            unsigned int r = titles.entries[i].index;
            if (r < TITLES_ROSTER && in_place[r] && titles.entries[i].fingerprint == titles.roster[r]) {
                titles.entries[i].fingerprint = now[r];
                changed = 1;
            }
        }
    }
    /* A RENAME (Codex, #516): the identity hashes the name, so the title of
       a villager the player renamed no longer matched their record and the
       sweep threw it away.  One record changed, the rest of the identity
       unchanged: the same villager, and the title takes the new identity. */
    if (renamed >= 0 && !titles.frozen) {
        moved = 0;                            /* one villager renamed: nobody moved */
        for (i = 0; i < titles.count; ++i) {
            if (titles.entries[i].index == (unsigned int)renamed
                && titles.entries[i].fingerprint == titles.roster[renamed]) {
                titles.entries[i].fingerprint = now[renamed];
                changed = 1;
            }
        }
    }
    titles_note_bases(game, now, now_age, moved, renamed, in_place, in_place_count);
    for (i = 0; i < TITLES_ROSTER; ++i) {
        reborn[i] = (unsigned char)titles_reborn(i, now, now_age);
    }
    roster_changed = memcmp(titles.roster, now, sizeof now) != 0;
    memcpy(titles.roster, now, sizeof now);
    memcpy(titles.roster_stable, now_stable, sizeof now_stable);
    memcpy(titles.roster_keep, now_keep, sizeof now_keep);
    memcpy(titles.roster_age, now_age, sizeof now_age);
    titles.roster_anyone = present > 0;
    /* START OVER BEFORE A FREEZE (review of #585, v1.35.71): Start Over
       deletes the file and puts a founder roster with nobody of the last look
       in the records -- which looks like the title screen's other array.
       Frozen at once, the table was never checked against the deleted file
       again, kept the erased village's titles in memory, and a founder later
       given the same record and identity could be shown one.  So the file is
       looked at before freezing, and every TITLES_CHECK_MS while frozen: gone,
       and the table is forgotten (titles_reset_detected). */
    if ((foreign && !titles.frozen)
        || (titles.frozen && GetTickCount() - titles.checked_at >= TITLES_CHECK_MS)) {
        titles.checked_at = GetTickCount();
        if (titles_reset_detected()) {
            return;
        }
    }
    /* The village went away (the title screen): nothing is judged, moved,
       swept or written -- the file keeps the village as it was left, and
       nobody seen there may be taken for dead.  The next array to arrive is
       a load, and every title is followed afresh then. */
    if (foreign && !titles.frozen) {
        titles.frozen = 1;
        memset(titles.seen, 0, sizeof titles.seen);
        return;
    }
    if (titles.frozen) {
        if (!moved) {
            return;
        }
        titles.frozen = 0;
        moved = 1;
    }
    if (titles.count == 0) {
        return;
    }
    if (GetTickCount() - titles.checked_at >= TITLES_CHECK_MS) {
        titles.checked_at = GetTickCount();
        periodic = 1;
        if (titles_reset_detected()) {
            return;
        }
    }
    changed |= titles_follow(game, moved, sweep, moved || roster_changed || periodic);
    for (i = titles.count - 1; sweep && i >= 0; --i) {
        const unsigned char *record;
        int match;
        if (titles.entries[i].index == VV_TITLE_PENDING) {
            continue;                         /* shown on nobody, waiting: never swept */
        }
        record = story_record(game, (int)titles.entries[i].index);
        match = record != NULL && story_record_present(game, record)
            && titles.entries[i].fingerprint == story_title_identity(game, record)
            && !(titles.entries[i].index < TITLES_ROSTER && reborn[titles.entries[i].index]);
        if (match) {
            titles.seen[i] = 1;
        } else if (titles.seen[i]) {
            titles_remove_at(i);
            changed = 1;
        } else if (titles.entries[i].index < TITLES_ROSTER && reborn[titles.entries[i].index]) {
            titles.entries[i].index = VV_TITLE_PENDING;   /* not seen die: whose it is waits */
            changed = 1;
        }
    }
    changed |= titles_refresh_looks(game);
    if (changed || titles_unpublished) {
        titles_unpublished = 0;
        titles_publish();
    }
}

static void titles_tick(int game) {
    titles_pass(game, 1);
}

/* Start Over or a deleted tribe in `slot` (VvfpStoryVillageReset): the
   village the table describes is gone -- its file is deleted by the reset
   (native/shared/save_reset.c) -- so its titles are forgotten at once,
   whatever the records show next (review of #585). */
static void titles_village_reset(int game, int slot) {
    if (titles.game == game && titles.slot == slot && titles.slot > 0) {
        titles_forget();
        titles.file_present = 0;
    }
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

/* Called by Origins' Change Appearance (native/shared/appearance_log.h) when
   a villager's head and body change, only when this companion is already
   loaded: the title's stored head and body follow at once (see
   titles_appearance_changed).  Always 1; never changes the villager. */
__declspec(dllexport) int __stdcall VvfpStoryAppearanceChanged(int game, const void *record, int head, int body) {
    if (game < 1 || game > 5 || record == NULL) {
        return 1;
    }
    (void)titles_appearance_changed(game, (const unsigned char *)record, head, body);
    return 1;
}
