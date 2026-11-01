"""Picture Studio's Everything tab, The Secret City (Virtual Villagers 3): every picture the game ships, and what
the game assembles from them, drawn as the stock executable draws it (docs/picture-studio-assets-vv3.md).

Every rule here is read from the stock executable (Virtual Villagers - The Secret City.exe) and every composed
plan is proven by tests/test_assets_vv3.py, which runs the game's own draw code in Unicorn
(scripts/emu_vv3_assets.py) and requires each blit it makes to equal the plan here, in order.

THE SPRITES.  The game builds its sprites from a resource table at 0x4A95A0 (181 entries of 0x30 bytes: id,
file, columns, rows, suffix, sheets across, sheets down), through 0x42EA80: columns and rows -> an atlas
(0x42E750 -> 0x40AF10, or the sheet grid 0x40AF90); columns only -> a strip (0x42E920 -> 0x401150, which is
0x40AF10(name, columns, 1)); neither -> one whole picture (0x40AD80).  Besides the table it builds, by name:
clamStates.png 2 x 1 (0x43296E), doorKeys.png 3 x 1 (0x4329A7), ruinsRubble.png 3 x 1 (0x4360FE), the 16
village map tiles "MapX%01dY%01d.jpg" (0x422F20, whole, 512 apart), the splash screens SPLASH_BG.JPG and
SPLASH1-3_BG.JPG (0x46C509 ...), menu_logo.png / loading_logo.png (0x4261A0 / 0x4261E5) and the two fonts
ldwBurweed27 / ldwarialbold + ".png" (0x4244D9 / 0x424569, read whole by the font loader 0x402560).

DRAWING.  The camera (0x58F6F8) draws a whole picture (0x42E4B0), frame f of a sheet (0x42E510: column
f % columns, row f / columns, 0x409510) or a whole picture scaled (0x42E570) at a place in the village; in the
Studio the camera is at no scroll and zoom 1.0, so a plan's x, y are the village's own coordinates (the window
crops the picture to what is drawn).  The screens draw by resource id with 0x42EB90(id, x, y, alpha, percent).
"""
from __future__ import annotations

from pathlib import Path

import vv_picture_image as pi
import vv_pictures_assets as pa

GAME = 3
ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

# ------------------------------------------------------------------------------------------- the stock sheets

# The stock pictures' sizes (scripts/sizes_vv3.py), for planning and the tests without the art.
SIZES = {
    'alchemy.jpg': (285, 50), 'alchemylab.png': (987, 359), 'AlchemyLab0.png': (68, 64),
    'AlchemyLab1.png': (68, 64), 'AlchemyLab2.png': (68, 64), 'AlchemyLab3.png': (68, 64),
    'AlchemyLab4.png': (68, 64), 'algae.png': (240, 240), 'amppuddle.png': (318, 200), 'arrowglow.png': (100, 100),
    'arrowglowdown.png': (100, 100), 'arrowleftglow.png': (100, 100), 'arrowrightglow.png': (100, 100),
    'awards.png': (375, 150), 'awards_bg.jpg': (800, 600), 'BambooMeterFrame1.png': (320, 30),
    'bananaDecals.png': (245, 25), 'bananaTree_bare.png': (266, 168), 'bath_plans.png': (64, 65),
    'beestriplarge_final2.png': (826, 140), 'bird.png': (600, 25), 'bird_shadow.png': (51, 25),
    'blurry_sparkle.png': (200, 20), 'Boxshot_CTButton.png': (624, 44), 'Boxshot_HelpButton.png': (459, 38),
    'Boxshot_OptsButton.png': (588, 41), 'Boxshot_PlayButton.png': (540, 44), 'Boxshot_QuitButton.png': (381, 35),
    'Boxshot_SOButton.png': (603, 42), 'bubble.png': (200, 20), 'bubblestrip.png': (180, 20),
    'buy_button.png': (304, 28), 'candlestrip.png': (180, 20), 'canopy.png': (671, 660), 'cape.png': (25, 51),
    'carrying.png': (520, 160), 'CheckboxStrip.png': (96, 32), 'checkmark.png': (32, 32),
    'clamStates.png': (160, 80), 'clothinghut_states.png': (400, 272), 'collectables_small.png': (240, 360),
    'collecting_coral.png': (280, 210), 'collecting_feathers.png': (500, 375), 'collecting_tablet.png': (320, 240),
    'collecting_turtleshells.png': (280, 210), 'collection_bg.png': (800, 600), 'credits.jpg': (800, 600),
    'Door.png': (62, 126), 'doorframe.png': (133, 130), 'doorKeys.png': (96, 32), 'doorKeys_small.png': (75, 24),
    'DownArrowButton.png': (54, 20), 'dragonflies.png': (210, 140), 'dust2.png': (270, 30),
    'empty1.png': (388, 32), 'farming.jpg': (285, 50), 'female_actions00.png': (680, 650),
    'female_actions01.png': (680, 650), 'female_actions02.png': (680, 650), 'female_bodies00.png': (640, 650),
    'female_bodies01.png': (640, 650), 'female_bodies02.png': (640, 650), 'female_bodies10.png': (640, 650),
    'female_bodies11.png': (640, 650), 'female_bodies12.png': (640, 650), 'female_heads.png': (320, 1950),
    'female_heads_old.png': (320, 1950), 'firestrip.png': (512, 256), 'foam.png': (192, 96),
    'focus_circle.png': (68, 64), 'footprints.png': (150, 8), 'gems_fordoor.png': (210, 70),
    'ghosts5.png': (80, 130), 'graveflowers.png': (201, 46), 'graves.png': (220, 44),
    'GreenDlgTileGrid.png': (576, 64), 'hand.png': (54, 54), 'hand_open.png': (54, 54),
    'healthBarbulb.png': (28, 28), 'help1.jpg': (800, 600), 'help2.jpg': (800, 600), 'help3.jpg': (800, 600),
    'help4.jpg': (800, 600), 'herb_magic.png': (53, 57), 'herb_nature.png': (53, 57),
    'hummingbirdstrip.png': (200, 100), 'hut_states.png': (400, 400), 'image1_page1.jpg': (800, 600),
    'image1_page2.jpg': (800, 600), 'image1_page3.jpg': (469, 600), 'image1_page4.jpg': (800, 369),
    'image1_page5.jpg': (800, 444), 'image1_page5mask.jpg': (800, 444), 'info_button.png': (112, 28),
    'ldwarialbold.png': (1940, 20), 'ldwBurweed27.png': (2364, 27), 'ldwLogo.png': (168, 178),
    'leftarrow.png': (120, 36), 'LoadColor.png': (8, 30), 'loading.jpg': (800, 600), 'logo1.png': (329, 207),
    'magic.jpg': (114, 354), 'magicPlantsFish.png': (400, 450), 'main_BG.png': (800, 600),
    'main_detail_button.png': (345, 52), 'main_wide_button2.png': (388, 32), 'male_actions00.png': (680, 650),
    'male_actions01.png': (680, 650), 'male_actions02.png': (680, 650), 'male_bodies00.png': (640, 650),
    'male_bodies01.png': (640, 650), 'male_bodies02.png': (640, 650), 'male_bodies10.png': (640, 650),
    'male_bodies11.png': (640, 650), 'male_bodies12.png': (640, 650), 'male_heads.png': (320, 1950),
    'male_heads_old.png': (320, 1950), 'mangoDecals.png': (46, 32), 'mangoTree_bare.png': (371, 219),
    'map_bath_filled.png': (306, 156), 'map_bathDamage.png': (183, 93), 'Map_Cloud01.png': (200, 100),
    'Map_Fog.png': (300, 100), 'map_foodbin.png': (580, 133), 'map_hospitalStates.png': (1071, 280),
    'MapX0Y0.jpg': (512, 512), 'MapX0Y1.jpg': (512, 512), 'MapX0Y2.jpg': (512, 512), 'MapX0Y3.jpg': (512, 512),
    'MapX1Y0.jpg': (512, 512), 'MapX1Y1.jpg': (512, 512), 'MapX1Y2.jpg': (512, 512), 'MapX1Y3.jpg': (512, 512),
    'MapX2Y0.jpg': (512, 512), 'MapX2Y1.jpg': (512, 512), 'MapX2Y2.jpg': (512, 512), 'MapX2Y3.jpg': (512, 512),
    'MapX3Y0.jpg': (512, 512), 'MapX3Y1.jpg': (512, 512), 'MapX3Y2.jpg': (512, 512), 'MapX3Y3.jpg': (512, 512),
    'medicine.jpg': (285, 50), 'midgame_page1.jpg': (600, 434), 'midgame_page2.jpg': (376, 600),
    'midgame_page3.jpg': (800, 401), 'MS_Button_01.png': (364, 52), 'MS_Button_02.png': (256, 50),
    'MS_Button_03.png': (300, 60), 'MS_Button_04.png': (288, 40), 'nature.jpg': (114, 354),
    'opendoor.png': (57, 122), 'OrangeDlgTileGrid.png': (576, 64), 'orchard_dirtMound.png': (55, 28),
    'overview_bg.jpg': (800, 600), 'page2_flicker_alphaMask.png': (616, 443), 'papayaDecals.png': (108, 26),
    'papayaTree_bare.png': (229, 183), 'peep_shadow1.png': (68, 64), 'petalstrip.png': (600, 300),
    'popup_button1.png': (420, 32), 'puzzle_covers.jpg': (640, 472), 'puzzle_solved.jpg': (640, 472),
    'puzzles_bg.png': (800, 600), 'radioblank.png': (32, 32), 'radioselected.png': (32, 32),
    'rainbow.png': (500, 25), 'raindrops.png': (66, 16), 'RainLift.png': (800, 266),
    'RainLiftBroke.png': (160, 160), 'reefFish1.png': (375, 300), 'reefFish2.png': (375, 400),
    'reefFish3.png': (375, 500), 'research_button.png': (172, 28), 'restoration.jpg': (285, 50),
    'rightarrow.png': (120, 36), 'ripple.png': (260, 65), 'rosterbush.png': (320, 160),
    'ruinsRubble.png': (330, 89), 'scaffolding.png': (97, 45), 'science.jpg': (285, 50),
    'sciencelab.png': (1056, 385), 'sharkstripfinal.png': (240, 30), 'sharp_sparkle.png': (200, 20),
    'skelly.png': (240, 65), 'sliderhandle.png': (16, 32), 'smokestriplight.png': (1440, 120),
    'sparklestrip.png': (250, 25), 'sparklestrip2.png': (120, 12), 'SPLASH_BG.jpg': (800, 600),
    'spray.png': (1200, 100), 'statue_plans.png': (64, 65), 'statueErect.png': (189, 245),
    'statueFallen.png': (233, 149), 'StatusBarSliceB.png': (16, 16), 'StatusBarSliceR.png': (16, 16),
    'story3_page1.jpg': (800, 485), 'story3_page2.jpg': (800, 366), 'story3_page3.jpg': (369, 600),
    'story3_page4.jpg': (800, 600), 'sunbeam.png': (214, 800), 'sundisk.png': (552, 117),
    'tech_bg.jpg': (800, 600), 'tree_overhang.png': (269, 247), 'ultra_wide_button.png': (1203, 42),
    'UpArrowButton.png': (54, 20), 'VD_BG_2.png': (800, 600), 'VerticalScrollKnob.png': (12, 26),
    'VerticalScrollTrack.png': (18, 220), 'vv2_boxshot.jpg': (800, 600), 'waterfallanimA.png': (512, 512),
    'waterfallanimb.png': (240, 60), 'waves_proto.png': (500, 50), 'WideSlider2.png': (260, 32),
    'woodpile.png': (67, 44), 'yellow_sparkle.png': (300, 30),
}

