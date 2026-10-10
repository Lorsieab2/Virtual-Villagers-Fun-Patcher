"""The player-facing description of the Births and Conceptions log.

The owner's rule is that all five games ship the same log format, so the part
of each game's "Write Births and Conceptions Log to Text File" description that
tells the player what the log is, where it is and what it holds is written
once, here, and every game's generator (scripts/build_vv<N>_parentage_feature.py)
starts its description with it. Only what genuinely differs between the games
-- where the father's details come from, which patch writes VV1's Birth
records -- follows in each generator.

Each statement is checked against native/parentage_export/parentage_export.c:
  * the folder: build_log_path -> vv_save_subfolder_w(
    L"Virtual Villagers Fun Patcher Logs\\Births and Conceptions") under
    Documents\\LDW\\<exe basename> (native/shared/save_folder.c);
  * the file name: "Virtual Villagers <N> Births and Conceptions Log <n>.txt";
  * the roll: RECORDS_PER_FILE = 256, counted by count_records, which matches
    only "Conception " markers, so Birth records never count toward it and a
    birth is appended to the file already holding records (select_log_file's
    for_birth);
  * the Birth fields: WriteParentageBirth prints the child's name, head, body,
    likes, dislikes and skills, and each parent's name, head and body;
  * the Birth records are numbered "Birth <n>" like Conceptions (v1.35.66), by
    count_running_records, which counts an older log's plain "Birth" too;
  * the Arrived records: KIND_ARRIVED, numbered by count_running_records and
    filed like a Birth (native/shared/arrival_backfill.h has the format),
    found by "VVFP Cause of Death.dll" (cod_arrivals.inc).
"""

PLAYER_LOG_DESCRIPTION = (
    "Keeps a plain-text log of the village's conceptions and births in "
    "'Virtual Villagers {game_number} Births and Conceptions Log <n>.txt', in "
    "the 'Virtual Villagers Fun Patcher Logs\\Births and Conceptions' folder "
    "beside the game's saves (Documents\\LDW\\<game executable name>\\). "
    "Each Conception record gives both parents' names, both parents' ages at "
    "conception, both head and body values, both parents' likes and dislikes, "
    "and the number of babies; the mother's age determines the child's age. "
    "Each Birth record gives the child's name, head, body, likes, dislikes and "
    "skills, and its mother's and father's names, heads and bodies. A new "
    "numbered file is started after every 256 Conception records; Birth "
    "records go into the file holding the latest conceptions and do not count "
    "toward that limit. "
    "Each Arrived record, numbered on its own, gives a villager who joined the "
    "village without being born into it -- a new village's founders, an "
    "island event's newcomers, the Barrel of Babies, the Custom Island Event's "
    "new villagers (never a birth): their name, age when they arrived, sex, "
    "head, body, likes, dislikes and skills, and how they came (\"Founder\", the "
    "event's title, \"Barrel of Babies\", \"Custom Island Event\", or "
    "\"unknown\"); villagers who arrived before this record existed get one, "
    "marked \"Recorded afterwards\", only once the player chooses Repair when "
    "the village is loaded. **The Arrived records are found by the Cause of Death patch "
    "(\"Log Every Death ...\"): with it off, none is written.** "
)
