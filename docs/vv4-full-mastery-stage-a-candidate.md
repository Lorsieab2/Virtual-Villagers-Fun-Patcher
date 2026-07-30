# VV4 Full Mastery disabled baked-asset UI candidate

Generated from acceptance contract `cd15e3b581df1e3020cfa022814119a97ba18af3` plus the repository-owned canonical mockup and direct-resource ABI gate. The command-7 record is disabled. Its candidate-only Tech and Detail buttons use the repository-owned canonical mockup crop as a deterministic 297x35 RGBA strip; independent emitted-byte recertification is pending.

- Canonical mockup SHA-256: `B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24`
- Secondary mockup SHA-256: `AD1B6A8A61F13BBBA2C902E04AB8AD205167FC48034F4D0A7C078A76C756FA30`
- Canonical crop RGBA SHA-256: `B8E9C4DB93F05450689528C5A04A532486771E53DDC23FCF63B0155C7949418B`
- Candidate button PNG SHA-256: `F03D57038CA7745A99C0D7D58A2558A4411828BF3243D85C8BAFE2E04036BE4B` (decoded RGBA `02B42DEAD3673BA5048160C2D337D284215336E39BCEAC52592432839ECB3AD4`)
- Candidate button path: `Images\btn_upgrades_297x35.png`; frames: normal, hover, pressed (99x35 each)
- Button construction: `sub_401C20`, grid 3x1, local 72,4; Tech event 13 and Detail event 2; parent `sub_40C190`.
- Runtime text/style/font helpers and `sub_40D8A0` are absent; the Tech wrapper uses `this+0x74` and paired scalar-destructor cleanup, while Detail uses list-owned `sub_40C300`.
- Runtime fail-closed guard calls wrapper vtable slots `+0x0C`/`+0x10` (native `0x401470`/`0x4014B0`) and requires a 99x35 frame before either `sub_40C190` attach; rejected wrappers receive scalar-destructor flag 1, and Tech leaves `this+0x74` null.
- The Tech helper emits exact `8B CB` (`mov ecx, ebx`) after clearing `this+0x74` and before `sub_40C340`; its continuation remains `0x43E23D`.
- Companion SHA-256: `9AC4E365BE55D32AB889E7B7472A1EDA8749B1EB259EA02BA35AB97BE666AF22`
- Stock installed slot SHA-256: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`
- Expanded installed slot SHA-256: `264A2D79A5184F2CFBEDCB447DBA260EC48101D19ACD9DA188363D9C659F41E6`
- Stock base+mastery render SHA-256: `98C685C3AAF2027B99CB1DCB5E8C2EDACC883703AC8BBA5346A42D37FEB57CAB`
- Expanded base+mastery render SHA-256: `B2256BDCB8F978C8E504FC5BC10A4D2611EBD6F373738BB7A9359C17A34D55CF`

The feature exposes command 7 only inside its certified base dependency. Commands 6/8, village-wide Running/Age bytes, direct skill stores, ownership, Remove, and save-format changes are absent. The disabled candidate is fail-closed on missing or mismatched companion files, preserves stock executables, Cure bytes, certified VV3 stock-mode hashes, and the expanded-256 hold. Independent disassembler recertification is required before any enablement or player playtest.
