/* Records that look like villagers and are not.

   Each game keeps some records in its villager table, flagged active, that it
   does not count as villagers: The Lost Children's Esteemed Elder statue
   (+0x558; live, 2026-10-06: the owner's slot 23 held 126 active records, 11
   of them statues, and the game showed Population 115), The Secret City's
   +0xE94 records, The Tree of Life's ghosts (+0x1CC7) and New Believers'
   Reanimate in progress (+0x1CE1 on the villager; its stand-in body is made in
   the first free record).  Every companion that lists or looks up villagers
   leaves them out (first in vvfp_cause_of_death.c).

   A game's records each have their own size, so the stride names the game:
   the layouts that ask carry no game number.  Header-only and static. */
#ifndef VV_VILLAGER_LOOKALIKE_H
#define VV_VILLAGER_LOOKALIKE_H

static int vv_lookalike(unsigned int stride, const unsigned char *record) {
    switch (stride) {
    case 0xE48Cu: return record[0x558] != 0;       /* The Lost Children */
    case 0x1F8Cu: return record[0xE94] != 0;       /* The Secret City */
    case 0x2E3Cu: return record[0x1CC7] != 0;      /* The Tree of Life */
    case 0x2F44u: return record[0x1CE1] != 0;      /* New Believers */
    default: return 0;                             /* A New Home: none */
    }
}

#endif /* VV_VILLAGER_LOOKALIKE_H */
