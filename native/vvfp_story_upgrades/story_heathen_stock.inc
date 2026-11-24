/* New Believers: Heathens in the game's OWN island events -- included by vvfp_story_upgrades.c after
   story_graph.inc (it reads the row through cg_heathens_row).

   The owner (2026-11-23): "All stock, adapt clashes" -- with the row "Heathens can be selected in Island Events/
   Heathen-Exclusive Events" every stock event that casts a villager may cast an ordinary Heathen.  The stock texts,
   odds and choices never change; only who may be drawn.  docs/event-collection/cie-v6-binary.md 45a.

   WHO (the believer's part of each event).  Every event picks through the game's picker 0x471870 (thiscall on the
   villager manager, 14 arguments: minAge, maxAge, sex, allowPregnant, allowSick, skill, minSkill, mustBePregnant,
   mustBeSick, &count, heathenOnly, a12, allowHeathen, allowRole; ret 0x38; it returns the record or 0).  A believer's
   part passes heathenOnly 0 and allowHeathen 0.  hv_pick runs the stock call as it is, then the same call for the
   Heathens alone the way the game picks a Heathen (heathenOnly 1, allowSick 0, mustBeSick 0, allowRole 0: never roles
   12-17, never sick, health above 0, present), and keeps the Heathen in proportion -- every believer and every
   Heathen the call could take is equally likely.  An event that must have a sick villager, a Pick Island Event
   whose villager the player chose, and the calls that already take Heathens stay stock.

   The sites.  Most believer calls are Story / Cheat Upgrades' own scope calls (story_tables.h, oc_scope_enter hands
   them here); the three that are not (Mushroom Day 0x4150D7, The Daredevil Jump's second villager 0x4159B5,
   Innovation in Farming's storyteller's listener 0x416FD9) are spliced to hv_pick_thunk.  The event object is ESI at
   every one (each condition does `mov esi, ecx` first) and the record goes to [esi+4] (or [esi+0xC]).

   TWO OF THE SAME.  Where the event then draws a Heathen for its other part (The Heathen Toy 0x415877, The Spa / The
   Cracked Mask 0x415C9D, Spying on the Heathens / The Missing Kids 0x415E80: [esi+0xC]; Outreach? 0x4162E0:
   [esi+4]), the other part's record is already stored, and that call never returns the same Heathen: it draws
   again, and with no other Heathen the event is not offered this time (stock: nothing else changes).  You're Doing It
   Wrong! (0x415FC0) needs no such care: an adult and a child are never the same.

   CLASHES (the owner: "A Faith rise on a Heathen does NOT make them join ... skip the Faith part for them"; "Becomes
   a Heathen does nothing to a Heathen"; "Your tribe gains ..." applies to the tribe as written).  The Vision (Faith
   +20..39), The Mask (put on: SetFaith -10 and so a Heathen; buried: Faith +10), Doubt (Faith -5 / +5), The Spa and
   The Cracked Mask (SetFaith -10, then the faction setter 0x466880(1)) change a drawn Heathen's Faith.  Around the
   event's own apply (the popup's OK, story_outcomes.inc oc_vv5_*_stub) a Heathen in that event's believer part has
   its Faith set to -100 -- so no change can cross 0, the game's conversion 0x4668B0 is never reached -- and after
   the apply its Faith and the two fields the faction setter writes (+0x2F14, +0x2F40) are put back as they were: the
   Faith part never happened.  Every other effect (health, likes, skills, Devotion -- a skill, it never makes anyone
   join -- the age, the tribe's food, tech and Divine Energy) is the stock event's own.

   GROUPS (everyone).  The group routine 0x470C60 (behaviour, minAge, maxAge, sex, &count, minCount; ret 0x18) skips
   Heathens (0x470CCB); it stops each villager (0x473440) and starts the behaviour (0x465580).  The game has the
   same routine for the Heathens, 0x470D60 (only its faction test reversed, 0x470DD2), and two events already call
   it right after the believers' -- The Allergy Season (0x414A97) and The Salty Air (0x4153DD): there the Heathens
   (every one, the game's own) already sneeze and hide, so those two are left as they are.  That is the proof the
   behaviours are the Heathens' too.  For the others hv_group runs the stock call, then does the same for every
   ordinary Heathen it would take by age and sex (never roles 12-17, never sick, health above 0, present): Isola Day
   Celebration (0x414AD1), Blessings Day Celebration (0x414B4E), Day of Honor (0x414DE1), The Especially Offensive
   Cloud (0x414F44), The Bottle of Spicy Juice (0x414F81), Mushroom Day! (0x415101), The Bed Bugs' "Let it go"
   (0x4156DE), Innovation in Farming's children (0x417092).

   INSTALLED with the row only (it is in the installed patches' list at start-up), every site verified first, all or
   none, after the companion's own install (hv_stock_install); nothing is written to the executable's file.  A
   puzzle's Heathen (roles 12-17) is never drawn or moved by any of it: the stock effects can not be told rather than
   made, so the owner's "EXEMPT from any actual effects" keeps them out of the stock events. */

