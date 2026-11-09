/* A Custom Island Event for a village where everyone has died -- all five
   games.  Included by vvfp_story_upgrades.c after the adapters.

   The owner (2026-10-21): "allow Custom Island Events to be bought and
   triggered when everyone is dead (so the player can add new villagers)".

   WHAT THE STOCK GAMES DO.  None of the five ends the village when the last
   villager dies: there is no game-over state, no return to the title and no
   change to the save.  The village goes on (the clock, the food, the menus);
   the game shows "Your tribe has been lost! Game over." on its status line
   every 2 seconds while its population count is 0 (VV1 0x421B40(0x1F) from
   the main update, VV2 0x42EE49, VV3 0x4686AF, VV4 0x43F9B7, VV5 0x442676),
   and A New Home, The Lost Children and The Tree of Life queue their "all of
   your villagers died" tip once.  The line stops by itself once the count is
   above 0 again.

   WHAT STOPPED THE EVENT.  Each game's island-event trigger, once its
   countdown is due, asks the game's own population count and does nothing
   while it is 0 -- not even rescheduling:

       A New Home        0x4237CB call 0x41CF90 (the world)            je 0x423ABE
       The Lost Children 0x42EEDB call 0x425860 (the world)            je 0x42F1D4
       The Secret City   0x468743 call 0x45E8F0 (the manager 0x59E110) je 0x4688DF
       The Tree of Life  0x43FA4E call 0x467610 (the manager 0x50E568) je 0x43FC0E
       New Believers     0x4426FB call 0x4713F0 (the manager 0x554148) je 0x44285F

   (New Believers counts believers only: a village of Heathens alone is
   empty to it, as to the owner's statistics.)  After it the trigger draws a
   living villager (story_fast_delivery.inc) and compares its two ages; the
   drawn villager is never used after that -- the register is overwritten --
   and nothing from there to the game's own popup reads a villager record for
   a custom event (its object shows no villager).  New Believers' selector
   also returns before the delivery site when no stock event's condition
   holds (0x4188E5), which an empty village can make so.  And the companion's
   own purchase refused a village with no living adult.

   THE FIX.  Each count call is replaced by a stub that runs it exactly as
   before; only when it answers 0 AND a plain Custom Island Event is queued
   for this village (ce_dead_bypass) does the trigger go on to the point
   after its villager draw -- with the registers the stock code has there
   (the value of the routine it calls between the draw and the age check:
   0x41D110 / 0x426110 / 0x402200 / 0x416EB0 / 0x417650) -- so the game
   itself reschedules the next event, plays the sound, counts the event,
   builds it (the companion's delivery point puts the custom event in it)
   and shows its own popup.  New Believers' selector, with no stock event
   possible and a plain custom event due, goes to its delivery site the way
   it does for a chosen event (its two trophy calls first, as stock).  With
   nothing queued, or a village with anyone in it, every byte runs as stock.

   The new villagers are made by the game's own creators, which need no other
   villager; skeletons are brought back by the same revive as always.  The
   village then counts them, and the game's own next tick makes it a normal
   village again (the status line stops, the trigger goes back to its
   draws).  Nothing else is changed: a question (two choices) needs a living
   villager to show, so it is refused for an empty village; and a new
   village's two opening island events are not waited for in an empty
   village, which can never have them.  A New Home's and The Lost Children's
   trigger makes a village's first island event the game's own visitor; an
   empty village that died before it gets the custom event past that check,
   uncounted, so the visitor is still its first island event once someone
   lives (ce_dead_first below). */

/* The game's own population count, as the trigger asks it.  -1 when there
   is no village to ask (the arrays not there yet). */
static int ce_population(int game) {
    unsigned char *world;
    switch (game) {
    case 1:
        world = *(unsigned char **)(uintptr_t)VV1_WORLD_GLOBAL;
        if (world == NULL || *(void **)(world + 0xADE8) == NULL) {
            return -1;
        }
        return TC0(0x41CF90u, world);
    case 2:
        world = *(unsigned char **)(uintptr_t)VV2_WORLD_GLOBAL;
        if (world == NULL || *(void **)(world + 0x305A4) == NULL) {
            return -1;
        }
        return TC0(0x425860u, world);
    /* The villager manager each build has (256 Villagers moves it). */
    case 3: return TC0(0x45E8F0u, C3_VILLAGE);
    case 4: return TC0(0x467610u, C4_MANAGER);
    case 5: return TC0(0x4713F0u, C5_MANAGER);
    default: return -1;
    }
}

/* Whether the village is empty to the game itself: there is a village and
   its own population count is 0 (no living villager and no baby on its way;
   New Believers: no living believer). */
