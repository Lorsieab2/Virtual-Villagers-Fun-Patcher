/* VVFP Parentage Export -- Virtual Villagers 1 (A New Home).

   Appends one plain-text record per conception to a log beside the game
   executable, capturing both parents while they are still identifiable.

   WHY CAPTURE AT CONCEPTION RATHER THAN AT BIRTH

   Parentage is not stored anywhere in a villager record. An independent RE
   audit of all four exact builds (data/mask_identity_adapters.json) found the
   inheritance path that writes a child's OWN head and body in each game, but
   no instruction that stores a mother_name, father_name, mother_head,
   father_head, mother_body or father_body into the child. Inheritance computes
   the child's own appearance and discards the parents' values.

   So the parents cannot be recovered from the child afterwards, at any later
   moment, by any amount of reading. They must be recorded at the instant the
   pregnancy begins, which is exactly what the owner's specification asks for
   and the only design that can work.

   WHERE THE DATA COMES FROM

   The hook runs at the head of VV1's conception routine, sub_43BBC0
   (0x00043BBC0 -> VA 0x0043BBC0), which is the only function in the image that
   increments all three birth counters. Those counter offsets are not guesses:
   they are the ones the shipping statistics companion already reads --

       manager + 0x9E24  Babies Made       inc at 0x43BC1C / 0x43BC5E / 0x43BC9C
       manager + 0x9E44  Twins Birthed     inc at 0x43BCC0
       manager + 0x9E48  Triplets Birthed     at 0x43BCA8 / 0x43BCB0

   Its decompiled form is:

       int __thiscall sub_43BBC0(int *this, int a2, int a3, int a4, int a5)
           v9 = this + 246 * a2;   // 246 * 4 == 0x3D8 == the record stride
           v9[215] = 2 or 3;       // record + 0x35C = litter size

   `246 * 4` reproducing the proven stride exactly is what establishes that
   `this` is the record array and `a2` is the MOTHER's record index.

   The litter size is written LATE, on the twins and triplets branches, which
   is why the hooks sit at the routine's success exits rather than its head --
   see the VV1 row in GAME_LAYOUTS for the full reasoning.

   FIELD OFFSETS

   Per-game offsets live in GAME_LAYOUTS below, each with the instruction that
   proves it. They are deliberately NOT duplicated here: an earlier version of
   this file carried a second copy under the heading "every offset here is
   proven", and when +0x394 was disproven the copy kept asserting it. A reader
   consulting the reference block got the wrong value, and the word "proven"
   made it look checked. One table, or the stale one wins.

   The name buffer start could not be found by the field-displacement audit
   because names are written by bulk string copies (sprintf), which take the
   buffer's ADDRESS and so leave no [reg+disp] access for a scan to see. It is
   0x1C bytes long: nothing at all is referenced between +0x370 and +0x38C, and
   +0x38C is the next field the conception routine itself writes. That also
   explains the warning in vv1_origins_icons.c that +0x374 "was inside the
   villager NAME buffer" -- it is four bytes into this one. */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>

enum {
    /* The log sits beside the executable, so the path is bounded by the
       executable's own path plus a fixed filename.

       This is deliberately NOT the 32768-wchar_t long-path maximum the
       statistics companion uses. Two such buffers -- one here and one in
       build_log_path -- are live at the same time in this call chain, which
       would put 128 KB on the stack. That companion is called from the save
       handler; this one is called from the conception routine during ordinary
       gameplay, and a frame that large risks STATUS_STACK_OVERFLOW on any
       thread whose stack is smaller than the main one. MAX_PATH plus room for
       the filename costs 1 KB per buffer instead.

       GetModuleFileNameW is checked for truncation against this bound, so an
       executable installed under a genuinely longer path disables the log
       rather than writing to a truncated one. */
    MAX_LOG_PATH = 512,

    /* A fixed local bound for a name, checked against each game's own
       name_capacity before use, so adding a game with a longer name field
       fails the guard rather than overrunning these buffers. */
    MAX_NAME_BYTES = 64,

    /* How a game records the other parent.

       This is not a detail: VV1 stores a father ID and his record is found by
       scanning the array for it, while VV4 and VV5 store the father's NAME
       directly in the mother's record and keep no id anywhere. Reading one as
       the other interprets a name buffer as an integer, resolves nothing, and
       logs "(unknown)" for every single birth -- a feature that appears to work
       and records nothing useful. */
    FATHER_BY_ID = 0,
    FATHER_BY_NAME = 1,
    /* The game records nothing about the other parent that can be read back
       from the mother. VV1 is the only such case: its conception routine
       RECEIVES a partner value and never reads it, and the field that looked
       like a father id turned out to be a skill value -- see the VV1 row. */
    FATHER_NOT_RECORDED = 2,

    GAME_VV1 = 1,
    GAME_VV2 = 2,
    GAME_VV3 = 3,
    GAME_VV4 = 4,
    GAME_VV5 = 5,

    /* The owner asked for a roll "past ~256 villagers". One record per
       conception, and VV1's record array itself holds 256 slots, so 256
       records per file keeps a log to roughly one village's worth of births. */
    RECORDS_PER_FILE = 256
};

/* Per-game record geometry.

   Every field is an offset into a villager record, and every one has to be
   established by instruction-level evidence in that game's own executable
   before it is filled in here. A wrong offset does not crash -- it silently
   logs the wrong number, and because parentage cannot be recovered from the
   child afterwards, a wrong record is permanent.

   So the four games whose evidence is not yet in are declared with `supported`
   zero and left at zero. WriteParentageRecord refuses them outright rather
   than reading a plausible-looking guess. */
