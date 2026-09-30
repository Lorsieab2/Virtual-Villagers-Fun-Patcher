/* Patcher-owned Village Statistics state, kept in .dat files beside the save.
 *
 * THE OWNER'S RULE: "in general if the game doesn't keep track of it, make a
 * .dat file." Nothing the patch counts is stored in the save any more.
 *
 * HOW A COUNT TRAVELS.
 *
 *   1. An executable hook (scripts/build_statistics_features.py) increments a
 *      PENDING field -- scratch space inside the block the game saves and
 *      loads wholesale -- or, for stews, sets a bit in a pending bitset.
 *   2. The full-save wrapper hands the save to SaveVillageStatistics, whose
 *      first step is vvs_flush(): each pending value is added into the slot's
 *      "Village Statistics - Save N.dat", each pending stew bit is normalised
 *      and merged into "Stew Discoveries - Save N.dat", both files are
 *      replaced atomically, and ONLY THEN are the pending fields zeroed, in
 *      the live block and in the save buffer the writer is about to write.
 *      A saved file therefore only ever holds zeros in those fields.
 *   3. The statistics log prints the .dat totals.
 *
 * Because the pending fields live inside the saved/loaded block, loading a
 * different village overwrites them with that save's zeros, and a new village
 * zeroes them, so an unsaved event is discarded with the village it belongs
 * to -- exactly as the game discards its own unsaved progress -- and can never
 * be credited to another village.
 *
 * MIGRATION. The fields earlier builds counted into are FROZEN: no hook
 * writes them now. When a slot's counters .dat has no entry for a counter,
 * that counter starts from the frozen field's value (Villagers Buried from the
 * larger of that and the memorial the game still holds; Chiefs Robed from the
 * larger of that and 1-if-a-chief-lives when the old seed never ran), and the
 * .dat records "migrated.<key>=<value>" so the migration is never repeated.
 * Reloading an older backup cannot add it twice: the entry already exists.
 *
 * LIMITATIONS, stated precisely.
 *   - The .dat outlives the save file: restoring an older backup of a save
 *     does not roll the .dat back, so events counted after that backup stay
 *     counted.
 *   - The flush happens before the stock writer. If the writer then fails,
 *     the flushed events stay counted -- they happened.
 *   - If the .dat cannot be written, the pending fields are NOT zeroed; they
 *     are saved with the village and flushed on a later save, so nothing is
 *     lost or counted twice.
 *   - Stew discoveries made before this build are not in any file and are
 *     not invented: an existing village's stew count starts at zero.
 *   - Start Over clears the slot's .dat files through the tribe-delete reset
 *     (native/shared/save_reset.c), which ships with the features that carry
 *     that reset hook; without it a new village started in the same slot
 *     would continue the old village's totals.
 */
#ifndef VVFP_STATISTICS_STORE_H
#define VVFP_STATISTICS_STORE_H

#include <wchar.h>

enum {
    VVS_BURIED = 0,
    VVS_TWINS,
    VVS_CHIEFS,
    VVS_DEBRIS,
    VVS_FOOD,
    VVS_HEATHENS,
    VVS_DIED,
    VVS_COUNTER_KINDS
};

/* Outcome of reading one .dat file. */
enum {
    VVS_FILE_OK = 0,
    VVS_FILE_MISSING,     /* no file: an empty history */
    VVS_FILE_CORRUPT,     /* present but not a valid file for this game */
    VVS_FILE_UNREADABLE   /* present but could not be read (locked, I/O) */
};

typedef struct {
    int game_id;                  /* 1..5 */
    unsigned char *manager;       /* the save manager the writer receives */
    unsigned char *module;        /* the game's image base */
    const wchar_t *counters_path; /* full path of the counters .dat */
    const wchar_t *stews_path;    /* full path of the stews .dat, or NULL */
} vvs_context;

/* Flush pending counters and stew bits into the .dat files, then zero them.
   Returns a bit mask: 1 = counters flushed, 2 = stews flushed. */
int vvs_flush(const vvs_context *context);

/* The value a row prints: the .dat total plus anything still pending.
   Returns 0 if this game has no such counter. */
int vvs_counter_value(const vvs_context *context, int kind, int *value);

/* The number of distinct stew identities discovered. Returns 0 if this game
   has no stews. */
int vvs_stews_value(const vvs_context *context, int *value);

/* Build the two paths for a save slot under the save folder, creating the
   folders. `stews` receives an empty string for a game without stews.
   Both buffers must hold MAX_PATH characters. Returns 1 on success. */
int vvs_build_paths(int game_id, int save_id, wchar_t *counters, wchar_t *stews);

/* The canonical identity of a stew, or -1 for herbs outside the game's set.
   Herbs are the game's own ids, in any order; `salt` matters only for VV4.
   Exposed for the harness. */
int vvs_stew_identity(int game_id, int h1, int h2, int h3, int salt);

/* Read a file's state without changing anything; for the harness. */
int vvs_probe_file(const wchar_t *path, int game_id, int stews);

#endif /* VVFP_STATISTICS_STORE_H */
