#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

EXPECTED_SHA="d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
ARCHIVE="${1:-}"
CONTROL_RUNTIME="${WAVE22_CONTROL_RUNTIME:-$HOME/Library/Application Support/Binario IA/Wave22/runtime}"
PYTHON_BIN="${WAVE22_PYTHON_BIN:-}"

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$1"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "Wave 22 Target Mac UAT must run on macOS"
pass "macOS $(sw_vers -productVersion) / $(uname -m)"

if [[ -z "$PYTHON_BIN" ]]; then
  "$ROOT/scripts/bootstrap_full_mac_python.sh" --target "$CONTROL_RUNTIME" || fail "pinned embedded CPython bootstrap failed"
  PYTHON_BIN="$CONTROL_RUNTIME/bin/python3"
fi
[[ -x "$PYTHON_BIN" ]] || fail "embedded CPython is unavailable: $PYTHON_BIN"
pass "$("$PYTHON_BIN" -I -B --version 2>&1)"

FREE_KB="$(df -Pk "$ROOT" | awk 'NR==2 {print $4}')"
[[ "${FREE_KB:-0}" -ge 1048576 ]] || fail "less than 1 GiB free in working filesystem"
pass "disk headroom >= 1 GiB"

if [[ -n "$ARCHIVE" ]]; then
  [[ -f "$ARCHIVE" ]] || fail "release ZIP not found: $ARCHIVE"
  ACTUAL_SHA="$(/usr/bin/shasum -a 256 "$ARCHIVE" | awk '{print $1}')"
  [[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || fail "Wave 21 SHA mismatch: $ACTUAL_SHA"
  pass "exact Wave 21 SHA-256"
  "$PYTHON_BIN" -I -B scripts/import_wave21_release.py "$ARCHIVE" --dry-run
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
