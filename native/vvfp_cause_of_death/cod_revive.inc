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

/* An export of a companion already in the game (never loaded from here), or NULL. */
static FARPROC rvs_export(const char *dll, const char *name) {
    HMODULE module = GetModuleHandleA(dll);
    return module != NULL ? GetProcAddress(module, name) : NULL;
}

/* What the patcher's own files keep for the villager in `record` (index `index`), into `e`. */
static void rvs_sidecars(vv_rs_entry *e, int index, const unsigned char *record) {
    rvs_record_fn get;
    int mask;
    get = (rvs_record_fn)(void *)rvs_export("VVFP Head Look.dll", "VvfpHeadLookGet");
    if (get != NULL) {
        int look = get(g_game, record);
        if (look >= 0 && look <= 2) {
            e->head_look = look;
            e->flags |= VV_RS_HEAD_LOOK;
        }
    }
    get = (rvs_record_fn)(void *)rvs_export("VVFP Gender Presentation.dll", "VvfpGenderPresentationGet");
    if (get != NULL) {
        int on = get(g_game, record);
        if (on == 0 || on == 1) {
            e->presentation = on;
            e->flags |= VV_RS_PRESENTATION;
        }
    }
    if (GetModuleHandleA(VV_MASK_ORIGINS[g_game]) != NULL) {
        mask = vv_mask_value(g_game, record);
        e->mask = mask;
        e->flags |= VV_RS_MASK;
    }
    get = (rvs_record_fn)(void *)rvs_export("VVFP Story Upgrades.dll", "VvfpStoryTraitsOf");
    if (get != NULL) {
        e->traits = (unsigned int)get(g_game, record);
        e->flags |= VV_RS_TRAITS;
    }
    if (g_game == 1 && index >= 0) {
        rvs_vv1_query_fn query = (rvs_vv1_query_fn)(void *)rvs_export("VVFP VV1 Parentage.dll", "Vv1ParentageQuery");
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
    rvs_sidecars(e, index, record);
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

/* Start Over erased `slot`: its snapshots go with the village. */
static void revive_reset(int slot) {
    char path[MAX_PATH];
    if (slot >= 1 && rvs_path(slot, path)) {
        DeleteFileA(path);
    }
    rvs_pending_count = 0;
    if (slot == rvs.slot) {
        vv_sidecar_gate_bind(&rvs.gate, -1);
        rvs.slot = 0;
    }
}
