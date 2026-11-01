"""Picture Studio's "Everything" tab, The Tree of Life (Virtual Villagers 4): every picture the game ships, and
the things it assembles from them, drawn the game's way (src/vv_pictures_assets.py has the framework;
docs/picture-studio-assets-vv4.md the addresses and what each proof covers).

THE GAME'S PICTURES.  The game builds every sprite from one table, 305 entries of 0x30 bytes at 0x4C07C8 (id,
name, columns, rows, suffix, sheets across, sheets down, ...), through its sprite registry (0x44CB80 by id):
  * columns 0 and rows 0: the whole picture (ldwImage, 0x40A840);
  * rows 0, columns n: an n-frame strip (ldwImageStrip, 0x401010 = 0x40AB10(name, n, 1)), the buttons' art;
  * rows r: a columns x rows grid of one picture (ldwImageGrid, 0x40AB10), or, with sheets across and down, a
    grid of sheets named name + across + down + suffix (0x40ABA0);
outside the table: the island map's 16 tiles "MapX<x>Y<y>.jpg" (0x46FCE0, whole), the splash pictures
(0x446690, whole), the puzzle screen's covers and button (0x445520, the same cuts as the table's), and the two
fonts, ldwarialbold.png and ldwBurweed27.png (0x4027A0, a glyph table each).  TABLE below is the exe's table;
tests/test_assets_vv4.py proves it, the cut of every cell, and every composed asset against the stock exe.

COMPOSED ASSETS (each plan is the game's own blits, in order; see the docs for each proof):
  * Buttons (the engine's button draw 0x401200, from 0x401540): state 0, 1 and 2 are the strip's frames 0-2.
  * The Tech screen (0x43E640): tech_bg.jpg, the colour carving's slices by how many of five tasks are done
    (0x41F570), and each technology's bar, its jpg's frame k at (3 + 132 k, the row's y) for each level learned.
  * Meters: the Villager Details bars (0x44D070: 4-pixel slices, value x 256 / 100 / 4 of them) and the loading
    bar (0x44DB10 kind 3: LoadColor.png every 8 pixels, the bamboo frame drawn after each).
  * Screens: the backgrounds and fixed art each screen's draw places with constant arguments.
  * The island map (0x46FCE0 / 0x46FE10): 16 tiles of 512 x 512, tile (x, y) at (512 x, 512 y).
  * Fonts: every glyph of both fonts, cut as 0x4027A0 cuts it.
  * The patcher's art: the Origins mask atlases (vv_pictures_vv4), the Golden Mushroom (native/vvfp_golden_mushroom:
    the collectables sheet's frame 50 replaced by golden_mushroom.png, 7 pixels to the right).
Everything else is listed cell by cell as the game's constructor cuts it, in the sheet's order, with a note
that how the game plays or places those cells is not proven here.
"""
from __future__ import annotations

from pathlib import Path

import vv_picture_image as pi
import vv_pictures_assets as va

GAME = 4
ROOT = Path(__file__).resolve().parents[1]
TABLE_AT = 0x4C07C8
TABLE_STRIDE = 0x30