struct game_layout {
    int supported;
    unsigned int stride;
    int slots;
    /* Where the first record sits relative to the pointer the caller passes.

       This is a CONTAINER HEADER, not a per-record bias: VV4 and VV5 keep the
       villager array inside an object whose first 0x44 bytes are something
       else, so records do NOT carry a 0x44-byte prefix each. Naming it
       record_base rather than record_prefix is deliberate for that reason.

       The caller passes the unbiased container and this subtracts the header,
       rather than the caller passing `container + 0x44` and this being zero.
       Both work, but only one fails safely: with the header recorded here, a
       caller that mistakenly pre-applies it is rejected at slot 0 -- loudly, on
       the very first birth -- while a caller that forgets to pre-apply it in
       the other design is accepted at every slot and silently misindexed. */
    unsigned int record_base;
    unsigned int active;      /* u8, == 1 when the slot is a live villager */
    unsigned int age;         /* i32 */
    unsigned int head;        /* i32 */
    unsigned int body;        /* i32 */
    /* The field a game uses to find one villager from another, when it has
       one at all. Only read when father_kind is FATHER_BY_ID.

       Deliberately not called an "identity": VV1's nearest candidate, +0x36C,
       is NOT unique. It is rand()%50+1 at 0x43C669 with a second writer using
       %99, and it is COPIED from parent to child at 0x43C9E5 alongside gender,
       head and body -- a field that is inherited cannot identify anyone, and
       with around ninety villagers and fifty values, living villagers share it
       routinely. Every reader compares it paired with +0x368, which is
       look-alike avoidance rather than lookup. No game currently sets
       FATHER_BY_ID, so this field is unused; it exists for a game that turns
       out to keep a real one. */
    unsigned int id;
    unsigned int name;        /* char[name_capacity] */
    unsigned int name_capacity;
    int father_kind;          /* FATHER_BY_ID or FATHER_BY_NAME */
    unsigned int father;      /* an i32 id, or a char[name_capacity] */
    unsigned int litter;      /* i32, babies in this pregnancy */
    /* Some games copy the father's own traits INTO the mother's record at
       conception, by value. Where they do, those copies are the better source:
       they are taken from the father himself at the moment of conception and
       survive his death, while a name scan can fail afterwards and can be
       defeated by two living villagers sharing a name.

       VV2 does this. Its conception routine sub_44B980 takes the father's
       fields as stack arguments and stores them on the mother: the caller at
       0x421FE7 pushes [father+0x54C] then [father+0x548] then a pointer to
       [father+0x564], and the callee writes [esp+0x24] to mother+0x5DC at
       0x44BA24 and [esp+0x20] to mother+0x5E0 at 0x44BA43 while sprintf'ing
       the name into mother+0x5C0. Since +0x548 is head and +0x54C is body on
       a VV2 villager, mother+0x5E0 is the father's head and mother+0x5DC is
       his body. The two other real-conception callers, at 0x464A38 and
       0x464C4D, push the same three fields in the same order; their internal
       branches select a later argument, not these.

       Zero means "this game copies nothing", which is every game but VV2. His
       AGE is not among the copied fields in any game -- VV2's neighbouring
       mother+0x5E4 is a hardcoded 1 written at 0x44BA10, a pregnancy flag
       rather than a trait, and reading it as an age would print 1 for every
       father who ever lived. */
    unsigned int father_head_copy;  /* i32 on the MOTHER, 0 when absent */
    unsigned int father_body_copy;  /* i32 on the MOTHER, 0 when absent */
    /* The "no such villager" id sentinel.
       VV1 uses 0xC7: it is written to the father field at 0x42427B and tested
       there at 0x42EF39. An unset father therefore resolves to no record and
       the log says so, rather than printing 199 as if it were a real id. The
       raw id is never written to the log at all -- it exists only to find the
       father's record -- so this guards a lookup, not a printed value. */
    int no_villager;
    const wchar_t *log_name;  /* "<name> <n>.txt" beside the executable */
};

