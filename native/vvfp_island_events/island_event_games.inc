/* The five games: where their villagers are, what is compared, and the
   routines that apply island events (included by vvfp_island_events.c).

   Every address and offset below was read in each stock executable
   (capstone) and agrees with the parentage exporter's GAME_LAYOUTS and the
   Story / Cheat Upgrades' outcome research (scripts/story_outcomes_vvN.py,
   docs/story-cheat-upgrades.md).  The routines are detoured at their FIRST
   instruction(s) -- whole instructions with no relative operand, re-run from
   a trampoline -- because the Story companion owns the call sites and the
   bytes inside them (0x428777, 0x41A444, 0x42D0C4; 0x4349B2, 0x42244A,
   0x422364; 0x419A29/0x419A41; 0x418749/0x418765). */

#include "../shared/vv3_villager_table.h"
#include "../shared/vv4_villager_table.h"
#include "../shared/vv5_villager_table.h"
#include "../shared/villager_lookalike.h"

/* ---- Reading villagers --------------------------------------------------- */

/* Every active record but the look-alikes the game does not count as
   villagers (The Lost Children's Esteemed Elder statues, The Secret City's
   +0xE94 records, The Tree of Life's ghosts, New Believers' Reanimate in
   progress: native/shared/villager_lookalike.h, as every other companion
   lists villagers), so an event that changes everyone never logs one as a
   changed, Gone or New villager. */
static int array_villagers(unsigned char *array, unsigned int stride, int slots, unsigned int present,
                           unsigned char **out, int capacity) {
    int i, n = 0;
    if (array == NULL || !readable(array, (size_t)stride * (size_t)slots)) {
        return 0;
    }
    for (i = 0; i < slots && n < capacity; ++i) {
        unsigned char *record = array + (size_t)i * stride;
        if (record[present] != 0 && !vv_lookalike(stride, record)) {
            out[n++] = record;
        }
    }
    return n;
}

static int vv1_villagers(unsigned char **out, int capacity) {
    return array_villagers(*(unsigned char **)(uintptr_t)0x48B614u, 0x3D8, 256, 0x28, out, capacity);
}

static int vv2_villagers(unsigned char **out, int capacity) {
    return array_villagers(*(unsigned char **)(uintptr_t)0x499F24u, 0xE48C, 256, 0x30, out, capacity);
}

static int vv3_villagers(unsigned char **out, int capacity) {
    unsigned char *module = (unsigned char *)GetModuleHandleA(NULL);
    unsigned int rva, slots;
    vv3_villager_table(module, &rva, &slots);
    return array_villagers(module + rva + 0x14, 0x1F8C, (int)slots, 0xF10, out, capacity);
}

static int vv4_villagers(unsigned char **out, int capacity) {
    unsigned char *module = (unsigned char *)GetModuleHandleA(NULL);
    unsigned int rva, slots;
    vv4_villager_table(module, &rva, &slots);
    return array_villagers(module + rva + 0x44, 0x2E3C, (int)slots, 0x1CC4, out, capacity);
}

static int vv5_villagers(unsigned char **out, int capacity) {
    unsigned char *module = (unsigned char *)GetModuleHandleA(NULL);
    unsigned int rva, slots;
    vv5_villager_table(module, &rva, &slots);
    return array_villagers(module + rva + 0x48, 0x2F44, (int)slots, 0x1CD4, out, capacity);
}