# The exe's sprite table (0x4C07C8): (id, name, columns, rows, suffix, sheets across, sheets down).
TABLE = (
    (0, 'No Graphic', 0, 0, '', 0, 0),
    (1, 'hand_open.png', 0, 0, '', 0, 0),
    (2, 'hand.png', 0, 0, '', 0, 0),
    (3, 'leaf_grid.png', 1, 2, '', 0, 0),
    (4, 'light-beams.png', 0, 0, '', 0, 0),
    (5, 'cloud_puff.png', 0, 0, '', 0, 0),
    (6, 'lei_left.png', 0, 0, '', 0, 0),
    (7, 'lei_center.png', 0, 0, '', 0, 0),
    (8, 'lei_right.png', 0, 0, '', 0, 0),
    (9, 'lei_rope_repaired.png', 0, 0, '', 0, 0),
    (10, 'lei_rope_motheaten.png', 0, 0, '', 0, 0),
    (11, 'collecting_mausoleum_ingame.png', 4, 3, '', 0, 0),
    (12, 'collecting_flutetops_ingame.png', 4, 3, '', 0, 0),
    (13, 'collectables_small_decal.png', 12, 2, '', 0, 0),
    (14, 'undertoe.png', 14, 1, '', 0, 0),
    (15, 'break.png', 2, 1, '', 0, 0),
    (16, 'moss1.png', 1, 1, '', 0, 0),
    (17, 'mossy_decal_large.png', 1, 1, '', 0, 0),
    (18, 'alchemy_pot_water.png', 1, 1, '', 0, 0),
    (19, 'focusWindowMask.png', 1, 1, '', 0, 0),
    (20, 'focus_window_lens.png', 0, 0, '', 0, 0),
    (21, 'cloth_bolt.png', 0, 0, '', 0, 0),
    (22, 'suds.png', 1, 1, '', 0, 0),
    (23, 'cloth_paste.png', 0, 0, '', 0, 0),
    (24, 'cutting_tool.png', 0, 0, '', 0, 0),
    (25, 'ruinsRubble.png', 3, 1, '', 0, 0),
    (70, 'blackberry.png', 1, 1, '', 0, 0),
    (40, 'bananaleafCover.png', 1, 1, '', 0, 0),
    (41, 'hotRockBed.png', 1, 1, '', 0, 0),
    (72, 'soap.png', 1, 1, '', 0, 0),
    (47, 'btn_done.png', 3, 0, '', 0, 0),
    (42, 'btn_CollectionsDone.png', 3, 0, '', 0, 0),
    (73, 'fishstrip1.png', 9, 1, '', 0, 0),
    (74, 'fishstrip2.png', 9, 1, '', 0, 0),
    (75, 'crabstrip1.png', 11, 1, '', 0, 0),
    (76, 'crabstrip2.png', 5, 1, '', 0, 0),
    (38, 'fishpile1.png', 1, 1, '', 0, 0),
    (39, 'GoldFishPile.png', 1, 1, '', 0, 0),
    (77, 'stalks_green.png', 1, 1, '', 0, 0),
    (78, 'hole-closed.png', 1, 1, '', 0, 0),
    (79, 'lowtide.png', 1, 1, '', 0, 0),
    (81, 'tree-state-00.png', 1, 1, '', 0, 0),
    (82, 'tree-state-01.png', 1, 1, '', 0, 0),
    (83, 'tree-state-02.png', 1, 1, '', 0, 0),
    (84, 'tree-state-03.png', 1, 1, '', 0, 0),
    (85, 'tree-state-04.png', 1, 1, '', 0, 0),
    (86, 'tree-state-05.png', 1, 1, '', 0, 0),
    (87, 'tree-sickbranch.png', 1, 1, '', 0, 0),
    (88, 'tree-newbranch.png', 1, 1, '', 0, 0),
    (89, 'blacktreesap.png', 1, 1, '', 0, 0),
    (90, 'Tech_colorcarving_slice1.png', 1, 1, '', 0, 0),
    (91, 'Tech_colorcarving_slice2.png', 1, 1, '', 0, 0),
    (92, 'Tech_colorcarving_slice3.png', 1, 1, '', 0, 0),
    (93, 'Tech_colorcarving_slice4.png', 1, 1, '', 0, 0),
    (94, 'Tech_colorcarving_slice5.png', 1, 1, '', 0, 0),
    (95, 'Tech_colorcarving_slice6.png', 1, 1, '', 0, 0),
    (104, 'northPierHoleEast.png', 1, 1, '', 0, 0),
    (105, 'southPierHoleNorthWest.png', 1, 1, '', 0, 0),
    (106, 'southPierHoleEast.png', 1, 1, '', 0, 0),
    (107, 'southPierHoleSouthWest.png', 1, 1, '', 0, 0),
    (108, 'northPierHoleMidSouth.png', 1, 1, '', 0, 0),
    (109, 'northPierHoleMidNorth.png', 1, 1, '', 0, 0),
    (110, 'northPierHoleSouthEast.png', 1, 1, '', 0, 0),
    (111, 'northPierHoleWest.png', 1, 1, '', 0, 0),
    (112, 'southPierHoleSouthEast.png', 1, 1, '', 0, 0),
    (113, 'southPierHoleNorthEast.png', 1, 1, '', 0, 0),
    (80, 'AlchemyLab1.png', 1, 1, '', 0, 0),
    (26, 'mausoleum_ui_bg.jpg', 0, 0, '', 0, 0),
    (27, 'mausoleum_ui_top.png', 0, 0, '', 0, 0),
    (28, 'mausoleum_ui_btm.png', 0, 0, '', 0, 0),
    (29, 'mausoleum_row.png', 0, 0, '', 0, 0),
    (30, 'mausoleum_knob_top.png', 0, 0, '', 0, 0),
    (31, 'mausoleum_knob_mid.png', 0, 0, '', 0, 0),
    (32, 'mausoleum_knob_btm.png', 0, 0, '', 0, 0),
    (33, 'mausoleum_scroll_track.png', 0, 0, '', 0, 0),
    (34, 'btn_arrow_up.png', 3, 1, '', 0, 0),
    (35, 'btn_arrow_dwn.png', 3, 1, '', 0, 0),
    (36, 'mausoleum_tint.png', 0, 0, '', 0, 0),
    (37, 'graves.png', 0, 0, '', 0, 0),
    (69, 'selectvillagers_UI_BG.jpg', 0, 0, '', 0, 0),
    (49, 'stream_section-2-reduced.png', 1, 1, '', 0, 0),
    (50, 'stream_section-2-strong-hole.png', 1, 1, '', 0, 0),
    (51, 'stream_section-2-strong.png', 1, 1, '', 0, 0),
    (52, 'stream_section-3-strong.png', 1, 1, '', 0, 0),
    (53, 'stream_section-3-weeping-walls.png', 1, 1, '', 0, 0),
    (54, 'stream_section-3-reduced.png', 1, 1, '', 0, 0),
    (55, 'stream_section-4-strong.png', 1, 1, '', 0, 0),
    (56, 'stream_section-4.-stagnant.png', 1, 1, '', 0, 0),
    (57, 'stream_section-4-reduced.png', 1, 1, '', 0, 0),
    (58, 'stream_section-1-debris.png', 1, 1, '', 0, 0),
    (59, 'stream_section-1-waterfall.png', 1, 1, '', 0, 0),
    (60, 'stream_section-1.png', 1, 1, '', 0, 0),
    (61, 'special-cork-rock.png', 1, 1, '', 0, 0),
    (62, 'special-cork-rock-in-ground.png', 1, 1, '', 0, 0),
    (63, 'upperNetInProgress.png', 1, 1, '', 0, 0),
    (64, 'lowerNetInProgress.png', 1, 1, '', 0, 0),
    (65, 'upperNetComplete.png', 1, 1, '', 0, 0),
    (66, 'lowerNetComplete.png', 1, 1, '', 0, 0),
    (67, 'boardTopPerspective.png', 1, 1, '', 0, 0),
    (68, 'boardBottomPerspective.png', 1, 1, '', 0, 0),
    (114, 'arrowup.png', 3, 1, '', 0, 0),
    (115, 'arrowdown.png', 3, 1, '', 0, 0),
    (116, 'btn_orange.png', 3, 0, '', 0, 0),
    (117, 'trophies_UI_BG.jpg', 0, 0, '', 0, 0),
    (118, 'trophy_scrollknob_top.png', 0, 0, '', 0, 0),
    (119, 'trophy_scrollknob_mid.png', 0, 0, '', 0, 0),
    (120, 'trophy_scrollknob_btm.png', 0, 0, '', 0, 0),
    (121, 'trophy_ui_top.png', 0, 0, '', 0, 0),
    (122, 'trophy_ui_btm.png', 0, 0, '', 0, 0),
    (123, 'trophy_star.png', 0, 0, '', 0, 0),
    (124, 'trophy_row.png', 0, 0, '', 0, 0),
    (125, 'trophybar_back.png', 0, 0, '', 0, 0),
    (126, 'trophybar_front.png', 0, 0, '', 0, 0),
    (127, 'btn_trophyarrow_up.png', 3, 1, '', 0, 0),
    (128, 'btn_trophyarrow_down.png', 3, 1, '', 0, 0),
    (129, 'butterflygreen.png', 4, 5, '', 0, 0),
    (71, 'branchWrap.png', 1, 1, '', 0, 0),
    (130, 'main_wide_button2.png', 3, 0, '', 0, 0),
    (131, 'ultra_wide_button.png', 3, 0, '', 0, 0),
    (132, 'MS_Button_01.png', 3, 0, '', 0, 0),
    (133, 'MS_Button_02.png', 3, 0, '', 0, 0),
    (134, 'MS_Button_03.png', 3, 0, '', 0, 0),
    (135, 'MS_Button_04.png', 3, 0, '', 0, 0),
    (136, 'btn_detail.png', 3, 0, '', 0, 0),
    (137, 'btn_arrowl.png', 3, 0, '', 0, 0),
    (138, 'btn_arrowr.png', 3, 0, '', 0, 0),
    (43, 'btn_arrow_lt.png', 3, 0, '', 0, 0),
    (44, 'btn_arrow_rt.png', 3, 0, '', 0, 0),
    (45, 'btn_help_arrowl.png', 3, 0, '', 0, 0),
    (46, 'btn_help_arrowr.png', 3, 0, '', 0, 0),
    (48, 'btn_creditsHelp.png', 3, 0, '', 0, 0),
    (139, 'btn_collections.png', 3, 0, '', 0, 0),
    (140, 'btn_trophies.png', 3, 0, '', 0, 0),
    (141, 'btn_puzzle.png', 3, 0, '', 0, 0),
    (142, 'btn_map.png', 3, 0, '', 0, 0),
    (143, 'btn_tech.png', 3, 0, '', 0, 0),
    (144, 'btn_menu.png', 3, 0, '', 0, 0),
    (145, 'Boxshot_CTButton.png', 3, 0, '', 0, 0),
    (146, 'Boxshot_HelpButton.png', 3, 0, '', 0, 0),
    (147, 'Boxshot_OptsButton.png', 3, 0, '', 0, 0),
    (148, 'Boxshot_PlayButton.png', 3, 0, '', 0, 0),
    (149, 'Boxshot_QuitButton.png', 3, 0, '', 0, 0),
    (150, 'Boxshot_SOButton.png', 3, 0, '', 0, 0),
    (151, 'popup_button1.png', 3, 0, '', 0, 0),
    (152, 'OrangeDlgTileGrid.png', 9, 1, '', 0, 0),
    (153, 'GreenDlgTileGrid.png', 9, 1, '', 0, 0),
    (154, 'leftarrow.png', 3, 0, '', 0, 0),
    (155, 'rightarrow.png', 3, 0, '', 0, 0),
    (156, 'radiobuttonstrip.png', 2, 0, '', 0, 0),
    (157, 'radioblank.png', 0, 0, '', 0, 0),
    (158, 'radioselected.png', 0, 0, '', 0, 0),
    (159, 'CheckboxStrip.png', 2, 0, '', 0, 0),
    (160, 'checkmark.png', 0, 0, '', 0, 0),
    (161, 'WideSlider2.png', 0, 0, '', 0, 0),
    (162, 'sliderhandle.png', 0, 0, '', 0, 0),
    (163, 'UpArrowButton.png', 3, 0, '', 0, 0),
    (164, 'DownArrowButton.png', 3, 0, '', 0, 0),
    (165, 'VerticalScrollTrack.png', 0, 0, '', 0, 0),
    (166, 'VerticalScrollKnob.png', 0, 0, '', 0, 0),
    (167, 'BambooMeterFrame1.png', 0, 0, '', 0, 0),
    (168, 'StatusBarSliceB.png', 0, 0, '', 0, 0),
    (169, 'StatusBarSliceR.png', 0, 0, '', 0, 0),
    (170, 'healthBarbulb.png', 0, 0, '', 0, 0),
    (171, 'LoadColor.png', 0, 0, '', 0, 0),
    (172, 'focus_circle.png', 0, 0, '', 0, 0),
    (173, 'overview_bg.jpg', 0, 0, '', 0, 0),
    (174, 'map_cloud01.png', 0, 0, '', 0, 0),
    (175, 'cloud variations1.png', 0, 0, '', 0, 0),
    (176, 'cloud variations2.png', 0, 0, '', 0, 0),
    (177, 'cloud variations3.png', 0, 0, '', 0, 0),
    (178, 'loading.jpg', 0, 0, '', 0, 0),
    (179, 'ldwLogo.png', 0, 0, '', 0, 0),
    (180, 'logo1.png', 0, 0, '', 0, 0),
    (181, 'small_logo.png', 1, 1, '', 0, 0),
    (182, 'image1_page1.jpg', 1, 1, '', 0, 0),
    (183, 'image1_page2.jpg', 1, 1, '', 0, 0),
    (184, 'image1_page3.jpg', 1, 1, '', 0, 0),
    (185, 'image1_page4.jpg', 1, 1, '', 0, 0),
    (186, 'image1_page5.jpg', 1, 1, '', 0, 0),
    (187, 'image1_page5_hands.png', 1, 1, '', 0, 0),
    (188, 'image1_page5mask.jpg', 1, 1, '', 0, 0),
    (189, 'midgame_page1.jpg', 1, 1, '', 0, 0),
    (190, 'midgame_page2.jpg', 1, 1, '', 0, 0),
    (191, 'midgame_page3.jpg', 1, 1, '', 0, 0),
    (192, 'midgame_page4.jpg', 1, 1, '', 0, 0),
    (193, 'midgame_page5.jpg', 1, 1, '', 0, 0),
    (194, 'story3_page1.jpg', 1, 1, '', 0, 0),
    (195, 'story3_page1mask.png', 1, 1, '', 0, 0),
    (196, 'story3_page2.jpg', 1, 1, '', 0, 0),
    (197, 'story3_page3.jpg', 1, 1, '', 0, 0),
    (198, 'story3_page3_Peep1.png', 1, 1, '', 0, 0),
    (199, 'story3_page3_Peep2.png', 1, 1, '', 0, 0),
    (200, 'story3_page3_Peep3.png', 1, 1, '', 0, 0),
    (201, 'story3_page3_Peep4.png', 1, 1, '', 0, 0),
    (202, 'story3_page3_Leaf.png', 5, 1, '', 0, 0),
    (203, 'story3_page4.jpg', 1, 1, '', 0, 0),
    (204, 'story3_page4_Leaf.png', 5, 1, '', 0, 0),
    (205, 'story3_page5.jpg', 1, 1, '', 0, 0),
    (206, 'story3_page5_hand.png', 1, 1, '', 0, 0),
    (207, 'story3_page5_mask.png', 1, 1, '', 0, 0),
    (208, 'main_UI_BG.png', 0, 0, '', 0, 0),
    (209, 'puzzles_bg.jpg', 0, 0, '', 0, 0),
    (210, 'help1.jpg', 0, 0, '', 0, 0),
    (211, 'help2.jpg', 0, 0, '', 0, 0),
    (212, 'help3.jpg', 0, 0, '', 0, 0),
    (213, 'help4.jpg', 0, 0, '', 0, 0),
    (214, 'credits.jpg', 0, 0, '', 0, 0),
    (215, 'vv2_boxshot.jpg', 0, 0, '', 0, 0),
    (216, 'empty1.png', 3, 0, '', 0, 0),
    (217, 'arrowglow.png', 0, 0, '', 0, 0),
    (218, 'arrowglowdown.png', 0, 0, '', 0, 0),
    (219, 'arrowleftglow.png', 0, 0, '', 0, 0),
    (220, 'arrowrightglow.png', 0, 0, '', 0, 0),
    (221, 'puzzle_covers.png', 4, 4, '', 0, 0),
    (222, 'collections_UI_BG.jpg', 0, 0, '', 0, 0),
    (223, 'collecting_fishscales_collectionscreen.png', 4, 3, '', 0, 0),
    (224, 'collecting_lab_collectionscreen.png', 4, 3, '', 0, 0),
    (225, 'collecting_mausoleum_collectionscreen.png', 4, 3, '', 0, 0),
    (226, 'collecting_flutetops_collectionscreen.png', 4, 3, '', 0, 0),
    (227, 'tech_bg.jpg', 0, 0, '', 0, 0),
    (228, 'tech_science.jpg', 3, 1, '', 0, 0),
    (229, 'tech_medicine.jpg', 3, 1, '', 0, 0),
    (230, 'tech_learning.jpg', 3, 1, '', 0, 0),
    (231, 'tech_restoration.jpg', 3, 1, '', 0, 0),
    (232, 'tech_foodmastery.jpg', 3, 1, '', 0, 0),
    (233, 'tech_dendrology.jpg', 3, 1, '', 0, 0),
    (234, 'tech_buy_btn.png', 3, 1, '', 0, 0),
    (235, 'tech_info_btn.png', 3, 1, '', 0, 0),
    (236, 'VD_BG_2.jpg', 0, 0, '', 0, 0),
    (237, 'map_foodbin.png', 5, 1, '', 0, 0),
    (238, 'lakeStrip.png', 3, 10, '', 0, 0),
    (96, 'waterfall1Strip.png', 6, 5, '', 0, 0),
    (97, 'waterfall2Strip.png', 7, 5, '', 0, 0),
    (98, 'waterfall3Strip.png', 11, 3, '', 0, 0),
    (99, 'waterfall4Strip.png', 3, 10, '', 0, 0),
    (100, 'waterfalls567Strip.png', 6, 5, '', 0, 0),
    (101, 'waterfall8Strip.png', 8, 4, '', 0, 0),
    (102, 'waterfall9Strip.png', 10, 3, '', 0, 0),
    (103, 'lakeReducedStrip.png', 3, 10, '', 0, 0),
    (239, 'waves_proto.png', 10, 1, '', 0, 0),
    (240, 'yellow_sparkle.png', 10, 1, '', 0, 0),
    (241, 'sparklestrip2.png', 10, 1, '', 0, 0),
    (242, 'sparklestrip.png', 10, 1, '', 0, 0),
    (243, 'dust2.png', 9, 1, '', 0, 0),
    (244, 'algae.png', 4, 4, '', 0, 0),
    (245, 'rainbow.png', 10, 1, '', 0, 0),
    (246, 'bubble.png', 10, 1, '', 0, 0),
    (247, 'candlestrip.png', 9, 1, '', 0, 0),
    (248, 'frogstrip1.png', 13, 1, '', 0, 0),
    (249, 'frogstrip2.png', 13, 1, '', 0, 0),
    (250, 'firestrip.png', 4, 2, '', 0, 0),
    (251, 'petalstrip.png', 12, 3, '', 0, 0),
    (252, 'leafstrip.png', 9, 5, '', 0, 0),
    (253, 'waterfallanimA.png', 8, 4, '', 0, 0),
    (254, 'waterfallanimb.png', 4, 2, '', 0, 0),
    (255, 'foam.png', 4, 2, '', 0, 0),
    (256, 'carrying.png', 13, 6, '', 0, 0),
    (257, 'spray.png', 12, 1, '', 0, 0),
    (258, 'sharp_sparkle.png', 10, 1, '', 0, 0),
    (259, 'blurry_sparkle.png', 10, 1, '', 0, 0),
    (260, 'collectables_small.png', 6, 9, '', 0, 0),
    (261, 'footprints.png', 15, 1, '', 0, 0),
    (262, 'raindrops.png', 3, 1, '', 0, 0),
    (263, 'smokestriplight.png', 12, 1, '', 0, 0),
    (264, 'smokestripdark.png', 12, 1, '', 0, 0),
    (265, 'reefFish1.png', 5, 6, '', 0, 0),
    (266, 'reefFish2.png', 5, 8, '', 0, 0),
    (267, 'reefFish3.png', 5, 10, '', 0, 0),
    (268, 'beestriplarge_final2.png', 14, 2, '', 0, 0),
    (269, 'fishflop.png', 15, 1, '', 0, 0),
    (270, 'bubblestrip.png', 9, 1, '', 0, 0),
    (271, 'amppuddle.png', 1, 1, '', 0, 0),
    (272, 'woodpile.png', 1, 1, '', 0, 0),
    (273, 'scaffolding.png', 1, 1, '', 0, 0),
    (274, 'graves.png', 4, 1, '', 0, 0),
    (275, 'firestrip.png', 4, 2, '', 0, 0),
    (276, 'female_heads', 16, 30, '.png', 2, 1),
    (277, 'female_bodies', 32, 30, '.png', 2, 3),
    (278, 'female_actions', 17, 30, '.png', 1, 3),
    (279, 'male_heads', 16, 30, '.png', 2, 1),
    (280, 'male_bodies', 32, 30, '.png', 2, 3),
    (281, 'male_actions', 17, 30, '.png', 1, 3),
    (282, 'bigheads', 12, 30, '.png', 2, 1),
    (283, 'bigbodies.png', 2, 30, '', 0, 0),
    (284, 'peep_shadow1.png', 0, 0, '', 0, 0),
    (285, 'skelly.png', 4, 1, '', 0, 0),
    (286, 'ripple.png', 4, 1, '', 0, 0),
    (287, 'sunbeam.png', 0, 0, '', 0, 0),
    (288, 'map_fog.png', 0, 0, '', 0, 0),
    (289, 'sciencelab.png', 2, 1, '', 0, 0),
    (290, 'AlchemyLab0.png', 0, 0, '', 0, 0),
    (291, 'AlchemyLab1.png', 0, 0, '', 0, 0),
    (292, 'AlchemyLab2.png', 0, 0, '', 0, 0),
    (293, 'AlchemyLab3.png', 0, 0, '', 0, 0),
    (294, 'AlchemyLab4.png', 0, 0, '', 0, 0),
    (295, 'hut_states.png', 2, 2, '', 0, 0),
    (296, 'clothinghut_states.png', 2, 3, '', 0, 0),
    (297, 'loveshack_states.png', 2, 3, '', 0, 0),
    (298, 'nurseryhut_states.png', 2, 3, '', 0, 0),
    (299, 'hospital_states.png', 2, 3, '', 0, 0),
    (300, 'bird.png', 12, 1, '', 0, 0),
    (301, 'bird_shadow.png', 1, 1, '', 0, 0),
    (302, 'dragonflies.png', 6, 4, '', 0, 0),
    (303, 'hummingbirdstrip.png', 4, 2, '', 0, 0),
    (304, 'rosterbush.png', 4, 2, '', 0, 0),
)

