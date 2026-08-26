#define WIN32_LEAN_AND_MEAN
#include <windows.h>

/* Sidecar persistence lives next to the game's own saves. CSIDL_PERSONAL
   follows OneDrive redirection (Documents may be C:\Users\<u>\OneDrive\Documents),
   which is exactly where the live .ldw saves are, so declare just the one
   shell32 entry point we need instead of pulling in <shlobj.h>. */
#ifndef CSIDL_PERSONAL
#define CSIDL_PERSONAL 0x0005
#endif
__declspec(dllimport) BOOL __stdcall SHGetSpecialFolderPathA(HWND, LPSTR, int, BOOL);

/* Villager sex flag drives the male/female sprite atlas (render path
   0x45F5CF: cmp [record+0x1B90],0 / setne). Displayed age >= 1100 (55
   displayed years) uses the old-frame atlas page. */
#ifndef VV_SEX_OFFSET
#define VV_SEX_OFFSET 0x1B90
#endif
#ifndef VV_DISPLAY_AGE_OFFSET
#define VV_DISPLAY_AGE_OFFSET 0x1B8C
#endif
#ifndef VV_OLD_AGE_THRESHOLD
#define VV_OLD_AGE_THRESHOLD 1100
#endif
/* Atlas geometry: each sprite sheet is a grid of 40x65 cells. Heads have 8
   columns (directional frames); bodies have 16 columns and 10 outfits per
   page, split across pages 0..2 (male_bodies00/01/02 etc.). The picker shows
   one fixed viewing frame per field (playtest-chosen). */
#ifndef VV_CELL_W
#define VV_CELL_W 40
#endif
#ifndef VV_CELL_H
#define VV_CELL_H 65
#endif
#ifndef VV_HEAD_FRAME_COL
#define VV_HEAD_FRAME_COL 5
#endif
#ifndef VV_BODY_FRAME_COL
/* Bodies use a 16-column atlas (vs the head's 8), and its column order differs
   from the head's: col 5 faces the wrong way. The front-facing (camera-on)
   frame is the 9th column counting from 1 at the left = 0-based col 8
   (owner-selected; sits in the symmetric front hemisphere cols 8-14 per an
   L-R silhouette-symmetry scan of the atlas). */
#define VV_BODY_FRAME_COL 8
#endif
#ifndef VV_BODY_ROWS_PER_PAGE
#define VV_BODY_ROWS_PER_PAGE 10
#endif

/* Minimal GDI+ flat-API surface (declared here to stay in C). Linked against
   gdiplus.lib; used only to load the PNG atlases and blit one cell. */
typedef INT GpStatus;
typedef void GpImage;
typedef void GpBitmap;
typedef void GpGraphics;
struct GdiplusStartupInputC {
    UINT32 GdiplusVersion;
    void *DebugEventCallback;
    BOOL SuppressBackgroundThread;
    BOOL SuppressExternalCodecs;
};
__declspec(dllimport) GpStatus __stdcall GdiplusStartup(
    ULONG_PTR *token, const struct GdiplusStartupInputC *input, void *output);
__declspec(dllimport) void __stdcall GdiplusShutdown(ULONG_PTR token);
__declspec(dllimport) GpStatus __stdcall GdipCreateBitmapFromFile(
    const WCHAR *filename, GpBitmap **bitmap);
__declspec(dllimport) GpStatus __stdcall GdipCreateFromHDC(
    HDC hdc, GpGraphics **graphics);
__declspec(dllimport) GpStatus __stdcall GdipDrawImageRectRectI(
    GpGraphics *graphics, GpImage *image,
    INT dstx, INT dsty, INT dstw, INT dsth,
    INT srcx, INT srcy, INT srcw, INT srch,
    INT srcUnit, void *imageAttributes, void *callback, void *callbackData);
__declspec(dllimport) GpStatus __stdcall GdipDeleteGraphics(GpGraphics *graphics);
__declspec(dllimport) GpStatus __stdcall GdipDisposeImage(GpImage *image);

static ULONG_PTR gdiplus_token = 0;

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
#define VV_HEAD_OFFSET 0x1BB8
#endif
#ifndef VV_CLOTHING_OFFSET
#define VV_CLOTHING_OFFSET 0x1BBC
#endif
/* VV4 head/body catalogs are gender-independent, unlike VV1's RNG(19)/RNG(20):
   the native clothing chooser (sub_419590) cycles the body field 0..28 for
   every villager (29 values), and both the male_heads and female_heads atlases
   carry exactly 30 rows (head 0..29). So no gender read is needed. */
#ifndef VV_HEAD_COUNT
#define VV_HEAD_COUNT 30
#endif
#ifndef VV_BODY_COUNT
#define VV_BODY_COUNT 29
#endif
/* Cosmetic Heathen-mask overlay. Each villager's mask selection is held in the
   DLL-owned side-table below (never in a villager record); the render caves
   SDL_UpperBlit the chosen mask cell from Images/vvfp_mask_atlas.png on top of
   the drawn head when the selection is non-zero.
   0 = none, 1..5 = Blue/Orange/Red/Purple/Tribal Chief. */
#ifndef VV_MASK_COUNT
#define VV_MASK_COUNT 6   /* (None) + 5 masks */
#endif
static const char *const g_mask_names[VV_MASK_COUNT] = {
    "(None)", "Blue Mask", "Orange Mask", "Red Mask", "Purple Mask",
    "Tribal Chief Mask"
};

/* SAFE STORAGE (never touches the villager record or the game save): the mask
   selection lives in a DLL-owned side-table keyed by villager INDEX. The
   villager record array is fixed at 0x5101EC with stride 0x2E3C (RE'd:
   game-ctx global 0x50E568 + 0x1C84, iterator FUN_00467490), so
   index = (record - 0x5101EC) / 0x2E3C, valid 0..149. A non-record pointer
   yields a non-multiple offset -> index -1 -> treated as (None), never a write.
   The table lives in the DLL's writable data (never an executable section, so
   no W^X / self-modifying-code concern), and its address is published to the
   render cave via a fixed .shr slot at init (see vv4_publish_mask_table).
   Persistence rides a sidecar file next to the save (see the sidecar helpers). */
/* Villager record array base. The game's own accessors are authoritative:
   the Details menu gets a record via FUN_00466040(this=0x50E568, idx) which
   returns this + 0x44 + idx*0x2E3C = 0x50E5AC + idx*0x2E3C, and the Full
   Mastery walker passes 0x50E5AC as the array base. (An earlier derivation
   used 0x5101EC = ctx+0x1C84, which is wrong -- it left vv_villager_index
   returning -1 for every real record, so masks never stored or rendered.) */
#define VV_REC_ARRAY_BASE 0x50E5ACu
#define VV_REC_STRIDE     0x2E3Cu
#define VV_MAX_VILLAGERS  150
#define VV_NAME_OFFSET    0x1BC0        /* 24-byte villager name string (stable) */
/* Occupied/free flag (byte). The game's villager-creation routine
   (FUN_00466270) scans slots 0..149 for the FIRST record whose +0x1CC4 byte is
   0 and reuses it for a newborn, so a dead villager's index gets reallocated.
   0 = free/dead, nonzero = occupied. Read-only; the sweep below uses it. */
#define VV_OCCUPIED_OFFSET 0x1CC4
static unsigned char g_mask_by_index[VV_MAX_VILLAGERS];
/* Slot-reuse guard. PRIMARY defence is the per-frame clear-on-death sweep
   (vv_mask_sweep, run from Vv4MaskCacheSurface): the instant a masked slot goes
   free (+0x1CC4 == 0) its mask is cleared, so a reused slot starts mask-less and
   index-keying stays correct with no record writes. SECONDARY is a fingerprint
   of STABLE fields (gender + name — NOT likes/dislikes/head/body/age, which all
   mutate during play and would false-invalidate a living villager's mask) that
   backstops the ~1-frame death-then-reuse race the sweep could miss. */
static unsigned int g_mask_fp[VV_MAX_VILLAGERS];
/* Per-slot "has ever held a live villager this session" latch. It lets the
   sweep tell "slot freed by a death" (clear the mask) apart from "slot not
   populated yet" (a village hasn't loaded, e.g. at the main menu) -- so a mask
   restored from the sidecar before its villager exists is NOT wiped. */
static unsigned char g_slot_seen_alive[VV_MAX_VILLAGERS];

/* Clear masks whose slot has been freed/reused by the game. Read-only over the
   villager array; called once per frame from the present-path surface cache. */
static void vv_mask_sweep(void) {
    int idx;
    for (idx = 0; idx < VV_MAX_VILLAGERS; idx++) {
        const unsigned char *rec =
            (const unsigned char *)(VV_REC_ARRAY_BASE + (unsigned int)idx * VV_REC_STRIDE);
        if (rec[VV_OCCUPIED_OFFSET] != 0) {
            g_slot_seen_alive[idx] = 1;              /* slot currently holds a villager */
        } else if (g_slot_seen_alive[idx] && g_mask_by_index[idx] != 0) {
            g_mask_by_index[idx] = 0;                /* was alive, now freed -> drop mask */
            g_mask_fp[idx] = 0;
        }
    }
}

static unsigned int vv_fingerprint(const unsigned char *villager) {
    unsigned int h = 2166136261u;               /* FNV-1a */
    unsigned int sex = *(const unsigned int *)(villager + VV_SEX_OFFSET);
    const unsigned char *name = villager + VV_NAME_OFFSET;
    int i;
    for (i = 0; i < 4; i++) { h = (h ^ ((unsigned char *)&sex)[i]) * 16777619u; }
    for (i = 0; i < 24 && name[i]; i++) { h = (h ^ name[i]) * 16777619u; }
    return h ? h : 1u;                           /* reserve 0 = "no fp stored" */
}

static int vv_villager_index(const unsigned char *villager) {
    unsigned int off;
    unsigned int idx;
    if (villager == NULL) {
        return -1;
    }
    off = (unsigned int)villager - VV_REC_ARRAY_BASE;
    if (off % VV_REC_STRIDE != 0) {          /* not a real record slot */
        return -1;
    }
    idx = off / VV_REC_STRIDE;
    return idx < (unsigned int)VV_MAX_VILLAGERS ? (int)idx : -1;
}
static int vv_get_mask(const unsigned char *villager) {
    int idx = vv_villager_index(villager);
    unsigned char m;
    if (idx < 0) {
        return 0;
    }
    m = g_mask_by_index[idx];
    if (m == 0 || m >= VV_MASK_COUNT) {
        return 0;
    }
    /* Key PURELY by positional record index -- NO gender+name fingerprint. The
       fingerprint desynced the bulk "Change Appearance for All" path: the name/
       gender hashed at set-time didn't match render-time (name not finalized in
       the bulk write), so vv_get_mask wrongly rejected every for-All mask while
       an individually-set mask (set+render adjacent) worked. Position is stable
       across the bulk set AND across save/reload (VV5's proven approach). Slot
       reuse (a newborn taking a dead villager's index) is handled by the
       clear-on-death sweep vv_mask_sweep, which zeroes the mask the moment the
       slot goes free -- so a reused slot starts mask-less. */
    return (int)m;
}
static void vv_set_mask(unsigned char *villager, int mask) {
    int idx = vv_villager_index(villager);
    if (idx < 0) {
        return;
    }
    if (mask > 0 && mask < VV_MASK_COUNT) {
        g_mask_by_index[idx] = (unsigned char)mask;
        g_mask_fp[idx] = vv_fingerprint(villager);
    } else {
        g_mask_by_index[idx] = 0;
        g_mask_fp[idx] = 0;
    }
}

