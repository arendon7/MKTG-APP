#!/usr/bin/env python3
"""Verify that Wave 22 control-plane files agree with the certified Wave 21 baseline.

The JSON baseline is the canonical source of truth. This guard rejects drift in the
strict importer and the manual UAT scenario catalog before a Mac build/UAT run.
Stdlib-only by design so it can run in CI and on a clean target Mac.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_PRODUCT = "Binario Marketing & Growth IA — App13"
EXPECTED_WAVE = 21
EXPECTED_VERSION = "0.5.5a1"
EXPECTED_RELEASE_FILE = "BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip"
EXPECTED_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
EXPECTED_MODE = "APP13_INTERNAL_BOUND_R22_UNBOUND"
EXPECTED_CORE_IDS = {"CORE-007", "CORE-008", "CORE-009"}
EXPECTED_MAC_IDS = {"MAC-001", "MAC-002", "MAC-003"}


class ContractError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"required contract file missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"top-level JSON object required: {path}")
    return value


def _require(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ContractError(f"{label}: expected {expected!r}, got {actual!r}")


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ContractError(f"{label}: lowercase 64-hex SHA-256 required")
    return value


def _load_importer(path: Path):
    if not path.is_file():
        raise ContractError(f"strict importer missing: {path}")
    spec = importlib.util.spec_from_file_location("wave21_import_guard", path)
    if spec is None or spec.loader is None:
        raise ContractError(f"cannot load strict importer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    baseline_path = repo_root / "docs" / "BASELINE_WAVE21.json"
    scenarios_path = repo_root / "docs" / "WAVE22_UAT_SCENARIOS.json"
    importer_path = repo_root / "scripts" / "import_wave21_release.py"

    baseline = _load_json(baseline_path)
    _require(baseline.get("product"), EXPECTED_PRODUCT, "baseline.product")
    _require(baseline.get("wave"), EXPECTED_WAVE, "baseline.wave")
    _require(baseline.get("version"), EXPECTED_VERSION, "baseline.version")
    _require(baseline.get("release_file"), EXPECTED_RELEASE_FILE, "baseline.release_file")
    sha = _require_sha(baseline.get("sha256"), "baseline.sha256")
    _require(sha, EXPECTED_SHA256, "baseline.sha256")
    _require(baseline.get("integration_mode"), EXPECTED_MODE, "baseline.integration_mode")

    certification = baseline.get("certification")
    if not isinstance(certification, dict):
        raise ContractError("baseline.certification object required")
    for key, expected in {
        "tests_passed": 472,
        "tests_total": 472,
        "modules_passed": 115,
        "modules_total": 115,
        "manifest_passed": 437,
        "manifest_total": 437,
        "engineering_acceptance": "18/18 PASS",
        "ux_engineering_audit": "19/19 PASS",
        "core_uat_preparation": "3/3 READY",
        "release_health_gate_static": "PASS",
        "release_health_gate_isolated_boot": "PASS",
    }.items():
        _require(certification.get(key), expected, f"baseline.certification.{key}")

    gates = baseline.get("external_gates")
    if not isinstance(gates, dict):
        raise ContractError("baseline.external_gates object required")
    for key, expected in {
        "human_core_uat": "NOT_SIGNED",
        "target_mac_uat": "NOT_SIGNED",
        "r22": "PHYSICALLY_UNBOUND",
        "live_provider_uat": "BLOCKED_UNTIL_GOVERNED_REAL_ACCOUNT",
        "production_signoff": "BLOCKED_UNTIL_HUMAN_UAT",
    }.items():
        _require(gates.get(key), expected, f"baseline.external_gates.{key}")

    policy = baseline.get("wave22_policy")
    if not isinstance(policy, dict):
        raise ContractError("baseline.wave22_policy object required")
    _require(policy.get("feature_freeze"), True, "baseline.wave22_policy.feature_freeze")
    forbidden = policy.get("forbidden_without_new_gate")
    if not isinstance(forbidden, list):
        raise ContractError("baseline.wave22_policy.forbidden_without_new_gate list required")
    for required in (
        "large new features",
        "R22 physical binding",
        "live provider activation",
        "fabricated human UAT evidence or sign-off",
    ):
        if required not in forbidden:
            raise ContractError(f"missing Wave 22 forbidden action: {required}")

    importer = _load_importer(importer_path)
    _require(getattr(importer, "EXPECTED_NAME", None), baseline["release_file"], "importer.EXPECTED_NAME")
    _require(getattr(importer, "EXPECTED_SHA256", None), baseline["sha256"], "importer.EXPECTED_SHA256")
    _require(getattr(importer, "EXPECTED_VERSION", None), baseline["version"], "importer.EXPECTED_VERSION")

    scenarios = _load_json(scenarios_path)
    _require(scenarios.get("baseline_version"), baseline["version"], "scenarios.baseline_version")
    _require(scenarios.get("baseline_sha256"), baseline["sha256"], "scenarios.baseline_sha256")
    profiles = scenarios.get("profiles")
    if not isinstance(profiles, dict):
        raise ContractError("scenarios.profiles object required")

    core = profiles.get("CORE_UAT")
    mac = profiles.get("STANDALONE_MAC_UAT")
    if not isinstance(core, list) or not isinstance(mac, list):
        raise ContractError("CORE_UAT and STANDALONE_MAC_UAT scenario lists required")
    core_ids = {item.get("id") for item in core if isinstance(item, dict)}
    mac_ids = {item.get("id") for item in mac if isinstance(item, dict)}
    _require(core_ids, EXPECTED_CORE_IDS, "CORE_UAT scenario IDs")
    _require(mac_ids, EXPECTED_MAC_IDS, "STANDALONE_MAC_UAT scenario IDs")
    for profile_name, items in (("CORE_UAT", core), ("STANDALONE_MAC_UAT", mac)):
        for item in items:
            if not isinstance(item, dict):
                raise ContractError(f"{profile_name} contains a non-object scenario")
            _require(item.get("mode"), "MANUAL_REQUIRED", f"{item.get('id', profile_name)}.mode")

    global_gate = scenarios.get("global_gate")
    if not isinstance(global_gate, dict):
        raise ContractError("scenarios.global_gate object required")
    _require(global_gate.get("p0_p1_open"), 0, "scenarios.global_gate.p0_p1_open")
    _require(global_gate.get("independent_second_actor_signoff"), True, "scenarios.global_gate.independent_second_actor_signoff")
    _require(global_gate.get("r22_expected_state"), gates["r22"], "scenarios.global_gate.r22_expected_state")
    _require(global_gate.get("live_provider_expected_state"), "BLOCKED", "scenarios.global_gate.live_provider_expected_state")

    return {
        "status": "PASS",
        "product": baseline["product"],
        "wave": baseline["wave"],
        "version": baseline["version"],
        "release_file": baseline["release_file"],
        "release_sha256": baseline["sha256"],
        "integration_mode": baseline["integration_mode"],
        "core_uat_scenarios": sorted(core_ids),
        "standalone_mac_uat_scenarios": sorted(mac_ids),
        "human_core_uat": gates["human_core_uat"],
        "target_mac_uat": gates["target_mac_uat"],
        "r22": gates["r22"],
        "live_provider_uat": gates["live_provider_uat"],
        "feature_freeze": policy["feature_freeze"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="print the verified contract as JSON")
    group.add_argument("--print-release-sha", action="store_true", help="print only the certified release SHA-256")
    group.add_argument("--print-version", action="store_true", help="print only the certified version")
    args = parser.parse_args(argv)
    try:
        result = verify(args.repo_root)
    except ContractError as exc:
        print(f"WAVE22 CONTRACT: FAIL: {exc}", file=sys.stderr)
        return 2

    if args.print_release_sha:
        print(result["release_sha256"])
    elif args.print_version:
        print(result["version"])
    elif args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "WAVE22 CONTRACT: PASS "
            f"version={result['version']} sha256={result['release_sha256']} "
            f"R22={result['r22']} CORE_UAT={result['human_core_uat']} MAC_UAT={result['target_mac_uat']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