# Pictures the exe builds outside its table: (name, what builds it).
MAP_TILE = "MapX{x}Y{y}.jpg"          # sprintf("%sX%01dY%01d.jpg", "Map", x, y) at 0x46FD46
OTHER_WHOLE = (
    ("SPLASH_BG.JPG", "0x4466A4 (ldwImage)"), ("SPLASH1_BG.JPG", "0x4466EB (ldwImage)"),
    ("SPLASH2_BG.JPG", "0x446732 (ldwImage)"), ("SPLASH3_BG.JPG", "0x446779 (ldwImage)"),
    ("menu_logo.png", "0x42079B (ldwImage)"), ("loading_logo.png", "0x4207E0 (ldwImage)"),
    ("puzzles_bg.jpg", "0x4458FF (ldwImage)"),
)
OTHER_GRID = (("puzzle_covers.png", 4, 4, "0x445934 (ldwImageGrid)"),)
# The pictures in the game's Images folder whose names the exe never builds (listed "(unused)" under Source
# sheets, cut at their own gaps; tests/test_assets_vv4.py checks this list against the game's folder).
UNUSED_FILES = ("break1.png", "btn_check.png", "buy_button.png", "graveflowers.png", "main_no-comm.png",
                "mausoleum_urn.png", "mossy_decal_small.png", "verticalslidertrack.png")
# Table pictures the shipped game does not have (the game would show its "Missing Graphic" log line): never
# listed, as there is nothing to show.
MISSING_FILES = ("small_logo.png", "story3_page1mask.png", "SPLASH1_BG.JPG", "SPLASH2_BG.JPG", "SPLASH3_BG.JPG",
                 "menu_logo.png", "loading_logo.png")

