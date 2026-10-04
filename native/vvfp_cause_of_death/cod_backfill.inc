/* Every grave in the Deaths log: the graves no hook saw.  Every game.
   Included by vvfp_cause_of_death.c.

   The owner: "two villagers are missing from the deaths log!" -- A New
   Home's Kito and Chika were buried before v1.35.51 brought the log -- and
   "make sure all the logs are consistent with the current save".  A Death
   record is written at the burial, by the hook this companion installs once
   a village is shown; a grave dug before the log existed, or during the
   load-time catch-up that runs before the install, never got one.

   At each save of a village (cod_save_done, after the village is named for
   the logs and before the roster is reconciled), every grave the game holds
   is handed to "VVFP Parentage Export.dll" (RecordGravesMissingFromLog,
   native/parentage_export/grave_backfill.inc), which finds the graves its
   Deaths log has no record for and writes one for each, from the grave.

   The graves:
     A New Home, The Lost Children  the 50 graves (cod_vv12.inc), the cause
                                    and A New Home's epitaph from this
                                    companion's graves file
     The Secret City, The Tree of   the Roster of the Dead / mausoleum's 500
     Life, New Believers            entries (cod_vv345.inc), with the game's
                                    own cause and epitaph
   The data, not the graveyard on screen: The Secret City shows its graves
   only once the Roster of the Dead puzzle is solved, New Believers once the
   mausoleum is restored, but the burial writes the entry either way.

   EXACTLY ONCE.  Which graves the log already has is kept here, per save
   slot:
       <save folder>\Virtual Villagers Fun Patcher Data\Deaths\
           Graves Logged - Save S.dat
   (format below): each grave whose Death record is in the log -- written at
   its burial (noted then, kept at the next save of that slot), found already
   there, or written from the grave now.  A grave is identified by its place
   (graves and entries are filled lowest-free-first and never moved) and the
   fingerprint of its name and age at death; a place now holding another
   grave (a replaced save) is not covered.  Only graves not in the file are
   handed over as uncovered, and the parentage DLL counts the log's own
   records before writing anything (grave_backfill.inc), so a grave already
   recorded -- by an older build, before this file existed -- is never
   recorded again.  Start Over deletes the file with the logs. */

#define LOGGED_MAGIC 0x31474356u          /* 'VCG1' */
#define LOGGED_VERSION 1u
#define LOGGED_HEADER 16u
#define LOGGED_ENTRY 8u
#define LOGGED_MAX V345_ENTRIES

/* The patcher's own data file for one kind of record, in that kind's own
   folder:  "<save folder>\Virtual Villagers Fun Patcher Data\<folder>\
   <stem> - Save <slot>.dat".  One helper, so a later move of the data
   files changes one place. */
static int cod_data_path(char *out, const char *folder_name, const char *stem, int slot) {
    char folder[MAX_PATH];
    char sub[96];
    wsprintfA(sub, "Virtual Villagers Fun Patcher Data\\%s", folder_name);
    if (lstrlenA(stem) > 48
        || !vv_save_subfolder(folder, sub, lstrlenA(stem) + (int)sizeof("\\ - Save 0.dat"))) {
        return 0;
    }
    wsprintfA(out, "%s\\%s - Save %d.dat", folder, stem, slot);
    return 1;
}

/* The graves covered, by place: the fingerprint of the grave covered there,
   0 = none. */
static unsigned int logged_fp[LOGGED_MAX];

static struct {
    int slot;
    int dirty;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} logged;

static unsigned char logged_buffer[LOGGED_HEADER + LOGGED_MAX * LOGGED_ENTRY];

/* Burials whose Death record the hook wrote since the last save, kept for
   that save of the slot they were made in (report_tag, cod_roster.inc). */
#define MARKS_MAX 256
static struct { signed char tag; short place; unsigned int fingerprint; } marks[MARKS_MAX];
static int mark_count;

static int cod_grave_places(void) {
    return g_game <= 2 ? GRAVES : V345_ENTRIES;
}

