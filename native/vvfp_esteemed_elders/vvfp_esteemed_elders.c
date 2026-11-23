/* VVFP Esteemed Elders -- "Esteemed Elders in Every Game" (A New Home, The Lost Children, The Tree of Life, New
   Believers).

   The owner (2026-11-22): "all 5 games should change a villager's title to 'Esteemed Elder' if they master 3
   skills (EXCEPT SPECIAL VILLAGERS LIKE THE GOLDEN CHILD, VV3 TRIBAL CHIEF ETC)".  The Secret City and New
   Believers already do it in the stock game; this companion gives the other three the same title by the rule in
   native/shared/esteemed_elder.h (three or more skills at the game's Master level -- 90 in A New Home, 88 in the
   others -- never the Golden Child, a totem statue or a ghost; The Tree of Life's Scholar, all five, still wins).

   WHERE THE TITLE SHOWS.  The only place any of the five games shows a villager's title is the villager panel's
   title line (the Villager Details screen), which each game builds in one function and the Story / Cheat Upgrades'
   custom titles replace at its end (0x41FD75, 0x429DE3, 0x4404D9) -- so a custom title still wins over this one.
   And the grave: the later games' burial writes a title's epitaph ("Esteemed Elder" in The Lost Children, The
   Secret City and New Believers; "Scholar" in The Tree of Life).  A New Home's graves keep no epitaph of their own
   (the Cause of Death companion keeps one in its Graves file, and gives an Esteemed Elder's grave "Esteemed
   Elder" when this companion is in: cod_vv12.inc).

     A New Home        the panel 0x41F9B0: at 0x41FBDC `cmp [ecx+0x36C], 0xC7 / jne 0x41FBFD` (ecx the record)
                       the Golden Child's string 0x5F (0x41FBE8); here an Esteemed Elder gets the title the same
                       way (pushed, copied by 0x44B23D at 0x41FD6D), the Golden Child first.
     The Lost Children the panel: at 0x429C1D `cmp byte [ecx+0x7FC], bl / je 0x429C3D` the stock elder flag takes
                       the game's own "Esteemed Elder" (string 0x87, 0x429C25); here the row's rule takes it too.
                       The burial 0x46513C `mov al, [ecx+0x7FC] / test al, al / je 0x465172` gives a flagged
                       elder's grave the game's own epitaph 0x1F0 (0x465146); here the row's rule does too
                       (only reached for an adult: under 360 age units the child pair comes first, 0x4650D9).
     The Tree of Life  the panel: at 0x440314 `call 0x46AC70 / test al, al / je 0x440335` ([esp+0x10] the record) the
                       Scholar takes string 0xDA (0x44031D); here, not a Scholar, an Esteemed Elder gets the
                       title (pushed, copied by 0x4716DB at 0x4404D1).  The Roster of the Dead writer 0x45D470,
                       after its epitaph copy (0x45D611, the record its first argument): an adult (age at death
                       360 or more), not a Scholar (+0x31), who is an Esteemed Elder gets "Esteemed Elder" in
                       place of the job's epitaph -- as The Secret City and New Believers' writers choose it.

     New Believers     the panel 0x442E70: at 0x442EB5 `call 0x475610 / test al, al / je 0x442EFD` (ecx the
                       record's skills, [esp+0x10] the record) the stock game gives "Esteemed Elder" (string
                       0xCA, or the Retired Chief's 0xD3, 0x442EBE) to ANY villager with three skills at 88 --
                       a Heathen too, whose role 12-17 only overwrites it later (0x443102).  The owner
                       (2026-11-22): a current Heathen never shows "Esteemed Elder"; a Former Heathen (a
                       believer now) does.  Here a Heathen (+0x1CEC set) goes on to the rank (0x442EFD).
                       Heathens are never buried, so no grave changes.

   The title is the player's language through "VVFP Translations.dll" when a translation is chosen (vvfp_tr),
   else English; The Lost Children's are the game's own strings.

   HOW.  Every site is spliced at run time after its stock bytes are checked, all or none
   (native/shared/install_sites.h); no executable byte is patched.  The splices keep every register the game reads
   afterwards, and the rule only reads the record (under structured exception handling: a fault is "not an
   elder").  Started by VVFP More Companions.dll (the third word, native/shared/startup_companions_3.h).  The logs'
   "Special villager:" line (native/shared/special_title.h) asks VvfpEsteemedEldersInstalled.  No debug output; no
   file is read or written. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/esteemed_elder.h"
#include "../shared/vvfp_translate.h"

/* A New Home: the panel's Golden Child test. */
#define V1_TITLE_SITE 0x41FBDC
#define V1_GOLDEN 0x41FBE8
#define V1_RANK 0x41FBFD
#define V1_COPY 0x41FD6D
/* The Lost Children: the panel's elder flag test, and the burial's. */
#define V2_TITLE_SITE 0x429C1D
#define V2_TITLE_ELDER 0x429C25
#define V2_TITLE_RANK 0x429C3D
#define V2_GRAVE_SITE 0x46513C
#define V2_GRAVE_ELDER 0x465146
#define V2_GRAVE_JOB 0x465172
/* The Tree of Life: the panel's Scholar test, and the Roster of the Dead writer's epitaph copy. */
#define V4_TITLE_SITE 0x440314
#define V4_SCHOLAR_TEST 0x46AC70
#define V4_SCHOLAR 0x44031D
#define V4_RANK 0x440335
#define V4_COPY 0x4404D1
#define V4_GRAVE_SITE 0x45D611
#define V4_GRAVE_NEXT 0x45D619
#define V4_GRAVE_AGE 0x1C
#define V4_GRAVE_SCHOLAR 0x31
#define V4_GRAVE_EPITAPH 0x38
#define V4_EPITAPH_BYTES 0x20
#define ADULT_AGE 360
/* New Believers: the panel's elder test. */
#define V5_TITLE_SITE 0x442EB5
#define V5_ELDER_TEST 0x475610
#define V5_ELDER 0x442EBE
#define V5_RANK 0x442EFD
#define V5_FACTION 0x1CEC

