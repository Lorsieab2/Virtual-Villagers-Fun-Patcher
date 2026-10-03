/* The stock no-skeleton removals of a living villager in A New Home and The
   Lost Children: the store that clears the presence byte (with the
   instruction after it when it is shorter than a jmp), the record, and the
   event in plain words.  Included by cod_gone.inc.

   The Lost Children's The Strange Request also clears a record (0x420899,
   and 0x4208FF on "Refuse"), but only ever the stranger its own setup made
   for the event (0x41F95E): he is never one of the tribe, and is kept out
   of the roster (cod_roster_sites.inc).  0x4208FF is shared with The Voices
   In The Brush, whose subject is a villager: that one is logged. */

static const struct gone_site GONE_VV1[] = {
    /* The Mysterious Face -> "take a closer look": lost on 0-50 of rand(100). */
    { 0x41979Du, "885C0228" "8B8EA4500000", R_EDX, R_EAX,
      "Took a closer look at The Mysterious Face and was never heard from again" },
    /* The Book -> "read it": always. */
    { 0x41A272u, "885C1128" "5B", R_ECX, R_EDX,
      "Read The Book and left the village" },
};

static const struct gone_site GONE_VV2[] = {
    /* A Dangerous Mission: up to eight villagers aged 280-499 leave. */
    { 0x433E9Bu, "46" "C6403000", R_EAX, 0,
      "Sailed off for the south shore on A Dangerous Mission" },
    /* The Voices In The Brush -> "investigate", the lost outcome (and The
       Strange Request's "Refuse", whose stranger is skipped). */
    { 0x4208FFu, "885C1130" "5B", R_ECX, R_EDX,
      "Investigated The Voices In The Brush and was never seen again" },
};

static void gone_table_for_game(void) {
    switch (g_game) {
    case 1: gone_table = GONE_VV1; gone_count = (int)(sizeof GONE_VV1 / sizeof GONE_VV1[0]); break;
    case 2: gone_table = GONE_VV2; gone_count = (int)(sizeof GONE_VV2 / sizeof GONE_VV2[0]); break;
    default: gone_table = NULL; gone_count = 0; break;
    }
}
