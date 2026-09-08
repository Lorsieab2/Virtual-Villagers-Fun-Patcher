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
           v9[229] = a3;           // record + 0x394 = father id
           v9[215] = 2 or 3;       // record + 0x35C = litter size

   `246 * 4` reproducing the proven stride exactly is what establishes that
   `this` is the record array and `a2` is the MOTHER's record index.

   The litter size is written AFTER our hook runs, on the twins/triplets
   branches, so this file must not read record+0x35C -- see the note on
   `babies` in WriteParentageRecord below.

   FIELD OFFSETS

   Every offset here is proven, with its evidence named:

       +0x28   active flag     vv1_origins_icons.c VV_OCCUPIED_OFFSET
       +0x348  age             vv1_origins_icons.c VV_AGE_OFFSET
       +0x360  head            vv1_origins_icons.c VV_HEAD_OFFSET
       +0x364  body            vv1_origins_icons.c VV_CLOTHING_OFFSET
       +0x36C  villager id     sentinel 0xC7 compared at six sites
       +0x370  name buffer     sprintf destination at 0x43C696..0x43C6A1;
                               read back as a string at 0x418753..0x418760
       +0x394  father id       written from a3 at 0x43BC04

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

    VV1_RECORD_STRIDE = 0x3D8,
    VV1_RECORD_SLOTS = 256,

    VV1_ACTIVE_OFFSET = 0x28,
    VV1_AGE_OFFSET = 0x348,
    VV1_HEAD_OFFSET = 0x360,
    VV1_BODY_OFFSET = 0x364,
    VV1_ID_OFFSET = 0x36C,
    VV1_NAME_OFFSET = 0x370,
    VV1_NAME_CAPACITY = 0x1C,
    VV1_FATHER_ID_OFFSET = 0x394,

    /* The engine's "no villager" sentinel, compared as 0C7h at six sites
       including 0x41FBDC, 0x42242D and 0x43C7AF. */
    VV1_NO_VILLAGER = 0xC7,

    /* The owner asked for a roll "past ~256 villagers". One record per
       conception, and the record array itself holds 256 slots, so 256 records
       per file keeps a log to roughly one village's worth of births. */
    RECORDS_PER_FILE = 256
};

/* Names are engine-written with sprintf into a fixed 0x1C-byte field, so a
   name that exactly fills the buffer leaves no terminator. Copy into a local
   that is one byte longer and terminate it ourselves rather than trusting the
   buffer, and replace anything unprintable so one corrupt record cannot make
   the whole log unreadable. */
static void copy_villager_name(
    const unsigned char *record,
    char *out,
    size_t out_size
) {
    size_t index;
    const unsigned char *source = record + VV1_NAME_OFFSET;

    if (out_size == 0) {
        return;
    }
    for (index = 0; index + 1 < out_size && index < VV1_NAME_CAPACITY; ++index) {
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

/* Resolve a villager id to its record by scanning the array.

   The id at +0x36C is not the record index -- the conception routine stores
   the FATHER by id, not by slot, so the father must be looked up. Returns NULL
   when no active record carries the id, which happens legitimately if the
   father died between conception and this call. */
static const unsigned char *find_record_by_id(
    const unsigned char *records,
    int id
) {
    int slot;

    if (records == NULL || id == VV1_NO_VILLAGER) {
        return NULL;
    }
    for (slot = 0; slot < VV1_RECORD_SLOTS; ++slot) {
        const unsigned char *record = records + (size_t)slot * VV1_RECORD_STRIDE;
        if (*(const unsigned char *)(record + VV1_ACTIVE_OFFSET) != 1) {
            continue;
        }
        if (*(const int *)(record + VV1_ID_OFFSET) == id) {
            return record;
        }
    }
    return NULL;
}

/* Build "<exe folder>\Virtual Villagers 1 Parentage Log <n>.txt".

   Beside the executable, matching where the statistics companion writes, so a
   player finds both logs in the same place. */
static int build_log_path(int file_number, wchar_t *destination) {
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
        L"%ls\\Virtual Villagers 1 Parentage Log %d.txt",
        module_path,
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
static int select_log_file(wchar_t *destination, int *existing_records) {
    int number;

    *existing_records = 0;
    for (number = 1; number <= 4096; ++number) {
        int records;
        if (!build_log_path(number, destination)) {
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

   `records`      the villager record array base (the conception routine's
                  `this`), from which the mother is records + index * stride.
   `mother_index` the mother's record index (the routine's a2).
   `father_id`    the father's villager id (the routine's a3), NOT an index.
   `babies`       how many children this pregnancy carries.

   On `babies`: the caller passes 1. The engine decides twins and triplets on
   branches that run AFTER this hook and writes the result to record+0x35C, so
   reading that field here would report the previous pregnancy's litter size,
   or zero. Recording the value the engine has actually committed at this
   instant is correct; claiming a number the engine has not yet chosen would
   not be.

   Returns 1 when a record was written, 0 otherwise. The caller ignores the
   result -- a failed log must never disturb the game. */
__declspec(dllexport) int __stdcall WriteParentageRecord(
    const void *records_pointer,
    int mother_index,
    int father_id,
    int babies
) {
    const unsigned char *records = (const unsigned char *)records_pointer;
    const unsigned char *mother;
    const unsigned char *father;
    wchar_t path[MAX_LOG_PATH];
    FILE *file;
    char mother_name[VV1_NAME_CAPACITY + 1];
    char father_name[VV1_NAME_CAPACITY + 1];
    int written;
    int existing_records;

    if (records == NULL) {
        return 0;
    }
    if (mother_index < 0 || mother_index >= VV1_RECORD_SLOTS) {
        return 0;
    }
    mother = records + (size_t)mother_index * VV1_RECORD_STRIDE;
    if (*(const unsigned char *)(mother + VV1_ACTIVE_OFFSET) != 1) {
        return 0;
    }

    copy_villager_name(mother, mother_name, sizeof(mother_name));
    father = find_record_by_id(records, father_id);
    if (father != NULL) {
        copy_villager_name(father, father_name, sizeof(father_name));
    } else {
        /* The father is recorded by id, and that id may no longer resolve --
           he can die between conception and delivery. Say so plainly rather
           than dropping the record or inventing a name. */
        memcpy(father_name, "(unknown)", 10);
    }

    if (!select_log_file(path, &existing_records)) {
        return 0;
    }
    file = _wfopen(path, L"ab");
    if (file == NULL) {
        return 0;
    }
    written = fprintf(
        file,
        "Conception %d\n"
        "  Mother: %s\n"
        "    Age at conception: %d\n"
        "    Head: %d\n"
        "    Body: %d\n"
        "  Father: %s\n"
        "    Age at conception: %d\n"
        "    Head: %d\n"
        "    Body: %d\n"
        "  Babies in pregnancy: %d\n"
        "\n",
        existing_records + 1,
        mother_name,
        *(const int *)(mother + VV1_AGE_OFFSET),
        *(const int *)(mother + VV1_HEAD_OFFSET),
        *(const int *)(mother + VV1_BODY_OFFSET),
        father_name,
        father != NULL ? *(const int *)(father + VV1_AGE_OFFSET) : 0,
        father != NULL ? *(const int *)(father + VV1_HEAD_OFFSET) : 0,
        father != NULL ? *(const int *)(father + VV1_BODY_OFFSET) : 0,
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
