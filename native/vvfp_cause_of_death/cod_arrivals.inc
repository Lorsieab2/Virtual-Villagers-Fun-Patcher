/* "Arrived" records: every villager who joins the village without being born
   into it, in the Births and Conceptions log, every game.  Included by
   vvfp_cause_of_death.c.  native/shared/arrival_backfill.h has the record's
   format and the owner's words.

   WHO ARRIVES.  Every villager the game's own creators make is reported here
   (roster_created, cod_roster_sites.inc): a birth, an island event's
   newcomer, the Barrel O' Babies, the Custom Island Event's new villagers.
   A birth is not an arrival: the path that made it says so (a marker of the
   delivery, cod_arrival_sites.inc), and so does the Births and Conceptions
   log (VvfpCauseNoteArrival, from the birth hook right after the creator, in
   the same frame).  A record the game makes and takes away again (The Lost
   Children's stranger, the ghosts, the stand-ins) is not one either.
   Everything else the creators make is an arrival.

   New Believers: a Heathen is never a villager (the owner), so a Heathen
   made by the creator is not an arrival.  A Heathen converted to a believer
   IS one from that moment, and the faction byte (+0x1CEC) is cleared in place
   (the setter 0x466880): the tick sees a record it saw as a Heathen become a
   believer, and that is an arrival, "Converted from the Heathens".

   HOW THEY CAME (the owner's words for the "How:" line).  The path's marker
   names it: "Founder" (the new-village seeding), the island event's title,
   "Barrel of Babies" (natural or bought: the purchase runs the game's own
   barrel); "Custom Island Event" when the Story / Cheat Upgrades companion
   says its event made them (VvfpCauseArrivedBy); "Converted from the
   Heathens"; "unknown" on any other path.

   WHEN.  The arrival is decided at the first tick after the creator (the
   birth note has come by then, the event has written the villager's name,
   age and looks), and its age then is the age at arrival.  The record is
   written at the next save of the slot it was made in, where the logs are
   named.  A founder is written only at a save with no village saved in the
   slot before (the reconciliation's have_previous), and only from the
   seeding's new-village callers: the startup scan's and the no-save-yet
   seeding run ahead of a load that overwrites what they made, so theirs
   are temporary (cod_arrival_sites.inc) -- an existing village saved for
   the first time by this build has no Village Roster file either.  A villager
   who arrived and leaves (a burial, a disappearance) before that save gets
   the record at the departure, while the record still holds them.  Either
   way the arrival is reported to the reconciliation, so the Unaccounted
   Villagers log never lists them.

   THE BACKFILL.  VvfpCauseScanArrivals / VvfpCauseRepairArrivals (and
   ...Now), for the cross-check, like the graves': the village's villagers (believers,
   and in The Lost Children to New Believers only those with no parents on
   their record -- a villager with parents was born) are handed to
   RecordArrivalsMissingFromLog, which counts those with no Birth or Arrived
   record; after Repair, at the next save, each gets an Arrived record marked
   "Recorded afterwards" -- "How: Founder" when the village's first Village
   History snapshot lists them, else "unknown" -- and once all are on disk the
   slot's marker says it is done, for good.  A new village's founders this
   companion did not see made (made before this record existed, or by a
   build that installed it only once a village was shown) are found the same
   way. */

#define ARRIVAL_NONE 0
#define ARRIVAL_MADE 1          /* made by a creator, not yet decided */
#define ARRIVAL_PENDING 2       /* an arrival, its record written at the next save */

#define ARRIVAL_HOW 48
#define ARRIVAL_PARENTS 256

static vv_arrival_fact arrival_facts[RECORDS_MAX];
static int arrival_fact_index[RECORDS_MAX];

static struct {
    signed char tag;            /* report_tag() when made: the slot it counts for */
    unsigned char state;
    unsigned char born;         /* a birth: the Births log's note, or a birth path's marker */
    unsigned char founder;      /* made by the new-village seeding */
    int age;                    /* at arrival */
    char how[ARRIVAL_HOW];
    /* The parents the Custom Island Event chose (VvfpCauseArrivedParents):
       the "  Parents:" block, as every Village History record prints it. */
    char parents[ARRIVAL_PARENTS];
} arrivals[RECORDS_MAX];

/* New Believers: -1 unknown, 0 a believer, 1 a Heathen -- as the tick last
   saw the record. */
static signed char faction_seen[RECORDS_MAX];
static int faction_ready;

