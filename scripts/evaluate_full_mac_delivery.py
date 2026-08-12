#!/usr/bin/env python3
"""Report whether Binario Marketing is actually ready to install/use on the target Mac.

This intentionally distinguishes the Wave 22 control kit from the product itself.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


payload_audit = load_module("full_payload_audit", "scripts/audit_full_app_payload.py")
bundle_audit = load_module("full_bundle_audit", "scripts/audit_full_mac_bundle.py")
gate_eval = load_module("wave22_gate_eval", "scripts/evaluate_wave22_gate.py")


def evaluate(
    app_source: Path,
    provenance: Path,
    bundle: Path,
    source_audit_json: Path,
    uat_status: Path,
) -> dict:
    source_present = app_source.is_dir() and provenance.is_file()
    source_result = payload_audit.audit(app_source, provenance) if source_present else {
        "status": "MISSING",
        "problems": ["exact Wave 21 App13 source payload is not mounted"],
    }

    bundle_present = bundle.is_dir()
    bundle_result = bundle_audit.audit(bundle, source_audit_json if source_audit_json.is_file() else None) if bundle_present else {
        "status": "MISSING",
        "problems": ["FULL MAC .app bundle has not been built"],
    }

    uat = gate_eval.evaluate(provenance, uat_status, app_source)

    if source_result.get("status") == "MISSING":
        phase = "SOURCE_RECOVERY_REQUIRED"
        install_candidate = False
        daily_use_ready = False
    elif source_result.get("status") != "PASS":
        phase = "SOURCE_PAYLOAD_REPAIR_REQUIRED"
        install_candidate = False
        daily_use_ready = False
    elif bundle_result.get("status") == "MISSING":
        phase = "FULL_MAC_BUILD_REQUIRED"
        install_candidate = False
        daily_use_ready = False
    elif bundle_result.get("status") != "PASS":
        phase = "FULL_MAC_BUNDLE_REPAIR_REQUIRED"
        install_candidate = False
        daily_use_ready = False
    else:
        install_candidate = True
        if uat.get("overall") == "WAVE22_GATE_PASSED":
            phase = "TARGET_MAC_UAT_PASSED"
            daily_use_ready = True
        elif uat.get("next_gate") == "CORE_UAT":
            phase = "INSTALLABLE_CANDIDATE_CORE_UAT_REQUIRED"
            daily_use_ready = False
        elif uat.get("next_gate") == "STANDALONE_MAC_UAT":
            phase = "INSTALLABLE_CANDIDATE_MAC_UAT_REQUIRED"
            daily_use_ready = False
        else:
            phase = f"INSTALLABLE_CANDIDATE_{uat.get('next_gate', 'UAT_REQUIRED')}"
            daily_use_ready = False

    return {
        "schema": "binario.marketing.full-mac-delivery-readiness.v1",
        "phase": phase,
        "control_kit_is_product": False,
        "installable_full_app_candidate": install_candidate,
        "ready_for_daily_use_on_target_mac": daily_use_ready,
        "source_payload": source_result,
        "full_mac_bundle": bundle_result,
        "wave22_uat": uat,
        "definition_of_done": {
            "complete_frontend_and_all_certified_modules_embedded": True,
            "embedded_python_runtime": True,
            "normal_finder_launch_without_homebrew_or_node": True,
            "bundle_audit_pass": True,
            "core_uat_signed": True,
            "standalone_mac_uat_signed": True,
            "open_p0_p1": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate FULL MAC APP delivery readiness")
    parser.add_argument("--source", type=Path, default=Path("app"))
    parser.add_argument("--provenance", type=Path, default=Path("provenance/WAVE21_IMPORT.json"))
    parser.add_argument("--bundle", type=Path, default=Path("dist/full-mac/Binario Marketing IA.app"))
    parser.add_argument("--source-audit", type=Path, default=Path("dist/full-mac/PAYLOAD_AUDIT.json"))
    parser.add_argument("--uat-status", type=Path, default=Path("uat-evidence/WAVE22_UAT_STATUS.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = evaluate(args.source, args.provenance, args.bundle, args.source_audit, args.uat_status)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["ready_for_daily_use_on_target_mac"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
