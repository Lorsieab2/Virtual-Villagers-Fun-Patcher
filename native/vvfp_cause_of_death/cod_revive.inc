/* Revive snapshots: every villager's complete record, kept at their death or disappearance (the owner,
   2026-11-25, all five games: "every single detail of every villager should be preserved so that the
   resurrect upgrade can perfectly recreate them").  Included by vvfp_cause_of_death.c after cod_roster.inc.

   WHEN.  roster_departed, which every death and disappearance reaches at the moment the game frees the record
   -- a burial, an unburied body's removal (the later three, A New Home and The Lost Children alike), a vanishing
   (cod_gone.inc), a Custom Island Event's death or vanishing (cod_cie_words.inc), a Heathen who died among the
   Heathens ("VVFP Heathen Aging.dll", VvfpCauseDiedAmongHeathens) -- the latest moment the record still holds the
   person: the bytes each game's own save keeps of them, and what the patcher's own files keep for them (the head
   look, the gender presentation, the cosmetic mask, the story traits, A New Home's parents), are copied then
   (native/shared/revive_snapshot.h has the fields).  A body revived by Custom Island Event's Revive is never
   freed, so it leaves no snapshot; deaths in the load-time catch-up and in a Time Warp or Time Skip are buried
   through the same sites later, and are kept then.

   KEPT.  In memory until the next save of the village, then added to this save slot's file
   (revive_snapshot.h THE FILE), so the file matches the save: a session quit without saving keeps nothing, and
   a departure made while another slot's village was loaded is never written into this one.  A file this build
   cannot read is set aside unread (sidecar_io.h) and a new one started; nothing is ever written into a save.
   Start Over deletes it with the village (VvfpCauseVillageReset).

   Only the Revive Buried/Disappeared Villagers row reads it ("VVFP Story Upgrades.dll"); the Deaths log and the
   statistics never do, so nothing is counted twice. */
#include "revive_snapshot.h"

#define RVS_PENDING 512                   /* departures between two saves (the oldest go past it) */

static vv_rs_entry *rvs_pending;         /* process heap: RVS_PENDING entries */
static int rvs_pending_slot[RVS_PENDING];
static int rvs_pending_count;
static unsigned char *rvs_file;           /* process heap: a whole file, VV_RS_MAX entries */
static struct {
    int slot;
    vv_sidecar_gate gate;
} rvs;

static int rvs_validate(const unsigned char *data, DWORD length, void *context) {
    (void)context;
    return vv_rs_file_valid(data, length, g_game);
}

static int rvs_path(int slot, char *out) {
    char stem[64];
    wsprintfA(stem, "Virtual Villagers %d Revive Snapshots", g_game);
    return cod_data_path(out, VV_RS_FOLDER, stem, slot);
}

typedef int (__stdcall *rvs_record_fn)(int game, const void *record);
typedef int (__stdcall *rvs_vv1_query_fn)(int index, int *out);

#ifdef VVFP_TEST
/* TEST build: the companions' exports the harness stands in for (NULL: the real lookup). */
static FARPROC (*rvs_test_export)(const char *dll, const char *name);
#endif

/* An export of a companion already in the game (never loaded from here), or NULL. */
static FARPROC rvs_export(const char *dll, const char *name) {
    HMODULE module;
#ifdef VVFP_TEST
    if (rvs_test_export != NULL) {
        return rvs_test_export(dll, name);
    }
#endif
    module = GetModuleHandleA(dll);
    return module != NULL ? GetProcAddress(module, name) : NULL;
}

/* EACH COMPANION'S EXPORT, FOUND ONCE (v1.35.102).  The per-frame tick asks RVS_PER_TICK records a frame, and looking
   every export up by name each time (GetModuleHandleA + GetProcAddress, five or six a record) cost New Believers
   about 0.3 ms a frame at 256 villagers.  No VVFP DLL is ever unloaded (none calls FreeLibrary), so an address found
   stays good for the game's life.  One not found yet -- its companion not installed, or not loaded yet -- is looked
   for again every RVS_RETRY lookups on the tick, and always on a departure (rvs_fresh), so a departure asks exactly
   what it asked before. */
enum { RVS_HEAD_LOOK, RVS_PRESENTATION, RVS_ORIGINAL, RVS_TRAITS, RVS_VV1_PARENTS, RVS_MASKS, RVS_LOOKUPS };
#define RVS_RETRY 64u
static FARPROC rvs_found[RVS_LOOKUPS];
static HMODULE rvs_mask_module;
static unsigned int rvs_misses[RVS_LOOKUPS];
static int rvs_fresh;

static int rvs_look_again(int which) {
    return rvs_fresh || rvs_misses[which]++ % RVS_RETRY == 0u;
}

