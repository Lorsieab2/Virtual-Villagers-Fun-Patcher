/* The head looks of one village, kept in the patcher's own per-save file and following each villager.
   Included by vvfp_head_look.c, and unchanged by native/vvfp_head_look/head_look_harness.c (which gives it a
   village of its own on real files).

   WHAT IS KEPT.  For each villager record, the look Change Appearance chose: 0 Auto (the game's own rule,
   the old head from a shown age of 1,100), 1 Young, 2 Old.  Nothing is ever written into a villager record
   (the owner: patcher data goes in the patcher's own files, never in record bytes).

   THE FILE.  The save's own "Virtual Villagers Fun Patcher\Save <S>\Data\Head Looks\Head Looks - Save <S>.dat"
   (native/shared/per_save_data.h routes it; an older-layout copy is used while one is there), written
   through native/shared/sidecar_io.h -- to "<path>.tmp", checked, then put in place, so a crash or a full disk
   never leaves half a file -- and never before the slot's load has settled.  Little-endian:

       u32 magic 'VHL1' (0x314C4856), u32 game (1..5), u32 count (150 or 256, the build's records),
       u32 roster[count]   the identity of whoever held each record when it was written (0 = nobody),
       u8  look[count]     0 Auto, 1 Young, 2 Old

   exactly 12 + count * 5 bytes.  A file of another shape, game or size is moved aside intact (sidecar_io.h)
   and the village starts with every look Auto; a look value above 2 reads as Auto.

   FOLLOWING THE VILLAGER -- the pattern of the Origins masks (VV5's "Village Masks - Save S.dat",
   native/vv5_task9_origins: Vv5MaskSync, vv5_mask_sidecar_load), with the same shared rules
   (native/shared/mask_follow.h, foreign_sidecar.h):
     * the file belongs to the village whose living roster it shares a STRICT majority with (of the smaller
       roster), never to a slot alone: slots are reused by Start Over and by copied saves;
     * on a load the game packs its records 0, 1, 2, ... (after a death everyone behind moves down), so each
       look goes to the one villager with its stored identity (name, sex and the parents' names; A New Home:
       name, sex and family), wherever they are now; an identity two villagers share is never guessed at;
     * during play a birth or a death moves nobody: a look stays on its record while the record is empty
       (a body not yet buried, a villager away) and is dropped the moment anyone else holds it -- a newborn
       in a dead villager's record never inherits a look; a RENAME keeps the look (one record changed, the
       sex and parents unchanged);
     * another village's file in the slot is never replaced: a table with nothing in it is never written
       over it, and the first look chosen moves it aside first;
     * Start Over deletes the file (native/shared/save_reset.c); the new founders share nobody with the
       table, so it is cleared and reloaded from the (now missing) file: every look Auto.

   The includer defines, for its game: HL_MAX, hl_slots(), hl_record(i), hl_present(r), hl_identity(r),
   hl_stable(r), hl_slot_now(), hl_game(). */

#define HL_MAGIC 0x314C4856u            /* 'VHL1' */
#define HL_HEADER 12u
#define HL_FILE_BYTES(count) (HL_HEADER + (DWORD)(count) * 5u)
#define HL_FILE_MAX HL_FILE_BYTES(HL_MAX)
#define HL_SYNC_MS 250u
#define HL_KIND "Head Looks"

static unsigned char g_look[HL_MAX];          /* by record: 0 Auto, 1 Young, 2 Old */
static unsigned int g_look_id[HL_MAX];        /* the identity each look was kept for */
static unsigned int g_roster[HL_MAX];         /* who held each record at the last look */
static unsigned int g_stable[HL_MAX];         /* ...and what a rename leaves of it */
static int g_have_roster;                     /* the table belongs to the village on screen */
static int g_slot;                            /* the slot it was loaded for */
static DWORD g_sync_tick;
static vv_sidecar_gate g_gate;
static int g_foreign;                         /* the slot's file is another village's */
static unsigned char g_file[HL_FILE_MAX];

/* Every record's identity and stable part (0 for a record nobody holds); returns how many are held. */
static int hl_roster(unsigned int *ids, unsigned int *stable) {
    int i, n = 0, slots = hl_slots();
    memset(ids, 0, HL_MAX * sizeof(unsigned int));
    memset(stable, 0, HL_MAX * sizeof(unsigned int));
    for (i = 0; i < slots && i < HL_MAX; ++i) {
        const unsigned char *r = hl_record(i);
        if (r != NULL && hl_present(r)) {
            ids[i] = hl_identity(r);
            stable[i] = hl_stable(r);
            ++n;
        }
    }
    return n;
}

/* How many of `a`'s villagers are in `b` at the same record or at their rank in `a` (the record a packed
   load puts them in) -- vv5_roster_overlap. */
