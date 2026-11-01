"""Picture Studio's Everything tab, New Believers (Virtual Villagers 5): every sprite the game builds, and the
things it assembles from them, drawn as its own code draws them (docs/picture-studio-assets-vv5.md; proven by
tests/test_assets_vv5.py, which runs that code in Unicorn on the stock executable).

THE SPRITES.  Almost every picture is built through the game's sprite table 0x4CEFB8 (341 records of 0x30 bytes:
id, name, columns, rows, suffix, sheets across, sheets down; looked up by 0x44F760).  The getter 0x44FA40 builds a
record on first use: rows > 0 -> the cell sprite 0x40B010 (name, columns, rows) or, with a suffix, the sheet grid
0x40B0A0; rows 0 and columns > 0 -> the strip 0x401000 (0x40B010 with one row); else the whole picture 0x40AD50.
Outside the table: puzzles_bg.jpg and puzzle_covers.png (4 x 4) at 0x448ABF / 0x448AF4, SPLASH_BG.JPG at 0x449964,
the island map's 25 tiles "%s%01dX%01dY.jpg" at 0x47ABE0, and the two fonts ldwarialbold / ldwBurweed27 (0x41E874,
0x41E8E4: font 0x402360 with a glyph table of (code, left, top, right, bottom) records).  The other names the exe
holds (menu_logo.png, loading_logo.png, SPLASH1-3_BG.JPG, small_logo.png, Tech_colorcarving_slice1-6.png, the four
collecting_*_collectionscreen.png) are not in the game's Images folder, so they are never drawn.

THE DRAW.  Everything goes through the sprite draw 0x44FC70 (id, frame, x, y, alpha, percent) or the sprite's own
methods (0x409B90 whole at x, y; 0x409BA0 with alpha; 0x409C30 cell); a cell is cut as vv_picture_image.Atlas.cell.

COMPOSED HERE (each drawn the game's way, the rule's address beside it):
  Tech screen 0x440F80   Tech_UI_BG.jpg at (0, 0); the six tech lines (table 0x4CD220: bar sprite, x, y) draw cell k
                         of their bar at (x + 167k, y) for each level k bought (0x423600); then the 11 god power
                         icons at the table 0x4CD300: lit once the Divine Energy cap reaches the power's cost
                         (0x49A19C) -- the backing (alpha of its fade) and the coloured icon -- else the grey icon and
                         the backing at alpha 0.6; then the icon's top ring.
  Skill bars 0x4500E0    (kind, value -100..100, y): n = trunc(trunc(value x 256 / 100) / 4) slices of 4 px from
                         x 571: StatusBarSliceB at y + 299/341/383/427/468 (kinds 3-7), y + 508 (kind 11),
                         StatusBarSliceR at y + 170 (kind 8, health).  Kind 9 (FaithMeterBG and half-length slices)
                         is never passed by any caller: listed under Unused.
  Divine Energy 0x450380 (x, y, cap, energy, cost): cap clamped 10..1,000; length L = trunc(cap x 372 / 1,000);
                         trunc(L / 4) green slices, trunc(trunc(L x energy / cap) / 4) blue slices over them, then
                         trunc(trunc(L x cost / cap) / 4) glow slices (a power's cost while one is chosen); the HUD
                         draws ManaBGBar.png at (614, 10) and the bar at (617, 12) (0x4431E8, 0x443217).
  Dialog boxes 0x40DFA0  9 tiles of a 64 x 64 grid sheet (0x40E160: columns (w + 63) // 64, rows (h + 63) // 64, at
                         least 2): corners 8, 0, 5, 6; edges 1 (top), 4 (bottom), 3 (left), 2 (right); middle 7.
  Island map 0x47ABE0    LargeMap<X>X<Y>Y.jpg at (512 X, 512 Y), X and Y 0-4, in the loader's order.

PATCHER ART: the Super-Secret Golden Mushroom (assets/golden_mushroom/golden_mushroom.png, drawn by VVFP Golden
Mushroom.dll in place of collectables frame 51 at +7, +1), the Details portrait masks
(assets/vv5_bighead_masks/bigheads_masks.png, 3 facings x 5 colours) and the Origins icons the VV5 Origins DLL carries.
"""
from __future__ import annotations

from pathlib import Path

import vv_picture_image as pi
import vv_pictures_assets as va
from vv_pictures_assets import (Asset, Frame, SheetSpec, BUILDINGS, COLLECTIBLES, CREATURES, CURSORS, EFFECTS, FONTS,
                                ICONS, METERS, PANELS, PATCHER, PLANTS, PUZZLES, SCENE, SCREENS, TECH, UNUSED,
                                VILLAGERS)

