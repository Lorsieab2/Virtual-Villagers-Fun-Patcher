/* New Believers' Tech screen counter and its "?" button (the shared helper is in counter_vv3.inc). */

/* 0x44121C: pop esi / pop ebp / pop ebx / add esp, 0x28 / ret -- the Tech screen draw's (0x440F80) epilogue,
   after its bottom label's text is set (0x441217). */
static const unsigned char SOL5_SITE[7] = { 0x5E, 0x5D, 0x5B, 0x83, 0xC4, 0x28, 0xC3 };
static const unsigned char SOL5_RENDERER[6] = { 0xA1, 0xE8, 0xB0, 0x4D, 0x00, 0xC3 };      /* mov eax, [0x4DB0E8] */
static const unsigned char SOL5_RESOURCES[7] = { 0x6A, 0xFF, 0x68, 0x4B, 0x3B, 0x49, 0x00 };
static const unsigned char SOL5_DRAW[7] = { 0x8B, 0x09, 0xE9, 0x89, 0xFA, 0xFF, 0xFF };     /* jmp 0x409930 */
static const unsigned char SOL5_HEIGHT[6] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6 };
/* 0x4407B7: mov dword ptr [esp+0x14], 1 -- in the constructor, after the title is attached (0x4407B2), before the
   technologies' loop (the Origins companion's own splice, 0x440A24, returns from the constructor itself). */
static const unsigned char SOL5_MAKE[8] = { 0xC7, 0x44, 0x24, 0x14, 0x01, 0x00, 0x00, 0x00 };

/* The counter: the carved strip of the top frame RIGHT of the title's plank (the title, string 0x134, is centred
   at x 500, y 4; the screen is 1024 x 768; left of it the Origins companion's Upgrades button sits in a patched build:
   seen live 2026-11-18), in the colour of the screen's bottom label (its global 0x4CD284, white on the dark frame). */
static const sol345_game SOL_VV5 = {
    0x44121Cu, 7, SOL5_SITE,
    0x4080C0u, SOL5_RENDERER,
    0x450D40u, SOL5_RESOURCES,
    0x409EA0u, SOL5_DRAW,
    0x4023E0u,
    0x4024B0u, SOL5_HEIGHT,
    0x4CD284u, 0,
    645, 990, 20,
    1024, 768,
    0x47BBDCu, 0x44FBB0u, 0x44FA30u, 0xCD, 37, 40,
    0x401BD0u, 0x4015D0u, 0x4CD2A0u, 0x497E94u, 0, 0x40C680u,
    0x41A760u, 0x401CF0u, 0x41A5F0u, 0x44C440u, 0x51F440u, 0x66,
    0x4407B7u, 8, SOL5_MAKE,
    0x49A218u, 0x4415F0u,
};

static void __cdecl sol345_frame_vv5(void) {
    sol345_draw(&SOL_VV5);
}

static void __cdecl sol345_make_vv5(unsigned char *screen) {
    sol345_make_button(&SOL_VV5, screen);
}

static void __cdecl sol345_help_vv5(unsigned char *screen) {
    sol345_help(&SOL_VV5, screen);
}

static __declspec(naked) void sol345_stub_vv5(void) {
    __asm {
        pushad
        call sol345_frame_vv5
        popad
        pop esi
        pop ebp
        pop ebx
        add esp, 0x28
        ret
    }
}

/* At 0x4407B7: esi = the Tech screen being built. */
static __declspec(naked) void sol345_make_stub_vv5(void) {
    __asm {
        pushfd
        pushad
        push esi
        call sol345_make_vv5
        add esp, 4
        popad
        popfd
        mov dword ptr [esp + 0x14], 1
        push 0x004407BF
        ret
    }
}

static __declspec(naked) void sol345_slot_vv5(void) {
    __asm {
        cmp dword ptr [esp + 4], 8
        jne stock
        cmp dword ptr [esp + 8], SOL345_BUTTON_ID
        jne stock
        pushad
        push ecx
        call sol345_help_vv5
        add esp, 4
        popad
        xor eax, eax
        ret 8
    stock:
        push 0x004415F0
        ret
    }
}

static int sol_counter_install_vv5(void) {
    return sol345_install(&SOL_VV5, (void *)sol345_stub_vv5, (void *)sol345_make_stub_vv5, (void *)sol345_slot_vv5);
}
