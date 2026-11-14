/* VVFP VV2 Empty Stew -- "Empty the Stew Pot from the Science Hut Door" in The Lost Children (vv2_empty_stew_pot).

   WHAT (the owner, 2026-11-14).  The Secret City and The Tree of Life let the player empty their pot by dropping a
   villager on a spot beside it (VV3 the herb table, action 112; VV4 the grate, action 145: "Emptying the pot").
   The Lost Children has no such action: a ready stew stays in the pot 15 real-life minutes (the world update
   empties it with 0x425B20 when the real clock passes its deadline, 0x42EBCC..0x42EBE7), and until then a villager
   dropped on the pot can only eat it, so no new stew can be started.  With this patch a villager dropped on the
   DOORWAY of the science hut (the hut with the bench and the pots) while a READY stew is in the pot walks to the
   pot and empties it ("Emptying the pot").  The owner's rules:
     * anyone aged 14 or older (expectant mothers and nursing parents too: it harms nobody);
     * a villager who dislikes cooking refuses and runs away, exactly as the game does at the pot (0x42FEA6:
       0x4454E0(slot, 0x31) -> 0x44B010);
     * a finished (ready) stew only: a stew still being made is left alone;
     * at the doorway the emptying wins over the drop-on-another-villager code (pairing, storytelling);
     * with no ready stew, or a villager under 14, the drop is the stock game's, unchanged: no text, no action.
   No food is involved: the stew's 10 food left the store when "Adding food to the stew" finished (callback 46,
   0x46236C), before the stew existed; the herbs cost nothing.  Emptying gives nothing back and takes nothing.

   THE DOORWAY.  The game decides what a drop does by the map area at the villager's feet (record x + 0x14,
   y + 0x41; the area grid 0x4181D0, built by 0x418660).  The science hut's door and step (feet x 780..819,
   y 550..609) are the hut's blocked ground (area 1) and the open ground below it (area 0): today a drop there runs
   only the drop-on-another-villager code (0x430E15), then the villager is moved off the hut (0x42D140).  The
   research drops (areas 6 and 45, "Researching", x 820..1019) are outside it and unchanged.

   HOW.  After every site's stock bytes, the stock code the detours rely on and the first bytes of every game
   routine called are checked (native/shared/install_sites.h: all of them, or none):
     * 0x430AF9 (the village drop routine, right after the Esteemed Elder statue's own case and before the
       expecting / child / adult cases): `mov ecx, [eax+0x540]` becomes `jmp drop_detour` + a nop.  eax is the
       dropped villager's record, esi the village scene.  When the feet are on the doorway, the pot holds a ready
       stew (state + 0x3044C, the stew 1..18; 0 = none) and the villager is 14 or older (record + 0x530 >= 280), the
       companion queues the job (or the running away) and continues at the drop's stock tail 0x430F63 (the move off
       the hut, the placement); otherwise it runs the stolen instruction and continues at 0x430AFF, the stock drop.
     * 0x461B10 (the job-step completion dispatcher, step 17 of the villager update): its first 6 bytes become
       `jmp cb_detour` + a nop.  The companion's own callback id (CB_EMPTY, past the game's 1..70) is answered by
       the companion; every other id runs the stolen bytes and continues at 0x461B16, the stock dispatcher.

   THE JOB is built like the game's own stew jobs, with the game's queue push 0x449B70 and start 0x44FBB0 (the drop
   has already emptied the villager's queue, 0x430A95 -> 0x4492A0), its Details text "Emptying the pot" (the later
   games' own words, eSayEmptyPot) written where the stock jobs write theirs (record + 0x4FC, 0x30 bytes):
     step 3  walk to the pot (779, 895), the spot of "Starting to prepare a stew" (0x45A4A0);
     step 11 the working pose, 3 (as "Adding water to the stew", 0x45B05A, before it pours);
     step 21 effect 0x41, the splash "Adding water to the stew" makes at the pot (0x45B06E);
     step 17 the companion's callback: the pot is emptied here;
     step 2  (2, 1) and step 22 (the effect ends), as "Adding water to the stew" finishes (0x45B082, 0x45B096).
   The callback empties the pot with the game's own 0x425B20 -- the routine the 15-minute timer runs -- only while
   the pot still holds the stew the job was queued for (its deadline, state + 0x30450, recorded at the drop): a
   stew that has run out meanwhile, or a newer stew cooked since, is never thrown away.

   SAFETY.  Game thread only, inside the game's own drop and step code; nothing is written to a save or a file (the
   pot is outside the saved range: a reload starts with an empty pot, and a job left in a saved queue finds no
   recorded deadline and does nothing).  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"
#include "../shared/vvfp_translate.h"

#define ES_GAME_BASE 0x400000u

/* The village drop routine. */
#define DROP_SITE 0x430AF9u             /* mov ecx, [eax+0x540] (the expecting test) */
#define DROP_RESUME 0x430AFF            /* test ecx, ecx */
#define DROP_DONE 0x430F63              /* the drop's stock tail: mov ecx, [esi+0x1E4] */
#define DROP_RECORD 0x430AB4u           /* eax = [esi+0x1E4] * 0xE48C + [esi+0x20]: the record the site reads */

