/* A Custom Island Event arrives within seconds -- all five games, custom
   events only (the owner, 2026-10-06: "ok yes for everything", "THEY SHOULD
   ONLY APPLY TO CUSTOM ISLAND EVENTS", "for all 5 games").

   WHY ONE COULD TAKE MINUTES.  Once its countdown is due, each game's event
   trigger runs every 2 seconds and draws ONE random villager from the
   game's own picker:

       A New Home       0x4237DD  call 0x43BCD0(1)   an index; record +0x348 == +0x34C
       The Lost Children 0x42EEED call 0x44BAE0(1)   an index; record +0x530 == +0x534
       The Secret City  0x468757  call 0x45C9D0(1)   an index; valid by 0x45EE60,
                                                     record by 0x45C840: +0xDC4 == +0xE74
       The Tree of Life 0x43FA70  call 0x4679B0(10)  a record; +0x1B8C == +0x1C3C
       New Believers    0x44272F  call 0x471870(14)  a record; +0x1B8C == +0x1C3C

   and fires only when that villager's age equals its processed age (the
   field the owner's Cheat Engine table calls "Nursing").  A miss is not
   rescheduled: the trigger simply draws again 2 seconds later.  So in a
   village where few villagers match -- anyone made younger by an event or
   an upgrade, or edited -- the event waits a random, sometimes long, time.
   The drawn villager is never used afterwards in any game: the register
   holding it is overwritten before the event is built.

   THE FIX.  Each of those five calls is retargeted to the wrapper below.
   With no Custom Island Event armed for this game it is exactly the stock
   call.  With one armed it asks the stock picker again -- the same
   arguments, so every one of the game's own filters still applies -- until
   it draws a villager the trigger accepts, up to CE_FAST_TRIES times, and
   hands that one back.  The stock check itself is untouched: a village with
   no eligible villager, or none that match, waits exactly as before.  The
   countdown, the frozen-time handling, the population check and the 2 s tick
   are all the game's own. */

#define CE_FAST_TRIES 64

typedef int (*ce_pick_fn)(void *ctx);
typedef int (*ce_fits_fn)(void *ctx, int drawn);

/* The stock picker's first answer when it says "nobody" (`none`), else the
   first of up to CE_FAST_TRIES draws that `fits`, else the last draw. */
static int ce_fast_pick(ce_pick_fn pick, ce_fits_fn fits, int none, void *ctx) {
    int drawn = pick(ctx);
    int tries;
    for (tries = 1; drawn != none && !fits(ctx, drawn) && tries < CE_FAST_TRIES; ++tries) {
        drawn = pick(ctx);
    }
    return drawn;
}

/* The age and its processed age, as the trigger compares them. */
static int ce_ages_match(const unsigned char *record, unsigned int age, unsigned int processed) {
    return record != NULL && *(const int *)(record + age) == *(const int *)(record + processed);
}

/* ---- A New Home, The Lost Children: an index into the array `self` ------- */

typedef struct {
    void *self;
    int arg;
    unsigned int picker, stride, age, processed;
} ce_index_pick;

static int ce_index_draw(void *ctx) {
    ce_index_pick *p = (ce_index_pick *)ctx;
    return TC1(p->picker, p->self, p->arg);
}

static int ce_index_fits(void *ctx, int drawn) {
    ce_index_pick *p = (ce_index_pick *)ctx;
    return drawn >= 0 && drawn < 256
           && ce_ages_match((const unsigned char *)p->self + (size_t)drawn * p->stride, p->age,
                            p->processed);
}

static int __fastcall c1_event_pick(void *self, void *unused_edx, int adults) {
    ce_index_pick p = { self, adults, 0x43BCD0u, 0x3D8u, 0x348u, 0x34Cu };
    (void)unused_edx;
    if (!ce_pending(1)) {
        return TC1(0x43BCD0u, self, adults);
    }
    return ce_fast_pick(ce_index_draw, ce_index_fits, -1, &p);
}

static int __fastcall c2_event_pick(void *self, void *unused_edx, int adults) {
    ce_index_pick p = { self, adults, 0x44BAE0u, 0xE48Cu, 0x530u, 0x534u };
    (void)unused_edx;
    if (!ce_pending(2)) {
        return TC1(0x44BAE0u, self, adults);
    }
    return ce_fast_pick(ce_index_draw, ce_index_fits, -1, &p);
}

/* ---- The Secret City: an index, checked and read through the manager ----- */

static int ce_vv3_fits(void *ctx, int drawn) {
    ce_index_pick *p = (ce_index_pick *)ctx;
    if ((TC1(0x45EE60u, p->self, drawn) & 0xFF) == 0) {
        return 0;                       /* the trigger's own "a live villager" test */
    }
    return ce_ages_match((const unsigned char *)(uintptr_t)TC1(0x45C840u, p->self, drawn),
                         0xDC4u, 0xE74u);
}

static int __fastcall c3_event_pick(void *self, void *unused_edx, int adults) {
    ce_index_pick p = { self, adults, 0x45C9D0u, 0, 0, 0 };
    (void)unused_edx;
    if (!ce_pending(3)) {
        return TC1(0x45C9D0u, self, adults);
    }
    return ce_fast_pick(ce_index_draw, ce_vv3_fits, -1, &p);
}

/* ---- The Tree of Life, New Believers: a record pointer, 0 for nobody ----- */

typedef int (__fastcall *tc10_fn)(void *self, void *unused_edx, int a, int b, int c, int d,
                                   int e, int f, int g, int h, int i, int j);
typedef int (__fastcall *tc14_fn)(void *self, void *unused_edx, int a, int b, int c, int d,
                                   int e, int f, int g, int h, int i, int j, int k, int l,
                                   int m, int n);

typedef struct {
    void *self;
    int args[14];
} ce_record_pick;

static int ce_record_fits(void *ctx, int drawn) {
    (void)ctx;
    return ce_ages_match((const unsigned char *)(uintptr_t)drawn, 0x1B8Cu, 0x1C3Cu);
}

static int ce_vv4_draw(void *ctx) {
    ce_record_pick *p = (ce_record_pick *)ctx;
    const int *a = p->args;
    return ((tc10_fn)(uintptr_t)0x4679B0u)(p->self, NULL, a[0], a[1], a[2], a[3], a[4], a[5],
                                           a[6], a[7], a[8], a[9]);
}

static int ce_vv5_draw(void *ctx) {
    ce_record_pick *p = (ce_record_pick *)ctx;
    const int *a = p->args;
    return ((tc14_fn)(uintptr_t)0x471870u)(p->self, NULL, a[0], a[1], a[2], a[3], a[4], a[5],
                                           a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13]);
}

static int __fastcall c4_event_pick(void *self, void *unused_edx, int a, int b, int c, int d,
                                    int e, int f, int g, int h, int i, int j) {
    ce_record_pick p = { self, { a, b, c, d, e, f, g, h, i, j } };
    (void)unused_edx;
    if (!ce_pending(4)) {
        return ce_vv4_draw(&p);
    }
    return ce_fast_pick(ce_vv4_draw, ce_record_fits, 0, &p);
}

static int __fastcall c5_event_pick(void *self, void *unused_edx, int a, int b, int c, int d,
                                    int e, int f, int g, int h, int i, int j, int k, int l,
                                    int m, int n) {
    ce_record_pick p = { self, { a, b, c, d, e, f, g, h, i, j, k, l, m, n } };
    (void)unused_edx;
    if (!ce_pending(5)) {
        return ce_vv5_draw(&p);
    }
    return ce_fast_pick(ce_vv5_draw, ce_record_fits, 0, &p);
}
