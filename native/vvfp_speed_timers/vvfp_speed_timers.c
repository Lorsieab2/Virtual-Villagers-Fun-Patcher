/* VVFP Speed Change Timers -- part of "Fix Vanilla Bugs" in all five games (the speed fix: The Secret
   City and The Tree of Life; the timed villager states: The Lost Children, The Secret City, The Tree
   of Life and New Believers; A New Home's start of its Golden Child fix) (owner-approved,
   2026-10-24: "yes fix that in all 5 games please!!!").

   THE STOCK BUG.  Both games keep a game clock object (VV3 0x5825D4, VV4 0x4D6F18) with the timers
   registered to it -- the campfire / Fire Pit among them -- and one routine set_speed(new) (VV3
   0x426630, VV4 0x41DBE0) for every speed change, the pause key, the unpause key and the Options
   speed buttons alike.  A timer holds a wall-clock deadline, so on a speed change the routine
   rescales it: from a running rate the factor is new / old and every set timer not yet due
   becomes trunc(timer * factor) + (now - trunc(now * factor)).  But from a paused clock (rate 0)
   the routine takes the factor 1 (VV3 0x42669F: mov eax,[esi+0x28] / mov [esp+0xC],1.0f; VV4
   0x41DC4E: fld1 / sub ecx,[esi+0x28] / fstp [esp+0x10]) and only moves each timer by the time
   paused -- whatever the new speed is.  So a village paused on Fast and unpaused on Normal (the
   Options buttons unpause too) keeps every timer at its Fast length: the fire lit for 10 hours on
   Fast burns 10 more real hours on Normal instead of 20.  The speed the clock had before the
   pause is in the clock itself (+0x24), written by the pause (0x42673B / 0x41DD01).

   THE FIX.  Only that from-paused branch changes: the factor becomes new / before, exactly as the
   running branch computes new / old (fild new; fidiv; fstp dword), and the base it is applied
   around becomes the wall clock at the pause (+0x28) -- trunc(pause * factor), with the game's own
   truncating conversion -- so each timer becomes now + (timer - pause) * new / before, through the
   routine's own rescale loop.  Unpausing at the speed it was paused at gives the factor 1 and the
   stock result byte for byte.  A clock whose "before" or new speed is not 3, 6 or 10 takes the
   stock branch.

   A New Home, The Lost Children and New Believers do not have the bug: their speed routine
   (0x42E830, 0x43B5A0, 0x426260) counts a paused speed as Normal on both sides, so a pause and an
   unpause at another speed rescale by 6 / old and new / 6 -- new / old in all.

   INSTALLING.  VvfpStartup(game, shipped), called once by VVFP Startup.dll at game start.  The
   whole of set_speed (VV3 0x426630..0x426742, VV4 0x41DBE0..0x41DD0F) and the constants the stub
   uses must hold the stock bytes, or nothing is written; the one detour goes in through the
   shared all-or-none writer (native/shared/install_sites.h).

   TIMED VILLAGER STATES (the owner, 2026-11-16, every game): a villager's effects pause while the
   game is paused, keep their base-game lengths (real time), and only the 10-minute autosave keeps
   them -- every other save ends them as the base game does.  The Secret City (potion effects), The
   Tree of Life and New Believers (their effect lists): each game's sections below.  The Lost
   Children has no lasting villager effect (a stew acts once, when eaten); its stew pot's 15 minutes
   pause instead.  A New Home has none: nothing changes there.

   A NEW HOME.  This is also the companion A New Home's Fix Vanilla Bugs ships, to start that
   game's own fix there: the startup loader's list of companions is full (native/shared/
   startup_companions.h, bits 1-29), so "VVFP VV1 Golden Child Safe.dll" -- the Golden Child is
   never the villager of a natural island event that could kill him -- is loaded from here, by its
   full path in the patcher's folder, and its VvfpStartup called; a fault in it is abandoned, and
   without the file nothing happens.  Nothing of the speed fix runs in A New Home. */
#include <windows.h>
#include <string.h>
#include "../shared/install_sites.h"
#include "../shared/patcher_files.h"
#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"

#define VV2_GAME 2
#define VV3_GAME 3
#define VV4_GAME 4
#define VV5_GAME 5

/* ---- The Secret City ------------------------------------------------------------------ */

#define VV3_ROUTINE 0x426630u
#define VV3_SITE 0x42669Fu
#define VV3_SITE_LEN 13
#define VV3_RESUME 0x4266D3u          /* sub edi, eax: ebx = now - eax, then the rescale loop */
#define VV3_FTOL 0x46EF58u
#define VV3_TWO32 0x47F510u            /* 4294967296.0f */