static FARPROC rvs_export_at(int which, const char *dll, const char *name) {
#ifdef VVFP_TEST
    if (rvs_test_export != NULL) {
        return rvs_test_export(dll, name);   /* the harness's stand-ins, never kept */
    }
#endif
    if (rvs_found[which] == NULL && rvs_look_again(which)) {
        rvs_found[which] = rvs_export(dll, name);
    }
    return rvs_found[which];
}

static int rvs_masks_loaded(void) {
    if (rvs_mask_module == NULL && rvs_look_again(RVS_MASKS)) {
        rvs_mask_module = GetModuleHandleA(VV_MASK_ORIGINS[g_game]);
    }
    return rvs_mask_module != NULL;
}

/* What the patcher's own files keep for the villager in `record` (index `index`), into `e`. */
static void rvs_sidecars(vv_rs_entry *e, int index, const unsigned char *record) {
    rvs_record_fn get;
    int mask;
    get = (rvs_record_fn)(void *)rvs_export_at(RVS_HEAD_LOOK, "VVFP Head Look.dll", "VvfpHeadLookGet");
    if (get != NULL) {
        int look = get(g_game, record);
        if (look >= 0 && look <= 2) {
            e->head_look = look;
            e->flags |= VV_RS_HEAD_LOOK;
        }
    }
    get = (rvs_record_fn)(void *)rvs_export_at(RVS_PRESENTATION, "VVFP Gender Presentation.dll",
                                                "VvfpGenderPresentationGet");
    if (get != NULL) {
        int on = get(g_game, record);
        if (on == 0 || on == 1) {
            e->presentation = on;
            e->flags |= VV_RS_PRESENTATION;
        }
    }
    if (rvs_masks_loaded()) {
        mask = vv_mask_value(g_game, record);
        e->mask = mask;
        e->flags |= VV_RS_MASK;
    }
    {
        typedef int (__stdcall *rvs_original_fn)(int game, const void *record, int *head, int *body, int *mask);
        rvs_original_fn original = (rvs_original_fn)(void *)rvs_export_at(RVS_ORIGINAL, "VVFP Original Look.dll",
                                                                          "VvfpOriginalLookGet");
        int head = -1, body = -1, kept_mask = -1;
        if (original != NULL && original(g_game, record, &head, &body, &kept_mask) == 1) {
            e->original_head = head;
            e->original_body = body;
            e->original_mask = kept_mask;
            e->flags |= VV_RS_ORIGINAL;
        }
    }
    get = (rvs_record_fn)(void *)rvs_export_at(RVS_TRAITS, "VVFP Story Upgrades.dll", "VvfpStoryTraitsOf");
    if (get != NULL) {
        e->traits = (unsigned int)get(g_game, record);
        e->flags |= VV_RS_TRAITS;
    }
    if (g_game == 1 && index >= 0) {
        rvs_vv1_query_fn query = (rvs_vv1_query_fn)(void *)rvs_export_at(RVS_VV1_PARENTS, "VVFP VV1 Parentage.dll",
                                                                          "Vv1ParentageQuery");
        int looks[4] = { -1, -1, -1, -1 };
        char father[ROSTER_PARENT_NAME], mother[ROSTER_PARENT_NAME];
        int named = vv1_parent_names(index, father, mother, (int)ROSTER_PARENT_NAME);
        if (query != NULL && query(index, looks)) {
            memcpy(e->parent_looks, looks, sizeof looks);
        }
        if (named) {
            lstrcpynA(e->father, father, VV_RS_NAME);
            lstrcpynA(e->mother, mother, VV_RS_NAME);
            e->flags |= VV_RS_PARENTS;
        }
    }
}

/* WHAT THE PATCHER'S FILES KEEP, ASKED WHILE THE VILLAGER IS STILL THERE (Codex, PR #880).  Every departure reaches
   roster_departed once the game has freed the record -- A New Home's and The Lost Children's burial after the store
   that frees it (cod_vv12.inc), the later three's with the presence byte cleared, a vanishing, a Heathen who died
   among the Heathens -- and the companions answer only for a villager still in their roster: "VVFP Original
   Look.dll"'s ol_get, for one, finds no freed record.  So the answers are taken while the record is present: the
   per-frame tick (revive_tick) asks for a few records each frame (RVS_PER_TICK, every record within
   slots / RVS_PER_TICK frames), bodies awaiting burial included, and keeps them by record with who they were
   (rvs_who); a departure takes the record's kept answers when they are its villager's, else asks there and then
   (a record still present). */
#define RVS_PER_TICK 4

typedef struct {
    unsigned int who;                 /* rvs_who of the villager asked for; 0 none */
    unsigned int flags;               /* VV_RS_HEAD_LOOK .. VV_RS_ORIGINAL */
    int head_look, presentation, mask;
    unsigned int traits;
    int original_head, original_body, original_mask;
    int parent_looks[4];
    char father[VV_RS_NAME], mother[VV_RS_NAME];
} rvs_side;

