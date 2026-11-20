/* VVFP Fog Listening -- "Fog of Doom Lets Every Heathen Listen", New Believers.

   The owner (2026-11-19): "the Fog of Doom can allow villagers to be dropped on red/yellow heathens to convert them
   like they can the blue ones"; "for heathens, they work only when the heathen's faith is lower than -10. at -10 or
   above only the Earthquake power can convert them".  And: the drop starts the game's own listening / "Explaining
   the truth" interaction, which raises the Heathen's Faith exactly as for a blue-masked Heathen; the conversion is
   the game's own when the Faith gets there.  Only the cast Fog of Doom God Power, never natural fog or other weather.
   (The game's orange mask is the owner's "yellow": the game has blue, orange, red, purple and the Chief's masks.)

   THE STOCK GAME.  A villager dropped on another goes through the drop handler 0x443BF0 (the target found under the
   drop by 0x470450).  An adult (age 280 age units or more, 0x443CFD) dropped on a Heathen (faction byte +0x1CEC)
   who is not the Heathen Doctor (role 12, 0x443D1A) reaches the mask test 0x443D4D: a Heathen in the orange mask
   (+0x1CED, the chasers) or the red mask (+0x1CEE, the scary ones) ends the drop at 0x44402D, nothing happens;
   every other Heathen (the blue mask) is given action 6 ("Waiting for someone") and the dropped villager action
   0x27 ("Explaining the truth"), 0x443D65..0x443D92.  The sermon's end is the work event 0x468DA0 (from 0x47387B):
   the Heathen Doctor, Chief, three Masters and Mommy (roles 12-17) refuse; a Heathen within 2 real-life hours of
   the last sermon refuses; else the preacher's Devotion check 0x46B270(5); on success the Heathen is "Listening"
   (action 0x29), the 2-hour wait is set (+0x1CF4, 0x468F33) and the Faith is raised through 0x468020 by 3, +1 at
   Devotion 50, +1 more at 88; the Faith setter 0x467F90 makes a Heathen above 0 a believer (0x4668B0).  The work
   event reads no mask.

   THE FOG OF DOOM.  Every fog starts at thickness 1 (0x475EDC); only the Fog of Doom God Power (CFogOfDoomSpell,
   0x41FB60) sets it to 4.  The game's own test 0x476260 (on the weather 0x710948: fog on, +0x500C, and thickness
   +0x5010 at least 2) is what stops Heathens seeing believers in the thick fog (0x46E2E8); this companion asks the
   same test, so natural fog, a Tempest's storm and every other weather never count.  The thick fog lasts until the
   weather next changes (the Game Mechanics page, God powers).

   THE EARTHQUAKE.  The Earthquake God Power (CEarthQuakeSpell, 0x41F6E0) already raises every living villager's
   Faith by 2 to 8 but the six special roles, Heathens of every mask included (0x41F79F; no mask test), and the
   conversion follows as for any Faith rise.  Nothing here changes it: from Faith -10 up the Earthquake is the one
   way left to a Heathen in the orange or red mask, as the owner asks.

   WHAT THIS COMPANION DOES.  The mask test 0x443D4D (24 bytes, both compares and both jumps) jumps to the
   companion.  A Heathen in neither mask goes on at 0x443D65 as before.  A Heathen in the orange or red mask goes
   on at 0x443D65 -- the stock listening path, with the stock actions, the stock sermon and its stock Faith -- when
   the Fog of Doom's thick fog is over the island (the game's test 0x476260) and the Heathen's own Faith (+0x1CF0)
   is below -10; otherwise at 0x44402D, the stock end of the drop.

   NO RESTRICTIONS.  The owner (2026-11-19), the default-off row "No Restrictions on Fog of Doom Conversions"
   (vv5_fog_of_doom_no_restrictions, which needs this one): "the -10 faith limit requiring Earthquakes is removed.
   Those heathens can now be talked to like any other blue heathen and eventually converted, as long as Fog of Doom
   is active."  The row ships no code: its one file, FL_NO_LIMIT_FLAG in the patcher's folder, read once at the
   start, drops the Faith condition.  The Fog of Doom is still needed; natural fog still never counts.

   HOW.  The site is spliced at run time, after its stock bytes are checked (native/shared/install_sites.h); no
   executable byte is patched.  The splice saves every register and flag around the decision, made under
   structured exception handling (a fault: the stock answer, nothing happens).  Started by VVFP More
   Companions.dll (the third word, native/shared/startup_companions_3.h).  No debug output, no text shown. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"

#define FL_GAME 5

#define FL_SITE 0x443D4Du               /* cmp byte [esi+0x1CED], bl / jne 0x44402D / cmp byte [esi+0x1CEE], bl / jne */
#define FL_LISTEN 0x443D65u             /* the stock listening path: Heathen action 6, believer action 0x27 */
#define FL_REFUSE 0x44402Du             /* the stock end of the drop: nothing happens */
#define FL_FOG_TEST 0x476260u           /* the weather's "thick fog" test (fog on, thickness 2 or more) */
#define FL_WEATHER 0x710948u            /* the weather object 0x46E2E3 asks */
#define FL_ORANGE 0x1CED
#define FL_RED 0x1CEE
#define FL_FAITH 0x1CF0
#define FL_FAITH_BELOW (-10)            /* the owner: "only when the heathen's faith is lower than -10" */
#define FL_NO_LIMIT_FLAG "VVFP Fog Listening No Restrictions.txt"