static const unsigned char VV3_STOCK[] = {
    0x8B, 0x44, 0x24, 0x04, 0x83, 0xEC, 0x08, 0x56, 0x8B, 0xF1, 0x3B, 0x46, 0x20, 0x0F, 0x84, 0xF9,
    0x00, 0x00, 0x00, 0x3D, 0xE7, 0x03, 0x00, 0x00, 0x57, 0x75, 0x3A, 0xA1, 0xD0, 0x25, 0x58, 0x00,
    0x33, 0xFF, 0x85, 0xC0, 0xC7, 0x44, 0x24, 0x14, 0x00, 0x00, 0x00, 0x00, 0x0F, 0x8E, 0xB3, 0x00,
    0x00, 0x00, 0x8B, 0x0C, 0xBE, 0xE8, 0xF6, 0x01, 0x00, 0x00, 0x84, 0xC0, 0x74, 0x08, 0x8B, 0x0C,
    0xBE, 0xE8, 0x4A, 0x02, 0x00, 0x00, 0xA1, 0xD0, 0x25, 0x58, 0x00, 0x47, 0x3B, 0xF8, 0x7C, 0xE2,
    0xE9, 0x90, 0x00, 0x00, 0x00, 0x53, 0xE8, 0xD5, 0x24, 0x00, 0x00, 0x8B, 0xC8, 0xE8, 0x9E, 0xCC,
    0xFD, 0xFF, 0x8B, 0xF8, 0x8B, 0x46, 0x20, 0x85, 0xC0, 0x89, 0x44, 0x24, 0x0C, 0x75, 0x0D, 0x8B,
    0x46, 0x28, 0xC7, 0x44, 0x24, 0x0C, 0x00, 0x00, 0x80, 0x3F, 0xEB, 0x27, 0x85, 0xFF, 0xDB, 0x44,
    0x24, 0x18, 0x89, 0x7C, 0x24, 0x10, 0xDA, 0x74, 0x24, 0x0C, 0xD9, 0x5C, 0x24, 0x0C, 0xDB, 0x44,
    0x24, 0x10, 0x7D, 0x06, 0xD8, 0x05, 0x10, 0xF5, 0x47, 0x00, 0xD8, 0x4C, 0x24, 0x0C, 0xE8, 0x85,
    0x88, 0x04, 0x00, 0x2B, 0xF8, 0xA1, 0xD0, 0x25, 0x58, 0x00, 0x8B, 0xDF, 0x33, 0xFF, 0x85, 0xC0,
    0x7E, 0x32, 0x55, 0x8B, 0x6C, 0x24, 0x10, 0x8B, 0x0C, 0xBE, 0xE8, 0x71, 0x01, 0x00, 0x00, 0x84,
    0xC0, 0x74, 0x16, 0x8B, 0x0C, 0xBE, 0xE8, 0x75, 0x01, 0x00, 0x00, 0x84, 0xC0, 0x75, 0x0A, 0x8B,
    0x0C, 0xBE, 0x55, 0x53, 0xE8, 0x57, 0x00, 0x00, 0x00, 0xA1, 0xD0, 0x25, 0x58, 0x00, 0x47, 0x3B,
    0xF8, 0x7C, 0xD4, 0x5D, 0x5B, 0x8B, 0xCE, 0xE8, 0x74, 0xFE, 0xFF, 0xFF, 0x89, 0x46, 0x2C, 0xE8,
    0x3C, 0x24, 0x00, 0x00, 0x8B, 0xC8, 0xE8, 0x05, 0xCC, 0xFD, 0xFF, 0x8B, 0x4C, 0x24, 0x14, 0x89,
    0x46, 0x28, 0x8B, 0x46, 0x20, 0x89, 0x46, 0x24, 0x89, 0x4E, 0x20, 0x5F, 0x5E, 0x83, 0xC4, 0x08,
    0xC2, 0x04, 0x00,
};
/* _ftol's first bytes and the 2^32 float the routine adds to a "negative" unsigned value. */
static const unsigned char VV3_FTOL_STOCK[] = { 0x55, 0x8B, 0xEC, 0x83, 0xEC, 0x20, 0x83, 0xE4, 0xF0 };
static const unsigned char TWO32_FLOAT[] = { 0x00, 0x00, 0x80, 0x4F };

/* THE VILLAGERS' POTION EFFECTS PAUSE TOO (Fix Vanilla Bugs, the owner 2026-11-16, as in The Tree of Life).  A
   villager's effects (+0xF50, up to 4 entries of 0x18, count +0xFB0: a potion's 10 or 5 real-life minutes) end when
   the computer's clock 0x403330 reaches the end each keeps at +0x10 (0 = no end; checked by the villager update at
   0x457051..0x457060, which does not run while paused).  Coming out of a pause every set end is moved on by the
   time paused (now - the wall clock at the pause, +0x28), so each effect resumes with the time it had left.  Their
   length while the game runs is unchanged (real time, the same at every speed). */
#define VV3_EFFECTS 0xF50u
#define VV3_EFFECT_COUNT 0xFB0u
#define VV3_EFFECT_SIZE 0x18u
#define VV3_EFFECT_END 0x10u
#define VV3_RECORD_SIZE 0x1F8Cu
#define VV3_FIRST_RECORD 0x14u
#define VV3_EFFECTS_MAX 4

static int readable(unsigned int va, size_t length);

/* Every set end (+`end_at`) of every effect of every villager record moved on by `paused` seconds; a record whose
   count is not a real one is left alone. */
static void effects_paused(unsigned char *record, unsigned int slots, unsigned int record_size,
                           unsigned int effects, unsigned int count_at, unsigned int size, unsigned int end_at,
                           int max, unsigned int paused) {
    unsigned int i;
    if (paused == 0 || !readable((unsigned int)(UINT_PTR)record, (size_t)slots * record_size)) {
        return;
    }
    for (i = 0; i < slots; ++i, record += record_size) {
        int count = *(const int *)(record + count_at), n;
        if (count <= 0 || count > max) {
            continue;
        }
        for (n = 0; n < count; ++n) {
            unsigned int *end = (unsigned int *)(record + effects + (unsigned int)n * size + end_at);
            if (*end != 0) {
                *end += paused;
            }
        }
    }
}

