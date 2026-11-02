# VV2 skin-tone source art

**Hand-authored by the owner in GIMP. Not reproducible by any script — if these
are lost, they must be redrawn by hand.** They are force-added past `.gitignore`
(the whole `research/` tree is normally ignored) for exactly that reason.

## Marking conventions

Two conventions are in use, and they are INVERSES. Check which a file uses
before reading it:

| Art | Magenta `#FF00FF` marks | Skin is |
|---|---|---|
| **Bodies** | the SKIN | the magenta pixels |
| **Heads** | the HAIR + accessories | everything opaque that is NOT magenta |

Heads are inverted because the hair is one large contiguous region, so marking
it is far less work than tracing around the face -- and it leaves the face's
original shading intact.

## Files

`gimp/` -- the owner's working files. `.xcf` keeps the layer masks, so prefer
editing those over the flattened `.png`.

- `*_magenta.png` / `*.xcf` -- magenta-marked art, per the table above
- `*_nohair.png` / `.xcf` -- earlier pass: hair erased to transparency instead
  of marked. Front frames only; the other facings were extrapolated by kNN
  (see `scripts/build_vv2_skin_masks.py`)
- `female_bodies00_singleframe_magenta.png` -- one 3/4-front frame marked, used
  to validate the pipeline before committing to a full sheet

`*_skinmask.png` (this directory) -- GENERATED from the above by
`scripts/build_vv2_skin_masks.py`. Safe to delete and regenerate.

## Recolour

`scripts/build_vv2_skin_atlases.py`, centre method, **K = 0.30**: skin is
re-centred on the target tone so the mean lands exactly on the palette swatch,
with K controlling how much of the original shading survives. K was chosen off a
0.1-0.5 ladder; do not change it without asking.
