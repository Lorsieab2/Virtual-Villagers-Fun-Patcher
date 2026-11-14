"""Review M2/M3 + the coda-odds rule: rebuild every V8/V9/V10 event's coda.

FIT TABLE (item: binding of the coda's figures to the event's own roles, the path it fits, rare):
- V8 "RARE EMOTIONAL CODAS" (L4332): a coda follows 1 time in 5 (rare against none, 5:20).
- V9 "UNIVERSAL CODA BANK" (L5225) and V10 "ADDITIONAL OUTCOME BANK" (L5929) give no rarity: 1 in 2.
  V9's editorial note (L5323-5325) makes violence, severe betrayal and custody rare: R1, R2, R11.
- A figure the event already cast takes that role's pronouns (an event-local copy of the item, same src); a figure
  the event never cast stays a random stranger (coda1/coda2).
"""
import json
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data" / "event_collection"
SHARED = json.load(open(D / "shared_pools.json", encoding="utf-8"))["pools"]


def V(*ids):
    return {"visited": ids[0]} if len(ids) == 1 else {"any": [{"visited": i} for i in ids]}


T = {
    # ---- V8
    "v8/vv1_masters_small_apprentice.json": ("v8", [
        ("c2", {"coda1": "builder", "coda2": "child"}, V("turn2"), False),
        ("c10", {}, None, False),
        ("c12", {"coda1": "builder", "coda2": "child"}, V("turn1"), False),
        ("c16", {"coda1": "elder"}, None, False)]),
    "v8/vv1_last_song_before_sunset.json": ("v8", [
        ("c5", {"coda1": "parent"}, None, False), ("c7", {}, None, False), ("c10", {}, None, False),
        ("c16", {"coda1": "elder"}, None, False)]),
    "v8/vv2_packed_hospital.json": ("v8", [
        ("c4", {"coda1": "elder"}, V("el2"), False), ("c5", {"coda1": "parent"}, None, False),
        ("c10", {}, None, False)]),
    "v8/vv2_timid_child.json": ("v8", [("c10", {}, None, False), ("c16", {}, None, False)]),
    "v8/vv3_unfortunate_portrait.json": ("v8", [("c10", {}, None, False), ("c16", {}, None, False)]),
    "v8/vv3_tale_telling_elder.json": ("v8", [
        ("c4", {"coda1": "elder"}, None, False), ("c5", {}, None, False), ("c7", {}, None, False),
        ("c10", {}, None, False), ("c16", {"coda1": "elder"}, None, False)]),
    "v8/vv4_fruity_masterpiece.json": ("v8", [
        ("c4", {"coda1": "elder"}, V("old"), False), ("c5", {}, None, False), ("c10", {}, None, False)]),
    "v8/vv4_quiet_gardener.json": ("v8", [
        ("c7", {}, None, False), ("c10", {}, None, False), ("c16", {"coda1": "elder"}, None, False)]),
    "v8/vv5_gift_or_insult.json": ("v8", [("c10", {}, None, False), ("c12", {}, None, False)]),
    "v8/vv5_little_things_remember.json": ("v8", [("c7", {}, None, False), ("c10", {}, None, False)]),
    # ---- V9
    "v9/vv1_the_wall.json": ("v9", [
        ("r1", {}, None, True), ("r3", {}, V("hearing"), False), ("r5", {"coda1": "child"}, V("w4"), False),
        ("r7", {"coda1": "friend"}, V("evidence", "fault"), False), ("r8", {}, V("p2"), False),
        ("r13", {"coda1": "culprit"}, V("sabotage"), False), ("r14", {}, None, False), ("r18", {}, None, False),
        ("r19", {}, V("r_tech", "r_plain"), False), ("r24", {}, V("u_tech", "u_plain"), False)]),
    "v9/vv1_missing_pearl.json": ("v9", [("r5", {}, None, False), ("r24", {}, V("theft"), False)]),
    "v9/vv2_experimental_remedy.json": ("v9", [
        ("r14", {}, V("m2"), False), ("r16", {}, V("v2"), False), ("r17", {}, None, False),
        ("r22", {}, V("d1", "d2", "d3", "d4"), False), ("r24", {}, V("m2"), False)]),
    "v9/vv2_stolen_spoon.json": ("v9", [
        ("r6", {}, V("wrong_guilt"), False), ("r7", {}, V("found"), False), ("r9", {}, V("t1"), False),
        ("r10", {}, V("trial"), False), ("r11", {}, V("accountability"), True), ("r14", {}, None, False),
        ("r15", {}, V("witnesses"), False), ("r17", {}, None, False), ("r24", {}, V("compromise"), False)]),
    "v9/vv3_chief_and_the_pearl.json": ("v9", [
        ("r4", {}, V("false"), False), ("r5", {}, V("false"), False), ("r10", {}, V("courtroom"), False),
        ("r15", {}, None, False), ("r16", {}, None, False), ("r25", {}, V("e2"), False)]),
    "v9/vv3_duel_terrible_inventors.json": ("v9", [
        ("r1", {}, None, True), ("r2", {}, None, True), ("r14", {}, V("cool"), False), ("r19", {}, None, False),
        ("r22", {}, V("test"), False), ("r24", {}, None, False)]),
    "v9/vv4_arbor_day_festival.json": ("v9", [("r17", {}, None, False), ("r22", {}, None, False)]),
    "v9/vv4_rotten_structure.json": ("v9", [
        ("r7", {"coda1": "apprentice"}, V("wrongful"), False), ("r8", {}, None, False),
        ("r9", {}, V("hearing"), False), ("r13", {}, V("misconduct"), False), ("r14", {}, None, False),
        ("r18", {}, None, False), ("r23", {}, None, False), ("r24", {}, V("mixed"), False)]),
    "v9/vv5_slug_race.json": ("v9", [
        ("r10", {}, V("mock"), False), ("r14", {}, V("apology"), False), ("r16", {}, V("children"), False),
        ("r21", {}, V("mock"), False), ("r26", {}, None, False)]),
    "v9/vv5_trial_shattered_pearls.json": ("v9", [
        ("r7", {}, V("exoneration"), False), ("r8", {}, V("exoneration", "bittersweet"), False),
        ("r9", {}, V("hearing"), False), ("r11", {}, V("intentional"), True),
        ("r13", {"coda1": "culprit"}, V("intentional"), False), ("r18", {}, None, False),
        ("r23", {}, V("c1"), False)]),
    # ---- V10
    "v10/all_no_good_very_bad_day.json": ("v10", [
        ("o1", {}, V("ostracism"), False), ("o3", {}, V("ostracism"), False), ("o14", {}, V("exon"), False),
        ("o15", {}, V("wrong", "x3"), False), ("o16", {}, V("wrong"), False), ("o17", {}, V("unresolved"), False),
        ("o19", {}, V("ostracism"), False), ("o20", {}, V("exon"), False), ("o24", {}, V("exon"), False),
        ("o28", {}, V("wrong"), False)]),
    "v10/all_impossible_invention.json": ("v10", [
        ("o2", {}, V("t2", "t3"), False), ("o3", {}, None, False), ("o4", {}, V("mad"), False),
        ("o16", {}, V("warning"), False), ("o18", {}, None, False), ("o20", {}, V("result", "human"), False),
        ("o29", {}, None, False)]),
    "v10/all_unlikely_advisor.json": ("v10", [
        ("o5", {}, V("ap1", "ap3"), False), ("o16", {}, V("ap2"), False), ("o23", {}, V("ap3"), False),
        ("o26", {}, V("ap1"), False), ("o27", {}, V("ap1", "ap4"), False)]),
    "v10/all_teacher_who_failed.json": ("v10", [("o16", {}, None, False), ("o23", {}, None, False),
                                               ("o29", {}, None, False)]),
    "v10/all_great_appointment_scandal.json": ("v10", [
        ("o17", {}, None, False), ("o19", {}, V("scandal"), False), ("o23", {}, None, False),
        ("o24", {}, None, False), ("o25", {}, V("appoint"), False), ("o27", {}, V("appoint"), False)]),
    "v10/vv345_magician_naturalist.json": ("v10", [
        ("o12", {}, V("oc5"), False), ("o13", {}, V("oc5"), False), ("o15", {}, None, False),
        ("o17", {}, V("oc2"), False)]),
}
RARE_HEADING = {"v8": True, "v9": False, "v10": False}