static const unsigned char V1_TITLE_STOCK[12] = { 0x81, 0xB9, 0x6C, 0x03, 0x00, 0x00, 0xC7, 0x00, 0x00, 0x00,
                                                  0x75, 0x15 };
static const unsigned char V2_TITLE_STOCK[8] = { 0x38, 0x99, 0xFC, 0x07, 0x00, 0x00, 0x74, 0x18 };
static const unsigned char V2_GRAVE_STOCK[10] = { 0x8A, 0x81, 0xFC, 0x07, 0x00, 0x00, 0x84, 0xC0, 0x74, 0x2C };
static const unsigned char V4_TITLE_STOCK[9] = { 0xE8, 0x57, 0xA9, 0x02, 0x00, 0x84, 0xC0, 0x74, 0x18 };
static const unsigned char V4_GRAVE_STOCK[8] = { 0x8B, 0x44, 0x24, 0x14, 0x8B, 0x4C, 0x24, 0x20 };
static const unsigned char V5_TITLE_STOCK[9] = { 0xE8, 0x56, 0x27, 0x03, 0x00, 0x84, 0xC0, 0x74, 0x3F };

static int g_game;
static int g_installed;
static unsigned int g_titles;           /* titles given this session (the tests read it) */
static unsigned int g_graves;           /* graves given the epitaph this session (the tests read it) */

/* The title in the player's language, within `cap` bytes with its NUL (0: drawn from a pointer). */
static const char *ee_text(unsigned int cap) {
    return vvfp_tr("vvfp.esteemed_elders/vvfp_esteemed_elders.ee_text.s1", "Esteemed Elder", cap);
}