static void __stdcall vv3_effects_paused(unsigned int paused) {
    const unsigned char *module = (const unsigned char *)(UINT_PTR)0x400000u;
    unsigned int manager_rva, slots;
    vv3_villager_table(module, &manager_rva, &slots);
    effects_paused((unsigned char *)(UINT_PTR)(0x400000u + manager_rva + VV3_FIRST_RECORD), slots, VV3_RECORD_SIZE,
                   VV3_EFFECTS, VV3_EFFECT_COUNT, VV3_EFFECT_SIZE, VV3_EFFECT_END, VV3_EFFECTS_MAX, paused);
}

/* At VV3_SITE, from a paused clock: esi = the clock, edi = now, the factor slot [esp+0xC], the new
   speed [esp+0x18] (the routine's frame: ebx, edi, esi pushed below 8 bytes of locals).  First moves the
   villagers' effects on by the time paused (vv3_effects_paused, every register kept).  Leaves
   eax = trunc(pause * factor) and the factor in [esp+0xC] for the stock code at VV3_RESUME. */
static __declspec(naked) void vv3_from_paused(void) {
    __asm {
        pushad
        mov eax, edi
        sub eax, dword ptr [esi + 0x28]
        push eax
        call vv3_effects_paused
        popad
        mov eax, dword ptr [esi + 0x24]
        cmp eax, 3
        je before_ok
        cmp eax, 6
        je before_ok
        cmp eax, 10
        jne stock
    before_ok:
        mov eax, dword ptr [esp + 0x18]
        cmp eax, 3
        je rescale
        cmp eax, 6
        je rescale
        cmp eax, 10
        jne stock
    rescale:
        fild dword ptr [esp + 0x18]
        fidiv dword ptr [esi + 0x24]
        fstp dword ptr [esp + 0x0C]
        mov eax, dword ptr [esi + 0x28]
        test eax, eax
        fild dword ptr [esi + 0x28]
        jge positive
        mov ecx, VV3_TWO32
        fadd dword ptr [ecx]
    positive:
        fmul dword ptr [esp + 0x0C]
        mov ecx, VV3_FTOL
        call ecx
        push VV3_RESUME
        ret
    stock:
        mov eax, dword ptr [esi + 0x28]
        mov dword ptr [esp + 0x0C], 0x3F800000
        push VV3_RESUME
        ret
    }
}

/* ---- The Tree of Life ------------------------------------------------------------------ */

#define VV4_ROUTINE 0x41DBE0u
#define VV4_SITE 0x41DC4Eu
#define VV4_SITE_LEN 11
#define VV4_RESUME 0x41DCA1u          /* ebx = ecx, then the rescale loop */
#define VV4_TWO32 0x48C4C0u

static const unsigned char VV4_STOCK[] = {
    0x83, 0xEC, 0x0C, 0x55, 0x8B, 0x6C, 0x24, 0x14, 0x56, 0x8B, 0xF1, 0x3B, 0x6E, 0x20, 0x0F, 0x84,
    0x14, 0x01, 0x00, 0x00, 0x81, 0xFD, 0xE7, 0x03, 0x00, 0x00, 0x57, 0x75, 0x37, 0x33, 0xFF, 0x33,
    0xED, 0x39, 0x3D, 0x10, 0x6F, 0x4D, 0x00, 0x0F, 0x8E, 0xD8, 0x00, 0x00, 0x00, 0x8D, 0x49, 0x00,
    0x8B, 0x0C, 0xBE, 0xE8, 0x48, 0x02, 0x00, 0x00, 0x84, 0xC0, 0x74, 0x08, 0x8B, 0x0C, 0xBE, 0xE8,
    0x9C, 0x02, 0x00, 0x00, 0x83, 0xC7, 0x01, 0x3B, 0x3D, 0x10, 0x6F, 0x4D, 0x00, 0x7C, 0xE1, 0xE9,
    0xB1, 0x00, 0x00, 0x00, 0x53, 0xE8, 0x36, 0x22, 0x00, 0x00, 0x8B, 0xC8, 0xE8, 0x0F, 0x5B, 0xFE,
    0xFF, 0x8B, 0xC8, 0x8B, 0x46, 0x20, 0x85, 0xC0, 0x89, 0x44, 0x24, 0x10, 0x75, 0x0B, 0xD9, 0xE8,
    0x2B, 0x4E, 0x28, 0xD9, 0x5C, 0x24, 0x10, 0xEB, 0x48, 0xDB, 0x44, 0x24, 0x20, 0x8B, 0xC1, 0x85,
    0xC0, 0x89, 0x44, 0x24, 0x20, 0xDA, 0x74, 0x24, 0x10, 0xD9, 0x5C, 0x24, 0x10, 0xDB, 0x44, 0x24,
    0x20, 0x7D, 0x06, 0xD8, 0x05, 0xC0, 0xC4, 0x48, 0x00, 0xD8, 0x4C, 0x24, 0x10, 0xD9, 0x7C, 0x24,
    0x20, 0x0F, 0xB7, 0x44, 0x24, 0x20, 0x0D, 0x00, 0x0C, 0x00, 0x00, 0x89, 0x44, 0x24, 0x14, 0xD9,
    0x6C, 0x24, 0x14, 0xDF, 0x7C, 0x24, 0x14, 0x8B, 0x54, 0x24, 0x14, 0x2B, 0xCA, 0xD9, 0x6C, 0x24,
    0x20, 0x33, 0xFF, 0x39, 0x3D, 0x10, 0x6F, 0x4D, 0x00, 0x8B, 0xD9, 0x7E, 0x37, 0x8D, 0x49, 0x00,
    0x8B, 0x0C, 0xBE, 0xE8, 0xA8, 0x01, 0x00, 0x00, 0x84, 0xC0, 0x74, 0x1D, 0x8B, 0x0C, 0xBE, 0xE8,
    0xAC, 0x01, 0x00, 0x00, 0x84, 0xC0, 0x75, 0x11, 0xD9, 0x44, 0x24, 0x10, 0x51, 0x8B, 0x0C, 0xBE,
    0xD9, 0x1C, 0x24, 0x53, 0xE8, 0x47, 0x00, 0x00, 0x00, 0x83, 0xC7, 0x01, 0x3B, 0x3D, 0x10, 0x6F,
    0x4D, 0x00, 0x7C, 0xCC, 0x5B, 0x8B, 0xCE, 0xE8, 0x34, 0xFE, 0xFF, 0xFF, 0x89, 0x46, 0x2C, 0xE8,
    0x7C, 0x21, 0x00, 0x00, 0x8B, 0xC8, 0xE8, 0x55, 0x5A, 0xFE, 0xFF, 0x89, 0x46, 0x28, 0x8B, 0x46,
    0x20, 0x89, 0x46, 0x24, 0x89, 0x6E, 0x20, 0x5F, 0x5E, 0x5D, 0x83, 0xC4, 0x0C, 0xC2, 0x04, 0x00,
};

