/* A New Home and The Lost Children: the burial, the decay of an unburied
   body, the grave popup, and the per-frame tick.  Included by
   vvfp_cause_of_death.c. */

/* ---- The burial ----------------------------------------------------------

   The burial frees the dead villager's record and writes the grave in the
   same step; these sites run only when a free grave slot was found (with all
   50 in use the stock game writes no grave, and nothing is carried).

     VV1 0x448FF9  `mov ebx, 0x33` -- the grave just written ends the slot
                   loop.  ebp = slot * 0x2C, [esi-0x2EC] = the dead
                   villager's index, edi = the villager array.
     VV2 0x465063  `mov ecx,[edi+0x60]; imul ecx,ecx,0xE48C` -- the first
                   write into the free slot.  ecx = the slot, [edi+0x60] =
                   the dead villager's index, esi = the pool.

   The statistics row's Villagers Buried hooks sit on the record-freeing
   store before both (VV1 0x448F65, VV2 0x46503B) and are not touched. */
static void cod_buried(unsigned char *record, int slot) {
    struct cod_event e;
    int index = cod_index_of(record);
    unsigned int fingerprint;
    if (index < 0 || slot < 0 || slot >= GRAVES) {
        return;
    }
    COD_COUNT(burials);
    fingerprint = cod_record_fingerprint(record);
    if (!(skeletons[index].valid && skeletons[index].fingerprint == fingerprint)
        && seen_alive[index] != 0 && seen_alive[index] == cod_name_hash(record)) {
        /* Died and was buried before any tick saw the body. */
        cod_died(record, CAUSE_UNKNOWN);
    }
    e.type = EVENT_BURIAL;
    e.index = index;
    e.grave = slot;
    if (skeletons[index].valid && skeletons[index].fingerprint == fingerprint) {
        e.entry = skeletons[index];
        COD_COUNT(graves_set);
    } else {
        /* A body that was already lying when this was installed: no cause
           is known.  A New Home still gets the epitaph its data decides. */
        e.entry.fingerprint = fingerprint;
        e.entry.cause = CAUSE_NONE;
        e.entry.epitaph = (unsigned char)(g_game == 1 ? cod_epitaph(record) : EPITAPH_NONE);
        e.entry.valid = (unsigned char)(e.entry.epitaph != EPITAPH_NONE);
        e.entry.reserved = 0;
    }
    seen_alive[index] = 0;
    cod_event(&e);
}

static void __cdecl vv1_buried(unsigned char *array, int index, int slot_offset) {
    if (index < 0 || index >= RECORDS) {
        return;
    }
    cod_buried(array + (size_t)index * GEO[1].stride, slot_offset / (int)GEO[1].grave_stride);
}

static void __cdecl vv2_buried(unsigned char *pool, int index, int slot) {
    if (index < 0 || index >= RECORDS) {
        return;
    }
    cod_buried(pool + (size_t)index * GEO[2].stride, slot);
}

/* ---- An unburied body decays (240 minutes; no grave) ---------------------

     VV1 0x42E9C3  `mov byte [edi+eax+0x28], 0`
     VV2 0x43B78D  `mov byte [eax+edi+0x30], 0` */
static void __cdecl cod_decayed(unsigned char *record) {
    struct cod_event e;
    int index = cod_index_of(record);
    if (index < 0) {
        return;
    }
    seen_alive[index] = 0;
    if (!skeletons[index].valid) {
        return;
    }
    memset(&e, 0, sizeof e);
    e.type = EVENT_DECAY;
    e.index = index;
    cod_event(&e);
}

/* ---- The grave popup ----------------------------------------------------- */

/* The games' text routine is __thiscall (ecx = renderer, five stack
   arguments, `ret 0x14`).  C has no __thiscall, but __fastcall puts its
   first argument in ecx, its second in edx (unused by the routine) and the
   rest on the stack for the callee to pop -- the same call. */
typedef void (__fastcall *text_fn)(void *renderer, int unused_edx, const char *text, int x,
                                   int y, void *font, int zero);

/* The cause one line under "Age" (+0xB4), the epitaph in A New Home between
   "Here Lies" (+0x23) and "Job" (+0x6E), where The Lost Children shows its
   own.  Same text routine, font and centre as the popup's own lines. */