GAME = 5
ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------ the game's sprite table 0x4CEFB8
# (id, name, columns, rows, sheets across, sheets down) -- across/down 0 when the record has no suffix.
DESCRIPTORS = (
    (0x0, 'No Graphic', 0, 0, 0, 0),
    (0x1, 'hand_open.png', 0, 0, 0, 0),
    (0x2, 'hand.png', 0, 0, 0, 0),
    (0x3, 'spell_backing.png', 0, 0, 0, 0),
    (0x4, 'spell_front.png', 0, 0, 0, 0),
    (0x5, 'stompped_shroom.png', 0, 0, 0, 0),
    (0x6, 'spell_area_160.png', 0, 0, 0, 0),
    (0x7, 'god_power_icons.png', 11, 1, 0, 0),
    (0x8, 'flowers.png', 6, 1, 0, 0),
    (0xA, 'StatusBarSliceG.png', 1, 1, 0, 0),
    (0x11, 'ManaBGBar.png', 1, 1, 0, 0),
    (0xF, 'FaithMeterBG.png', 1, 1, 0, 0),
    (0x10, 'FirePlaceDecal.png', 1, 1, 0, 0),
    (0x9, 'WillOWispStrip1.png', 9, 1, 0, 0),
    (0xC, 'SmeltPotStrip.png', 4, 1, 0, 0),
    (0xD, 'goldBall.png', 1, 1, 0, 0),
    (0xE, 'MosoleumDebrisStrip.png', 10, 1, 0, 0),
    (0x91, 'Builder_Puzzle_04.png', 5, 1, 0, 0),
    (0x92, 'idol_states.png', 4, 1, 0, 0),
    (0x89, 'canopy.png', 1, 1, 0, 0),
    (0x8A, 'duststrip.png', 11, 1, 0, 0),
    (0x8B, 'lab_states.png', 2, 1, 0, 0),
    (0x8C, 'DoctorNecklacePiece.png', 1, 1, 0, 0),
    (0x8D, 'FarmerNecklacePiece.png', 1, 1, 0, 0),
    (0x8E, 'BuilderNecklacePiece.png', 1, 1, 0, 0),
    (0x8F, 'ScientistNecklacePiece.png', 1, 1, 0, 0),
    (0x90, 'CompletedNecklace.png', 1, 1, 0, 0),
    (0x12, 'transportersparkles3.png', 14, 1, 0, 0),
    (0x13, 'lightningstripwhite.png', 7, 1, 0, 0),
    (0x30, 'RisingLightRays.png', 7, 1, 0, 0),
    (0x14, 'IdolCoverings.png', 2, 1, 0, 0),
    (0x15, 'ResearchTotemStrip.png', 3, 1, 0, 0),
    (0x16, 'BuildingTotemStrip.png', 3, 1, 0, 0),
    (0x17, 'MedicineTotemStrip.png', 3, 1, 0, 0),
    (0x18, 'FoodTotemStrip.png', 3, 1, 0, 0),
    (0x19, 'ClosedEyeTotemStrip.png', 2, 1, 0, 0),
    (0x2C, 'safezone.png', 4, 1, 0, 0),
    (0x2D, 'willowispstripsml2.png', 16, 1, 0, 0),
    (0x2E, 'BlinkyEyes.png', 1, 1, 0, 0),
    (0x2F, 'BlinkyEyesSm.png', 1, 1, 0, 0),
    (0x1A, 'ChildrensTotemStrip.png', 3, 1, 0, 0),
    (0x1B, 'hovel_cover.png', 1, 1, 0, 0),
    (0x1C, 'RainbowTotemStrip.png', 3, 1, 0, 0),
    (0x1D, 'BluePaintBucket.png', 1, 1, 0, 0),
    (0x1E, 'RedPaintBucket.png', 1, 1, 0, 0),
    (0x1F, 'YellowPaintBucket.png', 1, 1, 0, 0),
    (0x20, 'topPoolRed.png', 1, 1, 0, 0),
    (0x21, 'topPoolBlue.png', 1, 1, 0, 0),
    (0x22, 'topPoolYellow.png', 1, 1, 0, 0),
    (0x23, 'topPoolPurple.png', 1, 1, 0, 0),
    (0x24, 'topPoolGreen.png', 1, 1, 0, 0),
    (0x25, 'topPoolOrange.png', 1, 1, 0, 0),
    (0x26, 'topPoolBrown.png', 1, 1, 0, 0),
    (0x93, 'InvertedLightBeam.png', 1, 1, 0, 0),
    (0x94, 'invertedLightBeamSingleCenter.png', 1, 1, 0, 0),
    (0x27, 'ProofCompleteCrappy.png', 1, 1, 0, 0),
    (0x28, 'ProofCompleteGood.png', 1, 1, 0, 0),
    (0x29, 'ProofPartialCrappy.png', 1, 1, 0, 0),
    (0x2A, 'ProofPartialGood.png', 1, 1, 0, 0),
    (0x2B, 'ProofDisapprove.png', 1, 1, 0, 0),
    (0x31, 'leaf_grid.png', 1, 2, 0, 0),
    (0x32, 'collectables_small_decal.png', 12, 4, 0, 0),
    (0x33, 'focusWindowMask.png', 1, 1, 0, 0),
    (0x34, 'focus_window_lens.png', 0, 0, 0, 0),
    (0x4B, 'blackberry.png', 1, 1, 0, 0),
    (0x48, 'btn_done.png', 3, 0, 0, 0),
    (0x43, 'btn_CollectionsDone.png', 3, 0, 0, 0),
    (0x42, 'fishpile1.png', 1, 1, 0, 0),
    (0x4E, 'Tech_colorcarving_slice1.png', 1, 1, 0, 0),
    (0x4F, 'Tech_colorcarving_slice2.png', 1, 1, 0, 0),
    (0x50, 'Tech_colorcarving_slice3.png', 1, 1, 0, 0),
    (0x51, 'Tech_colorcarving_slice4.png', 1, 1, 0, 0),
    (0x52, 'Tech_colorcarving_slice5.png', 1, 1, 0, 0),
    (0x53, 'Tech_colorcarving_slice6.png', 1, 1, 0, 0),
    (0x35, 'mausoleum_ui_bg.jpg', 0, 0, 0, 0),
    (0x36, 'mausoleum_ui_top.png', 0, 0, 0, 0),
    (0x37, 'mausoleum_ui_btm.png', 0, 0, 0, 0),
    (0x38, 'mausoleum_row.png', 0, 0, 0, 0),
    (0x39, 'mausoleum_knob_top.png', 0, 0, 0, 0),
    (0x3A, 'mausoleum_knob_mid.png', 0, 0, 0, 0),
    (0x3B, 'mausoleum_knob_btm.png', 0, 0, 0, 0),
    (0x3C, 'mausoleum_scroll_track.png', 0, 0, 0, 0),
    (0x3D, 'btn_arrow_up.png', 3, 1, 0, 0),
    (0x3E, 'btn_arrow_dwn.png', 3, 1, 0, 0),
    (0x3F, 'mausoleum_tint.png', 0, 0, 0, 0),
    (0x40, 'graves.png', 0, 0, 0, 0),
    (0x41, 'help_UI_BG.png', 0, 0, 0, 0),
    (0x4A, 'selectvillagers_UI_BG.jpg', 0, 0, 0, 0),
    (0x54, 'arrowup.png', 3, 1, 0, 0),
    (0x55, 'arrowdown.png', 3, 1, 0, 0),
    (0x56, 'btn_orange.png', 3, 0, 0, 0),
    (0x57, 'trophies_UI_BG.jpg', 0, 0, 0, 0),
    (0x58, 'trophy_scrollknob_top.png', 0, 0, 0, 0),
    (0x59, 'trophy_scrollknob_mid.png', 0, 0, 0, 0),
    (0x5A, 'trophy_scrollknob_btm.png', 0, 0, 0, 0),
    (0x5B, 'trophy_ui_top.png', 0, 0, 0, 0),
    (0x5C, 'trophy_ui_btm.png', 0, 0, 0, 0),
    (0x5D, 'trophy_star.png', 0, 0, 0, 0),
    (0x5E, 'trophy_row.png', 0, 0, 0, 0),
    (0x5F, 'trophybar_back.png', 0, 0, 0, 0),
    (0x60, 'trophybar_front.png', 0, 0, 0, 0),
    (0x61, 'btn_trophyarrow_up.png', 3, 1, 0, 0),
    (0x62, 'btn_trophyarrow_down.png', 3, 1, 0, 0),
    (0x63, 'butterflygreen.png', 4, 5, 0, 0),
    (0x64, 'main_wide_button2.png', 3, 0, 0, 0),
    (0x65, 'ultra_wide_button.png', 3, 0, 0, 0),
    (0x66, 'btn_detail.png', 3, 0, 0, 0),
    (0x67, 'btn_arrowl.png', 3, 0, 0, 0),
    (0x68, 'btn_arrowr.png', 3, 0, 0, 0),
    (0x44, 'btn_arrow_lt.png', 3, 0, 0, 0),
    (0x45, 'btn_arrow_rt.png', 3, 0, 0, 0),
    (0x46, 'btn_help_arrowl.png', 3, 0, 0, 0),
    (0x47, 'btn_help_arrowr.png', 3, 0, 0, 0),
    (0x49, 'btn_creditsHelp.png', 3, 0, 0, 0),
    (0x69, 'btn_collections.png', 3, 0, 0, 0),
    (0x6A, 'btn_trophies.png', 3, 0, 0, 0),
    (0x6B, 'btn_puzzle.png', 3, 0, 0, 0),
    (0x6C, 'btn_map.png', 3, 0, 0, 0),
    (0x6D, 'btn_tech.png', 3, 0, 0, 0),
    (0x6E, 'btn_menu.png', 3, 0, 0, 0),
    (0x6F, 'btn_mainmenu_change.png', 3, 0, 0, 0),
    (0x70, 'btn_mainmenu_help.png', 3, 0, 0, 0),
    (0x71, 'btn_mainmenu_options.png', 3, 0, 0, 0),
    (0x72, 'btn_mainmenu_play.png', 3, 0, 0, 0),
    (0x73, 'btn_mainmenu_quit.png', 3, 0, 0, 0),
    (0x74, 'btn_mainmenu_startover.png', 3, 0, 0, 0),
    (0x75, 'popup_button1.png', 3, 0, 0, 0),
    (0x76, 'OrangeDlgTileGrid.png', 9, 1, 0, 0),
    (0x77, 'GreenDlgTileGrid.png', 9, 1, 0, 0),
    (0x78, 'leftarrow.png', 3, 0, 0, 0),
    (0x79, 'rightarrow.png', 3, 0, 0, 0),
    (0x7A, 'radiobuttonstrip.png', 2, 0, 0, 0),
    (0x7B, 'radioblank.png', 0, 0, 0, 0),
    (0x7C, 'radioselected.png', 0, 0, 0, 0),
    (0x7D, 'CheckboxStrip.png', 2, 0, 0, 0),
    (0x7E, 'checkmark.png', 0, 0, 0, 0),
    (0x7F, 'WideSlider2.png', 0, 0, 0, 0),
    (0x80, 'sliderhandle.png', 0, 0, 0, 0),
    (0x81, 'UpArrowButton.png', 3, 0, 0, 0),
    (0x82, 'DownArrowButton.png', 3, 0, 0, 0),
    (0x83, 'VerticalScrollTrack.png', 0, 0, 0, 0),
    (0x84, 'VerticalScrollKnob.png', 0, 0, 0, 0),
    (0x85, 'BambooMeterFrame1.png', 1, 0, 0, 0),
    (0x86, 'StatusBarSliceB.png', 0, 0, 0, 0),
    (0x87, 'StatusBarSliceR.png', 0, 0, 0, 0),
    (0x88, 'blueStatusBarGlow.png', 0, 0, 0, 0),
    (0x95, 'healthBarbulb.png', 0, 0, 0, 0),
    (0x96, 'LoadColor.png', 0, 0, 0, 0),
    (0x97, 'focus_circle.png', 0, 0, 0, 0),
    (0x98, 'overview_bg.jpg', 0, 0, 0, 0),
    (0x99, 'map_cloud01.png', 0, 0, 0, 0),
    (0x9A, 'cloud variations1.png', 0, 0, 0, 0),
    (0x9B, 'cloud variations2.png', 0, 0, 0, 0),
    (0x9C, 'cloud variations3.png', 0, 0, 0, 0),
    (0x9D, 'dark_cloud1.png', 0, 0, 0, 0),
    (0x9E, 'dark_cloud2.png', 0, 0, 0, 0),
    (0x9F, 'loading.jpg', 0, 0, 0, 0),
    (0xA0, 'ldwLogo.png', 0, 0, 0, 0),
    (0xA1, 'logo1.png', 0, 0, 0, 0),
    (0xA2, 'small_logo.png', 1, 1, 0, 0),
    (0xA3, 'image1_page1.jpg', 1, 1, 0, 0),
    (0xA4, 'image1_page2.jpg', 1, 1, 0, 0),
    (0xA5, 'image1_page3.jpg', 1, 1, 0, 0),
    (0xA6, 'intro_page5.jpg', 1, 1, 0, 0),
    (0xA7, 'intro_page5_masks.png', 1, 1, 0, 0),
    (0xA8, 'midgame_page1.jpg', 1, 1, 0, 0),
    (0xA9, 'midgame_page2.jpg', 1, 1, 0, 0),
    (0xAA, 'midgame_page3.jpg', 1, 1, 0, 0),
    (0xAB, 'midgame_page4.jpg', 1, 1, 0, 0),
    (0xAC, 'midgame_page5.jpg', 1, 1, 0, 0),
    (0xAD, 'end1.jpg', 1, 1, 0, 0),
    (0xAE, 'end2.jpg', 1, 1, 0, 0),
    (0xAF, 'end3.jpg', 1, 1, 0, 0),
    (0xB0, 'main_UI_BG_1024.png', 0, 0, 0, 0),
    (0xB1, 'main_UI_Top_1024.png', 0, 0, 0, 0),
    (0xB2, 'puzzles_bg.jpg', 0, 0, 0, 0),
    (0xB4, 'help1.png', 0, 0, 0, 0),
    (0xB5, 'help2.png', 0, 0, 0, 0),
    (0xB6, 'help3.png', 0, 0, 0, 0),
    (0xB7, 'help4.png', 0, 0, 0, 0),
    (0xB8, 'credits.png', 0, 0, 0, 0),
    (0xB9, 'mainmenu.jpg', 0, 0, 0, 0),
    (0xBA, 'empty1.png', 3, 0, 0, 0),
    (0xBB, 'arrowglow.png', 0, 0, 0, 0),
    (0xBC, 'arrowglowdown.png', 0, 0, 0, 0),
    (0xBD, 'arrowleftglow.png', 0, 0, 0, 0),
    (0xBE, 'arrowrightglow.png', 0, 0, 0, 0),
    (0xBF, 'puzzle_covers.png', 4, 4, 0, 0),
    (0xC0, 'collection_UI_BG.jpg', 0, 0, 0, 0),
    (0xC1, 'collecting_fishscales_collectionscreen.png', 4, 3, 0, 0),
    (0xC2, 'collecting_lab_collectionscreen.png', 4, 3, 0, 0),
    (0xC3, 'collecting_mausoleum_collectionscreen.png', 4, 3, 0, 0),
    (0xC4, 'collecting_flutetops_collectionscreen.png', 4, 3, 0, 0),
    (0xC5, 'Tech_UI_BG.jpg', 0, 0, 0, 0),
    (0xC6, 'science_bar.jpg', 3, 1, 0, 0),
    (0xC7, 'medicine_bar.jpg', 3, 1, 0, 0),
    (0xC8, 'learning_bar.jpg', 3, 1, 0, 0),
    (0xC9, 'restoration_bar.jpg', 3, 1, 0, 0),
    (0xCA, 'foodmastery_bar.jpg', 3, 1, 0, 0),
    (0xCB, 'evangelism_bar.jpg', 3, 1, 0, 0),
    (0xCC, 'btn_tech_buy.png', 3, 1, 0, 0),
    (0xCD, 'btn_tech_question.png', 3, 1, 0, 0),
    (0xCE, 'faith_meter_details_top.png', 1, 1, 0, 0),
    (0xCF, 'god_power_icons-techscreen_on.png', 11, 1, 0, 0),
    (0xD0, 'god_power_icons-techscreen_off.png', 11, 1, 0, 0),
    (0xD1, 'god_power_icons-techscreen_bckgrnd.png', 0, 0, 0, 0),
    (0xD2, 'god_power_icons-techscreen_top.png', 0, 0, 0, 0),
    (0xD3, 'VD_BG_2.jpg', 0, 0, 0, 0),
    (0xD4, 'hospital_states.png', 1, 2, 0, 0),
    (0xD5, 'map_foodbin.png', 5, 1, 0, 0),
    (0xD6, 'GranaryStagesStrip.png', 4, 1, 0, 0),
    (0xD7, 'blinkEyesMaskStrip.png', 6, 1, 0, 0),
    (0xD8, 'blinkEyesMaskStripSm.png', 6, 1, 0, 0),
    (0xD9, 'waves_proto.png', 10, 1, 0, 0),
    (0xDA, 'yellow_sparkle.png', 10, 1, 0, 0),
    (0xDB, 'sparklestrip2.png', 10, 1, 0, 0),
    (0xDC, 'sparklestrip.png', 10, 1, 0, 0),
    (0xDD, 'dust2.png', 9, 1, 0, 0),
    (0xDE, 'algae.png', 4, 4, 0, 0),
    (0xDF, 'rainbow.png', 10, 1, 0, 0),
    (0xE0, 'bubble.png', 10, 1, 0, 0),
    (0xE1, 'candlestrip.png', 9, 1, 0, 0),
    (0xE2, 'frogstrip1.png', 13, 1, 0, 0),
    (0xE3, 'frogstrip2.png', 13, 1, 0, 0),
    (0xE4, 'firestrip.png', 4, 2, 0, 0),
    (0xE5, 'petalstrip.png', 12, 3, 0, 0),
    (0xE6, 'leafstrip.png', 9, 5, 0, 0),
    (0xE7, 'foam.png', 4, 2, 0, 0),
    (0xE8, 'carrying.png', 13, 7, 0, 0),
    (0xE9, 'spray.png', 12, 1, 0, 0),
    (0xEA, 'sharp_sparkle.png', 10, 1, 0, 0),
    (0xEB, 'blurry_sparkle.png', 10, 1, 0, 0),
    (0xEC, 'collectables_small.png', 6, 9, 0, 0),
    (0xED, 'footprints.png', 15, 1, 0, 0),
    (0xEE, 'raindrops.png', 3, 1, 0, 0),
    (0xEF, 'smokestriplight.png', 12, 1, 0, 0),
    (0xF0, 'smokestripdark.png', 12, 1, 0, 0),
    (0xF1, 'beestriplarge_final2.png', 14, 2, 0, 0),
    (0xF2, 'fishflop.png', 15, 1, 0, 0),
    (0xF3, 'bubblestrip.png', 9, 1, 0, 0),
    (0xF4, 'amppuddle.png', 1, 1, 0, 0),
    (0xF5, 'woodpile.png', 1, 1, 0, 0),
    (0xF6, 'scaffolding.png', 1, 1, 0, 0),
    (0xF7, 'graves.png', 4, 1, 0, 0),
    (0xF8, 'firestrip.png', 4, 2, 0, 0),
    (0xF9, 'female_heads', 16, 30, 2, 1),
    (0xFA, 'female_bodies', 32, 30, 2, 3),
    (0xFB, 'female_actions', 17, 30, 1, 3),
    (0xFC, 'male_heads', 16, 30, 2, 1),
    (0xFD, 'male_bodies', 32, 30, 2, 3),
    (0xFE, 'male_actions', 17, 30, 1, 3),
    (0xFF, 'bigheads', 12, 30, 2, 1),
    (0x100, 'bigbodies.png', 2, 30, 0, 0),
    (0x101, 'vv5_heathenheads.png', 8, 5, 0, 0),
    (0x102, 'peep_shadow1.png', 0, 0, 0, 0),
    (0x103, 'skelly.png', 4, 1, 0, 0),
    (0x104, 'ripple.png', 4, 1, 0, 0),
    (0x105, 'sunbeam.png', 0, 0, 0, 0),
    (0x106, 'map_fog.png', 0, 0, 0, 0),
    (0x107, 'hut_states.png', 2, 2, 0, 0),
    (0x108, 'clothinghut_states.png', 2, 3, 0, 0),
    (0x109, 'loveshack_states.png', 2, 3, 0, 0),
    (0x10A, 'nurseryhut_states.png', 2, 3, 0, 0),
    (0x10B, 'hospital_states.png', 1, 2, 0, 0),
    (0x10C, 'bird.png', 12, 1, 0, 0),
    (0x10D, 'bird_shadow.png', 1, 1, 0, 0),
    (0x10E, 'dragonflies.png', 6, 4, 0, 0),
    (0x10F, 'hummingbirdstrip.png', 4, 2, 0, 0),
    (0x110, 'rockslidestrip.png', 14, 1, 0, 0),
    (0x111, 'rockslidesmall2_strip.png', 14, 1, 0, 0),
    (0x112, '01-duct-totallydestroyed.png', 1, 1, 0, 0),
    (0x113, '02-duct-partially-fixed.png', 1, 1, 0, 0),
    (0x114, '03-duct-mostly-fixed.png', 1, 1, 0, 0),
    (0x115, 'field_alive.png', 1, 1, 0, 0),
    (0x116, 'field_dead.png', 1, 1, 0, 0),
    (0x117, 'crops.png', 1, 1, 0, 0),
    (0x118, 'lake_puddles.jpg', 1, 1, 0, 0),
    (0x119, 'lake_full.jpg', 1, 1, 0, 0),
    (0x11A, 'fishstrip1.png', 9, 1, 0, 0),
    (0x11B, 'fishstrip2.png', 9, 1, 0, 0),
    (0x11C, 'pollen_clump.png', 0, 0, 0, 0),
    (0x11D, 'Top-Waterfall.png', 30, 1, 0, 0),
    (0x11E, 'Mid-Waterfall.png', 30, 1, 0, 0),
    (0x11F, 'Bottom-Waterfall.png', 30, 1, 0, 0),
    (0x120, 'Bridge-Water.png', 30, 1, 0, 0),
    (0x121, 'collectables_01.png', 1, 1, 0, 0),
    (0x122, 'collectables_02.png', 1, 1, 0, 0),
    (0x123, 'collectables_03.png', 1, 1, 0, 0),
    (0x124, 'collectables_04.png', 1, 1, 0, 0),
    (0x125, 'collectables_05.png', 1, 1, 0, 0),
    (0x126, 'collectables_06.png', 1, 1, 0, 0),
    (0x127, 'collectables_07.png', 1, 1, 0, 0),
    (0x128, 'collectables_08.png', 1, 1, 0, 0),
    (0x129, 'collectables_09.png', 1, 1, 0, 0),
    (0x12A, 'collectables_10.png', 1, 1, 0, 0),
    (0x12B, 'collectables_11.png', 1, 1, 0, 0),
    (0x12C, 'collectables_12.png', 1, 1, 0, 0),
    (0x12D, 'collectables_13.png', 1, 1, 0, 0),
    (0x12E, 'collectables_14.png', 1, 1, 0, 0),
    (0x12F, 'collectables_15.png', 1, 1, 0, 0),
    (0x130, 'collectables_16.png', 1, 1, 0, 0),
    (0x131, 'collectables_17.png', 1, 1, 0, 0),
    (0x132, 'collectables_18.png', 1, 1, 0, 0),
    (0x133, 'collectables_19.png', 1, 1, 0, 0),
    (0x134, 'collectables_20.png', 1, 1, 0, 0),
    (0x135, 'collectables_21.png', 1, 1, 0, 0),
    (0x136, 'collectables_22.png', 1, 1, 0, 0),
    (0x137, 'collectables_23.png', 1, 1, 0, 0),
    (0x138, 'collectables_24.png', 1, 1, 0, 0),
    (0x139, 'collectables_25.png', 1, 1, 0, 0),
    (0x13A, 'collectables_26.png', 1, 1, 0, 0),
    (0x13B, 'collectables_27.png', 1, 1, 0, 0),
    (0x13C, 'collectables_28.png', 1, 1, 0, 0),
    (0x13D, 'collectables_29.png', 1, 1, 0, 0),
    (0x13E, 'collectables_30.png', 1, 1, 0, 0),
    (0x13F, 'collectables_31.png', 1, 1, 0, 0),
    (0x140, 'collectables_32.png', 1, 1, 0, 0),
    (0x141, 'collectables_33.png', 1, 1, 0, 0),
    (0x142, 'collectables_34.png', 1, 1, 0, 0),
    (0x143, 'collectables_35.png', 1, 1, 0, 0),
    (0x144, 'collectables_36.png', 1, 1, 0, 0),
    (0x145, 'collectables_37.png', 1, 1, 0, 0),
    (0x146, 'collectables_38.png', 1, 1, 0, 0),
    (0x147, 'collectables_39.png', 1, 1, 0, 0),
    (0x148, 'collectables_40.png', 1, 1, 0, 0),
    (0x149, 'collectables_41.png', 1, 1, 0, 0),
    (0x14A, 'collectables_42.png', 1, 1, 0, 0),
    (0x14B, 'collectables_43.png', 1, 1, 0, 0),
    (0x14C, 'collectables_44.png', 1, 1, 0, 0),
    (0x14D, 'collectables_45.png', 1, 1, 0, 0),
    (0x14E, 'collectables_46.png', 1, 1, 0, 0),
    (0x14F, 'collectables_47.png', 1, 1, 0, 0),
    (0x150, 'collectables_48.png', 1, 1, 0, 0),
    (0x151, 'necklace_01.png', 1, 1, 0, 0),
    (0x152, 'necklace_02.png', 1, 1, 0, 0),
    (0x153, 'necklace_03.png', 1, 1, 0, 0),
    (0x154, 'necklace_04.png', 1, 1, 0, 0),
    (0x155, 'eye.png', 0, 0, 0, 0),
    (0x156, 'pupil.png', 0, 0, 0, 0),
    (0x157, 'puzzle_bonus_notsolved.png', 0, 0, 0, 0),
    (0x158, 'puzzle_bonus_solved.PNG', 0, 0, 0, 0),
)
GRID_SUFFIX = ".png"           # the one suffix the table holds (0x4CEFB8 records 0xF9-0xFF)

