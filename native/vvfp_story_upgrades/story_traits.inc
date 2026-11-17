/* The new island events' story traits (v1.35.97, the owner 2026-11-15).  Included by vvfp_story_upgrades.c after
   story_living.inc.

   "The Quiet Hands" (Inner Life 3, il003_*) gives the villager it casts the story trait "mute" (a "trait" effect,
   code 26, cie-v6-binary.md 32), kept whatever is ticked; a role whose words have them speak (role byte 13 bit 7)
   never takes a villager with it (cg_eligible).

   THE FILE is kept beside the save, never in it, and follows each villager as "VVFP Head Look.dll"'s looks do
   (native/vvfp_head_look/head_look_store.inc, the same rules: native/shared/mask_follow.h, foreign_sidecar.h,
   villager_rekey.h, sex_change.h); it belongs to the village whose living roster it shares a strict majority with:
       Virtual Villagers Fun Patcher\Save <S>\Data\Island Events\Island Event Story Traits - Save <S>.dat
   little-endian:
       u32 magic 'VST1' (0x31545356), u32 game (1..5), u32 count (150 or 256, the build's records),
       u32 roster[count]   the identity of the LIVING villager in each record when it was written (0 = nobody)
       u32 id[count]       the identity each entry was kept for (0 = none)
       u8  handle[count]   0 none, else the entry's row in the table below (1..255)
       u32 traits[255]     row k-1: the story traits (bit 0 "mute")
   exactly 12 + count * 9 + 255 * 4 bytes.  The handles follow the villagers (vv_mask_follow), the rows stay where
   they are.  The test build keeps the table in memory only. */

#define RS_MAX 256
#define RS_ROWS 255
#define RS_MAGIC 0x31545356u            /* 'V' 'S' 'T' '1' */
#define RS_HEADER 12u
#define RS_FILE_BYTES(count) (RS_HEADER + (DWORD)(count) * 9u + (DWORD)RS_ROWS * 4u)
#define RS_FILE_MAX RS_FILE_BYTES(RS_MAX)
#define RS_SYNC_MS 250u
#define RS_KIND "Island Events"

/* The record fields the entries are kept by: the head looks' identity (name, sex, the parents' names; A New Home
   the family number) and the byte that says a record is held -- the same offsets as vvfp_head_look.c. */
typedef struct {
    unsigned int present, name, name_bytes, sex, father, mother, family;
} rs_layout;

static const rs_layout RS_LAYOUT[6] = {
    { 0 },
    { 0x28u,   0x370u,  0x1Cu, 0x350u,  0u,      0u,      0x36Cu },
    { 0x30u,   0x564u,  0x18u, 0x538u,  0x57Du,  0x596u,  0u },
    { 0xF10u,  0xDD4u,  0x19u, 0xDC8u,  0xDF8u,  0xE11u,  0u },
    { 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u },
    { 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u },
};

static int rs_game;                              /* the game the hooks below answer for */
static unsigned char rs_handle[RS_MAX];
static unsigned int rs_id[RS_MAX], rs_roster[RS_MAX], rs_stable_ids[RS_MAX];
static unsigned int rs_traits[RS_ROWS];
static int rs_have_roster, rs_slot, rs_sync_tried, rs_foreign;
static DWORD rs_sync_tick;
static vv_sidecar_gate rs_gate;
static unsigned char rs_file[RS_FILE_MAX];

static int rs_slots(void) {
    const ce_adapter *a = ce_adapter_for(rs_game);
    if (a == NULL) {
        return 0;
    }
    return a->record_count < RS_MAX ? a->record_count : RS_MAX;
}

static const unsigned char *rs_record(int i) {
    const ce_adapter *a = ce_adapter_for(rs_game);
    if (a == NULL || i < 0 || i >= rs_slots()) {
        return NULL;
    }
    return a->record(i);
}

static int rs_present(const unsigned char *r) {
    unsigned char held = r[RS_LAYOUT[rs_game].present];
    return rs_game == 1 ? held == 1 : held != 0;
}

static unsigned int rs_text(unsigned int h, const unsigned char *text, unsigned int capacity) {
    unsigned int k;
    for (k = 0; k < capacity && text[k]; ++k) {
        h = (h ^ text[k]) * 16777619u;
    }
    return h;
}

static unsigned int rs_mix(unsigned int h, const unsigned char *at) {
    int k;
    for (k = 0; k < 4; ++k) {
        h = (h ^ at[k]) * 16777619u;
    }
    return h;
}