/* Is the villager in `record` an Esteemed Elder by the row's rule?  A fault is "no". */
static int ee_rule(const unsigned char *record) {
    int yes = 0;
    __try {
        yes = vv_elder_rule(g_game, record);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        yes = 0;
    }
    return yes;
}

/* The panel's question: is this villager's title "Esteemed Elder"? */
static int __cdecl ee_is_elder(const unsigned char *record) {
    int yes = ee_rule(record);
    if (yes) {
        ++g_titles;
    }
    return yes;
}

/* The title for the panel (A New Home, The Tree of Life): the game copies it into its own 256-byte buffer. */
static const char *__cdecl ee_title(void) {
    return ee_text(0);
}

/* ---- A New Home ------------------------------------------------------------------------------------------- */

/* In place of `cmp dword [ecx+0x36C], 0xC7 / jne 0x41FBFD`: ecx the record, eax the skill value the rank uses. */
__declspec(naked) static void v1_title_stub(void) {
    __asm {
        cmp dword ptr [ecx + 0x36C], 0xC7
        je golden
        push eax
        push ecx
        push edx
        push ecx
        call ee_is_elder
        add esp, 4
        test eax, eax
        pop edx
        pop ecx
        pop eax
        jnz elder
        push V1_RANK
        ret
    golden:
        push V1_GOLDEN
        ret
    elder:
        call ee_title
        push eax
        lea edx, [esp + 0x28]
        push edx
        push V1_COPY
        ret
    }
}

/* ---- The Lost Children ----------------------------------------------------------------------------------------- */

/* In place of `cmp byte [ecx+0x7FC], bl / je 0x429C3D` (bl is 0 there): ecx the record, eax the skill value. */
__declspec(naked) static void v2_title_stub(void) {
    __asm {
        cmp byte ptr [ecx + 0x7FC], bl
        jne elder
        push eax
        push ecx
        push edx
        push ecx
        call ee_is_elder
        add esp, 4
        test eax, eax
        pop edx
        pop ecx
        pop eax
        jnz elder
        push V2_TITLE_RANK
        ret
    elder:
        push V2_TITLE_ELDER
        ret
    }
}

static int __cdecl ee_v2_buried(const unsigned char *record) {
    int yes = ee_rule(record);
    if (yes) {
        ++g_graves;
    }
    return yes;
}

/* In place of `mov al, [ecx+0x7FC] / test al, al / je 0x465172`: ecx the record.  The game's own elder
   epitaph (0x465146) reloads ecx and al is not read again; the job's epitaph (0x465172) reloads eax. */
__declspec(naked) static void v2_grave_stub(void) {
    __asm {
        cmp byte ptr [ecx + 0x7FC], 0
        jne elder
        push ecx
        push edx
        push ecx
        call ee_v2_buried
        add esp, 4
        test eax, eax
        pop edx
        pop ecx
        jnz elder
        push V2_GRAVE_JOB
        ret
    elder:
        push V2_GRAVE_ELDER
        ret
    }
}

/* ---- The Tree of Life ---------------------------------------------------------------------------------------- */

/* In place of `call 0x46AC70 / test al, al / je 0x440335`: ecx and esi the record's skills (+0x1C5C), [esp+0x10]
   the record (0x4402EF). */
__declspec(naked) static void v4_title_stub(void) {
    __asm {
        mov eax, V4_SCHOLAR_TEST
        call eax
        test al, al
        jnz scholar
        push dword ptr [esp + 0x10]
        call ee_is_elder
        add esp, 4
        test eax, eax
        jnz elder
        push V4_RANK
        ret
    scholar:
        push V4_SCHOLAR
        ret
    elder:
        call ee_title
        push eax
        lea edx, [esp + 0x2C]
        push edx
        push V4_COPY
        ret
    }
}

/* The grave the writer just made for `record`: an adult, not a Scholar, who is an Esteemed Elder gets the
   title's epitaph in place of the job's. */