/* ---- What is compared (whitelists: a record also holds its position, pose
   and current action, which an event's celebration or swim changes for a
   moment and which are no lasting change) ----------------------------------

   An event can start a pregnancy (a conception), and the conception writes
   more on the mother than her Pregnant flag: how many babies, and in the
   later games the father's name, head and body copied onto her by value.
   Those are compared too, at the parentage exporter's offsets
   (native/parentage_export/parentage_export.c GAME_LAYOUTS: father,
   father_head_copy, father_body_copy, litter; the father's name 0x18 bytes,
   the conception's own copy count).  A New Home keeps no trace of the father
   on the mother (its parentage exporter captures him from the caller), so
   its table has only the babies, and the expected father comes from the
   Show Parents companion's record of the conception (vv1_expected_father
   below), printed in the same three lines.  These fields are marked `conception`: when the
   event makes a woman pregnant they are printed whole ("Babies nursing:
   2", "Expected father: Rongo"), even when the last pregnancy left the same
   values there (compare() in vvfp_island_events.c).  A New Home and The Lost
   Children store 0 for one baby (F_BABIES prints it as 1 while she is
   pregnant), the later games 1.

   The Lost Children (its Strange Request and Gong of Wonder can start one):
   the conception routine 0x44B980 sprintf's the father's name to +0x5C0
   (0x44BA35..0x44BA49), stores his head at +0x5E0 (0x44BA43) and body at
   +0x5DC (0x44BA24) -- every caller pushes his +0x54C, +0x548 and +0x564
   -- and 2 or 3 at +0x544 for twins or triplets (0x44BA82, 0x44BAB6), 0 for
   one baby.  The delivery 0x43BE52..0x43BE72 hands exactly those four to the
   child's creation, and clears +0x544 at 0x43BF85.  Checked against the
   owner's real saves, not a harness: in 38 save files from five of the
   owner's VV2 save folders (the unpatched game's own of 2023 among them)
   every pregnant woman's +0x5C0 names a villager of
   the save whose own head and body are her +0x5E0 / +0x5DC (no mismatch),
   and Topaz Temitope's +0x544 of 2 is the "Babies nursing: 2" of her
   conception in the owner's Births and Conceptions log, whose delivery the
   same log records as two Twin births.  The Gong of Wonder's pregnancies
   (its case 0x44EAA5) have no father: the game itself writes "?", head 0
   and body 0 (the pushes at 0x44EB1D..0x44EB25),
   and that is what is printed, as the Births and Conceptions log prints it. */

static const struct field VV1_FIELDS[] = {
    { "Health", 0x344, F_INT, 0 },
    { "Age", 0x348, F_INT, 0 },
    { "Sex", 0x350, F_SEX12, 0 },
    { "Sick", 0x354, F_FLAG, 0 },
    { "Nursing", 0x358, F_FLAG, 0 },
    { "Babies nursing", 0x35C, F_BABIES, 0x358, 1 },
    { "Head", 0x360, F_INT, 0 },
    { "Body", 0x364, F_INT, 0 },
    { "Name", 0x370, F_TEXT, 0x1C },
    { "Likes", 0x398, F_LIKES, 4 },
    { "Dislikes", 0x3A8, F_DISLIKES, 4 },
    { "Breeding", 0x3BC, F_INT, 0 },
    { "Building", 0x3C0, F_INT, 0 },
    { "Farming", 0x3C4, F_INT, 0 },
    { "Healing", 0x3C8, F_INT, 0 },
    { "Research", 0x3CC, F_INT, 0 },
};

static const struct field VV2_FIELDS[] = {
    { "Health", 0x52C, F_INT, 0 },
    { "Age", 0x530, F_INT, 0 },
    { "Sex", 0x538, F_SEX12, 0 },
    { "Sick", 0x53C, F_FLAG, 0 },
    { "Nursing", 0x540, F_FLAG, 0 },
    { "Babies nursing", 0x544, F_BABIES, 0x540, 1 },
    { "Expected father", 0x5C0, F_TEXT, 0x18, 1 },
    { "Expected father's head", 0x5E0, F_INT, 0, 1 },
    { "Expected father's body", 0x5DC, F_INT, 0, 1 },
    { "Head", 0x548, F_INT, 0 },
    { "Body", 0x54C, F_INT, 0 },
    { "Name", 0x564, F_TEXT, 0x18 },
    { "Likes", 0x5F0, F_LIKES, 62 },
    { "Dislikes", 0x6E8, F_DISLIKES, 62 },
    { "Parenting", 0x7E4, F_INT, 0 },
    { "Building", 0x7E8, F_INT, 0 },
    { "Farming", 0x7EC, F_INT, 0 },
    { "Healing", 0x7F0, F_INT, 0 },
    { "Research", 0x7F4, F_INT, 0 },
    { "Esteemed Elder", 0x7FC, F_BYTE_FLAG, 0 },
    /* The parents (the Custom Island Event can change them; the parentage exporter's offsets). */
    { "Father", 0x57D, F_NAME, 0x18 },
    { "Father's head", 0x5B0, F_INT, 0 },
    { "Father's body", 0x5B4, F_INT, 0 },
    { "Mother", 0x596, F_NAME, 0x18 },
    { "Mother's head", 0x5B8, F_INT, 0 },
    { "Mother's body", 0x5BC, F_INT, 0 },
};

