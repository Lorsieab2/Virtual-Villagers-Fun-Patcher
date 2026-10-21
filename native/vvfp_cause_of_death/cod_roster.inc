/* The Unaccounted Villagers log: the save-time reconciliation, every game.
   Included by vvfp_cause_of_death.c.

   The owner: "for villagers who somehow can't be reconciled by the logs or
   loggers, please put their data and details in a separate log. No villager
   gets unaccounted for!" -- a villager gone from the village with no Death
   or Disappeared record, and one who appears with no Birth record or known
   arrival, each gets an "Unaccounted" record with everything last known.

   WHEN.  Right after every successful save of a village (the game's own
   save call returns, al = 1, edi = the slot: VV2 0x424BF8,
   VV3 0x427D71, VV4 0x41F13F, VV5 0x4245FF -- the instruction after the
   call, which the Village Statistics row's own hook on the call leaves
   alone), against the roster kept at the previous save.  The games save
   only on a clean quit, so a session killed without saving never reaches a
   save: the next session loads the old save and reconciles against the
   roster that matches it, and nothing that happened in the lost session can
   be reported as missing.

   WHO IS ACCOUNTED FOR.  Departures: every Death record (a burial, an
   unburied body's removal) and every Disappeared record reports the record
   it closes (roster_departed).  Arrivals: every villager the game's own
   creator makes -- a birth, an event's newcomer, the Barrel of Babies, the
   Custom Island Event's new villagers -- reports the record it fills
   (roster_arrived, at the creator's sites in cod_roster_sites.inc).  A
   birth the Births and Conceptions log records is reported by that log's
   own companion too (VvfpCauseNoteArrival), because this companion is
   installed from the first village frame, after the load-time catch-up of
   the first village has already run its births.  A record is only ever
   matched by its own slot: the game hands it over, so nothing is matched by
   name.

   A report counts only for the save slot it was made in (or, made before
   this companion was installed, for the village then loading), and is
   spent by the save that accounts for it.

   VILLAGERS ARE FOLLOWED BY WHO THEY ARE, NEVER BY THEIR RECORD (the owner,
   2026-10-20).  A record number holds different villagers over time: every
   load packs the occupied records into 0, 1, 2, ...; a full village reuses
   a dead villager's record for the next birth; and The Lost Children's
   Elder Totems companion moves the totems out of the villager table, so
   every later villager loads into another record.  The first load with that
   companion wrote 112 "Arrived" and 108 "Left" records for villagers who
   had only moved (the owner's Kalahuna Tribe 2, 2026-10-20 09:22:01): this
   matched the kept roster by record or rank, and took a villager of the
   same sex in that place for the same villager.  Now each villager kept at
   the last save is matched to a villager in the village now by identity
   (roster_match), one to one:
     1. the name, sex, head, body, likes and dislikes, with the age gone on
        by the time every matched villager aged (the same for all of them);
     2. the name, sex, head and body, the age gone on by any amount
        (likes or dislikes changed; a villager who died and lies unburied
        keeps the age at death);
     3. the name, sex, likes and dislikes, aged on -- only when exactly one
        villager on each side is such (an island event changed the head);
     4. the sex, head, body, likes and dislikes, aged on -- only when
        exactly one on each side is such (a rename: Last Names, Rename);
     5. everything but the age, exactly one on each side (rejuvenated).
   First, a departure the game reported since -- the departing villager's
   own name, sex, head and body, kept at the departure (roster_departed),
   at an age at least the kept one -- accounts for the kept villager it
   names, who is then never matched to anybody now (one written back alive
   unreported, or a newcomer in their record, has arrived unaccounted for).
   A record the game's creator filled since (an arrival reported) is
   accounted for and is matched only when no unreported villager is such.
   A kept villager matched by nobody whose grave was just recorded from
   (cod_backfill.inc) is accounted for; one who is not is "Left the
   village"; a villager now matched by nobody and not reported "Arrived".  A Death or Disappeared
   record is never followed by "Left" for the same villager, and a villager
   who only moved to another record is neither.  When more departures were
   reported than can be kept (RECORDS_MAX between two saves), nothing is
   written as "Left" at that save: unsure, never guessed.

   A roster none of whose villagers is matched, with nothing reported for
   that slot since, is not this village's (its save was replaced outside
   the game): a new roster is started and nothing is logged against the old
   one.

   Every departure is reported where the game frees the record (a burial,
   a body's removal, a disappearance), never at a death, so a body that is
   revived keeps its record and reports nothing.

   KEPT.  <save folder>\Virtual Villagers Fun Patcher Data\Unaccounted Villagers\
              Virtual Villagers N Village Roster - Save S.dat
   (format below), written atomically after each reconciliation; Start Over
   deletes it with the village, and the next save starts a new one. */

#define ROSTER_MAGIC 0x31524356u          /* 'VCR1' */
/* Version 2 keeps each villager's mask (0 none, 1..5 native/shared/mask_line.h) in the
   entry's first spare byte, so an Unaccounted record written from the snapshot names it
   (Codex, #553); a version 1 file (those bytes 0) is still read.
   Version 3, A New Home only: each entry is followed by the villager's own parents' names
   (father char[32], mother char[32]) from the Show Parents companion's sidecar -- A New Home keeps
   no parents on the record, so without them its Unaccounted record of a villager who left could
   not carry the "Parents:" block The Lost Children to New Believers print from the record (the
   owner, 2026-10-09: no game gets less information).  Versions 1 and 2 are still read (no
   parents: none printed); the other games keep writing version 2. */
