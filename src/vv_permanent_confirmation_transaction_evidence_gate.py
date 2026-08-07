"""Disabled VV1/VV2 permanent-purchase transaction evidence gate."""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from typing import Any,Mapping
ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"data/candidates/vv1_vv2_permanent_confirmation_transaction_evidence_gate.json"
SCHEMA=ROOT/"data/candidates/vv1_vv2_permanent_confirmation_transaction_evidence.schema.json"
HEX=re.compile(r"^[0-9A-F]{64}$"); NO_CHARGE="No tech points have been deducted."
STOCK={"vv1":{"filename":"Virtual Villagers - A New Home.exe","size":581632,"sha256":"1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D"},"vv2":{"filename":"Virtual Villagers - The Lost Children.exe","size":724992,"sha256":"46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"}}
ROUTES=("tech_time_warp","tech_island_event","tech_barrel_of_babies","tech_legacy_cure","selected_grant_youth","selected_full_mastery","selected_running","selected_age_18")
ROUTE_FACTS={"tech_time_warp":(0,50000),"tech_island_event":(1,30000),"tech_barrel_of_babies":(2,75000),"tech_legacy_cure":(5,30000),"selected_grant_youth":(0,50000),"selected_full_mastery":(1,100000),"selected_running":(2,40000),"selected_age_18":(3,50000)}
FORBIDDEN=("synthetic","manual","placeholder","todo","tbd","unknown address")
class EvidenceError(ValueError):pass
def fail(p,m):raise EvidenceError(f"{p}: {m}")
def obj(v,p):
 if not isinstance(v,Mapping):fail(p,"must be object")
 return v
def required(v,p,names):
 for n in names:
  if n not in v:fail(f"{p}.{n}","missing")
def load_contract(path=CONTRACT):
 c=obj(json.loads(Path(path).read_text(encoding="utf-8")),"contract")
 for k,x in {"status":"STOP","enabled":False,"catalog_enabled":False,"catalog_hidden":True,"publication":False,"player_ready":False,"runtime_certified":False,"native_output":False}.items():
  if c.get(k)!=x or type(c.get(k)) is not type(x):fail(f"contract.{k}",f"must be {x!r}")
 if c.get("public_choices")!=[] or c.get("evidence_records")!=[]:fail("contract","must expose nothing")
 if tuple(r["id"] for r in c["routes"])!=ROUTES:fail("contract.routes","exact route order required")
 for r in c["routes"]:
  if r["action"]!="Buy" or r["remove"] is not False or (r["command"],r["price"])!=ROUTE_FACTS[r["id"]] or r["abi"] is not None or r["receipts"] is not None:fail(f"contract.routes.{r['id']}","must pin command/price, Buy-only, and unknown ABI/receipts null")
 if any(v is not None for v in c["unknown_evidence"].values()):fail("contract.unknown_evidence","must remain null")
 return c
def _clean(v,p="candidate"):
 if isinstance(v,str) and any(x in v.casefold() for x in FORBIDDEN):fail(p,"manual/synthetic/placeholder evidence forbidden")
 if isinstance(v,Mapping):
  for k,x in v.items():_clean(x,f"{p}.{k}")
 if isinstance(v,list):
  for i,x in enumerate(v):_clean(x,f"{p}[{i}]")