static const struct field VV3_FIELDS[] = {
    { "Age", 0xDC4, F_INT, 0 },
    { "Sex", 0xDC8, F_SEX01, 0 },
    { "Name", 0xDD4, F_TEXT, 0x19 },
    { "Head", 0xDF0, F_INT, 0 },
    { "Body", 0xDF4, F_INT, 0 },
    { "Health", 0xE78, F_INT, 0 },
    { "Tribal Chief", 0xE80, F_BYTE_FLAG, 0 },
    { "Sick", 0xE89, F_BYTE_FLAG, 0 },
    { "Nursing", 0xE8C, F_FLAG, 0 },
    { "Babies nursing", 0xE90, F_INT, 0, 1 },
    { "Expected father", 0xE48, F_TEXT, 0x18, 1 },
    { "Expected father's head", 0xE68, F_INT, 0, 1 },
    { "Expected father's body", 0xE64, F_INT, 0, 1 },
    { "Farming", 0xEAC, F_INT, 0 },
    { "Parenting", 0xEB0, F_INT, 0 },
    { "Healing", 0xEB4, F_INT, 0 },
    { "Research", 0xEB8, F_INT, 0 },
    { "Building", 0xEBC, F_INT, 0 },
    { "Likes", 0xFB4, F_LIKES, 3 },
    { "Dislikes", 0xFC0, F_DISLIKES, 3 },
    /* The parents (the Custom Island Event can change them; the parentage exporter's offsets). */
    { "Father", 0xDF8, F_NAME, 0x19 },
    { "Father's head", 0xE2C, F_INT, 0 },
    { "Father's body", 0xE30, F_INT, 0 },
    { "Mother", 0xE11, F_NAME, 0x19 },
    { "Mother's head", 0xE34, F_INT, 0 },
    { "Mother's body", 0xE38, F_INT, 0 },
};

static const struct field VV5_FIELDS[] = {
    { "Age", 0x1B8C, F_INT, 0 },
    { "Sex", 0x1B90, F_SEX01, 0 },
    { "Name", 0x1B9C, F_TEXT, 0x19 },
    { "Head", 0x1BB8, F_INT, 0 },
    { "Body", 0x1BBC, F_INT, 0 },
    { "Health", 0x1C40, F_INT, 0 },
    { "Sick", 0x1C48, F_BYTE_FLAG, 0 },
    { "Nursing", 0x1C4C, F_FLAG, 0 },
    { "Babies nursing", 0x1C50, F_INT, 0, 1 },
    { "Expected father", 0x1C10, F_TEXT, 0x18, 1 },
    { "Expected father's head", 0x1C30, F_INT, 0, 1 },
    { "Expected father's body", 0x1C2C, F_INT, 0, 1 },
    { "Farming", 0x1C5C, F_FLOAT, 0 },
    { "Parenting", 0x1C60, F_FLOAT, 0 },
    { "Healing", 0x1C64, F_FLOAT, 0 },
    { "Research", 0x1C68, F_FLOAT, 0 },
    { "Building", 0x1C6C, F_FLOAT, 0 },
    { "Devotion", 0x1C70, F_FLOAT, 0 },
    { "Heathen", 0x1CEC, F_BYTE_FLAG, 0 },
    { "Faith", 0x1CF0, F_INT, 0 },
    { "Likes", 0x1F5C, F_LIKES, 3 },
    { "Dislikes", 0x1F68, F_DISLIKES, 3 },
    /* The parents (the Custom Island Event can change them; the parentage exporter's offsets). */
    { "Father", 0x1BC0, F_NAME, 0x19 },
    { "Father's head", 0x1BF4, F_INT, 0 },
    { "Father's body", 0x1BF8, F_INT, 0 },
    { "Mother", 0x1BD9, F_NAME, 0x19 },
    { "Mother's head", 0x1BFC, F_INT, 0 },
    { "Mother's body", 0x1C00, F_INT, 0 },
};

