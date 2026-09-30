/* VVFP VV1 Watering Builds -- "Watering the Field" trains Building (A New Home).

   The owner: "Watering the field" gives building skill, but ONLY when it
   makes progress towards the garden puzzle (which it does once the lagoon
   puzzle is complete -- not the well).

   From the stock executable:

     * "Watering the field" is string 588, set by the job builder 0x43FC20.
       The villager fetches LAGOON water, waters the field three to five
       times, and finishes with a type-14 action whose parameter is 4.
       Unlike every other Building job it queues no practice action, so it
       trains no skill.  (The separate "Trying to water strange patch",
       0x4452A0, uses well water and never advances the garden; it is left
       alone.)
     * Type-14 parameter 4 is 0x43A230's case 4, at 0x43B1E6: garden progress
       (village state +0x9FBC) goes up by one, and at 200 the garden is done
       (state +0x9FC0 = 1).  This is the only writer that raises the count.

   So the companion detours 0x43B1E6 -- the progress step itself -- and, when
   the garden is not yet done at that moment, appends one ordinary "practice
   Building" action (type 6, skill 4, exactly what every stock Building job
   queues last: 0x4399F0 in append mode) to the villager's job.  The stock
   increment then runs unchanged.  Appending rather than calling the skill
   trainer here matters: a failed roll clears the villager's remaining
   actions (0x43D440 -> 0x439470), so it must happen at the end of the job,
   as it does for every other Building job, not in the middle of this one.
   Live play and catch-up both run queued type-6 actions (0x448600,
   0x446C70), so both are covered.

   Installed at run time by VvfpVv1WateringBuildsInstall(), which the Origins
   companion calls once from its per-frame tick; it verifies the twelve
   stock bytes first and installs nothing on any other build.  Missing DLL:
   the stock game. */
#include <windows.h>
#include <string.h>

#define SITE_VA          0x43B1E6u
#define SITE_LENGTH      12
#define RESUME_VA        0x43B1F2u
#define PUSH_ACTION_VA   0x4399F0u

static const unsigned char SITE_STOCK[SITE_LENGTH] = {
    0x8B, 0x86, 0x10, 0xE0, 0x03, 0x00,        /* mov eax, [esi+0x3E010] */
    0xFF, 0x80, 0xBC, 0x9F, 0x00, 0x00          /* inc dword ptr [eax+0x9FBC] */
};

/* Counters the tests read.  Compiled only into the TEST build (VVFP_TEST,
   tests/test_dlls/): the shipped DLL carries no counters and no probe. */
#ifdef VVFP_TEST
struct vv1_watering_stats {
    int progress_steps;     /* the garden progress step ran */
    int builds_queued;      /* ...and a practice-Building action was appended */
};
__declspec(dllexport) struct vv1_watering_stats VvfpVv1WateringStats = { 0 };
#endif

static const unsigned int push_action_va = PUSH_ACTION_VA;
static const unsigned int resume_va = RESUME_VA;

/* At 0x43B1E6: esi = the villager array (0x43A230's this), and the stack
   holds the routine's saved edi, ebp, ebx, esi, then its return address,
   then the villager's index -- [esp+0x14], which the stock code reads at
   0x43B287.  pushad and pushfd add 0x24 more. */
static __declspec(naked) void watering_stub(void) {
    __asm {
        pushfd
        pushad
#ifdef VVFP_TEST
        inc dword ptr [VvfpVv1WateringStats]
#endif
        mov eax, dword ptr [esi + 0x3E010]      ; village state
        cmp byte ptr [eax + 0x9FC0], 0          ; garden already done?
        jne skip
#ifdef VVFP_TEST
        inc dword ptr [VvfpVv1WateringStats + 4]
#endif
        mov edx, dword ptr [esp + 0x38]         ; the villager's index
        push 4                                  ; skill: Building
        push 0                                  ; mode: append
        push 0
        push 0
        push 0
        push 6                                  ; type: practice a skill
        push edx
        mov ecx, esi
        call dword ptr [push_action_va]         ; thiscall, ret 0x1C
    skip:
        popad
        popfd
        mov eax, dword ptr [esi + 0x3E010]      ; the displaced stock bytes
        inc dword ptr [eax + 0x9FBC]
        jmp dword ptr [resume_va]
    }
}

static int site_is_stock(void) {
    MEMORY_BASIC_INFORMATION info;
    const void *site = (const void *)(uintptr_t)SITE_VA;
    if (VirtualQuery(site, &info, sizeof(info)) != sizeof(info)
        || info.State != MEM_COMMIT
        || !(info.Protect & (PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE | PAGE_EXECUTE_WRITECOPY))) {
        return 0;
    }
    return memcmp(site, SITE_STOCK, SITE_LENGTH) == 0;
}

/* The bytes the site is overwritten with: a jmp to the stub, displaced from
   the SITE (where it executes), then nops. */
static void site_bytes(unsigned char *out) {
    unsigned int rel = (unsigned int)((const unsigned char *)watering_stub
                                      - ((const unsigned char *)(uintptr_t)SITE_VA + 5));
    int i;
    out[0] = 0xE9;
    memcpy(out + 1, &rel, 4);
    for (i = 5; i < SITE_LENGTH; ++i) {
        out[i] = 0x90;
    }
}

static int install_state;   /* 0 untried, 1 installed, -1 refused */

/* Called by the Origins companion from its per-frame tick.  Idempotent. */
__declspec(dllexport) int __stdcall VvfpVv1WateringBuildsInstall(void) {
    unsigned char bytes[SITE_LENGTH];
    unsigned char *site = (unsigned char *)(uintptr_t)SITE_VA;
    DWORD old;
    if (install_state != 0) {
        return install_state == 1;
    }
    install_state = -1;
    if (!site_is_stock()) {
        return 0;
    }
    site_bytes(bytes);
    if (!VirtualProtect(site, SITE_LENGTH, PAGE_EXECUTE_READWRITE, &old)) {
        return 0;
    }
    memcpy(site, bytes, SITE_LENGTH);
    VirtualProtect(site, SITE_LENGTH, old, &old);
    FlushInstructionCache(GetCurrentProcess(), site, SITE_LENGTH);
    install_state = 1;
    return 1;
}

#ifdef VVFP_TEST
/* For the test build only: the site, its stock bytes, what it becomes,
   and the stub. */
__declspec(dllexport) int __stdcall VvfpVv1WateringBuildsProbe(unsigned int *site_va,
                                                                unsigned char *stock,
                                                                unsigned char *patched,
                                                                unsigned int *stub_va) {
    *site_va = SITE_VA;
    memcpy(stock, SITE_STOCK, SITE_LENGTH);
    site_bytes(patched);
    *stub_va = (unsigned int)(uintptr_t)watering_stub;
    return SITE_LENGTH;
}
#endif /* VVFP_TEST */

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}
