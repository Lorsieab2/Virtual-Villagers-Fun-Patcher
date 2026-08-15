"""Build the optional village-wide Origins upgrade payloads.

The base Origins payload owns the menu and purchase plumbing.  These payloads
are deliberately independent: each writes only a certified zero-filled
extension cave containing a signature, a tiny ABI header, and the three
save-scoped record walkers.  The base payload's dormant extension ABI can call
the entry point when this feature is selected; the optional manifest never
rewrites the base Origins cave.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
COMPANION = ROOT / "assets" / "origins" / "VVFP Origins Icons.dll"

# These are the certified optional extension locations from the implementation
# plan.  Cure is kept at the beginning of the reserve; the optional payload is
# intentionally placed after it so the two manifests are composable.
CONFIG = {
    "vv1": {
        "title": "Virtual Villagers - A New Home",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - A New Home.exe",
        "sha256": "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D",
        "cave_offset": 0x8B004,
        "cave_va": 0x48D004,
        "payload_offset": 0x8B180,
        "stride": 0x3D8,
        "first": "ecx",
        "active": 0x28,
        "health": 0x344,
        "age": 0x348,
        "skills": (0x3BC, 0x3C0, 0x3C4, 0x3C8, 0x3CC),
        "native_skill_writer": 0x437230,
        "skill_codes": (2, 4, 1, 5, 3),
        "age_code_offset": 0x300,
        "likes": 0x398,
        "dislikes": 0x3A8,
        "slot_count": 4,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 100,
        "report_running_granted": True,
        "report_mastery_counts": True,
        "report_age_granted": True,
    },
    "vv2": {
        "title": "Virtual Villagers - The Lost Children",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - The Lost Children.exe",
        "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
        "cave_offset": 0x9A004,
        "cave_va": 0x49C004,
        # The VV2 base Origins UI uses 0x9A180-0x9A7CB for its preflight and
        # event helpers. Keep this optional village-wide payload after that
        # occupied range inside the same executable .shr reserve.
        "payload_offset": 0x9A800,
        "stride": 0xE48C,
        "first": "ecx",
        "active": 0x30,
        "health": 0x52C,
        "age": 0x530,
        "skills": (0x7E4, 0x7E8, 0x7EC, 0x7F0, 0x7F4),
        "native_skill_writer": 0x445430,
        "skill_codes": (2, 5, 1, 3, 4),
        "native_mastery_manager": 0x44F4E0,
        "totem": 0x558,
        "code_size": 0x500,
        "age_code_offset": 0x360,
        "likes": 0x5F0,
        "dislikes": 0x6E8,
        "slot_count": 62,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 100,
    },
    "vv3": {
        "title": "Virtual Villagers - The Secret City",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - The Secret City.exe",
        "sha256": "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
        "cave_offset": 0x7B664,
        "cave_va": 0x47B664,
        "payload_offset": 0x7B820,
        "stride": 0x1F8C,
        "first": "ecx",
        "active": 0xF10,
        "health": 0xE78,
        "age": 0xDC4,
        "skills": (0xEAC, 0xEB0, 0xEB4, 0xEB8, 0xEBC),
        "code_size": 0x500,
        "age_code_offset": 0x330,
        # VV3's native mastery writer takes the skill ordinal (0..4), not
        # the VV2-style physical-record index.  The native award evaluator is
        # record-scoped and must run once after each changed villager has
        # been post-verified at exactly 100.
        "native_skill_writer": 0x455740,
        "skill_codes": (0, 1, 2, 3, 4),
        "native_mastery_evaluator": 0x462500,
        "native_evaluator_per_record": True,
        "native_skill_writer_uses_physical_index": False,
        "likes": 0xFB4,
        "dislikes": 0xFC0,
        "slot_count": 3,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 100,
    },
    "vv4": {
        "title": "Virtual Villagers - The Tree of Life",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - The Tree of Life.exe",
        "sha256": "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        "cave_offset": 0xCC004,
        "cave_va": 0x728004,
        "payload_offset": 0xCC220,
        "stride": 0x2E3C,
        "first": "ecx",
        "active": 0x1CC4,
        "dead": 0x1CC7,
        "health": 0x1C40,
        "age": 0x1B8C,
        "skills": (0x1C5C, 0x1C60, 0x1C64, 0x1C68, 0x1C6C),
        # VV4 stores skills as Float32 values.  sub_46AD80 is the native
        # writer: push (100.0 - current), push skill ordinal, ECX = the
        # record's first-skill field; the callee returns with ret 8.
        "native_skill_writer": 0x46AD80,
        "native_skill_writer_uses_physical_index": False,
        "native_skill_writer_float": True,
        "skill_codes": (0, 1, 2, 3, 4),
        "code_size": 0x500,
        "age_code_offset": 0x450,
        "likes": 0x1E60,
        "dislikes": 0x1E6C,
        "slot_count": 3,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": False,
        "master_value": 0x42C80000,
    },
    "vv5": {
        "title": "Virtual Villagers - New Believers",
        "running_preference_id": 38,
        "exe": "Virtual Villagers - New Believers.exe",
        "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
        "cave_offset": 0x94339,
        "cave_va": 0x494339,
        "payload_offset": 0x94C20,
        "code_size": 0x260,
        "mastery_code_offset": 0x150,
        "age_code_offset": 0x1F0,
        "stride": 0x2F44,
        "first": "ecx",
        "active": 0x1CD4,
        "heathen_active_guard": 0x1CE1,
        "faction": 0x1CEC,
        "health": 0x1C40,
        "age": 0x1B8C,
        "skills": (7260, 7264, 7268, 7272, 7276, 7280),
        "likes": 8028,
        "dislikes": 8040,
        "slot_count": 3,
        "running_preference_id": 38,
        "bound": "edx",
        "heathen": True,
        "master_value": 0x42C80000,
        "native_running": 0x464F90,
        "native_running_insert": 0x464AD0,
        "native_running_remove": 0x4649E0,
        "native_mastery": 0x475730,
    },
}


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def _hex_word(value: int) -> str:
    return f"0x{value:X}"


def _first_expression(config: dict) -> str:
    return config["first"]


def _record_setup(config: dict) -> str:
    return "mov esi, ecx"


def _eligibility(config: dict, label: str) -> str:
    active = config["active"]
    health = config["health"]
    result = [
        f"cmp byte ptr [esi + {_hex_word(active)}], 0",
        f"je {label}",
    ]
    if config.get("dead") is not None:
        result.extend(
            [
                f"cmp byte ptr [esi + {_hex_word(config['dead'])}], 0",
                f"jne {label}",
            ]
        )
    if config.get("totem") is not None:
        result.extend(
            [
                f"cmp byte ptr [esi + {_hex_word(config['totem'])}], 0",
                f"jne {label}",
            ]
        )
    if config["heathen"]:
        result.extend(
            [
                f"cmp byte ptr [esi + {_hex_word(config['heathen_active_guard'])}], 0",
                f"jne {label}",
                f"cmp dword ptr [esi + {_hex_word(health)}], 0",
                f"jle {label}",
                f"cmp byte ptr [esi + {_hex_word(config['faction'])}], 0",
                f"jne {label}",
            ]
        )
    else:
        result.extend(
            [
                f"cmp dword ptr [esi + {_hex_word(health)}], 0",
                f"jle {label}",
            ]
        )
    return "\n".join(result)


def build_payload(config: dict) -> tuple[bytes, dict[str, int]]:
    cave_va = config["cave_va"]
    payload_va = config["cave_va"] + (config["payload_offset"] - config["cave_offset"])
    # The first 0x20 bytes are the fixed VVFPOWU header.  Assemble the code
    # relative to the byte immediately after that header; the previous
    # generator assembled against payload_va and then prepended the header,
    # shifting every entry and native call target by +0x20 at runtime.
    code_va = payload_va + 0x20
    # Entry is deliberately at a stable offset from the signature.  The base
    # Origins payload can check the signature and call this entry without
    # knowing the optional implementation's internal layout.
    entry_va = code_va
    running_va = code_va + 0x50
    mastery_va = code_va + config.get("mastery_code_offset", 0x190) - 0x20
    age_va = code_va + config.get("age_code_offset", 0x250) - 0x20
    code = bytearray(b"\0" * config.get("code_size", 0x390))

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - code_va
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(f"optional payload exceeds reserve at {va:#x}")
        if any(code[start:end]):
            raise RuntimeError(f"optional payload overlap at {va:#x}")
        code[start:end] = payload

    put(
        entry_va,
        f"""
            cmp eax, 6
            je 0x{running_va:X}
            cmp eax, 7
            je 0x{mastery_va:X}
            cmp eax, 8
            je 0x{age_va:X}
            xor edx, edx
            xor ecx, ecx
            mov eax, -1
            ret
        """,
    )

    if config.get("native_running"):
        slot_count = config["slot_count"]
        running_source = f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebx, edx
            {_record_setup(config)}
            xor edi, edi
            xor ebp, ebp
            push 0
        running_loop:
            test ebx, ebx
            jz running_done
            {_eligibility(config, 'running_next')}
            push {_hex_word(config['running_preference_id'])}
            lea ecx, [esi + {_hex_word(config['likes'])}]
            call {_hex_word(config['native_running'])}
            test al, al
            jnz running_existing
            mov edx, -1
            xor eax, eax
        running_scan:
            cmp dword ptr [esi+eax*4+{_hex_word(config['likes'])}], -1
            jne running_like_next
            cmp edx, -1
            jne running_like_next
            mov edx, eax
        running_like_next:
            inc eax
            cmp eax, {slot_count}
            jb running_scan
            cmp edx, -1
            jne running_insert
            inc edi
            jmp running_next
            running_existing:
                inc ebp
                jmp running_next
        running_insert:
            push {_hex_word(config['running_preference_id'])}
            lea ecx, [esi + {_hex_word(config['likes'])}]
            call {_hex_word(config['native_running_insert'])}
        running_remove_dislikes:
            xor eax, eax
        running_dislike_check:
            cmp dword ptr [esi+eax*4+{_hex_word(config['dislikes'])}], {_hex_word(config['running_preference_id'])}
            jne running_dislike_next
            push {_hex_word(config['running_preference_id'])}
            lea ecx, [esi + {_hex_word(config['dislikes'])}]
            call {_hex_word(config['native_running_remove'])}
            inc dword ptr [esp]
        running_dislike_next:
            inc eax
            cmp eax, {slot_count}
            jb running_dislike_check
        running_next:
            add esi, {_hex_word(config['stride'])}
            dec ebx
            jmp running_loop
        running_done:
            mov ecx, dword ptr [esp]
            add esp, 4
            mov eax, edi
            mov edx, ebp
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """
    else:
        slot_count = config["slot_count"]
        # report_running_granted is opt-in (VV1 only as of this writing) so
        # this shared branch stays byte-identical for every other game that
        # also reaches it (VV2-VV4 all lack native_running too). The granted
        # count itself has nowhere to go through the existing 3-register
        # return (eax/ecx/edx are already full, and every callee-saved
        # register -- ebx/esi/edi/ebp -- already carries something the
        # caller needs back), so it's written to a fixed scratch dword in
        # the confirmed-unused gap between entry_va's dispatch and
        # running_va instead, and the caller reads it back from there
        # after the call rather than trying to carry it through a register
        # across the LoadLibrary/GetProcAddress calls in between (which
        # aren't guaranteed to preserve ecx/edx).
        report_granted = bool(config.get("report_running_granted"))
        granted_push = "push 0" if report_granted else ""
        granted_increment = "inc dword ptr [esp]" if report_granted else ""
        if report_granted:
            granted_store = (
                f"pop eax\n            mov dword ptr [0x{entry_va + 0x30:X}], eax"
            )
        else:
            granted_store = ""
        running_source = f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebx, edx
            {_record_setup(config)}
            xor edi, edi
            xor ebp, ebp
            xor eax, eax
            {granted_push}
        running_loop:
            test ebx, ebx
            jz running_done
            {_eligibility(config, 'running_next')}
            xor edx, edx
            mov ecx, {slot_count}
        running_scan:
            cmp dword ptr [esi+edx*4+{_hex_word(config['likes'])}], {_hex_word(config['running_preference_id'])}
            je running_existing
            cmp dword ptr [esi+edx*4+{_hex_word(config['likes'])}], -1
            jne running_like_next
            cmp ecx, {slot_count}
            jne running_like_next
            mov ecx, edx
        running_like_next:
            inc edx
            cmp edx, {slot_count}
            jb running_scan
            cmp ecx, {slot_count}
            je running_full_like
            mov dword ptr [esi+ecx*4+{_hex_word(config['likes'])}], {_hex_word(config['running_preference_id'])}
            {granted_increment}
            jmp running_remove_dislikes
        running_full_like:
            inc edi
            jmp running_next
        running_existing:
            inc ebp
            jmp running_next
        running_remove_dislikes:
            xor edx, edx
            mov ecx, {slot_count}
        running_dislike_scan:
            cmp dword ptr [esi+edx*4+{_hex_word(config['dislikes'])}], {_hex_word(config['running_preference_id'])}
            jne running_dislike_next
            mov dword ptr [esi+edx*4+{_hex_word(config['dislikes'])}], -1
            inc eax
        running_dislike_next:
            inc edx
            dec ecx
            jne running_dislike_scan
        running_next:
            add esi, {_hex_word(config['stride'])}
            dec ebx
            jmp running_loop
        running_done:
            mov ecx, eax
            {granted_store}
            mov eax, edi
            mov edx, ebp
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """
    put(running_va, running_source)

    # report_mastery_counts is opt-in (VV1 only as of this writing). VV4
    # reaches the exact same native_skill_writer/no-manager/no-per-record
    # branch below with this flag unset, so it stays byte-identical.
    # Like report_running_granted, there is no free register left at
    # mastery_done/mastery_failure to carry two new counts back through
    # (eax/ecx/edx are already zeroed there for every existing caller, and
    # every callee-saved register is committed elsewhere), and unlike
    # Running there is also an early-exit path (mastery_failure) that
    # cannot be trusted to unwind extra stack pushes cleanly -- so these
    # go straight to fixed scratch dwords instead of the stack, and the
    # caller reads them back directly rather than through a register.
    report_mastery = bool(config.get("report_mastery_counts"))
    mastery_granted_va = entry_va + 0x38
    mastery_already_va = entry_va + 0x3C
    mastery_record_setup = _record_setup(config)
    mastery_advance = ""
    mastery_changed_setup = ""
    mastery_changed_increment = ""
    mastery_postverify = ""
    mastery_completion = ""
    mastery_per_record_completion = ""
    if config.get("native_skill_writer"):
        if config.get("native_mastery_manager"):
            mastery_record_setup += f"\n            call {_hex_word(config['native_mastery_manager'])}\n            test eax, eax\n            jz mastery_failure\n            lea ebp, [eax + 0x52C]\n            xor edi, edi"
        elif config.get("native_evaluator_per_record"):
            # This ABI writes directly through the villager's skill array and
            # does not need a manager-backed record pointer or a physical
            # index.  EDI is a per-record changed flag below.
            mastery_record_setup += "\n            xor edi, edi"
        else:
            mastery_record_setup += "\n            mov ebp, ecx\n            xor edi, edi"
        mastery_advance = (
            ""
            if config.get("native_evaluator_per_record")
            else "inc edi"
        )
        mastery_postverify = "\n".join(
            f"cmp dword ptr [esi + {_hex_word(offset)}], {_hex_word(config.get('master_value', 100))}\n            jne mastery_failure"
            for offset in config["skills"]
        )
        if config.get("native_mastery_evaluator") and not config.get(
            "native_evaluator_per_record"
        ):
            mastery_record_setup += "\n            xor eax, eax"
            mastery_changed_increment = "inc eax"
            mastery_completion = f"""
            test eax, eax
            jz mastery_return
            call {_hex_word(config['native_mastery_manager'])}
            test eax, eax
            jz mastery_return
            mov ecx, eax
            call {_hex_word(config['native_mastery_evaluator'])}
        mastery_return:
        """
        if config.get("native_evaluator_per_record"):
            mastery_changed_setup = "xor edi, edi"
            mastery_changed_increment = "inc edi"
            mastery_per_record_completion = f"""
            test edi, edi
            jz mastery_next
            push esi
            call {_hex_word(config['native_mastery_evaluator'])}
            """
        skill_writes = "\n".join(
            f"""
            cmp dword ptr [esi + {_hex_word(offset)}], {_hex_word(config.get('master_value', 100))}
            je mastery_skill_next_{index}
            {
                f"push {_hex_word(config.get('master_value', 100))}\n            fld dword ptr [esp]\n            fsub dword ptr [esi + {_hex_word(offset)}]\n            fstp dword ptr [esp]"
                if config.get('native_skill_writer_float')
                else f"mov eax, 100\n            sub eax, dword ptr [esi + {_hex_word(offset)}]\n            push eax"
            }
            {
                f"push {_hex_word(index)}"
                if not config.get("native_skill_writer_uses_physical_index", True)
                else f"push {_hex_word(code)}\n            push edi"
            }
            {
                f"lea ecx, [esi + {_hex_word(config['skills'][0])}]"
                if not config.get("native_skill_writer_uses_physical_index", True)
                else "mov ecx, ebp"
            }
            call {_hex_word(config['native_skill_writer'])}
            {mastery_changed_increment}
        mastery_skill_next_{index}:
            """
            for index, (offset, code) in enumerate(
                zip(config["skills"], config["skill_codes"])
            )
        )
    elif config.get("native_mastery"):
        skill_writes = f"""
            xor edi, edi
        mastery_skill_loop:
            cmp edi, {len(config['skills'])}
            jae mastery_skills_done
            cmp dword ptr [esi+edi*4+{_hex_word(config['skills'][0])}], {_hex_word(config['master_value'])}
            je mastery_skill_next
            push {_hex_word(config['master_value'])}
            fld dword ptr [esp]
            fsub dword ptr [esi+edi*4+{_hex_word(config['skills'][0])}]
            fstp dword ptr [esp]
            push edi
            lea ecx, [esi+edi*4+{_hex_word(config['skills'][0])}]
            call {_hex_word(config['native_mastery'])}
        mastery_skill_next:
            inc edi
            jmp mastery_skill_loop
        mastery_skills_done:
        """
    else:
        skill_writes = "\n".join(
            f"mov dword ptr [esi + {_hex_word(offset)}], {_hex_word(config['master_value'])}"
            for offset in config["skills"]
        )
    if report_mastery:
        # A villager already at master_value on every skill needs neither
        # a write nor a postverify -- count it as already-mastered and
        # skip straight to mastery_next, without disturbing edi's physical-
        # index bookkeeping (mastery_advance still runs there as normal).
        already_mastered_check = "\n".join(
            f"cmp dword ptr [esi + {_hex_word(offset)}], {_hex_word(config.get('master_value', 100))}\n            jne mastery_needs_write"
            for offset in config["skills"]
        )
        mastery_body = f"""
            {already_mastered_check}
            inc dword ptr [0x{mastery_already_va:X}]
            jmp mastery_next
        mastery_needs_write:
            {skill_writes}
            {mastery_postverify}
            inc dword ptr [0x{mastery_granted_va:X}]
        """
    else:
        mastery_body = f"""
            {skill_writes}
            {mastery_postverify}
        """
    mastery_scratch_init = (
        f"""
            mov dword ptr [0x{mastery_granted_va:X}], 0
            mov dword ptr [0x{mastery_already_va:X}], 0
        """
        if report_mastery
        else ""
    )
    put(
        mastery_va,
        f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebx, edx
            {mastery_record_setup}
            {mastery_scratch_init}
        mastery_loop:
            test ebx, ebx
            jz mastery_done
            {_eligibility(config, 'mastery_next')}
            {mastery_changed_setup}
            {mastery_body}
            {mastery_per_record_completion}
        mastery_next:
            add esi, {_hex_word(config['stride'])}
            {mastery_advance}
            dec ebx
            jmp mastery_loop
        mastery_done:
            {mastery_completion}
        mastery_failure:
            xor eax, eax
            xor edx, edx
            xor ecx, ecx
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
    )

    # report_age_granted mirrors report_running_granted/report_mastery_counts:
    # VV1-only opt-in, same fixed-scratch-dword approach (no register left at
    # age_done's return point either -- every existing caller already relies
    # on eax/edx/ecx being zeroed there).
    report_age = bool(config.get("report_age_granted"))
    age_granted_va = entry_va + 0x40
    age_scratch_init = (
        f"mov dword ptr [0x{age_granted_va:X}], 0" if report_age else ""
    )
    age_skip_check = (
        f"""
            cmp dword ptr [esi + {_hex_word(config['age'])}], 360
            je age_next
        """
        if report_age
        else ""
    )
    age_increment = (
        f"inc dword ptr [0x{age_granted_va:X}]" if report_age else ""
    )
    # Writing only the raw age field (config['age']) is not enough to make
    # a villager -- especially an elder, whose age can be well past 360 --
    # actually settle at 18: the stock engine's own age-mutation routine
    # (decompiled at 0x419543-0x4195be in the exact VV1 build) always
    # keeps age+4 (a "last-synced age" bookkeeping field the engine reads
    # back on the next per-frame update) equal to the current age right
    # after changing it, and shifts age+0x10 (the pregnancy timer) to
    # match, or the engine's own logic can recompute/override the age
    # right back to something derived from the stale bookkeeping. This
    # mirrors detail_age_18's own single-villager version exactly (down
    # to the same 318 = 360 - 42 gestation-offset constant), which
    # already gets this right and is the reason it doesn't have the same
    # bug this village-wide row does.
    age_sync = (
        f"""
            mov dword ptr [esi + {_hex_word(config['age'] + 4)}], 360
            cmp dword ptr [esi + {_hex_word(config['age'] + 0x10)}], 0
            je age_pregnancy_synced
            mov dword ptr [esi + {_hex_word(config['age'] + 0x10)}], 318
        age_pregnancy_synced:
        """
        if report_age
        else ""
    )
    put(
        age_va,
        f"""
            push ebp
            push ebx
            push esi
            push edi
            mov ebp, ecx
            mov ebx, edx
            {_record_setup(config)}
            {age_scratch_init}
        age_loop:
            test ebx, ebx
            jz age_done
            {_eligibility(config, 'age_next')}
            {age_skip_check}
            mov dword ptr [esi + {_hex_word(config['age'])}], 360
            {age_sync}
            {age_increment}
        age_next:
            add esi, {_hex_word(config['stride'])}
            dec ebx
            jmp age_loop
        age_done:
            xor eax, eax
            xor edx, edx
            xor ecx, ecx
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
    )

    header = bytearray(b"VVFPOWU\0")
    entry_offset = entry_va - payload_va
    if entry_offset < 0 or entry_offset > 0xFFFF:
        raise AssertionError(
            f"entry_offset {entry_offset:#x} does not fit the packed 16-bit field"
        )
    # version (low 16 bits) and entry_offset (high 16 bits) packed into one
    # dword at +0x8: every base Origins feature's preflight validator checks
    # this exact packed value, not two separate dwords. +0xC is reserved/zero
    # (unchecked) so the command count at +0x10 stays at the offset every
    # validator already expects.
    header.extend((1 | (entry_offset << 16)).to_bytes(4, "little"))
    header.extend(b"\0" * 4)
    header.extend((3).to_bytes(4, "little"))
    if len(header) > 0x20:
        raise AssertionError("optional ABI header grew beyond the reserved header")
    header.extend(b"\0" * (0x20 - len(header)))
    payload = bytes(header + code)
    return payload, {
        "signature_offset": config["payload_offset"],
        "entry_offset": config["payload_offset"] + (entry_va - payload_va),
        "running_offset": config["payload_offset"] + (running_va - payload_va),
        "mastery_offset": config["payload_offset"] + (mastery_va - payload_va),
        "age_offset": config["payload_offset"] + (age_va - payload_va),
    }


