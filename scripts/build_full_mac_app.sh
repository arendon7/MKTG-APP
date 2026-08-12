#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_SOURCE="${APP13_SOURCE:-$ROOT/app}"
PROVENANCE="${APP13_PROVENANCE:-$ROOT/provenance/WAVE21_IMPORT.json}"
OUT_DIR="${BINARIO_MAC_DIST:-$ROOT/dist/full-mac}"
APP_NAME="Binario Marketing IA.app"
BUNDLE="$OUT_DIR/$APP_NAME"
CONTENTS="$BUNDLE/Contents"
RESOURCES="$CONTENTS/Resources"
MACOS="$CONTENTS/MacOS"
APP_PAYLOAD="$RESOURCES/App13"
RUNTIME_PAYLOAD="$RESOURCES/runtime"
RUNTIME_STAGE="$OUT_DIR/.runtime-bootstrap"

fail() { printf 'FULL MAC APP BUILD BLOCKED: %s\n' "$1" >&2; exit 3; }
pass() { printf 'PASS: %s\n' "$1"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "production .app build must run on macOS"
mkdir -p "$OUT_DIR"
rm -rf "$RUNTIME_STAGE"
trap 'rm -rf "$RUNTIME_STAGE"' EXIT

"$ROOT/scripts/bootstrap_full_mac_python.sh" --target "$RUNTIME_STAGE"
PYTHON_BIN="$RUNTIME_STAGE/bin/python3"
[[ -x "$PYTHON_BIN" ]] || fail "pinned embedded CPython bootstrap did not produce bin/python3"

"$PYTHON_BIN" -I -B scripts/audit_full_app_payload.py \
  --root "$APP_SOURCE" \
  --provenance "$PROVENANCE" \
  --output "$OUT_DIR/PAYLOAD_AUDIT.json"
pass "certified App13 payload audit"

rm -rf "$BUNDLE"
mkdir -p "$MACOS" "$RESOURCES"

# Copy the complete certified App13 payload. Do not curate/subset modules.
/usr/bin/ditto "$APP_SOURCE" "$APP_PAYLOAD"
/usr/bin/ditto "$RUNTIME_STAGE" "$RUNTIME_PAYLOAD"
BUNDLE_PYTHON="$RUNTIME_PAYLOAD/bin/python3"
[[ -x "$BUNDLE_PYTHON" ]] || fail "embedded CPython missing after bundle copy"

RUNNER_ABS="$(/usr/bin/find "$APP_PAYLOAD" -type f -name 'run_app13_uat_kit.sh' -print -quit)"
[[ -n "$RUNNER_ABS" ]] || fail "canonical App13 runner not found after copy"
RUNNER_REL="${RUNNER_ABS#"$APP_PAYLOAD"/}"
[[ "$RUNNER_REL" != "$RUNNER_ABS" ]] || fail "canonical App13 runner resolved outside copied payload"

cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Binario Marketing IA</string>
  <key>CFBundleDisplayName</key><string>Binario Marketing IA</string>
  <key>CFBundleIdentifier</key><string>com.sistemabinario.marketingia</string>
  <key>CFBundleVersion</key><string>0.5.5.1</string>
  <key>CFBundleShortVersionString</key><string>0.5.5a1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>binario-marketing</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

cat > "$MACOS/binario-marketing" <<EOF
#!/bin/bash
set -euo pipefail
SELF_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
CONTENTS="\$(cd "\$SELF_DIR/.." && pwd)"
RESOURCES="\$CONTENTS/Resources"
APP13="\$RESOURCES/App13"
RUNTIME="\$RESOURCES/runtime"
PYTHON="\$RUNTIME/bin/python3"
DATA_HOME="\$HOME/Library/Application Support/Binario IA/Marketing Growth"
LOG_DIR="\$DATA_HOME/logs"
[[ -x "\$PYTHON" ]] || { printf 'Embedded Python runtime is unavailable.\n' >&2; exit 71; }
mkdir -p "\$DATA_HOME" "\$LOG_DIR"
chmod 700 "\$DATA_HOME" 2>/dev/null || true
export PATH="\$RUNTIME/bin:/usr/bin:/bin"
unset PYTHONHOME PYTHONPATH
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export BINARIO_MARKETING_APP_HOME="\$DATA_HOME"
export BINARIO_MARKETING_BUNDLE="\$CONTENTS"
cd "\$APP13/$(dirname "$RUNNER_REL")"
exec "./$(basename "$RUNNER_REL")" >>"\$LOG_DIR/launcher.log" 2>&1
EOF
chmod 755 "$MACOS/binario-marketing"

# Preserve critical source executability after ditto.
/usr/bin/find "$APP_PAYLOAD" -type f \( -name '*.sh' -o -name '*.command' \) -exec chmod 755 {} + 2>/dev/null || true

/usr/bin/plutil -lint "$CONTENTS/Info.plist" >/dev/null

"$BUNDLE_PYTHON" -I -B scripts/audit_full_mac_bundle.py "$BUNDLE" \
  --source-audit "$OUT_DIR/PAYLOAD_AUDIT.json" \
  --output "$OUT_DIR/FULL_MAC_BUNDLE_AUDIT.json"
pass "FULL MAC bundle audit"

# Ad-hoc signing is the final mutation of the local .app before packaging.
[[ -x /usr/bin/codesign ]] || fail "codesign is required on the target Mac"
/usr/bin/codesign --force --deep --sign - "$BUNDLE"
/usr/bin/codesign --verify --deep --strict "$BUNDLE"
pass "ad-hoc code signature"

cat > "$OUT_DIR/INSTALL_BINARIO_MARKETING.command" <<'INSTALL'
#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$ROOT/Binario Marketing IA.app"
TARGET="$HOME/Applications/Binario Marketing IA.app"
[[ -d "$SOURCE" ]] || { echo "No encuentro $SOURCE" >&2; exit 2; }
mkdir -p "$HOME/Applications"
rm -rf "$TARGET.new"
/usr/bin/ditto "$SOURCE" "$TARGET.new"
rm -rf "$TARGET"
mv "$TARGET.new" "$TARGET"
chmod +x "$TARGET/Contents/MacOS/binario-marketing"
/usr/bin/open "$TARGET"
echo "Instalada: $TARGET"
INSTALL
chmod 755 "$OUT_DIR/INSTALL_BINARIO_MARKETING.command"

rm -rf "$RUNTIME_STAGE"
trap - EXIT

# Package while preserving macOS metadata/permissions.
(
  cd "$OUT_DIR"
  rm -f BINARIO_MARKETING_FULL_MAC_APP.zip BINARIO_MARKETING_FULL_MAC_APP.zip.sha256
  /usr/bin/ditto -c -k --sequesterRsrc --keepParent "$APP_NAME" BINARIO_MARKETING_FULL_MAC_APP.zip
  /usr/bin/shasum -a 256 BINARIO_MARKETING_FULL_MAC_APP.zip > BINARIO_MARKETING_FULL_MAC_APP.zip.sha256
)

printf '\nFULL MAC APP BUILD: PASS\n'
printf 'Bundle: %s\n' "$BUNDLE"
printf 'Installer: %s\n' "$OUT_DIR/INSTALL_BINARIO_MARKETING.command"
printf 'Archive: %s\n' "$OUT_DIR/BINARIO_MARKETING_FULL_MAC_APP.zip"
cat "$OUT_DIR/BINARIO_MARKETING_FULL_MAC_APP.zip.sha256"
