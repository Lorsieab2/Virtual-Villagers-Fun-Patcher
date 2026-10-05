/* How each villager the game's creators make came, by game: the return
   addresses on the paths into the creators (cod_roster_sites.inc).  Included
   by cod_arrivals.inc.  Static analysis of the stock executables
   (research/stock-executables); the call sites below were enumerated over the
   whole .text section, and no creator or listed helper is reached through a
   pointer.

   READ AT FIXED PLACES, NEVER SEARCHED FOR.  At a creator's hook, `offset`
   is where one return address of the path sits, worked out from the pushes
   of every frame between the hook and that call; the marker applies when
   that slot holds `value` (and, with `need_offset`, a second slot holds
   `need_value`: a shared helper's own return address, so the deeper slot is
   only read on that helper's path).  A search up the stack is not safe: the
   creators' locals are partly uninitialised and can hold return addresses
   left by earlier calls.

   MARK_BIRTH: a child of a delivery (never an arrival, whatever the Births
   log says); MARK_FOUNDER: the new-village seeding; MARK_TEMPORARY: a record
   the game makes and takes away again; MARK_EVENT: `label` is what the
   record's "How:" line says.  A villager made on no listed path is
   "unknown". */

#define MARK_BIRTH 1
#define MARK_FOUNDER 2
#define MARK_EVENT 3
#define MARK_TEMPORARY 4

struct arrival_marker {
    unsigned int site;          /* the hook (cod_roster_sites.inc) */
    unsigned int offset;        /* from the hook's esp */
    unsigned int value;
    unsigned int need_offset;   /* 0: none */
    unsigned int need_value;
    int kind;
    const char *label;
};

/* A New Home: fresh creator 0x43C350 (hook 0x43C39B: sub esp,0x30, four
   pushes and push 0x4E -> its return address at +0x44), copy creator
   0x43C840 (hook 0x43C888: sub esp,0x20, four pushes, push 0x4E -> +0x34).
   All 25 calls, each the creator's own return address:
     the delivery 0x42E900: 0x42EF5F, 0x42EFD0 (fresh), 0x42F021, 0x42F06D
       (copy);
     the Golden Child (villager action 17, 0x424150): 0x4242F8 -- a birth:
       it spends the mother's pregnancy (+0x358/+0x35C cleared at
       0x42431C/0x424326), string 0x14A "...gave birth to a special, golden
       child!";
     the new-village initialiser 0x41C000 (allocates the villager array,
       sets the first island-event time at 0x41C4A9): seven seeding calls;
     the island body 0x427CA0, case 12 (`jmp [eax*4+0x428430]` -> 0x4281E7,
       string 0x1E3 "The Barrel O` Babies"): one to three babies by
       magnitude -- also the Origins purchase, which runs this same case;
     the crate answer handler 0x42B740, case 4 (table 0x42D014 -> 0x42C343;
       its intro string 0x1AD "...watertight"), "Open it": one to three;
     the encounter answer handler 0x419380, variant 3 (table 0x41A384 ->
       0x419697), "Get a closer look", string 0x16A "...welcomes the
       newcomer to the village": one newcomer. */