static const struct game_layout GAME_LAYOUTS[6] = {
    /* index 0 is unused so a game id indexes directly. */
    { 0 },

    /* VV1 -- A New Home. Every offset below is proven:
         +0x28   active      vv1_origins_icons.c VV_OCCUPIED_OFFSET
         +0x348  age         vv1_origins_icons.c VV_AGE_OFFSET
         +0x360  head        vv1_origins_icons.c VV_HEAD_OFFSET
         +0x364  body        vv1_origins_icons.c VV_CLOTHING_OFFSET
         +0x36C  appearance variant -- NOT an id, and not read by this file.
                 rand()%50+1 at 0x43C669, a second writer using %99, and
                 copied parent->child at 0x43C9E5 beside gender, head and
                 body. Every reader compares it paired with +0x368, which is
                 look-alike avoidance rather than lookup. Its 0xC7 sentinel
                 is NOT evidence that it identifies anyone -- the skill field
                 at +0x394 carries the same constant, which is exactly the
                 coincidence that made this file misread that one as a
                 father id.
         +0x370  name        sprintf destination at 0x43C696..0x43C6A1, read
                             back as a string at 0x418753..0x418760; bounded at
                             0x1C because nothing is referenced between +0x370
                             and +0x38C, and +0x38C is the next field the
                             conception routine itself writes
         +0x394  NOT the father -- see below

       VV1 RECORDS NOTHING ABOUT THE FATHER, which is why father_kind is
       FATHER_NOT_RECORDED here and only here.

       An earlier version of this file read +0x394 as a father id, on the
       strength of `mov [esi+0x394], edx` at 0x43BC04 inside the conception
       routine. That was wrong, and the disassembly says so plainly once the
       argument slots are traced rather than assumed:

           0x43BBD0  mov eax, [esp+0x10]     ; the same argument
           0x43BBD4  cmp eax, 2              ; normalised...
           0x43BBD9  mov eax, 1              ; ...into a skill slot
           0x43BC00  mov edx, [esp+0x10]     ; and reloaded here
           0x43BC04  mov [esi+0x394], edx    ; stored as what looked like a father
           0x43BC0A  mov [esi+0x38C], eax    ; skill slot
           0x43BC10  mov [esi+0x390], ecx    ; skill value

       All three come from one skill-selection pair. The caller does pass the
       partner's +0x36C at [esp+0xC], and the routine never reads that slot at
       all.

       +0x36C would not have identified him anyway: it is rand()%50+1 at
       0x43C669 (and rand()%99+1 at 0x41C247), it is COPIED from parent to child
       at 0x43C9E5 alongside gender, head and body, and every reader compares it
       paired with +0x368. That is look-alike avoidance, not identity -- with
       ~90 villagers and 50 possible values, living villagers share it routinely.

       So there is no father to name from the mother's record. The log says so
       rather than printing a skill value as if it were a parent. Both parents'
       records ARE live at the six call sites, so capturing him there is
       possible; that is a design change and it is with the owner.
         +0x35C  litter      2 at 0x43BC4E, 3 at 0x43BC8C; cleared per
                             pregnancy by 0x42F0C7, 0x43C722 and 0x43CABE

       Read the name as 28 bytes and force a terminator; the copier at
       0x44B23D is MSVC sprintf with count 0x7FFFFFFF, so it is unbounded and
       guarantees nothing. Anything that WRITES a VV1 name must use 0x18, the
       bound the game's own villager-to-villager copy uses. */
    {
        1, 0x3D8, 256, 0,
        0x28, 0x348, 0x360, 0x364, 0x36C,
        0x370, 0x1C,
        FATHER_NOT_RECORDED, 0, 0x35C,
        0, 0,
        0xC7,
        L"Virtual Villagers 1 Parentage Log"
    },

    /* VV2 -- The Lost Children. Conception is sub_44B980; the mother arrives as
       an INDEX in the first stack argument and is reached by
       `imul eax, 0E48Ch` at 0x44B994 feeding `lea esi,[eax+edi]` at 0x44B99B,
       which is what proves the stride and that ecx holds the array rather than
       a villager.

         +0x30    active
         +0x530   age     gates in sub_44F610 (>= 0x168, < 0x3E8)
         +0x548   head    lower of the appearance pair
         +0x54C   body    higher of the pair
         +0x564   name    sprintf destination in sub_44C600 and its siblings
         +0x5C0   father  sprintf'd from the partner's own +0x564 at 0x44BA49
         +0x544   litter  2 at 0x44BA82, 3 at 0x44BAB6

       VV2 keeps NO father id -- the father's NAME is copied into the mother's
       record, so he is found by name like VV3, VV4 and VV5.

       But the name is NOT the only trace of him. Conception also copies his
       head and body onto the mother by value: sub_44B980 takes them as stack
       arguments and stores them at mother+0x5E0 and mother+0x5DC, which is why
       father_head_copy and father_body_copy are set here and nowhere else.
       Those copies outlive him, so VV2 reports his head and body even when the
       name scan cannot find a record. His AGE is not copied and is not
       recoverable from the mother, so it alone can still read "record not
       found".

       Note the litter field is never written for a single birth: 0 means one
       baby, and the delivery routine clears it at 0x43BF85, so a singleton
       after twins correctly reads 0 rather than a stale 2. That is what makes
       the `< 1 -> 1` fallback safe rather than a guess. */
    {
        1, 0xE48C, 256, 0,
        0x30, 0x530, 0x548, 0x54C, 0,
        0x564, 0x18,
        FATHER_BY_NAME, 0x5C0, 0x544,
        0x5E0, 0x5DC,
        0,
        L"Virtual Villagers 2 Parentage Log"
    },

    /* VV3 -- The Secret City. Conception is sub_455AB0, and unlike VV1 and VV2
       the mother arrives as a RECORD POINTER directly in ecx -- `mov esi, ecx`
       at 0x455AB1, with no stride multiply anywhere in the routine. That is why
       a stride scan finds nothing in VV3 and why a hook ported from VV1 or VV2
       would read the wrong object.

         +0xF10   active
         +0xDC4   age     cmp [esi+0DC4h], 118h at nine sites
         +0xDF0   head    lower of the appearance pair
         +0xDF4   body    higher of the pair
         +0xDD4   name    strncpy bound 0x18 at 0x455B6D
         +0xE48   father  strncpy destination at 0x455B6D
         +0xE90   litter  1 at 0x455B7C, 3 at 0x455BBF, 2 at 0x455BDD

       VV3 WRITES the singleton default of 1 at 0x455B7C, where VV1 and VV2
       write nothing for a single birth. The `< 1 -> 1` fallback is therefore
       redundant here rather than load-bearing -- harmless, but the difference
       is why "which exit does a single birth take" has to be asked per game
       instead of assumed from one.

       record_base is 0x14 because the accessor sub_45C840 computes

           imul eax, [esp+4], 0x1F8C     the slot index times the stride
           lea  eax, [eax + ecx + 0x14]  plus the container header

       so record zero sits 0x14 bytes into the container the trampoline passes.
       Declaring it 0 while passing the unbiased container makes the span from
       that pointer to the mother 0x14 larger than a multiple of the stride, and
       the divisibility guard rejects EVERY conception -- a feature that loads,
       hooks, runs, and logs nothing. This was 0 for exactly that reason until
       an automated review caught it.

       The slot count is 150, not 256. data/builds.json declares VV3 with
       villager_slots 150 and absolute_maximum 150, and VV3 is the only game
       where the two disagreed with this table -- VV1 and VV2 really are
       256-slot games, VV4 and VV5 already said 150.

       That mattered because find_record_by_name cannot stop early: it has to
       walk the whole range to detect two active villagers sharing a name,
       which is the ambiguity guard that keeps it from attributing the wrong
       father. So the `active` byte was dereferenced for all 256 slots on every
       conception, and slots 150..255 are past the pool -- 106 slots, 856,056
       bytes at this stride. Whether that faults depends on what happens to sit
       after the pool at runtime, which is the shape of defect that survives
       every test here and crashes on a player's machine.

       The name field is 25 bytes (0x19), not 0x18. The burial writer at
       0x455032 does `push 0x19` before copying it, and
       data/mask_identity_adapters.json records length 25 for +0xDD4; main
       already ships VV3_NAME_LEN 0x19 for the same field. At 0x18 the scan
       compares truncated names, so two villagers differing only in the 25th
       character compare equal -- which does not merely truncate the log, it
       makes the ambiguity guard refuse a father who was actually
       distinguishable. Note this is the READ bound only: the adapter warns
       never to WRITE more than 0x18, and nothing here writes a name. */
    {
        1, 0x1F8C, 150, 0x14,
        0xF10, 0xDC4, 0xDF0, 0xDF4, 0,
        0xDD4, 0x19,
        FATHER_BY_NAME, 0xE48, 0xE90,
        0, 0,
        0,
        L"Virtual Villagers 3 Parentage Log"
    },

    /* VV4 -- The Tree of Life. Verified against the stock binary:
         +0x1B8C  age     cmp ecx, 118h at 0x45EC31 and 0x45EC37
         +0x1B90  sex     cmp [ecx+1B90h], 1 at 0x460990
         +0x1B9C  name    lea edx,[esi+1B9Ch] at 0x460A1E; 14 lea sites and no
                          scalar load, which is what a buffer looks like
         +0x1BB8  head    mov ecx,[esi+1BB8h] at 0x460A10
         +0x1BBC  body    mov edx,[esi+1BBCh] at 0x460A09
         +0x1C50  litter  1 at 0x45E87D, 3 at 0x45E8C0, 2 at 0x45E8D3
         +0x1C10  father  strncpy(esi+1C10h, Source, 0x18) at 0x45E86E

       On head vs body: both offsets have load instructions behind them, and the
       assignment is not inferred -- the owner states head comes first and body
       second in all five games, so the lower offset of the appearance pair is
       head. Static analysis could only ever have narrowed this to "the pair is
       {head, body}", since +0x1BB8 is inherited as (a10+a12)/2 and +0x1BBC is
       rand(29), both clamped 0..29, and neither carries a label. Which is worth
       remembering: when a question is about how the game BEHAVES rather than
       how it is encoded, asking is cheaper and more reliable than deriving.

       There is NO father id field, only the father's name, which is why the
       hook belongs at the role-resolver call site 0x460A2E where both parents
       are live record pointers (ecx/ebp the mother, esi the father) rather than
       at the routine head where the father is only decomposed scalars.

       The `no_villager` sentinel is 0: VV4 stores no father id at all, so the
       id-resolution path is unused here and the field is inert.

       record_base is 0x44 because the accessor sub_466040 computes
       `lea eax, [eax + ecx + 0x44]` after multiplying the index by the stride
       -- the villager array lives inside a container whose first 0x44 bytes are
       something else. The caller passes that container unbiased; the container
       itself is the global 0x50E568, loaded as an immediate by all 55 callers
       of the accessor.

       The name field is 25 bytes (0x19), the same as VV3's. Its burial writer
       proves it with a count operand:

           0x45D4B2  push 0x19
           0x45D4B4  lea  eax, [edi+0x1B9C]
           0x45D4BC  call 0x4724E0            (strncpy)
           0x45D4C1  mov  byte [esi+0x19], 0  (the terminator, at index 25)

       This read 0x18 until it was noticed that safe_write_limit 24 in the
       adapter record is the WRITE bound and says nothing about the read
       length -- the two are orthogonal, and reading 24 truncates the
       comparison find_record_by_name depends on. Two villagers differing only
       in the 25th character then compare equal, so the ambiguity guard refuses
       a father who was actually distinguishable. Nothing here writes a name,
       so the 24-byte write limit is not in play. */
    {
        1, 0x2E3C, 150, 0x44,
        0x1CC4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B98,
        0x1B9C, 0x19,
        FATHER_BY_NAME, 0x1C10, 0x1C50,
        0, 0,
        0,
        L"Virtual Villagers 4 Parentage Log"
    },

    /* VV5 -- New Believers. Structurally identical to VV4 at every offset used
       here; the resolver headers are byte-identical. Verified separately:
         +0x1C50  litter  1 at 0x465ECD, 3 at 0x465F10, 2 at 0x465F23
         +0x1C10  father  strncpy at 0x465EBE
       Its resolver call site is 0x467DBE. Same head/body caveat as VV4.

       The container header is 0x48, NOT VV4's 0x44 -- accessor sub_46F950 does
       `lea eax, [eax + ecx + 0x48]`. The two games are structurally identical
       at every record offset and differ here, which is why this was verified
       rather than inherited: carrying VV4's 0x44 across would have put every
       VV5 mother pointer four bytes off a record boundary, the guard would have
       rejected every call, and VV5 would have logged nothing at all without
       any error. The container is the global 0x554148, loaded as an immediate
       at all 445 of its occurrences.

       The name field is 25 bytes, established from VV5's OWN burial writer
       rather than from VV4's:

           0x464CB2  push 0x19
           0x464CB4  lea  eax, [edi+0x1B9C]
           0x464CBC  call 0x47D7C0            (strncpy)
           0x464CC1  mov  byte [esi+0x19], 0  (the terminator, at index 25)

       That distinction is not pedantry here. The adapter record for VV5 quotes
       VV4's address, 0x45D4B4, which in VV5's image decodes to
       `add dword [esi+0xB], edi` -- so anyone verifying VV5 at the cited
       address finds nothing and could conclude the length is unproven. VV5's
       real site is 0x464CB2 and it carries the same count operand. */
    {
        1, 0x2F44, 150, 0x48,
        0x1CD4, 0x1B8C, 0x1BB8, 0x1BBC, 0x1B98,
        0x1B9C, 0x19,
        FATHER_BY_NAME, 0x1C10, 0x1C50,
        0, 0,
        0,
        L"Virtual Villagers 5 Parentage Log"
    }
};

