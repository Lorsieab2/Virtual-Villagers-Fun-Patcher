/* How each villager the game's creators make came, by game: the return
   addresses on the paths into the creators (cod_roster_sites.inc).  Included
   by cod_arrivals.inc.

   At a creator's hook the stack above it holds the return addresses of the
   calls that led there; the first one found in this table, scanning up from
   the hook's esp, names the path.  Each value is the address right after a
   call instruction in the stock executable, on exactly one path, so it can
   only be on the stack while that path runs.  MARK_BIRTH: a child of a
   delivery (never an arrival, whatever the Births log says);
   MARK_FOUNDER: a new village's starting villagers; MARK_EVENT: the label is
   what the record's "How:" line says.  A villager made on no listed path is
   "unknown". */

#define MARK_BIRTH 1
#define MARK_FOUNDER 2
#define MARK_EVENT 3

/* How far above the hook the scan looks: deeper than any listed path's
   innermost marker, and never past the thread's own stack. */
#define ARRIVAL_STACK_SCAN 0x400

struct arrival_marker {
    unsigned int ret;
    int kind;
    const char *label;
};

/* A New Home: the delivery's four child-creation calls (0x42EF5F, 0x42EFD0
   to the fresh creator 0x43C350; 0x42F021, 0x42F06D to the copy creator
   0x43C840). */
static const struct arrival_marker MARKERS_VV1[] = {
    { 0x42EF64u, MARK_BIRTH, NULL },
    { 0x42EFD5u, MARK_BIRTH, NULL },
    { 0x42F026u, MARK_BIRTH, NULL },
    { 0x42F072u, MARK_BIRTH, NULL },
};

static void arrival_markers(const struct arrival_marker **table, int *count) {
    switch (g_game) {
    case 1:
        *table = MARKERS_VV1;
        *count = (int)(sizeof MARKERS_VV1 / sizeof MARKERS_VV1[0]);
        break;
    default:
        *table = NULL;
        *count = 0;
        break;
    }
}
