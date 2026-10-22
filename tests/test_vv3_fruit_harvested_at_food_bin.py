"""VV3 Fruit Counts When It Reaches the Food Bin: executed, not just rendered.

In the stock game a fruit picker's food is added, and the tree's fruit taken
off, inside the fruit trees' take-item listener 0x434A80 -- the moment the
pick step (the trees' drop handler 0x4348F0, step 0x1B of action 0x7D) hands
the villager the fruit item (0x26 + the tree's kind).  The villager then walks
to the food bin and lets go of the item (step 0x10), which only reaches the
trees' release-item listener 0x434C30.  Honey works the other way round: its
release listener 0x431A40 adds the food and takes the honey off the hive when
the item is let go in the food bin (region 0xE).

The patch moves fruit to the honey order.  These tests run the real game code
of a rendered executable in every patch mode -- the pick handler, the item
registry (0x455F30 -> 0x42CDF0 / 0x42CE50), both listeners and the stock award
-- stubbing only the helpers that need a running game: the villager's position
(0x455EF0), the map's region lookup (0x4205B0), the game object (0x428B60, for
the catch-up flag) and the chief's supervision roll (0x45FC60).  The food
store 0x582490 and its Food Gathered counter 0x5824AC are written by the real
food writer 0x4263F0.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK_VV3 = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_fruit_harvested_at_food_bin"
MODES = ("stock", "collection_progression", "immediate_fixed")

TREES = 0x5947E0             # the fruit trees object (game object 9)
TREES_LISTENER = TREES + 4   # its item-listener interface
PICK = 0x4348F0              # the trees' drop handler: step 0x1B(9) of the fruit job
SET_ITEM = 0x455F30          # villager: take (item) or let go (-1) of the carried item
REGISTRY = 0x58EDB8          # item -> listeners, 16 bytes per item
FOOD, FOOD_GATHERED = 0x582490, 0x5824AC
SPEED = 0x5825D4 + 0x20      # the game speed the yield divides by (6 = Normal)

POSITION = 0x455EF0          # thiscall (out), ret 4
REGION = 0x4205B0            # thiscall (x, y), ret 8
GAME = 0x428B60              # returns the game object
CHIEF_ROLL = 0x45FC60        # thiscall (site), ret 4

FRUIT_JOB, OTHER_JOB = 0x7D, 0x06
FOOD_BIN, ELSEWHERE = 0xE, 0x3
TREE_X = (0x500, 0x600, 0x700)  # x positions inside trees 0, 1 and 2

STACK, HEAP, GAME_OBJECT = 0x30000000, 0x31000000, 0x32000000
RECORD_SIZE = 0x1F8C
RETURN = 0x33000000          # sentinel return address


def _supply(tree: int) -> int:
    return TREES + 0x30 + tree * 0x18


class Village:
    """One village: a rendered executable loaded into an emulator."""

    def __init__(self, image: bytes, *, supply=(100, 100, 100), speed=6, catch_up=False, chief=False):
        pe = pefile.PE(data=image, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(base, size)
        uc.mem_write(base, pe.header)
        for section in pe.sections:
            data = section.get_data()
            room = size - section.VirtualAddress
            uc.mem_write(base + section.VirtualAddress, data[: max(0, min(len(data), room))])
        for area in (STACK, HEAP, GAME_OBJECT, RETURN):
            uc.mem_map(area, 0x100000)
        self.uc = uc
        self.region = ELSEWHERE
        self.chief = chief
        self.chief_rolls = 0
        # The trees object as its constructor (0x434E30) and planting leave it:
        # its two vtables, three planted trees of kinds 0, 1 and 2.
        self.write32(TREES, 0x49D1D0)
        self.write32(TREES_LISTENER, 0x49D1C4)
        self.write32(TREES + 0x64, 3)
        for tree in range(3):
            self.write32(TREES + 0x2C + tree * 0x18, tree)
            self.write32(_supply(tree), supply[tree])
        # The trees' interface listens for the three fruit items.
        for item in (0x26, 0x27, 0x28):
            self.write32(REGISTRY + item * 16, TREES_LISTENER)
            self.write32(REGISTRY + item * 16 + 0xC, 1)
        self.write32(FOOD, 0)
        self.write32(FOOD_GATHERED, 0)
        self.write32(SPEED, speed)
        uc.mem_write(GAME_OBJECT + 0x12FB4, bytes([1 if catch_up else 0]))
        uc.hook_add(UC_HOOK_CODE, self._stubs)

    def write32(self, address: int, value: int) -> None:
        self.uc.mem_write(address, struct.pack("<i", value))

    def read32(self, address: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(address, 4))[0]

    def villager(self, index: int, *, job=FRUIT_JOB, x=TREE_X[0]) -> int:
        record = HEAP + index * RECORD_SIZE
        self.uc.mem_write(record, bytes(RECORD_SIZE))
        self.write32(record + 0xF20, -1)       # carrying nothing
        self.write32(record + 0xF24, job)
        self.write32(record + 0xEE0, x)
        self.write32(record + 0xEE4, 0x300)
        return record

    def _ret(self, value: int, pop: int) -> None:
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", self.uc.mem_read(sp, 4))[0]
        self.uc.reg_write(UC_X86_REG_EAX, value)
        self.uc.reg_write(UC_X86_REG_ESP, sp + 4 + pop)
        self.uc.reg_write(UC_X86_REG_EIP, back)

    def _stubs(self, uc, address, _size, _data):
        if address == POSITION:
            record = uc.reg_read(UC_X86_REG_ECX)
            out = struct.unpack("<I", uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 4))[0]
            uc.mem_write(out, bytes(uc.mem_read(record + 0xEE0, 8)))
            self._ret(out, 4)
        elif address == REGION:
            self._ret(self.region, 8)
        elif address == GAME:
            self._ret(GAME_OBJECT, 0)
        elif address == CHIEF_ROLL:
            self.chief_rolls += 1
            self._ret(1 if self.chief else 0, 4)

    def call(self, function: int, this: int, *args: int) -> None:
        sp = STACK + 0x80000
        for value in reversed(args):
            sp -= 4
            self.uc.mem_write(sp, struct.pack("<i", value))
        sp -= 4
        self.uc.mem_write(sp, struct.pack("<I", RETURN))
        self.uc.reg_write(UC_X86_REG_ESP, sp)
        self.uc.reg_write(UC_X86_REG_ECX, this)
        self.uc.emu_start(function, RETURN, count=100000)
        assert self.uc.reg_read(UC_X86_REG_EIP) == RETURN
        assert self.uc.reg_read(UC_X86_REG_ESP) == STACK + 0x80000, "callee cleaned its arguments"

    # The fruit job's steps, as the game runs them.
    def pick(self, record: int) -> None:
        self.call(PICK, TREES, record, -1)

    def let_go(self, record: int, region: int) -> None:
        self.region = region
        self.call(SET_ITEM, record, -1)

    def carried(self, record: int) -> int:
        return self.read32(record + 0xF20)

    def supplies(self) -> tuple[int, int, int]:
        return tuple(self.read32(_supply(tree)) for tree in range(3))

    def food(self) -> tuple[int, int]:
        return self.read32(FOOD), self.read32(FOOD_GATHERED)


@unittest.skipUnless(STOCK_VV3.is_file(), "stock VV3 executable not present")
class FruitHarvestedAtFoodBinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock = STOCK_VV3.read_bytes()
        build = next(b for b in vfp.load_builds() if b.id == "vv3")
        cls.rendered = {}
        for mode in MODES:
            image, _ = vfp.render_patched_bytes(STOCK_VV3, build, mode, [FEATURE])
            cls.rendered[mode] = bytes(image)
        # 256 Villagers moves the chief's supervision roll's manager (0x434AF3),
        # inside the stock award this patch reuses: the two must compose.
        image, _ = vfp.render_patched_bytes(
            STOCK_VV3, build, "immediate_fixed", [FEATURE, "vv3_population_256"]
        )
        cls.rendered["immediate_fixed + 256 Villagers"] = bytes(image)
        cls.without = {}
        for mode in MODES:
            image, _ = vfp.render_patched_bytes(STOCK_VV3, build, mode, [])
            cls.without[mode] = bytes(image)
        # One load at Normal speed, as the stock pick pays it in this emulator.
        probe = Village(cls.stock)
        probe.pick(probe.villager(0))
        cls.load = probe.food()[0]

    def each(self):
        for name, image in self.rendered.items():
            with self.subTest(build=name):
                yield image

    def test_the_stock_game_pays_at_the_pick(self):
        # Guards the harness: the stock pick adds the food and takes the fruit.
        village = Village(self.stock)
        picker = village.villager(0, x=TREE_X[1])
        village.pick(picker)
        self.assertEqual(village.carried(picker), 0x27)
        self.assertEqual(village.read32(picker + 0xEA0), 0x17 + 1)
        self.assertGreater(self.load, 0)
        self.assertEqual(village.food(), (self.load, self.load))
        self.assertEqual(village.supplies(), (100, 100 - self.load, 100))
        village.let_go(picker, FOOD_BIN)
        self.assertEqual(village.food(), (self.load, self.load))
        self.assertEqual(village.supplies(), (100, 100 - self.load, 100))

    def test_picking_takes_nothing_and_the_food_bin_takes_it_once(self):
        for image in self.each():
            village = Village(image)
            picker = village.villager(0, x=TREE_X[2])
            village.pick(picker)
            self.assertEqual(village.carried(picker), 0x28, "the picker carries the fruit")
            self.assertEqual(village.read32(picker + 0xEA0), 0x17 + 2)
            self.assertEqual(village.food(), (0, 0))
            self.assertEqual(village.supplies(), (100, 100, 100))
            village.let_go(picker, FOOD_BIN)
            self.assertEqual(village.carried(picker), -1)
            self.assertEqual(village.food(), (self.load, self.load))
            self.assertEqual(village.supplies(), (100, 100, 100 - self.load))
            # Letting go again (the next job clears the queue) changes nothing.
            village.let_go(picker, FOOD_BIN)
            self.assertEqual(village.food(), (self.load, self.load))
            self.assertEqual(village.supplies(), (100, 100, 100 - self.load))

    def test_the_delivery_pays_what_the_stock_pick_paid(self):
        # Speed, catch-up and the chief's bonus are the stock award's own.
        cases = [
            dict(speed=6), dict(speed=3), dict(speed=12), dict(speed=6, chief=True),
            dict(speed=12, catch_up=True), dict(speed=3, catch_up=True, chief=True),
        ]
        for case in cases:
            stock = Village(self.stock, **case)
            stock_picker = stock.villager(0)
            stock.pick(stock_picker)
            for image in self.each():
                with self.subTest(**case):
                    village = Village(image, **case)
                    picker = village.villager(0)
                    village.pick(picker)
                    self.assertEqual(village.chief_rolls, 0, "no roll at the pick")
                    village.let_go(picker, FOOD_BIN)
                    self.assertEqual(village.food(), stock.food())
                    self.assertEqual(village.supplies(), stock.supplies())
                    self.assertEqual(village.chief_rolls, stock.chief_rolls)

    def test_letting_go_anywhere_else_takes_nothing(self):
        for image in self.each():
            village = Village(image)
            picker = village.villager(0)
            village.pick(picker)
            village.let_go(picker, ELSEWHERE)
            self.assertEqual(village.carried(picker), -1)
            self.assertEqual(village.food(), (0, 0))
            self.assertEqual(village.supplies(), (100, 100, 100))

    def test_an_interrupted_trip_takes_nothing_even_at_the_bin(self):
        # A new job is written (0x455570) before its handler clears the queue
        # and lets go of the fruit (0x460F70), so the release sees the new job.
        for image in self.each():
            village = Village(image)
            picker = village.villager(0)
            village.pick(picker)
            village.write32(picker + 0xF24, OTHER_JOB)
            village.let_go(picker, FOOD_BIN)
            self.assertEqual(village.food(), (0, 0))
            self.assertEqual(village.supplies(), (100, 100, 100))

    def test_a_site_that_is_not_a_tree_changes_nothing(self):
        for image in self.each():
            for site in (0, 0x15, 0x16, 0x1A, -1):
                with self.subTest(site=site):
                    village = Village(image)
                    picker = village.villager(0)
                    village.pick(picker)
                    village.write32(picker + 0xEA0, site)
                    village.let_go(picker, FOOD_BIN)
                    self.assertEqual(village.food(), (0, 0))
                    self.assertEqual(village.supplies(), (100, 100, 100))

    def test_several_carriers_never_take_the_tree_below_zero(self):
        for image in self.each():
            start = 2 * self.load + 1
            village = Village(image, supply=(start, 100, 100))
            pickers = [village.villager(i) for i in range(3)]
            for picker in pickers:
                village.pick(picker)
            self.assertEqual([village.carried(p) for p in pickers], [0x26] * 3)
            self.assertEqual(village.supplies(), (start, 100, 100))
            for picker, left in zip(pickers, (self.load + 1, 1, 0)):
                village.let_go(picker, FOOD_BIN)
                self.assertEqual(village.supplies()[0], left)
            # Every delivery still adds its food, as honey's does.
            self.assertEqual(village.food(), (3 * self.load, 3 * self.load))

    def test_a_tree_below_five_is_not_picked(self):
        # The stock pick test (supply >= 5) is unchanged: no fruit, no item.
        for image in self.each():
            village = Village(image, supply=(4, 100, 100))
            picker = village.villager(0)
            village.pick(picker)
            self.assertEqual(village.carried(picker), -1)
            self.assertEqual(village.supplies(), (4, 100, 100))

    def test_a_load_carried_over_a_save_is_delivered_once(self):
        # Saving keeps the record (+0xF20 item, +0xF24 job, +0xEA0 site) and the
        # trees; a new session delivering the load pays it exactly once.
        for image in self.each():
            before = Village(image)
            picker = before.villager(0, x=TREE_X[1])
            before.pick(picker)
            record = bytes(before.uc.mem_read(picker, RECORD_SIZE))
            trees = bytes(before.uc.mem_read(TREES, 0x70))
            after = Village(image)
            after.uc.mem_write(picker, record)
            after.uc.mem_write(TREES, trees)
            self.assertEqual(after.food(), (0, 0))
            after.let_go(picker, FOOD_BIN)
            self.assertEqual(after.food(), (self.load, self.load))
            self.assertEqual(after.supplies(), (100, 100 - self.load, 100))

    def test_other_items_and_jobs_at_the_bin_are_stock(self):
        # A villager on another job who lets go of a tree's item in the bin, or
        # anywhere else, gets the stock release: nothing, or the no-trees flag.
        for image in self.each():
            for region in (FOOD_BIN, ELSEWHERE):
                for trees in (3, 0):
                    with self.subTest(region=region, trees=trees):
                        patched = Village(image)
                        stock = Village(self.stock)
                        for village in (patched, stock):
                            village.write32(TREES + 0x64, trees)
                            village.uc.mem_write(TREES_LISTENER + 9, b"\x00")
                            planter = village.villager(0, job=OTHER_JOB)
                            village.write32(planter + 0xF20, 0x27)
                            village.let_go(planter, region)
                        self.assertEqual(patched.food(), stock.food())
                        self.assertEqual(patched.supplies(), stock.supplies())
                        self.assertEqual(
                            patched.uc.mem_read(TREES_LISTENER + 9, 1),
                            stock.uc.mem_read(TREES_LISTENER + 9, 1),
                        )

    def test_without_the_patch_the_bytes_are_stock(self):
        for mode, image in self.without.items():
            with self.subTest(mode=mode):
                self.assertEqual(image[0x34A80:0x34C80], self.stock[0x34A80:0x34C80])


if __name__ == "__main__":
    unittest.main()
