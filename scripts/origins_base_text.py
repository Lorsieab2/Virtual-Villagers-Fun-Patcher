"""The sentence every patch that runs on the Origins-exclusive base carries.

Each game's "Enable Origins-Exclusive Features" feature is an INTERNAL
prerequisite: it has no tickbox (src/vv_fun_patcher.py
INTERNAL_ORIGINS_BASE_FEATURE_ID_SET; load_public_fun_patches leaves it out),
and resolve_fun_patch_ids adds it whenever a selected patch depends on it.
Descriptions used to say "**Requires Enable Origins-Exclusive Features**,
whose companion loads this one; without it ... runs unchanged", which told the
player about a tickbox that does not exist and a "without it" case that cannot
occur, and said nothing about the visible side effect: selecting such a patch
alone installs the whole base, Upgrades buttons included.

The generators that describe those patches import this one sentence, so the
wording is the same everywhere and states the side effect.
"""

ORIGINS_BASE_SENTENCE = (
    "**Runs on the Origins-exclusive base, which the patcher installs "
    "automatically with it**, so selecting this patch also adds the Origins "
    "Upgrades buttons to the Tech and Villager Details screens."
)