# The resource table 0x4A95A0 as the stock executable holds it: (id, file, columns, rows, (across, down)).
# Entry 0 is "No Graphic" (no file).  tests/test_assets_vv3.py reads the table from the exe and compares.
TABLE = (
    (0x01, "hand_open.png", 0, 0, (0, 0)), (0x02, "hand.png", 0, 0, (0, 0)),
    (0x03, "main_wide_button2.png", 3, 1, (0, 0)), (0x04, "ultra_wide_button.png", 3, 1, (0, 0)),
    (0x05, "MS_Button_01.png", 3, 1, (0, 0)), (0x06, "MS_Button_02.png", 3, 1, (0, 0)),
    (0x07, "MS_Button_03.png", 3, 1, (0, 0)), (0x08, "MS_Button_04.png", 3, 1, (0, 0)),
    (0x09, "main_detail_button.png", 3, 1, (0, 0)), (0x0A, "Boxshot_CTButton.png", 3, 1, (0, 0)),
    (0x0B, "Boxshot_HelpButton.png", 3, 1, (0, 0)), (0x0C, "Boxshot_OptsButton.png", 3, 1, (0, 0)),
    (0x0D, "Boxshot_PlayButton.png", 3, 1, (0, 0)), (0x0E, "Boxshot_QuitButton.png", 3, 1, (0, 0)),
    (0x0F, "Boxshot_SOButton.png", 3, 1, (0, 0)), (0x10, "popup_button1.png", 3, 1, (0, 0)),
    (0x11, "OrangeDlgTileGrid.png", 9, 1, (0, 0)), (0x12, "GreenDlgTileGrid.png", 9, 1, (0, 0)),
    (0x13, "leftarrow.png", 3, 1, (0, 0)), (0x14, "rightarrow.png", 3, 1, (0, 0)),
    (0x15, "radioblank.png", 0, 0, (0, 0)), (0x16, "radioselected.png", 0, 0, (0, 0)),
    (0x17, "CheckboxStrip.png", 2, 0, (0, 0)), (0x18, "checkmark.png", 0, 0, (0, 0)),
    (0x19, "WideSlider2.png", 0, 0, (0, 0)), (0x1A, "sliderhandle.png", 0, 0, (0, 0)),
    (0x1B, "UpArrowButton.png", 3, 1, (0, 0)), (0x1C, "DownArrowButton.png", 3, 1, (0, 0)),
    (0x1D, "VerticalScrollTrack.png", 0, 0, (0, 0)), (0x1E, "VerticalScrollKnob.png", 0, 0, (0, 0)),
    (0x1F, "BambooMeterFrame1.png", 0, 0, (0, 0)), (0x20, "StatusBarSliceB.png", 0, 0, (0, 0)),
    (0x21, "StatusBarSliceR.png", 0, 0, (0, 0)), (0x22, "healthBarbulb.png", 0, 0, (0, 0)),
    (0x23, "LoadColor.png", 0, 0, (0, 0)), (0x24, "focus_circle.png", 0, 0, (0, 0)),
    (0x25, "overview_bg.jpg", 0, 0, (0, 0)), (0x26, "awards_bg.jpg", 0, 0, (0, 0)),
    (0x27, "map_cloud01.png", 0, 0, (0, 0)), (0x28, "loading.jpg", 0, 0, (0, 0)),
    (0x29, "ldwLogo.png", 0, 0, (0, 0)), (0x2A, "logo1.png", 0, 0, (0, 0)),
    (0x2B, "small_logo.png", 1, 1, (0, 0)), (0x2C, "image1_page1.jpg", 1, 1, (0, 0)),
    (0x2D, "image1_page2.jpg", 1, 1, (0, 0)), (0x2E, "image1_page3.jpg", 1, 1, (0, 0)),
    (0x2F, "image1_page4.jpg", 1, 1, (0, 0)), (0x30, "image1_page5.jpg", 1, 1, (0, 0)),
    (0x31, "image1_page5mask.jpg", 1, 1, (0, 0)), (0x32, "midgame_page1.jpg", 1, 1, (0, 0)),
    (0x33, "page2_flicker_alphaMask.png", 1, 1, (0, 0)), (0x34, "midgame_page2.jpg", 1, 1, (0, 0)),
    (0x35, "midgame_page3.jpg", 1, 1, (0, 0)), (0x36, "magicPlantsFish.png", 4, 3, (0, 0)),
    (0x37, "story3_page1.jpg", 1, 1, (0, 0)), (0x38, "story3_page1mask.png", 1, 1, (0, 0)),
    (0x39, "story3_page2.jpg", 1, 1, (0, 0)), (0x3A, "story3_page3.jpg", 1, 1, (0, 0)),
    (0x3B, "story3_page4.jpg", 1, 1, (0, 0)), (0x3C, "main_BG.png", 0, 0, (0, 0)),
    (0x3D, "puzzles_bg.png", 0, 0, (0, 0)), (0x3E, "help1.jpg", 0, 0, (0, 0)),
    (0x3F, "help2.jpg", 0, 0, (0, 0)), (0x40, "help3.jpg", 0, 0, (0, 0)),
    (0x41, "help4.jpg", 0, 0, (0, 0)), (0x42, "credits.jpg", 0, 0, (0, 0)),
    (0x43, "vv2_boxshot.jpg", 0, 0, (0, 0)), (0x44, "empty1.png", 3, 1, (0, 0)),
    (0x45, "arrowglow.png", 0, 0, (0, 0)), (0x46, "arrowglowdown.png", 0, 0, (0, 0)),
    (0x47, "arrowleftglow.png", 0, 0, (0, 0)), (0x48, "arrowrightglow.png", 0, 0, (0, 0)),
    (0x49, "puzzle_solved.jpg", 4, 4, (0, 0)), (0x4A, "puzzle_covers.jpg", 4, 4, (0, 0)),
    (0x4B, "collection_bg.png", 0, 0, (0, 0)), (0x4C, "collecting_turtleshells.png", 4, 3, (0, 0)),
    (0x4D, "collecting_coral.png", 4, 3, (0, 0)), (0x4E, "collecting_tablet.png", 4, 3, (0, 0)),
    (0x4F, "collecting_feathers.png", 4, 3, (0, 0)), (0x50, "gems_fordoor.png", 3, 1, (0, 0)),
    (0x51, "tech_bg.jpg", 0, 0, (0, 0)), (0x52, "science.jpg", 3, 1, (0, 0)),
    (0x53, "medicine.jpg", 3, 1, (0, 0)), (0x54, "alchemy.jpg", 3, 1, (0, 0)),
    (0x55, "restoration.jpg", 3, 1, (0, 0)), (0x56, "farming.jpg", 3, 1, (0, 0)),
    (0x57, "nature.jpg", 1, 3, (0, 0)), (0x58, "magic.jpg", 1, 3, (0, 0)),
    (0x59, "research_button.png", 3, 1, (0, 0)), (0x5A, "info_button.png", 3, 1, (0, 0)),
    (0x5B, "VD_BG_2.png", 0, 0, (0, 0)), (0x5C, "map_bathDamage.png", 1, 1, (0, 0)),
    (0x5D, "map_bath_filled.png", 1, 1, (0, 0)), (0x5E, "map_hospitalStates.png", 3, 1, (0, 0)),
    (0x5F, "map_foodbin.png", 5, 1, (0, 0)), (0x60, "cape.png", 1, 1, (0, 0)),
    (0x61, "statueFallen.png", 1, 1, (0, 0)), (0x62, "statueErect.png", 1, 1, (0, 0)),
    (0x63, "waves_proto.png", 10, 1, (0, 0)), (0x64, "yellow_sparkle.png", 10, 1, (0, 0)),
    (0x65, "sparklestrip2.png", 10, 1, (0, 0)), (0x66, "sparklestrip.png", 10, 1, (0, 0)),
    (0x67, "dust2.png", 9, 1, (0, 0)), (0x68, "algae.png", 4, 4, (0, 0)),
    (0x69, "rainbow.png", 10, 1, (0, 0)), (0x6A, "bubble.png", 10, 1, (0, 0)),
    (0x6B, "candlestrip.png", 9, 1, (0, 0)), (0x6C, "firestrip.png", 4, 2, (0, 0)),
    (0x6D, "petalstrip.png", 12, 3, (0, 0)), (0x6E, "waterfallanimA.png", 8, 4, (0, 0)),
    (0x6F, "waterfallanimb.png", 4, 2, (0, 0)), (0x70, "foam.png", 4, 2, (0, 0)),
    (0x71, "carrying.png", 13, 4, (0, 0)), (0x72, "spray.png", 12, 1, (0, 0)),
    (0x73, "sharp_sparkle.png", 10, 1, (0, 0)), (0x74, "blurry_sparkle.png", 10, 1, (0, 0)),
    (0x75, "collectables_small.png", 6, 9, (0, 0)), (0x76, "footprints.png", 15, 1, (0, 0)),
    (0x77, "raindrops.png", 3, 1, (0, 0)), (0x78, "smokestriplight.png", 12, 1, (0, 0)),
    (0x79, "reefFish1.png", 5, 6, (0, 0)), (0x7A, "reefFish2.png", 5, 8, (0, 0)),
    (0x7B, "reefFish3.png", 5, 10, (0, 0)), (0x7C, "beestriplarge_final2.png", 14, 2, (0, 0)),
    (0x7D, "bubblestrip.png", 9, 1, (0, 0)), (0x7E, "amppuddle.png", 1, 1, (0, 0)),
    (0x7F, "woodpile.png", 1, 1, (0, 0)), (0x80, "scaffolding.png", 1, 1, (0, 0)),
    (0x81, "graves.png", 4, 1, (0, 0)), (0x82, "firestrip.png", 4, 2, (0, 0)),
    (0x83, "graveflowers.png", 3, 1, (0, 0)), (0x84, "female_heads.png", 8, 30, (0, 0)),
    (0x85, "female_heads_old.png", 8, 30, (0, 0)), (0x86, "female_bodies", 32, 30, (2, 3)),
    (0x87, "female_actions", 17, 30, (1, 3)), (0x88, "male_heads.png", 8, 30, (0, 0)),
    (0x89, "male_heads_old.png", 8, 30, (0, 0)), (0x8A, "male_bodies", 32, 30, (2, 3)),
    (0x8B, "male_actions", 17, 30, (1, 3)), (0x8C, "ghosts5.png", 0, 0, (0, 0)),
    (0x8D, "peep_shadow1.png", 0, 0, (0, 0)), (0x8E, "skelly.png", 4, 1, (0, 0)),
    (0x8F, "ripple.png", 4, 1, (0, 0)), (0x90, "sunbeam.png", 0, 0, (0, 0)),
    (0x91, "sundisk.png", 3, 1, (0, 0)), (0x92, "map_fog.png", 0, 0, (0, 0)),
    (0x93, "AlchemyLab.png", 3, 1, (0, 0)), (0x94, "canopy.png", 0, 0, (0, 0)),
    (0x95, "door.png", 0, 0, (0, 0)), (0x96, "doorframe.png", 0, 0, (0, 0)),
    (0x97, "doorKeys_small.png", 3, 1, (0, 0)), (0x98, "herb_magic.png", 0, 0, (0, 0)),
    (0x99, "herb_nature.png", 0, 0, (0, 0)), (0x9A, "sciencelab.png", 3, 1, (0, 0)),
    (0x9B, "tree_overhang.png", 0, 0, (0, 0)), (0x9C, "AlchemyLab0.png", 0, 0, (0, 0)),
    (0x9D, "AlchemyLab1.png", 0, 0, (0, 0)), (0x9E, "AlchemyLab2.png", 0, 0, (0, 0)),
    (0x9F, "AlchemyLab3.png", 0, 0, (0, 0)), (0xA0, "AlchemyLab4.png", 0, 0, (0, 0)),
    (0xA1, "hut_states.png", 2, 2, (0, 0)), (0xA2, "clothinghut_states.png", 2, 2, (0, 0)),
    (0xA3, "orchard_dirtMound.png", 0, 0, (0, 0)), (0xA4, "bananaDecals.png", 7, 1, (0, 0)),
    (0xA5, "mangoDecals.png", 5, 1, (0, 0)), (0xA6, "papayaDecals.png", 6, 1, (0, 0)),
    (0xA7, "bananaTree_bare.png", 0, 0, (0, 0)), (0xA8, "mangoTree_bare.png", 0, 0, (0, 0)),
    (0xA9, "papayaTree_bare.png", 0, 0, (0, 0)), (0xAA, "RainLift.png", 4, 2, (0, 0)),
    (0xAB, "RainLiftBroke.png", 0, 0, (0, 0)), (0xAC, "bird.png", 12, 1, (0, 0)),
    (0xAD, "bird_shadow.png", 1, 1, (0, 0)), (0xAE, "sharkstripfinal.png", 8, 1, (0, 0)),
    (0xAF, "dragonflies.png", 6, 4, (0, 0)), (0xB0, "hummingbirdstrip.png", 4, 2, (0, 0)),
    (0xB1, "bath_plans.png", 0, 0, (0, 0)), (0xB2, "statue_plans.png", 0, 0, (0, 0)),
    (0xB3, "rosterbush.png", 4, 2, (0, 0)), (0xB4, "awards.png", 5, 2, (0, 0)),
)

