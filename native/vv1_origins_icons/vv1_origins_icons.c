#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shlobj.h>   /* SHGetFolderPathA / CSIDL_PERSONAL (mask sidecar path) */
#include <string.h>   /* strrchr / memcpy for the sidecar */
#include "vv1_mask_distribute.h"  /* Change Appearance for All distribution modes */
#include "vv1_head_buckets.h"     /* head-index buckets by hair colour (Heads override) */

#ifndef VV_AGE_OFFSET
#define VV_AGE_OFFSET 0x348
#endif
#ifndef VV_SKILL_FARMING_OFFSET
#define VV_SKILL_FARMING_OFFSET 0x3BC
#endif
#ifndef VV_SKILL_BUILDING_OFFSET
#define VV_SKILL_BUILDING_OFFSET 0x3C0
#endif
#ifndef VV_SKILL_RESEARCH_OFFSET
#define VV_SKILL_RESEARCH_OFFSET 0x3C4
#endif
#ifndef VV_SKILL_HEALING_OFFSET
#define VV_SKILL_HEALING_OFFSET 0x3C8
#endif
#ifndef VV_SKILL_PARENTING_OFFSET
#define VV_SKILL_PARENTING_OFFSET 0x3CC
#endif
#ifndef VV_LIKES_OFFSET
#define VV_LIKES_OFFSET 0x398
#endif
#ifndef VV_DISLIKES_OFFSET
#define VV_DISLIKES_OFFSET 0x3A8
#endif
#ifndef VV_LIKE_SLOT_COUNT
#define VV_LIKE_SLOT_COUNT 4
#endif
#ifndef VV_ALREADY_LIKES_TEXT
#define VV_ALREADY_LIKES_TEXT "Already 4 likes."
#endif
#ifndef VV_HEAD_OFFSET
#define VV_HEAD_OFFSET 0x360
#endif
#ifndef VV_CLOTHING_OFFSET
#define VV_CLOTHING_OFFSET 0x364
#endif
#ifndef VV_GENDER_OFFSET
#define VV_GENDER_OFFSET 0x350
#endif
#ifndef VV_GENDER_MALE
#define VV_GENDER_MALE 1
#endif
/* Purely cosmetic mask overlay choice (0 = none, 1..5 = mask variant).

   Deliberately NOT the native nursing-baby-icon flag at +0x29 -- that byte
   is real per-villager gameplay state (a genuinely nursing mother already
   has it set), so reusing it would either double-draw over her real baby
   icon or silently steal it. The render hook is additive and never reads or
   writes +0x29/+0x2A/+0x344.

   Where the choice actually lives is documented on VV_MASK_TABLE below: not
   in the villager record at all. */
#ifndef VV_MASK_COUNT
#define VV_MASK_COUNT 6
#endif

/* The chosen mask is NOT stored in the villager record. Two record bytes were
   tried and both proved occupied by the engine in ways a static displacement
   scan cannot see: +0x374 was inside the villager NAME buffer (names are
   written by bulk string copies, so nothing "references" the byte -- it was
   silently renaming villagers), and +0x3D4 is written by the save-LOAD path
   (all-zero across a 40-villager sample, but 14 of a real save's 210
   villagers had non-zero values on a fresh load with no mask ever set).
   A scan of all 211 records found no run of >=4 always-zero bytes, and every
   always-zero byte is the high byte of a dword holding a small value.

   So the selection lives in a table the PATCH owns, in its appended .vv1md
   R/W section: 256
   villagers, one nibble each. The engine cannot touch it, so no amount of
   save/load or villager churn can corrupt game state through it, and the
   worst possible failure is a cosmetic stale entry.

   Keyed by record INDEX -- the same key the render hook uses, which it forms
   exactly as the engine does at 0x437798 (manager + index*0x3D8). The dialog
   only holds a record POINTER, so it converts back using the villager-array
   base the render hook stashes every frame. Every conversion is fully
   validated; anything unexpected fails closed to "no mask", never a write. */
/* Mask scratch now lives in the exe's dedicated appended R/W section .vv1md
   (base 0x00491000), NOT the borrowed .data BSS tail (owner: no shared caves).
   These MUST match DATA_SCRATCH_BASE_VA + the same offsets in the build script:
   TABLE = base+0x00, MANAGER = base+0x98, SAVE_SLOT = base+0x1F4,
   BIRTH_DIRTY = base+0x1FC. */
#define VV_MASK_SCRATCH_BASE 0x00491000u
#define VV_MASK_TABLE ((unsigned char *)(VV_MASK_SCRATCH_BASE + 0x00))   /* .vv1md R/W */
#define VV_MASK_MANAGER (*(unsigned char **)(VV_MASK_SCRATCH_BASE + 0x98)) /* .vv1md R/W */
#define VV_MASK_SAVE_SLOT (*(unsigned int *)(VV_MASK_SCRATCH_BASE + 0x1F4)) /* .vv1md R/W; 1..5, 0 = fail closed */
#define VV_MASK_BIRTH_DIRTY (*(unsigned char *)(VV_MASK_SCRATCH_BASE + 0x1FC)) /* .vv1md R/W; newborn clear needs sidecar retry */
#define VV_RECORD_STRIDE 0x3D8
#define VV_MASK_SLOTS 256
#define VV_MASK_TABLE_BYTES (VV_MASK_SLOTS / 2)
#define VV_MASK_FIRST_SAVE_SLOT 1
#define VV_MASK_LAST_SAVE_SLOT 5
#define VV_OCCUPIED_OFFSET 0x28  /* record[+0x28] == 1 when the slot is a live
                                    villager (the compositor's own occupied
                                    check at 0x4377a5: cmp byte[+0x28],1). */

static int vv1_mask_index(unsigned char *villager) {
    unsigned char *base = VV_MASK_MANAGER;
    size_t delta;
    size_t index;
    if (base == NULL || villager == NULL || villager < base) {
        return -1;  /* engine not running yet, or a pointer we don't own */
    }
    delta = (size_t)(villager - base);
    if (delta % VV_RECORD_STRIDE != 0) {
        return -1;  /* not a record boundary -- refuse rather than guess */
    }
    index = delta / VV_RECORD_STRIDE;
    if (index >= VV_MASK_SLOTS) {
        return -1;
    }
    return (int)index;
}

static int vv1_mask_current_slot(void);
static int vv1_mask_prepare_slot(void);

static unsigned char vv1_mask_get(unsigned char *villager) {
    int index = vv1_mask_index(villager);
    unsigned char packed;
    unsigned char value;
    if (!vv1_mask_prepare_slot() || index < 0) {
        return 0;
    }
    packed = VV_MASK_TABLE[index >> 1];
    value = (index & 1)
        ? (unsigned char)(packed >> 4)
        : (unsigned char)(packed & 0x0F);
    /* Sidecars are external, user-writable input.  A corrupt high nibble
       must never become an atlas row or picker choice; treat it as None at
       the single accessor boundary shared by Details and Change Appearance. */
    return (value < VV_MASK_COUNT) ? value : 0;
}

static void vv1_mask_set(unsigned char *villager, unsigned char value) {
    int index = vv1_mask_index(villager);
    unsigned char *slot;
    if (!vv1_mask_prepare_slot() || index < 0 || value >= VV_MASK_COUNT) {
        return;
    }
    slot = &VV_MASK_TABLE[index >> 1];
    *slot = (index & 1)
        ? (unsigned char)((*slot & 0x0F) | (value << 4))
        : (unsigned char)((*slot & 0xF0) | value);
}

/* Per-slot "has this slot ever been seen occupied" latch (DLL BSS, zeroed at
   load). The sweep may only clear a slot that was seen ALIVE and is now free --
   never a slot that has simply not loaded yet. */
static unsigned char vv1_mask_seen_alive[VV_MASK_SLOTS];

/* The sidecar is keyed by the game's numbered save slot.  This is deliberately
   kept in the DLL rather than inferred from villager fingerprints: two save
   slots can contain identical villagers, and a fingerprint is not a save
   identity.  -1 means no slot has been loaded in this process yet. */
static int vv1_mask_loaded_slot = -1;

static int vv1_mask_current_slot(void) {
    unsigned int slot = VV_MASK_SAVE_SLOT;
    if (slot < VV_MASK_FIRST_SAVE_SLOT || slot > VV_MASK_LAST_SAVE_SLOT) {
        return 0;  /* slot zero, invalid values, and a not-yet-captured slot */
    }
    return (int)slot;
}

static void vv1_mask_clear_state(void) {
    memset(VV_MASK_TABLE, 0, VV_MASK_TABLE_BYTES);
    memset(vv1_mask_seen_alive, 0, sizeof(vv1_mask_seen_alive));
    VV_MASK_BIRTH_DIRTY = 0;
}

/* Synchronize the DLL's latches with the executable-captured slot.  The exe
   hook resets its restore latch and frame scratch whenever the slot changes;
   this handles the DLL-owned table/latch half before sidecar bytes are used. */
static int vv1_mask_prepare_slot(void) {
    int slot = vv1_mask_current_slot();
    if (slot != vv1_mask_loaded_slot) {
        vv1_mask_clear_state();
        vv1_mask_loaded_slot = slot;
    }
    return slot;
}

/* Slot-reuse guard. The mask table is keyed by record INDEX, so if a masked
   villager dies and a NEW villager is later born into the same record slot,
   the newcomer would inherit the dead villager's mask. Rather than a
   collidable fingerprint (villagers can share names/ages/stats by luck, and
   their skills/likes are mutated by upgrades), this clears a table entry whose
   record slot has gone free.

   CRITICAL (VV2 lesson): only clear a slot that was SEEN alive at least once
   and is now free -- do NOT clear a slot that has never loaded yet. The sidecar
   restore runs at startup, BEFORE the .ldw populates the villager array, so at
   that point every record reads occupied!=1; the old unconditional sweep wiped
   every just-restored mask right there, which is why masks vanished on reload
   and only came back when Change Appearance reloaded the sidecar with the
   village already live. Latching on seen-alive makes the startup sweep a no-op
   (nothing has been seen alive yet) while still clearing genuinely dead slots
   once the village is running. Fail-safe when the engine isn't up (base 0). */
