/* The game's own villager creators, by game: every record a creator fills
   is reported as an arrival (roster_arrived).  Births, twins and triplets,
   founders, every event's newcomers and the Custom Island Event's new
   villagers all go through these.  Included by cod_roster.inc.

   Each hook sits inside the creator, after it has chosen the record, with
   esi = the record:
     A New Home        fresh 0x43C350 at 0x43C39B, copy 0x43C840 at 0x43C885
     The Lost Children fresh 0x44C600 at 0x44C84F, copy 0x44CEC0 at 0x44CF04
     The Secret City   fresh init 0x456120 at 0x456326, copy init 0x4566E0
                       at 0x4566EF
     The Tree of Life  fresh init 0x45EF10 at 0x45F175, copy init 0x45D9B0
                       at 0x45D9BB
     New Believers     fresh init 0x4681F0 at 0x468411, copy init 0x4687F0
                       at 0x4687FE
   The Lost Children's Esteemed Elder statue (0x44D190) and The Tree of
   Life's ghosts are look-alikes, never villagers, so they need no report.

   TEMPORARY RECORDS.  Two creations are never members of the tribe and
   are kept out of the roster and the logs:
     The Lost Children's The Strange Request makes a stranger for the event
       (0x41F95E) and both its outcomes take him away again: the call
       returns his index in eax at 0x41F963.
     New Believers' Reanimate makes a stand-in corpse (manager 0x46FDE0,
       through the same init 0x4681F0) and removes it when the effect ends.
       The manager's entry marks the next init as the stand-in; a manager
       that finds no free record makes none, so the mark lasts only until
       the next tick. */

static int standin_pending;

static void roster_created(int site, const unsigned int *regs) {
    int index = cod_index_of((const unsigned char *)(uintptr_t)regs[R_ESI]);
    (void)site;
    if (index < 0) {
        return;
    }
    temporary[index] = (unsigned char)(standin_pending != 0);
    standin_pending = 0;
    if (!temporary[index]) {
        roster_arrived(index);
    }
}

/* VV2 0x41F963: The Strange Request's stranger, eax = his index. */
static void vv2_stranger(int site, const unsigned int *regs) {
    int index = (int)regs[R_EAX];
    (void)site;
    if (index >= 0 && index < RECORDS_MAX) {
        temporary[index] = 1;
    }
}

/* VV5 0x46FDE0: the Reanimate stand-in's manager. */
static void vv5_standin(int site, const unsigned int *regs) {
    (void)site; (void)regs;
    standin_pending = 1;
}

static void roster_sites(void) {
    switch (g_game) {
    case 1:
        cod_add(0x43C39Bu, "C6462A00" "896E40", roster_created);
        cod_add(0x43C885u, "885E29" "885E2A" "895E40", roster_created);
        break;
    case 2:
        cod_add(0x44C84Fu, "C6865805000000", roster_created);
        cod_add(0x44CF04u, "885E31" "885E32", roster_created);
        cod_add(0x41F963u, "8B8EB0500000", vv2_stranger);
        break;
    case 3:
        cod_add(0x456326u, "889E110F0000" "889E120F0000", roster_created);
        cod_add(0x4566EFu, "889E110F0000" "889E120F0000", roster_created);
        break;
    case 4:
        cod_add(0x45F175u, "889EC51C0000" "889EC61C0000", roster_created);
        cod_add(0x45D9BBu, "C686C51C000000", roster_created);
        break;
    case 5:
        cod_add(0x468411u, "8BCE" "89842490000000", roster_created);
        cod_add(0x4687FEu, "889ED51C0000", roster_created);
        cod_add(0x46FDE0u, "5356" "8BD9" "57", vv5_standin);
        break;
    default:
        break;
    }
}