static int ce_village_empty(int game) {
    return ce_population(game) == 0;
}

/* The game whose trigger is delivering a custom event to its empty village
   right now (0 = none): ce_held lets the event through, since an empty
   village can never have its two opening island events. */
static int ce_dead_firing;

/* A New Home / The Lost Children: the game whose empty village is being
   given a custom event before its first island event (0 = none).  The
   trigger makes a village's first island event the game's own visitor
   (VV1 0x42382C, VV2 0x42EF39: Island Events Seen still 0); for an empty
   village the stub resumes past that check (CE_DEAD_FIRST), and the
   delivery takes the trigger's count of the event back (ce_deliver), so
   Island Events Seen stays 0 and the village's first island event, once
   someone lives, is still the game's visitor -- with the 30-minute second
   one after it, as stock. */
static int ce_dead_first;

#define CE_DEAD_GO 1                   /* resume after the villager draw */
#define CE_DEAD_FIRST 2                /* ... and past the first-event visitor check */

/* Asked by a game's count stub when its count is 0: CE_DEAD_GO (or
   CE_DEAD_FIRST) = go on to the event as if a villager had been drawn, 0 =
   wait as stock.  Only a plain Custom Island Event (or the time skip's
   notice) queued for this village. */
static int __cdecl ce_dead_bypass(int game) {
    const int *counter;
    ce_dead_firing = 0;
    ce_dead_first = 0;
    if (!ce_plain_pending(game)) {
        return 0;
    }
    if (game == 1 || game == 2) {
        counter = ce_event_counter(game);
        if (counter == NULL) {
            return 0;                  /* a trigger this companion does not know */
        }
        if (*counter == 0) {
            ce_dead_firing = game;
            ce_dead_first = game;
            return CE_DEAD_FIRST;
        }
    }
    ce_dead_firing = game;
    return CE_DEAD_GO;
}

/* NOBODY THE TRIGGER ACCEPTS (the owner, 2026-11-09: "I want the following available at all times
   always: Custom Island Events (with full functionality) ESPECIALLY THE PARTS THAT BRING NEW
   VILLAGERS.  These should be a special exception where no adult is needed to spawn villagers.").
   Past its count, each trigger draws one villager with the game's own picker and runs the event only
   when that villager's age equals its processed age (story_fast_delivery.inc) -- A New Home's and The
   Lost Children's picker draws adults only (its argument 1), The Secret City's checks a live villager
   too.  So a village of children (A New Home, The Lost Children), or of villagers none of whom the
   picker or the age check accepts, never got its Custom Island Event.  With a plain one due and not
   held by the opening events, the count stub asks the same picker, with the trigger's own arguments,
   up to CE_FAST_TRIES times (as the quicker delivery does): no draw the trigger would accept, and the
   event goes on as for an empty village -- delivered by the game's own trigger, popup and count, its
   new villagers made by the game's own creators, which need no other villager. */
static int ce_trigger_accepts(int game, void *scene, void *count_this) {
    int drawn;
    switch (game) {
    case 1: case 2: {
        ce_index_pick p = { NULL, 1, game == 1 ? 0x43BCD0u : 0x44BAE0u, game == 1 ? 0x3D8u : 0xE48Cu,
                            game == 1 ? 0x348u : 0x530u, game == 1 ? 0x34Cu : 0x534u };
        if (scene == NULL || (p.self = *(void **)((unsigned char *)scene + 0x20)) == NULL) {
            return 1;                  /* nothing to ask: the game decides, as stock */
        }
        drawn = ce_fast_pick(ce_index_draw, ce_index_fits, -1, &p);
        return drawn != -1 && ce_index_fits(&p, drawn);
    }
    case 3: {
        ce_index_pick p = { count_this, 1, 0x45C9D0u, 0, 0, 0 };
        drawn = ce_fast_pick(ce_index_draw, ce_vv3_fits, -1, &p);
        return drawn != -1 && ce_vv3_fits(&p, drawn);
    }
    case 4: {
        ce_record_pick p = { count_this, { -1, -1, -1, 1, 1, -1, 0, 0, 0, 0 } };
        drawn = ce_fast_pick(ce_vv4_draw, ce_record_fits, 0, &p);
        return drawn != 0 && ce_record_fits(&p, drawn);
    }
    case 5: {
        ce_record_pick p = { count_this, { -1, -1, -1, 1, 1, -1, 0, 0, 0, 0, 0, 1, 0, 0 } };
        drawn = ce_fast_pick(ce_vv5_draw, ce_record_fits, 0, &p);
        return drawn != 0 && ce_record_fits(&p, drawn);
    }
    default:
        return 1;
    }
}