/* The player's answer to the backfill, per slot, this session. */
static signed char arrivals_repair[6];
/* ...and to the Birth records' backfill (The Lost Children to New Believers). */
static signed char births_repair[6];

/* The Births and Conceptions log recorded a birth into `index`. */
static void arrival_noted_birth(int index) {
    if (index >= 0 && index < RECORDS_MAX && arrivals[index].state == ARRIVAL_MADE) {
        arrivals[index].born = 1;
    }
}

#include "cod_arrival_sites.inc"

/* The return address in the stack slot `offset` above the hook's esp: the
   game's own, even while a Story / Cheat Upgrades scope call has its own
   there (cod_arrival_sites.inc) -- that companion says whose it is. */
typedef unsigned int (__stdcall *story_caller_fn)(unsigned int slot);
#ifdef VVFP_TEST
static story_caller_fn test_story_caller;
#endif

static story_caller_fn arrival_story_caller(void) {
    HMODULE story;
#ifdef VVFP_TEST
    if (test_story_caller != NULL) {
        return test_story_caller;
    }
#endif
    story = GetModuleHandleA("VVFP Story Upgrades.dll");
    return story != NULL ? (story_caller_fn)GetProcAddress(story, "VvfpStoryCallerReturn") : NULL;
}

static unsigned int arrival_slot(const unsigned int *regs, unsigned int offset, story_caller_fn caller) {
    unsigned int game_return = caller != NULL ? caller(regs[R_ESP] + offset) : 0u;
    return game_return != 0u ? game_return : reg_stack(regs, offset);
}

/* The marker naming the path that made the villager at the hook `site_va`:
   each is read at its own fixed place in the stack (cod_arrival_sites.inc),
   never searched for.  NULL when none matches. */
static const struct arrival_marker *arrival_marker_of(unsigned int site_va, const unsigned int *regs) {
    const struct arrival_marker *table = NULL;
    story_caller_fn caller;
    int count = 0;
    int k;
    if (regs == NULL) {
        return NULL;
    }
    caller = arrival_story_caller();
    arrival_markers(&table, &count);
    for (k = 0; k < count; ++k) {
        const struct arrival_marker *m = &table[k];
        if (m->site != site_va || arrival_slot(regs, m->offset, caller) != m->value) {
            continue;
        }
        if (m->need_offset != 0u && arrival_slot(regs, m->need_offset, caller) != m->need_value) {
            continue;
        }
        return m;
    }
    return NULL;
}

/* A creator made `index`, at the hook `site_va` with `regs` (NULL: not
   known). */
static void arrival_created(int index, unsigned int site_va, const unsigned int *regs) {
    const struct arrival_marker *m;
    if (index < 0 || index >= RECORDS_MAX) {
        return;
    }
    m = arrival_marker_of(site_va, regs);
    arrivals[index].tag = report_tag();
    arrivals[index].state = ARRIVAL_MADE;
    arrivals[index].born = (unsigned char)(m != NULL && (m->kind == MARK_BIRTH || m->kind == MARK_TEMPORARY));
    arrivals[index].founder = (unsigned char)(m != NULL && m->kind == MARK_FOUNDER);
    /* A new village's founders are seeded before the game gives the village
       its slot: the slot the host reports then is a stale one (live, The
       Lost Children with a fresh profile: 5, the village then saved in 1), so
       their records were never written.  They count for the slot of the
       first save instead -- which writes them only when no village was saved
       there before (arrival_save), so a seeding a load replaces still writes
       nothing. */
    if (arrivals[index].founder) {
        arrivals[index].tag = REPORT_EARLY;
        if (arrived[index] != REPORT_NONE) {
            arrived[index] = REPORT_EARLY;    /* the reconciliation's report, likewise */
        }
    }
    arrivals[index].age = 0;
    arrivals[index].how[0] = '\0';
    arrivals[index].parents[0] = '\0';
    if (m != NULL && m->label != NULL) {
        lstrcpynA(arrivals[index].how, m->label, ARRIVAL_HOW);
    }
    faction_seen[index] = -1;
}

static int arrival_heathen(const unsigned char *record) {
    return REC[g_game].heathen != 0u && record[REC[g_game].heathen] != 0;
}

/* Born in the village: the record keeps their parents' names (The Lost
   Children on; A New Home keeps none). */
