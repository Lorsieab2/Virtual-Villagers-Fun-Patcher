import copy, importlib.util, json, re, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("full256",ROOT/"scripts"/"validate_vv3_full_capacity_save_contract.py")
GATE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(GATE)


def _resolve(schema, root):
    reference = schema.get("$ref")
    if reference is None:
        return schema
    current = root
    for part in reference.removeprefix("#/").split("/"):
        current = current[part]
    return current


def _matches_type(value, expected):
    return {
        "null": value is None,
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": type(value) is int,
        "boolean": type(value) is bool,
    }.get(expected, False)


def _validate_schema(value, schema, root):
    schema = _resolve(schema, root)
    if "const" in schema and value != schema["const"]:
        raise ValueError("const mismatch")
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(_matches_type(value, item) for item in expected_type):
            raise ValueError("type mismatch")
    elif expected_type is not None and not _matches_type(value, expected_type):
        raise ValueError("type mismatch")
    if expected_type == "object":
        required = set(schema.get("required", []))
        if not required.issubset(value):
            raise ValueError("required field missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ValueError("extra field")
        for key, child in properties.items():
            if key in value:
                _validate_schema(value[key], child, root)
    elif expected_type == "array":
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            raise ValueError("array length mismatch")
        for item in value:
            _validate_schema(item, schema["items"], root)
    elif expected_type == "string":
        if len(value) < schema.get("minLength", 0):
            raise ValueError("string too short")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise ValueError("pattern mismatch")

class FullCapacitySaveContractTests(unittest.TestCase):
    def setUp(self):self.doc=copy.deepcopy(GATE.load())
    def test_contract_valid_stop(self):
        r=GATE.validate(self.doc);self.assertTrue(r["contract_valid"]);self.assertEqual("STOP",r["status"]);self.assertFalse(r["publication_ready"])
    def test_exact_functions(self):self.assertEqual(GATE.FUNCTIONS,tuple((x["id"],x["ea"]) for x in self.doc["native_evidence"]["stock_functions"]))
    def test_native_rows_empty(self):self.assertTrue(all(x["raw_bytes"] is None and x["function_bounds"] is None and x["complete_xrefs"] is None and x["artifact_refs"]==[] for x in self.doc["native_evidence"]["stock_functions"]))
    def test_candidate_bytes_null(self):
        n=self.doc["native_evidence"];self.assertIsNone(n["candidate_section_bytes"]);self.assertIsNone(n["candidate_hook_bytes"]);self.assertIsNone(n["candidate_final_bytes"])
    def test_geometry(self):
        f=self.doc["reference_findings"];self.assertEqual(("0x11C","0x7864","0x19464","0x1A4B4","0x1A4C0"),(f["record_size"],f["records_offset"],f["tail_offset"],f["expanded_body_size"],f["expanded_file_size"]))
    def test_record_256_lands_at_tail(self):self.assertEqual(int("7864",16)+256*int("11C",16),int("19464",16))
    def test_logical_boundary(self):self.assertEqual((0,255,[256,257,258,259]),(self.doc["reference_findings"]["logical_first"],self.doc["reference_findings"]["logical_last"],self.doc["reference_findings"]["padding_indices"]))
    def test_conditional_terminator_required(self):self.assertIn("write terminator only when count is less than 256",self.doc["required_semantics"]["writer"])
    def test_reader_exact_256_bound_required(self):self.assertIn("stop successfully after exactly 256 records without reading tail",self.doc["required_semantics"]["reader"])
    def test_padding_excluded_both_directions(self):
        self.assertIn("never serialize padding 256 through 259",self.doc["required_semantics"]["writer"]);self.assertIn("never construct or expose padding 256 through 259",self.doc["required_semantics"]["reader"])
    def test_atomic_verify_before_replace(self):self.assertLess(self.doc["required_semantics"]["atomic_writer"].index("verify exact size and authenticated integrity transform"),self.doc["required_semantics"]["atomic_writer"].index("atomically replace destination only after verification"))
    def test_fault_matrix_exact_pending(self):self.assertEqual(GATE.FAULTS,tuple(x["id"] for x in self.doc["runtime_fault_matrix"]));self.assertTrue(all(x["status"]=="pending" for x in self.doc["runtime_fault_matrix"]))
    def test_reference_not_promoted(self):self.assertEqual("D350_D351_unverified_reference_only",self.doc["reference_findings"]["classification"])
    def test_c342_bound(self):self.assertEqual(GATE.C342,self.doc["bindings"]["c342_dependency"])
    def test_enable_rejected(self):
        self.doc["enabled"]=True
        with self.assertRaises(GATE.ContractError):GATE.validate(self.doc)
    def test_runtime_go_rejected(self):
        self.doc["decision"]["runtime_go"]=True
        with self.assertRaises(GATE.ContractError):GATE.validate(self.doc)
    def test_populated_bytes_rejected(self):
        self.doc["native_evidence"]["stock_functions"][0]["raw_bytes"]="90"
        with self.assertRaises(GATE.ContractError):GATE.validate(self.doc)
    def test_missing_padding_rejected(self):
        self.doc["reference_findings"]["padding_indices"]=[256,257,258]
        with self.assertRaises(GATE.ContractError):GATE.validate(self.doc)
    def test_unconditional_terminator_rejected(self):
        self.doc["required_semantics"]["writer"].remove("write terminator only when count is less than 256")
        with self.assertRaises(GATE.ContractError):GATE.validate(self.doc)
    def test_atomic_replace_order_rejected(self):
        rows=self.doc["required_semantics"]["atomic_writer"];rows[rows.index("atomically replace destination only after verification")],rows[rows.index("verify exact size and authenticated integrity transform")]=rows[rows.index("verify exact size and authenticated integrity transform")],rows[rows.index("atomically replace destination only after verification")]
        with self.assertRaises(GATE.ContractError):GATE.validate(self.doc)
    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"x.json";p.write_text('{"a":1,"a":2}',encoding="utf-8")
            with self.assertRaises(GATE.ContractError):GATE.load(p)
    def test_schema_parses_and_accepts_checked_in_contract(self):
        schema=json.loads((ROOT/"data"/"vv3_expanded_256_full_capacity_save_contract.schema.json").read_text(encoding="utf-8"))
        _validate_schema(self.doc, schema, schema)

    def test_schema_rejects_each_required_nested_field_removal(self):
        schema=json.loads((ROOT/"data"/"vv3_expanded_256_full_capacity_save_contract.schema.json").read_text(encoding="utf-8"))
        locations=[
            (("reference_findings",), schema["$defs"]["reference_findings"]),
            (("required_semantics",), schema["$defs"]["required_semantics"]),
            (("native_evidence",), schema["$defs"]["native_evidence"]),
            (("native_evidence", "stock_functions", 0), schema["$defs"]["native_function"]),
        ]
        for path, definition in locations:
            for key in definition["required"]:
                altered=copy.deepcopy(self.doc)
                target=altered
                for part in path:
                    target=target[part]
                del target[key]
                with self.assertRaises(ValueError, msg=f"missing {path}.{key}"):
                    _validate_schema(altered, schema, schema)
            self.assertIs(False, definition["additionalProperties"], path)

    def test_schema_rejects_extra_key_at_each_nested_boundary(self):
        schema=json.loads((ROOT/"data"/"vv3_expanded_256_full_capacity_save_contract.schema.json").read_text(encoding="utf-8"))
        locations=[
            ((), schema),
            (("reference_findings",), schema["$defs"]["reference_findings"]),
            (("required_semantics",), schema["$defs"]["required_semantics"]),
            (("native_evidence",), schema["$defs"]["native_evidence"]),
            (("native_evidence", "stock_functions", 0), schema["$defs"]["native_function"]),
        ]
        for path, _definition in locations:
            altered=copy.deepcopy(self.doc)
            target=altered
            for part in path:
                target=target[part]
            target["__unexpected__"]=True
            with self.assertRaises(ValueError, msg=f"extra key at {path}"):
                _validate_schema(altered, schema, schema)
    def test_no_native_or_runtime_operations(self):
        s=(ROOT/"scripts"/"validate_vv3_full_capacity_save_contract.py").read_text(encoding="utf-8")
        for token in ("subprocess","Popen(","CreateProcess","emit_bytes","Savegame"):
            self.assertNotIn(token,s)

if __name__=="__main__":unittest.main()