static int vv1_mask_sweep_dead(void) {
    unsigned char *base = VV_MASK_MANAGER;
    int index, cleared = 0;
    if (base == NULL) {
        return 0;  /* engine not up yet -> the 256 records aren't mapped */
    }
    for (index = 0; index < VV_MASK_SLOTS; index++) {
        unsigned char *rec = base + (size_t)index * VV_RECORD_STRIDE;
        unsigned char *slot;
        unsigned char before;
        if (rec[VV_OCCUPIED_OFFSET] == 1) {
            vv1_mask_seen_alive[index] = 1;  /* latch: this slot IS a real villager */
            continue;                        /* live villager -> keep its mask */
        }
        if (!vv1_mask_seen_alive[index]) {
            continue;  /* never loaded yet (e.g. startup restore) -> DON'T wipe */
        }
        slot = &VV_MASK_TABLE[index >> 1];
        before = *slot;
        *slot = (index & 1)
            ? (unsigned char)(*slot & 0x0F)
            : (unsigned char)(*slot & 0xF0);
        if (*slot != before) {
            cleared++;  /* this dead slot actually held a mask */
        }
    }
    return cleared;  /* caller persists so the cleared state survives a restart */
}

/* --- Mask sidecar persistence -------------------------------------------
   The mask table (VV_MASK_TABLE, 128 bytes in .data) is patch-owned memory
   and is NEVER written into the villager record or the game's .ldw save --
   that is the safest option for a purely cosmetic overlay, because a bug in
   the mask code can then never corrupt a real village. To survive quitting
   the game, the table is mirrored to a small sidecar file that lives NEXT TO
   the save, inside the game's own per-exe save folder:

       <My Documents>\LDW\<exe basename>\vv1_masks_<slot>.dat

   Format (little-endian): 4-byte magic 'VM01' + the raw 128 table bytes.
   Keyed by save slot first, then villager record INDEX, the same key the
   render hook and picker use.  Slot zero and every value outside the exact
   five numbered game slots fail closed and never touch a sidecar.

   Fail-closed for invalid persistence: any failure (no Documents folder,
   missing file, short read, wrong magic, unmapped table) leaves the in-memory
   table empty, so the worst case is "masks not restored" -- never a crash and
   never a damaged save. File I/O is deliberately NOT done from DllMain (that
   runs under the loader lock, where SHGetFolderPath/CreateFile can deadlock);
   it happens from Vv1MaskRestore (called by the exe at startup, outside the
   lock) and from the picker's own open/commit handlers. */
#define VV_MASK_SIDECAR_MAGIC 0x31304D56u  /* 'V' 'M' '0' '1' */
static int vv1_mask_sidecar_path(char *out, size_t n, int slot) {
    char docs[MAX_PATH];
    char exe[MAX_PATH];
    char *base;
    char *dot;
    DWORD exelen;
    if (slot < VV_MASK_FIRST_SAVE_SLOT || slot > VV_MASK_LAST_SAVE_SLOT) {
        return 0;
    }
    if (FAILED(SHGetFolderPathA(NULL, CSIDL_PERSONAL, NULL, 0, docs))) {
        return 0;
    }
    /* Reject a truncated path: GetModuleFileNameA returns nSize when the real
       path is >= the buffer, and on some Windows versions leaves it without a
       NUL terminator, so `== 0` alone would let a truncated/unterminated `exe`
       through. Fail open (masks just aren't persisted) rather than parse it. */
    exelen = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (exelen == 0 || exelen >= MAX_PATH) {
        return 0;
    }
    base = strrchr(exe, '\\');
    base = base ? base + 1 : exe;
    dot = strrchr(base, '.');
    if (dot != NULL) {
        *dot = '\0';  /* strip ".exe" -> the save-folder basename */
    }
    /* Make sure the folder chain exists (the game normally makes it already;
       CreateDirectory is a harmless no-op when it does). wsprintfA (user32,
       already linked) is used instead of the CRT's snprintf because this DLL
       links without the CRT -- but wsprintfA takes no destination-size bound
       (it caps only at its own 1024-byte scratch), so a redirected Documents
       folder or a long exe basename could make the longest of these formats
       overrun the caller's `out` buffer. Bound it here against `n`: the final
       "<docs>\LDW\<base>\vv1_masks_5.dat" is the longest string written, so if
       that (plus NUL) doesn't fit, fail open (return 0 -> masks simply aren't
       persisted, never a stack smash). Reserve a conservative 32-byte suffix
       budget for the slot and extension rather than hand-counting it. */
    if ((size_t)lstrlenA(docs) + (size_t)lstrlenA(base) + 5 + 32 + 1 > n) {
        return 0;
    }
    wsprintfA(out, "%s\\LDW", docs);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s", docs, base);
    CreateDirectoryA(out, NULL);
    wsprintfA(out, "%s\\LDW\\%s\\vv1_masks_%u.dat", docs, base,
              (unsigned int)slot);
    return 1;
}

static int vv1_mask_sidecar_save(void) {
    char path[MAX_PATH];
    HANDLE file;
    DWORD wrote;
    unsigned int magic = VV_MASK_SIDECAR_MAGIC;
    int slot = vv1_mask_prepare_slot();
    if (!slot || !vv1_mask_sidecar_path(path, sizeof(path), slot)) {
        return 0;
    }
    file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return 0;
    }
    if (!WriteFile(file, &magic, sizeof(magic), &wrote, NULL)
        || wrote != sizeof(magic)
        || !WriteFile(file, VV_MASK_TABLE, VV_MASK_TABLE_BYTES, &wrote, NULL)
        || wrote != VV_MASK_TABLE_BYTES) {
        CloseHandle(file);
        return 0;
    }
    CloseHandle(file);
    return 1;
}

static void vv1_mask_sidecar_load(void) {
    char path[MAX_PATH];
    HANDLE file;
    DWORD got;
    unsigned int magic = 0;
    unsigned char buf[VV_MASK_TABLE_BYTES];
    int slot = vv1_mask_prepare_slot();
    /* Missing, malformed, or unreadable sidecars must not leave a previous
       slot's in-memory choices visible. Slot changes already clear this in
       vv1_mask_prepare_slot; clearing here also makes a same-slot re-open
       deterministic and fail closed. */
    memset(VV_MASK_TABLE, 0, VV_MASK_TABLE_BYTES);
    if (!slot || !vv1_mask_sidecar_path(path, sizeof(path), slot)) {
        return;
    }
    file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                       FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) {
        return;  /* no sidecar yet -> the table is already cleared */
    }
    if (ReadFile(file, &magic, sizeof(magic), &got, NULL) && got == sizeof(magic)
        && magic == VV_MASK_SIDECAR_MAGIC
        && ReadFile(file, buf, sizeof(buf), &got, NULL) && got == sizeof(buf)) {
        int swept;
        memcpy(VV_MASK_TABLE, buf, sizeof(buf));
        /* Drop any restored mask whose slot isn't a live villager now -- this
           clears entries left by villagers who died since the save, and (for a
           different village loaded from the same folder) any freed slots. */
        swept = vv1_mask_sweep_dead();
        CloseHandle(file);
        if (swept) {
            /* Persist the clears so a later restart can't restore a dead
               slot's mask onto whoever reuses that record slot. */
            vv1_mask_sidecar_save();
        }
        return;
    }
    CloseHandle(file);
}

/* ---- Details-screen portrait ("bighead") mask overlay --------------------
   The world mask hook draws masks in the village loop (sub_437790); the
   Details portrait renders through a SEPARATE scaled compositor (sub_437340 ->
   the shared scaled draw sub_409410). This overlays the mask on that portrait
   by re-issuing the engine's OWN scaled draw with a mask sprite built through
   the engine's OWN sprite-from-file constructor, so the engine scales the mask
   to the age-scaled portrait exactly like it scaled the head -- for free, at
   any size (VV2's method). Everything is done via engine calls; the DLL never
   writes foreign memory (Malwarebytes-safe).

   Atlas Images/mask_atlas.png = 7 facing-cols x 5 colour-rows, 40x160 cells
   (same grid as the world sheets). The exe wrapper preserves the complete
   seven-argument native head-draw tuple. This function reuses that tuple's
   exact x, y, facing, scale, enable flag, and draw-manager wrapper; it changes
   only the atlas and colour row, plus the same scale-aware vertical art
   registration used by the village head replay. That is the VV5 rule:
   replay the head draw, never reconstruct it from screen constants or age. */
#define VV_MASK_ATLAS_COLS   7   /* mask_atlas.png: 7 facing cols x 5 colour rows, 40x160 cells, matching the generator and VV1 head atlas */
/* The village wrapper seats this same atlas with lift=(scale*15)>>5. Reusing
   the identical scale-aware registration here keeps child/adult/portrait scale
   changes attached to the native head instead of reviving fixed age buckets. */
#define VV_PORTRAIT_LIFT_MUL   15
#define VV_PORTRAIT_LIFT_SHIFT 5

/* Engine functions are called directly by their fixed .text addresses (stable
   -- patches live in .shr caves and never move .text). The two engine calls
   here are __thiscall (this in ecx, callee cleans the stack); MSVC in C mode
   won't take __thiscall on a function-pointer typedef, so they go through
   inline asm, which also lets us match the exact push order + ret-size. The
   plain operator-new is __cdecl and goes through a typedef. */
typedef void * (__cdecl *vv_new_fn)(unsigned int size);
#define VV_ADDR_OPERATOR_NEW  0x0044AF03u
#define VV_ADDR_SPRITE_CTOR   0x0040A070u   /* thiscall(this,file,cols,rows) ret 0xC */
#define VV_ADDR_SCALED_DRAW   0x00409410u   /* thiscall(this,atlas,x,a2,idx,a4,scale) ret 0x18 */

static void *vv_portrait_mask_sprite = NULL;  /* 0 = untried, 1 = failed, else sprite */

static void *vv1_portrait_mask_atlas(void) {
    void *obj, *built;
    const char *file = "mask_atlas.png";
    int cols = VV_MASK_ATLAS_COLS, rows = 5;
    if (vv_portrait_mask_sprite != NULL) {
        return (vv_portrait_mask_sprite == (void *)1) ? NULL : vv_portrait_mask_sprite;
    }
    obj = ((vv_new_fn)VV_ADDR_OPERATOR_NEW)(0x34);   /* operator new(0x34) */
    if (obj == NULL) {
        vv_portrait_mask_sprite = (void *)1;          /* don't retry */
        return NULL;
    }
    built = NULL;
    __asm {
        push rows
        push cols
        push file
        mov  ecx, obj
        mov  eax, VV_ADDR_SPRITE_CTOR
        call eax                 /* thiscall; callee cleans the 3 args (ret 0xC) */
        mov  built, eax
    }
    vv_portrait_mask_sprite = (built == NULL) ? (void *)1 : built;
    return (vv_portrait_mask_sprite == (void *)1) ? NULL : built;
}