def main() -> None:
    stock_dir = ROOT / "research" / "stock-executables"
    for game_id, config in CONFIG.items():
        stock_path = stock_dir / config["exe"]
        original = stock_path.read_bytes()
        actual_hash = hashlib.sha256(original).hexdigest().upper()
        if actual_hash != config["sha256"]:
            raise RuntimeError(f"{game_id} stock SHA-256 mismatch: {actual_hash}")
        payload, entries = build_payload(config)
        offset = config["payload_offset"]
        before = original[offset : offset + len(payload)]
        if len(before) != len(payload) or any(before):
            raise RuntimeError(
                f"{game_id} optional reserve is not certified zero-filled at 0x{offset:X}"
            )
        rendered = bytearray(original)
        rendered[offset : offset + len(payload)] = payload
        out_dir = ROOT / "research" / f"{game_id}-origins-village-wide"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_exe = out_dir / f"{config['title']} - Origins Village Wide Research.exe"
        out_exe.write_bytes(rendered)
        feature_id = f"{game_id}_origins_village_wide_upgrades"
        feature_name = "Enable Origins Tech, Details, and Village-Wide Upgrades"
        enabled = True
        description = (
            "Includes the Origins Tech screen and Villager Details-screen buttons "
            "and their upgrades through the internal Origins prerequisite. The "
            "Village-Wide menu offers Running, Full Mastery, and Make Villagers "
            "Young Adults."
        )
        if game_id == "vv1":
            description += " Island Events, Duplicate Collectibles, and Golden Child tech gains are excluded."
        elif game_id == "vv2":
            description += " Island Events, Duplicate Collectibles, and Gong of Wonder tech gains are excluded."
        elif game_id in {"vv3", "vv4"}:
            description += " Island Events and Duplicate Collectibles are excluded."
        else:
            description += " Island Events and Duplicate Collectibles are excluded; only Believers are processed and Heathens are skipped."
        record_fields = {
            "stride": f"0x{config['stride']:X}",
            "first_record_argument": "ECX",
            "active_offset": f"0x{config['active']:X}",
            "health_offset": f"0x{config['health']:X}",
            "age_offset": f"0x{config['age']:X}",
            "likes_offset": f"0x{config['likes']:X}",
            "dislikes_offset": f"0x{config['dislikes']:X}",
            "like_slot_count": config["slot_count"],
            "dislike_slot_count": config["slot_count"],
            "running_preference_id": config["running_preference_id"],
            "skill_offsets": [f"0x{offset:X}" for offset in config["skills"]],
            "native_skill_writer": (
                f"0x{config['native_skill_writer']:X}"
                if config.get("native_skill_writer")
                else None
            ),
            "bound_source": "EDX physical record bound",
        }
        if config.get("totem") is not None:
            record_fields["totem_offset"] = f"0x{config['totem']:X}"
        if config.get("native_mastery_manager"):
            record_fields["native_mastery_manager"] = f"0x{config['native_mastery_manager']:X}"
        if config.get("native_mastery_evaluator"):
            record_fields["native_mastery_evaluator"] = f"0x{config['native_mastery_evaluator']:X}"
        if config.get("native_evaluator_per_record"):
            record_fields["native_evaluator_scope"] = "once per changed villager after exact-100 postverification"
        if config.get("native_skill_writer_uses_physical_index") is False:
            record_fields["native_skill_writer_index"] = "skill ordinal 0..4"
        if config.get("native_skill_writer_float"):
            record_fields["mastery_target"] = "Float32 100.0"
            record_fields["native_skill_writer_value"] = "Float32 delta: 100.0-current"
        mastery_behavior = (
            "Grant Full Mastery to All Villagers uses the native Float32 skill writer "
            "for each changed skill and postverifies exact 100.0 values."
            if config.get("native_skill_writer_float")
            else "Grant Full Mastery to All Villagers writes native mastery values and runs the native award evaluator for each changed eligible villager."
        )
        feature = {
            "id": feature_id,
            "game_id": game_id,
            "running_preference_id": config["running_preference_id"],
            "running_preference_evidence": {
                "source": "exact stock executable embedded preference table",
                "table_file_offset": {
                    "vv1": "0x7B260",
                    "vv2": "0x8B808",
                    "vv3": "0x97488",
                    "vv4": "0xA0CD8",
                    "vv5": "0xAEF60",
                }[game_id],
                "entry_name": "running",
            },
            "name": feature_name,
            "description": description,
            "output_tag": "Origins Tech, Details, and Village-Wide Upgrades",
            "dependencies": [f"{game_id}_enable_origins_exclusive_features"],
            "extension_abi": {
                "signature": "VVFPOWU",
                "signature_offset": f"0x{entries['signature_offset']:X}",
                "entry_offset": f"0x{entries['entry_offset']:X}",
                "entry_virtual_address": f"0x{config['cave_va'] + (entries['entry_offset'] - config['cave_offset']):X}",
                "calling_convention": "near call with EAX=command 6/7/8, ECX=first physical record pointer, EDX=physical record bound; command 6 returns full-Like skips in EAX, already-Running (already-running) skips in EDX, and villagers with a removed Running dislike in ECX; full Like records receive no preference writes; commands 7/8 return zero counts; invalid commands return EAX=-1 and EDX/ECX=0; preserves EBX/ESI/EDI/EBP/ESP",
                "commands": {
                    "6": "All Villagers Like Running",
                    "7": "Grant Full Mastery to All Villagers",
                    "8": "All Villagers are 18",
                },
            },
            "record_fields": record_fields,
            "behavior_changes": [
                "Includes the matching base Origins feature so the Tech-screen and Villager Details-screen buttons and upgrades are installed with this public route.",
                "Adds rows 6-8 to the Origins Tech-screen Upgrades dialog only when this optional feature is installed.",
                "Charges exactly 1,000,000 tech points once per selected village-wide purchase in the current save.",
                f"Running scans exactly {config['slot_count']} physical Like and Dislike slots, adds Running only to the first free Like slot, removes Running Dislikes only after that insertion, and leaves already-Running or full-like villagers unchanged.",
                mastery_behavior,
                "All Villagers are 18 writes only the verified displayed-age field to 360 age units.",
            ],
            "running_preference_id": config["running_preference_id"],
            "explicit_non_changes": [
                "No unrelated Like is replaced or removed.",
                "No movement speed, movement initialization, nursing timer, pregnancy timer, or pregnancy state is written.",
                "The upgrades are save-scoped and do not set a global ownership bit.",
            ],
            "evidence_status": "static exact-build payload and field-map verification performed; runtime/player confirmation pending",
            "cave": {
                "file_offset": f"0x{offset:X}",
                "virtual_address": f"0x{config['cave_va'] + (offset - config['cave_offset']):X}",
                "length": len(payload),
                "reserved_range": f"0x{config['cave_offset']:X}-0x{config['cave_offset'] + 0x1000:X}",
                "ownership": "optional Origins village-wide payload only",
            },
            "companion_files": [],
            "patches": [
                {
                    "offset": f"0x{offset:X}",
                    "before": before.hex().upper(),
                    "after": payload.hex().upper(),
                    "purpose": "install the optional signed Origins village-wide ABI payload without overwriting base Origins bytes",
                }
            ],
        }
        # This user-requested package exposes the complete five-game set as
        # static/runtime-playtest options. It does not claim player or runtime
        # GO, and the package documentation preserves the reported crash gates.
        feature["enabled"] = enabled
        if game_id == "vv5":
            feature["explicit_non_changes"].append(
                "VV5 Heathens are excluded from all three village-wide operations."
            )
            feature["record_fields"].update(
                {
                    "heathen_active_guard_offset": f"0x{config['heathen_active_guard']:X}",
                    "faction_offset": f"0x{config['faction']:X}",
                    "eligibility": "active != 0, heathen-active guard == 0, faction == believer (0), health > 0",
                }
            )
        manifest_path = ROOT / "data" / f"{feature_id}.json"
        manifest_path.write_text(json.dumps(feature, indent=2) + "\n", encoding="utf-8")
        print(f"{game_id}: {len(payload):#x} bytes -> {manifest_path}")


if __name__ == "__main__":
    main()