/* THE VILLAGERS' EFFECTS PAUSE TOO (Fix Vanilla Bugs, the owner 2026-11-16: "All of those effect timers should
   pause when the game is paused").  A villager's effects (+0x1D0C, up to 12 entries of 0x1C, count +0x1E5C: the
   clean body, the meditation's glow, the sticky gunk, a stew's wait) end when the computer's clock 0x403750
   reaches the end each keeps at +0x14 (0 = no end; checked by 0x45FC70, which does not run while paused).  They
   are not timers of the game clock, so set_speed never moves them.  Coming out of a pause -- the one branch this
   detour enters -- every set end is moved on by the time paused (now - the wall clock at the pause, +0x28), so
   each effect resumes with the time it had left.  Their length while the game runs is unchanged (real time, the
   same at every speed). */
#define VV4_EFFECTS 0x1D0Cu
#define VV4_EFFECT_COUNT 0x1E5Cu
#define VV4_EFFECT_SIZE 0x1Cu
#define VV4_EFFECT_END 0x14u
#define VV4_RECORD_SIZE 0x2E3Cu
#define VV4_FIRST_RECORD 0x44u
#define VV4_EFFECTS_MAX 12

static int readable(unsigned int va, size_t length);

static void __stdcall vv4_effects_paused(unsigned int paused) {
    const unsigned char *module = (const unsigned char *)(UINT_PTR)0x400000u;
    unsigned int manager_rva, slots, i;
    unsigned char *record;
    vv4_villager_table(module, &manager_rva, &slots);
    record = (unsigned char *)(UINT_PTR)(0x400000u + manager_rva + VV4_FIRST_RECORD);
    if (paused == 0 || !readable((unsigned int)(UINT_PTR)record, (size_t)slots * VV4_RECORD_SIZE)) {
        return;
    }
    for (i = 0; i < slots; ++i, record += VV4_RECORD_SIZE) {
        int count = *(const int *)(record + VV4_EFFECT_COUNT), n;
        if (count <= 0 || count > VV4_EFFECTS_MAX) {
            continue;
        }
        for (n = 0; n < count; ++n) {
            unsigned int *end = (unsigned int *)(record + VV4_EFFECTS + (unsigned int)n * VV4_EFFECT_SIZE
                                                 + VV4_EFFECT_END);
            if (*end != 0) {
                *end += paused;
            }
        }
    }
}

/* At VV4_SITE, from a paused clock: esi = the clock, ecx = now, the factor slot [esp+0x10], the new
   speed [esp+0x20] (ebx, edi, esi, ebp pushed below 12 bytes of locals).  First moves the villagers'
   effects on by the time paused (vv4_effects_paused, every register kept).  Leaves ecx = now -
   trunc(pause * factor) and the factor in [esp+0x10] for the stock code at VV4_RESUME, converting
   with truncation exactly as the routine's own fistp does (0x41DC7D..0x41DC9D). */
static __declspec(naked) void vv4_from_paused(void) {
    __asm {
        pushad
        mov eax, ecx
        sub eax, dword ptr [esi + 0x28]
        push eax
        call vv4_effects_paused
        popad
        mov eax, dword ptr [esi + 0x24]
        cmp eax, 3
        je before_ok
        cmp eax, 6
        je before_ok
        cmp eax, 10
        jne stock
    before_ok:
        mov eax, dword ptr [esp + 0x20]
        cmp eax, 3
        je rescale
        cmp eax, 6
        je rescale
        cmp eax, 10
        jne stock
    rescale:
        fild dword ptr [esp + 0x20]
        fidiv dword ptr [esi + 0x24]
        fstp dword ptr [esp + 0x10]
        mov eax, dword ptr [esi + 0x28]
        test eax, eax
        fild dword ptr [esi + 0x28]
        jge positive
        mov edx, VV4_TWO32
        fadd dword ptr [edx]
    positive:
        fmul dword ptr [esp + 0x10]
        sub esp, 0x0C
        fnstcw word ptr [esp]
        movzx eax, word ptr [esp]
        or eax, 0x0C00
        mov dword ptr [esp + 8], eax
        fldcw word ptr [esp + 8]
        fistp qword ptr [esp + 4]
        mov edx, dword ptr [esp + 4]
        fldcw word ptr [esp]
        add esp, 0x0C
        sub ecx, edx
        push VV4_RESUME
        ret
    stock:
        fld1
        sub ecx, dword ptr [esi + 0x28]
        fstp dword ptr [esp + 0x10]
        push VV4_RESUME
        ret
    }
}

