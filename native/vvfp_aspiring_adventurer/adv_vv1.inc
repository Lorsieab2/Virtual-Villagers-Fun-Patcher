/* The Aspiring Adventurer: A New Home.  Included by vvfp_aspiring_adventurer.c.

   A New Home's two-choice island events are its villager encounters: the trigger (0x4237B3; 20% of its island
   events, and the village's first) builds the encounter dialog (0x41A460, on its own stack), whose setup 0x4189E0
   draws the encounter with the roller 0x418920 -- rand(16) over a class table (0x4189A4 / 0x418990), again while
   the drawn encounter's class says it cannot happen -- so each possible encounter is 1 in m (m the possible ones).
   The modal loop (0x401AB0 with 0) runs only the dialog: the village does not run while it is up.

   THE SHARE.  The setup's `call 0x418920` (0x4189F2) calls this DLL first: when the event can happen (two
   villagers who may go, adv_possible; never the village's first island event, the visitor every village starts
   with; never while a Story / Cheat Upgrades pick or custom event is on its way) it draws rand(m + 1) with the
   game's own rand (0x402F10) -- m counted from the live class table as the roller would accept, so a re-aimed
   entry (Restore Missing Island Events' The Furry Food: stored food) counts too -- and takes the draw m: one more
   encounter, 1 in m + 1, like each of the others.  Otherwise the stock roller runs (its own draws).  The event then
   writes the setup's fields itself and leaves through the setup's own ending (0x4192E3: AL = 1, the dialog kept):
   its kind +0x5094 = ADV_VV1_KIND (past every stock jump table), the question +0x74 (the title line, the five lines
   the villager's picture is drawn in -- 0x4187E0 draws it under the title at +0x68 -- and the first page, padded
   to the event's tallest page: the dialog is sized from +0x74 once, 0x41A460), the labels +0x4E92 / +0x4F92, the
   villager shown +0x5098 (selected, 0x43A160, as the stock setup selects its own), the width +0x60 = 450.

   THE PAGES.  The dialog draws +0x74 while +0x50 is 0, else +0x2783 (the result); it does not wrap (each '\n' is a
   line).  Three more sites:
     0x41A87C `call 0x40AB80` (the constructor attaching the second answer): when the question is more than one
       page, the two answers are taken off again and OK attached (0x40ABC0 / 0x40AB80 -- the click handler's own
       swap), +0x50 = 1, and the first page put in +0x2783;
     0x41A3EE `call 0x40C9B0` (OK's close in the click handler 0x41A3D0): while a page is left it is shown instead
       (the last question page brings the two answers back, OK off, +0x50 = 0); on the last result page the close
       runs;
     0x41939D `ja 0x41A37A` (the answer's resolve 0x419380, past the stock kinds): the event's kind is answered
       here -- the effects (adv_choose) and the first result page -- and the resolve leaves as for any other kind
       (0x41A37A).  The Island Events log watches the click handler's answer (its entry, 0x41A3D0): the effects are
       made inside it, as every stock encounter's are. */

#define ADV_VV1_KIND 0x7F4B1A2E               /* past every stock jump table (Story's own questions are 0x...2D) */
#define VV1_WORLD() (*(unsigned char **)(uintptr_t)0x48AEDCu)
#define VV1_ARRAY() (*(unsigned char **)(uintptr_t)0x48B614u)
#define VV1_STRIDE 0x3D8u
#define VV1_RECORDS 256
#define VV1_DLG_QUESTION 0x74u
#define VV1_DLG_RESULT 0x2783u
#define VV1_DLG_TEXT 0x270F
#define VV1_DLG_LABEL_A 0x4E92u
#define VV1_DLG_LABEL_B 0x4F92u
#define VV1_DLG_LABEL 0x100
#define VV1_DLG_KIND 0x5094u
#define VV1_DLG_SUBJECT 0x5098u
#define VV1_DLG_CHOICE 0x509Cu
#define VV1_PICTURE_LINES 5

typedef int (__cdecl *vv1_rand_fn)(int bound);
typedef int (__fastcall *vv1_tc0r)(void *self, void *unused);

static unsigned char *v1_record(int index) {
    unsigned char *array = VV1_ARRAY();
    return array == NULL || index < 0 || index >= VV1_RECORDS ? NULL : array + (size_t)index * VV1_STRIDE;
}

static int v1_count(void) {
    return VV1_ARRAY() == NULL ? 0 : VV1_RECORDS;
}

/* Present (+0x28 == 1, the game's own test), alive (+0x344), 14 or more (+0x348), not carrying a baby (+0x358,
   the conception's mark), not the Golden Child (family +0x36C 0xC7, 0x43C350). */