/* The job-step completion dispatcher: thiscall (slot, callback), ret 8. */
#define CB_SITE 0x461B10u
#define CB_RESUME 0x461B16

/* Game routines. */
#define QUEUE_PUSH 0x449B70u            /* thiscall (slot, step, a, b, c, d, param), ret 0x1C */
#define JOB_START 0x44FBB0u             /* thiscall (slot), ret 4 */
#define DISLIKES 0x4454E0u              /* thiscall (slot, word), ret 8: al 1 when the word is a dislike */
#define RUN_AWAY 0x44B010u              /* thiscall (slot), ret 4: "Running away" */
#define POT_EMPTY 0x425B20u             /* thiscall on the game state: the pot emptied (the 15-minute timer's) */

/* The scene, the villagers and the game state. */
#define SCENE_STATE 0x10
#define SCENE_VILLAGERS 0x20
#define SCENE_HELD 0x1E4
#define VILLAGERS_STATE 0xE574D4
#define RECORD 0xE48C
#define RECORDS 256                     /* 0x426001: cmp edi, 0xE48C00 */
#define REC_X 0x4
#define REC_Y 0x8
#define REC_LABEL 0x4FC
#define REC_LABEL_SIZE 0x30             /* up to health +0x52C */
#define REC_AGE 0x530
#define AGE_14 280                      /* 20 age units a year; 0x430C9E's child limit */
#define STATE_STEW 0x3044C              /* the ready stew, 1..18; 0 none */
#define STATE_STEW_END 0x30450          /* its deadline on the real clock 0x403200 */
#define WORD_COOKING 0x31               /* the likes/dislikes word the pot tests (0x42FEA9) */

/* The doorway, at the villager's feet (record x + 0x14, y + 0x41, as the drop reads the map). */
#define FEET_DX 0x14
#define FEET_DY 0x41
#define DOOR_X0 780
#define DOOR_X1 819
#define DOOR_Y0 550
#define DOOR_Y1 609

/* The job. */
#define POT_X 0x30B
#define POT_Y 0x37F
#define CB_EMPTY 0x0E57                 /* the companion's callback id: the game's own are 1..0x46 (0x461B19) */
#define EFFECT_SPLASH 0x41

static const char EMPTYING_EN[] = "Emptying the pot";