#define HV_GAME 5
#define HV_PICKER 0x471870u
#define HV_GROUP 0x470C60u
#define HV_STOP 0x473440u
#define HV_BEHAVE 0x465580u
#define HV_PRESENT 0x466170u
#define HV_RAND 0x403660u
#define HV_PRESENT_BYTE 0x1CD4u          /* 0x466170's "present" test */
#define HV_FACTION 0x1CECu
#define HV_FAITH 0x1CF0u
#define HV_ROLE 0x1CFCu
#define HV_AGE 0x1B8Cu
#define HV_SEX 0x1B90u
#define HV_HEALTH 0x1C40u
#define HV_SICK 0x1C48u
#define HV_SETTER_A 0x2F14u               /* the faction setter 0x466880's two other fields */
#define HV_SETTER_B 0x2F40u

enum { HV_BELIEVER = 1, HV_HEATHEN_SIDE = 2 };
typedef struct {
    unsigned int va;                      /* the `call 0x471870` */
    unsigned char store, other;           /* the event object's field it fills; the other part's (HV_HEATHEN_SIDE) */
    unsigned char side;
} hv_pick_site;

static const hv_pick_site HV_PICKS[] = {
    { 0x414BB4u, 4, 0, HV_BELIEVER },     /* The Vision, The Mask, Doubt, The Aphids in the Noni Bush, The Straw Hat */
    { 0x4150D7u, 4, 0, HV_BELIEVER },     /* Mushroom Day! */
    { 0x415664u, 4, 0, HV_BELIEVER },     /* The Bed Bugs */
    { 0x415848u, 4, 0, HV_BELIEVER },     /* The Heathen Toy: the child */
    { 0x415877u, 0xC, 4, HV_HEATHEN_SIDE },   /* ... the toy's owner */
    { 0x415984u, 4, 0, HV_BELIEVER },     /* The Daredevil Jump: the jumper */
    { 0x4159B5u, 0xC, 0, HV_BELIEVER },   /* ... the second villager (stock: may be the same one) */
    { 0x415C65u, 4, 0, HV_BELIEVER },     /* The Spa, The Cracked Mask */
    { 0x415C9Du, 0xC, 4, HV_HEATHEN_SIDE },   /* ... the Heathen child */
    { 0x415E48u, 4, 0, HV_BELIEVER },     /* Spying on the Heathens, The Missing Kids: the child */
    { 0x415E80u, 0xC, 4, HV_HEATHEN_SIDE },   /* ... the Heathen child */
    { 0x415F88u, 4, 0, HV_BELIEVER },     /* You're Doing It Wrong! */
    { 0x4162A8u, 0xC, 0, HV_BELIEVER },   /* Outreach?: the guide */
    { 0x4162E0u, 4, 0xC, HV_HEATHEN_SIDE },   /* ... the envoy */
    { 0x41647Eu, 4, 0, HV_BELIEVER },     /* The Advanced Artifacts */
    { 0x416601u, 4, 0, HV_BELIEVER },     /* Trick Or Trade */
    { 0x416717u, 4, 0, HV_BELIEVER },     /* The Migrating Fruit Bats */
    { 0x416AD7u, 4, 0, HV_BELIEVER },     /* The Strange Nectar */
    { 0x416FD9u, 4, 0, HV_BELIEVER },     /* Innovation in Farming (the storyteller's listener) */
};
#define HV_PICK_COUNT ((int)(sizeof HV_PICKS / sizeof HV_PICKS[0]))

