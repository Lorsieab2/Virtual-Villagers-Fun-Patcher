/* The Secret City, The Tree of Life and New Believers: the Death records,
   written at the burial (with the grave's skill line and epitaph, from the
   Roster of the Dead entry the burial has just written) and at the removal
   of an unburied body.  The cause is the game's own, kept on the record
   beside health (VV3 +0xE7C, VV4 and VV5 +0x1C44), which the grave dialog
   words.  Included by vvfp_cause_of_death.c.

   THE BURIAL.  The burial clears the body's presence byte (VV3 0x462293,
   VV4 0x46A977, VV5 0x473F8F) and then calls the Roster of the Dead writer
   (VV3 0x454FF0, VV4 0x45D470, VV5 0x464C70) with the record; the writer
   takes the first free entry of 500, fills it, and on The Secret City gives
   the first 50 a gravestone (with the epitaph) as well.  Two hooks:

     the writer's shared exit, reached only when an entry was written:
       VV3 0x4551D7  edi = the entry's slot, ebp = the record
       VV4 0x45D62E  ebp = the slot, [esp+0x10] = the record
       VV5 0x464E51  the same
     right after the writer's call, reached on every burial:
       VV3 0x4622C8  edi = the record
       VV4 0x46A996  esi = the record
       VV5 0x473FAE  esi = the record

   The record is written at the second; a burial whose writer found no free
   entry gets "no grave (the Roster of the Dead was full)".

   THE UNBURIED BODY.  After 240 minutes the game removes a body nobody
   buried:
       VV3 0x45F437  the `div` whose quotient (the minutes) decides it: the
                     removal follows when it is 0xF0 or more; esi = record +
                     0xF10
       VV4 0x4664B4  `lea edi, [esi-0x1cc7]`, reached only once it is due
       VV5 0x46FF12  the store itself, esi = the record */

struct v345_layout {
    unsigned int roster;         /* the Roster of the Dead's first entry */
    unsigned int entry_stride;
    unsigned int e_age, e_job, e_value, e_cause, e_epitaph;   /* e_epitaph 0: on the gravestone */
    unsigned int cause;          /* the record's own cause */
};

static const struct v345_layout V345[6] = {
    { 0 }, { 0 }, { 0 },
    /* VV3: entries 0x5973F0 + 0x974, 0x30 each; gravestones 0x5973F0, 0x2C
       each (+4 value, +8 epitaph char[0x20]) for the first 50. */
    { 0x5973F0u + 0x974u, 0x30u, 0x1Cu, 0x20u, 0x24u, 0x2Cu, 0u, 0xE7Cu },
    { 0x5025C8u, 0x5Cu, 0x1Cu, 0x28u, 0x2Cu, 0x34u, 0x38u, 0x1C44u },
    { 0x5481A8u, 0x5Cu, 0x1Cu, 0x28u, 0x2Cu, 0x34u, 0x38u, 0x1C44u },
};

#define V345_ENTRIES 500
#define VV3_GRAVESTONES 0x5973F0u
#define VV3_GRAVESTONE_STRIDE 0x2Cu

/* The grave dialog's profession words (VV3 0x41E6D0, VV4 0x41BBA0, VV5
   0x41C3F0); New Believers adds the Devotee. */
static const char *const V345_JOBS[6] = {
    "Farmer", "Parent", "Doctor", "Scientist", "Builder", "Devotee"
};

static unsigned char *v345_entry(int slot) {
    if (slot < 0 || slot >= V345_ENTRIES) {
        return NULL;
    }
    return (unsigned char *)(uintptr_t)(V345[g_game].roster + (unsigned int)slot * V345[g_game].entry_stride);
}

/* The skill line the dialog shows under "Job", as it builds it:
   "Untrained" with no profession or a best skill under 20; otherwise the
   rank -- "Trainee" under 50, "Adept" under 88, "Master" -- and the
   profession; The Tree of Life calls everyone under 280 age units with a
   skill of 20 or more an "Apprentice". */
static void v345_title(const unsigned char *entry, char *out) {
    const struct v345_layout *l = &V345[g_game];
    int job = *(const int *)(entry + l->e_job);
    int value = *(const int *)(entry + l->e_value);
    int age = *(const int *)(entry + l->e_age);
    const char *rank;
    if (job < 0 || job > (g_game == 5 ? 5 : 4) || value < 20) {
        lstrcpyA(out, "Untrained");
        return;
    }
    if (g_game == 4 && age < 0x118) {
        rank = "Apprentice";
    } else {
        rank = value < 50 ? "Trainee" : value < 88 ? "Adept" : "Master";
    }
    wsprintfA(out, "%s %s", rank, V345_JOBS[job]);
}