static int hl_overlap(const unsigned int *a, const unsigned int *b) {
    int i, n = 0, rank = 0;
    for (i = 0; i < HL_MAX; ++i) {
        if (a[i] == 0) {
            continue;
        }
        if (a[i] == b[i] || a[i] == b[rank]) {
            ++n;
        }
        ++rank;
    }
    return n;
}

static int hl_living(const unsigned int *a) {
    int i, n = 0;
    for (i = 0; i < HL_MAX; ++i) {
        n += a[i] != 0;
    }
    return n;
}

/* The same village: a STRICT majority of the smaller roster is shared (vv5_roster_same). */
static int hl_same_village(const unsigned int *a, const unsigned int *b) {
    int la = hl_living(a), lb = hl_living(b);
    int need = la < lb ? la : lb;
    if (need == 0) {
        return 0;
    }
    return hl_overlap(a, b) >= need / 2 + 1;
}

/* The slot's file. */
static int hl_path(int slot, char *out) {
    char name[] = "Head Looks - Save 0.dat";
    if (slot < 1 || slot > 5) {
        return 0;
    }
    name[sizeof "Head Looks - Save " - 1] = (char)('0' + slot);
    return vv_ps_data_file_a(out, HL_KIND, name, VV_PS_RESERVE);
}

static int hl_valid(const unsigned char *data, DWORD len, void *ctx) {
    unsigned int magic, game, count;
    (void)ctx;
    if (len < HL_HEADER) {
        return 0;
    }
    memcpy(&magic, data, 4);
    memcpy(&game, data + 4, 4);
    memcpy(&count, data + 8, 4);
    return magic == HL_MAGIC && game == (unsigned int)hl_game() && (count == 150u || count == 256u)
        && count <= HL_MAX && len == HL_FILE_BYTES(count);
}

/* Write the table with the roster it belongs to.  1 when it is on disk (or there was nothing to write over
   another village's file). */
static int hl_publish(void) {
    static unsigned int written[HL_MAX];
    char path[MAX_PATH];
    unsigned int header[3];
    const void *parts[3];
    DWORD sizes[3];
    int i, nothing, slots = hl_slots();
    if (!g_have_roster || !vv_sidecar_gate_ready(&g_gate, g_slot) || !hl_path(g_slot, path)) {
        return 0;
    }
    /* A record nobody holds keeps the identity of the look left on it (a body not yet buried). */
    for (i = 0; i < HL_MAX; ++i) {
        written[i] = g_roster[i] != 0 ? g_roster[i] : (g_look[i] != 0 ? g_look_id[i] : 0u);
    }
    header[0] = HL_MAGIC;
    header[1] = (unsigned int)hl_game();
    header[2] = (unsigned int)slots;
    parts[0] = header;  sizes[0] = sizeof header;
    parts[1] = written; sizes[1] = (DWORD)slots * sizeof(unsigned int);
    parts[2] = g_look;  sizes[2] = (DWORD)slots;
    if (!vv_foreign_before_write(&g_foreign, path, vv_table_any(g_look, slots), &nothing)) {
        return nothing;
    }
    return vv_sidecar_publish(&g_gate, path, parts, sizes, 3);
}

/* Move each look to where its villager is in `live` (mask_follow.h).  1 when the table changed. */
static int hl_follow(const unsigned int *stored_roster, const unsigned int *live, int in_play) {
    static unsigned char moved[HL_MAX];
    static unsigned int moved_id[HL_MAX];
    int slots = hl_slots();
    int changed = in_play
        ? vv_mask_follow_in_play(slots, g_look, stored_roster, stored_roster, live, 0, moved, moved_id)
        : vv_mask_follow(slots, g_look, stored_roster, stored_roster, live, 0, moved, moved_id);
    memcpy(g_look, moved, (size_t)slots);
    memcpy(g_look_id, moved_id, (size_t)slots * sizeof(unsigned int));
    return changed;
}

/* Load the slot's file for the village whose roster is `live`.  The table is cleared FIRST, so every
   failure leaves every look Auto.  1 when the load settled (read, missing, or an invalid file moved aside),
   0 while it must stay pending (blocked: nothing may be written).  *rewrite: the looks moved on the way. */
