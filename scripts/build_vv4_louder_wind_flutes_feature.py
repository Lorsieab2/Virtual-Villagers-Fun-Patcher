"""Write The Tree of Life's "Louder Wind Flutes" row (the owner, 2026-11-10: "I would like to make the sound volume
for just the wind flutes a bit louder so they're clearly heard above the game music", then, after hearing a preview
of Flute1 2.5 times louder over song1: "yes make the patch").

THE STOCK GAME (research/stock-executables, capstone, 2026-11-10):
  * The weather update 0x46BE10 plays a wind flute when its timer (+0xC) passes the game clock 0x41DB20.  Setting
    the weather (0x46BC30) clears the timer for every kind but fog (4), which sets it to the clock + 60 + rand(30)
    (0x46BCA0); each flute sets it again the same way.  Then with at least one Wind Flute piece (0x413B90 on set 0x6A) it counts
    the achievement (0x412F90, 0x13) and plays sound 0x8B Flute1.ogg (1-4 pieces), 0x8C Flute3.ogg (5-9) or 0x8D
    Flute5.ogg (10-12) through 0x448E30 at volume 3.0 (the float 0x4AB3A8, read only there).
  * The play 0x448C20 sets the channel's volume to that x the Sound slider ([0x4DA020+0x75C]) x 255
    (FSOUND_SetVolume, FMOD 3.74), so from a third of the slider up the flutes already play at FMOD's full 255.
  * The flutes are recorded quietly (peaks -9.1, -11.7, -11.4 dBFS; average about -26, -29, -28 dBFS) against the
    music's average of about -16 dBFS.
  * Every sound effect is loaded by one call of FSOUND_Sample_Load(FSOUND_FREE, path, 0, 0, 0), 0x40C4E1 in the
    loader 0x40C490 (the startup preload 0x448B80 and the first play 0x448C20 both reach it), via the thunk
    0x47099E.  The real fmod.dll (3.74) loads each flute as mode 0x151 (16-bit, stereo, signed PCM), and
    FSOUND_Sample_Lock hands back the whole sample in one piece, identical (within 1) to a decode of the .ogg.

THE CHANGE: "VVFP VV4 Louder Flutes.dll" (native/vvfp_vv4_louder_flutes) points the call 0x40C4E1 at its own
load_sample, which makes the same call and, for Flute1.ogg, Flute3.ogg and Flute5.ogg only, makes the sample N times
louder through a limiter that keeps every sample at or under -1 dBFS.  N is the patcher window's Louder Wind Flutes
slider (the owner, 2026-11-15: "add an option to control how loud the wind flutes are too! (same slider)" -- a 2x to
100x slider like Classic VV Difficulty's, 5 unless moved), written by the patcher as "VVFP VV4 Louder Flutes.txt"
beside the DLL.  tests/test_vv4_louder_wind_flutes.py runs it by emulation.

MEASURED (the game's own Sounds folder decoded, both sliders at their maximum, where the flutes and the music both
play at FMOD's full 255; "level" is the RMS of the louder half of 50 ms windows; the loudest song, song4, is -12.9
dBFS, song1-3 -14.7 to -15.2):
  stock   Flute1 -22.9, Flute3 -26.5, Flute5 -25.5 dBFS (10 to 14 dB under the music)
  x 2     -16.8, -20.5, -19.5 (no limiting)
  x 5     -9.9, -12.6, -11.7 (0 to 3 dB over the loudest song, 2 to 5 over the others; peaks -1.0)
  x 10    -7.4, -8.3, -7.3
  x 100   -5.9, -6.1, -5.2

One command after the DLL's source changes: this script builds it (scripts/build_vvfp_vv4_louder_flutes.ps1) and
pins it by SHA-256.  --no-build pins what is already built.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROW_ID = "vv4_louder_wind_flutes"
NAME = "Louder Wind Flutes"
DLL_NAME = "VVFP VV4 Louder Flutes.dll"
DLL = ROOT / "assets" / "vv4_louder_flutes" / DLL_NAME
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
LOAD_CALL, LOAD_CALL_STOCK = 0x40C4E1, "E8B8440600"


def description() -> str:
    return (
        "The wind flutes that play in fog once you have found a Wind Flute (every 60 to 89 seconds of the game's "
        "clock while the fog lasts: Flute1 with 1 to 4 flutes found, Flute3 with 5 to 9, Flute5 with 10 to 12) are "
        "made louder, so they are heard clearly over the music. How much louder is the Louder Wind Flutes slider in "
        "the patcher window: 2 to 100 times (a whole number, 5 unless you move it; type it in the box beside the "
        "slider too). The game's own flute recordings are much quieter than its music, and the game already plays "
        "them at full volume, so the sounds themselves are made louder as the game loads them. They never distort: "
        "the loudest moments are held just under the loudest a sound can be, so from about 3 times up the quiet "
        "parts gain the most and every higher number is still louder. At 5 times, with the game's Sound and Music "
        "sliders at their maximum, the flutes are a little louder than the loudest song and clearly louder than the "
        "others. Every other sound, the music, the Sound and Music sliders and when the flutes play are unchanged; "
        "the game's sound files are never changed. **On by default.** **Needs no other "
        "patch.** **Works the same with every other patch and in every population mode.** **Not yet heard in a "
        "running game** (checked with the game's own sound library and by emulation of the stock executable). The "
        "companion is \"VVFP VV4 Louder Flutes.dll\", started by VVFP Startup.dll, and the slider's number is "
        "written beside it in \"VVFP VV4 Louder Flutes.txt\"; saves are never written by it."
    )


def row(dll_sha: str) -> dict:
    return {
        "id": ROW_ID,
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv4",
        "name": NAME,
        "description": description(),
        "output_tag": "Louder Wind Flutes",
        "dependencies": [],
        "behavior_changes": [
            "The sound loader's call of FSOUND_Sample_Load (0x40C4E1 in 0x40C490, every sound effect the game "
            "loads) goes to the companion, which makes the same call; when the file is Flute1.ogg, Flute3.ogg or "
            "Flute5.ogg and FMOD made a 16-bit signed PCM sample, it locks the whole sample (FSOUND_Sample_Lock), "
            "makes it N times louder and unlocks it, N the slider (2 to 100, 5 by default) read at start from "
            "\"VVFP VV4 Louder Flutes.txt\" beside the companion (above 100 is 100, below 2 is 2, none is 5). The "
            "gain goes through a limiter worked out over the whole sample first: each frame's largest gain that keeps "
            "it at or under -1 dBFS (29,204), falling ahead of a loud frame by at most 3 dB per 220 frames and "
            "recovering after it by at most 3 dB per 4,410 frames (24-bit fixed point). Nothing is clipped.",
            "Measured with both sliders at their maximum (the louder half's RMS; the loudest song -12.9 dBFS): "
            "stock -22.9 / -26.5 / -25.5 dBFS (Flute1 / 3 / 5); x 2 -16.8 / -20.5 / -19.5; x 5 -9.9 / -12.6 / "
            "-11.7; x 10 -7.4 / -8.3 / -7.3; x 100 -5.9 / -6.1 / -5.2.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion replaces the one call at run time, only after verifying "
            "its stock bytes; FMOD functions missing from the game's fmod.dll mean nothing is installed.",
            "Every other sound and the music are loaded exactly as before; the volume the game asks for (3.0 x the "
            "Sound slider, 0x4AB3A8), when the flutes play (the weather update 0x46BE10) and which flute plays are "
            "the game's own. A sample that is not 16-bit signed PCM, or that FMOD does not hand back whole, is "
            "left as it is.",
            "The game's sound files are never changed; the companion only reads its setting file and writes nothing "
            "to a save, a villager record or a file; no text is shown.",
        ],
        "evidence_status": ("the real fmod.dll 3.74 loads each flute as 16-bit stereo signed PCM (mode 0x151) and "
                            "hands back the whole sample from FSOUND_Sample_Lock, equal within 1 to a decode of the "
                            ".ogg (a scratch 32-bit probe, 2026-11-10); the companion's install and its scaling are "
                            "emulated on the rendered executable in tests/test_vv4_louder_wind_flutes.py; runtime/"
                            "player confirmation pending"),
        "companion_files": [
            {"source": f"assets/vv4_louder_flutes/{DLL_NAME}", "destination": DLL_NAME, "sha256": dll_sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{LOAD_CALL:X}", "stock_bytes": LOAD_CALL_STOCK, "written_bytes": "E8XXXXXXXX",
             "routine": "the sound loader 0x40C490's call of FSOUND_Sample_Load (the thunk 0x47099E) goes to the "
                        "companion, which makes the same call and makes the three wind flute samples N times "
                        "louder (the slider), held under clipping",
             "installed_by": INSTALLED_BY},
        ],
    }


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> None:
    if "--no-build" not in sys.argv[1:]:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "build_vvfp_vv4_louder_flutes.ps1")], check=True)
    out = ROOT / "data" / f"{ROW_ID}_feature.json"
    out.write_text(json.dumps(row(sha(DLL)), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