# Sprites built outside the table: (name, columns, rows, where); columns 0 is a whole picture.
DIRECT = (
    ("puzzles_bg.jpg", 0, 0, "0x448ABF"),
    ("puzzle_covers.png", 4, 4, "0x448AF4"),
    ("SPLASH_BG.JPG", 0, 0, "0x449964"),
)
MAP_TILES = tuple((x, y) for x in range(5) for y in range(5))        # the loader's order (X outer, Y inner)
MAP_PREFIX = "LargeMap"                                                # [0x4D96B4]
TILE = 512


def map_tile(x: int, y: int) -> str:
    return f"{MAP_PREFIX}{x}X{y}Y.jpg"


# The fonts (0x41E874 / 0x41E8E4): glyph tables 0x4C7FE0 / 0x4C8F08, records (code, left, 0, right, height).
_ARIAL_GLYPHS = (  # (code, left, right) x 190
    33, 0, 5, 34, 5, 14, 35, 14, 24, 36, 24, 34, 37, 34, 51, 38, 51, 64, 39, 64, 68, 40, 68, 74, 41, 74, 80, 42, 80,
    87, 43, 87, 98, 44, 98, 103, 45, 103, 109, 46, 109, 114, 47, 114, 119, 48, 119, 129, 49, 129, 139, 50, 139, 149,
    51, 149, 159, 52, 159, 169, 53, 169, 179, 54, 179, 189, 55, 189, 199, 56, 199, 209, 57, 209, 219, 58, 219, 226,
    59, 226, 233, 60, 233, 244, 61, 244, 255, 62, 255, 266, 63, 266, 277, 64, 277, 295, 65, 295, 308, 66, 308, 321,
    67, 321, 334, 68, 334, 347, 69, 347, 359, 70, 359, 370, 71, 370, 384, 72, 384, 397, 73, 397, 402, 74, 402, 412,
    75, 412, 425, 76, 425, 436, 77, 436, 451, 78, 451, 464, 79, 464, 478, 80, 478, 490, 81, 490, 504, 82, 504, 517,
    83, 517, 529, 84, 529, 540, 85, 540, 553, 86, 553, 566, 87, 566, 583, 88, 583, 595, 89, 595, 608, 90, 608, 618,
    91, 618, 619, 92, 619, 624, 93, 624, 630, 94, 630, 641, 95, 641, 651, 96, 651, 657, 97, 657, 667, 98, 667, 678,
    99, 678, 688, 100, 688, 699, 101, 699, 710, 102, 710, 716, 103, 716, 727, 104, 727, 738, 105, 738, 743, 106,
    743, 748, 107, 748, 758, 108, 758, 763, 109, 763, 780, 110, 780, 791, 111, 791, 802, 112, 802, 813, 113, 813,
    824, 114, 824, 831, 115, 831, 841, 116, 841, 847, 117, 847, 858, 118, 858, 869, 119, 869, 884, 120, 884, 895,
    121, 895, 906, 122, 906, 915, 123, 915, 919, 124, 919, 923, 125, 923, 930, 126, 930, 941, 32, 941, 946, -95,
    955, 960, -94, 960, 970, -93, 970, 980, -92, 980, 990, -91, 990, 1000, -90, 1000, 1004, -89, 1004, 1014, -88,
    1014, 1020, -87, 1020, 1033, -86, 1033, 1040, -85, 1040, 1050, -84, 1050, 1061, -83, 1061, 1067, -82, 1067,
    1080, -81, 1080, 1090, -80, 1090, 1097, -79, 1097, 1107, -78, 1107, 1113, -77, 1113, 1119, -76, 1119, 1125, -75,
    1125, 1135, -74, 1135, 1145, -73, 1145, 1150, -72, 1150, 1156, -71, 1156, 1162, -70, 1162, 1169, -69, 1169,
    1179, -68, 1179, 1194, -67, 1194, 1209, -66, 1209, 1224, -65, 1224, 1235, -64, 1235, 1248, -63, 1248, 1261, -62,
    1261, 1274, -61, 1274, 1287, -60, 1287, 1300, -59, 1300, 1313, -58, 1313, 1331, -57, 1331, 1344, -56, 1344,
    1356, -55, 1356, 1368, -54, 1368, 1380, -53, 1380, 1392, -52, 1392, 1397, -51, 1397, 1402, -50, 1402, 1407, -49,
    1407, 1412, -48, 1412, 1425, -47, 1425, 1438, -46, 1438, 1452, -45, 1452, 1466, -44, 1466, 1480, -43, 1480,
    1494, -42, 1494, 1508, -41, 1508, 1519, -40, 1519, 1533, -39, 1533, 1546, -38, 1546, 1559, -37, 1559, 1572, -36,
    1572, 1585, -35, 1585, 1597, -34, 1597, 1609, -33, 1609, 1621, -32, 1621, 1631, -31, 1631, 1641, -30, 1641,
    1651, -29, 1651, 1661, -28, 1661, 1671, -27, 1671, 1681, -26, 1681, 1697, -25, 1697, 1707, -24, 1707, 1717, -23,
    1717, 1727, -22, 1727, 1737, -21, 1737, 1747, -20, 1747, 1752, -19, 1752, 1757, -18, 1757, 1762, -17, 1762,
    1767, -16, 1767, 1778, -15, 1778, 1789, -14, 1789, 1800, -13, 1800, 1811, -12, 1811, 1822, -11, 1822, 1833, -10,
    1833, 1844, -9, 1844, 1854, -8, 1854, 1865, -7, 1865, 1876, -6, 1876, 1887, -5, 1887, 1898, -4, 1898, 1909, -3,
    1909, 1919, -2, 1919, 1930, -1, 1930, 1940)

