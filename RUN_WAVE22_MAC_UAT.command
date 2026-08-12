#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

EXPECTED_NAME="BINARIO_MARKETING_APP13_INTEGRATED_F15_F25_WAVE21_CORE_UAT_SOURCE.zip"
EXPECTED_SHA="d241696f9404a2373ed02a7c7c0246fa11b4a52afaedc4e1b60a03de2b441861"
STATUS_DIR="$ROOT/uat-evidence"
STATUS_FILE="$STATUS_DIR/WAVE22_UAT_STATUS.json"

say_step() { printf '\n==> %s\n' "$1"; }
fail() { printf '\nERROR: %s\n' "$1" >&2; printf '\nNo se modificó R22 ni se activó ningún provider.\n' >&2; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || fail "este launcher debe ejecutarse en macOS"
command -v python3 >/dev/null 2>&1 || fail "python3 no está disponible"

ARCHIVE="${1:-}"
if [[ -z "$ARCHIVE" ]]; then
  say_step "Buscando la release Wave 21 certificada"
  for base in "$ROOT" "$HOME/Downloads" "$HOME/Desktop" "$HOME/Documents"; do
    candidate="$base/$EXPECTED_NAME"
    if [[ -f "$candidate" ]]; then ARCHIVE="$candidate"; break; fi
  done
fi

[[ -n "$ARCHIVE" && -f "$ARCHIVE" ]] || fail "no encontré $EXPECTED_NAME. Pon el ZIP en Descargas, Escritorio, Documentos o junto a este launcher."

say_step "Verificando SHA-256 y preflight"
bash scripts/wave22_mac_preflight.sh "$ARCHIVE"

if [[ ! -d app || -z "$(find app -mindepth 1 -print -quit 2>/dev/null || true)" ]]; then
  say_step "Importando la Wave 21 exacta en app/"
  python3 scripts/import_wave21_release.py "$ARCHIVE"
else
  if [[ -f provenance/WAVE21_IMPORT.json ]]; then
    IMPORT_SHA="$(python3 - <<'PY'
import json
from pathlib import Path
p=Path('provenance/WAVE21_IMPORT.json')
try: print(json.loads(p.read_text()).get('sha256',''))
except Exception: print('')
PY
)"
    [[ "$IMPORT_SHA" == "$EXPECTED_SHA" ]] || fail "app/ ya contiene una importación cuya procedencia no coincide con Wave 21"
    say_step "La Wave 21 exacta ya estaba importada; no se sobrescribe"
  else
    fail "app/ no está vacío y no tiene provenance/WAVE21_IMPORT.json; me niego a mezclar fuentes"
  fi
fi

bash scripts/wave22_mac_preflight.sh "$ARCHIVE"

say_step "Inicializando/preservando estado UAT gobernado"
python3 scripts/wave22_uat_operator.py --status "$STATUS_FILE" init >/dev/null
printf 'Estado: %s\n' "$STATUS_FILE"

say_step "Gate actual"
python3 scripts/evaluate_wave22_gate.py --status "$STATUS_FILE"

INSTALLER="$(find app -type f \( -name 'install_app13_uat_kit_macos.sh' -o -name 'install_app13_uat_operator_macos.sh' \) -print -quit 2>/dev/null || true)"
RUNNER="$(find app -type f -name 'run_app13_uat_kit.sh' -print -quit 2>/dev/null || true)"
[[ -n "$INSTALLER" ]] || fail "no encontré el instalador UAT dentro de la release importada"
[[ -n "$RUNNER" ]] || fail "no encontré run_app13_uat_kit.sh dentro de la release importada"
chmod +x "$INSTALLER" "$RUNNER" 2>/dev/null || true

say_step "Instalando el kit UAT aislado"
(cd "$(dirname "$INSTALLER")" && "./$(basename "$INSTALLER")")

say_step "Abriendo App13 para CORE_UAT"
(cd "$(dirname "$RUNNER")" && "./$(basename "$RUNNER")")

cat <<'EOF'

Wave 22 iniciada correctamente.

Dentro de App13:
1. Sistema → CORE UAT Preparation: CORE-007/008/009 deben estar READY.
2. Sistema → User Acceptance Testing → CORE_UAT.
3. Ejecuta realmente CORE-007, CORE-008 y CORE-009.
4. Guarda evidencia concreta de cada ejecución.

Registro gobernado desde esta carpeta:
  python3 scripts/wave22_uat_operator.py record CORE-007 PASS --actor "OPERADOR" --evidence "ruta/evidencia" --note "qué ocurrió"

Si falla:
  python3 scripts/wave22_uat_operator.py defect-open W22-001 P1 CORE-007 --actor "OPERADOR" --summary "defecto reproducible"
  python3 scripts/wave22_uat_operator.py record CORE-007 FAIL --actor "OPERADOR" --evidence "ruta/evidencia" --note "qué falló" --defect-id W22-001

Firma independiente (otro actor):
  python3 scripts/wave22_uat_operator.py sign core --actor "REVISOR"

Consultar gate:
  python3 scripts/evaluate_wave22_gate.py

Empaquetar evidencia saneada:
  python3 scripts/package_wave22_evidence.py <carpeta-evidencia> --status-json uat-evidence/WAVE22_UAT_STATUS.json

R22 permanece UNBOUND y providers live permanecen bloqueados.
EOF