static int v1_eligible(const unsigned char *r) {
    return r[0x28] == 1 && *(const int *)(r + 0x344) > 0 && *(const int *)(r + 0x348) >= ADV_ADULT_UNITS
        && *(const int *)(r + 0x358) == 0 && *(const int *)(r + 0x36C) != 0xC7;
}

static int v1_female(const unsigned char *r) {
    return *(const int *)(r + 0x350) == 2;
}

static void v1_name(const unsigned char *r, char *out, int cap) {
    char field[0x1D];
    memcpy(field, r + 0x370, 0x1C);
    field[0x1C] = '\0';
    adv_copy(out, cap, field);
}

static int v1_rand(int n) {
    return n <= 1 ? 0 : ((vv1_rand_fn)(uintptr_t)0x402F10u)(n);
}

/* Health 0: the game's own death (as Strange Berries, 0x419509); the Cause of Death companion's tick logs
   "Unknown causes". */
static void v1_kill(int index) {
    *(int *)(v1_record(index) + 0x344) = 0;
}

/* "Get a closer look... never heard from again" (0x41979D / 0x4197BF): the record freed, the selection dropped
   when it is this villager. */
static void v1_vanish(int index) {
    unsigned char *r = v1_record(index);
    unsigned char *world = VV1_WORLD();
    r[0x28] = 0;
    if (world != NULL && *(int *)(world + 0xAD34) == index) {
        ADV_TC0(0x4393E0u, VV1_ARRAY());
    }
}

static void v1_injure(int index, int health) {
    unsigned char *r = v1_record(index);
    *(int *)(r + 0x344) = health;
    adv_dislike((int *)(r + 0x398), (int *)(r + 0x3A8), 4, 38);
}

/* The game's own skill adder 0x437230 (on the villagers: index, code, amount; 0..100): codes 1 Farming, 4 Building,
   3 Research, 5 Healing. */
static void v1_skill(int index, int which, int amount) {
    static const int CODE[4] = { 1, 4, 3, 5 };
    typedef void (__fastcall *adder_fn)(void *, void *, int, int, int);
    ((adder_fn)(uintptr_t)0x437230u)(VV1_ARRAY(), NULL, index, CODE[which], amount);
}

/* Fixed amounts in the stock game; with Island Events Scale ticked, its companion's rule: the population 0x41CF90
   on the world, or a tenth of the store (world +0xA2EC food, +0xA2FC tech). */
