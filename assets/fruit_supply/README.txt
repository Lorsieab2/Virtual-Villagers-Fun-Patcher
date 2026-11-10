Yellow Fruit Trees are No Longer Unlimited (The Tree of Life) -- the fruit trees' pictures
=========================================================================================

The two yellow fruit trees are painted on the island map itself (tile MapX0Y3.jpg). The map is
never changed: "VVFP VV4 Fruit Supply.dll" draws one picture over the trees, chosen by the fruit
left, in the village and on the Overview Map. The pictures are new files the game loads from its
own Images folder.

THE PICTURES (this folder):

    vvfp_fruit_tree_N.png   N fruits on each tree (N = 5, 4, 3, 2, 1, 0) -> Images\vvfp_fruit_tree_N.png

    All six are the owner's art (2026-11-10); the owner may still revise them. (The map's own
    trees have 3 fruits each.)

    The owner's stages (2026-11-10, the even split): picture 5 with 801 to 1,000 fruit, 4 with 601
    to 800, 3 with 401 to 600, 2 with 201 to 400, 1 with 1 to 200, 0 at 0. While the fruit is not known (no village yet, or its file not read yet) nothing is
    drawn: the map's own trees show. The numbers are ONE table, FS_STAGES in
    native\vvfp_vv4_fruit_supply\vvfp_vv4_fruit_supply.c.

EXPECTED LAYOUT:

    * PNG with transparency, 8-bit RGBA, exactly 256 x 256 pixels;
    * its top-left corner is drawn on world (0, 1664): the picture covers the section
      (0, 128)-(256, 384) of MapX0Y3.jpg, which yellow_fruit_trees_map_section.png is (the map's
      own full trees: the base to paint on);
    * see-through wherever the map should show; paint only what changes. The left tree's fruit
      is near (64-101, 74-134) of the picture, the right tree's near (145-182, 94-140).

A picture of any other size or kind is never drawn by the DLL (the map's own trees show), and the
row builder refuses it.

DROPPING IN NEW ART:

    1. Save it over vvfp_fruit_tree_0.png .. _5.png here (same names, same layout).
    2. Run:   python scripts/build_vv4_yellow_fruit_trees_limited_feature.py --no-build
       It checks each picture and pins it in data/vv4_yellow_fruit_trees_limited_feature.json.
    3. Preview: python scripts/vv4_fruit_tree_mockups.py <folder>
       writes the six stages laid over the game's own map tile.
    4. Run the tests: python -m pytest tests/test_vv4_yellow_fruit_trees_limited.py
