/* VVFP Healers Study -- healers keep studying plants regardless of the food
   supply (A New Home, The Lost Children).

   The owner: "Healers study plants (VV1-VV2) or study medicine regardless of
   the food supply (for VV4 and VV5, only if the Hospital is accessible/
   built)."  The Secret City, The Tree of Life and New Believers read no food
   total on the way to their medicine study (and VV4/VV5 already require the
   Hospital), so only A New Home and The Lost Children need this.

   WHAT THE STOCK GAMES DO, read from the executables.  One idle scheduler,
   reached from both the live per-frame caller and the catch-up loop:

     VV1 0x448220  cmp [state+0xA2EC], 400; jge 0x44836F.  Below 400 it tries
                   the preferred job and then 0x447CD0(index, 60), which
                   continues the villager's last activity [record+0x3B8]; for
                   activity 9 (plant study) that starts "Studying medical
                   cactus" (0x443270) when Healing >= 1 or the village flag
                   [state+0xA30C] is clear.  At 400 food or more both are
                   skipped, so a healer who was studying stops.
     VV2 0x461850  the same at 300 food: below it, 0x460590(index, 40)
                   continues state [record+0x7E0]; state 9 is plant study
                   (Healing >= 1 or the flag, then one of four plants).

   Plant-study state 9 is set only when the player drops a villager on a plant
   (and, in VV2, by Easier Healing Mastery when no one is sick).

   WHAT THIS COMPANION DOES.  At the high-food target -- the first
   instruction of the general selection (VV1 0x44836F, VV2 0x461A22), which
   the low-food path also falls into -- a villager in plant-study state 9 at
   or above the threshold gets the same continuation call the stock game makes
   below it; if that starts a job, the scheduler's own "done" epilogue runs
   (VV1 0x44843D, VV2 0x461AF0).  Below the threshold (the stock code already
   made the call), for every other state, and when the continuation starts
   nothing, the displaced instructions run and the stock selection continues.

   Installed at run time by VvfpHealersStudyInstall(game) from the Origins
   companion, which runs every frame; the stock bytes at the site are verified
   first, and any other build installs nothing. */
#include <windows.h>
#include <string.h>
#include <stdint.h>

/* Counters a test can read from the running game.  Diagnostic only. */
struct vvfp_healers_stats {
    int checks;         /* a studying villager reached the site at high food */
    int continued;      /* the continuation started a job */
};
__declspec(dllexport) struct vvfp_healers_stats VvfpHealersStudyStats = { 0 };

/* ---- VV1 --------------------------------------------------------------- */
/* ebp = state, esi = village (villager array), edi = the villager's index. */
#define VV1_SITE      0x44836Fu
#define VV1_RESUME    0x448379u     /* push eax: the pick */
#define VV1_DONE      0x44843Du
#define VV1_PICKER    0x439AE0u
#define VV1_CONTINUE  0x447CD0u
static const unsigned char VV1_STOCK[10] = { 0x6A, 0x00, 0x57, 0x8B, 0xCE, 0xE8, 0x67, 0x17, 0xFF, 0xFF };

static int __cdecl vv1_studying(const unsigned char *state, const unsigned char *village, unsigned int index) {
    if (*(const int *)(state + 0xA2ECu) < 400) {
        return 0;                                  /* the stock code already asked */
    }
    if (*(const int *)(village + index * 0x3D8u + 0x3B8u) != 9) {
        return 0;
    }
    ++VvfpHealersStudyStats.checks;
    return 1;
}

static const unsigned int vv1_resume = VV1_RESUME, vv1_done = VV1_DONE;
static const unsigned int vv1_picker = VV1_PICKER, vv1_continue = VV1_CONTINUE;
static __declspec(naked) void vv1_stub(void) {
    __asm {
        pushad
        push edi
        push esi
        push ebp
        call vv1_studying
        add esp, 12
        test eax, eax
        popad
        jz selection
        push 0x3C
        push edi
        mov ecx, esi
        call dword ptr [vv1_continue]
        test eax, eax
        jz selection
        inc dword ptr [VvfpHealersStudyStats + 4]
        jmp dword ptr [vv1_done]
    selection:
        ; the displaced selection, entered as the scheduler's own call: the
        ; picker returns straight to the stock code after the call site, so
        ; anything that looks at the picker's caller (Builders and Healers
        ; Work First) sees the scheduler.
        push 0
        push edi
        mov ecx, esi
        push dword ptr [vv1_resume]
        jmp dword ptr [vv1_picker]
    }
}

