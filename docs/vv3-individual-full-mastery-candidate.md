# VV3 selected-villager Full Mastery candidate (disabled)

This is a disabled, catalog-hidden stock-mode candidate for command 1. It
depends on the existing certified VV3 Origins → Full Mastery → selected
Grant Running chain, and it does not alter the command-7 Full Mastery page or
the command-2 Running route at `0x6DF900`.

The source transaction model performs a complete dry run before the
`Villager Upgrades` OK/Cancel confirmation, captures the five signed DWORD
skills at `+0xEAC..+0xEBC` and preferred-job `+0xEC0`, reacquires the same
physical index/record, writes only below-100 skills through native
`sub_455740`, post-verifies exact 100, calls `sub_462500` exactly once, and
deducts 100,000 once. The preferred-job field is never written or normalized;
stock naming/tie behavior, including Master Parent without a checked
preference, remains authoritative.

Cancel, no-change, dependency, recheck, and funds failures are no-charge and
include `No tech points have been deducted.` Native partial effects are
reported truthfully without claiming rollback. Expanded-256 and unknown or
corrupt inputs fail closed.

The executable command-1 boundary and a separately owned `.vv3im` extension
remain pending independent byte-level proof. Therefore no executable patch is
emitted, and the candidate remains disabled/catalog-hidden.