static rvs_side rvs_kept[RECORDS_MAX];
static int rvs_cursor;


/* Who a record holds, for the kept answers: the name, sex, head and body (never 0). */
static unsigned int rvs_who(const unsigned char *record) {
    unsigned int h = cod_name_hash(record) ^ (cod_looks_hash(record) * 16777619u);
    return h != 0 ? h : 1u;
}

static void rvs_side_from(rvs_side *s, const vv_rs_entry *e, unsigned int who) {
    s->who = who;
    s->flags = e->flags;
    s->head_look = e->head_look;
    s->presentation = e->presentation;
    s->mask = e->mask;
    s->traits = e->traits;
    s->original_head = e->original_head;
    s->original_body = e->original_body;
    s->original_mask = e->original_mask;
    memcpy(s->parent_looks, e->parent_looks, sizeof s->parent_looks);
    memcpy(s->father, e->father, VV_RS_NAME);
    memcpy(s->mother, e->mother, VV_RS_NAME);
}

static void rvs_side_to(vv_rs_entry *e, const rvs_side *s) {
    e->flags |= s->flags;
    e->head_look = s->head_look;
    e->presentation = s->presentation;
    e->mask = s->mask;
    e->traits = s->traits;
    e->original_head = s->original_head;
    e->original_body = s->original_body;
    e->original_mask = s->original_mask;
    memcpy(e->parent_looks, s->parent_looks, sizeof e->parent_looks);
    memcpy(e->father, s->father, VV_RS_NAME);
    memcpy(e->mother, s->mother, VV_RS_NAME);
}

/* The answers for record `index` (present) asked now and kept. */
static void rvs_keep(int index, const unsigned char *record) {
    vv_rs_entry e;
    vv_rs_begin(&e, g_game);
    rvs_sidecars(&e, index, record);
    rvs_side_from(&rvs_kept[index], &e, rvs_who(record));
}

/* The per-frame tick (VvfpCauseTick): RVS_PER_TICK records' answers asked and kept, round the table. */
static void revive_tick(void) {
    int k, slots = (int)REC[g_game].slots;
    for (k = 0; k < RVS_PER_TICK && slots > 0; ++k) {
        int index;
        const unsigned char *record;
        rvs_cursor = (rvs_cursor + 1) % (slots < RECORDS_MAX ? slots : RECORDS_MAX);
        index = rvs_cursor;
        record = cod_record(index);
        if (record != NULL && rec_present(record) && !rec_lookalike(record)) {
            rvs_keep(index, record);
        }
    }
}

/* A departure (roster_departed): the record `index` as the game frees it. */
static void revive_note(int index, const unsigned char *record) {
    vv_rs_entry *e;
    FILETIME now;
    if (record == NULL || rec_lookalike(record) || g_game < 1 || g_game > 5) {
        return;
    }
    if (rvs_pending == NULL) {
        rvs_pending = (vv_rs_entry *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY,
                                               (SIZE_T)RVS_PENDING * sizeof(vv_rs_entry));
        if (rvs_pending == NULL) {
            return;
        }
    }
    if (rvs_pending_count == RVS_PENDING) {
        memmove(rvs_pending, rvs_pending + 1, (RVS_PENDING - 1) * sizeof(vv_rs_entry));
        memmove(rvs_pending_slot, rvs_pending_slot + 1, (RVS_PENDING - 1) * sizeof(int));
        --rvs_pending_count;
    }
    e = &rvs_pending[rvs_pending_count];
    vv_rs_begin(e, g_game);
    if (!vv_rs_take(e, record)) {
        return;
    }
    GetSystemTimeAsFileTime(&now);
    e->when_lo = now.dwLowDateTime;
    e->when_hi = now.dwHighDateTime;
    /* The answers kept while they were present (the companions no longer answer for a freed record), else asked now. */
    if (index >= 0 && index < RECORDS_MAX && rvs_kept[index].who != 0u && rvs_kept[index].who == rvs_who(record)) {
        rvs_side_to(e, &rvs_kept[index]);
    } else if (rec_present(record)) {
        rvs_fresh = 1;                /* a departure looks every companion up afresh (rvs_export_at) */
        rvs_sidecars(e, index, record);
        rvs_fresh = 0;
    }
    if (index >= 0 && index < RECORDS_MAX) {
        rvs_kept[index].who = 0u;     /* the record is free: whoever takes it next is asked afresh */
    }
    vv_rs_seal(e);
    rvs_pending_slot[rvs_pending_count] = install_state == 1 ? cod_slot() : 0;
    ++rvs_pending_count;
}

/* A save of `slot`: its departures added to its file.  Those noted for another slot's village are dropped (that
   village was left without a save); a file that cannot be read keeps them for the next save. */
