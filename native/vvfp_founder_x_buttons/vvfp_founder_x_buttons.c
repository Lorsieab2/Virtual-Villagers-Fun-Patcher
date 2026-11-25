/* VVFP Founder X Buttons -- "X Buttons to Remove Chosen Founders", The Tree of Life and New Believers.

   The owner (2026-11-24): "add patches to vv4 and vv5 when selecting villagers for the expedition. I want to add X
   buttons beside the 5 slots so we can choose new candidates."  And: clicking X removes that chosen villager -- gone,
   like a Reject; the slot opens; the other chosen villagers stay (they move down to fill it); the player keeps
   picking new candidates until five are chosen.  The art is the game's own: the blank three-frame stone button (The
   Tree of Life's image 0xEB tech_info_btn.png, New Believers' 0xCD btn_tech_question.png, 37 x 40 a frame), labelled
   "X" by the game's own button-label call, as Village Solidarity labels its "?".

   THE STOCK SCREEN ("Select 5 villagers", the manager's scene 3; VV4 / VV5).  One object, kept in [0x4D8DA4] /
   [0x51E1CC] by its getter (0x43B9D0 / 0x43E3C0), vtable 0x48EB38 / 0x49A074.  Its fields: +8 the record index of
   the candidate on show; +0x18 the number chosen; +0x1C..+0x2C the five chosen record indexes; +0x30 the Reject
   button.  Its command handler (vtable slot 3, 0x43BC00 / 0x43E600) gets every click as (8, id): Select is id 1,
   Reject id 2 (the Enter key sends (8, 1) through the same slot, 0x43AAF0 / 0x43D3E0).  Select stores +8 as chosen
   [+0x18] and adds one; Reject just shows the next candidate (0x43BA80 / 0x43E470), whose generator (0x43B830 /
   0x43E220) clears the present byte (+0x1CC4 / +0x1CD4) of record [+0x18], makes the new candidate with the game's
   allocator (the first record whose present byte is 0) and returns [+0x18] -- the stock screen counts on the
   candidate's record being the one numbered as many as are chosen.  At the fifth Select, with the manager's flag
   (+0x171C4 / +0x17E38) 0, Select is relabelled "Done" (string 0xE1 / 0xDA), Reject is taken off the screen and the
   fifth pick stays on show; the next Select starts the island (scene 15).  With the flag set, the island starts at
   once.

   WHAT THIS COMPANION DOES.
     * Five buttons, ids FX_ID + 0..4, made like the screen's own (the button constructor with the picture from the
       game's image manager and the screen as parent, the label "X" in the colours of Select's and Reject's labels),
       stand at the right end of each filled slot's name plank, just above it.  They are on the screen exactly while
       their slot is filled and a pick can still change: never once the island has started.  They are put on and
       taken off the screen (the screen's own add / remove child calls, as it does Reject) only in the screen's draw
       (vtable slot 6), never inside a click.
     * The screen's command handler (slot 3) is replaced: an X click removes that chosen villager -- the record's
       present byte cleared, exactly what a Reject does to a candidate -- moves the later chosen ones down one place
       and counts one fewer chosen, with the game's own click sound (tap.ogg).  The candidate on show stays.  In the
       Done state the X also gives Select back its label (string 0x54 / 0x49, as the screen's show does), puts
       Reject back (in the next draw) and shows a new candidate (the screen's own 0x43BA80 / 0x43E470).  Every other
       click goes on to the stock handler.
     * The generator's entry is spliced: before the stock code runs, the candidate on show is freed when it is not a
       chosen villager (what the stock code does to record [+0x18]), and while the stock code runs the screen's count
       reads as the lowest free record -- where the game's allocator puts the new candidate -- so the stock code frees,
       fills and returns that record; the real count is put back after.  With no X used the lowest free record IS the
       count, so nothing changes: the stock screen, byte for byte.
   Nothing else is touched: no file, no save, no text but "X".  The founders are whatever records are present when
   the island starts (the start-game step 0x41FEF0 / 0x4259D0 walks every record by its present byte), so a founder
   in any record is a founder.  Cause of Death marks founder candidates by record when they are made and drops, at the
   first real save, every one whose present byte is 0 (arrival_decide): a removed villager is gone as a rejected
   candidate is, never a disappearance (no stock removal site is hooked here, cod_gone.inc).  Saves while this screen
   is open are not the village (Cause of Death, Population Export and Original Look skip them).

   POPULATION.  The villager table is read from the generator's own `mov ecx, <table>` (the 256 Villagers fork moves
   it), records are reached only through the game's record getter (0..149, or 0..255 in the fork), and the free
   record is searched until the getter says there is none: 150 and 256 alike.

   SAFETY.  The three sites (the generator's entry, slots 3 and 6 of the screen's vtable) are written only when each
   holds its stock bytes and every routine called holds its own (all or nothing, native/shared/install_sites.h).
   The work runs under structured exception handling (a fault: that step is skipped, the stock code still runs).
   Started by VVFP More Companions.dll (the third word, native/shared/startup_companions_3.h).  No debug output. */