/* THE AUTOSAVE KEEPS THE VILLAGERS' EFFECTS (Fix Vanilla Bugs, the owner 2026-11-16: "just the autosave should
   have all effects kept").  The save writer 0x4660A0 ends every effect of each villager it saves (0x4660C4: call
   0x45EAA0); the effects are not part of the saved entry, so this only wipes the village in play.  The 10-minute
   autosave (0x41F1A0: its one call of the slot saver 0x41F160, at 0x41F1C4) now runs with a flag set, and the
   writer's call at 0x4660C4 skips 0x45EAA0 while it is set.  Every other save -- quitting, leaving the village for
   the slot menu, each menu's save -- calls 0x41F160 from elsewhere and ends the effects as the base game does. */
#define VV4_AUTOSAVE_SITE 0x41F1C4u        /* call 0x41F160, in the autosave check 0x41F1A0 */
#define VV4_SLOT_SAVER 0x41F160u
#define VV4_STRIP_SITE 0x4660C4u           /* call 0x45EAA0, in the save writer 0x4660A0 */
#define VV4_STRIP 0x45EAA0u

static const unsigned char VV4_AUTOSAVE_STOCK[] = { 0xE8, 0x97, 0xFF, 0xFF, 0xFF };
static const unsigned char VV4_STRIP_STOCK[] = { 0xE8, 0xD7, 0x89, 0xFF, 0xFF };
static volatile unsigned int g_autosaving;

/* At VV4_AUTOSAVE_SITE: thiscall(game; slot argument), ret 4 -- the slot saver with the flag set around it. */
static __declspec(naked) void vv4_autosave(void) {
    __asm {
        mov dword ptr [g_autosaving], 1
        push dword ptr [esp + 4]
        mov eax, VV4_SLOT_SAVER
        call eax
        mov dword ptr [g_autosaving], 0
        ret 4
    }
}

/* At VV4_STRIP_SITE: thiscall(villager) -- 0x45EAA0 unless the autosave is writing. */
static __declspec(naked) void vv4_strip(void) {
    __asm {
        cmp dword ptr [g_autosaving], 0
        jne keep
        mov eax, VV4_STRIP
        jmp eax
    keep:
        ret
    }
}

/* WIPING STICKY GUNK ENDS ONLY THE GUNK (Fix Vanilla Bugs, the owner 2026-11-16).  The last step of "Wiping
   sticky gunk off on tree" (the action's step 0x4A, at 0x46431C) calls 0x45EAA0, which ends EVERY effect of the
   villager: the clean body and the glow went with the gunk.  That call now runs vv4_wipe_gunk instead, which ends
   only the gunk: each entry of the sparkle manager 0x4CE1C0 whose sparkle is of kind 5 (the kind the game's own
   gunk check 0x438FA0 looks for) goes through the game's own remove-one routine 0x45E9F0 (which frees its
   sparkle as 0x45EAA0 does).  Every other effect keeps its own end. */
#define VV4_GUNK_SITE 0x46431Cu            /* call 0x45EAA0, step 0x4A of "Wiping sticky gunk off on tree" */
#define VV4_SPARKLES 0x4CE1C0u             /* the sparkle manager: an effect entry's owner */
#define VV4_SPARKLE_KIND 0x41D1C0u         /* thiscall(sparkles; id) -> its kind, -1 for none */
#define VV4_EFFECT_REMOVE 0x45E9F0u        /* thiscall(villager; owner, &id), ret 8: ends that one entry */
#define VV4_GUNK_KIND 5

static const unsigned char VV4_GUNK_STOCK[] = { 0xE8, 0x7F, 0xA7, 0xFF, 0xFF };

/* The game's thiscall routines, called as __fastcall (ecx = this, edx unused, the rest on the stack, callee pops). */
typedef int (__fastcall *vv4_kind_fn)(unsigned int sparkles, unsigned int unused, int id);
typedef void (__fastcall *vv4_remove_fn)(unsigned char *villager, unsigned int unused, unsigned int owner, int *id);

static void __stdcall vv4_wipe_gunk_of(unsigned char *villager) {
    int n = 0;
    for (;;) {
        int count = *(const int *)(villager + VV4_EFFECT_COUNT);
        const unsigned char *entry;
        int id;
        if (count <= 0 || count > VV4_EFFECTS_MAX || n >= count) {
            return;
        }
        entry = villager + VV4_EFFECTS + (unsigned int)n * VV4_EFFECT_SIZE;
        id = *(const int *)(entry + 4);
        if (*(const unsigned int *)entry == VV4_SPARKLES && id >= 0
            && ((vv4_kind_fn)(UINT_PTR)VV4_SPARKLE_KIND)(VV4_SPARKLES, 0, id) == VV4_GUNK_KIND) {
            ((vv4_remove_fn)(UINT_PTR)VV4_EFFECT_REMOVE)(villager, 0, VV4_SPARKLES, &id);
            if (*(const int *)(villager + VV4_EFFECT_COUNT) < count) {
                continue;                  /* the rest moved down one: look at the same place again */
            }
        }
        ++n;
    }
}

