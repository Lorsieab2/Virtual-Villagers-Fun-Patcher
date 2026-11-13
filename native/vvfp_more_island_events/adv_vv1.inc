/* The Aspiring Adventurer and The Cave Explorers: A New Home.  Included by vvfp_more_island_events.c.

   BOTH EVENTS share the sites below through adv_flow (adv_core.inc): the draw takes rand(m + k), k the events that
   can happen now (the Adventurer at m, The Cave Explorers after it), each one more encounter.  The Cave Explorers asks
   up to three questions in the same dialog: after an answer that leads to another question, the two answer buttons
   get that question's words (the constructor's own text setter 0x4015A0, then centred again with the button's own
   size and move, as the constructor places them) and come back on its last page.

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
       here -- the next question, or the ending's first page -- and the resolve leaves as for any other kind
       (0x41A37A).  The ending's effects wait for their own page (adv_log.inc): they are made when the page that ends
       its text is shown -- in the answer's click when the ending is one page, else in the OK click that brings it --
       and the event keeps its own one Island Events log entry, with a "Choice:" line for each answer clicked. */

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
        && !adv_is_protected(1, r);
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

static int v1_age(const unsigned char *r) {
    return *(const int *)(r + 0x348);
}

/* The Cave puzzle (the Puzzles screen's "The Cave"): world byte +0x9FA8, set to 1 only by the Golden Child opening
   the cave (effect 1, 0x43ABCA). */
static int v1_cave_open(void) {
    unsigned char *world = VV1_WORLD();
    return world != NULL && world[0x9FA8] != 0;
}

/* The awards' base ranges (src/vv_aspiring_adventurer.py AWARD_RANGES: the smallest and largest stock island-event
   gain): food 200 (The Greedy Little Monkey, 200 x n at strength 1) .. 1,500 (the wooden crate at strength 3); tech
   500 (the badly weathered crate at strength 1) .. 4,999 (The Brass Compass, rand(3000) + 2000 at 0x41A367). */
static const adv_game ADV_VV1 = {
    1, v1_count, v1_record, v1_eligible, v1_female, v1_name, v1_rand, v1_kill, v1_vanish, v1_injure, v1_skill, NULL,
    v1_amount, v1_award, v1_joins, 46, 9, 1,
    200, 1500, 500, 4999, v1_age, v1_cave_open
};

/* ---- The share --------------------------------------------------------------------------------------------- */

static void *v1_dialog;
static int v1_stage, v1_page;
static const adv_flow *v1_flow;        /* the event in the dialog: ADV_FLOW or CAVE_FLOW */
static int v1_node, v1_ending;         /* its question on screen; the ending reached */
static int v1_effects_page;            /* the ending's page that makes its effects (its last), -1 made */

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

/* A page as the dialog shows it: the title, the picture's lines, the page's own lines (wrapped here: the dialog
   breaks only at '\n'). */
static void v1_page_text(char *out, int cap, const char *page, int pad_to) {
    static char wrapped[ADV_PAGE_BYTES];
    int i, lines;
    adv_copy(out, cap, g_vv12_title);
    for (i = 0; i < VV1_PICTURE_LINES + 1; ++i) {
        adv_cat(out, cap, "\n");
    }
    adv_wrap(page, ADV_VV1.width, wrapped, sizeof wrapped);
    adv_cat(out, cap, wrapped);
    lines = adv_lines(&ADV_VV1, page);
    while (lines < pad_to && adv_len(out) + 2 < cap) {
        adv_cat(out, cap, "\n ");
        ++lines;
    }
}

/* The answers' words of question `node` in the dialog's two labels (which the Island Events log reads as the answer
   clicked). */
static void v1_set_labels(unsigned char *d, int node) {
    static char label[VV1_DLG_LABEL];
    v1_flow->label(node, 0, label, sizeof label);
    adv_copy((char *)d + VV1_DLG_LABEL_A, VV1_DLG_LABEL, label);
    v1_flow->label(node, 1, label, sizeof label);
    adv_copy((char *)d + VV1_DLG_LABEL_B, VV1_DLG_LABEL, label);
}