def validate_candidate(c):
 c=obj(c,"candidate"); _clean(c)
 required(c,"candidate",("schema_version","game_id","route_id","command","price","action","remove","status","enabled","catalog_enabled","catalog_hidden","publication","player_ready","runtime_certified","native_output","source","stock","folder_inventory","dry_run","confirmation","reacquisition","native_mutation","postverify","deduction","charge_certainty","fullscreen","wording","ownership","receipts"))
 for k,x in {"schema_version":1,"status":"STOP","enabled":False,"catalog_enabled":False,"catalog_hidden":True,"publication":False,"player_ready":False,"runtime_certified":False,"native_output":False,"source":"repository-owned-automated-evidence"}.items():
  if c[k]!=x or type(c[k]) is not type(x):fail(f"candidate.{k}",f"must be {x!r}")
 if c["game_id"] not in STOCK or dict(c["stock"])!=STOCK[c["game_id"]]:fail("candidate.stock","exact stock required")
 if c["route_id"] not in ROUTES:fail("candidate.route_id","unsupported")
 if (c["command"],c["price"])!=ROUTE_FACTS[c["route_id"]] or c["action"]!="Buy" or c["remove"] is not False:fail("candidate.route","exact command/price and permanent Buy-only action required")
 inv=obj(c["folder_inventory"],"candidate.folder_inventory"); required(inv,"candidate.folder_inventory",("complete","no_follow","inventory_sha256","dlls"))
 if inv["complete"] is not True or inv["no_follow"] is not True or not HEX.fullmatch(inv["inventory_sha256"]):fail("candidate.folder_inventory","complete no-follow inventory required")
 if not isinstance(inv["dlls"],list) or not inv["dlls"]:fail("candidate.folder_inventory.dlls","complete DLL inventory required")
 dry=obj(c["dry_run"],"candidate.dry_run"); required(dry,"candidate.dry_run",("complete","exact_eligibility","world_id","selected_index","record_id","account_id","funds","predicted_count","no_op_before_confirmation"))
 if dry["complete"] is not True or dry["no_op_before_confirmation"] is not True:fail("candidate.dry_run","complete dry run/no-op gate required")
 conf=obj(c["confirmation"],"candidate.confirmation"); required(conf,"candidate.confirmation",("owner_valid_same_process","owner_reused","accepted_result","all_other_results_cancel","prompt_binds_target_cost_prediction"))
 if conf["accepted_result"]!="IDOK" or not all(conf[k] is True for k in ("owner_valid_same_process","owner_reused","all_other_results_cancel","prompt_binds_target_cost_prediction")):fail("candidate.confirmation","owner-bound IDOK-only required")
 reac=obj(c["reacquisition"],"candidate.reacquisition"); required(reac,"candidate.reacquisition",("fresh_world","fresh_selection","fresh_record","fresh_account","fresh_funds","identities_equal","prestate_equal"))
 if not all(reac.values()):fail("candidate.reacquisition","all identities/funds/prestate must be fresh and equal")
 mut=obj(c["native_mutation"],"candidate.native_mutation"); required(mut,"candidate.native_mutation",("setter_abi","side_effects","direct_store","legacy_route","readback"))
 if mut["direct_store"] is not False or mut["legacy_route"] is not False or not mut["setter_abi"] or not mut["side_effects"] or mut["readback"] is not True:fail("candidate.native_mutation","native setter/readback required; direct/legacy routes rejected")
 post=obj(c["postverify"],"candidate.postverify"); required(post,"candidate.postverify",("complete","before_deduction","verified_count"))
 if post["complete"] is not True or post["before_deduction"] is not True:fail("candidate.postverify","complete pre-deduction postverify required")
 ded=obj(c["deduction"],"candidate.deduction"); required(ded,"candidate.deduction",("native_abi","call_count","after_postverify","funds_readback","precharge"))
 if ded["call_count"] not in (0,1) or ded["funds_readback"] is not True or ded["precharge"] is not False or (ded["call_count"]==1 and ded["after_postverify"] is not True):fail("candidate.deduction","zero-or-one native deduction with readback and no precharge required")
 word=obj(c["wording"],"candidate.wording"); required(word,"candidate.wording",("count_phrase","result","charge_sentence","partial_disclosure"))
 if "villager(s)" in json.dumps(word):fail("candidate.wording","unnatural pluralization forbidden")
 expected_count="No villagers were changed." if post["verified_count"]==0 else "1 villager was changed." if post["verified_count"]==1 else f"{post['verified_count']} villagers were changed."
 if word["count_phrase"]!=expected_count:fail("candidate.wording.count_phrase","must use exact natural zero/one/many form")
 charge=c["charge_certainty"]
 if charge not in ("not_charged","charged_once","unknown"):fail("candidate.charge_certainty","invalid")
 text=json.dumps(word)
 if charge=="unknown" and NO_CHARGE in text:fail("candidate.wording","unknown charge cannot claim no deduction")
 if charge=="not_charged" and (NO_CHARGE not in text or ded["call_count"]!=0):fail("candidate.wording","proved no-charge requires zero deduction and exact suffix")
 if charge=="charged_once" and ded["call_count"]!=1:fail("candidate.deduction","charged_once requires one call")
 full=obj(c["fullscreen"],"candidate.fullscreen"); required(full,"candidate.fullscreen",("owner_contract_sha256","leave_succeeded","restore_count","result_owner_reused","cleanup"))
 if not HEX.fullmatch(full["owner_contract_sha256"]) or full["result_owner_reused"] is not True or full["cleanup"] is not True or full["restore_count"]!=int(bool(full["leave_succeeded"])):fail("candidate.fullscreen","owner lifecycle/restore cardinality invalid")
 if not isinstance(c["receipts"],list) or not c["receipts"]:fail("candidate.receipts","runtime receipts required")
 return True
def assert_enablement_blocked(*a,**k):raise EvidenceError("enablement unavailable; tracked evidence is empty")
def validate_clean_archive(root):
 required_paths=[CONTRACT.relative_to(ROOT),SCHEMA.relative_to(ROOT),Path("src/vv_permanent_confirmation_transaction_evidence_gate.py"),Path("tests/test_vv1_vv2_permanent_confirmation_transaction_evidence_gate.py"),Path("docs/vv1-vv2-permanent-confirmation-transaction-evidence-gate.md")]
 for p in required_paths:
  if not (Path(root)/p).is_file():fail("archive",f"missing {p}")
 for p in Path(root).rglob("*"):
  if p.is_file() and p.suffix.casefold() in (".exe",".dll",".bin",".zip",".page"):fail("archive",f"native/package artifact forbidden: {p.name}")
