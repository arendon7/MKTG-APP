#!/usr/bin/env python3
"""Verify an extracted Wave 22 Target Mac Control Kit against its build manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

EXPECTED_BASELINE_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
SCHEMA = "binario.marketing.wave22.control-kit-manifest.v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_relative(value: str) -> PurePosixPath:
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe manifest path: {value!r}")
    return p


def build_manifest(root: Path, revision: str) -> dict:
    root = root.resolve()
    files = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "CONTROL_KIT_MANIFEST.json"):
        rel = path.relative_to(root).as_posix()
        files.append({
            "path": rel,
            "size": path.stat().st_size,
            "sha256": sha256(path),
            "executable": bool(path.stat().st_mode & 0o111),
        })
    return {
        "schema": SCHEMA,
        "baseline_sha256": EXPECTED_BASELINE_SHA256,
        "control_plane_revision": revision,
        "files": files,
    }


def verify(root: Path, manifest_path: Path) -> dict:
    root = root.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if manifest.get("schema") != SCHEMA:
        problems.append("manifest schema mismatch")
    if manifest.get("baseline_sha256") != EXPECTED_BASELINE_SHA256:
        problems.append("manifest baseline SHA mismatch")
    if not str(manifest.get("control_plane_revision") or "").strip():
        problems.append("manifest control-plane revision missing")

    seen: set[str] = set()
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            problems.append("invalid manifest file record")
            continue
        try:
            rel = safe_relative(str(item.get("path") or ""))
        except ValueError as exc:
            problems.append(str(exc))
            continue
        rel_s = rel.as_posix()
        if rel_s in seen:
            problems.append(f"duplicate manifest path: {rel_s}")
            continue
        seen.add(rel_s)
        path = root.joinpath(*rel.parts)
        if not path.is_file() or path.is_symlink():
            problems.append(f"missing/invalid file: {rel_s}")
            continue
        actual_size = path.stat().st_size
        actual_sha = sha256(path)
        if actual_size != item.get("size"):
            problems.append(f"size mismatch: {rel_s}")
        if actual_sha != item.get("sha256"):
            problems.append(f"SHA mismatch: {rel_s}")
        expected_exec = bool(item.get("executable"))
        actual_exec = bool(path.stat().st_mode & 0o111)
        if expected_exec and not actual_exec:
            problems.append(f"executable bit missing: {rel_s}")

    return {
        "schema": "binario.marketing.wave22.control-kit-verification.v1",
        "status": "PASS" if not problems else "BLOCKED",
        "control_plane_revision": manifest.get("control_plane_revision"),
        "baseline_sha256": manifest.get("baseline_sha256"),
        "verified_files": len(seen),
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify extracted Wave 22 control kit")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=Path("CONTROL_KIT_MANIFEST.json"))
    parser.add_argument("--build", action="store_true", help="build manifest instead of verifying")
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA", ""))
    args = parser.parse_args()
    try:
        if args.build:
            payload = build_manifest(args.root, args.revision)
            args.manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = {"status": "BUILT", "files": len(payload["files"]), "revision": payload["control_plane_revision"]}
        else:
            result = verify(args.root, args.manifest)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] in {"PASS", "BUILT"} else 3
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