/* At VV4_GUNK_SITE: thiscall(villager), in place of 0x45EAA0. */
static __declspec(naked) void vv4_wipe_gunk(void) {
    __asm {
        push ecx
        call vv4_wipe_gunk_of
        ret
    }
}

/* ---- The Secret City: only the autosave keeps the potion effects --------------------------
   The save routine 0x427D90 (the settings, the slot and slot + 20 through the game's vtable +0x38) ends every
   villager's effects on the way (the writer's per-villager call at 0x45EF9C: call 0x455DD0); the effects are not
   saved.  The 10-minute autosave check 0x427DD0 ends with a jump to it (0x427DF3), which now goes to vv3_autosave:
   the same call with the flag set, so the writer's call skips 0x455DD0.  Every other save -- quitting, leaving the
   village, each menu's save (0x41AEB5, 0x41B681, 0x41B95D, 0x41BA4D, 0x42840C) -- ends the effects as before. */
#define VV3_AUTOSAVE_SITE 0x427DF3u        /* jmp 0x427D90, the autosave check's last instruction */
#define VV3_SAVE 0x427D90u
#define VV3_STRIP_SITE 0x45EF9Cu           /* call 0x455DD0 in the save writer */
#define VV3_STRIP 0x455DD0u

static const unsigned char VV3_AUTOSAVE_STOCK[] = { 0xE9, 0x98, 0xFF, 0xFF, 0xFF };
static const unsigned char VV3_AUTOSAVE_AROUND[] = { 0x8B, 0xCE, 0x5E, 0xE9, 0x98, 0xFF, 0xFF, 0xFF, 0x5E, 0xC3 };
static const unsigned char VV3_STRIP_STOCK[] = { 0xE8, 0x2F, 0x6E, 0xFF, 0xFF };
static const unsigned char VV3_STRIP_AROUND[] = { 0x8B, 0xCE, 0xE8, 0x2F, 0x6E, 0xFF, 0xFF };

/* At VV3_AUTOSAVE_SITE (a tail jump, ecx = the game): the save routine with the flag set around it. */
static __declspec(naked) void vv3_autosave(void) {
    __asm {
        mov dword ptr [g_autosaving], 1
        mov eax, VV3_SAVE
        call eax
        mov dword ptr [g_autosaving], 0
        ret
    }
}

/* At VV3_STRIP_SITE: thiscall(villager) -- 0x455DD0 unless the autosave is writing. */
static __declspec(naked) void vv3_strip(void) {
    __asm {
        cmp dword ptr [g_autosaving], 0
        jne keep
        mov eax, VV3_STRIP
        jmp eax
    keep:
        ret
    }
}

/* ---- New Believers: the villagers' effects pause, and only the autosave keeps them --------
   The same effect list as The Tree of Life's: +0x1D3C, up to 12 entries of 0x1C, count +0x1E8C, the end at +0x14
   on the computer's clock 0x4036E0 (0 = no end; set by the adder 0x467E20, checked at 0x46746B by the villager
   update, which does not run while paused).  The game clock's speed routine 0x41EE00 comes out of a pause through
   0x41EE6E (the clock's rate +0x20 is 0; ecx = now, +0x28 = the wall clock at the pause): there every set end is
   moved on by the time paused first.  The save writer 0x46F9B0 ends every effect of each villager it saves
   (0x46F9CF: call 0x4660C0); the autosave check 0x424660's call of the save routine 0x424620 (0x424684) now runs
   with the flag set, so that call is skipped; every other save (0x418CD1, 0x4194A3, 0x419775, 0x419BD1, 0x424990)
   ends them as before. */
#define VV5_SITE 0x41EE6Eu
#define VV5_SITE_LEN 11
#define VV5_RESUME 0x41EEC1u
#define VV5_EFFECTS 0x1D3Cu
#define VV5_EFFECT_COUNT 0x1E8Cu
#define VV5_EFFECT_SIZE 0x1Cu
#define VV5_EFFECT_END 0x14u
#define VV5_RECORD_SIZE 0x2F44u
#define VV5_FIRST_RECORD 0x48u
#define VV5_EFFECTS_MAX 12
#define VV5_AUTOSAVE_SITE 0x424684u        /* call 0x424620 in the autosave check 0x424660 */
#define VV5_SAVE 0x424620u
#define VV5_STRIP_SITE 0x46F9CFu           /* call 0x4660C0 in the save writer 0x46F9B0 */
#define VV5_STRIP 0x4660C0u

/* 0x41EE54..0x41EE79: the from-pause branch round the site (call 0x425950; call 0x4036E0; mov ecx, eax; ...). */
static const unsigned char VV5_AROUND[] = {
    0x53, 0xE8, 0xF6, 0x6A, 0x00, 0x00, 0x8B, 0xC8, 0xE8, 0x7F, 0x48, 0xFE, 0xFF, 0x8B, 0xC8, 0x8B,
    0x46, 0x20, 0x85, 0xC0, 0x89, 0x44, 0x24, 0x10, 0x75, 0x0B, 0xD9, 0xE8, 0x2B, 0x4E, 0x28, 0xD9,
    0x5C, 0x24, 0x10, 0xEB, 0x48,
};
#define VV5_AROUND_VA 0x41EE54u
static const unsigned char VV5_AUTOSAVE_STOCK[] = { 0xE8, 0x97, 0xFF, 0xFF, 0xFF };
static const unsigned char VV5_STRIP_STOCK[] = { 0xE8, 0xEC, 0x66, 0xFF, 0xFF };