/* The exe-side village mask hook fetches the built mask-atlas engine sprite
   through this export (resolved once, then cached in .data by the hook). The
   sprite is built lazily through the engine ctor, which needs graphics up --
   always true when a villager head is being drawn -- so building on first call
   from the draw path is safe. Returns NULL on failure; the hook then skips the
   mask (fail-open) rather than drawing garbage. Shares the single cached atlas
   with the Details portrait, so both paths use the same sprite. */
__declspec(dllexport) void *__stdcall Vv1GetMaskSprite(void) {
    return vv1_portrait_mask_atlas();
}

/* Called by the shared sub_437340 wrapper AFTER the stock head was drawn from a
   duplicate tuple. `draw_wrapper` is the exact ECX received by 0x409410, and
   args[0..6] are the untouched original seven draw arguments:
     atlas, x, y, row, facing, scale, enable.
   The wrapper returns with `ret 0x1C`, so this @16 helper never owns the native
   argument cleanup. */
__declspec(dllexport) int __stdcall Vv1DrawPortraitMask(void *gameobj,
                                                        void *record,
                                                        void *draw_wrapper,
                                                        const int *args) {
    unsigned char *g = (unsigned char *)gameobj;
    unsigned char *rec = (unsigned char *)record;
    unsigned char packed, mask;
    void *sprite;
    size_t delta;
    int index, cell;
    int x, y, col, scale, enable;
    if (g == NULL || rec == NULL || rec < g || draw_wrapper == NULL || args == NULL) {
        return 0;
    }
    /* villager index from THIS gameobj (record = gameobj + index*stride), not
       the world hook's cached base -- so it's correct in the Details context. */
    delta = (size_t)(rec - g);
    if ((delta % VV_RECORD_STRIDE) != 0) {
        return 0;
    }
    index = (int)(delta / VV_RECORD_STRIDE);
    if (index < 0 || index >= VV_MASK_SLOTS) {
        return 0;
    }
    packed = VV_MASK_TABLE[index >> 1];
    mask = (index & 1) ? (unsigned char)(packed >> 4) : (unsigned char)(packed & 0x0F);
    if (mask == 0 || mask > 5) {
        return 0;                                  /* no mask -> nothing to draw */
    }
    sprite = vv1_portrait_mask_atlas();
    if (sprite == NULL) {
        return 0;
    }
    /* The engine's scaled draw takes ROW and COLUMN as SEPARATE args (arg4=row,
       arg5=col; the accessor 0x409f90 does srcRect.y = cellH*row, .x =
       cellW*col, each clamped to rows/cols). So the mask cell is:
         row = mask-1  (colour; table is 1-based, 0 = none)
         col = args[4], the exact head-facing column from this draw.
       A linear (mask-1)*cols+col fed into the ROW arg (not COL) is what clamped
       everything to the last row (chief) in the earlier broken build. */
    cell = mask - 1;   /* ROW = colour (0-based) */
    x = args[1];
    scale = args[5];
    y = args[2] - ((scale * VV_PORTRAIT_LIFT_MUL) >> VV_PORTRAIT_LIFT_SHIFT);
    col = args[4];
    enable = args[6];
    /* Same 7-arg push order as the native head draw (deepest first). The
       exact renderer wrapper, x, facing, scale, and enable flag are replayed;
       only atlas/row and the scale-aware atlas registration differ. */
    __asm {
        push enable
        push scale
        push col
        push cell
        push y
        push x
        push sprite
        mov  ecx, draw_wrapper
        mov  eax, VV_ADDR_SCALED_DRAW
        call eax
    }
    return 1;
}

/* Exe-callable, exported so the patch can restore masks once at startup
   (outside the loader lock). __stdcall/no args to match the exe's own
   GetProcAddress-and-call convention for the other Origins exports. */
/* Change Appearance for All -- apply a whole-village mask distribution.
 * mode: 0=single (use single_mask, 0..5), 1=random, 2=VV5-style, 3=equal.
 * Reads the live occupied villagers off the render-hook-stashed array base,
 * runs the pure distribution (vv1_mask_distribute.h), writes each result into
 * the .data table by record index, and persists via the sidecar. Never touches
 * a villager record or the save. Exported for the exe's upgrade handler to
 * call after it charges the 450k tech points. Fail-safe when the engine isn't
 * up (base 0) or the village is empty. */
#define VV_GOLDEN_CHILD_PTR (*(unsigned char **)0x0048B614) /* current golden child record, 0=none */

__declspec(dllexport) int __stdcall Vv1MaskApplyDistribution(int mode,
                                                             int single_mask) {
    unsigned char *base = VV_MASK_MANAGER;
    int rec_index[VV_MASK_SLOTS];
    unsigned char is_male[VV_MASK_SLOTS];
    unsigned char out[VV_MASK_SLOTS];
    int scratch[VV_MASK_SLOTS];
    int count = 0, golden = -1, i, nchanged = 0;
    unsigned int rng;
    unsigned char *golden_rec;

    /* A distribution is a write operation too: synchronize the captured
       save slot first and fail closed for slot zero/unvalidated values. */
    if (!vv1_mask_prepare_slot()) {
        return 0;
    }
    base = VV_MASK_MANAGER;
    if (base == NULL) {
        return 0;
    }
    /* compact list of the currently occupied villagers */
    for (i = 0; i < VV_MASK_SLOTS; i++) {
        unsigned char *rec = base + (size_t)i * VV_RECORD_STRIDE;
        if (rec[VV_OCCUPIED_OFFSET] != 1) {
            continue;
        }
        rec_index[count] = i;
        is_male[count] = (unsigned char)(
            *(int *)(rec + VV_GENDER_OFFSET) == VV_GENDER_MALE);
        count++;
    }
    if (count == 0) {
        return 0;
    }
    /* map the golden child's record pointer to a position in the compact list */
    golden_rec = VV_GOLDEN_CHILD_PTR;
    if (golden_rec != NULL && golden_rec >= base) {
        size_t delta = (size_t)(golden_rec - base);
        if (delta % VV_RECORD_STRIDE == 0) {
            int gidx = (int)(delta / VV_RECORD_STRIDE);
            for (i = 0; i < count; i++) {
                if (rec_index[i] == gidx) {
                    golden = i;
                    break;
                }
            }
        }
    }
    rng = GetTickCount() ^ 0x9E3779B9u;   /* varies per apply; fine to be cheap */
    switch (mode) {
    case 1:
        vv1_dist_random(count, &rng, out);
        break;
    case 2:
        vv1_dist_vv5(count, golden, &rng, scratch, out);
        break;
    case 3:
        vv1_dist_equal(count, is_male, &rng, scratch, out);
        break;
    case 4:
        vv1_dist_random_with_none(count, &rng, out);
        break;
    default:
        if (single_mask < 0 || single_mask > 5) {
            single_mask = 0;
        }
        vv1_dist_single(count, (unsigned char)single_mask, out);
        break;
    }
    /* write results into the mask table by record index, counting only slots
       that actually change (so an apply that lands every villager on the mask
       they already wear -- e.g. "None" over an already-unmasked village --
       reports 0 changes and the caller charges nothing), then persist. */
    for (i = 0; i < count; i++) {
        int idx = rec_index[i];
        unsigned char *slot = &VV_MASK_TABLE[idx >> 1];
        unsigned char v = out[i];
        unsigned char old = (idx & 1)
            ? (unsigned char)(*slot >> 4)
            : (unsigned char)(*slot & 0x0F);
        if (old == v) {
            continue;
        }
        *slot = (idx & 1)
            ? (unsigned char)((*slot & 0x0F) | (v << 4))
            : (unsigned char)((*slot & 0xF0) | v);
        nchanged++;
    }
    if (nchanged) {
        vv1_mask_sidecar_save();
    }
    return nchanged;
}

__declspec(dllexport) void __stdcall Vv1MaskRestore(void) {
    vv1_mask_sidecar_load();
}

/* Called once from the main village render tick on every frame, after the
   one-shot restore gate. This is deliberately separate from Details and from
   any selection/pickup flag: it observes the authoritative occupied byte for
   every record, clears only slots that were previously seen alive and are now
   free, and writes the sidecar only when a non-zero mask was actually removed
   or an exact newborn boundary marked a reused mask dirty.
   Static wiring proves cadence/guards; runtime reuse behavior remains a player
   acceptance gate. */
__declspec(dllexport) void __stdcall Vv1MaskTick(void) {
    int swept;
    int birth_dirty;
    if (!vv1_mask_prepare_slot()) {
        return;  /* slot not captured yet -> no table or sidecar mutation */
    }
    birth_dirty = VV_MASK_BIRTH_DIRTY != 0;
    swept = vv1_mask_sweep_dead();
    if (swept || birth_dirty) {
        /* Keep the dirty flag set when the sidecar cannot be written; a later
           frame retries instead of allowing the old sidecar entry to return
           after reload. */
        if (vv1_mask_sidecar_save()) {
            VV_MASK_BIRTH_DIRTY = 0;
        }
    }
}

static HINSTANCE module_instance;

/* None of this DLL's three dialog templates (IDD_ORIGINS_TECH,
   IDD_ORIGINS_VILLAGER, IDD_ORIGINS_APPEARANCE -- see the .rc file's
   "DIALOGEX 0, 0, ..." lines) specify DS_CENTER, so without this,
   DialogBoxParamA places each one at literal screen pixel (0,0) -- the
   real display's extreme top-left corner. That is easy to miss by
   accident in a small windowed game, but VV1 is an old game rendered at
   a small logical resolution that SDL scales up to fill the real
   display (SDL_RenderSetLogicalSize is imported and used for this).
   Once the real display is much larger than the game's own logical
   resolution, as it always is in fullscreen, a dialog pinned at (0,0)
   is effectively unreachable rather than merely off-center.

   Centers on the owner window's own current rect -- which SDL keeps
   accurate to the real on-screen window, fullscreen or windowed, unlike
   the game's internal logical resolution -- then clamps to that owner's
   monitor work area so the title bar and buttons stay fully reachable
   even if the owner window is smaller than the dialog or sits near a
   monitor edge. */