/* Names are engine-written with sprintf into a fixed 0x1C-byte field, so a
   name that exactly fills the buffer leaves no terminator. Copy into a local
   that is one byte longer and terminate it ourselves rather than trusting the
   buffer, and replace anything unprintable so one corrupt record cannot make
   the whole log unreadable. */
static void copy_name_field(
    const unsigned char *source,
    char *out,
    size_t out_size,
    unsigned int capacity
) {
    size_t index;

    if (out_size == 0) {
        return;
    }
    for (index = 0; index + 1 < out_size && index < capacity; ++index) {
        unsigned char value = source[index];
        if (value == 0) {
            break;
        }
        out[index] = (value >= 0x20 && value < 0x7F) ? (char)value : '?';
    }
    out[index] = '\0';
    if (index == 0) {
        /* An empty name is not an error worth dropping the record over: the
           rest of the row still identifies the villager by id, head and body. */
        if (out_size >= 8) {
            memcpy(out, "(unnamed)", 9 < out_size ? 9 : out_size - 1);
            out[out_size - 1 < 9 ? out_size - 1 : 9] = '\0';
        }
    }
}

static void copy_villager_name(
    const struct game_layout *g,
    const unsigned char *record,
    char *out,
    size_t out_size
) {
    copy_name_field(record + g->name, out, out_size, g->name_capacity);
}