_BURWEED_GLYPHS = (  # (code, left, right) x 190
    33, 0, 7, 34, 7, 14, 35, 14, 27, 36, 27, 37, 37, 37, 53, 38, 53, 69, 39, 69, 73, 40, 73, 81, 41, 81, 89, 42, 89,
    99, 43, 99, 114, 44, 114, 121, 45, 121, 129, 46, 129, 133, 47, 133, 145, 48, 145, 157, 49, 157, 165, 50, 165,
    177, 51, 177, 187, 52, 187, 200, 53, 200, 211, 54, 211, 223, 55, 223, 235, 56, 235, 246, 57, 246, 257, 58, 257,
    261, 59, 261, 268, 60, 268, 281, 61, 281, 295, 62, 295, 308, 63, 308, 318, 64, 318, 336, 65, 336, 353, 66, 353,
    366, 67, 366, 379, 68, 379, 392, 69, 392, 404, 70, 404, 416, 71, 416, 430, 72, 430, 446, 73, 446, 454, 74, 454,
    464, 75, 464, 478, 76, 478, 491, 77, 491, 513, 78, 513, 530, 79, 530, 543, 80, 543, 557, 81, 557, 572, 82, 572,
    588, 83, 588, 600, 84, 600, 616, 85, 616, 632, 86, 632, 651, 87, 651, 676, 88, 676, 692, 89, 692, 708, 90, 708,
    724, 91, 724, 734, 92, 734, 744, 93, 744, 754, 94, 754, 770, 95, 770, 784, 96, 784, 794, 97, 794, 805, 98, 805,
    818, 99, 818, 828, 100, 828, 841, 101, 841, 853, 102, 853, 862, 103, 862, 874, 104, 874, 886, 105, 886, 892,
    106, 892, 900, 107, 900, 912, 108, 912, 918, 109, 918, 940, 110, 940, 954, 111, 954, 965, 112, 965, 978, 113,
    2364, 2378, 114, 987, 997, 115, 997, 1006, 116, 1006, 1016, 117, 1016, 1031, 118, 1031, 1047, 119, 1047, 1071,
    120, 1071, 1084, 121, 1084, 1101, 122, 1101, 1113, 123, 1113, 1121, 124, 1121, 1129, 125, 1129, 1137, 126, 1137,
    1152, 32, 1152, 1159, -95, 1166, 1173, -94, 1173, 1183, -93, 1183, 1195, -92, 1195, 1207, -91, 1207, 1223, -90,
    1223, 1231, -89, 1231, 1242, -88, 1242, 1252, -87, 1252, 1268, -86, 1268, 1275, -85, 1275, 1287, -84, 1287,
    1302, -83, 1302, 1315, -82, 1315, 1331, -81, 1331, 1341, -80, 1341, 1349, -79, 1349, 1362, -78, 1362, 1371, -77,
    1371, 1379, -76, 1379, 1389, -75, 1389, 1404, -74, 1404, 1418, -73, 1418, 1422, -72, 1422, 1432, -71, 1432,
    1438, -70, 1438, 1445, -69, 1445, 1457, -68, 1457, 1475, -67, 1475, 1494, -66, 1494, 1513, -65, 1513, 1523, -64,
    1523, 1541, -63, 1541, 1559, -62, 1559, 1577, -61, 1577, 1595, -60, 1595, 1613, -59, 1613, 1631, -58, 1631,
    1653, -57, 1653, 1666, -56, 1666, 1678, -55, 1678, 1690, -54, 1690, 1702, -53, 1702, 1714, -52, 1714, 1722, -51,
    1722, 1730, -50, 1730, 1738, -49, 1738, 1746, -48, 1746, 1762, -47, 1762, 1779, -46, 1779, 1792, -45, 1792,
    1805, -44, 1805, 1818, -43, 1818, 1831, -42, 1831, 1844, -41, 1844, 1859, -40, 1859, 1873, -39, 1873, 1889, -38,
    1889, 1905, -37, 1905, 1921, -36, 1921, 1937, -35, 1937, 1953, -34, 1953, 1967, -33, 1967, 1979, -32, 1979,
    1990, -31, 1990, 2001, -30, 2001, 2012, -29, 2012, 2023, -28, 2023, 2034, -27, 2034, 2045, -26, 2045, 2062, -25,
    2062, 2072, -24, 2072, 2084, -23, 2084, 2096, -22, 2096, 2108, -21, 2108, 2120, -20, 2120, 2126, -19, 2126,
    2132, -18, 2132, 2138, -17, 2138, 2144, -16, 2144, 2157, -15, 2157, 2171, -14, 2171, 2183, -13, 2183, 2195, -12,
    2195, 2207, -11, 2207, 2219, -10, 2219, 2231, -9, 2231, 2245, -8, 2245, 2257, -7, 2257, 2272, -6, 2272, 2287,
    -5, 2287, 2302, -4, 2302, 2317, -3, 2317, 2334, -2, 2334, 2347, -1, 2347, 2364)