#define ROSTER_VERSION 2u
#define ROSTER_VERSION_VV1 3u
#define ROSTER_HEADER 32u
#define ROSTER_ENTRY_HEAD 16u
#define ROSTER_PARENT_NAME 32u
#define ROSTER_PARENTS (2u * ROSTER_PARENT_NAME)

/* What the hooks reported since the last save, by record: the save slot
   the report was made in (REPORT_NONE: nothing; REPORT_EARLY: made before
   this companion was installed, when no slot is known). */
#define REPORT_NONE 0
#define REPORT_EARLY (-1)
static signed char departed[RECORDS_MAX];
static signed char arrived[RECORDS_MAX];

static signed char report_tag(void) {
    int slot = install_state == 1 ? cod_slot() : 0;
    return (signed char)(slot > 0 ? slot : REPORT_EARLY);
}

static int report_counts(signed char tag, int slot) {
    return tag == slot || tag == REPORT_EARLY;
}

/* A departure frees the record: an arrival reported into it before
   accounted for the villager who has now left, never for whoever the
   record holds next. */
/* Who each reported departure was (the record as the game frees it): the
   reconciliation accounts for a kept villager by this, never by the record
   number, which the next load gives to somebody else. */
#define GONE_NAME 32
struct roster_gone {
    signed char tag;                  /* report_tag(); REPORT_NONE: free */
    int age, sex, head, body;
    char name[GONE_NAME];
};
static struct roster_gone gone[RECORDS_MAX];
static signed char gone_overflow[2 + 5];   /* [tag + 1]: more departures than gone[] holds */
static unsigned char gone_spent[RECORDS_MAX];   /* matched to a kept villager at this reconciliation */

static void roster_gone_note(const unsigned char *record) {
    const struct game_records *r = &REC[g_game];
    signed char tag = report_tag();
    int i;
    unsigned int n;
    if (record == NULL) {
        return;
    }
    for (i = 0; i < RECORDS_MAX; ++i) {
        if (gone[i].tag == REPORT_NONE) {
            gone[i].tag = tag;
            gone[i].age = rec_age(record);
            gone[i].sex = *(const int *)(record + r->sex);
            gone[i].head = *(const int *)(record + r->head);
            gone[i].body = *(const int *)(record + r->body);
            for (n = 0; n + 1 < GONE_NAME && n < r->name_capacity && record[r->name + n] != 0; ++n) {
                gone[i].name[n] = (char)record[r->name + n];
            }
            gone[i].name[n] = '\0';
            return;
        }
    }
    if (tag + 1 >= 0 && tag + 1 < (int)sizeof gone_overflow) {
        gone_overflow[tag + 1] = 1;
    }
}

static void roster_departed(int index, const unsigned char *record) {
    arrival_departed(index);          /* an arrival not yet written: now */
    if (index >= 0 && index < RECORDS_MAX) {
        departed[index] = report_tag();
        arrived[index] = REPORT_NONE;
        roster_gone_note(record);
        COD_COUNT(departed);
    }
}

static void roster_arrived(int index) {
    if (index >= 0 && index < RECORDS_MAX) {
        arrived[index] = report_tag();
        COD_COUNT(arrived);
    }
}

static struct {
    int slot;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} roster;

static unsigned char *roster_buffer;          /* the file: header + entries */
static unsigned char *roster_scratch;         /* one record, rebuilt for the log */

/* FORMAT (little-endian), exactly 32 + count * (16 + (hi - lo)) bytes:
       u32 magic 'VCR1', u32 version 2 (1 read too), u32 game, u32 count,
       u32 lo, u32 hi (the record bytes kept, [lo, hi)), u32 0, u32 0,
       count x { u16 record index, u16 rank (the record's place among all
                 the occupied records the save packs, look-alikes and
                 temporary records included), u8 mask (version 2; 0 in
                 version 1), u8 0, u16 0, u64 when saved
                 (FILETIME, local time), (hi - lo) bytes of the record at
                 lo }
   Entries are in record order, one per occupied record that is a villager
   (living or a body; never a look-alike); both index and rank increase. */
static unsigned int roster_write_version(void) {
    return g_game == 1 ? ROSTER_VERSION_VV1 : ROSTER_VERSION;
}

/* An entry's size in a file of `version`: version 3 (A New Home) adds the parents' names. */
static unsigned int roster_entry_size_of(unsigned int version) {
    return ROSTER_ENTRY_HEAD + REC[g_game].snapshot_hi - REC[g_game].snapshot_lo
         + (version >= ROSTER_VERSION_VV1 ? ROSTER_PARENTS : 0u);
}

static unsigned int roster_entry_size(void) {
    return roster_entry_size_of(roster_write_version());
}

static unsigned int roster_max_bytes(void) {
    return ROSTER_HEADER + REC[g_game].slots * roster_entry_size();
}

/* A New Home's villager's own parents, from the Show Parents companion ("VVFP VV1 Parentage.dll",
   Vv1ParentageQueryNames, by record index): 1 when at least one is known.  Never for another game
   (theirs are on the record), nor without the companion. */
