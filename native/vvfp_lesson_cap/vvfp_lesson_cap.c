/* VVFP Lesson Cap -- The Secret City's Tribal Chief lessons stop at 50.

   The owner: "Tribal chief lecturing children limits skill gain to exactly
   50", and, when a skill is already at 50, option (b): pick only among the
   skills still below 50, so no lesson is wasted -- the same rule the A New
   Home and The Lost Children lesson patches follow, and the rule The Tree of
   Life's and New Believers' Nursery Schools already apply (a skill at 50 or
   above is skipped).

   WHAT THE STOCK GAME DOES, read from the executable.  The Leadership-2
   Tribal Chief's lesson ends with callback 42 in the callback dispatcher.
   Its case, at 0x458F11:

     push 5; call RNG (0x4032D0); add esp, 4      ; one of five skills
     cmp eax, 4; ja default; jmp [0x459474 + eax*4]
     -- each branch --
     push 3; call RNG; mov ecx, [esp+0xC]; add esp, 4
     add eax, 7                                    ; 7, 8 or 9 points
     push eax; push <skill>; add ecx, 0xEAC
     call 0x455740                                 ; skills[i] += n, clamped 0..100
     pop esi; ret 8

   [esp+8] at the case is the child's record; the five skills are ints at
   record + 0xEAC.  The helper caps at 100, so repeated lessons make Masters.

   WHAT THIS COMPANION DOES.  VvfpLessonCapAward(3, record) does the same
   award with the cap at 50: it counts the skills below 50 (none -> the
   lesson awards nothing), asks the game's own RNG for one of them, asks it
   for 3 (+7) as the stock case does, adds the points and stops at exactly
   50.  A skill at or above 50 is never chosen and never lowered.  The
   executable-side stub in the page Origins appends (see
   scripts/build_vv3_lesson_cap_feature.py) diverts the case to it and
   returns through the case's own `pop esi; ret 8`. */
#include <windows.h>

#define CAP 50
#define SKILLS 5

/* The Secret City's own generator: cdecl, one bound, returns 0..bound-1.
   Called so the lesson consumes the stream exactly as the stock case does. */
typedef int (__cdecl *rng_t)(int bound);
#define VV3_RNG ((rng_t)0x4032D0u)
#define VV3_SKILLS_OFFSET 0xEACu

/* Counters a test can read from the running game.  Diagnostic only. */
struct vvfp_lesson_cap_stats {
    int lessons;        /* the award was reached */
    int awarded;        /* a skill gained */
    int nothing;        /* every skill was already at 50 or above */
};
__declspec(dllexport) struct vvfp_lesson_cap_stats VvfpLessonCapStats = { 0 };

static int award(int *skills, rng_t rng) {
    int eligible[SKILLS];
    int count = 0;
    int i, k, points;
    ++VvfpLessonCapStats.lessons;
    for (i = 0; i < SKILLS; ++i) {
        if (skills[i] < CAP) {
            eligible[count++] = i;
        }
    }
    if (count == 0) {
        ++VvfpLessonCapStats.nothing;
        return 0;
    }
    k = rng(count);
    if (k < 0 || k >= count) {
        k = 0;                         /* not the generator's contract; be safe */
    }
    points = rng(3) + 7;
    i = eligible[k];
    skills[i] += points;
    if (skills[i] > CAP) {
        skills[i] = CAP;
    }
    ++VvfpLessonCapStats.awarded;
    return 1;
}

/* Called from the stub with the case's record pointer.  Returns 1 when a
   skill gained, 0 when nothing could.  cdecl, like the fix-huts decision. */
__declspec(dllexport) int __cdecl VvfpLessonCapAward(int game_id, unsigned char *record) {
    if (game_id != 3 || record == NULL) {
        return 0;
    }
    return award((int *)(record + VV3_SKILLS_OFFSET), VV3_RNG);
}

/* For tests: the same award over a caller-supplied skill array with a
   caller-supplied generator, so an emulator can script every branch. */
__declspec(dllexport) int __stdcall VvfpLessonCapProbe(int *skills, rng_t rng) {
    return award(skills, rng);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
