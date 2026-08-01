# VV4 Full Mastery disabled baked-asset UI candidate

Generated from clean C6 baseline `577072f5b5205c3a0a857c0645d855bb98ec19d2` plus the repository-owned canonical mockup provenance and native ordinal ABI gate. The base and command-7 records are HARD WITHDRAWN and catalog-hidden after Playtest 3 crashed at RVA 0x89E0C / VA 0x489E0C. Individual-menu calls at 0x4897CA and 0x489ABB targeted the show-menu epilogue at 0x489573 instead of the result helper at 0x489583. This disabled candidate repairs only those guarded calls; individual Full Mastery remains STOP because it writes raw Float32 90 and precharges, and command 7 awaits D25 recertification. The legacy Cure row is rendered unavailable, command 5 is rejected before charge/dispatch, and the unchanged Cure payload remains withdrawn.

- Canonical mockup SHA-256: `B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24`
- Secondary mockup SHA-256: `AD1B6A8A61F13BBBA2C902E04AB8AD205167FC48034F4D0A7C078A76C756FA30`
- Canonical crop RGBA SHA-256: `B8E9C4DB93F05450689528C5A04A532486771E53DDC23FCF63B0155C7949418B`
- Native asset: cached ordinal `0x8C` (`btn_trophies.png`), natural frame 100x39 at local 72,4, half-open bounds [72,4,172,43); no custom runtime PNG, path, grid, crop, or resize.
- Button construction: manager `sub_44CCF0`, ordinal loader `sub_44CB60`, `sub_401C20`; Tech event 13 and Detail event 2; parent `sub_40C190`.
- `Upgrades` is copied through proven native `sub_401600` text overlay and `sub_401630` style ABIs; `sub_40D8A0` is absent. Tech uses `this+0x74` and paired cleanup; Detail uses list-owned `sub_40C300`.
- Wrapper-null returns without attach. Loader-null raw-frees the unconstructed wrapper through cdecl `sub_470B7B`; it never virtual-destructs raw memory. Inner-null after `sub_401C20` uses the proven scalar destructor with flag 1.
- The Tech helper emits exact `8B CB` (`mov ecx, ebx`) after clearing `this+0x74` and before `sub_40C340`; its continuation remains `0x43E23D`.
- Companion SHA-256: `4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7`
- Stock installed slot SHA-256: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`
- Expanded installed slot SHA-256: `264A2D79A5184F2CFBEDCB447DBA260EC48101D19ACD9DA188363D9C659F41E6`
- Stock base+mastery render SHA-256: `B93ACE7E0EE6FF0EEA1477D7178288599E170EC49D4F6EEF500FF4B92B6960B1`
- Expanded base+mastery render SHA-256: `F97498F7D94A2493044FC4D4290DA62EF47242F258AF0E27B2B6AEFDAFF27D10`

The disabled feature would expose command 7 only with its hash-guarded base dependency; neither record is selectable. Commands 6/8, village-wide Running/Age bytes, direct skill stores, ownership, Remove, and save-format changes are absent. The candidate is fail-closed on missing or mismatched companion files, preserves stock executables, Cure bytes, certified VV3 stock-mode hashes, and the expanded-256 hold. Earlier D19/D21 approvals are superseded by the Playtest 3 crash evidence. Expanded-256 remains ON HOLD/fail-closed.
- D19 factory SHA-256: `58E21A9597EB6ABF6949A1E607C3B607FABAF1AE5D280D899A062F5D021ACE21`; helper: `C7379FB1AFDDD44F06CF48FAEED14C1701D796F5FC2568E10745337DADE13DB1`; Tech constructor: `1D710074D6F5717A420646B2DCEE2BCC351754B4DC0CCFB5A32F586E2E258BDC`; Detail constructor: `AC2A88CBD0B7805941EA34261D765F4A727187B35B5443BFB7CDEA8DF43A7E8C`; command-7 slot: `023CF384A52CB6A6A49511B8B069B952718DC70E771FEE15CAC8A0777FB5F6DE`; Cure: `2BB7A32344293DCACB4D0359818C6839AC1FBBAEE8F9E3D00DB59C274238D726`.