static unsigned int rs_stable(const unsigned char *r) {
    const rs_layout *l = &RS_LAYOUT[rs_game];
    unsigned int h = rs_mix(2166136261u, r + l->sex);
    if (l->family != 0) {
        h = rs_mix(h, r + l->family);
    } else {
        h = rs_text(h, r + l->father, 0x19u);
        h = (h ^ 0xFEu) * 16777619u;
        h = rs_text(h, r + l->mother, 0x19u);
        h = (h ^ 0xFDu) * 16777619u;
    }
    return h ? h : 1u;
}

static unsigned int rs_identity(const unsigned char *r) {
    const rs_layout *l = &RS_LAYOUT[rs_game];
    unsigned int h = rs_text(2166136261u, r + l->name, l->name_bytes);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ rs_stable(r)) * 16777619u;
    return h ? h : 1u;
}

static int rs_roster_now(unsigned int *ids, unsigned int *stable) {
    int i, n = 0, slots = rs_slots();
    memset(ids, 0, RS_MAX * sizeof(unsigned int));
    memset(stable, 0, RS_MAX * sizeof(unsigned int));
    for (i = 0; i < slots; ++i) {
        const unsigned char *r = rs_record(i);
        if (r != NULL && rs_present(r)) {
            ids[i] = rs_identity(r);
            stable[i] = rs_stable(r);
            ++n;
        }
    }
    return n;
}

/* The same village: a STRICT majority of the smaller roster is shared, each villager wherever they are. */
static int rs_same_village(const unsigned int *a, const unsigned int *b) {
    int i, j, la = 0, lb = 0, n = 0, need;
    for (i = 0; i < RS_MAX; ++i) {
        la += a[i] != 0;
        lb += b[i] != 0;
    }
    need = la < lb ? la : lb;
    if (need == 0) {
        return 0;
    }
    for (i = 0; i < RS_MAX; ++i) {
        for (j = 0; a[i] != 0 && j < RS_MAX; ++j) {
            if (b[j] == a[i]) {
                ++n;
                break;
            }
        }
    }
    return n >= need / 2 + 1;
}

#ifndef VVFP_TEST
static int rs_path(int slot, char *out) {
    char name[] = "Island Event Story Traits - Save 0.dat";
    if (slot < 1 || slot > 5) {
        return 0;
    }
    name[sizeof "Island Event Story Traits - Save " - 1] = (char)('0' + slot);
    return vv_ps_data_file_a(out, RS_KIND, name, VV_PS_RESERVE);
}

static int rs_valid(const unsigned char *data, DWORD len, void *ctx) {
    unsigned int magic, game, count;
    (void)ctx;
    if (len < RS_HEADER) {
        return 0;
    }
    memcpy(&magic, data, 4);
    memcpy(&game, data + 4, 4);
    memcpy(&count, data + 8, 4);
    return magic == RS_MAGIC && game == (unsigned int)rs_game && (count == 150u || count == 256u)
           && count <= RS_MAX && len == RS_FILE_BYTES(count);
}
#endif

/* Whether any villager holds an entry (a table with nothing in it is never written over another village's file). */
static int rs_any(void) {
    return vv_table_any(rs_handle, rs_slots());
}

/* Write the table with the roster it belongs to.  1 when it is on disk (the test build: always). */
static int rs_publish(void) {
#ifdef VVFP_TEST
    return rs_have_roster;
#else
    static unsigned int ids[RS_MAX];
    char path[MAX_PATH];
    unsigned int header[3];
    const void *parts[5];
    DWORD sizes[5];
    int i, nothing, slots = rs_slots();
    if (!rs_have_roster || !vv_sidecar_gate_ready(&rs_gate, rs_slot) || !rs_path(rs_slot, path)) {
        return 0;
    }
    for (i = 0; i < RS_MAX; ++i) {
        ids[i] = rs_handle[i] != 0 ? rs_id[i] : 0u;
    }
    header[0] = RS_MAGIC;
    header[1] = (unsigned int)rs_game;
    header[2] = (unsigned int)slots;
    parts[0] = header;        sizes[0] = sizeof header;
    parts[1] = rs_roster;     sizes[1] = (DWORD)slots * sizeof(unsigned int);
    parts[2] = ids;           sizes[2] = (DWORD)slots * sizeof(unsigned int);
    parts[3] = rs_handle;     sizes[3] = (DWORD)slots;
    parts[4] = rs_traits;     sizes[4] = sizeof rs_traits;
    if (!vv_foreign_before_write(&rs_foreign, path, rs_any(), &nothing)) {
        return nothing;
    }
    return vv_sidecar_publish(&rs_gate, path, parts, sizes, 5);
#endif
}