typedef int (__stdcall *vv1_parent_names_fn)(int index, char *father, char *mother, int capacity);
static int vv1_parent_names(int index, char *father, char *mother, int capacity) {
    HMODULE module;
    vv1_parent_names_fn names;
    father[0] = mother[0] = '\0';
    if (g_game != 1 || index < 0 || capacity < 2) {
        return 0;
    }
    module = GetModuleHandleA("VVFP VV1 Parentage.dll");
    if (module == NULL) {
        module = vvfp_load_patcher_dll("VVFP VV1 Parentage.dll");
    }
    names = module != NULL ? (vv1_parent_names_fn)GetProcAddress(module, "Vv1ParentageQueryNames") : NULL;
    if (names == NULL || !names(index, father, mother, capacity)) {
        father[0] = mother[0] = '\0';
        return 0;
    }
    father[capacity - 1] = mother[capacity - 1] = '\0';
    return father[0] != '\0' || mother[0] != '\0';
}

/* The "  Parents:" block exactly as the parentage exporter prints it from The Lost Children's to
   New Believers' records (WriteVillageRecord, detail 2): names only, "(none)" for one not known;
   empty when neither is. */
static void roster_parents_block(char *out, int size, const char *father, const char *mother) {
    out[0] = '\0';
    if ((father == NULL || father[0] == '\0') && (mother == NULL || mother[0] == '\0')) {
        return;
    }
    wsprintfA(out, "  Parents:\n    Father: %.31s\n    Mother: %.31s\n",
              father != NULL && father[0] != '\0' ? father : "(none)",
              mother != NULL && mother[0] != '\0' ? mother : "(none)");
    (void)size;
}

/* The block for A New Home's live record `index` (empty for the other games, whose exporter prints
   it from the record itself). */
static void vv1_parents_block(char *out, int size, int index) {
    char father[ROSTER_PARENT_NAME], mother[ROSTER_PARENT_NAME];
    out[0] = '\0';
    if (vv1_parent_names(index, father, mother, (int)ROSTER_PARENT_NAME)) {
        roster_parents_block(out, size, father, mother);
    }
}

static int roster_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count;
    unsigned int i;
    unsigned int previous = 0;
    unsigned int previous_rank = 0;
    unsigned int version;
    (void)context;
    if (length < ROSTER_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    version = *(const unsigned int *)(data + 4);
    if (*(const unsigned int *)data != ROSTER_MAGIC
        || (version != 1u && version != ROSTER_VERSION && !(g_game == 1 && version == ROSTER_VERSION_VV1))
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game
        || *(const unsigned int *)(data + 16) != REC[g_game].snapshot_lo
        || *(const unsigned int *)(data + 20) != REC[g_game].snapshot_hi
        || count > REC[g_game].slots
        || length != ROSTER_HEADER + count * roster_entry_size_of(version)) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + ROSTER_HEADER + i * roster_entry_size_of(version);
        if (version >= ROSTER_VERSION_VV1) {
            const unsigned char *names = e + roster_entry_size_of(version) - ROSTER_PARENTS;
            if (names[ROSTER_PARENT_NAME - 1] != 0 || names[ROSTER_PARENTS - 1] != 0) {
                return 0;             /* each name ends inside its field */
            }
        }
        unsigned int index = (unsigned int)(e[0] | e[1] << 8);
        unsigned int rank = (unsigned int)(e[2] | e[3] << 8);
        if (index >= REC[g_game].slots || rank > index || (i > 0 && index <= previous)
            || (i > 0 && rank <= previous_rank) || e[4] > (version == 1u ? 0 : 5) || e[5] || e[6]
            || e[7]) {
            return 0;
        }
        previous = index;
        previous_rank = rank;
    }
    return 1;
}

static int roster_build_path(int slot, char *out) {
    char name[64];
    /* "Virtual Villagers Fun Patcher Data\Unaccounted Villagers\" -- not
       "Village Roster", which would be confused with Village Statistics' own
       "Village Statistics\Village Roster - Save S.dat". A file an older
       build left loose in the Data folder is moved in on the way, and if it
       will not move the loose file is the one read and written
       (native/shared/data_subfolder.h). */
    if (!vv_save_subfolder(out, VV_DATA_FOLDER,
                           (int)sizeof(
                                       "\\Virtual Villagers 1 Village Roster - Save 0.dat"))) {
        return 0;
    }
    /* "... Villagers at Last Save - Save S.dat": "... Village Roster - Save S.dat" in older builds,
       in its folder or loose.  Nothing is renamed (native/shared/save_layout.h): an older build's
       file is read and written under its own name, and when the roster is there under both names
       the one written last is used -- it is the roster of the save the game will load. */
    {
        char data[MAX_PATH], old_name[MAX_PATH];
        int i;
        lstrcpyA(data, out);
        wsprintfA(name, "Virtual Villagers %d Villagers at Last Save - Save %d.dat", g_game, slot);
        if (!vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_UNACCOUNTED, name, VV_DATA_RESERVE)) {
            return 0;
        }
        for (i = 0; i < 2; ++i) {
            if (_snprintf_s(old_name, MAX_PATH, _TRUNCATE,
                            i == 0 ? "%s\\" VV_DATA_SUB_UNACCOUNTED "\\Virtual Villagers %d Village Roster - Save %d.dat"
                                   : "%s\\Virtual Villagers %d Village Roster - Save %d.dat",
                            data, g_game, slot) > 0
                && lstrlenA(old_name) + VV_DATA_RESERVE <= MAX_PATH
                && vv_layout_pick_file_a(old_name, out)) {
                lstrcpyA(out, old_name);
            }
        }
        return 1;
    }
}