# The fonts (0x41D840 / 0x41D8B0 -> 0x4023B0 -> 0x4027A0): the glyph table (character, left, top, right,
# bottom), five ints a glyph, ended by a 0 character; the picture is the name + ".png".
ARIAL = (  # 190 glyphs at 0x4ba140
    33, 0, 0, 5, 20, 34, 5, 0, 14, 20, 35, 14, 0, 24, 20, 36, 24, 0, 34, 20,
    37, 34, 0, 51, 20, 38, 51, 0, 64, 20, 39, 64, 0, 68, 20, 40, 68, 0, 74, 20,
    41, 74, 0, 80, 20, 42, 80, 0, 87, 20, 43, 87, 0, 98, 20, 44, 98, 0, 103, 20,
    45, 103, 0, 109, 20, 46, 109, 0, 114, 20, 47, 114, 0, 119, 20, 48, 119, 0, 129, 20,
    49, 129, 0, 139, 20, 50, 139, 0, 149, 20, 51, 149, 0, 159, 20, 52, 159, 0, 169, 20,
    53, 169, 0, 179, 20, 54, 179, 0, 189, 20, 55, 189, 0, 199, 20, 56, 199, 0, 209, 20,
    57, 209, 0, 219, 20, 58, 219, 0, 226, 20, 59, 226, 0, 233, 20, 60, 233, 0, 244, 20,
    61, 244, 0, 255, 20, 62, 255, 0, 266, 20, 63, 266, 0, 277, 20, 64, 277, 0, 295, 20,
    65, 295, 0, 308, 20, 66, 308, 0, 321, 20, 67, 321, 0, 334, 20, 68, 334, 0, 347, 20,
    69, 347, 0, 359, 20, 70, 359, 0, 370, 20, 71, 370, 0, 384, 20, 72, 384, 0, 397, 20,
    73, 397, 0, 402, 20, 74, 402, 0, 412, 20, 75, 412, 0, 425, 20, 76, 425, 0, 436, 20,
    77, 436, 0, 451, 20, 78, 451, 0, 464, 20, 79, 464, 0, 478, 20, 80, 478, 0, 490, 20,
    81, 490, 0, 504, 20, 82, 504, 0, 517, 20, 83, 517, 0, 529, 20, 84, 529, 0, 540, 20,
    85, 540, 0, 553, 20, 86, 553, 0, 566, 20, 87, 566, 0, 583, 20, 88, 583, 0, 595, 20,
    89, 595, 0, 608, 20, 90, 608, 0, 618, 20, 91, 618, 0, 619, 20, 92, 619, 0, 624, 20,
    93, 624, 0, 630, 20, 94, 630, 0, 641, 20, 95, 641, 0, 651, 20, 96, 651, 0, 657, 20,
    97, 657, 0, 667, 20, 98, 667, 0, 678, 20, 99, 678, 0, 688, 20, 100, 688, 0, 699, 20,
    101, 699, 0, 710, 20, 102, 710, 0, 716, 20, 103, 716, 0, 727, 20, 104, 727, 0, 738, 20,
    105, 738, 0, 743, 20, 106, 743, 0, 748, 20, 107, 748, 0, 758, 20, 108, 758, 0, 763, 20,
    109, 763, 0, 780, 20, 110, 780, 0, 791, 20, 111, 791, 0, 802, 20, 112, 802, 0, 813, 20,
    113, 813, 0, 824, 20, 114, 824, 0, 831, 20, 115, 831, 0, 841, 20, 116, 841, 0, 847, 20,
    117, 847, 0, 858, 20, 118, 858, 0, 869, 20, 119, 869, 0, 884, 20, 120, 884, 0, 895, 20,
    121, 895, 0, 906, 20, 122, 906, 0, 915, 20, 123, 915, 0, 919, 20, 124, 919, 0, 923, 20,
    125, 923, 0, 930, 20, 126, 930, 0, 941, 20, 32, 941, 0, 946, 20, -95, 955, 0, 960, 20,
    -94, 960, 0, 970, 20, -93, 970, 0, 980, 20, -92, 980, 0, 990, 20, -91, 990, 0, 1000, 20,
    -90, 1000, 0, 1004, 20, -89, 1004, 0, 1014, 20, -88, 1014, 0, 1020, 20, -87, 1020, 0, 1033, 20,
    -86, 1033, 0, 1040, 20, -85, 1040, 0, 1050, 20, -84, 1050, 0, 1061, 20, -83, 1061, 0, 1067, 20,
    -82, 1067, 0, 1080, 20, -81, 1080, 0, 1090, 20, -80, 1090, 0, 1097, 20, -79, 1097, 0, 1107, 20,
    -78, 1107, 0, 1113, 20, -77, 1113, 0, 1119, 20, -76, 1119, 0, 1125, 20, -75, 1125, 0, 1135, 20,
    -74, 1135, 0, 1145, 20, -73, 1145, 0, 1150, 20, -72, 1150, 0, 1156, 20, -71, 1156, 0, 1162, 20,
    -70, 1162, 0, 1169, 20, -69, 1169, 0, 1179, 20, -68, 1179, 0, 1194, 20, -67, 1194, 0, 1209, 20,
    -66, 1209, 0, 1224, 20, -65, 1224, 0, 1235, 20, -64, 1235, 0, 1248, 20, -63, 1248, 0, 1261, 20,
    -62, 1261, 0, 1274, 20, -61, 1274, 0, 1287, 20, -60, 1287, 0, 1300, 20, -59, 1300, 0, 1313, 20,
    -58, 1313, 0, 1331, 20, -57, 1331, 0, 1344, 20, -56, 1344, 0, 1356, 20, -55, 1356, 0, 1368, 20,
    -54, 1368, 0, 1380, 20, -53, 1380, 0, 1392, 20, -52, 1392, 0, 1397, 20, -51, 1397, 0, 1402, 20,
    -50, 1402, 0, 1407, 20, -49, 1407, 0, 1412, 20, -48, 1412, 0, 1425, 20, -47, 1425, 0, 1438, 20,
    -46, 1438, 0, 1452, 20, -45, 1452, 0, 1466, 20, -44, 1466, 0, 1480, 20, -43, 1480, 0, 1494, 20,
    -42, 1494, 0, 1508, 20, -41, 1508, 0, 1519, 20, -40, 1519, 0, 1533, 20, -39, 1533, 0, 1546, 20,
    -38, 1546, 0, 1559, 20, -37, 1559, 0, 1572, 20, -36, 1572, 0, 1585, 20, -35, 1585, 0, 1597, 20,
    -34, 1597, 0, 1609, 20, -33, 1609, 0, 1621, 20, -32, 1621, 0, 1631, 20, -31, 1631, 0, 1641, 20,
    -30, 1641, 0, 1651, 20, -29, 1651, 0, 1661, 20, -28, 1661, 0, 1671, 20, -27, 1671, 0, 1681, 20,
    -26, 1681, 0, 1697, 20, -25, 1697, 0, 1707, 20, -24, 1707, 0, 1717, 20, -23, 1717, 0, 1727, 20,
    -22, 1727, 0, 1737, 20, -21, 1737, 0, 1747, 20, -20, 1747, 0, 1752, 20, -19, 1752, 0, 1757, 20,
    -18, 1757, 0, 1762, 20, -17, 1762, 0, 1767, 20, -16, 1767, 0, 1778, 20, -15, 1778, 0, 1789, 20,
    -14, 1789, 0, 1800, 20, -13, 1800, 0, 1811, 20, -12, 1811, 0, 1822, 20, -11, 1822, 0, 1833, 20,
    -10, 1833, 0, 1844, 20, -9, 1844, 0, 1854, 20, -8, 1854, 0, 1865, 20, -7, 1865, 0, 1876, 20,
    -6, 1876, 0, 1887, 20, -5, 1887, 0, 1898, 20, -4, 1898, 0, 1909, 20, -3, 1909, 0, 1919, 20,
    -2, 1919, 0, 1930, 20, -1, 1930, 0, 1940, 20,
)
BURWEED = (  # 190 glyphs at 0x4bb068
    33, 0, 0, 7, 27, 34, 7, 0, 14, 27, 35, 14, 0, 27, 27, 36, 27, 0, 37, 27,
    37, 37, 0, 53, 27, 38, 53, 0, 69, 27, 39, 69, 0, 73, 27, 40, 73, 0, 81, 27,
    41, 81, 0, 89, 27, 42, 89, 0, 99, 27, 43, 99, 0, 114, 27, 44, 114, 0, 121, 27,
    45, 121, 0, 129, 27, 46, 129, 0, 133, 27, 47, 133, 0, 145, 27, 48, 145, 0, 157, 27,
    49, 157, 0, 165, 27, 50, 165, 0, 177, 27, 51, 177, 0, 187, 27, 52, 187, 0, 200, 27,
    53, 200, 0, 211, 27, 54, 211, 0, 223, 27, 55, 223, 0, 235, 27, 56, 235, 0, 246, 27,
    57, 246, 0, 257, 27, 58, 257, 0, 261, 27, 59, 261, 0, 268, 27, 60, 268, 0, 281, 27,
    61, 281, 0, 295, 27, 62, 295, 0, 308, 27, 63, 308, 0, 318, 27, 64, 318, 0, 336, 27,
    65, 336, 0, 353, 27, 66, 353, 0, 366, 27, 67, 366, 0, 379, 27, 68, 379, 0, 392, 27,
    69, 392, 0, 404, 27, 70, 404, 0, 416, 27, 71, 416, 0, 430, 27, 72, 430, 0, 446, 27,
    73, 446, 0, 454, 27, 74, 454, 0, 464, 27, 75, 464, 0, 478, 27, 76, 478, 0, 491, 27,
    77, 491, 0, 513, 27, 78, 513, 0, 530, 27, 79, 530, 0, 543, 27, 80, 543, 0, 557, 27,
    81, 557, 0, 572, 27, 82, 572, 0, 588, 27, 83, 588, 0, 600, 27, 84, 600, 0, 616, 27,
    85, 616, 0, 632, 27, 86, 632, 0, 651, 27, 87, 651, 0, 676, 27, 88, 676, 0, 692, 27,
    89, 692, 0, 708, 27, 90, 708, 0, 724, 27, 91, 724, 0, 734, 27, 92, 734, 0, 744, 27,
    93, 744, 0, 754, 27, 94, 754, 0, 770, 27, 95, 770, 0, 784, 27, 96, 784, 0, 794, 27,
    97, 794, 0, 805, 27, 98, 805, 0, 818, 27, 99, 818, 0, 828, 27, 100, 828, 0, 841, 27,
    101, 841, 0, 853, 27, 102, 853, 0, 862, 27, 103, 862, 0, 874, 27, 104, 874, 0, 886, 27,
    105, 886, 0, 892, 27, 106, 892, 0, 900, 27, 107, 900, 0, 912, 27, 108, 912, 0, 918, 27,
    109, 918, 0, 940, 27, 110, 940, 0, 954, 27, 111, 954, 0, 965, 27, 112, 965, 0, 978, 27,
    113, 978, 0, 987, 27, 114, 987, 0, 997, 27, 115, 997, 0, 1006, 27, 116, 1006, 0, 1016, 27,
    117, 1016, 0, 1031, 27, 118, 1031, 0, 1047, 27, 119, 1047, 0, 1071, 27, 120, 1071, 0, 1084, 27,
    121, 1084, 0, 1101, 27, 122, 1101, 0, 1113, 27, 123, 1113, 0, 1121, 27, 124, 1121, 0, 1129, 27,
    125, 1129, 0, 1137, 27, 126, 1137, 0, 1152, 27, 32, 1152, 0, 1159, 27, -95, 1166, 0, 1173, 27,
    -94, 1173, 0, 1183, 27, -93, 1183, 0, 1195, 27, -92, 1195, 0, 1207, 27, -91, 1207, 0, 1223, 27,
    -90, 1223, 0, 1231, 27, -89, 1231, 0, 1242, 27, -88, 1242, 0, 1252, 27, -87, 1252, 0, 1268, 27,
    -86, 1268, 0, 1275, 27, -85, 1275, 0, 1287, 27, -84, 1287, 0, 1302, 27, -83, 1302, 0, 1315, 27,
    -82, 1315, 0, 1331, 27, -81, 1331, 0, 1341, 27, -80, 1341, 0, 1349, 27, -79, 1349, 0, 1362, 27,
    -78, 1362, 0, 1371, 27, -77, 1371, 0, 1379, 27, -76, 1379, 0, 1389, 27, -75, 1389, 0, 1404, 27,
    -74, 1404, 0, 1418, 27, -73, 1418, 0, 1422, 27, -72, 1422, 0, 1432, 27, -71, 1432, 0, 1438, 27,
    -70, 1438, 0, 1445, 27, -69, 1445, 0, 1457, 27, -68, 1457, 0, 1475, 27, -67, 1475, 0, 1494, 27,
    -66, 1494, 0, 1513, 27, -65, 1513, 0, 1523, 27, -64, 1523, 0, 1541, 27, -63, 1541, 0, 1559, 27,
    -62, 1559, 0, 1577, 27, -61, 1577, 0, 1595, 27, -60, 1595, 0, 1613, 27, -59, 1613, 0, 1631, 27,
    -58, 1631, 0, 1653, 27, -57, 1653, 0, 1666, 27, -56, 1666, 0, 1678, 27, -55, 1678, 0, 1690, 27,
    -54, 1690, 0, 1702, 27, -53, 1702, 0, 1714, 27, -52, 1714, 0, 1722, 27, -51, 1722, 0, 1730, 27,
    -50, 1730, 0, 1738, 27, -49, 1738, 0, 1746, 27, -48, 1746, 0, 1762, 27, -47, 1762, 0, 1779, 27,
    -46, 1779, 0, 1792, 27, -45, 1792, 0, 1805, 27, -44, 1805, 0, 1818, 27, -43, 1818, 0, 1831, 27,
    -42, 1831, 0, 1844, 27, -41, 1844, 0, 1859, 27, -40, 1859, 0, 1873, 27, -39, 1873, 0, 1889, 27,
    -38, 1889, 0, 1905, 27, -37, 1905, 0, 1921, 27, -36, 1921, 0, 1937, 27, -35, 1937, 0, 1953, 27,
    -34, 1953, 0, 1967, 27, -33, 1967, 0, 1979, 27, -32, 1979, 0, 1990, 27, -31, 1990, 0, 2001, 27,
    -30, 2001, 0, 2012, 27, -29, 2012, 0, 2023, 27, -28, 2023, 0, 2034, 27, -27, 2034, 0, 2045, 27,
    -26, 2045, 0, 2062, 27, -25, 2062, 0, 2072, 27, -24, 2072, 0, 2084, 27, -23, 2084, 0, 2096, 27,
    -22, 2096, 0, 2108, 27, -21, 2108, 0, 2120, 27, -20, 2120, 0, 2126, 27, -19, 2126, 0, 2132, 27,
    -18, 2132, 0, 2138, 27, -17, 2138, 0, 2144, 27, -16, 2144, 0, 2157, 27, -15, 2157, 0, 2171, 27,
    -14, 2171, 0, 2183, 27, -13, 2183, 0, 2195, 27, -12, 2195, 0, 2207, 27, -11, 2207, 0, 2219, 27,
    -10, 2219, 0, 2231, 27, -9, 2231, 0, 2245, 27, -8, 2245, 0, 2257, 27, -7, 2257, 0, 2272, 27,
    -6, 2272, 0, 2287, 27, -5, 2287, 0, 2302, 27, -4, 2302, 0, 2317, 27, -3, 2317, 0, 2334, 27,
    -2, 2334, 0, 2347, 27, -1, 2347, 0, 2364, 27,
)
FONTS = (("ldwarialbold", "ldwarialbold.png", 0x4BA140, ARIAL), ("ldwBurweed27", "ldwBurweed27.png", 0x4BB068, BURWEED))

