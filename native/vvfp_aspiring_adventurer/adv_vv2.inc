/* The Aspiring Adventurer: The Lost Children.  Included by vvfp_aspiring_adventurer.c.

   The Lost Children's two-choice island events are its family A: the trigger (0x42E990; 20% of its events, and
   the village's first) builds the family-A dialog (constructor 0x422380, on its own stack), whose setup 0x41F780
   draws the event with 0x41F570 -- up to ten draws of rand(22) (0x41F59D), each event 0..20 kept when its own
   condition holds; the draw 21 (`cmp eax, 0x14; ja 0x41F696`, 0x41F5AC) is never kept, so it draws again -- and
   the modal loop (0x401AD0 with 0) runs only the dialog.

   THE SHARE.  The draw 21 is this event: the `ja` at 0x41F5AC goes here first and keeps 21 when the event can
   happen (two villagers who may go, adv_possible; never the village's first island event) -- 1 in 22 a draw,
   exactly like each stock event.  The setup's `ja 0x420408` past its jump table (0x41F7A0) and the resolve's
   `ja 0x422257` (0x4204CE) take the event's 21 here; every other value goes on as before.  The setup writes the
   question (+0x7C: the title line, the picture's five lines -- 0x41F430 draws the villager under the title -- and
   the first page, padded to the event's tallest page: the dialog is sized from +0x7C once, by its constructor), the
   labels +0x4E9A / +0x4F9A, the villager shown +0x50A0 (selected, 0x44B2D0, as the stock setups select theirs) and
   the width +0x60 = 450, then leaves through the setup's own ending (0x4203FE, AL = 1).

   THE PAGES.  The dialog draws +0x7C while +0x50 is 0, else the result +0x278B; it does not wrap.  Two more sites:
     0x42F1A3 `call 0x422380` (the trigger's constructor call): after it, a question of more than one page starts
       on its first page with OK (the answers taken off and OK attached, 0x40B5A0 / 0x40B560 -- the click handler's
       own swap; +0x50 = 1, the page in +0x278B);
     0x42230E `call 0x40D390` (OK's close in the click handler 0x4222F0): while a page is left it is shown instead
       (the last question page brings the answers back, OK off, +0x50 = 0); on the last result page the close runs.
   The answer (the resolve, after the click handler took the answers off and set +0x50A4 = 1 or 2) makes the
   effects inside the click, as every family-A event does, so the Island Events log records them. */

#define ADV_VV2_EVENT 21
#define VV2_WORLD() (*(unsigned char **)(uintptr_t)0x4997BCu)
#define VV2_POOL() (*(unsigned char **)(uintptr_t)0x499F24u)
#define VV2_STRIDE 0xE48Cu
#define VV2_FIRST 0x30u
#define VV2_RECORDS 256
#define VV2_DLG_QUESTION 0x7Cu
#define VV2_DLG_RESULT 0x278Bu
#define VV2_DLG_TEXT 0x270F
#define VV2_DLG_LABEL_A 0x4E9Au
#define VV2_DLG_LABEL_B 0x4F9Au
#define VV2_DLG_LABEL 0x100
#define VV2_DLG_EVENT 0x509Cu
#define VV2_DLG_SUBJECT 0x50A0u
#define VV2_DLG_CHOICE 0x50A4u
#define VV2_PICTURE_LINES 5

typedef int (__cdecl *vv2_rand_fn)(int bound);

static unsigned char *v2_dlg;          /* the family-A dialog this event is in */
static int v2_stage, v2_page;

static unsigned char *v2_record(int index) {
    unsigned char *pool = VV2_POOL();
    return pool == NULL || index < 0 || index >= VV2_RECORDS ? NULL
                                                            : pool + VV2_FIRST + (size_t)index * VV2_STRIDE;
}

static int v2_count(void) {
    return VV2_POOL() == NULL ? 0 : VV2_RECORDS;
}