static int arrival_parented(const unsigned char *record) {
    static const unsigned int PARENTS[6][2] = {
        { 0, 0 }, { 0, 0 }, { 0x57Du, 0x596u }, { 0xDF8u, 0xE11u },
        { 0x1BC0u, 0x1BD9u }, { 0x1BC0u, 0x1BD9u },
    };
    return PARENTS[g_game][0] != 0u
        && (record[PARENTS[g_game][0]] != 0 || record[PARENTS[g_game][1]] != 0);
}

/* Decide a made record: a birth, a Heathen or gone -> nothing; otherwise an
   arrival, aged as it is now.  A "founder" whose record keeps parents was
   born in a village a load put there (the seeding ran ahead of it): never
   an arrival (the owner's v1.35.58 live pass, Miki and Mem). */
static void arrival_decide(int index) {
    const unsigned char *record = cod_record(index);
    if (arrivals[index].state != ARRIVAL_MADE) {
        return;
    }
    if (arrivals[index].born || record == NULL || !roster_member(record) || arrival_heathen(record)
        || (arrivals[index].founder && arrival_parented(record))) {
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
    char after[96 + ARRIVAL_PARENTS];
    if (record == NULL) {
        return;
    }
    wsprintfA(before, "  Age at arrival: %d\n  Sex: %s\n", arrivals[index].age,
              roster_sex(*(const int *)(record + REC[g_game].sex)));
    wsprintfA(after, "  How: %s\n%s", arrivals[index].how, arrivals[index].parents);
    COD_COUNT(arrivals);
    cod_write(LOG_ARRIVED, record, 1, before, after, 2);
}

/* New Believers: a believer the tick saw become a Heathen -- The Mask's
   "...and is a believer no more" (string 0xA41B8), the Custom Island Event's
   "Becomes a Heathen", any path -- leaves the tribe (the owner: a Heathen is
   never a villager), the mirror of "Converted from the Heathens": a
   "Disappeared" record in the Deaths and Disappearances log, "Left the
   tribe: became a Heathen".  The record is still theirs and still in the
   Village Roster (Heathens are kept there too), so no departure is reported
   to the reconciliation -- which would make the next save call them an
   unaccounted arrival -- and they are never Unaccounted.  An Arrived record
   not yet written is written first, so the two read in order.  Converted
   back, the tick writes their Arrived record as for any Heathen. */
static void arrival_left_for_the_heathens(int index, const unsigned char *record) {
    char before[256];
    if (arrivals[index].state != ARRIVAL_NONE) {
        arrival_departed(index);
    }
    wsprintfA(before, "  Age: %d\n  Sex: %s\n  What happened: Left the tribe: became a Heathen\n",
              rec_age(record), roster_sex(*(const int *)(record + REC[g_game].sex)));
    COD_COUNT(left_tribe);
    cod_write(LOG_DISAPPEARED, record, 1, before, NULL, 1);
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
            former_forget(i);
            continue;
        }
        heathen = arrival_heathen(record);
        former_tick(i, record, heathen, faction_seen[i]);
        if (faction_seen[i] == 0 && heathen) {
            arrival_left_for_the_heathens(i, record);
        }
        if (faction_seen[i] == 1 && !heathen && arrivals[i].state == ARRIVAL_NONE) {
            arrivals[i].tag = report_tag();
            arrivals[i].state = ARRIVAL_PENDING;
            arrivals[i].born = 0;
            arrivals[i].age = rec_age(record);
            lstrcpynA(arrivals[i].how, "Converted from the Heathens", ARRIVAL_HOW);
            arrivals[i].parents[0] = '\0';
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
   arrivals made for it get their records.  A founder -- made by the
   new-village seeding -- only at a save with no village saved in the slot
   before (`same_village` 0: the new village's first save): the seeding also
   runs ahead of a load that then overwrites what it made (The Lost
   Children's startup scan), and those were never this village's. */
static void arrival_save(int slot, int same_village) {
    int i;
    for (i = 0; i < RECORDS_MAX && (unsigned int)i < REC[g_game].slots; ++i) {
        if (arrivals[i].state == ARRIVAL_NONE || !report_counts(arrivals[i].tag, slot)) {
            continue;
        }
        arrival_decide(i);
        if (arrivals[i].state == ARRIVAL_PENDING && (!arrivals[i].founder || !same_village)) {
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
    former_reset(slot);
    if (slot >= 1 && slot <= 5) {
        arrivals_repair[slot] = 0;
        births_repair[slot] = 0;
    }
}

/* ---- The backfill ---------------------------------------------------------- */

/* Whether this install writes Birth records for every birth: in A New Home
   only with Show Parents in Details Screen ("VVFP VV1 Parentage.dll"). */
static int births_are_logged(void) {
    if (g_game != 1) {
        return 1;
    }
#ifdef VVFP_TEST
    if (test_vv1_births != 0) {
        return test_vv1_births > 0;
    }
#endif
    return vvfp_patcher_file_exists("VVFP VV1 Parentage.dll");
}

/* The village's villagers, members and believers, every one of them: the
   ones this backfill records -- `births` 0: with no parents on their record
   (who could have arrived); 1: with parents there (The Lost Children on:
   born in the village) -- and the others marked VV_ARRIVAL_CONTEXT, which
   are only counted (a name they share decides nothing).  -1 when the
   records are not there. */
static int arrival_gather(int births) {
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
        f = &arrival_facts[n];
        memset(f, 0, sizeof *f);
        f->record = record;
        /* Born here: the record keeps their parents (never in A New Home). */
        if (arrival_parented(record) != births) {
            f->outcome = VV_ARRIVAL_CONTEXT;
        }
        /* Made by a creator this session, its own record not written yet:
           the live record is theirs (arrival_save, right after the backfill
           at the same save), never the backfill's as well.  The owner's
           v1.35.58 preview gave a Custom Island Event's villager both. */
        if (arrivals[i].state != ARRIVAL_NONE) {
            f->outcome = VV_ARRIVAL_CONTEXT;
        }
        wsprintfA(f->before, "  Age at arrival: (unknown)\n  Age when recorded: %d\n  Sex: %s\n",
                  rec_age(record), roster_sex(*(const int *)(record + REC[g_game].sex)));
        arrival_fact_index[n] = (int)i;
        ++n;
    }
    return n;
}

/* The village in `slot` for its backfill markers: its "Village: <name>
   (Save S)" line read from its save file by "VVFP Save Reset.dll"
   (SavedVillageHeader, as the Deaths log's grave backfill reads it); 0 when
   that cannot be told. */
static unsigned int cod_marker_village(int slot) {
    typedef int (__stdcall *saved_header_fn)(int, int, char *, int);
    char header[256];
    saved_header_fn get;
    HMODULE module = GetModuleHandleA("VVFP Save Reset.dll");
    if (module == NULL) {
        module = vvfp_patcher_dll("VVFP Save Reset.dll");
    }
    get = module != NULL ? (saved_header_fn)GetProcAddress(module, "SavedVillageHeader") : NULL;
    if (get == NULL || !get(g_game, slot, header, (int)sizeof header)) {
        return 0u;
    }
    return vv_backfill_village_id(header);
}

static int arrival_backfill_ready(void) {
    return cod_log_ready() && record_arrivals != NULL && births_are_logged();
}

/* At a save of `slot`, after Repair: each villager the log has no record
   for gets one; the marker once every one is on disk.  `save_buffer` NULL:
   right after the quit save (VvfpCauseRepairArrivalsNow), the header read
   back from the saved file. */
static void arrival_backfill_at_save(int slot, const void *save_buffer) {
    int count;
    int i;
    int done = 1;
    if (install_state != 1 || slot < 1 || slot > 5 || !arrivals_repair[slot]
        || !arrival_backfill_ready() || vv_arrival_marker_present(g_game, slot, cod_marker_village(slot))) {
        return;
    }
    count = arrival_gather(0);
    if (count < 0) {
        return;
    }
    if (count > 0 && record_arrivals(g_game, save_buffer, slot, arrival_facts, count, VV_ARRIVAL_APPLY) < 0) {
        return;
    }
    for (i = 0; i < count; ++i) {
        int outcome = arrival_facts[i].outcome;
        if (outcome == VV_ARRIVAL_CONTEXT) {
            continue;                 /* not this backfill's */
        }
        if (outcome == VV_ARRIVAL_RECORDED || outcome == VV_ARRIVAL_QUEUED) {
            roster_arrived(arrival_fact_index[i]);   /* never Unaccounted now */
            COD_COUNT(arrivals_backfilled);
        }
        if (outcome != VV_ARRIVAL_IN_LOG && outcome != VV_ARRIVAL_RECORDED) {
            done = 0;                 /* held, or undecided: the next save looks again */
        }
    }
    if (done && vv_arrival_marker_write(g_game, slot, cod_marker_village(slot))) {
        arrivals_repair[slot] = 0;
    }
}

/* ---- For the cross-check (native/shared/crosscheck_bridge.h) ---------------

   VvfpCauseScanArrivals(game, slot): how many of the village's villagers
   have neither a Birth nor an Arrived record in its Births and Conceptions
   log, writing nothing -- 0 once the slot's marker is there, -1 when that
   cannot be told now.  Call it once the village is loaded.
   VvfpCauseRepairArrivals(game, slot, repair): the player's go-ahead, given
   before a save.  1 (Repair): at the village's next save each gets an
   Arrived record marked "Recorded afterwards (arrived before this log
   existed)", how they came unknown; 0: nothing. */
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
    if (!births_are_logged() || vv_arrival_marker_present(game, slot, cod_marker_village(slot))) {
        return 0;
    }
    count = arrival_gather(0);
    if (count <= 0) {
        return count;
    }
    return record_arrivals(g_game, NULL, slot, arrival_facts, count, VV_ARRIVAL_COUNT);
}

__declspec(dllexport) void __stdcall VvfpCauseRepairArrivals(int game, int slot, int repair) {
    if (game < 1 || game > 5 || (g_game != 0 && game != g_game) || slot < 1 || slot > 5) {
        return;
    }
    arrivals_repair[slot] = (signed char)(repair != 0);
}

/* VvfpCauseRepairArrivalsNow(game, slot): Repair, answered right after the
   game's quit save (native/shared/crosscheck_bridge.h): the Arrived records
   are written now from the villagers that save just wrote, as the next save
   would write them (the header read back from the saved file), and the
   marker once all are on disk.  1 when nothing is left to record. */
__declspec(dllexport) int __stdcall VvfpCauseRepairArrivalsNow(int game, int slot) {
    if (install_state != 1 || game != g_game || slot < 1 || slot > 5) {
        return 0;
    }
    arrivals_repair[slot] = 1;
    arrival_backfill_at_save(slot, NULL);
    /* Done only when every record is on disk: the marker is written only
       then.  The scan would also count a record merely held in the
       parentage DLL's queue for a save that never comes -- the game is
       closing -- as there (Codex, #542). */
    return vv_arrival_marker_present(g_game, slot, cod_marker_village(slot));
}

/* VvfpCauseVillager(game, index, name, cap, looks): the village's villager in
   record `index`, read only, for the cross-check's missing last names
   (native/shared/crosscheck_bridge.h; the owner, v1.35.66: "if repair logs
   detects a missing last name, please prompt the player to add one").
   1: a living villager of the village -- their name in name[cap], their head
   in looks[0] and body in looks[1] (0 is a real head and body); 0: no
   villager there (an empty record, a body, a statue, ghost or stand-in, a
   Heathen); -1: past the last record, or the table is not there. */
__declspec(dllexport) int __stdcall VvfpCauseVillager(int game, int index, char *name, int cap, int *looks) {
    const struct game_records *r;
    const unsigned char *record;
    unsigned char *records;
    if (install_state == -1 || game < 1 || game > 5 || (g_game != 0 && game != g_game)
        || name == NULL || cap < 2 || looks == NULL) {
        return -1;
    }
    if (install_state == 0) {
        g_game = game;
        cod_locate_table();
    }
    r = &REC[g_game];
    if (index < 0 || index >= RECORDS_MAX || (unsigned int)index >= r->slots
        || (records = cod_records()) == NULL) {
        return -1;
    }
    record = records + (size_t)index * r->stride;
    if (!roster_member(record) || arrival_heathen(record) || rec_lookalike(record) || rec_health(record) <= 0
        || record[r->name] == 0) {
        return 0;
    }
    lstrcpynA(name, (const char *)(record + r->name), cap < (int)r->name_capacity + 1 ? cap : (int)r->name_capacity + 1);
    looks[0] = *(const int *)(record + r->head);
    looks[1] = *(const int *)(record + r->body);
    return 1;
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

/* ---- Birth records, backfilled (The Lost Children to New Believers) -------

   native/shared/arrival_backfill.h.  The same shape as the Arrived records'
   backfill above: the villagers whose record keeps parents -- born in the
   village -- with no Birth or Arrived record in its Births and Conceptions
   log get a Birth record from their own record, marked "Recorded afterwards
   (born before this log existed)", at the next save after Repair; the slot's
   marker ("...Data\Births\...") once every one is on disk.  A New Home keeps
   no parents on the record: nothing to backfill there. */
static int births_backfill_ready(void) {
    return g_game >= 2 && cod_log_ready() && record_births != NULL;
}

static void births_backfill_at_save(int slot, const void *save_buffer) {
    int count;
    int i;
    int done = 1;
    if (install_state != 1 || slot < 1 || slot > 5 || !births_repair[slot]
        || !births_backfill_ready() || vv_backfill_marker_present(VV_BACKFILL_BIRTHS, g_game, slot, cod_marker_village(slot))) {
        return;
    }
    count = arrival_gather(1);
    if (count < 0) {
        return;
    }
    if (count > 0 && record_births(g_game, save_buffer, slot, arrival_facts, count, VV_ARRIVAL_APPLY) < 0) {
        return;
    }
    for (i = 0; i < count; ++i) {
        int outcome = arrival_facts[i].outcome;
        if (outcome == VV_ARRIVAL_CONTEXT) {
            continue;
        }
        if (outcome == VV_ARRIVAL_RECORDED || outcome == VV_ARRIVAL_QUEUED) {
            roster_arrived(arrival_fact_index[i]);   /* never Unaccounted now */
            COD_COUNT(births_backfilled);
        }
        if (outcome != VV_ARRIVAL_IN_LOG && outcome != VV_ARRIVAL_RECORDED) {
            done = 0;
        }
    }
    if (done && vv_backfill_marker_write(VV_BACKFILL_BIRTHS, g_game, slot, cod_marker_village(slot))) {
        births_repair[slot] = 0;
    }
}

/* VvfpCauseScanBirths(game, slot): how many of the village's villagers born
   there (their record keeps parents) have neither a Birth nor an Arrived
   record in its Births and Conceptions log, writing nothing -- 0 in A New
   Home and once the slot's marker is there, -1 when that cannot be told now.
   VvfpCauseRepairBirths(game, slot, repair): the player's answer, as for the
   arrivals. */
__declspec(dllexport) int __stdcall VvfpCauseScanBirths(int game, int slot) {
    int count;
    if (install_state == -1 || game < 1 || game > 5 || (g_game != 0 && game != g_game)
        || slot < 1 || slot > 5) {
        return -1;
    }
    if (game == 1) {
        return 0;
    }
    if (install_state == 0) {
        g_game = game;
        cod_locate_table();
    }
    if (!cod_log_ready() || record_births == NULL) {
        return -1;
    }
    if (vv_backfill_marker_present(VV_BACKFILL_BIRTHS, game, slot, cod_marker_village(slot))) {
        return 0;
    }
    count = arrival_gather(1);
    if (count <= 0) {
        return count;
    }
    return record_births(g_game, NULL, slot, arrival_facts, count, VV_ARRIVAL_COUNT);
}

__declspec(dllexport) void __stdcall VvfpCauseRepairBirths(int game, int slot, int repair) {
    if (game < 2 || game > 5 || (g_game != 0 && game != g_game) || slot < 1 || slot > 5) {
        return;
    }
    births_repair[slot] = (signed char)(repair != 0);
}

/* VvfpCauseRepairBirthsNow(game, slot): the same for the Birth records
   written from the save (The Lost Children to New Believers).  1 when
   nothing is left to record. */
__declspec(dllexport) int __stdcall VvfpCauseRepairBirthsNow(int game, int slot) {
    if (install_state != 1 || game < 2 || game != g_game || slot < 1 || slot > 5) {
        return 0;
    }
    births_repair[slot] = 1;
    births_backfill_at_save(slot, NULL);
    /* As for the arrivals: the marker, written only once every record is on
       disk, never a record merely held for a save that never comes. */
    return vv_backfill_marker_present(VV_BACKFILL_BIRTHS, g_game, slot, cod_marker_village(slot));
}

/* ...and the parents it chose for that villager (the owner, 2026-10-10:
   "the Births log's Arrived record ... must show the chosen parents"): the
   "  Parents:" block with each known parent's name, head and body, written
   after "How:" -- the block every Village History and Population record
   has, which the Family Tree and the Matchmaker read.  Right after
   VvfpCauseArrivedBy, in the same frame. */
__declspec(dllexport) void __stdcall VvfpCauseArrivedParents(int game, int index, const char *parents) {
    if (install_state != 1 || game != g_game || index < 0 || index >= RECORDS_MAX || parents == NULL
        || arrivals[index].state != ARRIVAL_MADE) {
        return;
    }
    lstrcpynA(arrivals[index].parents, parents, ARRIVAL_PARENTS);
}