# ------------------------------------------------------------------------------------------- the sprites

SPRITES = {sid: (name, cols, rows, suffix, across, down) for sid, name, cols, rows, suffix, across, down in TABLE}


def table_index(sid: int) -> int:
    for i, row in enumerate(TABLE):
        if row[0] == sid:
            return i
    raise KeyError(sid)


def sprite_where(sid: int) -> str:
    return f"sprite {sid}, table entry {TABLE_AT + table_index(sid) * TABLE_STRIDE:#x}"


def sprite_spec(sid: int) -> va.SheetSpec:
    """The sprite as the registry builds it (0x44C9B0 / 0x44C8F0 / 0x44CB80)."""
    name, cols, rows, suffix, across, down = SPRITES[sid]
    if rows <= 0 and cols <= 0:
        return va.SheetSpec(name, whole=True, where=sprite_where(sid))
    if rows <= 0:
        return va.SheetSpec(name, cols, 1, where=sprite_where(sid))
    if across:
        return va.SheetSpec(name, cols, rows, (across, down), suffix or ".png", where=sprite_where(sid))
    return va.SheetSpec(name, cols, rows, where=sprite_where(sid))


def sprite_atlas(sid: int) -> pi.Atlas:
    return sprite_spec(sid).atlas


def sheet_table() -> list[va.SheetSpec]:
    """Every sprite the stock exe constructs: its table (one entry per distinct cut, the ids that share it in
    `where`), the map tiles, the splash pictures, the puzzle screen's own and the fonts."""
    out: dict = {}
    for sid, *_rest in TABLE:
        spec = sprite_spec(sid)
        if spec.name == "No Graphic":
            continue                                       # entry 0: the table's empty slot, no file
        key = (spec.name.casefold(), spec.cols, spec.rows, tuple(spec.sheets), spec.whole)
        if key in out:
            old = out[key]
            out[key] = va.SheetSpec(old.name, old.cols, old.rows, old.sheets, old.suffix, old.whole, old.used,
                                    old.where + "; " + spec.where)
        else:
            out[key] = spec
    for name, where in OTHER_WHOLE:
        key = (name.casefold(), 1, 1, (1, 1), True)
        if key not in out:
            out[key] = va.SheetSpec(name, whole=True, where=where)
    for name, cols, rows, where in OTHER_GRID:
        key = (name.casefold(), cols, rows, (1, 1), False)
        if key in out:
            old = out[key]
            out[key] = va.SheetSpec(old.name, old.cols, old.rows, where=old.where + "; " + where)
        else:
            out[key] = va.SheetSpec(name, cols, rows, where=where)
    for x in range(4):
        for y in range(4):
            name = MAP_TILE.format(x=x, y=y)
            out[(name.casefold(), 1, 1, (1, 1), True)] = va.SheetSpec(name, whole=True, where="0x46FD6C (map tile)")
    for _font, picture, at, _glyphs in FONTS:
        out[(picture.casefold(), 1, 1, (1, 1), True)] = va.SheetSpec(
            picture, whole=True, where=f"font, glyph table {at:#x} (its glyphs: Fonts and digits)")
    return list(out.values())


# ------------------------------------------------------------------------------------------- fonts

def font_glyphs(table, width: int) -> list[tuple[int, tuple[int, int, int, int]]]:
    """(character, (left, top, right, bottom)) of every glyph, as 0x4027A0 leaves its table: the line height
    is the first glyph's bottom - top; each glyph moves left by the running x shift and down by the running
    y shift, and one whose right passes the picture's width starts a new line (the x shift grows by its
    left, the y shift by the line height + 1).  A character below 0 is its byte (0x40294D)."""
    entries = [list(table[i:i + 5]) for i in range(0, len(table), 5)]
    if not entries:
        return []
    line = entries[0][4] - entries[0][2]
    dx = dy = 0
    out = []
    for n, e in enumerate(entries):
        if e[0] == 0 or n >= 0x100:
            break
        e[1] -= dx
        e[3] -= dx
        e[2] += dy
        e[4] += dy
        if e[3] > width:
            dx += e[1]
            dy += line + 1
            e[3] -= e[1]
            e[1] = 0
            e[2] += line + 1
            e[4] += line + 1
        out.append((e[0] & 0xFF if e[0] < 0 else e[0], (e[1], e[2], e[3], e[4])))
    return out


def _glyph_label(ch: int) -> str:
    if 33 <= ch < 127:
        return f"character {chr(ch)!r} ({ch})"
    try:
        text = bytes([ch]).decode("cp1252")
        return f"character {text!r} ({ch})"
    except UnicodeDecodeError:
        return f"character {ch}"


def font_assets(sheets) -> list[va.Asset]:
    out = []
    for font, picture, at, table in FONTS:
        if not sheets.has(picture):
            continue
        width = sheets.size(picture)[0]
        frames = tuple(va.Frame(_glyph_label(ch), (pi.Draw(picture, rect, 0, 0),))
                       for ch, rect in font_glyphs(table, width))
        out.append(va.Asset(f"font:{font}", va.FONTS, f"{font} (every glyph)", frames, group="Fonts",
                            note=f"glyphs as the font loader 0x4027A0 cuts {picture} (glyph table {at:#x})",
                            proof="emulated 0x4027A0"))
    return out


# ------------------------------------------------------------------------------------------- buttons

STATE_LABELS = ("state 0: normal", "state 1: mouse over", "state 2: pressed")
# Where the exe asks the registry for a strip (0x44CB60, which hands out the buttons' ldwImageStrip) by a
# constant id: push id; mov ecx, reg; call 0x44CB60.  Strips not here are never asked for by a constant.
STRIP_REQUESTS = {
    42: (0x43BEF8,), 43: (0x4197FA, 0x446F21), 44: (0x4198A2, 0x446ED2), 45: (0x43EDA1,), 46: (0x43EDE8,),
    47: (0x43A736, 0x43C9DF, 0x43DE86, 0x444FFC, 0x446E51), 48: (0x43ED24,),
    130: (0x417884, 0x418627, 0x4187E4, 0x41914B, 0x41918D, 0x419923, 0x419AE4, 0x419CA9, 0x41A1D1, 0x41B436,
          0x41BC95, 0x43D7E8, 0x43D85D),
    131: (0x4179C8, 0x417A0C), 136: (0x441BA6,), 137: (0x441C5E,), 138: (0x441CAB,), 139: (0x4416A5,),
    140: (0x44175C,), 141: (0x441815,), 142: (0x4418CD,), 143: (0x441985,), 144: (0x441A3E,), 145: (0x444109,),
    146: (0x443F7B,), 147: (0x443EB4,), 148: (0x443D33,), 149: (0x444042,), 150: (0x443DED,), 216: (0x43D73D, 0x441AF4),
}