static void center_dialog_on_owner(HWND dialog) {
    HWND owner = GetWindow(dialog, GW_OWNER);
    RECT dlg_rect;
    RECT owner_rect;
    MONITORINFO monitor_info;
    int width;
    int height;
    int x;
    int y;

    if (owner == NULL || !IsWindow(owner)) {
        owner = GetForegroundWindow();
        if (owner != NULL && !IsWindow(owner)) {
            owner = NULL;
        }
    }
    if (!GetWindowRect(dialog, &dlg_rect)) {
        return;
    }
    width = dlg_rect.right - dlg_rect.left;
    height = dlg_rect.bottom - dlg_rect.top;

    if (owner != NULL && GetWindowRect(owner, &owner_rect)) {
        x = owner_rect.left + ((owner_rect.right - owner_rect.left) - width) / 2;
        y = owner_rect.top + ((owner_rect.bottom - owner_rect.top) - height) / 2;
    } else {
        x = (GetSystemMetrics(SM_CXSCREEN) - width) / 2;
        y = (GetSystemMetrics(SM_CYSCREEN) - height) / 2;
    }

    monitor_info.cbSize = sizeof(monitor_info);
    if (GetMonitorInfo(
            MonitorFromWindow(
                owner != NULL ? owner : dialog,
                MONITOR_DEFAULTTONEAREST
            ),
            &monitor_info
        )) {
        const RECT *work_rect = &monitor_info.rcWork;
        if (x + width > work_rect->right) {
            x = work_rect->right - width;
        }
        if (y + height > work_rect->bottom) {
            y = work_rect->bottom - height;
        }
        if (x < work_rect->left) {
            x = work_rect->left;
        }
        if (y < work_rect->top) {
            y = work_rect->top;
        }
    }

    SetWindowPos(dialog, NULL, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
}

/* Reported: the game's own view goes black behind the dialog while it's
   open, and (more importantly) stays black even after it closes.
   Two earlier attempts at fixing this from inside this DLL both failed
   badly enough to need a live revert:

   1. Calling the game's own native fullscreen leave/enter pair directly
      (raw hardcoded VAs through an engine singleton pointer) -- crashed
      the game immediately: the singleton's address turned out to fall
      inside a byte range this repo's own Origins village-wide payload
      already claims as scratch cave space, so on a patched build that
      address no longer holds what it holds in the stock exe.
   2. Forcing a synchronous RedrawWindow(..., RDW_UPDATENOW | RDW_FRAME)
      on the owner right after DialogBoxParamA returned -- hung the whole
      game instead (confirmed via process inspection: no crash dialog,
      just an unresponsive process that had to be force-closed), almost
      certainly by reentering something in SDL's or the driver's
      fullscreen present path from inside this DLL's own call stack
      before the game's own loop had a chance to resume on its own.

   The actual root cause (found by checking VV2's already-merged,
   playtest-confirmed fix for the identical symptom -- VV2 shares this
   exact file) is neither of those: in exclusive SDL fullscreen, the
   game's own SDL runtime minimizes the window the instant it loses
   focus to our modal dialog, dropping the player to the bare desktop
   behind it -- which is what reads as "black" and, apparently, is also
   what the freeze-on-close was: restoring from a real Win32-minimized
   state while SDL still believes it owns exclusive fullscreen is a
   known-hazardous transition. vv1_prep_fullscreen below heads this off
   before it happens, and vv1_surface_dialog (called from each dialog's
   own WM_INITDIALOG) makes sure the dialog itself is actually visible
   above the game's topmost fullscreen surface once it doesn't minimize
   out from under it. Neither call touches game internals: both are
   standard, documented Win32/SDL APIs against the game's own
   already-loaded SDL2.dll and our own dialog window. */
static void vv1_surface_dialog(HWND window) {
    SetWindowPos(
        window, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
    );
    SetForegroundWindow(window);
}

static void vv1_prep_fullscreen(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    if (sdl != NULL) {
        typedef int(__cdecl * set_hint_t)(const char *, const char *);
        set_hint_t set_hint = (set_hint_t)GetProcAddress(sdl, "SDL_SetHint");
        if (set_hint != NULL) {
            set_hint("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0");
        }
    }
}

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_APPEARANCE = 203,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1011,   /* row 11 = Change Appearance for All (always-Buy) */
    ID_CHECK_FIRST = 1100,
    /* IDC_HEAD_PREVIEW/IDC_BODY_PREVIEW: owner-draw STATIC controls that
       preview the real head/body sprite cropped from the stock game art
       (see appearance_draw below) -- these reuse the same control IDs the
       plain-text labels used before this dialog grew real art. */
    IDC_HEAD_PREVIEW = 2000,
    ID_HEAD_PREV = 2001,
    ID_HEAD_NEXT = 2002,
    IDC_BODY_PREVIEW = 2010,
    ID_BODY_PREV = 2011,
    ID_BODY_NEXT = 2012,
    ID_MASK_PREV = 2020,
    IDC_MASK_LABEL = 2021,
    ID_MASK_NEXT = 2022,
    /* Owner-draw mask preview, matching VV5's picker layout for parity. */
    IDC_MASK_PREVIEW = 2023,
    IDB_HEAD_M = 3001,
    IDB_HEAD_F = 3002,
    IDB_BODY_M = 3011,
    IDB_BODY_F = 3012,
    /* One 40-wide column, six 76px rows: row 0 blank for "(None)", rows 1-5
       the five masks head-on. Built by build_vv1_heathen_mask_sheets.py, so
       the strip is indexed by the mask value directly. */
    IDB_MASK = 3021,
    STATE_VILLAGER = 0x10000,
    STATE_VILLAGE_WIDE = 0x20000,
    STATE_RUNNING_ONLY = 0x40000,
    STATE_VILLAGE_WIDE_BUY = 0x80000
};

/* Every strip built by scripts/build_vv1_appearance_bitmaps.py is a single
   40-wide column holding all 20 variant rows stacked vertically (one
   villager-record index per row), 65 pixels tall each -- exactly the cell
   geometry the stock exe's own sprite-sheet loader computes for these same
   source images (see that script's docstring for the decompiled proof). */
#define APPEARANCE_CELL_W 40
#define APPEARANCE_CELL_H 65

/* Only one appearance picker can be open at a time (it is a modal dialog),
   so a single file-scope slot for its working state is sufficient -- this
   mirrors module_instance above, which is the same kind of single-instance
   global already used in this file. The tech-point balance check and
   charge live in the caller (the same reused code path every other
   Villager Upgrades row already charges through), not here: this dialog
   only ever previews and either keeps or reverts the head/body fields.

   valid_count is not a fixed 20 for both fields: the villager-creation
   code assigns head and body their random starting value from RNG(19)
   for male villagers and RNG(20) for everyone else (confirmed by
   decompiling the exact-build initializer), so male villagers only have
   19 valid values (0-18) for both fields, not 20 -- cycling through 19
   for a male villager would write a value the stock renderer was never
   given a sprite for. */
static struct {
    unsigned char *villager;
    int original_head;
    int original_body;
    int original_mask;
    int valid_count;
    int male;
    /* Set once the player accepts the head-genetics warning below, so it
       only ever shows once per picker session (the OFFICIAL spreadsheet's
       "changing it first shows..." wording), not on every arrow click. */
    int head_warned;
} appearance_state;

static const char *vv1_mask_name(int mask) {
    switch (mask) {
        case 1: return "Blue Mask";
        case 2: return "Orange Mask";
        case 3: return "Red Mask";
        case 4: return "Purple Mask";
        case 5: return "Tribal Chief Mask";
        default: return "(None)";
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
    }
    return TRUE;
}

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        int row_count = villager_menu
            ? 5
            : ((lparam & STATE_RUNNING_ONLY) != 0
                ? 7
                : ((lparam & STATE_VILLAGE_WIDE) != 0 ? 9 : 6));
        int row;
        center_dialog_on_owner(window);
        vv1_surface_dialog(window);
        /* Only rows 0-8 carry a status-badge ICON (ID_CHECK_FIRST+row) in the
           two-column .rc; the Equal Division rows (9/10) and Change Appearance
           for All (11) have no badge at all (matching VV2's layout, where those
           rows never report an "owned" state), so there is nothing to hide for
           them -- their GetDlgItem is NULL and ShowWindow is a no-op even if
           the bound reached them.  Hide all badges up front; the loop below
           re-shows the ones whose owned bit is set. */
        for (row = 0; row < 9; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                if (villager_menu) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Done");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
                } else if (village_wide_buy && row >= 6) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                } else {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                }
            } else if ((lparam & (1 << (8 + row))) != 0) {
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            EndDialog(window, (INT_PTR)(command - ID_BUY_FIRST));
            return TRUE;
        }
        if (command == IDCANCEL) {
            EndDialog(window, -1);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, -1);
        return TRUE;
    }
    return FALSE;
}

static int show_upgrade_menu(int villager_menu, int dialog_state) {
    int resource = villager_menu ? IDD_ORIGINS_VILLAGER : IDD_ORIGINS_TECH;
    HWND owner = GetForegroundWindow();
    int result;
    vv1_prep_fullscreen();
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        owner,
        upgrade_dialog,
        dialog_state
    );
    return result;
}

/* Crops row `index` (one villager-record value = one cell row) out of the
   strip for the current villager's sex and draws it into the owner-draw
   control's rect.

   The sprite is fitted, not stretched: it is scaled by the SMALLER of the
   two axis ratios and centred, so its aspect ratio is preserved and any
   leftover space stays background. Stretching each axis independently (what
   this did before) distorted every preview, and made VV1's pickers visibly
   different from VV5's for the same art. This is VV5's own math, so head and
   body -- and now the mask preview too, which is generated on that same
   40x65 cell -- render identically in both games' pickers. */
static void appearance_draw(DRAWITEMSTRUCT *item, int bitmap_id, int index) {
    const int cell_h = APPEARANCE_CELL_H;
    RECT rc = item->rcItem;
    int width = rc.right - rc.left;
    int height = rc.bottom - rc.top;
    HBRUSH background = CreateSolidBrush(RGB(236, 236, 236));
    HBITMAP bitmap;
    HDC source;
    HBITMAP previous;
    double scale_x, scale_y, scale;
    int draw_w, draw_h, draw_x, draw_y;

    FillRect(item->hDC, &rc, background);
    DeleteObject(background);

    bitmap = LoadBitmapA(module_instance, MAKEINTRESOURCEA(bitmap_id));
    if (bitmap == NULL) {
        return;
    }
    source = CreateCompatibleDC(item->hDC);
    previous = (HBITMAP)SelectObject(source, bitmap);

    scale_x = (double)width / APPEARANCE_CELL_W;
    scale_y = (double)height / cell_h;
    scale = scale_x < scale_y ? scale_x : scale_y;
    draw_w = (int)(APPEARANCE_CELL_W * scale);
    draw_h = (int)(cell_h * scale);
    draw_x = rc.left + (width - draw_w) / 2;
    draw_y = rc.top + (height - draw_h) / 2;

    SetStretchBltMode(item->hDC, COLORONCOLOR);
    StretchBlt(
        item->hDC, draw_x, draw_y, draw_w, draw_h,
        source, 0, index * cell_h, APPEARANCE_CELL_W, cell_h,
        SRCCOPY
    );

    SelectObject(source, previous);
    DeleteDC(source);
    DeleteObject(bitmap);
}

