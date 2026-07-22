# VV2 Teaching Children Grants Skill research

Supported executable: `Virtual Villagers - The Lost Children.exe`

- Size: `724,992` bytes
- SHA-256: `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`

## Stock lesson path

The VV2 action table identifies `0x15C` as **Teaching children** and `0x15D` as **Attending lessons**. The lesson initializer at virtual address `0x44A4E0` assigns action `0x15C` to the selected teacher, constructs the stock teacher action queue, and then scans all 256 villager records.

For each active record that passes the stock child threshold, the loop beginning at `0x44A793` resets the child's current action, assigns localized action `0x15D`, and builds that child's stock lesson queue. The loop advances by the stock villager-record stride `0xE48C`. The only static caller of `0x44A4E0` is at `0x44F9DC`.

The five integer skill fields are contiguous in each villager record:

- `+0x7E4`: Farming
- `+0x7E8`: Building
- `+0x7EC`: Research
- `+0x7F0`: Healing
- `+0x7F4`: Parenting

## Patch behavior

The five-byte `push 0x96` at file offset `0x4A7FA`, immediately after the Attending lessons text is copied into a confirmed child's status field, is replaced with a jump to unused mapped padding at file offset `0x73CD0`.

The added code:

1. Saves all general-purpose registers.
2. Calls the stock random routine at `0x4031A0` for a value from 0 through 99.
3. Divides that value by five and uses the remainder, 0 through 4, to select one of the five contiguous skill fields. Because 100 is divisible by five, each skill has exactly 20 possible source values.
4. Adds one point only when the chosen field is below 100.
5. Restores registers, reproduces the displaced `push 0x96`, and returns to `0x44A7FF` so the original lesson queue is unchanged.

The reward runs once for every child actually processed by the stock attendee loop. It does not change teacher selection, attendance eligibility, lesson frequency, action coordinates, or the remainder of the action queue.

## Guarded bytes

| File offset | Stock bytes | Patched bytes |
|---|---|---|
| `0x4A7FA` | `6896000000` | `E9D1940200` |
| `0x73CD0` | 44 zero bytes | `606A64E8C8F4F8FF83C40499B905000000F7F98D8493DC0700008338647D02FF00616896000000E9036BFDFF` |
