#!/usr/bin/env python3
"""Govern Wave 22 human UAT state without hand-editing JSON.

This CLI records scenario outcomes, defect lifecycle and independent sign-off while
preserving the certified Wave 21 baseline and Wave 22 external safety gates.
It never executes product/provider actions and never fabricates acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_VERSION = "0.5.5a1"
EXPECTED_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
CORE_IDS = ("CORE-007", "CORE-008", "CORE-009")
MAC_IDS = ("MAC-001", "MAC-002", "MAC-003")
ALL_IDS = (*CORE_IDS, *MAC_IDS)
RESULTS = {"PASS", "FAIL", "BLOCKED"}
SEVERITIES = {"P0", "P1", "P2", "P3"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def validate_baseline(state: dict) -> None:
    baseline = state.get("baseline", {})
    if baseline.get("version") != EXPECTED_VERSION or baseline.get("sha256") != EXPECTED_SHA256:
        raise ValueError("UAT state is not bound to the certified Wave 21 baseline")
    external = state.get("external_gates", {})
    if external.get("r22") != "PHYSICALLY_UNBOUND":
        raise ValueError("R22 must remain PHYSICALLY_UNBOUND in Wave 22")
    if external.get("live_providers") != "BLOCKED":
        raise ValueError("live providers must remain BLOCKED in Wave 22")


def normalize(state: dict) -> dict:
    validate_baseline(state)
    state.setdefault("events", [])
    state.setdefault("defect_records", [])
    state.setdefault("updated_at_utc", None)
    state.setdefault("signoff", {})
    state["signoff"].setdefault("core_uat", "NOT_SIGNED")
    state["signoff"].setdefault("standalone_mac_uat", "NOT_SIGNED")
    state["signoff"].setdefault("independent_second_actor", None)
    state["signoff"].setdefault("core_uat_signature", None)
    state["signoff"].setdefault("standalone_mac_uat_signature", None)
    for item in state.get("scenarios", []):
        item.setdefault("operator", None)
        item.setdefault("recorded_at_utc", None)
        item.setdefault("defect_id", None)
    recompute_defects(state)
    return state


def scenario_map(state: dict) -> dict[str, dict]:
    items = state.get("scenarios", [])
    result = {item.get("id"): item for item in items if isinstance(item, dict)}
    if set(result) != set(ALL_IDS):
        raise ValueError("UAT state must contain exactly CORE-007/008/009 and MAC-001/002/003")
    return result


def recompute_defects(state: dict) -> None:
    counts = {"open_p0": 0, "open_p1": 0, "open_p2": 0, "open_p3": 0}
    for defect in state.get("defect_records", []):
        if defect.get("status") == "OPEN":
            key = f"open_{str(defect.get('severity', '')).lower()}"
            if key in counts:
                counts[key] += 1
    state["defects"] = counts


def event(state: dict, kind: str, actor: str, **data: object) -> None:
    state.setdefault("events", []).append({"at_utc": now(), "kind": kind, "actor": actor, **data})
    state["updated_at_utc"] = state["events"][-1]["at_utc"]


def open_defect(state: dict, *, defect_id: str, severity: str, scenario_id: str, summary: str, actor: str) -> None:
    if severity not in SEVERITIES:
        raise ValueError("severity must be P0, P1, P2 or P3")
    if scenario_id not in ALL_IDS:
        raise ValueError("unknown scenario id")
    if any(d.get("id") == defect_id for d in state.get("defect_records", [])):
        raise ValueError(f"defect already exists: {defect_id}")
    record = {
        "id": defect_id,
        "severity": severity,
        "scenario_id": scenario_id,
        "summary": summary.strip(),
        "status": "OPEN",
        "opened_by": actor.strip(),
        "opened_at_utc": now(),
        "closed_by": None,
        "closed_at_utc": None,
        "resolution": None,
        "retest_evidence_ref": None,
    }
    if not record["id"].strip() or not record["summary"] or not record["opened_by"]:
        raise ValueError("defect id, summary and actor are required")
    state.setdefault("defect_records", []).append(record)
    recompute_defects(state)
    event(state, "DEFECT_OPENED", actor.strip(), defect_id=defect_id, severity=severity, scenario_id=scenario_id)


def close_defect(state: dict, *, defect_id: str, resolution: str, evidence_ref: str, actor: str) -> None:
    defect = next((d for d in state.get("defect_records", []) if d.get("id") == defect_id), None)
    if not defect:
        raise ValueError(f"unknown defect: {defect_id}")
    if defect.get("status") != "OPEN":
        raise ValueError(f"defect is not OPEN: {defect_id}")
    if not resolution.strip() or not evidence_ref.strip() or not actor.strip():
        raise ValueError("resolution, retest evidence and actor are required")
    defect.update({
        "status": "VERIFIED",
        "closed_by": actor.strip(),
        "closed_at_utc": now(),
        "resolution": resolution.strip(),
        "retest_evidence_ref": evidence_ref.strip(),
    })
    recompute_defects(state)
    event(state, "DEFECT_VERIFIED", actor.strip(), defect_id=defect_id)


def record_scenario(
    state: dict,
    *,
    scenario_id: str,
    result: str,
    evidence_ref: str,
    note: str,
    actor: str,
    defect_id: str | None = None,
) -> None:
    if result not in RESULTS:
        raise ValueError("result must be PASS, FAIL or BLOCKED")
    if not actor.strip() or not evidence_ref.strip() or not note.strip():
        raise ValueError("actor, evidence and operator note are required")
    scenarios = scenario_map(state)
    if scenario_id not in scenarios:
        raise ValueError("unknown scenario id")
    item = scenarios[scenario_id]
    if result in {"FAIL", "BLOCKED"}:
        if not defect_id:
            raise ValueError("FAIL/BLOCKED requires --defect-id for an existing OPEN defect")
        defect = next((d for d in state.get("defect_records", []) if d.get("id") == defect_id), None)
        if not defect or defect.get("status") != "OPEN" or defect.get("scenario_id") != scenario_id:
            raise ValueError("defect must exist, be OPEN and belong to this scenario")
    elif defect_id:
        raise ValueError("PASS must not be tied to an open defect")

    item.update({
        "status": result,
        "evidence_ref": evidence_ref.strip(),
        "operator_note": note.strip(),
        "operator": actor.strip(),
        "recorded_at_utc": now(),
        "defect_id": defect_id,
    })
    if scenario_id in CORE_IDS:
        state["signoff"]["core_uat"] = "NOT_SIGNED"
        state["signoff"]["core_uat_signature"] = None
    else:
        state["signoff"]["standalone_mac_uat"] = "NOT_SIGNED"
        state["signoff"]["standalone_mac_uat_signature"] = None
    event(state, "SCENARIO_RECORDED", actor.strip(), scenario_id=scenario_id, result=result, defect_id=defect_id)


def sign_profile(state: dict, *, profile: str, actor: str, rationale: str | None = None) -> None:
    scenarios = scenario_map(state)
    ids = CORE_IDS if profile == "core" else MAC_IDS
    label = "CORE_UAT" if profile == "core" else "STANDALONE_MAC_UAT"
    key = "core_uat" if profile == "core" else "standalone_mac_uat"
    signature_key = f"{key}_signature"

    incomplete = [sid for sid in ids if scenarios[sid].get("status") != "PASS"]
    if incomplete:
        raise ValueError(f"cannot sign {label}; scenarios not PASS: {', '.join(incomplete)}")
    if any(not str(scenarios[sid].get("evidence_ref") or "").strip() for sid in ids):
        raise ValueError(f"cannot sign {label}; every PASS requires evidence")

    defects = state.get("defects", {})
    if any(int(defects.get(k, 0) or 0) for k in ("open_p0", "open_p1")):
        raise ValueError(f"cannot sign {label} with open P0/P1 defects")
    residual = int(defects.get("open_p2", 0) or 0) + int(defects.get("open_p3", 0) or 0)
    if residual and not str(rationale or "").strip():
        raise ValueError(f"cannot sign {label} with open P2/P3 without explicit --rationale")

    operators = {str(scenarios[sid].get("operator") or "").strip() for sid in ids}
    operators.discard("")
    signer = actor.strip()
    if not signer:
        raise ValueError("signing actor is required")
    if signer in operators:
        raise ValueError("independent sign-off actor must differ from scenario operator(s)")

    signature = {
        "actor": signer,
        "signed_at_utc": now(),
        "scenario_evidence": {sid: scenarios[sid].get("evidence_ref") for sid in ids},
        "residual_p2_p3": residual,
        "risk_acceptance_rationale": str(rationale or "").strip() or None,
    }
    state["signoff"][key] = "SIGNED"
    state["signoff"][signature_key] = signature
    state["signoff"]["independent_second_actor"] = signer
    state["authority"] = "HUMAN_UAT_IN_PROGRESS" if profile == "core" else "HUMAN_UAT_SIGNED"
    event(state, "PROFILE_SIGNED", signer, profile=label, residual_p2_p3=residual)


def init_state(template: Path, output: Path) -> dict:
    if output.exists():
        return normalize(read_json(output))
    state = normalize(read_json(template))
    state["created_at_utc"] = now()
    event(state, "STATUS_INITIALIZED", "SYSTEM")
    atomic_write(output, state)
    return state


def load_state(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"status file not found: {path}; run init first")
    return normalize(read_json(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Govern Wave 22 UAT state")
    parser.add_argument("--status", type=Path, default=Path("uat-evidence/WAVE22_UAT_STATUS.json"))
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--template", type=Path, default=Path("docs/WAVE22_UAT_STATUS_TEMPLATE.json"))

    p_record = sub.add_parser("record")
    p_record.add_argument("scenario_id", choices=ALL_IDS)
    p_record.add_argument("result", choices=sorted(RESULTS))
    p_record.add_argument("--actor", required=True)
    p_record.add_argument("--evidence", required=True)
    p_record.add_argument("--note", required=True)
    p_record.add_argument("--defect-id")

    p_open = sub.add_parser("defect-open")
    p_open.add_argument("defect_id")
    p_open.add_argument("severity", choices=sorted(SEVERITIES))
    p_open.add_argument("scenario_id", choices=ALL_IDS)
    p_open.add_argument("--summary", required=True)
    p_open.add_argument("--actor", required=True)

    p_close = sub.add_parser("defect-verify")
    p_close.add_argument("defect_id")
    p_close.add_argument("--resolution", required=True)
    p_close.add_argument("--evidence", required=True)
    p_close.add_argument("--actor", required=True)

    p_sign = sub.add_parser("sign")
    p_sign.add_argument("profile", choices=("core", "mac"))
    p_sign.add_argument("--actor", required=True)
    p_sign.add_argument("--rationale")

    sub.add_parser("show")
    args = parser.parse_args()

    try:
        if args.command == "init":
            state = init_state(args.template, args.status)
        else:
            state = load_state(args.status)
            if args.command == "record":
                record_scenario(state, scenario_id=args.scenario_id, result=args.result, evidence_ref=args.evidence, note=args.note, actor=args.actor, defect_id=args.defect_id)
            elif args.command == "defect-open":
                open_defect(state, defect_id=args.defect_id, severity=args.severity, scenario_id=args.scenario_id, summary=args.summary, actor=args.actor)
            elif args.command == "defect-verify":
                close_defect(state, defect_id=args.defect_id, resolution=args.resolution, evidence_ref=args.evidence, actor=args.actor)
            elif args.command == "sign":
                sign_profile(state, profile=args.profile, actor=args.actor, rationale=args.rationale)
            elif args.command == "show":
                pass
            if args.command != "show":
                atomic_write(args.status, state)
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