static void __stdcall ee_v4_buried(unsigned char *grave, const unsigned char *record) {
    __try {
        if (*(const int *)(grave + V4_GRAVE_AGE) >= ADULT_AGE && grave[V4_GRAVE_SCHOLAR] == 0
            && vv_elder_rule(4, record)) {
            lstrcpynA((char *)grave + V4_GRAVE_EPITAPH, ee_text(V4_EPITAPH_BYTES), V4_EPITAPH_BYTES);
            ++g_graves;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of `mov eax, [esp+0x14] / mov ecx, [esp+0x20]` after the epitaph copy (its three arguments still on
   the stack): esi the grave, [esp+0x1C] the record (the writer's first argument). */
__declspec(naked) static void v4_grave_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x20 + 0x1C]
        push esi
        call ee_v4_buried
        popad
        mov eax, dword ptr [esp + 0x14]
        mov ecx, dword ptr [esp + 0x20]
        push V4_GRAVE_NEXT
        ret
    }
}

/* ---- New Believers ---------------------------------------------------------------------------------------- */

/* In place of `call 0x475610 / test al, al / je 0x442EFD`: ecx the record's skills, [esp+0x10] the record.  The
   game's own three-mastered test, then never for a current Heathen. */
__declspec(naked) static void v5_title_stub(void) {
    __asm {
        mov eax, V5_ELDER_TEST
        call eax
        test al, al
        jz rank
        mov eax, dword ptr [esp + 0x10]
        cmp byte ptr [eax + V5_FACTION], 0
        jne rank
        push V5_ELDER
        ret
    rank:
        push V5_RANK
        ret
    }
}

/* ---- Exports ---------------------------------------------------------------------------------------------- */

/* 1 when every site of this game is in (native/shared/esteemed_elder.h vv_elders_row_on), else 0. */
int __stdcall VvfpEsteemedEldersInstalled(void) {
    return g_installed;
}

/* How many titles (and graves) this companion gave this session (for the tests' emulation). */
unsigned int __stdcall VvfpEsteemedEldersGiven(int graves) {
    return graves ? g_graves : g_titles;
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    vvfp_site_write sites[2];
    int count = 0;
    (void)shipped;
    if (g_installed) {
        return;
    }
    switch (game) {
    case 1:
        vvfp_site_branch(&sites[count++], V1_TITLE_SITE, (int)sizeof V1_TITLE_STOCK, V1_TITLE_STOCK, 0xE9,
                         (const void *)v1_title_stub);
        break;
    case 2:
        vvfp_site_branch(&sites[count++], V2_TITLE_SITE, (int)sizeof V2_TITLE_STOCK, V2_TITLE_STOCK, 0xE9,
                         (const void *)v2_title_stub);
        vvfp_site_branch(&sites[count++], V2_GRAVE_SITE, (int)sizeof V2_GRAVE_STOCK, V2_GRAVE_STOCK, 0xE9,
                         (const void *)v2_grave_stub);
        break;
    case 4:
        vvfp_site_branch(&sites[count++], V4_TITLE_SITE, (int)sizeof V4_TITLE_STOCK, V4_TITLE_STOCK, 0xE9,
                         (const void *)v4_title_stub);
        vvfp_site_branch(&sites[count++], V4_GRAVE_SITE, (int)sizeof V4_GRAVE_STOCK, V4_GRAVE_STOCK, 0xE9,
                         (const void *)v4_grave_stub);
        break;
    case 5:
        vvfp_site_branch(&sites[count++], V5_TITLE_SITE, (int)sizeof V5_TITLE_STOCK, V5_TITLE_STOCK, 0xE9,
                         (const void *)v5_title_stub);
        break;
    default:
        return;                         /* The Secret City: the stock game's own title */
    }
    g_game = game;
    if (vvfp_install_sites(sites, count)) {
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