# Sprites the exe builds by name, outside the table: (file, columns, rows, where).
DIRECT = (
    ("clamStates.png", 2, 1, "0x43296E"), ("doorKeys.png", 3, 1, "0x4329A7"), ("ruinsRubble.png", 3, 1, "0x4360FE"),
    ("SPLASH_BG.JPG", 1, 1, "0x46C509"), ("SPLASH1_BG.JPG", 1, 1, "0x46C553"), ("SPLASH2_BG.JPG", 1, 1, "0x46C59D"),
    ("SPLASH3_BG.JPG", 1, 1, "0x46C5E7"), ("menu_logo.png", 1, 1, "0x4261A0"), ("loading_logo.png", 1, 1, "0x4261E5"),
    ("ldwBurweed27.png", 1, 1, "0x4244D9 (font)"), ("ldwarialbold.png", 1, 1, "0x424569 (font)"),
)
MAP_TILES = tuple((f"MapX{x}Y{y}.jpg", 512 * x, 512 * y) for x in range(4) for y in range(4))   # 0x422F20
FONTS = ("ldwBurweed27.png", "ldwarialbold.png")

# Never built by the stock exe (no table entry, no constructor names them): listed under Source sheets.
UNUSED_FILES = ("buy_button.png", "opendoor.png")


def entry(rid: int) -> tuple:
    for e in TABLE:
        if e[0] == rid:
            return e
    raise KeyError(rid)


def atlas_of(rid: int) -> pi.Atlas:
    """The sprite 0x42EA80 builds for a resource id, as an Atlas (a whole picture is 1 x 1)."""
    _rid, name, cols, rows, sheets = entry(rid)
    if cols and rows:
        grid = tuple(sheets) if sheets[0] else (1, 1)
        return pi.Atlas(name, cols, rows, grid)
    if cols:
        return pi.Atlas(name, cols, 1)
    return pi.Atlas(name, 1, 1)


def sheet_table() -> list:
    """Every sprite the stock exe constructs (the resource table, then the sprites it builds by name)."""
    out, seen = [], set()
    for rid, name, cols, rows, sheets in TABLE:
        kind = "atlas" if cols and rows else "strip" if cols else "whole"
        a = atlas_of(rid)
        key = (a.name.casefold(), a.cols, a.rows, tuple(a.sheets))
        if key in seen:
            continue
        seen.add(key)
        out.append(pa.SheetSpec(a.name, a.cols, a.rows, tuple(a.sheets), whole=kind == "whole",
                                where=f"resource {rid:#04x} ({kind})"))
    for name, cols, rows, where in DIRECT:
        out.append(pa.SheetSpec(name, cols, rows, whole=(cols, rows) == (1, 1), where=where))
    for name, _x, _y in MAP_TILES:
        out.append(pa.SheetSpec(name, whole=True, where="0x422F20 (village map tile)"))
    return out


# ------------------------------------------------------------------------------------------- plan helpers

def _whole(sheets, name: str, x: int, y: int, alpha: float = 1.0, scale: float = 1.0, what: str = "") -> pi.Draw:
    w, h = sheets.size(name)
    return pi.Draw(name, (0, 0, w, h), x, y, scale, alpha, what)


def _frame(sheets, atlas: pi.Atlas, frame: int, x: int, y: int, alpha: float = 1.0, scale: float = 1.0,
           what: str = "") -> pi.Draw:
    """Frame `frame` of a sheet, as 0x409510 picks it (column frame % columns, row frame / columns)."""
    row, col = pi._cdivmod(frame, atlas.cols)
    name, rect = atlas.cell(sheets.size, col, row)
    return pi.Draw(name, rect, x, y, scale, alpha, what)


def _has(sheets, *names) -> bool:
    return all(sheets.has(n) for n in names)