/* Resolve a villager id to its record by scanning the array.

   The id at +0x36C is not the record index -- the conception routine stores
   the FATHER by id, not by slot, so the father must be looked up. Returns NULL
   when no active record carries the id, which happens legitimately if the
   father died between conception and this call. */
static const unsigned char *find_record_by_id(
    const struct game_layout *g,
    const unsigned char *records,
    int id
) {
    int slot;

    if (records == NULL || id == g->no_villager) {
        return NULL;
    }
    for (slot = 0; slot < g->slots; ++slot) {
        const unsigned char *record =
            records + g->record_base + (size_t)slot * g->stride;
        if (*(const unsigned char *)(record + g->active) != 1) {
            continue;
        }
        if (*(const int *)(record + g->id) == id) {
            return record;
        }
    }
    return NULL;
}

/* Build "<exe folder>\Virtual Villagers 1 Parentage Log <n>.txt".

   Beside the executable, matching where the statistics companion writes, so a
   player finds both logs in the same place. */
static int build_log_path(
    const struct game_layout *g,
    int file_number,
    wchar_t *destination
) {
    wchar_t module_path[MAX_LOG_PATH];
    wchar_t *separator;
    DWORD length = GetModuleFileNameW(NULL, module_path, MAX_LOG_PATH);

    if (length == 0 || length >= MAX_LOG_PATH) {
        return 0;
    }
    separator = wcsrchr(module_path, L'\\');
    if (separator == NULL) {
        return 0;
    }
    *separator = L'\0';
    return _snwprintf_s(
        destination,
        MAX_LOG_PATH,
        _TRUNCATE,
        L"%ls\\%ls %d.txt",
        module_path,
        g->log_name,
        file_number
    ) >= 0;
}

/* Count the records already in a file, so a roll happens at the right point
   and a restarted game continues the current file rather than overwriting it.

   Counts the row marker rather than newlines, because a record spans several
   lines and a partially written trailing row must not inflate the count. */
static int count_records(const wchar_t *path) {
    FILE *file = _wfopen(path, L"rb");
    int count = 0;
    char line[512];

    if (file == NULL) {
        return 0;
    }
    while (fgets(line, (int)sizeof(line), file) != NULL) {
        if (strncmp(line, "Conception ", 11) == 0) {
            ++count;
        }
    }
    fclose(file);
    return count;
}

/* Choose the file to append to: the highest-numbered existing file that is not
   yet full, else the next one. Starts at 1 so the first log reads "... 1.txt".

   Bounded so a corrupt or unwritable directory cannot spin forever; 4096 files
   is far beyond any real playthrough. */
static int select_log_file(
    const struct game_layout *g,
    wchar_t *destination,
    int *existing_records
) {
    int number;

    *existing_records = 0;
    for (number = 1; number <= 4096; ++number) {
        int records;
        if (!build_log_path(g, number, destination)) {
            return 0;
        }
        if (GetFileAttributesW(destination) == INVALID_FILE_ATTRIBUTES) {
            return 1;
        }
        records = count_records(destination);
        if (records < RECORDS_PER_FILE) {
            /* Hand the count back rather than making the caller re-derive it.
               Counting again after opening the file for append would rescan
               the whole log on every single birth, and would do it through a
               second handle on a file this call already holds open. */
            *existing_records = records;
            return 1;
        }
    }
    return 0;
}