static const struct field VV4_FIELDS[] = {
    { "Age", 0x1B8C, F_INT, 0 },
    { "Sex", 0x1B90, F_SEX01, 0 },
    { "Name", 0x1B9C, F_TEXT, 0x19 },
    { "Head", 0x1BB8, F_INT, 0 },
    { "Body", 0x1BBC, F_INT, 0 },
    { "Health", 0x1C40, F_INT, 0 },
    { "Sick", 0x1C48, F_BYTE_FLAG, 0 },
    { "Nursing", 0x1C4C, F_FLAG, 0 },
    { "Babies nursing", 0x1C50, F_INT, 0, 1 },
    { "Expected father", 0x1C10, F_TEXT, 0x18, 1 },
    { "Expected father's head", 0x1C30, F_INT, 0, 1 },
    { "Expected father's body", 0x1C2C, F_INT, 0, 1 },
    { "Farming", 0x1C5C, F_FLOAT, 0 },
    { "Parenting", 0x1C60, F_FLOAT, 0 },
    { "Healing", 0x1C64, F_FLOAT, 0 },
    { "Research", 0x1C68, F_FLOAT, 0 },
    { "Building", 0x1C6C, F_FLOAT, 0 },
    { "Likes", 0x1E60, F_LIKES, 3 },
    { "Dislikes", 0x1E6C, F_DISLIKES, 3 },
    /* The parents (the Custom Island Event can change them; the parentage exporter's offsets). */
    { "Father", 0x1BC0, F_NAME, 0x19 },
    { "Father's head", 0x1BF4, F_INT, 0 },
    { "Father's body", 0x1BF8, F_INT, 0 },
    { "Mother", 0x1BD9, F_NAME, 0x19 },
    { "Mother's head", 0x1BFC, F_INT, 0 },
    { "Mother's body", 0x1C00, F_INT, 0 },
};

/* A New Home's expected father.  The game keeps no trace of him on the
   mother, but its conception hands his record to the parentage exporter
   (FATHER_BY_CAPTURE), which stashes his name, head and body against her
   record index in the Show Parents companion's Parentage Records sidecar
   (native/vv1_parentage, vv1_stash) before the event returns -- the same
   record his Births and Conceptions entry and the child's parents come from.
   Vv1ParentageQueryExpectedFather tells the father the birth will record
   (vv1_expected_father there), and nothing for a woman who is not carrying.
   Without that companion (Show Parents not installed) there is no record of
   him and no line is printed. */
typedef int (__stdcall *vv1_query_expected_fn)(int index, int *out, char *name, int capacity);
static vv1_query_expected_fn g_vv1_query_expected;
static int g_vv1_query_looked;

static unsigned char *vv1_live_array(void) {
    return *(unsigned char **)(uintptr_t)0x48B614u;
}
static unsigned char *(*g_vv1_array)(void) = vv1_live_array;

static int vv1_expected_father(const unsigned char *record, char *name, size_t size, int *head, int *body) {
    unsigned char *array = g_vv1_array();
    size_t span;
    int out[2];
    if (!g_vv1_query_looked) {
        HMODULE module = vvfp_load_patcher_dll("VVFP VV1 Parentage.dll");
        g_vv1_query_looked = 1;
        if (module != NULL) {
            g_vv1_query_expected = (vv1_query_expected_fn)GetProcAddress(module, "Vv1ParentageQueryExpectedFather");
        }
    }
    if (g_vv1_query_expected == NULL || array == NULL || record < array) {
        return 0;
    }
    span = (size_t)(record - array);
    if (span % 0x3D8 != 0 || span / 0x3D8 >= 256) {
        return 0;
    }
    name[0] = '\0';
    out[0] = out[1] = -1;
    if (!g_vv1_query_expected((int)(span / 0x3D8), out, name, (int)size)) {
        return 0;
    }
    name[size - 1] = '\0';
    *head = out[0];
    *body = out[1];
    return name[0] != '\0' || out[0] >= 0 || out[1] >= 0;   /* empty and -1: no father known */
}

