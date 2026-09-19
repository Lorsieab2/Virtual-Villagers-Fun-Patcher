/* Reset the patcher's own state for one village, when the game erases it.
 *
 * The player presses Start Over, the game deletes that slot's .ldw, and the
 * village is gone. Everything the patcher wrote about that village has to go
 * with it -- otherwise the next village started in the same slot inherits a
 * dead village's masks and logs. The owner reported exactly that: masks on
 * Believers in a brand-new village, bled through from an old one.
 *
 * WHAT IS DELETED, AND NOTHING ELSE.
 *
 * Only files this patcher created, only for the slot being erased, only inside
 * the folder resolved by vv_save_folder(). Each name is built explicitly. There
 * is no wildcard, no directory walk and no recursive delete anywhere in this
 * file, because a reset that guessed could take a player's saves with it.
 *
 * The game's own files are never touched. The .ldw is the game's to delete and
 * it has already done so by the time this runs.
 *
 * FAILING IS SAFE. If the save folder cannot be resolved, nothing is deleted:
 * an unresolved path must never become a deletion target, and an unlabelled
 * sidecar left on disk is a far smaller harm than deleting the wrong file.
 */
#ifndef VVFP_SAVE_RESET_H
#define VVFP_SAVE_RESET_H

/* Delete this patcher's state for `slot`.
 *
 * `game` is 1..5. `slot` is the village slot the game is erasing; slots are
 * 1-based, and a slot outside 1..5 is refused.
 *
 * `village` is the header string of the village being erased, as the
 * exporters write it. Statistics and population logs are addressed by slot,
 * but parentage logs roll over by count and can only be identified by that
 * header; without it they are left alone rather than deleted on a guess.
 *
 * Returns the number of files deleted, or -1 if the save folder could not be
 * resolved and nothing was attempted. A file that does not exist is not an
 * error -- a village with no masks simply has no sidecar to remove. */
int vv_reset_slot_state(int game, int slot, const char *village);

#endif /* VVFP_SAVE_RESET_H */
