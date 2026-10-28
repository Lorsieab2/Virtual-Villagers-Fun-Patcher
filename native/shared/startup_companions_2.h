/* The second word of companions "VVFP Startup.dll" may start (the owner, 2026-10-25: the first word,
   native/shared/startup_companions.h, is full -- bits 1-29 companions, 30 and 31 settings).

   A build that ships any of these has the patcher's startup stub call VvfpStartupEx(game, shipped,
   shipped2) instead of VvfpStartup(game, shipped): bit i of `shipped2` is VVFP_STARTUP_COMPANIONS_2[i].
   A build that ships none of them keeps the stub exactly as before (the same bytes), and an executable
   patched before this list existed calls VvfpStartup, which still starts everything in the first word.
   The order is a contract with the patcher (STARTUP_LOADER_COMPANIONS_2 in src/vv_fun_patcher.py, pinned
   by tests/test_startup_loader.py): APPEND ONLY -- never reorder, rename or remove an entry.

   Each is started as the first word's companions are: loaded by its full path from the patcher's folder,
   then its VvfpStartup(game, shipped) called (with the FIRST word, as every companion gets), a fault in it
   abandoned.  Only "VVFP Startup.dll" reads this list: no Origins bridge loads these companions. */
#ifndef VVFP_STARTUP_COMPANIONS_2_H
#define VVFP_STARTUP_COMPANIONS_2_H

static const char *const VVFP_STARTUP_COMPANIONS_2[] = {
    "VVFP VV1 Genetics.dll",
    "VVFP Appearance Rolls.dll",
    "VVFP VV1 Grey Hair.dll",
    "VVFP Head Look.dll",
    /* APPEND ONLY (see above). */
};
#define VVFP_STARTUP_COMPANION_COUNT_2 \
    (sizeof VVFP_STARTUP_COMPANIONS_2 / sizeof VVFP_STARTUP_COMPANIONS_2[0])

#endif /* VVFP_STARTUP_COMPANIONS_2_H */