static void cod_grave_lines(const unsigned char *grave, int slot, void *renderer, int x, int top,
                            unsigned int draw, unsigned int font_global) {
    const struct cod_entry *entry;
    void *font = *(void **)(uintptr_t)font_global;
    if (grave == NULL || slot < 0 || slot >= GRAVES
        || *(const int *)(grave + GEO[g_game].grave_age) == 0) {
        return;
    }
    entry = &graves[slot];
    if (!entry->valid || entry->fingerprint != cod_grave_fingerprint(grave)) {
        return;                       /* a grave from before: nothing extra */
    }
    if (entry->epitaph != EPITAPH_NONE && entry->epitaph < EPITAPH_COUNT) {
        char line[64];
        wsprintfA(line, "\"%s\"", EPITAPHS[entry->epitaph]);
        ((text_fn)(uintptr_t)draw)(renderer, 0, line, x, top + 0x46, font, 0);
        COD_COUNT(draws);
    }
    if (entry->cause != CAUSE_NONE) {
        ((text_fn)(uintptr_t)draw)(renderer, 0, cod_cause_words(entry->cause), x, top + 0xD2, font, 0);
        COD_COUNT(draws);
    }
}

/* VV1 0x436440, the popup's Draw: ebx = popup ([+0x60] slot, [+0x74]
   manager, [+0x18] top), esi = renderer, ebp = centre x; text 0x4094C0,
   font [0x48B608]. */
static void __cdecl vv1_grave_draw(unsigned char *popup, void *renderer, int x) {
    int slot = *(const int *)(popup + 0x60);
    unsigned char *manager = *(unsigned char **)(popup + 0x74);
    const unsigned char *grave = manager != NULL && slot >= 0 && slot < GRAVES
        ? manager + GEO[1].graves + (size_t)slot * GEO[1].grave_stride : NULL;
    cod_grave_lines(grave, slot, renderer, x, *(const int *)(popup + 0x18), 0x4094C0u, 0x48B608u);
}

/* VV2 0x444490: ebp = panel ([+0x60] slot, [+0x78] world, [+0x18] top),
   esi = renderer, ebx = centre x; text 0x4096B0, font [0x499F18]. */
static void __cdecl vv2_grave_draw(unsigned char *panel, void *renderer, int x) {
    int slot = *(const int *)(panel + 0x60);
    unsigned char *world = *(unsigned char **)(panel + 0x78);
    const unsigned char *grave = world != NULL && slot >= 0 && slot < GRAVES
        ? world + GEO[2].graves + (size_t)slot * GEO[2].grave_stride : NULL;
    cod_grave_lines(grave, slot, renderer, x, *(const int *)(panel + 0x18), 0x4096B0u, 0x499F18u);
}

/* ---- The stubs ----------------------------------------------------------- */

static const unsigned int vv1_bury_resume = 0x448FFEu, vv2_bury_resume = 0x46506Cu;
static const unsigned int vv1_decay_resume = 0x42E9C8u, vv2_decay_resume = 0x43B792u;
static const unsigned int vv2_draw_resume = 0x444796u;

static __declspec(naked) void vv1_bury_stub(void) {
    __asm {
        pushad
        push ebp
        push dword ptr [esi - 0x2EC]
        push edi
        call vv1_buried
        add esp, 12
        popad
        mov ebx, 0x33
        jmp dword ptr [vv1_bury_resume]
    }
}

static __declspec(naked) void vv2_bury_stub(void) {
    __asm {
        pushad
        push ecx
        push dword ptr [edi + 0x60]
        push esi
        call vv2_buried
        add esp, 12
        popad
        mov ecx, dword ptr [edi + 0x60]
        imul ecx, ecx, 0xE48C
        jmp dword ptr [vv2_bury_resume]
    }
}

static __declspec(naked) void vv1_decay_stub(void) {
    __asm {
        pushad
        lea ecx, [edi + eax]
        push ecx
        call cod_decayed
        add esp, 4
        popad
        mov byte ptr [edi + eax + 0x28], 0
        jmp dword ptr [vv1_decay_resume]
    }
}

static __declspec(naked) void vv2_decay_stub(void) {
    __asm {
        pushad
        lea ecx, [eax + edi]
        push ecx
        call cod_decayed
        add esp, 4
        popad
        mov byte ptr [eax + edi + 0x30], 0
        jmp dword ptr [vv2_decay_resume]
    }
}

/* VV1: the stub takes over the popup Draw's epilogue (pops, add esp,0xCC,
   ret) after its own last line. */
static __declspec(naked) void vv1_draw_stub(void) {
    __asm {
        pushad
        push ebp
        push esi
        push ebx
        call vv1_grave_draw
        add esp, 12
        popad
        pop edi
        pop esi
        pop ebp
        pop ebx
        add esp, 0xCC
        ret
    }
}