/* Append one conception record.

   `records`  the villager record array base (edi at the hook site).
   `mother`   the mother's record (esi at the hook site).

   The father's id and the litter size are read from the mother's own record
   rather than passed in, because the hook sits at the routine's two SUCCESS
   TAILS -- after the engine has written record+0x35C -- rather than at its
   head. At the head neither is knowable: the litter size has not been chosen,
   and the conception may still be rejected by the capacity predicate.

   Returns 1 when a record was written, 0 otherwise. The caller ignores the
   result -- a failed log must never disturb the game. */
/* Is this layout row self-consistent enough to read a record with?

   The `supported` flag alone is not enough. While every later game is left at
   { 0 } the flag is the only thing that matters, but the moment a row is filled
   in, a single mistyped constant is all that stands between a typo and a
   permanently wrong parentage record -- and a wrong record cannot be corrected
   later, because parentage is not recoverable from the child.

   The specific hazards, each checked below:

     * a zero stride reaches `span % g->stride` and divides by zero;
     * a nonpositive slot count makes the array bound meaningless, so any
       pointer at or above `records` passes the boundary test;
     * a null log_name is passed straight to _snwprintf_s;
     * a field offset at or beyond the stride reads the NEXT villager's record,
       which produces plausible, wrong, and completely undetectable output.

   Every field is checked against the stride with its own width, so a four-byte
   read at stride-2 is rejected rather than straddling the record boundary. */
static int layout_is_usable(const struct game_layout *g) {
    static const unsigned int WORD = 4;
    unsigned int stride;

    if (g == NULL || !g->supported) {
        return 0;
    }
    if (g->stride == 0 || g->slots <= 0 || g->log_name == NULL) {
        return 0;
    }
    /* The first record does not always sit at the array base. VV4's accessor
       sub_466040 computes `lea eax, [eax + ecx + 0x44]` after multiplying the
       index by the stride, so record zero is 0x44 bytes in. Without that bias
       the boundary check below would reject every VV4 and VV5 pointer -- the
       span would never be an exact multiple of the stride -- and the feature
       would silently log nothing at all. */
    if (g->record_base >= g->stride) {
        return 0;
    }
    if (g->name_capacity == 0 || g->name_capacity + 1 > MAX_NAME_BYTES) {
        return 0;
    }
    stride = g->stride;

    /* One-byte field. */
    if (g->active >= stride) {
        return 0;
    }
    /* Four-byte fields: the LAST byte read must still be inside the record. */
    if (g->age + WORD > stride) return 0;
    if (g->head + WORD > stride) return 0;
    if (g->body + WORD > stride) return 0;
    /* The villager-id field is only read when a game records the father BY ID
       and his record has to be found by scanning for it. VV2, VV3, VV4 and VV5
       record the father's name instead and have no proven id field at all, so
       requiring one there would mean inventing an offset -- exactly what the
       unsupported-by-default design exists to prevent. */
    if (g->father_kind == FATHER_BY_ID && g->id + WORD > stride) {
        return 0;
    }
    /* The father's copied traits are read from the MOTHER's record, so they are
       bounded by the same stride as every other field here. Zero means the game
       copies nothing and nothing is read, which is why the guard is conditional
       rather than unconditional -- an unconditional `0 + WORD > stride` would
       pass anyway, but stating the condition keeps the "0 means absent" rule in
       one shape everywhere it appears. */
    if (g->father_head_copy != 0 && g->father_head_copy + WORD > stride) {
        return 0;
    }
    if (g->father_body_copy != 0 && g->father_body_copy + WORD > stride) {
        return 0;
    }
    if (g->father_kind == FATHER_NOT_RECORDED) {
        /* Nothing to validate: the field is unused. */
        (void)0;
    } else if (g->father_kind == FATHER_BY_ID) {
        if (g->father + WORD > stride) return 0;
    } else if (g->father_kind == FATHER_BY_NAME) {
        /* A name field is read with the same capacity as the villager's own
           name, so it must fit whole. */
        if (g->father + g->name_capacity > stride) return 0;
    } else {
        return 0;
    }
    if (g->litter + WORD > stride) return 0;
    /* The whole name buffer must fit. */
    if (g->name + g->name_capacity > stride) {
        return 0;
    }
    return 1;
}

/* Resolve a villager to his record by NAME, for the games that store a father's
   name rather than an id.

   VV2 through VV5 copy the father's name into the mother's record and keep no
   id at all -- in VV2 it arrives at the conception site as a formatted string
   argument, not a record pointer, so there is nothing to capture at the hook.
   Without a lookup his age, head and body would be printed as zeros while the
   feature advertises them, which is worse than useless: a reader cannot tell a
   genuine zero from a missing one.

   The name is not guaranteed unique -- two living villagers may share one --
   so an ambiguous match resolves to NULL rather than to a guess. Reporting no
   values is honest; reporting the wrong father's values is not, and a
   parentage record is permanent with no second source to correct it from.

   Returns NULL when the name matches no active record, which happens
   legitimately if the father died between conception and this call. */
static const unsigned char *find_record_by_name(
    const struct game_layout *g,
    const unsigned char *records,
    const char *name
) {
    const unsigned char *found = NULL;
    int slot;

    if (records == NULL || name == NULL || name[0] == '\0') {
        return NULL;
    }
    for (slot = 0; slot < g->slots; ++slot) {
        const unsigned char *record =
            records + g->record_base + (size_t)slot * g->stride;
        char candidate[MAX_NAME_BYTES];

        if (*(const unsigned char *)(record + g->active) != 1) {
            continue;
        }
        copy_villager_name(g, record, candidate, sizeof(candidate));
        if (strcmp(candidate, name) != 0) {
            continue;
        }
        if (found != NULL) {
            /* Two active villagers share this name; neither can be shown to be
               the father, so record none of his values rather than one of
               theirs. */
            return NULL;
        }
        found = record;
    }
    return found;
}