/* The stock bytes each detour relies on: written sites, and code only checked. */
static const unsigned char DROP_SITE_STOCK[6] = { 0x8B, 0x88, 0x40, 0x05, 0x00, 0x00 };   /* mov ecx,[eax+0x540] */
static const unsigned char DROP_RECORD_STOCK[17] = {
    0x8B, 0x86, 0xE4, 0x01, 0x00, 0x00,                          /* mov eax, [esi+0x1E4]    */
    0x8B, 0x4E, 0x20,                                            /* mov ecx, [esi+0x20]     */
    0x69, 0xC0, 0x8C, 0xE4, 0x00, 0x00,                          /* imul eax, eax, 0xE48C   */
    0x03, 0xC1                                                   /* add eax, ecx            */
};
static const unsigned char DROP_RESUME_STOCK[2] = { 0x85, 0xC9 };                       /* test ecx, ecx */
static const unsigned char DROP_DONE_STOCK[6] = { 0x8B, 0x8E, 0xE4, 0x01, 0x00, 0x00 };   /* mov ecx,[esi+0x1E4] */
static const unsigned char CB_SITE_STOCK[6] = { 0x51, 0x8B, 0x44, 0x24, 0x0C, 0x53 };     /* push ecx; mov eax,[esp+0xC]; push ebx */
static const unsigned char CB_RESUME_STOCK[2] = { 0x33, 0xDB };                         /* xor ebx, ebx */
static const unsigned char QUEUE_PUSH_STOCK[8] = { 0x83, 0xEC, 0x18, 0x8B, 0x44, 0x24, 0x20, 0x8B };
static const unsigned char JOB_START_STOCK[8] = { 0x8B, 0x44, 0x24, 0x04, 0x8B, 0xD0, 0x69, 0xD2 };
static const unsigned char DISLIKES_STOCK[8] = { 0x8B, 0x54, 0x24, 0x04, 0x33, 0xC0, 0x69, 0xD2 };
static const unsigned char RUN_AWAY_STOCK[8] = { 0x53, 0x56, 0x57, 0x8B, 0x7C, 0x24, 0x10, 0x8B };
static const unsigned char POT_EMPTY_STOCK[8] = { 0x33, 0xC0, 0x89, 0x81, 0x4C, 0x04, 0x03, 0x00 };

typedef void (__fastcall *push_fn)(void *villagers, void *unused, int slot, int step, int a, int b, int c, int d,
                                   int param);
typedef void (__fastcall *slot_fn)(void *villagers, void *unused, int slot);
typedef unsigned char (__fastcall *dislikes_fn)(void *villagers, void *unused, int slot, int word);
typedef void (__fastcall *state_fn)(void *state, void *unused);

static int g_installed;
static int g_armed[RECORDS];
static int g_deadline[RECORDS];

static int i32(const unsigned char *base, unsigned int offset) {
    return *(const int *)(base + offset);
}

static void push_step(unsigned char *villagers, int slot, int step, int a, int b, int c, int d, int param) {
    ((push_fn)(UINT_PTR)QUEUE_PUSH)(villagers, NULL, slot, step, a, b, c, d, param);
}

static void set_label(unsigned char *record) {
    const char *text = vvfp_tr("vvfp.vv2_empty_stew/vvfp_vv2_empty_stew.x.s0", EMPTYING_EN, REC_LABEL_SIZE);
    char *label = (char *)(record + REC_LABEL);
    int i = 0;
    for (; i < REC_LABEL_SIZE - 1 && text[i] != '\0'; ++i) {
        label[i] = text[i];
    }
    label[i] = '\0';
}