static int v1_amount(int kind, int base) {
    typedef int (__stdcall *mode_fn)(void);
    HMODULE module = GetModuleHandleA("VVFP Island Events Scale.dll");
    mode_fn mode = module != NULL ? (mode_fn)(void *)GetProcAddress(module, "VvfpIslandEventsScaleMode") : NULL;
    int m = mode != NULL ? mode() : 0;
    unsigned char *world = VV1_WORLD();
    if (world == NULL) {
        return base;
    }
    __try {
        if (m == 2) {
            int stored = *(int *)(world + (kind == ADV_KIND_FOOD ? 0xA2ECu : 0xA2FCu));
            return base + (stored > 0 ? stored / 10 : 0);
        }
        if (m == 1) {
            int n = ((vv1_tc0r)(uintptr_t)0x41CF90u)(world, NULL);
            return base * (n > 50 ? 3 : (n > 25 ? 2 : 1));
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return base;
}

/* The writers the stock encounters call: 0x41D140 food (The Trapped Whale), 0x41D120 tech (The Brass Compass). */
static void v1_award(int kind, int amount) {
    ADV_TC1(kind == ADV_KIND_FOOD ? 0x41D140u : 0x41D120u, VV1_WORLD(), amount);
}

static int v1_joins(void) {
    return ADV_L2_OTHER;
}

static const adv_game ADV_VV1 = {
    1, v1_count, v1_record, v1_eligible, v1_female, v1_name, v1_rand, v1_kill, v1_vanish, v1_injure, v1_skill, NULL,
    v1_amount, v1_award, v1_joins, 46, 9, 1
};

/* ---- The share --------------------------------------------------------------------------------------------- */

static void *v1_dialog;
static int v1_stage, v1_page;

static int v1_any_child(void) {
    int i;
    for (i = 0; i < VV1_RECORDS; ++i) {
        const unsigned char *r = v1_record(i);
        if (r != NULL && r[0x28] != 0 && *(const int *)(r + 0x344) > 0 && *(const int *)(r + 0x348) < ADV_ADULT_UNITS) {
            return 1;
        }
    }
    return 0;
}

/* The encounters the roller would accept now (its class table, read live). */
static int v1_possible_encounters(void) {
    unsigned char *world = VV1_WORLD();
    int v, m = 0;
    for (v = 0; v < 16; ++v) {
        unsigned int cls = *(const unsigned char *)(uintptr_t)(0x4189A4u + (unsigned int)v);
        unsigned int target = cls < 5 ? *(const unsigned int *)(uintptr_t)(0x418990u + 4u * cls) : 0u;
        int ok;
        switch (target) {
        case 0x41894Fu: ok = *(int *)(world + 0xA2BC) < 3; break;
        case 0x418963u: ok = *(int *)(world + 0xA2D4) < 3; break;
        case 0x418977u: ok = v1_any_child(); break;
        case 0x418930u: ok = 0; break;               /* the stock re-roll */
        case 0x456670u: ok = *(int *)(world + 0xA2EC) > 0; break;   /* Restore Missing Island Events */
        default: ok = 1; break;                      /* 0x418987, or anything else that accepts */
        }
        m += ok;
    }
    return m;
}

static int v1_story_busy(void) {
    typedef int (__stdcall *pending_fn)(int);
    HMODULE module = GetModuleHandleA("VVFP Story Upgrades.dll");
    pending_fn pending = module != NULL ? (pending_fn)(void *)GetProcAddress(module, "VvfpStoryPickPending") : NULL;
    return pending != NULL && pending(1) != 0;
}

/* A page as the dialog shows it: the title, the picture's lines, the page's own lines. */
static void v1_page_text(char *out, int cap, const char *page, int pad_to) {
    int i, lines;
    adv_copy(out, cap, g_vv12_title);
    for (i = 0; i < VV1_PICTURE_LINES + 1; ++i) {
        adv_cat(out, cap, "\n");
    }
    adv_cat(out, cap, adv_shown(page));
    lines = adv_lines(adv.g, page);
    while (lines < pad_to && adv_len(out) + 2 < cap) {
        adv_cat(out, cap, "\n ");
        ++lines;
    }
}

/* adv_begin done: the setup's fields. */
static void v1_fill(unsigned char *d) {
    static char label[VV1_DLG_LABEL];
    unsigned char *villagers = *(unsigned char **)(d + 0x50A8u);
    adv_piece(g_vv12_title, sizeof g_vv12_title, ADV_TITLE, 0);
    v1_page_text((char *)d + VV1_DLG_QUESTION, VV1_DLG_TEXT, adv.intro.text[adv.intro.count - 1],
                 adv_lines(&ADV_VV1, adv_tallest_text()));
    adv_piece(label, sizeof label, ADV_LABEL_A, 0);
    adv_copy((char *)d + VV1_DLG_LABEL_A, VV1_DLG_LABEL, label);
    adv_piece(label, sizeof label, ADV_LABEL_B, 0);
    adv_copy((char *)d + VV1_DLG_LABEL_B, VV1_DLG_LABEL, label);
    *(int *)(d + VV1_DLG_KIND) = ADV_VV1_KIND;
    *(int *)(d + VV1_DLG_SUBJECT) = adv.hero;
    *(int *)(d + 0x60) = 0x1C2;
    d[VV1_DLG_RESULT] = '\0';
    if (villagers != NULL) {
        ADV_TC1(0x43A160u, villagers, adv.hero);
    }
}

/* In place of the setup's `call 0x418920`: the stock draw, or ADV_VV1_KIND -2 when this event is drawn. */
static int __cdecl v1_choose(void *dialog) {
    unsigned char *world = VV1_WORLD();
    int m;
    __try {
        if (world != NULL && VV1_ARRAY() != NULL && *(int *)(world + 0x9E40) > 1 && !v1_story_busy()
            && adv_possible(&ADV_VV1)) {
            m = v1_possible_encounters();
            if (v1_rand(m + 1) == m && adv_begin(&ADV_VV1)) {
                v1_fill((unsigned char *)dialog);
                v1_dialog = dialog;
                v1_stage = ADV_STAGE_QUESTION;
                v1_page = 0;
                return -2;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    v1_dialog = NULL;
    return ((vv1_tc0r)(uintptr_t)0x418920u)(dialog, NULL);
}

/* `call` from 0x4189F2 (ecx the dialog). */
__declspec(naked) static void v1_choose_stub(void) {
    __asm {
        push ecx
        call v1_choose
        add esp, 4
        cmp eax, -2
        je ours
        ret
    ours:
        add esp, 4
        push 0x4192E3
        ret
    }
}

static int v1_ours(const unsigned char *d) {
    return d != NULL && d == v1_dialog && *(const int *)(d + VV1_DLG_KIND) == ADV_VV1_KIND;
}

static void v1_result(unsigned char *d, const char *page) {
    v1_page_text((char *)d + VV1_DLG_RESULT, VV1_DLG_TEXT, page, 0);
}

/* In place of the constructor's `call 0x40AB80` attaching the second answer (thiscall, the child). */
static void __fastcall v1_attach(void *dialog, void *unused, void *child) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused;
    ADV_TC1(0x40AB80u, dialog, child);
    __try {
        if (!v1_ours(d)) {
            if (*(int *)(d + VV1_DLG_KIND) != ADV_VV1_KIND) {
                v1_dialog = NULL;
            }
            return;
        }
        if (adv.intro.count > 1) {
            ADV_TC1(0x40ABC0u, dialog, *(void **)(d + 0x50BC));
            ADV_TC1(0x40ABC0u, dialog, *(void **)(d + 0x50C0));
            ADV_TC1(0x40AB80u, dialog, *(void **)(d + 0x50C4));
            d[0x50] = 1;
            v1_result(d, adv.intro.text[0]);
            v1_stage = ADV_STAGE_INTRO;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* In place of OK's `call 0x40C9B0` (thiscall, the close). */
static void __fastcall v1_ok(void *dialog, void *unused) {
    unsigned char *d = (unsigned char *)dialog;
    (void)unused;
    __try {
        if (v1_ours(d)) {
            if (v1_stage == ADV_STAGE_INTRO) {
                ++v1_page;
                if (v1_page >= adv.intro.count - 1) {
                    ADV_TC1(0x40ABC0u, dialog, *(void **)(d + 0x50C4));
                    ADV_TC1(0x40AB80u, dialog, *(void **)(d + 0x50BC));
                    ADV_TC1(0x40AB80u, dialog, *(void **)(d + 0x50C0));
                    d[0x50] = 0;
                    v1_stage = ADV_STAGE_QUESTION;
                } else {
                    v1_result(d, adv.intro.text[v1_page]);
                }
                return;
            }
            if (v1_stage == ADV_STAGE_RESULT && v1_page + 1 < adv.result[adv.choice].count) {
                ++v1_page;
                v1_result(d, adv.result[adv.choice].text[v1_page]);
                return;
            }
            v1_dialog = NULL;
            v1_stage = ADV_STAGE_NONE;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    ADV_TC0(0x40C9B0u, dialog);
}

/* The answer (the resolve, the event's kind): +0x509C is 1 for the first button, 2 for the second. */
static void __cdecl v1_answer(unsigned char *d) {
    __try {
        if (!v1_ours(d)) {
            return;
        }
        adv_choose(*(int *)(d + VV1_DLG_CHOICE) == 2);
        v1_stage = ADV_STAGE_RESULT;
        v1_page = 0;
        v1_result(d, adv.result[adv.choice].text[0]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* jmp from the resolve's `ja 0x41A37A` (0x41939D; eax the kind, esi the dialog, flags of cmp eax, 0xF). */
__declspec(naked) static void v1_resolve_stub(void) {
    __asm {
        cmp eax, ADV_VV1_KIND
        jne stock
        pushad
        push esi
        call v1_answer
        add esp, 4
        popad
        push 0x41A37A
        ret
    stock:
        cmp eax, 0xF
        ja leave_it
        push 0x4193A3
        ret
    leave_it:
        push 0x41A37A
        ret
    }
}

static int v1_install(void) {
    static const unsigned char CHOOSE_STOCK[5] = { 0xE8, 0x29, 0xFF, 0xFF, 0xFF };
    static const unsigned char RESOLVE_STOCK[6] = { 0x0F, 0x87, 0xD7, 0x0F, 0x00, 0x00 };
    static const unsigned char OK_STOCK[5] = { 0xE8, 0xBD, 0x25, 0xFF, 0xFF };
    static const unsigned char ATTACH_STOCK[5] = { 0xE8, 0xFF, 0x02, 0xFF, 0xFF };
    static vvfp_site_write w[4];
    vvfp_site_branch(&w[0], 0x4189F2u, 5, CHOOSE_STOCK, 0xE8, (const void *)v1_choose_stub);
    vvfp_site_branch(&w[1], 0x41939Du, 6, RESOLVE_STOCK, 0xE9, (const void *)v1_resolve_stub);
    vvfp_site_branch(&w[2], 0x41A3EEu, 5, OK_STOCK, 0xE8, (const void *)v1_ok);
    vvfp_site_branch(&w[3], 0x41A87Cu, 5, ATTACH_STOCK, 0xE8, (const void *)v1_attach);
    if (!vvfp_install_sites(w, 4)) {
        return 0;
    }
    g_adv_game = &ADV_VV1;
    return 1;
}