/* Is this pointer one of the array's own record slots?

   The caller hands a record pointer straight from a register, so it is checked
   rather than trusted: it must sit inside the array, land exactly on a record
   boundary once the base bias is removed, and be within the slot count. The
   same test serves the mother and the father, which is the point of factoring
   it out -- a second copy that drifted would be a silent wrong-record read,
   and parentage cannot be recovered from the child afterwards. */
static int is_record_slot(
    const struct game_layout *g,
    const unsigned char *records,
    const unsigned char *record
) {
    size_t span;

    if (records == NULL || record == NULL || record < records) {
        return 0;
    }
    span = (size_t)(record - records);
    if (span < g->record_base) {
        return 0;
    }
    span -= g->record_base;
    if (span % g->stride != 0) {
        return 0;
    }
    if (span / g->stride >= (size_t)g->slots) {
        return 0;
    }
    return 1;
}

/* The full entry point. WriteParentageRecord below is the original three
   argument form and forwards here with no father record, so a trampoline that
   has not been rebuilt keeps working exactly as it did. */
__declspec(dllexport) int __stdcall WriteParentageRecordWithFather(
    int game_id,
    const void *records_pointer,
    const void *mother_pointer,
    const void *father_pointer
) {
    const struct game_layout *g;
    const unsigned char *records = (const unsigned char *)records_pointer;
    const unsigned char *mother = (const unsigned char *)mother_pointer;
    const unsigned char *father_supplied =
        (const unsigned char *)father_pointer;
    const unsigned char *father_from_caller = NULL;
    int babies;
    const unsigned char *father;
    wchar_t path[MAX_LOG_PATH];
    FILE *file;
    char mother_name[MAX_NAME_BYTES];
    char father_name[MAX_NAME_BYTES];
    /* Rendered rather than printed as %d, so an unavailable field can say so
       instead of printing a 0 that a real villager could also hold. Sized for
       "not recorded by this game" plus its terminator. */
    char father_age[32];
    char father_head[32];
    char father_body[32];
    int written;
    int existing_records;

    if (game_id < GAME_VV1 || game_id > GAME_VV5) {
        return 0;
    }
    g = &GAME_LAYOUTS[game_id];
    /* A game whose record geometry has not been established refuses outright,
       and so does one whose row is filled in but not self-consistent. Logging a
       plausible-looking wrong number would be worse than logging nothing,
       because parentage cannot be recovered from the child later and there is
       no second source to correct the record from. */
    if (!layout_is_usable(g)) {
        return 0;
    }
    if (records == NULL || mother == NULL) {
        return 0;
    }
    if (!is_record_slot(g, records, mother)) {
        return 0;
    }
    if (*(const unsigned char *)(mother + g->active) != 1) {
        return 0;
    }

    /* The father's record, when the caller could supply one.

       Games that record the father BY NAME keep no pointer to his record in
       the mother's, so his age, head and body used to be unavailable on every
       birth -- the whole column read as "not recorded by this game". They are
       not unavailable at the hook site, though: the conception routine holds
       both parent records in registers, so the trampoline can pass the second
       one and these games gain three real fields.

       It is validated exactly like the mother, and additionally rejected if it
       IS the mother: a caller that passed the same record twice would print
       her numbers under his name, which is worse than saying nothing. An
       unusable pointer falls back to the name-only path rather than failing the
       record, so a trampoline that passes rubbish loses three fields instead of
       the whole log. */
    if (father_supplied != NULL
        && father_supplied != mother
        && is_record_slot(g, records, father_supplied)
        && *(const unsigned char *)(father_supplied + g->active) == 1) {
        father_from_caller = father_supplied;
    }

    /* Both are read from the mother's own record, which is why the hook sits at
       the routine's success tails rather than its head: at the head the engine
       has not yet chosen the litter size, so every twin and triplet birth would
       be recorded as a singleton, and a rejected conception would be logged as
       though it happened. */

    babies = *(const int *)(mother + g->litter);
    if (babies < 1) {
        /* A single birth never writes the field -- only the twins branch
           (0x43BC4E) and the triplets branch (0x43BC8C) do -- so it reads zero
           and one is the correct answer.

           Zero, not a stale 2 or 3 from the previous pregnancy: every writer of
           +0x35C in the image was enumerated, and the delivery routine
           sub_42E900 clears it at 0x42F0C7 (xor eax,eax; then 0 into both
           +0x358 and +0x35C), while the two villager-creation routines
           sub_43C350 and sub_43C840 clear it at 0x43C722 and 0x43CABE. So the
           field is reliably zero going into each pregnancy.

           That mattered enough to check: if it had retained the previous
           litter, a single birth following a twin birth would have been logged
           as twins, and there is no second source to correct such a record
           from. */
        babies = 1;
    }

    copy_villager_name(g, mother, mother_name, sizeof(mother_name));
    if (g->father_kind == FATHER_NOT_RECORDED) {
        memcpy(father_name, "(not recorded by this game)", 28);
        father = NULL;
    } else if (g->father_kind == FATHER_BY_NAME) {
        /* The name is in the mother's record, so it is read from there either
           way -- it is the name the game itself recorded for this conception,
           and it stays authoritative even when a record is also supplied.

           His three numbers come from his record, found in one of two ways,
           and the order matters:

           1. The record the trampoline captured, when it passed one. VV4 and
              VV5 hold both parent records in registers at the conception site,
              so the pointer is the father the engine itself was working with.
           2. Otherwise, a scan for his name. VV1's, VV2's and VV3's hook sites
              have no father record to capture -- in VV2 the name arrives as a
              formatted string argument -- so the scan is the only route there.

           The captured pointer is preferred because the scan cannot resolve a
           name shared by two living villagers, and returns NULL rather than
           guessing. A pointer the engine handed us has no such ambiguity. When
           neither route finds him the log says so rather than printing a 0
           that a real villager could hold. */
        copy_name_field(mother + g->father, father_name, sizeof(father_name),
                        g->name_capacity);
        father = father_from_caller;
        if (father == NULL) {
            father = find_record_by_name(g, records, father_name);
        }
    } else {
        father = find_record_by_id(
            g, records, *(const int *)(mother + g->father));
    }
    if (father != NULL && g->father_kind != FATHER_BY_NAME) {
        /* Not for FATHER_BY_NAME: there the name already came from the
           mother's record, which is what the game recorded for THIS
           conception. The supplied record contributes the numbers only, so a
           father who is later renamed still logs the name he had. */
        copy_villager_name(g, father, father_name, sizeof(father_name));
    } else if (father == NULL && g->father_kind == FATHER_BY_ID) {
        /* The father is recorded by id, and that id may no longer resolve --
           he can die between conception and delivery. Say so plainly rather
           than dropping the record or inventing a name. */
        memcpy(father_name, "(unknown)", 10);
    }

    if (!select_log_file(g, path, &existing_records)) {
        return 0;
    }
    file = _wfopen(path, L"ab");
    if (file == NULL) {
        return 0;
    }
    /* The father's three numbers are rendered as text so an unavailable field
       can say so. They used to print 0 whenever no father record was found,
       and 0 is a value a real villager can hold -- so a reader could not tell
       an unavailable field from a measured one, and the whole column read as a
       village of newborn fathers.

       Two different unavailable cases, kept distinct because they mean
       different things to a reader:

         "not recorded by this game" -- the game keeps no father for this birth
         at all, so nothing was ever looked for. Only VV1 reaches this.

         "(record not found)" -- a father WAS recorded and we went looking for
         his record, and it is not there. He may have died between conception
         and this call, or two living villagers may share his name, in which
         case the scan refuses to guess. Saying "not recorded by this game"
         here would be a false statement about the game rather than about this
         particular birth. */
    if (father != NULL) {
        _snprintf(father_age, sizeof(father_age), "%d",
                  *(const int *)(father + g->age));
        _snprintf(father_head, sizeof(father_head), "%d",
                  *(const int *)(father + g->head));
        _snprintf(father_body, sizeof(father_body), "%d",
                  *(const int *)(father + g->body));
        father_age[sizeof(father_age) - 1] = '\0';
        father_head[sizeof(father_head) - 1] = '\0';
        father_body[sizeof(father_body) - 1] = '\0';
    } else if (g->father_kind == FATHER_NOT_RECORDED) {
        memcpy(father_age, "not recorded by this game", 26);
        memcpy(father_head, "not recorded by this game", 26);
        memcpy(father_body, "not recorded by this game", 26);
    } else {
        memcpy(father_age, "(record not found)", 19);
        memcpy(father_head, "(record not found)", 19);
        memcpy(father_body, "(record not found)", 19);
    }

    /* Where the game copied the father's traits onto the mother at conception,
       prefer those copies over anything the name scan produced -- and use them
       even when it produced nothing. They are the same numbers, read from the
       father himself at conception rather than from whoever still answers to
       his name at delivery, so they are correct in the two cases the scan is
       not: he has died in the interval, or a second living villager shares his
       name and the scan rightly refuses to guess.

       This replaces the head and body text only. His age is not copied by any
       game, so it keeps whatever the scan concluded, and a log can legitimately
       report a measured head and body beside an unavailable age. */
    if (g->father_head_copy != 0) {
        _snprintf(father_head, sizeof(father_head), "%d",
                  *(const int *)(mother + g->father_head_copy));
        father_head[sizeof(father_head) - 1] = '\0';
    }
    if (g->father_body_copy != 0) {
        _snprintf(father_body, sizeof(father_body), "%d",
                  *(const int *)(mother + g->father_body_copy));
        father_body[sizeof(father_body) - 1] = '\0';
    }
    written = fprintf(
        file,
        "Conception %d\n"
        "  Mother: %s\n"
        "    Age at conception: %d\n"
        "    Head: %d\n"
        "    Body: %d\n"
        "  Father: %s\n"
        "    Age at conception: %s\n"
        "    Head: %s\n"
        "    Body: %s\n"
        "  Babies in pregnancy: %d\n"
        "\n",
        existing_records + 1,
        mother_name,
        *(const int *)(mother + g->age),
        *(const int *)(mother + g->head),
        *(const int *)(mother + g->body),
        father_name,
        father_age,
        father_head,
        father_body,
        babies
    ) >= 0;
    /* Flush before closing so a write error is seen while the record can still
       be reported as failed. A record begins with its "Conception " marker, and
       that marker is what count_records counts -- so a half-flushed row would
       be counted as complete by the next call and shift every later record
       number. Checking the flush separately keeps the failure visible instead
       of hiding it in fclose. */
    if (fflush(file) != 0) {
        written = 0;
    }
    if (fclose(file) != 0) {
        return 0;
    }
    return written;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)instance;
    (void)reason;
    (void)reserved;
    return TRUE;
}


/* The original three argument entry point, kept so that a trampoline built
   before the father record was carried keeps working unchanged. It forwards
   with no father, which is exactly the behaviour it had. */
__declspec(dllexport) int __stdcall WriteParentageRecord(
    int game_id,
    const void *records_pointer,
    const void *mother_pointer
) {
    return WriteParentageRecordWithFather(
        game_id, records_pointer, mother_pointer, NULL);
}
