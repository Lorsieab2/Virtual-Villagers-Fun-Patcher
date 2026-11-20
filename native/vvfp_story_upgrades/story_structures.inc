/* The structures a village has finished, for the "repair" effect (code 36; the owner, 2026-11-15: "the damaged huts
   are repaired").  Included by vvfp_story_upgrades.c after story_living.inc.

   A structure may be repaired only when it is not finished now but this village had finished it before (damaged by an
   island event: the collection's "damage", More Island Events' The Rumblings, or any other way), never one the
   village has not built yet.  Which ones were finished is kept beside the save, never in it:
       the paid-purchases folder's "Island Event Structures" file of the slot (vv_paid_named_path), little-endian:
       u32 magic 'VSS1' (0x31535356), u32 game (1..5), u32 the village's roster signature (lv_roster_sig: the file
       belongs to the village holding that villager), u32 mask (bit k: structure k of native/shared/
       structure_damage.h finished at some time), 16 bytes in all.
   Every two seconds the finished structures are seen and the mask grows; another village (a different signature, a
   Start Over) starts a fresh mask.  The repair itself leaves one step of building work, so the game's own
   construction finishes it with its own completion (sd_repair). */

#define ST_MAGIC 0x31535356u
#define ST_WHAT "Island Event Structures"
#define ST_TICK_MS 2000u

static int st_game, st_slot;
static unsigned int st_mask, st_sig;
static story_village st_village;
static DWORD st_last;
#ifdef VVFP_TEST
static int st_test_mask = -1;                    /* -1: the file's; else forced */
#endif

static void st_store(void) {
#ifndef VVFP_TEST
    char path[MAX_PATH];
    unsigned int out[4];
    const void *parts[1];
    DWORD sizes[1];
    if (st_slot < 1 || !vv_paid_named_path(st_game, st_slot, ST_WHAT, path, 1)) {
        return;
    }
    out[0] = ST_MAGIC;
    out[1] = (unsigned int)st_game;
    out[2] = st_sig;
    out[3] = st_mask;
    parts[0] = out;
    sizes[0] = sizeof out;
    (void)vv_paid_write_parts(path, parts, sizes, 1);
#endif
}

/* The mask of `game`'s village now, read from its file once a village (fresh when missing, damaged or another
   village's). */
static void st_bind(int game) {
    int slot = story_current_slot(game);
    if (st_game == game && st_slot == slot && story_village_is(game, &st_village)) {
        return;
    }
    st_game = game;
    st_slot = slot;
    st_village = story_village_now(game);
    st_mask = 0u;
    st_sig = 0u;
#ifndef VVFP_TEST
    {
        char path[MAX_PATH];
        unsigned char data[16];
        unsigned int size = 0, v[4];
        if (slot >= 1 && vv_paid_named_path(game, slot, ST_WHAT, path, 0)
            && cg_read_whole(path, data, sizeof data, &size) && size == 16u) {
            memcpy(v, data, 16);
            if (v[0] == ST_MAGIC && v[1] == (unsigned int)game && lv_roster_has(game, v[2])) {
                st_mask = v[3];
                st_sig = v[2];
            }
        }
    }
#endif
}

/* Every frame (VvfpStoryInstall's tick): every two seconds, the structures finished now join the mask. */
static void st_tick(int game) {
    DWORD now = GetTickCount();
    unsigned int seen = 0u;
    int k;
    if (game < 1 || game > 5 || now - st_last < ST_TICK_MS) {
        return;
    }
    st_last = now;
    st_bind(game);
    if (st_slot < 1) {
        return;
    }
    __try {
        for (k = 0; k < sd_structures(game) && k < 32; ++k) {
            if (sd_finished(game, k)) {
                seen |= 1u << k;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return;
    }
    if ((st_mask | seen) != st_mask || st_sig == 0u) {
        st_mask |= seen;
        st_sig = lv_roster_sig(game);
        if (st_sig != 0u) {
            st_store();
        }
    }
}

/* Whether structure `k` of `game` was finished by this village before. */
static int st_was_finished(int game, int k) {
#ifdef VVFP_TEST
    if (st_test_mask >= 0) {
        return ((unsigned int)st_test_mask >> k) & 1u;
    }
#endif
    st_bind(game);
    return k >= 0 && k < 32 && ((st_mask >> k) & 1u);
}