/* Asked by every count stub with the count the game answered (and the trigger's own object and the
   count's `this`): CE_DEAD_GO / CE_DEAD_FIRST = go on to the event as if a villager had been drawn,
   0 = as stock.  A count of 0 is the empty village (ce_dead_bypass); otherwise only a plain Custom
   Island Event due now, not held, in a village with nobody the trigger's own draw accepts. */
static int __cdecl ce_trigger_bypass(int game, int count, void *scene, void *count_this) {
    const int *counter = ce_event_counter(game);
    /* Before the trigger counts the event it makes: the village's first island event still to come. */
    ce_first_before = counter != NULL && *counter == 0 ? game : 0;
    if (count == 0) {
        return ce_dead_bypass(game);
    }
    ce_dead_firing = 0;
    ce_dead_first = 0;
    /* A New Home, The Lost Children: a village's first island event is the game's own visitor
       (0x42382C, 0x42EF3C).  A player's own event comes first: the trigger goes on past that check
       for it, uncounted, so the visitor is still the village's first island event after it. */
    if ((game == 1 || game == 2) && ce_first_before == game && ce_pending(game) && !ce_armed_is_notice) {
        ce_dead_first = game;
        return CE_DEAD_FIRST;
    }
    if (!ce_plain_pending(game) || ce_trigger_accepts(game, scene, count_this)) {
        return 0;
    }
    return CE_DEAD_GO;
}

/* New Believers' selector found no stock event possible: 1 = present the
   custom event instead (a plain one due now). */
static int __cdecl ce_dead_select(int game) {
    return ce_plain_pending(game) && !ce_held(game, 1);
}

/* The arm refusal's answer for a village with no living adult.  A plain
   event is never refused for it -- no adult is needed: the trigger's own
   draw is gone around when nobody it accepts lives (ce_trigger_bypass), and
   changes for villagers who are not there are skipped and named in the
   popup.  Only a question needs someone to ask: refused with `refusal`
   (someone lives but no adult), or its own words for an empty village. */
static const char *ce_empty_refusal(int game, const char *refusal) {
    if (!ce_refusal_for_choice) {
        return NULL;
    }
    if (!ce_village_empty(game)) {
        return refusal;
    }
    return "Everyone in the village has died, so there is nobody to ask a question. "
           "Untick \"Ask a question with two choices\" to send this event to the empty village.";
}

/* ---- The count stubs -------------------------------------------------------

   Each is the trigger's `call <count>` retargeted.  ECX is already what the
   stock code loads -- the world, or the villager manager, which 256
   Villagers (Experimental) moves, so the `mov ecx` before the call is left
   as it is.  The stub runs the count and returns to the stock `test eax,
   eax; je <skip>` with it -- or, with a plain custom event due and nobody
   the trigger accepts (the count 0, or no draw it would take:
   ce_trigger_bypass), drops its return address and goes on at the point
   after the villager draw and age check, with the register the stock code has there
   (EDI in A New Home / The Lost Children, EBP in the later three: the value
   of the routine called between the draw and the check).  pushad keeps
   every register for the stock path; the saved EAX is [esp+0x1C]. */

__declspec(naked) static void c1_count_stub(void) {
    __asm {
        push ecx                     /* the count's this (the world, or the villager manager) */
        mov eax, 0x41CF90
        call eax
        pushad
        push dword ptr [esp + 0x20]  /* the count's this, pushed before the call */
        push esi                     /* the trigger's own object */
        push eax                     /* the count the game answered */
        push 1
        call ce_trigger_bypass
        add esp, 16
        test eax, eax
        jnz go
        popad                        /* as stock: the game's own count */
        add esp, 4
        ret
    go:
        mov dword ptr [esp + 0x1C], eax
        popad
        add esp, 8                   /* the kept this and the return: on past the draw */
        push eax                    /* CE_DEAD_GO or CE_DEAD_FIRST */
        mov ecx, dword ptr [esi + 0x10]
        mov eax, 0x41D110
        call eax
        mov edi, eax
        xor ebp, ebp
        pop eax
        cmp eax, 2
        je first
        push 0x423816
        ret
    first:                          /* past the first-event visitor check */
        push 0x423838
        ret
    }
}