static void __stdcall vv5_effects_paused(unsigned int paused) {
    const unsigned char *module = (const unsigned char *)(UINT_PTR)0x400000u;
    unsigned int manager_rva, slots;
    vv5_villager_table(module, &manager_rva, &slots);
    effects_paused((unsigned char *)(UINT_PTR)(0x400000u + manager_rva + VV5_FIRST_RECORD), slots, VV5_RECORD_SIZE,
                   VV5_EFFECTS, VV5_EFFECT_COUNT, VV5_EFFECT_SIZE, VV5_EFFECT_END, VV5_EFFECTS_MAX, paused);
}

/* At VV5_SITE (esi = the clock, ecx = now): the effects moved on, then the stock branch (fld1; sub ecx, [esi+0x28];
   fstp [esp+0x10]; jmp 0x41EEC1). */
static __declspec(naked) void vv5_from_paused(void) {
    __asm {
        pushad
        mov eax, ecx
        sub eax, dword ptr [esi + 0x28]
        push eax
        call vv5_effects_paused
        popad
        fld1
        sub ecx, dword ptr [esi + 0x28]
        fstp dword ptr [esp + 0x10]
        push VV5_RESUME
        ret
    }
}

/* At VV5_AUTOSAVE_SITE: thiscall(game; slot argument), ret 4 -- the save routine with the flag set around it. */
static __declspec(naked) void vv5_autosave(void) {
    __asm {
        mov dword ptr [g_autosaving], 1
        push dword ptr [esp + 4]
        mov eax, VV5_SAVE
        call eax
        mov dword ptr [g_autosaving], 0
        ret 4
    }
}

/* At VV5_STRIP_SITE: thiscall(villager) -- 0x4660C0 unless the autosave is writing. */
static __declspec(naked) void vv5_strip(void) {
    __asm {
        cmp dword ptr [g_autosaving], 0
        jne keep
        mov eax, VV5_STRIP
        jmp eax
    keep:
        ret
    }
}

/* ---- The Lost Children: the stew pot's 15 minutes pause -----------------------------------
   A finished stew stays in the pot until the computer's clock 0x403200 reaches the end the cook routine sets at
   +0x30450 of the game object (0x425BAB: now + 900); the world update empties the pot then (0x42EBCC..0x42EBE7).
   The game's own village step 0x43B690 moves its other real-clock timers (+0x2EAE0, +0x2EAC0, +0x2EAC4) on by the
   time since its last step (+0x2EAE4) on every step while paused (0x43B6AF..0x43B718); the pot's end was not among
   them, so paused time used the stew up.  At 0x43B6B8 (reached only while paused; eax = now, edi = the game) the
   pot's end, when a stew is in it, is moved on the same way.  The stews themselves act once, when eaten: no
   villager effect to keep. */
#define VV2_SITE 0x43B6B8u
#define VV2_SITE_LEN 6
#define VV2_RESUME 0x43B6BEu
#define VV2_POT_END 0x30450u
/* 0x43B6AF..0x43B6CE: mov edi, eax; mov ecx, eax; call 0x403200; mov edx, [edi+0x2EAE4]; mov ecx, [edi+0x2EAE0];
   sub eax, edx; add ecx, eax; mov [edi+0x2EAE0], ecx */
static const unsigned char VV2_AROUND[] = {
    0x8B, 0xF8, 0x8B, 0xC8, 0xE8, 0x48, 0x7B, 0xFC, 0xFF, 0x8B, 0x97, 0xE4, 0xEA, 0x02, 0x00, 0x8B,
    0x8F, 0xE0, 0xEA, 0x02, 0x00, 0x2B, 0xC2, 0x03, 0xC8, 0x89, 0x8F, 0xE0, 0xEA, 0x02, 0x00,
};
#define VV2_AROUND_VA 0x43B6AFu

/* At VV2_SITE: the stolen `mov edx, [edi+0x2EAE4]`, the pot's end moved on by now - that, then back. */
static __declspec(naked) void vv2_paused_step(void) {
    __asm {
        mov edx, dword ptr [edi + 0x2EAE4]
        cmp dword ptr [edi + VV2_POT_END], 0
        je done
        push eax
        sub eax, edx
        add dword ptr [edi + VV2_POT_END], eax
        pop eax
    done:
        push VV2_RESUME
        ret
    }
}

/* ---- installing ------------------------------------------------------------------------ */

static int installed;

static int readable(unsigned int va, size_t length) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(UINT_PTR)va;
    if (VirtualQuery(at, &info, sizeof info) != sizeof info || info.State != MEM_COMMIT
        || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return 0;
    }
    return (UINT_PTR)at + length <= (UINT_PTR)info.BaseAddress + info.RegionSize;
}

static int holds(unsigned int va, const unsigned char *bytes, size_t length) {
    return readable(va, length) && memcmp((const void *)(UINT_PTR)va, bytes, length) == 0;
}