/* --- Mask atlas as a game sprite (for the thunk-reuse render) ---------------
   Instead of a raw SDL blit (which ignored the game's per-draw scroll/scale
   transform -> masks absent in-world / too tiny on the scaled portrait), the
   head-draw caves draw the mask THROUGH the game's own head-draw thunk
   (0x409A70) with the head's x/y/facing/transform. That needs the mask atlas as
   a drawable game sprite object.

   Build it via the game's MULTI-FILE ldwImageGrid ctor FUN_0040ABA0 -- the SAME
   ctor the head atlases use -- so the object layout is byte-identical to what the
   draw path (FUN_00408c40 -> FUN_0040a990) reads. Critically, that draw resolves
   the SURFACE from the surface-ARRAY at this[0xc]; the single-file loader leaves
   this[0xc]=0 so the draw finds no surface and blits nothing. The multi-file ctor
   populates this[0xc]. (Confirmed by the VV2 + VV5 chats; VV5 renders masks the
   same way on this engine.)

     void __thiscall FUN_0040ABA0(this, name, ext, cols, rows, subcols, subrows):
         this[0xc] = surface array (cols*rows entries), loads "<name><c><r><ext>"
         this[8]=cols this[9]=rows this[2]=subcols this[3]=subrows
         this[4]=totalW/subcols (=cellW) this[5]=totalH/subrows (=cellH)
         this[0xa]=fileW/cellW this[0xb]=fileH/cellH

   With cols=1, rows=1, subcols=8, subrows=5 on one 320x325 file it yields
   cellW=40, cellH=65, one surface at this[0xc][0], and FUN_0040a990 selects the
   cell as (facing-col x mask-row). The ctor sprintf's "%s%d%d%s" -> "<name>00.png"
   so we ship Images\vvfp_mask_atlas00.png; the name is passed BARE (no "Images\\"
   -- the loader resolves relative to a working dir that already contains Images).

   Over-allocated to 0x70 and zeroed so the scaled-view clip path (FUN_00407f80
   reads this+0x60..0x6c when transform!=100) sees sane zero bounds instead of
   reading past a 0x34 object (the two hooked twins pass transform==100, which
   skips that path, but the over-alloc is cheap insurance). The object ptr is
   published to a fixed .shr slot the head cave reads; a failed load leaves
   cellW 0 and the cave draws no mask (no crash). */
#define VV_ALLOC_FN      0x470C5Cu     /* game allocator: void*(unsigned size) */
#define VV_LDWGRID_CTOR  0x40ABA0u     /* ldwImageGrid multi-file __thiscall ctor */
#define VV_MASK_ATLAS_SLOT_VA 0x728D70u /* .shr slot: published atlas obj ptr */
static void *g_mask_atlas_obj = NULL;
static int g_mask_atlas_tried = 0;
static void *g_dest_surface;    /* fwd tentative def (real one below); diag use */

static void vv_ensure_mask_atlas(void) {
    void *obj;
    /* BARE name -- the game names its own atlases bare ("male_heads"), and the
       ctor sprintf's "%s%d%d%s" -> "vvfp_mask_atlas00.png", fopen'd relative to a
       working dir that resolves into Images\. A leading "Images\\" would double
       to Images\Images\... and fail to load. */
    static const char atlas_name[] = "vvfp_mask_atlas";
    static const char atlas_ext[] = ".png";
    const char *namep = atlas_name;
    const char *extp = atlas_ext;
    if (g_mask_atlas_tried) {
        return;                        /* one-shot: never retry (no crash loop) */
    }
    g_mask_atlas_tried = 1;
    obj = ((void *(__cdecl *)(unsigned int))(UINT_PTR)VV_ALLOC_FN)(0x70u);
    if (obj == NULL) {
        return;
    }
    {   /* zero the over-alloc so the clip path reads sane bounds */
        unsigned int *z = (unsigned int *)obj;
        int i;
        for (i = 0; i < 0x70 / 4; i++) z[i] = 0;
    }
    /* FUN_0040ABA0(this=obj, name, ext, cols=1, rows=1, subcols=8, subrows=5),
       __thiscall, callee-cleans the 6 stack args (ret 0x18). */
    __asm {
        push 5
        push 8
        push 1
        push 1
        mov  eax, extp
        push eax
        mov  eax, namep
        push eax
        mov  ecx, obj
        mov  eax, VV_LDWGRID_CTOR
        call eax
    }
    /* CLIP BOUNDS (this+0x60..0x6c = left/top/right/bottom). The draw's clip
       stage FUN_00407f80 reads these whenever the transform != 100 (walking
       villagers pass ~93, NOT 100), and rejects the sprite when they're 0 --
       which is why masks never drew in the scrolled village while the details
       path (which happened to pass) did. Set a viewport wider than any on-screen
       coord so masks always pass the clip and draw at the head's own scale. */
    {
        int *o = (int *)obj;
        o[0x18] = -30000;      /* byte 0x60: left   */
        o[0x19] = -30000;      /* byte 0x64: top    */
        o[0x1a] =  30000;      /* byte 0x68: right  */
        o[0x1b] =  30000;      /* byte 0x6c: bottom */
    }
    /* Reject a failed/empty load (cellW at obj[4] == 0) so the cave never draws
       a garbage cell. */
    if (((unsigned int *)obj)[4] == 0) {
        return;
    }
    g_mask_atlas_obj = obj;
    *(void **)(UINT_PTR)VV_MASK_ATLAS_SLOT_VA = obj;   /* publish to the head cave */
}

/* Head-draw caves call this: ensure the atlas is built + published, and return
   the fingerprint-checked mask (0 = none) for the villager record. */
__declspec(dllexport) int __stdcall Vv4MaskGetForRecord(unsigned char *villager) {
    int mask;
    vv_ensure_mask_atlas();
    mask = vv_get_mask(villager);
    /* Skip the mask on non-living villagers: the mausoleum-collection bonus
       spawns GHOSTS from dead villager records that still carry a mask in the
       index-keyed side-table and render through the same world compositor. Gate
       on the game's own liveness fields (matching vv_eligible): dead flag +0x1CC7
       set, or health +0x1C40 <= 0. Render-only -- the stored mask is untouched,
       so a revived villager gets it back. */
    if (mask > 0 && (villager[0x1CC7] != 0 ||
                     *(const int *)(villager + 0x1C40) <= 0)) {
        mask = 0;
    }
    return mask;
}

/* --- Sidecar persistence ---------------------------------------------------
   The mask side-table is snapshotted to a small file that lives NEXT TO the
   game's own saves (never inside the .ldw, so a save can never be corrupted):
   <Documents>\LDW\<exe-basename>\vvfp_masks.dat, where <Documents> comes from
   SHGetSpecialFolderPathA(CSIDL_PERSONAL) so it follows OneDrive redirection to
   wherever the live .ldw saves actually are. Written on chooser OK; read once,
   lazily, on the first present frame. The stored fingerprints guard identity on
   reload, and the sweep's seen-alive latch keeps a restored mask until its
   villager appears. Format: "VVMK" + u32 version + u32 count(150) + 150 mask
   bytes + 150 u32 fingerprints (magic/version added per VV3/VV5 advice so the
   entry shape can evolve without silently misreading an old file). */
#define VV_SIDECAR_VERSION 1u

static int vv_build_sidecar_path(char *out) {
    char exe[MAX_PATH];
    char base[MAX_PATH];
    DWORD n;
    int i, start, end, j;
    if (!SHGetSpecialFolderPathA(NULL, out, CSIDL_PERSONAL, TRUE)) {
        return 0;
    }
    lstrcatA(out, "\\LDW");
    CreateDirectoryA(out, NULL);                 /* harmless if it already exists */
    n = GetModuleFileNameA(NULL, exe, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return 0;
    }
    start = 0;
    for (i = (int)n - 1; i >= 0; i--) {
        if (exe[i] == '\\' || exe[i] == '/') { start = i + 1; break; }
    }
    end = (int)n;
    for (i = (int)n - 1; i > start; i--) {
        if (exe[i] == '.') { end = i; break; }    /* strip the extension */
    }
    j = 0;
    for (i = start; i < end && j < MAX_PATH - 1; i++) {
        base[j++] = exe[i];
    }
    base[j] = '\0';
    lstrcatA(out, "\\");
    lstrcatA(out, base);
    CreateDirectoryA(out, NULL);
    lstrcatA(out, "\\vvfp_masks.dat");
    return 1;
}

static void vv_write_mask_sidecar(void) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD wr;
    unsigned int header[2];
    if (!vv_build_sidecar_path(path)) {
        return;
    }
    h = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return;
    }
    header[0] = VV_SIDECAR_VERSION;
    header[1] = VV_MAX_VILLAGERS;
    WriteFile(h, "VVMK", 4, &wr, NULL);
    WriteFile(h, header, sizeof(header), &wr, NULL);
    WriteFile(h, g_mask_by_index, VV_MAX_VILLAGERS, &wr, NULL);
    WriteFile(h, g_mask_fp, VV_MAX_VILLAGERS * (DWORD)sizeof(unsigned int), &wr, NULL);
    CloseHandle(h);
}

static void vv_read_mask_sidecar(void) {
    char path[MAX_PATH];
    HANDLE h;
    DWORD rd;
    char magic[4];
    unsigned int header[2];
    unsigned char masks[VV_MAX_VILLAGERS];
    unsigned int fps[VV_MAX_VILLAGERS];
    int i;
    if (!vv_build_sidecar_path(path)) {
        return;
    }
    h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        return;                                  /* no file yet -> stay all-unmasked */
    }
    if (ReadFile(h, magic, 4, &rd, NULL) && rd == 4 &&
        magic[0] == 'V' && magic[1] == 'V' && magic[2] == 'M' && magic[3] == 'K' &&
        ReadFile(h, header, sizeof(header), &rd, NULL) && rd == sizeof(header) &&
        header[0] == VV_SIDECAR_VERSION && header[1] == VV_MAX_VILLAGERS &&
        ReadFile(h, masks, VV_MAX_VILLAGERS, &rd, NULL) && rd == VV_MAX_VILLAGERS &&
        ReadFile(h, fps, sizeof(fps), &rd, NULL) && rd == sizeof(fps)) {
        for (i = 0; i < VV_MAX_VILLAGERS; i++) {
            g_mask_by_index[i] = (masks[i] < VV_MASK_COUNT) ? masks[i] : 0;
            g_mask_fp[i] = fps[i];
        }
    }
    CloseHandle(h);
}

/* --- In-world / details mask render via SDL surface blit -------------------
   VV4 is surface-based: the game blits every sprite with SDL_UpperBlit onto the
   render-target surface at [screen_obj+0x30]. We blit the chosen mask on top
   the same way. The mask atlas is the head-aligned Images/vvfp_mask_atlas.png
   (8 frames x 5 masks of 40x65). All SDL entry points are resolved via
   GetProcAddress (SDL_BlitScaled / SDL_SetSurfaceBlendMode are not in the exe's
   imports), and EVERY pointer is null-guarded so a missing DLL/PNG degrades to
   no-mask instead of crashing (renamed/moved exe safe). All state lives here in
   the DLL's writable data -- never an executable section (W^X clean). */
#define VV_R_CELL_W 40
#define VV_R_CELL_H 65
/* Screen anchor of the mask relative to the head-draw x/y (tuned in playtest). */
#ifndef VV_R_DX
#define VV_R_DX 0
#endif
#ifndef VV_R_DY
#define VV_R_DY 0
#endif
#define VV_SDL_BLENDMODE_BLEND 1

typedef struct { int x, y, w, h; } VvSdlRect;
typedef void *(__cdecl *vv_IMG_Load_t)(const char *);
typedef int (__cdecl *vv_SDL_UpperBlit_t)(void *, const VvSdlRect *, void *, VvSdlRect *);
typedef int (__cdecl *vv_SDL_BlitScaled_t)(void *, const VvSdlRect *, void *, VvSdlRect *);
typedef int (__cdecl *vv_SDL_SetSurfaceBlendMode_t)(void *, int);

static void *g_mask_surface;   /* the 40x65-cell mask atlas (SDL_Surface*) */
static void *g_dest_surface;   /* cached render target [screen_obj+0x30]    */
static vv_IMG_Load_t p_IMG_Load;
static vv_SDL_UpperBlit_t p_SDL_UpperBlit;
static vv_SDL_BlitScaled_t p_SDL_BlitScaled;
static vv_SDL_SetSurfaceBlendMode_t p_SDL_SetSurfaceBlendMode;
static int g_mask_render_init;

/* SDL_Surface field offsets (SDL2): w=+0x08, h=+0x0C, pitch=+0x10. */
#define VV_SURF_W(s)     (*(int *)((char *)(s) + 0x08))
#define VV_SURF_PITCH(s) (*(int *)((char *)(s) + 0x10))

