"""Generate the five "Cause of Death" rows.

The owner: "for the games that don't write a cause of death like VV1-VV2,
can you add them please?" -- shown in the game, the way The Secret City, The
Tree of Life and New Believers show it -- then "mention it for all 5 games in
the logs, age of death too" (the age in the game's own units), and "can you
also put the epitaphs for VV1-VV2 too?".

One companion, "VVFP Cause of Death.dll" (native/vvfp_cause_of_death), loaded
by each game's Origins companion (native/shared/cause_bridge.h), which
verifies every site's stock bytes (all or nothing) and writes its detours at
run time.  The rows patch no executable byte.

* A New Home and The Lost Children: the cause recorded at each death, carried
  to the grave at the burial, kept per save slot in a .dat file beside the
  saves, and drawn on the grave popup; A New Home's grave also gets an
  epitaph (The Lost Children's graves already carry one).
* All five: each death written to the Deaths log by "VVFP Parentage
  Export.dll" (WriteDeathRecord).

The DLL is pinned by SHA-256, so re-run this after every rebuild.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DLL = ROOT / "assets" / "cause_of_death" / "VVFP Cause of Death.dll"
INSTALLED_BY = "VVFP Cause of Death.dll, VvfpCauseInstall"

CAUSE_WORDS = ("Old age, Disease, Starvation, Work accident, or Unknown causes")

# (va, stock bytes, what the site is).  The same tables the DLL carries.
DEATH_SITES = {
    "vv1": [
        ("0x42EF05", "C78344030000" "00000000", "the aging step's old-age store (Old age)"),
        ("0x42ECB7", "8B8C0744030000", "the aging step's hunger drain at 200 food or less (Starvation)"),
        ("0x42ED37", "8B8C1744030000", "the aging step's no-food drain (Starvation)"),
        ("0x42EDA3", "8B8C1744030000", "the aging step's sickness drain (Disease)"),
        ("0x43A5B4", "29038B8610E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43A793", "29078B8610E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43A8BA", "29078B9610E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43A9E1", "29078B9610E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43AAE7", "29078B8E10E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43AC9B", "29078B8610E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43B112", "29078B8E10E00300", "a job's 2% injury, rand(15) (Work accident)"),
        ("0x43B2D4", "8B0B83C404", "a job's 2% injury, rand(10) (Work accident)"),
        ("0x43B393", "8B0B83C404", "a job's 2% injury, rand(10) (Work accident)"),
    ],
    "vv2": [
        ("0x43BDEE", "C7832C050000" "00000000", "the aging step's old-age store (Old age)"),
        ("0x43BAEB", "8D84382C050000", "the aging step's hunger drain at 150 food or less (Starvation)"),
        ("0x43BB7E", "8D843A2C050000", "the aging step's no-food drain (Starvation)"),
        ("0x43BC43", "8D843A2C050000", "the aging step's sickness drain (Disease)"),
        ("0x46299C", "2945008B86D474E500", "the Ancient Mosaic's injury, rand(15) (Work accident)"),
        ("0x462AD9", "29078B8ED474E500", "the Lovely Hut's injury, rand(15) (Work accident)"),
        ("0x462C11", "29078B86D474E500", "a hut's injury, rand(15) (Work accident)"),
        ("0x462D48", "29078B96D474E500", "a hut's injury, rand(15) (Work accident)"),
        ("0x462E84", "29078B96D474E500", "a hut's injury, rand(15) (Work accident)"),
        ("0x462F96", "29078B96D474E500", "the Hospital's injury, rand(15) (Work accident)"),
        ("0x463099", "29078B96D474E500", "the Sewing Hut's injury, rand(15) (Work accident)"),
        ("0x463644", "8B4D0083C404", "research's injury, rand(10) (Work accident)"),
        ("0x4638E6", "8B0F83C404", "the Gong restoration's injury, rand(10) (Work accident)"),
        ("0x46404A", "8B0F83C404", "the Vine Wall's injury, rand(10) (Work accident)"),
        ("0x4641B3", "8B4D0083C404", "the Dam's injury, rand(10) (Work accident)"),
    ],
}
FIXED_SITES = {
    "vv1": [
        ("0x448FF9", "BB33000000", "the burial's grave write (carries the cause to the grave slot)"),
        ("0x42E9C3", "C644072800", "an unburied body's decay (no grave)"),
        ("0x436700", "5F5E5D5B81C4CC000000", "the grave popup's Draw epilogue (draws the cause and the epitaph)"),
    ],
    "vv2": [
        ("0x465063", "8B4F6069C98CE40000", "the burial's grave write (carries the cause to the grave slot)"),
        ("0x43B78D", "C644383000", "an unburied body's decay (no grave)"),
        ("0x444790", "8B8D84000000", "the grave panel's Draw, after its Age line (draws the cause)"),
    ],
}
ARBITERS = {
    "vv3": (("0x462670", "8B44240485C0"), ("0x4626B0", "8B4424048B510C")),
    "vv4": (("0x46AF00", "8B44240485C0"), ("0x46AF40", "8B44240401410C")),
    "vv5": (("0x4758B0", "8B44240485C0"), ("0x4758F0", "8B44240401410C")),
}

LOG = ("'Virtual Villagers {n} Deaths Log <n>.txt', in the 'Virtual Villagers Fun Patcher "
       "Logs\\Deaths' folder beside the game's saves (Documents\\LDW\\<game executable name>\\)")
RECORD = ("Each Death record gives the villager's name, their age at death in the game's own "
          "units (20 per year, the value the Village Population log prints as Age), the cause "
          "of death, and their head and body. The log is headed with the village and its save "
          "slot, is created when a village is first saved and again after Start Over (which "
          "deletes it with the village), only ever grows, and starts a new numbered file after "
          "every 256 Death records.")
NEEDS_LOG = ("**The Deaths log is written by Write Births and Conceptions Log to Text File's DLL: "
             "with that patch off, no Deaths log is written.**")

NAMES = {
    "vv1": "Show Cause of Death and Epitaphs on Graves",
    "vv2": "Show Cause of Death on Graves",
    "vv3": "Log Each Death's Cause and Age",
    "vv4": "Log Each Death's Cause and Age",
    "vv5": "Log Each Death's Cause and Age",
}


def description(game: str) -> str:
    n = game[-1]
    if game in ("vv1", "vv2"):
        epitaph = (
            " The grave also gets an epitaph under the name, chosen by the rule those games use at "
            "a burial: a child's is \"Curious and Playful\" or \"Loving and Special\"; an adult's "
            "comes from their best skill (for example \"Strong Arms, Big Heart\" or \"Inspired "
            "Architect\" for a builder, \"Child of the Earth\" or \"Nature's Friend\" for a farmer); "
            "a villager with no skill at all is a \"Respected Citizen\". Those games' Chief, "
            "Esteemed Elder and Scholar epitaphs have no counterpart in A New Home and are not used."
            if game == "vv1" else
            " The Lost Children already writes an epitaph on every grave; that is unchanged."
        )
        return (
            "Shows each dead villager's cause of death on their grave, the way The Secret City, "
            "The Tree of Life and New Believers do: clicking a gravestone shows the cause under "
            f"the age, in those games' own words ({CAUSE_WORDS}). The cause is the one that "
            "killed them -- old age, sickness, hunger or an empty food bin, an injury at work -- "
            "and \"Unknown causes\" for an island event and anything else, which is how those "
            f"games word an island-event death.{epitaph} The game keeps no cause of death, so it "
            "is recorded the moment a villager dies and kept for each save slot in a file beside "
            "the saves ('Virtual Villagers Fun Patcher Data'); Start Over deletes it. "
            + ("**Graves dug before this patch was installed show nothing extra, and a body that "
               "was already lying when it was installed gets its epitaph but no cause: how it died "
               "was never recorded.** " if game == "vv1" else
               "**Graves dug before this patch was installed, and bodies that were already lying "
               "when it was, show no cause: how they died was never recorded.** ") +
            f"Each death is also written to the Deaths log, {LOG.format(n=n)}. {RECORD} "
            f"{NEEDS_LOG} {ORIGINS_BASE_SENTENCE} That base's companion loads this patch's DLL; "
            "if the DLL cannot be loaded, the game runs unchanged."
        )
    first_catch_up = (
        " **Deaths in the time The Secret City catches up when a village is first loaded in a "
        "session (the time that passed while the game was closed) happen before this patch's "
        "DLL is loaded and are not logged; every later death is.**" if game == "vv3" else ""
    )
    return (
        f"Writes every death, as it happens, to the Deaths log, {LOG.format(n=n)}. {RECORD} "
        "The cause is the one the game itself records and shows on the grave, in its own words "
        f"({CAUSE_WORDS}, which is how the game words every island-event death).{first_catch_up} "
        f"{NEEDS_LOG} {ORIGINS_BASE_SENTENCE} That base's companion loads this patch's DLL; "
        "if the DLL cannot be loaded, the game runs unchanged."
    )


def manifest(game: str, sha: str) -> dict:
    n = game[-1]
    if game in ("vv1", "vv2"):
        detours = [{"va": va, "stock_bytes": stock, "routine": what, "installed_by": INSTALLED_BY}
                   for va, stock, what in DEATH_SITES[game] + FIXED_SITES[game]]
        changes = [
            "At each site that can kill (the aging step's old-age store and its sickness, hunger and no-food drains; every work injury), a check made before the site's own instructions records the cause when that change takes a living villager's health to 0 or below; the site's instructions then run unchanged.",
            "Every frame, a villager seen alive on an earlier frame who is now a body, with no site having reported the death, is recorded with \"Unknown causes\" (island events, the Gong of Wonder, the Custom Island Event's \"dies\", an edited save).",
            "At the burial's grave write, the cause recorded for that body is carried to the grave slot; at an unburied body's decay it is dropped.",
            "The grave popup draws the cause one line under its Age line" + (", and the epitaph between the name and Job." if game == "vv1" else "."),
            f"Kept per save slot in 'Virtual Villagers Fun Patcher Data\\Virtual Villagers {n} Graves - Save <n>.dat' (written atomically; an unreadable file is set aside, never overwritten; deleted by Start Over).",
            "Each death is written to the Deaths log through WriteDeathRecord in \"VVFP Parentage Export.dll\" (name, age in age units, cause, head, body).",
        ]
        non_changes = [
            "This row changes no executable bytes: the Origins companion loads the DLL, which detours the listed sites at run time only after verifying every site's stock bytes; any other build installs nothing.",
            "No game value is changed: health, age, the graves and the save are only read. The epitaph's two-way choices use the companion's own random numbers, never the game's.",
            "Nothing is written into the game's grave table or a villager record; the cause and epitaph live only in the patcher's .dat file.",
            "The Statistics row's Villagers Buried hook (VV1 0x448F65, VV2 0x46503B) is a different site and is untouched.",
        ]
    else:
        detours = [{"va": va, "stock_bytes": stock,
                    "routine": ("the health setter" if k == 0 else "the health adder") + " (its first instructions)",
                    "installed_by": INSTALLED_BY}
                   for k, (va, stock) in enumerate(ARBITERS[game])]
        changes = [
            "Every change of health goes through the game's two health arbiters (set and add, each with a cause); at their first instructions, a change that takes a living villager from above 0 to 0 or below is written to the Deaths log with the cause the caller passes, worded as the game's own grave does (string table, Unknown causes for -1).",
        ] + (["New Believers' Reanimate stand-in corpse (set(0, -1) at 0x46FE66) is not a death and is not logged."] if game == "vv5" else [])
        non_changes = [
            "This row changes no executable bytes: the Origins companion loads the DLL, which detours the two arbiters at run time only after verifying their stock bytes; any other build installs nothing.",
            "The arbiters run unchanged: health and cause are written by the game exactly as before. The Statistics row's Villagers Died hooks sit later in the same routines and are untouched.",
        ]
    record = {
        "id": f"{game}_cause_of_death",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": game,
        "name": NAMES[game],
        "description": description(game),
        "output_tag": "Cause of Death",
        "dependencies": [f"{game}_enable_origins_exclusive_features"],
        "needs_on": [{"id": f"{game}_write_parentage_log",
                      "for": "the Deaths log, which that patch's DLL writes (without it no Deaths log is written)"}],
        "behavior_changes": changes,
        "explicit_non_changes": non_changes,
        "companion_files": [
            {"source": "assets/cause_of_death/VVFP Cause of Death.dll",
             "destination": "VVFP Cause of Death.dll", "sha256": sha},
        ],
        "patches": [],
        "runtime_detours": detours,
    }
    return record


def main() -> None:
    sha = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
    for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
        out = ROOT / "data" / f"{game}_cause_of_death_feature.json"
        out.write_text(json.dumps(manifest(game, sha), indent=2) + "\n", encoding="utf-8", newline="\n")
        print("wrote", out.relative_to(ROOT), sha)


if __name__ == "__main__":
    main()