#define VV1_FRESH 0x43C39Bu, 0x44u
#define VV1_COPY 0x43C888u, 0x34u
static const struct arrival_marker MARKERS_VV1[] = {
    { VV1_FRESH, 0x42EF64u, 0, 0, MARK_BIRTH, NULL },
    { VV1_FRESH, 0x42EFD5u, 0, 0, MARK_BIRTH, NULL },
    { VV1_COPY, 0x42F026u, 0, 0, MARK_BIRTH, NULL },
    { VV1_COPY, 0x42F072u, 0, 0, MARK_BIRTH, NULL },
    { VV1_FRESH, 0x4242FDu, 0, 0, MARK_BIRTH, NULL },
    { VV1_FRESH, 0x41C50Eu, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x41C54Eu, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x41C576u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x41C5B6u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x41C5EBu, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x41C613u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x41C648u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV1_FRESH, 0x428268u, 0, 0, MARK_EVENT, "Barrel of Babies" },
    { VV1_FRESH, 0x4282CBu, 0, 0, MARK_EVENT, "Barrel of Babies" },
    { VV1_FRESH, 0x4282E8u, 0, 0, MARK_EVENT, "Barrel of Babies" },
    { VV1_FRESH, 0x428341u, 0, 0, MARK_EVENT, "Barrel of Babies" },
    { VV1_FRESH, 0x42835Eu, 0, 0, MARK_EVENT, "Barrel of Babies" },
    { VV1_FRESH, 0x42837Bu, 0, 0, MARK_EVENT, "Barrel of Babies" },
    { VV1_FRESH, 0x42C3F4u, 0, 0, MARK_EVENT, "A Mysterious Crate (watertight)" },
    { VV1_FRESH, 0x42C415u, 0, 0, MARK_EVENT, "A Mysterious Crate (watertight)" },
    { VV1_FRESH, 0x42C436u, 0, 0, MARK_EVENT, "A Mysterious Crate (watertight)" },
    { VV1_FRESH, 0x42C4B4u, 0, 0, MARK_EVENT, "A Mysterious Crate (watertight)" },
    { VV1_FRESH, 0x42C4D5u, 0, 0, MARK_EVENT, "A Mysterious Crate (watertight)" },
    { VV1_FRESH, 0x42C553u, 0, 0, MARK_EVENT, "A Mysterious Crate (watertight)" },
    { VV1_FRESH, 0x41974Fu, 0, 0, MARK_EVENT, "The Mysterious Face" },
};

/* The Lost Children: fresh creator 0x44C600 (hook 0x44C84F: sub esp,0x16C,
   four pushes, push ebx -> +0x180; `ret 0x38`), copy creator 0x44CEC0 (hook
   0x44CF04: sub esp,0x20, four pushes, push 0x4E -> +0x34).  The fresh
   creator's callers:
     the world reset 0x424C80: eight seeding calls, right after 0x42529B sets
       the next island event to now + 15 minutes;
     the birth wrapper 0x44F5C0 (its one caller is the delivery, 0x43BE8E):
       the creator returns to 0x44F602;
     the event wrapper 0x44F580 (the creator returns to 0x44F5B0; its own
       caller's return address is then at +0x1BC = 0x180 + 0x38 + 4):
       0x41F95E  The Strange Request's stranger (named "Biggles", taken away
                 by both answers: temporary);
       0x4209A4  The Savage Child, answer 1 (answer handler 0x4204B0 case 4):
                 500 food, one villager;
       0x434102, 0x4341A2, 0x4341C3, 0x434262, 0x434283, 0x4342A4  the
                 island body 0x433600 case 21, The Barrel O` Babies (one, two
                 or three by magnitude) -- also the Origins purchase, which
                 the Origins page delivers as 0x433600(21, 10);
       0x434467, 0x4344A3  case 25, Old Friends (a man and a woman).
   The copy creator's callers: the delivery's twins and triplets (0x43BEDF,
   0x43BF2B) and The Silver Mirror's answer 2 (0x4217F9, answer handler case
   14), which copies the event's villager. */
#define VV2_FRESH 0x44C84Fu, 0x180u
#define VV2_EVENT 0x44C84Fu, 0x1BCu
#define VV2_VIA_EVENT 0x180u, 0x44F5B0u
#define VV2_COPY 0x44CF04u, 0x34u
static const struct arrival_marker MARKERS_VV2[] = {
    { VV2_FRESH, 0x44F602u, 0, 0, MARK_BIRTH, NULL },
    { VV2_COPY, 0x43BEE4u, 0, 0, MARK_BIRTH, NULL },
    { VV2_COPY, 0x43BF30u, 0, 0, MARK_BIRTH, NULL },
    { VV2_FRESH, 0x4252F7u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x42534Cu, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x425380u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x4253B1u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x4253E2u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x425413u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x425439u, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_FRESH, 0x42545Du, 0, 0, MARK_FOUNDER, "Founder" },
    { VV2_EVENT, 0x41F963u, VV2_VIA_EVENT, MARK_TEMPORARY, NULL },
    { VV2_EVENT, 0x4209A9u, VV2_VIA_EVENT, MARK_EVENT, "The Savage Child" },
    { VV2_EVENT, 0x434107u, VV2_VIA_EVENT, MARK_EVENT, "Barrel of Babies" },
    { VV2_EVENT, 0x4341A7u, VV2_VIA_EVENT, MARK_EVENT, "Barrel of Babies" },
    { VV2_EVENT, 0x4341C8u, VV2_VIA_EVENT, MARK_EVENT, "Barrel of Babies" },
    { VV2_EVENT, 0x434267u, VV2_VIA_EVENT, MARK_EVENT, "Barrel of Babies" },
    { VV2_EVENT, 0x434288u, VV2_VIA_EVENT, MARK_EVENT, "Barrel of Babies" },
    { VV2_EVENT, 0x4342A9u, VV2_VIA_EVENT, MARK_EVENT, "Barrel of Babies" },
    { VV2_EVENT, 0x43446Cu, VV2_VIA_EVENT, MARK_EVENT, "Old Friends" },
    { VV2_EVENT, 0x4344A8u, VV2_VIA_EVENT, MARK_EVENT, "Old Friends" },
    { VV2_COPY, 0x4217FEu, 0, 0, MARK_EVENT, "The Silver Mirror" },
};

