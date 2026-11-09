/* skin_tones.h -- what "VVFP Skin Tones.dll" (native/vvfp_skin_tones; A New Home only, a DRAFT) offers the
   other A New Home companions.

   Each villager has a skin tone, kept in the patcher's own per-save file and following the villager (never
   in a record byte).  Tone 0 is the game's own art; tones 1..N are the owner's hand-made sheets in the
   game's Images\vvfp_skin\<tone>\ folder, under the game's own file names (docs/skin-tones-art-guide.md).
   A sheet that is not there (or not the stock size) is drawn from the game's own art, so nothing breaks
   before the art exists.

   Who asks what (each finds the DLL with GetModuleHandleA: "VVFP Startup.dll" loads it at game start, and
   GetModuleHandle never loads anything, so with the row off every answer is "the game's own"):
     * Grey Hair at 55 (native/vv1_grey_hair) draws every head: at its engine-entry swap it asks
       Vv1SkinToneSheetFor (the young sheet) or Vv1SkinToneGreySheetFor (its grey sheet).
     * Show Parents (native/vv1_parentage) asks Vv1SkinToneSheetFor for the child's body it draws again.
     * The Origins companion (native/vv1_origins_icons): Vv1Born hands every birth to Vv1SkinToneBorn, and
       Change Appearance reads and keeps the tone (Get / Set / SetMany / Original / Count / DrawPreview).
     * The parentage log's conception hook (native/parentage_export) hands each conception to
       Vv1SkinToneConceived, so a baby's tone comes from its parents' tones AS THEY WERE AT CONCEPTION. */
#ifndef VVFP_SKIN_TONES_H
#define VVFP_SKIN_TONES_H

#define VVFP_SKIN_TONES_DLL "VVFP Skin Tones.dll"

/* The most tones the DLL looks for (folders 1..15), and how many it uses when no tone folder is there yet
   (the design's eight presets, so the mechanics run -- and tones are given -- before the art exists). */
#define VVFP_SKIN_TONE_MAX 15
#define VVFP_SKIN_TONE_DEFAULT_COUNT 8

/* What a sheet is, for Vv1SkinToneDrawPreview. */
#define VVFP_SKIN_PART_HEAD 0
#define VVFP_SKIN_PART_BODY 1
#define VVFP_SKIN_PART_GREY_HEAD 2

/* int __stdcall Vv1SkinToneInstalled(void): 1 when the body and action draws follow the tone. */
#define VV1_SKIN_TONE_INSTALLED "Vv1SkinToneInstalled"
/* int __stdcall Vv1SkinToneCount(void): N, the tones besides 0 (the game's own art). */
#define VV1_SKIN_TONE_COUNT "Vv1SkinToneCount"
/* int __stdcall Vv1SkinToneGet(const void *record): the villager's tone 0..N; -1 while none is kept yet
   (drawn as 0) or the village is not known. */
#define VV1_SKIN_TONE_GET "Vv1SkinToneGet"
/* int __stdcall Vv1SkinToneOriginal(const void *record): the tone the villager was born with or first
   given (Reset to original); -1 when not known. */
#define VV1_SKIN_TONE_ORIGINAL "Vv1SkinToneOriginal"
/* int __stdcall Vv1SkinToneSet(const void *record, int tone): keep `tone` (0..N); 1 when the file says so. */
#define VV1_SKIN_TONE_SET "Vv1SkinToneSet"
/* int __stdcall Vv1SkinToneSetMany(const void *const *records, const int *tones, int count): all in ONE
   write; 1 when the file says so for every one, 0 when nothing changed. */
#define VV1_SKIN_TONE_SET_MANY "Vv1SkinToneSetMany"
/* int __stdcall Vv1SkinToneDrawPreview(HDC dc, const RECT *rc, int male, int part, int row, int tone): the
   Change Appearance preview cell of the owner's sheet, centred in rc on the picker's grey; 1 when drawn,
   0 when that tone's sheet is not there (the caller draws its own strip). */
#define VV1_SKIN_TONE_DRAW_PREVIEW "Vv1SkinToneDrawPreview"
/* void *__stdcall Vv1SkinToneSheetFor(const void *gameobj, const void *record, void *sprite): `sprite`, one
   of the game's six villager sheets in `gameobj` (the heads, bodies or actions of either sex), as that
   villager's tone draws it; `sprite` itself for tone 0, a missing sheet, or anything else. */
