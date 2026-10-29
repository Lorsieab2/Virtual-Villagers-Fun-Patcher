/* vv1_grey_hair.h -- what "VVFP VV1 Grey Hair.dll" (native/vv1_grey_hair) offers another companion.

   The Origins companion's Change Appearance picker (native/vv1_origins_icons) shows a villager's head
   the way the village will draw it: when this DLL is in the game and says a villager is drawn grey
   (Vv1GreyHairWanted), the picker crops the head from this DLL's own preview strips instead of its
   young ones.  Without the DLL, or when it installed nothing, the picker is as before. */
#ifndef VV1_GREY_HAIR_H
#define VV1_GREY_HAIR_H

#define VV1_GREY_HAIR_DLL "VVFP VV1 Grey Hair.dll"
/* int __stdcall Vv1GreyHairWanted(const void *record): 1 when the village draws this villager (an A New
   Home villager record) with its grey head, else 0. */
#define VV1_GREY_HAIR_WANTED "Vv1GreyHairWanted"
/* int __stdcall Vv1GreyHairUsable(int male): 1 when the grey heads of that sex can be drawn (the splices
   are in and that sex's grey sheet is there and the right size) -- whatever the villager's age or look.
   The picker previews the head look being chosen with it (native/shared/head_look.h). */
#define VV1_GREY_HAIR_USABLE "Vv1GreyHairUsable"
/* void *__stdcall Vv1GreyHairSheetFor(const void *gameobj, const void *record, void *sprite): the sheet a
   head draw of that villager takes -- this DLL's grey sheet of the sex `sprite` is the young sheet of
   (gameobj+0x3DFF8 a man's, +0x3DFF4 a woman's) when the village draws that villager grey, else `sprite`
   itself.  Show Parents (native/vv1_parentage) asks it before it draws a child's head again over the
   parents with the Details portrait's own arguments, whose sprite is the young sheet. */
#define VV1_GREY_HAIR_SHEET_FOR "Vv1GreyHairSheetFor"
#ifndef RC_INVOKED
typedef int (__stdcall *vv1_grey_hair_wanted_fn)(const void *record);
typedef int (__stdcall *vv1_grey_hair_usable_fn)(int male);
typedef void *(__stdcall *vv1_grey_hair_sheet_for_fn)(const void *gameobj, const void *record, void *sprite);
#endif
/* The preview strips in the DLL's resources: BITMAP, 40 x 1300, column 5 of the grey sheets (the column
   the young strips in native/vv1_origins_icons/appearance are cut from), one 65-pixel row per head. */
#define VV1_GREY_HAIR_PREVIEW_MALE 101
#define VV1_GREY_HAIR_PREVIEW_FEMALE 102

#endif /* VV1_GREY_HAIR_H */