static void vv4_mask_render_init(void) {
    HMODULE sdl, img;
    char path[MAX_PATH];
    DWORD n;
    int i;
    if (g_mask_render_init) {
        return;
    }
    g_mask_render_init = 1;                 /* attempt once, even on failure */
    sdl = GetModuleHandleA("SDL2.dll");
    img = GetModuleHandleA("SDL2_image.dll");
    if (sdl == NULL || img == NULL) {
        return;
    }
    p_IMG_Load = (vv_IMG_Load_t)GetProcAddress(img, "IMG_Load");
    p_SDL_UpperBlit = (vv_SDL_UpperBlit_t)GetProcAddress(sdl, "SDL_UpperBlit");
    p_SDL_BlitScaled = (vv_SDL_BlitScaled_t)GetProcAddress(sdl, "SDL_BlitScaled");
    p_SDL_SetSurfaceBlendMode =
        (vv_SDL_SetSurfaceBlendMode_t)GetProcAddress(sdl, "SDL_SetSurfaceBlendMode");
    if (p_IMG_Load == NULL) {
        return;
    }
    /* exe-dir absolute path: <exe folder>\Images\vvfp_mask_atlas.png */
    n = GetModuleFileNameA(NULL, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) {
        return;
    }
    for (i = (int)n - 1; i >= 0; i--) {
        if (path[i] == '\\' || path[i] == '/') {
            path[i + 1] = '\0';
            break;
        }
    }
    lstrcatA(path, "Images\\vvfp_mask_atlas.png");
    g_mask_surface = p_IMG_Load(path);      /* NULL on failure -> no mask, no crash */
    if (g_mask_surface != NULL && p_SDL_SetSurfaceBlendMode != NULL) {
        p_SDL_SetSurfaceBlendMode(g_mask_surface, VV_SDL_BLENDMODE_BLEND);
    }
}

/* Called from the present-path hook every frame with the live render-target
   surface ([screen_obj+0x30]); read at the real site, never a guessed global. */
__declspec(dllexport) void __stdcall Vv4MaskCacheSurface(void *surface) {
    static int g_sidecar_loaded = 0;
    g_dest_surface = surface;
    if (!g_sidecar_loaded) {
        g_sidecar_loaded = 1;   /* one-shot: restore persisted masks on first frame */
        vv_read_mask_sidecar();
    }
    vv_mask_sweep();            /* clear masks on slots the game freed/reused */
}

/* Blit one resolved mask (1..5) at the head's screen x/y. scale_pct: 100 =
   in-world, ~150/200 = Details (scales the cell AND the anchor offset). */
static void vv4_blit_mask(int mask, int x, int y, int frame, int scale_pct) {
    VvSdlRect src, dst;
    vv4_mask_render_init();
    if (g_dest_surface == NULL || g_mask_surface == NULL || p_SDL_UpperBlit == NULL) {
        return;                              /* not ready -> no mask, no crash */
    }
    if (mask <= 0 || mask >= VV_MASK_COUNT) {
        return;
    }
    /* SDL_UpperBlit format-converts as needed, so no dest-format guard here
       (an earlier 32bpp pitch check silently skipped every in-world blit). */
    if (frame < 0 || frame > 7) {
        frame = 5;                           /* front-facing default */
    }
    src.x = frame * VV_R_CELL_W;
    src.y = (mask - 1) * VV_R_CELL_H;
    src.w = VV_R_CELL_W;
    src.h = VV_R_CELL_H;
    if (scale_pct > 0 && scale_pct != 100 && p_SDL_BlitScaled != NULL) {
        dst.x = x + VV_R_DX * scale_pct / 100;
        dst.y = y + VV_R_DY * scale_pct / 100;
        dst.w = VV_R_CELL_W * scale_pct / 100;
        dst.h = VV_R_CELL_H * scale_pct / 100;
        p_SDL_BlitScaled(g_mask_surface, &src, g_dest_surface, &dst);
    } else {
        dst.x = x + VV_R_DX;
        dst.y = y + VV_R_DY;
        dst.w = VV_R_CELL_W;
        dst.h = VV_R_CELL_H;
        p_SDL_UpperBlit(g_mask_surface, &src, g_dest_surface, &dst);
    }
}

/* By raw index (no fingerprint check) -- for callers that only have the index
   (e.g. the Details screen's selected villager). */
__declspec(dllexport) void __stdcall Vv4MaskDraw(int index, int x, int y,
                                                 int frame, int scale_pct) {
    if (index < 0 || index >= VV_MAX_VILLAGERS) {
        return;
    }
    vv4_blit_mask((int)g_mask_by_index[index], x, y, frame, scale_pct);
}

/* Primary render entry: the head-draw hooks hold the villager RECORD (esi), so
   this derives the index AND fingerprint-checks (slot-reuse safe). */
__declspec(dllexport) void __stdcall Vv4MaskDrawRecord(unsigned char *villager,
                                                       int x, int y, int frame,
                                                       int scale_pct) {
    vv4_blit_mask(vv_get_mask(villager), x, y, frame, scale_pct);
}

static HINSTANCE module_instance;

enum {
    IDD_ORIGINS_TECH = 201,
    IDD_ORIGINS_VILLAGER = 202,
    IDD_ORIGINS_APPEARANCE = 203,
    IDD_ORIGINS_FORALL = 214,
    ID_BUY_FIRST = 1000,
    ID_BUY_LAST = 1013,          /* 14 tech rows (row 13 = Change Appearance for All) */
    ID_CHECK_FIRST = 1100,
    ID_HEAD_LABEL = 2000,
    ID_HEAD_PREV = 2001,
    ID_HEAD_NEXT = 2002,
    ID_HEAD_PIC = 2003,
    ID_BODY_LABEL = 2010,
    ID_BODY_PREV = 2011,
    ID_BODY_NEXT = 2012,
    ID_BODY_PIC = 2013,
    ID_MASK_LABEL = 2020,
    ID_MASK_PREV = 2021,
    ID_MASK_NEXT = 2022,
    ID_MASK_PIC = 2023,
    STATE_VILLAGER = 0x10000,
    STATE_VILLAGE_WIDE = 0x20000,
    STATE_RUNNING_ONLY = 0x40000,
    STATE_VILLAGE_WIDE_BUY = 0x80000
};

/* Only one appearance picker can be open at a time (it is a modal dialog),
   so a single file-scope slot for its working state is sufficient -- this
   mirrors module_instance above, which is the same kind of single-instance
   global already used in this file. The tech-point balance check and
   charge live in the caller (the same reused code path every other
   Villager Upgrades row already charges through), not here: this dialog
   only ever previews and either keeps or reverts the head/body fields.

   VV4's head and body catalogs differ from each other and, unlike VV1, do
   NOT depend on gender: the native clothing chooser (sub_419590) cycles the
   body field over 0..28 for every villager (29 values; special value 29 is
   the chief outfit, outside the cycle), and both the male_heads and
   female_heads atlases carry exactly 30 rows (head 0..29). So head_count is
   30 and body_count is 29 for all villagers -- see VV_HEAD_COUNT/VV_BODY_COUNT
   above. Each field is stored as the 0-based atlas row index directly. */
static struct {
    unsigned char *villager;
    int original_head;
    int original_body;
    int original_mask;
    int head_count;
    int body_count;
    int sex;      /* 0 / non-zero -> female / male sprite atlas */
    int is_old;   /* displayed age >= VV_OLD_AGE_THRESHOLD */
} appearance_state;

/* GDI+ must NOT be started from DllMain: GdiplusStartup is unsupported under the
   loader lock and can deadlock while loading its dependencies. Initialize it
   lazily the first time the appearance picker (the only GDI+ user) runs. The
   process-exit teardown is likewise left to the OS rather than GdiplusShutdown
   from DllMain. */
static void vv4_ensure_gdiplus(void) {
    if (gdiplus_token == 0) {
        struct GdiplusStartupInputC input;
        input.GdiplusVersion = 1;
        input.DebugEventCallback = NULL;
        input.SuppressBackgroundThread = FALSE;
        input.SuppressExternalCodecs = FALSE;
        GdiplusStartup(&gdiplus_token, &input, NULL);
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        module_instance = instance;
    }
    return TRUE;
}

/* Blit one 40x65 atlas cell for the given head/body value into an
   owner-drawn control. head==1 selects the head sheet + column, otherwise
   the body sheet + column (and its per-page split). The atlas PNGs live in
   the game's Images folder; the villager re-renders live behind this dialog
   regardless, so a failed load simply shows nothing here. */
static void appearance_draw_cell(HDC hdc, RECT rc, int is_head, int value, int clear) {
    WCHAR path[MAX_PATH];
    /* LDW engine convention (matches the VV2 companion): a non-zero sex field
       is female, zero is male. */
    const WCHAR *sex = appearance_state.sex ? L"female" : L"male";
    int age = appearance_state.is_old ? 1 : 0;
    int col, row, page;
    GpBitmap *bitmap = NULL;
    int dstw = rc.right - rc.left;
    int dsth = rc.bottom - rc.top;

    if (clear) {
        FillRect(hdc, &rc, (HBRUSH)(COLOR_BTNFACE + 1));
    }
    if (is_head) {
        col = VV_HEAD_FRAME_COL;
        row = value;
        wsprintfW(path, L"Images\\%ls_heads%d0.png", sex, age);
    } else {
        col = VV_BODY_FRAME_COL;
        page = value / VV_BODY_ROWS_PER_PAGE;
        row = value % VV_BODY_ROWS_PER_PAGE;
        wsprintfW(path, L"Images\\%ls_bodies%d%d.png", sex, age, page);
    }
    if (GdipCreateBitmapFromFile(path, &bitmap) == 0 && bitmap != NULL) {
        GpGraphics *graphics = NULL;
        if (GdipCreateFromHDC(hdc, &graphics) == 0 && graphics != NULL) {
            /* Preserve the 40x65 cell aspect ratio: scale by the smaller of the
               two axis ratios and centre the result, so the sprite is never
               squashed to fill a differently-proportioned control. */
            double scale_x = (double)dstw / VV_CELL_W;
            double scale_y = (double)dsth / VV_CELL_H;
            double scale = scale_x < scale_y ? scale_x : scale_y;
            int draw_w = (int)(VV_CELL_W * scale);
            int draw_h = (int)(VV_CELL_H * scale);
            int draw_x = rc.left + (dstw - draw_w) / 2;
            int draw_y = rc.top + (dsth - draw_h) / 2;
            /* UnitPixel == 2 */
            GdipDrawImageRectRectI(
                graphics, bitmap,
                draw_x, draw_y, draw_w, draw_h,
                col * VV_CELL_W, row * VV_CELL_H, VV_CELL_W, VV_CELL_H,
                2, NULL, NULL, NULL);
            GdipDeleteGraphics(graphics);
        }
        GdipDisposeImage(bitmap);
    }
}

/* Isolated Heathen-mask preview, matching VV5's Change Appearance: show the
   selected mask on its own (not overlaid on the head), front-facing. The mask
   sheet ships beside the head atlases as Images/vvfp_masks.png -- an 8x5 grid
   of 65x145 cells; the front-facing view is column 5, and mask value 1..5 maps
   to rows 0..4. (None) leaves the cell blank. */
/* Preview strip = VV2's shared mask_preview sprites (pixel-identical pickers
   across all 5 games): 240x65 = SIX 40x65 cells, cell index == mask value
   (0 = none/blank, 1..5 = Blue/Orange/Red/Purple/Chief), front frame, ~90% fill.
   scale-to-fit the control preserving aspect, centred; cell 0 draws "(none)". */
#define VV_MASK_SHEET L"Images\\vvfp_mask_preview.png"
#define VV_MASK_CELL_W 40
#define VV_MASK_CELL_H 65
static void appearance_draw_mask_cell(HDC hdc, RECT rc, int mask) {
    GpBitmap *bitmap = NULL;
    int dstw = rc.right - rc.left;
    int dsth = rc.bottom - rc.top;
    FillRect(hdc, &rc, (HBRUSH)(COLOR_BTNFACE + 1));
    if (mask <= 0 || mask >= VV_MASK_COUNT) {
        /* (None): leave the preview box blank -- the ID_MASK_LABEL (2020) below
           already reads "(None)", so drawing "(none)" here too is a duplicate. */
        return;
    }
    vv4_ensure_gdiplus();
    if (GdipCreateBitmapFromFile(VV_MASK_SHEET, &bitmap) == 0 && bitmap != NULL) {
        GpGraphics *graphics = NULL;
        if (GdipCreateFromHDC(hdc, &graphics) == 0 && graphics != NULL) {
            double scale_x = (double)dstw / VV_MASK_CELL_W;
            double scale_y = (double)dsth / VV_MASK_CELL_H;
            double scale = scale_x < scale_y ? scale_x : scale_y;
            int draw_w = (int)(VV_MASK_CELL_W * scale);
            int draw_h = (int)(VV_MASK_CELL_H * scale);
            int draw_x = rc.left + (dstw - draw_w) / 2;
            int draw_y = rc.top + (dsth - draw_h) / 2;
            GdipDrawImageRectRectI(
                graphics, bitmap,
                draw_x, draw_y, draw_w, draw_h,
                mask * VV_MASK_CELL_W, 0, VV_MASK_CELL_W, VV_MASK_CELL_H,
                2, NULL, NULL, NULL);
            GdipDeleteGraphics(graphics);
        }
        GdipDisposeImage(bitmap);
    }
}

