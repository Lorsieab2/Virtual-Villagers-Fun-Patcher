/* The special title a villager's Details panel shows, for the logs' "Special
   villager:" line (the owner, 2026-10-06: "in the logs please signify Special
   Villagers (tribal chief, esteemed elder, scholar, retired chief, golden
   child etc etc)").

   Each game's own rule, read from its Details-panel title code (static
   analysis of the stock executables; record offsets from each record's start
   as every exporter and companion uses them):

     A New Home         Golden Child             i32 +0x36C == 0xC7 (0x41FBDC)
     The Lost Children  Esteemed Elder           u8 +0x7FC != 0 (0x429C1D)
     The Secret City    Tribal Chief             u8 +0xE80 != 0, tested first (0x468E01)
                        Esteemed Elder           3 or more of the five i32 skills
                                                 +0xEAC..+0xEBC at 88 or more (0x462570)
     The Tree of Life   Scholar                  all five float skills +0x1C5C..+0x1C6C
                                                 at 88.0 or more (0x46AC70)
     New Believers      a Heathen (u8 +0x1CEC) whose role (i32 +0x1CFC) is 12..17
                        is shown by the role alone, over everything else (0x443102):
                          12 Heathen Doctor, 13 Heathen Chief, 14 Heathen Master
                          Scientist, 15 Heathen Master Builder, 16 Heathen Master
                          Farmer, 17 Heathen Mommy
                        otherwise, with 3 or more of the six float skills
                        +0x1C5C..+0x1C70 at 88.0 or more (0x475610):
                          Retired Chief    role 13 once the puzzle progress 0x10 is
                                           reached: [0x51E008 + 0x80] >= [0x51DF30 + 0x40]
                                           (0x43AE80(0x10), 0x442EBE)
                          Esteemed Elder   otherwise

   "Master <skill>" is never a title in any game: it is the ordinary
   skill-and-job label.  NULL for a villager with no special title.

   Header-only and static. */
#ifndef VVFP_SPECIAL_TITLE_H
#define VVFP_SPECIAL_TITLE_H

#include <windows.h>
#include <stdint.h>

static int vv_title_count_at_least(const unsigned char *r, unsigned int at, int count,
                                   int floats) {
    int i, n = 0;
    for (i = 0; i < count; ++i) {
        n += floats ? *(const float *)(r + at + 4u * (unsigned)i) >= 88.0f
                    : *(const int *)(r + at + 4u * (unsigned)i) >= 88;
    }
    return n;
}

/* New Believers' puzzle progress 0x10 (0x43AE80), read only when both words
   are readable; 0 otherwise (no Retired Chief claimed). */
static int vv_title_vv5_retired_gate(void) {
    const int *done = (const int *)(uintptr_t)(0x51E008u + 0x10u * 8u);
    const int *need = (const int *)(uintptr_t)(0x51DF30u + 0x10u * 4u);
    if (IsBadReadPtr(done, sizeof *done) || IsBadReadPtr(need, sizeof *need)) {
        return 0;
    }
    return *done >= *need;
}

static const char *vv_special_title(int game, const unsigned char *r) {
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
        int role = *(const int *)(r + 0x1CFC);
        if (r[0x1CEC] != 0 && role >= 12 && role <= 17) {
            return VV5_HEATHENS[role - 12];
        }
        if (vv_title_count_at_least(r, 0x1C5C, 6, 1) < 3) {
            return NULL;
        }
        return role == 13 && vv_title_vv5_retired_gate() ? "Retired Chief" : "Esteemed Elder";
    }
    default:
        return NULL;
    }
}

#endif
