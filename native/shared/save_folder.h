/* The one place that answers "where does this game keep its save?".
 *
 * Every Virtual Villagers title stores its saves in
 *
 *     <My Documents>\LDW\<exe basename without .exe>\
 *
 * and the basename is the ONLY thing that varies between a stock install and a
 * renamed one. A player running "Virtual Villagers - The Lost Children - Modded.exe"
 * has saves under "...\LDW\Virtual Villagers - The Lost Children - Modded\", and a
 * patcher-owned file that belongs to that village has to land in the same folder.
 *
 * WHY THIS HEADER EXISTS.
 *
 * Two different answers to that question had grown up side by side, and both
 * were wrong in a way the owner could see on disk:
 *
 *   * the three log exporters (parentage, statistics, population) resolved
 *     GetModuleFileNameW and stripped to the EXECUTABLE'S directory, so every
 *     exported log landed next to the .exe instead of next to the save. The
 *     owner found "Village Population 1.txt" sitting in two install folders.
 *
 *   * one mask sidecar reader hardcoded a literal game folder name, so a
 *     renamed exe read another install's masks. The owner's VV2 masks were in
 *     the vanilla folder while the Modded folder he actually played had no
 *     mask file at all, and 144 masked villagers bled into whatever village
 *     occupied slot 1.
 *
 * So the rule is: NO HARDCODED GAME FOLDER NAMES, and one resolver that every
 * write, read, append, rollover and reset agrees on. If the player renames the
 * executable, the patcher follows the save; the save never follows a string
 * literal.
 *
 * Failure is always reported rather than papered over. A caller that cannot
 * resolve the folder must not fall back to the current directory, the install
 * directory, or a guess -- particularly the reset path, where a wrong folder
 * would delete the wrong files.
 */
#ifndef VVFP_SAVE_FOLDER_H
#define VVFP_SAVE_FOLDER_H

#include <windows.h>

/* Write "<My Documents>\LDW\<exe basename>" into `out`, creating both
   directories if they do not exist.

   `out` must have room for MAX_PATH characters. Returns 1 on success, 0 if the
   Documents folder cannot be found, the module path cannot be read, or the
   result would not fit -- in which case `out` is left unmodified and the
   caller MUST NOT construct a path from it.

   `reserve` is the number of characters the caller still intends to append,
   including a leading backslash and the terminating NUL. Passing the real
   figure is what stops a long basename producing a truncated path that points
   somewhere unintended. */
int vv_save_folder(char *out, int reserve);

/* The wide-character form, for callers using _wfopen and the wide Win32 API.
   Same contract, same failure behaviour. */
int vv_save_folder_w(wchar_t *out, int reserve);

#endif /* VVFP_SAVE_FOLDER_H */
