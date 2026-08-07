# Disabled VV5 Tech and Villager Detail native evidence gate

This additive gate records what must be authenticated before any repair of the
broken VV5 Tech or Villager Detail buttons may be proposed. It is disabled,
catalog-hidden, publication-false, and emits no bytes, hooks, caves, patches,
package, or save access. The UI candidate still exposes exactly four reference
actions and links this record only as absent/pending evidence.

The stock fingerprint is the 991,232-byte `Virtual Villagers - New
Believers.exe` with SHA-256
`92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`.
An executable alone is insufficient: evidence must be bound to an authenticated
complete-folder manifest and authentication receipt.

Known stock facts are pinned without inventing a route: resource `0x6A`, size
`96x39`, local position `(137,2)`, message `8`, event `13`, factory `0x401BD0`,
ownership registration `0x40C680`, Tech constructor `sub_4405F0`, Tech handler
`sub_4415F0`, and Detail draw `sub_44B250`. `0x44B560` is a Detail input/hit-test
method entry, not a callsite. Its first 16 bytes are
`83EC44535556BD7F03000057BF580300`; it allocates `0x44`, saves
`EBX/EBP/ESI/EDI`, and returns with `ret 0xC`. Vtable `0x49A590` also binds
destructor `0x44B9F0`, draw `0x44B250`, and the distinct event method
`0x44BC20` (`83EC18A1A8974D00`, `ret 8`). Stock has no xref to the
candidate-only `.shr` addresses `0x7B22C0` or `0x7B2600`.

Readiness additionally requires exact authenticated stock bytes and
continuations for the constructor and handler; an authenticated candidate EXE,
complete-folder manifest, and machine export identifying the real route/callsite; decoded
instruction boundaries; the `thiscall` receiver; message ABI; register/stack
preservation; child ownership and destructor path; and final-tree range-overlap
proof. Neither stock method entry `0x44B560` nor event method `0x44BC20` may be
relabeled as a proven candidate callsite. The actual candidate route and callsite
remain null/unknown.

Authenticated historical C260 evidence records a separate dependency failure:
the wrapper pushes `0x7B2A64`, one byte after the `SDL_GetWindowFlags` string at
`0x7B2A63`, so it requests `DL_GetWindowFlags` and exits before either menu.
This defect is rejected evidence only; the contract emits no one-byte repair.
The historical lineage is stock `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`,
working-windowed C99 parent `15E04105D84809AC944C9060E140A0AD4DEFB9BFCDFCE9155E68DE1A67A703C7`,
and fullscreen C260 `4D8A13996094567B088D931AB826C76AB8034BFAB2D63957F1408C5199F9934F`.
Historical patches include constructor raw `0x40A24 -> 0x7B2040` and
`0x4AF12 -> 0x7B2100`, Tech raw `0x415F0 -> 0x7B2000`, and Detail raw
`0x4BC20 -> 0x7B20C0`; payload menu calls occur at raw `0xDB00E` and `0xDB0CE`.
These facts explain prior candidates but do not certify current Detail input
ownership, receiver/stack ABI, destructor/HWND behavior, or final-tree composition.

Four independently authenticated player receipts are mandatory: Tech windowed,
Tech fullscreen, Detail windowed, and Detail fullscreen. Each receipt must prove
the click reached the expected dialog and must bind dialog visibility, owner,
centering, and window-mode restoration to the same authenticated folder.

Composition preserves Full Mastery `0xF2000-0xF4000`, Running
`0xF4000-0xF6000`, the final UI range inventory, and zero Full Heal native
ranges. This gate owns no range. Even complete evidence remains publication
false until a separate reviewed implementation and player authorization.
