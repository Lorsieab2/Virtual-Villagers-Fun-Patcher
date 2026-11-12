/* scroll_popup.h -- the popups "VVFP Scrolling Popups.dll" gives scrollbars, one row per popup class per game.

   THE ENGINE (all five games share it; every address below was read from the stock executables with capstone and
   is pinned by tests/test_scrolling_popups.py):
     * software rendering on one drawing context `ctx` (the game's global holder [ctx_global] -> holder, [holder]
       = ctx); ctx+0x08 / +0x0C the screen's width and height, ctx+0x60..+0x6C the clip rectangle (left, top, right,
       bottom, exclusive) every glyph and picture blit honours (the clip test VV4 0x407EE0);
     * pictures: the game's image table (`image_lookup`, stdcall(id) ret 4 -> the entry, whose +4 is the picture's
       file name) and its frame-strip constructor (`frame_image`, thiscall(strip; file, columns, rows) ret 0xC,
       0x34 bytes, the class every button and panel picture is); a strip's +4 holds the loaded file whose first field
       is its SDL_Surface (w +8, h +0xC).  The companion builds its own strips of the scrollbar pictures, once, from
       the game's own files, exactly as the game builds its button pictures (they are never freed);
     * `frame_draw`  thiscall(holder; strip, x, y, frame, float alpha) ret 0x14 (the 9-slice panels' own draw);
     * text: `justify` thiscall(holder; text, x, y, width, colour, font, measure_only) ret 0x1C -> height (the
       popups' body text; words wrap, a word wider than the box overflows it on a line of its own); `nbyte`
       thiscall(ctx; text, bytes, x, y, measure_only, colour, font) ret 0x1C -> advance (its words' widths);
     * the event pump hands every mouse event to one dispatcher, thiscall(manager; 1 move / 2 down / 3 up, x, y)
       ret 0xC, from one call site (`mouse_site`), coordinates already in the game's 800 x 600 / 1024 x 768 space;
       it never reads SDL_MOUSEWHEEL (0x403), which an SDL event watch sees (y at +20).

   A WORD WIDER THAN THE BOX.  The justified paragraph cannot place a word wider than its width: it backs off to
   an empty line and tries the same word again, for ever (the game hangs; tests/test_scrolling_popups.py runs it).
   So the class's every call of it -- the constructor's measures (`measure_sites`) and the draw -- is given the
   width of its widest word when that is wider than the box, and the box scrolls sideways over it.

   A POPUP CLASS (sp_class) is a panel (9-slice, any height) whose body text is drawn by one `call justify`
   (`draw_site`, with esi = the popup + `text` pushed as the text) and sized by one `call sizer` in its constructor
   (`size_site`, thiscall(popup; panel picture, width, height) ret 0xC, the panel then centred on the screen and the
   popup's buttons placed from the panel's bottom).  `reserve` says how the class keeps room below its text for
   its buttons, so the box the text may fill is the panel's bottom less that room (stock layout: panel height =
   text top + text height + room).

   Adding a game or a class (A New Home, The Lost Children, the other popups of docs/reports/popups/INVENTORY.md)
   is adding a row; A New Home and The Lost Children have no scroll art of their own and will name picture files
   shipped beside the companion (sp_art.file) instead of image ids. */
#ifndef VVFP_SCROLL_POPUP_H
#define VVFP_SCROLL_POPUP_H

/* How a class keeps room for its buttons below its text. */
enum {
    SP_RESERVE_EVENT_DIALOG = 1   /* the island-event dialog: with two choices ([event]->vtable[4]() true) 4 x the
                                     height of the first choice button, else 5/2 x the OK button's height */
};

typedef struct sp_class {
    unsigned int draw_site;      /* `call justify` drawing the body text */
    unsigned int size_site;      /* `call sizer` in the constructor */
    unsigned int sizer;          /* its target */
    unsigned int size_push;      /* its `push edi` of the height: edi holds the height the constructor then centres
                                    the panel's contents by, so a capped height is put in edi too */
    unsigned char draw_before[6];/* the bytes just before draw_site: add esi, text / push esi / mov ecx, edi */
    unsigned int text;           /* the body text, inside the popup (char[]) */
    unsigned int panel;          /* the panel rectangle: left, top, right, bottom (+0, +4, +8, +0xC) */
    unsigned int box;            /* the text box: x, y, width (+0, +4, +8) */
    unsigned int font;           /* the font the body is drawn in */
    int reserve;                 /* SP_RESERVE_* */
    unsigned int event;          /* the event the dialog shows (its vtable[4]: two choices) */
    unsigned int choice_button;  /* the first choice button */
    unsigned int ok_button;      /* the OK button */
    unsigned int text_cap;       /* the text field's size (not raised here: the 2000-byte cap stays) */
    unsigned int measure_sites[4]; /* the constructor's `call justify` measuring its texts (measure only) */
} sp_class;

