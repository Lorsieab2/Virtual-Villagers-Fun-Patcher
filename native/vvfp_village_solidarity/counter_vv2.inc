/* The Lost Children's Tech screen counter: drawn by counter_vv1.inc's sol12_draw (the two games' Tech screens are
   laid out alike: the same tech_bg banner, the same screen fields, the same widgets).

   THE SCREEN.  The Tech screen's draw is 0x441830 (thiscall, the screen in ecx): tech_bg.jpg at (0, 0), then the six
   technologies' cells at the screen's fade alpha ([screen+0x20]) while it fades in ([screen+0x1C] <= 3); both paths
   meet at 0x441D2B, where its seven text widgets are drawn ([screen+0x124] .. [screen+0x13C], vtable slot 0x18):
   +0x124 the bottom strip's label at (0x24C, 0x23C) in the resource object's ([screen+0x18]) first font.

   THE SPOT.  The empty tan banner across the top (about x 45..745, y 3..33): centred at x 400, on y 18.

   THE TEXT.  The game's centred text routine 0x4096B0 (thiscall on the graphics wrapper [screen+8]: text, centre
   x, y, colour, font; ret 0x14) in the bottom label's font, white, at the fade alpha; measured with 0x4021F0 (font;
   text, scale; ret 8), one line 0x402190(font; NULL) high; too wide: wrapped / cut as in counter_vv1.inc.

   THE SPLICE.  0x441D2B: "mov ecx, [esi+0x124]" (8B 8E 24 01 00 00), reached by both paths (0x441AB8 jle, 0x441D0D
   jl and the fall-through); the stub draws the counter, runs the six stock bytes and goes on at 0x441D31. */

#define SOL_VV2_SITE 0x00441D2Bu            /* mov ecx, [esi+0x124] (8B 8E 24 01 00 00) */
#define SOL_VV2_RESUME 0x00441D31u
static const sol12_game SOL_VV2 = { 0x004096B0u, 0x004021F0u, 0x00402190u };

static void __cdecl sol_vv2_draw(unsigned char *screen) {
    sol12_draw(&SOL_VV2, screen);
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

static int sol_counter_install_vv2(void) {
    vvfp_site_write w[1];
    if (!sol12_routines_stock(&SOL_VV2)) {
        return 0;
    }
    vvfp_site_branch(&w[0], SOL_VV2_SITE, sizeof SOL12_SITE_STOCK, SOL12_SITE_STOCK, 0xE9, (const void *)sol_vv2_stub);
    return vvfp_install_sites(w, 1);
}
