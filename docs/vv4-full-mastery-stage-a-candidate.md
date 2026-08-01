# VV4 Full Mastery certified corrected-geometry playtest feature

Generated from clean C6 baseline `577072f5b5205c3a0a857c0645d855bb98ec19d2` plus the repository-owned canonical mockup and direct-resource ABI gate. The exact corrected artifact received independent D13 recertification GO at commit `e9afe69e0461ff986adddb55d743cf091eea598b`; command 7 is available for stock-mode runtime playtesting.

- Canonical mockup SHA-256: `B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24`
- Secondary mockup SHA-256: `AD1B6A8A61F13BBBA2C902E04AB8AD205167FC48034F4D0A7C078A76C756FA30`
- Canonical crop RGBA SHA-256: `B8E9C4DB93F05450689528C5A04A532486771E53DDC23FCF63B0155C7949418B`
- Candidate button PNG SHA-256: `F03D57038CA7745A99C0D7D58A2558A4411828BF3243D85C8BAFE2E04036BE4B` (decoded RGBA `02B42DEAD3673BA5048160C2D337D284215336E39BCEAC52592432839ECB3AD4`)
- Candidate button path: `Images\btn_upgrades_297x35.png`; frames: normal, hover, pressed (99x35 each)
- Button construction: `sub_401C20`, grid 3x1, local 72,4; Tech event 13 and Detail event 2; parent `sub_40C190`.
- Runtime text/style/font helpers and `sub_40D8A0` are absent; the Tech wrapper uses `this+0x74` and paired scalar-destructor cleanup, while Detail uses list-owned `sub_40C300`.
- Runtime wrapper handling validates both the outer wrapper and its inner object at `wrapper+0x10`: only complete wrappers are attached/stored, while an incomplete wrapper is scalar-destroyed with flag 1 and Tech `this+0x74` remains empty. No wrapper vtable `+0x0C`/`+0x10` calls or runtime dimension comparisons are emitted; 297x35/3x1 validation is static and occurs before output mutation.
- The Tech helper emits exact `8B CB` (`mov ecx, ebx`) after clearing `this+0x74` and before `sub_40C340`; its continuation remains `0x43E23D`.
- Companion SHA-256: `4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7`
- Stock installed slot SHA-256: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`
- Expanded installed slot SHA-256: `264A2D79A5184F2CFBEDCB447DBA260EC48101D19ACD9DA188363D9C659F41E6`
- Stock base+mastery render SHA-256: `A01EF593321B12685FFA96BF888FA9ED556C3C2A506DEA7FDE2471FF2E83DA33`
- Expanded base+mastery render SHA-256: `98CD9D3287D9790D0669FAEA155A1832D883AA99EF45BE582C8B2FF6F023C9F9`

The feature exposes command 7 only with its enabled, hash-guarded base dependency. Commands 6/8, village-wide Running/Age bytes, direct skill stores, ownership, Remove, and save-format changes are absent. The candidate is fail-closed on missing or mismatched companion files, preserves stock executables, Cure bytes, certified VV3 stock-mode hashes, and the expanded-256 hold. Independent D13 recertification is complete; runtime player validation remains pending. Expanded-256 remains ON HOLD/fail-closed.
- D13 helper SHA-256: `C7379FB1AFDDD44F06CF48FAEED14C1701D796F5FC2568E10745337DADE13DB1`; Tech constructor: `4BAD0B344BA63130A1A1144CDE740CEBB61E82826FCDBD0171B182A3D8B62FA4`; Detail constructor: `BEC747E7EFC08BBA8BB7B65181B85E0E24AA30E1BBC2C1879206376C4468584E`; command-7 slot: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`; Cure: `2BB7A32344293DCACB4D0359818C6839AC1FBBAEE8F9E3D00DB59C274238D726`.