/* Full-screen support ports VV2's player-confirmed approach (its PR #13). Three
   pieces work together; the plain-dialog attempt without them left the menus
   hidden in full-screen. */

/* 1) The game is SDL2-based; in full-screen SDL minimizes its window the instant
      it loses focus to our modal dialog, dropping the player to the desktop and
      hiding the menu. Turn off SDL's minimize-on-focus-loss so the game stays
      full-screen behind the dialog. SDL2.dll is already loaded by the game and
      re-reads the hint on focus loss, so setting it before we create any dialog
      or message box is enough. (Left set for the session, as VV2 does, so it
      also covers the result pop-ups shown after the menu closes.) */
static void vv4_prep_fullscreen(void) {
    HMODULE sdl = GetModuleHandleA("SDL2.dll");
    if (sdl != NULL) {
        typedef int(__cdecl * set_hint_t)(const char *, const char *);
        set_hint_t set_hint = (set_hint_t)GetProcAddress(sdl, "SDL_SetHint");
        if (set_hint != NULL) {
            set_hint("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0");
        }
    }
}

/* 2) The dialogs use DS_CENTER so Windows centers them on the display; this also
      lifts them above the full-screen surface and to the foreground so they are
      visible and clickable. Called from each dialog's WM_INITDIALOG. */
static void vv4_surface_dialog(HWND window) {
    SetWindowPos(window, HWND_TOPMOST, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
    SetForegroundWindow(window);
}

/* 3) Message boxes must also come topmost/foreground over the full-screen game. */
#define VV_MB_FRONT (MB_SETFOREGROUND | MB_TOPMOST)

/* OFFICIAL per-row purchase-confirm names + costs. Tech rows 6-8 (village-wide)
   use the payload's own OFFICIAL confirm and are skipped here. */
static const char *const g_tech_names[14] = {
    "Time Warp", "Island Event", "Barrel of Babies",
    "Tech Point Doubler", "Food Point Doubler", "Full Heal / Cure All",
    "", "", "", "Complete All Collections", "Reset All Collections",
    "Equal Division of Labor (Includes Parenting)",
    "Equal Division of Labor (No Parenting)",
    "Change Appearance for All"
};
static const char *const g_tech_costs[14] = {
    "50,000", "30,000", "75,000", "500,000", "500,000", "30,000", "", "", "",
    "1,000,000", "1,000,000", "1,000,000", "1,000,000", "450,000"
};
static const char *const g_villager_names[5] = {
    "Grant Youth", "Grant Full Mastery", "Grant Running",
    "Set Age to 18", "Change Appearance"
};
static const char *const g_villager_costs[5] = {
    "50,000", "100,000", "40,000", "50,000", "5,000"
};
static int g_villager_menu;  /* set at WM_INITDIALOG; menus are modal/one-at-a-time */
/* The full state bitmask handed to the villager menu at open time (low bits:
   0=youth already youngest, 1=already fully mastered, 2=already likes Running,
   3=already 18, 10=no free Like slot). Used by WM_COMMAND to report the
   OFFICIAL no-change line when a would-do-nothing row is clicked. */
static int g_villager_mask;
/* The row/menu the player last acted on, captured at click time so the result
   popup (shown after the menu closes) can name the upgrade. */
static int g_last_row = -1;
static int g_last_villager;

/* Remove a Running dislike from the villager whose record the payload stored in
   the detail-menu scratch slot (.shr 0x728D40), via the game's managed
   remove-from-array helper 0x45D1C0 (thiscall: ECX = the dislikes array, one
   stack arg = the preference id, callee-cleaned ret 4). Used by the "Likes are
   full but a Running dislike was cleared" no-change case. */
static void vv4_remove_detail_running_dislike(void) {
    unsigned char *rec = *(unsigned char **)(UINT_PTR)0x728D40u;
    void *dislikes;
    if (rec == NULL) { return; }
    dislikes = rec + 0x1E6C;   /* dislikes array */
    __asm {
        push 38                /* RUNNING preference id */
        mov  ecx, dislikes
        mov  eax, 0x45D1C0
        call eax
    }
}

/* Change Appearance for All (row 13 of the village-wide tech menu) is fully
   self-contained -- it runs its own dialog, charge and apply -- so the menu
   invokes it directly rather than returning a row for the payload to dispatch.
   Defined further down; forward-declared here. */
__declspec(dllexport) int __stdcall ShowVv4AppearanceForAll(void);
#define ID_FORALL_ROW 13

static INT_PTR CALLBACK upgrade_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        int villager_menu = (lparam & STATE_VILLAGER) != 0;
        g_villager_menu = villager_menu;
        g_villager_mask = (int)lparam;
        int village_wide_buy = (lparam & STATE_VILLAGE_WIDE_BUY) != 0;
        /* Village-wide tech menu carries 14 rows: the 6 base upgrades, the 3
           village-wide grants (rows 6-8), Complete/Reset All Collections
           (rows 9-10), the two Equal Division of Labor rows (11-12), and
           Change Appearance for All (row 13). */
        int row_count = villager_menu
            ? 5
            : ((lparam & STATE_RUNNING_ONLY) != 0
                ? 7
                : ((lparam & STATE_VILLAGE_WIDE) != 0 ? 14 : 6));
        int row;
        for (row = 0; row < 14; ++row) {
            ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_HIDE);
        }
        for (row = 0; row < row_count; ++row) {
            if (!villager_menu && row == ID_FORALL_ROW) {
                /* Change Appearance for All: always purchasable in the tech
                   menu; no availability bit and no checkmark. Its own dialog
                   confirms and charges, so it never shows Remove/Unavailable. */
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                continue;
            }
            if (villager_menu) {
                /* Every villager row stays a clickable "Buy". A row that would
                   change nothing is not greyed out; it opens and reports the
                   OFFICIAL no-change line (see WM_COMMAND) so the specified
                   wording actually reaches the player, and nothing is charged.
                   The check-mark still flags an already-satisfied row. */
                if ((lparam & (1 << row)) != 0
                    || (lparam & (1 << (8 + row))) != 0) {
                    ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                }
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                continue;
            }
            if ((lparam & (1 << row)) != 0) {
                ShowWindow(GetDlgItem(window, ID_CHECK_FIRST + row), SW_SHOW);
                if (village_wide_buy && row >= 6) {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Buy");
                    EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), TRUE);
                } else {
                    SetDlgItemTextA(window, ID_BUY_FIRST + row, "Remove");
                }
            } else if ((8 + row) >= row_count && (8 + row) < 16
                       && (lparam & (1 << (8 + row))) != 0) {
                /* The (8+row) unavailable bit must stay below the STATE_* flags
                   at bits 16-19, or rows 8-10 would read a state flag (e.g.
                   STATE_VILLAGE_WIDE at bit 17) as an "Unavailable" marker. */
                SetDlgItemTextA(window, ID_BUY_FIRST + row, "Unavailable");
                EnableWindow(GetDlgItem(window, ID_BUY_FIRST + row), FALSE);
            }
        }
        vv4_surface_dialog(window);
        return TRUE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        if (command >= ID_BUY_FIRST && command <= ID_BUY_LAST) {
            int row = (int)(command - ID_BUY_FIRST);
            char label[16];
            if (!g_villager_menu && row == ID_FORALL_ROW) {
                /* Change Appearance for All owns its own confirm/charge/apply
                   dialog, so run it directly and close the menu -- the payload
                   dispatch is bypassed (return -1 = no row bought here). */
                ShowVv4AppearanceForAll();
                EndDialog(window, -1);
                return TRUE;
            }
            label[0] = '\0';
            GetDlgItemTextA(window, command, label, (int)sizeof(label));
            /* A villager row that would change nothing reports the OFFICIAL
               no-change line and charges nothing, using the state bits the
               payload computed for this villager at open time. Running has two
               distinct cases: already-likes (checked first) vs. no free slot. */
            if (g_villager_menu) {
                const char *nochange = NULL;
                if (row == 0 && (g_villager_mask & (1 << 0)) != 0) {
                    nochange = "This villager is already full of youth. "
                               "No tech points have been deducted.";
                } else if (row == 1 && (g_villager_mask & (1 << 1)) != 0) {
                    nochange = "This villager is already fully mastered. "
                               "No tech points have been deducted.";
                } else if (row == 2 && (g_villager_mask & (1 << 2)) != 0) {
                    nochange = "This villager already likes Running. "
                               "No tech points have been deducted.";
                } else if (row == 2 && (g_villager_mask & (1 << (8 + 2))) != 0) {
                    if ((g_villager_mask & 0x2000) != 0) {
                        /* Likes are full but there is a Running dislike: clear
                           it (free) and report, matching Grant Running to All. */
                        vv4_remove_detail_running_dislike();
                        nochange = "This villager's Likes are full, so Running "
                                   "could not be added, but its Running dislike "
                                   "was removed. No tech points have been "
                                   "deducted.";
                    } else {
                        nochange = "This villager already has full Likes slots. "
                                   "Running can not be added.";
                    }
                } else if (row == 3 && (g_villager_mask & (1 << 3)) != 0) {
                    nochange = "No changes were needed. "
                               "No tech points have been deducted.";
                }
                if (nochange != NULL) {
                    MessageBoxA(window, nochange, "Villager Upgrades",
                                MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
                    return TRUE; /* Stay in the menu; nothing was purchased. */
                }
            }
            /* Only the "Buy" action is confirmed here; the doubler "Remove"
               toggle is reversible and not a purchase. The village-wide rows
               (tech 6/7/8) run their own OFFICIAL confirm from the payload
               after a dry run, so pass straight through for them -- but the
               Collections rows (9/10) take the standard confirm here. */
            if (lstrcmpA(label, "Buy") == 0
                && !(!g_villager_menu && row >= 6 && row <= 8)) {
                const char *name = g_villager_menu ? g_villager_names[row]
                                                   : g_tech_names[row];
                const char *cost = g_villager_menu ? g_villager_costs[row]
                                                   : g_tech_costs[row];
                char msg[256];
                wsprintfA(msg,
                    "Do you want to buy %s for %s tech points?\r\n"
                    "Press OK to confirm, or Cancel.", name, cost);
                if (MessageBoxA(window, msg,
                        g_villager_menu ? "Villager Upgrades" : "Origins Upgrades",
                        MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) != IDOK) {
                    return TRUE; /* Cancel: stay in the menu. */
                }
            }
            g_last_row = row;
            g_last_villager = g_villager_menu;
            EndDialog(window, (INT_PTR)row);
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
    if (villager_menu) {
        dialog_state |= STATE_VILLAGER;
    }
    vv4_prep_fullscreen();
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(resource),
        GetForegroundWindow(),
        upgrade_dialog,
        dialog_state
    );
}

static void appearance_revert(void) {
    *(int *)(appearance_state.villager + VV_HEAD_OFFSET) = appearance_state.original_head;
    *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET) = appearance_state.original_body;
    vv_set_mask(appearance_state.villager, appearance_state.original_mask);
}

/* Writes each tentative value straight into the live villager record so
   the stock renderer (which already reads these exact fields every
   frame, the same field the F6 clothing-cycle cheat uses for body) shows
   the change immediately behind this dialog -- no separate preview
   rendering is built or needed here. Reverted on Cancel/close; kept on
   OK. The tech-point balance check and charge are the caller's job (the
   exact same charge code every other Villager Upgrades row already
   uses) -- this dialog never touches tech points, only the head/body
   fields, and returns 1 only when the player actually confirmed with
   OK. */