/* One picture: an image-table id of the game (or, for the games without the art, a file shipped beside the
   companion: not used yet), cut into `columns` frames side by side; `trim` is its drawn part (left, top, width,
   height; the rest is transparent), measured from the pictures (0: the whole frame). */
typedef struct sp_art {
    unsigned int id;
    int columns;
    const char *file;
    int trim[4];
} sp_art;

/* The message box (theMessageBoxDlg; all five games share its layout): a text control (a label sized to its text,
   every line of it, no wrapping) and one or two buttons below it.  Its constructor asks the sizer for (panel
   picture, w = the wider of the text + 0x3C and the buttons + 0x3C, h = the text + a button + 0x3C) from one call
   (`size_site`, after `push eax; mov ecx, esi`) and then places the text (panel_h - h) / 2 + 0x14 below the top,
   centred, and the buttons from the panel's bottom.  Its vtable (written by every constructor before the sizer)
   tells its text control from the others when that is drawn. */
typedef struct sp_msgbox {
    unsigned int vtable, size_site, sizer;
} sp_msgbox;

typedef struct sp_game {
    unsigned int justify, nbyte;
    unsigned int ctx_global;
    unsigned int image_lookup, frame_image;
    unsigned int frame_draw;
    unsigned int mouse_site, mouse_dispatch;
    int screen_w, screen_h;
    /* VerticalScrollTrack (18 x 220), VerticalScrollKnob (12 x 26), UpArrowButton / DownArrowButton (54 x 20, three
       18-pixel states), WideSlider2 (260 x 32), sliderhandle (16 x 32 / 23 x 30).  A New Home and The Lost Children
       have WideSlider2 and sliderhandle of their own (The Secret City's very pictures) but no vertical scrollbar:
       they borrow The Secret City's four, shipped as Images\vvfp_scroll_*.png (byte-identical copies; no game file
       is replaced) and loaded by name by the game's own picture loader. */
    sp_art up, down, track, knob, wide, handle;
    const sp_class *classes;
    int class_count;
    /* The text draw (holder; text, x, y, colour, font) ret 0x14 (`mov ecx, [ecx]; jmp` the core draw: '\n' starts a
       line) and the text control draw's one call of it (`ctl_site`, esi = the control, after `ctl_before`). */
    unsigned int text_draw, ctl_site;
    unsigned char ctl_before[4];
    sp_msgbox msgbox;
} sp_game;

/* The Secret City: the island-event dialog 0x4192F0. */
static const sp_class SP_VV3_CLASSES[] = {
    {0x418591u, 0x41983Fu, 0x40DDD0u, 0x41982Fu, {0x83, 0xC6, 0x58, 0x56, 0x8B, 0xCF}, 0x58u, 0x14u, 0x850u, 0x82Cu, SP_RESERVE_EVENT_DIALOG,
     0x50u, 0x85Cu, 0x864u, 2000u, {0x419611u, 0x419648u, 0x419681u, 0x4197F7u}},
};
/* The Tree of Life: the island-event dialog 0x417790. */
static const sp_class SP_VV4_CLASSES[] = {
    {0x416F4Cu, 0x417CEFu, 0x40DE20u, 0x417CDCu, {0x83, 0xC6, 0x58, 0x56, 0x8B, 0xCF}, 0x58u, 0x14u, 0x850u, 0x82Cu, SP_RESERVE_EVENT_DIALOG,
     0x50u, 0x85Cu, 0x864u, 2000u, {0x417AC7u, 0x417B00u, 0x417B3Bu, 0x417CA4u}},
};
/* New Believers: the island-event dialog 0x418020. */
static const sp_class SP_VV5_CLASSES[] = {
    {0x4176E9u, 0x418573u, 0x40E310u, 0x418563u, {0x83, 0xC6, 0x58, 0x56, 0x8B, 0xCF}, 0x58u, 0x14u, 0x850u, 0x82Cu, SP_RESERVE_EVENT_DIALOG,
     0x50u, 0x85Cu, 0x864u, 2000u, {0x41834Eu, 0x418387u, 0x4183C2u, 0x41852Bu}},
};