FONTS_TABLE = (("ldwarialbold.png", "Arial bold", 20, "0x4C7FE0"), ("ldwBurweed27.png", "Burweed", 27, "0x4C8F08"))


def font_glyphs(which: int) -> list[tuple[int, int, int]]:
    flat = (_ARIAL_GLYPHS, _BURWEED_GLYPHS)[which]
    return [tuple(flat[k:k + 3]) for k in range(0, len(flat), 3)]


# Pictures in the game's Images folder whose names the executable never holds or builds (see the test).
UNUSED_FILES = (
    "FaithGradientArc.png", "FaithGradientBar.png", "MS_Button_01.png", "MS_Button_02.png", "MS_Button_03.png",
    "MS_Button_04.png", "break.png", "break1.png", "btn_check.png", "buy_button.png", "click.png", "cloud_puff.png",
    "crabstrip1.png", "crabstrip2.png", "cutting_tool.png", "graveflowers.png", "growth.png", "help_label_1.png",
    "help_label_2.png", "help_label_3.png", "help_label_4.png", "hole-closed.png", "light-beams.png",
    "main_UI_BG.png", "map_hospitalStates.png", "mausoleum_urn.png", "reefFish1.png", "reefFish2.png",
    "reefFish3.png", "ruinsRubble.png", "selectvillager.png", "undertoe.png", "verticalslidertrack.png",
    "vv5_heathenheads06.png", "willowisp1.png",
)


def descriptor(ident: int):
    for rec in DESCRIPTORS:
        if rec[0] == ident:
            return rec
    raise KeyError(hex(ident))


def spec_of(rec) -> SheetSpec | None:
    """The sprite the getter 0x44FA40 builds from a table record."""
    ident, name, cols, rows, across, down = rec
    where = f"sprite 0x{ident:X}"
    if ident == 0:
        return None                                           # "No Graphic"
    if rows > 0 and across:
        return SheetSpec(name, cols, rows, (across, down), GRID_SUFFIX, where=where + " (grid 0x40B0A0)")
    if rows > 0:
        if cols * rows == 1:
            return SheetSpec(name, 1, 1, where=where + " (0x40B010, 1 x 1)")
        return SheetSpec(name, cols, rows, where=where + " (0x40B010)")
    if cols > 0:
        if cols == 1:
            return SheetSpec(name, 1, 1, where=where + " (strip 0x401000, 1 frame)")
        return SheetSpec(name, cols, 1, where=where + " (strip 0x401000)")
    return SheetSpec(name, whole=True, where=where + " (whole 0x40AD50)")


def geometry(rec) -> tuple[int, int, tuple]:
    """(columns, rows, sheets) the record's sprite is cut into (1, 1, (1, 1) for a whole picture)."""
    spec = spec_of(rec)
    if spec is None or spec.whole:
        return 1, 1, (1, 1)
    return spec.cols, spec.rows, tuple(spec.sheets)


def sheet_table() -> list[SheetSpec]:
    """Every sprite the stock executable constructs: the table's records (one per distinct picture and cut),
    the sprites built outside it, the map tiles and the fonts."""
    merged: dict[tuple, list] = {}
    for rec in DESCRIPTORS:
        spec = spec_of(rec)
        if spec is None:
            continue
        key = (spec.name.casefold(), spec.cols, spec.rows, tuple(spec.sheets), spec.whole)
        merged.setdefault(key, [spec, []])[1].append(spec.where)
    for name, cols, rows, where in DIRECT:
        spec = (SheetSpec(name, whole=True, where=where) if cols == 0 else SheetSpec(name, cols, rows, where=where))
        key = (name.casefold(), spec.cols, spec.rows, tuple(spec.sheets), spec.whole)
        merged.setdefault(key, [spec, []])[1].append(where)
    out = []
    for spec, wheres in merged.values():
        out.append(SheetSpec(spec.name, spec.cols, spec.rows, tuple(spec.sheets), spec.suffix, spec.whole, True,
                             ", ".join(wheres)))
    for x, y in MAP_TILES:
        out.append(SheetSpec(map_tile(x, y), whole=True, where="0x47ABE0 (island map tile)"))
    for name, _label, _h, table in FONTS_TABLE:
        out.append(SheetSpec(name, whole=True, where=f"font 0x402360, glyphs {table}"))
    return out


def patcher_art() -> dict[str, Path]:
    """The patcher's own art for New Believers, by the name the Everything tab reads it under."""
    art = {"golden_mushroom.png": ROOT / "assets" / "golden_mushroom" / "golden_mushroom.png",
           "bigheads_masks.png": ROOT / "assets" / "vv5_bighead_masks" / "bigheads_masks.png"}
    for stem, _label in ORIGINS_ICONS:          # inside the shipped Origins companion (its largest image)
        where = va.origins_icon(GAME, int(stem[:3]))
        if where is not None:
            art[stem + ".png"] = where
    return art


ORIGINS_ICONS = (("101-time-warp", "Time Warp"), ("102-island-event", "Island Event"),
                 ("103-barrel-of-babies", "Barrel of Babies"), ("104-tech-point-doubler", "Tech Point Doubler"),
                 ("105-food-point-doubler", "Food Point Doubler"), ("106-grant-youth", "Grant Youth"),
                 ("107-grant-full-mastery", "Grant Full Mastery"), ("108-grant-running", "Grant Running"),
                 ("109-upgrade-checkmark", "Upgrade checkmark"), ("110-cure-all", "Cure All"))

# ------------------------------------------------------------------ what each sprite is (category, group, label)

_TOTEMS = {"researchtotemstrip.png": "Research Totem", "buildingtotemstrip.png": "Building Totem",
           "medicinetotemstrip.png": "Medicine Totem", "foodtotemstrip.png": "Food Totem",
           "closedeyetotemstrip.png": "The Blind Totem (closed eye)", "childrenstotemstrip.png": "Children's Totem",
           "rainbowtotemstrip.png": "Rainbow Totem"}
