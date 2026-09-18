/* Village identity -- the tribe name and savegame number for a log header.
 *
 * WHY THIS EXISTS
 * ---------------
 * The owner keeps several villages per game, so a log that opens with only the
 * game's title gives no way to tell which village it describes.  Every exported
 * log is therefore required to name the village and its save slot at the top.
 *
 * WHERE THE NAME COMES FROM
 * -------------------------
 * The player-entered village name lives inside the block the game hands to its
 * own save writer.  At the statistics hook that block is already in registers:
 *
 *     push edi                ; the save slot, 1..5
 *     lea  eax, [esi + 8]     ; the save buffer
 *     push <buffer length>
 *     mov  ecx, esi
 *     push eax
 *     call <save writer>      ; <-- the hook sits here
 *
 * All five games use that identical shape, and `ecx` is what the statistics
 * companion already receives as its manager pointer.  So the name is reachable
 * as `manager + 8 + offset`, with no file ever opened.  That matters beyond
 * convenience: reading the save from disk would mean knowing where the save
 * folder is, and this project may not hardcode save-folder names into patched
 * executables, nor change save-folder behaviour.
 *
 * The offsets were measured across 348 real save files spanning both of the
 * owner's save folders, every slot, and multiple villages per game, and the
 * owner separately confirmed the decoded names against what the games display.
 *
 * WHAT THIS MODULE REFUSES TO DO
 * ------------------------------
 * It never writes to the game.  It reads a bounded span, requires the result to
 * look like a name a player could have typed, and otherwise reports failure so
 * the caller can fall back to a header without a name.  A wrong name printed
 * confidently is worse than no name, because the logs are meant to be
 * cross-referenced against each other.
 */
#ifndef VV_VILLAGE_IDENTITY_H
#define VV_VILLAGE_IDENTITY_H

#include <stddef.h>

/* The longest village name any game will accept, plus room for a terminator.
   The games' own name buffers are far larger than the player can fill, so this
   bound is about what is worth printing in a header, not about the game. */
#define VV_VILLAGE_NAME_MAX 64

/* Read the village name for `game_id` out of the save block the statistics
   hook is handed.

   `manager` is the pointer the companion receives -- the same `ecx` the game
   sets up before its save call, NOT the buffer; this routine applies the +8
   itself so that callers cannot disagree about whether it was already applied.

   On success writes a NUL-terminated name into `out` and returns 1.  On any
   doubt at all -- null pointer, unknown game, unreadable memory, or bytes that
   do not look like a player-typed name -- writes an empty string and returns 0.

   `out` must have room for VV_VILLAGE_NAME_MAX bytes. */
int vv_village_name(int game_id, const void *manager, char *out);

/* Write the standard identifying header line(s) for an exported log.

   Produces "Village: <name> (Save <n>)" when both are known, degrading to
   whichever half is available, and to nothing at all when neither is.  Callers
   print this immediately after the game's title so every log identifies its
   village the same way.

   `name` may be NULL or empty; `save_id` may be 0 to mean "not known".
   Returns the number of characters written, excluding the terminator. */
int vv_village_header(char *out, size_t size, const char *name, int save_id);

/* The per-game offset of the name inside the save BUFFER (after the +8).
   Exposed so tests can assert the table rather than re-deriving it, and so a
   harness can build a synthetic block.  Returns 0 for an unknown game, which
   is never a valid offset for any game here. */
unsigned int vv_village_name_offset(int game_id);

/* Publish the assembled header so exports that are NOT on the save call can
   use it.

   The parentage log is written at CONCEPTION, not at save, so it has no save
   buffer and no slot -- the two things the name and number come from. It can
   only learn them from whoever does have them, which is the statistics
   companion sitting on the save call.

   The handoff is a named, process-local shared block rather than a file: it
   costs no disk I/O on a path that runs inside the game's own save, it cannot
   be left behind as a stray file next to the executable, and it needs nothing
   from the save folder, whose location and behaviour this project must leave
   exactly as the base game has it.

   Publishing is best-effort by design. A village that has never been saved in
   a patched session has nothing to publish, and the parentage log must still
   be written -- without a header rather than not at all. */
void vv_village_publish(const char *header);

/* Read back the last published header, or an empty string when nothing has
   been published in this process. `out` must have room for `size` bytes.
   Returns 1 when a non-empty header was recovered. */
int vv_village_recall(char *out, size_t size);

#endif /* VV_VILLAGE_IDENTITY_H */
