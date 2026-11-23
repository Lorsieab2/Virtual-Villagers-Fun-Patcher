/* Esteemed Elders in Every Game: who is an Esteemed Elder by the row's rule,
   and whether the row is in this game (its companion loaded and installed).

   The owner (2026-11-22): "all 5 games should change a villager's title to
   'Esteemed Elder' if they master 3 skills (EXCEPT SPECIAL VILLAGERS LIKE THE
   GOLDEN CHILD, VV3 TRIBAL CHIEF ETC)".  Mastered is the game's own Master
   level -- the level its Villager Details screen first says "Master" at.
   The Secret City and New Believers already give the title in the stock game
   (0x462570, 0x475610: three or more skills at 88 or more) and are left as
   they are; this rule is the other three's:

     A New Home         five i32 skills +0x3BC..+0x3CC, Master from 90 (the
                        Details screen 0x41FC16 `cmp eax, 0x5A`; the grave
                        0x436565 and Village Statistics' Village Elders use
                        the same 90).  Never the Golden Child (+0x36C == 0xC7,
                        0x41FBDC): his title comes first.
     The Lost Children  five i32 skills +0x7E4..+0x7F4, Master from 88
                        (0x429C59 `cmp eax, 0x58`); the stock flag +0x7FC (the
                        elder pass 0x44D4C0, which also makes the totem) still
                        gives it too.  Never a totem statue (+0x558 != 0, set
                        only by 0x44D485).
     The Tree of Life   five float skills +0x1C5C..+0x1C6C, Master from 88.0
                        (0x440359 `cmp eax, 0x58`); all five is the game's
                        Scholar (0x46AC70), which still wins, so three or
                        four.  Never a ghost (+0x1CC7 != 0, 0x466370).

   The row's companion is "VVFP Esteemed Elders.dll"
   (native/vvfp_esteemed_elders): the title on the Villager Details screen and
   the epitaph on a new grave.  Every other reader -- the logs' "Special
   villager:" line (special_title.h), A New Home's grave epitaph (Cause of
   Death) -- asks vv_elders_row_on() first, so with the row out of the game
   nothing changes.

   Header-only and static. */
#ifndef VVFP_ESTEEMED_ELDER_H
#define VVFP_ESTEEMED_ELDER_H

#include <windows.h>

#define VV_ELDERS_DLL "VVFP Esteemed Elders.dll"
#define VV_ELDERS_INSTALLED "VvfpEsteemedEldersInstalled"
#define VV_ELDERS_TITLE "Esteemed Elder"
#define VV_ELDERS_NEEDED 3

/* How many of the record's skills are at the game's Master level (games 1, 2, 4). */
static int vv_elder_mastered(int game, const unsigned char *r) {
    int i, n = 0;
    for (i = 0; i < 5; ++i) {
        switch (game) {
        case 1: n += *(const int *)(r + 0x3BC + 4 * i) >= 90; break;
        case 2: n += *(const int *)(r + 0x7E4 + 4 * i) >= 88; break;
        case 4: n += *(const float *)(r + 0x1C5C + 4 * i) >= 88.0f; break;
        default: return 0;
        }
    }
    return n;
}

/* 1 when the villager in `r` is an Esteemed Elder by the row's rule (A New
   Home, The Lost Children, The Tree of Life); 0 for anyone else, a special
   villager, or another game. */
static int vv_elder_rule(int game, const unsigned char *r) {
    int n;
    if (r == NULL) {
        return 0;
    }
    switch (game) {
    case 1:
        if (*(const int *)(r + 0x36C) == 0xC7) {
            return 0;                       /* the Golden Child */
        }
        return vv_elder_mastered(1, r) >= VV_ELDERS_NEEDED;
    case 2:
        if (r[0x558] != 0) {
            return 0;                       /* a totem statue */
        }
        return r[0x7FC] != 0 || vv_elder_mastered(2, r) >= VV_ELDERS_NEEDED;
    case 4:
        if (r[0x1CC7] != 0) {
            return 0;                       /* a ghost */
        }
        n = vv_elder_mastered(4, r);
        return n >= VV_ELDERS_NEEDED && n < 5;     /* all five: the game's Scholar */
    default:
        return 0;
    }
}

typedef int (__stdcall *vv_elders_installed_fn)(void);

/* 1 when "VVFP Esteemed Elders.dll" is loaded in this game and its sites are
   in: the row is in the exe and working.  Asked each time (a handful of
   kernel32 calls): the startup companion loads it before the game's first
   frame, and nothing unloads it. */
static int vv_elders_row_on(void) {
    HMODULE module = GetModuleHandleA(VV_ELDERS_DLL);
    vv_elders_installed_fn installed;
    if (module == NULL) {
        return 0;
    }
    installed = (vv_elders_installed_fn)GetProcAddress(module, VV_ELDERS_INSTALLED);
    return installed != NULL && installed() != 0;
}

#endif /* VVFP_ESTEEMED_ELDER_H */
