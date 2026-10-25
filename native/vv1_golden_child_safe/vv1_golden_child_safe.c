/* VVFP VV1 Golden Child Safe -- part of "Fix Vanilla Bugs" in A New Home (owner-approved,
   2026-10-24, decision "B").

   THE STOCK BUG.  The Golden Child (the record whose +0x36C is 0xC7: 0x41FBDC, 0x42242D, 0x424B56,
   0x42E5A4, 0x438982) stays five forever: the per-age tick puts his age back to 100 every pass
   (0x42EB70..0x42EB98) and skips the rest of its body for him, so he never heals what he loses.
   Yet the island events that are about one villager pick him like anyone else: their setups ask
   the villager picker 0x43BCD0(adults_only) -- every record with health (+0x344) above 0 and the
   present byte (+0x28) set, adults only when asked (age +0x348 >= 0x118), one of them by rand(count)
   at 0x43BE53 -- and some of those events can kill the villager they picked or make them vanish:

     The Strange Berries (setup 0x418AA3)  Taste: 49% health 0 (resolve 0x419509).
     The Mysterious Face (0x418BB1)        Take a closer look: at least 49% the villager is never
                                           heard from again (+0x28 cleared, 0x41979D).
     The Book (0x4191C8)                   Read: always vanishes (0x41A272).
     The Suspicious Monkey (0x418F25)      Chase it away: health -50, floored at 0 (0x419DB1).
     The Wild Mushroom (0x418FAC)          Taste: 50% health -25..-49, floored at 0 (0x419F65).
     A Mysterious Crate, rotting (0x42B22B) Open: the finder is bitten with everyone else (below:
                                           up to -20 at the highest level, 0x42C1D8) and then
                                           loses 15 more with no floor (0x42C2B0).
     A Mysterious Crate, old fruit (0x42B391) Open: the finder loses 40, 70 or 110, no floor
                                           (0x42C842, 0x42C777, 0x42C6A2).

   And the rotting crate's bite (0x42AAA0(chance, bites, damage), called at 0x42C272) goes through
   every living villager: rand(100) < chance at 0x42AAEC makes them sick and takes `damage`
   (10 / 15 / 20 by the crate's level), floored at 0 -- the Golden Child included.

   THE FIX (the owner's rule: "lethal = sets health to 0 or below", judged against his health at
   the moment the event picks; natural island events only).

   * The picker, called from one of those seven setups for a NATURAL event, never returns the
     Golden Child when the event could kill him or make him vanish: always for the Strange
     Berries, the Mysterious Face and the Book; for the others when the most the event could take
     from him (Monkey 50, Mushroom 49, rotting crate 20 + 15 = 35, old fruit crate 110) is at least
     his health now.  It then picks among everyone else exactly as the game does -- the same
     records in the same order, one rand(count) from the game's own generator (0x402F10) -- so
     each of the others is as likely as before.  When he is the only villager the event could be
     about, the picker returns -1, the game's own answer when nobody is there: the setup returns 0
     (0x41925F / 0x42B5D7) and the game shows no event, as it does in an empty village.
   * The rotting crate's bite passes over the Golden Child -- he is neither bitten nor made sick --
     when that bite would bring his health to 0 or below (health <= damage); otherwise it is the
     game's own.  Everyone else's roll is made as before (the bite's rand(100) is drawn before this
     decision), so nobody else's chances change.
   * Every other caller of the picker (every other event, the Troubled Child's own picker 0x43BE70,
     Story / Cheat Upgrades' Fast Delivery) and every other villager is the game's own.

   PICKED AND CUSTOM EVENTS ARE THE PLAYER'S (the owner: Custom Island Event and Pick Island Event
   may pick any villager the player wishes, the Golden Child included).  "VVFP Story Upgrades.dll"
   says whether the event being set up was delivered by Pick Island Event (VvfpStoryEventChosen);
   for such an event nothing here changes anything.  A Custom Island Event never reaches these
   setups.  With Story / Cheat Upgrades installed, the seven setup calls are its "scope" calls
   (story_tables.h VV1_OC_SCOPES): the return address in the picker's stack slot is its
   oc_scope_back, and VvfpStoryCallerReturn(slot) gives back the game's own.

   INSTALLING.  VvfpStartup(1, shipped), called by "VVFP Speed Change Timers.dll" (the Fix Vanilla
   Bugs companion, which "VVFP Startup.dll" starts at game start).  The picker 0x43BCD0..0x43BE67
   and the bite 0x42AAA0..0x42AB52 must hold the stock bytes -- apart from the rand call of each
   (0x43BE53, 0x42AAEC), which Story / Cheat Upgrades may already have pointed at its own -- as must
   the game's rand, the seven setup calls and the code after each; then both detours go in through
   the shared all-or-none writer (native/shared/install_sites.h), or neither does. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"

#define VV1_GAME 1

#define RECORD_STRIDE 0x3D8u
#define RECORD_COUNT 256
#define REC_PRESENT 0x28u
#define REC_HEALTH 0x344u
#define REC_AGE 0x348u
#define REC_GOLDEN 0x36Cu
#define GOLDEN_CHILD 0xC7
#define ADULT_AGE 0x118

#define RAND_VA 0x402F10u
#define PICKER 0x43BCD0u
#define PICKER_RAND 0x43BE53u
#define PICKER_SITE_LEN 6                 /* sub esp, 0x400 */
#define PICKER_RESUME 0x43BCD6u           /* push ebx: the stock picker goes on */
#define BITE 0x42AAA0u
#define BITE_RAND 0x42AAECu
#define BITE_SITE 0x42AAFCu               /* test bl, bl; mov ecx, [edi+0x50AC] */
#define BITE_SITE_LEN 8
#define BITE_RESUME 0x42AB04u             /* mov [ecx+esi+0x354], 1: sick, then the damage */
#define BITE_NEXT 0x42AB3Eu               /* the next villager */
#define DIALOG_RECORDS 0x50ACu            /* the crate dialog's villager array (0x42AAD0) */

