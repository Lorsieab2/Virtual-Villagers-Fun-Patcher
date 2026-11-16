/* The island events' rest periods (v1.35.97, the owner 2026-11-15).  Included by vvfp_story_upgrades.c after
   story_living.inc.

   Rest Periods for Island Events (island_event_rest_periods, in "VVFP Installed Patches.txt"): after a serious
   outcome of a NEW island event (the Isola Grand Event Collection's and the Living Event Engine's), the villager and
   their recorded immediate family -- spouse, parents, children, siblings (story_graph.inc cg_kin) -- are kept out of
   further serious new-event outcomes for a while: 30 in-game days after a serious injury, a disappearance or a
   bereavement, 60 days after a death or a pregnancy loss (for the surviving family).  The build writes a "rest"
   effect (code 25, its days in the effect's first value) beside each such outcome (src/vv_event_content.py); when it
   is made, rs_rest_role keeps "rested until <now + days>" for those villagers.  While a villager rests they are
   never cast in a role of a new event that a rest effect names -- a role that can take a serious outcome
   (cg_eligible).  An in-game day is 86,400 seconds of the game's own clock (the island events' clock, sc_clock).

   THE FILE follows each villager as "VVFP Head Look.dll"'s does (native/vvfp_head_look/head_look_store.inc, the
   same rules: native/shared/mask_follow.h, foreign_sidecar.h, villager_rekey.h, sex_change.h): the save's own
       Virtual Villagers Fun Patcher\Save <S>\Data\Island Events\Island Event Rest - Save <S>.dat
   little-endian:
       u32 magic 'VRS1' (0x31535256), u32 game (1..5), u32 count (150 or 256, the build's records),
       u32 roster[count]   the identity of the LIVING villager in each record when it was written (0 = nobody)
       u32 id[count]       the identity each entry was kept for (0 = none)
       u8  handle[count]   0 none, else the entry's row in the table below (1..255)
       u32 until[255]      row k-1: the game-clock second the rest ends (0 = none)
       u32 traits[255]     row k-1: the story traits (bit 0 "mute": The Quiet Hands; cie-v6-binary.md 32)
   exactly 12 + count * 9 + 255 * 8 bytes.  The handles follow the villagers (vv_mask_follow), the rows stay where
   they are.  The test build keeps the table in memory only. */

#define RS_MAX 256
#define RS_ROWS 255
#define RS_MAGIC 0x31535256u            /* 'V' 'R' 'S' '1' */
#define RS_HEADER 12u
#define RS_FILE_BYTES(count) (RS_HEADER + (DWORD)(count) * 9u + (DWORD)RS_ROWS * 8u)
#define RS_FILE_MAX RS_FILE_BYTES(RS_MAX)
#define RS_SYNC_MS 250u
#define RS_KIND "Island Events"
#define RS_DAY 86400u
#define RS_PATCH "island_event_rest_periods"

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
static unsigned int rs_until[RS_ROWS], rs_traits[RS_ROWS];
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
    char name[] = "Island Event Rest - Save 0.dat";
    if (slot < 1 || slot > 5) {
        return 0;
    }
    name[sizeof "Island Event Rest - Save " - 1] = (char)('0' + slot);
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
    const void *parts[6];
    DWORD sizes[6];
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
    parts[4] = rs_until;      sizes[4] = sizeof rs_until;
    parts[5] = rs_traits;     sizes[5] = sizeof rs_traits;
    if (!vv_foreign_before_write(&rs_foreign, path, rs_any(), &nothing)) {
        return nothing;
    }
    return vv_sidecar_publish(&rs_gate, path, parts, sizes, 6);
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
    memset(rs_until, 0, sizeof rs_until);
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
        memcpy(rs_until, rs_file + RS_HEADER + count * 9u, sizeof rs_until);
        memcpy(rs_traits, rs_file + RS_HEADER + count * 9u + sizeof rs_until, sizeof rs_traits);
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
            rs_until[k - 1] = 0;
            rs_traits[k - 1] = 0;
            rs_handle[i] = (unsigned char)k;
            rs_id[i] = rs_roster[i];
            return k;
        }
    }
    return 0;
}

