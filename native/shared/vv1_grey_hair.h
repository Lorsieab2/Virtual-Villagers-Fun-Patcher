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
#ifndef RC_INVOKED
typedef int (__stdcall *vv1_grey_hair_wanted_fn)(const void *record);
#endif
/* The preview strips in the DLL's resources: BITMAP, 40 x 1300, column 5 of the grey sheets (the column
   the young strips in native/vv1_origins_icons/appearance are cut from), one 65-pixel row per head. */
#define VV1_GREY_HAIR_PREVIEW_MALE 101
#define VV1_GREY_HAIR_PREVIEW_FEMALE 102

#endif /* VV1_GREY_HAIR_H */