static const unsigned int HV_GROUPS[] = {
    0x414AD1u, 0x414B4Eu, 0x414DE1u, 0x414F44u, 0x414F81u, 0x415101u, 0x4156DEu, 0x417092u,
};
#define HV_GROUP_COUNT ((int)(sizeof HV_GROUPS / sizeof HV_GROUPS[0]))

/* The events whose believer part's Faith a drawn Heathen keeps (their vtables, 0x417790's slot table): The Vision
   (slot 5), The Mask (12), The Spa (34), Doubt (35), The Cracked Mask (47); the part is [object+4] in each. */
static const unsigned int HV_FAITH_EVENTS[] = { 0x497674u, 0x497D7Cu, 0x497E9Cu, 0x497EE4u, 0x49824Cu };

typedef void *(__fastcall *hv_picker_fn)(void *self, void *unused_edx, int min_age, int max_age, int sex,
                                         int pregnant, int sick, int skill, int min_skill, int must_pregnant,
                                         int must_sick, int *count, int heathen_only, int a12, int allow_heathen,
                                         int allow_role);
typedef int (__fastcall *hv_group_fn)(void *self, void *unused_edx, int behaviour, int min_age, int max_age, int sex,
                                      int *count, int min_count);
typedef int (__cdecl *hv_rand_fn)(int bound);

static int hv_installed;
static unsigned char *hv_obj;             /* the event object (ESI) of the call in progress */
static unsigned int hv_ret;               /* that call's own return address (its site + 5) */

static int hv_on(void) {
    return hv_installed && cg_heathens_row(HV_GAME);
}

static const hv_pick_site *hv_site_at(unsigned int va) {
    int i;
    for (i = 0; i < HV_PICK_COUNT; ++i) {
        if (HV_PICKS[i].va == va) {
            return &HV_PICKS[i];
        }
    }
    return NULL;
}

/* Pick Island Event's armed outcome names the villager for this event: the game's own draw (story_outcomes.inc). */
static int hv_victim_chosen(void) {
    const oc_game *g = &OC_GAMES[HV_GAME];
    int i;
    if (oc.state == OC_IDLE || oc.game != HV_GAME || oc.event == NULL) {
        return 0;
    }
    for (i = 0; i < oc.event->control_count && i < OC_MAX_CONTROLS; ++i) {
        if (g->controls[oc.event->control_first + i].kind == OC_VICTIM && oc.set.choice[i] != OC_RANDOM) {
            return 1;
        }
    }
    return 0;
}

#define HV_STOCK_ARGS min_age, max_age, sex, pregnant, sick, skill, min_skill, must_pregnant, must_sick

