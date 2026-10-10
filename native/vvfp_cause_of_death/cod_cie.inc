/* The Custom Island Event's "Dies": "Died in a custom island event" in the
   Deaths log, every game.  Included by vvfp_cause_of_death.c after
   cod_backfill.inc (cod_data_path).

   The Story / Cheat Upgrades companion's Custom Island Event kills a villager
   the way the stock island events do -- health 0 (A New Home, The Lost
   Children), or the game's own health setter with cause -1, "Unknown causes"
   (The Secret City, The Tree of Life, New Believers) -- so nothing here could
   tell its death from an island event's.  The companion says so itself, right
   after each kill it made (story_custom.inc ce_tell_killed): VvfpCauseKilled.
   Only that event's deaths: every stock island event stays "Unknown causes",
   as the games word them.

   A NEW HOME, THE LOST CHILDREN keep no cause of their own: this companion
   records each body's (cod_vv12.inc), so the body is given cause 5 there,
   which the graves file keeps (version 2) and the grave popup's cause line
   and the Death record both word.  The kill is a plain store no death site
   hooks, and the tick's "Unknown causes" is only for a villager still in
   seen_alive, which cod_died clears -- so nothing overwrites it; a cause a
   hooked site might have recorded for the same death is replaced, the event
   being what killed them.

   THE SECRET CITY, THE TREE OF LIFE, NEW BELIEVERS keep the cause on the
   record and in the grave, and their grave dialog words it from the game's
   own string table: the game's -1 is never touched (nothing unusual is ever
   written into the game).  Only the Death record gets the event's words, so
   the bodies the event left are kept here, by record and by the body's
   fingerprint (cod_fingerprint: name and age, frozen at death), until the
   burial or the removal of the unburied body writes the record:

       <save folder>\Virtual Villagers Fun Patcher Data\
           Custom Island Event Deaths\
               Virtual Villagers N Custom Island Event Deaths - Save S.dat

   written at each save of the village (cod_save_done), so it always matches
   the save: a body saved lying is still known after a quit and a reload, and
   a kill the game never saved is never in it.  An entry is dropped when its
   body is buried or removed (the record written), when the villager is
   brought back to life (Story / Cheat Upgrades' revive: the tick sees the
   record alive again with the same fingerprint), and at a save when no body
   in the village has its fingerprint any more (the record reused).  A body
   whose record's cause is no longer -1 died again of something else after a
   revive the tick did not see: the game's own cause is used.  Start Over
   deletes the file (native/shared/save_reset.c).

   Every population mode the same: the table is RECORDS_MAX records (256),
   and the records are the ones cod_locate_table found. */

/* ---- The report, every game ---------------------------------------------- */

static unsigned int cie_fp[RECORDS_MAX];   /* the body's fingerprint, 0 = none */

static struct {
    int slot;          /* the village the table belongs to, 0 = none known */
    int loaded;
    int dirty;
    int merge;         /* kills made before the slot was known: kept over the file's */
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} cie;

static void cie_bind(int slot);

/* The Story / Cheat Upgrades companion's Custom Island Event: called right
   after its kill of the villager in record `index` (story_custom.inc: "Dies",
   health 0, and a new villager made with health 0).  The record holds the
   body: present, health 0. */
__declspec(dllexport) void __stdcall VvfpCauseKilled(int game, int index) {
    unsigned char *record;
    if (install_state != 1 || game != g_game) {
        return;
    }
    record = cod_record(index);
    if (record == NULL || !rec_present(record) || rec_health(record) > 0 || !cod_is_villager(record)) {
        return;
    }
    if (g_game <= 2) {
        cod_died(record, CAUSE_CUSTOM_EVENT);          /* cod_vv12.inc */
        return;
    }
    cie_bind(cod_slot());
    cie_fp[index] = cod_record_fingerprint(record);
    cie.dirty = 1;
}

/* ---- The later three: the file ----------------------------------------------

   FORMAT (little-endian), exactly 16 + 8 * count bytes:
       u32 magic 'VCE1', u32 version 1, u32 game (3, 4 or 5), u32 count,
       count x { u16 record (0..255), u16 0, u32 fingerprint (cod_fingerprint
                 of the body's name and age at death; never 0) }
   in increasing record, each record once. */