/* What the writer's exit reported: the entry it wrote and for whom. */
static const unsigned char *written_record;
static int written_slot = -1;

static void v345_written(int site, const unsigned int *regs) {
    (void)site;
    if (g_game == 3) {
        written_record = (const unsigned char *)(uintptr_t)regs[R_EBP];
        written_slot = (int)regs[R_EDI];
    } else {
        written_record = (const unsigned char *)(uintptr_t)reg_stack(regs, 0x10);
        written_slot = (int)regs[R_EBP];
    }
}

static void v345_buried(int site, const unsigned int *regs) {
    const unsigned char *record = (const unsigned char *)(uintptr_t)regs[g_game == 3 ? R_EDI : R_ESI];
    const unsigned char *entry = NULL;
    char title[64];
    char epitaph[64];
    int index = cod_index_of(record);
    (void)site;
    if (index < 0 || cod_temporary(index, record) || rec_lookalike(record)) {
        written_record = NULL;
        return;
    }
    COD_COUNT(burials);
    roster_departed(index, record);
    if (written_record == record) {
        entry = v345_entry(written_slot);
    }
    written_record = NULL;
    if (entry == NULL) {
        cod_log_death(record, *(const int *)(record + V345[g_game].cause),
                      "no grave (the Roster of the Dead was full)", NULL);
        return;
    }
    v345_title(entry, title);
    if (g_game != 3) {
        cod_printable(epitaph, sizeof epitaph, (const char *)entry + V345[g_game].e_epitaph, EPITAPH_TEXT);
    } else if (written_slot < 50) {
        cod_printable(epitaph, sizeof epitaph,
                      (const char *)(uintptr_t)(VV3_GRAVESTONES + (unsigned int)written_slot * VV3_GRAVESTONE_STRIDE + 8u),
                      EPITAPH_TEXT);
    } else {
        lstrcpyA(epitaph, "(none: only the first 50 graves get a gravestone)");
    }
    /* The cause the entry keeps: the record's own, copied by the writer. */
    cod_log_death(record, *(const int *)(entry + V345[g_game].e_cause), title, epitaph);
}

static void v345_decayed_record(const unsigned char *record) {
    int index = cod_index_of(record);
    if (index < 0 || cod_temporary(index, record) || rec_lookalike(record) || !rec_present(record)
        || rec_health(record) > 0) {
        return;
    }
    roster_departed(index, record);
    cod_log_death(record, *(const int *)(record + V345[g_game].cause), NO_GRAVE_NEVER_BURIED, NULL);
}

/* VV3 0x45F437 `div dword [ecx+0x12f20]`: edx:eax / the divisor >= 0xF0. */
static void vv3_decay(int site, const unsigned int *regs) {
    unsigned int divisor = *(const unsigned int *)(uintptr_t)(regs[R_ECX] + 0x12F20u);
    unsigned long long dividend = ((unsigned long long)regs[R_EDX] << 32) | regs[R_EAX];
    (void)site;
    if (divisor != 0 && dividend / divisor >= 0xF0u) {
        v345_decayed_record((const unsigned char *)(uintptr_t)(regs[R_ESI] - 0xF10u));
    }
}

static void vv4_decay(int site, const unsigned int *regs) {
    (void)site;
    v345_decayed_record((const unsigned char *)(uintptr_t)(regs[R_ESI] - 0x1CC7u));
}

static void vv5_decay(int site, const unsigned int *regs) {
    (void)site;
    v345_decayed_record((const unsigned char *)(uintptr_t)regs[R_ESI]);
}

static void v345_sites(void) {
    switch (g_game) {
    case 3:
        cod_add(0x4551D7u, "5D5B5FB001", v345_written);
        cod_add(0x4622C8u, "5F5E5D" "C7432801000000", v345_buried);
        cod_add(0x45F437u, "F7B1202F0100", vv3_decay);
        break;
    case 4:
        cod_add(0x45D62Eu, "5EB0015D59", v345_written);
        cod_add(0x46A996u, "5E" "C7435401000000", v345_buried);
        cod_add(0x4664B4u, "8DBE39E3FFFF", vv4_decay);
        break;
    case 5:
        cod_add(0x464E51u, "5EB0015D59", v345_written);
        cod_add(0x473FAEu, "5E" "C7435401000000", v345_buried);
        cod_add(0x46FF12u, "889ED41C0000", vv5_decay);
        break;
    default:
        break;
    }
}
