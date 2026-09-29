/* VVFP Work First -- Builders and Healers Work First (all five games).

   An addendum to Builders Fix Huts When Idle (and, in A New Home and The Lost
   Children, Healers Study Plants Regardless of Food): while not every
   population hut is built, a villager whose selected job is Building does
   building work first and one whose selected job is Healing does healing and
   study first, at any food level, before idling, farming or gathering.

   Loaded by "VVFP Fix Huts.dll" (VvfpFixHutsInstall, from a companion that
   runs every frame) by full path; The Secret City's hook is a stub in the
   fix-huts page that resolves VvfpWorkFirstPriority.  Not shipped: nothing
   is loaded, and every hook falls through to the stock code. */
#include <windows.h>
#include <string.h>
#include <stdint.h>

/* ---- Population huts ------------------------------------------------------ */
/* The same tests the fix-huts companion makes (native/vvfp_fix_huts):
   VV1 state = [village+0x3E010], huts complete: bytes +0x9FE8/+0x9FF0/+0x9FF8
   == 1; VV2 state = [village+0xE574D4], +0x2E818/+0x2E820/+0x2E828; VV3-VV5
   the games' own "project complete" predicate over the four huts. */
static int vv1_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0x3E010);
    return !(state[0x9FE8] == 1 && state[0x9FF0] == 1 && state[0x9FF8] == 1);
}

static int vv2_huts_incomplete(const unsigned char *village) {
    const unsigned char *state = *(const unsigned char *const *)(village + 0xE574D4);
    return !(state[0x2E818] == 1 && state[0x2E820] == 1 && state[0x2E828] == 1);
}

struct later_game {
    unsigned int complete_fn;      /* __stdcall(int) -> al, ecx = complete_obj */
    unsigned int complete_obj;
    int project_base;
};
static const struct later_game VV3 = { 0x4321F0u, 0x594620u, 0 };
static const struct later_game VV4 = { 0x438960u, 0x4D8BF8u, 19 };
static const struct later_game VV5 = { 0x43AE80u, 0x51E008u, 19 };

typedef unsigned char (__stdcall *complete_t)(int);

static int later_complete(const struct later_game *g, int hut) {
    complete_t fn = (complete_t)(uintptr_t)g->complete_fn;
    unsigned char r;
    unsigned int obj = g->complete_obj;
    int arg = g->project_base + hut;
    __asm {
        mov ecx, obj
        push arg
        call fn
        mov r, al
    }
    return r != 0;
}

static int later_huts_incomplete(const struct later_game *g) {
    int i;
    for (i = 0; i < 4; ++i) {
        if (!later_complete(g, i)) {
            return 1;
        }
    }
    return 0;
}

/* ---- Builders and healers work first ------------------------------------ */
/* The owner: "in both low and high food situations, builders and healers
   still should prioritize fixing huts over other stuff for all 5 games" --
   builders their building work and healers their healing and study, before
   anything else, at any food level, while not every population hut is built.

   Every game's adult idle scheduler asks one job picker what to do; the
   picker weighs the skills and the selected job and may also say "nothing".
   Here the picker, when called from the adult scheduler, answers with the
   villager's own selected job when that job is Building or Healing and a
   population hut is still unbuilt; the stock scheduler then dispatches it
   exactly as it dispatches any pick (on both of its food paths).  Every other
   villager, every other caller of the picker (the younger villagers' routine)
   and every village whose huts are all built get the stock picker.

     game  picker     entry (displaced)             scheduler return addresses  selected job      Building  Healing
     VV1   0x439AE0   push ebx/ebp/esi; push 100    0x44834C 0x448379           village+i*0x3D8+0x3D0   4       5
     VV2   0x449C60   push ecx/ebx/esi/edi; xor esi 0x4619FF 0x461A2C           village+i*0xE48C+0x7F8  5       3
     VV3   0x459730   push ebx/esi/edi; push 100    0x45C227 0x45C286           record+0xEC0            4       2
     VV4   0x461CC0   push ebx/esi/edi; push 100    0x4659B0 0x465A22           [obj+0x1B88]+0x1C70     4       2
     VV5   0x46A3C0   push ebx/esi/edi; push 100    0x46F271 0x46F2E2           [obj+0x1B88]+0x1C74     4       2

   VV1/VV2: thiscall(index, flag), ret 8, ecx = village.  VV3: thiscall
   (record), ret 4, ecx = the scheduler object.  VV4/VV5: thiscall(), ret,
   ecx = the villager object.  The Secret City's hook is executable-side
   (VvfpWorkFirstPriority below). */

__declspec(dllexport) int VvfpWorkFirstPicks = 0;

static int priority_job(int selected, int building, int healing, int huts_incomplete) {
    if ((selected == building || selected == healing) && huts_incomplete) {
        ++VvfpWorkFirstPicks;
        return selected;
    }
    return -1;
}

static int __cdecl vv1_priority(unsigned int ret, const unsigned char *village, unsigned int index) {
    if (ret != 0x44834Cu && ret != 0x448379u) return -1;
    return priority_job(*(const int *)(village + index * 0x3D8u + 0x3D0u), 4, 5,
                        vv1_huts_incomplete(village));
}

static int __cdecl vv2_priority(unsigned int ret, const unsigned char *village, unsigned int index) {
    if (ret != 0x4619FFu && ret != 0x461A2Cu) return -1;
    return priority_job(*(const int *)(village + index * 0xE48Cu + 0x7F8u), 5, 3,
                        vv2_huts_incomplete(village));
}

static int __cdecl vv4_priority(unsigned int ret, const unsigned char *object) {
    const unsigned char *record;
    if (ret != 0x4659B0u && ret != 0x465A22u) return -1;
    record = *(const unsigned char *const *)(object + 0x1B88u);
    return priority_job(*(const int *)(record + 0x1C70u), 4, 2, later_huts_incomplete(&VV4));
}

