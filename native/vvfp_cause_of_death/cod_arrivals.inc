/* "Arrived" records: every villager who joins the village without being born
   into it, in the Births and Conceptions log, every game.  Included by
   vvfp_cause_of_death.c.  native/shared/arrival_backfill.h has the record's
   format and the owner's words.

   WHO ARRIVES.  Every villager the game's own creators make is reported here
   (roster_created, cod_roster_sites.inc): a birth, an island event's
   newcomer, the Barrel O' Babies, the Custom Island Event's new villagers.
   A birth is not an arrival: the Births and Conceptions log records it and
   says so (VvfpCauseNoteArrival), from the birth hook that runs right after
   the creator, in the same frame.  A New Home's Birth records come from Show
   Parents in Details Screen, so there a birth is also told by the creator's
   own return address -- one of the four child-creation calls of the delivery
   (0x42EF5F, 0x42EFD0, 0x42F021, 0x42F06D) -- with that row off as well.
   Everything else the creators make is an arrival.

   New Believers: a Heathen is never a villager (the owner), so a Heathen
   made by the creator is not an arrival.  A Heathen converted to a believer
   IS one from that moment, and the faction byte (+0x1CEC) is cleared in place
   (the setter 0x466880): the tick sees a record it saw as a Heathen become a
   believer, and that is an arrival, "Converted from the Heathens".

   HOW THEY CAME.  "Custom Island Event" when the Story / Cheat Upgrades
   companion says its event made them (VvfpCauseArrivedBy); "Converted from
   the Heathens"; otherwise "unknown" -- the stock events' newcomers are made
   by the same creators from many places, and nothing here names the event.

   WHEN.  The arrival is decided at the first tick after the creator (the
   birth note has come by then, the event has written the villager's name,
   age and looks), and its age then is the age at arrival.  The record is
   written at the next save of the slot it was made in, where the logs are
   named -- and only when that save's roster reconciliation recognises the
   village saved before (have_previous): a new village's founders, made with
   no saved roster (a new slot, Start Over), are not arrivals.  A villager
   who arrived and leaves (a burial, a disappearance) before that save gets
   the record at the departure, while the record still holds them.  Either
   way the arrival is reported to the reconciliation, so the Unaccounted
   Villagers log never lists them.

   THE BACKFILL.  VvfpCauseScanArrivals / VvfpCauseRepairArrivals, for the
   first-load prompt, like the graves': the village's villagers (believers,
   and in The Lost Children to New Believers only those with no parents on
   their record -- a villager with parents was born) are handed to
   RecordArrivalsMissingFromLog, which counts those with no Birth or Arrived
   record; after Repair, at the next save, each gets an Arrived record marked
   "Recorded afterwards", and once all are on disk the slot's marker says it
   is done, for good. */

#define ARRIVAL_NONE 0
#define ARRIVAL_MADE 1          /* made by a creator, not yet decided */
#define ARRIVAL_PENDING 2       /* an arrival, its record written at the next save */

#define ARRIVAL_HOW 48

static struct {
    signed char tag;            /* report_tag() when made: the slot it counts for */
    unsigned char state;
    unsigned char born;         /* a birth (VvfpCauseNoteArrival, or A New Home's creator caller) */
    int age;                    /* at arrival */
    char how[ARRIVAL_HOW];
} arrivals[RECORDS_MAX];

/* New Believers: -1 unknown, 0 a believer, 1 a Heathen -- as the tick last
   saw the record. */
static signed char faction_seen[RECORDS_MAX];
static int faction_ready;

/* The player's answer to the backfill, per slot, this session. */
static signed char arrivals_repair[6];

/* The Births and Conceptions log recorded a birth into `index`. */
static void arrival_noted_birth(int index) {
    if (index >= 0 && index < RECORDS_MAX && arrivals[index].state == ARRIVAL_MADE) {
        arrivals[index].born = 1;
    }
}

/* A New Home's four child-creation calls: the creator's return address. */
static int vv1_birth_return(unsigned int ret) {
    return ret == 0x42EF64u || ret == 0x42EFD5u || ret == 0x42F026u || ret == 0x42F072u;
}

/* A creator made `index`: `creator_return` is its return address where the
   hook knows it (A New Home), else 0. */
static void arrival_created(int index, unsigned int creator_return) {
    if (index < 0 || index >= RECORDS_MAX) {
        return;
    }
    arrivals[index].tag = report_tag();
    arrivals[index].state = ARRIVAL_MADE;
    arrivals[index].born = (unsigned char)(g_game == 1 && vv1_birth_return(creator_return));
    arrivals[index].age = 0;
    arrivals[index].how[0] = '\0';
    faction_seen[index] = -1;
}

static int arrival_heathen(const unsigned char *record) {
    return REC[g_game].heathen != 0u && record[REC[g_game].heathen] != 0;
}

/* Decide a made record: a birth, a Heathen or gone -> nothing; otherwise an
   arrival, aged as it is now. */