static void revive_saved(int slot) {
    char path[MAX_PATH];
    DWORD length = 0;
    unsigned int count = 0, keep;
    int result, i, mine = 0;
    const void *parts[1];
    DWORD sizes[1];
    for (i = 0; i < rvs_pending_count; ++i) {
        mine += rvs_pending_slot[i] == slot || rvs_pending_slot[i] <= 0;
    }
    if (mine == 0) {
        rvs_pending_count = 0;
        return;
    }
    if (slot != rvs.slot) {
        rvs.slot = slot;
        vv_sidecar_gate_bind(&rvs.gate, 0x480 + g_game * 16 + slot);
    }
    if (vv_sidecar_gate_throttled(&rvs.gate) || !rvs_path(slot, path)) {
        return;
    }
    if (rvs_file == NULL) {
        rvs_file = (unsigned char *)HeapAlloc(GetProcessHeap(), 0,
                                              VV_RS_HEADER + (SIZE_T)(VV_RS_MAX + RVS_PENDING) * VV_RS_ENTRY_BYTES);
        if (rvs_file == NULL) {
            return;
        }
    }
    result = vv_sidecar_load(&rvs.gate, path, rvs_file, VV_RS_HEADER + (DWORD)VV_RS_MAX * VV_RS_ENTRY_BYTES,
                             &length, rvs_validate, NULL);
    if (result == VV_SIDECAR_LOAD_BLOCKED) {
        return;                           /* kept in memory for the next save */
    }
    if (result == VV_SIDECAR_LOAD_VALID) {
        count = ((const unsigned int *)rvs_file)[3];
    }
    for (i = 0; i < rvs_pending_count; ++i) {
        if (rvs_pending_slot[i] == slot || rvs_pending_slot[i] <= 0) {
            memcpy(rvs_file + VV_RS_HEADER + count * VV_RS_ENTRY_BYTES, &rvs_pending[i], VV_RS_ENTRY_BYTES);
            ++count;
        }
    }
    keep = count > (unsigned int)VV_RS_MAX ? (unsigned int)VV_RS_MAX : count;
    if (keep < count) {                   /* the oldest go: the newest deaths are always kept */
        memmove(rvs_file + VV_RS_HEADER, rvs_file + VV_RS_HEADER + (count - keep) * VV_RS_ENTRY_BYTES,
                (SIZE_T)keep * VV_RS_ENTRY_BYTES);
    }
    ((unsigned int *)rvs_file)[0] = VV_RS_MAGIC;
    ((unsigned int *)rvs_file)[1] = VV_RS_VERSION;
    ((unsigned int *)rvs_file)[2] = (unsigned int)g_game;
    ((unsigned int *)rvs_file)[3] = keep;
    parts[0] = rvs_file;
    sizes[0] = VV_RS_HEADER + keep * VV_RS_ENTRY_BYTES;
    if (vv_sidecar_publish(&rvs.gate, path, parts, sizes, 1)) {
        rvs_pending_count = 0;
        COD_COUNT(published);
    }
}

/* The current village's snapshots not written yet (Codex, PR #880): a villager who died or vanished since the last
   save of `slot` has a Death or Disappeared record already (the parentage exporter writes it then) but a snapshot
   only here until the next save.  Revive ("VVFP Story Upgrades.dll", found by GetModuleHandleA) reads them through
   this and merges them with the file, these winning.  Copies up to `max_entries` (VV_RS_ENTRY_BYTES each, oldest
   first) into `out` (NULL: only counted); the number there is.  Another slot's departures are never given. */
__declspec(dllexport) int __stdcall VvfpCauseReviveSnapshots(int game, int slot, void *out, int max_entries) {
    int i, n = 0;
    if (game != g_game || slot < 1 || slot > 5 || rvs_pending == NULL) {
        return 0;
    }
    for (i = 0; i < rvs_pending_count; ++i) {
        if (rvs_pending_slot[i] == slot || rvs_pending_slot[i] <= 0) {
            if (out != NULL && n < max_entries) {
                memcpy((unsigned char *)out + (size_t)n * VV_RS_ENTRY_BYTES, &rvs_pending[i], VV_RS_ENTRY_BYTES);
            }
            ++n;
        }
    }
    return out != NULL && n > max_entries ? max_entries : n;
}
/* Start Over erased `slot`: its snapshots go with the village. */
static void revive_reset(int slot) {
    char path[MAX_PATH];
    if (slot >= 1 && rvs_path(slot, path)) {
        DeleteFileA(path);
    }
    rvs_pending_count = 0;
    memset(rvs_kept, 0, sizeof rvs_kept);
    if (slot == rvs.slot) {
        vv_sidecar_gate_bind(&rvs.gate, -1);
        rvs.slot = 0;
    }
}
