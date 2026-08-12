#!/usr/bin/env python3
"""Audit the built Binario Marketing IA.app bundle before Target Mac UAT."""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import stat
from pathlib import Path

EXPECTED_BUNDLE_ID = "com.sistemabinario.marketingia"
EXPECTED_VERSION = "0.5.5a1"
EXPECTED_SOURCE_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
EXPECTED_PYTHON_VERSION = "3.12.13"
EXPECTED_PYTHON_RELEASE = "20260807"
EXPECTED_RUNTIME_SCHEMA = "binario.marketing.full-mac-python-runtime.v1"
EXPECTED_RUNTIME_BY_ARCH = {
    "arm64": {
        "source_asset": "cpython-3.12.13+20260807-aarch64-apple-darwin-install_only_stripped.tar.gz",
        "source_sha256": "25baa97c65b3f0aa90e21131b4f9e80aef8899e8144006db8a9d2c1ab9e807e3",
    },
    "x86_64": {
        "source_asset": "cpython-3.12.13+20260807-x86_64-apple-darwin-install_only_stripped.tar.gz",
        "source_sha256": "127053f1736f721e391ddb46f07585d05756e15bb8d757d3bbc0519738998ba1",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def audit(bundle: Path, source_audit: Path | None = None) -> dict:
    bundle = bundle.expanduser().resolve()
    problems: list[str] = []
    details: dict = {}

    if not bundle.is_dir() or bundle.suffix != ".app":
        return {"status": "BLOCKED", "problems": [f"invalid .app bundle: {bundle}"]}

    contents = bundle / "Contents"
    resources = contents / "Resources"
    macos = contents / "MacOS"
    plist_path = contents / "Info.plist"
    launcher = macos / "binario-marketing"
    app13 = resources / "App13"
    runtime = resources / "runtime"
    python_bin = runtime / "bin" / "python3"
    runtime_manifest = runtime / "FULL_MAC_PYTHON_RUNTIME.json"

    for required in (contents, resources, macos, app13, runtime):
        if not required.exists():
            problems.append(f"missing bundle path: {required.relative_to(bundle)}")

    if not plist_path.is_file():
        problems.append("missing Contents/Info.plist")
    else:
        try:
            with plist_path.open("rb") as f:
                plist = plistlib.load(f)
            details["bundle_identifier"] = plist.get("CFBundleIdentifier")
            details["bundle_version"] = plist.get("CFBundleShortVersionString")
            if plist.get("CFBundleIdentifier") != EXPECTED_BUNDLE_ID:
                problems.append("unexpected CFBundleIdentifier")
            if plist.get("CFBundleShortVersionString") != EXPECTED_VERSION:
                problems.append("unexpected CFBundleShortVersionString")
            if plist.get("CFBundleExecutable") != "binario-marketing":
                problems.append("unexpected CFBundleExecutable")
        except Exception as exc:
            problems.append(f"invalid Info.plist: {exc}")

    if not launcher.is_file():
        problems.append("missing native app launcher")
    elif not (launcher.stat().st_mode & stat.S_IXUSR):
        problems.append("native app launcher is not executable")
    else:
        launcher_text = launcher.read_text(encoding="utf-8", errors="replace")
        required_launcher_contract = (
            'PYTHON="$RUNTIME/bin/python3"',
            'export PATH="$RUNTIME/bin:/usr/bin:/bin"',
            "unset PYTHONHOME PYTHONPATH",
            "export PYTHONNOUSERSITE=1",
            "export PYTHONDONTWRITEBYTECODE=1",
        )
        for token in required_launcher_contract:
            if token not in launcher_text:
                problems.append(f"launcher isolation contract missing: {token}")
        for forbidden in ("command -v python3", "/usr/bin/python3", "/usr/bin/env python3"):
            if forbidden in launcher_text:
                problems.append(f"launcher may fall back to host Python: {forbidden}")

    if not python_bin.is_file():
        problems.append("embedded CPython bin/python3 missing")
    elif not (python_bin.stat().st_mode & stat.S_IXUSR):
        problems.append("embedded CPython bin/python3 is not executable")

    if not runtime_manifest.is_file():
        problems.append("embedded CPython runtime manifest missing")
    else:
        try:
            manifest = json.loads(runtime_manifest.read_text(encoding="utf-8"))
            details["runtime"] = manifest
            if manifest.get("schema") != EXPECTED_RUNTIME_SCHEMA:
                problems.append("embedded CPython runtime schema mismatch")
            if manifest.get("python_version") != EXPECTED_PYTHON_VERSION:
                problems.append("embedded CPython version mismatch")
            if manifest.get("release") != EXPECTED_PYTHON_RELEASE:
                problems.append("embedded CPython release mismatch")
            arch = manifest.get("architecture")
            expected_runtime = EXPECTED_RUNTIME_BY_ARCH.get(arch)
            if expected_runtime is None:
                problems.append(f"unsupported embedded CPython architecture: {arch}")
            else:
                if manifest.get("source_asset") != expected_runtime["source_asset"]:
                    problems.append("embedded CPython source asset mismatch")
                if manifest.get("source_sha256") != expected_runtime["source_sha256"]:
                    problems.append("embedded CPython source SHA256 mismatch")
            if manifest.get("upstream") != "astral-sh/python-build-standalone":
                problems.append("embedded CPython upstream mismatch")
        except Exception as exc:
            problems.append(f"invalid embedded CPython runtime manifest: {exc}")

    runners = list(app13.rglob("run_app13_uat_kit.sh")) if app13.is_dir() else []
    installers = []
    if app13.is_dir():
        installers.extend(app13.rglob("install_app13_uat_kit_macos.sh"))
        installers.extend(app13.rglob("install_app13_uat_operator_macos.sh"))
    if not runners:
        problems.append("certified App13 runtime runner missing inside bundle")
    if not installers:
        problems.append("certified App13 macOS installer missing inside bundle")

    app13_files = [p for p in app13.rglob("*") if p.is_file()] if app13.is_dir() else []
    details["embedded_app13_files"] = len(app13_files)
    if len(app13_files) < 437:
        problems.append(f"embedded App13 looks incomplete: {len(app13_files)} files")

    if source_audit:
        if not source_audit.is_file():
            problems.append(f"source audit missing: {source_audit}")
        else:
            try:
                source = json.loads(source_audit.read_text(encoding="utf-8"))
                details["source_audit_status"] = source.get("status")
                if source.get("status") != "PASS":
                    problems.append("source payload audit is not PASS")
                baseline = source.get("baseline", {})
                if baseline.get("version") != EXPECTED_VERSION:
                    problems.append("source audit version mismatch")
                if baseline.get("sha256") != EXPECTED_SOURCE_SHA256:
                    problems.append("source audit SHA mismatch")
                if source.get("file_count") != len(app13_files):
                    problems.append(
                        f"bundle source copy count differs from audited payload: {len(app13_files)} != {source.get('file_count')}"
                    )
            except Exception as exc:
                problems.append(f"invalid source audit: {exc}")

    details["launcher_sha256"] = sha256(launcher) if launcher.is_file() else None
    details["python_sha256"] = sha256(python_bin) if python_bin.is_file() else None
    details["app13_runner_count"] = len(runners)
    details["app13_installer_count"] = len(installers)

    return {
        "schema": "binario.marketing.full-mac-bundle-audit.v1",
        "status": "PASS" if not problems else "BLOCKED",
        "bundle": str(bundle),
        "baseline": {"version": EXPECTED_VERSION, "sha256": EXPECTED_SOURCE_SHA256},
        "details": details,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Binario Marketing FULL MAC APP bundle")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--source-audit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.bundle, args.source_audit)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