/* Present (+0x30), alive (+0x52C), not an Esteemed Elder's statue (+0x558: made with health 0 and this byte,
   0x44D467 / 0x44D485), 14 or more (+0x530), not carrying a baby (+0x540). */
static int v2_eligible(const unsigned char *r) {
    return r[0x30] != 0 && *(const int *)(r + 0x52C) > 0 && r[0x558] == 0
        && *(const int *)(r + 0x530) >= ADV_ADULT_UNITS && *(const int *)(r + 0x540) == 0;
}

static int v2_female(const unsigned char *r) {
    return *(const int *)(r + 0x538) == 2;
}

static void v2_name(const unsigned char *r, char *out, int cap) {
    char field[0x19];
    memcpy(field, r + 0x564, 0x18);
    field[0x18] = '\0';
    adv_copy(out, cap, field);
}

static int v2_rand(int n) {
    return n <= 1 ? 0 : ((vv2_rand_fn)(uintptr_t)0x4031A0u)(n);
}

/* Health 0, as The Nightmare's (0x420E44); the Cause of Death companion's tick logs "Unknown causes". */
static void v2_kill(int index) {
    *(int *)(v2_record(index) + 0x52C) = 0;
}

/* The Voices in the Brush (0x4208DF..0x4208FF): the selection cleared (0x4491F0 on the pool), the record's
   active byte cleared. */
static void v2_vanish(int index) {
    ADV_TC0(0x4491F0u, VV2_POOL());
    v2_record(index)[0x30] = 0;
}

static void v2_injure(int index, int health) {
    unsigned char *r = v2_record(index);
    *(int *)(r + 0x52C) = health;
    adv_dislike((int *)(r + 0x5F0), (int *)(r + 0x6E8), 62, 38);
}

/* Skills (ints, 0..100): +0x7E4 Parenting, +0x7E8 Building, +0x7EC Farming, +0x7F0 Healing, +0x7F4 Research. */
static void v2_skill(int index, int which, int amount) {
    static const unsigned int AT[4] = { 0x7EC, 0x7E8, 0x7F4, 0x7F0 };
    int *field = (int *)(v2_record(index) + AT[which]);
    *field = adv_capped(*field + amount);
}

/* The game's own two-choice factor 0x41F720 (thiscall on the dialog: the amount x 1, 2 or 3 by the population). */
static int v2_amount(int kind, int base) {
    (void)kind;
    if (v2_dlg == NULL) {
        return base;
    }
    return ((adv_tc1r)(uintptr_t)0x41F720u)(v2_dlg, NULL, base);
}

/* The family-A writers (thiscall on the world [dialog+0x50AC]): 0x4262B0 food, 0x426290 tech. */
static void v2_award(int kind, int amount) {
    void *world = v2_dlg != NULL ? *(void **)(v2_dlg + 0x50AC) : (void *)VV2_WORLD();
    ADV_TC1(kind == ADV_KIND_FOOD ? 0x4262B0u : 0x426290u, world, amount);
}

static int v2_joins(void) {
    return ADV_L2_OTHER;
}

static const adv_game ADV_VV2 = {
    2, v2_count, v2_record, v2_eligible, v2_female, v2_name, v2_rand, v2_kill, v2_vanish, v2_injure, v2_skill, NULL,
    v2_amount, v2_award, v2_joins, 46, 12, 1
};

/* ---- The sites ---------------------------------------------------------------------------------------------- */

/* The draw 21: kept when the event can happen. */
static int __cdecl v2_keep(void) {
    unsigned char *world = VV2_WORLD();
    int keep = 0;
    __try {
        keep = world != NULL && *(int *)(world + 0x2E51C) > 1 && adv_possible(&ADV_VV2);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        keep = 0;
    }
    return keep;
}

/* `ja` from 0x41F5AC (eax the draw, above 20; bl 0 = not kept). */
__declspec(naked) static void v2_keep_stub(void) {
    __asm {
        cmp eax, ADV_VV2_EVENT
        jne leave_it
        pushad
        call v2_keep
        test eax, eax
        popad
        jz leave_it
        mov bl, 1
    leave_it:
        push 0x41F696
        ret
    }
}