def _frames_of(sheets, atlas: pi.Atlas, count: int | None = None, label: str = "frame") -> tuple:
    n = atlas.cols * atlas.rows if count is None else count
    return tuple(pa.Frame(f"{label} {k + 1}", (_frame(sheets, atlas, k, 0, 0),)) for k in range(n))


# ------------------------------------------------------------------------------------------- the Tech screen

TECH_BG = 0x51
# 0x4B1F68: (resource, x, y, across) for the seven skills, in the screen's order (0x4649C0).
TECH_BARS = ((0x52, 17, 55, True), (0x53, 17, 158, True), (0x54, 17, 258, True), (0x55, 17, 359, True),
             (0x56, 17, 460, True), (0x57, 367, 146, False), (0x58, 643, 146, False))
TECH_NAMES = ("Science", "Medicine", "Alchemy", "Restoration", "Farming", "Nature", "Magic")
TECH_STEP_ACROSS = 0x5F                 # a horizontal bar's pieces, 95 apart, left to right
TECH_FIRST_DOWN, TECH_STEP_DOWN = 0xEC, 0x76   # a vertical bar's pieces, from 236 below the top, 118 up each
TECH_LEVELS = 3


def tech_pieces(sheets, skill: int, level: int) -> list:
    """0x4649C0: the pieces of a skill's bar for a level (0..3), each a frame of its sheet (fully faded in)."""
    rid, x, y, across = TECH_BARS[skill]
    a = atlas_of(rid)
    out = []
    for k in range(level):
        if across:
            out.append(_frame(sheets, a, k, x + TECH_STEP_ACROSS * k, y, what="tech"))
        else:
            out.append(_frame(sheets, a, k, x, y + TECH_FIRST_DOWN - TECH_STEP_DOWN * k, what="tech"))
    return out


def tech_screen(sheets, levels) -> list:
    """The Tech screen as 0x4649C0 draws it with these levels (no skill selected, every piece faded in)."""
    out = [_whole(sheets, atlas_of(TECH_BG).name, 0, 0, what="background")]
    for skill, level in enumerate(levels):
        out += tech_pieces(sheets, skill, level)
    return out


def tech_bar_box(sheets, skill: int) -> tuple:
    """Where a whole bar lies on the screen: its three pieces' box."""
    rid, x, y, across = TECH_BARS[skill]
    w, h = sheets.size(atlas_of(rid).name)
    return (x, y, x + w, y + h)


def _tech_assets(sheets) -> list:
    out = []
    bg = atlas_of(TECH_BG).name
    if not sheets.has(bg):
        return out
    for skill, name in enumerate(TECH_NAMES):
        rid = TECH_BARS[skill][0]
        if not sheets.has(atlas_of(rid).name):
            continue
        left, top, right, bottom = tech_bar_box(sheets, skill)
        under = pi.Draw(bg, (left, top, right, bottom), left, top, what="background")
        frames = [pa.Frame("uncoloured (no level: the screen's own bar)", (under,))]
        for level in range(1, TECH_LEVELS + 1):
            frames.append(pa.Frame(f"level {level} of 3 coloured", (under,) + tuple(tech_pieces(sheets, skill, level))))
        out.append(pa.Asset(f"tech:{skill}", pa.TECH, f"{name} bar", tuple(frames), group="Technology bars",
                            note="the uncoloured bar is the Tech screen picture under the bar's pieces",
                            proof="emulated 0x4649C0"))
        out.append(pa.Asset(f"tech:{skill}:pieces", pa.TECH, f"{name} bar pieces",
                            _frames_of(sheets, atlas_of(rid), label="piece"), group="Technology bars",
                            proof="constructor"))
    frames = tuple(pa.Frame(f"every skill at level {lv}", tuple(tech_screen(sheets, [lv] * 7))) for lv in range(4))
    frames += (pa.Frame("mixed levels", tuple(tech_screen(sheets, [1, 2, 3, 0, 1, 2, 3]))),)
    out.append(pa.Asset("tech:screen", pa.TECH, "Tech screen", frames, proof="emulated 0x4649C0"))
    return out


# ------------------------------------------------------------------------------------------- meters

# 0x42EF60(meter, percent): the Villager Details screen's bars, in 16-pixel slices from x 462.
METER_X, METER_STEP = 462, 16
METERS = ((3, "Skill bar 1", 223), (4, "Skill bar 2", 265), (5, "Skill bar 3", 308),
          (6, "Skill bar 4", 351), (7, "Skill bar 5", 392), (8, "Health", 94))    # which skill is which: not traced
METER_SLICE = {True: "StatusBarSliceR.png", False: "StatusBarSliceB.png"}
HEALTH_BULB = ("healthBarbulb.png", 417, 88)
METER_FILLS = (0, 10, 25, 50, 75, 100)


def meter_slices(percent: int) -> int:
    """0x42EF60: min(100, max(0, percent)) x 256 / 100, then / 16 (C divisions)."""
    p = min(100, max(0, percent))
    return pi._cdivmod(pi._cdivmod(p * 256, 100)[0], 16)[0]


def meter_plan(sheets, meter: int, percent: int) -> list:
    _m, _name, y = next(m for m in METERS if m[0] == meter)
    health = meter == 8
    n = meter_slices(percent)
    out = []
    if health and min(100, max(0, percent)) > 0:
        out.append(_whole(sheets, HEALTH_BULB[0], HEALTH_BULB[1], HEALTH_BULB[2], what="bulb"))
    slice_ = METER_SLICE[health]
    out += [_whole(sheets, slice_, METER_X + METER_STEP * k, y, what="slice")
            for k in range(n)]
    return out


def _meter_assets(sheets) -> list:
    if not _has(sheets, *METER_SLICE.values(), HEALTH_BULB[0]):
        return []
    out = []
    for meter, name, _y in METERS:
        frames = tuple(pa.Frame(f"{p}%", tuple(meter_plan(sheets, meter, p))) for p in METER_FILLS if p)
        out.append(pa.Asset(f"meter:{meter}", pa.METERS, f"{name} meter", frames, group="Villager Details",
                            note="0% draws nothing", proof="emulated 0x42EF60"))
    return out


# ------------------------------------------------------------------------------------------- screens

# Pictures the screens draw whole with 0x42EB90(id, x, y, 1.0, 100), at the call's own place.
SCREEN_DRAWS = (
    (0x46C305, 0x25, 0, 0, "Overview map"), (0x46414F, 0x26, 0, 0, "Awards"), (0x464210, 0x3D, 0, 0, "Puzzles"),
    (0x4649E3, 0x51, 0, 0, "Tech screen"), (0x46DCEB, 0x5B, 0, 0, "Villager Details"),
    (0x46607D, 0x28, 0, 0, "Loading"), (0x4660ED, 0x2A, 229, 10, "Loading: game logo"),
    (0x466104, 0x29, 47, 400, "Loading: LDW logo"), (0x46A7E7, 0x43, 0, 0, "Title (box shot)"),
    (0x46A820, 0x2A, 242, 4, "Title: game logo"),
    (0x46594D, 0x3E, 0, 0, "Help page 1"), (0x465964, 0x3F, 0, 0, "Help page 2"),
    (0x46597B, 0x40, 0, 0, "Help page 3"), (0x465992, 0x41, 0, 0, "Help page 4"),
    (0x4659A9, 0x42, 0, 0, "Credits"),
)
SCREEN_GROUPS = (("Loading screen", (0x46607D, 0x4660ED, 0x466104)), ("Title screen", (0x46A7E7, 0x46A820)))


def screen_draw(sheets, rid: int, x: int, y: int) -> pi.Draw:
    """0x42EB90 at 100%: a whole picture at (x, y) (an atlas or strip: its frame 0)."""
    a = atlas_of(rid)
    if (a.cols, a.rows) == (1, 1):
        return _whole(sheets, a.name, x, y)
    return _frame(sheets, a, 0, x, y)


def _screen_assets(sheets) -> list:
    out = []
    by_site = {s[0]: s for s in SCREEN_DRAWS}
    grouped = {site for _n, sites in SCREEN_GROUPS for site in sites}
    for name, sites in SCREEN_GROUPS:
        draws = [by_site[s] for s in sites]
        if all(sheets.has(atlas_of(d[1]).name) for d in draws):
            plan = tuple(screen_draw(sheets, d[1], d[2], d[3]) for d in draws)
            out.append(pa.Asset(f"screen:{name}", pa.SCREENS, name, (pa.Frame("", plan),),
                                note="the pictures only (text and buttons not drawn)",
                                proof="emulated 0x42EB90 at " + ", ".join(hex(s) for s in sites)))
    for site, rid, x, y, label in SCREEN_DRAWS:
        if site in grouped or not sheets.has(atlas_of(rid).name):
            continue
        out.append(pa.Asset(f"screen:{site:x}", pa.SCREENS, label, (pa.Frame("", (screen_draw(sheets, rid, x, y),)),),
                            proof=f"emulated 0x42EB90 at {site:#x}"))
    for name in ("SPLASH_BG.jpg", "main_BG.png", "collection_bg.png", "awards_bg.jpg"):
        if sheets.has(name) and name in ("SPLASH_BG.jpg", "main_BG.png", "collection_bg.png"):
            label = {"SPLASH_BG.jpg": "Splash screen", "main_BG.png": "Main menu",
                     "collection_bg.png": "Collections"}[name]
            out.append(pa.one(sheets, f"screen:{name}", pa.SCREENS, label, name,
                              note="the whole picture (its screen's draw not emulated)", proof="sheet"))
    story = ("image1_page1.jpg", "image1_page2.jpg", "image1_page3.jpg", "image1_page4.jpg", "image1_page5.jpg",
             "midgame_page1.jpg", "midgame_page2.jpg", "midgame_page3.jpg", "story3_page1.jpg", "story3_page2.jpg",
             "story3_page3.jpg", "story3_page4.jpg")
    for name in story:
        if sheets.has(name):
            out.append(pa.one(sheets, f"story:{name}", pa.SCREENS, name.rsplit(".", 1)[0].replace("_", " "), name,
                              group="Story pages", note="whole; how the story mixes its mask pictures is not modelled",
                              proof="sheet"))
    for name in ("image1_page5mask.jpg", "page2_flicker_alphaMask.png"):
        if sheets.has(name):
            out.append(pa.one(sheets, f"story:{name}", pa.SCREENS, name.rsplit(".", 1)[0] + " (mask)", name,
                              group="Story pages", note="a mask picture, shown as it is", proof="sheet"))
    return out


