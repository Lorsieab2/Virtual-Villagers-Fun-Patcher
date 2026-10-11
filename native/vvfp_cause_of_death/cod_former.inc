/* New Believers' former Heathens: who was converted, and which mask they
   wore (native/shared/former_heathens.h has the file and why the game cannot
   say it).  Included by vvfp_cause_of_death.c, after cod_backfill.inc
   (cod_data_path) and before cod_arrivals.inc, whose tick sees the
   conversions.

   While the tick sees a record as a Heathen it keeps the mask that Heathen
   wears (vv_former_kind_of: the game's own mask choice, 0x4728C6); the tick
   that sees the same villager a believer -- the conversion 0x4668B0, or any
   other path through the faction setter 0x466880 -- files that mask for
   the villager's identity in the slot's Former Heathens file.  A Heathen the
   tick never saw as one (converted before this build ran) is not filed:
   Repair Saves & Logs asks the player about those. */

static signed char former_kind_seen[RECORDS_MAX];   /* -1: not seen as a Heathen */
static int former_ready;

static struct {
    int slot;
    vv_sidecar_gate gate;
    char path[MAX_PATH];
} former;

static unsigned char former_buffer[VV_FORMER_FILE_MAX];

static int former_validate(const unsigned char *data, DWORD length, void *context) {
    (void)context;
    return vv_former_validate(data, length);
}

/* New Believers' record: the identity custom titles and former Heathens are
   kept by (custom_titles.h: name, likes, dislikes). */
#define FORMER_NAME 0x1B9Cu
#define FORMER_NAME_CAP 0x19u
#define FORMER_LIKES 0x1F5Cu
#define FORMER_DISLIKES 0x1F68u
#define FORMER_SLOTS 3u

/* File `kind` for the villager in `record`, replacing any entry of the same
   identity; the oldest entry gives way when the file is full. */
static void former_file(const unsigned char *record, int kind) {
    int slot = cod_slot();
    DWORD length = 0;
    int result;
    unsigned int count = 0, kept = 0, i, identity;
    const void *parts[1];
    DWORD sizes[1];
    if (slot <= 0 || kind < VV_FORMER_BLUE || kind > VV_FORMER_CHIEF) {
        return;
    }
    if (slot != former.slot) {
        former.slot = slot;
        former.path[0] = '\0';
        vv_sidecar_gate_bind(&former.gate, 0x300 + slot);
    }
    if (former.path[0] == '\0' && !cod_data_path(former.path, "Former Heathens", "Former Heathens", slot)) {
        return;
    }
    result = vv_sidecar_load(&former.gate, former.path, former_buffer, sizeof former_buffer, &length,
                             former_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;
    }
    if (result == VV_SIDECAR_LOAD_VALID) {
        count = vv_former_u32(former_buffer + 12);
    }
    identity = vv_title_identity(record, FORMER_NAME, FORMER_NAME_CAP, FORMER_LIKES, FORMER_DISLIKES,
                                 FORMER_SLOTS);
    for (i = 0; i < count; ++i) {
        unsigned char *e = former_buffer + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
        if (vv_former_u32(e) == identity) {
            continue;
        }
        memmove(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY, e, VV_FORMER_ENTRY);
        ++kept;
    }
    if (kept == VV_FORMER_MAX) {
        memmove(former_buffer + VV_FORMER_HEADER, former_buffer + VV_FORMER_HEADER + VV_FORMER_ENTRY,
                (VV_FORMER_MAX - 1) * VV_FORMER_ENTRY);
        --kept;
    }
    memcpy(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY, &identity, 4);
    memcpy(former_buffer + VV_FORMER_HEADER + kept * VV_FORMER_ENTRY + 4, &kind, 4);
    ++kept;
    ((unsigned int *)former_buffer)[0] = VV_FORMER_MAGIC;
    ((unsigned int *)former_buffer)[1] = VV_FORMER_VERSION;
    ((unsigned int *)former_buffer)[2] = 5u;
    ((unsigned int *)former_buffer)[3] = kept;
    parts[0] = former_buffer;
    sizes[0] = VV_FORMER_HEADER + kept * VV_FORMER_ENTRY;
    (void)vv_sidecar_publish(&former.gate, former.path, parts, sizes, 1);
}

/* FORMER HEATHENS FOLLOW THEIR VILLAGER (v1.35.68).  The file keeps each
   former Heathen by name, likes and dislikes; an island event, the Custom
   Island Event or an upgrade that changes a villager's likes or dislikes
   left the entry under the old identity, and the villager was no longer
   called a Former Heathen.  So every tick looks at the roster, and when a
   villager changed identity in place -- same record, name, sex and age, and
   nobody moved (native/shared/identity_in_place.h) -- or was renamed (the
   same rule as the masks' and titles': one record changed, its sex, likes
   and dislikes unchanged), their entry is carried to the new identity.  An
   identity two entries carry stays nobody's (vv_former_lookup): nothing is
   guessed. */
static unsigned int former_roster[RECORDS_MAX];
static unsigned int former_roster_stable[RECORDS_MAX];
static unsigned int former_roster_keep[RECORDS_MAX];
static int former_roster_age[RECORDS_MAX];
static int former_roster_known;