/* FORMAT (little-endian), exactly 16 + 8 * count bytes:
       u32 magic 'VCG1', u32 version 1, u32 game, u32 count,
       count x { u16 place (VV1/VV2 grave 0-49, VV3-VV5 entry 0-499), u16 0,
                 u32 fingerprint (cod_fingerprint of the grave's name and age
                 at death; never 0) }
   in increasing place, each place once. */
static int logged_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count;
    unsigned int i;
    int previous = -1;
    (void)context;
    if (length < LOGGED_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    if (*(const unsigned int *)data != LOGGED_MAGIC
        || *(const unsigned int *)(data + 4) != LOGGED_VERSION
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game
        || count > (unsigned int)cod_grave_places()
        || length != LOGGED_HEADER + count * LOGGED_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + LOGGED_HEADER + i * LOGGED_ENTRY;
        int place = e[0] | e[1] << 8;
        if (place <= previous || place >= cod_grave_places() || e[2] || e[3]
            || *(const unsigned int *)(e + 4) == 0u) {
            return 0;
        }
        previous = place;
    }
    return 1;
}

/* The file for `slot`, read into logged_fp.  0 when it is blocked (a lock):
   nothing is decided at this save. */
static int logged_bind(int slot) {
    DWORD length = 0;
    int result;
    unsigned int i;
    if (slot != logged.slot) {
        logged.slot = slot;
        logged.path[0] = '\0';
        vv_sidecar_gate_bind(&logged.gate, 0x200 + g_game * 16 + slot);
    }
    if (logged.path[0] == '\0' && !cod_data_path(logged.path, "Deaths", "Graves Logged", slot)) {
        return 0;
    }
    result = vv_sidecar_load(&logged.gate, logged.path, logged_buffer, sizeof logged_buffer,
                             &length, logged_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return 0;
    }
    memset(logged_fp, 0, sizeof logged_fp);
    logged.dirty = 0;
    if (result == VV_SIDECAR_LOAD_VALID) {
        unsigned int count = *(const unsigned int *)(logged_buffer + 12);
        for (i = 0; i < count; ++i) {
            const unsigned char *e = logged_buffer + LOGGED_HEADER + i * LOGGED_ENTRY;
            logged_fp[e[0] | e[1] << 8] = *(const unsigned int *)(e + 4);
        }
    }
    return 1;
}

static void logged_publish(void) {
    const void *parts[1];
    DWORD sizes[1];
    unsigned int count = 0;
    int place;
    if (!logged.dirty) {
        return;
    }
    for (place = 0; place < cod_grave_places(); ++place) {
        unsigned char *e;
        if (logged_fp[place] == 0u) {
            continue;
        }
        e = logged_buffer + LOGGED_HEADER + count * LOGGED_ENTRY;
        e[0] = (unsigned char)(place & 0xFF);
        e[1] = (unsigned char)(place >> 8);
        e[2] = 0;
        e[3] = 0;
        *(unsigned int *)(e + 4) = logged_fp[place];
        ++count;
    }
    ((unsigned int *)logged_buffer)[0] = LOGGED_MAGIC;
    ((unsigned int *)logged_buffer)[1] = LOGGED_VERSION;
    ((unsigned int *)logged_buffer)[2] = (unsigned int)g_game;
    ((unsigned int *)logged_buffer)[3] = count;
    parts[0] = logged_buffer;
    sizes[0] = LOGGED_HEADER + count * LOGGED_ENTRY;
    if (vv_sidecar_publish(&logged.gate, logged.path, parts, sizes, 1)) {
        logged.dirty = 0;
        COD_COUNT(published);
    }
}

/* A burial's Death record was written (or queued) for the grave at
   `place`: it is covered from the next save of this slot. */
static void backfill_mark(int place, unsigned int fingerprint) {
    if (place < 0 || place >= cod_grave_places() || fingerprint == 0u) {
        return;
    }
    if (mark_count < MARKS_MAX) {
        marks[mark_count].tag = report_tag();
        marks[mark_count].place = (short)place;
        marks[mark_count].fingerprint = fingerprint;
        ++mark_count;
    }
    /* A full journal only means the log is read for the rest: the parentage
       DLL finds their records there. */
}