#ifdef VVFP_TEST
static unsigned int rs_test_now;                 /* the test's game clock (0: the game's own) */
#endif

static unsigned int rs_now(int game) {
    unsigned int now = 0, *timer = NULL;
#ifdef VVFP_TEST
    if (rs_test_now != 0) {
        return rs_test_now;
    }
#endif
    return sc_clock(game, &now, &timer) ? now : 0u;
}

static int rs_on(int game) {
#ifdef VVFP_TEST
    if (rs_test_on >= 0) {
        return rs_test_on;
    }
#endif
    cg_installed_load();
    return cg_installed_state == 1 && cg_installed_has(game, RS_PATCH);
}

/* Whether the villager in `record` rests now (Rest Periods for Island Events on). */
static int rs_resting(int game, const unsigned char *record) {
    int i, slots;
    unsigned int now;
    if (record == NULL || !rs_on(game) || !rs_sync(game)) {
        return 0;
    }
    slots = rs_slots();
    for (i = 0; i < slots && rs_record(i) != record; ++i) {
    }
    if (i >= slots || rs_handle[i] == 0 || rs_roster[i] != rs_identity(record)) {
        return 0;
    }
    now = rs_now(game);
    return rs_until[rs_handle[i] - 1] != 0 && now != 0 && now < rs_until[rs_handle[i] - 1];
}

/* A rest effect made for the villager in record `index`: they and their recorded immediate family rest `days`
   in-game days from now (a longer rest already kept stays). */
static void rs_rest_role(const ce_adapter *a, int game, int index, int days) {
    unsigned int now, until;
    int k, changed = 0, slots;
    if (!rs_on(game) || days <= 0 || days > 3650 || !rs_sync(game) || (now = rs_now(game)) == 0) {
        return;
    }
    until = now + (unsigned int)days * RS_DAY;
    cg_kin_read(a, game);
    slots = rs_slots();
    for (k = 0; k < slots && k < CE_MAX_RECORDS; ++k) {
        int row;
        if (rs_roster[k] == 0
            || (k != index && !cg_kin(game, CG_REL_SPOUSE, index, k) && !cg_kin(game, CG_REL_PARENT, k, index)
                && !cg_kin(game, CG_REL_CHILD, k, index) && !cg_kin(game, CG_REL_SIBLING, index, k))) {
            continue;
        }
        row = rs_row_of(k);
        if (row != 0 && rs_until[row - 1] < until) {
            rs_until[row - 1] = until;
            changed = 1;
        }
    }
    if (changed) {
        (void)rs_publish();
    }
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

/* Whether the villager in `record` has story trait `trait` (cie-v6-binary.md 32), whatever is ticked. */
static int rs_has_trait(int game, const unsigned char *record, unsigned int trait) {
    int row = rs_row_of_record(game, record);
    return row != 0 && (rs_traits[row - 1] & trait) != 0;
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

#ifdef VVFP_TEST
/* ---- Test build only ---------------------------------------------------------------------------------------- */

/* Rest Periods forced on (1) / off (0) / as installed (-1); then whether record `index` of `game` rests now, and
   (out, when not NULL) the second its rest ends (0 none) and the game clock now. */
__declspec(dllexport) int __stdcall VvfpStoryProbeRest(int on, int game, int index, unsigned int *out) {
    const ce_adapter *a = ce_adapter_for(game);
    const unsigned char *r = a != NULL && index >= 0 && index < a->record_count ? a->record(index) : NULL;
    rs_test_on = on;
    rs_test_now = on >= 0 ? 5000000u : 0u;      /* a game clock of its own: the emulator runs no game clock */
    rs_sync_tick = GetTickCount() - RS_SYNC_MS;
    if (out != NULL) {
        out[0] = 0;
        out[1] = rs_now(game);
        if (r != NULL && rs_sync(game) && index < RS_MAX && rs_handle[index] != 0) {
            out[0] = rs_until[rs_handle[index] - 1];
        }
    }
    return rs_resting(game, r);
}
#endif