def strip_ids(frames: int = 3) -> list[int]:
    """The table's button strips (rows 0, `frames` columns): the art the engine's buttons draw."""
    return [sid for sid, name, cols, rows, *_r in TABLE if rows == 0 and cols == frames]


def button_plan(sheets, sid: int, state: int, x: int = 0, y: int = 0) -> list:
    """0x401200(state) with the button's strip at [impl+0x3C], enabled ([impl+0x29] = 1): the strip's frame
    `state` at the button's place (0x4099F0 -> 0x4088F0), unscaled and opaque."""
    return [va.cell_plan(sheets, sprite_atlas(sid), state, 0, x, y)]


def button_assets(sheets) -> list[va.Asset]:
    out = []
    for sid in strip_ids(3):
        name = SPRITES[sid][0]
        if not sheets.has(name):
            continue
        frames = tuple(va.Frame(STATE_LABELS[k], tuple(button_plan(sheets, sid, k))) for k in range(3))
        asked = STRIP_REQUESTS.get(sid)
        where = (f"asked for at {', '.join(f'{a:#x}' for a in asked)}" if asked else
                 "no code asks for this strip by a constant id (a computed one is not ruled out)")
        out.append(va.Asset(f"button:{sid}", va.PANELS, f"{name} button", frames, group="Buttons",
                            note="drawn as the engine's button draws a 3-frame strip: state 0, 1, 2 (0x401540 picks "
                                 "it from the button's state) is frame 0, 1, 2; " + where + "; the caption the "
                                 "game writes over it is text, not drawn here; a disabled button is tinted pixel "
                                 "by pixel (0x408F60), not drawn here",
                            proof="emulated 0x401200"))
    return out


# ------------------------------------------------------------------------------------------- the Tech screen

TECH_BG = 227                           # tech_bg.jpg
CARVING = ((95, 395, 135), (94, 395, 201), (93, 395, 271), (92, 395, 340), (91, 395, 408))
CARVING_BASE = (90, 395, 474)           # slice 1: always drawn
TECH_ROWS = ((228, 3, 73, "Science"), (229, 3, 179, "Medicine"), (230, 3, 281, "Learning"),
             (231, 3, 386, "Construction"), (232, 3, 489, "Food Mastery"), (233, 398, 74, "Dendrology"))
TECH_ROW_TABLE = 0x4BEE60               # (sprite, x, y, across) x 6, 16 bytes each
TECH_STEP = 0x84                        # each level's piece 132 pixels right of the last
TECH_LEVELS = 3                         # each bar's jpg has 3 frames


def _whole(sheets, sid: int, x: int, y: int) -> pi.Draw:
    """0x44CDB0(id, x, y, 1.0, 100): a whole picture or frame 0 of a sheet, unscaled."""
    spec = sprite_spec(sid)
    if spec.whole:
        return va.whole_plan(sheets, spec.name, x, y)
    return va.cell_plan(sheets, spec.atlas, 0, 0, x, y)


def carving_plan(sheets, carving: int) -> list:
    """The colour carving as 0x43E640 draws it when 0x41F570 says `carving` (0-5): slice 6 when 5 or more,
    slice 5 when 4 or more ... slice 2 when 1 or more, top down, then slice 1 always."""
    out = []
    for k, (sid, x, y) in enumerate(CARVING):
        if carving >= 5 - k:
            out.append(_whole(sheets, sid, x, y))
    out.append(_whole(sheets, *CARVING_BASE))
    return out


def tech_row_plan(sheets, row: int, levels: int) -> list:
    """Technology `row`'s bar with `levels` learned (0x41E1C0): its jpg's frame k at (x + 132 k, y), k = 0 ..
    levels - 1, each at its fade-in alpha (1.0 once shown: 0x43E7A3 adds 0.02 a frame up to 1)."""
    sid, x, y, _name = TECH_ROWS[row]
    atlas = sprite_atlas(sid)
    return [va.cell_plan(sheets, atlas, k, 0, x + TECH_STEP * k, y) for k in range(levels)]


def tech_screen_plan(sheets, carving: int, levels) -> list:
    """0x43E640: tech_bg.jpg at (0, 0), the carving, then the six bars (the dialog's buttons and text it
    draws after, 0x40D3E0, are not part of this)."""
    out = [_whole(sheets, TECH_BG, 0, 0)]
    out += carving_plan(sheets, carving)
    for row in range(6):
        out += tech_row_plan(sheets, row, levels[row])
    return out


def tech_assets(sheets) -> list[va.Asset]:
    names = [SPRITES[s][0] for s in (TECH_BG, CARVING_BASE[0], *(c[0] for c in CARVING), *(r[0] for r in TECH_ROWS))]
    if not all(sheets.has(n) for n in names):
        return []
    out = []
    screens = tuple(va.Frame(f"every technology at level {n}, carving {min(n * 2, 5)} of 5",
                             tuple(tech_screen_plan(sheets, min(n * 2, 5), (n,) * 6))) for n in range(4))
    out.append(va.Asset("tech:screen", va.TECH, "Tech screen", screens, group="The screen",
                        note="the Tech screen's own art (its buttons and writing are drawn after it)",
                        proof="emulated 0x43E640"))
    out.append(va.Asset("tech:carving", va.TECH, "Colour carving", tuple(
        va.Frame(f"{n} of 5 tasks done ({n + 1} slices coloured)", tuple(carving_plan(sheets, n))) for n in range(6)),
        group="The screen", note="0x41F570 counts five tasks (flags 1, 12, 13, 14 and 15 of 0x4D8BF8)",
        proof="emulated 0x43E640"))
    bg = SPRITES[TECH_BG][0]
    for row, (sid, x, y, label) in enumerate(TECH_ROWS):
        w, h = sprite_atlas(sid).cell(sheets.size, 0, 0)[1][2:]
        under = pi.Draw(bg, (x, y, x + w * TECH_LEVELS, y + h), x, y, what="uncoloured")
        frames = [va.Frame("uncoloured (nothing learned: the screen's background under the bar)", (under,))]
        for n in range(1, TECH_LEVELS + 1):
            frames.append(va.Frame(f"level {n} coloured", (under,) + tuple(tech_row_plan(sheets, row, n))))
        out.append(va.Asset(f"tech:bar:{row}", va.TECH, f"{label} bar ({SPRITES[sid][0]})", tuple(frames),
                            group="Technology bars",
                            note="the coloured pieces are the game's own blits; the uncoloured bar is tech_bg.jpg's "
                                 "own picture under them (the game draws the whole background)",
                            proof="emulated 0x43E640"))
    return out


# ------------------------------------------------------------------------------------------- meters

SLICE_B, SLICE_R, BULB, BAMBOO, LOADCOLOR = 168, 169, 170, 167, 171
BAR_KINDS = {3: (SLICE_B, 0xE0), 4: (SLICE_B, 0x10A), 5: (SLICE_B, 0x134), 6: (SLICE_B, 0x160),
             7: (SLICE_B, 0x189), 8: (SLICE_R, 0x5F)}
BAR_X = 0x1D4
METER_LEVELS = (10, 25, 50, 75, 100)


