/* New Believers' Tech screen counter (the shared helper is in counter_vv3.inc). */

/* 0x44121C: pop esi / pop ebp / pop ebx / add esp, 0x28 / ret -- the Tech screen draw's (0x440F80) epilogue,
   after its bottom label's text is set (0x441217). */
static const unsigned char SOL5_SITE[7] = { 0x5E, 0x5D, 0x5B, 0x83, 0xC4, 0x28, 0xC3 };
static const unsigned char SOL5_RENDERER[6] = { 0xA1, 0xE8, 0xB0, 0x4D, 0x00, 0xC3 };      /* mov eax, [0x4DB0E8] */
static const unsigned char SOL5_RESOURCES[7] = { 0x6A, 0xFF, 0x68, 0x4B, 0x3B, 0x49, 0x00 };
static const unsigned char SOL5_DRAW[7] = { 0x8B, 0x09, 0xE9, 0x89, 0xFA, 0xFF, 0xFF };     /* jmp 0x409930 */
static const unsigned char SOL5_HEIGHT[6] = { 0x56, 0x8B, 0x71, 0x04, 0x85, 0xF6 };

/* The counter: the carved strip of the top frame left of the title's plank (the title, string 0x134, is centred
   at x 500, y 4; the screen is 1024 x 768), in the colour of the screen's bottom label (its global 0x4CD284). */
static const sol345_game SOL_VV5 = {
    0x44121Cu, 7, SOL5_SITE,
    0x4080C0u, SOL5_RENDERER,
    0x450D40u, SOL5_RESOURCES,
    0x409EA0u, SOL5_DRAW,
    0x4023E0u,
    0x4024B0u, SOL5_HEIGHT,
    0x4CD284u, 0,
    45, 370, 8,
    768,
};

static void __cdecl sol345_frame_vv5(void) {
    sol345_draw(&SOL_VV5);
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

static int sol_counter_install_vv5(void) {
    return sol345_install(&SOL_VV5, (void *)sol345_stub_vv5);
}