/* In place of the event's `call 0x471870` (ECX the manager; the 14 arguments on the stack; ret 0x38). */
static void *__fastcall hv_pick(void *mgr, void *unused_edx, int min_age, int max_age, int sex, int pregnant,
                                int sick, int skill, int min_skill, int must_pregnant, int must_sick, int *count,
                                int heathen_only, int a12, int allow_heathen, int allow_role) {
    hv_picker_fn pick = (hv_picker_fn)(uintptr_t)HV_PICKER;
    const hv_pick_site *s = hv_ret != 0 ? hv_site_at(hv_ret - 5u) : NULL;   /* the call's own site */
    unsigned char *obj = hv_obj;
    void *b, *h, *other = NULL;
    int nb = 0, nh = 0;
    (void)unused_edx;
    hv_ret = 0;
    hv_obj = NULL;
    if (s == NULL || !hv_on()) {
        return pick(mgr, NULL, HV_STOCK_ARGS, count, heathen_only, a12, allow_heathen, allow_role);
    }
    if (s->side == HV_BELIEVER) {
        if (heathen_only || allow_heathen || must_sick || hv_victim_chosen()) {
            return pick(mgr, NULL, HV_STOCK_ARGS, count, heathen_only, a12, allow_heathen, allow_role);
        }
        b = pick(mgr, NULL, HV_STOCK_ARGS, &nb, heathen_only, a12, allow_heathen, allow_role);
        h = pick(mgr, NULL, min_age, max_age, sex, pregnant, 0, skill, min_skill, must_pregnant, 0, &nh, 1, a12, 1,
                 0);
        if (count != NULL) {
            *count = nb + nh;
        }
        if (h == NULL || nh <= 0) {
            return b;
        }
        if (b == NULL || nb <= 0) {
            return h;
        }
        return ((hv_rand_fn)(uintptr_t)HV_RAND)(nb + nh) < nb ? b : h;
    }
    /* A Heathen's part: never the Heathen the believer's part already took. */
    __try {
        other = obj != NULL ? *(void **)(obj + s->other) : NULL;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        other = NULL;
    }
    h = pick(mgr, NULL, HV_STOCK_ARGS, &nh, heathen_only, a12, allow_heathen, allow_role);
    if (other != NULL && h == other) {
        /* drawn again with that Heathen out of the picker's sight for this one call (its "present" byte +0x1CD4,
           put back at once): every other Heathen the call takes is as likely */
        unsigned char *o = (unsigned char *)other, present = 0;
        h = NULL;
        nh = 0;
        __try {
            present = o[HV_PRESENT_BYTE];
            o[HV_PRESENT_BYTE] = 0;
            h = pick(mgr, NULL, HV_STOCK_ARGS, &nh, heathen_only, a12, allow_heathen, allow_role);
        } __finally {
            o[HV_PRESENT_BYTE] = present;
        }
    }
    if (count != NULL) {
        *count = nh;
    }
    return h;
}

/* A direct site's `call` lands here: the event object and the return address noted, then hv_pick with the stack as
   the game made it. */
__declspec(naked) static void hv_pick_thunk(void) {
    __asm {
        mov hv_obj, esi
        mov eax, dword ptr [esp]
        mov hv_ret, eax
        jmp hv_pick
    }
}

/* story_outcomes.inc oc_scope_enter: a scope call at `va` (ESI in regs[1]) -- hv_pick when it is one of these sites
   and the row's draw is on, else 0 (the game's own picker). */
static unsigned int hv_scope_target(unsigned int va, const unsigned int *regs) {
    if (!hv_on() || hv_site_at(va) == NULL) {
        return 0;
    }
    hv_obj = (unsigned char *)(uintptr_t)regs[1];
    hv_ret = va + 5u;
    return (unsigned int)(uintptr_t)hv_pick;
}

