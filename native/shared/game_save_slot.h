/* The game's own current save slot -- the slot its next save writes -- for
   all five games.

   The companions used to know the slot only from the executable's save-path
   stub, which records the number each time the game builds a "%s%d.ldw"
   path.  That number is not always the village on screen:

     - A New Home, first village of a fresh save folder: the game rebuilds its
       slot list by loading slots 1..5 (0x41D260), so the stub holds 5; the
       new village is then made in slot 1 with no load and no save of slot 1
       (its first save waits until the village has started, 0x41BF70 tests
       manager+0x9E1C), and every file written at creation was "Save 5".
     - The Lost Children, The Secret City, The Tree of Life: the "save all"
       routine (VV2 0x424C00, VV3
       0x427D90, VV4 0x41F160) saves the slot and then its backup generation,
       slot + 20, so after every autosave (each 600 s), every Change Tribe and
       every new tribe a stub that keeps any number holds 21..25 (The Lost
       Children's does, 0x4B3F10), which reads as "no slot" until
       the next load or quit save.  A tribe made with Change Tribe therefore
       had no slot for its whole first session.

   The game itself keeps the slot in its save manager, a singleton, and every
   save of the village uses that field (VV1 0x41B245, VV2 0x423C45, VV4
   0x41E4D8; the save-all routines above): VV1 [0x48AEDC]+0xABE4, VV2
   [0x4997BC]+0x30378, VV3 [0x4B309C]+0x12F24, VV4 [0x4CB51C]+0x17114, VV5
   [0x4DACE0]+0x17D80 (the singletons are stored right after their
   constructors: VV1 0x41D53E, VV2 0x426D7E, VV3 0x428B9E, VV4 0x41FEB9, VV5
   0x425999).  The field is the first dword of the meta block the game loads
   from slot 0 at start, and the slot-select menu sets it before it creates
   or loads a village there.

   vv_current_save_slot(game, captured) answers that field when it holds a
   slot (1..5), and otherwise the stub's captured slot -- before the save
   manager exists, and in the native harnesses, whose zero-filled stand-in
   memory reads as no manager. */
#ifndef VV_GAME_SAVE_SLOT_H
#define VV_GAME_SAVE_SLOT_H

static const unsigned int VV_GAME_SAVE_MANAGER[6] = {
    0, 0x0048AEDCu, 0x004997BCu, 0x004B309Cu, 0x004CB51Cu, 0x004DACE0u
};
static const unsigned int VV_GAME_SAVE_SLOT_FIELD[6] = { 0, 0xABE4u, 0x30378u, 0x12F24u, 0x17114u, 0x17D80u };

/* Where the singleton pointer is read from; a native harness defines this
   before the include to stand in for the game's own address. */
#ifndef VV_GAME_SAVE_MANAGER_AT
#define VV_GAME_SAVE_MANAGER_AT(game) \
    ((const unsigned char *const volatile *)(UINT_PTR)VV_GAME_SAVE_MANAGER[game])
#endif

static int vv_game_save_slot(int game) {
    const unsigned char *manager;
    int slot;
    if (game < 1 || game > 5) {
        return 0;
    }
    manager = *VV_GAME_SAVE_MANAGER_AT(game);
    if (manager == NULL) {
        return 0;
    }
    slot = *(const volatile int *)(manager + VV_GAME_SAVE_SLOT_FIELD[game]);
    return slot >= 1 && slot <= 5 ? slot : 0;
}

static int vv_current_save_slot(int game, int captured) {
    int slot = vv_game_save_slot(game);
    if (slot != 0) {
        return slot;
    }
    return captured >= 1 && captured <= 5 ? captured : 0;
}

#endif /* VV_GAME_SAVE_SLOT_H */