_KINDS = {
    CURSORS: ("hand_open.png", "hand.png"),
    ICONS: ("god_power_icons.png",),
    PLANTS: ("flowers.png", "blackberry.png", "crops.png", "field_alive.png", "field_dead.png",
             "stompped_shroom.png", "pollen_clump.png", "fishpile1.png", "leaf_grid.png"),
    METERS: ("StatusBarSliceG.png", "StatusBarSliceB.png", "StatusBarSliceR.png", "ManaBGBar.png",
             "FaithMeterBG.png", "BambooMeterFrame1.png", "blueStatusBarGlow.png", "healthBarbulb.png",
             "LoadColor.png", "faith_meter_details_top.png"),
    BUILDINGS: ("FirePlaceDecal.png", "SmeltPotStrip.png", "MosoleumDebrisStrip.png", "idol_states.png",
                "canopy.png", "lab_states.png", "IdolCoverings.png", "hovel_cover.png", "BluePaintBucket.png",
                "RedPaintBucket.png", "YellowPaintBucket.png", "topPoolRed.png", "topPoolBlue.png",
                "topPoolYellow.png", "topPoolPurple.png", "topPoolGreen.png", "topPoolOrange.png",
                "topPoolBrown.png", "hut_states.png", "clothinghut_states.png", "loveshack_states.png",
                "nurseryhut_states.png", "hospital_states.png", "map_foodbin.png", "GranaryStagesStrip.png",
                "scaffolding.png", "woodpile.png", "graves.png", "01-duct-totallydestroyed.png",
                "02-duct-partially-fixed.png", "03-duct-mostly-fixed.png", "Builder_Puzzle_04.png")
              + tuple(_TOTEMS),
    PUZZLES: ("DoctorNecklacePiece.png", "FarmerNecklacePiece.png", "BuilderNecklacePiece.png",
              "ScientistNecklacePiece.png", "CompletedNecklace.png", "ProofCompleteCrappy.png",
              "ProofCompleteGood.png", "ProofPartialCrappy.png", "ProofPartialGood.png", "ProofDisapprove.png",
              "puzzle_covers.png", "puzzle_bonus_notsolved.png", "puzzle_bonus_solved.PNG", "eye.png", "pupil.png",
              "necklace_01.png", "necklace_02.png", "necklace_03.png", "necklace_04.png", "goldBall.png",
              "BlinkyEyes.png", "BlinkyEyesSm.png", "blinkEyesMaskStrip.png", "blinkEyesMaskStripSm.png"),
    COLLECTIBLES: tuple(f"collectables_{k:02d}.png" for k in range(1, 49))
                  + ("collectables_small.png", "collectables_small_decal.png"),
    VILLAGERS: ("peep_shadow1.png", "skelly.png", "ripple.png", "vv5_heathenheads.png", "focus_circle.png",
                "carrying.png", "bigbodies.png"),
    CREATURES: ("butterflygreen.png", "bird.png", "bird_shadow.png", "dragonflies.png", "hummingbirdstrip.png",
                "frogstrip1.png", "frogstrip2.png", "fishstrip1.png", "fishstrip2.png", "fishflop.png",
                "beestriplarge_final2.png"),
    SCENE: ("lake_puddles.jpg", "lake_full.jpg", "Top-Waterfall.png", "Mid-Waterfall.png", "Bottom-Waterfall.png",
            "Bridge-Water.png", "waves_proto.png", "foam.png", "sunbeam.png", "map_fog.png", "map_cloud01.png",
            "cloud variations1.png", "cloud variations2.png", "cloud variations3.png", "dark_cloud1.png",
            "dark_cloud2.png", "rockslidestrip.png", "rockslidesmall2_strip.png", "algae.png", "overview_bg.jpg"),
    EFFECTS: ("spell_backing.png", "spell_front.png", "spell_area_160.png", "WillOWispStrip1.png",
              "willowispstripsml2.png", "duststrip.png", "transportersparkles3.png", "lightningstripwhite.png",
              "RisingLightRays.png", "InvertedLightBeam.png", "invertedLightBeamSingleCenter.png",
              "yellow_sparkle.png", "sparklestrip2.png", "sparklestrip.png", "dust2.png", "rainbow.png",
              "bubble.png", "candlestrip.png", "firestrip.png", "petalstrip.png", "leafstrip.png", "spray.png",
              "sharp_sparkle.png", "blurry_sparkle.png", "footprints.png", "raindrops.png", "smokestriplight.png",
              "smokestripdark.png", "bubblestrip.png", "amppuddle.png", "safezone.png"),
    TECH: ("Tech_UI_BG.jpg", "science_bar.jpg", "medicine_bar.jpg", "learning_bar.jpg", "restoration_bar.jpg",
           "foodmastery_bar.jpg", "evangelism_bar.jpg", "btn_tech_buy.png", "btn_tech_question.png",
           "god_power_icons-techscreen_on.png", "god_power_icons-techscreen_off.png",
           "god_power_icons-techscreen_bckgrnd.png", "god_power_icons-techscreen_top.png"),
    SCREENS: ("mausoleum_ui_bg.jpg", "selectvillagers_UI_BG.jpg", "trophies_UI_BG.jpg", "collection_UI_BG.jpg",
              "VD_BG_2.jpg", "loading.jpg", "ldwLogo.png", "logo1.png", "image1_page1.jpg", "image1_page2.jpg",
              "image1_page3.jpg", "intro_page5.jpg", "intro_page5_masks.png", "midgame_page1.jpg",
              "midgame_page2.jpg", "midgame_page3.jpg", "midgame_page4.jpg", "midgame_page5.jpg", "end1.jpg",
              "end2.jpg", "end3.jpg", "puzzles_bg.jpg", "help1.png", "help2.png", "help3.png", "help4.png",
              "credits.png", "mainmenu.jpg", "SPLASH_BG.JPG", "help_UI_BG.png", "main_UI_BG_1024.png",
              "main_UI_Top_1024.png"),
}
_KIND_OF = {name.casefold(): cat for cat, names in _KINDS.items() for name in names}
_GROUPS = {
    "hut_states.png": "Huts", "clothinghut_states.png": "Huts", "loveshack_states.png": "Huts",
    "nurseryhut_states.png": "Huts", "hospital_states.png": "Huts", "scaffolding.png": "Huts",
    "woodpile.png": "Huts", "map_foodbin.png": "Food stores", "granarystagesstrip.png": "Food stores",
    "graves.png": "Graves", "puzzle_covers.png": "Puzzle screen", "puzzle_bonus_notsolved.png": "Puzzle screen",
    "puzzle_bonus_solved.png": "Puzzle screen", "collectables_small.png": "Small (on the island)",
    "collectables_small_decal.png": "Small (on the island)", "carrying.png": "Carried items (cells only)",
    "statusbarsliceg.png": "Meter parts", "statusbarsliceb.png": "Meter parts", "statusbarslicer.png": "Meter parts",
    "manabgbar.png": "Meter parts", "faithmeterbg.png": "Meter parts", "bamboometerframe1.png": "Meter parts",
    "bluestatusbarglow.png": "Meter parts", "healthbarbulb.png": "Meter parts", "loadcolor.png": "Meter parts",
    "faith_meter_details_top.png": "Meter parts",
}
for _n in _TOTEMS:
    _GROUPS[_n] = "Totems"
for _k in range(1, 49):
    _GROUPS[f"collectables_{_k:02d}.png"] = "Collection screen"
for _n in ("topPoolRed.png", "topPoolBlue.png", "topPoolYellow.png", "topPoolPurple.png", "topPoolGreen.png",
           "topPoolOrange.png", "topPoolBrown.png", "BluePaintBucket.png", "RedPaintBucket.png",
           "YellowPaintBucket.png"):
    _GROUPS[_n.casefold()] = "Paint pools and buckets"
for _n in ("01-duct-totallydestroyed.png", "02-duct-partially-fixed.png", "03-duct-mostly-fixed.png"):
    _GROUPS[_n] = "Water duct"
for _n in ("necklace_01.png", "necklace_02.png", "necklace_03.png", "necklace_04.png", "DoctorNecklacePiece.png",
           "FarmerNecklacePiece.png", "BuilderNecklacePiece.png", "ScientistNecklacePiece.png",
           "CompletedNecklace.png"):
    _GROUPS[_n.casefold()] = "Necklace"
for _n in ("ProofCompleteCrappy.png", "ProofCompleteGood.png", "ProofPartialCrappy.png", "ProofPartialGood.png",
           "ProofDisapprove.png"):
    _GROUPS[_n.casefold()] = "Proofs"

_LABELS = {
    "hand_open.png": "Hand cursor, open", "hand.png": "Hand cursor", "god_power_icons.png": "God power icons (HUD)",
    "stompped_shroom.png": "Stomped mushroom", "fishpile1.png": "Fish pile", "statusbarsliceg.png":
    "Green bar slice", "statusbarsliceb.png": "Blue bar slice", "statusbarslicer.png": "Red bar slice",
    "manabgbar.png": "Divine Energy bar backing", "faithmeterbg.png": "Faith meter backing",
    "bamboometerframe1.png": "Bamboo meter frame", "bluestatusbarglow.png": "Bar glow slice",
    "healthbarbulb.png": "Health bulb", "loadcolor.png": "Loading bar colour", "mosoleumdebrisstrip.png":
    "Mausoleum debris", "idol_states.png": "Idol", "lab_states.png": "Laboratory", "hut_states.png": "Hut",
    "clothinghut_states.png": "Clothing hut", "loveshack_states.png": "Love shack", "nurseryhut_states.png":
    "Nursery hut", "hospital_states.png": "Hospital", "map_foodbin.png": "Food bin", "granarystagesstrip.png":
    "Granary", "peep_shadow1.png": "Villager shadow", "skelly.png": "Skeleton (a body awaiting burial)",
    "ripple.png": "Swimming ripple", "vv5_heathenheads.png": "Heathen masks (5 colours x 8 head turns)",
    "focus_circle.png": "Focus circle", "carrying.png": "Carried items",
    "bigbodies.png": "Details portrait bodies (Villager Details)",
    "beestriplarge_final2.png": "Bees", "butterflygreen.png": "Butterflies", "fishflop.png": "Fish flopping",
    "tech_ui_bg.jpg": "Tech screen background", "vd_bg_2.jpg": "Villager Details background",
    "selectvillagers_ui_bg.jpg": "Select villagers background", "mausoleum_ui_bg.jpg": "Mausoleum background",
    "trophies_ui_bg.jpg": "Trophies background", "collection_ui_bg.jpg": "Collections background",
    "loading.jpg": "Loading screen", "mainmenu.jpg": "Main menu", "splash_bg.jpg": "Splash screen",
    "end1.jpg": "Ending 1", "end2.jpg": "Ending 2", "end3.jpg": "Ending 3", "credits.png": "Credits",
}
for _n, _t in _TOTEMS.items():
    _LABELS[_n] = _t


def kind_of(name: str) -> tuple[str, str, str]:
    """(category, group, label) of a sprite's picture; PANELS when the list above does not name it."""
    key = name.casefold()
    return _KIND_OF.get(key, PANELS), _GROUPS.get(key, ""), _LABELS.get(key, name)


# ------------------------------------------------------------------ plans