static int __cdecl vv5_priority(unsigned int ret, const unsigned char *object) {
    const unsigned char *record;
    if (ret != 0x46F271u && ret != 0x46F2E2u) return -1;
    record = *(const unsigned char *const *)(object + 0x1B88u);
    return priority_job(*(const int *)(record + 0x1C74u), 4, 2, later_huts_incomplete(&VV5));
}

/* For The Secret City's executable-side stub at the picker's entry: the
   scheduler's return address and the record argument.  -1 = the stock
   picker. */
__declspec(dllexport) int __cdecl VvfpWorkFirstPriority(int game_id, unsigned int ret, const unsigned char *record) {
    if (game_id != 3 || record == NULL) return -1;
    if (ret != 0x45C227u && ret != 0x45C286u) return -1;
    return priority_job(*(const int *)(record + 0xEC0u), 4, 2, later_huts_incomplete(&VV3));
}

#define VV1_PICKER 0x439AE0u
#define VV2_PICKER 0x449C60u
#define VV4_PICKER 0x461CC0u
#define VV5_PICKER 0x46A3C0u
static const unsigned char VV1_PICKER_STOCK[5] = { 0x53, 0x55, 0x56, 0x6A, 0x64 };
static const unsigned char VV2_PICKER_STOCK[6] = { 0x51, 0x53, 0x56, 0x57, 0x33, 0xF6 };
static const unsigned char VV4_PICKER_STOCK[5] = { 0x53, 0x56, 0x57, 0x6A, 0x64 };
static const unsigned char VV5_PICKER_STOCK[5] = { 0x53, 0x56, 0x57, 0x6A, 0x64 };
static const unsigned int vv1_picker_body = VV1_PICKER + 5, vv2_picker_body = VV2_PICKER + 6;
static const unsigned int vv4_picker_body = VV4_PICKER + 5, vv5_picker_body = VV5_PICKER + 5;

/* pushad puts the return address at [esp+0x20] and the first argument at
   [esp+0x24]; a forced job goes back through pushad's eax slot. */
static __declspec(naked) void vv1_picker_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x24]     ; index
        push ecx                        ; village
        push dword ptr [esp + 0x28]     ; the caller (0x20 + the two pushes)
        call vv1_priority
        add esp, 12
        cmp eax, -1
        je stock
        mov [esp + 0x1C], eax
        popad
        ret 8
    stock:
        popad
        push ebx
        push ebp
        push esi
        push 0x64
        jmp dword ptr [vv1_picker_body]
    }
}

static __declspec(naked) void vv2_picker_stub(void) {
    __asm {
        pushad
        push dword ptr [esp + 0x24]
        push ecx
        push dword ptr [esp + 0x28]
        call vv2_priority
        add esp, 12
        cmp eax, -1
        je stock
        mov [esp + 0x1C], eax
        popad
        ret 8
    stock:
        popad
        push ecx
        push ebx
        push esi
        push edi
        xor esi, esi
        jmp dword ptr [vv2_picker_body]
    }
}

#define LATER_PICKER_STUB(NAME)                                               \
    static __declspec(naked) void NAME##_picker_stub(void) {                  \
        __asm {                                                              \
            __asm pushad                                                     \
            __asm push ecx                                                   \
            __asm push dword ptr [esp + 0x24]                                \
            __asm call NAME##_priority                                       \
            __asm add esp, 8                                                 \
            __asm cmp eax, -1                                                \
            __asm je stock_picker                                            \
            __asm mov [esp + 0x1C], eax                                      \
            __asm popad                                                      \
            __asm ret                                                        \
            __asm stock_picker:                                              \
            __asm popad                                                      \
            __asm push ebx                                                   \
            __asm push esi                                                   \
            __asm push edi                                                   \
            __asm push 0x64                                                  \
            __asm jmp dword ptr [NAME##_picker_body]                          \
        }                                                                    \
    }

LATER_PICKER_STUB(vv4)
LATER_PICKER_STUB(vv5)

/* ---- Installing ---------------------------------------------------------- */
struct site {
    unsigned int va;
    const unsigned char *stock;
    int length;
    void (*stub)(void);
};

static const struct site SITES[6] = {
    { 0 },
    { VV1_PICKER, VV1_PICKER_STOCK, sizeof VV1_PICKER_STOCK, vv1_picker_stub },
    { VV2_PICKER, VV2_PICKER_STOCK, sizeof VV2_PICKER_STOCK, vv2_picker_stub },
    { 0 },
    { VV4_PICKER, VV4_PICKER_STOCK, sizeof VV4_PICKER_STOCK, vv4_picker_stub },
    { VV5_PICKER, VV5_PICKER_STOCK, sizeof VV5_PICKER_STOCK, vv5_picker_stub },
};
static int install_state[6];

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

/* Called by the fix-huts companion from its per-frame install.  Idempotent. */
__declspec(dllexport) int __stdcall VvfpWorkFirstInstall(int game_id) {
    const struct site *s;
    unsigned char bytes[16];
    unsigned char *at;
    DWORD old;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    if (install_state[game_id] != 0) {
        return install_state[game_id] == 1;
    }
    install_state[game_id] = -1;
    s = &SITES[game_id];
    if (s->va == 0 || !site_is_stock(s)) {
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
__declspec(dllexport) int __stdcall VvfpWorkFirstProbeSite(int game_id, unsigned int *va,
                                                            unsigned char *stock,
                                                            unsigned char *patched,
                                                            unsigned int *stub_va) {
    const struct site *s;
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    s = &SITES[game_id];
    if (s->va == 0) {
        return 0;
    }
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