/* Each handle to where its villager is in `live`. */
static int rs_follow(const unsigned int *stored, const unsigned int *stored_roster, const unsigned int *live,
                     int in_play) {
    static unsigned char moved[RS_MAX];
    static unsigned int moved_id[RS_MAX];
    int slots = rs_slots();
    int changed = in_play
        ? vv_mask_follow_in_play(slots, rs_handle, stored, stored_roster, live, 0, moved, moved_id)
        : vv_mask_follow(slots, rs_handle, stored, stored_roster, live, 0, moved, moved_id);
    memcpy(rs_handle, moved, (size_t)slots);
    memcpy(rs_id, moved_id, (size_t)slots * sizeof(unsigned int));
    return changed;
}

/* Load the slot's file for the village `live` (cleared first: every failure leaves nobody resting).  1 when the load
   settled, 0 while it must stay pending.  *rewrite: the entries moved on the way. */
static int rs_load(int slot, const unsigned int *live, int *rewrite) {
    memset(rs_handle, 0, sizeof rs_handle);
    memset(rs_id, 0, sizeof rs_id);
    memset(rs_traits, 0, sizeof rs_traits);
    rs_foreign = 0;
    *rewrite = 0;
#ifdef VVFP_TEST
    (void)slot;
    (void)live;
    return 1;
#else
    {
        static unsigned int filesnap[RS_MAX], fileids[RS_MAX];
        char path[MAX_PATH];
        DWORD got = 0;
        unsigned int count;
        int status, kept, i, renamed;
        vv_sidecar_gate_bind(&rs_gate, slot);
        if (vv_sidecar_gate_throttled(&rs_gate)) {
            return 0;
        }
        if (!rs_path(slot, path)) {
            vv_sidecar_gate_block(&rs_gate);
            return 0;
        }
        status = vv_sidecar_load(&rs_gate, path, rs_file, sizeof rs_file, &got, rs_valid, NULL);
        if (status == VV_SIDECAR_LOAD_BLOCKED) {
            return 0;
        }
        if (status != VV_SIDECAR_LOAD_VALID) {
            return 1;
        }
        memcpy(&count, rs_file + 8, 4);
        kept = (int)count < rs_slots() ? (int)count : rs_slots();
        memset(filesnap, 0, sizeof filesnap);
        memset(fileids, 0, sizeof fileids);
        memcpy(filesnap, rs_file + RS_HEADER, (size_t)kept * sizeof(unsigned int));
        memcpy(fileids, rs_file + RS_HEADER + count * 4u, (size_t)kept * sizeof(unsigned int));
        (void)vv_sex_log_note(rs_game, slot, rs_slots(), rs_record, rs_present, rs_identity);
        renamed = vv_rekey_apply(slot, filesnap, kept) + vv_rekey_apply(slot, fileids, kept);
        rs_foreign = !rs_same_village(filesnap, live);
        if (rs_foreign) {
            return 1;                               /* another village's file: kept, never replaced */
        }
        for (i = 0; i < kept; ++i) {
            rs_handle[i] = rs_file[RS_HEADER + count * 8u + (unsigned int)i];
            if (rs_handle[i] == 0) {
                fileids[i] = 0;
            }
        }
        memcpy(rs_traits, rs_file + RS_HEADER + count * 9u, sizeof rs_traits);
        *rewrite = rs_follow(fileids, filesnap, live, 0) || renamed > 0;
        return 1;
    }
#endif
}

/* Bind the table to the village on screen (throttled).  1 when it is that village's. */
static int rs_sync(int game) {
    static unsigned int cur[RS_MAX], cur_stable[RS_MAX];
    DWORD now = GetTickCount();
    int slot, renamed, rewrite;
    if (game != rs_game) {
        rs_game = game;
        rs_have_roster = 0;
        rs_sync_tried = 0;
    }
    if ((rs_have_roster || rs_sync_tried) && (DWORD)(now - rs_sync_tick) < RS_SYNC_MS) {
        return rs_have_roster;
    }
    rs_sync_tick = now;
    rs_sync_tried = 1;
    slot = story_current_slot(game);
    if (slot <= 0 || rs_roster_now(cur, cur_stable) == 0) {
        return 0;
    }
    if (rs_have_roster && slot == rs_slot) {
        renamed = vv_roster_renamed_in_play(RS_MAX, rs_roster, rs_stable_ids, cur, cur_stable);
        if (renamed >= 0) {
            rs_roster[renamed] = cur[renamed];
            if (rs_handle[renamed] != 0) {
                rs_id[renamed] = cur[renamed];
            }
            memcpy(rs_stable_ids, cur_stable, sizeof rs_stable_ids);
            (void)rs_publish();
            return 1;
        }
        if (rs_same_village(rs_roster, cur)) {
            if (memcmp(rs_roster, cur, sizeof cur) != 0) {
                (void)rs_follow(rs_roster, rs_roster, cur, 1);
                memcpy(rs_roster, cur, sizeof cur);
                memcpy(rs_stable_ids, cur_stable, sizeof cur_stable);
                (void)rs_publish();
            }
            return 1;
        }
    }
    rs_have_roster = 0;
    if (!rs_load(slot, cur, &rewrite)) {
        return 0;
    }
    memcpy(rs_roster, cur, sizeof cur);
    memcpy(rs_stable_ids, cur_stable, sizeof cur_stable);
    rs_have_roster = 1;
    rs_slot = slot;
    if (rewrite) {
        (void)rs_publish();
    }
    return 1;
}