static void roster_when(char *out, const unsigned char *filetime) {
    FILETIME ft;
    SYSTEMTIME st;
    memcpy(&ft, filetime, sizeof ft);
    if (!FileTimeToSystemTime(&ft, &st)) {
        lstrcpyA(out, "(unknown)");
        return;
    }
    wsprintfA(out, "%04d-%02d-%02d %02d:%02d:%02d", st.wYear, st.wMonth, st.wDay,
              st.wHour, st.wMinute, st.wSecond);
}

static const char *roster_sex(int value) {
    if (g_game <= 2) {
        return value == 1 ? "Male" : "Female";
    }
    return value == 0 ? "Male" : "Female";
}

/* "Unaccounted <n>" for a villager last seen in a save (`kept`, rebuilt into
   a scratch record) or found now (`live`). */
/* `parents` is A New Home's "  Parents:" block (roster_parents_block), or "" -- the other games'
   exporter prints it from the record itself. */
static void roster_log(const unsigned char *record, int live, int index, const char *kind,
                       const char *last_seen, const char *now, int mask, const char *parents) {
    char before[512];
    char masked[48];
    char after[160 + 128];
    char extra[96];
    int pregnant = REC[g_game].pregnant != 0u && *(const int *)(record + REC[g_game].pregnant) != 0;
    extra[0] = '\0';
    if (pregnant) {
        int litter = *(const int *)(record + REC[g_game].litter);
        /* The games' own word for the state: every villager screen shows "Nursing"
           (cod_lost.inc); an older build wrote "Pregnant", which the readers still take. */
        wsprintfA(extra, "  Nursing: yes, %d %s\n", litter > 1 ? litter : 1,
                  litter > 1 ? "babies" : "baby");
    }
    if (REC[g_game].heathen != 0u) {
        lstrcatA(extra, record[REC[g_game].heathen] ? "  Faction: Heathen\n" : "  Faction: Believer\n");
    }
    /* A live record's mask the exporter asks for itself; a departed villager's is the one
       the snapshot kept (New Believers' own Heathen mask is read from the copy by the
       exporter). */
    masked[0] = '\0';
    if (!live && mask >= 1 && mask <= 5
        && !(REC[g_game].heathen != 0u && record[REC[g_game].heathen] != 0)) {
        wsprintfA(masked, "  Mask: %s\n", VV_MASK_NAMES[mask]);
    }
    wsprintfA(before, "%s  What: %s\n  Age: %d\n  Sex: %s\n  Health: %d\n%s",
              masked, kind, rec_age(record), roster_sex(*(const int *)(record + REC[g_game].sex)),
              rec_health(record), extra);
    wsprintfA(after, "%s  Record: %d\n  Last seen: %s\n  Found: %s\n", parents != NULL ? parents : "", index,
              last_seen, now);
    COD_COUNT(unaccounted);
    cod_write(LOG_UNACCOUNTED, record, live, before, after, 2);
}

/* The villagers this save holds, as records: present, not a look-alike,
   not one of the temporary records (cod_roster_sites.inc).  New Believers'
   villager being reanimated (+0x1CE1) is still one of the tribe. */
static int roster_member(const unsigned char *record) {
    int index = cod_index_of(record);
    if (!rec_present(record) || index < 0 || cod_temporary(index, record)) {
        return 0;
    }
    return g_game == 5 || !rec_lookalike(record);
}

/* ---- Who is who between two saves (roster_match) ---------------------------- */

/* Likes and dislikes on a villager record, every game: (likes, dislikes,
   dwords each); both lie inside the bytes the roster keeps. */
static const unsigned int PREFS[6][3] = {
    { 0, 0, 0 }, { 0x398u, 0x3A8u, 4u }, { 0x5F0u, 0x6E8u, 62u }, { 0xFB4u, 0xFC0u, 3u },
    { 0x1E60u, 0x1E6Cu, 3u }, { 0x1F5Cu, 0x1F68u, 3u },
};

/* A field of a villager: `p` is a live record, or (kept) a roster entry,
   whose bytes start at the record's snapshot_lo. */
static const unsigned char *id_field(const unsigned char *p, int kept, unsigned int offset) {
    return kept ? p + ROSTER_ENTRY_HEAD + (offset - REC[g_game].snapshot_lo) : p + offset;
}

static int id_int(const unsigned char *p, int kept, unsigned int offset) {
    return *(const int *)id_field(p, kept, offset);
}

/* The name, to its terminator. */
static int id_same_name(const unsigned char *a, int a_kept, const unsigned char *b, int b_kept) {
    const unsigned char *x = id_field(a, a_kept, REC[g_game].name);
    const unsigned char *y = id_field(b, b_kept, REC[g_game].name);
    unsigned int n;
    for (n = 0; n < REC[g_game].name_capacity; ++n) {
        if (x[n] != y[n]) {
            return 0;
        }
        if (x[n] == 0) {
            break;
        }
    }
    return 1;
}

#define ID_NAME 1u
#define ID_SEX 2u
#define ID_LOOKS 4u        /* head and body */
#define ID_PREFS 8u        /* likes and dislikes */
#define ID_FULL (ID_NAME | ID_SEX | ID_LOOKS | ID_PREFS)

