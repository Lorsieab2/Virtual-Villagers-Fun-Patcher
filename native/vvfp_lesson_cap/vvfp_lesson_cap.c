/* VVFP Lesson Cap -- lessons stop at 50 (A New Home, The Lost Children,
   The Secret City).

   The owner: "going to school (VV1) / attending lessons (VV2) / the Tribal
   Chief lecturing children (VV3) limits skill gain to exactly 50", and,
   when a skill is already at 50, option (b): pick only among the skills
   still below 50, so no lesson is wasted -- the rule The Tree of Life's and
   New Believers' Nursery Schools already apply (a skill at 50 or above is
   skipped).  The owner keeps the ordinary lesson rows as they are (cap 100)
   and adds these as SEPARATE rows on top of them.

   THE THREE AWARDS, read from the executables and the shipped rows:

     VV1  School Lessons Grant Skill: callback 127, private cave 0x4566E0
          (entered from the callback dispatcher's detour at 0x43A230 with
          ecx = the villager array, [esp+4] = the child's index, [esp+8] =
          the callback id).  Record stride 0x3D8, five int skills at +0x3BC,
          RNG 0x402F10 (cdecl, one bound).
     VV2  Teaching Children Grants Skill: callback 127, the shared private
          dispatcher cave 0x473D80 (same contract; it also carries Hospital
          Recovery's callback 126, which stays the cave's own).  Stride
          0xE48C, skills at +0x7E4, RNG 0x4031A0.
     VV3  the game's own callback 42 at 0x458F11: push 5 / call RNG picks
          one of five, then push 3 / call RNG + 7 through the 100-capped
          helper 0x455740.  [esp+8] at the case is the record; skills at
          record + 0xEAC, RNG 0x4032D0.

   WHAT THIS COMPANION DOES.  award() counts the skills below 50 (none ->
   the lesson awards nothing), asks the game's own RNG for one of them and
   for 3 (+7) as the stock awards do, adds the points and stops at exactly
   50.  A skill at or above 50 is never chosen and never lowered.

     VV1/VV2: VvfpLessonCapInstall(game), called once from the Origins
     companion's per-frame tick, verifies the lesson row's own cave head at
     the site (`cmp [esp+8], 7Fh; jne; pushad; mov esi, ecx`) and detours
     its first instruction to a stub that handles callback 127 here and
     sends every other id back into the cave's `jne` with the compare
     replayed.  The lesson row not applied (the cave is zeros), or a
     different build: nothing is installed.
     VV3: an executable-side stub in the page Origins appends (see
     scripts/build_lesson_cap_features.py) calls VvfpLessonCapAward(3,
     record) and returns through the case's own `pop esi; ret 8`. */
#include <windows.h>
#include <string.h>
#include <stdint.h>

#define CAP 50
#define SKILLS 5

typedef int (__cdecl *rng_t)(int bound);

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

/* ---- VV1 / VV2: the lesson rows' callback-127 caves ------------------- */
/* Both caves open with the same ten bytes; only the first instruction (the
   five-byte cmp) is replaced, so the cave's `jne` at site+5 stays the
   re-entry for every other callback id. */
static const unsigned char CAVE_HEAD[10] = {
    0x83, 0x7C, 0x24, 0x08, 0x7F,      /* cmp dword ptr [esp+8], 7Fh */
    0x75, 0x3F,                        /* jne stock */
    0x60,                              /* pushad */
    0x8B, 0xF1                         /* mov esi, ecx */
};
#define VV1_SITE    0x4566E0u
#define VV1_STRIDE  0x3D8u
#define VV1_SKILLS  0x3BCu
#define VV1_RNG     0x402F10u
#define VV2_SITE    0x473D80u
#define VV2_STRIDE  0xE48Cu
#define VV2_SKILLS  0x7E4u
#define VV2_RNG     0x4031A0u

static int __cdecl vv1_award(unsigned char *array, unsigned int index) {
    return award((int *)(array + index * VV1_STRIDE + VV1_SKILLS), (rng_t)VV1_RNG);
}

static int __cdecl vv2_award(unsigned char *array, unsigned int index) {
    return award((int *)(array + index * VV2_STRIDE + VV2_SKILLS), (rng_t)VV2_RNG);
}

static const unsigned int vv1_resume = VV1_SITE + 5, vv2_resume = VV2_SITE + 5;

/* The stub: the displaced compare, then either this award (callback 127)
   or the cave's own `jne`, whose flags the replayed compare provides. */
#define CAVE_STUB(NAME)                                                       \
    static __declspec(naked) void NAME##_stub(void) {                         \
        __asm {                                                              \
            __asm cmp dword ptr [esp + 8], 0x7F                              \
            __asm je handle_127                                                  \
            __asm jmp dword ptr [NAME##_resume]                              \
            __asm handle_127:                                                    \
            __asm pushad                                                     \
            __asm push dword ptr [esp + 0x24]     /* the child's index */    \
            __asm push ecx                        /* the villager array */   \
            __asm call NAME##_award                                          \
            __asm add esp, 8                                                 \
            __asm popad                                                      \
            __asm ret 8                                                      \
        }                                                                    \
    }

CAVE_STUB(vv1)
CAVE_STUB(vv2)

/* ---- VV3: called from the executable-side stub -------------------------- */
#define VV3_RNG ((rng_t)0x4032D0u)
#define VV3_SKILLS_OFFSET 0xEACu

/* Returns 1 when a skill gained, 0 when nothing could.  cdecl, like the
   fix-huts decision. */
__declspec(dllexport) int __cdecl VvfpLessonCapAward(int game_id, unsigned char *record) {
    if (game_id != 3 || record == NULL) {
        return 0;
    }
    return award((int *)(record + VV3_SKILLS_OFFSET), VV3_RNG);
}

/* ---- Installing (VV1, VV2) ---------------------------------------------- */
struct site {
    unsigned int va;
    void (*stub)(void);
};
static const struct site SITES[3] = { { 0 }, { VV1_SITE, vv1_stub }, { VV2_SITE, vv2_stub } };
static int install_state[3];

static int site_is_the_cave_head(const struct site *s) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)s->va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, CAVE_HEAD, sizeof CAVE_HEAD) == 0;
}

static void site_bytes(const struct site *s, unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)s->stub
                                      - ((const unsigned char *)(uintptr_t)s->va + 5));
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
}

/* Called by a companion that runs every frame in the game.  Idempotent. */
__declspec(dllexport) int __stdcall VvfpLessonCapInstall(int game_id) {
    const struct site *s;
    unsigned char bytes[5];
    unsigned char *at;
    DWORD old;
    if (game_id < 1 || game_id > 2) {
        return 0;
    }
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = -1;
    s = &SITES[game_id];
    if (!site_is_the_cave_head(s)) {
        return 0;                      /* the lesson row is not applied */
    }
    at = (unsigned char *)(uintptr_t)s->va;
    site_bytes(s, bytes);
    if (!VirtualProtect(at, sizeof bytes, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, sizeof bytes);
    VirtualProtect(at, sizeof bytes, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, sizeof bytes);
    install_state[game_id] = 1;
    return 1;
}

/* For the test: the site, the cave head it expects, what it becomes, the
   stub. */
__declspec(dllexport) int __stdcall VvfpLessonCapProbeSite(int game_id, unsigned int *va,
                                                            unsigned char *expected,
                                                            unsigned char *patched,
                                                            unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 2) {
        return 0;
    }
    s = &SITES[game_id];
    *va = s->va;
    memcpy(expected, CAVE_HEAD, sizeof CAVE_HEAD);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return (int)sizeof CAVE_HEAD;
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
