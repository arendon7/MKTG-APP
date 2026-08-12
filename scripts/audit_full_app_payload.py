#!/usr/bin/env python3
"""Audit the imported App13 payload before any FULL MAC APP build.

This is intentionally conservative. It does not infer that a partial tree is complete.
The exact certified Wave 21 provenance is mandatory, and the payload must expose the
native/UAT/runtime surfaces historically certified for App13.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path

EXPECTED_VERSION = "0.5.5a1"
EXPECTED_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
MIN_CERTIFIED_MANIFEST_ENTRIES = 437

REQUIRED_FILENAMES = {
    "run_app13_uat_kit.sh": "Mac/runtime launcher",
}
INSTALLER_ALTERNATIVES = {
    "install_app13_uat_kit_macos.sh",
    "install_app13_uat_operator_macos.sh",
}

SURFACE_TOKENS = {
    "campaign": ("campaign",),
    "content": ("content",),
    "crm": ("crm", "customer_360", "customer360"),
    "inbox": ("inbox", "handoff"),
    "growth": ("growth",),
    "paid_media": ("paid_media", "paidmedia", "paid-media"),
    "automation": ("automation",),
    "autopilot": ("autopilot",),
    "action_center": ("action_center", "action-center", "actioncenter"),
    "system": ("diagnostic", "system"),
    "uat": ("uat", "acceptance"),
    "release": ("release", "rollback"),
}

SOURCE_SUFFIXES = {".py", ".js", ".html", ".css", ".sh", ".swift", ".json", ".md"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_named(root: Path, name: str) -> list[Path]:
    return [p for p in root.rglob(name) if p.is_file()]


def searchable_paths(root: Path) -> list[str]:
    values: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES:
            values.append(p.relative_to(root).as_posix().lower())
    return values


def audit(root: Path, provenance: Path) -> dict:
    root = root.expanduser().resolve()
    provenance = provenance.expanduser().resolve()
    problems: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        return {"status": "BLOCKED", "problems": [f"payload root missing: {root}"]}
    if not provenance.is_file():
        return {"status": "BLOCKED", "problems": [f"provenance missing: {provenance}"]}

    try:
        prov = load_json(provenance)
    except Exception as exc:
        return {"status": "BLOCKED", "problems": [f"invalid provenance: {exc}"]}

    if prov.get("version") != EXPECTED_VERSION:
        problems.append(f"version mismatch: {prov.get('version')!r}")
    if prov.get("sha256") != EXPECTED_SHA256:
        problems.append("source SHA-256 does not match certified Wave 21")
    if prov.get("zip_crc") != "PASS":
        problems.append("source ZIP CRC is not PASS")

    members = int(prov.get("members", 0) or 0)
    if members < MIN_CERTIFIED_MANIFEST_ENTRIES:
        problems.append(
            f"payload provenance reports only {members} ZIP members; certified manifest baseline is {MIN_CERTIFIED_MANIFEST_ENTRIES}"
        )

    files = [p for p in root.rglob("*") if p.is_file()]
    if len(files) < MIN_CERTIFIED_MANIFEST_ENTRIES:
        problems.append(
            f"payload contains only {len(files)} files; expected at least {MIN_CERTIFIED_MANIFEST_ENTRIES} from certified Wave 21"
        )

    for filename, purpose in REQUIRED_FILENAMES.items():
        matches = find_named(root, filename)
        if not matches:
            problems.append(f"missing {purpose}: {filename}")
        else:
            mode = matches[0].stat().st_mode
            if not (mode & stat.S_IXUSR):
                problems.append(f"required launcher is not executable: {matches[0].relative_to(root)}")

    installers = [p for name in INSTALLER_ALTERNATIVES for p in find_named(root, name)]
    if not installers:
        problems.append("missing canonical macOS installer")
    elif not any(p.stat().st_mode & stat.S_IXUSR for p in installers):
        problems.append("macOS installer exists but is not executable")

    suffix_counts = {}
    for suffix in (".py", ".js", ".html", ".sh", ".swift"):
        suffix_counts[suffix] = sum(1 for p in files if p.suffix.lower() == suffix)

    if suffix_counts[".py"] == 0:
        problems.append("no Python runtime/source found")
    if suffix_counts[".js"] == 0:
        problems.append("no JavaScript frontend/runtime found")
    if suffix_counts[".html"] == 0:
        problems.append("no HTML frontend found")
    if suffix_counts[".sh"] == 0:
        problems.append("no shell launch/install scripts found")
    if suffix_counts[".swift"] == 0:
        problems.append("no Swift Security.framework helper source found")

    paths = searchable_paths(root)
    joined = "\n".join(paths)
    surfaces = {}
    for surface, tokens in SURFACE_TOKENS.items():
        present = any(token in joined for token in tokens)
        surfaces[surface] = "PRESENT_BY_PATH" if present else "NOT_PROVEN"
        if not present:
            problems.append(f"certified product surface not proven in payload paths: {surface}")

    contamination = []
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        parts = set(p.parts)
        if "__pycache__" in parts or "node_modules" in parts or ".git" in parts:
            contamination.append(rel)
        if p.is_file() and p.suffix.lower() in {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db"}:
            contamination.append(rel)
    if contamination:
        problems.append(f"source/runtime contamination detected ({len(contamination)} paths)")

    return {
        "schema": "binario.marketing.full-mac-payload-audit.v1",
        "status": "PASS" if not problems else "BLOCKED",
        "baseline": {"version": EXPECTED_VERSION, "sha256": EXPECTED_SHA256},
        "payload_root": str(root),
        "file_count": len(files),
        "provenance_members": members,
        "source_type_counts": suffix_counts,
        "surfaces": surfaces,
        "problems": problems,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit App13 before FULL MAC APP packaging")
    parser.add_argument("--root", type=Path, default=Path("app"))
    parser.add_argument("--provenance", type=Path, default=Path("provenance/WAVE21_IMPORT.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit(args.root, args.provenance)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.get("status") == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
