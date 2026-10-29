/* Each game's villager records, as far as an original look needs them: the record layout and the identity an
   original is kept by.  Included by vvfp_original_look.c and by original_look_harness.c (which lays out
   records of the real games in memory of its own); the includer defines g_game (1..5). */

/* The record fields an original is kept by -- name, sex and the parents' names (A New Home: the family
   number instead), the presence byte: the same as vvfp_head_look.c's LAYOUT (tests/test_original_look.py
   holds the two together) -- and the head and body the original is made of (the Origins companions'
   VV_HEAD_OFFSET / VV2_HEAD_OFFSET / VV3_HEAD_OFF; the log exporters' record tables). */
typedef struct {
    unsigned int stride;
    unsigned int present;           /* the byte that says a record is held */
    unsigned int name, name_bytes;
    unsigned int sex;
    unsigned int father, mother;    /* the parents' names, 0x19 bytes each (0: none in this game) */
    unsigned int family;            /* A New Home's family number (0: none) */
    unsigned int head, body;
} ol_layout;

static const ol_layout LAYOUT[6] = {
    { 0 },
    { 0x3D8u,  0x28u,   0x370u,  0x1Cu, 0x350u,  0u,      0u,      0x36Cu, 0x360u,  0x364u },
    { 0xE48Cu, 0x30u,   0x564u,  0x18u, 0x538u,  0x57Du,  0x596u,  0u,     0x548u,  0x54Cu },
    { 0x1F8Cu, 0xF10u,  0xDD4u,  0x19u, 0xDC8u,  0xDF8u,  0xE11u,  0u,     0xDF0u,  0xDF4u },
    { 0x2E3Cu, 0x1CC4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1BB8u, 0x1BBCu },
    { 0x2F44u, 0x1CD4u, 0x1B9Cu, 0x19u, 0x1B90u, 0x1BC0u, 0x1BD9u, 0u,     0x1BB8u, 0x1BBCu },
};

static int ol_present(const unsigned char *r) {
    const unsigned char held = r[LAYOUT[g_game].present];
    return g_game == 1 ? held == 1 : held != 0;
}

/* A record the game has named: one made a moment ago and not named yet is seen once it is. */
static int ol_named(const unsigned char *r) {
    return r[LAYOUT[g_game].name] != 0;
}

static unsigned int ol_text(unsigned int h, const unsigned char *text, unsigned int capacity) {
    unsigned int k;
    for (k = 0; k < capacity && text[k]; ++k) {
        h = (h ^ text[k]) * 16777619u;
    }
    return h;
}

static unsigned int ol_mix_dword(unsigned int h, const unsigned char *at) {
    int k;
    for (k = 0; k < 4; ++k) {
        h = (h ^ at[k]) * 16777619u;
    }
    return h;
}

/* What a rename leaves of a villager's identity: the sex and the parents' names (A New Home: the sex and
   the family).  Never 0.  (vvfp_head_look.c hl_stable; src/vv_original_look.py identity.) */
static unsigned int ol_stable(const unsigned char *r) {
    const ol_layout *l = &LAYOUT[g_game];
    unsigned int h = ol_mix_dword(2166136261u, r + l->sex);
    if (l->family != 0) {
        h = ol_mix_dword(h, r + l->family);
    } else {
        h = ol_text(h, r + l->father, 0x19u);
        h = (h ^ 0xFEu) * 16777619u;
        h = ol_text(h, r + l->mother, 0x19u);
        h = (h ^ 0xFDu) * 16777619u;
    }
    return h ? h : 1u;
}

/* A held record's identity: the name and ol_stable's part.  Never 0.  (vvfp_head_look.c hl_identity.) */
static unsigned int ol_identity(const unsigned char *r) {
    const ol_layout *l = &LAYOUT[g_game];
    unsigned int h = ol_text(2166136261u, r + l->name, l->name_bytes);
    h = (h ^ 0xFFu) * 16777619u;
    h = (h ^ ol_stable(r)) * 16777619u;
    return h ? h : 1u;
}