#define STOCK (-2)                        /* gc_pick: let the game's own picker run */

typedef int (__cdecl *rand_fn)(int bound);
typedef unsigned int (__stdcall *caller_return_fn)(unsigned int slot);
typedef int (__stdcall *event_chosen_fn)(int game);

static const char STORY_DLL[] = "VVFP Story Upgrades.dll";

/* The stock picker 0x43BCD0..0x43BE67 (0x198 bytes). */
static const unsigned char PICKER_STOCK[] = {
    0x81, 0xEC, 0x00, 0x04, 0x00, 0x00, 0x53, 0x56, 0x57, 0x8D, 0x41, 0x28, 0x8A, 0x8C, 0x24, 0x10,
    0x04, 0x00, 0x00, 0x33, 0xD2, 0xBE, 0x02, 0x00, 0x00, 0x00, 0xBF, 0x18, 0x01, 0x00, 0x00, 0x90,
    0x8B, 0x98, 0x1C, 0x03, 0x00, 0x00, 0x85, 0xDB, 0x7E, 0x19, 0x80, 0x38, 0x00, 0x74, 0x14, 0x39,
    0xB8, 0x20, 0x03, 0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x08, 0x8D, 0x5E, 0xFE, 0x89, 0x5C,
    0x94, 0x0C, 0x42, 0x8B, 0x98, 0xF4, 0x06, 0x00, 0x00, 0x85, 0xDB, 0x7E, 0x1E, 0x8A, 0x98, 0xD8,
    0x03, 0x00, 0x00, 0x84, 0xDB, 0x74, 0x14, 0x39, 0xB8, 0xF8, 0x06, 0x00, 0x00, 0x7D, 0x04, 0x84,
    0xC9, 0x75, 0x08, 0x8D, 0x5E, 0xFF, 0x89, 0x5C, 0x94, 0x0C, 0x42, 0x8B, 0x98, 0xCC, 0x0A, 0x00,
    0x00, 0x85, 0xDB, 0x7E, 0x1B, 0x8A, 0x98, 0xB0, 0x07, 0x00, 0x00, 0x84, 0xDB, 0x74, 0x11, 0x39,
    0xB8, 0xD0, 0x0A, 0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x05, 0x89, 0x74, 0x94, 0x0C, 0x42,
    0x8B, 0x98, 0xA4, 0x0E, 0x00, 0x00, 0x85, 0xDB, 0x7E, 0x1E, 0x8A, 0x98, 0x88, 0x0B, 0x00, 0x00,
    0x84, 0xDB, 0x74, 0x14, 0x39, 0xB8, 0xA8, 0x0E, 0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x08,
    0x8D, 0x5E, 0x01, 0x89, 0x5C, 0x94, 0x0C, 0x42, 0x8B, 0x98, 0x7C, 0x12, 0x00, 0x00, 0x85, 0xDB,
    0x7E, 0x1E, 0x8A, 0x98, 0x60, 0x0F, 0x00, 0x00, 0x84, 0xDB, 0x74, 0x14, 0x39, 0xB8, 0x80, 0x12,
    0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x08, 0x8D, 0x5E, 0x02, 0x89, 0x5C, 0x94, 0x0C, 0x42,
    0x8B, 0x98, 0x54, 0x16, 0x00, 0x00, 0x85, 0xDB, 0x7E, 0x1E, 0x8A, 0x98, 0x38, 0x13, 0x00, 0x00,
    0x84, 0xDB, 0x74, 0x14, 0x39, 0xB8, 0x58, 0x16, 0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x08,
    0x8D, 0x5E, 0x03, 0x89, 0x5C, 0x94, 0x0C, 0x42, 0x8B, 0x98, 0x2C, 0x1A, 0x00, 0x00, 0x85, 0xDB,
    0x7E, 0x1E, 0x8A, 0x98, 0x10, 0x17, 0x00, 0x00, 0x84, 0xDB, 0x74, 0x14, 0x39, 0xB8, 0x30, 0x1A,
    0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x08, 0x8D, 0x5E, 0x04, 0x89, 0x5C, 0x94, 0x0C, 0x42,
    0x8B, 0x98, 0x04, 0x1E, 0x00, 0x00, 0x85, 0xDB, 0x7E, 0x1E, 0x8A, 0x98, 0xE8, 0x1A, 0x00, 0x00,
    0x84, 0xDB, 0x74, 0x14, 0x39, 0xB8, 0x08, 0x1E, 0x00, 0x00, 0x7D, 0x04, 0x84, 0xC9, 0x75, 0x08,
    0x8D, 0x5E, 0x05, 0x89, 0x5C, 0x94, 0x0C, 0x42, 0x83, 0xC6, 0x08, 0x8D, 0x5E, 0xFE, 0x05, 0xC0,
    0x1E, 0x00, 0x00, 0x81, 0xFB, 0x00, 0x01, 0x00, 0x00, 0x0F, 0x8C, 0xB1, 0xFE, 0xFF, 0xFF, 0x85,
    0xD2, 0x5F, 0x5E, 0x5B, 0x75, 0x0C, 0x83, 0xC8, 0xFF, 0x81, 0xC4, 0x00, 0x04, 0x00, 0x00, 0xC2,
    0x04, 0x00, 0x52, 0xE8, 0xB8, 0x70, 0xFC, 0xFF, 0x8B, 0x44, 0x84, 0x04, 0x83, 0xC4, 0x04, 0x81,
    0xC4, 0x00, 0x04, 0x00, 0x00, 0xC2, 0x04, 0x00,
};