/* ---- The graves, as each game holds them ---------------------------------- */

static vv_grave_fact facts[LOGGED_MAX];
static unsigned int fact_fp[LOGGED_MAX];

/* Copy a name as the grave holds it (raw bytes, at most `capacity`). */
static void fact_name(vv_grave_fact *f, const unsigned char *name, unsigned int capacity) {
    unsigned int i;
    for (i = 0; i + 1 < VV_GRAVE_NAME && i < capacity && name[i] != 0; ++i) {
        f->name[i] = (char)name[i];
    }
    f->name[i] = '\0';
}

#ifdef VVFP_TEST
/* The harnesses have no game image at the later games' addresses: they hand
   their own Roster of the Dead (and The Secret City's gravestones) here. */
static unsigned char *test_roster;
static unsigned char *test_gravestones;
#endif

static const unsigned char *backfill_entry(int place) {
#ifdef VVFP_TEST
    if (test_roster != NULL) {
        return test_roster + (size_t)place * V345[g_game].entry_stride;
    }
#endif
    return v345_entry(place);
}

static const unsigned char *backfill_gravestone(int place) {
#ifdef VVFP_TEST
    if (test_gravestones != NULL) {
        return test_gravestones + (size_t)place * VV3_GRAVESTONE_STRIDE;
    }
#endif
    return (const unsigned char *)(uintptr_t)(VV3_GRAVESTONES + (unsigned int)place * VV3_GRAVESTONE_STRIDE);
}

/* Every grave the village holds into facts[], in place order, with its
   fingerprint in fact_fp[]; the count, or -1 when the graves cannot be read
   now.  The cause and epitaph are added only to the graves not yet covered
   (backfill_words). */
static int backfill_gather(void) {
    int n = 0;
    int place;
    if (g_game <= 2) {
        if (cod_grave_owner() == NULL) {
            return -1;
        }
        for (place = 0; place < GRAVES; ++place) {
            const unsigned char *grave = cod_grave(place);
            vv_grave_fact *f = &facts[n];
            int age = *(const int *)(grave + GRV[g_game].age);
            if (age == 0) {
                continue;
            }
            memset(f, 0, sizeof *f);
            f->place = place;
            f->age = age;
            fact_name(f, grave, GRV[g_game].name_capacity);
            cod_grave_title(grave, f->grave);
            fact_fp[n] = cod_grave_fingerprint(grave);
            ++n;
        }
        return n;
    }
    for (place = 0; place < V345_ENTRIES; ++place) {
        const unsigned char *entry = backfill_entry(place);
        vv_grave_fact *f = &facts[n];
        int age = *(const int *)(entry + V345[g_game].e_age);
        unsigned int capacity = v345_name_capacity();
        if (age == 0) {
            continue;
        }
        memset(f, 0, sizeof *f);
        f->place = place;
        f->age = age;
        fact_name(f, entry, capacity);
        v345_title(entry, f->grave);
        fact_fp[n] = v345_fingerprint(entry);
        ++n;
    }
    return n;
}

/* The cause and the epitaph of an uncovered grave, as its Death record
   would have had them. */
static void backfill_words(vv_grave_fact *f) {
    if (g_game <= 2) {
        const unsigned char *grave = cod_grave(f->place);
        const struct cod_entry *entry = cod_grave_entry(f->place, grave);
        int cause = entry != NULL ? entry->cause : CAUSE_NONE;
        lstrcpynA(f->cause, cod_cause_words(cause), VV_GRAVE_CAUSE);
        if (g_game == 1) {
            /* The epitaph A New Home's popup shows: the one this companion
               gave the grave (cod_grave_entry gives one now to a grave from
               before, by the same rule, and keeps it), or the player's own. */
            const char *text = entry != NULL ? cod_entry_epitaph(entry) : NULL;
            lstrcpynA(f->epitaph, text != NULL ? text : "", VV_GRAVE_EPITAPH);
        } else {
            cod_printable(f->epitaph, VV_GRAVE_EPITAPH, (const char *)grave + GRV[2].epitaph,
                          (int)GRV[2].epitaph_capacity);
        }
        return;
    }
    {
        const unsigned char *entry = backfill_entry(f->place);
        lstrcpynA(f->cause, cod_cause_words(*(const int *)(entry + V345[g_game].e_cause)),
                  VV_GRAVE_CAUSE);
        if (g_game != 3) {
            cod_printable(f->epitaph, VV_GRAVE_EPITAPH, (const char *)entry + V345[g_game].e_epitaph,
                          EPITAPH_TEXT);
        } else if (f->place < 50) {
            cod_printable(f->epitaph, VV_GRAVE_EPITAPH,
                          (const char *)backfill_gravestone(f->place) + 8, EPITAPH_TEXT);
        } else {
            lstrcpynA(f->epitaph, "(none: only the first 50 graves get a gravestone)", VV_GRAVE_EPITAPH);
        }
    }
}