def pool_to_branch(d, pool, node, idprefix):
    p = d["pools"].pop(pool)
    n = d["nodes"][node]
    kids = {}
    for i, it in enumerate(p["items"], 1):
        c = {k: v for k, v in n.items() if k not in ("text", "name", "src")}
        c["src"], c["text"] = it["src"], it["text"]
        kids[f"{idprefix}{i}"] = c
    new = {}
    for k, v in d["nodes"].items():
        if k == node:
            new[node] = {"type": "branch", "set": p["set"], "children": [{"next": c} for c in kids]}
            new.update(kids)
        else:
            new[k] = v
    d["nodes"] = new


for f, (sec, items) in T.items():
    p = D / f
    d = json.load(open(p, encoding="utf-8"))
    if f.endswith("vv345_magician_naturalist.json") and "OUTCOMES" in d["pools"]:
        pool_to_branch(d, "OUTCOMES", "outcome", "oc")
    nodes = {k: v for k, v in d["nodes"].items() if not (k.startswith("coda") or k == "no_coda")}
    d["include_pools"] = [x for x in d.get("include_pools", []) if not x.startswith(("v8_", "v9_r", "v10_"))]
    d["pools"] = {k: v for k, v in d.get("pools", {}).items() if not k.startswith("CODA_")}
    for r in ("coda1", "coda2"):
        d["roles"].pop(r, None)
    need = set()
    kids = []
    rare_any = any(x[3] for x in items)
    prefix = {"v8": "v8_", "v9": "v9_", "v10": "v10_"}[sec]
    for item, bind, cond, rare in items:
        shared = prefix + item
        text = SHARED[shared]["items"][0]["text"]
        src = SHARED[shared]["items"][0]["src"]
        if bind:
            for a, b in bind.items():
                text = text.replace(f"({a}.", f"({b}.")
            # a bound copy of the item lives in shared_pools.json too (an event pool may not cite lines outside
            # the event): v8_c2_builder_child = C2 with the adult as the builder and the child as the child
            name = shared + "_" + "_".join(bind[k] for k in sorted(bind))
            SHARED[name] = {"items": [{"text": text, "src": src}]}
            d["include_pools"].append(name)
        else:
            name = shared
            d["include_pools"].append(shared)
        for r in ("coda1", "coda2"):
            if f"({r}." in text:
                need.add(r)
        nodes[f"coda_{item}"] = {"popup": "append", "join": "paragraph", "text": "{" + name + "}"}
        c = {"next": f"coda_{item}"}
        if cond:
            c["if"] = cond
        if rare_any:
            c["weight"] = 5 if rare else 20
            if rare:
                c["rarity"] = "rare"
        kids.append(c)
    for r in sorted(need):
        d["roles"][r] = {"kind": "stranger", "sex": "random"}
    if RARE_HEADING[sec]:
        top = [{"next": "coda_pick", "weight": 5, "rarity": "rare"}, {"next": "no_coda", "weight": 20}]
    else:
        top = [{"next": "coda_pick"}, {"next": "no_coda"}]
    nodes["coda"] = {"type": "branch", "children": top}
    nodes["coda_pick"] = {"type": "branch", "children": kids, "else": "no_coda"}
    nodes["no_coda"] = {"type": "branch"}
    d["nodes"] = nodes
    if not d["include_pools"]:
        del d["include_pools"]
    p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("ok", f)
sp = json.load(open(D / "shared_pools.json", encoding="utf-8"))
sp["pools"] = SHARED
(D / "shared_pools.json").write_text(json.dumps(sp, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