/* The stock bite 0x42AAA0..0x42AB52 (0xB3 bytes). */
static const unsigned char BITE_STOCK[] = {
    0x8B, 0x44, 0x24, 0x04, 0x83, 0xF8, 0x63, 0x53, 0x55, 0x56, 0x57, 0x8B, 0xF9, 0x7E, 0x0A, 0xC7,
    0x44, 0x24, 0x14, 0x63, 0x00, 0x00, 0x00, 0xEB, 0x0D, 0x83, 0xF8, 0x01, 0x7D, 0x08, 0xC7, 0x44,
    0x24, 0x14, 0x01, 0x00, 0x00, 0x00, 0x8B, 0x6C, 0x24, 0x1C, 0x8A, 0x5C, 0x24, 0x18, 0x33, 0xF6,
    0x8B, 0x87, 0xAC, 0x50, 0x00, 0x00, 0x8A, 0x4C, 0x30, 0x28, 0x03, 0xC6, 0x84, 0xC9, 0x74, 0x5E,
    0x8B, 0x88, 0x44, 0x03, 0x00, 0x00, 0x85, 0xC9, 0x7E, 0x54, 0x6A, 0x64, 0xE8, 0x1F, 0x84, 0xFD,
    0xFF, 0x8B, 0x4C, 0x24, 0x18, 0x83, 0xC4, 0x04, 0x3B, 0xC1, 0x7D, 0x42, 0x84, 0xDB, 0x8B, 0x8F,
    0xAC, 0x50, 0x00, 0x00, 0xC7, 0x84, 0x31, 0x54, 0x03, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x74,
    0x2D, 0x8B, 0x97, 0xAC, 0x50, 0x00, 0x00, 0x8D, 0x84, 0x32, 0x44, 0x03, 0x00, 0x00, 0x29, 0x28,
    0x8B, 0x87, 0xAC, 0x50, 0x00, 0x00, 0x8B, 0x8C, 0x30, 0x44, 0x03, 0x00, 0x00, 0x85, 0xC9, 0x8D,
    0x84, 0x30, 0x44, 0x03, 0x00, 0x00, 0x7D, 0x06, 0xC7, 0x00, 0x00, 0x00, 0x00, 0x00, 0x81, 0xC6,
    0xD8, 0x03, 0x00, 0x00, 0x81, 0xFE, 0x00, 0xD8, 0x03, 0x00, 0x7C, 0x84, 0x5F, 0x5E, 0x5D, 0x5B,
    0xC2, 0x0C, 0x00,
};