static void v2_page_text(char *out, int cap, const char *page, int pad_to) {
    int i, lines;
    adv_copy(out, cap, g_vv12_title);
    for (i = 0; i < VV2_PICTURE_LINES + 1; ++i) {
        adv_cat(out, cap, "\n");
    }
    adv_cat(out, cap, adv_shown(page));
    lines = adv_lines(adv.g, page);
    while (lines < pad_to && adv_len(out) + 2 < cap) {
        adv_cat(out, cap, "\n ");
        ++lines;
    }
}

/* The setup for the draw 21: 1 = the dialog is kept. */
static int __cdecl v2_setup(unsigned char *d) {
    static char label[VV2_DLG_LABEL];
    __try {
        v2_dlg = d;
        if (!adv_begin(&ADV_VV2)) {
            v2_dlg = NULL;
            return 0;
        }
        adv_piece(g_vv12_title, sizeof g_vv12_title, ADV_TITLE, 0);
        v2_page_text((char *)d + VV2_DLG_QUESTION, VV2_DLG_TEXT, adv.intro.text[adv.intro.count - 1],
                     adv_lines(&ADV_VV2, adv_tallest_text()));
        adv_piece(label, sizeof label, ADV_LABEL_A, 0);
        adv_copy((char *)d + VV2_DLG_LABEL_A, VV2_DLG_LABEL, label);
        adv_piece(label, sizeof label, ADV_LABEL_B, 0);
        adv_copy((char *)d + VV2_DLG_LABEL_B, VV2_DLG_LABEL, label);
        *(int *)(d + VV2_DLG_SUBJECT) = adv.hero;
        *(int *)(d + 0x60) = 0x1C2;
        d[VV2_DLG_RESULT] = '\0';
        ADV_TC1(0x44B2D0u, VV2_POOL(), adv.hero);
        v2_stage = ADV_STAGE_QUESTION;
        v2_page = 0;
        return 1;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        v2_dlg = NULL;
        return 0;
    }
}

/* `ja` from 0x41F7A0 (eax the event, esi the dialog). */
__declspec(naked) static void v2_setup_stub(void) {
    __asm {
        cmp eax, ADV_VV2_EVENT
        jne error
        pushad
        push esi
        call v2_setup
        add esp, 4
        mov dword ptr [esp + 0x1C], eax
        popad
        test eax, eax
        jz dropped
        push 0x4203FE
        ret
    dropped:
        push 0x42037B
        ret
    error:
        push 0x420408
        ret
    }
}

static int v2_ours(const unsigned char *d) {
    return d != NULL && d == v2_dlg && *(const int *)(d + VV2_DLG_EVENT) == ADV_VV2_EVENT;
}

static void v2_result(unsigned char *d, const char *page) {
    v2_page_text((char *)d + VV2_DLG_RESULT, VV2_DLG_TEXT, page, 0);
}

