"""Game Mechanics, all five games: children's tag and sandcastles, stock first, then "Children Play Tag and Build
Sandcastles" (scripts/build_children_play_feature.py, native/vvfp_children_play).

Every line is read from the stock code (static tracing of reachable code, 2026-11-14):
  * the pastime pick, from the villager's life tick for a child (age below 0x118) with nothing to do: A New Home
    0x4479B0 (called at 0x448299 after the tick's rand(100) > 65), The Lost Children 0x45EE00 (0x4618C9), The Secret
    City 0x45B9B0 (0x45C16A; 0x45BDC9; the potion 0x4269C9), The Tree of Life 0x465260 (0x4658D7), New Believers
    0x46E3F0 (0x46F125); each first gives nothing on rand(100) <= 15;
  * tag: The Lost Children 0x455CF0 (rand(17) case 9, then rand(100) < 5; players: in use, under 0x118, alive, not
    sick, hands empty, at least two); New Believers behaviour 0xEE (rand(14) case 11, then 5%; the recruiter
    0x4710B0: each child rand(100) < 80, up to three in four, at least two).  The Secret City's and The Tree of
    Life's "Playing tag" strings (0x190/0x191, 0x1EB/0x1EC) are never used; A New Home has none;
  * sandcastles: The Secret City 0xC3 -> 0x44DE40 (likers' rand(5) case 4; others' rand(13) case 11, not for a
    child who dislikes Playing), The Tree of Life 0x61 -> 0x4576F0 (likers' rand(6) case 4; others' rand(15) case 11,
    not for a disliker); New Believers registers 0x6A -> 0x45F0B0 (0x46446C) but no code starts 0x6A: DEAD.
"""
from __future__ import annotations

import vv_game_mechanics as gm

FEATURE = {game: f"vv{game}_children_play" for game in range(1, 6)}

STOCK = {
    1: "Children's play: a child with nothing to do picks a pastime, 16 times in 100 nothing, otherwise one of the "
       "game's own play choices, each equally likely. A New Home has no tag and no sandcastles.",
    2: "Children's play: a child with nothing to do picks a pastime, 16 times in 100 nothing. \"Playing tag\" is one "
       "of 17 choices for a child who does not like playing, and then only 5 times in 100 (about 1 pick in 400); "
       "every child who is not sick and has empty hands joins, and it needs at least two. A child who likes playing "
       "never starts it. The Lost Children has no sandcastles.",
    3: "Children's play: a child with nothing to do picks a pastime, 16 times in 100 nothing. \"Making "
       "sandcastles\" is one of 13 choices (one of 5 for a child who likes playing), never for a child who dislikes "
       "playing: one child on the beach below the reef lagoon. The Secret City has no tag (its \"Playing tag\" "
       "words are never used).",
    4: "Children's play: a child with nothing to do picks a pastime, 16 times in 100 nothing. \"Making "
       "sandcastles\" is one of 15 choices (one of 6 for a child who likes playing), never for a child who dislikes "
       "playing: one child on the east beach at the water. The Tree of Life has no tag (its \"Playing tag\" words "
       "are never used).",
    5: "Children's play: a child with nothing to do picks a pastime, 16 times in 100 nothing. \"Playing tag\" is one "
       "of 14 choices for a child who does not like playing, and then only 5 times in 100; each child joins 4 times "
       "in 5, up to three in four of the children, and it needs at least two. The game's own \"Making "
       "sandcastles\" is never started (DEAD: the action exists but nothing in the game starts it).",
}

PATCHED = {
    1: "a child's pick is tag 1 time in 15 and sandcastles 1 time in 15, the usual choices otherwise with their "
       "usual odds (the Golden Child keeps his own choices). Tag: every child who is not sick and has empty hands "
       "joins (the Golden Child too), the starter is \"It\", they run around the village centre, four runs and "
       "pauses each; it needs at least two, otherwise the child picks as usual. Sandcastles: one child, six times "
       "a walk to one of three places on the south beach at the water and twice bent over in the sand",
    2: "a child's pick is the game's own tag 1 time in 15 and sandcastles 1 time in 15, the usual choices "
       "otherwise with their usual odds; never for a child who dislikes playing. Sandcastles: one child, six times "
       "a walk to one of three places on the west beach by the sea and twice bent over in the sand",
    3: "a child's pick is tag 1 time in 15 (also the potion's pick), the usual choices otherwise with their usual "
       "odds; never for a child who dislikes playing. Every child who is not sick, has empty hands and does not "
       "dislike playing joins (never the Tribal Chief), the starter is \"It\", and they run together through the "
       "six places of \"Running around\"; it needs at least two, otherwise the child picks as usual",
    4: "a child's pick is tag 1 time in 15, the usual choices otherwise with their usual odds; never for a child "
       "who dislikes playing. Every child who is not sick, has empty hands and does not dislike playing joins, the "
       "starter is \"It\", and they run together through the six places of \"Running around\"; it needs at least "
       "two, otherwise the child picks as usual",
    5: "a child's pick is the game's own tag 1 time in 15 (without the 5 in 100), the usual choices otherwise with "
       "their usual odds; never for a child who dislikes playing; who joins is the game's own rule",
}


def lines(village: gm.Village) -> list[tuple[str, object]]:
    """The children's-play lines for the Other group: the stock line, then the patch's when it may be in."""
    game = village.game
    out: list[tuple[str, object]] = [(STOCK[game], gm.CODE)]
    if village.has(FEATURE[game]) is not False:
        out.append((gm.patch_words(village, FEATURE[game], PATCHED[game]), gm.CODE))
    return out