/* The game's rand(bound), 0x402F10: its first bytes. */
static const unsigned char RAND_STOCK[] = {
    0x56, 0x8B, 0x74, 0x24, 0x08, 0x85, 0xF6, 0x7E, 0x14, 0x81, 0xFE, 0xFF, 0x7F, 0x00, 0x00, 0x7F, 0x0C,
};

/* The events whose villager can die or vanish: the address the picker returns to in the game's
   own setup, and what the event could do to him. */
typedef struct {
    unsigned int call;            /* the setup's `call 0x43BCD0` */
    int always;                   /* it can kill or remove whatever his health */
    int most_lost;                /* else: the most health it could take from him */
} gc_event;

static const gc_event EVENTS[] = {
    { 0x418AA3u, 1, 0 },          /* The Strange Berries: Taste, health 0 (0x419509) */
    { 0x418BB1u, 1, 0 },          /* The Mysterious Face: a closer look, vanishes (0x41979D) */
    { 0x4191C8u, 1, 0 },          /* The Book: Read, vanishes (0x41A272) */
    { 0x418F25u, 0, 50 },         /* The Suspicious Monkey: chase it away, -50 (0x419DB1) */
    { 0x418FACu, 0, 49 },         /* The Wild Mushroom: taste, -25 - rand(25) (0x419F65) */
    { 0x42B22Bu, 0, 20 + 15 },    /* rotting crate: bitten -20 at most (0x42C1D8), then -15 (0x42C2B0) */
    { 0x42B391u, 0, 110 },        /* old fruit crate: -40 / -70 / -110 (0x42C842, 0x42C777, 0x42C6A2) */
};
#define EVENT_COUNT ((int)(sizeof EVENTS / sizeof EVENTS[0]))

