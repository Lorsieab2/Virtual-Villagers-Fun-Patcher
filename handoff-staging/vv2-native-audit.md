# VV2 exact-build native audit

Read-only audit. No tracked files were edited.

## Exact input

- Executable: `inputs/vv2-stock-copy/Virtual Villagers - The Lost Children.exe`
- Size: `724992` bytes
- SHA-256: `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`
- IDA Pro: `C:\Program Files\IDA Professional 9.4\idat.exe`
- Export: `handoff-staging/ida-doubler-audit/vv2-native-required.json`

## Native record and handlers

- Native record stride: `0xE48C` (`58508` bytes).
- Active: `+0x30`.
- Health: `+0x52C`.
- Age: `+0x530`.
- Processed/life field: `+0x534`.
- Pregnancy-related field used by native helper: `+0x540`.
- Totem/special marker: `+0x558`.
- Likes: `+0x5F0`, 62 DWORD slots.
- Dislikes: `+0x6E8`, 62 DWORD slots.
- Skills: Farming `+0x7E4`, Building `+0x7E8`, Research `+0x7EC`, Healing `+0x7F0`, Parenting `+0x7F4`.

Exact native routines:

- Tech writer `0x426290`: adds delta to state `+0x2EADC` and statistic/counter `+0x2E4FC`.
- Food writer `0x4262B0`: adds delta to state `+0x2EAA4` and statistic/counter `+0x2E504`.
- Skill writer `0x445430`: selects the five fields above by skill code and clamps each result to `[0,100]`.
- Native life/age updater `0x43B690`; `0x44D4C0` is an internal continuation reached by a jump from this routine, not a mastery evaluator.
- Pregnancy/native helper `0x44B980`.
- Gong handler `0x44E8A0`.
- Island-event routines `0x4204B0` and `0x433600`.
- Duplicate-collectible dispatcher `0x461B10`.

## Exact doubler inventory

IDA found 17 direct calls to `0x426290` and 13 direct calls to `0x4262B0`; no tail-jump calls were found.

Tech exclusions are preserved at immediate return addresses:

`0x4205AC`, `0x434351`, `0x44EA32`, `0x44ED52`, `0x44F202`, `0x463461`, `0x46346D`, `0x463479`.

These cover Island Events, VV2 Gong of Wonder, and duplicate collectibles. Food exclusions are:

`0x420AE9`, `0x433FC6`, `0x44E9C3`, `0x44EDB9`, `0x44F0D9`.

The current wrapper doubles only positive deltas and preserves the native store/statistic writes. Static result: Food Doubler and Tech Doubler are **GO for exact-build producer routing**, with runtime/player verification still pending.

## Requirements audit

| Patch | Result | Evidence/blocker |
|---|---|---|
| Village-wide Origins menu enablement | GO static; runtime pending | Button hook `0x435EF`; action handler `0x437C0`; non-target messages jump to stock `0x4437C5`. |
| Details Origins menu enablement | GO static; runtime pending | Button hook `0x67624`; action handler `0x67720`; non-target messages jump to stock `0x467725`. |
| Village-wide Full Mastery | STOP | Active payload writes raw 100s but bypasses native skill writer/evaluator/statistics/Elder behavior. Source/data metadata is stale: source names `0x44F4E0`/`0x44D4C0`, but `0x44F4E0` is a singleton manager and `0x44D4C0` is the life-updater continuation. |
| Details Full Mastery | STOP | Active details payload writes `90`, not exact `100`, to the five skill fields; it also bypasses native `0x445430` and native side effects. |
| Village-wide Running | STOP | Current route uses 3 Like/Dislike slots, but native VV2 records have 62. It cannot find entries beyond slot 3 and has no native preference transaction/persistence proof. |
| Details Running | STOP | Mutation scans 62 slots, but the Details menu preflight scans only 3; mutation removes Running dislikes before proving a free Like slot or existing-like state, so it can mutate an ineligible villager. It uses raw stores rather than a native preference helper. |
| Village-wide Cure All | STOP | Cure helper only clears sickness at `+0x53C`; it never sets health `+0x52C` from `<80` to `100`. Preflight and mutation also disagree about the `+0x558` exclusion. |
| Details Cure All | STOP | Uses the same shared Cure helper, so the health-restoration requirement is not met. |
| Village-wide Age 18 | STOP | Current route uses raw age/lifecycle writes and does not call native `0x43B690`; native age/statistics/lifecycle behavior is therefore not preserved. |
| Details Make Younger | STOP | Raw writes to `+0x530`, `+0x534`, and pregnancy-related `+0x540`; bypasses native age/pregnancy handlers. |
| Details Age 18 | STOP | Raw writes to `+0x530`, `+0x534`, and `+0x540`; bypasses native age/pregnancy handlers and changes pregnancy-related state. |
| Barrel of Babies | GO static; runtime pending | Custom route calls native capacity helper `0x425860` and native event/dispatch routine `0x433600`; static call path is present. |
| Island Event | STOP for the Origins action | Custom route directly writes the event flag at state `+0x2EAE0` rather than proving the native event handler runs. The doubler’s Island producer exclusions are separately GO static. |
| Food Doubler | GO static; runtime pending | Hooks native food writer `0x4262B0`, doubles only positive eligible producer deltas, and preserves the five required exclusions. |
| Tech Doubler | GO static; runtime pending | Hooks native tech writer `0x426290`, doubles only positive eligible producer deltas, and preserves the eight required exclusions. |

## Native-handler preservation conclusion

Stock non-target UI messages remain routed to their original handlers. The targeted custom actions do not preserve all requested native behavior: mastery, Cure, age, and Running use custom/raw mutations; the configured mastery-evaluator address is not a valid evaluator in this executable. Gong scanning remains on the native `0x44E8A0` path, and its native food/tech calls remain excluded from doubling. This is static call evidence only, not player/runtime proof.
