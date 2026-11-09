/* A BARREL OF BABIES THAT CAN NEVER ARRIVE IS REFUNDED (The Tree of Life, New Believers).

   The owner (2026-11-09), on PR #745: "A Barrel bought in a village with no adults left: REFUND it.
   Give back exactly what it cost (0 if it was free ...), then clear it so nothing stays blocked ...
   Decide 'no adults' with the trigger's own test ... Refund it once, never twice ... and tell the
   player with a short message."

   WHICH GAMES.  The Tree of Life's and New Believers' purchased Barrel rides the game's own
   island-event trigger: the purchase zeroes the shared timer (The Tree of Life [world+0x170E0],
   New Believers [manager+0x17D3C]) and the barrel is presented from inside that trigger (The Tree
   of Life's cue at 0x43FBE5, New Believers' selector stub at 0x41890F).  A New Home, The Lost
   Children and The Secret City deliver theirs from their own frame code (the main tick's delay
   counter, the cue counter, the island handler's frame hook), which waits for nothing but room --
   their barrel always comes, and waiting for room is never refunded.

   THE TRIGGER'S OWN TEST.  Once the timer is due, each trigger asks the game's own count of the
   villagers it can run an event for (The Tree of Life 0x467610 on its villager manager, New
   Believers 0x4713F0, believers only) and does nothing -- not even reschedule -- while it is 0:

       The Tree of Life  0x43FA49  mov ecx, <manager>   0x43FA4E  call 0x467610   je 0x43FC0E
       New Believers     0x4426F6  mov ecx, <manager>   0x4426FB  call 0x4713F0   je 0x44285F

   (the manager is read from the trigger's own `mov ecx, imm32`, which 256 Villagers moves).  Past
   that, the trigger draws a living villager of ANY age (0x4679B0 / 0x471870 with no age bounds) and
   waits only while that villager's age has not caught up with its processed age, which it always
   does -- so a village of children still gets its barrel; one where the count is 0 never does.
   That count is what is asked here, at the very moment the trigger finds the timer due (the
   island-timer keeper's itk_due_hook): only in play, with the village loaded, never on a load
   frame.  (New Believers also waits while a God Power is armed, which passes by itself.)

   THE REFUND.  The barrel's price is added back to the village's tech points as the game holds
   them (written directly, as the Story / Cheat Upgrades' tech changes are, so no doubler doubles
   it): the Origins price, or 0 when the Origins upgrades are free (Story / Cheat Upgrades without
   its "cost Tech Points" row) -- exactly what the purchase charged in this patched game.  The
   barrel's pending state is cleared in the same step, so no later check can pay again; The Tree of
   Life's Paid Purchases file goes at once (a reload never re-arms it), and New Believers' bits are
   in the save itself, so whichever save is loaded holds either the barrel or the refund, never
   both.  The shared timer goes back to the game's own next event's time (the keeper's
   itk_withdraw), unless an Island Event bought too is still waiting on it (it is the Custom Island
   Event's to replace there, story_custom_ui.inc).  The player is told at once by a message box
   (vv_br_tell), in their language (vvfp_tr): the trigger runs on the game's own thread between
   frames, and an empty village draws no villager whose frame could tell them later.

   Included by each of the two games' Origins companions after island_timer_keep.h; everything is
   file-static. */
#ifndef VV_BARREL_REFUND_H
#define VV_BARREL_REFUND_H

#include <windows.h>

typedef struct {
    int game;
    unsigned int count_routine;        /* the trigger's own count, thiscall */
    unsigned int count_this_imm;       /* the VA of the imm32 of the trigger's `mov ecx, <manager>` */
    volatile int *tech;                /* the village's tech points */
    int (*pending)(void);              /* a purchased barrel not yet presented */
    int (*island_waiting)(void);       /* an Island Event bought too, waiting on the same timer */
    void (*cancel)(void);              /* clear the barrel's pending state */
    int (*price)(void);                /* what the barrel cost: the Origins price, or 0 when free */
    void (*withdrawn)(void);           /* its per-slot file, if it has one */
} vv_barrel_refund_game;

static const vv_barrel_refund_game *vv_br_g;
static int vv_br_count;                /* refunds made (the tests read it) */

static int vv_br_living(const vv_barrel_refund_game *g) {
    void *manager = *(void *const volatile *)(UINT_PTR)g->count_this_imm;
    if (manager == NULL) {
        return -1;                     /* no village to ask */
    }
    return ((int (__fastcall *)(void *, void *))(UINT_PTR)g->count_routine)(manager, NULL);
}

#ifndef VV_BARREL_REFUND_TELL
/* Tell the player, at once (the trigger runs on the game's own thread, between frames). */
static void vv_br_tell(int refunded) {
    char amount[24];
    char text[600];
    if (refunded > 0) {
        if (refunded >= 1000) {
            wsprintfA(amount, "%d,%03d", refunded / 1000, refunded % 1000);
        } else {
            wsprintfA(amount, "%d", refunded);
        }
        wsprintfA(text, vvfp_tr("vvfp.shared/barrel_refund.vv_br_tell.s0",
                                "Nobody is left in the village to receive the Barrel of Babies, so it has been "
                                "cancelled and its %s tech points have been given back.", 400), amount);
    } else {
        lstrcpynA(text, vvfp_tr("vvfp.shared/barrel_refund.vv_br_tell.s1",
                                "Nobody is left in the village to receive the Barrel of Babies, so it has been "
                                "cancelled. It cost no tech points, so none were given back.", 400),
                  sizeof text);
    }
    vvfp_message_box(GetActiveWindow(), text, "Barrel of Babies",
                     MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND);
}
#else
#define vv_br_tell(refunded) VV_BARREL_REFUND_TELL(refunded)
#endif

/* itk_due_hook: the trigger has found the timer at `field` due. */
static int __cdecl vv_br_due(unsigned int *field) {
    const vv_barrel_refund_game *g = vv_br_g;
    int price, withdrawn;
    if (g == NULL || !g->pending() || vv_br_living(g) != 0) {
        return 0;
    }
    price = g->price();
    if (price < 0) {
        price = 0;
    }
    g->cancel();                       /* first: no second check can find it pending */
    *g->tech += price;
    if (g->withdrawn != NULL) {
        g->withdrawn();
    }
    ++vv_br_count;
    withdrawn = !g->island_waiting() && itk_withdraw(field);   /* the game's own next event keeps its time */
    vv_br_tell(price);
    return withdrawn;
}

static void vv_br_install(const vv_barrel_refund_game *g) {
    vv_br_g = g;
    itk_due_hook = vv_br_due;
}


#endif /* VV_BARREL_REFUND_H */