/* An answer button given its new words and centred again, as the constructor 0x41A460 places it: the text setter
   0x4015A0 (the constructor's own, font 0), its width and height (vtable +0xC / +0x10), and the move (+4) to x = the
   dialog's width / 2 - its width / 2 and y = the dialog's height - h / 2 - 3h (the first, 0x41A687) or - 2h (the
   second, 0x41A772). */
typedef void (__fastcall *v1_text_fn)(void *self, void *unused, const char *text, int font);
typedef int (__fastcall *v1_size_fn)(void *self, void *unused);
typedef void (__fastcall *v1_move_fn)(void *self, void *unused, int x, int y);

static void v1_relabel_one(unsigned char *d, unsigned int button_at, unsigned int label_at, int second) {
    void *button = *(void **)(d + button_at);
    void **vtable;
    int w, h, x, y;
    if (button == NULL) {
        return;
    }
    ((v1_text_fn)(uintptr_t)0x4015A0u)(button, NULL, (const char *)d + label_at, 0);
    vtable = *(void ***)button;
    w = ((v1_size_fn)vtable[3])(button, NULL);
    h = ((v1_size_fn)vtable[4])(button, NULL);
    x = (*(int *)(d + 0x1C) - *(int *)(d + 0x14)) / 2 - w / 2;
    y = (*(int *)(d + 0x20) - *(int *)(d + 0x18)) - (second ? 2 * h : h / 2 + 3 * h);
    ((v1_move_fn)vtable[1])(button, NULL, x, y);
}

static void v1_relabel(unsigned char *d) {
    v1_relabel_one(d, 0x50BCu, VV1_DLG_LABEL_A, 0);
    v1_relabel_one(d, 0x50C0u, VV1_DLG_LABEL_B, 1);
}

/* The two answers up and OK off (the click handler's own swap, reversed), or OK up and the answers off. */
static void v1_answers_on(unsigned char *d) {
    ADV_TC1(0x40ABC0u, d, *(void **)(d + 0x50C4));
    ADV_TC1(0x40AB80u, d, *(void **)(d + 0x50BC));
    ADV_TC1(0x40AB80u, d, *(void **)(d + 0x50C0));
}

static void v1_ok_on(unsigned char *d) {
    ADV_TC1(0x40ABC0u, d, *(void **)(d + 0x50BC));
    ADV_TC1(0x40ABC0u, d, *(void **)(d + 0x50C0));
    ADV_TC1(0x40AB80u, d, *(void **)(d + 0x50C4));
}

/* The shared popup's client (vvfp_multi_answer_12.h): an event whose flow has answers(). */
static int v1_ours(const unsigned char *d);

static int v1_mb_state(void *dialog) {
    if (!v1_ours((const unsigned char *)dialog)) {
        return MB_NOT_OURS;
    }
    return v1_stage == ADV_STAGE_QUESTION ? MB_ASKING : (v1_stage == ADV_STAGE_INTRO ? MB_OK_UP : MB_ANSWERED);
}

static int v1_mb_answers(void *dialog) {
    (void)dialog;
    return adv_answers(v1_flow, v1_node);
}

static void v1_mb_label(void *dialog, int k, char *out, int cap) {
    (void)dialog;
    v1_flow->label(v1_node, k, out, cap);
}

/* The game's own resolve (0x419380): its kind is ours, so v1_answer answers (the choice field 3 or 4). */
static void v1_mb_resolve(void *dialog) {
    ADV_TC0(0x419380u, dialog);
}

static const mb_client V1_MB = { v1_mb_state, v1_mb_answers, v1_mb_label, v1_mb_resolve };

