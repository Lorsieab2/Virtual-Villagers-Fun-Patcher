# VV4 Full Mastery disabled baked-asset UI candidate

Generated from clean C6 baseline `577072f5b5205c3a0a857c0645d855bb98ec19d2` plus the repository-owned canonical mockup and direct-resource ABI gate. The command-7 record is disabled. Its candidate-only Tech and Detail buttons use the repository-owned canonical mockup crop as a deterministic 297x35 RGBA strip; independent emitted-byte recertification is pending. The legacy Cure row is rendered unavailable, command 5 is rejected before charge/dispatch, and the unchanged Cure payload remains withdrawn.

- Canonical mockup SHA-256: `B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24`
- Secondary mockup SHA-256: `AD1B6A8A61F13BBBA2C902E04AB8AD205167FC48034F4D0A7C078A76C756FA30`
- Canonical crop RGBA SHA-256: `B8E9C4DB93F05450689528C5A04A532486771E53DDC23FCF63B0155C7949418B`
- Candidate button PNG SHA-256: `F03D57038CA7745A99C0D7D58A2558A4411828BF3243D85C8BAFE2E04036BE4B` (decoded RGBA `02B42DEAD3673BA5048160C2D337D284215336E39BCEAC52592432839ECB3AD4`)
- Candidate button path: `Images\btn_upgrades_297x35.png`; frames: normal, hover, pressed (99x35 each)
- Button construction: `sub_401C20`, grid 3x1, local 72,4; Tech event 13 and Detail event 2; parent `sub_40C190`.
- Runtime text/style/font helpers and `sub_40D8A0` are absent; the Tech wrapper uses `this+0x74` and paired scalar-destructor cleanup, while Detail uses list-owned `sub_40C300`.
- Runtime wrapper handling performs only the proven null check: nonnull wrappers are attached/stored through the certified ownership paths and null results leave Tech `this+0x74` empty. No wrapper vtable `+0x0C`/`+0x10` calls or runtime dimension comparisons are emitted; 297x35/3x1 validation is static and occurs before output mutation.
- The Tech helper emits exact `8B CB` (`mov ecx, ebx`) after clearing `this+0x74` and before `sub_40C340`; its continuation remains `0x43E23D`.
- Companion SHA-256: `9AC4E365BE55D32AB889E7B7472A1EDA8749B1EB259EA02BA35AB97BE666AF22`
- Stock installed slot SHA-256: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`
- Expanded installed slot SHA-256: `264A2D79A5184F2CFBEDCB447DBA260EC48101D19ACD9DA188363D9C659F41E6`
- Stock base+mastery render SHA-256: `E858508C7710CFBC95E6AD9FE9FE52D8F34B14A834BD2FEC23656D23859368B1`
- Expanded base+mastery render SHA-256: `3BB164E4288442856BF1DB52543E99D96B852C4130EDFF0A218630684416CD28`

The feature exposes command 7 only inside its disabled base dependency. Commands 6/8, village-wide Running/Age bytes, direct skill stores, ownership, Remove, and save-format changes are absent. The candidate is fail-closed on missing or mismatched companion files, preserves stock executables, Cure bytes, certified VV3 stock-mode hashes, and the expanded-256 hold. Fresh independent recertification is required before enablement; Expanded-256 remains ON HOLD/fail-closed.
- R3 helper SHA-256 (unchanged): `C7379FB1AFDDD44F06CF48FAEED14C1701D796F5FC2568E10745337DADE13DB1`; previous Tech constructor: `5A374941D4A6E2F0C36B5F1464738112C353AD0BC727FDDF9610E24A9B2EEE88`; Detail constructor: `0D38AAE3CF8F1EEFF81B95AE3AC334E488053FD60D136FC733A24E74A4AB31EC`; command-7 slot: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`; Cure: `2BB7A32344293DCACB4D0359818C6839AC1FBBAEE8F9E3D00DB59C274238D726`.