static unsigned int former_identity(const unsigned char *record) {
    return vv_title_identity(record, FORMER_NAME, FORMER_NAME_CAP, FORMER_LIKES, FORMER_DISLIKES,
                             FORMER_SLOTS);
}

/* Bind the gate and path to `slot`; 0 when the file has no place. */
static int former_bind(int slot) {
    if (slot <= 0) {
        return 0;
    }
    if (slot != former.slot) {
        former.slot = slot;
        former.path[0] = '\0';
        vv_sidecar_gate_bind(&former.gate, 0x300 + slot);
    }
    return former.path[0] != '\0' || cod_data_path(former.path, "Former Heathens", "Former Heathens", slot);
}

/* Carry every entry of identity `from` to `to` in the slot's file. */
static void former_rekey(unsigned int from, unsigned int to) {
    int slot = cod_slot();
    DWORD length = 0;
    unsigned int count, i;
    int changed = 0;
    const void *parts[1];
    DWORD sizes[1];
    if (from == to || !former_bind(slot)
        || vv_sidecar_load(&former.gate, former.path, former_buffer, sizeof former_buffer, &length,
                           former_validate, NULL) != VV_SIDECAR_LOAD_VALID) {
        return;
    }
    count = vv_former_u32(former_buffer + 12);
    for (i = 0; i < count; ++i) {
        unsigned char *e = former_buffer + VV_FORMER_HEADER + i * VV_FORMER_ENTRY;
        if (vv_former_u32(e) == from) {
            memcpy(e, &to, 4);
            changed = 1;
        }
    }
    if (changed) {
        parts[0] = former_buffer;
        sizes[0] = VV_FORMER_HEADER + count * VV_FORMER_ENTRY;
        (void)vv_sidecar_publish(&former.gate, former.path, parts, sizes, 1);
    }
}

/* What a rename leaves of the identity: the likes, dislikes and sex. */
static unsigned int former_stable(const unsigned char *record) {
    unsigned int h = vv_title_identity(record, FORMER_NAME, 0u, FORMER_LIKES, FORMER_DISLIKES, FORMER_SLOTS);
    h = (h ^ (unsigned int)*(const int *)(record + REC[g_game].sex)) * 16777619u;
    return h ? h : 1u;
}

/* Every tick (New Believers): the roster now against the last look. */
static void former_follow(const unsigned char *records) {
    static unsigned int now[RECORDS_MAX], now_stable[RECORDS_MAX], now_keep[RECORDS_MAX];
    static int now_age[RECORDS_MAX];
    static unsigned char same[RECORDS_MAX];
    int n = (int)REC[g_game].slots < RECORDS_MAX ? (int)REC[g_game].slots : RECORDS_MAX;
    int i, anyone = 0;
    for (i = 0; i < n; ++i) {
        const unsigned char *record = records + (size_t)i * REC[g_game].stride;
        now[i] = now_stable[i] = now_keep[i] = 0;
        now_age[i] = 0;
        if (roster_member(record)) {
            now[i] = former_identity(record);
            now_stable[i] = former_stable(record);
            now_keep[i] = vv_identity_keep(record, FORMER_NAME, FORMER_NAME_CAP, REC[g_game].sex);
            now_age[i] = rec_age(record);
            anyone = 1;
        }
    }
    if (former_roster_known && anyone) {
        int renamed = vv_roster_renamed(n, former_roster, former_roster_stable, now, now_stable);
        if (renamed >= 0) {
            former_rekey(former_roster[renamed], now[renamed]);
        } else if (vv_roster_changed_in_place(n, former_roster, former_roster_keep, former_roster_age, now,
                                              now_keep, now_age, same) > 0) {
            for (i = 0; i < n; ++i) {
                if (same[i]) {
                    former_rekey(former_roster[i], now[i]);
                }
            }
        }
    }
    memcpy(former_roster, now, sizeof(unsigned int) * (size_t)n);
    memcpy(former_roster_stable, now_stable, sizeof(unsigned int) * (size_t)n);
    memcpy(former_roster_keep, now_keep, sizeof(unsigned int) * (size_t)n);
    memcpy(former_roster_age, now_age, sizeof(int) * (size_t)n);
    former_roster_known = anyone;
}

/* The tick's view of record `index`: `heathen` as it is now, `was_heathen`
   as the last tick saw it (faction_seen). */
static void former_tick(int index, const unsigned char *record, int heathen, int was_heathen) {
    if (!former_ready) {
        memset(former_kind_seen, -1, sizeof former_kind_seen);
        former_ready = 1;
    }
    if (heathen) {
        former_kind_seen[index] = (signed char)vv_former_kind_of(record);
        return;
    }
    if (was_heathen == 1 && former_kind_seen[index] >= 0) {
        former_file(record, former_kind_seen[index]);
    }
    former_kind_seen[index] = -1;
}

static void former_forget(int index) {
    if (former_ready && index >= 0 && index < RECORDS_MAX) {
        former_kind_seen[index] = -1;
    }
}

static void former_reset(int slot) {
    if (slot == former.slot) {
        vv_sidecar_gate_bind(&former.gate, -1);
        former.slot = 0;
        former.path[0] = '\0';
    }
    former_roster_known = 0;
    if (former_ready) {
        memset(former_kind_seen, -1, sizeof former_kind_seen);
    }
}