static void __cdecl v2_answer(unsigned char *d) {
    __try {
        if (!v2_ours(d)) {
            return;
        }
        adv_choose(*(int *)(d + VV2_DLG_CHOICE) == 2);
        v2_stage = ADV_STAGE_RESULT;
        v2_page = 0;
        v2_result(d, adv.result[adv.choice].text[0]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* `ja` from 0x4204CE (eax the event, esi the dialog). */
__declspec(naked) static void v2_resolve_stub(void) {
    __asm {
        cmp eax, ADV_VV2_EVENT
        jne leave_it
        pushad
        push esi
        call v2_answer
        add esp, 4
        popad
    leave_it:
        push 0x422257
        ret
    }
}

/* In place of the trigger's `call 0x422380` (thiscall, no arguments). */
static void *__fastcall v2_ctor(void *dialog, void *unused) {
    unsigned char *d = (unsigned char *)dialog;
    void *made;
    (void)unused;
    made = ((void *(__fastcall *)(void *, void *))(uintptr_t)0x422380u)(dialog, NULL);
    __try {
        if (!v2_ours(d)) {
            if (*(int *)(d + VV2_DLG_EVENT) != ADV_VV2_EVENT) {
                v2_dlg = NULL;
            }
        } else if (adv.intro.count > 1) {
            ADV_TC1(0x40B5A0u, dialog, *(void **)(d + 0x50C8));
            ADV_TC1(0x40B5A0u, dialog, *(void **)(d + 0x50CC));
            ADV_TC1(0x40B560u, dialog, *(void **)(d + 0x50D0));
            d[0x50] = 1;
            v2_result(d, adv.intro.text[0]);
            v2_stage = ADV_STAGE_INTRO;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return made;
}

/* In place of OK's `call 0x40D390` (thiscall, the close). */
static void __fastcall v2_ok(void *dialog, void *unused) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused;
    __try {
        if (v2_ours(d)) {
            if (v2_stage == ADV_STAGE_INTRO) {
                ++v2_page;
                if (v2_page >= adv.intro.count - 1) {
                    ADV_TC1(0x40B5A0u, dialog, *(void **)(d + 0x50D0));
                    ADV_TC1(0x40B560u, dialog, *(void **)(d + 0x50C8));
                    ADV_TC1(0x40B560u, dialog, *(void **)(d + 0x50CC));
                    d[0x50] = 0;
                    v2_stage = ADV_STAGE_QUESTION;
                } else {
                    v2_result(d, adv.intro.text[v2_page]);
                }
                return;
            }
            if (v2_stage == ADV_STAGE_RESULT && v2_page + 1 < adv.result[adv.choice].count) {
                ++v2_page;
                v2_result(d, adv.result[adv.choice].text[v2_page]);
                return;
            }
            v2_dlg = NULL;
            v2_stage = ADV_STAGE_NONE;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    ADV_TC0(0x40D390u, dialog);
}

/* A 6-byte `ja rel32` kept a `ja`, aimed at `to`. */
static void v2_ja(vvfp_site_write *w, unsigned int va, const unsigned char *expect, const void *to) {
    unsigned char bytes[6];
    unsigned int rel = (unsigned int)((uintptr_t)to - ((uintptr_t)va + 6u));
    bytes[0] = 0x0F;
    bytes[1] = 0x87;
    memcpy(bytes + 2, &rel, 4);
    vvfp_site_bytes(w, va, 6, expect, bytes);
}

static int v2_install(void) {
    static const unsigned char KEEP_STOCK[6] = { 0x0F, 0x87, 0xE4, 0x00, 0x00, 0x00 };
    static const unsigned char SETUP_STOCK[6] = { 0x0F, 0x87, 0x62, 0x0C, 0x00, 0x00 };
    static const unsigned char RESOLVE_STOCK[6] = { 0x0F, 0x87, 0x83, 0x1D, 0x00, 0x00 };
    static const unsigned char OK_STOCK[5] = { 0xE8, 0x7D, 0xB0, 0xFE, 0xFF };
    static const unsigned char CTOR_STOCK[5] = { 0xE8, 0xD8, 0x31, 0xFF, 0xFF };
    static vvfp_site_write w[5];
    v2_ja(&w[0], 0x41F5ACu, KEEP_STOCK, (const void *)v2_keep_stub);
    v2_ja(&w[1], 0x41F7A0u, SETUP_STOCK, (const void *)v2_setup_stub);
    v2_ja(&w[2], 0x4204CEu, RESOLVE_STOCK, (const void *)v2_resolve_stub);
    vvfp_site_branch(&w[3], 0x42230Eu, 5, OK_STOCK, 0xE8, (const void *)v2_ok);
    vvfp_site_branch(&w[4], 0x42F1A3u, 5, CTOR_STOCK, 0xE8, (const void *)v2_ctor);
    if (!vvfp_install_sites(w, 5)) {
        return 0;
    }
    g_adv_game = &ADV_VV2;
    return 1;
}