static int hl_load(int slot, const unsigned int *live, int *rewrite) {
    static unsigned int filesnap[HL_MAX];
    char path[MAX_PATH];
    DWORD got = 0;
    unsigned int count;
    int status, kept, i;
    memset(g_look, 0, sizeof g_look);
    memset(g_look_id, 0, sizeof g_look_id);
    g_foreign = 0;
    *rewrite = 0;
    vv_sidecar_gate_bind(&g_gate, slot);
    if (vv_sidecar_gate_throttled(&g_gate)) {
        return 0;
    }
    if (!hl_path(slot, path)) {
        vv_sidecar_gate_block(&g_gate);
        return 0;
    }
    status = vv_sidecar_load(&g_gate, path, g_file, sizeof g_file, &got, hl_valid, NULL);
    if (status == VV_SIDECAR_LOAD_BLOCKED) {
        return 0;
    }
    if (status != VV_SIDECAR_LOAD_VALID) {
        return 1;                               /* no file (or an invalid one set aside): every look Auto */
    }
    memcpy(&count, g_file + 8, 4);
    kept = (int)count < hl_slots() ? (int)count : hl_slots();
    memset(filesnap, 0, sizeof filesnap);
    memcpy(filesnap, g_file + HL_HEADER, (size_t)kept * sizeof(unsigned int));
    g_foreign = !hl_same_village(filesnap, live);
    if (g_foreign) {
        return 1;                               /* another village's file: kept, never replaced */
    }
    for (i = 0; i < kept; ++i) {
        unsigned char v = g_file[HL_HEADER + count * 4u + (unsigned int)i];
        g_look[i] = v <= 2 ? v : 0;             /* the file is the player's to edit: anything else is Auto */
    }
    *rewrite = hl_follow(filesnap, live, 0);
    return 1;
}

/* Bind the table to the village on screen (throttled: at most every HL_SYNC_MS).  Called on head draws and
   from the Change Appearance window.  1 when the table is that village's. */
static int hl_sync(void) {
    static unsigned int cur[HL_MAX], cur_stable[HL_MAX];
    DWORD now = GetTickCount();
    int slot, renamed, rewrite;
    if (g_have_roster && (DWORD)(now - g_sync_tick) < HL_SYNC_MS) {
        return 1;
    }
    g_sync_tick = now;
    slot = hl_slot_now();
    if (slot <= 0 || hl_roster(cur, cur_stable) == 0) {
        return 0;                               /* no village known: nothing touched */
    }
    if (g_have_roster && slot == g_slot) {
        renamed = vv_roster_renamed_in_play(HL_MAX, g_roster, g_stable, cur, cur_stable);
        if (renamed >= 0) {
            /* A rename: the same villager, the look stays on the record under the new name. */
            g_roster[renamed] = cur[renamed];
            if (g_look[renamed] != 0) {
                g_look_id[renamed] = cur[renamed];
            }
            memcpy(g_stable, cur_stable, sizeof g_stable);
            hl_publish();
            return 1;
        }
        if (hl_same_village(g_roster, cur)) {
            if (memcmp(g_roster, cur, sizeof cur) != 0) {
                /* A birth, a death, or a reload of the same village: each look goes to its villager. */
                hl_follow(g_roster, cur, 1);
                memcpy(g_roster, cur, sizeof cur);
                memcpy(g_stable, cur_stable, sizeof cur_stable);
                hl_publish();
            }
            return 1;
        }
    }
    /* Another village (or the first look): reload, adopt only a settled load. */
    g_have_roster = 0;
    if (!hl_load(slot, cur, &rewrite)) {
        return 0;
    }
    memcpy(g_roster, cur, sizeof cur);
    memcpy(g_stable, cur_stable, sizeof cur_stable);
    g_have_roster = 1;
    g_slot = slot;
    if (rewrite) {
        hl_publish();
    }
    return 1;
}

/* The record's number, or -1 when `record` is not the start of one (the records are one array). */
static int hl_index(const unsigned char *record) {
    const unsigned char *first = hl_record(0);
    const unsigned char *second = hl_record(1);
    size_t stride, offset;
    if (first == NULL || second == NULL || record < first) {
        return -1;
    }
    stride = (size_t)(second - first);
    offset = (size_t)(record - first);
    if (offset % stride != 0 || offset / stride >= (size_t)hl_slots()) {
        return -1;
    }
    return (int)(offset / stride);
}

/* The look of the villager in `record`: 0 Auto, 1 Young, 2 Old (Auto while the village is not known). */
static int hl_get(const unsigned char *record) {
    int i;
    if (record == NULL || !hl_sync()) {
        return 0;
    }
    i = hl_index(record);
    if (i < 0 || g_roster[i] == 0 || g_roster[i] != hl_identity(record)) {
        return 0;
    }
    return g_look[i];
}

/* Keep `look` for the villager in `record`.  1 when the file says so; otherwise nothing changed. */
static int hl_set(const unsigned char *record, int look) {
    unsigned char was;
    unsigned int was_id;
    int i;
    if (record == NULL || look < 0 || look > 2) {
        return 0;
    }
    g_sync_tick = GetTickCount() - HL_SYNC_MS;  /* look at the village now, not a moment ago */
    if (!hl_sync()) {
        return 0;
    }
    i = hl_index(record);
    if (i < 0 || !hl_present(record) || g_roster[i] != hl_identity(record)) {
        return 0;
    }
    was = g_look[i];
    was_id = g_look_id[i];
    g_look[i] = (unsigned char)look;
    g_look_id[i] = look != 0 ? g_roster[i] : 0u;
    if (!hl_publish()) {
        g_look[i] = was;                        /* memory never says what the file does not */
        g_look_id[i] = was_id;
        return 0;
    }
    return 1;
}
