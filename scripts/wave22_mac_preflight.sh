#!/bin/bash
set -euo pipefail

EXPECTED_SHA="d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
ARCHIVE="${1:-}"

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "Wave 22 Target Mac UAT must run on macOS"
pass "macOS $(sw_vers -productVersion) / $(uname -m)"

command -v python3 >/dev/null 2>&1 || fail "python3 is required"
pass "$(python3 --version 2>&1)"

FREE_KB="$(df -Pk . | awk 'NR==2 {print $4}')"
[[ "${FREE_KB:-0}" -ge 1048576 ]] || fail "less than 1 GiB free in working filesystem"
pass "disk headroom >= 1 GiB"

if [[ -n "$ARCHIVE" ]]; then
  [[ -f "$ARCHIVE" ]] || fail "release ZIP not found: $ARCHIVE"
  ACTUAL_SHA="$(python3 - "$ARCHIVE" <<'PY'
import hashlib, sys
p=sys.argv[1]
h=hashlib.sha256()
with open(p,'rb') as f:
    for b in iter(lambda:f.read(1024*1024), b''):
        h.update(b)
print(h.hexdigest())
PY
)"
  [[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || fail "Wave 21 SHA mismatch: $ACTUAL_SHA"
  pass "exact Wave 21 SHA-256"
  python3 scripts/import_wave21_release.py "$ARCHIVE" --dry-run
fi

if [[ -d app ]]; then
  INSTALLER="$(find app -type f \( -name 'install_app13_uat_kit_macos.sh' -o -name 'install_app13_uat_operator_macos.sh' \) -print -quit 2>/dev/null || true)"
  RUNNER="$(find app -type f -name 'run_app13_uat_kit.sh' -print -quit 2>/dev/null || true)"
  [[ -n "$INSTALLER" ]] || fail "app/ exists but the macOS UAT installer was not found"
  [[ -n "$RUNNER" ]] || fail "app/ exists but run_app13_uat_kit.sh was not found"
  pass "UAT installer found: $INSTALLER"
  pass "UAT runner found: $RUNNER"
fi

printf '\nWave 22 preflight complete. R22/provider activation is intentionally out of scope.\n'
