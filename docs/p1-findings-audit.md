# P1 findings audit

Every P1 review finding raised on this repository, checked against `main`.

At the time of writing there are **70 P1 findings across 179 pull requests**.
They break down as:

| | count |
| --- | ---: |
| received a later commit on the same PR | 49 |
| anchored to a file that no longer exists | 4 |
| verified individually below | 17 |

The middle row is not evidence on its own — a finding can be answered in a
later PR, or be the last comment before a merge — so the 17 with neither a
follow-up commit nor a deleted anchor were each checked against the current
tree.

## The 17, and how each stands

| PR | Finding | Status |
| --- | --- | --- |
| #6 | VV3 individual Full Mastery candidate unusable: stale companion pins | Moot — the id is no longer an exposed fun patch (`Unknown fun patch`) |
| #6 | Appearance chooser: cancel after Buy loses 5,000 points | Fixed — refund paths restore the charge on every non-success exit |
| #8 | VV5 collection writers exposed despite fail-closed evidence gates | Fixed — both evidence records are `enabled=false` and the UI status is `disabled_hidden` |
| #8 | Mass Set-Age-18 also shifts `+0x1C3C` / `+0x1C4C` | Resolved by contract — the emitted docstring now states this explicitly and it mirrors the per-villager action |
| #12 | Barrel presentation can consume an unrelated one-shot island event | Fixed — the "seen" byte array is saved and restored around the present |
| #15 | Second Barrel purchase charges again but queues only one event | Fixed — a pending-purchase guard tests the queued-event word before charging |
| #18 | Barrel capacity ignored physical demand across the whole record pool | Fixed — `barrel_room` |
| #22 | Barrel preflight checked room for one child, not three | Fixed — `barrel_room` evaluates room for all three at both preflights |
| #52 | Full Heal charged before reacquiring and verifying the heal set | Fixed — the verification pass over all 150 records and the funds check both run *before* the deduction, with a balance readback after |
| #53 | Clickable Tips used a stock `.shr` VA that moves in Expanded-256 | Fixed — the generator converts through `.text` and no longer references the stock `.shr` VA |
| #53 | Barrel three-slot reservation lost with the mode-dynamic replacement | Fixed — `barrel_room` |
| #73 | `vv4_text_changes.json` missing from the release manifest | Fixed — it is in `build_release.py`'s `FILES` |
| #110 | VV3 "None" skipped when a mask was recovered from an old slot | Fixed — the branch compares against `VV3_GetMaskForRecord`'s recovered value and the stored fingerprint |
| #117 | VV3 `stock` mode raised `KeyError: 'stock'` | Fixed — stock mode renders |
| #123 | VV5 needs the inverse `K / speed`, not `speed * 3600` | Satisfied — VV5 ships `194400 / speed` |
| #138 | Restore the VV2 Origins crash warning | Present in the README; the owner has since retested those rows and they no longer crash |
| #178 ×3 | Pause guard clobbered the flags feeding `jb insufficient` in VV1/VV2/VV4 | Fixed in #179 — the branch consumes the flags before the guard runs |

## Reproducing this

`scripts` has no audit tool; the check was done with the GitHub API:

```
gh api repos/<owner>/<repo>/pulls/<n>/comments    # inline findings
gh pr view <n> --json comments                    # summary / quota notices
```

Filter bodies containing `P1-orange`. Note that `gh pr view` shows only the
review SUMMARY, which can report a completed review while the findings
themselves sit as inline comments — both have to be read.
