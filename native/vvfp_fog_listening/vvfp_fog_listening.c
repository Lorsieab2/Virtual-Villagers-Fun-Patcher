/* VVFP Fog Listening -- "Fog of Doom Lets Red and Orange Heathens Listen", New Believers.

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
   Companions.dll (the third word, native/shared/startup_companions_3.h).  No debug output.

   THE NOTICE.  The owner (2026-11-19): when the Fog of Doom is on and the Faith limit turns a drop away (the main
   row without No Restrictions), a popup like the game's normal ones says "The fog hides you, but <Name> still
   won't listen. Something stronger may stir them." (with the Guardians of Isola rewrite: "... <Name> is still wary.
   Perhaps another approach may convince them."), <Name> the Heathen's whole name (long_name.h), the words through
   VVFP Translations.dll.  This companion only keeps the notice waiting (one at a time) and composes its words;
   "VVFP Story Upgrades.dll" (story_fog_notice.inc) shows it the way it shows Popup When Believers Become
   Heathens' popup -- the game's own island-event popup window with its OK, only when no other popup or event is
   showing or on its way and the game is running -- asks VvfpFogNoticePending each frame and calls
   VvfpFogNoticeTaken once it is armed.  Only once per village, ever: Taken makes a small file in the slot's own data
   folder, kept across quitting; Start Over deletes the save's folder (and VvfpStoryVillageReset drops a notice
   still waiting), so the next village is told again.  A notice still waiting at a quit was never shown, so the
   next refusal makes it again.  Never for a blue Heathen, natural fog, no fog, an unknown slot, or with No
   Restrictions. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/per_save_data.h"
#include "../shared/game_save_slot.h"
#include "../shared/long_name.h"
#include "../shared/vvfp_translate.h"

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
/* The record's role (+0x1CFC): 12 the Heathen Doctor and 14-16 the three Masters (purple masks), 13 the Chief, 17 the
   Heathen Mommy.  The owner (2026-11-20): these are puzzle Heathens and never listen this way, with or without No
   Restrictions -- never let through here (the stock sermon end 0x468DA0 refuses roles 12-17 too). */
#define FL_ROLE 0x1CFC
#define FL_ROLE_FIRST_SPECIAL 12
#define FL_ROLE_LAST_SPECIAL 17
#define FL_NO_LIMIT_FLAG "VVFP Fog Listening No Restrictions.txt"

static const unsigned char SITE_STOCK[24] = {
    0x38, 0x9E, 0xED, 0x1C, 0x00, 0x00,     /* cmp byte [esi+0x1CED], bl */
    0x0F, 0x85, 0xD4, 0x02, 0x00, 0x00,     /* jne 0x44402D */
    0x38, 0x9E, 0xEE, 0x1C, 0x00, 0x00,     /* cmp byte [esi+0x1CEE], bl */
    0x0F, 0x85, 0xC8, 0x02, 0x00, 0x00      /* jne 0x44402D */
};

#define FL_STRINGS 0x5240A8u            /* the game's string table (entry pointers by id) */
#define FL_NAME 0x1B9C                  /* the villager's name field */
#define FL_NAME_FIELD 0x19
#define FL_WORDS_CAP 512                /* a translation of the words, at most */
#define FL_WHOLE_NAME 512               /* a whole name, at most */
#define FL_NOTICE_LINE "Virtual Villagers Fun Patcher - the Fog of Doom notice was shown in this village.\r\n"

/* The owner's words (2026-11-19); %s is the Heathen's whole name. */
static const char WONT_LISTEN_EN[] =
    "The fog hides you, but %s still won't listen. Something stronger may stir them.";
static const char WARY_EN[] =
    "The fog hides you, but %s is still wary. Perhaps another approach may convince them.";

static int g_installed;
static int g_no_limit;                  /* "No Restrictions on Fog of Doom Conversions" is shipped */
static unsigned int g_listened;         /* masked Heathens let listen this session (the tests read it) */
static unsigned int g_notices;          /* notices handed over to be shown this session (the tests read it) */
static int g_waiting_slot;              /* the slot of the notice waiting to be shown, 0 when none */
static char g_waiting_name[FL_WHOLE_NAME];

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

/* ---- THE NOTICE: once per village, the first time the Faith limit turns a drop away ---------------------------- */

/* The game's eSayStoppedBelieving (string 0x48 in the table 0x5240A8) says "left the tribe" only with the Guardians
   of Isola rewrite's sm.xml: the same test as Popup When Believers Become Heathens' (story_faith_notice.inc) and
   More Island Events' (adv_vv345.inc vv5_joins_key). */
