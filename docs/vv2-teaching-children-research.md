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

## VV3 parity target

VV3's Leadership-level-2 Tribal Chief education route assigns action 55 to the children. The action-55 constructor places callback 42 at the end. Callback case 42 chooses one of five skills with equal odds and adds `RNG(3)+7`, or 7 through 9 points, through the stock capped skill helper.

## Completion-only patch behavior

The former action-construction award at `0x44A7FA` is not patched. A detour at `0x44AB4B`, after all ten response iterations have been constructed for an attendee, appends opcode 17 with private callback ID 127 before calling the original queue finalizer.

The callback dispatcher at `0x461B10` is detoured only for callback 127. Callback 127:

1. uses stock RNG `0x4031A0` with bound 5 to select one of the five contiguous skill fields;
2. uses the same RNG with bound 3 and adds 7, producing 7, 8, or 9 points;
3. caps the selected field at 100;
4. returns to the action runner.

All stock callback IDs execute the displaced dispatcher prologue and original switch. Because callback 127 is the last attendee queue entry, the reward runs once only when that child's full stock lesson queue reaches its end. An interrupted lesson that never reaches the callback earns nothing.

The patch does not change teacher selection, attendance eligibility, lesson frequency, action coordinates, or any earlier queue entry.