/* The four borrowed pictures (A New Home, The Lost Children). */
#define SP_BORROWED_ART                                                                                           \
    {0, 3, "vvfp_scroll_up.png"}, {0, 3, "vvfp_scroll_down.png"}, {0, 1, "vvfp_scroll_track.png"},               \
    {0, 1, "vvfp_scroll_knob.png"}

static const sp_game SP_GAMES[6] = {
    {0},
    {0, 0, 0x48B2E8u, 0, 0x40A070u, 0x4093E0u, 0x403C6Eu, 0x401FE0u, 800, 600,
     SP_BORROWED_ART, {0, 1, "WideSlider2.png"}, {0, 1, "sliderhandle.png", {0, 3, 12, 27}},
     NULL, 0,
     0x4094B0u, 0x40C197u, {0x8B, 0x4C, 0x24, 0x24}, {0x459AB0u, 0x427378u, 0x40C760u}},              /* vv1 */
    {0, 0, 0x499BC8u, 0, 0x40A270u, 0x4095D0u, 0x403EFEu, 0x402070u, 800, 600,
     SP_BORROWED_ART, {0, 1, "WideSlider2.png"}, {0, 1, "sliderhandle.png", {0, 3, 12, 27}},
     NULL, 0,
     0x4096A0u, 0x40CB77u, {0x8B, 0x4C, 0x24, 0x24}, {0x476DC4u, 0x432EE8u, 0x40D140u}},              /* vv2 */
    {0x40A0C0u, 0x409AD0u, 0x4B34A8u, 0x42E6F0u, 0x40AF10u, 0x409F80u, 0x40451Eu, 0x4020A0u, 800, 600,
     {0x1B, 3, 0}, {0x1C, 3, 0}, {0x1D, 1, 0}, {0x1E, 1, 0}, {0x19, 1, 0}, {0x1A, 1, 0, {0, 3, 12, 27}},
     SP_VV3_CLASSES, (int)(sizeof SP_VV3_CLASSES / sizeof SP_VV3_CLASSES[0]),
     0x40A060u, 0x40D807u, {0x8B, 0x4C, 0x24, 0x24}, {0x47F3ACu, 0x41C53Fu, 0x40DDD0u}},              /* vv3 */
    {0x409C30u, 0x4094F0u, 0x4CB928u, 0x44C8A0u, 0x40AB10u, 0x409A00u, 0x404B02u, 0x402320u, 800, 600,
     {0xA3, 3, 0}, {0xA4, 3, 0}, {0xA5, 1, 0}, {0xA6, 1, 0}, {0xA1, 1, 0, {1, 1, 258, 30}},
     {0xA2, 1, 0, {3, 5, 16, 21}},
     SP_VV4_CLASSES, (int)(sizeof SP_VV4_CLASSES / sizeof SP_VV4_CLASSES[0]),
     0x409BD0u, 0x40CFC9u, {0x57, 0x51, 0x8B, 0xCD}, {0x48D3C4u, 0x419BE0u, 0x40DE20u}},              /* vv4 */
    {0x409F00u, 0x409720u, 0x4DB0E8u, 0x44F760u, 0x40B010u, 0x409C30u, 0x404A92u, 0x4022D0u, 1024, 768,
     {0x81, 3, 0}, {0x82, 3, 0}, {0x83, 1, 0}, {0x84, 1, 0}, {0x7F, 1, 0, {1, 1, 258, 30}},
     {0x80, 1, 0, {3, 5, 16, 21}},
     SP_VV5_CLASSES, (int)(sizeof SP_VV5_CLASSES / sizeof SP_VV5_CLASSES[0]),
     0x409EA0u, 0x40D4B9u, {0x57, 0x51, 0x8B, 0xCD}, {0x4985D4u, 0x41A47Bu, 0x40E310u}},              /* vv5 */
};

#endif /* VVFP_SCROLL_POPUP_H */
