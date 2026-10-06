#ifndef VVFP_VILLAGE_ELDERS_H
#define VVFP_VILLAGE_ELDERS_H

/* The most lines the elders file may hold: a longer file is not read
   (village_elders.c load), so the reconcile refuses it too. */
#define VV_ELDERS_FILE_MAX 4096

/* Where a game keeps what Village Elders reads. Offsets are into the
   villager record (from the record base) and into a memorial record. A zero
   pointer or offset means "this game has none". */
struct elders_layout {
    const unsigned char *villagers;    /* villager container */
    unsigned int record_base;          /* container header before slot 0 */
    unsigned int stride;
    unsigned int slots;
    unsigned int active;               /* u8, == 1 when the slot is live */
    unsigned int tribe;                /* u8, 0 = one of the player's villagers; offset 0 = every
                                          live record is (VV5 keeps its heathens in the same array) */
    unsigned int name;
    unsigned int name_capacity;
    unsigned int father_name;          /* the villager's own parents, 0 = not stored */
    unsigned int mother_name;
    unsigned int parent_name_capacity;
    unsigned int skills;
    unsigned int skill_count;
    int skills_are_float;
    int master_int;                    /* the game's own Master threshold */
    float master_float;
    const unsigned char *graves;       /* memorial / Roster of the Dead */
    unsigned int grave_stride;
    unsigned int grave_capacity;
    unsigned int grave_occupied;       /* dword, non-zero when occupied */
    unsigned int grave_name;
    unsigned int grave_name_capacity;
    unsigned int grave_elder_flag;     /* u8 the game's burial writer stores, 0 = none */
    /* Where the previous save's villagers are after a reload: the games save
       their occupied records packed and load them into records 0, 1, 2, ...,
       so rank_of_slot[s] is the record the villager the previous save found
       at record s comes back in (its rank among that save's living
       villagers), -1 when that save found nobody there.  NULL (or
       rank_slots 0) when the previous roster is not known. */
    const int *rank_of_slot;
    unsigned int rank_slots;
};

/* Update the save's Village Elders .dat and return the number of elders,
   or -1 when the file cannot be read or written. */
int vv_village_elders(int game_id, int save_id, const struct elders_layout *layout);

/* The same, on explicit .dat and temporary paths (used by the harness). */
#include <wchar.h>
int vv_village_elders_file(int game_id, const wchar_t *path, const wchar_t *temporary,
                           const struct elders_layout *layout);

#endif