#include <windows.h>
#include "../shared/install_sites.h"

#define FX_SLOTS 5
#define FX_ID 0x5858                    /* the X of slot k is FX_ID + k (stock ids on this screen are 1 and 2) */
#define FX_CANDIDATE 0x08               /* the screen: the candidate's record index */
#define FX_COUNT 0x18                   /* the number chosen */
#define FX_CHOSEN 0x1C                  /* the five chosen record indexes */
#define FX_REJECT 0x30                  /* the Reject button */
#define FX_SELECT_ID 1
#define FX_REJECT_ID 2
#define FX_COMMAND 8                    /* a button's click */
#define FX_RECORDS_CAP 4096             /* never more records than this are looked at */
#define FX_PLANK_HALF 67                /* a name plank is 135 pixels wide, centred on its slot */
#define FX_ABOVE_PLANK 1                /* pixels between the X and the plank's top */

typedef struct {
    int game;
    unsigned int vtable;                /* the screen's vtable */
    unsigned int handler;               /* slot 3's stock value: thiscall(screen; command, id) ret 8 */
    unsigned int draw;                  /* slot 6's stock value: thiscall(screen) */
    unsigned int generator;             /* the next candidate's maker, its entry spliced */
    unsigned int generator_back;        /* after its first two instructions */
    unsigned int returns_count;         /* its two returns of [screen+0x18] (checked) */
    unsigned int returns_count_2;
    unsigned int table_mov;             /* `mov ecx, <villager table>` inside the generator */
    unsigned int record_get;            /* thiscall(table; index) ret 4 -> the record, or 0 */
    int present;                        /* the record's present byte */
    unsigned int next_candidate;        /* thiscall(screen): the next candidate, its name box filled */
    unsigned int op_new;                /* cdecl(size) */
    unsigned int images_get;            /* cdecl: the image manager */
    unsigned int image_get;             /* thiscall(manager; id) ret 4 -> the picture */
    int image_id;
    int button_w, button_h;             /* the picture's frame */
    unsigned int button_new;            /* thiscall(button; id, picture, x, y, parent, 0) ret 0x18 */
    unsigned int button_label;          /* thiscall(button; text, colour, hover, pressed, 0) ret 0x14 */
    unsigned int label_text;            /* thiscall(button; text, 0) ret 8 (the screen's show relabels Select so) */
    unsigned int label_colour;          /* the global Select's and Reject's labels are coloured from */
    unsigned int add_child;             /* thiscall(screen; child) ret 4 */
    unsigned int find_child;            /* thiscall(screen; id) ret 4 -> the child, or 0 */
    unsigned int remove_child;          /* thiscall(screen; child) ret 4 */
    unsigned int resources_get;         /* cdecl: the resource singleton */
    unsigned int string_get;            /* thiscall(resources; id) ret 4 -> the text */
    int select_string;                  /* "Select" */
    unsigned int sound;                 /* thiscall(sounds; id) ret 4 */
    unsigned int sounds;
    int sound_id;                       /* tap.ogg */
    unsigned int slots_site;            /* the draw's five slot x's (checked) */
    int slot_x[FX_SLOTS];
    int plank_top;
} fx_game;

typedef void *(__fastcall *fx_record_fn)(void *table, void *edx, int index);
typedef int (__fastcall *fx_generate_fn)(unsigned char *screen);
typedef char (__fastcall *fx_handler_fn)(unsigned char *screen, void *edx, int command, int id);
typedef void (__fastcall *fx_draw_fn)(unsigned char *screen);
typedef void (__fastcall *fx_next_fn)(unsigned char *screen);
typedef void *(__cdecl *fx_new_fn)(unsigned int size);
typedef void *(__cdecl *fx_get_fn)(void);
typedef void *(__fastcall *fx_image_fn)(void *manager, void *edx, int id);
typedef void *(__fastcall *fx_button_fn)(void *button, void *edx, int id, void *picture, int x, int y, void *parent,
                                         int zero);