/* The Secret City: fresh init 0x456120 (hook 0x456326: sub esp,0x140 and
   four pushes -> its return address at +0x150), called only by 0x45F0B0
   (return 0x45F1C9; push esi, 14 arguments, so 0x45F0B0's own return
   address is at +0x190); copy init 0x4566E0 (hook 0x4566EF: three pushes
   and the next call's argument -> +0x10).
     0x45F0B0's callers:
       0x45FF90 (0x45FFD2): the delivery's first child (its one caller);
       0x45FF50 (0x45FF80; its caller's return address at +0x1CC):
         0x414D90 (0x414DB4)  slot 7's apply, The Canoe from the Other Side;
         0x415320 (0x415355, 0x415398, 0x4153DB)  slot 57's apply, Another
                    One of Those Barrels -- also the Origins purchase, which
                    selects this same event object;
       0x427F70, the game-state reset and default villagers (eight calls;
         its caller's return address at +0x1D8): founders when the reset is
         a new tribe in an empty slot (0x41B7E4), the first tribe's naming
         (0x41BA0F) or Start Over (0x4283F2); temporary when a load follows
         and overwrites them (0x428428 load, 0x4285EA startup scan, 0x4285BD
         no save yet).
     The copy init's callers:
       0x45F1D0 (0x45F2AB): the delivery's twins and triplets;
       0x45F2D0 (0x45F3A8; its caller's return address at +0x1C):
         0x4191E0 (0x419238)  The Crystal of Reflections, "keep";
         0x417770 (0x417840)  The Mysterious Vial (amber), the first copy --
                    the second is reached by a tail jmp, so the slot holds
                    the event dispatcher's own return, 0x419A33. */
#define VV3_FRESH2 0x456326u, 0x190u
#define VV3_FRESH3 0x456326u, 0x1CCu
#define VV3_RESET 0x456326u, 0x1D8u
#define VV3_COPY1 0x4566EFu, 0x10u
#define VV3_COPY2 0x4566EFu, 0x1Cu
#define VV3_SEED(l2) \
    { VV3_RESET, 0x41B7E4u, 0x190u, (l2), MARK_FOUNDER, "Founder" }, \
    { VV3_RESET, 0x41BA0Fu, 0x190u, (l2), MARK_FOUNDER, "Founder" }, \
    { VV3_RESET, 0x4283F2u, 0x190u, (l2), MARK_FOUNDER, "Founder" }, \
    { VV3_RESET, 0x428428u, 0x190u, (l2), MARK_TEMPORARY, NULL }, \
    { VV3_RESET, 0x4285EAu, 0x190u, (l2), MARK_TEMPORARY, NULL }, \
    { VV3_RESET, 0x4285BDu, 0x190u, (l2), MARK_TEMPORARY, NULL }