static int id_same(const unsigned char *kept, const unsigned char *now, unsigned int what) {
    const struct game_records *r = &REC[g_game];
    if ((what & ID_NAME) && !id_same_name(kept, 1, now, 0)) {
        return 0;
    }
    if ((what & ID_SEX) && id_int(kept, 1, r->sex) != id_int(now, 0, r->sex)) {
        return 0;
    }
    if ((what & ID_LOOKS) && (id_int(kept, 1, r->head) != id_int(now, 0, r->head)
                              || id_int(kept, 1, r->body) != id_int(now, 0, r->body))) {
        return 0;
    }
    if ((what & ID_PREFS) && PREFS[g_game][2] != 0u) {
        unsigned int bytes = 4u * PREFS[g_game][2];
        if (memcmp(id_field(kept, 1, PREFS[g_game][0]), now + PREFS[g_game][0], bytes) != 0
            || memcmp(id_field(kept, 1, PREFS[g_game][1]), now + PREFS[g_game][1], bytes) != 0) {
            return 0;
        }
    }
    return 1;
}

/* Whether live[l] is a villager whose arrival was reported since the last save. */
static unsigned char live_reported[RECORDS_MAX];

/* How the age may have gone on between the two saves. */
enum { AGE_ELAPSED, AGE_ON, AGE_ANY };

static int id_age_ok(int kept_age, int now_age, int mode, int elapsed) {
    int step = now_age - kept_age;
    if (mode == AGE_ANY) {
        return 1;
    }
    if (mode == AGE_ELAPSED && elapsed >= 0) {
        return step == elapsed;
    }
    return step >= 0;
}

/* One pass: each kept villager not yet matched to one now, by `what` and
   the age rule; `unique`: only when exactly one on each side is such,
   otherwise the closest age step to the elapsed time. */
static void roster_match_pass(const unsigned char *const *kept, int nk, unsigned char *records,
                              const int *live, int nl, int *km, int *lm, unsigned int what, int mode,
                              int unique, int elapsed) {
    const struct game_records *r = &REC[g_game];
    int k, l;
    for (k = 0; k < nk; ++k) {
        int best = -1, best_cost = 0, count = 0;
        int kept_age;
        if (km[k] != -1) {
            continue;                 /* matched, or accounted for by a reported departure */
        }
        kept_age = id_int(kept[k], 1, r->age);
        for (l = 0; l < nl; ++l) {
            const unsigned char *now;
            int cost;
            if (lm[l] >= 0) {
                continue;
            }
            now = records + (size_t)live[l] * r->stride;
            if (!id_same(kept[k], now, what) || !id_age_ok(kept_age, rec_age(now), mode, elapsed)) {
                continue;
            }
            ++count;
            cost = rec_age(now) - kept_age - (elapsed >= 0 ? elapsed : 0);
            cost = cost < 0 ? -cost : cost;
            if (live_reported[l]) {
                cost += 0x40000000;   /* a reported arrival only when nobody else is such */
            }
            if (best < 0 || cost < best_cost) {
                best = l;
                best_cost = cost;
            }
        }
        if (best < 0 || (unique && count != 1)) {
            continue;
        }
        if (unique) {
            /* ...and that villager is such for no other kept villager. */
            int others = 0;
            const unsigned char *now = records + (size_t)live[best] * r->stride;
            int j;
            for (j = 0; j < nk; ++j) {
                if (j != k && km[j] == -1 && id_same(kept[j], now, what)
                    && id_age_ok(id_int(kept[j], 1, r->age), rec_age(now), mode, elapsed)) {
                    ++others;
                }
            }
            if (others != 0) {
                continue;
            }
        }
        km[k] = best;
        lm[best] = k;
    }
}

/* The time every villager aged between the two saves: the age step most of
   the villagers matched beyond doubt (the full identity, one on each side)
   share; -1 when none is. */
static int roster_elapsed(const unsigned char *const *kept, int nk, unsigned char *records,
                          const int *live, int nl) {
    const struct game_records *r = &REC[g_game];
    static int steps[RECORDS_MAX];
    int n = 0, k, l, best = -1, best_count = 0;
    for (k = 0; k < nk; ++k) {
        int found = -1, count = 0;
        for (l = 0; l < nl; ++l) {
            if (id_same(kept[k], records + (size_t)live[l] * r->stride, ID_FULL)) {
                found = l;
                ++count;
            }
        }
        if (count == 1) {
            int j, twins = 0;
            for (j = 0; j < nk; ++j) {
                twins += id_same(kept[j], records + (size_t)live[found] * r->stride, ID_FULL);
            }
            if (twins == 1) {
                int step = rec_age(records + (size_t)live[found] * r->stride) - id_int(kept[k], 1, r->age);
                if (step >= 0) {
                    steps[n++] = step;
                }
            }
        }
    }
    for (k = 0; k < n; ++k) {
        int count = 0;
        for (l = 0; l < n; ++l) {
            count += steps[l] == steps[k];
        }
        if (count > best_count) {
            best = steps[k];
            best_count = count;
        }
    }
    return best;
}

/* Every kept villager matched to one now (km[k] = index into live; -1 none;
   -2, set by the caller, accounted for by a reported departure and never
   matched), by identity, one to one (the passes in this file's header).
   Returns how many were matched. */