static int fl_isola(void) {
    static const char WORDS[] = "left the tribe";
    int found = 0;
    __try {
        const unsigned int *entry = *(const unsigned int *const *)(UINT_PTR)(FL_STRINGS + 4u * 0x48u);
        const char *text;
        int i, k;
        if (entry != NULL && entry[0] == 0x48u) {
            text = (const char *)(UINT_PTR)(entry[3] != 0 ? entry[3] : entry[2]);
            for (i = 0; text != NULL && text[i] != '\0' && i < 256 && !found; ++i) {
                for (k = 0; WORDS[k] != '\0'; ++k) {
                    char c = text[i + k];
                    if (c >= 'A' && c <= 'Z') {
                        c = (char)(c - 'A' + 'a');
                    }
                    if (c != WORDS[k]) {
                        break;
                    }
                }
                found = WORDS[k] == '\0';
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        found = 0;
    }
    return found;
}

/* The slot's notice file: "<save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\Fog of Doom\Fog of Doom
   Notice - Save <S>.dat" (per_save_data.h).  Start Over deletes the save's whole folder (native/shared/save_reset.c,
   START OVER WIPES THE WHOLE SAVE), so the next village in the slot is told again.  0 when the slot or the folder
   is not known. */
static int fl_notice_path(wchar_t *out, int slot) {
    wchar_t name[64];
    if (slot < 1 || slot > 5) {
        return 0;
    }
    wsprintfW(name, L"Fog of Doom Notice - Save %d.dat", slot);
    return vv_ps_data_file_w(out, L"Fog of Doom", name, VV_PS_RESERVE);
}

/* The village's first refusal: the notice is kept waiting, with the Heathen's whole name, for the Story companion
   to show.  Nothing when one is waiting already, the slot is not known, or this village was told before. */
static void fl_notice(const unsigned char *heathen) {
    wchar_t path[MAX_PATH];
    char field[FL_NAME_FIELD + 1];
    int slot = vv_game_save_slot(FL_GAME);
    if (g_waiting_slot != 0 || !fl_notice_path(path, slot) || GetFileAttributesW(path) != INVALID_FILE_ATTRIBUTES) {
        return;
    }
    memcpy(field, heathen + FL_NAME, FL_NAME_FIELD);
    field[FL_NAME_FIELD] = '\0';
    lstrcpynA(g_waiting_name, vv_long_name(field), (int)sizeof g_waiting_name);
    g_waiting_slot = slot;
}

/* For "VVFP Story Upgrades.dll" (story_fog_notice.inc), every frame: 1 with the popup's words in `out` (`cap`
   bytes, at least 1,024) while a notice of the village in play waits; 0 otherwise (a notice of another slot's
   village is dropped). */
int __stdcall VvfpFogNoticePending(int game, char *out, int cap) {
    const char *words;
    int found = 0;
    __try {
        if (game != FL_GAME || g_waiting_slot == 0 || out == NULL || cap < 1024) {
            return 0;
        }
        if (vv_game_save_slot(FL_GAME) != g_waiting_slot) {
            g_waiting_slot = 0;         /* the player went to another village: it was that one's */
            return 0;
        }
        words = fl_isola()
            ? vvfp_tr("vvfp.fog_listening/vvfp_fog_listening.WARY_EN.s0", WARY_EN, FL_WORDS_CAP)
            : vvfp_tr("vvfp.fog_listening/vvfp_fog_listening.WONT_LISTEN_EN.s0", WONT_LISTEN_EN, FL_WORDS_CAP);
        if (lstrlenA(words) + lstrlenA(g_waiting_name) >= cap) {
            return 0;                   /* cannot happen: at most 511 + 511 bytes in 1,024 */
        }
        wsprintfA(out, words, g_waiting_name);
        found = 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        found = 0;
    }
    return found;
}

/* For "VVFP Story Upgrades.dll": the popup is armed (the game's own trigger shows it), so the village is marked
   as told and the notice is no longer waiting. */
void __stdcall VvfpFogNoticeTaken(int game) {
    wchar_t path[MAX_PATH];
    HANDLE file;
    DWORD wrote;
    if (game != FL_GAME || g_waiting_slot == 0) {
        return;
    }
    __try {
        if (fl_notice_path(path, g_waiting_slot)) {
            file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
            if (file != INVALID_HANDLE_VALUE) {
                (void)WriteFile(file, FL_NOTICE_LINE, (DWORD)(sizeof FL_NOTICE_LINE - 1), &wrote, NULL);
                CloseHandle(file);
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    g_waiting_slot = 0;
    ++g_notices;
}

/* For "VVFP Story Upgrades.dll" (VvfpStoryVillageReset): Start Over or a deleted tribe; a notice still waiting was
   that village's. */
void __stdcall VvfpFogNoticeVillageReset(int game) {
    if (game == FL_GAME) {
        g_waiting_slot = 0;
    }
}

/* 1 when a believer dropped on this orange- or red-masked Heathen starts the stock listening. */
static int fl_may_listen(const unsigned char *heathen) {
    int role = *(const int *)(heathen + FL_ROLE);
    if (role >= FL_ROLE_FIRST_SPECIAL && role <= FL_ROLE_LAST_SPECIAL) {
        return 0;                       /* a puzzle Heathen (purple mask, the Chief, the Mommy): the stock refusal */
    }
    if (!((fl_fog_fn)FL_FOG_TEST)((void *)FL_WEATHER)) {
        return 0;                       /* no Fog of Doom: natural fog and other weather never count */
    }
    if (!g_no_limit && *(const int *)(heathen + FL_FAITH) >= FL_FAITH_BELOW) {
        __try {
            fl_notice(heathen);         /* -10 or more: only the Earthquake reaches them */
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
        return 0;
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

/* How many notices were handed over to be shown this session (for the tests' emulation). */
unsigned int __stdcall VvfpFogListeningNotices(void) {
    return g_notices;
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