static const struct arrival_marker MARKERS_VV3[] = {
    { VV3_FRESH2, 0x45FFD2u, 0x150u, 0x45F1C9u, MARK_BIRTH, NULL },
    { VV3_COPY1, 0x45F2ABu, 0, 0, MARK_BIRTH, NULL },
    { VV3_FRESH3, 0x414DB4u, 0x190u, 0x45FF80u, MARK_EVENT, "The Canoe from the Other Side" },
    { VV3_FRESH3, 0x415355u, 0x190u, 0x45FF80u, MARK_EVENT, "Barrel of Babies" },
    { VV3_FRESH3, 0x415398u, 0x190u, 0x45FF80u, MARK_EVENT, "Barrel of Babies" },
    { VV3_FRESH3, 0x4153DBu, 0x190u, 0x45FF80u, MARK_EVENT, "Barrel of Babies" },
    VV3_SEED(0x428134u), VV3_SEED(0x428188u), VV3_SEED(0x4281BCu), VV3_SEED(0x4281E3u),
    VV3_SEED(0x428215u), VV3_SEED(0x428253u), VV3_SEED(0x428296u), VV3_SEED(0x4282E6u),
    { VV3_COPY2, 0x419238u, 0x10u, 0x45F3A8u, MARK_EVENT, "The Crystal of Reflections" },
    { VV3_COPY2, 0x417840u, 0x10u, 0x45F3A8u, MARK_EVENT, "The Mysterious Vial (amber)" },
    { VV3_COPY2, 0x419A33u, 0x10u, 0x45F3A8u, MARK_EVENT, "The Mysterious Vial (amber)" },
};

/* The Tree of Life: fresh init 0x45EF10 (hook 0x45F175: sub esp,0x144 and
   four pushes -> its return address at +0x154; `ret 0x38`), copy init
   0x45D9B0 (hook 0x45D9BB: push esi, push edi -> +0x8).
     Through 0x466270 (the init returns to 0x466302; 0x466270's own return
     address at +0x194):
       0x467D50 (the init's return 0x467D92): the delivery's first child;
       0x43B830 (0x43B929): the adoption scene's founder candidates;
       0x41FEF0 (0x420268): the start-game balancing of the founders;
       0x467D10 (0x467D40; its caller's return address at +0x1D0):
         0x4148B0 (0x4148D4)  The Canoe from the Other Side;
         0x414D90 (0x414DC5, 0x414E08, 0x414E4B)  Daredevil Barrel...of
                              Babies! -- also the Origins purchase, which
                              fires this same event object;
         0x43B830 (0x43B965)  the adoption scene's stand-in father, freed at
                              0x43B9A2: temporary;
         0x440840             the developers' F7 command: "unknown".
     Through 0x466370 (the init returns to 0x4663E5): the ghosts (look-alikes,
     +0x1CC7), temporary.
     Copy init through 0x466310 (its return address at +0x14): the
     delivery's twins and triplets, 0x4688F3 and 0x468996.
   The Abandoned Infants makes women pregnant; its babies are births. */
#define VV4_FRESH0 0x45F175u, 0x154u
#define VV4_FRESH1 0x45F175u, 0x194u
#define VV4_FRESH2 0x45F175u, 0x1D0u
#define VV4_VIA_466270 0x154u, 0x466302u
#define VV4_VIA_467D10 0x194u, 0x467D40u
static const struct arrival_marker MARKERS_VV4[] = {
    { VV4_FRESH1, 0x467D92u, VV4_VIA_466270, MARK_BIRTH, NULL },
    { 0x45D9BBu, 0x14u, 0x4688F3u, 0, 0, MARK_BIRTH, NULL },
    { 0x45D9BBu, 0x14u, 0x468996u, 0, 0, MARK_BIRTH, NULL },
    { VV4_FRESH1, 0x43B929u, VV4_VIA_466270, MARK_FOUNDER, "Founder" },
    { VV4_FRESH1, 0x420268u, VV4_VIA_466270, MARK_FOUNDER, "Founder" },
    { VV4_FRESH0, 0x4663E5u, 0, 0, MARK_TEMPORARY, NULL },
    { VV4_FRESH2, 0x43B965u, VV4_VIA_467D10, MARK_TEMPORARY, NULL },
    { VV4_FRESH2, 0x4148D4u, VV4_VIA_467D10, MARK_EVENT, "The Canoe from the Other Side" },
    { VV4_FRESH2, 0x414DC5u, VV4_VIA_467D10, MARK_EVENT, "Barrel of Babies" },
    { VV4_FRESH2, 0x414E08u, VV4_VIA_467D10, MARK_EVENT, "Barrel of Babies" },
    { VV4_FRESH2, 0x414E4Bu, VV4_VIA_467D10, MARK_EVENT, "Barrel of Babies" },
};