/* The event's begin done: the setup's fields. */
static void v1_fill(unsigned char *d) {
    const adv_pages *first = v1_flow->question(0);
    unsigned char *villagers = *(unsigned char **)(d + 0x50A8u);
    int subject = v1_flow->subject();
    v1_flow->title(g_vv12_title, sizeof g_vv12_title);
    int room = v1_flow->answers != NULL ? mb_room_lines(1, d, adv_answers(v1_flow, 0)) : 0;
    v1_page_text((char *)d + VV1_DLG_QUESTION, VV1_DLG_TEXT, first->text[first->count - 1],
                 adv_lines(&ADV_VV1, v1_flow->tallest()) + room);
    v1_set_labels(d, 0);
    if (v1_flow->answers != NULL) {
        mb_attach(1, &V1_MB, d);               /* three or four answers (vvfp_multi_answer_12.h) */
    }
    *(int *)(d + VV1_DLG_KIND) = ADV_VV1_KIND;
    *(int *)(d + VV1_DLG_SUBJECT) = subject;
    *(int *)(d + 0x60) = 0x1C2;
    d[VV1_DLG_RESULT] = '\0';
    if (villagers != NULL) {
        ADV_TC1(0x43A160u, villagers, subject);
    }
}

/* In place of the setup's `call 0x418920`: the stock draw, or ADV_VV1_KIND -2 when one of the events is drawn --
   each possible event one more encounter, rand(m + k) with k of them possible: m + 0 The Aspiring Adventurer (when
   it can happen), the next The Cave Explorers (when it can). */