#define CIE_MAGIC 0x31454356u          /* 'VCE1' */
#define CIE_VERSION 1u
#define CIE_HEADER 16u
#define CIE_ENTRY 8u

static unsigned char cie_buffer[CIE_HEADER + RECORDS_MAX * CIE_ENTRY];

static int cie_validate(const unsigned char *data, DWORD length, void *context) {
    unsigned int count;
    unsigned int i;
    int previous = -1;
    (void)context;
    if (length < CIE_HEADER) {
        return 0;
    }
    count = *(const unsigned int *)(data + 12);
    if (*(const unsigned int *)data != CIE_MAGIC
        || *(const unsigned int *)(data + 4) != CIE_VERSION
        || *(const unsigned int *)(data + 8) != (unsigned int)g_game
        || count > RECORDS_MAX
        || length != CIE_HEADER + count * CIE_ENTRY) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        const unsigned char *e = data + CIE_HEADER + i * CIE_ENTRY;
        int index = e[0] | e[1] << 8;
        if (index <= previous || index >= RECORDS_MAX || e[2] || e[3]
            || *(const unsigned int *)(e + 4) == 0u) {
            return 0;
        }
        previous = index;
    }
    return 1;
}

/* Bind the table to `slot`, reading its file the first time (again after a
   blocked read's retry window).  Kills made while no slot was known stay,
   over what the file says for their records. */
static void cie_bind(int slot) {
    DWORD length = 0;
    int result;
    unsigned int i;
    if (g_game < 3) {
        return;
    }
    if (slot != cie.slot) {
        if (cie.slot == 0) {
            for (i = 0; i < RECORDS_MAX; ++i) {
                if (cie_fp[i] != 0u) {
                    cie.merge = 1;
                }
            }
        } else {
            memset(cie_fp, 0, sizeof cie_fp);
            cie.merge = 0;
        }
        cie.slot = slot;
        cie.loaded = 0;
        cie.dirty = cie.merge;
        cie.path[0] = '\0';
        vv_sidecar_gate_bind(&cie.gate, 0x300 + g_game * 16 + slot);
    }
    if (slot <= 0 || cie.loaded || vv_sidecar_gate_throttled(&cie.gate)) {
        return;
    }
    if (cie.path[0] == '\0') {
        char stem[64];
        wsprintfA(stem, "Virtual Villagers %d Custom Island Event Deaths", g_game);
        if (!cod_data_path(cie.path, "Custom Island Event Deaths", stem, slot)) {
            cie.path[0] = '\0';
            vv_sidecar_gate_block(&cie.gate);
            return;
        }
    }
    result = vv_sidecar_load(&cie.gate, cie.path, cie_buffer, sizeof cie_buffer, &length,
                             cie_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;
    }
    if (!cie.merge) {
        memset(cie_fp, 0, sizeof cie_fp);
    }
    if (result == VV_SIDECAR_LOAD_VALID) {
        unsigned int count = *(const unsigned int *)(cie_buffer + 12);
        for (i = 0; i < count; ++i) {
            const unsigned char *e = cie_buffer + CIE_HEADER + i * CIE_ENTRY;
            int index = e[0] | e[1] << 8;
            if (cie_fp[index] == 0u) {
                cie_fp[index] = *(const unsigned int *)(e + 4);
            }
        }
    }
    cie.merge = 0;
    cie.loaded = 1;
}

static void cie_publish(void) {
    const void *parts[1];
    DWORD sizes[1];
    unsigned int count = 0;
    int i;
    if (!cie.loaded || cie.slot <= 0 || !cie.dirty) {
        return;
    }
    for (i = 0; i < RECORDS_MAX; ++i) {
        unsigned char *e;
        if (cie_fp[i] == 0u) {
            continue;
        }
        e = cie_buffer + CIE_HEADER + count * CIE_ENTRY;
        e[0] = (unsigned char)(i & 0xFF);
        e[1] = (unsigned char)(i >> 8);
        e[2] = 0;
        e[3] = 0;
        *(unsigned int *)(e + 4) = cie_fp[i];
        ++count;
    }
    ((unsigned int *)cie_buffer)[0] = CIE_MAGIC;
    ((unsigned int *)cie_buffer)[1] = CIE_VERSION;
    ((unsigned int *)cie_buffer)[2] = (unsigned int)g_game;
    ((unsigned int *)cie_buffer)[3] = count;
    parts[0] = cie_buffer;
    sizes[0] = CIE_HEADER + count * CIE_ENTRY;
    if (vv_sidecar_publish(&cie.gate, cie.path, parts, sizes, 1)) {
        cie.dirty = 0;
        COD_COUNT(published);
    }
}

