/* See village_identity.h for why this module exists and where the name lives. */
#include "village_identity.h"

#include <stdio.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#endif

/* The name's offset inside the save buffer, per game.  Measured across 348 real
   saves with zero failures, and cross-checked against each game's own save call
   site: every offset below lies inside the buffer length that game pushes, so
   the read can never leave the block the game is about to write.

       game   pushed buffer length   name offset
       VV1          0x0ABDC             0x00008
       VV2          0x30370             0x00008
       VV3          0x12F1C             0x12ECC
       VV4          0x1710C             0x170B8
       VV5          0x17D78             0x17D14

   VV1 and VV2 place the name at the very front of the buffer; the later three
   place it near the end.  An earlier reading of this data treated VV4 as an
   exception whose name sat a fixed distance from the end of the FILE, which was
   an artifact of assuming one header size for all five games.  Measured as
   buffer offsets, all five behave the same way. */
static const unsigned int NAME_OFFSETS[5] = {
    0x00008u,  /* VV1 */
    0x00008u,  /* VV2 */
    0x12ECCu,  /* VV3 */
    0x170B8u,  /* VV4 */
    0x17D14u   /* VV5 */
};

/* The save buffer begins at manager + 8 at every game's save call site
   (`lea eax, [esi + 8]`). */
#define SAVE_BUFFER_BIAS 8

unsigned int vv_village_name_offset(int game_id) {
    if (game_id < 1 || game_id > 5) {
        return 0u;
    }
    return NAME_OFFSETS[game_id - 1];
}

/* Whether a byte can appear in a name the player typed into the game.

   This deliberately accepts far more than the owner's own villages use.  Real
   names on this machine include "Poop", "Testificate!!!" and
   "HeathenParentSave1.0", so punctuation, digits and mixed case all occur, and
   a filter tuned to tidy names would reject the very saves it has to read.
   What it excludes is control bytes, which is what uninitialised or structural
   memory looks like -- the thing actually worth guarding against. */
static int is_name_byte(unsigned char c) {
    return c >= 0x20 && c <= 0x7E;
}

int vv_village_name(int game_id, const void *manager, char *out) {
    const unsigned char *buffer;
    unsigned int offset;
    size_t index = 0;

    if (out == NULL) {
        return 0;
    }
    out[0] = '\0';
    if (manager == NULL) {
        return 0;
    }
    if (game_id < 1 || game_id > 5) {
        return 0;
    }
    offset = vv_village_name_offset(game_id);

    buffer = (const unsigned char *)manager + SAVE_BUFFER_BIAS + offset;

#ifdef _WIN32
    /* The offsets are measured, but a mismatched build or an unexpected call
       path would turn a wrong offset into a fault inside the game's own save.
       An export that prints a name is never worth faulting a player's save, so
       the span is checked before it is touched. */
    if (IsBadReadPtr(buffer, VV_VILLAGE_NAME_MAX)) {
        return 0;
    }
#endif

    for (index = 0; index + 1 < VV_VILLAGE_NAME_MAX; ++index) {
        unsigned char c = buffer[index];
        if (c == 0) {
            break;
        }
        if (!is_name_byte(c)) {
            /* Something other than a name is here.  Report nothing rather than
               print a garbled village into a log header. */
            out[0] = '\0';
            return 0;
        }
        out[index] = (char)c;
    }
    out[index] = '\0';

    /* An empty name is not a failure of this reader -- a player may leave the
       village unnamed -- but it is not something worth printing either. */
    return index > 0 ? 1 : 0;
}

int vv_village_header(char *out, size_t size, const char *name, int save_id) {
    int has_name = name != NULL && name[0] != '\0';
    int has_save = save_id >= 1 && save_id <= 5;
    int written;

    if (out == NULL || size == 0) {
        return 0;
    }
    out[0] = '\0';

    if (has_name && has_save) {
        written = _snprintf_s(
            out, size, _TRUNCATE, "Village: %s (Save %d)\n", name, save_id);
    } else if (has_name) {
        written = _snprintf_s(out, size, _TRUNCATE, "Village: %s\n", name);
    } else if (has_save) {
        written = _snprintf_s(out, size, _TRUNCATE, "Save %d\n", save_id);
    } else {
        return 0;
    }
    return written < 0 ? 0 : written;
}

#ifdef _WIN32
/* The shared block is backed by the page file rather than a real file, so
   nothing is written to disk and nothing can be left behind beside the game.

   Its name carries the PROCESS ID, which is what actually keeps two games
   apart. A bare "Local\..." name is per-logon-session, not per-process, so two
   Virtual Villagers games running side by side would map the SAME block, and
   the second one to save would relabel the first one's parentage log with its
   own village. Scoping the name to the process makes each game see only its
   own, which matters here because the owner plays several of these games and
   keeps several villages in each.

   Sized for the assembled header: the name plus the fixed wrapper text and the
   slot. */
#define VV_SHARE_BYTES (VV_VILLAGE_NAME_MAX + 32)

static HANDLE vv_share_open(int create) {
    wchar_t name[64];
    _snwprintf_s(name, 64, _TRUNCATE, L"Local\\VVFP.VillageIdentity.%lu",
                 (unsigned long)GetCurrentProcessId());
    if (create) {
        return CreateFileMappingW(
            INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0,
            VV_SHARE_BYTES, name);
    }
    return OpenFileMappingW(FILE_MAP_READ, FALSE, name);
}

void vv_village_publish(const char *header) {
    HANDLE mapping;
    void *view;

    if (header == NULL) {
        return;
    }
    mapping = vv_share_open(1);
    if (mapping == NULL) {
        return;
    }
    view = MapViewOfFile(mapping, FILE_MAP_WRITE, 0, 0, VV_SHARE_BYTES);
    if (view != NULL) {
        /* Truncate rather than overflow: the block is sized for the longest
           header this module can assemble, so a longer one means the caller
           built something this module did not. */
        size_t length = strlen(header);
        if (length >= VV_SHARE_BYTES) {
            length = VV_SHARE_BYTES - 1;
        }
        memcpy(view, header, length);
        ((char *)view)[length] = '\0';
        UnmapViewOfFile(view);
    }
    /* The handle is deliberately NOT closed. A file mapping lives only while a
       handle to it is open, so closing here would discard the village the
       moment this call returns, and the parentage log -- which runs at a
       completely different time -- would never see it. It is one handle for
       the lifetime of the process, released when the game exits. */
}

int vv_village_recall(char *out, size_t size) {
    HANDLE mapping;
    const char *view;
    int recovered = 0;

    if (out == NULL || size == 0) {
        return 0;
    }
    out[0] = '\0';
    mapping = vv_share_open(0);
    if (mapping == NULL) {
        return 0;
    }
    view = (const char *)MapViewOfFile(mapping, FILE_MAP_READ, 0, 0,
                                       VV_SHARE_BYTES);
    if (view != NULL) {
        size_t index;
        for (index = 0; index + 1 < size && index + 1 < VV_SHARE_BYTES;
             ++index) {
            char c = view[index];
            if (c == '\0') {
                break;
            }
            out[index] = c;
        }
        out[index] = '\0';
        recovered = index > 0;
        UnmapViewOfFile(view);
    }
    CloseHandle(mapping);
    return recovered;
}
#else
void vv_village_publish(const char *header) {
    (void)header;
}

int vv_village_recall(char *out, size_t size) {
    if (out != NULL && size > 0) {
        out[0] = '\0';
    }
    return 0;
}
#endif