def _cell(sheets, rec, frame: int, x: int = 0, y: int = 0, alpha: float = 1.0, what: str = "") -> pi.Draw:
    """Sprite `rec` drawn by 0x44FC70 at frame `frame`: the cell (frame mod columns, frame div columns), the
    whole picture for a whole sprite."""
    cols, rows, sheets_ = geometry(rec)
    name = rec[1]
    if (cols, rows, tuple(sheets_)) == (1, 1, (1, 1)):
        return va.whole_plan(sheets, name, x, y, alpha, what)
    atlas = pi.Atlas(name, cols, rows, tuple(sheets_), GRID_SUFFIX)
    down, across = pi._cdivmod(frame, cols)
    return va.cell_plan(sheets, atlas, across, down, x, y, 1.0, alpha, what)


def cell_count(rec) -> int:
    cols, rows, _ = geometry(rec)
    return cols * rows


def _files_of(rec) -> list[str]:
    spec = spec_of(rec)
    return spec.files() if spec is not None else []


def _has(sheets, names) -> bool:
    return all(sheets.has(n) for n in names)


# Tech screen 0x440F80
TECH_LINES = ((0xC6, 5, 78, "Science"), (0xC7, 5, 192, "Medicine"), (0xC8, 5, 307, "Learning"),
              (0xC9, 5, 420, "Restoration"), (0xCA, 5, 534, "Food Mastery"), (0xCB, 5, 647, "Evangelism"))
TECH_STEP = 167                                                    # 0x441080: add 0xA7 a level
TECH_BG = 0xC5
POWER_SPOTS = ((796, 547), (596, 499), (881, 456), (521, 401), (879, 361), (578, 313), (834, 266), (570, 217),
               (774, 163), (685, 123), (872, 74))                     # 0x4CD300
POWER_COSTS = (10, 25, 50, 100, 150, 300, 400, 500, 600, 700, 800)   # 0x49A19C
POWER_NAMES = ("Spawn Butterflies", "Swarm of Bees", "Sunshine", "Lightning Strike", "Hand of Bloom", "Tempest",
               "Fog of Doom", "Time Warp", "Revive", "Grant Youth", "Earthquake")
ICON_ON, ICON_OFF, ICON_BACK, ICON_TOP = 0xCF, 0xD0, 0xD1, 0xD2
OFF_BACK_ALPHA = pi.f32(0.6)                                       # 0x498938


def power_icon_plan(sheets, power: int, lit: bool, x: int = 0, y: int = 0, fade: float = 1.0) -> list[pi.Draw]:
    if lit:
        out = [_cell(sheets, descriptor(ICON_BACK), power, x, y, fade, "backing"),
               _cell(sheets, descriptor(ICON_ON), power, x, y, fade, "icon")]
    else:
        out = [_cell(sheets, descriptor(ICON_OFF), power, x, y, 1.0, "icon"),
               _cell(sheets, descriptor(ICON_BACK), power, x, y, OFF_BACK_ALPHA, "backing")]
    return out + [_cell(sheets, descriptor(ICON_TOP), power, x, y, 1.0, "ring")]


def tech_bar_plan(sheets, line: int, levels: int) -> list[pi.Draw]:
    ident, x, y, _name = TECH_LINES[line]
    return [_cell(sheets, descriptor(ident), k, x + TECH_STEP * k, y, 1.0, "level") for k in range(levels)]


def tech_screen_plan(sheets, levels, cap: int) -> list[pi.Draw]:
    """0x440F80 with `levels[line]` bought on each line and the Divine Energy cap `cap` (every fade finished)."""
    out = [_cell(sheets, descriptor(TECH_BG), 0, 0, 0, 1.0, "background")]
    for line in range(6):
        out += tech_bar_plan(sheets, line, levels[line])
    for power, (x, y) in enumerate(POWER_SPOTS):
        out += power_icon_plan(sheets, power, cap >= POWER_COSTS[power], x, y)
    return out


# Skill bars 0x4500E0 (meter object 0x450040: +0xC blue 0x86, +0x14 red 0x87, +0x10 faith backing 0xF)
SLICE_B, SLICE_R, SLICE_G, GLOW, FAITH_BG, MANA_BG = 0x86, 0x87, 0x0A, 0x88, 0x0F, 0x11
METER_X = 0x23B
SKILL_ROWS = {3: 0x12B, 4: 0x155, 5: 0x17F, 6: 0x1AB, 7: 0x1D4, 8: 0xAA, 11: 0x1FC}
SKILL_NAMES = {3: "Farming", 4: "Building", 5: "Research", 6: "Healing", 7: "Parenting", 8: "Health",
               11: "Devotion"}                                     # 0x43E0C7.., 0x44B302..: record +0x1C5C..


def _trunc4(v: int) -> int:
    return pi._cdivmod(v, 4)[0]


def skill_slices(value: int) -> tuple[int, int]:
    """(full, half) slice counts of 0x4500E0 for a value (clamped to -100..100)."""
    v = max(-100, min(100, int(value))) << 8
    return _trunc4(pi._cdivmod(v, 100)[0]), _trunc4(pi._cdivmod(v, 200)[0])


def skill_bar_plan(sheets, kind: int, value: int, y: int = 0) -> list[pi.Draw]:
    full, half = skill_slices(value)
    if kind in (3, 4, 5, 6, 7, 11):
        return [_cell(sheets, descriptor(SLICE_B), 0, METER_X + 4 * k, y + SKILL_ROWS[kind]) for k in range(full)]
    if kind == 8:
        return [_cell(sheets, descriptor(SLICE_R), 0, METER_X + 4 * k, y + SKILL_ROWS[8]) for k in range(full)]
    if kind == 9:
        out = [_cell(sheets, descriptor(FAITH_BG), 0, 0x1B9, y + 0x26, 1.0, "backing")]
        if half > 0:
            out += [_cell(sheets, descriptor(SLICE_B), 0, METER_X + 4 * k, y + 0x28) for k in range(half)]
        elif half < 0:
            out += [_cell(sheets, descriptor(SLICE_R), 0, 0x227 - 4 * k, y + 0x28) for k in range(-half)]
        return out
    return []


def energy_slices(cap: int, energy: int, cost: int) -> tuple[int, int, int, int]:
    """(cap as clamped, green, blue, glow) slice counts of 0x450380."""
    cap = max(10, min(1000, int(cap)))
    length = pi._cdivmod(cap * 372, 1000)[0]
    filled = pi._cdivmod(length * int(energy), cap)[0]
    glow = _trunc4(pi._cdivmod(length * int(cost), cap)[0]) if cost else 0
    return cap, _trunc4(length), _trunc4(filled), glow


def energy_bar_plan(sheets, cap: int, energy: int, cost: int = 0, x: int = 0x269, y: int = 0xC) -> list[pi.Draw]:
    _cap, green, blue, glow = energy_slices(cap, energy, cost)
    out = [_cell(sheets, descriptor(SLICE_G), 0, x + 4 * k, y, 1.0, "capacity") for k in range(green)]
    out += [_cell(sheets, descriptor(SLICE_B), 0, x + 4 * k, y, 1.0, "energy") for k in range(blue)]
    out += [_cell(sheets, descriptor(GLOW), 0, x + 4 * k, y, 1.0, "cost") for k in range(glow)]
    return out


# Dialog boxes 0x40E160 / 0x40DFA0
DIALOGS = ((0x76, "Orange"), (0x77, "Green"))
DIALOG_SIZES = ((455, 400), (360, 200), (640, 508), (480, 320))   # 0x418CF6, 0x419821, 0x41A8D1, 0x41C486


def dialog_tiles(sheets, ident: int, w: int, h: int) -> tuple[int, int, int, int]:
    rec = descriptor(ident)
    _name, rect = pi.Atlas(rec[1], *geometry(rec)[:2]).cell(sheets.size, 0, 0)
    tw, th = rect[2] - rect[0], rect[3] - rect[1]
    cols = pi._cdivmod(tw + w - 1, tw)[0]
    rows = pi._cdivmod(th + h - 1, th)[0]
    return tw, th, cols if cols > 1 else 2, rows if rows > 1 else 2


def dialog_plan(sheets, ident: int, w: int, h: int, x: int = 0, y: int = 0, alpha: float = 1.0) -> list[pi.Draw]:
    rec = descriptor(ident)
    tw, th, cols, rows = dialog_tiles(sheets, ident, w, h)
    out = []

    def row(yy, left, mid, right):
        out.append(_cell(sheets, rec, left, x, yy, alpha))
        for j in range(cols - 2):
            out.append(_cell(sheets, rec, mid, x + tw * (j + 1), yy, alpha))
        out.append(_cell(sheets, rec, right, x + tw * (cols - 1), yy, alpha))
    row(y, 8, 1, 0)
    for r in range(rows - 2):
        row(y + th * (r + 1), 3, 7, 2)
    row(y + th * (rows - 1), 5, 4, 6)
    return out


def map_plan(sheets) -> list[pi.Draw]:
    return [va.whole_plan(sheets, map_tile(x, y), TILE * x, TILE * y, what=f"tile {x}, {y}") for x, y in MAP_TILES]


# ------------------------------------------------------------------ the assets

PROOF_DRAW = "emulated 0x44FC70, every frame"


def _sprite_assets(sheets) -> list[Asset]:
    """Every table sprite with a picture, every frame as the sprite draw 0x44FC70 draws it, under its kind."""
    out, seen = [], set()
    for rec in DESCRIPTORS:
        spec = spec_of(rec)
        if spec is None or not _has(sheets, spec.files()):
            continue
        cols, rows, sheets_ = geometry(rec)
        key = (rec[1].casefold(), cols, rows, tuple(sheets_))
        if key in seen:
            continue
        seen.add(key)
        if len(spec.files()) > 1:
            continue                         # the villager sheets: Source sheets, and the Picture Studio's villagers
        category, group, label = kind_of(rec[1])
        n = cell_count(rec)
        frames = tuple(Frame("" if n == 1 else f"frame {k + 1}", (_cell(sheets, rec, k),)) for k in range(n))
        note = "" if n == 1 else (f"{cols} x {rows} frames; which frame the game shows when is up to the thing "
                                  "drawn, the frames are in the sheet's order")
        out.append(Asset(f"sprite:{rec[0]:X}", category, label, frames, group=group, note=note, proof=PROOF_DRAW))
    return out