static void appearance_repaint(HWND window, int control_id) {
    InvalidateRect(GetDlgItem(window, control_id), NULL, TRUE);
}

static void appearance_revert(void) {
    *(int *)(appearance_state.villager + VV_HEAD_OFFSET) = appearance_state.original_head;
    *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET) = appearance_state.original_body;
    vv1_mask_set(appearance_state.villager, (unsigned char)appearance_state.original_mask);
}

/* The head field is hereditary (it's the one the villager's children
   inherit from), so the OFFICIAL Origins Upgrade Prompts spreadsheet
   requires a one-time OK/Cancel warning the first time the player
   actually tries to change it in this picker session -- Cancel leaves
   that specific arrow click without effect, no field write at all.
   Returns 1 to proceed (already warned, or just accepted), 0 to abort
   the click that triggered it. */
static int vv1_confirm_head_genetics_warning(HWND window) {
    if (appearance_state.head_warned) {
        return 1;
    }
    if (MessageBoxA(
            window,
            "Warning: This will change the villager's head genetics.",
            "Villager Upgrades",
            MB_OKCANCEL | MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND
        ) != IDOK) {
        return 0;
    }
    appearance_state.head_warned = 1;
    return 1;
}

/* Writes each tentative value straight into the live villager record so
   the stock renderer (which already reads these exact fields every
   frame, the same field the F6 clothing-cycle cheat uses for body) shows
   the change immediately behind this dialog -- no separate preview
   rendering is built or needed here. Reverted on Cancel/close. On OK,
   returns 1 if the head or body actually differs from what it was when
   the picker opened (the caller charges and keeps the change), or 2 if
   OK was pressed but nothing was actually changed (the caller charges
   nothing and reports that explicitly, per the OFFICIAL spreadsheet --
   fields already match their originals in that case, so there is
   nothing to revert either). The tech-point balance check and charge
   are the caller's job (the exact same charge code every other Villager
   Upgrades row already uses) -- this dialog never touches tech points,
   only the head/body fields. */
static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        /* appearance_state was already populated by ShowOriginsAppearancePicker
           before this dialog was created; WM_DRAWITEM below paints the
           starting values on the dialog's own first paint, nothing else to
           do here besides positioning (see center_dialog_on_owner). The
           mask row has no owner-draw preview (it's a plain text label,
           not a bitmap strip cell), so its starting text is set directly
           here rather than through WM_DRAWITEM. */
        center_dialog_on_owner(window);
        vv1_surface_dialog(window);
        SetDlgItemTextA(
            window,
            IDC_MASK_LABEL,
            vv1_mask_name(vv1_mask_get(appearance_state.villager))
        );
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        DRAWITEMSTRUCT *item = (DRAWITEMSTRUCT *)lparam;
        if (item->CtlID == IDC_HEAD_PREVIEW) {
            appearance_draw(
                item,
                appearance_state.male ? IDB_HEAD_M : IDB_HEAD_F,
                *(int *)(appearance_state.villager + VV_HEAD_OFFSET)
            );
            return TRUE;
        }
        if (item->CtlID == IDC_MASK_PREVIEW) {
            appearance_draw(
                item,
                IDB_MASK,
                vv1_mask_get(appearance_state.villager)
            );
            return TRUE;
        }
        if (item->CtlID == IDC_BODY_PREVIEW) {
            appearance_draw(
                item,
                appearance_state.male ? IDB_BODY_M : IDB_BODY_F,
                *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET)
            );
            return TRUE;
        }
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        int count = appearance_state.valid_count;
        int *head = (int *)(appearance_state.villager + VV_HEAD_OFFSET);
        int *body = (int *)(appearance_state.villager + VV_CLOTHING_OFFSET);
        if (command == ID_HEAD_PREV) {
            if (!vv1_confirm_head_genetics_warning(window)) {
                return TRUE;
            }
            *head = (*head + count - 1) % count;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == ID_HEAD_NEXT) {
            if (!vv1_confirm_head_genetics_warning(window)) {
                return TRUE;
            }
            *head = (*head + 1) % count;
            appearance_repaint(window, IDC_HEAD_PREVIEW);
            return TRUE;
        }
        if (command == ID_BODY_PREV) {
            *body = (*body + count - 1) % count;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == ID_BODY_NEXT) {
            *body = (*body + 1) % count;
            appearance_repaint(window, IDC_BODY_PREVIEW);
            return TRUE;
        }
        if (command == ID_MASK_PREV || command == ID_MASK_NEXT) {
            unsigned char mask = vv1_mask_get(appearance_state.villager);
            int next = command == ID_MASK_PREV
                ? (mask + VV_MASK_COUNT - 1) % VV_MASK_COUNT
                : (mask + 1) % VV_MASK_COUNT;
            vv1_mask_set(appearance_state.villager, (unsigned char)next);
            SetDlgItemTextA(window, IDC_MASK_LABEL, vv1_mask_name(next));
            appearance_repaint(window, IDC_MASK_PREVIEW);
            return TRUE;
        }
        if (command == IDOK) {
            int mask_changed = (vv1_mask_get(appearance_state.villager)
                    != (unsigned char)appearance_state.original_mask);
            int changed = (*head != appearance_state.original_head)
                || (*body != appearance_state.original_body)
                || mask_changed;
            /* Persist the mask table the moment a mask edit is confirmed, so
               the choice survives a quit even without the exe's own save. */
            if (mask_changed) {
                vv1_mask_sidecar_save();
            }
            EndDialog(window, changed ? 1 : 2);
            return TRUE;
        }
        if (command == IDCANCEL) {
            appearance_revert();
            EndDialog(window, 0);
            return TRUE;
        }
    } else if (message == WM_CLOSE) {
        appearance_revert();
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

__declspec(dllexport) int __stdcall ShowOriginsAppearancePicker(
    int villager_ptr
) {
    unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)villager_ptr;
    HWND owner;
    int result;
    if (villager == NULL) {
        return 0;
    }
    /* Refresh the table from the sidecar before showing the chooser, so the
       previewed/edited mask reflects what was persisted (safe here -- we are
       far outside the loader lock). */
    vv1_mask_sidecar_load();
    appearance_state.villager = villager;
    appearance_state.original_head = *(int *)(villager + VV_HEAD_OFFSET);
    appearance_state.original_body = *(int *)(villager + VV_CLOTHING_OFFSET);
    appearance_state.original_mask = vv1_mask_get(villager);
    appearance_state.male = *(int *)(villager + VV_GENDER_OFFSET) == VV_GENDER_MALE;
    /* 20 for both sexes: the head/body sheets are 20 rows and index 19 is the
       GOLDEN CHILD's head (pale, hairless) and body (gold) -- the last frame of
       male_heads/bodies (user-confirmed). Villager-creation RNG only rolls
       0..18 for males so a normal male never gets index 19, which is why the
       picker used to cap males at 19 -- but the sprite exists and renders fine,
       and excluding it left a golden child whose appearance was changed with no
       way to cycle back to gold. Including 19 lets the golden look be restored
       (and set) from the picker. Female row 19 is a normal head, not golden. */
    appearance_state.valid_count = 20;
    appearance_state.head_warned = 0;
    vv1_prep_fullscreen();
    owner = GetForegroundWindow();
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_ORIGINS_APPEARANCE),
        owner,
        appearance_dialog,
        (LPARAM)(UINT_PTR)villager
    );
    return result;
}

/* ===================== Change Appearance for All ======================= */
/* Whole-village chooser (dialog 204). Per-sex Head/Body/Mask selections plus a
   whole-village mask override. On OK it applies the per-sex head/body/mask to
   every occupied villager of that sex (head/body are normal record fields the
   game itself edits; the mask goes only into the .data table), then, unless
   "Use choices above" is selected, overrides ALL masks with the chosen
   distribution / single colour via Vv1MaskApplyDistribution. Never touches the
   .ldw save. The 450k charge stays the exe's job (same contract as the
   per-villager picker). */
#define IDD_ORIGINS_APPEARANCE_ALL 204
/* Per-gender head/body variant counts (same ranges the per-sex cyclers use). */
#define VV_HEAD_COUNT_M 19
#define VV_HEAD_COUNT_F 20
#define VV_BODY_COUNT_M 19
#define VV_BODY_COUNT_F 20

/* Whole-village override selections (each has its own "Off"):
   mask_override:   0 = use per-sex Mask cyclers; 1..4 = a Vv1MaskApplyDistribution
                    distribution mode (1 Random-All-5, 2 VV5-style, 3 Equal,
                    4 Random-All-5+No-Mask); 10..15 = single village-wide colour
                    (10 None, 11 Blue, 12 Orange, 13 Red, 14 Purple, 15 Chief).
   heads_override:  0 = per-sex Head cyclers; 1 = random by gender; 2..6 = all one
                    hair colour (2 Black, 3 Brown, 4 Red/Ginger, 5 Blonde, 6 Other).
   bodies_override: 0 = per-sex Body cyclers; 1 = random by gender. */
static struct {
    int male_head, male_body, male_mask;
    int female_head, female_body, female_mask;
    int mask_override;
    int heads_override;
    int bodies_override;
    unsigned int rng;
} forall_state;

/* Selections default to -1 = "No change": cycling steps -1 -> 0 -> ... ->
   count-1 -> -1, and a field left at -1 is not written on apply. This is why
   the upgrade doesn't force every villager to head/body/mask index 0. */
#define FORALL_NO_CHANGE (-1)

static int forall_cycle(int cur, int delta, int count) {
    int v = cur + delta;
    if (v < FORALL_NO_CHANGE) {
        return count - 1;
    }
    if (v >= count) {
        return FORALL_NO_CHANGE;
    }
    return v;
}

/* Apply every selected override to all occupied villagers. Returns the number
   of "effects" applied so the caller can bill ONLY when something changed (an
   all-Off / all-No-change OK must not deduct). Head/Body are ordinary record
   fields; masks go to the .data table (never the .ldw save). */