/* What follows each of those calls in the setup: cmp eax, -1 ... */
static const unsigned char AFTER_CALL[] = { 0x83, 0xF8, 0xFF };

static int installed;

static int is_golden(const unsigned char *record) {
    return *(const int *)(record + REC_GOLDEN) == GOLDEN_CHILD;
}

static const gc_event *event_at(unsigned int return_address) {
    int i;
    for (i = 0; i < EVENT_COUNT; ++i) {
        if (EVENTS[i].call + 5u == return_address) {
            return &EVENTS[i];
        }
    }
    return NULL;
}

/* Whether Pick Island Event delivered the event now being set up (Story / Cheat Upgrades says;
   without it, or an older build of it, every event is the game's own). */
static int event_chosen(void) {
    HMODULE story = GetModuleHandleA(STORY_DLL);
    event_chosen_fn chosen;
    if (story == NULL) {
        return 0;
    }
    chosen = (event_chosen_fn)GetProcAddress(story, "VvfpStoryEventChosen");
    return chosen != NULL && chosen(VV1_GAME) != 0;
}

/* The event whose setup called the picker, from the return address in `slot` -- the game's own,
   or the one a Story / Cheat Upgrades scope call took from that slot. */
static const gc_event *calling_event(unsigned int *slot) {
    const gc_event *e = event_at(*slot);
    HMODULE story;
    caller_return_fn caller;
    if (e != NULL) {
        return e;
    }
    story = GetModuleHandleA(STORY_DLL);
    if (story == NULL) {
        return NULL;
    }
    caller = (caller_return_fn)GetProcAddress(story, "VvfpStoryCallerReturn");
    return caller != NULL ? event_at(caller((unsigned int)(UINT_PTR)slot)) : NULL;
}

static int could_lose_him(const gc_event *e, int health) {
    return e->always || health <= e->most_lost;
}

/* The picker's answer for this call: STOCK to let the game's own run (another caller, a picked
   event, or no Golden Child the event could kill among those it would pick from), else the
   record index it picks (-1: nobody). */
static int __cdecl gc_pick(unsigned char *records, unsigned int *slot) {
    const gc_event *e = calling_event(slot);
    int adults_only;
    int list[RECORD_COUNT];
    int count = 0;
    int spared = 0;
    int i;
    if (e == NULL || records == NULL || event_chosen()) {
        return STOCK;
    }
    adults_only = *(const unsigned char *)(slot + 1) != 0;     /* the byte argument (0x43BCDC) */
    for (i = 0; i < RECORD_COUNT; ++i) {
        const unsigned char *r = records + (size_t)i * RECORD_STRIDE;
        int health = *(const int *)(r + REC_HEALTH);
        if (health <= 0 || r[REC_PRESENT] == 0) {
            continue;
        }
        if (*(const int *)(r + REC_AGE) < ADULT_AGE && adults_only) {
            continue;
        }
        if (is_golden(r) && could_lose_him(e, health)) {
            spared = 1;
            continue;
        }
        list[count++] = i;
    }
    if (!spared) {
        return STOCK;
    }
    if (count == 0) {
        return -1;
    }
    return list[((rand_fn)(UINT_PTR)RAND_VA)(count)];
}

/* The bite of 0x42AAA0 for the villager at `offset`: 1 to pass over him (the Golden Child, whom
   this bite would bring to 0 or below, in a natural event). */
static int __cdecl gc_spare(const unsigned char *dialog, unsigned int offset, int bites, int damage) {
    const unsigned char *records = *(unsigned char *const *)(dialog + DIALOG_RECORDS);
    const unsigned char *r;
    if ((bites & 0xFF) == 0 || records == NULL) {
        return 0;
    }
    r = records + offset;
    if (!is_golden(r) || *(const int *)(r + REC_HEALTH) > damage) {
        return 0;
    }
    return !event_chosen();
}