static void arrival_decide(int index) {
    const unsigned char *record = cod_record(index);
    if (arrivals[index].state != ARRIVAL_MADE) {
        return;
    }
    if (arrivals[index].born || record == NULL || !roster_member(record) || arrival_heathen(record)) {
        arrivals[index].state = ARRIVAL_NONE;
        return;
    }
    arrivals[index].state = ARRIVAL_PENDING;
    arrivals[index].age = rec_age(record);
    if (arrivals[index].how[0] == '\0') {
        lstrcpynA(arrivals[index].how, "unknown", ARRIVAL_HOW);
    }
}

/* The Arrived record of `index`, from its live record. */
static void arrival_write(int index) {
    const unsigned char *record = cod_record(index);
    char before[VV_ARRIVAL_BEFORE];
    char after[96];
    if (record == NULL) {
        return;
    }
    wsprintfA(before, "  Age at arrival: %d\n  Sex: %s\n", arrivals[index].age,
              roster_sex(*(const int *)(record + REC[g_game].sex)));
    wsprintfA(after, "  How: %s\n", arrivals[index].how);
    COD_COUNT(arrivals);
    cod_write(LOG_ARRIVED, record, 1, before, after, 2);
}

/* Every frame: decide what was made, and see New Believers' conversions. */
static void arrival_tick(void) {
    unsigned char *records = cod_records();
    int i;
    for (i = 0; i < RECORDS_MAX && (unsigned int)i < REC[g_game].slots; ++i) {
        arrival_decide(i);
    }
    if (REC[g_game].heathen == 0u || records == NULL) {
        return;
    }
    if (!faction_ready) {
        memset(faction_seen, -1, sizeof faction_seen);
        faction_ready = 1;
    }
    for (i = 0; i < RECORDS_MAX && (unsigned int)i < REC[g_game].slots; ++i) {
        const unsigned char *record = records + (size_t)i * REC[g_game].stride;
        int heathen;
        if (!roster_member(record)) {
            faction_seen[i] = -1;
            continue;
        }
        heathen = arrival_heathen(record);
        if (faction_seen[i] == 1 && !heathen && arrivals[i].state == ARRIVAL_NONE) {
            arrivals[i].tag = report_tag();
            arrivals[i].state = ARRIVAL_PENDING;
            arrivals[i].born = 0;
            arrivals[i].age = rec_age(record);
            lstrcpynA(arrivals[i].how, "Converted from the Heathens", ARRIVAL_HOW);
            roster_arrived(i);
        }
        faction_seen[i] = (signed char)heathen;
    }
}

/* `index` leaves the village: an arrival not yet written is written now,
   while the record still holds them. */
static void arrival_departed(int index) {
    if (index < 0 || index >= RECORDS_MAX) {
        return;
    }
    arrival_decide(index);
    if (arrivals[index].state == ARRIVAL_PENDING && cod_slot() > 0
        && report_counts(arrivals[index].tag, cod_slot())) {
        arrival_write(index);
    }
    arrivals[index].state = ARRIVAL_NONE;
    faction_seen[index] = -1;
}

/* At a save of `slot`, before the reconciliation lists anyone: the
   arrivals made for it are written when the village is the one saved before
   (`same_village`); a new village's founders are not. */
static void arrival_save(int slot, int same_village) {
    int i;
    for (i = 0; i < RECORDS_MAX && (unsigned int)i < REC[g_game].slots; ++i) {
        if (arrivals[i].state == ARRIVAL_NONE || !report_counts(arrivals[i].tag, slot)) {
            continue;
        }
        arrival_decide(i);
        if (arrivals[i].state == ARRIVAL_PENDING && same_village) {
            arrival_write(i);
        }
        arrivals[i].state = ARRIVAL_NONE;
    }
}

static void arrival_reset(int slot) {
    int i;
    for (i = 0; i < RECORDS_MAX; ++i) {
        if (arrivals[i].tag == slot) {
            arrivals[i].state = ARRIVAL_NONE;
        }
    }
    memset(faction_seen, -1, sizeof faction_seen);
    if (slot >= 1 && slot <= 5) {
        arrivals_repair[slot] = 0;
    }
}

/* ---- The backfill ---------------------------------------------------------- */

static vv_arrival_fact arrival_facts[RECORDS_MAX];
static int arrival_fact_index[RECORDS_MAX];

/* Whether this install writes Birth records for every birth: in A New Home
   only with Show Parents in Details Screen ("VVFP VV1 Parentage.dll"). */
static int births_are_logged(void) {
    char path[MAX_PATH];
    char *slash;
    DWORD n;
    if (g_game != 1) {
        return 1;
    }
#ifdef VVFP_TEST
    if (test_vv1_births != 0) {
        return test_vv1_births > 0;
    }
#endif
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    slash = n != 0 && n < MAX_PATH ? strrchr(path, '\\') : NULL;
    if (slash == NULL || (size_t)(slash + 1 - path) + sizeof("VVFP VV1 Parentage.dll") > sizeof(path)) {
        return 0;
    }
    lstrcpyA(slash + 1, "VVFP VV1 Parentage.dll");
    return GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES;
}

