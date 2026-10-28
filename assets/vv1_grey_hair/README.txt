Grey Hair at 55 (A New Home) -- the art
=========================================

The patch draws an A New Home villager of 55 years or more from a grey version of its head.
Its two sheets are new files the game loads from its own Images folder; the game's own
male_heads.png and female_heads.png are never changed.

THE SHEETS THAT SHIP (this folder):

    vvfp_grey_male_heads.png      the men's grey heads   -> Images\vvfp_grey_male_heads.png
    vvfp_grey_female_heads.png    the women's grey heads -> Images\vvfp_grey_female_heads.png

EXPECTED LAYOUT -- exactly the stock sheets' (young_male_reference.png and
young_female_reference.png here ARE the stock male_heads.png / female_heads.png):

    * PNG with transparency (RGBA), 280 x 1300 pixels;
    * 7 columns x 20 rows of 40 x 65 cells;
    * the row is the head value, 0 to 19 (top to bottom); the columns are the same
      facings and walking frames as the stock sheet's, in the same order;
    * rows that are already grey or bald should look the same as the stock row
      (men 4, 15, 16 and 19 -- 19 is the Golden Child's; women 6; counted from 0),
      but whatever is in them is used. Row 19 is used like every other row: the
      Golden Child himself never grows old, but anyone else given head 19 shows
      it from 55.

A sheet of any other size is refused by the build (scripts/build_vv1_grey_hair_art.py) and,
in the game, by the DLL, which then keeps that sex's usual heads.

DROPPING IN THE FINAL SHEETS:

    1. Save them over vvfp_grey_male_heads.png and vvfp_grey_female_heads.png in this
       folder (same names, same layout).
    2. Run:   python scripts/build_vv1_grey_hair_feature.py
       It checks both sheets, rewrites the Change Appearance preview strips
       (native/vv1_grey_hair/preview), rebuilds "VVFP VV1 Grey Hair.dll" and pins the DLL
       and both sheets in data/vv1_grey_hair_feature.json.
    3. Run the tests: python -m pytest tests/test_vv1_grey_hair.py

THE PLACEHOLDER: PLACEHOLDER_grey_male.png and PLACEHOLDER_grey_female.png are a
machine-made mockup in the same layout, for building and testing only. Until the final
art is dropped in, the shipped sheets are copies of them, and
"python scripts/build_release.py" refuses to build a release
(_refuse_placeholder_art; tests/test_vv1_grey_hair.py checks the guard).