/* At 0x43BCD0 (the picker's entry): ECX = the villager records, [esp] the return address,
   [esp+4] the adults-only byte.  Returns from the picker with our answer, or runs the stock one. */
static __declspec(naked) void pick_stub(void) {
    __asm {
        pushad
        lea eax, [esp + 32]
        push eax
        push ecx
        call gc_pick
        add esp, 8
        cmp eax, STOCK
        je stock
        mov dword ptr [esp + 28], eax
        popad
        ret 4
    stock:
        popad
        sub esp, 0x400
        push PICKER_RESUME
        ret
    }
}

/* At 0x42AAFC, after the bite's roll hit: EDI = the crate dialog, ESI = the record's offset,
   BL = whether bites take health, EBP = the damage. */
static __declspec(naked) void bite_stub(void) {
    __asm {
        pushad
        push ebp
        movzx eax, bl
        push eax
        push esi
        push edi
        call gc_spare
        add esp, 16
        test eax, eax
        popad
        jnz spare
        test bl, bl
        mov ecx, dword ptr [edi + DIALOG_RECORDS]
        push BITE_RESUME
        ret
    spare:
        push BITE_NEXT
        ret
    }
}

/* ---- installing ------------------------------------------------------------------------ */

static int readable(unsigned int va, size_t length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(UINT_PTR)va;
    if (VirtualQuery(at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return 0;
    }
    return (UINT_PTR)at + length <= (UINT_PTR)info.BaseAddress + info.RegionSize;
}

/* The routine at `va` holds `stock`, except the rel32 of its `call rand` at `call_va` (still a
   call: Story / Cheat Upgrades may have pointed it at its own answer). */
static int holds_but_the_rand_call(unsigned int va, const unsigned char *stock, size_t length,
                                   unsigned int call_va) {
    const unsigned char *at = (const unsigned char *)(UINT_PTR)va;
    size_t call = call_va - va;
    if (!readable(va, length)) {
        return 0;
    }
    return memcmp(at, stock, call + 1) == 0 && at[call] == 0xE8
           && memcmp(at + call + 5, stock + call + 5, length - call - 5) == 0;
}

/* Each setup still calls the picker there (or a Story scope call stands in its place, an E8
   too), and still tests its answer for -1 right after. */
static int setups_hold(void) {
    int i;
    for (i = 0; i < EVENT_COUNT; ++i) {
        unsigned int at = EVENTS[i].call;
        if (!readable(at, 8) || *(const unsigned char *)(UINT_PTR)at != 0xE8
            || memcmp((const void *)(UINT_PTR)(at + 5), AFTER_CALL, sizeof AFTER_CALL) != 0) {
            return 0;
        }
    }
    return 1;
}

static void install_vv1(void) {
    vvfp_site_write w[2];
    if (!holds_but_the_rand_call(PICKER, PICKER_STOCK, sizeof PICKER_STOCK, PICKER_RAND)
        || !holds_but_the_rand_call(BITE, BITE_STOCK, sizeof BITE_STOCK, BITE_RAND)
        || !readable(RAND_VA, sizeof RAND_STOCK)
        || memcmp((const void *)(UINT_PTR)RAND_VA, RAND_STOCK, sizeof RAND_STOCK) != 0
        || !setups_hold()) {
        return;
    }
    vvfp_site_branch(&w[0], PICKER, PICKER_SITE_LEN, PICKER_STOCK, 0xE9, (const void *)pick_stub);
    vvfp_site_branch(&w[1], BITE_SITE, BITE_SITE_LEN, BITE_STOCK + (BITE_SITE - BITE), 0xE9,
                     (const void *)bite_stub);
    if (vvfp_install_sites(w, 2)) {
        installed = 1;
    }
}

/* Called once at game start by "VVFP Speed Change Timers.dll", outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (installed || game != VV1_GAME) {
        return;
    }
    install_vv1();
}

/* Whether both detours are in (tests). */
__declspec(dllexport) int __stdcall VvfpGoldenChildSafeInstalled(void) {
    return installed;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
