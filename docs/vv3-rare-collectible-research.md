# VV3 rare-collectible action research

The supported stock Secret City executable can complete **Pointing out a rare
collectible**, consume its full cooldown, and place no collectible.

The action requires the Tribal Chief flag at villager offset `+0xE80`,
Leadership level 3, and an expired saved cooldown. It assigns action 137 and
immediately advances the cooldown by 82,800 game-clock units. The completed
action queues command type `0x14`, which calls the collectible spawn routine
once and does not inspect or retry its result.

The spawn routine clears the two on-map collectible slots, randomly chooses one
of four regions, and chooses one of that region's four rare collectible IDs.
It then silently rejects the selected ID when:

- an active villager is already targeting that exact collectible ID; or
- the selected ID is 84 through 87 and its collection count is already
  positive.

The action and cooldown remain completed after either rejection. When all four
IDs in the second condition have been collected and there is no target
collision, the stock action therefore has a 25-percent chance to produce
nothing.

The patch reroutes both rejection branches through five bytes of verified stock
NOP padding immediately before the next IDA-defined function. The stub jumps
back to the original category and item selection. It changes no successful
path, collectible table, collection count, spawn region, timing, requirement,
or cooldown.

Supported-build edits:

| File offset | Stock | Patched |
|---:|---|---|
| `0x2DC4F` | `75 2C` | `75 34` |
| `0x2DC5E` | `75 1D` | `75 25` |
| `0x2DC85` | `90 90 90 90 90` | `E9 E6 FE FF FF` |

The last edit uses the first five bytes of an 11-byte stock NOP run ending
before the function at virtual address `0x42DC90`. The three ranges do not
overlap any current VV3 expanded-256 relocation.