#define FIELDS(a) a, (int)(sizeof a / sizeof a[0])

/* copy: bytes kept per villager (the whole record but in The Lost Children,
   whose 58 KB records end long after the last field); pad: the record's
   stride, so the log writer can read a removed villager's copy as a record. */
static const struct game_layout LAYOUT_VV1 = { vv1_villagers, 0x3D8, 0x3D8, 0x370, 0x360, 0x364, FIELDS(VV1_FIELDS),
                                              vv1_expected_father };
static const struct game_layout LAYOUT_VV2 = { vv2_villagers, 0x800, 0xE48C, 0x564, 0x548, 0x54C, FIELDS(VV2_FIELDS) };
static const struct game_layout LAYOUT_VV3 = { vv3_villagers, 0x1F8C, 0x1F8C, 0xDD4, 0xDF0, 0xDF4, FIELDS(VV3_FIELDS) };
static const struct game_layout LAYOUT_VV4 = { vv4_villagers, 0x2E3C, 0x2E3C, 0x1B9C, 0x1BB8, 0x1BBC, FIELDS(VV4_FIELDS) };
static const struct game_layout LAYOUT_VV5 = { vv5_villagers, 0x2F44, 0x2F44, 0x1B9C, 0x1BB8, 0x1BBC, FIELDS(VV5_FIELDS) };

/* ---- The routines that apply events ---------------------------------------- */

/* A click on one of a two-choice dialog's answers: msg 8 and the clicked id
   one of the dialog's two answer buttons (A New Home's encounters and crates,
   The Lost Children's two-choice events: their ids at +0x54 / +0x58; the
   OK at +0x5C applies nothing). */
static int answer_click(const unsigned int *frame) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    return frame[9] == 8 && readable(self + 0x54, 8)
        && (frame[10] == *(const unsigned int *)(self + 0x54) || frame[10] == *(const unsigned int *)(self + 0x58));
}

/* The answer clicked, from the dialog's two button labels. */
static void answer_label(const unsigned int *frame, unsigned int first_label, struct snapshot_text *out) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    int second = frame[10] == *(const unsigned int *)(self + 0x58);
    first_line((const char *)(self + first_label + (second ? 0x100 : 0)), 0x100, out->choice, out->size);
}

/* A New Home: the island event's constructor, whose chooser runs the event
   (and a Custom Island Event, which writes its text into the same buffer);
   the title is the first line of the text it wrote, +0x277F. */
static void title_at_277f(unsigned int self, struct snapshot_text *out) {
    event_text((const char *)(uintptr_t)(self + 0x277F), 0x270F, out);
}

/* A New Home's encounters (0x41A3D0) and crates (0x42D050): the question,
   +0x74, opens with the title; the answers' labels at +0x4E92 / +0x4F92. */
static void vv1_question(const unsigned int *frame, struct snapshot_text *out) {
    event_text((const char *)(uintptr_t)(frame[6] + 0x74), 0x200, out);
    answer_label(frame, 0x4E92, out);
}

static const struct site VV1_SITES[] = {
    { 0x4286B0, { 0x6A, 0xFF, 0x68, 0x9E, 0x56, 0x45, 0x00 }, 7, NULL, NULL, title_at_277f },
    { 0x41A3D0, { 0x83, 0x7C, 0x24, 0x04, 0x08 }, 5, answer_click, vv1_question, NULL },
    { 0x42D050, { 0x83, 0x7C, 0x24, 0x04, 0x08 }, 5, answer_click, vv1_question, NULL },
    { 0 },
};

