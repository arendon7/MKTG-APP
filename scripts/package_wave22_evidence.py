#!/usr/bin/env python3
"""Create an integrity-bound Wave 22 UAT evidence bundle.

This script never signs UAT. It packages already-produced human evidence only after
running the conservative evidence guard, and binds the bundle to the canonical
Wave 21 baseline plus the Wave 22 scenario catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = Path(__file__).resolve().with_name("wave22_evidence_guard.py")
DEFAULT_BASELINE = ROOT / "docs" / "BASELINE_WAVE21.json"
DEFAULT_SCENARIOS = ROOT / "docs" / "WAVE22_UAT_SCENARIOS.json"
ALLOWED_STATUS = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


def _load_guard():
    spec = importlib.util.spec_from_file_location("wave22_evidence_guard", GUARD_PATH)
    if not spec or not spec.loader:
        raise RuntimeError("unable to load evidence guard")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def known_scenario_ids(scenarios: dict) -> set[str]:
    ids: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            scenario_id = value.get("id")
            if isinstance(scenario_id, str):
                ids.add(scenario_id)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(scenarios)
    return ids


def validate_status(status: dict, scenarios: dict) -> None:
    known = known_scenario_ids(scenarios)
    if not known:
        raise ValueError("scenario catalog contains no scenario ids")

    results = status.get("scenarios")
    if not isinstance(results, list):
        raise ValueError("status JSON must contain a scenarios array")

    seen: set[str] = set()
    for entry in results:
        if not isinstance(entry, dict):
            raise ValueError("each scenario status must be an object")
        scenario_id = entry.get("id")
        state = entry.get("status")
        if scenario_id not in known:
            raise ValueError(f"unknown scenario id: {scenario_id}")
        if scenario_id in seen:
            raise ValueError(f"duplicate scenario id: {scenario_id}")
        if state not in ALLOWED_STATUS:
            raise ValueError(f"invalid status for {scenario_id}: {state}")
        seen.add(scenario_id)


def evidence_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    )


def package_evidence(
    evidence_dir: Path,
    output_zip: Path,
    baseline_path: Path = DEFAULT_BASELINE,
    scenarios_path: Path = DEFAULT_SCENARIOS,
    status_path: Path | None = None,
) -> dict:
    evidence_dir = evidence_dir.expanduser().resolve()
    output_zip = output_zip.expanduser().resolve()
    baseline_path = baseline_path.expanduser().resolve()
    scenarios_path = scenarios_path.expanduser().resolve()
    status_path = status_path.expanduser().resolve() if status_path else None

    if not evidence_dir.is_dir():
        raise ValueError(f"evidence directory not found: {evidence_dir}")
    if not baseline_path.is_file() or not scenarios_path.is_file():
        raise ValueError("baseline/scenario control files are required")
    if output_zip == evidence_dir or evidence_dir in output_zip.parents:
        raise ValueError("output ZIP must be outside the evidence directory")

    baseline = load_json(baseline_path)
    scenarios = load_json(scenarios_path)
    status = load_json(status_path) if status_path else None
    if status is not None:
        validate_status(status, scenarios)

    guard = _load_guard()
    guard_result = guard.inspect(evidence_dir)
    if guard_result.get("status") != "PASS":
        findings = guard_result.get("findings", [])
        raise ValueError(f"evidence guard blocked bundle: {findings}")

    files = evidence_files(evidence_dir)
    if not files:
        raise ValueError("evidence directory is empty")

    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema": "binario.marketing.wave22.evidence-bundle.v1",
        "generated_at_utc": generated_at,
        "authority": "EVIDENCE_ONLY_NOT_A_UAT_SIGNATURE",
        "baseline": {
            "version": baseline.get("version"),
            "sha256": baseline.get("sha256"),
            "integration_mode": baseline.get("integration_mode"),
        },
        "guard": {
            "status": guard_result.get("status"),
            "file_count": guard_result.get("file_count"),
        },
        "evidence": [
            {
                "path": path.relative_to(evidence_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
        "status_json_included": status is not None,
    }

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    if output_zip.exists():
        raise FileExistsError(output_zip)

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = path.relative_to(evidence_dir).as_posix()
            zf.write(path, f"evidence/{rel}")
        zf.write(baseline_path, "control/BASELINE_WAVE21.json")
        zf.write(scenarios_path, "control/WAVE22_UAT_SCENARIOS.json")
        if status_path:
            zf.write(status_path, "control/WAVE22_UAT_STATUS.json")
        zf.writestr(
            "control/EVIDENCE_GUARD.json",
            json.dumps(guard_result, indent=2, sort_keys=True) + "\n",
        )
        zf.writestr(
            "control/EVIDENCE_MANIFEST.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )

    bad = None
    with zipfile.ZipFile(output_zip, "r") as zf:
        bad = zf.testzip()
    if bad is not None:
        output_zip.unlink(missing_ok=True)
        raise ValueError(f"bundle ZIP CRC failed at {bad}")

    bundle_sha = sha256_file(output_zip)
    sidecar = output_zip.with_suffix(output_zip.suffix + ".sha256")
    sidecar.write_text(f"{bundle_sha}  {output_zip.name}\n", encoding="utf-8")

    return {
        "status": "PASS",
        "bundle": str(output_zip),
        "bundle_sha256": bundle_sha,
        "sha256_file": str(sidecar),
        "evidence_files": len(files),
        "baseline_version": baseline.get("version"),
        "baseline_sha256": baseline.get("sha256"),
        "human_uat_signed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Package Wave 22 UAT evidence")
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--status-json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or Path("uat-bundles") / f"WAVE22_UAT_EVIDENCE_{stamp}.zip"
    try:
        result = package_evidence(
            args.evidence_dir,
            output,
            status_path=args.status_json,
        )
    except (ValueError, FileNotFoundError, FileExistsError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