static __declspec(naked) void vv2_draw_stub(void) {
    __asm {
        pushad
        push ebx
        push esi
        push ebp
        call vv2_grave_draw
        add esp, 12
        popad
        mov ecx, dword ptr [ebp + 0x84]
        jmp dword ptr [vv2_draw_resume]
    }
}

static const unsigned char VV1_BURY_STOCK[5] = { 0xBB, 0x33, 0x00, 0x00, 0x00 };
static const unsigned char VV2_BURY_STOCK[9] = { 0x8B, 0x4F, 0x60, 0x69, 0xC9, 0x8C, 0xE4, 0x00, 0x00 };
static const unsigned char VV1_DECAY_STOCK[5] = { 0xC6, 0x44, 0x07, 0x28, 0x00 };
static const unsigned char VV2_DECAY_STOCK[5] = { 0xC6, 0x44, 0x38, 0x30, 0x00 };
static const unsigned char VV1_DRAW_STOCK[10] = { 0x5F, 0x5E, 0x5D, 0x5B, 0x81, 0xC4, 0xCC, 0x00, 0x00, 0x00 };
static const unsigned char VV2_DRAW_STOCK[6] = { 0x8B, 0x8D, 0x84, 0x00, 0x00, 0x00 };

#define VV12_FIXED 3
static const struct cod_site VV12_FIXED_SITES[3][VV12_FIXED] = {
    { { 0 } },
    { { 0x448FF9u, VV1_BURY_STOCK, 5, vv1_bury_stub },
      { 0x42E9C3u, VV1_DECAY_STOCK, 5, vv1_decay_stub },
      { 0x436700u, VV1_DRAW_STOCK, 10, vv1_draw_stub } },
    { { 0x465063u, VV2_BURY_STOCK, 9, vv2_bury_stub },
      { 0x43B78Du, VV2_DECAY_STOCK, 5, vv2_decay_stub },
      { 0x444790u, VV2_DRAW_STOCK, 6, vv2_draw_stub } },
};

/* All or nothing: every site must hold its stock bytes before any is
   written, so a build where another patch took one of them is left alone
   entirely rather than half-recorded. */
static int vv12_install(void) {
    int count;
    const struct death_site *sites = cod_sites(&count);
    int i;
    for (i = 0; i < count; ++i) {
        if (!cod_bytes_are(sites[i].va, sites[i].stock, sites[i].length)) {
            return 0;
        }
    }
    for (i = 0; i < VV12_FIXED; ++i) {
        if (!cod_site_is_stock(&VV12_FIXED_SITES[g_game][i])) {
            return 0;
        }
    }
    stub_page = cod_build_stubs(sites, count);
    if (stub_page == NULL) {
        return 0;
    }
    for (i = 0; i < count; ++i) {
        if (!cod_write_jmp(sites[i].va, sites[i].length, stub_page + i * STUB_BYTES)) {
            return 0;
        }
    }
    for (i = 0; i < VV12_FIXED; ++i) {
        if (!cod_install_site(&VV12_FIXED_SITES[g_game][i])) {
            return 0;
        }
    }
    return 1;
}

/* ---- The tick ------------------------------------------------------------ */

static void vv12_tick(void) {
    const struct game_geometry *g = &GEO[g_game];
    int slot = g_host != NULL && g_host->slot != NULL ? g_host->slot() : 0;
    unsigned char *array;
    int i;
    if (slot < 1 || slot > 5) {
        slot = 0;
    }
    cod_bind(slot);
    array = cod_array();
    if (array != NULL) {
        for (i = 0; i < RECORDS; ++i) {
            unsigned char *record = array + (size_t)i * g->stride;
            if (record[g->present] == 0 || (g->totem != 0u && record[g->totem] != 0)) {
                seen_alive[i] = 0;
                continue;
            }
            if (*(const int *)(record + g->health) > 0) {
                seen_alive[i] = cod_name_hash(record);
                continue;
            }
            /* A body.  Seen alive on an earlier frame, with no site having
               reported it: an island event, the Gong, the Custom Island
               Event, an edit.  A body never seen alive is one the village
               was loaded with. */
            if (seen_alive[i] != 0 && seen_alive[i] == cod_name_hash(record)) {
                COD_COUNT(unhooked);
                cod_died(record, CAUSE_UNKNOWN);
            }
            seen_alive[i] = 0;
        }
    }
    if (store.loaded) {
        journal_count = 0;
        cod_publish();
    }
}