def _cdiv(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def bar_plan(sheets, value: int, kind: int, y: int = 0) -> list:
    """0x44D070(value, kind, y): value clamped to 0-100, value x 256 / 100 / 4 slices (C division), each the
    whole slice picture at (468 + 4 i, y + the kind's offset); kind 8 is the red slice."""
    v = max(0, min(100, value))
    n = _cdiv(_cdiv(v << 8, 100), 4)
    sid, dy = BAR_KINDS[kind]
    name = SPRITES[sid][0]
    return [va.whole_plan(sheets, name, BAR_X + 4 * i, y + dy) for i in range(n)]


def loading_bar_plan(sheets, value: int, x: int = 0xF0, y: int = 0x1F4) -> list:
    """0x44DB10(3, x, y, value) (the loading screen's): value clamped to 1-100; value x 320 / 100 / 8
    segments; for each, LoadColor.png at (x + 8 i, y) and then the bamboo frame at (x, y) again."""
    v = max(1, min(100, value))
    n = _cdiv(_cdiv(v * 5 << 6, 100), 8)
    out = []
    for i in range(n):
        out.append(va.whole_plan(sheets, SPRITES[LOADCOLOR][0], x + 8 * i, y))
        out.append(va.whole_plan(sheets, SPRITES[BAMBOO][0], x, y))
    return out


def meter_assets(sheets) -> list[va.Asset]:
    out = []
    if sheets.has(SPRITES[SLICE_B][0]):
        out.append(va.Asset("meter:bar:blue", va.METERS, "Villager Details bar (StatusBarSliceB.png)", tuple(
            va.Frame(f"{v}% full", tuple(bar_plan(sheets, v, 3))) for v in METER_LEVELS), group="Villager Details",
            note="kinds 3-7 of 0x44D070 (the same slices, at five heights)", proof="emulated 0x44D070"))
    if sheets.has(SPRITES[SLICE_R][0]):
        out.append(va.Asset("meter:bar:red", va.METERS, "Villager Details bar (StatusBarSliceR.png)", tuple(
            va.Frame(f"{v}% full", tuple(bar_plan(sheets, v, 8))) for v in METER_LEVELS), group="Villager Details",
            note="kind 8 of 0x44D070", proof="emulated 0x44D070"))
    if sheets.has(SPRITES[LOADCOLOR][0]) and sheets.has(SPRITES[BAMBOO][0]):
        out.append(va.Asset("meter:loading", va.METERS, "Loading bar", tuple(
            va.Frame(f"{v}% loaded", tuple(loading_bar_plan(sheets, v))) for v in METER_LEVELS), group="Loading",
            note="below 3% the game draws nothing, not even the frame", proof="emulated 0x44DB10"))
        out.append(va.Asset("meter:bamboo", va.METERS, "Bamboo meter frame", (
            va.Frame("", (va.whole_plan(sheets, SPRITES[BAMBOO][0], 0, 0),)),), group="Loading",
            note="0x44DB10 kinds 0-2 fill a rectangle (a colour, not a picture) inside this frame; the fill "
                 "is not drawn here", proof="emulated 0x44DB10"))
    return out


# ------------------------------------------------------------------------------------------- screens

# Each screen's fixed art: (key, label, draw function, [(sprite, x, y, call)], note).  The constant arguments
# of each 0x44CDB0 call (push 100, alpha 1.0, y, x, sprite) are read from the exe by the tests.
SCREENS = (
    ("loading", "Loading screen", 0x43F400, ((178, 0, 0, 0x43F421), (180, 212, 10, 0x43F49B),
                                            (179, 47, 400, 0x43F4B6)),
     "between the background and the logos the game fills the screen with a 60% wash and draws the loading "
     "bar (Meters); the wash is a fill, not a picture, and is not drawn here"),
    ("trophies", "Trophies screen", 0x43A950, ((117, 0, 0, 0x43A979), (121, 0, 0, 0x43AAC7),
                                              (122, 0, 545, 0x43AADF)), "its rows and scroll knob come between"),
    ("mausoleum", "Mausoleum screen", 0x43D280, ((26, 0, 0, 0x43D2AD), (27, 0, 0, 0x43D371),
                                                (28, 0, 545, 0x43D389)), "its rows and scroll knob come between"),
    ("select", "Select villagers screen", 0x43B6A0, ((69, 0, 0, 0x43B6CB),), ""),
    ("collections", "Collections screen", 0x43C6D0, ((222, 0, 0, 0x43C6F3),), "the collected items come after"),
    ("details", "Villager Details screen", 0x447D30, ((236, 0, 0, 0x447D4F),),
     "the villager, bars and checkmarks come after"),
    ("overview", "Island overview (map) screen", 0x4453C0, ((173, 0, 0, 0x4453DD),), "the map marks come after"),
    ("boxshot", "Boxshot screen", 0x443560, ((215, 0, 0, 0x44357E),),
     "then the butterflies (0x42BC40) and light-beams.png at (350, 0) at an opacity that wavers with time "
     "(0x44358D), not drawn here"),
    ("puzzles", "Puzzles page", 0x43EF40, ((209, 0, 0, 0x43EF5E),), ""),
    ("help1", "Help page 1", 0x43EF40, ((210, 0, 0, 0x43EF89),), ""),
    ("help2", "Help page 2", 0x43EF40, ((211, 0, 0, 0x43EFA4),), ""),
    ("help3", "Help page 3", 0x43EF40, ((212, 0, 0, 0x43EFBF),), ""),
    ("help4", "Help page 4", 0x43EF40, ((213, 0, 0, 0x43EFDA),), ""),
    ("credits", "Credits page", 0x43EF40, ((214, 0, 0, 0x43EFF5),), ""),
)


def screen_plan(sheets, draws) -> list:
    return [_whole(sheets, sid, x, y) for sid, x, y, _call in draws]


def screen_assets(sheets) -> list[va.Asset]:
    out = []
    for key, label, fn, draws, note in SCREENS:
        if not all(sheets.has(SPRITES[sid][0]) for sid, *_r in draws):
            continue
        out.append(va.Asset(f"screen:{key}", va.SCREENS, label, (va.Frame("", tuple(screen_plan(sheets, draws))),),
                            group="Screens", note=(f"the fixed art {fn:#x} draws, in its order" +
                                                   (f"; {note}" if note else "")),
                            proof="exe call arguments"))
    if sheets.has("SPLASH_BG.JPG"):
        out.append(va.one(sheets, "screen:splash", va.SCREENS, "Splash screen (SPLASH_BG.JPG)", "SPLASH_BG.JPG",
                          group="Screens", note="built whole at 0x4466A4; " + va.NOT_PLACED, proof="constructor"))
    return out


# ------------------------------------------------------------------------------------------- dialogs

DIALOG_MARGIN = (0, 0)                  # [0x4CBB78], [0x4CBB74]: added to the width and height (never written)
DIALOGS = ((153, 800, 60, "Green dialog, 800 x 60 (0x412AEF)"), (153, 300, 200, "Green dialog, 300 wide (0x41983F)"),
           (152, 512, 300, "Orange dialog, 512 wide (0x417CDD)"))
DIALOG_TILES = (("top left", 8), ("top", 1), ("top right", 0), ("left", 3), ("middle", 7), ("right", 2),
                ("bottom left", 5), ("bottom", 4), ("bottom right", 6))


def dialog_size(sheets, sid: int, w: int, h: int) -> tuple[int, int, int, int]:
    """(tile w, tile h, tiles across, tiles down) as 0x40DC70 / 0x40DA30 set them: the grid's cell, and
    (margin + w + tile - 1) / tile tiles (C division), at least 2."""
    tw, th = sprite_atlas(sid).cell(sheets.size, 0, 0)[1][2:]
    nx = _cdiv(tw + DIALOG_MARGIN[0] + w - 1, tw)
    ny = _cdiv(th + DIALOG_MARGIN[1] + h - 1, th)
    return tw, th, nx if nx > 1 else 2, ny if ny > 1 else 2


def dialog_plan(sheets, sid: int, w: int, h: int, x: int = 0, y: int = 0) -> list:
    """0x40DAB0(x, y, 1.0): a dialog of the 9-tile grid laid row by row: the top row tile 8, tile 1 across,
    tile 0; each middle row tile 3, tile 7 across, tile 2; the bottom row tile 5, tile 4 across, tile 6."""
    tw, th, nx, ny = dialog_size(sheets, sid, w, h)
    atlas = sprite_atlas(sid)
    out = []

    def row(yy, first, mid, last):
        out.append(va.cell_plan(sheets, atlas, first, 0, x, yy))
        for i in range(nx - 2):
            out.append(va.cell_plan(sheets, atlas, mid, 0, x + tw * (i + 1), yy))
        out.append(va.cell_plan(sheets, atlas, last, 0, x + tw * (nx - 1), yy))
    row(y, 8, 1, 0)
    for j in range(ny - 2):
        row(y + th * (j + 1), 3, 7, 2)
    row(y + th * (ny - 1), 5, 4, 6)
    return out


def dialog_assets(sheets) -> list[va.Asset]:
    out = []
    for k, (sid, w, h, label) in enumerate(DIALOGS):
        if not sheets.has(SPRITES[sid][0]):
            continue
        out.append(va.Asset(f"dialog:{k}", va.PANELS, label, (va.Frame("", tuple(dialog_plan(sheets, sid, w, h))),),
                            group="Dialogs",
                            note=(f"{SPRITES[sid][0]}'s 9 tiles as the tiled background 0x40DAB0 lays them; the width "
                                  "is the game's; " + ("the height is the game's" if k == 0 else
                                                       "the height varies with the message: 200 / 300 shown")),
                            proof="emulated 0x40DC70 and 0x40DAB0"))
        if k == 0 or DIALOGS[k - 1][0] != sid:
            atlas = sprite_atlas(sid)
            out.append(va.Asset(f"dialog:tiles:{sid}", va.PANELS, f"{SPRITES[sid][0]} tiles", tuple(
                va.Frame(f"tile {n} ({where})", (va.cell_plan(sheets, atlas, n, 0),)) for where, n in DIALOG_TILES),
                group="Dialogs", note="what each tile is, from where 0x40DAB0 puts it", proof="emulated 0x40DAB0"))
    return out


# ------------------------------------------------------------------------------------------- huts

HUT_DRAW = 0x42FF80                     # the huts' draw (vtable entry 7 of 0x48E3CC, 0x48E44C, 0x48E4CC, ...)
HUTS = ((295, "Hut (hut_states.png)"), (297, "Love shack (loveshack_states.png)"),
        (298, "Nursery hut (nurseryhut_states.png)"), (299, "Hospital (hospital_states.png)"))
SCAFFOLDING = 273                       # 0x42FD41: the hut's [+0x64]
SCAFFOLD_PLACES = ((0, 110), (88, 75))  # 0x4BDC80: draw parts 0 and 1


def hut_part_plan(sheets, sid: int, part: int, x: int = 0, y: int = 0) -> list:
    """0x42FF80(part << 24) for a hut at (x, y), not highlighted: part 0 and 1 are scaffolding.png whole at
    (x, y) + 0x4BDC80[part] (0x44C5E0); part 2 and up is the hut sheet's frame part - 2 at (x, y)
    (0x44C640), camera at rest."""
    if part < 2:
        dx, dy = SCAFFOLD_PLACES[part]
        return [va.whole_plan(sheets, SPRITES[SCAFFOLDING][0], x + dx, y + dy)]
    atlas = sprite_atlas(sid)
    row, col = divmod(part - 2, atlas.cols)
    return [va.cell_plan(sheets, atlas, col, row, x, y)]


def hut_assets(sheets) -> list[va.Asset]:
    out = []
    if not sheets.has(SPRITES[SCAFFOLDING][0]):
        return out
    for sid, label in HUTS:
        if not sheets.has(SPRITES[sid][0]):
            continue
        atlas = sprite_atlas(sid)
        frames = [va.Frame(f"scaffolding, part {p + 1}", tuple(hut_part_plan(sheets, sid, p))) for p in range(2)]
        frames += [va.Frame(f"frame {k + 1}", tuple(hut_part_plan(sheets, sid, k + 2)))
                   for k in range(atlas.cols * atlas.rows)]
        out.append(va.Asset(f"hut:{sid}", va.BUILDINGS, label, tuple(frames), group="Huts",
                            note="each part as the huts' draw 0x42FF80 places it against the hut's own place "
                                 "(scaffolding 0 and 1, then the sheet's frames); which parts the game queues "
                                 "at each build stage is not traced here, so they are not shown together",
                            proof="emulated 0x42FF80"))
    return out


# ------------------------------------------------------------------------------------------- the island map

MAP_TILE_SIZE = 512


def map_plan(sheets) -> list:
    """0x46FE10 with the camera at (0, 0) and the whole map in view: the 16 tiles in the order 0x46FCE0 made
    them (x outer, y inner), tile (x, y) whole at (512 x, 512 y)."""
    return [va.whole_plan(sheets, MAP_TILE.format(x=x, y=y), MAP_TILE_SIZE * x, MAP_TILE_SIZE * y)
            for x in range(4) for y in range(4)]


def map_assets(sheets) -> list[va.Asset]:
    if not all(sheets.has(MAP_TILE.format(x=x, y=y)) for x in range(4) for y in range(4)):
        return []
    return [va.Asset("scene:map", va.SCENE, "The island (its 16 map tiles)", (va.Frame("", tuple(map_plan(sheets))),),
                     group="The island", note="the ground only: everything on it is drawn over these tiles",
                     proof="emulated 0x46FCE0 and 0x46FE10")]


# ------------------------------------------------------------------------------------------- the patcher's art

MASK_FILE = "vvfp_mask_atlas00.png"           # vv_pictures_vv4.MASK_FILE / MASK_ATLAS (8 x 5)
BIG_MASK_FILE = "vvfp_bighead_mask_atlas00.png"  # vv_pictures_vv4.BIG_MASK_FILE / BIG_MASK_ATLAS (3 x 5)
MASK_PREVIEW = "vvfp_mask_preview.png"
GOLDEN = "golden_mushroom.png"
GOLDEN_FRAME = 50                             # the collectables sheet's frame it replaces
GOLDEN_DX, GOLDEN_DY = 7, 0                   # LATER_STUB(vv4, 0x4CC9E8, 0x44C645u, 7, 0)
MASK_NAMES = ("Chief's mask", "Red mask", "Blue mask", "Orange mask", "Purple mask")
ORIGINS_ICONS = ((101, "Time Warp"), (102, "Island Event"), (103, "Barrel of Babies"), (104, "Tech Point Doubler"),
                 (105, "Food Point Doubler"), (106, "Grant Youth"), (107, "Grant Full Mastery"),
                 (108, "Grant Running"), (109, "Upgrade checkmark"), (110, "Cure All"))


def patcher_art() -> dict:
    """The patcher's own art for The Tree of Life that the release ships (scripts/build_release.py FILES), the
    Origins icons read from inside their shipped companion DLL."""
    art: dict = {MASK_FILE: ROOT / "assets" / "vv4_masks" / "vvfp_mask_atlas.png",
                 BIG_MASK_FILE: ROOT / "assets" / "vv4_masks" / "vvfp_bighead_mask_atlas.png",
                 MASK_PREVIEW: ROOT / "assets" / "vv4_masks" / "vvfp_mask_preview.png",
                 GOLDEN: ROOT / "assets" / "golden_mushroom" / "golden_mushroom.png"}
    art.update(origins_icon_resources())
    return art


def origins_icon_resources() -> dict[str, tuple[Path, int, int]]:
    """The Origins icons as the shipped companion DLL carries them (RT_ICON 3, PNG images 1-49: five sizes of
    each icon group 101-110), read by vv_pictures_assets.read_patcher_art."""
    dll = ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll"
    out = {}
    for k, (group, _label) in enumerate(ORIGINS_ICONS):
        sizes = (16, 24, 32, 48, 64) if group != 110 else (16, 32, 48, 64)
        first = 1 + 5 * k
        for j, size in enumerate(sizes):
            out[f"vvfp_origins_icon_{group}_{size}.png"] = (dll, 3, first + j)
    return out


def golden_plan(sheets, x: int = 0, y: int = 0) -> list:
    """The Golden Mushroom companion at the world draw 0x44C640: frame 50 of the collectables sheet at (x, y)
    becomes golden_mushroom.png (a 1 x 1 sprite, 0x40AB10) at (x + 7, y + 0), frame 0."""
    return [va.cell_plan(sheets, pi.Atlas(GOLDEN, 1, 1), 0, 0, x + GOLDEN_DX, y + GOLDEN_DY)]


def patcher_assets(sheets) -> list[va.Asset]:
    out = []
    if sheets.has(GOLDEN):
        out.append(va.Asset("patcher:golden", va.COLLECTIBLES, "Super-Secret Golden Mushroom", (
            va.Frame("in the world", tuple(golden_plan(sheets))),), group="The patcher's", patcher=True,
            note="drawn by the Golden Mushroom companion in place of the collectables sheet's frame 50, "
                 "7 pixels to its right", proof="emulated 0x44C640; native/vvfp_golden_mushroom"))
    for name, cols, label in ((MASK_FILE, 8, "Origins masks (village)"), (BIG_MASK_FILE, 3, "Origins masks (Villager Details)")):
        if not sheets.has(name):
            continue
        atlas = pi.Atlas(name, cols, 5)
        frames = tuple(va.Frame(f"{MASK_NAMES[row]}, facing {col + 1}", (va.cell_plan(sheets, atlas, col, row),))
                       for row in range(5) for col in range(cols))
        out.append(va.Asset(f"patcher:{name}", va.PATCHER, label, frames, group="Origins masks", patcher=True,
                            note=f"{cols} x 5 cells as the companion's 0x40ABA0(name, \".png\", 1, 1, {cols}, 5) "
                                 "cuts them (worn on a villager: Villagers tab)", proof="vv_pictures_vv4"))
    if sheets.has(MASK_PREVIEW):
        out.append(va.one(sheets, "patcher:mask_preview", va.PATCHER, "Origins mask preview", MASK_PREVIEW,
                          group="Origins masks", patcher=True, note="the patcher's own preview; " + va.NOT_PLACED,
                          proof="file"))
    icons = []
    for name in origins_icon_resources():
        if sheets.has(name):
            icons.append(va.Frame(name, (va.whole_plan(sheets, name),)))
    if icons:
        out.append(va.Asset("patcher:origins_icons", va.PATCHER, "Origins icons (companion DLL)", tuple(icons),
                            group="Origins icons", patcher=True,
                            note="the icons Windows shows for the Origins upgrades; " + va.NOT_PLACED, proof="file"))
    return out


# ------------------------------------------------------------------------------------------- everything else

# Where each remaining sprite is listed besides Source sheets: (category, group) by id.
def _groups() -> dict:
    g = {}

    def put(cat, group, *ids):
        for i in ids:
            g[i] = (cat, group)
    put(va.CREATURES, "Fish", 73, 74, 265, 266, 267, 269, 38, 39)
    put(va.CREATURES, "Crabs and frogs", 75, 76, 248, 249)
    put(va.CREATURES, "Birds and insects", 300, 301, 302, 303, 129, 268)
    put(va.BUILDINGS, "Huts", 295, 296, 297, 298, 299, 273, 272)
    put(va.BUILDINGS, "Laboratories", 289, 290, 291, 292, 293, 294, 80, 18)
    put(va.BUILDINGS, "The Tree of Life", 81, 82, 83, 84, 85, 86, 87, 88, 89, 71)
    put(va.BUILDINGS, "Graves and the mausoleum", 37, 274)
    put(va.BUILDINGS, "Food bin", 237)
    put(va.PUZZLES, "Island puzzles", 6, 7, 8, 9, 10, 25, 40, 41, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61,
        62, 63, 64, 65, 66, 67, 68, 78, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 19, 20, 21, 22, 23, 24, 72, 79)
    put(va.PUZZLES, "Puzzle covers", 221)
    put(va.COLLECTIBLES, "Collectables", 260, 13, 11, 12, 223, 224, 225, 226)
    put(va.PLANTS, "Plants and food", 70, 77, 304, 16, 17, 244)
    put(va.EFFECTS, "Water", 96, 97, 98, 99, 100, 101, 102, 103, 238, 239, 253, 254, 255, 257, 14, 15, 246, 270, 271)
    put(va.EFFECTS, "Sparkles, smoke and weather", 240, 241, 242, 243, 245, 247, 250, 251, 252, 258, 259, 261, 262,
        263, 264, 275, 4, 5, 287, 288, 174, 175, 176, 177)
    put(va.VILLAGERS, "Villagers", 284, 285, 286, 172)
    put(va.CURSORS, "The hand", 1, 2)
    put(va.ICONS, "Icons", 160, 123, 217, 218, 219, 220, 170, 3)
    put(va.PANELS, "Dialogs", 152, 153)
    put(va.PANELS, "Controls", 156, 157, 158, 159, 161, 162, 165, 166, 34, 35, 114, 115, 127, 128, 234, 235)
    put(va.PANELS, "Screen parts", 26, 27, 28, 29, 30, 31, 32, 33, 36, 117, 118, 119, 120, 121, 122, 124, 125, 126,
        208, 69, 222, 236, 173)
    put(va.SCREENS, "Story pages", *range(182, 208))
    put(va.SCREENS, "Logos", 178, 179, 180, 181, 209, 210, 211, 212, 213, 214, 215)
    return g


GROUPS = _groups()
COMPOSED_ELSEWHERE = {TECH_BG, *(c[0] for c in CARVING), CARVING_BASE[0], *(r[0] for r in TECH_ROWS), SLICE_B,
                      SLICE_R, BAMBOO, LOADCOLOR, *(h[0] for h in HUTS), *(d[0] for d in DIALOGS)}


def cell_assets(sheets) -> list[va.Asset]:
    """Every table sprite not composed above, listed in its category as the constructor cuts it."""
    out = []
    buttons = set(strip_ids(3))
    for sid, name, *_r in TABLE:
        if sid == 0 or sid in buttons or sid in COMPOSED_ELSEWHERE or sid not in GROUPS:
            continue
        spec = sprite_spec(sid)
        if not all(sheets.has(f) for f in spec.files()):
            continue
        cat, group = GROUPS[sid]
        frames = va.sheet_frames(sheets, spec)
        many = len(frames) > 1
        out.append(va.Asset(f"cells:{sid}", cat, name if not spec.atlas.grid else f"{name} sheets", frames,
                            group=group,
                            note=(("cells in the sheet's order, as the game's constructor cuts them; how the game "
                                   "plays or places them is not proven here") if many else
                                  "the whole picture; where the game places it is not proven here"),
                            proof="constructor"))
    return out


def assets(sheets) -> list[va.Asset]:
    """Every composed asset of The Tree of Life, and every remaining sprite in its category."""
    out = []
    for part in (tech_assets, meter_assets, button_assets, dialog_assets, screen_assets, map_assets, hut_assets,
                 font_assets, patcher_assets, cell_assets):
        out += part(sheets)
    return out