/* The drop of the held villager (`record`); 1 when the doorway took it (the stock drop's tail runs next). */
static int __cdecl drop_hook(unsigned char *scene, unsigned char *record) {
    int handled = 0;
    __try {
        unsigned char *state = *(unsigned char **)(scene + SCENE_STATE);
        unsigned char *villagers = *(unsigned char **)(scene + SCENE_VILLAGERS);
        int slot = i32(scene, SCENE_HELD);
        int x, y;
        if (state == NULL || villagers == NULL || slot < 0 || slot >= RECORDS
            || record != villagers + (unsigned int)slot * RECORD) {
            return 0;
        }
        if (i32(state, STATE_STEW) == 0) {
            return 0;                       /* no ready stew: the stock drop */
        }
        x = i32(record, REC_X) + FEET_DX;
        y = i32(record, REC_Y) + FEET_DY;
        if (x < DOOR_X0 || x > DOOR_X1 || y < DOOR_Y0 || y > DOOR_Y1 || i32(record, REC_AGE) < AGE_14) {
            return 0;
        }
        handled = 1;
        if (((dislikes_fn)(UINT_PTR)DISLIKES)(villagers, NULL, slot, WORD_COOKING)) {
            ((slot_fn)(UINT_PTR)RUN_AWAY)(villagers, NULL, slot);
            return 1;
        }
        set_label(record);
        g_deadline[slot] = i32(state, STATE_STEW_END);
        g_armed[slot] = 1;
        push_step(villagers, slot, 3, POT_X, POT_Y, 0, 0, 0x64);
        push_step(villagers, slot, 0xB, 0, 0, 3, 0, 0);
        push_step(villagers, slot, 0x15, 0, 0, 0, 0, EFFECT_SPLASH);
        push_step(villagers, slot, 0x11, 0, 0, 0, 0, CB_EMPTY);
        push_step(villagers, slot, 2, 0, 0, 2, 0, 1);
        push_step(villagers, slot, 0x16, 0, 0, 0, 0, 0);
        ((slot_fn)(UINT_PTR)JOB_START)(villagers, NULL, slot);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return handled;
}

/* The job's step 17: the pot emptied, only while it still holds the stew the job was queued for. */
static void __cdecl empty_hook(unsigned char *villagers, int slot) {
    __try {
        unsigned char *state;
        int armed, deadline;
        if (slot < 0 || slot >= RECORDS) {
            return;
        }
        armed = g_armed[slot];
        deadline = g_deadline[slot];
        g_armed[slot] = 0;
        state = *(unsigned char **)(villagers + VILLAGERS_STATE);
        if (!armed || state == NULL || i32(state, STATE_STEW) == 0 || i32(state, STATE_STEW_END) != deadline) {
            return;
        }
        ((state_fn)(UINT_PTR)POT_EMPTY)(state, NULL);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* At 0x430AF9: eax the dropped villager's record, esi the village scene. */
__declspec(naked) static void drop_detour(void) {
    __asm {
        pushad
        push eax
        push esi
        call drop_hook
        add esp, 8
        test eax, eax
        popad
        jnz taken
        mov ecx, dword ptr [eax + 0x540]
        push DROP_RESUME
        ret
    taken:
        push DROP_DONE
        ret
    }
}

/* At 0x461B10: ecx the villagers, [esp+4] the slot, [esp+8] the callback id. */
__declspec(naked) static void cb_detour(void) {
    __asm {
        cmp dword ptr [esp + 8], CB_EMPTY
        je mine
        push ecx
        mov eax, dword ptr [esp + 0xC]
        push ebx
        push CB_RESUME
        ret
    mine:
        push dword ptr [esp + 4]
        push ecx
        call empty_hook
        add esp, 8
        ret 8
    }
}

/* 1 when both detours are installed (for the tests' emulation), else 0. */
int __stdcall VvfpVv2EmptyStewInstalled(void) {
    return g_installed;
}

/* Called once by VVFP Startup.dll before WinMain. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    static vvfp_site_write w[2];
    static const struct {
        unsigned int va;
        const unsigned char *bytes;
        int length;
    } checked[] = {
        { DROP_RECORD, DROP_RECORD_STOCK, sizeof DROP_RECORD_STOCK },
        { DROP_RESUME, DROP_RESUME_STOCK, sizeof DROP_RESUME_STOCK },
        { DROP_DONE, DROP_DONE_STOCK, sizeof DROP_DONE_STOCK },
        { CB_RESUME, CB_RESUME_STOCK, sizeof CB_RESUME_STOCK },
        { QUEUE_PUSH, QUEUE_PUSH_STOCK, sizeof QUEUE_PUSH_STOCK },
        { JOB_START, JOB_START_STOCK, sizeof JOB_START_STOCK },
        { DISLIKES, DISLIKES_STOCK, sizeof DISLIKES_STOCK },
        { RUN_AWAY, RUN_AWAY_STOCK, sizeof RUN_AWAY_STOCK },
        { POT_EMPTY, POT_EMPTY_STOCK, sizeof POT_EMPTY_STOCK },
    };
    const unsigned char *module;
    int i;
    (void)shipped;
    if (g_installed || game != 2) {
        return;
    }
    module = (const unsigned char *)GetModuleHandleA(NULL);
    if (module != NULL && (UINT_PTR)module != ES_GAME_BASE) {
        return;                             /* every site is a VA of the game's fixed base */
    }
    for (i = 0; i < (int)(sizeof checked / sizeof checked[0]); ++i) {
        if (!vvfp_site_holds(checked[i].va, checked[i].bytes, checked[i].length)) {
            return;
        }
    }
    vvfp_site_branch(&w[0], DROP_SITE, sizeof DROP_SITE_STOCK, DROP_SITE_STOCK, 0xE9, (const void *)drop_detour);
    vvfp_site_branch(&w[1], CB_SITE, sizeof CB_SITE_STOCK, CB_SITE_STOCK, 0xE9, (const void *)cb_detour);
    if (vvfp_install_sites(w, 2)) {
        g_installed = 1;
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