/* New Believers: fresh init 0x4681F0 (hook 0x468411: sub esp,0x144 and four
   pushes -> its return address at +0x154; `ret 0x38`), copy init 0x4687F0
   (hook 0x4687FE: three pushes -> +0xC).  The fresh init's three callers:
     0x46FAD0, the believer allocator (0x46FB6F; three pushes and 14
       arguments, so its own return address is at +0x19C):
       0x471E60 (0x471EA2): the delivery's first child (its one caller);
       0x43E220 (0x43E317): the choose-your-founders screen's candidates;
       0x4259D0 (0x425D48): the village seeding's balancing replacements;
       0x471E20 (0x471E50; its caller's return address at +0x1D8):
         0x4151D0 (0x415205, 0x415248, 0x41528B)  slot 26, Barrel O'
                    Babies! (believers) -- also the Origins purchase, which
                    runs this same apply;
         0x415410 (0x415445, 0x415488, 0x4154CB)  slot 30, Chutes Without
                    Ladders;
         0x415510 (0x415559, 0x415588)  slot 31, News From Another Tribe;
         0x43E220 (0x43E353)  a founder candidate's stand-in father, hidden
                    again at 0x43E390: temporary;
     0x46FB80, the Heathen allocator (0x46FC28): every Heathen, never a
       villager (the faction byte, cod_arrivals.inc);
     0x46FDE0, Reanimate's stand-in (0x46FE5C): temporary.
   The copy init's one caller, 0x46FD70 (0x46FDCE): the delivery's twins
   and triplets.  The Abandoned Infants makes women pregnant; its babies are
   births. */
#define VV5_FRESH1 0x468411u, 0x154u
#define VV5_FRESH2 0x468411u, 0x19Cu
#define VV5_FRESH3 0x468411u, 0x1D8u
#define VV5_VIA_46FAD0 0x154u, 0x46FB6Fu
#define VV5_VIA_471E20 0x19Cu, 0x471E50u
static const struct arrival_marker MARKERS_VV5[] = {
    { VV5_FRESH2, 0x471EA2u, VV5_VIA_46FAD0, MARK_BIRTH, NULL },
    { 0x4687FEu, 0xCu, 0x46FDCEu, 0, 0, MARK_BIRTH, NULL },
    { VV5_FRESH2, 0x43E317u, VV5_VIA_46FAD0, MARK_FOUNDER, "Founder" },
    { VV5_FRESH2, 0x425D48u, VV5_VIA_46FAD0, MARK_FOUNDER, "Founder" },
    { VV5_FRESH1, 0x46FE5Cu, 0, 0, MARK_TEMPORARY, NULL },
    { VV5_FRESH3, 0x43E353u, VV5_VIA_471E20, MARK_TEMPORARY, NULL },
    { VV5_FRESH3, 0x415205u, VV5_VIA_471E20, MARK_EVENT, "Barrel of Babies" },
    { VV5_FRESH3, 0x415248u, VV5_VIA_471E20, MARK_EVENT, "Barrel of Babies" },
    { VV5_FRESH3, 0x41528Bu, VV5_VIA_471E20, MARK_EVENT, "Barrel of Babies" },
    { VV5_FRESH3, 0x415445u, VV5_VIA_471E20, MARK_EVENT, "Chutes Without Ladders" },
    { VV5_FRESH3, 0x415488u, VV5_VIA_471E20, MARK_EVENT, "Chutes Without Ladders" },
    { VV5_FRESH3, 0x4154CBu, VV5_VIA_471E20, MARK_EVENT, "Chutes Without Ladders" },
    { VV5_FRESH3, 0x415559u, VV5_VIA_471E20, MARK_EVENT, "News From Another Tribe" },
    { VV5_FRESH3, 0x415588u, VV5_VIA_471E20, MARK_EVENT, "News From Another Tribe" },
};

#define MARKERS(table) do { *out = (table); *count = (int)(sizeof(table) / sizeof((table)[0])); } while (0)

static void arrival_markers(const struct arrival_marker **out, int *count) {
    switch (g_game) {
    case 1: MARKERS(MARKERS_VV1); break;
    case 2: MARKERS(MARKERS_VV2); break;
    case 3: MARKERS(MARKERS_VV3); break;
    case 4: MARKERS(MARKERS_VV4); break;
    case 5: MARKERS(MARKERS_VV5); break;
    default:
        *out = NULL;
        *count = 0;
        break;
    }
}