static int roster_match(const unsigned char *const *kept, int nk, unsigned char *records, const int *live,
                        int nl, int *km, int *lm) {
    int elapsed, k, matched = 0;
    for (k = 0; k < nl; ++k) {
        lm[k] = -1;
    }
    elapsed = roster_elapsed(kept, nk, records, live, nl);
    roster_match_pass(kept, nk, records, live, nl, km, lm, ID_FULL, AGE_ELAPSED, 0, elapsed);
    roster_match_pass(kept, nk, records, live, nl, km, lm, ID_NAME | ID_SEX | ID_LOOKS, AGE_ON, 0, elapsed);
    roster_match_pass(kept, nk, records, live, nl, km, lm, ID_NAME | ID_SEX | ID_PREFS, AGE_ON, 1, elapsed);
    roster_match_pass(kept, nk, records, live, nl, km, lm, ID_SEX | ID_LOOKS | ID_PREFS, AGE_ON, 1, elapsed);
    roster_match_pass(kept, nk, records, live, nl, km, lm, ID_FULL, AGE_ANY, 1, elapsed);
    for (k = 0; k < nk; ++k) {
        matched += km[k] >= 0;
    }
    return matched;
}

/* A kept villager no one now is: a departure reported since the last save,
   of the same name, sex, head and body, at an age at least the kept one,
   accounts for them (one departure, one villager). */
static int roster_gone_accounts(const unsigned char *kept, int slot) {
    const struct game_records *r = &REC[g_game];
    const unsigned char *name = id_field(kept, 1, r->name);
    int i;
    for (i = 0; i < RECORDS_MAX; ++i) {
        unsigned int n;
        int same = 1;
        if (gone[i].tag == REPORT_NONE || !report_counts(gone[i].tag, slot) || gone_spent[i]
            || gone[i].age < id_int(kept, 1, r->age) || gone[i].sex != id_int(kept, 1, r->sex)
            || gone[i].head != id_int(kept, 1, r->head) || gone[i].body != id_int(kept, 1, r->body)) {
            continue;
        }
        for (n = 0; n < GONE_NAME && n < r->name_capacity; ++n) {
            if ((unsigned char)gone[i].name[n] != name[n]) {
                same = 0;
                break;
            }
            if (name[n] == 0) {
                break;
            }
        }
        if (same) {
            gone_spent[i] = 1;        /* spent on this villager (at this reconciliation) */
            return 1;
        }
    }
    return 0;
}