static INT_PTR CALLBACK appearance_dialog(
    HWND window,
    UINT message,
    WPARAM wparam,
    LPARAM lparam
) {
    if (message == WM_INITDIALOG) {
        /* appearance_state was already populated by ShowOriginsAppearancePicker
           before this dialog was created; the owner-drawn previews read the
           live head/body/mask fields directly. Show the current mask name. */
        SetDlgItemTextA(window, ID_MASK_LABEL,
                        g_mask_names[vv_get_mask(appearance_state.villager)]);
        vv4_surface_dialog(window);
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        const DRAWITEMSTRUCT *dis = (const DRAWITEMSTRUCT *)lparam;
        if (dis->CtlID == ID_HEAD_PIC) {
            appearance_draw_cell(dis->hDC, dis->rcItem, 1,
                *(int *)(appearance_state.villager + VV_HEAD_OFFSET), 1);
            return TRUE;
        }
        if (dis->CtlID == ID_BODY_PIC) {
            appearance_draw_cell(dis->hDC, dis->rcItem, 0,
                *(int *)(appearance_state.villager + VV_CLOTHING_OFFSET), 1);
            return TRUE;
        }
        if (dis->CtlID == ID_MASK_PIC) {
            /* Preview = the isolated mask, front-facing (VV5 parity); (None)
               shows a blank cell. */
            appearance_draw_mask_cell(dis->hDC, dis->rcItem,
                                      vv_get_mask(appearance_state.villager));
            return TRUE;
        }
        return FALSE;
    } else if (message == WM_COMMAND) {
        unsigned int command = LOWORD(wparam);
        int head_count = appearance_state.head_count;
        int body_count = appearance_state.body_count;
        int *head = (int *)(appearance_state.villager + VV_HEAD_OFFSET);
        int *body = (int *)(appearance_state.villager + VV_CLOTHING_OFFSET);
        if (command == ID_MASK_PREV || command == ID_MASK_NEXT) {
            int delta = (command == ID_MASK_NEXT) ? 1 : (VV_MASK_COUNT - 1);
            int m = (vv_get_mask(appearance_state.villager) + delta) % VV_MASK_COUNT;
            vv_set_mask(appearance_state.villager, m);
            SetDlgItemTextA(window, ID_MASK_LABEL, g_mask_names[m]);
            InvalidateRect(GetDlgItem(window, ID_MASK_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_HEAD_PREV) {
            *head = (*head + head_count - 1) % head_count;
            InvalidateRect(GetDlgItem(window, ID_HEAD_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_HEAD_NEXT) {
            *head = (*head + 1) % head_count;
            InvalidateRect(GetDlgItem(window, ID_HEAD_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_BODY_PREV) {
            *body = (*body + body_count - 1) % body_count;
            InvalidateRect(GetDlgItem(window, ID_BODY_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == ID_BODY_NEXT) {
            *body = (*body + 1) % body_count;
            InvalidateRect(GetDlgItem(window, ID_BODY_PIC), NULL, TRUE);
            return TRUE;
        }
        if (command == IDOK) {
            int head_changed = (*head != appearance_state.original_head);
            int body_changed = (*body != appearance_state.original_body);
            int mask_changed = (vv_get_mask(appearance_state.villager)
                                != appearance_state.original_mask);
            if (!head_changed && !body_changed && !mask_changed) {
                /* OK with nothing changed: no write, no charge (return 0). */
                MessageBoxA(window,
                    "The appearance is unchanged. No tech points have been "
                    "deducted.",
                    "Villager Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
                EndDialog(window, 0);
                return TRUE;
            }
            if (head_changed) {
                /* The head field is hereditary; warn before committing it.
                   Cancel backs out with no write and no charge. */
                if (MessageBoxA(window,
                        "Warning: This will change the villager's head genetics.",
                        "Villager Upgrades",
                        MB_OKCANCEL | MB_ICONWARNING | VV_MB_FRONT) != IDOK) {
                    appearance_revert();
                    EndDialog(window, 0);
                    return TRUE;
                }
            }
            /* Something changed and was confirmed: keep it; caller charges 5,000.
               Persist the mask side-table so the choice survives save/reload. */
            vv_write_mask_sidecar();
            EndDialog(window, 1);
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

/* --- Change Appearance for All (Tech-screen 450,000-point upgrade) ----------
   Dialog 214: per-sex Body/Head/Mask cyclers (value -1 == "No change") plus ONE
   mutually-exclusive whole-village mask mode. Reuses the per-villager picker's
   draw helpers. Applies en-masse over the villager array (head/body -> record,
   mask -> the DLL side-table), charges 450k, and sidecar-saves. No new exe
   caves; dispatched by a one-call tech-menu row. */
enum {                                   /* whole-village mask mode = radio - 3200 */
    FA_MODE_OFF = 0, FA_MODE_VV5, FA_MODE_RANDOM, FA_MODE_RANDOM5, FA_MODE_EQUAL,
    FA_MODE_NONE, FA_MODE_BLUE, FA_MODE_ORANGE, FA_MODE_RED,
    FA_MODE_PURPLE, FA_MODE_CHIEF
};
#define FA_RADIO_FIRST 3200
#define FA_RADIO_LAST  3210
/* Village-wide HEAD mode = radio - 3220 (Off / Random-by-gender / 5 hair buckets). */
enum {
    FA_HEAD_OFF = 0, FA_HEAD_RANDOM, FA_HEAD_BLACK, FA_HEAD_BROWN, FA_HEAD_RED,
    FA_HEAD_BLONDE, FA_HEAD_OTHER
};
#define FA_HEAD_RADIO_FIRST 3220
#define FA_HEAD_RADIO_LAST  3226
/* Village-wide BODY mode = radio - 3240 (Off / Random-by-gender). */
enum { FA_BODY_OFF = 0, FA_BODY_RANDOM };
#define FA_BODY_RADIO_FIRST 3240
#define FA_BODY_RADIO_LAST  3241
#define FA_NOCHANGE (-1)
static struct {
    int male_head, male_body, male_mask;       /* -1 = No change */
    int female_head, female_body, female_mask; /* -1 = No change */
    int tribe_mode;                            /* FA_MODE_* (mask) */
    int head_mode;                             /* FA_HEAD_* (village-wide head) */
    int body_mode;                             /* FA_BODY_* (village-wide body) */
} forall_state;

/* Per-sex head-row -> hair-colour buckets (order: Black, Brown, Red/Ginger,
   Blonde, Other). AUTO-DERIVED from the head-atlas hair band (VV2's method:
   front-frame hair-band median RGB, high-chroma gate for Red so auburn falls to
   Brown). REVIEW PENDING -- adjust an index if a head is miscategorised, esp.
   (a) auburn heads over-labelled Red, and (b) hat/flower-topped heads whose top
   band samples the accessory colour (those legitimately land in Other when the
   hair is accessory-hidden). VV4: 30 heads (0..29) per sex. */
static const unsigned char fa_m_black[]  = {0,1,2,4,7,8};
static const unsigned char fa_m_brown[]  = {3,6,9,10,11,12,13,15};
static const unsigned char fa_m_red[]    = {14,16,20,21,22};
static const unsigned char fa_m_blonde[] = {18,23,24,25,26,27,29};
static const unsigned char fa_m_other[]  = {5,17,19,28};
static const unsigned char fa_f_black[]  = {0,1,2,4,5,6,7,8};
static const unsigned char fa_f_brown[]  = {9,10,11,12,14,15,17,20};
static const unsigned char fa_f_red[]    = {22,24};
static const unsigned char fa_f_blonde[] = {3,23,26,27,28,29};
static const unsigned char fa_f_other[]  = {13,16,18,19,21,25};
struct fa_bucket { const unsigned char *rows; int n; };
/* [female][bucket 0..4] */
static const struct fa_bucket fa_buckets[2][5] = {
    { {fa_m_black,  (int)(sizeof fa_m_black)},  {fa_m_brown,  (int)(sizeof fa_m_brown)},
      {fa_m_red,    (int)(sizeof fa_m_red)},    {fa_m_blonde, (int)(sizeof fa_m_blonde)},
      {fa_m_other,  (int)(sizeof fa_m_other)} },
    { {fa_f_black,  (int)(sizeof fa_f_black)},  {fa_f_brown,  (int)(sizeof fa_f_brown)},
      {fa_f_red,    (int)(sizeof fa_f_red)},    {fa_f_blonde, (int)(sizeof fa_f_blonde)},
      {fa_f_other,  (int)(sizeof fa_f_other)} },
};

static unsigned int fa_rng;
static unsigned int fa_rand(void) {
    fa_rng ^= fa_rng << 13; fa_rng ^= fa_rng >> 17; fa_rng ^= fa_rng << 5;
    return fa_rng;
}
static void fa_shuffle(int *a, int n) {
    int i, j, t;
    for (i = n - 1; i > 0; i--) {
        j = (int)(fa_rand() % (unsigned int)(i + 1));
        t = a[i]; a[i] = a[j]; a[j] = t;
    }
}
/* Cycle one field through [No change, 0 .. count-1] in either direction. */
static int fa_cycle(int v, int count, int dir) {
    int s = v + 1;                             /* 0 = No change; 1..count = value */
    s = (s + (dir > 0 ? 1 : count)) % (count + 1);
    return s - 1;
}
static unsigned char *fa_record(int idx) {
    return (unsigned char *)(VV_REC_ARRAY_BASE + (unsigned int)idx * VV_REC_STRIDE);
}
static int fa_is_male(const unsigned char *rec) {
    return *(const int *)(rec + VV_SEX_OFFSET) == 0;   /* 0 = male */
}

/* Pick a head row for the village-wide HEAD mode: FA_HEAD_RANDOM = any row of
   the villager's sex; a bucket mode = a random row of that hair colour. Empty
   buckets fall back to any row so the feature never no-ops silently. */
static int fa_pick_head(int female, int head_mode) {
    if (head_mode == FA_HEAD_RANDOM) {
        return (int)(fa_rand() % (unsigned int)VV_HEAD_COUNT);
    }
    {
        const struct fa_bucket *b = &fa_buckets[female ? 1 : 0][head_mode - FA_HEAD_BLACK];
        if (b->n <= 0) {
            return (int)(fa_rand() % (unsigned int)VV_HEAD_COUNT);
        }
        return b->rows[fa_rand() % (unsigned int)b->n];
    }
}

/* Apply the chosen appearance to every active villager. */
static void vv4_apply_for_all(void) {
    int active[VV_MAX_VILLAGERS];
    int actsex[VV_MAX_VILLAGERS];              /* 1 = male */
    int nact = 0;
    int i, idx, mode;

    fa_rng = GetTickCount() | 1u;
    for (idx = 0; idx < VV_MAX_VILLAGERS; idx++) {
        unsigned char *rec = fa_record(idx);
        int male;
        if (rec[VV_OCCUPIED_OFFSET] == 0) {
            continue;                          /* empty/dead slot */
        }
        male = fa_is_male(rec);
        /* HEAD: a village-wide mode overrides the per-sex Head cycler. */
        if (forall_state.head_mode != FA_HEAD_OFF) {
            *(int *)(rec + VV_HEAD_OFFSET) = fa_pick_head(!male, forall_state.head_mode);
        } else {
            int h = male ? forall_state.male_head : forall_state.female_head;
            if (h != FA_NOCHANGE)
                *(int *)(rec + VV_HEAD_OFFSET) = h;
        }
        /* BODY: a village-wide mode overrides the per-sex Body cycler. */
        if (forall_state.body_mode != FA_BODY_OFF) {
            *(int *)(rec + VV_CLOTHING_OFFSET) =
                (int)(fa_rand() % (unsigned int)VV_BODY_COUNT);
        } else {
            int b = male ? forall_state.male_body : forall_state.female_body;
            if (b != FA_NOCHANGE)
                *(int *)(rec + VV_CLOTHING_OFFSET) = b;
        }
        active[nact] = idx;
        actsex[nact] = male;
        nact++;
    }

    mode = forall_state.tribe_mode;
    if (mode == FA_MODE_OFF) {                  /* per-sex mask cyclers */
        for (i = 0; i < nact; i++) {
            int m = actsex[i] ? forall_state.male_mask : forall_state.female_mask;
            if (m != FA_NOCHANGE) {
                vv_set_mask(fa_record(active[i]), m);
            }
        }
    } else if (mode >= FA_MODE_NONE) {          /* one solid colour for everyone */
        int solid = mode - FA_MODE_NONE;        /* 0=(None),1=Blue..5=Chief */
        for (i = 0; i < nact; i++) {
            vv_set_mask(fa_record(active[i]), solid);
        }
    } else if (mode == FA_MODE_RANDOM) {            /* All 5 + No Mask (0..5) */
        for (i = 0; i < nact; i++) {
            vv_set_mask(fa_record(active[i]), (int)(fa_rand() % VV_MASK_COUNT));
        }
    } else if (mode == FA_MODE_RANDOM5) {           /* All 5 colours only (1..5) */
        for (i = 0; i < nact; i++) {
            vv_set_mask(fa_record(active[i]), (int)(fa_rand() % 5u) + 1);
        }
    } else if (mode == FA_MODE_VV5) {
        int order[VV_MAX_VILLAGERS];
        int n, k;
        for (i = 0; i < nact; i++) order[i] = active[i];
        fa_shuffle(order, nact);
        for (k = 0; k < nact; k++) {
            int col;
            if (k < 1) col = 5;                 /* 1 Chief */
            else if (k < 1 + 4) col = 4;        /* 4 Purple */
            else if (k < 1 + 4 + 7) col = 3;    /* up to 7 Red */
            else if (k < 1 + 4 + 7 + 10) col = 2; /* up to 10 Orange */
            else col = 1;                       /* rest Blue */
            vv_set_mask(fa_record(order[k]), col);
        }
        (void)n;
    } else if (mode == FA_MODE_EQUAL) {
        int males[VV_MAX_VILLAGERS], females[VV_MAX_VILLAGERS];
        int nm = 0, nf = 0, order[VV_MAX_VILLAGERS], no = 0, mi = 0, fi = 0, k;
        for (i = 0; i < nact; i++) {
            if (actsex[i]) males[nm++] = active[i]; else females[nf++] = active[i];
        }
        fa_shuffle(males, nm);
        fa_shuffle(females, nf);
        while (mi < nm || fi < nf) {            /* interleave M,F,M,F,... */
            if (mi < nm) order[no++] = males[mi++];
            if (fi < nf) order[no++] = females[fi++];
        }
        for (k = 0; k < no; k++) {
            vv_set_mask(fa_record(order[k]), (k % 5) + 1);   /* 1..5 balanced per sex */
        }
    }
    vv_write_mask_sidecar();
}

/* Draw one for-All preview cell (or "No change"). */
static void fa_draw_cell(const DRAWITEMSTRUCT *dis, int value, int is_head,
                         int is_mask, int sex_female) {
    if (value == FA_NOCHANGE) {
        FillRect(dis->hDC, &dis->rcItem, (HBRUSH)(COLOR_BTNFACE + 1));
        DrawTextA(dis->hDC, "No change", -1, (RECT *)&dis->rcItem,
                  DT_CENTER | DT_VCENTER | DT_SINGLELINE);
        return;
    }
    if (is_mask) {
        appearance_draw_mask_cell(dis->hDC, dis->rcItem, value);
        return;
    }
    appearance_state.sex = sex_female;          /* draw helper reads this global */
    appearance_state.is_old = 0;                /* young atlas for the preview */
    appearance_draw_cell(dis->hDC, dis->rcItem, is_head, value, 1);
}

static void fa_sync_enable(HWND window) {
    /* A non-Off village-wide mode greys the matching per-sex cyclers (the
       village-wide choice overrides them). Each group's "Off" radio is its
       FIRST id (mask 3200, head 3220, body 3240). */
    BOOL mask_off = (IsDlgButtonChecked(window, FA_RADIO_FIRST) == BST_CHECKED);
    BOOL head_off = (IsDlgButtonChecked(window, FA_HEAD_RADIO_FIRST) == BST_CHECKED);
    BOOL body_off = (IsDlgButtonChecked(window, FA_BODY_RADIO_FIRST) == BST_CHECKED);
    int mask_ids[6] = { 3021, 3022, 3023, 3121, 3122, 3123 };
    int head_ids[6] = { 3001, 3002, 3003, 3101, 3102, 3103 };
    int body_ids[6] = { 3011, 3012, 3013, 3111, 3112, 3113 };
    int i;
    for (i = 0; i < 6; i++) {
        EnableWindow(GetDlgItem(window, mask_ids[i]), mask_off);
        EnableWindow(GetDlgItem(window, head_ids[i]), head_off);
        EnableWindow(GetDlgItem(window, body_ids[i]), body_off);
    }
}

static INT_PTR CALLBACK forall_dialog(HWND window, UINT message,
                                      WPARAM wparam, LPARAM lparam) {
    (void)lparam;
    if (message == WM_INITDIALOG) {
        forall_state.male_head = forall_state.male_body = forall_state.male_mask =
            FA_NOCHANGE;
        forall_state.female_head = forall_state.female_body =
            forall_state.female_mask = FA_NOCHANGE;
        forall_state.tribe_mode = FA_MODE_OFF;
        forall_state.head_mode = FA_HEAD_OFF;
        forall_state.body_mode = FA_BODY_OFF;
        CheckDlgButton(window, FA_RADIO_FIRST, BST_CHECKED);
        CheckDlgButton(window, FA_HEAD_RADIO_FIRST, BST_CHECKED);
        CheckDlgButton(window, FA_BODY_RADIO_FIRST, BST_CHECKED);
        fa_sync_enable(window);
        vv4_surface_dialog(window);
        return TRUE;
    } else if (message == WM_DRAWITEM) {
        const DRAWITEMSTRUCT *dis = (const DRAWITEMSTRUCT *)lparam;
        switch (dis->CtlID) {
        case 3013: fa_draw_cell(dis, forall_state.male_body, 0, 0, 0); return TRUE;
        case 3003: fa_draw_cell(dis, forall_state.male_head, 1, 0, 0); return TRUE;
        case 3023: fa_draw_cell(dis, forall_state.male_mask, 0, 1, 0); return TRUE;
        case 3113: fa_draw_cell(dis, forall_state.female_body, 0, 0, 1); return TRUE;
        case 3103: fa_draw_cell(dis, forall_state.female_head, 1, 0, 1); return TRUE;
        case 3123: fa_draw_cell(dis, forall_state.female_mask, 0, 1, 1); return TRUE;
        default: return FALSE;
        }
    } else if (message == WM_COMMAND) {
        int id = LOWORD(wparam);
        int dir = 0, *field = NULL, count = 0, pic = 0;
        switch (id) {
        case 3011: field = &forall_state.male_body;   count = VV_BODY_COUNT; dir = -1; pic = 3013; break;
        case 3012: field = &forall_state.male_body;   count = VV_BODY_COUNT; dir =  1; pic = 3013; break;
        case 3001: field = &forall_state.male_head;   count = VV_HEAD_COUNT; dir = -1; pic = 3003; break;
        case 3002: field = &forall_state.male_head;   count = VV_HEAD_COUNT; dir =  1; pic = 3003; break;
        case 3021: field = &forall_state.male_mask;   count = VV_MASK_COUNT; dir = -1; pic = 3023; break;
        case 3022: field = &forall_state.male_mask;   count = VV_MASK_COUNT; dir =  1; pic = 3023; break;
        case 3111: field = &forall_state.female_body; count = VV_BODY_COUNT; dir = -1; pic = 3113; break;
        case 3112: field = &forall_state.female_body; count = VV_BODY_COUNT; dir =  1; pic = 3113; break;
        case 3101: field = &forall_state.female_head; count = VV_HEAD_COUNT; dir = -1; pic = 3103; break;
        case 3102: field = &forall_state.female_head; count = VV_HEAD_COUNT; dir =  1; pic = 3103; break;
        case 3121: field = &forall_state.female_mask; count = VV_MASK_COUNT; dir = -1; pic = 3123; break;
        case 3122: field = &forall_state.female_mask; count = VV_MASK_COUNT; dir =  1; pic = 3123; break;
        default: break;
        }
        if (field != NULL) {
            *field = fa_cycle(*field, count, dir);
            InvalidateRect(GetDlgItem(window, pic), NULL, TRUE);
            return TRUE;
        }
        if (id >= FA_RADIO_FIRST && id <= FA_RADIO_LAST) {
            forall_state.tribe_mode = id - FA_RADIO_FIRST;   /* auto-radio handles check */
            fa_sync_enable(window);
            return TRUE;
        }
        if (id >= FA_HEAD_RADIO_FIRST && id <= FA_HEAD_RADIO_LAST) {
            forall_state.head_mode = id - FA_HEAD_RADIO_FIRST;
            fa_sync_enable(window);
            return TRUE;
        }
        if (id >= FA_BODY_RADIO_FIRST && id <= FA_BODY_RADIO_LAST) {
            forall_state.body_mode = id - FA_BODY_RADIO_FIRST;
            fa_sync_enable(window);
            return TRUE;
        }
        if (id == IDOK) { EndDialog(window, 1); return TRUE; }
        if (id == IDCANCEL) { EndDialog(window, 0); return TRUE; }
    } else if (message == WM_CLOSE) {
        EndDialog(window, 0);
        return TRUE;
    }
    return FALSE;
}

/* Tech-menu row entry point: show the dialog, and on OK charge 450,000 and
   apply. Returns 1 when applied+charged, 0 otherwise. No arg needed -- VV4's
   tech points are the global at 0x4D6F88 and the record array is fixed. */
static int fa_nothing_selected(void) {
    return forall_state.tribe_mode == FA_MODE_OFF &&
           forall_state.head_mode == FA_HEAD_OFF &&
           forall_state.body_mode == FA_BODY_OFF &&
           forall_state.male_head == FA_NOCHANGE &&
           forall_state.male_body == FA_NOCHANGE &&
           forall_state.male_mask == FA_NOCHANGE &&
           forall_state.female_head == FA_NOCHANGE &&
           forall_state.female_body == FA_NOCHANGE &&
           forall_state.female_mask == FA_NOCHANGE;
}

__declspec(dllexport) int __stdcall ShowVv4AppearanceForAll(void) {
    vv4_prep_fullscreen();
    /* Buy-confirm before the dialog (parity wording across all 5 games). */
    if (MessageBoxA(NULL,
            "Do you want to buy Change Appearance for All for 450,000 tech "
            "points?\r\nPress OK to confirm, or Cancel.",
            "Change Appearance for All",
            MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) != IDOK) {
        return 0;
    }
    if ((int)DialogBoxParamA(module_instance, MAKEINTRESOURCEA(214), NULL,
                             forall_dialog, 0) != 1) {
        return 0;                              /* cancelled -> no charge */
    }
    if (fa_nothing_selected()) {
        MessageBoxA(NULL,
            "No appearance options were selected. No tech points deducted.",
            "Change Appearance for All", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    if (*(volatile unsigned int *)(UINT_PTR)0x4D6F88u < 450000u) {
        MessageBoxA(NULL,
            "Not enough tech points. This upgrade costs 450,000.",
            "Change Appearance for All", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    /* Head is hereditary: warn once before committing a head change en-masse. */
    if (forall_state.male_head != FA_NOCHANGE ||
        forall_state.female_head != FA_NOCHANGE ||
        forall_state.head_mode != FA_HEAD_OFF) {
        if (MessageBoxA(NULL,
                "Warning: This will change the head genetics of every villager "
                "of the selected sex, affecting their descendants.\r\n\r\n"
                "Proceed?",
                "Change Appearance for All",
                MB_OKCANCEL | MB_ICONWARNING | VV_MB_FRONT) != IDOK) {
            return 0;
        }
    }
    vv4_apply_for_all();
    __asm {
        push -450000
        mov  ecx, 0x4D6F88
        mov  eax, 0x41E300
        call eax
    }
    MessageBoxA(NULL, "Change Appearance for All applied to every villager.",
                "Change Appearance for All", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    return 1;
}

__declspec(dllexport) int __stdcall ShowOriginsAppearancePicker(
    int villager_ptr
) {
    unsigned char *villager = (unsigned char *)(UINT_PTR)(unsigned int)villager_ptr;
    if (villager == NULL) {
        return 0;
    }
    vv4_ensure_gdiplus();
    vv4_prep_fullscreen();
    appearance_state.villager = villager;
    appearance_state.original_head = *(int *)(villager + VV_HEAD_OFFSET);
    appearance_state.original_body = *(int *)(villager + VV_CLOTHING_OFFSET);
    /* A magic-untagged (uninitialised) slot reads as (None); no write-back so an
       unopened villager's garbage never counts as a change. */
    appearance_state.original_mask = vv_get_mask(villager);
    appearance_state.head_count = VV_HEAD_COUNT;
    appearance_state.body_count = VV_BODY_COUNT;
    appearance_state.sex = *(int *)(villager + VV_SEX_OFFSET);
    appearance_state.is_old =
        *(int *)(villager + VV_DISPLAY_AGE_OFFSET) >= VV_OLD_AGE_THRESHOLD;
    return (int)DialogBoxParamA(
        module_instance,
        MAKEINTRESOURCEA(IDD_ORIGINS_APPEARANCE),
        GetForegroundWindow(),
        appearance_dialog,
        (LPARAM)(UINT_PTR)villager
    );
}

/* Simple status popup for the payload's upgrade menus ("Purchased.",
   "Not enough tech points.", etc.). Owned by the game's foreground window so
   it reliably appears on top -- a NULL owner could render behind the game
   window right after the menu dialog closed and never be seen. */
__declspec(dllexport) int __stdcall ShowOriginsUpgradeMessage(
    const char *title,
    const char *text
) {
    char msg[192];
    const char *out = (text != NULL) ? text : "";
    /* The payload's Barrel capacity guard uses a short string to fit the full
       payload string table; render the OFFICIAL near-max wording here where DLL
       string space is free. Row-independent, so it always translates. */
    if (text != NULL
        && lstrcmpA(text,
               "The village population is already at maximum capacity.") == 0) {
        out = "Village population is close to its maximum. The Barrel of Babies "
              "needs room for 3 children. No tech points have been deducted.";
    } else if (text != NULL && g_last_row >= 0) {
        /* Translate the payload's generic result strings into the OFFICIAL
           per-upgrade wording, using the row the player just clicked. (Cure and
           the village-wide grants have their own result exports and never reach
           here.) */
        const char *const *names = g_last_villager ? g_villager_names
                                                   : g_tech_names;
        int nmax = g_last_villager ? 5 : 9;
        if (g_last_row < nmax) {
            if (lstrcmpA(text, "Purchased.") == 0) {
                if (g_last_villager && g_last_row == 4) {
                    return 0;  /* Change Appearance shows no result box */
                }
                wsprintfA(msg, "%s completed.", names[g_last_row]);
                out = msg;
            } else if (lstrcmpA(text, "Removed.") == 0) {
                wsprintfA(msg, "%s was removed. No refund was issued.",
                          names[g_last_row]);
                out = msg;
            }
        }
    }
    MessageBoxA(
        GetForegroundWindow(),
        out,
        title != NULL ? title : "Origins Upgrades",
        MB_OK | VV_MB_FRONT
    );
    return 0;
}

/* Full Heal / Cure All result. The caller (the exact-build .shr cure cave)
   passes how many villagers had their sickness cleared and how many were
   restored to full health. Shows the exact two-line result, or -- when both
   are zero -- the all-healthy notice, and returns 1 when anything was done /
   0 when nothing was so the caller can refund the charge. */
__declspec(dllexport) int __stdcall ShowOriginsCureResult(
    int sickness_cleared,
    int health_restored
) {
    char text[256];
    if (sickness_cleared == 0 && health_restored == 0) {
        MessageBoxA(
            GetForegroundWindow(),
            "Everyone is at full health already. No villagers are sick. "
            "No tech points have been deducted.",
            "Origins Upgrades",
            MB_OK | VV_MB_FRONT
        );
        return 0;
    }
    wsprintfA(
        text,
        "Cured sickness from %d villagers.\r\n\r\n"
        "Restored %d villagers to full health.",
        sickness_cleared,
        health_restored
    );
    MessageBoxA(GetForegroundWindow(), text, "Origins Upgrades", MB_OK);
    return 1;
}

/* ---- Complete / Reset All Collections (VV4 collectible + goal system) ----
   Reverse-engineered from the native collect handler at 0x4144xx (verified
   live with Cheat Engine): the 48 collectible found-flags are the contiguous
   dwords 0x4CC918..0x4CC9D4 (Fish Scales, Lab Pieces, Mausoleum, Wind Flutes;
   found == non-zero). Each collection's TROPHY only latches through the game's
   own goal machinery, so we drive it exactly as a natural final collect does:
   enqueue each collection goal id through the native goal writer 0x44B890
   (thiscall on the goal manager 0x4DACE0), which the game drains on the next
   tick and shows the trophy. Goal ids: Fish 0x302, Lab 0x303, Mausoleum 0x304,
   Wind Flute 0x305, master "All Collections Complete!" 0x306. Reset clears the
   flags and zeroes those five 0x20-byte goal records; the shared difficulty-
   scaled score stats and one-time rewards are left untouched (not collection-
   exclusive / not reversible), so Reset undoes exactly what Complete did. */
#define VV4_COLL_FLAG_BASE   0x4CC918u   /* found-flag for item index 0x46 */
#define VV4_COLL_FLAG_COUNT  48
#define VV4_GOAL_MANAGER     0x4DACE0u
#define VV4_GOAL_RECORD(id)  (VV4_GOAL_MANAGER + (unsigned)((id) - 0x2AA) * 0x20u)

static const int VV4_COLLECTION_GOALS[5] = { 0x302, 0x303, 0x304, 0x305, 0x306 };

/* The Trophies-screen "N of 12" progress is a native statistic, not the
   found-flags: the collect handler increments a per-collection stat for each
   new find via 0x412F90 (ECX = stat manager 0x4CBB98). Records are 12 bytes at
   [0x4CBB98 + id*12] = { byte0 complete-flag, +4 value }, and the writer latches
   the trophy when the value reaches its threshold. Fish Scales 0xE, Lab 0x11,
   Mausoleum 0xF, Wind Flutes 0x10 (indexed by collection = flag_index / 12). */
#define VV4_STAT_MANAGER     0x4CBB98u
#define VV4_STAT_RECORD(id)  (VV4_STAT_MANAGER + (unsigned)(id) * 12u)
static const int VV4_COLLECTION_STATS[4] = { 0xE, 0x11, 0xF, 0x10 };

/* Enqueue one goal through the native writer 0x44B890 (thiscall: this in ECX,
   three stack args, callee-cleaned via ret 0xC). Inline asm keeps the exact
   calling convention without a __thiscall typedef the C compiler rejects. */
static void vv4_enqueue_goal(int id) {
    void *mgr = (void *)(UINT_PTR)VV4_GOAL_MANAGER;
    __asm {
        push 0
        push 0
        mov  eax, id
        push eax
        mov  ecx, mgr
        mov  eax, 0x44B890
        call eax
    }
}

/* Add `amount` to statistic `id` via the native writer 0x412F90 (thiscall:
   this in ECX = stat manager, two stack args id/amount, ret 8). Reaching the
   stat's threshold latches its trophy, exactly as a real new find does. */
static void vv4_stat_add(int id, int amount) {
    void *mgr = (void *)(UINT_PTR)VV4_STAT_MANAGER;
    __asm {
        mov  eax, amount
        push eax
        mov  eax, id
        push eax
        mov  ecx, mgr
        mov  eax, 0x412F90
        call eax
    }
}

/* Returns the number of collectibles newly marked found (0 => everything was
   already complete, so the caller can report no-change and refund the charge). */
__declspec(dllexport) int __stdcall ApplyVV4CompleteCollections(void) {
    unsigned int *flags = (unsigned int *)(UINT_PTR)VV4_COLL_FLAG_BASE;
    int i, newly = 0;
    for (i = 0; i < VV4_COLL_FLAG_COUNT; ++i) {
        if (flags[i] == 0) {
            flags[i] = 1;
            /* Drive the same progress stat a real new find fires, so the
               Trophies screen reaches N-of-12 and latches (found-flags alone
               update the Collections screen but never the trophy). */
            vv4_stat_add(VV4_COLLECTION_STATS[i / 12], 1);
            ++newly;
        }
    }
    if (newly == 0) {
        /* Everything was already found: no-change, no charge (payload refunds
           on a 0 return). */
        MessageBoxA(GetForegroundWindow(),
            "All collectibles are already found. No tech points have been "
            "deducted.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    /* Fire every collection trophy plus the master; the writer is idempotent
       (it skips a goal whose record is already latched), so it is safe even for
       collections that were already complete. */
    for (i = 0; i < 5; ++i) {
        vv4_enqueue_goal(VV4_COLLECTION_GOALS[i]);
    }
    {
        char msg[160];
        wsprintfA(msg,
            "Marked all %d collectibles as found and triggered %d collection goals.",
            VV4_COLL_FLAG_COUNT, 5);
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    }
    return newly;
}

/* Returns the number of collectibles cleared (0 => nothing was collected). */
__declspec(dllexport) int __stdcall ApplyVV4ResetCollections(void) {
    unsigned int *flags = (unsigned int *)(UINT_PTR)VV4_COLL_FLAG_BASE;
    int i, cleared = 0;
    for (i = 0; i < VV4_COLL_FLAG_COUNT; ++i) {
        if (flags[i] != 0) { flags[i] = 0; ++cleared; }
    }
    if (cleared == 0) {
        /* Nothing was collected: no-change, no charge (payload refunds on 0). */
        MessageBoxA(GetForegroundWindow(),
            "The collections are already cleared. No tech points have been "
            "deducted.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    /* Mark each collection goal/trophy incomplete again by zeroing its record. */
    for (i = 0; i < 5; ++i) {
        unsigned char *rec =
            (unsigned char *)(UINT_PTR)VV4_GOAL_RECORD(VV4_COLLECTION_GOALS[i]);
        int j;
        for (j = 0; j < 0x20; ++j) { rec[j] = 0; }
    }
    /* Reset the four "N of 12" progress stats (value + latched flag) so the
       Trophies screen shows the collections incomplete again, plus the master
       "collections completed" counter (stat 0x12) that the native latch
       (0x412F10) bumps once per completed collection -- otherwise the "Master
       Collector - 4 of 4" trophy stays complete after a reset. */
    for (i = 0; i < 4; ++i) {
        unsigned char *rec =
            (unsigned char *)(UINT_PTR)VV4_STAT_RECORD(VV4_COLLECTION_STATS[i]);
        int j;
        for (j = 0; j < 12; ++j) { rec[j] = 0; }
    }
    {
        unsigned char *master = (unsigned char *)(UINT_PTR)VV4_STAT_RECORD(0x12);
        int j;
        for (j = 0; j < 12; ++j) { master[j] = 0; }
    }
    {
        char msg[96];
        wsprintfA(msg, "Cleared all %d collectibles.", VV4_COLL_FLAG_COUNT);
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    }
    return cleared;
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

/* ---- Village-wide dry-run counting (for VV5-task9-style confirms) ---- */
#define VV_RECORD_BASE       0x50E5AC
#define VV_RECORD_STRIDE     0x2E3C
#define VV_RECORD_COUNT_ADDR 0x42001C   /* record-array capacity (150) */
#define VV_ACTIVE_OFFSET     0x1CC4
#define VV_DEAD_OFFSET       0x1CC7
#define VV_HEALTH_OFFSET     0x1C40
#define VVW_LIKES_OFFSET     0x1E60
#define VVW_DISLIKES_OFFSET  0x1E6C
#define VV_SKILL0_OFFSET     0x1C5C
#define VV_PREF_OFFSET       0x1C70   /* preferred-skill: -1 none, 0 Farm,1 Parent,2 Heal,3 Research,4 Build */
#define VV_DISPLAY_AGE_OFF   0x1B8C
#define VV_RUNNING_PREF      38
#define VV_LIKE_SLOTS        3
#define VV_SKILL_COUNT       5
#define VV_MASTER_VALUE      0x42C80000  /* float 100.0 */
#define VV_AGE_18            360         /* 20 displayed units per year */

static int vv_record_total(void) { return *(int *)VV_RECORD_COUNT_ADDR; }
static unsigned char *vv_record(int i) {
    return (unsigned char *)(VV_RECORD_BASE + (unsigned)i * VV_RECORD_STRIDE);
}
static int vv_eligible(const unsigned char *r) {
    return r[VV_ACTIVE_OFFSET] != 0 && r[VV_DEAD_OFFSET] == 0
        && *(const int *)(r + VV_HEALTH_OFFSET) > 0;
}

/* Dry-run counts for the current village-wide action, computed in the confirm
   and reused in the result. Valid only within one confirm->apply->result
   sequence, which is modal so village state cannot change between them. */
static int vw_granted, vw_already, vw_full, vw_removed;

static const char *vv_villagers(int n) { return n == 1 ? "Villager" : "Villagers"; }

/* ---- Equal Division of Labor ----
   Round-robin every living villager's preferred-skill field (+0x1C70) across the
   professions in the requested order -- Farmer, Builder, Researcher, Healer[,
   Parenting] -- cycling males and females INDEPENDENTLY so each profession ends
   with a balanced count and a balanced male/female split. Everyone living is
   eligible (children of any age, nursing moms, adults); it overwrites each
   villager's current preference unconditionally, so N is simply how many were
   eligible. Preferred-skill values: 0=Farming 1=Parenting 2=Healing 3=Research
   4=Building. vw_prof_m/f are indexed by that value. */
static int vw_prof_m[5], vw_prof_f[5];
static int vv4_apply_equal_division(int include_parenting) {
    static const int order_p[5]  = { 0, 4, 3, 2, 1 }; /* Farmer,Builder,Researcher,Healer,Parenting */
    static const int order_np[4] = { 0, 4, 3, 2 };    /* Farmer,Builder,Researcher,Healer */
    const int *order = include_parenting ? order_p : order_np;
    const int n = include_parenting ? 5 : 4;
    int total = vv_record_total(), i, assigned = 0, male_idx = 0, female_idx = 0, p;
    for (p = 0; p < 5; ++p) { vw_prof_m[p] = 0; vw_prof_f[p] = 0; }
    for (i = 0; i < total; ++i) {
        unsigned char *r = vv_record(i);
        int val;
        if (!vv_eligible(r)) continue;
        if (r[VV_SEX_OFFSET] != 0) { val = order[female_idx % n]; ++female_idx; ++vw_prof_f[val]; }
        else                       { val = order[male_idx   % n]; ++male_idx;   ++vw_prof_m[val]; }
        *(int *)(r + VV_PREF_OFFSET) = val;
        ++assigned;
    }
    return assigned;
}

/* Append one "Skill: N Villagers (N Male, N Female)." line for profession value v. */
static char *vv4_ed_line(char *p, const char *name, int v) {
    int m = vw_prof_m[v], f = vw_prof_f[v];
    return p + wsprintfA(p, "\n\n%s: %d %s (%d Male, %d Female).",
                         name, m + f, vv_villagers(m + f), m, f);
}

/* Apply Equal Division and show the OFFICIAL result box. Returns the number of
   villagers assigned (0 => none eligible, no charge -- the payload refunds). */
static int vv4_equal_division(int include_parenting) {
    int assigned = vv4_apply_equal_division(include_parenting);
    char msg[512], *p = msg;
    if (assigned == 0) {
        MessageBoxA(GetForegroundWindow(),
            "No villagers were eligible. No tech points have been deducted.",
            "Origins Upgrades", MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
        return 0;
    }
    p += wsprintfA(p, "Set %d %s' Job Preferences.",
                   assigned, assigned == 1 ? "Villager" : "Villagers");
    p = vv4_ed_line(p, "Farming", 0);
    p = vv4_ed_line(p, "Building", 4);
    p = vv4_ed_line(p, "Research", 3);
    p = vv4_ed_line(p, "Healing", 2);
    if (include_parenting) vv4_ed_line(p, "Breeding", 1);
    MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    return assigned;
}

__declspec(dllexport) int __stdcall ApplyVV4EqualDivisionParenting(void) {
    return vv4_equal_division(1);
}
__declspec(dllexport) int __stdcall ApplyVV4EqualDivisionNoParenting(void) {
    return vv4_equal_division(0);
}

/* Running: classify every eligible villager into granted / already-liking /
   full-slots, and count how many of the granted ones also had a Running
   dislike that will be removed. */
static void vv_scan_running(void) {
    int total = vv_record_total(), i;
    vw_granted = vw_already = vw_full = vw_removed = 0;
    for (i = 0; i < total; ++i) {
        const unsigned char *r = vv_record(i);
        const int *likes;
        int s, has_run = 0, free_slot = 0;
        if (!vv_eligible(r)) continue;
        likes = (const int *)(r + VVW_LIKES_OFFSET);
        for (s = 0; s < VV_LIKE_SLOTS; ++s) {
            if (likes[s] == VV_RUNNING_PREF) has_run = 1;
            else if (likes[s] == -1) free_slot = 1;
        }
        if (has_run) { ++vw_already; continue; }
        if (!free_slot) {
            /* Full Likes: the Like can't be added, but a Running Dislike is
               still cleared (free) -- OFFICIAL edge case counts this villager in
               BOTH "Skipped: already have 3 likes" AND "Removed a dislike". */
            const int *dis = (const int *)(r + VVW_DISLIKES_OFFSET);
            ++vw_full;
            for (s = 0; s < VV_LIKE_SLOTS; ++s) {
                if (dis[s] == VV_RUNNING_PREF) { ++vw_removed; break; }
            }
            continue;
        }
        ++vw_granted;
        {
            const int *dis = (const int *)(r + VVW_DISLIKES_OFFSET);
            for (s = 0; s < VV_LIKE_SLOTS; ++s) {
                if (dis[s] == VV_RUNNING_PREF) { ++vw_removed; break; }
            }
        }
    }
}

/* Mastery: eligible villagers with any skill below 100 are mastered; the rest
   are already fully mastered. */
static void vv_scan_mastery(void) {
    int total = vv_record_total(), i;
    vw_granted = vw_already = 0;
    for (i = 0; i < total; ++i) {
        const unsigned char *r = vv_record(i);
        const int *sk;
        int s, full = 1;
        if (!vv_eligible(r)) continue;
        sk = (const int *)(r + VV_SKILL0_OFFSET);
        for (s = 0; s < VV_SKILL_COUNT; ++s) {
            if (sk[s] != (int)VV_MASTER_VALUE) { full = 0; break; }
        }
        if (full) ++vw_already; else ++vw_granted;
    }
}

/* Age dry-run: vw_granted = eligible villagers that will be set to 18 (not
   already exactly 18), vw_already = eligible villagers already at 18. */
static void vv_scan_age18(void) {
    int total = vv_record_total(), i;
    vw_granted = vw_already = 0;
    for (i = 0; i < total; ++i) {
        const unsigned char *r = vv_record(i);
        if (!vv_eligible(r)) continue;
        if (*(const int *)(r + VV_DISPLAY_AGE_OFF) == VV_AGE_18) ++vw_already;
        else ++vw_granted;
    }
}

/* Free removal path for Grant Running to All when NO Like can be added anywhere
   (every eligible villager has full Like slots) but some have Running in a
   Dislike slot: clear those Dislikes, no charge. Mirrors the detail Grant
   Running edge case and the OFFICIAL note. */
static void vv4_clear_full_slot_running_dislikes(void) {
    int total = vv_record_total(), i, s;
    for (i = 0; i < total; ++i) {
        unsigned char *r = vv_record(i);
        const int *likes, *dis;
        int has_run = 0, free_slot = 0, has_dis = 0;
        if (!vv_eligible(r)) continue;
        likes = (const int *)(r + VVW_LIKES_OFFSET);
        for (s = 0; s < VV_LIKE_SLOTS; ++s) {
            if (likes[s] == VV_RUNNING_PREF) has_run = 1;
            else if (likes[s] == -1) free_slot = 1;
        }
        if (has_run || free_slot) continue;   /* has/can-add a Running Like */
        dis = (const int *)(r + VVW_DISLIKES_OFFSET);
        for (s = 0; s < VV_LIKE_SLOTS; ++s) {
            if (dis[s] == VV_RUNNING_PREF) { has_dis = 1; break; }
        }
        if (!has_dis) continue;
        {
            void *dislikes = r + VVW_DISLIKES_OFFSET;
            __asm {
                push 38
                mov  ecx, dislikes
                mov  eax, 0x45D1C0
                call eax
            }
        }
    }
}

/* Confirmation shown before charging a village-wide upgrade (OFFICIAL wording).
   Dry-runs first: if nothing would change, report it with no charge and return
   0; otherwise show "Do you want to buy ... ?" and return 1 only on OK.
   Commands not yet converted return 1 (proceed with the old flow). */
__declspec(dllexport) int __stdcall ConfirmOriginsVillageWide(int command) {
    if (command == 6) {
        vv_scan_running();
        if (vw_granted == 0) {
            if (vw_removed > 0) {
                /* No Like can be added anywhere, but some full-slot villagers
                   have a Running Dislike -- clear those free (no charge) and
                   report, matching the detail path and the OFFICIAL edge case. */
                char msg[256], line[128];
                vv4_clear_full_slot_running_dislikes();
                wsprintfA(msg, "Removed a Running dislike from %d %s.",
                          vw_removed, vv_villagers(vw_removed));
                if (vw_full) {
                    wsprintfA(line,
                              "\r\n\r\nSkipped %d %s: already have 3 likes.",
                              vw_full, vv_villagers(vw_full));
                    lstrcatA(msg, line);
                }
                lstrcatA(msg, "\r\n\r\nNo tech points have been deducted.");
                MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                            MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
                return 0;
            }
            MessageBoxA(GetForegroundWindow(),
                "Everyone already likes running, or has full Likes slots. "
                "No tech points have been deducted.",
                "Origins Upgrades", MB_OK | MB_ICONWARNING | VV_MB_FRONT);
            return 0;
        }
        return MessageBoxA(GetForegroundWindow(),
            "Do you want to buy Grant Running to All Villagers for 1,000,000 "
            "tech points?\r\nPress OK to confirm, or Cancel.",
            "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) == IDOK;
    }
    if (command == 7) {
        vv_scan_mastery();
        if (vw_granted == 0) {
            MessageBoxA(GetForegroundWindow(),
                "Everyone has already mastered their skills. "
                "No tech points have been deducted.",
                "Origins Upgrades", MB_OK | MB_ICONWARNING | VV_MB_FRONT);
            return 0;
        }
        return MessageBoxA(GetForegroundWindow(),
            "Do you want to buy Grant Full Mastery to All Villagers for "
            "1,000,000 tech points?\r\nPress OK to confirm, or Cancel.",
            "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) == IDOK;
    }
    if (command == 8) {
        vv_scan_age18();
        if (vw_granted == 0) {
            MessageBoxA(GetForegroundWindow(),
                "Everyone is already exactly 18. No tech points have been deducted.",
                "Origins Upgrades", MB_OK | MB_ICONWARNING | VV_MB_FRONT);
            return 0;
        }
        return MessageBoxA(GetForegroundWindow(),
            "Do you want to buy All Villagers are Exactly 18 for 1,000,000 tech "
            "points?\r\nPress OK to confirm, or Cancel.",
            "Origins Upgrades", MB_OKCANCEL | MB_ICONQUESTION | VV_MB_FRONT) == IDOK;
    }
    return 1;
}

/* Counted result (OFFICIAL wording), using the stored dry-run counts. */
__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult(
    int command,
    int granted,
    int already_running_skipped,
    int removed_running_dislike
) {
    char msg[512], line[128];
    (void)granted;
    (void)already_running_skipped;
    (void)removed_running_dislike;
    if (command == 6) {
        wsprintfA(msg, "Granted Running to %d %s.",
                  vw_granted, vv_villagers(vw_granted));
        if (vw_removed) {
            wsprintfA(line, "\r\n\r\nRemoved a Running dislike from %d %s.",
                      vw_removed, vv_villagers(vw_removed));
            lstrcatA(msg, line);
        }
        if (vw_already) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already like Running.",
                      vw_already, vv_villagers(vw_already));
            lstrcatA(msg, line);
        }
        if (vw_full) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already have 3 likes.",
                      vw_full, vv_villagers(vw_full));
            lstrcatA(msg, line);
        }
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    } else if (command == 7) {
        wsprintfA(msg, "Granted Full Mastery to %d %s.",
                  vw_granted, vv_villagers(vw_granted));
        if (vw_already) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already fully mastered.",
                      vw_already, vv_villagers(vw_already));
            lstrcatA(msg, line);
        }
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    } else if (command == 8) {
        wsprintfA(msg, "Set %d %s to Age 18.",
                  vw_granted, vv_villagers(vw_granted));
        if (vw_already) {
            wsprintfA(line, "\r\n\r\nSkipped %d %s: already exactly 18.",
                      vw_already, vv_villagers(vw_already));
            lstrcatA(msg, line);
        }
        MessageBoxA(GetForegroundWindow(), msg, "Origins Upgrades",
                    MB_OK | MB_ICONINFORMATION | VV_MB_FRONT);
    }
    return 0;
}

__declspec(dllexport) int __stdcall ShowOriginsVillageWideResult20(
    int command,
    unsigned int granted,
    unsigned int already_like,
    unsigned int full_like,
    unsigned int removed_dislike
) {
    char message[256];
    char line[96];
    if (command != 6) {
        return 0;
    }
    wsprintfA(message, "Granted Running to %u villagers", granted);
    wsprintfA(
        line,
        "\r\nSkipped over %u villagers. Reason: already likes running",
        already_like
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\nSkipped over %u villagers. Reason: all like slots are occupied",
        full_like
    );
    lstrcatA(message, line);
    wsprintfA(
        line,
        "\r\nRemoved running dislike from %u villagers",
        removed_dislike
    );
    lstrcatA(message, line);
    MessageBoxA(
        GetForegroundWindow(),
        message,
        "Origins Upgrades",
        MB_OK | MB_ICONINFORMATION | VV_MB_FRONT
    );
    return 0;
}