/* The set_speed detour and the autosave's two sites: all three, or nothing at all. */
static void install_vv3(void) {
    vvfp_site_write w[3];
    if (!holds(VV3_ROUTINE, VV3_STOCK, sizeof VV3_STOCK)
        || !holds(VV3_FTOL, VV3_FTOL_STOCK, sizeof VV3_FTOL_STOCK)
        || !holds(VV3_TWO32, TWO32_FLOAT, sizeof TWO32_FLOAT)
        || !holds(VV3_AUTOSAVE_SITE - 3u, VV3_AUTOSAVE_AROUND, sizeof VV3_AUTOSAVE_AROUND)
        || !holds(VV3_STRIP_SITE - 2u, VV3_STRIP_AROUND, sizeof VV3_STRIP_AROUND)) {
        return;
    }
    vvfp_site_branch(&w[0], VV3_SITE, VV3_SITE_LEN, VV3_STOCK + (VV3_SITE - VV3_ROUTINE), 0xE9,
                     (const void *)vv3_from_paused);
    vvfp_site_branch(&w[1], VV3_AUTOSAVE_SITE, 5, VV3_AUTOSAVE_STOCK, 0xE9, (const void *)vv3_autosave);
    vvfp_site_branch(&w[2], VV3_STRIP_SITE, 5, VV3_STRIP_STOCK, 0xE8, (const void *)vv3_strip);
    if (vvfp_install_sites(w, 3)) {
        installed = 1;
    }
}

/* The from-pause detour and the autosave's two calls: all three, or nothing at all. */
static void install_vv5(void) {
    vvfp_site_write w[3];
    if (!holds(VV5_AROUND_VA, VV5_AROUND, sizeof VV5_AROUND)
        || !holds(VV5_AUTOSAVE_SITE, VV5_AUTOSAVE_STOCK, sizeof VV5_AUTOSAVE_STOCK)
        || !holds(VV5_STRIP_SITE, VV5_STRIP_STOCK, sizeof VV5_STRIP_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], VV5_SITE, VV5_SITE_LEN, VV5_AROUND + (VV5_SITE - VV5_AROUND_VA), 0xE9,
                     (const void *)vv5_from_paused);
    vvfp_site_branch(&w[1], VV5_AUTOSAVE_SITE, 5, VV5_AUTOSAVE_STOCK, 0xE8, (const void *)vv5_autosave);
    vvfp_site_branch(&w[2], VV5_STRIP_SITE, 5, VV5_STRIP_STOCK, 0xE8, (const void *)vv5_strip);
    if (vvfp_install_sites(w, 3)) {
        installed = 1;
    }
}

/* The paused step's site, checked with the instructions round it. */
static void install_vv2(void) {
    vvfp_site_write w[1];
    if (!holds(VV2_AROUND_VA, VV2_AROUND, sizeof VV2_AROUND)) {
        return;
    }
    vvfp_site_branch(&w[0], VV2_SITE, VV2_SITE_LEN, VV2_AROUND + (VV2_SITE - VV2_AROUND_VA), 0xE9,
                     (const void *)vv2_paused_step);
    if (vvfp_install_sites(w, 1)) {
        installed = 1;
    }
}

/* The set_speed detour, the autosave's two calls and the gunk wipe's call: all four, or nothing at all. */
static void install_vv4(void) {
    vvfp_site_write w[4];
    if (!holds(VV4_ROUTINE, VV4_STOCK, sizeof VV4_STOCK)
        || !holds(VV4_TWO32, TWO32_FLOAT, sizeof TWO32_FLOAT)
        || !holds(VV4_AUTOSAVE_SITE, VV4_AUTOSAVE_STOCK, sizeof VV4_AUTOSAVE_STOCK)
        || !holds(VV4_STRIP_SITE, VV4_STRIP_STOCK, sizeof VV4_STRIP_STOCK)
        || !holds(VV4_GUNK_SITE, VV4_GUNK_STOCK, sizeof VV4_GUNK_STOCK)) {
        return;
    }
    vvfp_site_branch(&w[0], VV4_SITE, VV4_SITE_LEN, VV4_STOCK + (VV4_SITE - VV4_ROUTINE), 0xE9,
                     (const void *)vv4_from_paused);
    vvfp_site_branch(&w[1], VV4_AUTOSAVE_SITE, 5, VV4_AUTOSAVE_STOCK, 0xE8, (const void *)vv4_autosave);
    vvfp_site_branch(&w[2], VV4_STRIP_SITE, 5, VV4_STRIP_STOCK, 0xE8, (const void *)vv4_strip);
    vvfp_site_branch(&w[3], VV4_GUNK_SITE, 5, VV4_GUNK_STOCK, 0xE8, (const void *)vv4_wipe_gunk);
    if (vvfp_install_sites(w, 4)) {
        installed = 1;
    }
}

/* ---- A New Home: the Golden Child's fix, in its own companion ---------------------------- */

#define VV1_GAME 1
static const char GOLDEN_CHILD_SAFE[] = "VVFP VV1 Golden Child Safe.dll";
typedef void (__stdcall *startup_fn)(int game, unsigned int shipped);
static int vv1_started;

static void start_vv1(int game, unsigned int shipped) {
    HMODULE module;
    startup_fn startup;
    if (vv1_started) {
        return;
    }
    vv1_started = 1;
    module = vvfp_load_patcher_dll(GOLDEN_CHILD_SAFE);
    if (module == NULL) {
        return;
    }
    startup = (startup_fn)GetProcAddress(module, "VvfpStartup");
    if (startup != NULL) {
        __try {
            startup(game, shipped);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
        }
    }
}

/* Called once by VVFP Startup.dll at game start, outside DllMain. */
__declspec(dllexport) void __stdcall VvfpStartup(int game, unsigned int shipped) {
    if (game == VV1_GAME) {
        start_vv1(game, shipped);
        return;
    }
    if (installed) {
        return;
    }
    if (game == VV2_GAME) {
        install_vv2();
    } else if (game == VV3_GAME) {
        install_vv3();
    } else if (game == VV4_GAME) {
        install_vv4();
    } else if (game == VV5_GAME) {
        install_vv5();
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