/* In place of a group event's `call 0x470C60` (ECX the manager; 6 arguments; ret 0x18). */
static int __fastcall hv_group(void *mgr, void *unused_edx, int behaviour, int min_age, int max_age, int sex,
                               int *count, int min_count) {
    const ce_adapter *a;
    int answer, i;
    (void)unused_edx;
    answer = ((hv_group_fn)(uintptr_t)HV_GROUP)(mgr, NULL, behaviour, min_age, max_age, sex, count, min_count);
    if (!hv_on() || min_count > 0 || (a = ce_adapter_for(HV_GAME)) == NULL) {
        return answer;
    }
    __try {
        for (i = 0; i < a->record_count; ++i) {
            unsigned char *r = (unsigned char *)a->record(i);
            int role, age;
            unsigned char flag = 0;
            if (r == NULL || r[HV_FACTION] == 0) {
                continue;
            }
            role = *(const int *)(r + HV_ROLE);
            age = *(const int *)(r + HV_AGE);
            if ((role >= 12 && role <= 17) || r[HV_SICK] != 0 || *(const int *)(r + HV_HEALTH) <= 0
                || (TC1(HV_PRESENT, r, 0) & 0xFF) == 0
                || (min_age != -1 && age < min_age) || (max_age != -1 && age >= max_age)
                || (sex != -1 && *(const int *)(r + HV_SEX) != sex)) {
                continue;
            }
            TC0(HV_STOP, r);
            TC2(HV_BEHAVE, r, behaviour, (int)(uintptr_t)&flag);
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
    return answer;
}

/* ---- the Faith part kept (around the event's apply, story_outcomes.inc oc_vv5_*_stub) ---- */
static struct {
    unsigned char *record;
    int faith, a, b;
} hv_kept;

static void __cdecl hv_apply_begin(void *object) {
    unsigned char *r;
    int i, hit = 0;
    hv_kept.record = NULL;
    if (!hv_on() || object == NULL) {
        return;
    }
    __try {
        for (i = 0; i < (int)(sizeof HV_FAITH_EVENTS / sizeof HV_FAITH_EVENTS[0]); ++i) {
            hit |= *(const unsigned int *)object == HV_FAITH_EVENTS[i];
        }
        r = hit ? *(unsigned char **)((unsigned char *)object + 4) : NULL;
        if (r != NULL && story_record_index(HV_GAME, r) >= 0 && r[HV_FACTION] != 0) {
            hv_kept.record = r;
            hv_kept.faith = *(int *)(r + HV_FAITH);
            hv_kept.a = *(int *)(r + HV_SETTER_A);
            hv_kept.b = *(int *)(r + HV_SETTER_B);
            *(int *)(r + HV_FAITH) = -100;    /* no change can reach 0: never the conversion */
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        hv_kept.record = NULL;
    }
}

static void __cdecl hv_apply_end(void *object) {
    unsigned char *r = hv_kept.record;
    (void)object;
    hv_kept.record = NULL;
    if (r == NULL) {
        return;
    }
    __try {
        *(int *)(r + HV_FAITH) = hv_kept.faith;
        *(int *)(r + HV_SETTER_A) = hv_kept.a;
        *(int *)(r + HV_SETTER_B) = hv_kept.b;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

/* ---- installing ---- */
static int hv_is_scope(unsigned int va) {
    const oc_game *g = &OC_GAMES[HV_GAME];
    int i;
    for (i = 0; i < g->scope_count; ++i) {
        if (g->scopes[i].va == va) {
            return 1;
        }
    }
    return 0;
}

static void hv_call_bytes(unsigned char *out, unsigned int va, unsigned int target) {
    unsigned int rel = target - (va + 5u);
    out[0] = 0xE8;
    memcpy(out + 1, &rel, 4);
}

/* After the companion's own install (VvfpStoryArm): every direct site must hold its stock call, every other picker
   site must be one of the companion's scope calls -- then all are written, or none. */
static int hv_stock_install_now(void) {
    static vvfp_site_write writes[HV_PICK_COUNT + HV_GROUP_COUNT];
    static unsigned char expect[HV_PICK_COUNT + HV_GROUP_COUNT][5];
    int i, n = 0;
    if (hv_installed) {
        return 1;
    }
    if (install_state[HV_GAME] != 1) {
        return 0;
    }
    for (i = 0; i < HV_PICK_COUNT; ++i) {
        hv_call_bytes(expect[n], HV_PICKS[i].va, HV_PICKER);
        if (mem_matches(HV_PICKS[i].va, expect[n], 5)) {
            vvfp_site_branch(&writes[n], HV_PICKS[i].va, 5, expect[n], 0xE8, (const void *)hv_pick_thunk);
            ++n;
        } else if (!hv_is_scope(HV_PICKS[i].va)) {
            return 0;
        }
    }
    for (i = 0; i < HV_GROUP_COUNT; ++i) {
        hv_call_bytes(expect[n], HV_GROUPS[i], HV_GROUP);
        if (!mem_matches(HV_GROUPS[i], expect[n], 5)) {
            return 0;
        }
        vvfp_site_branch(&writes[n], HV_GROUPS[i], 5, expect[n], 0xE8, (const void *)hv_group);
        ++n;
    }
    if (!vvfp_install_sites(writes, n)) {
        return 0;
    }
    hv_installed = 1;
    return 1;
}

/* VvfpStoryArm, New Believers: with the row in the installed patches' list. */
static void hv_stock_install(void) {
    if (cg_heathens_row(HV_GAME)) {
        (void)hv_stock_install_now();
    }
}

#ifdef VVFP_TEST
/* The test build: the sites installed whatever the list (the tests set the row after the companion's install), 1 when
   they are in place. */
__declspec(dllexport) int __stdcall VvfpStoryProbeHeathenStock(void) {
    return hv_stock_install_now();
}
#endif