static const unsigned char SITE_STOCK[24] = {
    0x38, 0x9E, 0xED, 0x1C, 0x00, 0x00,     /* cmp byte [esi+0x1CED], bl */
    0x0F, 0x85, 0xD4, 0x02, 0x00, 0x00,     /* jne 0x44402D */
    0x38, 0x9E, 0xEE, 0x1C, 0x00, 0x00,     /* cmp byte [esi+0x1CEE], bl */
    0x0F, 0x85, 0xC8, 0x02, 0x00, 0x00      /* jne 0x44402D */
};

static int g_installed;
static int g_no_limit;                  /* "No Restrictions on Fog of Doom Conversions" is shipped */
static unsigned int g_listened;         /* masked Heathens let listen this session (the tests read it) */

typedef unsigned char (__fastcall *fl_fog_fn)(void *weather);

/* "No Restrictions on Fog of Doom Conversions" is shipped: its file is in the patcher's folder.  Any failure reads
   as not shipped: the Faith condition stays. */
static int fl_no_limit_shipped(void) {
    wchar_t path[VVFP_PATCHER_FILES_PATH_CAP];
    DWORD attributes;
    if (vvfp_exe_relative_path_w(path, VVFP_PATCHER_FILES_PATH_CAP, VVFP_PATCHER_FILES_FOLDER,
                                 FL_NO_LIMIT_FLAG) == 0) {
        return 0;
    }
    attributes = GetFileAttributesW(path);
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

/* 1 when a believer dropped on this orange- or red-masked Heathen starts the stock listening. */
static int fl_may_listen(const unsigned char *heathen) {
    if (!g_no_limit && *(const int *)(heathen + FL_FAITH) >= FL_FAITH_BELOW) {
        return 0;                       /* -10 or more: only the Earthquake reaches them */
    }
    if (!((fl_fog_fn)FL_FOG_TEST)((void *)FL_WEATHER)) {
        return 0;                       /* no Fog of Doom: natural fog and other weather never count */
    }
    ++g_listened;
    return 1;
}

static unsigned int __stdcall fl_next(const unsigned char *heathen) {
    int listen = 0;
    __try {
        listen = fl_may_listen(heathen);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        listen = 0;
    }
    return listen ? FL_LISTEN : FL_REFUSE;
}

/* In place of the mask test: esi is the Heathen, ebx 0.  Blue goes on as before; a mask asks fl_next. */
__declspec(naked) static void fl_stub(void) {
    __asm {
        cmp byte ptr [esi + FL_ORANGE], 0
        jne masked
        cmp byte ptr [esi + FL_RED], 0
        jne masked
        push FL_LISTEN
        ret
    masked:
        sub esp, 4                      /* the slot for where to go on */
        pushfd
        pushad
        push esi
        call fl_next
        mov dword ptr [esp + 36], eax   /* above the 32 bytes of pushad and the 4 of pushfd */
        popad
        popfd
        ret
    }
}

/* 1 when the site is installed (for the tests' emulation), else 0. */
int __stdcall VvfpFogListeningInstalled(void) {
    return g_installed;
}

/* How many orange- or red-masked Heathens were let listen this session (for the tests' emulation). */
unsigned int __stdcall VvfpFogListeningCount(void) {
    return g_listened;
}

/* 1 when "No Restrictions on Fog of Doom Conversions" is in effect (for the tests' emulation), else 0. */
int __stdcall VvfpFogListeningNoRestrictions(void) {
    return g_no_limit;
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write site;
    (void)shipped;
    if (g_installed || game != FL_GAME) {
        return;
    }
    g_no_limit = fl_no_limit_shipped();
    vvfp_site_branch(&site, FL_SITE, (int)sizeof SITE_STOCK, SITE_STOCK, 0xE9, (const void *)fl_stub);
    if (vvfp_install_sites(&site, 1)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
