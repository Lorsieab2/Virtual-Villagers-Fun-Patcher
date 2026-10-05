/* Disappearances: a living villager removed with no skeleton and no grave,
   every game.  Included by vvfp_cause_of_death.c.

   The owner: these "get their own separate 'Disappeared' record: name (+
   identifying fields), age in game units, and what took them in plain
   words" -- the event's own name, and the Custom Island Event's as
   "Disappeared in a custom island event".

   Each stock removal is hooked where it happens, with the event in its own
   words:
     A New Home, The Lost Children   the store that clears the presence byte
                                     (cod_gone_sites.inc)
     The Secret City                 the sweep 0x45D990(percent, sex) that
                                     both The Tsunami (0x414B39) and The Low
                                     Tide (0x415EFF) call: its entry and its
                                     exit, compared
     The Tree of Life                The Sealed Box's wave, 0x415DA6
     New Believers                   none in the stock game
   The Custom Island Event's "Disappears" is reported by the Story / Cheat
   Upgrades companion itself (VvfpCauseVanished).  Anything else that takes
   a villager away is caught at the next save by the reconciliation
   (cod_roster.inc) and logged as Unaccounted. */

static void cod_log_gone(const unsigned char *record, const char *what) {
    char before[256];
    int index = cod_index_of(record);
    wsprintfA(before, "  Age: %d\n  What happened: %s\n", rec_age(record), what);
    if (index >= 0) {
        seen_alive[index] = 0;
        roster_departed(index, record);
    }
    cod_write(LOG_DISAPPEARED, record, 1, before, NULL, 1);
}

/* A villager of the tribe, alive, in its record. */
static int cod_is_villager(const unsigned char *record) {
    int index = cod_index_of(record);
    return index >= 0 && !cod_temporary(index, record) && !rec_lookalike(record);
}

/* ---- A New Home, The Lost Children: the stores ------------------------- */

struct gone_site {
    unsigned int va;
    const char *stock;
    unsigned char ra;             /* the record is regs[ra] + regs[rb] (rb 0 = none) */
    unsigned char rb;
    const char *what;
};

static const struct gone_site *gone_table;
static int gone_count;

static void site_gone(int site, const unsigned int *regs) {
    const struct gone_site *g = NULL;
    unsigned char *record;
    int i;
    for (i = 0; i < gone_count; ++i) {
        if (gone_table[i].va == sites[site].va) {
            g = &gone_table[i];
        }
    }
    if (g == NULL) {
        return;
    }
    record = (unsigned char *)(uintptr_t)(regs[g->ra] + (g->rb ? regs[g->rb] : 0u));
    if (cod_is_villager(record) && rec_present(record) && rec_health(record) > 0) {
        cod_log_gone(record, g->what);
    }
}

#include "cod_gone_sites.inc"

/* ---- The Secret City: the sweep ------------------------------------------- */

static unsigned char sweep_alive[RECORDS_MAX];
static unsigned int sweep_caller;

/* Entry, 0x45D990: [esp] = the caller's return address. */
static void vv3_sweep_entry(int site, const unsigned int *regs) {
    unsigned char *records = cod_records();
    int i;
    (void)site;
    sweep_caller = reg_stack(regs, 0);
    memset(sweep_alive, 0, sizeof sweep_alive);
    if (records == NULL) {
        return;
    }
    for (i = 0; i < (int)REC[3].slots; ++i) {
        const unsigned char *record = records + (size_t)i * REC[3].stride;
        sweep_alive[i] = (unsigned char)(rec_present(record) && rec_health(record) > 0
                                         && cod_is_villager(record));
    }
}

/* Exit, 0x45D9DD: everyone alive at the entry and no longer present. */
static void vv3_sweep_exit(int site, const unsigned int *regs) {
    unsigned char *records = cod_records();
    const char *what;
    int i;
    (void)site; (void)regs;
    if (records == NULL) {
        return;
    }
    if (sweep_caller == 0x414B3Eu) {
        what = "Swept away by The Tsunami";
    } else if (sweep_caller == 0x415F04u) {
        what = "Swept away by the wave at The Low Tide";
    } else {
        what = "Swept away by a wave";   /* no other caller in the stock game */
    }
    for (i = 0; i < (int)REC[3].slots; ++i) {
        const unsigned char *record = records + (size_t)i * REC[3].stride;
        if (sweep_alive[i] && !rec_present(record)) {
            cod_log_gone(record, what);
        }
    }
    memset(sweep_alive, 0, sizeof sweep_alive);
}

/* ---- The Tree of Life: The Sealed Box ------------------------------------

   "Swim it back", the wave outcome: health is set to 0 (0x415D9E), then the
   villager is taken, `mov byte [ecx+0x1cc4], 0` (ecx = record). */
static void vv4_sealed_box(int site, const unsigned int *regs) {
    unsigned char *record = (unsigned char *)(uintptr_t)regs[R_ECX];
    (void)site;
    if (cod_is_villager(record) && rec_present(record)) {
        cod_log_gone(record, "Swept away by a wave swimming The Sealed Box back");
    }
}

static void gone_sites(void) {
    int i;
    gone_table_for_game();
    for (i = 0; i < gone_count; ++i) {
        cod_add(gone_table[i].va, gone_table[i].stock, site_gone);
    }
    if (g_game == 3) {
        cod_add(0x45D990u, "5355" "8B6C240C" "5657", vv3_sweep_entry);
        cod_add(0x45D9DDu, "5F5E5D5B" "C20800", vv3_sweep_exit);
    } else if (g_game == 4) {
        cod_add(0x415DA6u, "C681C41C000000", vv4_sealed_box);
    }
}

/* ---- Whom the tick saw alive ---------------------------------------------

   A New Home and The Lost Children word a death no site reported as the
   later games word every island event's, "Unknown causes" -- but only for a
   villager this companion saw alive (cod_vv12.inc).  Every game keeps the
   list: the per-frame tick notes every living villager. */
static int seen_slot = -1;

static void seen_tick(void) {
    unsigned char *records = cod_records();
    int slot = cod_slot();
    int i;
    if (slot != seen_slot) {
        seen_slot = slot;
        memset(seen_alive, 0, sizeof seen_alive);
    }
    if (records == NULL) {
        return;
    }
    for (i = 0; i < (int)REC[g_game].slots; ++i) {
        unsigned char *record = records + (size_t)i * REC[g_game].stride;
        if (rec_present(record) && rec_health(record) > 0 && cod_is_villager(record)) {
            seen_alive[i] = cod_name_hash(record);
        }
    }
}

/* The Story / Cheat Upgrades companion's Custom Island Event: called right
   after its "Disappears" took the villager in record `index` (the record
   still holds them; only the presence byte is cleared). */
__declspec(dllexport) void __stdcall VvfpCauseVanished(int game, int index) {
    unsigned char *record;
    if (install_state != 1 || game != g_game) {
        return;
    }
    record = cod_record(index);
    if (record != NULL && !rec_present(record) && rec_health(record) > 0 && cod_is_villager(record)) {
        cod_log_gone(record, "Disappeared in a custom island event");
    }
}
