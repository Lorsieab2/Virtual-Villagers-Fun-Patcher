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

Known route facts are pinned without inventing bytes: resource `0x6A`, size
`96x39`, local position `(137,2)`, message `8`, event `13`, factory `0x401BD0`,
ownership registration `0x40C680`, Tech constructor `sub_4405F0`, Tech handler
`sub_4415F0`, Tech dialog target `0x7B22C0`, Detail draw `sub_44B250`, Detail
mouse callsite `sub_44B560`, and Detail dialog target `0x7B2600`.

Readiness additionally requires exact authenticated stock bytes and
continuations for the constructor, handler, and Detail callsite; decoded
instruction boundaries; the `thiscall` receiver; message ABI; register/stack
preservation; child ownership and destructor path; and final-tree range-overlap
proof. The old/current `0x44BC20` location is explicitly rejected and cannot be
reused as evidence or a repair hook.

Four independently authenticated player receipts are mandatory: Tech windowed,
Tech fullscreen, Detail windowed, and Detail fullscreen. Each receipt must prove
the click reached the expected dialog and must bind dialog visibility, owner,
centering, and window-mode restoration to the same authenticated folder.

Composition preserves Full Mastery `0xF2000-0xF4000`, Running
`0xF4000-0xF6000`, the final UI range inventory, and zero Full Heal native
ranges. This gate owns no range. Even complete evidence remains publication
false until a separate reviewed implementation and player authorization.