/* The row (1..255) of record `i`, a new one when it has none (0: the table is full). */
static int rs_row_of(int i) {
    static unsigned char used[RS_ROWS + 1];
    int k;
    if (rs_handle[i] != 0) {
        return rs_handle[i];
    }
    memset(used, 0, sizeof used);
    for (k = 0; k < rs_slots(); ++k) {
        used[rs_handle[k]] = 1;
    }
    for (k = 1; k <= RS_ROWS; ++k) {
        if (!used[k]) {
            rs_traits[k - 1] = 0;
            rs_handle[i] = (unsigned char)k;
            rs_id[i] = rs_roster[i];
            return k;
        }
    }
    return 0;
}

/* The record's row in the table when it holds the villager in `record`, else 0. */
static int rs_row_of_record(int game, const unsigned char *record) {
    int i, slots;
    if (record == NULL || !rs_sync(game)) {
        return 0;
    }
    slots = rs_slots();
    for (i = 0; i < slots && rs_record(i) != record; ++i) {
    }
    if (i >= slots || rs_handle[i] == 0 || rs_roster[i] != rs_identity(record)) {
        return 0;
    }
    return rs_handle[i];
}

/* Whether the villager in `record` dislikes talking, in a game whose list has the word (The Lost Children .. New
   Believers; A New Home has none): the owner (2026-11-17), "dislike talking if it exists = mute" -- however they
   came by it (born with it, any game action, any event). */
static int rs_dislikes_talking(int game, const unsigned char *record) {
    const ce_adapter *a = ce_adapter_for(game);
    const int *dislikes;
    int k, word;
    if (a == NULL || record == NULL || (word = cg_preference(a, CG_MUTE_WORD)) < 0) {
        return 0;
    }
    dislikes = (const int *)(record + a->off_dislikes);
    for (k = 0; k < a->pref_slots; ++k) {
        if (dislikes[k] == word) {
            return 1;
        }
    }
    return 0;
}

/* Whether the villager in `record` has story trait `trait` (cie-v6-binary.md 32), whatever is ticked: "mute" also
   when they dislike talking (rs_dislikes_talking). */
static int rs_has_trait(int game, const unsigned char *record, unsigned int trait) {
    int row;
    if ((trait & CG_TRAIT_MUTE) && rs_dislikes_talking(game, record)) {
        return 1;
    }
    row = rs_row_of_record(game, record);
    return row != 0 && (rs_traits[row - 1] & trait) != 0;
}

/* A villager's sex changed (native/shared/sex_change.h; VvfpVillagerSexChanged): the identity holds the sex, so the
   villager's entry is carried to the identity they have now and the file written -- otherwise the next look would
   take the record for someone else's and drop the trait.  1 when anything was carried. */
static int rs_sex_changed(int game, const unsigned char *record, const unsigned char *before) {
    int i, slots;
    unsigned int was;
    if (record == NULL || before == NULL || game != rs_game || !rs_have_roster) {
        return 0;
    }
    slots = rs_slots();
    for (i = 0; i < slots && rs_record(i) != record; ++i) {
    }
    if (i >= slots) {
        return 0;
    }
    was = rs_identity(before);
    if (rs_roster[i] != was) {
        return 0;
    }
    rs_roster[i] = rs_identity(record);
    rs_stable_ids[i] = rs_stable(record);
    if (rs_handle[i] == 0) {
        return 0;
    }
    rs_id[i] = rs_roster[i];
    (void)rs_publish();
    return 1;
}

/* A trait effect made for the villager in record `index`: they keep `trait` from now on (the file follows them). */
static void rs_set_trait(int game, int index, unsigned int trait) {
    int row;
    if (trait == 0 || !rs_sync(game) || index < 0 || index >= rs_slots() || rs_roster[index] == 0) {
        return;
    }
    row = rs_row_of(index);
    if (row != 0 && (rs_traits[row - 1] & trait) != trait) {
        rs_traits[row - 1] |= trait;
        (void)rs_publish();
    }
}