/* The Lost Children.  Family C (single result): the constructor 0x4348E0,
   whose chooser runs the case (and a Custom Island Event in its place), text
   at +0x277F.  Family A (two choices): the constructor 0x422380, whose setup
   can bring a villager (The Strange Request), question at +0x7C; and its
   click handler 0x4222F0, answers' labels at +0x4E9A / +0x4F9A.  Family B
   (sacks and vials): the resolve 0x438160, question at +0x74, the choice at
   +0x509C (1 the first answer).  The Gong of Wonder: 0x44E8A0. */
static void title_at_7c(unsigned int self, struct snapshot_text *out) {
    event_text((const char *)(uintptr_t)(self + 0x7C), 0x200, out);
}

static void vv2_family_a_click(const unsigned int *frame, struct snapshot_text *out) {
    title_at_7c(frame[6], out);
    answer_label(frame, 0x4E9A, out);
}

static void vv2_family_b(const unsigned int *frame, struct snapshot_text *out) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    event_text((const char *)(self + 0x74), 0x200, out);
    if (readable(self + 0x509C, 4) && *(const int *)(self + 0x509C) >= 1 && *(const int *)(self + 0x509C) <= 2) {
        first_line((const char *)(self + 0x4E92 + (*(const int *)(self + 0x509C) - 1) * 0x100), 0x100,
                   out->choice, out->size);
    }
}

static void vv2_gong(const unsigned int *frame, struct snapshot_text *out) {
    (void)frame;
    _snprintf(out->title, out->size, "The Gong of Wonder");
    out->title[out->size - 1] = '\0';
}

static const struct site VV2_SITES[] = {
    { 0x4348E0, { 0x6A, 0xFF, 0x68, 0x2E, 0x2B, 0x47, 0x00 }, 7, NULL, NULL, title_at_277f },
    { 0x422380, { 0x6A, 0xFF, 0x68, 0xB4, 0x20, 0x47, 0x00 }, 7, NULL, NULL, title_at_7c },
    { 0x4222F0, { 0x83, 0x7C, 0x24, 0x04, 0x08 }, 5, answer_click, vv2_family_a_click, NULL },
    { 0x438160, { 0xB8, 0x30, 0x76, 0x00, 0x00 }, 5, NULL, vv2_family_b, NULL },
    { 0x44E8A0, { 0x53, 0x55, 0x56, 0x57, 0x6A, 0x64 }, 6, NULL, vv2_gong, NULL },
    { 0 },
};

/* The Secret City and New Believers: the event dialog's click handler
   (0x419A00, 0x418720) applies the event on OK (id 1) -- and New Believers'
   custom two-choice events on the answer click (ids 2, 3); the dialog keeps
   the event at +0x50 and its title's text at +0x54 (a char*). */
static int vv3_ok(const unsigned int *frame) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    return frame[9] == 8 && frame[10] == 1 && readable(self + 0x50, 8) && *(const unsigned int *)(self + 0x50) != 0;
}

static int vv5_click(const unsigned int *frame) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    return frame[9] == 8 && frame[10] >= 1 && frame[10] <= 3 && readable(self + 0x50, 8)
        && *(const unsigned int *)(self + 0x50) != 0;
}

static void title_pointer_54(const unsigned int *frame, struct snapshot_text *out) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    if (readable(self + 0x54, 4)) {
        event_text(*(const char *const *)(self + 0x54), 0x200, out);
    }
}

/* The presenters 0x419B30 (The Secret City) and 0x418870 (New Believers) pick the event -- a
   Custom Island Event makes its changes there, before the dialog (the Story companion's pick-site
   stubs 0x419BDB, 0x41895B) -- show it and run its OK inside their own modal loop, which runs only
   the dialog (as The Tree of Life's): one bracket around each, the click handler inside naming the
   event.  The click handler is watched on its own too, for a dialog shown outside them. */
/* The answer clicked in The Secret City's, The Tree of Life's and New
   Believers' two-choice dialog (the stock two-choice events, e.g. The
   Secret City's vtable 0x47EA40, The Tree of Life's The Sealed Box, and a
   Custom Island Event's question), worded as A New Home's and The Lost
   Children's "Choice:" line.  The three dialogs are one design (constructors
   0x4192F0 / 0x417790 / 0x418020): the click handler (0x419A00 / 0x417EA0 /
   0x418720) takes msg 8 with id 2 for the first answer and 3 for the second
   (0x419A7D `cmp edi, 2; setne al` -> the choice +0x830), and the two
   answer buttons are the dialog's +0x85C and +0x860.  Each button's label,
   as shown, is set through its +0x10 control (0x401620 / 0x401600 /
   0x4015D0 -> 0x4012E0 / 0x401140 / 0x401110), which keeps its own copy
   of the text at +0x40. */