/* The graves recorded at this save, for the roster reconciliation that
   follows it: a villager the last save held who left with no report, and
   whose grave was just recorded, is accounted for (cod_roster.inc). */
static int recorded_now[LOGGED_MAX];      /* indices into facts[] */
static int recorded_now_count;
static unsigned char recorded_used[LOGGED_MAX];

/* Whether the player chose Repair for the slot's graves this session
   (VvfpCauseRepairGraves): the owner, "the player should be notified first
   before any fix runs".  Not asked, or "Not now": nothing is written. */
static signed char repair_chosen[6];

/* The slot's graves into facts[], each marked covered when the file (or a
   burial recorded since the last save) says its Death record is in the log.
   The count, or -1 when the graves or the file cannot be read now.  Nothing
   is written: logged_fp is brought up to date in memory (logged.dirty). */
static int backfill_survey(int slot) {
    int count;
    int i;
    int place;
    int k = 0;
    if (!logged_bind(slot)) {
        return -1;
    }
    /* The burials recorded since the last save of this slot. */
    for (i = 0; i < mark_count; ++i) {
        if (report_counts(marks[i].tag, slot) && logged_fp[marks[i].place] != marks[i].fingerprint) {
            logged_fp[marks[i].place] = marks[i].fingerprint;
            logged.dirty = 1;
        }
    }
    count = backfill_gather();
    if (count < 0) {
        return -1;
    }
    /* A place covered for another grave than the one there now (the save
       was replaced, or the grave is gone) is not covered. */
    for (place = 0; place < cod_grave_places(); ++place) {
        unsigned int now = 0;
        if (k < count && facts[k].place == place) {
            now = fact_fp[k++];
        }
        if (logged_fp[place] != 0u && logged_fp[place] != now) {
            logged_fp[place] = 0u;
            logged.dirty = 1;
        }
    }
    for (i = 0; i < count; ++i) {
        facts[i].covered = logged_fp[facts[i].place] == fact_fp[i];
    }
    return count;
}

static void backfill_at_save(int slot, const void *save_buffer) {
    int count;
    int i;
    int uncovered = 0;
    recorded_now_count = 0;
    if (install_state != 1 || save_buffer == NULL || slot < 1 || slot > 5 || !repair_chosen[slot]
        || !cod_log_ready() || record_graves == NULL) {
        return;
    }
    /* A New Home's and The Lost Children's causes (and A New Home's
       epitaphs) are in the graves file, which must be this slot's. */
    if (g_game <= 2 && (!store.loaded || store.slot != slot)) {
        return;
    }
    count = backfill_survey(slot);
    if (count < 0) {
        return;
    }
    for (i = 0; i < count; ++i) {
        if (!facts[i].covered) {
            backfill_words(&facts[i]);
            ++uncovered;
        }
    }
    if (uncovered > 0 && record_graves(g_game, save_buffer, slot, facts, count, 1) >= 0) {
        for (i = 0; i < count; ++i) {
            if (facts[i].covered) {
                continue;
            }
            if (facts[i].outcome == VV_GRAVE_IN_LOG || facts[i].outcome == VV_GRAVE_RECORDED) {
                logged_fp[facts[i].place] = fact_fp[i];
                logged.dirty = 1;
            }
            if (facts[i].outcome == VV_GRAVE_RECORDED) {
                recorded_used[recorded_now_count] = 0;
                recorded_now[recorded_now_count++] = i;
                COD_COUNT(backfilled);
            }
        }
    }
    logged_publish();
    if (!logged.dirty) {
        /* The marks for this slot are in the file now. */
        int kept = 0;
        for (i = 0; i < mark_count; ++i) {
            if (!report_counts(marks[i].tag, slot)) {
                marks[kept++] = marks[i];
            }
        }
        mark_count = kept;
    }
}