static void roster_reconcile(int slot) {
    unsigned char *records = cod_records();
    const struct game_records *r = &REC[g_game];
    unsigned int size = roster_entry_size();
    unsigned int read_version = 0;
    unsigned int span = r->snapshot_hi - r->snapshot_lo;
    DWORD length = 0;
    int result;
    int have_previous;
    unsigned int kept_count = 0;
    unsigned int count = 0;
    unsigned int rank = 0;
    unsigned int i;
    char now[32];
    unsigned char stamp[8];
    SYSTEMTIME st;
    FILETIME ft;
    const unsigned char *kept[RECORDS_MAX];
    static int live[RECORDS_MAX], kept_match[RECORDS_MAX], live_match[RECORDS_MAX];
    int live_count = 0;
    int matched = 0;

    if (records == NULL || slot <= 0) {
        return;
    }
    if (roster_buffer == NULL) {
        roster_buffer = (unsigned char *)VirtualAlloc(NULL, roster_max_bytes() * 2u,
                                                      MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
        roster_scratch = (unsigned char *)VirtualAlloc(NULL, r->stride, MEM_COMMIT | MEM_RESERVE,
                                                       PAGE_READWRITE);
        if (roster_buffer == NULL || roster_scratch == NULL) {
            return;
        }
    }
    if (slot != roster.slot) {
        roster.slot = slot;
        roster.path[0] = '\0';
        vv_sidecar_gate_bind(&roster.gate, 0x100 + g_game * 16 + slot);
    }
    if (roster.path[0] == '\0' && !roster_build_path(slot, roster.path)) {
        return;
    }
    GetLocalTime(&st);
    SystemTimeToFileTime(&st, &ft);
    memcpy(stamp, &ft, sizeof stamp);
    roster_when(now, stamp);
    result = vv_sidecar_load(&roster.gate, roster.path, roster_buffer, roster_max_bytes(),
                             &length, roster_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;                       /* reconcile at a later save */
    }
    have_previous = result == VV_SIDECAR_LOAD_VALID;
    memset((void *)kept, 0, sizeof kept);
    memset(gone_spent, 0, sizeof gone_spent);
    if (have_previous) {
        unsigned int n = *(const unsigned int *)(roster_buffer + 12);
        int reported = 0;
        /* The kept file's own entry size (version 3 keeps A New Home's parents). */
        read_version = *(const unsigned int *)(roster_buffer + 4);
        size = roster_entry_size_of(read_version);
        kept_count = n;
        for (i = 0; i < n; ++i) {
            kept[i] = roster_buffer + ROSTER_HEADER + i * size;
        }
        /* The villagers now.  One whose arrival was reported (the game's creator made them, or the
           Births log recorded their birth) is accounted for and never written as arriving; they are
           matched to a kept villager only when no villager unreported is such (live_reported). */
        for (i = 0; i < r->slots; ++i) {
            if (roster_member(records + (size_t)i * r->stride)) {
                live_reported[live_count] = (unsigned char)report_counts(arrived[i], slot);
                live[live_count++] = (int)i;
            }
        }
        /* A departure the game reported since (a burial, a body's removal, a disappearance: its
           Death or Disappeared record) accounts for the kept villager it names first: whoever is
           in the village now is never taken for them -- one written back alive unreported, or a
           newcomer in their record, has arrived unaccounted for. */
        for (i = 0; i < n; ++i) {
            kept_match[i] = roster_gone_accounts(kept[i], slot) ? -2 : -1;
        }
        matched = roster_match(kept, (int)n, records, live, live_count, kept_match, live_match);
        for (i = 0; i < r->slots; ++i) {
            if (report_counts(departed[i], slot) || report_counts(arrived[i], slot)) {
                ++reported;
            }
        }
        if (n > 0 && matched == 0 && reported == 0) {
            have_previous = 0;        /* another village's roster */
        }
    }
    /* The arrivals made for this slot get their Arrived records -- unless
       there is no village saved before to arrive in: a new village's
       founders (cod_arrivals.inc).  A roster with nobody in it is no
       village to arrive in either: The Tree of Life and New Believers save
       a new village once before its founders are chosen (seen live: an
       empty roster at the creation save), and the founders' first save then
       found that roster and wrote none of them. */
    arrival_save(slot, have_previous && kept_count > 0);
    if (have_previous) {
        signed char early_tag = REPORT_EARLY;
        /* More departures than could be kept: who left is not known for
           sure, so nobody is written as having left (unsure, never guessed). */
        int unsure = gone_overflow[slot + 1] || gone_overflow[early_tag + 1];
        for (i = 0; i < kept_count; ++i) {
            const unsigned char *e = kept[i];
            char last_seen[32];
            char parents[128];
            if (kept_match[i] != -1) {
                continue;             /* still here, in whatever record, or a reported departure */
            }
            memset(roster_scratch, 0, r->stride);
            memcpy(roster_scratch + r->snapshot_lo, e + ROSTER_ENTRY_HEAD, span);
            /* A departure reported since (a burial, a body's removal, a
               disappearance: its Death or Disappeared record), or a grave
               just recorded from (a burial no hook saw: the load-time
               catch-up; cod_backfill.inc). */
            if (backfill_accounts_for(roster_scratch) || unsure) {
                continue;
            }
            roster_when(last_seen, e + 8);
            parents[0] = '\0';
            if (read_version >= ROSTER_VERSION_VV1) {
                /* A New Home: the parents the snapshot kept beside the record. */
                const char *names = (const char *)e + size - ROSTER_PARENTS;
                roster_parents_block(parents, (int)sizeof parents, names, names + ROSTER_PARENT_NAME);
            }
            roster_log(roster_scratch, 0, (int)(e[0] | e[1] << 8),
                       "Left the village with no Death or Disappeared record", last_seen, now, e[4], parents);
        }
        for (i = 0; i < (unsigned int)live_count; ++i) {
            char parents[128];
            unsigned char *now_record = records + (size_t)live[i] * r->stride;
            if (live_match[i] >= 0 || live_reported[i]) {
                continue;         /* the same villager as at the last save, or an arrival reported */
            }
            vv1_parents_block(parents, (int)sizeof parents, live[i]);
            roster_log(now_record, 1, live[i],
                       "Arrived with no Birth record or known arrival", "(never before)", now, 0, parents);
        }
    }
    /* The roster for the next save: this one, in record order, each with
       its rank among every occupied record (what the load will make its
       record). */
    for (i = 0; i < r->slots; ++i) {
        const unsigned char *record = records + (size_t)i * r->stride;
        unsigned char *e;
        if (!rec_present(record)) {
            continue;
        }
        ++rank;
        if (!roster_member(record)) {
            continue;
        }
        e = roster_buffer + roster_max_bytes() + ROSTER_HEADER + count * roster_entry_size();
        memset(e, 0, roster_entry_size());
        e[0] = (unsigned char)(i & 0xFF);
        e[1] = (unsigned char)(i >> 8);
        e[2] = (unsigned char)((rank - 1) & 0xFF);
        e[3] = (unsigned char)((rank - 1) >> 8);
        e[4] = (unsigned char)vv_mask_value(g_game, record);
        memcpy(e + 8, stamp, sizeof stamp);
        memcpy(e + ROSTER_ENTRY_HEAD, record + r->snapshot_lo, span);
        if (roster_write_version() >= ROSTER_VERSION_VV1) {
            /* A New Home: the villager's own parents, for a record of them should they leave unseen. */
            char *names = (char *)e + ROSTER_ENTRY_HEAD + span;
            (void)vv1_parent_names((int)i, names, names + ROSTER_PARENT_NAME, (int)ROSTER_PARENT_NAME);
        }
        ++count;
    }
    {
        unsigned char *head = roster_buffer + roster_max_bytes();
        const void *parts[1];
        DWORD sizes[1];
        memset(head, 0, ROSTER_HEADER);
        ((unsigned int *)head)[0] = ROSTER_MAGIC;
        ((unsigned int *)head)[1] = roster_write_version();
        ((unsigned int *)head)[2] = (unsigned int)g_game;
        ((unsigned int *)head)[3] = count;
        ((unsigned int *)head)[4] = r->snapshot_lo;
        ((unsigned int *)head)[5] = r->snapshot_hi;
        parts[0] = head;
        sizes[0] = ROSTER_HEADER + count * roster_entry_size();
        if (vv_sidecar_publish(&roster.gate, roster.path, parts, sizes, 1)) {
            for (i = 0; i < r->slots; ++i) {
                if (report_counts(departed[i], slot)) {
                    departed[i] = REPORT_NONE;
                }
                if (report_counts(arrived[i], slot)) {
                    arrived[i] = REPORT_NONE;
                }
            }
            for (i = 0; i < RECORDS_MAX; ++i) {
                if (gone[i].tag != REPORT_NONE && report_counts(gone[i].tag, slot)) {
                    gone[i].tag = REPORT_NONE;
                }
            }
            gone_overflow[slot + 1] = 0;
            gone_overflow[0] = 0;
        }
    }
}

static void roster_reset(int slot) {
    int i;
    if (slot == roster.slot) {
        vv_sidecar_gate_bind(&roster.gate, -1);
        roster.slot = 0;
        roster.path[0] = '\0';
    }
    for (i = 0; i < RECORDS_MAX; ++i) {
        if (departed[i] == slot) {
            departed[i] = REPORT_NONE;
        }
        if (arrived[i] == slot) {
            arrived[i] = REPORT_NONE;
        }
        if (gone[i].tag == slot) {
            gone[i].tag = REPORT_NONE;
        }
    }
    if (slot >= 1 && slot <= 5) {
        gone_overflow[slot + 1] = 0;
    }
}

#include "cod_roster_sites.inc"

/* A successful save of `slot` from `save_buffer`: name the village for the
   logs first, so this save's Unaccounted records go under its header, then
   reconcile -- only once installed: with the save hook merely armed
   (VvfpCauseArmSave) nothing has been watching departures and arrivals, so
   a reconciliation would report everyone who changed. */
static void cod_save_done(int slot, const void *save_buffer) {
    cod_publish_village(save_buffer, slot);
    if (install_state == 1) {
        /* A New Home and The Lost Children: the causes of the bodies this
           save keeps go to this slot's graves file now, whatever slot the
           per-frame tick had (cod_vv12.inc). */
        if (g_game <= 2) {
            vv12_saved(slot);
        } else {
            /* The later three: the bodies the Custom Island Event's "Dies"
               left, which this save keeps, go to this slot's file now
               (cod_cie.inc). */
            cie_saved(slot);
        }
        saved_slot = slot;
        /* Every grave in the Deaths log first, so the reconciliation knows
           the villagers whose graves were recorded from now. */
        backfill_at_save(slot, save_buffer);
        /* ...and every villager who arrived before the Arrived record
           existed, after Repair (cod_arrivals.inc). */
        arrival_backfill_at_save(slot, save_buffer);
        /* ...and every villager born there before the Births log existed
           (The Lost Children on), after Repair (cod_arrivals.inc). */
        births_backfill_at_save(slot, save_buffer);
        roster_reconcile(slot);
    }
}

/* Right after the game's own save call: al = 1 when it saved, edi = the
   slot, and esi the block the call saved from -- the same `lea eax,
   [esi + 8]` buffer the statistics hook reads the village name from. The
   village is named for the logs first, so this save's Unaccounted records
   go under its header (cod_publish_village). */
static void roster_saved(int site, const unsigned int *regs) {
    int slot = (int)regs[R_EDI];
    (void)site;
    if ((regs[R_EAX] & 0xFFu) != 0 && slot >= 1 && slot <= 5) {
        cod_save_done(slot, (const void *)(uintptr_t)(regs[R_ESI] + 8u));
    }
}

/* A New Home's save epilogue (0x41BF68) is the Origins base's own hook, so
   there the file writer every save goes through (0x403160, (buffer, size,
   slot), `ret 0xc`) is hooked on its success path's epilogue instead,
   0x40322A `pop edi; pop esi; mov al, bl; pop ebx`: bl = written, and the
   village is the write of the village state's 0xABDC bytes (the player
   profile is 0xC0).  Telling it by its size, not by its caller, keeps it
   right when the Village Statistics row routes the save call through its
   own DLL, which calls this same writer. */
static void vv1_written(int site, const unsigned int *regs) {
    int slot = (int)reg_stack(regs, 0x218);
    (void)site;
    if ((regs[R_EBX] & 0xFFu) != 0 && reg_stack(regs, 0x214) == 0xABDCu && slot >= 1 && slot <= 5) {
        /* The writer's first argument is the buffer it wrote. */
        cod_save_done(slot, (const void *)(uintptr_t)reg_stack(regs, 0x210));
    }
}

static void roster_save_site(void) {
    static const unsigned int SAVE_RETURN[6] = {
        0, 0, 0x424BF8u, 0x427D71u, 0x41F13Fu, 0x4245FFu
    };
    if (g_game == 1) {
        cod_add(0x40322Au, "5F5E" "8AC3" "5B", vv1_written);
    } else {
        cod_add(SAVE_RETURN[g_game], "5F5E" "C20400", roster_saved);
    }
}

/* A birth the Births and Conceptions log has recorded, from that log's own
   companion ("VVFP Parentage Export.dll"), which may call this before this
   companion is installed. */
__declspec(dllexport) void __stdcall VvfpCauseNoteArrival(int game, const void *record) {
    if (game < 1 || game > 5 || install_state == -1 || (g_game != 0 && game != g_game)) {
        return;
    }
    g_game = game;
    roster_arrived(cod_index_of((const unsigned char *)record));
    arrival_noted_birth(cod_index_of((const unsigned char *)record));   /* a birth, not an arrival */
}