typedef void (__fastcall *fx_label_fn)(void *button, void *edx, const char *text, unsigned int colour,
                                       unsigned int hover, unsigned int pressed, int zero);
typedef void (__fastcall *fx_text_fn)(void *button, void *edx, const char *text, int zero);
typedef void (__fastcall *fx_child_fn)(void *screen, void *edx, void *child);
typedef void *(__fastcall *fx_find_fn)(void *screen, void *edx, int id);
typedef const char *(__fastcall *fx_string_fn)(void *resources, void *edx, int id);
typedef void (__fastcall *fx_sound_fn)(void *sounds, void *edx, int id);

static const char FX_LABEL[] = "X";

static int g_installed;
static unsigned char *g_screen;         /* the screen the buttons belong to */
static void *g_button[FX_SLOTS];
static int g_made;                      /* 1 the buttons are made; -1 making them failed (never tried again) */
static int g_restore_reject;            /* an X in the Done state: Reject goes back on in the next draw */
static int g_real_count = -1;           /* the count the generator's splice put aside, or -1 */

/* ---- the game's records -------------------------------------------------------------------------------------- */

static void *fx_table(const fx_game *g) {
    return *(void *const *)(UINT_PTR)(g->table_mov + 1);
}

static unsigned char *fx_record(const fx_game *g, int index) {
    if (index < 0 || index >= FX_RECORDS_CAP) {
        return NULL;
    }
    return (unsigned char *)((fx_record_fn)(UINT_PTR)g->record_get)(fx_table(g), NULL, index);
}

static int fx_count(const unsigned char *screen) {
    return *(const int *)(screen + FX_COUNT);
}

static int *fx_chosen(unsigned char *screen) {
    return (int *)(screen + FX_CHOSEN);
}

/* Whether record `index` is one of the `count` chosen. */
static int fx_is_chosen(unsigned char *screen, int count, int index) {
    const int *ids = fx_chosen(screen);
    int k;
    for (k = 0; k < count && k < FX_SLOTS; ++k) {
        if (ids[k] == index) {
            return 1;
        }
    }
    return 0;
}

/* The lowest record whose present byte is 0 -- where the game's allocator puts the next villager -- or -1. */
static int fx_lowest_free(const fx_game *g) {
    int i;
    for (i = 0; i < FX_RECORDS_CAP; ++i) {
        const unsigned char *record = fx_record(g, i);
        if (record == NULL) {
            return -1;
        }
        if (record[g->present] == 0) {
            return i;
        }
    }
    return -1;
}

/* ---- the generator -------------------------------------------------------------------------------------------- */

/* Before the stock code: the candidate on show freed unless chosen; the count read as the lowest free record. */
static void fx_generate_before(const fx_game *g, unsigned char *screen) {
    int count = fx_count(screen), candidate = *(const int *)(screen + FX_CANDIDATE), lowest;
    g_real_count = -1;
    if (count < 0 || count > FX_SLOTS) {
        return;
    }
    if (candidate >= 0 && !fx_is_chosen(screen, count, candidate)) {
        unsigned char *record = fx_record(g, candidate);
        if (record != NULL) {
            record[g->present] = 0;     /* what the stock code does to record [+0x18]: the candidate goes */
        }
    }
    lowest = fx_lowest_free(g);
    if (lowest >= 0 && lowest != count) {
        g_real_count = count;
        *(int *)(screen + FX_COUNT) = lowest;
    }
}

static void fx_generate_after(unsigned char *screen) {
    if (g_real_count >= 0) {
        *(int *)(screen + FX_COUNT) = g_real_count;
        g_real_count = -1;
    }
}