#define VV1_SKIN_TONE_SHEET_FOR "Vv1SkinToneSheetFor"
/* void *__stdcall Vv1SkinToneGreySheetFor(const void *record, int male, void *sprite): Grey Hair at 55's grey
   head sheet of that sex, `sprite`, as the villager's tone draws it. */
#define VV1_SKIN_TONE_GREY_SHEET_FOR "Vv1SkinToneGreySheetFor"
/* int __stdcall Vv1SkinToneConceived(const void *mother, const void *father): the parents' tones are kept
   against the mother for the birth to come (father NULL: not known). */
#define VV1_SKIN_TONE_CONCEIVED "Vv1SkinToneConceived"
/* int __stdcall Vv1SkinToneBorn(const void *child, const void *mother): the child's tone from its parents'. */
#define VV1_SKIN_TONE_BORN "Vv1SkinToneBorn"

#ifndef RC_INVOKED
typedef int (__stdcall *vv1_skin_tone_int_fn)(void);
typedef int (__stdcall *vv1_skin_tone_get_fn)(const void *record);
typedef int (__stdcall *vv1_skin_tone_set_fn)(const void *record, int tone);
typedef int (__stdcall *vv1_skin_tone_set_many_fn)(const void *const *records, const int *tones, int count);
typedef int (__stdcall *vv1_skin_tone_preview_fn)(HDC dc, const RECT *rc, int male, int part, int row, int tone);
typedef void *(__stdcall *vv1_skin_tone_sheet_for_fn)(const void *gameobj, const void *record, void *sprite);
typedef void *(__stdcall *vv1_skin_tone_grey_sheet_for_fn)(const void *record, int male, void *sprite);
typedef int (__stdcall *vv1_skin_tone_pair_fn)(const void *a, const void *b);

/* The exports Change Appearance uses, or all NULL when the DLL is not in the game or its draws are not in. */
typedef struct {
    int count;                                  /* N */
    vv1_skin_tone_get_fn get;
    vv1_skin_tone_get_fn original;
    vv1_skin_tone_set_fn set;
    vv1_skin_tone_set_many_fn set_many;
    vv1_skin_tone_preview_fn preview;
} vv1_skin_tone_api;

static __inline int vv1_skin_tone_find(vv1_skin_tone_api *api) {
    HMODULE dll = GetModuleHandleA(VVFP_SKIN_TONES_DLL);
    vv1_skin_tone_int_fn installed = dll != NULL
        ? (vv1_skin_tone_int_fn)GetProcAddress(dll, VV1_SKIN_TONE_INSTALLED) : NULL;
    vv1_skin_tone_int_fn count = dll != NULL ? (vv1_skin_tone_int_fn)GetProcAddress(dll, VV1_SKIN_TONE_COUNT) : NULL;
    api->count = 0;
    api->get = api->original = NULL;
    api->set = NULL;
    api->set_many = NULL;
    api->preview = NULL;
    if (installed == NULL || count == NULL || !installed()) {
        return 0;
    }
    api->get = (vv1_skin_tone_get_fn)GetProcAddress(dll, VV1_SKIN_TONE_GET);
    api->original = (vv1_skin_tone_get_fn)GetProcAddress(dll, VV1_SKIN_TONE_ORIGINAL);
    api->set = (vv1_skin_tone_set_fn)GetProcAddress(dll, VV1_SKIN_TONE_SET);
    api->set_many = (vv1_skin_tone_set_many_fn)GetProcAddress(dll, VV1_SKIN_TONE_SET_MANY);
    api->preview = (vv1_skin_tone_preview_fn)GetProcAddress(dll, VV1_SKIN_TONE_DRAW_PREVIEW);
    if (api->get == NULL || api->original == NULL || api->set == NULL || api->set_many == NULL
        || api->preview == NULL) {
        api->get = api->original = NULL;
        api->set = NULL;
        api->set_many = NULL;
        api->preview = NULL;
        return 0;
    }
    api->count = count();
    return 1;
}

/* A tone's name, as the window and the "Appearance changed" record write it: "Game's own" for 0, else
   "Tone <n>".  `out` holds at least 16 characters. */
static __inline void vv1_skin_tone_name(char *out, int tone) {
    if (tone <= 0) {
        lstrcpyA(out, "Game's own");
    } else {
        wsprintfA(out, "Tone %d", tone);
    }
}
#endif

#endif /* VVFP_SKIN_TONES_H */
