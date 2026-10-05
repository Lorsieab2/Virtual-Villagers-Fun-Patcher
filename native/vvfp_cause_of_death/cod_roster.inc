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

   WHICH RECORD IS WHOSE AFTER A LOAD.  Every game saves only its occupied
   records, packed in record order, and its load unpacks them into records
   0, 1, 2, ... (seen live in A New Home: a villager in record 15 at the
   save, with record 14 freed by a burial, is in record 14 after the load).
   So each roster entry keeps both its record and its rank among the
   occupied records, and the reconciliation reads the kept roster by rank
   when the village has been loaded since (the usual case: the games save
   on quitting) and by record when it has not.  Which one is decided by the
   data: the reading under which more kept villagers are still in their
   place under the same name (a tie reads by rank).  When nothing was freed
   before the save the two readings are the same.

   A roster none of whose villagers is still in its place under the same
   name, with nothing reported for that slot since, is not this village's
   (its save was replaced outside the game): a new roster is started and
   nothing is logged against the old one.

   Every departure is reported where the game frees the record (a burial,
   a body's removal, a disappearance), never at a death, so a body that is
   revived keeps its record and reports nothing.  A record whose departure
   was reported since the last save holds somebody else now, if anybody:
   never the villager kept there, whatever the name and sex, so a newcomer
   in it is accounted for only by an arrival reported after that departure
   (a departure cancels any arrival reported into the record before it).

   Otherwise a villager in the same record at both saves is the same
   villager unless both the name and the sex changed with neither a
   departure nor an arrival reported -- then one left and another arrived
   unseen.

   KEPT.  <save folder>\Virtual Villagers Fun Patcher Data\Unaccounted Villagers\
              Virtual Villagers N Village Roster - Save S.dat
   (format below), written atomically after each reconciliation; Start Over
   deletes it with the village, and the next save starts a new one. */

#define ROSTER_MAGIC 0x31524356u          /* 'VCR1' */
#define ROSTER_VERSION 1u
#define ROSTER_HEADER 32u
#define ROSTER_ENTRY_HEAD 16u

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
static void roster_departed(int index, const unsigned char *record) {
    (void)record;
    if (index >= 0 && index < RECORDS_MAX) {
        departed[index] = report_tag();
        arrived[index] = REPORT_NONE;
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
       u32 magic 'VCR1', u32 version 1, u32 game, u32 count,
       u32 lo, u32 hi (the record bytes kept, [lo, hi)), u32 0, u32 0,
       count x { u16 record index, u16 rank (the record's place among all
                 the occupied records the save packs, look-alikes and
                 temporary records included), u32 0, u64 when saved
                 (FILETIME, local time), (hi - lo) bytes of the record at
                 lo }
   Entries are in record order, one per occupied record that is a villager
   (living or a body; never a look-alike); both index and rank increase. */
static unsigned int roster_entry_size(void) {
    return ROSTER_ENTRY_HEAD + REC[g_game].snapshot_hi - REC[g_game].snapshot_lo;
}

static unsigned int roster_max_bytes(void) {
    return ROSTER_HEADER + REC[g_game].slots * roster_entry_size();
}

static int roster_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count;
    unsigned int i;
    unsigned int previous = 0;
    unsigned int previous_rank = 0;
    (void)context;
    if (length < ROSTER_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    if (*(const unsigned int *)data != ROSTER_MAGIC
        || *(const unsigned int *)(data + 4) != ROSTER_VERSION
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game
        || *(const unsigned int *)(data + 16) != REC[g_game].snapshot_lo
        || *(const unsigned int *)(data + 20) != REC[g_game].snapshot_hi
        || count > REC[g_game].slots
        || length != ROSTER_HEADER + count * roster_entry_size()) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + ROSTER_HEADER + i * roster_entry_size();
        unsigned int index = (unsigned int)(e[0] | e[1] << 8);
        unsigned int rank = (unsigned int)(e[2] | e[3] << 8);
        if (index >= REC[g_game].slots || rank > index || (i > 0 && index <= previous)
            || (i > 0 && rank <= previous_rank) || e[4] || e[5] || e[6] || e[7]) {
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
    wsprintfA(name, "Virtual Villagers %d Village Roster - Save %d.dat", g_game, slot);
    return vv_data_file_path(out, MAX_PATH, VV_DATA_SUB_UNACCOUNTED, name, VV_DATA_RESERVE) != 0;
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
static void roster_log(const unsigned char *record, int live, int index, const char *kind,
                       const char *last_seen, const char *now) {
    char before[512];
    char after[160];
    char extra[96];
    int pregnant = REC[g_game].pregnant != 0u && *(const int *)(record + REC[g_game].pregnant) != 0;
    extra[0] = '\0';
    if (pregnant) {
        int litter = *(const int *)(record + REC[g_game].litter);
        wsprintfA(extra, "  Pregnant: yes, %d %s\n", litter > 1 ? litter : 1,
                  litter > 1 ? "babies" : "baby");
    }
    if (REC[g_game].heathen != 0u) {
        lstrcatA(extra, record[REC[g_game].heathen] ? "  Faction: Heathen\n" : "  Faction: Believer\n");
    }
    wsprintfA(before, "  What: %s\n  Age: %d\n  Sex: %s\n  Health: %d\n%s",
              kind, rec_age(record), roster_sex(*(const int *)(record + REC[g_game].sex)),
              rec_health(record), extra);
    wsprintfA(after, "  Record: %d\n  Last seen: %s\n  Found: %s\n", index, last_seen, now);
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

/* The same name in the same place. */
static int roster_same_name(const unsigned char *kept, const unsigned char *now) {
    const struct game_records *r = &REC[g_game];
    return memcmp(kept + r->name, now + r->name, r->name_capacity) == 0;
}

/* Same villager in the same place: the name or the sex still matches (a
   name can be changed by the player; the sex never is). */
static int roster_same(const unsigned char *kept, const unsigned char *now) {
    const struct game_records *r = &REC[g_game];
    return memcmp(kept + r->name, now + r->name, r->name_capacity) == 0
        || *(const int *)(kept + r->sex) == *(const int *)(now + r->sex);
}

static void roster_reconcile(int slot) {
    unsigned char *records = cod_records();
    const struct game_records *r = &REC[g_game];
    unsigned int size = roster_entry_size();
    unsigned int span = r->snapshot_hi - r->snapshot_lo;
    DWORD length = 0;
    int result;
    int have_previous;
    unsigned int count = 0;
    unsigned int rank = 0;
    unsigned int i;
    char now[32];
    unsigned char stamp[8];
    SYSTEMTIME st;
    FILETIME ft;
    const unsigned char *kept[RECORDS_MAX];

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
    if (have_previous) {
        unsigned int n = *(const unsigned int *)(roster_buffer + 12);
        int by_record = 0;
        int by_rank = 0;
        int reported = 0;
        int read_by_rank;
        for (i = 0; i < n; ++i) {
            const unsigned char *e = roster_buffer + ROSTER_HEADER + i * size;
            unsigned int index = (unsigned int)(e[0] | e[1] << 8);
            unsigned int place = (unsigned int)(e[2] | e[3] << 8);
            memset(roster_scratch, 0, r->stride);
            memcpy(roster_scratch + r->snapshot_lo, e + ROSTER_ENTRY_HEAD, span);
            if (roster_member(records + (size_t)index * r->stride)
                && roster_same_name(roster_scratch, records + (size_t)index * r->stride)) {
                ++by_record;
            }
            if (roster_member(records + (size_t)place * r->stride)
                && roster_same_name(roster_scratch, records + (size_t)place * r->stride)) {
                ++by_rank;
            }
        }
        read_by_rank = by_rank >= by_record;
        for (i = 0; i < n; ++i) {
            const unsigned char *e = roster_buffer + ROSTER_HEADER + i * size;
            kept[read_by_rank ? (e[2] | e[3] << 8) : (e[0] | e[1] << 8)] = e;
        }
        for (i = 0; i < r->slots; ++i) {
            if (report_counts(departed[i], slot) || report_counts(arrived[i], slot)) {
                ++reported;
            }
        }
        if (n > 0 && (read_by_rank ? by_rank : by_record) == 0 && reported == 0) {
            have_previous = 0;        /* another village's roster */
        }
    }
    if (have_previous) {
        for (i = 0; i < r->slots; ++i) {
            unsigned char *now_record = records + (size_t)i * r->stride;
            int present = roster_member(now_record);
            int same = 0;
            char last_seen[32];
            if (kept[i] != NULL) {
                memset(roster_scratch, 0, r->stride);
                memcpy(roster_scratch + r->snapshot_lo, kept[i] + ROSTER_ENTRY_HEAD, span);
                roster_when(last_seen, kept[i] + 8);
                /* A recorded departure freed this record: whoever is in it
                   now is somebody else, whatever their name or sex. */
                same = present && !report_counts(departed[i], slot)
                    && roster_same(roster_scratch, now_record);
                /* ...unless their grave was just recorded from (a burial no
                   hook saw: the load-time catch-up; cod_backfill.inc). */
                if ((!present || !same) && !report_counts(departed[i], slot)
                    && !backfill_accounts_for(roster_scratch)) {
                    roster_log(roster_scratch, 0, (int)i,
                               "Left the village with no Death or Disappeared record", last_seen, now);
                }
            }
            if (present && (kept[i] == NULL || !same) && !report_counts(arrived[i], slot)) {
                roster_log(now_record, 1, (int)i,
                           "Arrived with no Birth record or known arrival", "(never before)", now);
            }
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
        e = roster_buffer + roster_max_bytes() + ROSTER_HEADER + count * size;
        memset(e, 0, ROSTER_ENTRY_HEAD);
        e[0] = (unsigned char)(i & 0xFF);
        e[1] = (unsigned char)(i >> 8);
        e[2] = (unsigned char)((rank - 1) & 0xFF);
        e[3] = (unsigned char)((rank - 1) >> 8);
        memcpy(e + 8, stamp, sizeof stamp);
        memcpy(e + ROSTER_ENTRY_HEAD, record + r->snapshot_lo, span);
        ++count;
    }
    {
        unsigned char *head = roster_buffer + roster_max_bytes();
        const void *parts[1];
        DWORD sizes[1];
        memset(head, 0, ROSTER_HEADER);
        ((unsigned int *)head)[0] = ROSTER_MAGIC;
        ((unsigned int *)head)[1] = ROSTER_VERSION;
        ((unsigned int *)head)[2] = (unsigned int)g_game;
        ((unsigned int *)head)[3] = count;
        ((unsigned int *)head)[4] = r->snapshot_lo;
        ((unsigned int *)head)[5] = r->snapshot_hi;
        parts[0] = head;
        sizes[0] = ROSTER_HEADER + count * size;
        if (vv_sidecar_publish(&roster.gate, roster.path, parts, sizes, 1)) {
            for (i = 0; i < r->slots; ++i) {
                if (report_counts(departed[i], slot)) {
                    departed[i] = REPORT_NONE;
                }
                if (report_counts(arrived[i], slot)) {
                    arrived[i] = REPORT_NONE;
                }
            }
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
        /* Every grave in the Deaths log first, so the reconciliation knows
           the villagers whose graves were recorded from now. */
        backfill_at_save(slot, save_buffer);
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
}