def _tech_assets(sheets) -> list[Asset]:
    need = [descriptor(i)[1] for i in (TECH_BG, ICON_ON, ICON_OFF, ICON_BACK, ICON_TOP)] + \
           [descriptor(line[0])[1] for line in TECH_LINES]
    if not _has(sheets, need):
        return []
    out = []
    states = (("Nothing bought, no Divine Energy", (0,) * 6, 0),
              ("Every line at level 1, cap 50", (1,) * 6, 50),
              ("Every line at level 2, cap 300", (2,) * 6, 300),
              ("Every line at level 3 (full), cap 800", (3,) * 6, 800),
              ("Mixed: 3, 2, 1, 0, 1, 2 levels, cap 150", (3, 2, 1, 0, 1, 2), 150))
    out.append(Asset("tech:screen", TECH, "Tech screen", tuple(
        Frame(label, tuple(tech_screen_plan(sheets, levels, cap))) for label, levels, cap in states),
        group="Whole screen", proof="emulated 0x440F80"))
    bg = descriptor(TECH_BG)[1]
    for line, (ident, x, y, name) in enumerate(TECH_LINES):
        w, h = va.whole_plan(sheets, descriptor(ident)[1]).rect[2] // 3, sheets.size(descriptor(ident)[1])[1]
        under = pi.Draw(bg, (x, y, x + w * 3, y + h), x, y, 1.0, 1.0, "the background under the bar")
        frames = [Frame("uncoloured (nothing bought)", (under,))]
        for levels in (1, 2, 3):
            frames.append(Frame(f"{levels} level{'s' if levels > 1 else ''} coloured" + (" (full)" if levels == 3
                                                                                          else ""),
                                (under,) + tuple(tech_bar_plan(sheets, line, levels))))
        out.append(Asset(f"tech:bar:{line}", TECH, f"{name} bar", tuple(frames), group="Tech bars",
                         note="the uncoloured bar is the screen background's own pixels under it",
                         proof="emulated 0x440F80"))
    for power, name in enumerate(POWER_NAMES):
        out.append(Asset(f"tech:power:{power}", TECH, f"{name} ({POWER_COSTS[power]} Divine Energy)", (
            Frame("lit (the cap reached its cost)", tuple(power_icon_plan(sheets, power, True))),
            Frame("not yet (grey)", tuple(power_icon_plan(sheets, power, False)))),
            group="God power icons", proof="emulated 0x440F80"))
    return out


def _meter_assets(sheets) -> list[Asset]:
    out = []
    if _has(sheets, [descriptor(SLICE_B)[1], descriptor(SLICE_R)[1]]):
        for kind in (3, 4, 5, 6, 7, 11, 8):
            frames = tuple(Frame(f"{v}", tuple(skill_bar_plan(sheets, kind, v))) for v in (0, 1, 2, 25, 50, 75, 100))
            out.append(Asset(f"meter:skill:{kind}", METERS, f"{SKILL_NAMES[kind]} bar (Villager Details)", frames,
                             group="Villager Details bars", note="at its place on the Details screen",
                             proof="emulated 0x4500E0"))
    if _has(sheets, [descriptor(i)[1] for i in (SLICE_G, SLICE_B, GLOW, MANA_BG)]):
        frames = []
        backing = _cell(sheets, descriptor(MANA_BG), 0, 0x266, 0xA, 1.0, "backing")
        for cap, energy, cost in ((10, 0, 0), (100, 50, 0), (400, 400, 0), (800, 200, 0), (1000, 1000, 0),
                                  (1000, 640, 300), (600, 120, 600)):
            label = f"cap {cap}, energy {energy}" + (f", a power costing {cost} chosen" if cost else "")
            frames.append(Frame(label, (backing,) + tuple(energy_bar_plan(sheets, cap, energy, cost))))
        out.append(Asset("meter:energy", METERS, "Divine Energy bar", tuple(frames), group="Divine Energy",
                         note="at its place on the screen (the HUD 0x4431E8)", proof="emulated 0x450380"))
    return out


def _panel_assets(sheets) -> list[Asset]:
    out = []
    for ident, colour in DIALOGS:
        if not sheets.has(descriptor(ident)[1]):
            continue
        frames = tuple(Frame(f"{w} x {h}", tuple(dialog_plan(sheets, ident, w, h))) for w, h in DIALOG_SIZES)
        out.append(Asset(f"dialog:{ident:X}", PANELS, f"{colour} dialog box", frames, group="Dialog boxes",
                         proof="emulated 0x40DFA0"))
    return out


def _scene_assets(sheets) -> list[Asset]:
    names = [map_tile(x, y) for x, y in MAP_TILES]
    if not _has(sheets, names):
        return []
    out = [Asset("scene:map", SCENE, "The island, assembled from its 25 tiles", (Frame("", tuple(map_plan(sheets))),),
                 group="Island map", proof="emulated 0x47ABE0 (the tiles' places)")]
    out.append(Asset("scene:tiles", SCENE, "Island map tiles", tuple(
        Frame(f"X {x}, Y {y}", (va.whole_plan(sheets, map_tile(x, y)),)) for x, y in MAP_TILES), group="Island map",
        proof="emulated 0x47ABE0"))
    return out


def _font_assets(sheets) -> list[Asset]:
    out = []
    for which, (name, label, _height, table) in enumerate(FONTS_TABLE):
        if not sheets.has(name):
            continue
        h = sheets.size(name)[1]
        frames = []
        for code, left, right in font_glyphs(which):
            ch = chr(code if code >= 0 else 256 + code)
            text = "space" if ch == " " else ch
            frames.append(Frame(f"{text} (code {code if code >= 0 else 256 + code})",
                                (pi.Draw(name, (left, 0, right, h), 0, 0, 1.0, 1.0, "glyph"),)))
        out.append(Asset(f"font:{which}", FONTS, f"{label} font", tuple(frames), group="Fonts",
                         note=f"each glyph as the game's glyph table {table} cuts it", proof="exe glyph table"))
    return out


def _patcher_assets(sheets) -> list[Asset]:
    out = []
    if sheets.has("golden_mushroom.png"):
        out.append(Asset("patcher:golden", PATCHER, "Super-Secret Golden Mushroom", (
            Frame("", (va.whole_plan(sheets, "golden_mushroom.png", 7, 1, what="golden mushroom"),)),),
            group="Golden Mushroom", patcher=True,
            note="VVFP Golden Mushroom.dll draws it in place of collectables frame 51, moved 7 right and 1 down",
            proof="native/vvfp_golden_mushroom (LATER_STUB vv5)"))
    if sheets.has("bigheads_masks.png"):
        atlas = pi.Atlas("bigheads_masks.png", 3, 5)
        colours = ("Blue", "Orange", "Red", "Purple", "Chief")
        facings = ("right", "front", "left")
        frames = [Frame("whole", (va.whole_plan(sheets, "bigheads_masks.png"),))]
        frames += [Frame(f"{colours[r]} mask, facing {facings[c]}", (va.cell_plan(sheets, atlas, c, r),))
                   for r in range(5) for c in range(3)]
        out.append(Asset("patcher:bigmasks", PATCHER, "Details portrait masks", tuple(frames), group="Masks",
                         patcher=True, note="cells as scripts/build_vv5_bighead_mask_atlas.py lays them out (3 x 5); "
                         "where the patcher draws them is " + va.NOT_PLACED, proof="sheet"))
    for stem, label in ORIGINS_ICONS:
        if sheets.has(stem + ".png"):
            out.append(va.one(sheets, f"patcher:{stem}", PATCHER, f"Origins icon: {label}", stem + ".png",
                              group="Origins icons", patcher=True, proof="sheet",
                              note="the picture of the icon the VV5 Origins DLL carries"))
    return out


def _unused_assets(sheets) -> list[Asset]:
    out = []
    for name in UNUSED_FILES:
        if sheets.has(name):
            out.append(va.one(sheets, f"unused:{name}", UNUSED, name, name, group="Never named by the game",
                              unused=True, proof="exe scan", note="whole; " + va.NOT_PLACED))
    if _has(sheets, [descriptor(i)[1] for i in (FAITH_BG, SLICE_B, SLICE_R)]):
        frames = tuple(Frame(f"{v}", tuple(skill_bar_plan(sheets, 9, v))) for v in (-100, -50, 0, 50, 100))
        out.append(Asset("unused:faith-meter", UNUSED, "Faith meter (the skill bar's kind 9)", frames,
                         group="Drawn by code no caller reaches", unused=True, proof="emulated 0x4500E0",
                         note="0x4500E0 can draw it, but no call passes kind 9 (its 13 callers pass 3-8 and 11)"))
    return out


def _direct_assets(sheets) -> list[Asset]:
    """The whole pictures built outside the table that no table sprite also builds (SPLASH_BG.JPG)."""
    table = {rec[1].casefold() for rec in DESCRIPTORS}
    out = []
    for name, cols, _rows, where in DIRECT:
        if cols == 0 and name.casefold() not in table and sheets.has(name):
            category, group, label = kind_of(name)
            out.append(va.one(sheets, f"direct:{name}", category, label, name, group=group,
                              proof=f"whole picture ({where})"))
    return out


def assets(sheets) -> list[Asset]:
    return (_tech_assets(sheets) + _meter_assets(sheets) + _panel_assets(sheets) + _scene_assets(sheets)
            + _font_assets(sheets) + _patcher_assets(sheets) + _unused_assets(sheets) + _sprite_assets(sheets)
            + _direct_assets(sheets))
