/* The special title of a villager, for the logs' "Special villager:" line.

   The owner (2026-10-06): "in the logs please signify Special Villagers", and
   the list, in this order: Tribal Chief, Retired Heathen Chief, Heathen
   Mommy, Former Heathen (blue/red/orange mask), Former Heathen Master
   (purple mask), Golden Child, Esteemed Elder, Scholar -- current Heathens
   keeping every role title the game's Details panel gives them (the owner's
   answer), a converted Heathen Doctor being a Former Heathen Master.

   Each game's own facts (static analysis of the stock executables; record
   offsets from each record's start as every exporter and companion uses
   them):

     A New Home         Golden Child             i32 +0x36C == 0xC7 (0x41FBDC)
     The Lost Children  Esteemed Elder           u8 +0x7FC != 0 (0x429C1D)
     The Secret City    Tribal Chief             u8 +0xE80 != 0, tested first (0x468E01)
                        Esteemed Elder           3 or more of the five i32 skills
                                                 +0xEAC..+0xEBC at 88 or more (0x462570)
     The Tree of Life   Scholar                  all five float skills +0x1C5C..+0x1C6C
                                                 at 88.0 or more (0x46AC70)
     New Believers      a Heathen (u8 +0x1CEC) whose role (i32 +0x1CFC) is 12..17
                        is shown by the role alone, over everything else (0x443102,
                        jump table 0x443270, strings 0xD4-0xD9):
                          12 Heathen Doctor, 13 Heathen Chief, 14 Heathen Master
                          Scientist, 15 Heathen Master Builder, 16 Heathen Master
                          Farmer, 17 Heathen Mommy
                        a believer still of role 13: the conversion 0x4668B0 keeps
                          13 only for the Heathen Chief (0x466966) -- Retired
                          Heathen Chief
                        a believer converted from the Heathens: the mask they wore
                          (native/shared/former_heathens.h, the Former Heathens
                          file, `former` here; else the orange +0x1CED / red
                          +0x1CEE mask bytes the conversion leaves) -- Former
                          Heathen (blue/orange/red mask), Former Heathen Master
                          (purple mask)
                        otherwise, with 3 or more of the six float skills
                        +0x1C5C..+0x1C70 at 88.0 or more (0x475610): Esteemed Elder

   "Master <skill>" is never a title in any game: it is the ordinary
   skill-and-job label.  NULL for a villager with no special title.

   Header-only and static. */
#ifndef VVFP_SPECIAL_TITLE_H
#define VVFP_SPECIAL_TITLE_H

#include <windows.h>
#include <stdint.h>
#include "former_heathens.h"

static int vv_title_count_at_least(const unsigned char *r, unsigned int at, int count,
                                   int floats) {
    int i, n = 0;
    for (i = 0; i < count; ++i) {
        n += floats ? *(const float *)(r + at + 4u * (unsigned)i) >= 88.0f
                    : *(const int *)(r + at + 4u * (unsigned)i) >= 88;
    }
    return n;
}

/* `former` is New Believers' Former Heathens file's kind for this villager
   (VV_FORMER_*), or -1 when the file has none (or for any other game). */
static const char *vv_special_title_former(int game, const unsigned char *r, int former) {
    static const char *const VV5_HEATHENS[] = {
        "Heathen Doctor", "Heathen Chief", "Heathen Master Scientist",
        "Heathen Master Builder", "Heathen Master Farmer", "Heathen Mommy",
    };
    if (r == NULL) {
        return NULL;
    }
    switch (game) {
    case 1:
        return *(const int *)(r + 0x36C) == 0xC7 ? "Golden Child" : NULL;
    case 2:
        return r[0x7FC] != 0 ? "Esteemed Elder" : NULL;
    case 3:
        if (r[0xE80] != 0) {
            return "Tribal Chief";
        }
        return vv_title_count_at_least(r, 0xEAC, 5, 0) >= 3 ? "Esteemed Elder" : NULL;
    case 4:
        return vv_title_count_at_least(r, 0x1C5C, 5, 1) >= 5 ? "Scholar" : NULL;
    case 5: {
        int role = *(const int *)(r + VV5_TYPE);
        if (r[VV5_FACTION] != 0) {
            if (role >= 12 && role <= 17) {
                return VV5_HEATHENS[role - 12];
            }
        } else if (role == 13) {
            return vv_former_title(VV_FORMER_CHIEF);
        } else if (former >= VV_FORMER_BLUE && former <= VV_FORMER_CHIEF) {
            return vv_former_title(former);
        } else if (r[VV5_ORANGE] != 0 || r[VV5_RED] != 0) {
            return vv_former_title(r[VV5_ORANGE] != 0 ? VV_FORMER_ORANGE : VV_FORMER_RED);
        }
        return vv_title_count_at_least(r, 0x1C5C, 6, 1) >= 3 ? "Esteemed Elder" : NULL;
    }
    default:
        return NULL;
    }
}

static const char *vv_special_title(int game, const unsigned char *r) {
    return vv_special_title_former(game, r, -1);
}

#endif