__declspec(naked) static void c2_count_stub(void) {
    __asm {
        push ecx                     /* the count's this (the world, or the villager manager) */
        mov eax, 0x425860
        call eax
        pushad
        push dword ptr [esp + 0x20]  /* the count's this, pushed before the call */
        push esi                     /* the trigger's own object */
        push eax                     /* the count the game answered */
        push 2
        call ce_trigger_bypass
        add esp, 16
        test eax, eax
        jnz go
        popad                        /* as stock: the game's own count */
        add esp, 4
        ret
    go:
        mov dword ptr [esp + 0x1C], eax
        popad
        add esp, 8                   /* the kept this and the return: on past the draw */
        push eax                    /* CE_DEAD_GO or CE_DEAD_FIRST */
        mov ecx, dword ptr [esi + 0x10]
        mov eax, 0x426110
        call eax
        mov edi, eax
        xor ebp, ebp
        pop eax
        cmp eax, 2
        je first
        push 0x42EF26
        ret
    first:                          /* past the first-event visitor check */
        push 0x42EF48
        ret
    }
}

__declspec(naked) static void c3_count_stub(void) {
    __asm {
        push ecx                     /* the count's this (the world, or the villager manager) */
        mov eax, 0x45E8F0
        call eax
        pushad
        push dword ptr [esp + 0x20]  /* the count's this, pushed before the call */
        push esi                     /* the trigger's own object */
        push eax                     /* the count the game answered */
        push 3
        call ce_trigger_bypass
        add esp, 16
        test eax, eax
        jnz go
        popad                        /* as stock: the game's own count */
        add esp, 4
        ret
    go:
        mov dword ptr [esp + 0x1C], eax
        popad
        add esp, 8                   /* the kept this and the return: on past the draw */
        mov ecx, dword ptr [esi + 0x10]
        mov eax, 0x402200
        call eax
        mov ebp, eax
        xor edi, edi
        push 0x468798
        ret
    }
}

__declspec(naked) static void c4_count_stub(void) {
    __asm {
        push ecx                     /* the count's this (the world, or the villager manager) */
        mov eax, 0x467610
        call eax
        pushad
        push dword ptr [esp + 0x20]  /* the count's this, pushed before the call */
        push esi                     /* the trigger's own object */
        push eax                     /* the count the game answered */
        push 4
        call ce_trigger_bypass
        add esp, 16
        test eax, eax
        jnz go
        popad                        /* as stock: the game's own count */
        add esp, 4
        ret
    go:
        mov dword ptr [esp + 0x1C], eax
        popad
        add esp, 8                   /* the kept this and the return: on past the draw */
        mov ecx, dword ptr [esi + 0x10]
        mov eax, 0x416EB0
        call eax
        mov ebp, eax
        xor edi, edi
        push 0x43FA9B
        ret
    }
}

/* New Believers also keeps, on the empty-village path, the stock check that
   follows its count: no God Power armed on the pointer ([0x51D5A4] == -1, the
   God Powers manager 0x51D4C8 +0xDC). */
__declspec(naked) static void c5_count_stub(void) {
    __asm {
        push ecx                     /* the count's this (the world, or the villager manager) */
        mov eax, 0x4713F0
        call eax
        pushad
        push dword ptr [esp + 0x20]  /* the count's this, pushed before the call */
        push esi                     /* the trigger's own object */
        push eax                     /* the count the game answered */
        push 5
        call ce_trigger_bypass
        add esp, 16
        test eax, eax
        jnz go
        popad                        /* as stock: the game's own count */
        add esp, 4
        ret
    go:
        mov dword ptr [esp + 0x1C], eax
        popad
        add esp, 8                   /* the kept this and the return: on past the draw */
        cmp dword ptr ds:[0x51D5A4], -1   /* the stock check after the count: no God Power armed */
        jne skip
        mov ecx, dword ptr [esi + 0x10]
        mov eax, 0x417650
        call eax
        mov ebp, eax
        xor edi, edi
        push 0x44275A
        ret
    skip:
        push 0x44285F
        ret
    }
}

/* New Believers' selector 0x418870, at 0x4188E5 `test edi, edi; je 0x4189C5`
   (edi = how many stock events are possible).  None, with a plain custom
   event due: the stock path's two trophy calls (0x413450 on 0x4DB358 with
   (0x2F, 1) and (0x30, 1), as 0x4188ED..0x418904), then the delivery site
   0x41895B with esi 1 (a valid table slot: the site's own write at 0x41899A
   marks that slot shown, as for any event). */
__declspec(naked) static void c5_select_stub(void) {
    __asm {
        test edi, edi
        jz nothing
        push 0x4188ED
        ret
    nothing:
        pushad
        push 5
        call ce_dead_select
        add esp, 4
        mov dword ptr [esp + 0x1C], eax
        popad
        test eax, eax
        jnz custom
        push 0x4189C5
        ret
    custom:
        push 1
        push 0x2F
        mov ecx, 0x4DB358
        mov eax, 0x413450
        call eax
        push 1
        push 0x30
        mov ecx, 0x4DB358
        mov eax, 0x413450
        call eax
        mov esi, 1
        push 0x41895B
        ret
    }
}