/* The splice's work: `stock` runs the stock generator (thiscall on the screen) and returns its record index. */
static int fx_generate(const fx_game *g, unsigned char *screen, fx_generate_fn stock) {
    int made;
    __try {
        fx_generate_before(g, screen);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        g_real_count = -1;
    }
    made = stock(screen);
    __try {
        fx_generate_after(screen);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return made;
}

/* ---- the buttons ---------------------------------------------------------------------------------------------- */

static void *fx_find(const fx_game *g, unsigned char *screen, int id) {
    return ((fx_find_fn)(UINT_PTR)g->find_child)(screen, NULL, id);
}

static void fx_add(const fx_game *g, unsigned char *screen, void *child) {
    ((fx_child_fn)(UINT_PTR)g->add_child)(screen, NULL, child);
}

static void fx_remove_child(const fx_game *g, unsigned char *screen, void *child) {
    ((fx_child_fn)(UINT_PTR)g->remove_child)(screen, NULL, child);
}

/* Slot k's X: the right end of its name plank, just above it. */
static void fx_spot(const fx_game *g, int k, int *x, int *y) {
    *x = g->slot_x[k] + FX_PLANK_HALF - g->button_w;
    *y = g->plank_top - FX_ABOVE_PLANK - g->button_h;
}

/* The five X buttons, made as the screen makes Select and Reject (none put on the screen yet). */
static void fx_make(const fx_game *g, unsigned char *screen) {
    unsigned int colour = *(const unsigned int *)(UINT_PTR)g->label_colour;
    int k;
    g_made = -1;
    for (k = 0; k < FX_SLOTS; ++k) {
        void *button = ((fx_new_fn)(UINT_PTR)g->op_new)(0x14);
        void *manager = ((fx_get_fn)(UINT_PTR)g->images_get)();
        void *picture;
        int x, y;
        if (button == NULL || manager == NULL) {
            return;
        }
        picture = ((fx_image_fn)(UINT_PTR)g->image_get)(manager, NULL, g->image_id);
        fx_spot(g, k, &x, &y);
        button = ((fx_button_fn)(UINT_PTR)g->button_new)(button, NULL, FX_ID + k, picture, x, y, screen, 0);
        if (button == NULL) {
            return;
        }
        ((fx_label_fn)(UINT_PTR)g->button_label)(button, NULL, FX_LABEL, colour, colour, colour, 0);
        g_button[k] = button;
    }
    g_made = 1;
}

/* How many X buttons belong on the screen: one per chosen villager while a pick can still change; none once the
   island has started (five chosen with Reject still on: the manager's flag started it at the fifth Select). */
static int fx_wanted(const fx_game *g, unsigned char *screen) {
    int count = fx_count(screen);
    if (count <= 0 || count > FX_SLOTS) {
        return 0;
    }
    if (count == FX_SLOTS && fx_find(g, screen, FX_REJECT_ID) != NULL) {
        return 0;
    }
    return count;
}

/* In the screen's draw (before the stock draw, so before its children are drawn): Reject back after an X in the
   Done state, and each X on the screen exactly while its slot is filled. */
static void fx_sync(const fx_game *g, unsigned char *screen) {
    int wanted, k;
    if (screen != g_screen) {
        g_screen = screen;
        g_made = 0;
        g_restore_reject = 0;
        memset(g_button, 0, sizeof g_button);
    }
    if (g_restore_reject) {
        void *reject = *(void **)(screen + FX_REJECT);
        g_restore_reject = 0;
        if (reject != NULL && fx_find(g, screen, FX_REJECT_ID) == NULL) {
            fx_add(g, screen, reject);
        }
    }
    wanted = fx_wanted(g, screen);
    if (wanted > 0 && g_made == 0) {
        fx_make(g, screen);
    }
    if (g_made != 1) {
        return;
    }
    for (k = 0; k < FX_SLOTS; ++k) {
        int shown = fx_find(g, screen, FX_ID + k) != NULL;
        if (k < wanted && !shown) {
            fx_add(g, screen, g_button[k]);
        } else if (k >= wanted && shown) {
            fx_remove_child(g, screen, g_button[k]);
        }
    }
}

/* Slot k's X clicked: that chosen villager goes, as a rejected candidate does; the later ones move down. */
static void fx_take_out(const fx_game *g, unsigned char *screen, int k) {
    int count = fx_count(screen), *ids = fx_chosen(screen), done, i;
    unsigned char *record;
    if (count < 1 || count > FX_SLOTS || k < 0 || k >= count) {
        return;                         /* an empty slot (its X is coming off): nothing */
    }
    done = count == FX_SLOTS && fx_find(g, screen, FX_REJECT_ID) == NULL;
    if (count == FX_SLOTS && !done) {
        return;                         /* the island has started */
    }
    ((fx_sound_fn)(UINT_PTR)g->sound)((void *)(UINT_PTR)g->sounds, NULL, g->sound_id);
    record = fx_record(g, ids[k]);
    if (record != NULL) {
        record[g->present] = 0;
    }
    for (i = k; i + 1 < count; ++i) {
        ids[i] = ids[i + 1];
    }
    *(int *)(screen + FX_COUNT) = count - 1;
    if (done) {
        /* Out of the Done state: Select's own label back (as the screen's show gives it), Reject back in the next
           draw, and a new candidate (the fifth pick on show is still chosen, or was the one taken out). */
        void *select = fx_find(g, screen, FX_SELECT_ID);
        g_restore_reject = 1;
        if (select != NULL) {
            void *resources = ((fx_get_fn)(UINT_PTR)g->resources_get)();
            const char *text = resources != NULL
                ? ((fx_string_fn)(UINT_PTR)g->string_get)(resources, NULL, g->select_string) : NULL;
            if (text != NULL) {
                ((fx_text_fn)(UINT_PTR)g->label_text)(select, NULL, text, 0);
            }
        }
        ((fx_next_fn)(UINT_PTR)g->next_candidate)(screen);
    }
}

/* The command handler's work: 1 when the click was an X (handled here), else 0 (the stock handler's). */
static int fx_command(const fx_game *g, unsigned char *screen, int command, int id) {
    if (command != FX_COMMAND || id < FX_ID || id >= FX_ID + FX_SLOTS) {
        return 0;
    }
    __try {
        fx_take_out(g, screen, id - FX_ID);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return 1;
}

static void fx_draw_work(const fx_game *g, unsigned char *screen) {
    __try {
        fx_sync(g, screen);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* ---- The Tree of Life ----------------------------------------------------------------------------------------- */

static const fx_game FX_VV4 = {
    4,
    0x48EB38u, 0x43BC00u, 0x43B6A0u,
    0x43B830u, 0x43B836u, 0x43B9A9u, 0x43B9B4u, 0x43B83Bu,
    0x466040u, 0x1CC4,
    0x43BA80u,
    0x470C5Cu, 0x44CCF0u, 0x44CB70u, 0xEB, 37, 40,
    0x401C20u, 0x401600u, 0x4015F0u, 0x4BE894u,
    0x40C190u, 0x40C1E0u, 0x40C210u,
    0x44DA20u, 0x44D3D0u, 0x54,
    0x448E10u, 0x4DA020u, 0x64,
    0x43B78Cu, { 97, 245, 398, 546, 698 },
    140,
};

static int __fastcall fx_stock_generator_vv4(unsigned char *screen);
static int __stdcall fx_generate_vv4(unsigned char *screen) {
    return fx_generate(&FX_VV4, screen, fx_stock_generator_vv4);
}

/* The generator's first two instructions, then on in the stock code (its `ret` returns to fx_generate). */
static __declspec(naked) int __fastcall fx_stock_generator_vv4(unsigned char *screen) {
    (void)screen;
    __asm {
        sub esp, 0x10
        mov eax, dword ptr [ecx + 0x18]
        push 0x0043B836
        ret
    }
}

/* In place of the generator's entry: ecx the screen; returns the record index in eax, as the stock code does. */
static __declspec(naked) void fx_generator_stub_vv4(void) {
    __asm {
        push ecx
        call fx_generate_vv4
        ret
    }
}

static char __fastcall fx_handler_vv4(unsigned char *screen, void *edx, int command, int id) {
    (void)edx;
    if (fx_command(&FX_VV4, screen, command, id)) {
        return 1;
    }
    return ((fx_handler_fn)(UINT_PTR)FX_VV4.handler)(screen, NULL, command, id);
}

static void __fastcall fx_draw_vv4(unsigned char *screen) {
    fx_draw_work(&FX_VV4, screen);
    ((fx_draw_fn)(UINT_PTR)FX_VV4.draw)(screen);
}

/* The draw's slot x's: mov dword ptr [esp+0x10..0x20], 97 / 245 / 398 / 546 / 698 (0x43B78C). */
static const unsigned char FX4_SLOTS[40] = {
    0xC7, 0x44, 0x24, 0x10, 0x61, 0x00, 0x00, 0x00, 0xC7, 0x44, 0x24, 0x14, 0xF5, 0x00, 0x00, 0x00,
    0xC7, 0x44, 0x24, 0x18, 0x8E, 0x01, 0x00, 0x00, 0xC7, 0x44, 0x24, 0x1C, 0x22, 0x02, 0x00, 0x00,
    0xC7, 0x44, 0x24, 0x20, 0xBA, 0x02, 0x00, 0x00,
};
/* 0x43B9A9: mov eax, [ebx+0x18] (pregnant path) / 0x43B9B4: mov eax, [esp+0x14] / mov eax, [eax+0x18]. */
static const unsigned char FX4_RETURN_1[3] = { 0x8B, 0x43, 0x18 };
static const unsigned char FX4_RETURN_2[7] = { 0x8B, 0x44, 0x24, 0x14, 0x8B, 0x40, 0x18 };

/* ---- New Believers -------------------------------------------------------------------------------------------- */

static const fx_game FX_VV5 = {
    5,
    0x49A074u, 0x43E600u, 0x43E030u,
    0x43E220u, 0x43E226u, 0x43E397u, 0x43E3A2u, 0x43E22Bu,
    0x46F950u, 0x1CD4,
    0x43E470u,
    0x47BBDCu, 0x44FBB0u, 0x44FA30u, 0xCD, 37, 40,
    0x401BD0u, 0x4015D0u, 0x4015C0u, 0x4CCBCCu,
    0x40C680u, 0x40C6D0u, 0x40C700u,
    0x450D40u, 0x4506D0u, 0x49,
    0x44C440u, 0x51F440u, 0x66,
    0x43E174u, { 202, 350, 503, 651, 803 },
    215,
};

static int __fastcall fx_stock_generator_vv5(unsigned char *screen);
static int __stdcall fx_generate_vv5(unsigned char *screen) {
    return fx_generate(&FX_VV5, screen, fx_stock_generator_vv5);
}

static __declspec(naked) int __fastcall fx_stock_generator_vv5(unsigned char *screen) {
    (void)screen;
    __asm {
        sub esp, 0x10
        mov eax, dword ptr [ecx + 0x18]
        push 0x0043E226
        ret
    }
}

static __declspec(naked) void fx_generator_stub_vv5(void) {
    __asm {
        push ecx
        call fx_generate_vv5
        ret
    }
}

static char __fastcall fx_handler_vv5(unsigned char *screen, void *edx, int command, int id) {
    (void)edx;
    if (fx_command(&FX_VV5, screen, command, id)) {
        return 1;
    }
    return ((fx_handler_fn)(UINT_PTR)FX_VV5.handler)(screen, NULL, command, id);
}

static void __fastcall fx_draw_vv5(unsigned char *screen) {
    fx_draw_work(&FX_VV5, screen);
    ((fx_draw_fn)(UINT_PTR)FX_VV5.draw)(screen);
}

/* 0x43E174: mov dword ptr [esp+0x18..0x28], 202 / 350 / 503 / 651 / 803. */
static const unsigned char FX5_SLOTS[40] = {
    0xC7, 0x44, 0x24, 0x18, 0xCA, 0x00, 0x00, 0x00, 0xC7, 0x44, 0x24, 0x1C, 0x5E, 0x01, 0x00, 0x00,
    0xC7, 0x44, 0x24, 0x20, 0xF7, 0x01, 0x00, 0x00, 0xC7, 0x44, 0x24, 0x24, 0x8B, 0x02, 0x00, 0x00,
    0xC7, 0x44, 0x24, 0x28, 0x23, 0x03, 0x00, 0x00,
};
static const unsigned char FX5_RETURN_1[3] = { 0x8B, 0x43, 0x18 };
static const unsigned char FX5_RETURN_2[7] = { 0x8B, 0x44, 0x24, 0x14, 0x8B, 0x40, 0x18 };

/* ---- install -------------------------------------------------------------------------------------------------- */

/* sub esp, 10h / mov eax, [ecx+18h]: the generator's entry (both games). */
static const unsigned char FX_GENERATOR[6] = { 0x83, 0xEC, 0x10, 0x8B, 0x41, 0x18 };
static const unsigned char FX_MOV_ECX[1] = { 0xB9 };
static const unsigned char FX_RECORD_GET[5] = { 0x8B, 0x44, 0x24, 0x04, 0x3D };        /* cmp eax, <last index> */
static const unsigned char FX_NEXT[6] = { 0x81, 0xEC, 0x04, 0x01, 0x00, 0x00 };
static const unsigned char FX_SEH[3] = { 0x6A, 0xFF, 0x68 };                          /* push -1; push <handler> */
static const unsigned char FX_ADD_CHILD[4] = { 0x56, 0x57, 0x6A, 0x08 };
static const unsigned char FX_FIND_CHILD[6] = { 0x8B, 0x41, 0x04, 0x8B, 0x40, 0x18 };
static const unsigned char FX_REMOVE_CHILD[6] = { 0x8B, 0x49, 0x04, 0x8B, 0x41, 0x18 };
static const unsigned char FX_LABEL_SET[7] = { 0x8B, 0x41, 0x10, 0x8B, 0x54, 0x24, 0x10 };
static const unsigned char FX_LABEL_TEXT[4] = { 0x8B, 0x49, 0x10, 0xE9 };
static const unsigned char FX_STRING_GET[5] = { 0x8B, 0x44, 0x24, 0x04, 0x85 };

static int fx_install(const fx_game *g, const unsigned char *slots, const unsigned char *return_1,
                      const unsigned char *return_2, void *generator_stub, void *handler, void *draw) {
    vvfp_site_write w[3];
    unsigned int new_handler = (unsigned int)(UINT_PTR)handler, new_draw = (unsigned int)(UINT_PTR)draw;
    unsigned char stock_handler[4], stock_draw[4];
    memcpy(stock_handler, &g->handler, 4);
    memcpy(stock_draw, &g->draw, 4);
    if (!vvfp_site_holds(g->table_mov, FX_MOV_ECX, 1)
        || !vvfp_site_holds(g->returns_count, return_1, 3)
        || !vvfp_site_holds(g->returns_count_2, return_2, 7)
        || !vvfp_site_holds(g->record_get, FX_RECORD_GET, 5)
        || !vvfp_site_holds(g->next_candidate, FX_NEXT, 6)
        || !vvfp_site_holds(g->button_new, FX_SEH, 3)
        || !vvfp_site_holds(g->images_get, FX_SEH, 3)
        || !vvfp_site_holds(g->resources_get, FX_SEH, 3)
        || !vvfp_site_holds(g->add_child, FX_ADD_CHILD, 4)
        || !vvfp_site_holds(g->find_child, FX_FIND_CHILD, 6)
        || !vvfp_site_holds(g->remove_child, FX_REMOVE_CHILD, 6)
        || !vvfp_site_holds(g->button_label, FX_LABEL_SET, 7)
        || !vvfp_site_holds(g->label_text, FX_LABEL_TEXT, 4)
        || !vvfp_site_holds(g->string_get, FX_STRING_GET, 5)
        || !vvfp_site_holds(g->slots_site, slots, 40)) {
        return 0;
    }
    vvfp_site_branch(&w[0], g->generator, (int)sizeof FX_GENERATOR, FX_GENERATOR, 0xE9, generator_stub);
    vvfp_site_bytes(&w[1], g->vtable + 3 * 4, 4, stock_handler, (const unsigned char *)&new_handler);
    vvfp_site_bytes(&w[2], g->vtable + 6 * 4, 4, stock_draw, (const unsigned char *)&new_draw);
    return vvfp_install_sites(w, 3);
}

/* 1 when the sites are installed (the tests' emulation), else 0. */
int __stdcall VvfpFounderXInstalled(void) {
    return g_installed;
}

/* Called once by VVFP More Companions.dll before WinMain, on the game's own thread. */
void __stdcall VvfpStartup(int game, unsigned int shipped) {
    (void)shipped;
    if (g_installed) {
        return;
    }
    if (game == 4) {
        g_installed = fx_install(&FX_VV4, FX4_SLOTS, FX4_RETURN_1, FX4_RETURN_2, (void *)fx_generator_stub_vv4,
                                 (void *)fx_handler_vv4, (void *)fx_draw_vv4);
    } else if (game == 5) {
        g_installed = fx_install(&FX_VV5, FX5_SLOTS, FX5_RETURN_1, FX5_RETURN_2, (void *)fx_generator_stub_vv5,
                                 (void *)fx_handler_vv5, (void *)fx_draw_vv5);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
    }
    return TRUE;
}
