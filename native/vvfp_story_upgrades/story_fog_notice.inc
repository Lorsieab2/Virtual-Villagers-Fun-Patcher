/* Fog of Doom Lets Every Heathen Listen's notice (New Believers) -- included by vvfp_story_upgrades.c, after
   story_faith_notice.inc.

   The owner (2026-11-19): when the Fog of Doom is on and a Heathen in an orange or red mask with Faith -10 or more
   turns a drop away, a popup like the game's normal ones says "The fog hides you, but <Name> still won't listen.
   Something stronger may stir them." (with the Guardians of Isola rewrite: "... <Name> is still wary. Perhaps
   another approach may convince them."), once per village.  "VVFP Fog Listening.dll" (native/vvfp_fog_listening)
   decides it and composes the words (VvfpFogNoticePending); this shows them exactly as Popup When Believers Become
   Heathens shows its popup (story_faith_notice.inc): the island-event notice the Time Skip's closing popup uses
   (story_notice_arm), armed only when the slot is free and the game's trigger will show it at once -- never during
   a time skip or its closing popup, an island event's popup, a pick or custom event on its way, or while the game
   is not running -- kept apart from the island events (not counted, not logged, the next island event keeps its
   time).  Once armed the companion is told (VvfpFogNoticeTaken), which marks the village as told.  The title is
   the God Power's own name, "Fog of Doom" (its translation row is ...FOG_NOTICE_TITLE.s0). */

#define FOG_NOTICE_GAME 5
#define FOG_NOTICE_TITLE "Fog of Doom"

typedef int (__stdcall *fog_pending_fn)(int game, char *out, int cap);
typedef void (__stdcall *fog_taken_fn)(int game);
static fog_pending_fn fog_pending_export;
static fog_taken_fn fog_taken_export;
static ce_event fog_notice_event;

/* Asks "VVFP Fog Listening.dll" (absent: nothing to say) for the popup's words. */
static int fog_notice_pending(char *out, int cap) {
    HMODULE module;
    if (fog_pending_export == NULL || fog_taken_export == NULL) {
        module = GetModuleHandleA("VVFP Fog Listening.dll");
        if (module == NULL) {
            return 0;
        }
        fog_pending_export = (fog_pending_fn)(void *)GetProcAddress(module, "VvfpFogNoticePending");
        fog_taken_export = (fog_taken_fn)(void *)GetProcAddress(module, "VvfpFogNoticeTaken");
        if (fog_pending_export == NULL || fog_taken_export == NULL) {
            return 0;
        }
    }
    return fog_pending_export(FOG_NOTICE_GAME, out, cap) != 0;
}

/* Called every frame (VvfpStoryInstall), after the Faith popup's tick: the same waits. */
static void fog_notice_tick(int game) {
    const story_host *host = story_time_skip_host(game);
    if (game != FOG_NOTICE_GAME || !story_installed(game)
        || (time_skip.game == game && (time_skip.active || time_skip.finishing || time_skip.notice > 0))
        || time_skip_event_open() || (host != NULL && !story_host_running(host))) {
        return;
    }
    memset(&fog_notice_event, 0, sizeof fog_notice_event);
    if (!fog_notice_pending(fog_notice_event.text, (int)sizeof fog_notice_event.text)
        || fog_notice_event.text[0] == '\0') {
        return;
    }
    lstrcpynA(fog_notice_event.title, vvfp_tr("vvfp.story/story_fog_notice.FOG_NOTICE_TITLE.s0", FOG_NOTICE_TITLE,
                                              sizeof fog_notice_event.title), sizeof fog_notice_event.title);
    if (story_notice_arm(game, &fog_notice_event) && fog_taken_export != NULL) {
        fog_taken_export(FOG_NOTICE_GAME);     /* armed: the game's own trigger shows it */
    }
}

/* Start Over or a deleted tribe (VvfpStoryVillageReset): a notice still waiting was that village's. */
static void fog_notice_village_reset(int game) {
    typedef void (__stdcall *reset_fn)(int game);
    HMODULE module;
    reset_fn reset;
    if (game != FOG_NOTICE_GAME) {
        return;
    }
    module = GetModuleHandleA("VVFP Fog Listening.dll");
    reset = module != NULL ? (reset_fn)(void *)GetProcAddress(module, "VvfpFogNoticeVillageReset") : NULL;
    if (reset != NULL) {
        reset(game);
    }
}