# ------------------------------------------------------------------------------------------- buttons, panels

BUTTON_STATES = ("normal", "mouse over", "pressed")      # 0x4016B0 keeps +0x30: 0 away, 1 over, 2 over and down
BUTTONS = (0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x13, 0x14,
           0x1B, 0x1C, 0x44, 0x59, 0x5A)


def _panel_assets(sheets) -> list:
    out = []
    for rid in BUTTONS:
        a = atlas_of(rid)
        if not sheets.has(a.name):
            continue
        frames = tuple(pa.Frame(state, (_frame(sheets, a, k, 0, 0),)) for k, state in enumerate(BUTTON_STATES))
        out.append(pa.Asset(f"button:{rid}", pa.PANELS, a.name.rsplit(".", 1)[0], frames, group="Buttons",
                            note="cells in the order of the button's state (normal, mouse over, pressed)",
                            proof="emulated 0x42EB90 frames"))
    a = atlas_of(0x17)
    if sheets.has(a.name):
        out.append(pa.Asset("check:strip", pa.PANELS, "Check box", (
            pa.Frame("cell 1", (_frame(sheets, a, 0, 0, 0),)), pa.Frame("cell 2", (_frame(sheets, a, 1, 0, 0),))),
            group="Check boxes and sliders", proof="constructor 0x401150"))
    for name in ("radioblank.png", "radioselected.png", "checkmark.png", "WideSlider2.png", "sliderhandle.png",
                 "VerticalScrollTrack.png", "VerticalScrollKnob.png"):
        if sheets.has(name):
            out.append(pa.one(sheets, f"panel:{name}", pa.PANELS, name.rsplit(".", 1)[0], name,
                              group="Check boxes and sliders", proof="sheet"))
    for rid in (0x11, 0x12):
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"dialog:{rid}", pa.PANELS, a.name.rsplit(".", 1)[0] + " tiles",
                                _frames_of(sheets, a, label="tile"), group="Dialog tiles",
                                note="the nine tiles a dialog is built from; the dialog's own layout is not modelled",
                                proof="constructor"))
    for name in ("arrowglow.png", "arrowglowdown.png", "arrowleftglow.png", "arrowrightglow.png"):
        if sheets.has(name):
            out.append(pa.one(sheets, f"glow:{name}", pa.PANELS, name.rsplit(".", 1)[0], name, group="Tutorial arrows",
                              proof="sheet"))
    return out


# ------------------------------------------------------------------------------------------- scene objects

# The village's scene objects (registry 0x4B0D88), each drawn by its vtable's +0x18 with a queued parameter
# (0x435860).  Positions are the game's own (tables in .data, or set by the object's constructor).
HUTS = ((1025, 870), (1040, 600), (550, 890), (853, 776))        # 0x4B09EC: three huts, then the clothing hut
HUT_SCAFFOLD = ((0, 110), (88, 75))                               # 0x4B09A4: the two scaffolds, from the hut
HUT_REGISTRY = 0x15
HUT_STAGES = ("being built, 1", "being built, 2", "being built, 3", "finished")
STATUE_AT, STATUE_SCAFFOLD = (700, 460), (790, 235)
RAINLIFT_AT, RAINLIFT_BROKE_AT = (1477, 845), (1520, 824)
RUBBLE = ((0x4C8, 0x726), (0x4C4, 0x728), (0x4C7, 0x73F), (0x460, 0x727), (0x4C5, 0x715), (0x528, 0x723),
          (0x4CA, 0x728), (0x480, 0x73F), (0x500, 0x729), (0x4CD, 0x727))                     # 0x436277
RUBBLE_SCAFFOLD = ((1240, 1880), (1270, 1830))                     # 0x4B1068
ROSTER = ((0x76B, 0x58F), (0x773, 0x5D7), (0x78D, 0x5D6), (0x7A6, 0x5D4), (0x762, 0x5BC), (0x7A7, 0x59D),
          (0x7AF, 0x5D7), (0x7AF, 0x5C4))                                                     # 0x435F14
ALCHEMY_SPOTS = ((310, 1970), (1245, 1968), (110, 1323), (1381, 506), (1545, 1000))       # 0x593B40 + 0x10
PLANS_AT = (265, 1266)                                             # 0x4B08B0
KEYS = ((881, 1052), (1945, 925), (1854, 279))                     # 0x594690 +0x14, +0x20, +0x2C
CLAM_AT = (1830, 235)                                              # 0x4B0A2C
SUNDISK_AT, SUNBEAM_AT = (124, 432), (0, -200)                    # 0x4B1158, 0x4B1160
WOODPILE_AT = (901 - 40, 1032 + 12)                                # 0x4B0B44 less (40, -12)

HUT_SHEETS = (pi.Atlas("hut_states.png", 2, 2), pi.Atlas("clothinghut_states.png", 2, 2))
SCAFFOLD = "scaffolding.png"


def hut_plan(sheets, hut: int, stage: int) -> list:
    """0x432110 with parameter ((stage + 2) << 24) | ((hut + 1) << 16): the hut's picture for its stage, frame
    `stage` of hut_states.png (clothinghut_states.png for the clothing hut, 3) at the hut's place."""
    x, y = HUTS[hut]
    return [_frame(sheets, HUT_SHEETS[1 if hut == 3 else 0], stage, x, y, what="hut")]


def hut_scaffold_plan(sheets, hut: int, which: int) -> list:
    """0x432110 with parameter (which << 24) | ((hut + 1) << 16): a scaffold beside the hut."""
    x, y = HUTS[hut]
    dx, dy = HUT_SCAFFOLD[which]
    return [_whole(sheets, SCAFFOLD, x + dx, y + dy, what="scaffold")]


def hut_building_plan(sheets, hut: int, stage: int, progress: int) -> list:
    """A hut being built as the camera's queue orders it (0x432410): scaffold 1 from 1 point of work, scaffold 2
    from 50, both in layer 6 keyed by the hut's y + 45; the hut keyed by its y + 110 (+ 75 for huts 2-4), in
    layer 3 at stage 0 (under the scaffolds) and layer 6 after (over them)."""
    y = HUTS[hut][1]
    queue = []                                  # (layer << 16) + key, in the order 0x432410 queues them
    if progress >= 1:
        queue.append(((6 << 16) + y + HUT_SCAFFOLD[0][1] + 0x2D, hut_scaffold_plan(sheets, hut, 0)))
    if progress >= 50:
        queue.append(((6 << 16) + y + HUT_SCAFFOLD[1][1] + 0x2D, hut_scaffold_plan(sheets, hut, 1)))
    layer = 3 if stage < 1 else 6
    queue.append(((layer << 16) + y + (0x6E if hut == 0 else 0x4B), hut_plan(sheets, hut, stage)))
    out = []
    for _key, plan in sorted(queue, key=lambda q: q[0]):       # 0x42E2A0's insertion sort keeps ties in order
        out += plan
    return out


def rubble_pieces(progress: int) -> int:
    """0x436200: max(1, (100 - progress) x 10 / 100)."""
    return max(1, pi._cdivmod((100 - progress) * 10, 100)[0])


def rubble_plan(sheets, progress: int) -> list:
    a = pi.Atlas("ruinsRubble.png", 3, 1)
    return [_frame(sheets, a, k % 3, x, y, what="rubble") for k, (x, y) in enumerate(RUBBLE[:rubble_pieces(progress)])]


def roster_bushes(progress: int) -> int:
    """0x435EA5: max(1, (100 - progress) x 8 / 100)."""
    return max(1, pi._cdivmod((100 - progress) * 8, 100)[0])


def roster_plan(sheets, progress: int) -> list:
    a = atlas_of(0xB3)
    return [_frame(sheets, a, 7 - k, x, y, what="bush") for k, (x, y) in enumerate(ROSTER[:roster_bushes(progress)])]


