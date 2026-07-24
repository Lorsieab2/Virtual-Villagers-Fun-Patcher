# VV2 Gong of Wonder Coconuts Fix research

Supported executable: `Virtual Villagers - The Lost Children.exe`

- Size: `724,992` bytes
- SHA-256: `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677`

VV2 stores the coconut-tree resource at global-state offset `+0x2EACC`.
The Gong outcome handler at virtual address `0x44E8A0` contains two separate
resolution paths that write the literal value 30 to this field:

- file offset `0x4E9A9`
- file offset `0x4F18C`

Both stock instructions are:

`mov dword ptr [eax+0x2EACC], 30`

The patch replaces each assignment with an equal-length guarded sequence:

`add dword ptr [eax+0x2EACC], 30`

The remaining three bytes are NOP padding. No other Gong outcome, coconut
consumption rule, starting amount, tree capacity, or food conversion is
changed.
