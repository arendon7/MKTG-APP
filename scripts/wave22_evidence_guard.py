#!/usr/bin/env python3
"""Inspect a Wave 22 UAT evidence bundle before it is shared.

The guard is intentionally conservative: it never rewrites evidence. It hashes every
regular file and blocks obvious credential material, symlinks, or risky filenames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RISKY_FILENAMES = (
    re.compile(r"(^|/)\.env($|\.)", re.I),
    re.compile(r"credentials?.*\.json$", re.I),
    re.compile(r"secrets?.*\.json$", re.I),
    re.compile(r"\.(pem|key|p12|pfx)$", re.I),
)
SECRET_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("authorization", re.compile(r"(?i)authorization\s*[:=]\s*(?:bearer\s+)?[A-Za-z0-9._~+/=-]{12,}")),
    ("api_key", re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{8,}")),
)
TEXT_SCAN_LIMIT = 5 * 1024 * 1024


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_file(path: Path, root: Path) -> dict:
    rel = path.relative_to(root).as_posix() if path != root else path.name
    record = {
        "path": rel,
        "size": path.stat().st_size,
        "sha256": file_sha256(path),
        "findings": [],
    }
    for pattern in RISKY_FILENAMES:
        if pattern.search(rel):
            record["findings"].append("risky_filename")
            break

    if record["size"] <= TEXT_SCAN_LIMIT:
        data = path.read_bytes()
        text = data.decode("utf-8", errors="ignore")
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                record["findings"].append(label)
    return record


def inspect(target: Path) -> dict:
    target = target.expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(target)

    if target.is_symlink():
        return {
            "target": str(target),
            "status": "BLOCKED",
            "findings": [{"path": target.name, "findings": ["symlink_target"]}],
            "files": [],
        }

    root = target if target.is_dir() else target.parent
    paths = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.is_file() or p.is_symlink())
    files = []
    findings = []
    for path in paths:
        rel = path.relative_to(root).as_posix() if path != root else path.name
        if path.is_symlink():
            finding = {"path": rel, "findings": ["symlink"]}
            findings.append(finding)
            continue
        record = inspect_file(path, root)
        files.append(record)
        if record["findings"]:
            findings.append({"path": record["path"], "findings": record["findings"]})

    return {
        "target": str(target),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not findings else "BLOCKED",
        "file_count": len(files),
        "findings": findings,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard UAT evidence before sharing it")
    parser.add_argument("target", type=Path, help="file or directory containing UAT evidence")
    parser.add_argument("--manifest", type=Path, help="optional JSON output path")
    args = parser.parse_args()

    try:
        result = inspect(args.target)
    except FileNotFoundError as exc:
        print(f"ERROR: evidence target not found: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        args.manifest.expanduser().resolve().write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