def _building_assets(sheets) -> list:
    out = []
    if _has(sheets, "hut_states.png", "clothinghut_states.png", SCAFFOLD):
        for hut in range(4):
            label = "Clothing hut" if hut == 3 else f"Hut {hut + 1}"
            frames = [pa.Frame(stage, tuple(hut_plan(sheets, hut, s))) for s, stage in enumerate(HUT_STAGES)]
            frames += [pa.Frame(f"{HUT_STAGES[s]}, with scaffolds", tuple(hut_building_plan(sheets, hut, s, 50)))
                       for s in range(3)]
            out.append(pa.Asset(f"hut:{hut}", pa.BUILDINGS, label, tuple(frames), group="Huts",
                                proof="emulated 0x432110"))
    if _has(sheets, "statueFallen.png", "statueErect.png", SCAFFOLD):
        out.append(pa.Asset("statue", pa.BUILDINGS, "Statue", (
            pa.Frame("fallen", (_whole(sheets, "statueFallen.png", *STATUE_AT),)),
            pa.Frame("being raised", (_whole(sheets, "statueFallen.png", *STATUE_AT),
                                      _whole(sheets, SCAFFOLD, *STATUE_SCAFFOLD))),
            pa.Frame("raised", (_whole(sheets, "statueErect.png", *STATUE_AT),))),
            group="Statue", note="'being raised': each blit is the game's; which is drawn over the other (the "
                                 "camera queue's order) is not proven",
            proof="emulated 0x435000"))
    if _has(sheets, "RainLift.png", "RainLiftBroke.png"):
        a = atlas_of(0xAA)
        frames = tuple(pa.Frame(f"working, frame {k + 1}", (_frame(sheets, a, k, *RAINLIFT_AT),)) for k in range(8))
        frames += (pa.Frame("broken", (_whole(sheets, "RainLiftBroke.png", *RAINLIFT_BROKE_AT),)),)
        out.append(pa.Asset("rainlift", pa.BUILDINGS, "Rain lift", frames, group="Rain lift",
                            proof="emulated 0x435B60"))
    if _has(sheets, "ruinsRubble.png", SCAFFOLD):
        frames = tuple(pa.Frame(f"{p}% cleared ({rubble_pieces(p)} pieces)", tuple(rubble_plan(sheets, p)))
                       for p in range(0, 100, 10))
        frames += tuple(pa.Frame(f"scaffold {k + 1}", (_whole(sheets, SCAFFOLD, *RUBBLE_SCAFFOLD[k]),)) for k in range(2))
        out.append(pa.Asset("rubble", pa.BUILDINGS, "Ruins rubble", frames, group="Ruins",
                            proof="emulated 0x436190"))
    if sheets.has("rosterbush.png"):
        frames = tuple(pa.Frame(f"{p}% cleared ({roster_bushes(p)} bushes)", tuple(roster_plan(sheets, p)))
                       for p in range(0, 100, 13))
        out.append(pa.Asset("rosterbush", pa.PLANTS, "Bushes", frames, group="Bushes",
                            proof="emulated 0x435E90"))
    names = [f"AlchemyLab{k}.png" for k in range(5)]
    if _has(sheets, *names):
        frames = tuple(pa.Frame(f"spot {k + 1}", (_whole(sheets, names[k], *ALCHEMY_SPOTS[k]),)) for k in range(5))
        frames += (pa.Frame("all five", tuple(_whole(sheets, names[k], *ALCHEMY_SPOTS[k]) for k in range(5))),)
        out.append(pa.Asset("alchemy:spots", pa.BUILDINGS, "AlchemyLab0-4", frames, group="City",
                            proof="emulated 0x42FBA0"))
    for rid, label in ((0xB1, "Bath plans"), (0xB2, "Statue plans")):
        name = atlas_of(rid).name
        if sheets.has(name):
            out.append(pa.Asset(f"plans:{rid}", pa.ICONS, label, (pa.Frame("", (_whole(sheets, name, *PLANS_AT),)),),
                                group="Plans", note="drawn fading in; shown fully in", proof="emulated 0x431E80"))
    return out


def _puzzle_assets(sheets) -> list:
    out = []
    keys, clam = pi.Atlas("doorKeys.png", 3, 1), pi.Atlas("clamStates.png", 2, 1)
    if sheets.has(keys.name):
        frames = tuple(pa.Frame(f"key {k + 1} where it lies", (_frame(sheets, keys, k, *KEYS[k]),)) for k in range(2))
        out.append(pa.Asset("puzzle:keys", pa.PUZZLES, "Door keys", frames, group="Door keys",
                            proof="emulated 0x432C10"))
    if _has(sheets, keys.name, clam.name):
        out.append(pa.Asset("puzzle:clam", pa.PUZZLES, "Giant clam", (
            pa.Frame("open, holding the key", (_frame(sheets, clam, 0, *CLAM_AT), _frame(sheets, keys, 2, *KEYS[2]))),
            pa.Frame("closed", (_frame(sheets, clam, 1, *CLAM_AT),))), group="Door keys",
            proof="emulated 0x432C10"))
    return out


def _sun_assets(sheets) -> list:
    out = []
    if sheets.has("sundisk.png"):
        a = atlas_of(0x91)
        out.append(pa.Asset("sundisk", pa.PUZZLES, "Sun disk", tuple(
            pa.Frame(f"state {k + 1}", (_frame(sheets, a, k, *SUNDISK_AT),)) for k in range(3)),
            group="Sun disk", proof="emulated 0x436890"))
    if sheets.has("sunbeam.png"):
        beam = _whole(sheets, "sunbeam.png", *SUNBEAM_AT)
        out.append(pa.Asset("sunbeam", pa.EFFECTS, "Sun beam", (pa.Frame("", (beam, beam, beam)),), group="Sun disk",
                            note="the game blits it three times over itself (fading in; shown fully in)",
                            proof="emulated 0x436890"))
    return out


# ------------------------------------------------------------------------------------------- the orchards

ORCHARD_REGISTRY = 9
TREES = (("Banana", "bananaTree_bare.png", "bananaDecals.png", 7, (0x6E, 0xA0)),
         ("Mango", "mangoTree_bare.png", "mangoDecals.png", 10, (0x72, 0xD4)),
         ("Papaya", "papayaTree_bare.png", "papayaDecals.png", None, (0x4B, 0xB0)))
DIRT = "orchard_dirtMound.png"
# The fruit's places on each tree (0x4343BF, 0x4344F7, 0x434653 ...): filled from the exe by the tests.
FRUIT_SPOTS = (
    ((0x60, 0x80), (0x5A, 0x7F), (0x59, 0x89), (0x68, 0x83), (0x65, 0x73), (0x69, 0x68), (0x5C, 0x65)),
    ((0x1C, 0x70), (0x32, 0x5A), (0x37, 0x87), (0x58, 0x89), (0x73, 0x53), (0x9B, 0x69), (0xB2, 0x2B),
     (0xC8, 0x53), (0xB8, 0x94), (0x7D, 0x58)),
    ((0x47, 0x26), (0x4A, 0x34), (0x4A, 0x4E), (0x4A, 0x5C), (0x48, 0x6D), (0x48, 0x80)),
)
FRUIT_MAX = (7, 10, 6)
TREE_DECALS = (pi.Atlas("bananaDecals.png", 7, 1), pi.Atlas("mangoDecals.png", 5, 1), pi.Atlas("papayaDecals.png", 6, 1))
SAPLING_AGE, GROWN_AGE = 300, 0x7080           # clock units from planting (0x434253, 0x43429A)
F_GROW = pi.f32(3.508771987981163e-05)         # 0x49D1C0
ORCHARD_SPOT = (1000, 1000)                    # where the Studio plants its tree (any place draws the same)


def fruit_count(tree: int, amount: int) -> int:
    """0x434439 ...: amount x max / 333 (the compiler's division), at most the tree's max; one for 5 or more."""
    top = FRUIT_MAX[tree]
    n = min(top, pi._cdivmod(amount * top, 333)[0])
    return 1 if n == 0 and amount >= 5 else n


def grow_scale(age: int) -> float:
    """0x4342A5: 1 - (28800 - age) x 3.5087720e-5, as a 32-bit float."""
    return pi.f32(1.0 - pi.f32((GROWN_AGE - age) * F_GROW))


def orchard_plan(sheets, tree: int, age: int, fruit: int = 0, x: int = ORCHARD_SPOT[0],
                 y: int = ORCHARD_SPOT[1]) -> list:
    """0x4341A0 for one orchard tree planted `age` clock units ago holding `fruit` food."""
    _name, bare, _decals, _top, (ox, oy) = TREES[tree]
    dw, dh = sheets.size(DIRT)
    dirt = _whole(sheets, DIRT, x - pi._cdivmod(dw, 2)[0], y - (dh - 0x12), what="dirt")
    if age < SAPLING_AGE:
        return [dirt]
    if age < GROWN_AGE:
        s = grow_scale(age)
        tx, ty = int(x - ox * s), int(y - oy * s)
        return [dirt, _whole(sheets, bare, tx, ty, scale=pi.percent_scale(int(100 * s)), what="tree")]
    out = [_whole(sheets, bare, x - ox, y - oy, what="tree")]
    for k in range(fruit_count(tree, fruit)):
        fx, fy = FRUIT_SPOTS[tree][k]
        out.append(_frame(sheets, TREE_DECALS[tree], k, x - ox + fx, y - oy + fy, what="fruit"))
    return out


def _orchard_assets(sheets) -> list:
    out = []
    for tree, (name, bare, decals, _top, _o) in enumerate(TREES):
        if not _has(sheets, bare, decals, DIRT):
            continue
        frames = [pa.Frame("just planted", tuple(orchard_plan(sheets, tree, 0)))]
        for k, age in enumerate((SAPLING_AGE, 7500, 15000, 22500, GROWN_AGE - 1)):
            frames.append(pa.Frame(f"growing, {k + 1}", tuple(orchard_plan(sheets, tree, age))))
        for n in range(FRUIT_MAX[tree] + 1):
            amount = next(a for a in range(0, 400) if fruit_count(tree, a) == n)
            frames.append(pa.Frame("grown, no fruit" if n == 0 else f"grown, {n} fruit",
                                   tuple(orchard_plan(sheets, tree, GROWN_AGE, amount))))
        out.append(pa.Asset(f"tree:{tree}", pa.PLANTS, f"{name} tree", tuple(frames), group="Fruit trees",
                            note="mango fruit 6-10 repeat the last fruit picture (the sheet has 5)",
                            proof="emulated 0x4341A0"))
    return out


