# VVFP handoff — 2026-08-10

This folder is a self-contained handoff for the Virtual Villagers Fun Patcher.

## Install on the other computer

1. Keep the project on a local path such as `C:\Users\<new-user>\Documents\Codex\Misc LDW Game Projects\Virtual-Villagers-Fun-Patcher` (not OneDrive).
2. Extract `source\VVFP-source-31206b3.zip` into that project directory.
3. Copy the contents of `inputs`, `runtime-deps`, and `.tools` into the extracted project root, preserving their names and subfolders. `runtime-deps` is the preferred readable fallback and includes the local Capstone, Keystone, and pefile copies.
4. The complete VV2 stress-test folder is under `playtest-vv2-barrel-babies`. Run its EXE directly from that folder; its DLLs are beside it.
5. Use the manifest below to verify the copy before running any tools.

The source archive is branch `codex/collectibles-native-routes` at commit `31206b3ab3d44197b91b1074858f564c8980c73b` (short ref `31206b3`). It is a tracked-source snapshot only; it does not contain the large generated `outputs` tree, local inputs, local dependency copies, or saves.

## Included

- `source\VVFP-source-31206b3.zip`: tracked source snapshot; SHA-256 `220E2C1E5D18D999715A9455B937262E359202B1960E6D359521FABBFB4A676`.
- `inputs`: four complete stock game folders, 1,922 files / 229,235,460 bytes.
- `runtime-deps`: local runtime/dependency copies, 302 files / 29,619,591 bytes.
- `.tools`: local protected tool/dependency copies used by the test runtime. Preserve all files; some entries may require administrator approval during copying.
- `SOURCE-REPOSITORY-URL.txt`: private Git repository URL, branch, and exact handoff commit.
- `playtest-vv2-barrel-babies`: complete VV2 playtest folder, 316 files / 32,696,662 bytes, 7 DLLs, zero saves. EXE SHA-256 `4CD31A9ADB716D7230F6AEEBA8F673E06EFF798F22407AC60478108528D381E7`.

The full historical `outputs` tree is intentionally omitted (about 39 GB). It is generated/history data, not required for installing the source and current playtest. No personal saves are included.

## Stock input fingerprints

| Game | Folder | Files / DLLs | Inventory SHA-256 | Stock EXE SHA-256 |
|---|---|---:|---|---|
| VV2 | `inputs\vv2-stock-copy` | 312 / 7 | `F25C03B209820E3F62C237821DA47425E0B14489A6EADCEA1CA8ADA2346A7A06` | `46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677` |
| VV3 | `inputs\vv3-stock-copy` | 415 / 7 | `1B348AC2FA05E1D723F92AFBBB2E98507F624F7EDBC39B237D8C2B722955A1E6` | `8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503` |
| VV4 | `inputs\vv4-stock-copy` | 556 / 7 | `DDA63528390D271F356E1A359AD991DB6A759E118F1EAD8F58813FD00103E155` | `6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220` |
| VV5 | `inputs\vv5-stock-copy` | 639 / 7 | `9B9773905E5DA8D7A5B67FB8FD58E70093870429C60853C0023F5FFFEF3BF977` | `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D` |

The source is also available from the private GitHub repository. If using Git, clone `https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher.git`, check out `codex/collectibles-native-routes` at the commit above, then copy the three untracked/local directories from this handoff.

This handoff preserves the current fail-closed project state. Static/source and playtest materials are included; do not interpret them as authenticated native/runtime/publication certification.
