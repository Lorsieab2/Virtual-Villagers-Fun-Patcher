"""Disabled catalog-wide runtime coverage matrix validator."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

SOURCE_COMMIT="e43464eb21667aba619d63272a808b0540ccf015"
GAMES=("vv3","vv4","vv5")
CATALOG={
"vv3":("vv3_nature_honey_refill","vv3_nature_level_three_alters_mortality","vv3_rare_collectible_retry","vv3_enable_origins_exclusive_features","vv3_full_mastery_all_stage_a_candidate","vv3_write_village_statistics"),
"vv4":("vv4_complete_scales_golden_fish","vv4_enable_origins_exclusive_features","vv4_full_mastery_all_stage_a_candidate","vv4_write_village_statistics"),
"vv5":("vv5_heathen_mommy_puzzle","vv5_easier_devotee_training","vv5_statue_polishing_or_honoring","vv5_vv4_nursery_divisor_parity","vv5_enable_origins_exclusive_features","vv5_write_village_statistics")}
SCENARIOS=("windowed","fullscreen","success","no_op","failure","uninstall","composition","crash_hang_monitoring")
SAVE_SCENARIOS=("full_save_completion","save_reload","offline_catch_up","failed_load_nonmutation","rotation")
MODES=("experimental_expanded_256","experimental_expanded_256_progression")
INDICES=(149,150,254,255)

@dataclass(frozen=True)
class Result:
 structural: bool; complete: bool; publication: bool; errors: tuple[str,...]

def validate(data: Mapping[str,Any], root: Path|None=None)->Result:
 e=[]
 if data.get("schema")!="vvfp.vv345_runtime_coverage_matrix" or data.get("version")!=1:e.append("schema mismatch")
 if data.get("source_commit")!=SOURCE_COMMIT:e.append("source commit mismatch")
 flags=data.get("flags")
 if not isinstance(flags,Mapping) or set(flags)!={"enabled","native_emission","runtime_go","player_go","publication"} or any(v is not False for v in flags.values()):e.append("all flags must remain false")
 if tuple(data.get("required_scenarios",()))!=SCENARIOS:e.append("scenario matrix mismatch")
 if tuple(data.get("save_scenarios",()))!=SAVE_SCENARIOS:e.append("save scenario matrix mismatch")
 if tuple(data.get("late_record_indices",()))!=INDICES:e.append("late-record boundary mismatch")
 cat=data.get("catalog_visible")
 if not isinstance(cat,Mapping) or set(cat)!=set(GAMES):e.append("catalog games mismatch")
 else:
  for g in GAMES:
   if tuple(cat[g])!=CATALOG[g] or len(cat[g])!=len(set(cat[g])):e.append(f"{g} catalog IDs missing, duplicate, or reordered")
 modes=data.get("expanded_modes")
 if not isinstance(modes,Mapping) or set(modes)!=set(GAMES) or any(tuple(modes[g])!=MODES for g in GAMES):e.append("expanded mode matrix mismatch")
 inputs=data.get("required_inputs",{})
 if inputs.get("status")!="missing":e.append("checked-in inputs must remain missing")
 if inputs.get("expanded_256_save_with_indices")!=list(INDICES) or inputs.get("rotation_generations_per_game")!=3:e.append("save input requirements mismatch")
 existing=data.get("existing_evidence",{})
 if root is not None:
  for label,rel in existing.items():
   if not isinstance(rel,str) or not (root/rel).is_file():e.append(f"existing evidence path missing: {label}")
 receipts=data.get("receipts")
 complete=isinstance(receipts,list) and len(receipts)==sum(len(v) for v in CATALOG.values())*len(SCENARIOS)+len(GAMES)*len(MODES)*len(SAVE_SCENARIOS)
 if not isinstance(receipts,list) or receipts:e.append("checked-in receipts must be empty")
 return Result(not any(x.startswith(("schema","source","all flags","catalog games","expanded mode")) for x in e),complete and not e,False,tuple(e))

def load(path:Path):return json.loads(path.read_text(encoding="utf-8"))