# ------------------------------------------------------------------------------------------- the overview map

# 0x428EF0(scale, x, y) draws the overview's list of the village's places (0x428E60 whole, 0x428EA0 a frame,
# filled by 0x4290B0 from the game's state) at (x + trunc(px x scale), y + trunc(py x scale)), at
# trunc(scale x 100) percent; the overview (0x46C330) passes (0.20703125, 0xBC, 0x3D).
OVERVIEW_SCALE, OVERVIEW_AT = pi.f32(0.20703125), (0xBC, 0x3D)
# (label, sheet, frame or None, place in the village) as 0x4290B0 lists them.
OVERVIEW_PLACES = (
    ("Bath, filled", "map_bath_filled.png", None, (0xEA, 0x6DB)),
    ("Bath, damaged", "map_bathDamage.png", None, (0x13A, 0x75D)),
    ("Bath scaffold 1", "scaffolding.png", None, (0x12C, 0x794)),
    ("Bath scaffold 2", "scaffolding.png", None, (0x190, 0x79E)),
    ("Hospital, straw beds", "map_hospitalStates.png", 0, (0x434, 0x59F)),
    ("Hospital, mats", "map_hospitalStates.png", 1, (0x434, 0x59F)),
    ("Hospital, sleeping bags", "map_hospitalStates.png", 2, (0x434, 0x59F)),
    ("Puddle", "amppuddle.png", None, (0x1CD, 0x259)),
    ("Cape", "cape.png", None, (0x1DE, 0x232)),
) + tuple((f"Food bin, {k + 1} of 5", "map_foodbin.png", k, (0x43C, 0x471)) for k in range(5))
FOOD_BIN_LIMITS = (150, 1000, 2500, 4000)      # 0x4292B0: food below each -> picture 1, 2, 3, 4; else 5
OVERVIEW_BY_LABEL = {p[0]: p for p in OVERVIEW_PLACES}


def overview_list(bath_done: bool, bath_work: int, hospital: int, puddle: int, cape_worn: bool, food: int) -> list:
    """0x4290B0's list of the overview's places for a village state (collectables left out): the bath (filled
    once built, else damaged with a scaffold while its work is 1-84% and 51-94%), the hospital for its level
    1-3, the puddle when its value is over 50, the cape unless someone wears it, the food bin by the food."""
    out = []
    if bath_done:
        out.append(OVERVIEW_BY_LABEL["Bath, filled"])
    else:
        out.append(OVERVIEW_BY_LABEL["Bath, damaged"])
        if 0 < bath_work < 0x55:
            out.append(OVERVIEW_BY_LABEL["Bath scaffold 1"])
        if 0x32 < bath_work < 0x5F:
            out.append(OVERVIEW_BY_LABEL["Bath scaffold 2"])
    if hospital in (1, 2, 3):
        out.append(OVERVIEW_PLACES[3 + hospital])
    if puddle > 0x32:
        out.append(OVERVIEW_BY_LABEL["Puddle"])
    if not cape_worn:
        out.append(OVERVIEW_BY_LABEL["Cape"])
    k = next((i for i, limit in enumerate(FOOD_BIN_LIMITS) if food < limit), 4)
    out.append(OVERVIEW_BY_LABEL[f"Food bin, {k + 1} of 5"])
    return out


def overview_place(sheets, sheet: str, frame, px: int, py: int) -> pi.Draw:
    s = OVERVIEW_SCALE
    x, y = OVERVIEW_AT[0] + int(px * s), OVERVIEW_AT[1] + int(py * s)
    scale = pi.percent_scale(int(s * 100.0))
    if frame is None:
        return _whole(sheets, sheet, x, y, scale=scale)
    rid = {"map_hospitalStates.png": 0x5E, "map_foodbin.png": 0x5F}[sheet]
    return _frame(sheets, atlas_of(rid), frame, x, y, scale=scale)


def _overview_assets(sheets) -> list:
    out = []
    for label, sheet, frame, (px, py) in OVERVIEW_PLACES:
        if sheets.has(sheet):
            out.append(pa.Asset(f"overview:{label}", pa.BUILDINGS, label,
                                (pa.Frame("", (overview_place(sheets, sheet, frame, px, py),)),),
                                group="On the overview map", proof="emulated 0x428EF0"))
    bg = "overview_bg.jpg"
    if sheets.has(bg) and all(sheets.has(p[1]) for p in OVERVIEW_PLACES):
        states = (("a new village", (False, 0, 0, 0, False, 0)),
                  ("the bath being built, the hospital opened", (False, 60, 1, 0, False, 1200)),
                  ("everything built", (True, 100, 3, 60, True, 5000)))
        frames = []
        for label, state in states:
            plan = (_whole(sheets, bg, 0, 0),) + tuple(overview_place(sheets, s, f, px, py)
                                                       for _l, s, f, (px, py) in overview_list(*state))
            frames.append(pa.Frame(label, plan))
        out.append(pa.Asset("overview:map", pa.SCENE, "Overview map", tuple(frames),
                            note="the background and the village's places (collectables and villagers not drawn)",
                            proof="emulated 0x42EB90, 0x4290B0 and 0x428EF0"))
    return out


# ------------------------------------------------------------------------------------------- effects, creatures

EFFECT_STRIPS = (0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F, 0x70, 0x72, 0x73,
                 0x74, 0x76, 0x77, 0x78, 0x7D)
CREATURE_STRIPS = ((0x79, "Reef fish 1"), (0x7A, "Reef fish 2"), (0x7B, "Reef fish 3"), (0x7C, "Bees"),
                   (0xAE, "Shark"), (0xAF, "Dragonflies"), (0xB0, "Hummingbird"))
BIRD_FRAMES = 12


def _effect_assets(sheets) -> list:
    out = []
    for rid in EFFECT_STRIPS:
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"effect:{rid}", pa.EFFECTS, a.name.rsplit(".", 1)[0], _frames_of(sheets, a),
                                group="Animations", note="each frame as the effect draw 0x429610 draws it",
                                proof="emulated 0x429610 (frames)"))
    for rid, label in CREATURE_STRIPS:
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"creature:{rid}", pa.CREATURES, label, _frames_of(sheets, a), group="Animals",
                                note="every frame of the sheet in order; the creature's own draw is not emulated",
                                proof="constructor"))
    if _has(sheets, "bird.png", "bird_shadow.png"):
        a = atlas_of(0xAC)
        frames = tuple(pa.Frame(f"frame {k + 1}", tuple(bird_plan(sheets, k, 0, 0))) for k in range(BIRD_FRAMES))
        out.append(pa.Asset("creature:bird", pa.CREATURES, "Bird", frames, group="Birds",
                            note="with its shadow, on the ground", proof="emulated 0x4249E0"))
    return out


def bird_plan(sheets, frame: int, x: int, y: int, height: int = 0) -> list:
    """0x4249E0 for a bird flying (state 1, not landing): its shadow at (x, y - height + 3), then frame `frame` of
    bird.png at (x, y - height), both at the bird's alpha (100)."""
    return [_whole(sheets, "bird_shadow.png", x, y - height + 3, what="shadow"),
            _frame(sheets, atlas_of(0xAC), frame, x, y - height, what="bird")]


# ------------------------------------------------------------------------------------------- the rest

def _village_assets(sheets) -> list:
    out = []
    if all(sheets.has(n) for n, _x, _y in MAP_TILES):
        plan = tuple(_whole(sheets, n, x, y, what="tile") for n, x, y in MAP_TILES)
        out.append(pa.Asset("scene:village", pa.SCENE, "The village (16 map tiles)", (pa.Frame("", plan),),
                            note="the tiles at the places their loader 0x422F20 gives them", proof="emulated 0x422F20"))
    for name, label in (("canopy.png", "Canopy"), ("tree_overhang.png", "Tree overhang"), ("Map_Fog.png", "Fog"),
                        ("Map_Cloud01.png", "Cloud")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"scene:{name}", pa.SCENE, label, name, proof="sheet"))
    for rid, label in ((0x93, "Alchemy lab"), (0x9A, "Science lab")):
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"lab:{rid}", pa.BUILDINGS, label, _frames_of(sheets, a, label="state"), group="City",
                                proof="constructor"))
    for name, label in (("Door.png", "Door"), ("doorframe.png", "Door frame")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"city:{name}", pa.BUILDINGS, label, name, group="City", proof="sheet"))
    if sheets.has("woodpile.png"):
        out.append(pa.Asset("woodpile", pa.BUILDINGS, "Wood pile", (pa.Frame("", (
            _whole(sheets, "woodpile.png", *WOODPILE_AT),)),), group="Wood pile", proof="emulated 0x433910"))
    for name, group in (("graves.png", "Graves"), ("graveflowers.png", "Graves")):
        if sheets.has(name):
            a = atlas_of(0x81 if name == "graves.png" else 0x83)
            out.append(pa.Asset(f"grave:{name}", pa.BUILDINGS, name.rsplit(".", 1)[0], _frames_of(sheets, a, label="kind"),
                                group=group, proof="constructor"))
    for rid, label in ((0x5E, "Hospital"), (0x5F, "Food bin")):
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"map:{rid}", pa.BUILDINGS, label, _frames_of(sheets, a, label="state"),
                                group="Hospital and food" , proof="constructor"))
    for name, label in (("map_bathDamage.png", "Bath, damaged"), ("map_bath_filled.png", "Bath, filled"),
                        ("cape.png", "Cape"), ("amppuddle.png", "Puddle")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"map:{name}", pa.BUILDINGS, label, name, group="Hospital and food",
                              proof="sheet"))
    return out


