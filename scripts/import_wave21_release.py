#!/usr/bin/env python3
"""Import the exact certified Wave 21 source archive into app/.

This is deliberately strict: a byte-different archive is rejected before extraction.
It also rejects unsafe ZIP paths, symlinks and known source-contamination patterns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

EXPECTED_NAME = "BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip"
EXPECTED_SHA256 = "d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
EXPECTED_VERSION = "0.5.5a1"
FORBIDDEN_PARTS = {"__pycache__", "node_modules", ".git"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".sqlite", ".sqlite3", ".db"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_member(info: zipfile.ZipInfo) -> PurePosixPath:
    name = info.filename.replace("\\", "/")
    p = PurePosixPath(name)
    if not name or name.startswith("/") or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe ZIP member: {info.filename!r}")
    if any(part in FORBIDDEN_PARTS for part in p.parts):
        raise ValueError(f"forbidden source contamination: {info.filename}")
    if p.suffix.lower() in FORBIDDEN_SUFFIXES:
        raise ValueError(f"forbidden runtime artifact: {info.filename}")
    mode = (info.external_attr >> 16) & 0xFFFF
    if mode and stat.S_ISLNK(mode):
        raise ValueError(f"symlink is not accepted in certified import: {info.filename}")
    return p


def extract_strict(archive: Path, target: Path) -> dict:
    with zipfile.ZipFile(archive, "r") as zf:
        bad_crc = zf.testzip()
        if bad_crc:
            raise ValueError(f"ZIP CRC failed at {bad_crc}")
        members = [(info, validate_member(info)) for info in zf.infolist()]

        with tempfile.TemporaryDirectory(prefix="mktg-wave21-") as tmp:
            tmp_root = Path(tmp)
            for info, rel in members:
                dest = tmp_root.joinpath(*rel.parts)
                if info.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                mode = (info.external_attr >> 16) & 0o7777
                if mode:
                    os.chmod(dest, mode)

            if target.exists():
                if not target.is_dir():
                    raise ValueError(f"target exists and is not a directory: {target}")
                if any(target.iterdir()):
                    raise ValueError(f"target is not empty: {target}")
                target.rmdir()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp_root), str(target))

    return {
        "archive": archive.name,
        "sha256": EXPECTED_SHA256,
        "version": EXPECTED_VERSION,
        "zip_crc": "PASS",
        "members": len(members),
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(target),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path, help="path to the exact Wave 21 source ZIP")
    parser.add_argument("--target", type=Path, default=Path("app"))
    parser.add_argument("--provenance", type=Path, default=Path("provenance/WAVE21_IMPORT.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    archive = args.archive.expanduser().resolve()
    if not archive.is_file():
        print(f"ERROR: archive not found: {archive}", file=sys.stderr)
        return 2
    if archive.name != EXPECTED_NAME:
        print(
            f"ERROR: unexpected Wave 21 archive name: {archive.name}; expected {EXPECTED_NAME}",
            file=sys.stderr,
        )
        return 3

    actual = sha256(archive)
    print(f"archive: {archive.name}")
    print(f"sha256 : {actual}")
    if actual != EXPECTED_SHA256:
        print("ERROR: Wave 21 SHA-256 mismatch; refusing import.", file=sys.stderr)
        return 3

    with zipfile.ZipFile(archive, "r") as zf:
        bad_crc = zf.testzip()
        if bad_crc:
            print(f"ERROR: ZIP CRC failed at {bad_crc}", file=sys.stderr)
            return 4
        for info in zf.infolist():
            validate_member(info)
        count = len(zf.infolist())

    print(f"ZIP CRC : PASS ({count} members)")
    if args.dry_run:
        print("DRY RUN  : PASS; no files extracted")
        return 0

    target = args.target.resolve()
    provenance = args.provenance.resolve()
    result = extract_strict(archive, target)
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"IMPORTED : {target}")
    print(f"PROVENANCE: {provenance}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