/* The village's villagers who could have arrived: members, believers, and
   (The Lost Children on) with no parents on their record. */
static int arrival_gather(void) {
    static const unsigned int PARENTS[6][2] = {
        { 0, 0 }, { 0, 0 }, { 0x57Du, 0x596u }, { 0xDF8u, 0xE11u },
        { 0x1BC0u, 0x1BD9u }, { 0x1BC0u, 0x1BD9u },
    };
    unsigned char *records = cod_records();
    int n = 0;
    unsigned int i;
    if (records == NULL) {
        return -1;
    }
    for (i = 0; i < REC[g_game].slots && i < RECORDS_MAX; ++i) {
        const unsigned char *record = records + (size_t)i * REC[g_game].stride;
        vv_arrival_fact *f;
        if (!roster_member(record) || arrival_heathen(record)) {
            continue;
        }
        if (PARENTS[g_game][0] != 0u
            && (record[PARENTS[g_game][0]] != 0 || record[PARENTS[g_game][1]] != 0)) {
            continue;                 /* born here: the record keeps their parents */
        }
        f = &arrival_facts[n];
        memset(f, 0, sizeof *f);
        f->record = record;
        wsprintfA(f->before, "  Age at arrival: (unknown)\n  Age when recorded: %d\n  Sex: %s\n",
                  rec_age(record), roster_sex(*(const int *)(record + REC[g_game].sex)));
        arrival_fact_index[n] = (int)i;
        ++n;
    }
    return n;
}

static int arrival_backfill_ready(void) {
    return cod_log_ready() && record_arrivals != NULL && births_are_logged();
}

/* At a save of `slot`, after Repair: each villager the log has no record
   for gets one; the marker once every one is on disk. */
static void arrival_backfill_at_save(int slot, const void *save_buffer) {
    int count;
    int i;
    int done = 1;
    if (install_state != 1 || save_buffer == NULL || slot < 1 || slot > 5 || !arrivals_repair[slot]
        || !arrival_backfill_ready() || vv_arrival_marker_present(g_game, slot)) {
        return;
    }
    count = arrival_gather();
    if (count < 0) {
        return;
    }
    if (count > 0 && record_arrivals(g_game, save_buffer, slot, arrival_facts, count, 1) < 0) {
        return;
    }
    for (i = 0; i < count; ++i) {
        int outcome = arrival_facts[i].outcome;
        if (outcome == VV_ARRIVAL_RECORDED || outcome == VV_ARRIVAL_QUEUED) {
            roster_arrived(arrival_fact_index[i]);   /* never Unaccounted now */
            COD_COUNT(arrivals_backfilled);
        }
        if (outcome != VV_ARRIVAL_IN_LOG && outcome != VV_ARRIVAL_RECORDED) {
            done = 0;                 /* held, or undecided: the next save looks again */
        }
    }
    if (done && vv_arrival_marker_write(g_game, slot)) {
        arrivals_repair[slot] = 0;
    }
}

/* ---- For the first-load cross-check's popup --------------------------------

   VvfpCauseScanArrivals(game, slot): how many of the village's villagers
   have neither a Birth nor an Arrived record in its Births and Conceptions
   log, writing nothing -- 0 once the slot's marker is there, -1 when that
   cannot be told now.  Call it once the village is loaded.
   VvfpCauseRepairArrivals(game, slot, repair): the player's answer.  1
   (Repair): at the village's next save each gets an Arrived record marked
   "Recorded afterwards (arrived before this log existed)", how they came
   unknown; 0 (Not now): nothing, and the next load asks again. */
__declspec(dllexport) int __stdcall VvfpCauseScanArrivals(int game, int slot) {
    int count;
    if (install_state == -1 || game < 1 || game > 5 || (g_game != 0 && game != g_game)
        || slot < 1 || slot > 5) {
        return -1;
    }
    if (install_state == 0) {
        g_game = game;
        cod_locate_table();
    }
    if (!cod_log_ready() || record_arrivals == NULL) {
        return -1;
    }
    if (!births_are_logged() || vv_arrival_marker_present(game, slot)) {
        return 0;
    }
    count = arrival_gather();
    if (count <= 0) {
        return count;
    }
    return record_arrivals(g_game, NULL, slot, arrival_facts, count, 0);
}

__declspec(dllexport) void __stdcall VvfpCauseRepairArrivals(int game, int slot, int repair) {
    if (game < 1 || game > 5 || (g_game != 0 && game != g_game) || slot < 1 || slot > 5) {
        return;
    }
    arrivals_repair[slot] = (signed char)(repair != 0);
}

/* The Story / Cheat Upgrades companion: its Custom Island Event made the
   villager in `index` (right after the creator, in the same frame). */
__declspec(dllexport) void __stdcall VvfpCauseArrivedBy(int game, int index, const char *how) {
    if (install_state != 1 || game != g_game || index < 0 || index >= RECORDS_MAX || how == NULL
        || arrivals[index].state != ARRIVAL_MADE) {
        return;
    }
    lstrcpynA(arrivals[index].how, how, ARRIVAL_HOW);
}