/* ---- The later three: the bodies ------------------------------------------- */

/* Does record `i` hold the body with `fingerprint`? */
static int cie_holds(const unsigned char *records, int i, unsigned int fingerprint) {
    const unsigned char *record;
    if (records == NULL || i < 0 || (unsigned int)i >= REC[g_game].slots) {
        return 0;
    }
    record = records + (size_t)i * REC[g_game].stride;
    return rec_present(record) && !rec_lookalike(record) && rec_health(record) <= 0
        && cod_record_fingerprint(record) == fingerprint;
}

/* The cause for the Death record of the body in `record`, whose own cause is
   `game_cause`: "Died in a custom island event" when the event's "Dies" left
   it (the entry is used up), otherwise the game's.  The entry is the
   record's, or -- the records packed by a load -- another record's that no
   longer holds its body. */
static int cie_taken(const unsigned char *record, int game_cause) {
    unsigned char *records;
    unsigned int fingerprint;
    int index = cod_index_of(record);
    int k;
    int found = -1;
    if (g_game < 3 || index < 0) {
        return game_cause;
    }
    cie_bind(cod_slot());
    records = cod_records();
    fingerprint = cod_record_fingerprint(record);
    if (cie_fp[index] == fingerprint) {
        found = index;
    } else {
        for (k = 0; k < RECORDS_MAX; ++k) {
            if (k != index && cie_fp[k] == fingerprint && !cie_holds(records, k, fingerprint)) {
                found = k;
                break;
            }
        }
    }
    if (found < 0) {
        return game_cause;
    }
    cie_fp[found] = 0u;
    cie.dirty = 1;
    /* The event's kill writes -1; any other cause is a later death the game
       recorded itself. */
    return game_cause == CAUSE_UNKNOWN ? CAUSE_CUSTOM_EVENT : game_cause;
}

/* Every frame: a body brought back to life is no longer the event's. */
static void cie_tick(void) {
    unsigned char *records = cod_records();
    int i;
    if (records == NULL) {
        return;
    }
    for (i = 0; i < RECORDS_MAX && (unsigned int)i < REC[g_game].slots; ++i) {
        const unsigned char *record;
        if (cie_fp[i] == 0u) {
            continue;
        }
        record = records + (size_t)i * REC[g_game].stride;
        if (rec_present(record) && rec_health(record) > 0 && cod_record_fingerprint(record) == cie_fp[i]) {
            cie_fp[i] = 0u;
            cie.dirty = 1;
        }
    }
}

/* A save of `slot`: the entries follow their bodies (a load packs the
   records), an entry with no body left is dropped, and the file is written
   to match the save. */
static void cie_saved(int slot) {
    unsigned char *records;
    int i, k;
    cie_bind(slot);
    if (!cie.loaded) {
        return;                       /* blocked: kept in memory for the next save */
    }
    records = cod_records();
    if (records != NULL) {
        for (i = 0; i < RECORDS_MAX; ++i) {
            unsigned int fingerprint = cie_fp[i];
            if (fingerprint == 0u || cie_holds(records, i, fingerprint)) {
                continue;
            }
            cie_fp[i] = 0u;
            cie.dirty = 1;
            for (k = 0; k < RECORDS_MAX; ++k) {
                if (cie_fp[k] == 0u && cie_holds(records, k, fingerprint)) {
                    cie_fp[k] = fingerprint;
                    break;
                }
            }
        }
    }
    cie_publish();
}

/* Start Over erased `slot`: nothing of its village is kept, and the reset
   deletes the file next. */
static void cie_reset(int slot) {
    if (slot == cie.slot || cie.slot == 0) {
        memset(cie_fp, 0, sizeof cie_fp);
        cie.loaded = 0;
        cie.dirty = 0;
        cie.merge = 0;
        cie.path[0] = '\0';
        vv_sidecar_gate_bind(&cie.gate, -1);
        cie.slot = 0;
    }
}