static int __cdecl v1_choose(void *dialog) {
    unsigned char *world = VV1_WORLD();
    int m, adv_ok, cave_ok, draw;
    adv_log_reset();                   /* an encounter is drawn: whatever was ours is over */
    __try {
        if (world != NULL && VV1_ARRAY() != NULL && *(int *)(world + 0x9E40) > 1 && !v1_story_busy()) {
            adv_ok = adv_possible(&ADV_VV1);
            cave_ok = cave_possible(&ADV_VV1);
            if (adv_ok || cave_ok) {
                m = v1_possible_encounters();
                draw = v1_rand(m + adv_ok + cave_ok) - m;
                if (draw >= 0) {
                    int is_cave = !adv_ok || draw > 0;
                    if (is_cave ? cave_begin(&ADV_VV1) : adv_begin(&ADV_VV1)) {
                        v1_flow = is_cave ? &CAVE_FLOW : &ADV_FLOW;
                        v1_node = 0;
                        v1_ending = -1;
                        v1_fill((unsigned char *)dialog);
                        adv_log_event(1, g_vv12_title);
                        v1_effects_page = -1;
                        v1_dialog = dialog;
                        v1_stage = ADV_STAGE_QUESTION;
                        v1_page = 0;
                        return -2;
                    }
                }
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

/* Ending page `k` shown, and the ending's effects when it is the last (adv_log.inc). */
static void v1_result_page(unsigned char *d, int k) {
    v1_result(d, v1_flow->ending(v1_ending)->text[k]);
    if (k == v1_effects_page) {
        v1_effects_page = -1;
        adv_log_effects(v1_flow->effects, v1_ending);
    }
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
        if (v1_flow->question(0)->count > 1) {
            v1_ok_on(d);
            d[0x50] = 1;
            v1_result(d, v1_flow->question(0)->text[0]);
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
                const adv_pages *pages = v1_flow->question(v1_node);
                ++v1_page;
                if (v1_page >= pages->count - 1) {
                    v1_answers_on(d);
                    if (v1_node == 0) {
                        d[0x50] = 0;                  /* the question's last page, +0x74 */
                    } else {
                        v1_result(d, pages->text[pages->count - 1]);
                    }
                    v1_stage = ADV_STAGE_QUESTION;
                } else {
                    v1_result(d, pages->text[v1_page]);
                }
                return;
            }
            if (v1_stage == ADV_STAGE_RESULT && v1_page + 1 < v1_flow->ending(v1_ending)->count) {
                ++v1_page;
                v1_result_page(d, v1_page);
                return;
            }
            if (v1_stage == ADV_STAGE_RESULT && v1_effects_page >= 0) {
                v1_effects_page = -1;            /* never left unmade (a page count that changed: a fault) */
                adv_log_effects(v1_flow->effects, v1_ending);
            }
            v1_dialog = NULL;
            v1_stage = ADV_STAGE_NONE;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    ADV_TC0(0x40C9B0u, dialog);
}

/* The answer (the resolve, the event's kind): +0x509C is 1 for the first button, 2 for the second.  The click
   handler has already taken the answers off and put OK up, and sets +0x50 (the result shown) after this.  An ending:
   its first page (its effects wait for the last).  Another question (The Cave Explorers): its words on the two
   answers, and its pages -- the answers back at once when it is one page. */
static void __cdecl v1_answer(unsigned char *d) {
    __try {
        int next, which;
        const adv_pages *pages;
        if (!v1_ours(d) || v1_stage != ADV_STAGE_QUESTION) {
            return;
        }
        which = *(int *)(d + VV1_DLG_CHOICE) - 1;          /* 1 / 2 the game's two, 3 / 4 ours */
        if (which < 0 || which >= adv_answers(v1_flow, v1_node)) {
            which = 0;
        }
        if (which < 2) {
            adv_log_choice((const char *)d + (which ? VV1_DLG_LABEL_B : VV1_DLG_LABEL_A));
        } else {
            static char label[VV1_DLG_LABEL];
            v1_flow->label(v1_node, which, label, sizeof label);
            adv_log_choice(label);
        }
        next = v1_flow->choose(v1_node, which);
        v1_page = 0;
        if (next < 0) {
            v1_ending = -1 - next;
            v1_stage = ADV_STAGE_RESULT;
            v1_effects_page = v1_flow->ending(v1_ending)->count - 1;
            v1_result_page(d, 0);
            return;
        }
        v1_node = next;
        v1_set_labels(d, next);
        v1_relabel(d);
        pages = v1_flow->question(next);
        if (pages->count <= 1) {
            v1_answers_on(d);
            v1_stage = ADV_STAGE_QUESTION;
        } else {
            v1_stage = ADV_STAGE_INTRO;
        }
        v1_result(d, pages->text[0]);
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

static void cr_v1_sites(vvfp_site_write *w);   /* The Remembrance Ceremony, The Rumblings (ceremony_games.inc) */
static void cr_v12_ready(int game);

static int v1_install(void) {
    static const unsigned char CHOOSE_STOCK[5] = { 0xE8, 0x29, 0xFF, 0xFF, 0xFF };
    static const unsigned char RESOLVE_STOCK[6] = { 0x0F, 0x87, 0xD7, 0x0F, 0x00, 0x00 };
    static const unsigned char OK_STOCK[5] = { 0xE8, 0xBD, 0x25, 0xFF, 0xFF };
    static const unsigned char ATTACH_STOCK[5] = { 0xE8, 0xFF, 0x02, 0xFF, 0xFF };
    static vvfp_site_write w[6];
    vvfp_site_branch(&w[0], 0x4189F2u, 5, CHOOSE_STOCK, 0xE8, (const void *)v1_choose_stub);
    vvfp_site_branch(&w[1], 0x41939Du, 6, RESOLVE_STOCK, 0xE9, (const void *)v1_resolve_stub);
    vvfp_site_branch(&w[2], 0x41A3EEu, 5, OK_STOCK, 0xE8, (const void *)v1_ok);
    vvfp_site_branch(&w[3], 0x41A87Cu, 5, ATTACH_STOCK, 0xE8, (const void *)v1_attach);
    cr_v1_sites(&w[4]);                 /* two more, all six or none */
    if (!vvfp_install_sites(w, 6)) {
        return 0;
    }
    g_adv_game = &ADV_VV1;
    cr_v12_ready(1);
    return 1;
}