def _villager_bits(sheets) -> list:
    out = []
    if sheets.has("peep_shadow1.png"):
        out.append(pa.one(sheets, "v:shadow", pa.VILLAGERS, "Shadow", "peep_shadow1.png", proof="sheet"))
    if sheets.has("focus_circle.png"):
        out.append(pa.one(sheets, "v:focus", pa.VILLAGERS, "Selection ring", "focus_circle.png", proof="sheet"))
    for rid, label, alpha in ((0x8E, "Skeleton", 1.0), (0x8F, "Swimming ripple", pi.f32(0.4))):
        a = atlas_of(rid)
        if sheets.has(a.name):
            frames = tuple(pa.Frame(f"frame {k + 1}", (_frame(sheets, a, k, 0, 0, alpha=alpha),)) for k in range(4))
            out.append(pa.Asset(f"v:{rid}", pa.VILLAGERS, label, frames,
                                proof="emulated 0x4605F0 (tests/test_pictures_vv3.py)"))
    if sheets.has("ghosts5.png"):
        out.append(pa.one(sheets, "v:ghost", pa.VILLAGERS, "Ghost", "ghosts5.png",
                          note="it bobs with the clock (0x436890); shown still", proof="sheet"))
    return out


def _collectible_assets(sheets) -> list:
    out = []
    a = atlas_of(0x75)
    if sheets.has(a.name):
        out.append(pa.Asset("collectables", pa.COLLECTIBLES, "Collectables", _frames_of(sheets, a, label="item"),
                            group="In the village", proof="constructor"))
    for rid, label in ((0x4C, "Turtle shells"), (0x4D, "Coral"), (0x4E, "Tablet pieces"), (0x4F, "Feathers")):
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"collection:{rid}", pa.COLLECTIBLES, label, _frames_of(sheets, a, label="piece"),
                                group="Collections screen", proof="constructor"))
    for rid, label in ((0x50, "Door gems"), (0x97, "Door keys (small)")):
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"gems:{rid}", pa.COLLECTIBLES, label, _frames_of(sheets, a), group="Door",
                                proof="constructor"))
    for name, label in (("herb_magic.png", "Magic herb"), ("herb_nature.png", "Nature herb")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"herb:{name}", pa.PLANTS, label, name, group="Herbs", proof="sheet"))
    a = atlas_of(0x36)
    if sheets.has(a.name):
        out.append(pa.Asset("magicplants", pa.PLANTS, "Magic plants and fish", _frames_of(sheets, a, label="cell"),
                            group="Herbs", proof="constructor"))
    for rid, label in ((0x49, "Puzzle pictures, solved"), (0x4A, "Puzzle pictures, covered")):
        a = atlas_of(rid)
        if sheets.has(a.name):
            out.append(pa.Asset(f"puzzlepics:{rid}", pa.PUZZLES, label, _frames_of(sheets, a, label="puzzle"),
                                group="Puzzles screen", proof="constructor"))
    a = atlas_of(0xB4)
    if sheets.has(a.name):
        out.append(pa.Asset("awards", pa.ICONS, "Awards", _frames_of(sheets, a, label="award"), group="Awards",
                            proof="constructor"))
    a = atlas_of(0x71)
    if sheets.has(a.name):
        out.append(pa.Asset("carrying", pa.ICONS, "Carried items", _frames_of(sheets, a, label="item"),
                            group="Carried", proof="constructor"))
    return out


def _small_assets(sheets) -> list:
    out = []
    for name, label in (("hand.png", "Hand"), ("hand_open.png", "Open hand")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"cursor:{name}", pa.CURSORS, label, name, proof="sheet"))
    for name in FONTS:
        if sheets.has(name):
            out.append(pa.one(sheets, f"font:{name}", pa.FONTS, name.rsplit(".", 1)[0], name,
                              note="the whole font picture; its glyph cut (0x402560) is not modelled", proof="sheet"))
    for name, label in (("BambooMeterFrame1.png", "Bamboo meter frame"), ("LoadColor.png", "Loading bar colour")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"meterbit:{name}", pa.METERS, label, name, group="Parts", proof="sheet"))
    for name in ("StatusBarSliceB.png", "StatusBarSliceR.png", "healthBarbulb.png"):
        if sheets.has(name):
            out.append(pa.one(sheets, f"meterbit:{name}", pa.METERS, name.rsplit(".", 1)[0], name, group="Parts",
                              proof="sheet"))
    for name, label in (("ldwLogo.png", "LDW logo"), ("logo1.png", "Game logo")):
        if sheets.has(name):
            out.append(pa.one(sheets, f"logo:{name}", pa.ICONS, label, name, group="Logos", proof="sheet"))
    for name in ("orchard_dirtMound.png",):
        if sheets.has(name):
            out.append(pa.one(sheets, f"plant:{name}", pa.PLANTS, "Dirt mound", name, group="Fruit trees",
                              proof="sheet"))
    for name in UNUSED_FILES:
        if sheets.has(name):
            out.append(pa.Asset(f"unused:{name}", pa.UNUSED, name.rsplit(".", 1)[0],
                                pa.gap_frames(sheets, name) if isinstance(sheets, pa.AssetSheets)
                                else (pa.Frame("whole", (_whole(sheets, name, 0, 0),)),),
                                unused=True, note="no table entry or constructor of the stock exe names it; "
                                + pa.NOT_PLACED, proof="exe scan"))
    return out


# ------------------------------------------------------------------------------------------- the patcher's art

MASK_ART = ASSETS / "vv3_heathen_masks" / "heathen_masks.png"
HOSPITAL_FIXED = ASSETS / "vv3_hospital" / "vvfp_hospitalFixed.png"
GOLDEN_MUSHROOM = ASSETS / "golden_mushroom" / "golden_mushroom.png"
ORIGINS_ICONS = tuple(Path(n) for n in (
    "101-time-warp.png", "102-island-event.png", "103-barrel-of-babies.png", "104-tech-point-doubler.png",
    "105-food-point-doubler.png", "106-grant-youth.png", "107-grant-full-mastery.png", "108-grant-running.png",
    "109-upgrade-checkmark.png", "110-cure-all.png"))
# The release ships the mask atlas inside the Origins companion (vv_pictures_vv3.SHIPPED_DLL, RCDATA 5000).
SHIPPED_DLL = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
MASK_NAMES = ("Blue", "Orange", "Red", "Purple", "Tribal Chief")   # row = mask - 1 (vv_pictures_common.MASK_NAMES)
GOLDEN_FRAME = 0x66 - 0x34            # vvfp_golden_mushroom.c: collectable frame 50


def patcher_images() -> list[str]:
    """Pictures the patcher puts in a patched game's Images (listed as the patcher's, never as unused)."""
    return ["heathen_masks.png"]


def patcher_art() -> dict:
    out = {}
    for name, path in (("vvfp_hospitalFixed.png", HOSPITAL_FIXED), ("golden_mushroom.png", GOLDEN_MUSHROOM)):
        if path.is_file():
            out[name] = path
    if SHIPPED_DLL.is_file():                   # the mask atlas as the release ships it (RCDATA 5000)
        out["heathen_masks.png"] = (SHIPPED_DLL, 10, 5000)
    for path in ORIGINS_ICONS:                  # inside the shipped Origins companion (its largest image)
        where = pa.origins_icon(GAME, int(path.name[:3]))
        if where is not None:
            out["vvfp origins " + path.name] = where
    return out


def _patcher_assets(sheets) -> list:
    out = []
    if sheets.has("heathen_masks.png"):
        a = pi.Atlas("heathen_masks.png", 8, 5)
        frames = tuple(pa.Frame(f"{MASK_NAMES[r] if r < len(MASK_NAMES) else r + 1} mask, facing {c + 1}",
                                (pa.cell_plan(sheets, a, c, r),)) for r in range(5) for c in range(8))
        out.append(pa.Asset("patcher:masks", pa.PATCHER, "Origins masks", frames, patcher=True,
                            note="drawn over the head by the Origins companion (docs/picture-studio-vv3.md)",
                            proof="companion source"))
    if sheets.has("vvfp_hospitalFixed.png"):
        a = pi.Atlas("vvfp_hospitalFixed.png", 3, 1)
        out.append(pa.Asset("patcher:hospital", pa.PATCHER, "Hospital (Fix Vanilla Bugs)",
                            _frames_of(sheets, a, label="state"), patcher=True,
                            note="the stock hospital sheet with the table legs redrawn; cut as the game cuts the stock",
                            proof="constructor"))
    if sheets.has("golden_mushroom.png"):
        out.append(pa.one(sheets, "patcher:golden", pa.PATCHER, "Super-Secret Golden Mushroom", "golden_mushroom.png",
                          patcher=True, note=f"drawn in place of collectable frame {GOLDEN_FRAME + 1}",
                          proof="sheet"))
    for path in ORIGINS_ICONS:
        name = "vvfp origins " + path.name
        if sheets.has(name):
            out.append(pa.one(sheets, f"patcher:{path.name}", pa.PATCHER, path.stem.split("-", 1)[1].replace("-", " "),
                              name, patcher=True, group="Origins icons",
                              note="the patcher's menu icon (not drawn by the game)", proof="sheet"))
    return out


# ------------------------------------------------------------------------------------------- everything

def assets(sheets) -> list:
    out = []
    for part in (_tech_assets, _meter_assets, _screen_assets, _panel_assets, _building_assets, _puzzle_assets,
                 _sun_assets, _orchard_assets, _overview_assets, _effect_assets, _village_assets, _villager_bits, _collectible_assets, _small_assets,
                 _patcher_assets):
        out += part(sheets)
    return out
