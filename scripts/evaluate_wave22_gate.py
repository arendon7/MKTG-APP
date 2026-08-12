#!/usr/bin/env python3
"""Evaluate Wave 22 progression without fabricating human acceptance.

The evaluator is read-only. It reports the first real gate that remains unresolved:
exact Wave 21 import -> CORE_UAT -> STANDALONE_MAC_UAT -> R22_UAT readiness.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPECTED_VERSION = "0.5.5a1"
EXPECTED_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
CORE_IDS = ("CORE-007", "CORE-008", "CORE-009")
MAC_IDS = ("MAC-001", "MAC-002", "MAC-003")
ALLOWED_STATUS = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(
    provenance_path: Path,
    status_path: Path,
    app_path: Path,
) -> dict:
    problems: list[str] = []

    source = "MISSING"
    provenance = None
    if provenance_path.is_file():
        provenance = read_json(provenance_path)
        if (
            provenance.get("sha256") == EXPECTED_SHA256
            and provenance.get("version") == EXPECTED_VERSION
            and provenance.get("zip_crc") == "PASS"
            and app_path.is_dir()
        ):
            source = "PASS"
        else:
            source = "INVALID"
            problems.append("Wave 21 provenance/app does not match certified baseline")

    scenario_state = {scenario_id: "NOT_RUN" for scenario_id in (*CORE_IDS, *MAC_IDS)}
    core_signoff = "NOT_SIGNED"
    mac_signoff = "NOT_SIGNED"
    defects = {"open_p0": 0, "open_p1": 0, "open_p2": 0, "open_p3": 0}
    r22 = "PHYSICALLY_UNBOUND"
    live = "BLOCKED"

    if status_path.is_file():
        status = read_json(status_path)
        baseline = status.get("baseline", {})
        if baseline.get("version") != EXPECTED_VERSION or baseline.get("sha256") != EXPECTED_SHA256:
            problems.append("UAT status is not bound to certified Wave 21 baseline")

        seen = set()
        for item in status.get("scenarios", []):
            if not isinstance(item, dict):
                problems.append("invalid scenario status entry")
                continue
            scenario_id = item.get("id")
            state = item.get("status")
            if scenario_id not in scenario_state:
                problems.append(f"unknown scenario id: {scenario_id}")
                continue
            if scenario_id in seen:
                problems.append(f"duplicate scenario id: {scenario_id}")
                continue
            if state not in ALLOWED_STATUS:
                problems.append(f"invalid scenario state for {scenario_id}: {state}")
                continue
            scenario_state[scenario_id] = state
            seen.add(scenario_id)

        defects.update(status.get("defects", {}))
        signoff = status.get("signoff", {})
        core_signoff = signoff.get("core_uat", core_signoff)
        mac_signoff = signoff.get("standalone_mac_uat", mac_signoff)
        external = status.get("external_gates", {})
        r22 = external.get("r22", r22)
        live = external.get("live_providers", live)

    if r22 != "PHYSICALLY_UNBOUND":
        problems.append("R22 must remain PHYSICALLY_UNBOUND during Wave 22")
    if live != "BLOCKED":
        problems.append("live providers must remain BLOCKED during Wave 22")

    open_p0 = int(defects.get("open_p0", 0) or 0)
    open_p1 = int(defects.get("open_p1", 0) or 0)
    critical_clear = open_p0 == 0 and open_p1 == 0

    core_scenarios_pass = all(scenario_state[s] == "PASS" for s in CORE_IDS)
    mac_scenarios_pass = all(scenario_state[s] == "PASS" for s in MAC_IDS)
    core = "PASS" if core_scenarios_pass and core_signoff == "SIGNED" and critical_clear else "PENDING"
    mac = "PASS" if mac_scenarios_pass and mac_signoff == "SIGNED" and critical_clear else "PENDING"

    if problems:
        next_gate = "CONTROL_POLICY_REPAIR"
        overall = "BLOCKED"
    elif source != "PASS":
        next_gate = "IMPORT_EXACT_WAVE21"
        overall = "PENDING"
    elif core != "PASS":
        next_gate = "CORE_UAT"
        overall = "PENDING"
    elif mac != "PASS":
        next_gate = "STANDALONE_MAC_UAT"
        overall = "PENDING"
    else:
        next_gate = "BINARIO_R22_UAT"
        overall = "WAVE22_GATE_PASSED"

    return {
        "schema": "binario.marketing.wave22.gate-evaluation.v1",
        "overall": overall,
        "next_gate": next_gate,
        "source_import": source,
        "core_uat": {
            "state": core,
            "signoff": core_signoff,
            "scenarios": {s: scenario_state[s] for s in CORE_IDS},
        },
        "standalone_mac_uat": {
            "state": mac,
            "signoff": mac_signoff,
            "scenarios": {s: scenario_state[s] for s in MAC_IDS},
        },
        "critical_defects_clear": critical_clear,
        "defects": defects,
        "external_gates": {"r22": r22, "live_providers": live},
        "problems": problems,
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
        print(json.dumps({"overall": "BLOCKED", "next_gate": "CONTROL_POLICY_REPAIR", "error": str(exc)}, indent=2))
        return 3

    print(json.dumps(result, indent=2, sort_keys=True))
    return 3 if result["overall"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
