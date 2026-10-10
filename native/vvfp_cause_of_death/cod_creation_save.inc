/* THE LOGS AT VILLAGE CREATION (the owner: "all logs and dat files to be
   written as soon as a new save file is created in a slot and if the player
   presses start over").  Every log is written from a hook on the game's own
   save, and three games make their new village's first save with nobody in
   it -- live, v1.35.66:

     A New Home      the creation's save-all (0x41BF70) skips the village
                     slot until the village's start time [manager+0x9E1C] is
                     set (0x41BF7D); the reset 0x41C000 zeroes it and the
                     start-or-skip scene's button (0x41EC40) sets it.  The
                     first village of a fresh folder wrote no log at all
                     until the first quit.
     The Tree of Life  the name dialog (0x4193F0), a new player (0x418B80)
     New Believers     and Start Over (0x41F3E0 / 0x424930) reset the village
                     and save it at once, before the founder screen (state 3)
                     picks the founders; the start-game step (VV4 0x41FEF0,
                     VV5 0x4259D0) sets the start time and nothing saves after
                     it.  The files were created empty and the founders were
                     logged only at the first quit (or the 600 s autosave).

   So once a new village's founders are made (the arrivals this companion
   holds as "founder", cod_arrivals.inc) and the village has started, the
   game is asked for ONE save through its own path: its autosave field --
   the next-autosave time in seconds, compared unsigned every frame (VV1
   0x41BFC0, VV4 0x41F1A0, VV5 0x424660) -- is set to 0, so on its next frame
   the game runs its normal save-all (settings, the slot, its backup) and
   re-arms the field for 600 s itself.  Every save hook then writes what it
   writes at any save: the founders' Arrived records, the Population, the
   History and the Statistics.  One aligned dword store; nothing else is
   changed, and no game routine is called from here.

   Once per village (slot and start time).  A New Home also seeds founders
   ahead of a load (the slot list, 0x41D160 / 0x41D260), so there the save
   is asked only for a village that started in the last few minutes of its
   own clock (0x402F70, seconds): a loaded village is never saved for it.
   A village whose start time is never set (A New Home's skip path 0x41F480)
   is left to the game's own quit save, as before.  The Lost Children and The
   Secret City save after their seeding already (VV2 0x41AC4D, VV3 0x41BA4D). */

#define CREATION_RECENT_SECONDS 300u

static const struct {
    unsigned int manager;       /* the save manager singleton's address */
    unsigned int slot;          /* its current slot */
    unsigned int state;         /* its scene */
    unsigned int main_state;    /* the village's own scene */
    unsigned int autosave;      /* the next autosave time */
    unsigned int start_field;   /* the start time: a manager field ... */
    unsigned int start_global;  /* ... or a global */
} CREATION_SAVE[6] = {
    { 0 },
    { 0x48AEDCu, 0xABE4u, 0xACB4u, 1u, 0xADECu, 0x9E1Cu, 0u },
    { 0 },
    { 0 },
    { 0x4CB51Cu, 0x17114u, 0x171A8u, 0u, 0x171C0u, 0u, 0x4D6DE0u },
    { 0x4DACE0u, 0x17D80u, 0x17E1Cu, 0u, 0x17E34u, 0u, 0x51D358u },
};

static int creation_saved_slot;          /* the village asked for: slot ... */
static unsigned int creation_saved_start; /* ... and start time */

#ifdef VVFP_TEST
static unsigned char *test_creation_manager;   /* a harness's stand-in manager */
static unsigned int test_creation_start;       /* ... its start global */
static unsigned int test_creation_now;         /* ... and A New Home's clock */
#endif

static unsigned char *creation_manager(void) {
#ifdef VVFP_TEST
    if (test_creation_manager != NULL) {
        return test_creation_manager;
    }
    return NULL;
#else
    return *(unsigned char *const volatile *)(uintptr_t)CREATION_SAVE[g_game].manager;
#endif
}

static unsigned int creation_start(const unsigned char *manager) {
    if (CREATION_SAVE[g_game].start_field != 0u) {
        return *(const volatile unsigned int *)(manager + CREATION_SAVE[g_game].start_field);
    }
#ifdef VVFP_TEST
    return test_creation_start;
#else
    return *(const volatile unsigned int *)(uintptr_t)CREATION_SAVE[g_game].start_global;
#endif
}

typedef unsigned int (__fastcall *creation_clock_fn)(void *self, void *unused_edx);

static unsigned int creation_vv1_now(unsigned char *manager) {
#ifdef VVFP_TEST
    (void)manager;
    return test_creation_now;
#else
    return ((creation_clock_fn)(uintptr_t)0x402F70u)(manager, NULL);
#endif
}

/* Whether a founder made for a new village waits for its first save. */
static int creation_founders_pending(int slot) {
    int i;
    for (i = 0; i < RECORDS_MAX && (unsigned int)i < REC[g_game].slots; ++i) {
        if (arrivals[i].founder && (arrivals[i].state == ARRIVAL_MADE || arrivals[i].state == ARRIVAL_PENDING)
            && report_counts(arrivals[i].tag, slot)) {
            return 1;
        }
    }
    return 0;
}

/* Every frame (VvfpCauseTick).  Returns 1 when it asked for the save. */
static int creation_save_tick(void) {
    unsigned char *manager;
    unsigned int start;
    int slot;
    if (g_game < 1 || g_game > 5 || CREATION_SAVE[g_game].manager == 0u) {
        return 0;
    }
    manager = creation_manager();
    if (manager == NULL) {
        return 0;
    }
    slot = *(const volatile int *)(manager + CREATION_SAVE[g_game].slot);
    if (slot < 1 || slot > 5
        || *(const volatile unsigned int *)(manager + CREATION_SAVE[g_game].state) != CREATION_SAVE[g_game].main_state) {
        return 0;
    }
    start = creation_start(manager);
    if (start == 0u || (slot == creation_saved_slot && start == creation_saved_start)
        || !creation_founders_pending(slot)) {
        return 0;
    }
    if (g_game == 1 && creation_vv1_now(manager) - start > CREATION_RECENT_SECONDS) {
        return 0;               /* a loaded village: the seeding ran ahead of the load */
    }
    creation_saved_slot = slot;
    creation_saved_start = start;
    *(volatile unsigned int *)(manager + CREATION_SAVE[g_game].autosave) = 0u;
    COD_COUNT(creation_saves);
    return 1;
}
