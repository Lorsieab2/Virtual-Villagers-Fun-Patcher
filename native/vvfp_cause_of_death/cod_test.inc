/* For the TEST build only: drive the tables, the graves file and the
   roster without a game image.  Setup takes the place of VvfpCauseInstall
   (no site is written); the others call the same routines the hooks call.
   Included by vvfp_cause_of_death.c under VVFP_TEST. */

__declspec(dllexport) int __stdcall VvfpCauseTestSetup(int game, const void *host, void *table) {
    if (game < 1 || game > 5) {
        return 0;
    }
    g_game = game;
    g_host = (const cod_host *)host;
    test_table = (unsigned char *)table;
    install_state = 1;
    return 1;
}

__declspec(dllexport) void __stdcall VvfpCauseTestDied(int index, int cause) {
    unsigned char *record = cod_record(index);
    if (record != NULL && g_game <= 2) {
        cod_died(record, cause);
    }
}

/* A burial into grave `slot` (-1: the graveyard was full). */
__declspec(dllexport) void __stdcall VvfpCauseTestBuried(int index, int slot) {
    if (g_game <= 2) {
        cod_buried(index, slot >= 0, slot);
    }
}

__declspec(dllexport) void __stdcall VvfpCauseTestDecayed(int index) {
    unsigned char *record = cod_record(index);
    if (record != NULL && g_game <= 2) {
        cod_decayed(record);
    }
}

__declspec(dllexport) void __stdcall VvfpCauseTestArrived(int index) {
    roster_arrived(index);
}

/* The player typed `text` into grave `slot`'s epitaph box and pressed Done
   (A New Home). */
__declspec(dllexport) void __stdcall VvfpCauseTestEpitaph(int slot, const char *text) {
    char box[EPITAPH_TEXT];
    if (g_game == 1) {
        memset(box, 0, sizeof box);
        lstrcpynA(box, text, EPITAPH_TEXT);
        vv1_commit_epitaph(slot, cod_grave(slot), box);
    }
}

/* A successful save of `slot`: what the hook after the save call does. */
__declspec(dllexport) void __stdcall VvfpCauseTestSaved(int slot) {
    roster_reconcile(slot);
}

/* Whether VvfpCauseArmSave succeeds here: 1 yes, -1 no. */
__declspec(dllexport) void __stdcall VvfpCauseTestArm(int outcome) {
    test_arm = outcome;
}

/* The same, with the save buffer: what an armed or installed save hook does
   (cod_save_done), including naming the village. */
__declspec(dllexport) void __stdcall VvfpCauseTestSaveDone(int slot, const void *save_buffer) {
    cod_save_done(slot, save_buffer);
}

/* The entry the popup would draw for grave `slot`: 1 with its cause and
   epitaph when it is recorded for the grave the game holds there now. */
__declspec(dllexport) int __stdcall VvfpCauseTestGrave(int slot, int *cause, int *epitaph) {
    const unsigned char *grave;
    const struct cod_entry *entry;
    if (g_game > 2) {
        return 0;
    }
    grave = cod_grave(slot);
    entry = cod_grave_entry(slot, grave);
    if (entry == NULL) {
        return 0;
    }
    *cause = entry->cause;
    *epitaph = entry->custom ? 0x100 : entry->epitaph;
    return 1;
}

/* The Secret City's, The Tree of Life's and New Believers' Roster of the
   Dead (and The Secret City's gravestones) at the harness's own addresses
   (cod_backfill.inc). */
__declspec(dllexport) void __stdcall VvfpCauseTestRoster(void *entries, void *gravestones) {
    test_roster = (unsigned char *)entries;
    test_gravestones = (unsigned char *)gravestones;
}

/* A creator made `index` (cod_roster_sites.inc's roster_created) on the
   path whose marker value is `marker` (0: none): the stack the hook sees is
   built with that marker -- and the one it needs -- at their own places. */
__declspec(dllexport) void __stdcall VvfpCauseTestCreated(int index, unsigned int marker) {
    static unsigned int stack[0x100];
    unsigned int regs[9];
    unsigned int site = 0;
    const struct arrival_marker *table = NULL;
    int count = 0;
    int k;
    memset(stack, 0, sizeof stack);
    memset(regs, 0, sizeof regs);
    regs[R_ESP] = (unsigned int)(uintptr_t)stack;
    arrival_markers(&table, &count);
    for (k = 0; k < count && marker != 0u; ++k) {
        if (table[k].value == marker) {
            site = table[k].site;
            stack[table[k].offset / 4] = marker;
            if (table[k].need_offset != 0u) {
                stack[table[k].need_offset / 4] = table[k].need_value;
            }
            break;
        }
    }
    if (index >= 0 && index < RECORDS_MAX && !temporary[index]) {
        roster_arrived(index);
        arrival_created(index, site, regs);
    }
}

/* The arrivals' part of the per-frame tick (cod_arrivals.inc). */
__declspec(dllexport) void __stdcall VvfpCauseTestArrivalTick(void) {
    arrival_tick();
}

/* Whether A New Home's Birth records are written: 1 yes, -1 no, 0 look. */
__declspec(dllexport) void __stdcall VvfpCauseTestVv1Births(int outcome) {
    test_vv1_births = outcome;
}

/* A departure the hooks report (a burial, a removal, a disappearance). */
__declspec(dllexport) void __stdcall VvfpCauseTestDeparted(int index) {
    roster_departed(index, cod_record(index));
}
