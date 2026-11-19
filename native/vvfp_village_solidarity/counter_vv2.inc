/* The Lost Children's Tech screen counter and its "?" button: A New Home's code (counter_vv1.inc, sol12_*), with The
   Lost Children's addresses.  The screen (vtable 0x48F9D8) draws in 0x441830; both of its paths meet at 0x441D2B,
   where its text widgets are drawn.  Its constructor attaches its title (string 0xC9) at 0x443559; its slot 3 is
   0x4437C0.  Its technologies' "?" open 0x4422F0: the sound 0x4E (0x43F010), the popup 0x433120, the modal loop
   0x401AD0, the destructor 0x432BD0. */

#define SOL_VV2_SITE 0x00441D2Bu            /* mov ecx, [esi+0x124] (8B 8E 24 01 00 00) */
#define SOL_VV2_RESUME 0x00441D31u
#define SOL_VV2_MAKE_SITE 0x00443559u       /* mov ecx, [esi+0x18]; push 0xC9 (8B 4E 18 68 C9 00 00 00) */
#define SOL_VV2_MAKE_RESUME 0x00443561u
#define SOL_VV2_SLOT 0x0048F9E4u            /* the Tech screen's vtable slot 3: 0x4437C0 */
static const unsigned char SOL_VV2_MAKE_STOCK[8] = { 0x8B, 0x4E, 0x18, 0x68, 0xC9, 0x00, 0x00, 0x00 };
static const unsigned char SOL_VV2_SLOT_STOCK[4] = { 0xC0, 0x37, 0x44, 0x00 };
static const sol12_game SOL_VV2 = {
    0x004096B0u, 0x004021F0u, 0x00402190u,              /* text, width, line height */
    0x00467F83u, 0x004019D0u, 0x004015D0u, 0x0040B560u, /* new, button, label, attach */
    0x00433120u, 0x00401AD0u, 0x00432BD0u,              /* popup, modal loop, destructor */
    0x0043F010u, 0x4E,                                  /* sound, the "?" sound */
    0x0048FA28u, 0x00476290u,                           /* "info_button.png", "?" */
    0x004437C0u,                                        /* the stock slot 3 */
};

static void __cdecl sol_vv2_draw(unsigned char *screen) {
    sol12_draw(&SOL_VV2, screen);
}

static void __cdecl sol_vv2_make(unsigned char *screen) {
    sol12_make_button(&SOL_VV2, screen);
}

static void __cdecl sol_vv2_help(unsigned char *screen) {
    sol12_help(&SOL_VV2, screen);
}

/* At SOL_VV2_SITE: esi = the Tech screen. */
static __declspec(naked) void sol_vv2_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol_vv2_draw
        add esp, 4
        popad
        popfd
        mov ecx, dword ptr [esi + 0x124]
        push SOL_VV2_RESUME
        ret
    }
}

/* At SOL_VV2_MAKE_SITE: esi = the Tech screen being built. */
static __declspec(naked) void sol_vv2_make_stub(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol_vv2_make
        add esp, 4
        popad
        popfd
        mov ecx, dword ptr [esi + 0x18]
        push 0xC9
        push SOL_VV2_MAKE_RESUME
        ret
    }
}

/* The screen's slot 3 (thiscall: message, id; ret 8): the "?" beside the counter, else the stock handler. */
static __declspec(naked) void sol_vv2_slot(void) {
    __asm {
        cmp dword ptr [esp + 4], 8
        jne stock
        cmp dword ptr [esp + 8], SOL12_BUTTON_ID
        jne stock
        pushad
        push ecx
        call sol_vv2_help
        add esp, 4
        popad
        xor eax, eax
        ret 8
    stock:
        push 0x004437C0
        ret
    }
}

static int sol_counter_install_vv2(void) {
    vvfp_site_write w[3];
    unsigned int slot = (unsigned int)(UINT_PTR)sol_vv2_slot;
    if (!sol12_routines_stock(&SOL_VV2, SOL12_SOUND_STOCK_VV2)) {
        return 0;
    }
    vvfp_site_branch(&w[0], SOL_VV2_SITE, sizeof SOL12_SITE_STOCK, SOL12_SITE_STOCK, 0xE9, (const void *)sol_vv2_stub);
    vvfp_site_branch(&w[1], SOL_VV2_MAKE_SITE, sizeof SOL_VV2_MAKE_STOCK, SOL_VV2_MAKE_STOCK, 0xE9,
                     (const void *)sol_vv2_make_stub);
    vvfp_site_bytes(&w[2], SOL_VV2_SLOT, sizeof SOL_VV2_SLOT_STOCK, SOL_VV2_SLOT_STOCK, (const unsigned char *)&slot);
    return vvfp_install_sites(w, 3);
}
