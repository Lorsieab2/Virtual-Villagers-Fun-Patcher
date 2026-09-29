"""Everyone Collects Like A New Home (VV2-VV5, off by default).

The owner: "In Virtual Villagers A New Home you can drop as many children as
you like on a mushroom and they will all pick it up, as long as it's still
visible on the screen. I would like to implement that behavior in the other
games."  Live in A New Home: eight children dropped (while paused) on the one
mushroom on the map each went to "Picking a mushroom" and each brought one
back -- eight mushrooms.

What stops the others, read from the executables:

* The Secret City, The Tree of Life, New Believers: the drop hit-test
  (collectible manager vf2) accepts only a slot whose reserver field (+0x18)
  is -1, so a second villager dropped on a claimed item is refused.  The row
  NOPs that one `jne`.  A later villager is still awarded: the pickup (vf0)
  returns 1 even when the first pickup already removed the item, and the
  award (vf1) depends only on the carried id.
* The Lost Children: the pickup callbacks (0x3E mushroom, 0x3F collectible)
  cancel another child still collecting.  The row jumps over each cancel loop
  to the callback's own ending.

Pinned here: the stock bytes and the patched bytes in a real render; the VV2
jumps land on each callback's own epilogue; and the VV3-VV5 hit-test, RUN in
an emulator on the stock and on the rendered bytes, refuses a slot another
villager has claimed in stock and accepts it with the row.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import capstone
import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
EXE = {"vv2": "Virtual Villagers - The Lost Children.exe", "vv3": "Virtual Villagers - The Secret City.exe",
       "vv4": "Virtual Villagers - The Tree of Life.exe", "vv5": "Virtual Villagers - New Believers.exe"}
CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

# game: (hit-test entry, the reservation jne, its stock bytes, the accept block, slots)
HIT = {
    "vv3": (0x42DDB0, 0x42DDCF, "7522", 0x42DE07, 2),
    "vv4": (0x413A20, 0x413A3F, "751E", 0x413A75, 2),
    "vv5": (0x413E40, 0x413E5F, "751E", 0x413E95, 0x3E),
}


def _render(game: str, with_row: bool = True) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == game)
    rows = [f"{game}_everyone_collects_like_vv1"] if with_row else []
    rendered, applied = vfp.render_patched_bytes(STOCK / EXE[game], build, "immediate_fixed", rows)
    owners = {r["owner"] for r in applied}
    assert (f"feature:{game}_everyone_collects_like_vv1" in owners) == with_row, owners
    return bytes(rendered)


def _off(game: str, va: int) -> int:
    pe = pefile.PE(str(STOCK / EXE[game]), fast_load=True)
    return pe.get_offset_from_rva(va - 0x400000)


def _hit_test(game: str, image: bytes, reserver: int) -> str:
    """Run the hit-test over a one-slot manager (x=100, y=200, id 0x70) with
    the drop at the item.  'accepted' when it reaches the accept block."""
    entry, _, _, accept, slots = HIT[game]
    pe = pefile.PE(data=image, fast_load=True)
    text = pe.sections[0]
    base = 0x400000 + text.VirtualAddress
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    size = (text.Misc_VirtualSize + 0xFFF) & ~0xFFF
    mu.mem_map(base, size)
    mu.mem_write(base, image[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData][:size])
    mgr, rec, stack, ret = 0x20000000, 0x21000000, 0x70000000, 0x60000000
    for a in (mgr, rec, ret):
        mu.mem_map(a, 0x10000)
    mu.mem_map(stack - 0x10000, 0x20000)
    manager = bytearray(4 + 0x1C * slots)
    # slot 0: active, id 0x70, x 100, y 200, reserved by another villager (or free)
    manager[4] = 1
    struct.pack_into("<iiiiii", manager, 8, 0x70, 0, 100, 200, reserver, 0)
    mu.mem_write(mgr, bytes(manager))
    mu.mem_write(ret, b"\xF4")
    esp = stack - 0x100
    mu.mem_write(esp, struct.pack("<4I", ret, rec, 100, 200))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, mgr)
    state = {"result": None}

    def hook(mu, address, size, user_data):
        if address == accept:
            state["result"] = "accepted"
            mu.emu_stop()
        elif address == ret:
            state["result"] = "refused" if mu.reg_read(UC_X86_REG_EAX) == 0xFFFFFFFF else "other"
            mu.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(entry, 0, count=10000)
    return state["result"]


class EveryoneCollectsTests(unittest.TestCase):
    def test_vv3_to_vv5_a_claimed_item_is_refused_in_stock_and_accepted_with_the_row(self):
        for game, (entry, site, stock, accept, slots) in HIT.items():
            stock_image = (STOCK / EXE[game]).read_bytes()
            patched = _render(game)
            o = _off(game, site)
            with self.subTest(game=game):
                self.assertEqual(stock_image[o:o + 2], bytes.fromhex(stock))
                self.assertEqual(patched[o:o + 2], b"\x90\x90")
                self.assertEqual(_hit_test(game, stock_image, reserver=-1), "accepted", "free slot: stock accepts")
                self.assertEqual(_hit_test(game, stock_image, reserver=5), "refused", "claimed: stock refuses")
                self.assertEqual(_hit_test(game, patched, reserver=5), "accepted", "claimed: the row accepts")
                self.assertEqual(_hit_test(game, patched, reserver=-1), "accepted")

    def test_the_row_changes_only_its_own_bytes(self):
        # Against a render WITHOUT the row, so the patcher's automatic safety
        # patches cancel out; only the row's bytes and the PE checksum differ.
        for game in EXE:
            with self.subTest(game=game):
                a, b = _render(game, with_row=False), _render(game)
                self.assertEqual(len(a), len(b))
                checksum = struct.unpack_from("<I", a, 0x3C)[0] + 0x58   # PE OptionalHeader.CheckSum
                diff = {i for i in range(len(a)) if a[i] != b[i]} - set(range(checksum, checksum + 4))
                allowed = set()
                if game == "vv2":
                    for va, n in ((0x461D5F, 2), (0x461E01, 8)):
                        o = _off(game, va)
                        allowed |= set(range(o, o + n))
                else:
                    o = _off(game, HIT[game][1])
                    allowed = {o, o + 1}
                self.assertTrue(diff <= allowed, [hex(x) for x in sorted(diff - allowed)])
                self.assertTrue(diff, "the row changed nothing")

    def test_vv2_each_pickup_callback_skips_its_cancel_loop_to_its_own_ending(self):
        stock = (STOCK / EXE["vv2"]).read_bytes()
        patched = _render("vv2")
        for site, before, after, tail in ((0x461D5F, "33DB", "EB70", 0x461DD1),
                                          (0x461E01, "33DB8DAEFC040000", "E9D3000000909090", 0x461ED9)):
            with self.subTest(site=hex(site)):
                o = _off("vv2", site)
                n = len(bytes.fromhex(before))
                self.assertEqual(stock[o:o + n], bytes.fromhex(before))
                self.assertEqual(patched[o:o + n], bytes.fromhex(after))
                (jump,) = list(CS.disasm(patched[o:o + 5], site))[:1]
                self.assertIn(jump.mnemonic, ("jmp",))
                self.assertEqual(int(jump.op_str, 16), tail)
                # the target is the callback's own epilogue: refresh, pop x5, ret 8
                t = _off("vv2", tail)
                self.assertEqual(stock[t:t + 6], bytes.fromhex("8B8EE874E500"))
                self.assertEqual(stock[t + 11:t + 19], bytes.fromhex("5F5D5E5B59C20800"))
                # the skipped loop's match branch leads to the cancel: the
                # job-clear 0x4492A0 on the other child, then this same ending
                loop = list(CS.disasm(stock[o:t], site))
                exits = {int(i.op_str, 16) for i in loop
                         if i.mnemonic in ("je", "jz") and i.op_str.startswith("0x")
                         and not site <= int(i.op_str, 16) < tail}
                cancels = []
                for target in exits:
                    c = _off("vv2", target)
                    calls = [int(i.op_str, 16) for i in CS.disasm(stock[c:c + 16], target)
                             if i.mnemonic == "call"]
                    if calls[:1] == [0x4492A0]:
                        cancels.append(target)
                self.assertTrue(cancels, "no branch out of the loop leads to the job-clear 0x4492A0")

    def test_the_rows_are_off_by_default_and_documented(self):
        from vv_fun_patcher_gui import default_fun_patch_selection
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for game in EXE:
            pid = f"{game}_everyone_collects_like_vv1"
            with self.subTest(game=game):
                self.assertFalse(default_fun_patch_selection(pid))
                self.assertIn(f"`{pid}`", readme)


if __name__ == "__main__":
    unittest.main()