static int forall_apply(void) {
    unsigned char *base = VV_MASK_MANAGER;
    int mo = forall_state.mask_override;
    int ho = forall_state.heads_override;
    int bo = forall_state.bodies_override;
    int i, occ = 0, changed = 0;
    if (base == NULL) {
        return 0;
    }
    forall_state.rng ^= GetTickCount() * 2654435761u;
    for (i = 0; i < VV_MASK_SLOTS; i++) {
        unsigned char *rec = base + (size_t)i * VV_RECORD_STRIDE;
        int male, hcount, bcount;
        if (rec[VV_OCCUPIED_OFFSET] != 1) {
            continue;
        }
        occ++;
        male = (*(int *)(rec + VV_GENDER_OFFSET) == VV_GENDER_MALE);
        hcount = male ? VV_HEAD_COUNT_M : VV_HEAD_COUNT_F;
        bcount = male ? VV_BODY_COUNT_M : VV_BODY_COUNT_F;
        /* HEAD -- count a change only when the field actually differs, so an
           apply that re-selects a value every villager already has bills
           nothing (see the no-charge-if-nothing-changed contract). */
        if (ho == 0) {
            int h = male ? forall_state.male_head : forall_state.female_head;
            if (h != FORALL_NO_CHANGE && *(int *)(rec + VV_HEAD_OFFSET) != h) {
                *(int *)(rec + VV_HEAD_OFFSET) = h; changed++;
            }
        } else if (ho == 1) {
            int h;
            forall_state.rng = forall_state.rng * 1664525u + 1013904223u;
            h = (int)((forall_state.rng >> 16) % (unsigned int)hcount);
            if (*(int *)(rec + VV_HEAD_OFFSET) != h) {
                *(int *)(rec + VV_HEAD_OFFSET) = h; changed++;
            }
        } else {
            int h = vv1_head_pick(male, ho - 2, &forall_state.rng);
            if (h >= 0 && *(int *)(rec + VV_HEAD_OFFSET) != h) {
                *(int *)(rec + VV_HEAD_OFFSET) = h; changed++;
            }
        }
        /* BODY */
        if (bo == 0) {
            int b = male ? forall_state.male_body : forall_state.female_body;
            if (b != FORALL_NO_CHANGE && *(int *)(rec + VV_CLOTHING_OFFSET) != b) {
                *(int *)(rec + VV_CLOTHING_OFFSET) = b; changed++;
            }
        } else {  /* bo == 1: random by gender */
            int b;
            forall_state.rng = forall_state.rng * 1664525u + 1013904223u;
            b = (int)((forall_state.rng >> 16) % (unsigned int)bcount);
            if (*(int *)(rec + VV_CLOTHING_OFFSET) != b) {
                *(int *)(rec + VV_CLOTHING_OFFSET) = b; changed++;
            }
        }
        /* MASK: per-sex only when there is no whole-village mask override */
        if (mo == 0) {
            int m = male ? forall_state.male_mask : forall_state.female_mask;
            if (m != FORALL_NO_CHANGE && vv1_mask_get(rec) != (unsigned char)m) {
                vv1_mask_set(rec, (unsigned char)m); changed++;
            }
        }
    }
    if (mo != 0 && occ > 0) {
        /* Whole-village mask override -- charge only for villagers whose mask
           actually changed (Vv1MaskApplyDistribution returns that count and
           persists the sidecar itself only when something changed). */
        if (mo >= 1 && mo <= 4) {
            changed += Vv1MaskApplyDistribution(mo, 0);      /* distribution mode */
        } else {
            changed += Vv1MaskApplyDistribution(0, mo - 10); /* 10..15 -> single 0..5 */
        }
        return changed;
    }
    if (changed) {
        vv1_mask_sidecar_save();
    }
    return changed;
}

