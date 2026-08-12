#!/usr/bin/env python3
"""Evaluate Wave 22 progression without fabricating human acceptance.

Read-only gate chain: exact Wave 21 import -> CORE_UAT -> STANDALONE_MAC_UAT
-> R22 readiness. A plain SIGNED string is insufficient: current evidence,
independent actor metadata and defect state must also be internally consistent.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EXPECTED_VERSION = "0.5.5a1"
EXPECTED_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
CORE_IDS = ("CORE-007", "CORE-008", "CORE-009")
MAC_IDS = ("MAC-001", "MAC-002", "MAC-003")
ALL_IDS = (*CORE_IDS, *MAC_IDS)
ALLOWED_STATUS = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
ALLOWED_SEVERITY = {"P0", "P1", "P2", "P3"}
ALLOWED_DEFECT_STATUS = {"OPEN", "VERIFIED"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def defect_counts(status: dict, problems: list[str]) -> dict:
    expected = {"open_p0": 0, "open_p1": 0, "open_p2": 0, "open_p3": 0}
    records = status.get("defect_records", [])
    if not isinstance(records, list):
        problems.append("defect_records must be a list")
        return expected
    seen: set[str] = set()
    for defect in records:
        if not isinstance(defect, dict):
            problems.append("invalid defect record")
            continue
        defect_id = str(defect.get("id") or "").strip()
        severity = defect.get("severity")
        state = defect.get("status")
        scenario_id = defect.get("scenario_id")
        if not defect_id or defect_id in seen:
            problems.append(f"invalid/duplicate defect id: {defect_id or '<missing>'}")
            continue
        seen.add(defect_id)
        if severity not in ALLOWED_SEVERITY:
            problems.append(f"invalid defect severity for {defect_id}: {severity}")
        if state not in ALLOWED_DEFECT_STATUS:
            problems.append(f"invalid defect status for {defect_id}: {state}")
        if scenario_id not in ALL_IDS:
            problems.append(f"invalid defect scenario for {defect_id}: {scenario_id}")
        if state == "OPEN" and severity in ALLOWED_SEVERITY:
            expected[f"open_{severity.lower()}"] += 1
        if state == "VERIFIED":
            if not str(defect.get("resolution") or "").strip() or not str(defect.get("retest_evidence_ref") or "").strip():
                problems.append(f"verified defect lacks resolution/retest evidence: {defect_id}")

    declared = status.get("defects", {})
    for key, value in expected.items():
        try:
            declared_value = int(declared.get(key, 0) or 0)
        except (TypeError, ValueError):
            problems.append(f"invalid defect counter: {key}")
            continue
        if declared_value != value:
            problems.append(f"defect counter drift for {key}: declared={declared_value} actual={value}")
    return expected


def signature_valid(
    *,
    profile: str,
    ids: tuple[str, ...],
    signoff: dict,
    scenarios: dict[str, dict],
    defects: dict,
    problems: list[str],
) -> bool:
    key = "core_uat" if profile == "core" else "standalone_mac_uat"
    sig_key = f"{key}_signature"
    declared = signoff.get(key, "NOT_SIGNED")
    if declared != "SIGNED":
        return False
    signature = signoff.get(sig_key)
    if not isinstance(signature, dict):
        problems.append(f"{key} says SIGNED but structured signature is missing")
        return False

    actor = str(signature.get("actor") or "").strip()
    signed_at = str(signature.get("signed_at_utc") or "").strip()
    if not actor or not signed_at:
        problems.append(f"{key} signature lacks actor/timestamp")
        return False

    operators = {str(scenarios[sid].get("operator") or "").strip() for sid in ids}
    operators.discard("")
    if actor in operators:
        problems.append(f"{key} signer is not independent from scenario operator")

    evidence = signature.get("scenario_evidence")
    expected_evidence = {sid: scenarios[sid].get("evidence_ref") for sid in ids}
    if evidence != expected_evidence:
        problems.append(f"{key} signature evidence no longer matches current scenario evidence")

    residual = int(defects.get("open_p2", 0)) + int(defects.get("open_p3", 0))
    try:
        signed_residual = int(signature.get("residual_p2_p3", 0) or 0)
    except (TypeError, ValueError):
        signed_residual = -1
    if signed_residual != residual:
        problems.append(f"{key} signature residual P2/P3 count is stale")
    if residual and not str(signature.get("risk_acceptance_rationale") or "").strip():
        problems.append(f"{key} signature lacks P2/P3 risk acceptance rationale")

    return not any(p.startswith(key) for p in problems)


def evaluate(provenance_path: Path, status_path: Path, app_path: Path) -> dict:
    problems: list[str] = []
    source = "MISSING"
    if provenance_path.is_file():
        provenance = read_json(provenance_path)
        if (provenance.get("sha256") == EXPECTED_SHA256 and provenance.get("version") == EXPECTED_VERSION
                and provenance.get("zip_crc") == "PASS" and app_path.is_dir()):
            source = "PASS"
        else:
            source = "INVALID"
            problems.append("Wave 21 provenance/app does not match certified baseline")

    scenario_state = {sid: "NOT_RUN" for sid in ALL_IDS}
    scenario_items = {sid: {"id": sid, "status": "NOT_RUN"} for sid in ALL_IDS}
    signoff: dict = {"core_uat": "NOT_SIGNED", "standalone_mac_uat": "NOT_SIGNED"}
    defects = {"open_p0": 0, "open_p1": 0, "open_p2": 0, "open_p3": 0}
    r22 = "PHYSICALLY_UNBOUND"
    live = "BLOCKED"

    if status_path.is_file():
        status = read_json(status_path)
        baseline = status.get("baseline", {})
        if baseline.get("version") != EXPECTED_VERSION or baseline.get("sha256") != EXPECTED_SHA256:
            problems.append("UAT status is not bound to certified Wave 21 baseline")

        seen: set[str] = set()
        for item in status.get("scenarios", []):
            if not isinstance(item, dict):
                problems.append("invalid scenario status entry")
                continue
            sid, state = item.get("id"), item.get("status")
            if sid not in scenario_state:
                problems.append(f"unknown scenario id: {sid}")
                continue
            if sid in seen:
                problems.append(f"duplicate scenario id: {sid}")
                continue
            if state not in ALLOWED_STATUS:
                problems.append(f"invalid scenario state for {sid}: {state}")
                continue
            seen.add(sid)
            scenario_state[sid] = state
            scenario_items[sid] = item
            if state == "PASS":
                for field in ("evidence_ref", "operator_note", "operator", "recorded_at_utc"):
                    if not str(item.get(field) or "").strip():
                        problems.append(f"PASS scenario {sid} lacks {field}")
        missing = sorted(set(ALL_IDS) - seen)
        if missing:
            problems.append(f"missing scenario entries: {', '.join(missing)}")

        defects = defect_counts(status, problems)
        signoff = status.get("signoff", {}) if isinstance(status.get("signoff", {}), dict) else {}
        external = status.get("external_gates", {})
        r22 = external.get("r22", r22)
        live = external.get("live_providers", live)

    if r22 != "PHYSICALLY_UNBOUND": problems.append("R22 must remain PHYSICALLY_UNBOUND during Wave 22")
    if live != "BLOCKED": problems.append("live providers must remain BLOCKED during Wave 22")

    critical_clear = defects["open_p0"] == 0 and defects["open_p1"] == 0
    core_scenarios_pass = all(scenario_state[s] == "PASS" for s in CORE_IDS)
    mac_scenarios_pass = all(scenario_state[s] == "PASS" for s in MAC_IDS)
    core_signature_ok = signature_valid(profile="core", ids=CORE_IDS, signoff=signoff, scenarios=scenario_items, defects=defects, problems=problems) if signoff.get("core_uat") == "SIGNED" else False
    mac_signature_ok = signature_valid(profile="mac", ids=MAC_IDS, signoff=signoff, scenarios=scenario_items, defects=defects, problems=problems) if signoff.get("standalone_mac_uat") == "SIGNED" else False

    core = "PASS" if core_scenarios_pass and core_signature_ok and critical_clear else "PENDING"
    mac = "PASS" if mac_scenarios_pass and mac_signature_ok and critical_clear and core == "PASS" else "PENDING"

    if problems:
        next_gate, overall = "CONTROL_POLICY_REPAIR", "BLOCKED"
    elif source != "PASS":
        next_gate, overall = "IMPORT_EXACT_WAVE21", "PENDING"
    elif core != "PASS":
        next_gate, overall = "CORE_UAT", "PENDING"
    elif mac != "PASS":
        next_gate, overall = "STANDALONE_MAC_UAT", "PENDING"
    else:
        next_gate, overall = "BINARIO_R22_UAT", "WAVE22_GATE_PASSED"

    return {
        "schema": "binario.marketing.wave22.gate-evaluation.v2", "overall": overall,
        "next_gate": next_gate, "source_import": source,
        "core_uat": {"state": core, "signoff": signoff.get("core_uat", "NOT_SIGNED"), "signature_valid": core_signature_ok,
                     "scenarios": {s: scenario_state[s] for s in CORE_IDS}},
        "standalone_mac_uat": {"state": mac, "signoff": signoff.get("standalone_mac_uat", "NOT_SIGNED"), "signature_valid": mac_signature_ok,
                               "scenarios": {s: scenario_state[s] for s in MAC_IDS}},
        "critical_defects_clear": critical_clear, "defects": defects,
        "external_gates": {"r22": r22, "live_providers": live}, "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate current Wave 22 gate")
    parser.add_argument("--provenance", type=Path, default=Path("provenance/WAVE21_IMPORT.json"))
    parser.add_argument("--status", type=Path, default=Path("uat-evidence/WAVE22_UAT_STATUS.json"))
    parser.add_argument("--app", type=Path, default=Path("app"))
    args = parser.parse_args()
    try:
        result = evaluate(args.provenance, args.status, args.app)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"overall": "BLOCKED", "next_gate": "CONTROL_POLICY_REPAIR", "error": str(exc)}, indent=2)); return 3
    print(json.dumps(result, indent=2, sort_keys=True)); return 3 if result["overall"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