/* ---- VV2 --------------------------------------------------------------- */
/* esi = village, edi = the villager's index, ebp = the villager's record;
   state = [esi+0xE574D4], food [state+0x2EAA4]. */
#define VV2_SITE      0x461A22u
#define VV2_RESUME    0x461A2Cu
#define VV2_DONE      0x461AF0u
#define VV2_PICKER    0x449C60u
#define VV2_CONTINUE  0x460590u
static const unsigned char VV2_STOCK[10] = { 0x6A, 0x00, 0x57, 0x8B, 0xCE, 0xE8, 0x34, 0x82, 0xFE, 0xFF };

static int __cdecl vv2_studying(const unsigned char *village, const unsigned char *record) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4u);
    if (*(const int *)(state + 0x2EAA4u) < 300) {
        return 0;
    }
    if (*(const int *)(record + 0x7E0u) != 9) {
        return 0;
    }
    ++VvfpHealersStudyStats.checks;
    return 1;
}

static const unsigned int vv2_resume = VV2_RESUME, vv2_done = VV2_DONE;
static const unsigned int vv2_picker = VV2_PICKER, vv2_continue = VV2_CONTINUE;
static __declspec(naked) void vv2_stub(void) {
    __asm {
        pushad
        push ebp
        push esi
        call vv2_studying
        add esp, 8
        test eax, eax
        popad
        jz selection
        push 0x28
        push edi
        mov ecx, esi
        call dword ptr [vv2_continue]
        test eax, eax
        jz selection
        inc dword ptr [VvfpHealersStudyStats + 4]
        jmp dword ptr [vv2_done]
    selection:
        ; the displaced selection, entered as the scheduler's own call: the
        ; picker returns straight to the stock code after the call site, so
        ; anything that looks at the picker's caller (Builders and Healers
        ; Work First) sees the scheduler.
        push 0
        push edi
        mov ecx, esi
        push dword ptr [vv2_resume]
        jmp dword ptr [vv2_picker]
    }
}

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};
static const struct site SITES[3] = {
    { 0 },
    { VV1_SITE, VV1_STOCK, sizeof VV1_STOCK, vv1_stub },
    { VV2_SITE, VV2_STOCK, sizeof VV2_STOCK, vv2_stub },
};
static int install_state[3];

static int site_is_stock(const struct site *s) {
    MEMORY_BASIC_INFORMATION info;
    const void *at = (const void *)(uintptr_t)s->va;
    if (VirtualQuery(at, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(at, s->stock, (size_t)s->length) == 0;
}

static void site_bytes(const struct site *s, unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)s->stub
                                      - ((const unsigned char *)(uintptr_t)s->va + 5));
    int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < s->length; ++i) {
        out[i] = 0x90;
    }
}

/* Called by a companion that runs every frame in the game.  Idempotent. */
__declspec(dllexport) int __stdcall VvfpHealersStudyInstall(int game_id) {
    const struct site *s;
    unsigned char bytes[16];
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
    if (!site_is_stock(s)) {
        return 0;
    }
    at = (unsigned char *)(uintptr_t)s->va;
    site_bytes(s, bytes);
    if (!VirtualProtect(at, (SIZE_T)s->length, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(at, bytes, (size_t)s->length);
    VirtualProtect(at, (SIZE_T)s->length, old, &old);
    FlushInstructionCache(GetCurrentProcess(), at, (SIZE_T)s->length);
    install_state[game_id] = 1;
    return 1;
}

/* For the test: the site, its stock bytes, what it becomes, the stub. */
__declspec(dllexport) int __stdcall VvfpHealersStudyProbeSite(int game_id, unsigned int *va,
                                                               unsigned char *stock,
                                                               unsigned char *patched,
                                                               unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 2) {
        return 0;
    }
    s = &SITES[game_id];
    *va = s->va;
    memcpy(stock, s->stock, (size_t)s->length);
    site_bytes(s, patched);
    *stub_va = (unsigned int)(uintptr_t)s->stub;
    return s->length;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