static void forall_draw_one(DRAWITEMSTRUCT *item, int bitmap, int sel) {
    if (sel == FORALL_NO_CHANGE) {
        RECT rc = item->rcItem;
        HBRUSH bg = CreateSolidBrush(RGB(236, 236, 236));
        FillRect(item->hDC, &rc, bg);
        DeleteObject(bg);
        SetBkMode(item->hDC, TRANSPARENT);
        DrawTextA(item->hDC, "No change", -1, &rc,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    } else {
        appearance_draw(item, bitmap, sel);
    }
}

static void forall_draw_item(DRAWITEMSTRUCT *item) {
    switch (item->CtlID) {
    case 2100: forall_draw_one(item, IDB_HEAD_M, forall_state.male_head); break;
    case 2110: forall_draw_one(item, IDB_BODY_M, forall_state.male_body); break;
    case 2120: forall_draw_one(item, IDB_MASK,  forall_state.male_mask);  break;
    case 2200: forall_draw_one(item, IDB_HEAD_F, forall_state.female_head); break;
    case 2210: forall_draw_one(item, IDB_BODY_F, forall_state.female_body); break;
    case 2220: forall_draw_one(item, IDB_MASK,  forall_state.female_mask); break;
    default: break;
    }
}

static INT_PTR CALLBACK forall_dialog(HWND window, UINT message,
                                      WPARAM wparam, LPARAM lparam) {
    if (message == WM_INITDIALOG) {
        forall_state.male_head = forall_state.male_body = forall_state.male_mask = FORALL_NO_CHANGE;
        forall_state.female_head = forall_state.female_body = forall_state.female_mask = FORALL_NO_CHANGE;
        forall_state.mask_override = 0;
        forall_state.heads_override = 0;
        forall_state.bodies_override = 0;
        forall_state.rng = GetTickCount();
        /* Surface + center on the owner exactly like the per-villager picker
           and the tech menu (WM_INITDIALOG handlers at appearance_dialog /
           upgrade_dialog). vv1_prep_fullscreen() is the pre-DialogBox global
           prep and was already called by ShowOriginsAppearanceForAll before
           this dialog opened; calling it again here (instead of centering)
           left the whole-village dialog pinned at (0,0) -- effectively
           unreachable in fullscreen. */
        center_dialog_on_owner(window);
        vv1_surface_dialog(window);
        /* radios managed in code (they span groupboxes -- don't rely on WS_GROUP
           across boxes; VV2's lesson). Each override group starts on its Off. */
        CheckDlgButton(window, 2300, BST_CHECKED);   /* Mask Distribution: Off */
        CheckDlgButton(window, 2320, BST_CHECKED);   /* Village-wide Heads: Off */
        CheckDlgButton(window, 2330, BST_CHECKED);   /* Village-wide Bodies: Off */
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        forall_draw_item((DRAWITEMSTRUCT *)lparam);
        return TRUE;
    } else if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        switch (id) {
        /* male */
        case 2101: forall_state.male_head = forall_cycle(forall_state.male_head, -1, 19); appearance_repaint(window, 2100); return TRUE;
        case 2102: forall_state.male_head = forall_cycle(forall_state.male_head, +1, 19); appearance_repaint(window, 2100); return TRUE;
        case 2111: forall_state.male_body = forall_cycle(forall_state.male_body, -1, 19); appearance_repaint(window, 2110); return TRUE;
        case 2112: forall_state.male_body = forall_cycle(forall_state.male_body, +1, 19); appearance_repaint(window, 2110); return TRUE;
        case 2121: forall_state.male_mask = forall_cycle(forall_state.male_mask, -1, VV_MASK_COUNT); appearance_repaint(window, 2120); return TRUE;
        case 2122: forall_state.male_mask = forall_cycle(forall_state.male_mask, +1, VV_MASK_COUNT); appearance_repaint(window, 2120); return TRUE;
        /* female */
        case 2201: forall_state.female_head = forall_cycle(forall_state.female_head, -1, 20); appearance_repaint(window, 2200); return TRUE;
        case 2202: forall_state.female_head = forall_cycle(forall_state.female_head, +1, 20); appearance_repaint(window, 2200); return TRUE;
        case 2211: forall_state.female_body = forall_cycle(forall_state.female_body, -1, 20); appearance_repaint(window, 2210); return TRUE;
        case 2212: forall_state.female_body = forall_cycle(forall_state.female_body, +1, 20); appearance_repaint(window, 2210); return TRUE;
        case 2221: forall_state.female_mask = forall_cycle(forall_state.female_mask, -1, VV_MASK_COUNT); appearance_repaint(window, 2220); return TRUE;
        case 2222: forall_state.female_mask = forall_cycle(forall_state.female_mask, +1, VV_MASK_COUNT); appearance_repaint(window, 2220); return TRUE;
        case IDOK:
            /* Do NOT apply here -- the charge is checked/taken in
               ShowOriginsAppearanceForAll first (VV2's DLL-side-charge model),
               and forall_apply runs only if the player could afford it. */
            EndDialog(window, 1);
            return TRUE;
        case IDCANCEL:
            EndDialog(window, 0);
            return TRUE;
        default:
            if ((id >= 2300 && id <= 2304) || (id >= 2310 && id <= 2315)) {
                /* Mask override: the Distribution box (2300-2304) and the
                   Single-Colour box (2310-2315) are alternative mask paths but
                   ONE mutually-exclusive selection -- managed in code across the
                   boxes (VV2: don't trust WS_GROUP across boxes). Off (2300)
                   re-enables the per-sex Mask cyclers; any other grays them. */
                int r, use_per_sex;
                for (r = 2300; r <= 2304; r++) CheckDlgButton(window, r, r == id ? BST_CHECKED : BST_UNCHECKED);
                for (r = 2310; r <= 2315; r++) CheckDlgButton(window, r, r == id ? BST_CHECKED : BST_UNCHECKED);
                switch (id) {
                case 2300: forall_state.mask_override = 0; break;    /* Off */
                case 2301: forall_state.mask_override = 2; break;    /* VV5-style */
                case 2302: forall_state.mask_override = 4; break;    /* Random (All 5 + No Mask) */
                case 2303: forall_state.mask_override = 1; break;    /* Random (All 5) */
                case 2304: forall_state.mask_override = 3; break;    /* Equal Colors */
                default:   forall_state.mask_override = 10 + (id - 2310); break;  /* single 10..15 */
                }
                use_per_sex = (forall_state.mask_override == 0);
                EnableWindow(GetDlgItem(window, 2120), use_per_sex);
                EnableWindow(GetDlgItem(window, 2121), use_per_sex);
                EnableWindow(GetDlgItem(window, 2122), use_per_sex);
                EnableWindow(GetDlgItem(window, 2220), use_per_sex);
                EnableWindow(GetDlgItem(window, 2221), use_per_sex);
                EnableWindow(GetDlgItem(window, 2222), use_per_sex);
                return TRUE;
            }
            if (id >= 2320 && id <= 2326) {
                /* Village-wide Heads: Off re-enables the per-sex Head cyclers. */
                int r, use_per_sex;
                for (r = 2320; r <= 2326; r++) CheckDlgButton(window, r, r == id ? BST_CHECKED : BST_UNCHECKED);
                forall_state.heads_override = id - 2320;
                use_per_sex = (forall_state.heads_override == 0);
                EnableWindow(GetDlgItem(window, 2100), use_per_sex);
                EnableWindow(GetDlgItem(window, 2101), use_per_sex);
                EnableWindow(GetDlgItem(window, 2102), use_per_sex);
                EnableWindow(GetDlgItem(window, 2200), use_per_sex);
                EnableWindow(GetDlgItem(window, 2201), use_per_sex);
                EnableWindow(GetDlgItem(window, 2202), use_per_sex);
                return TRUE;
            }
            if (id >= 2330 && id <= 2331) {
                /* Village-wide Bodies: Off re-enables the per-sex Body cyclers. */
                int r, use_per_sex;
                for (r = 2330; r <= 2331; r++) CheckDlgButton(window, r, r == id ? BST_CHECKED : BST_UNCHECKED);
                forall_state.bodies_override = id - 2330;
                use_per_sex = (forall_state.bodies_override == 0);
                EnableWindow(GetDlgItem(window, 2110), use_per_sex);
                EnableWindow(GetDlgItem(window, 2111), use_per_sex);
                EnableWindow(GetDlgItem(window, 2112), use_per_sex);
                EnableWindow(GetDlgItem(window, 2210), use_per_sex);
                EnableWindow(GetDlgItem(window, 2211), use_per_sex);
                EnableWindow(GetDlgItem(window, 2212), use_per_sex);
                return TRUE;
            }
            break;
        }
    } else if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

/* Tech-points field on the game-context object (the exe menu code's own
   [edi+0xA2FC] afford check). The exe passes that context pointer in. */
#define VV_TECH_POINTS_OFFSET 0xA2FC
#define VV_FORALL_COST 450000

/* Whole-village chooser. Takes the game-context pointer (edi in the exe's Buy
   dispatch). On OK it checks the balance and, only if the player can afford it,
   deducts 450,000 tech points and applies the change to every villager --
   VV2's DLL-side-charge model, so the exe side is a single one-arg call with
   no charge logic to overrun a fixed handler box. Returns 1 if applied (the
   exe need do nothing further), 0 if cancelled or unaffordable. */
__declspec(dllexport) int __stdcall ShowOriginsAppearanceForAll(int gamectx_ptr) {
    unsigned char *ctx = (unsigned char *)(UINT_PTR)(unsigned int)gamectx_ptr;
    int *tech;
    HWND owner;
    int result;
    if (ctx == NULL) {
        return 0;
    }
    tech = (int *)(ctx + VV_TECH_POINTS_OFFSET);
    vv1_mask_sidecar_load();      /* start from the persisted table */
    vv1_prep_fullscreen();
    owner = GetForegroundWindow();
    result = (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_ORIGINS_APPEARANCE_ALL),
        owner,
        forall_dialog,
        0
    );
    if (result != 1) {
        return 0;                 /* cancelled -> no charge, no change */
    }
    /* Nothing chosen (every group on Off and every per-sex cycler on No change)
       must NOT bill. */
    {
        int any = forall_state.mask_override || forall_state.heads_override
                  || forall_state.bodies_override
                  || forall_state.male_head != FORALL_NO_CHANGE
                  || forall_state.female_head != FORALL_NO_CHANGE
                  || forall_state.male_body != FORALL_NO_CHANGE
                  || forall_state.female_body != FORALL_NO_CHANGE
                  || forall_state.male_mask != FORALL_NO_CHANGE
                  || forall_state.female_mask != FORALL_NO_CHANGE;
        if (!any) {
            MessageBoxA(owner,
                        "No appearance options were selected. No tech points deducted.",
                        "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
            return 0;
        }
    }
    if (*tech < VV_FORALL_COST) {
        MessageBoxA(owner, "Not enough tech points. This upgrade costs 450,000.",
                    "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
        return 0;
    }
    /* Head is hereditary -- warn once before committing if any head will change
       (a village-wide Heads override, or either per-sex Head cycler moved). */
    if (forall_state.heads_override != 0
        || forall_state.male_head != FORALL_NO_CHANGE
        || forall_state.female_head != FORALL_NO_CHANGE) {
        if (MessageBoxA(owner,
                "Warning: This will change the head genetics of every villager "
                "of the selected sex, affecting their descendants.\r\n\r\nProceed?",
                "Change Appearance for All",
                MB_OKCANCEL | MB_ICONWARNING) != IDOK) {
            return 0;
        }
    }
    if (forall_apply() <= 0) {
        return 0;                 /* nothing actually applied -> no charge */
    }
    *tech -= VV_FORALL_COST;
    MessageBoxA(owner, "Change Appearance for All applied to every villager.",
                "Change Appearance for All", MB_OK | MB_ICONINFORMATION);
    return 1;
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenuState(
    int villager_menu,
    int dialog_state
) {
    return show_upgrade_menu(villager_menu, dialog_state);
}

__declspec(dllexport) int __stdcall ShowOriginsUpgradeMenu(
    int villager_menu,
    int state
) {
    int dialog_state = 0;
    if (villager_menu) {
        unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)state;
        int row;
        int running_like = 0;
        int running_dislike = 0;
        int available_like = 0;
        if (villager != NULL) {
            if (*(int *)(villager + VV_AGE_OFFSET) <= 100) {
                dialog_state |= 1 << 0;
            }
            if (*(int *)(villager + VV_SKILL_FARMING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_BUILDING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_RESEARCH_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_HEALING_OFFSET) == 100
                && *(int *)(villager + VV_SKILL_PARENTING_OFFSET) == 100) {
                dialog_state |= 1 << 1;
            }
            for (row = 0; row < VV_LIKE_SLOT_COUNT; ++row) {
                int like = *(int *)(villager + VV_LIKES_OFFSET + row * 4);
                if (like == 38) {
                    running_like = 1;
                } else if (like == -1) {
                    available_like = 1;
                }
                if (*(int *)(villager + VV_DISLIKES_OFFSET + row * 4) == 38) {
                    running_dislike = 1;
                }
            }
            if (running_like) {
                dialog_state |= 1 << 2;
            } else if (!available_like) {
                dialog_state |= 1 << (8 + 2);
            }
            if (*(int *)(villager + VV_AGE_OFFSET) == 360) {
                dialog_state |= 1 << 3;
            }
        }
    } else {
        if ((state & 1) != 0) {
            dialog_state |= 1 << 3;
        }
        if ((state & 2) != 0) {
            dialog_state |= 1 << 4;
        }
    }
    return show_upgrade_menu(villager_menu, dialog_state);
}

/* Row names for the confirmation prompt below. Kept here rather than as
   ASM string-table entries: the .shr string budget is already tight, and
   this is the only place these particular names are ever shown, so
   there's no reason to spend .shr bytes on them at all. */
static const char *vv1_tech_row_name(int row) {
    switch (row) {
    case 0: return "Time Warp";
    case 1: return "Island Event";
    case 2: return "Barrel of Babies";
    case 3: return "Tech Point Doubler";
    case 4: return "Food Point Doubler";
    case 5: return "Full Heal / Cure All";
    case 6: return "Grant Running to All Villagers";
    case 7: return "Grant Full Mastery to All Villagers";
    case 8: return "All Villagers are Exactly 18";
    case 9: return "Equal Division of Labor (Includes Parenting)";
    case 10: return "Equal Division of Labor (No Parenting)";
    case 11: return "Change Appearance for All";
    default: return "Origins upgrade";
    }
}

/* Correct singular/plural for a villager count, matching the OFFICIAL
   Origins Upgrade Prompts spreadsheet's own note: "counts use correct
   singular/plural ('1 Villager' vs '3 Villagers')". */
static const char *vv1_vpl(unsigned int n) { return n == 1 ? "Villager" : "Villagers"; }

/* Renders value with thousands separators ("1000000" -> "1,000,000") for
   the confirmation prompt below -- wsprintfA's %d has no such thing, and
   the OFFICIAL spreadsheet's confirm wording always shows costs comma-
   formatted. out must be at least 16 bytes; every VV1 upgrade cost is at
   most 7 digits (1,000,000), so that is always enough room. */
static void vv1_format_cost(int value, char *out) {
    char digits[16];
    int count = 0;
    int position;
    int written = 0;
    if (value < 0) {
        value = 0;
    }
    do {
        digits[count++] = (char)('0' + (value % 10));
        value /= 10;
    } while (value > 0 && count < (int)sizeof(digits));
    for (position = count - 1; position >= 0; --position) {
        out[written++] = digits[position];
        if (position > 0 && (position % 3) == 0) {
            out[written++] = ',';
        }
    }
    out[written] = '\0';
}

static const char *vv1_detail_row_name(int row) {
    switch (row) {
    case 0: return "Grant Youth";
    case 1: return "Grant Full Mastery";
    case 2: return "Grant Running";
    case 3: return "Set Age to 18";
    case 4: return "Change Appearance";
    default: return "Origins upgrade";
    }
}

/* Shared confirmation prompt: every purchasable row on both the Tech
   screen (including its Village-Wide rows) and the Villager Details
   screen routes through this before any charge or change happens.
   Names the row and its exact cost rather than a generic warning, and
   uses OK/Cancel (not Yes/No) -- matching the wording style already
   proposed for VV5's own Task9 Origins upgrades
   (native/vv5_task9_origins/vv5_task9_origins.c's ConfirmVV5Task9Action)
   for parity across games. Only ever called for a real purchase, not
   for removing an owned doubler -- the caller (menu) only reaches this
   on the Buy path, after it already knows the row isn't being removed. */
__declspec(dllexport) int __stdcall ShowOriginsPermanentChangeConfirm(
    int is_detail,
    int row,
    int cost
) {
    char message[192];
    char cost_text[16];
    const char *name = is_detail ? vv1_detail_row_name(row) : vv1_tech_row_name(row);
    vv1_format_cost(cost, cost_text);
    wsprintfA(
        message,
        "Do you want to buy %s for %s tech points?\r\nPress OK to confirm, or Cancel.",
        name,
        cost_text
    );
    return MessageBoxA(
        GetForegroundWindow(),
        message,
        is_detail ? "Villager Upgrades" : "Origins Upgrades",
        MB_OKCANCEL | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
    ) == IDOK;
}

/* Full Heal/Cure All Villagers: the .shr helper only calls this once it
   already knows at least one villager was sick or below full health (and
   has already charged for it), so this never needs its own "nothing
   happened" branch -- that message is a plain string shown directly by
   the helper without ever resolving this export. */
__declspec(dllexport) int __stdcall ShowOriginsCureResult(
    int sick_cured,
    int healed_restored
) {
    char message[128];
    wsprintfA(
        message,
        "Cured sickness from %d villagers.\r\n\r\nRestored %d villagers to full health.",
        sick_cured,
        healed_restored
    );
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* Grant Running to All Villagers: reports each outcome on its own line, in
   the exact order and wording the OFFICIAL Origins Upgrade Prompts
   spreadsheet specifies -- granted, then dislikes removed, then each skip
   reason, with correct singular/plural throughout. granted comes from a
   fixed .shr scratch dword the native payload's running_va writes right
   before returning (see RUNNING_GRANTED_VA in
   scripts/build_vv1_origins_feature.py and report_running_granted in
   scripts/build_village_wide_origins_features.py) -- there was no register
   left to carry it back through directly. Called only for command 6
   (Running); command 8 (Set All Villagers to 18) now routes its own
   result through the generic ShowOriginsRowMessage below instead, since
   the spreadsheet gives it a plain "completed." line with no counts. */
__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(
    int command,
    int granted,
    int full_like_skipped,
    int already_running_skipped,
    int removed_running_dislike
) {
    char message[384];
    char line[128];
    if (command != 6) {
        return 0;
    }
    wsprintfA(
        message,
        "Granted Running to %d %s.",
        granted, vv1_vpl(granted)
    );
    wsprintfA(
        line,
        "\r\n\r\nRemoved a Running dislike from %d %s.",
        removed_running_dislike, vv1_vpl(removed_running_dislike)
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already like Running.",
        already_running_skipped, vv1_vpl(already_running_skipped)
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already have %d likes.",
        full_like_skipped, vv1_vpl(full_like_skipped), VV_LIKE_SLOT_COUNT
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* All Villagers are 18: granted/already/golden_child come from three fixed
   .shr scratch dwords age_va (in the shared village-wide script,
   report_age_granted opt-in) zeroes at its own start and increments as it
   goes (AGE_GRANTED_VA/AGE_ALREADY_VA/AGE_GOLDEN_CHILD_VA) -- same shape
   as ShowOriginsMasteryResult's own granted/already-satisfied pairing,
   extended with one more count. Restored per the OFFICIAL Origins Upgrade
   Prompts spreadsheet, which asks for a counted result here after all (an
   earlier pass had briefly simplified this row to a plain "completed."
   line to match what the spreadsheet said at the time).

   The Golden Child is always excluded (hardcoded to stay a child, per the
   user) regardless of how many the village happens to have -- age_va's
   own per-villager loop compares each candidate against the live
   dword ptr [0x48B614] singleton (the stock game's own lazily-created
   "current Golden Child" pointer, confirmed via disassembly of its
   matching getter/destructor pair) rather than assuming there is exactly
   one, so this reports however many were actually skipped for that
   reason, same as every other count here. */
__declspec(dllexport) int __stdcall ShowOriginsAgeResult(
    int granted,
    int already,
    int golden_child
) {
    char message[256];
    char line[128];
    wsprintfA(
        message,
        "Set %d %s to Age 18.",
        granted, vv1_vpl(granted)
    );
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already exactly 18.",
        already, vv1_vpl(already)
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: is Golden Child.",
        golden_child, vv1_vpl(golden_child)
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* Equal Division of Labor (both the Includes-Parenting and No-Parenting
   Tech screen rows share this one export): granted/golden_child_skipped
   come from two fixed .shr scratch dwords equal_division_core zeroes at
   its own start and increments as it goes (VV1-only, not part of the
   shared cross-game village-wide extension -- see equal_division_core's
   own comment in build_vv1_origins_feature.py). Unlike Grant Running/
   Mastery/Age, there is no "already correct" state to skip past: every
   eligible villager's job preference is reassigned unconditionally, so
   granted is simply how many villagers were actually eligible (active,
   alive, not the Golden Child).

   male_counts/female_counts each point at 5 more scratch dwords indexed
   by the same table position equal_division_core's own cyclic index
   (esi) uses -- 0=Farming, 1=Building, 2=Research, 3=Healing,
   4=Breeding, matching EQUAL_DIVISION_TABLE_BYTES's own on-screen Skills
   order, not the raw 1-5 job-preference codes written to the record.
   include_parenting selects how many of the 5 entries to report (4 for
   the No-Parenting row, which never reaches the trailing Breeding
   entry). */
__declspec(dllexport) int __stdcall ShowOriginsEqualDivisionResult(
    int granted,
    int golden_child_skipped,
    int include_parenting,
    const int *male_counts,
    const int *female_counts
) {
    static const char *job_names[5] = {
        "Farming", "Building", "Research", "Healing", "Breeding"
    };
    char message[768];
    char line[192];
    int job_count = include_parenting ? 5 : 4;
    int i;
    wsprintfA(
        message,
        "Set %d %s' Job Preferences.",
        granted, vv1_vpl(granted)
    );
    for (i = 0; i < job_count; ++i) {
        int total = male_counts[i] + female_counts[i];
        wsprintfA(
            line,
            "\r\n\r\n%s: %d %s (%d Male, %d Female).",
            job_names[i], total, vv1_vpl(total),
            male_counts[i], female_counts[i]
        );
        lstrcatA(message, line);
    }
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: is Golden Child.",
        golden_child_skipped, vv1_vpl(golden_child_skipped)
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* Grant Full Mastery to All Villagers: granted/already_mastered come from
   two fixed .shr scratch dwords mastery_va zeroes at its own start and
   increments as it goes (MASTERY_GRANTED_VA/MASTERY_ALREADY_VA) -- unlike
   Running's single count, mastery_va also has an early-exit failure path
   (mastery_failure) that a stack-based accumulator couldn't survive
   cleanly, so scratch memory was the only safe option for either count. */
__declspec(dllexport) int __stdcall ShowOriginsMasteryResult(
    int granted,
    int already_mastered
) {
    char message[192];
    char line[128];
    wsprintfA(
        message,
        "Granted Full Mastery to %d %s.",
        granted, vv1_vpl(granted)
    );
    wsprintfA(
        line,
        "\r\n\r\nSkipped %d %s: already fully mastered.",
        already_mastered, vv1_vpl(already_mastered)
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}

/* No-change wording for the Tech screen's three village-wide rows (Grant
   Running to All Villagers, Grant Full Mastery to All Villagers, Set All
   Villagers to 18) -- the only three Tech rows the OFFICIAL spreadsheet
   gives distinct no-change text to instead of the shared fallback. Rows 9
   and 10 (Equal Division of Labor) share one no-change case: unlike the
   three rows above, this row never checks a villager's existing state
   before reassigning, so "no change" only means no eligible villager was
   found at all (an empty or all-Golden-Child village), not "already
   correct". */
static const char *vv1_tech_no_change_text(int row) {
    switch (row) {
    case 6: return "Everyone already likes running, or has full Likes slots. No tech points have been deducted.";
    case 7: return "Everyone has already mastered their skills. No tech points have been deducted.";
    case 8: return "Everyone is already exactly 18. No tech points have been deducted.";
    case 9:
    case 10: return "No villagers were eligible. No tech points have been deducted.";
    default: return "No changes were needed. No tech points have been deducted.";
    }
}

/* No-change wording for the Villager Details screen's rows. Set Age to 18
   (row 3) happens to already use the shared fallback text verbatim per the
   spreadsheet, so only rows 0/1/2/4 need their own case. */
static const char *vv1_detail_no_change_text(int row) {
    switch (row) {
    case 0: return "This villager is already full of youth. No tech points have been deducted.";
    case 1: return "This villager is already fully mastered. No tech points have been deducted.";
    case 2: return "This villager already likes Running. No tech points have been deducted.";
    case 4: return "The appearance is unchanged. No tech points have been deducted.";
    default: return "No changes were needed. No tech points have been deducted.";
    }
}

enum {
    VV1_ROWMSG_SUCCESS = 0,
    VV1_ROWMSG_NO_CHANGE = 1,
    VV1_ROWMSG_NO_SLOT = 2,
    VV1_ROWMSG_REMOVED = 3,
    VV1_ROWMSG_POPULATION_FULL = 4,
    VV1_ROWMSG_NO_SLOT_DISLIKE_REMOVED = 5,
    VV1_ROWMSG_IS_GOLDEN_CHILD = 6
};

/* Generic result box for every Tech/Details row whose wording is either a
   plain "<Upgrade> completed." success line or one of a small set of
   fixed no-change/removed/blocked lines -- everything in the OFFICIAL
   Origins Upgrade Prompts spreadsheet that isn't a counted multi-line
   result (those keep their own dedicated export above: Cure, Grant
   Running to All, Grant Full Mastery to All). Replaces what used to be
   five separate ASM string-table entries (purchase_complete/removed/
   no_change/event_queued/running_unavailable) plus the now-removed
   ShowOriginsAgeResult export -- moving the text here costs the tight
   .shr string cave nothing and only a few bytes of code per call site. */
__declspec(dllexport) int __stdcall ShowOriginsRowMessage(
    int is_detail,
    int row,
    int status
) {
    char message[192];
    const char *name = is_detail ? vv1_detail_row_name(row) : vv1_tech_row_name(row);
    switch (status) {
    case VV1_ROWMSG_NO_CHANGE:
        lstrcpyA(
            message,
            is_detail ? vv1_detail_no_change_text(row) : vv1_tech_no_change_text(row)
        );
        break;
    case VV1_ROWMSG_NO_SLOT:
        lstrcpyA(message, "This villager already has full Likes slots. Running can not be added.");
        break;
    case VV1_ROWMSG_NO_SLOT_DISLIKE_REMOVED:
        lstrcpyA(
            message,
            "This villager's Likes are full, so Running could not be added, "
            "but its Running dislike was removed. No tech points have been deducted."
        );
        break;
    case VV1_ROWMSG_REMOVED:
        wsprintfA(message, "%s was removed. No refund was issued.", name);
        break;
    case VV1_ROWMSG_POPULATION_FULL:
        lstrcpyA(message, "Village population is close to its maximum. The Barrel of Babies needs room for 3 children. No tech points have been deducted.");
        break;
    case VV1_ROWMSG_IS_GOLDEN_CHILD:
        lstrcpyA(message, "This villager is the Golden Child. No tech points have been deducted.");
        break;
    default:
        wsprintfA(message, "%s completed.", name);
        break;
    }
    MessageBoxA(
        GetForegroundWindow(),
        message,
        is_detail ? "Villager Upgrades" : "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND
    );
    return 0;
}