/* ---- For the first-load cross-check's popup --------------------------------

   VvfpCauseScanGraves(game, slot): how many of the village's graves have no
   Death record in its Deaths log, writing nothing -- -1 when that cannot be
   told now (Cause of Death refused, the log's DLL absent, a file locked, the
   village unknown).  Call it once the village is loaded.
   VvfpCauseRepairGraves(game, slot, repair): the player's answer.  1
   (Repair): at the village's next save -- where its logs are named -- each
   such grave gets its Death record; 0 (Not now): nothing this session, and
   the scan finds them again at the next load. */
__declspec(dllexport) int __stdcall VvfpCauseScanGraves(int game, int slot) {
    int count;
    if (install_state == -1 || game < 1 || game > 5 || (g_game != 0 && game != g_game)
        || slot < 1 || slot > 5) {
        return -1;
    }
    if (install_state == 0) {
        g_game = game;
        cod_locate_table();
    }
    if (!cod_log_ready() || record_graves == NULL) {
        return -1;
    }
    count = backfill_survey(slot);
    if (count < 0) {
        return -1;
    }
    {
        int i;
        int uncovered = 0;
        for (i = 0; i < count; ++i) {
            uncovered += !facts[i].covered;
        }
        if (uncovered == 0) {
            return 0;
        }
    }
    return record_graves(g_game, NULL, slot, facts, count, 0);
}

__declspec(dllexport) void __stdcall VvfpCauseRepairGraves(int game, int slot, int repair) {
    if (game < 1 || game > 5 || (g_game != 0 && game != g_game) || slot < 1 || slot > 5) {
        return;
    }
    repair_chosen[slot] = (signed char)(repair != 0);
}

/* A villager the last save held, gone with no report: the grave recorded
   from at this save with the same name and an age at death at least the age
   they were saved at accounts for them -- one grave for one villager, and
   only when exactly one such grave is left (otherwise they stay
   unaccounted). */
static int backfill_accounts_for(const unsigned char *kept) {
    const struct game_records *r = &REC[g_game];
    int found = -1;
    int i;
    for (i = 0; i < recorded_now_count; ++i) {
        const vv_grave_fact *f = &facts[recorded_now[i]];
        unsigned int n;
        int same = 1;
        if (recorded_used[i] || f->age < rec_age(kept)) {
            continue;
        }
        for (n = 0; n < r->name_capacity && n < VV_GRAVE_NAME; ++n) {
            unsigned char a = kept[r->name + n];
            unsigned char b = (unsigned char)f->name[n];
            if (a != b) {
                same = 0;
                break;
            }
            if (a == 0) {
                break;
            }
        }
        if (!same) {
            continue;
        }
        if (found >= 0) {
            return 0;                 /* two graves could be theirs */
        }
        found = i;
    }
    if (found < 0) {
        return 0;
    }
    recorded_used[found] = 1;
    return 1;
}

static void backfill_reset(int slot) {
    int i, kept = 0;
    if (slot == logged.slot) {
        vv_sidecar_gate_bind(&logged.gate, -1);
        logged.slot = 0;
        logged.path[0] = '\0';
        logged.dirty = 0;
        memset(logged_fp, 0, sizeof logged_fp);
    }
    for (i = 0; i < mark_count; ++i) {
        if (marks[i].tag != slot) {
            marks[kept++] = marks[i];
        }
    }
    mark_count = kept;
    recorded_now_count = 0;
    if (slot >= 1 && slot <= 5) {
        repair_chosen[slot] = 0;      /* the answer was for the village erased */
    }
}