static void dialog_answer(const unsigned int *frame, char *out, size_t size) {
    const unsigned char *self = (const unsigned char *)(uintptr_t)frame[6];
    const unsigned char *button, *control;
    out[0] = '\0';
    if (frame[9] != 8 || (frame[10] != 2 && frame[10] != 3) || !readable(self + 0x85C, 8)) {
        return;
    }
    button = *(const unsigned char *const *)(self + (frame[10] == 2 ? 0x85C : 0x860));
    if (button == NULL || !readable(button + 0x10, 4)) {
        return;
    }
    control = *(const unsigned char *const *)(button + 0x10);
    if (control == NULL || !readable(control + 0x40, 4)) {
        return;
    }
    first_line(*(const char *const *)(control + 0x40), 0x100, out, size);
}

/* The Tree of Life's click handler starts no comparison of its own (its
   presenter's bracket is exact, see below): it is watched for the answer. */
static int never(const unsigned int *frame) {
    (void)frame;
    return 0;
}

static const struct site VV3_SITES[] = {
    { 0x419B30, { 0x64, 0xA1, 0x00, 0x00, 0x00, 0x00 }, 6, NULL, NULL, NULL },
    { 0x419A00, { 0x83, 0x7C, 0x24, 0x04, 0x08 }, 5, vv3_ok, title_pointer_54, NULL, dialog_answer },
    { 0 },
};

static const struct site VV5_SITES[] = {
    { 0x418870, { 0x6A, 0xFF, 0x68, 0xDB, 0x15, 0x49, 0x00 }, 7, NULL, NULL, NULL },
    { 0x418720, { 0x83, 0x7C, 0x24, 0x04, 0x08 }, 5, vv5_click, title_pointer_54, NULL, dialog_answer },
    { 0 },
};

/* The Tree of Life: its event presenter 0x418000 picks the event (a Pick or
   Custom Island Event is delivered there, before the dialog), shows it and
   runs the answer and OK inside its own modal loop, which never runs the
   village (0x401D40 calls only the dialog's update and draw) -- so one
   bracket around it is exact.  0x418190 shows one event the same way (the
   Origins Barrel).  The title: the dialog constructor 0x417790 sets +0x54. */
static void title_pointer_54_after(unsigned int self, struct snapshot_text *out) {
    if (readable((const void *)(uintptr_t)(self + 0x54), 4)) {
        event_text(*(const char *const *)(uintptr_t)(self + 0x54), 0x200, out);
    }
}

static const struct site VV4_SITES[] = {
    { 0x418000, { 0x6A, 0xFF, 0x68, 0x1B, 0x66, 0x48, 0x00 }, 7, NULL, NULL, NULL },
    { 0x418190, { 0x6A, 0xFF, 0x68, 0x5B, 0x66, 0x48, 0x00 }, 7, NULL, NULL, NULL },
    { 0x417790, { 0x6A, 0xFF, 0x68, 0xB9, 0x65, 0x48, 0x00 }, 7, NULL, NULL, title_pointer_54_after },
    { 0x417EA0, { 0x83, 0x7C, 0x24, 0x04, 0x08 }, 5, never, NULL, NULL, dialog_answer },
    { 0 },
};

static const struct game_layout *const GAME_LAYOUTS[GAMES + 1] = {
    NULL, &LAYOUT_VV1, &LAYOUT_VV2, &LAYOUT_VV3, &LAYOUT_VV4, &LAYOUT_VV5,
};
static const struct site *const GAME_SITES[GAMES + 1] = {
    NULL, VV1_SITES, VV2_SITES, VV3_SITES, VV4_SITES, VV5_SITES,
};
